import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import delete

from app.api.routes.vacancies import dislike_vacancy, selected_vacancies, undislike_vacancy
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.schemas.vacancy import VacancyFeedbackRequest


class FeedbackFlowIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"feedback-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Feedback Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="feedback-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            extracted_text="feedback flow",
            analysis={"target_role": "backend engineer"},
            error_message=None,
            is_active=True,
        )
        self.db.add(self.resume)

        self.vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 1000000}",
            title="DevOps Engineer",
            company="Test Corp",
            location="Москва",
            status="indexed",
            raw_payload={},
            raw_text="DevOps, monitoring, observability, SRE",
            error_message=None,
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.resume)
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(delete(UserVacancyFeedback).where(UserVacancyFeedback.user_id == self.user.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.api.routes.vacancies.recompute_user_preference_profile")
    def test_undislike_moves_vacancy_to_selected(self, _mock_recompute: object) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)

        dislike_response = dislike_vacancy(payload=payload, current_user=self.user, db=self.db)
        self.assertTrue(dislike_response.disliked)
        self.assertFalse(dislike_response.liked)

        undislike_response = undislike_vacancy(payload=payload, current_user=self.user, db=self.db)
        self.assertFalse(undislike_response.disliked)
        self.assertTrue(undislike_response.liked)

        selected = selected_vacancies(limit=100, current_user=self.user, db=self.db)
        self.assertTrue(any(item.vacancy_id == self.vacancy.id for item in selected))


if __name__ == "__main__":
    unittest.main()
