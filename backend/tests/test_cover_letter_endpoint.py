"""POST /api/applications/{id}/cover-letter tests (Phase 1.5).

No network: `generate_cover_letter_text` is patched so the endpoint
never calls OpenAI. Covers the 24h cooldown, force-refresh, and the
required-resume / required-vacancy-context guards.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException, Request, Response
from sqlalchemy import delete

from app.api.routes.applications import (
    create_application_endpoint,
    draft_cover_letter_endpoint,
)
from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.models.application import Application
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy import Vacancy
from app.schemas.application import ApplicationCreateRequest, CoverLetterRequest

CANNED_LETTER = "Здравствуйте!\n\nЗаинтересовался вашей вакансией...\n\nС уважением."


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/applications/0/cover-letter",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 0),
        "query_string": b"",
    }
    return Request(scope)


class CoverLetterEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self._limiter_was_enabled = limiter.enabled
        limiter.enabled = False
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"letter-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Letter Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="resume.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/resume-{self.suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend engineer",
                "specialization": "Платформы данных",
                "total_experience_years": 6,
                "seniority": "senior",
                "summary": "Строил ETL и API на Python, работал с Kafka и Postgres.",
                "hard_skills": ["python", "postgres", "kafka"],
                "strengths": ["ownership", "mentoring"],
            },
        )
        self.db.add(self.resume)

        self.vacancy = Vacancy(
            source="test",
            source_url=f"https://example.test/vacancy/letter-{self.suffix}",
            title=f"Backend engineer {self.suffix}",
            company="Example Inc.",
            location="Москва",
            status="indexed",
            raw_text="Ищем senior backend на Python с опытом построения платформ данных.",
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.resume)
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(delete(Application).where(Application.user_id == self.user.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()
        limiter.enabled = self._limiter_was_enabled

    def _make_application(self) -> Application:
        result = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        row = self.db.get(Application, result.id)
        assert row is not None
        return row

    def test_first_call_generates_and_stores_letter(self) -> None:
        application = self._make_application()
        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value=CANNED_LETTER,
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=False,
                current_user=self.user,
                db=self.db,
            )
        self.assertFalse(response.cached)
        self.assertEqual(response.cover_letter_text, CANNED_LETTER)
        fake.assert_called_once()
        # Stored on the row.
        self.db.refresh(application)
        self.assertEqual(application.cover_letter_text, CANNED_LETTER)
        self.assertIsNotNone(application.cover_letter_generated_at)

    def test_second_call_within_24h_returns_cached(self) -> None:
        application = self._make_application()
        application.cover_letter_text = CANNED_LETTER
        application.cover_letter_generated_at = datetime.now(UTC) - timedelta(hours=1)
        self.db.add(application)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value="fresh letter",
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=False,
                current_user=self.user,
                db=self.db,
            )
        fake.assert_not_called()
        self.assertTrue(response.cached)
        self.assertEqual(response.cover_letter_text, CANNED_LETTER)

    def test_force_bypasses_cache(self) -> None:
        application = self._make_application()
        application.cover_letter_text = CANNED_LETTER
        application.cover_letter_generated_at = datetime.now(UTC) - timedelta(hours=1)
        self.db.add(application)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value="regenerated letter",
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=True,
                current_user=self.user,
                db=self.db,
            )
        fake.assert_called_once()
        self.assertFalse(response.cached)
        self.assertEqual(response.cover_letter_text, "regenerated letter")

    def test_cooldown_elapsed_allows_regeneration(self) -> None:
        application = self._make_application()
        application.cover_letter_text = "stale letter"
        application.cover_letter_generated_at = datetime.now(UTC) - timedelta(hours=25)
        self.db.add(application)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value="new letter",
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=False,
                current_user=self.user,
                db=self.db,
            )
        fake.assert_called_once()
        self.assertFalse(response.cached)
        self.assertEqual(response.cover_letter_text, "new letter")

    def test_other_user_cannot_generate(self) -> None:
        application = self._make_application()
        other = User(
            email=f"letter-other-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Other",
            is_active=True,
            email_verified=True,
        )
        self.db.add(other)
        self.db.commit()
        self.db.refresh(other)
        try:
            with self.assertRaises(HTTPException) as ctx:
                draft_cover_letter_endpoint(
                    request=_make_request(),
                    response=Response(),
                    application_id=application.id,
                    force=False,
                    current_user=other,
                    db=self.db,
                )
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            self.db.execute(delete(User).where(User.id == other.id))
            self.db.commit()

    def test_409_when_no_resume_with_analysis(self) -> None:
        application = self._make_application()
        self.resume.analysis = None
        self.db.add(self.resume)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value=CANNED_LETTER,
        ) as fake:
            with self.assertRaises(HTTPException) as ctx:
                draft_cover_letter_endpoint(
                    request=_make_request(),
                    response=Response(),
                    application_id=application.id,
                    force=False,
                    current_user=self.user,
                    db=self.db,
                )
        self.assertEqual(ctx.exception.status_code, 409)
        fake.assert_not_called()

    def test_400_when_no_vacancy_context(self) -> None:
        # Direct insert bypasses the create-endpoint title guard so we can
        # exercise the cover-letter route's own context check. Happens in
        # practice if the vacancy row was later deleted and the denormalized
        # title was cleared manually.
        row = Application(
            user_id=self.user.id,
            vacancy_id=None,
            status="draft",
            vacancy_title="",
            vacancy_company=None,
            source_url="",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value=CANNED_LETTER,
        ) as fake:
            with self.assertRaises(HTTPException) as ctx:
                draft_cover_letter_endpoint(
                    request=_make_request(),
                    response=Response(),
                    application_id=row.id,
                    force=False,
                    current_user=self.user,
                    db=self.db,
                )
        self.assertEqual(ctx.exception.status_code, 400)
        fake.assert_not_called()

    def test_extra_instructions_bypass_cooldown(self) -> None:
        # Fresh draft within the cooldown — would normally return cached, but
        # a non-empty refinement always forces regeneration.
        application = self._make_application()
        application.cover_letter_text = CANNED_LETTER
        application.cover_letter_generated_at = datetime.now(UTC) - timedelta(hours=1)
        self.db.add(application)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value="refined letter",
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=False,
                payload=CoverLetterRequest(
                    extra_instructions="ответь на вопросы анкеты: откуда узнал — LinkedIn"
                ),
                current_user=self.user,
                db=self.db,
            )
        fake.assert_called_once()
        self.assertFalse(response.cached)
        self.assertEqual(response.cover_letter_text, "refined letter")
        kwargs = fake.call_args.kwargs
        self.assertEqual(
            kwargs.get("extra_instructions"),
            "ответь на вопросы анкеты: откуда узнал — LinkedIn",
        )

    def test_whitespace_only_instructions_does_not_bypass_cooldown(self) -> None:
        # Validator strips whitespace-only input to None — bypass should not fire.
        application = self._make_application()
        application.cover_letter_text = CANNED_LETTER
        application.cover_letter_generated_at = datetime.now(UTC) - timedelta(hours=1)
        self.db.add(application)
        self.db.commit()

        with patch(
            "app.api.routes.applications.generate_cover_letter_text",
            return_value="should not be called",
        ) as fake:
            response = draft_cover_letter_endpoint(
                request=_make_request(),
                response=Response(),
                application_id=application.id,
                force=False,
                payload=CoverLetterRequest(extra_instructions="   \n  \t"),
                current_user=self.user,
                db=self.db,
            )
        fake.assert_not_called()
        self.assertTrue(response.cached)
        self.assertEqual(response.cover_letter_text, CANNED_LETTER)


if __name__ == "__main__":
    unittest.main()
