"""Asserts Qdrant payload keys after Level A PII minimization."""

import unittest

from app.services.resume_profile_pipeline import build_resume_vector_payload


class VectorPayloadPIITest(unittest.TestCase):
    def _payload(self):
        profile = {
            "candidate_name": "Иван Петров",
            "target_role": "Backend Engineer",
            "specialization": "Python",
            "seniority": "middle",
            "seniority_confidence": 0.85,
            "total_experience_years": 4,
            "hard_skills": ["Python", "FastAPI"],
            "tools": ["Docker"],
            "domains": ["fintech"],
            "languages": ["Russian", "English"],
            "matching_keywords": ["backend", "api"],
        }
        return build_resume_vector_payload(profile, canonical_text="some text")

    def test_candidate_name_absent(self):
        payload = self._payload()
        self.assertNotIn("candidate_name", payload)

    def test_canonical_text_absent(self):
        payload = self._payload()
        self.assertNotIn("canonical_text", payload)

    def test_matcher_fields_present(self):
        payload = self._payload()
        for key in (
            "target_role",
            "specialization",
            "seniority",
            "hard_skills",
            "tools",
            "domains",
        ):
            self.assertIn(key, payload, f"Missing key: {key}")

    def test_type_field_present(self):
        payload = self._payload()
        self.assertEqual(payload["type"], "resume_profile")


if __name__ == "__main__":
    unittest.main()
