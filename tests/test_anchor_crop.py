import unittest

from rape_ocr.config import load_patterns
from rape_ocr.domain import AnchorConfig
from rape_ocr.ocr_service import _bbox_from_anchor, _find_anchor_item


class AnchorCropTest(unittest.TestCase):
    def test_loads_ppk_anchor_config(self):
        patterns = load_patterns()
        hn = next(field for field in patterns["ppk_rape"].fields if field.name == "hn")

        self.assertIsNotNone(hn.anchor)
        self.assertEqual(hn.anchor.side, "right")
        self.assertIn("HN", hn.anchor.texts)

    def test_finds_anchor_item_by_normalized_text(self):
        items = [
            ("Other", (0.1, 0.1, 0.2, 0.2), 0.9),
            ("H.N.", (0.2, 0.7, 0.24, 0.74), 0.9),
        ]
        anchor = AnchorConfig(texts=("HN",), side="right", width=0.2)

        found = _find_anchor_item(items, anchor)

        self.assertIsNotNone(found)
        self.assertEqual(found[0], "H.N.")

    def test_builds_right_side_bbox_from_anchor(self):
        anchor = AnchorConfig(
            texts=("HN",),
            side="right",
            width=0.2,
            offset_x=0.01,
            pad_y=0.01,
        )

        bbox = _bbox_from_anchor((0.1, 0.7, 0.15, 0.74), anchor)

        self.assertAlmostEqual(bbox[0], 0.16)
        self.assertAlmostEqual(bbox[1], 0.69)
        self.assertAlmostEqual(bbox[2], 0.36)
        self.assertAlmostEqual(bbox[3], 0.75)
