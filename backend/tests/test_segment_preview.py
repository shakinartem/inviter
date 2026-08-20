from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.api.router import api_router
from app.features.segments.preview import SegmentPreviewService
from app.features.segments.preview_schemas import SegmentPreviewRequest


class SegmentPreviewContractTests(unittest.TestCase):
    def test_static_preview_route_precedes_dynamic_segment_route(self) -> None:
        paths = [getattr(route, "path", "") for route in api_router.routes]
        preview_index = paths.index("/segments/preview")
        dynamic_index = paths.index("/segments/{segment_id}")
        self.assertLess(preview_index, dynamic_index)

    def test_average_ignores_missing_values(self) -> None:
        self.assertEqual(SegmentPreviewService._average([10, None, 20]), 15.0)
        self.assertIsNone(SegmentPreviewService._average([None, None]))

    def test_preview_criteria_accepts_explicit_community_scope(self) -> None:
        ids = [uuid4(), uuid4()]
        request = SegmentPreviewRequest.model_validate(
            {
                "platform": "telegram",
                "criteria": {
                    "community_ids": [str(value) for value in ids],
                    "min_readiness_score": 50,
                    "max_members": 500,
                },
            }
        )
        self.assertEqual(request.criteria.community_ids, ids)
        self.assertEqual(request.criteria.min_readiness_score, 50)

    def test_preview_rejects_invalid_score_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            SegmentPreviewRequest.model_validate(
                {
                    "platform": "telegram",
                    "criteria": {"min_readiness_score": 101},
                }
            )


if __name__ == "__main__":
    unittest.main()
