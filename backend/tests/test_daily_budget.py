"""Per-user daily OpenAI budget ceiling.

Covers both the pre-flight check (start_recommendation_job raises when today's
spend already exceeds the cap) and the in-flight check (the tracker raises
DailyBudgetExceeded as soon as the UPSERT'd total crosses the cap).
"""

from __future__ import annotations

import unittest
import uuid
from decimal import Decimal

from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_daily_spend import UserDailySpend
from app.repositories.user_daily_spend import get_daily_spend_usd, increment_daily_spend
from app.services.openai_usage import (
    DailyBudgetExceeded,
    OpenAIUsageTracker,
)
from app.services.recommendation_jobs import (
    DailyBudgetReachedBeforeStart,
    start_recommendation_job,
)


class DailyBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"spend-{suffix}@example.com",
            hashed_password="x",
            full_name="Budget Test",
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.user_id = int(self.user.id)
        self.original_budget = settings.openai_user_daily_budget_usd
        self.original_enforce = settings.openai_enforce_user_daily_budget
        settings.openai_user_daily_budget_usd = 0.10
        settings.openai_enforce_user_daily_budget = True

    def tearDown(self) -> None:
        self.db.execute(delete(UserDailySpend).where(UserDailySpend.user_id == self.user_id))
        self.db.execute(delete(User).where(User.id == self.user_id))
        self.db.commit()
        self.db.close()
        settings.openai_user_daily_budget_usd = self.original_budget
        settings.openai_enforce_user_daily_budget = self.original_enforce

    def test_increment_is_atomic_upsert(self) -> None:
        total = increment_daily_spend(self.db, user_id=self.user_id, amount_usd=0.03)
        self.assertAlmostEqual(total, 0.03, places=4)
        total = increment_daily_spend(self.db, user_id=self.user_id, amount_usd=0.02)
        self.assertAlmostEqual(total, 0.05, places=4)
        self.assertAlmostEqual(get_daily_spend_usd(self.db, user_id=self.user_id), 0.05, places=4)

    def test_tracker_raises_when_daily_cap_crossed(self) -> None:
        # Seed today's spend to just under the cap.
        increment_daily_spend(self.db, user_id=self.user_id, amount_usd=0.09)

        tracker = OpenAIUsageTracker(
            budget_usd=10.0,  # don't trip the per-request cap
            budget_enforced=True,
            user_id=self.user_id,
            daily_budget_usd=settings.openai_user_daily_budget_usd,
            daily_budget_enforced=True,
        )
        # A large call whose cost will push total past 0.10 must raise.
        with self.assertRaises(DailyBudgetExceeded):
            # 100k output tokens at $8/M * 1.15 safety = $0.92 — well over cap.
            tracker.add_responses_usage(input_tokens=0, output_tokens=100_000)

    def test_start_recommendation_job_refuses_when_pre_spent(self) -> None:
        # User's today spend already exceeds the daily cap.
        increment_daily_spend(self.db, user_id=self.user_id, amount_usd=float(Decimal("0.20")))
        with self.assertRaises(DailyBudgetReachedBeforeStart):
            start_recommendation_job(
                user_id=self.user_id,
                resume_id=-1,  # would fail later, but pre-flight check fires first
                request_payload={"discover_count": 1, "match_limit": 1},
            )


if __name__ == "__main__":
    unittest.main()
