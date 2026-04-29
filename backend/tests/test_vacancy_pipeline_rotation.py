import unittest

from app.services.vacancy_pipeline import _build_rotation_offset


class VacancyPipelineRotationTest(unittest.TestCase):
    def test_rotation_offset_uses_deeper_pages(self) -> None:
        offsets = [
            _build_rotation_offset("devops observability", 300, attempt) for attempt in range(1, 7)
        ]
        self.assertTrue(all(offset >= 1 for offset in offsets))
        # v0.22.1: HH public API rejects (page+1)*per_page > 2000, and our
        # parallel wave fetches ~8 pages ahead — anything past 11 turns into
        # 8+ guaranteed 400s. Cap is now 11 (was 90, prod was burning ~185
        # bad requests per worker cycle on 2026-04-29).
        self.assertTrue(all(offset <= 11 for offset in offsets))
        self.assertEqual(offsets, sorted(offsets))

    def test_rotation_never_exceeds_hh_ceiling_across_attempts(self) -> None:
        # Stress: large counts + deep attempts must still respect the cap.
        for count in (40, 100, 300, 800):
            for attempt in range(1, 12):
                offset = _build_rotation_offset("backend python kafka", count, attempt)
                self.assertLessEqual(
                    offset,
                    11,
                    f"rotation_offset overshot for count={count} attempt={attempt}: {offset}",
                )


if __name__ == "__main__":
    unittest.main()
