"""API + schema tests for POST /resumes/{id}/profile-confirm (Phase 1.2).

Network-free: the DB writes go through a real SessionLocal but Qdrant re-embed
is monkey-patched so these tests don't call OpenAI.
"""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete

from app.api.routes.resumes import confirm_resume_profile
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import (
    TARGET_ROLE_MAX,
    TOP_SKILLS_MAX,
    ResumeAnalysisUpdate,
    ResumePreferenceUpdate,
    ResumeProfileConfirmRequest,
)


class ResumeAnalysisUpdateSchemaTest(unittest.TestCase):
    def test_empty_update_is_valid_but_zero_dump(self) -> None:
        payload = ResumeAnalysisUpdate()
        self.assertEqual(payload.model_dump(exclude_unset=True), {})

    def test_rejects_overlong_target_role(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeAnalysisUpdate(target_role="x" * (TARGET_ROLE_MAX + 1))

    def test_top_skills_are_trimmed(self) -> None:
        payload = ResumeAnalysisUpdate(top_skills=["  Python ", "", "SRE   "])
        self.assertEqual(payload.top_skills, ["Python", "SRE"])

    def test_rejects_too_many_top_skills(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeAnalysisUpdate(top_skills=[f"skill-{i}" for i in range(TOP_SKILLS_MAX + 1)])

    def test_rejects_bad_seniority(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeAnalysisUpdate(seniority="principal")

    def test_years_experience_out_of_range(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeAnalysisUpdate(total_experience_years=-1)
        with self.assertRaises(ValidationError):
            ResumeAnalysisUpdate(total_experience_years=200)

    def test_empty_target_role_becomes_none(self) -> None:
        payload = ResumeAnalysisUpdate(target_role="   ")
        self.assertIsNone(payload.target_role)


class ResumeProfileConfirmEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"confirm-{self.suffix}@example.com",
            hashed_password=hash_password("Str0ngPass!"),
            full_name="Confirm Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename=f"cv-{self.suffix}.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/cv-{self.suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "API",
                "seniority": "middle",
                "total_experience_years": 3,
                "hard_skills": ["Python", "Postgres"],
                "home_city": "Москва",
            },
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _call(self, payload: ResumeProfileConfirmRequest):
        with patch("app.api.routes.resumes.persist_resume_profile", return_value=None) as reembed:
            result = confirm_resume_profile(
                resume_id=self.resume.id,
                payload=payload,
                current_user=self.user,
                db=self.db,
            )
            return result, reembed

    def test_missing_resume_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            confirm_resume_profile(
                resume_id=999999,
                payload=ResumeProfileConfirmRequest(
                    analysis_updates=ResumeAnalysisUpdate(target_role="X")
                ),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_empty_request_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            confirm_resume_profile(
                resume_id=self.resume.id,
                payload=ResumeProfileConfirmRequest(),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_part_a_only_merges_into_analysis(self) -> None:
        payload = ResumeProfileConfirmRequest(
            analysis_updates=ResumeAnalysisUpdate(
                target_role="Senior Backend",
                seniority="senior",
                total_experience_years=5,
                top_skills=["Python", "FastAPI"],
            )
        )
        result, reembed = self._call(payload)
        reembed.assert_called_once()
        # New analysis keeps untouched fields (specialization) and overrides the rest.
        analysis = result.resume.analysis
        assert analysis is not None
        self.assertEqual(analysis["target_role"], "Senior Backend")
        self.assertEqual(analysis["seniority"], "senior")
        self.assertEqual(analysis["total_experience_years"], 5)
        self.assertEqual(analysis["hard_skills"], ["Python", "FastAPI"])
        self.assertEqual(analysis["specialization"], "API")

    def test_part_b_only_updates_user_prefs(self) -> None:
        payload = ResumeProfileConfirmRequest(
            preference_updates=ResumePreferenceUpdate(
                preferred_work_format="remote",
                home_city="Санкт-Петербург",
                preferred_titles=["Senior Backend"],
            )
        )
        result, reembed = self._call(payload)
        # No analysis change → no re-embed call.
        reembed.assert_not_called()
        self.assertEqual(result.preferences["preferred_work_format"], "remote")
        self.assertEqual(result.preferences["home_city"], "Санкт-Петербург")
        self.assertEqual(result.preferences["preferred_titles"], ["Senior Backend"])
        # DB roundtrip.
        self.db.expire_all()
        fresh = self.db.get(User, self.user.id)
        assert fresh is not None
        self.assertEqual(fresh.preferred_work_format, "remote")
        self.assertEqual(fresh.home_city, "Санкт-Петербург")

    def test_combined_save_applies_both_halves_atomically(self) -> None:
        payload = ResumeProfileConfirmRequest(
            analysis_updates=ResumeAnalysisUpdate(
                target_role="Senior Backend",
                specialization="API / Platform",
            ),
            preference_updates=ResumePreferenceUpdate(
                preferred_work_format="hybrid",
                relocation_mode="any_city",
            ),
        )
        result, reembed = self._call(payload)
        reembed.assert_called_once()
        assert result.resume.analysis is not None
        self.assertEqual(result.resume.analysis["target_role"], "Senior Backend")
        self.assertEqual(result.resume.analysis["specialization"], "API / Platform")
        self.assertEqual(result.preferences["preferred_work_format"], "hybrid")
        self.assertEqual(result.preferences["relocation_mode"], "any_city")

    def test_clear_home_city_flag_sets_null(self) -> None:
        # First set a city.
        self._call(
            ResumeProfileConfirmRequest(
                preference_updates=ResumePreferenceUpdate(home_city="Казань"),
            )
        )
        # Now clear it.
        result, _ = self._call(
            ResumeProfileConfirmRequest(
                preference_updates=ResumePreferenceUpdate(clear_home_city=True),
            )
        )
        self.assertIsNone(result.preferences["home_city"])

    def test_analysis_patch_does_not_overwrite_unrelated_keys(self) -> None:
        payload = ResumeProfileConfirmRequest(
            analysis_updates=ResumeAnalysisUpdate(target_role="Senior Backend")
        )
        result, _ = self._call(payload)
        assert result.resume.analysis is not None
        # home_city came from the original analysis and must survive a partial update.
        self.assertEqual(result.resume.analysis.get("home_city"), "Москва")


if __name__ == "__main__":
    unittest.main()
