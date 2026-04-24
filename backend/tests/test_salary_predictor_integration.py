"""Integration tests for salary predictor pipeline wiring."""

from __future__ import annotations

import types
import unittest
from unittest.mock import MagicMock, patch

from app.services import salary_predictor
from app.services.salary_pipeline import populate_predicted_salary


def _make_profile(salary_min=None, salary_max=None, role_family="software_engineering", seniority="middle"):
    profile = MagicMock()
    profile.salary_min = salary_min
    profile.salary_max = salary_max
    profile.profile = {"role_family": role_family, "seniority": seniority}
    profile.predicted_salary_p25 = None
    profile.predicted_salary_p50 = None
    profile.predicted_salary_p75 = None
    profile.predicted_salary_confidence = None
    profile.predicted_salary_model_version = None
    return profile


def _make_vacancy(location="Москва"):
    vacancy = MagicMock()
    vacancy.location = location
    return vacancy


class TestPredictorPopulatesFields(unittest.TestCase):
    def test_predictor_populates_fields_when_lgbm_returns_band(self):
        db = MagicMock()
        profile = _make_profile()
        vacancy = _make_vacancy()

        band = salary_predictor.SalaryBand(
            p25=100000, p50=150000, p75=200000, confidence=0.8, model_version="lgbm-v1"
        )
        with patch("app.services.salary_predictor.predict", return_value=band):
            populate_predicted_salary(db, profile=profile, vacancy=vacancy)

        self.assertEqual(profile.predicted_salary_p25, 100000)
        self.assertEqual(profile.predicted_salary_p50, 150000)
        self.assertEqual(profile.predicted_salary_p75, 200000)
        self.assertAlmostEqual(profile.predicted_salary_confidence, 0.8)
        self.assertEqual(profile.predicted_salary_model_version, "lgbm-v1")

    def test_predictor_skips_when_stated_salary_present(self):
        db = MagicMock()
        profile = _make_profile(salary_min=100000)
        vacancy = _make_vacancy()

        with patch("app.services.salary_predictor.predict") as mock_predict:
            populate_predicted_salary(db, profile=profile, vacancy=vacancy)
            mock_predict.assert_not_called()

        self.assertIsNone(profile.predicted_salary_p50)

    def test_predictor_skips_when_feature_disabled(self):
        """feature_salary_predictor_enabled=False means persist_vacancy_profile
        does not call populate_predicted_salary. We test this by patching the
        vacancy_profile_pipeline settings and the helper import, then verifying
        the helper is never invoked."""
        import app.services.vacancy_profile_pipeline as vpp

        band = salary_predictor.SalaryBand(
            p25=100000, p50=150000, p75=200000, confidence=0.8, model_version="lgbm-v1"
        )

        called = []

        def _mock_populate(*args, **kwargs):
            called.append(True)

        with patch("app.services.salary_predictor.predict", return_value=band):
            with patch("app.services.vacancy_profile_pipeline.settings") as mock_settings:
                mock_settings.feature_salary_predictor_enabled = False
                with patch(
                    "app.services.vacancy_profile_pipeline.create_or_update_vacancy_profile"
                ) as mock_create:
                    mock_vp = MagicMock()
                    mock_vp.vacancy = None
                    mock_create.return_value = mock_vp
                    with patch("app.services.vacancy_profile_pipeline.create_embedding", return_value=[0.1]):
                        with patch("app.services.vacancy_profile_pipeline.get_vector_store") as mock_vs:
                            mock_vs.return_value.upsert_vacancy_profile.return_value = ("col", "pt")
                            with patch(
                                "app.services.salary_pipeline.populate_predicted_salary",
                                side_effect=_mock_populate,
                            ):
                                vpp.persist_vacancy_profile(
                                    MagicMock(),
                                    vacancy_id=1,
                                    source_url="https://hh.ru/vacancy/1",
                                    title="Dev",
                                    company=None,
                                    profile={},
                                )

        self.assertEqual(called, [])

    def test_baseline_fallback_activates_when_lgbm_returns_none(self):
        db = MagicMock()
        profile = _make_profile()
        vacancy = _make_vacancy()

        from app.services.salary_baseline import BaselineBand

        baseline_band = BaselineBand(p25=80000, p50=120000, p75=160000, confidence=0.4, support=10)

        with patch("app.services.salary_predictor.predict", return_value=None):
            with patch("app.services.salary_pipeline.settings") as mock_settings:
                mock_settings.feature_salary_baseline_enabled = True
                with patch("app.services.salary_baseline.get_baseline_band", return_value=baseline_band):
                    populate_predicted_salary(db, profile=profile, vacancy=vacancy)

        self.assertEqual(profile.predicted_salary_p50, 120000)
        self.assertEqual(profile.predicted_salary_model_version, "baseline-v0")

    def test_baseline_fallback_off_when_flag_false(self):
        db = MagicMock()
        profile = _make_profile()
        vacancy = _make_vacancy()

        from app.services.salary_baseline import BaselineBand

        baseline_band = BaselineBand(p25=80000, p50=120000, p75=160000, confidence=0.4, support=10)

        with patch("app.services.salary_predictor.predict", return_value=None):
            with patch("app.services.salary_pipeline.settings") as mock_settings:
                mock_settings.feature_salary_baseline_enabled = False
                with patch("app.services.salary_baseline.get_baseline_band", return_value=baseline_band) as mock_baseline:
                    populate_predicted_salary(db, profile=profile, vacancy=vacancy)
                    mock_baseline.assert_not_called()

        self.assertIsNone(profile.predicted_salary_p50)


if __name__ == "__main__":
    unittest.main()
