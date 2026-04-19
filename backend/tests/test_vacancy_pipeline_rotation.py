import unittest

from app.services.vacancy_pipeline import _build_rotation_offset


class VacancyPipelineRotationTest(unittest.TestCase):
    def test_rotation_offset_uses_deeper_pages(self) -> None:
        offsets = [_build_rotation_offset("devops observability", 300, attempt) for attempt in range(1, 7)]
        self.assertTrue(all(offset >= 1 for offset in offsets))
        self.assertTrue(all(offset <= 90 for offset in offsets))
        self.assertGreater(max(offsets), 6)
        self.assertEqual(offsets, sorted(offsets))


if __name__ == "__main__":
    unittest.main()
