import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_user_skill import ResumeUserSkill
from app.models.user import User
from app.repositories.resume_user_skills import (
    count_recent_added_curations,
    delete_curated_skill,
    list_added_skill_texts,
    list_curated_skills,
    list_rejected_skill_texts,
    upsert_curated_skill,
)


class ResumeUserSkillsRepoTest(unittest.TestCase):
    """Phase 1.9 PR C1: user agency layer — user curates skills on their
    resume, matcher respects it. Tests cover the repo contract; route &
    matching integration live in separate files."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"curated-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Curated Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="curated-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={},
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(delete(ResumeUserSkill).where(ResumeUserSkill.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_upsert_inserts_new_row(self) -> None:
        row = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Kubernetes",
            direction="added",
            source_vacancy_id=None,
        )
        self.assertIsNotNone(row.id)
        self.assertEqual(row.skill_text, "Kubernetes")
        self.assertEqual(row.direction, "added")

    def test_upsert_is_case_insensitive(self) -> None:
        first = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Kubernetes",
            direction="added",
        )
        second = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="kubernetes",
            direction="added",
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(list_curated_skills(self.db, resume_id=self.resume.id)), 1)

    def test_upsert_flips_direction(self) -> None:
        row = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Grafana",
            direction="added",
        )
        flipped = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Grafana",
            direction="rejected",
        )
        self.assertEqual(row.id, flipped.id)
        self.assertEqual(flipped.direction, "rejected")

    def test_upsert_rejects_bad_direction(self) -> None:
        with self.assertRaises(ValueError):
            upsert_curated_skill(
                self.db,
                resume_id=self.resume.id,
                skill_text="x",
                direction="maybe",
            )

    def test_upsert_rejects_blank_skill(self) -> None:
        with self.assertRaises(ValueError):
            upsert_curated_skill(
                self.db,
                resume_id=self.resume.id,
                skill_text="   ",
                direction="added",
            )

    def test_list_added_and_rejected_split(self) -> None:
        upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Kubernetes",
            direction="added",
        )
        upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="PHP",
            direction="rejected",
        )
        added = list_added_skill_texts(self.db, resume_id=self.resume.id)
        rejected = list_rejected_skill_texts(self.db, resume_id=self.resume.id)
        self.assertEqual(added, ["Kubernetes"])
        self.assertEqual(rejected, ["PHP"])

    def test_delete_removes_row(self) -> None:
        row = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Redis",
            direction="added",
        )
        removed = delete_curated_skill(self.db, resume_id=self.resume.id, skill_id=row.id)
        self.assertTrue(removed)
        self.assertEqual(list_curated_skills(self.db, resume_id=self.resume.id), [])
        # Deleting again is a no-op.
        removed_again = delete_curated_skill(self.db, resume_id=self.resume.id, skill_id=row.id)
        self.assertFalse(removed_again)

    def test_count_recent_added_respects_window(self) -> None:
        upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Ansible",
            direction="added",
        )
        upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Terraform",
            direction="added",
        )
        count = count_recent_added_curations(self.db, resume_id=self.resume.id)
        self.assertEqual(count, 2)
        # Rejected entries don't count toward sanity-warning.
        upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="Go",
            direction="rejected",
        )
        count = count_recent_added_curations(self.db, resume_id=self.resume.id)
        self.assertEqual(count, 2)

    def test_cascade_on_resume_delete(self) -> None:
        row = upsert_curated_skill(
            self.db,
            resume_id=self.resume.id,
            skill_text="MongoDB",
            direction="added",
        )
        self.assertIsNotNone(row.id)
        # Delete the resume; curated skills must cascade.
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.commit()
        remaining = self.db.scalars(
            delete(ResumeUserSkill)
            .where(ResumeUserSkill.resume_id == self.resume.id)
            .returning(ResumeUserSkill.id)
        ).all()
        self.assertEqual(list(remaining), [])
        # Rehydrate resume so tearDown doesn't complain.
        self.resume = Resume(
            id=self.resume.id,
            user_id=self.user.id,
            original_filename="curated-test.pdf",
            content_type="application/pdf",
            storage_path="/tmp/x.pdf",
            status="completed",
            analysis={},
        )
        self.db.add(self.resume)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
