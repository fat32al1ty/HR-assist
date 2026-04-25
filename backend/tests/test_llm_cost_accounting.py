"""Phase 5.2.4 — Unit-style integration tests for daily_user_llm_cost_usd.

Real DB rows are inserted for ResumeAudit and VacancyStrategy, then we assert
the helper sums them correctly per-user and ignores yesterday's rows.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy
from app.services.llm_cost_accounting import daily_user_llm_cost_usd


def _make_user(db, suffix: str) -> User:
    user = User(
        email=f"cost-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name="Cost Test User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resume(db, user_id: int) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={"target_role": "Dev"},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def _make_vacancy(db) -> Vacancy:
    uid = uuid.uuid4().hex[:12]
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.com/jobs/{uid}",
        title="Test Job",
        company="TestCo",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    from app.models.vacancy_profile import VacancyProfile

    vp = VacancyProfile(
        vacancy_id=vacancy.id,
        profile={"title": "Test Job", "must_have_skills": ["Python"]},
        canonical_text="Job: Test Job",
        qdrant_collection="test_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp)
    db.commit()
    return vacancy


class DailyUserLlmCostTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        s1 = uuid.uuid4().hex[:10]
        s2 = uuid.uuid4().hex[:10]
        self.user1 = _make_user(self.db, s1)
        self.user2 = _make_user(self.db, s2)
        self.resume1 = _make_resume(self.db, self.user1.id)
        self.resume2 = _make_resume(self.db, self.user2.id)
        self.vacancy = _make_vacancy(self.db)
        self.today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    def tearDown(self) -> None:
        self.db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == self.resume1.id))
        self.db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == self.resume2.id))
        self.db.execute(delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume1.id))
        self.db.execute(delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume2.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume1.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume2.id))
        self.db.execute(delete(VacancyProfile).where(VacancyProfile.vacancy_id == self.vacancy.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id == self.user1.id))
        self.db.execute(delete(User).where(User.id == self.user2.id))
        self.db.commit()
        self.db.close()

    def _add_audit(self, resume_id: int, cost: float, at: datetime) -> None:
        audit = ResumeAudit(
            resume_id=resume_id,
            audit_json={"dummy": True},
            prompt_version="audit-v1",
            computed_at=at,
            cost_usd=cost,
        )
        self.db.add(audit)
        self.db.commit()

    def _add_strategy(
        self,
        resume_id: int,
        vacancy_id: int,
        cost: float | None,
        at: datetime,
    ) -> None:
        row = VacancyStrategy(
            resume_id=resume_id,
            vacancy_id=vacancy_id,
            prompt_version="strategy-v1",
            strategy_json={"match_highlights": [], "gap_mitigations": [], "cover_letter_draft": ""},
            cost_usd=cost,
            template_mode=cost is None,
            computed_at=at,
        )
        self.db.add(row)
        self.db.commit()

    def test_sums_audit_and_strategy_costs_for_correct_user(self) -> None:
        now = datetime.now(UTC)
        self._add_audit(self.resume1.id, 0.01, now)
        self._add_strategy(self.resume1.id, self.vacancy.id, 0.02, now)
        # user2 gets a different audit — must not bleed into user1's sum
        self._add_audit(self.resume2.id, 0.50, now)

        total = daily_user_llm_cost_usd(self.db, self.user1.id, self.today)
        self.assertAlmostEqual(total, 0.03, places=5)

    def test_excludes_yesterdays_rows(self) -> None:
        yesterday = datetime.now(UTC) - timedelta(days=1)
        now = datetime.now(UTC)
        self._add_audit(self.resume1.id, 0.10, yesterday)
        self._add_strategy(self.resume1.id, self.vacancy.id, 0.05, now)

        total = daily_user_llm_cost_usd(self.db, self.user1.id, self.today)
        # Only the strategy row from today should be counted
        self.assertAlmostEqual(total, 0.05, places=5)

    def test_returns_zero_when_no_rows(self) -> None:
        total = daily_user_llm_cost_usd(self.db, self.user1.id, self.today)
        self.assertAlmostEqual(total, 0.0, places=5)

    def test_user2_costs_do_not_appear_in_user1_sum(self) -> None:
        now = datetime.now(UTC)
        self._add_audit(self.resume2.id, 99.99, now)
        total = daily_user_llm_cost_usd(self.db, self.user1.id, self.today)
        self.assertAlmostEqual(total, 0.0, places=5)

    def test_template_mode_null_cost_counts_as_zero(self) -> None:
        # Template-mode strategy rows persist `cost_usd=NULL`; they must be
        # treated as 0 by the helper, not raise / not be skipped.
        now = datetime.now(UTC)
        self._add_audit(self.resume1.id, 0.01, now)
        self._add_strategy(self.resume1.id, self.vacancy.id, None, now)

        total = daily_user_llm_cost_usd(self.db, self.user1.id, self.today)
        self.assertAlmostEqual(total, 0.01, places=5)


if __name__ == "__main__":
    unittest.main()
