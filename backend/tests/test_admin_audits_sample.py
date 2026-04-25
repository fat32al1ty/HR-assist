"""Phase 5.0.4 — Admin audits sample endpoint tests.

Non-admin gets 403, admin gets up to 20 rows.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
from app.models.user import User


def _make_user(db, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Test User",
        is_active=True,
        email_verified=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


class AdminAuditsSampleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]

        self.user_email = f"nonadmin-audit-{suffix}@example.com"
        self.admin_email = f"admin-audit-{suffix}@example.com"
        self.user = _make_user(self.db, self.user_email, is_admin=False)
        self.admin = _make_user(self.db, self.admin_email, is_admin=True)

        # Create a resume + audit for the non-admin user
        self.resume = Resume(
            user_id=self.user.id,
            original_filename="test.pdf",
            content_type="application/pdf",
            status="completed",
            analysis={"target_role": "Dev"},
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

        self.audit = ResumeAudit(
            resume_id=self.resume.id,
            audit_json={
                "resume_hash": "abc123",
                "role_read": {"primary": {"role_family": "software_engineering", "seniority": "middle", "confidence": 0.8}, "alt": []},
                "skill_gaps": [],
                "quality_issues": [],
                "triggered_question_ids": [],
                "template_mode_active": False,
            },
            prompt_version="audit-v1",
            computed_at=datetime.now(UTC),
            cost_usd=None,
        )
        self.db.add(self.audit)
        self.db.commit()
        self.db.refresh(self.audit)

    def tearDown(self) -> None:
        self.db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.admin.id))
        self.db.commit()
        self.db.close()

    def test_non_admin_gets_403(self) -> None:
        resp = self.client.get(
            "/api/admin/audits/sample",
            headers=_auth_header(self.user_email),
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_gets_200_with_rows(self) -> None:
        resp = self.client.get(
            "/api/admin/audits/sample",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 20)

        # Verify our audit row is present
        ids = [r["resume_id"] for r in rows]
        self.assertIn(self.resume.id, ids)

    def test_admin_audits_sample_no_resume_hash_in_response(self) -> None:
        resp = self.client.get(
            "/api/admin/audits/sample",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        for row in rows:
            # resume_hash must be stripped from audit_json (redaction)
            self.assertNotIn("resume_hash", row.get("audit_json", {}))

    def test_limit_parameter(self) -> None:
        resp = self.client.get(
            "/api/admin/audits/sample?limit=1",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertLessEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
