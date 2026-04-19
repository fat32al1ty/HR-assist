import unittest
import uuid

from sqlalchemy import delete

from app.api.routes.vacancies import _filter_matches_by_feedback
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.repositories.user_vacancy_feedback import list_disliked_vacancies, list_liked_vacancies


class FeedbackVisibilityRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"feedback-visibility-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Feedback Visibility Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.filtered_vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 1000000}",
            title="Observability Lead",
            company="Company A",
            location="Москва",
            status="filtered",
            raw_payload={},
            raw_text="observability",
            error_message=None,
        )
        self.failed_vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 1000000}",
            title="SRE Manager",
            company="Company B",
            location="Москва",
            status="failed",
            raw_payload={},
            raw_text="sre",
            error_message=None,
        )
        self.db.add(self.filtered_vacancy)
        self.db.add(self.failed_vacancy)
        self.db.commit()
        self.db.refresh(self.filtered_vacancy)
        self.db.refresh(self.failed_vacancy)

        self.db.add(
            UserVacancyFeedback(
                user_id=self.user.id,
                vacancy_id=self.filtered_vacancy.id,
                liked=True,
                disliked=False,
            )
        )
        self.db.add(
            UserVacancyFeedback(
                user_id=self.user.id,
                vacancy_id=self.failed_vacancy.id,
                liked=False,
                disliked=True,
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.execute(delete(UserVacancyFeedback).where(UserVacancyFeedback.user_id == self.user.id))
        self.db.execute(
            delete(Vacancy).where(Vacancy.id.in_([self.filtered_vacancy.id, self.failed_vacancy.id]))
        )
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_feedback_lists_include_non_indexed_vacancies(self) -> None:
        liked = list_liked_vacancies(self.db, user_id=self.user.id, limit=100)
        disliked = list_disliked_vacancies(self.db, user_id=self.user.id, limit=100)
        self.assertTrue(any(item.id == self.filtered_vacancy.id for item in liked))
        self.assertTrue(any(item.id == self.failed_vacancy.id for item in disliked))

    def test_filter_matches_excludes_feedback_ids(self) -> None:
        payload = [
            {"vacancy_id": self.filtered_vacancy.id, "title": "keep out"},
            {"vacancy_id": self.failed_vacancy.id, "title": "keep out"},
            {"vacancy_id": 999999, "title": "keep in"},
        ]
        excluded = {self.filtered_vacancy.id, self.failed_vacancy.id}
        filtered = _filter_matches_by_feedback(matches=payload, excluded_ids=excluded)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(int(filtered[0]["vacancy_id"]), 999999)


if __name__ == "__main__":
    unittest.main()
