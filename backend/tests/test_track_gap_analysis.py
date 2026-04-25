"""Integration tests for track_gap_analysis.compute_for_resume().

Hits a real DB (test container). Creates vacancies, vacancy profiles, and
resume_vacancy_scores — then verifies aggregation correctness.
"""

from __future__ import annotations

import uuid
import unittest

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.resume_vacancy_score import ResumeVacancyScore
from app.models.track_gap_analysis import TrackGapAnalysis
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.services.track_gap_analysis import compute_for_resume


# ---------------------------------------------------------------------------
# Data-creation helpers
# ---------------------------------------------------------------------------


def _make_user(db, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Gap Test User",
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
        analysis={},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def _make_vacancy(db, idx: int) -> Vacancy:
    v = Vacancy(
        source="test",
        source_url=f"https://test.example.com/vac/{uuid.uuid4().hex}",
        title=f"Test Vacancy {idx}",
        status="indexed",
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_vacancy_profile(db, vacancy_id: int, must_have_skills: list[str]) -> VacancyProfile:
    vp = VacancyProfile(
        vacancy_id=vacancy_id,
        profile={"must_have_skills": must_have_skills},
        canonical_text="",
        qdrant_collection="test",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vp


def _make_score(
    db, resume_id: int, vacancy_id: int, track: str, similarity: float = 0.80
) -> ResumeVacancyScore:
    score = ResumeVacancyScore(
        resume_id=resume_id,
        vacancy_id=vacancy_id,
        pipeline_version="test-v1",
        similarity_score=similarity,
        track=track,
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------


class TrackGapAnalysisIntegrationTest(unittest.TestCase):
    """30 vacancies spread across match / grow / stretch with controlled skills."""

    # Skills design
    # match track (12 vacancies):
    #   - skill "kafka"  appears in 8/12 vacancies  ← top gap
    #   - skill "docker" appears in 5/12 vacancies
    #   - skill "redis"  appears in 2/12 vacancies
    #   resume_skills = {"Python"}  ← present in every vac but filtered out as "user has it"
    #
    # grow track (10 vacancies): skill set G
    #   - "golang", "grpc"  — different from match set
    #
    # stretch track (8 vacancies): skill set S
    #   - "terraform", "k8s"  — different from both

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        self.email = f"tga-{suffix}@example.com"
        self.user = _make_user(self.db, self.email)
        self.resume = _make_resume(self.db, self.user.id)

        self.vacancy_ids: list[int] = []
        self.score_ids: list[int] = []
        self.vp_ids: list[int] = []

        resume_skills: set[str] = {"python"}

        idx = 0
        # ── match track ──────────────────────────────────────────────────────
        for i in range(12):
            v = _make_vacancy(self.db, idx)
            self.vacancy_ids.append(v.id)
            idx += 1
            must: list[str] = ["python"]  # user has this → filtered from gaps
            if i < 8:
                must.append("kafka")  # appears in 8/12
            if i < 5:
                must.append("docker")  # appears in 5/12
            if i < 2:
                must.append("redis")  # appears in 2/12
            vp = _make_vacancy_profile(self.db, v.id, must)
            self.vp_ids.append(vp.id)
            s = _make_score(self.db, self.resume.id, v.id, "match")
            self.score_ids.append(s.id)

        # ── grow track ────────────────────────────────────────────────────────
        for i in range(10):
            v = _make_vacancy(self.db, idx)
            self.vacancy_ids.append(v.id)
            idx += 1
            must = ["golang", "grpc"]
            vp = _make_vacancy_profile(self.db, v.id, must)
            self.vp_ids.append(vp.id)
            s = _make_score(self.db, self.resume.id, v.id, "grow")
            self.score_ids.append(s.id)

        # ── stretch track ─────────────────────────────────────────────────────
        # softer_subset: vacancies where missing skills <= 2
        # All 8 vacancies have exactly 2 must_have skills and user has none → all are softer
        for i in range(8):
            v = _make_vacancy(self.db, idx)
            self.vacancy_ids.append(v.id)
            idx += 1
            must = ["terraform", "k8s"]  # 2 missing → softer_subset
            vp = _make_vacancy_profile(self.db, v.id, must)
            self.vp_ids.append(vp.id)
            s = _make_score(self.db, self.resume.id, v.id, "stretch")
            self.score_ids.append(s.id)

        self.resume_skills = resume_skills

    def tearDown(self) -> None:
        db = self.db
        db.execute(delete(TrackGapAnalysis).where(TrackGapAnalysis.resume_id == self.resume.id))
        for sid in self.score_ids:
            db.execute(delete(ResumeVacancyScore).where(ResumeVacancyScore.id == sid))
        for vpid in self.vp_ids:
            db.execute(delete(VacancyProfile).where(VacancyProfile.id == vpid))
        for vid in self.vacancy_ids:
            db.execute(delete(Vacancy).where(Vacancy.id == vid))
        db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        db.execute(delete(Resume).where(Resume.id == self.resume.id))
        db.execute(delete(User).where(User.id == self.user.id))
        db.commit()
        db.close()

    # ── result structure ─────────────────────────────────────────────────────

    def test_returns_all_three_tracks(self) -> None:
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertIn("match", result)
        self.assertIn("grow", result)
        self.assertIn("stretch", result)

    # ── match track assertions ────────────────────────────────────────────────

    def test_match_vacancies_count(self) -> None:
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertEqual(result["match"].vacancies_count, 12)

    def test_match_top_gaps_ordered_by_frequency_desc(self) -> None:
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        gaps = result["match"].top_gaps
        self.assertGreater(len(gaps), 0)
        # Fractions must be non-increasing
        fractions = [g.fraction for g in gaps]
        self.assertEqual(fractions, sorted(fractions, reverse=True))

    def test_match_top_gap_is_kafka_with_correct_fraction(self) -> None:
        """kafka is in 8/12 vacancies → fraction ≈ 0.667 ± 0.05."""
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        gaps = result["match"].top_gaps
        top_skill = gaps[0].skill
        self.assertEqual(top_skill, "kafka")
        self.assertAlmostEqual(gaps[0].fraction, 8 / 12, delta=0.05)

    def test_match_gaps_do_not_include_user_skills(self) -> None:
        """'python' is in the resume → must NOT appear in gaps."""
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        gap_skills = {g.skill for g in result["match"].top_gaps}
        self.assertNotIn("python", gap_skills)

    # ── grow track assertions ─────────────────────────────────────────────────

    def test_grow_vacancies_count(self) -> None:
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertEqual(result["grow"].vacancies_count, 10)

    def test_grow_gaps_are_grow_skills_not_match_skills(self) -> None:
        """grow track should surface golang/grpc gaps, NOT kafka/docker from match."""
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        gap_skills = {g.skill for g in result["grow"].top_gaps}
        self.assertTrue(
            gap_skills & {"golang", "grpc"},
            f"Expected grow-specific skills in gaps, got: {gap_skills}",
        )
        self.assertNotIn("kafka", gap_skills)

    # ── stretch track assertions ───────────────────────────────────────────────

    def test_stretch_vacancies_count(self) -> None:
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertEqual(result["stretch"].vacancies_count, 8)

    def test_stretch_softer_subset_count(self) -> None:
        """All 8 stretch vacancies have exactly 2 missing skills → softer_subset_count == 8."""
        result = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertEqual(result["stretch"].softer_subset_count, 8)

    # ── empty resume case ─────────────────────────────────────────────────────

    def test_empty_resume_returns_zero_counts(self) -> None:
        """A resume with no ResumeVacancyScore rows returns zeros without raising."""
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        email = f"tga-empty-{suffix}@example.com"
        user = _make_user(db, email)
        resume = _make_resume(db, user.id)
        try:
            result = compute_for_resume(db, resume_id=resume.id, resume_skills=set())
            for track in ("match", "grow", "stretch"):
                self.assertEqual(result[track].vacancies_count, 0, f"track={track}")
                self.assertEqual(result[track].top_gaps, [], f"track={track}")
                self.assertEqual(result[track].softer_subset_count, 0, f"track={track}")
        finally:
            db.execute(delete(TrackGapAnalysis).where(TrackGapAnalysis.resume_id == resume.id))
            db.execute(delete(Resume).where(Resume.id == resume.id))
            db.execute(delete(User).where(User.id == user.id))
            db.commit()
            db.close()

    # ── cache test ────────────────────────────────────────────────────────────

    def test_second_call_hits_cache_and_is_stable(self) -> None:
        """Second compute_for_resume call within TTL reads from cache.

        Verification strategy: after the first call, insert a NEW score row
        pointing at a new vacancy (different track counts). The second call
        must still return the original counts — proving it read cache, not DB.
        """
        # First call — populates cache
        result1 = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        original_match_count = result1["match"].vacancies_count

        # Verify one cache row exists
        cache_rows = (
            self.db.execute(
                select(TrackGapAnalysis).where(TrackGapAnalysis.resume_id == self.resume.id)
            )
            .scalars()
            .all()
        )
        self.assertEqual(len(cache_rows), 1)
        ts_after_first = cache_rows[0].computed_at

        # Add a new match vacancy + score AFTER cache was written
        extra_v = _make_vacancy(self.db, 9999)
        self.vacancy_ids.append(extra_v.id)
        extra_vp = _make_vacancy_profile(self.db, extra_v.id, ["newskill"])
        self.vp_ids.append(extra_vp.id)
        extra_s = _make_score(self.db, self.resume.id, extra_v.id, "match")
        self.score_ids.append(extra_s.id)

        # Second call — must return cached result (same count as before extra row)
        result2 = compute_for_resume(
            self.db, resume_id=self.resume.id, resume_skills=self.resume_skills
        )
        self.assertEqual(result2["match"].vacancies_count, original_match_count)

        # computed_at should be unchanged (still one row, same timestamp)
        self.db.expire_all()
        cache_rows2 = (
            self.db.execute(
                select(TrackGapAnalysis).where(TrackGapAnalysis.resume_id == self.resume.id)
            )
            .scalars()
            .all()
        )
        self.assertEqual(len(cache_rows2), 1)
        self.assertEqual(cache_rows2[0].computed_at, ts_after_first)


if __name__ == "__main__":
    unittest.main()
