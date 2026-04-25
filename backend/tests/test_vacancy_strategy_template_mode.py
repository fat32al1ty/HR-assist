"""Phase 5.2.4 — Pure DB integration for the vacancy_strategy template path.

No LLM calls are made; feature_vacancy_strategy_template_mode_enabled is forced True.
"""

from __future__ import annotations

import re
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy
from app.services import vacancy_strategy as vs_service

_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w.\-]+", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-()\*]*\d{3}[\s\-()\*]*\d{3}[\s\-()\*]*\d{2}[\s\-()\*]*\d{2}",
    re.IGNORECASE,
)
_CYR_NAME_RE = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+")


def _make_user(db, suffix: str) -> User:
    user = User(
        email=f"vs-tmpl-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name="Test VS User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resume(db, user_id: int, skills: list[str], experience: list[dict]) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={"target_role": "Python Developer", "seniority": "middle"},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    profile = ResumeProfile(
        resume_id=resume.id,
        user_id=user_id,
        profile={
            "role_family": "software_engineering",
            "seniority": "middle",
            "seniority_confidence": 0.85,
            "total_experience_years": 3,
            "skills": skills,
            "hard_skills": skills,
            "experience": experience,
        },
        canonical_text="Target role: Python Developer\nSkills: " + ", ".join(skills),
        qdrant_collection="test_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return resume


def _make_vacancy(db, must_have_skills: list[str], title: str = "Senior Python Dev") -> Vacancy:
    uid = uuid.uuid4().hex[:12]
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.com/jobs/{uid}",
        title=title,
        company="Acme Corp",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    vp = VacancyProfile(
        vacancy_id=vacancy.id,
        profile={
            "title": title,
            "must_have_skills": must_have_skills,
            "role_family": "software_engineering",
        },
        canonical_text=f"Job: {title}\nRequired: " + ", ".join(must_have_skills),
        qdrant_collection="test_vac_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vacancy


class VacancyStrategyTemplateModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(
            self.db,
            self.user.id,
            skills=["Python", "FastAPI", "PostgreSQL"],
            experience=[
                {
                    "company": "Acme",
                    "role": "Backend Developer",
                    "highlights": [
                        "Built Python microservices",
                        "Optimized FastAPI endpoints",
                        "Maintained PostgreSQL schemas",
                    ],
                }
            ],
        )
        self.vacancy = _make_vacancy(
            self.db,
            must_have_skills=["Python", "Docker", "Kubernetes"],
            title="Backend Engineer",
        )

    def tearDown(self) -> None:
        self.db.execute(delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume.id))
        self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(VacancyProfile).where(VacancyProfile.vacancy_id == self.vacancy.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _compute(self, force: bool = False):
        with patch("app.services.vacancy_strategy.settings") as mock_settings:
            mock_settings.feature_vacancy_strategy_enabled = True
            mock_settings.feature_vacancy_strategy_template_mode_enabled = True
            mock_settings.vacancy_strategy_cache_ttl_days = 30
            mock_settings.openai_api_key = None
            mock_settings.vacancy_strategy_cost_cap_usd_per_day = 1.0
            return vs_service.compute_strategy(
                self.db, self.resume.id, self.vacancy.id, self.user.id, force=force
            )

    def test_template_mode_returns_vacancystrategyout_with_template_mode_true(self) -> None:
        out = self._compute()
        self.assertTrue(out.template_mode)
        self.assertEqual(out.resume_id, self.resume.id)
        self.assertEqual(out.vacancy_id, self.vacancy.id)

    def test_match_highlights_nonempty_when_experience_overlaps_must_have_skills(self) -> None:
        out = self._compute()
        # Resume has Python in both skills and experience highlights; vacancy requires Python
        self.assertGreater(len(out.match_highlights), 0)

    def test_gap_mitigations_lists_at_most_2_items_with_vacancy_requirements_not_in_skills(
        self,
    ) -> None:
        out = self._compute()
        self.assertLessEqual(len(out.gap_mitigations), 2)
        vac_profile_row = self.db.scalar(
            select(VacancyProfile).where(VacancyProfile.vacancy_id == self.vacancy.id)
        )
        must_haves = {s.lower() for s in vac_profile_row.profile.get("must_have_skills", [])}
        resume_profile_row = self.db.scalar(
            select(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id)
        )
        resume_skills = {
            s.lower()
            for s in (
                resume_profile_row.profile.get("skills")
                or resume_profile_row.profile.get("hard_skills")
                or []
            )
        }
        for gm in out.gap_mitigations:
            self.assertIn(gm.requirement.lower(), must_haves)
            self.assertNotIn(gm.requirement.lower(), resume_skills)

    def test_cover_letter_draft_length_at_most_1200_chars(self) -> None:
        out = self._compute()
        self.assertLessEqual(len(out.cover_letter_draft), 1200)

    def test_cover_letter_draft_contains_zero_pii_patterns(self) -> None:
        out = self._compute()
        text = out.cover_letter_draft
        emails = _EMAIL_RE.findall(text)
        phones = _PHONE_RE.findall(text)
        self.assertEqual(emails, [], f"Email PII found in cover letter: {emails}")
        self.assertEqual(phones, [], f"Phone PII found in cover letter: {phones}")

    def test_cache_second_call_does_not_create_new_row(self) -> None:
        self._compute()
        count_after_first = self.db.scalar(
            select(VacancyStrategy)
            .where(VacancyStrategy.resume_id == self.resume.id)
            .where(VacancyStrategy.vacancy_id == self.vacancy.id)
        )
        self.assertIsNotNone(count_after_first)

        # Second call — must serve from cache, not create duplicate row
        self._compute()
        all_rows = self.db.scalars(
            select(VacancyStrategy).where(
                VacancyStrategy.resume_id == self.resume.id,
                VacancyStrategy.vacancy_id == self.vacancy.id,
            )
        ).all()
        self.assertEqual(len(all_rows), 1, "Cache must not create a second row for same pair")

    def test_cost_usd_is_none_or_zero_in_template_mode(self) -> None:
        out = self._compute()
        # Verify via DB row that cost_usd is NULL (template mode incurs no cost)
        row = self.db.scalar(
            select(VacancyStrategy).where(
                VacancyStrategy.resume_id == self.resume.id,
                VacancyStrategy.vacancy_id == self.vacancy.id,
            )
        )
        self.assertIsNotNone(row)
        self.assertIsNone(row.cost_usd)


if __name__ == "__main__":
    unittest.main()
