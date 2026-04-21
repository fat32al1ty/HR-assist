"""Applications API tests (Phase 1.4).

Network-free: real Postgres via SessionLocal, no OpenAI calls anywhere
on this code path. Covers the create/list/update/delete lifecycle plus
the cross-user guard and the one-vacancy-one-application rule that
Phase 1.6's "Откликнуться" shortcut relies on.
"""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy import delete

from app.api.routes.applications import (
    create_application_endpoint,
    delete_application_endpoint,
    get_application_endpoint,
    list_applications,
    update_application_endpoint,
)
from app.db.session import SessionLocal
from app.models.application import Application
from app.models.user import User
from app.models.vacancy import Vacancy
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationUpdateRequest,
)


def _make_vacancy(db, *, suffix: str) -> Vacancy:
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.test/vacancy/{suffix}",
        title=f"Backend engineer {suffix}",
        company="Example Inc.",
        location="Москва",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


class ApplicationsEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"apps-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Apps Tester",
            is_active=True,
            email_verified=True,
        )
        self.other_user = User(
            email=f"apps-other-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Other Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other_user)

        self.vacancy = _make_vacancy(self.db, suffix=self.suffix)

    def tearDown(self) -> None:
        self.db.execute(
            delete(Application).where(Application.user_id.in_([self.user.id, self.other_user.id]))
        )
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id.in_([self.user.id, self.other_user.id])))
        self.db.commit()
        self.db.close()

    def test_create_from_vacancy_copies_denormalized_fields(self) -> None:
        payload = ApplicationCreateRequest(vacancy_id=self.vacancy.id)
        result = create_application_endpoint(payload=payload, current_user=self.user, db=self.db)
        self.assertEqual(result.vacancy_id, self.vacancy.id)
        self.assertEqual(result.vacancy_title, self.vacancy.title)
        self.assertEqual(result.vacancy_company, self.vacancy.company)
        self.assertEqual(result.source_url, self.vacancy.source_url)
        self.assertEqual(result.status, "draft")
        # Draft status shouldn't stamp applied_at yet.
        self.assertIsNone(result.applied_at)

    def test_create_with_applied_status_stamps_applied_at(self) -> None:
        payload = ApplicationCreateRequest(vacancy_id=self.vacancy.id, status="applied")
        result = create_application_endpoint(payload=payload, current_user=self.user, db=self.db)
        self.assertEqual(result.status, "applied")
        self.assertIsNotNone(result.applied_at)

    def test_create_without_vacancy_requires_title(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_application_endpoint(
                payload=ApplicationCreateRequest(),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_with_freeform_title_no_vacancy(self) -> None:
        payload = ApplicationCreateRequest(
            vacancy_title="Platform Engineer",
            vacancy_company="Somewhere",
            source_url="https://hh.ru/vacancy/1234",
        )
        result = create_application_endpoint(payload=payload, current_user=self.user, db=self.db)
        self.assertIsNone(result.vacancy_id)
        self.assertEqual(result.vacancy_title, "Platform Engineer")
        self.assertEqual(result.source_url, "https://hh.ru/vacancy/1234")

    def test_create_rejects_missing_vacancy(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_application_endpoint(
                payload=ApplicationCreateRequest(vacancy_id=999_999_999),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_duplicate_vacancy_is_409_with_existing_id(self) -> None:
        first = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_application_endpoint(
                payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        assert isinstance(ctx.exception.detail, dict)
        self.assertEqual(ctx.exception.detail["application_id"], first.id)

    def test_list_returns_only_this_users_applications(self) -> None:
        create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        # Another user applies to the same vacancy — must not leak.
        create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.other_user,
            db=self.db,
        )
        rows = list_applications(status_filter=None, current_user=self.user, db=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].vacancy_id, self.vacancy.id)

    def test_list_status_filter(self) -> None:
        create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id, status="applied"),
            current_user=self.user,
            db=self.db,
        )
        # Draft for a different (no-vacancy) entry.
        create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_title="Freelance gig"),
            current_user=self.user,
            db=self.db,
        )
        applied_only = list_applications(
            status_filter="applied", current_user=self.user, db=self.db
        )
        self.assertEqual(len(applied_only), 1)
        self.assertEqual(applied_only[0].status, "applied")

    def test_patch_status_updates_applied_at_on_first_transition(self) -> None:
        app_row = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        self.assertIsNone(app_row.applied_at)

        result = update_application_endpoint(
            application_id=app_row.id,
            payload=ApplicationUpdateRequest(status="applied"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(result.status, "applied")
        self.assertIsNotNone(result.applied_at)

        # Moving further along doesn't reset the original applied_at.
        first_stamp = result.applied_at
        result2 = update_application_endpoint(
            application_id=app_row.id,
            payload=ApplicationUpdateRequest(status="interview"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(result2.status, "interview")
        self.assertEqual(result2.applied_at, first_stamp)

    def test_patch_empty_payload_is_rejected(self) -> None:
        app_row = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        with self.assertRaises(HTTPException) as ctx:
            update_application_endpoint(
                application_id=app_row.id,
                payload=ApplicationUpdateRequest(),
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_patch_notes_and_clear_notes(self) -> None:
        app_row = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id, notes="Initial note"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(app_row.notes, "Initial note")

        updated = update_application_endpoint(
            application_id=app_row.id,
            payload=ApplicationUpdateRequest(notes="Updated"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(updated.notes, "Updated")

        cleared = update_application_endpoint(
            application_id=app_row.id,
            payload=ApplicationUpdateRequest(clear_notes=True),
            current_user=self.user,
            db=self.db,
        )
        self.assertIsNone(cleared.notes)

    def test_get_returns_only_owner(self) -> None:
        app_row = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        fetched = get_application_endpoint(
            application_id=app_row.id, current_user=self.user, db=self.db
        )
        self.assertEqual(fetched.id, app_row.id)

        with self.assertRaises(HTTPException) as ctx:
            get_application_endpoint(
                application_id=app_row.id,
                current_user=self.other_user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_removes_row(self) -> None:
        app_row = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id),
            current_user=self.user,
            db=self.db,
        )
        delete_application_endpoint(application_id=app_row.id, current_user=self.user, db=self.db)
        with self.assertRaises(HTTPException):
            get_application_endpoint(application_id=app_row.id, current_user=self.user, db=self.db)


if __name__ == "__main__":
    unittest.main()
