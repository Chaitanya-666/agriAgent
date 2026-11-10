"""Unit tests for service/validation.py (Field Service input rules).

Test design: Equivalence Partitioning for the valid/invalid classes of every input and
Boundary Value Analysis on each numeric limit (confidence 0.70-1.00, image side 32 px,
image pixels, upload bytes, page limit 1-100, offset >= 0). IDs: UT-V-xx.
"""

import io
import math
import unittest
from unittest import mock

from PIL import Image

from service import config
from service.validation import (
    ValidationError,
    decode_image,
    parse_crop,
    parse_min_confidence,
    parse_mode,
    parse_page,
    parse_params,
    sniff_image_type,
)


def image_bytes(width=64, height=64, fmt="PNG", mode="RGB", color=(90, 160, 60)):
    buf = io.BytesIO()
    fill = color if mode != "L" else 128
    if mode == "RGBA":
        fill = (*color, 200)
    Image.new(mode, (width, height), fill).save(buf, format=fmt)
    return buf.getvalue()


class CropTests(unittest.TestCase):
    def test_every_supported_crop_is_accepted(self):  # UT-V-01 (EP: valid class)
        for crop in config.CROPS:
            with self.subTest(crop=crop):
                self.assertEqual(parse_crop(crop), crop)

    def test_case_and_spaces_are_normalised(self):  # UT-V-02
        self.assertEqual(parse_crop("  Sugar Beet "), "sugar beet")

    def test_unknown_empty_and_missing_crops_are_refused(self):  # UT-V-03 (EP: invalid class)
        for value in ("maize", "", "   ", None, "cotton plant"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    parse_crop(value)
                self.assertEqual((ctx.exception.status, ctx.exception.field), (422, "crop"))


class ModeTests(unittest.TestCase):
    def test_mock_is_always_allowed(self):  # UT-V-04
        self.assertEqual(parse_mode("mock", allow_real=False), "mock")
        self.assertEqual(parse_mode(" MOCK ", allow_real=False), "mock")

    def test_real_mode_needs_the_server_switch(self):  # UT-V-05
        self.assertEqual(parse_mode("real", allow_real=True), "real")
        with self.assertRaises(ValidationError) as ctx:
            parse_mode("real", allow_real=False)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (403, "real_mode_disabled"))

    def test_other_modes_are_refused(self):  # UT-V-06
        for value in ("fast", "", None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    parse_mode(value, allow_real=True)
                self.assertEqual(ctx.exception.status, 422)


class MinConfidenceTests(unittest.TestCase):
    def test_missing_value_uses_the_default(self):  # UT-V-07
        self.assertEqual(parse_min_confidence(None), config.DEFAULT_MIN_CONFIDENCE)
        self.assertEqual(parse_min_confidence("  "), config.DEFAULT_MIN_CONFIDENCE)

    def test_boundaries_inside_the_range_are_accepted(self):  # UT-V-08 (BVA)
        for text, expected in (("0.70", 0.70), ("0.71", 0.71), ("0.99", 0.99), ("1.00", 1.0),
                               ("1e0", 1.0), (" 0.8 ", 0.8)):
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_min_confidence(text), expected)

    def test_values_just_outside_the_range_are_refused(self):  # UT-V-09 (BVA)
        for text in ("0.69", "0.6999", "1.01", "0", "-0.8", "70"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError) as ctx:
                    parse_min_confidence(text)
                self.assertEqual(ctx.exception.code, "invalid_min_confidence")

    def test_nan_and_infinity_are_refused(self):  # UT-V-10 (Lab 2 defect: gate accepted NaN)
        # NaN fails every comparison, so a plain "lo <= x <= hi" check would wrongly pass it.
        self.assertFalse(math.nan < 0.70 or math.nan > 1.0)
        for text in ("nan", "NaN", "inf", "-inf", "infinity"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError) as ctx:
                    parse_min_confidence(text)
                self.assertIn("finite", ctx.exception.message)

    def test_text_is_refused(self):  # UT-V-11
        for text in ("abc", "0.7.0", "seventy"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError) as ctx:
                    parse_min_confidence(text)
                self.assertEqual(ctx.exception.message, "min_confidence must be a number")


class ParamsTests(unittest.TestCase):
    def test_parse_params_combines_all_three(self):  # UT-V-12
        p = parse_params("Wheat", "mock", "0.85", allow_real=False)
        self.assertEqual((p.crop, p.mode, p.min_confidence), ("wheat", "mock", 0.85))

    def test_first_bad_field_is_reported(self):  # UT-V-13
        with self.assertRaises(ValidationError) as ctx:
            parse_params("maize", "fast", "nan", allow_real=False)
        self.assertEqual(ctx.exception.field, "crop")


class SniffTests(unittest.TestCase):
    def test_png_and_jpeg_signatures(self):  # UT-V-14
        self.assertEqual(sniff_image_type(image_bytes(fmt="PNG")), "png")
        self.assertEqual(sniff_image_type(image_bytes(fmt="JPEG")), "jpeg")

    def test_other_content_is_unknown(self):  # UT-V-15
        for raw in (image_bytes(fmt="GIF", mode="L"), b"", b"hello", b"\x89PN", b"%PDF-1.7"):
            with self.subTest(raw=raw[:8]):
                self.assertIsNone(sniff_image_type(raw))


class DecodeImageTests(unittest.TestCase):
    def test_png_and_jpeg_decode_to_rgb(self):  # UT-V-16
        for fmt in ("PNG", "JPEG"):
            with self.subTest(fmt=fmt):
                img = decode_image(image_bytes(80, 60, fmt=fmt))
                self.assertEqual((img.mode, img.size), ("RGB", (80, 60)))

    def test_rgba_and_greyscale_are_converted(self):  # UT-V-17
        self.assertEqual(decode_image(image_bytes(mode="RGBA")).mode, "RGB")
        self.assertEqual(decode_image(image_bytes(mode="L")).mode, "RGB")

    def test_empty_file(self):  # UT-V-18
        with self.assertRaises(ValidationError) as ctx:
            decode_image(b"")
        self.assertEqual((ctx.exception.status, ctx.exception.code), (422, "empty_file"))

    def test_upload_size_boundary(self):  # UT-V-19 (BVA on bytes)
        with mock.patch.object(config, "MAX_UPLOAD_BYTES", 2000):
            ok = image_bytes(40, 40)
            self.assertLessEqual(len(ok), 2000)
            decode_image(ok)  # under the limit: accepted
            too_big = ok + b"\0" * (2001 - len(ok))  # exactly limit + 1
            with self.assertRaises(ValidationError) as ctx:
                decode_image(too_big)
            self.assertEqual((ctx.exception.status, ctx.exception.code), (413, "file_too_large"))

    def test_content_is_sniffed_not_trusted(self):  # UT-V-20
        with self.assertRaises(ValidationError) as ctx:
            decode_image(b"just some text pretending to be a png")
        self.assertEqual((ctx.exception.status, ctx.exception.code), (415, "unsupported_type"))

    def test_truncated_png_is_corrupt(self):  # UT-V-21
        raw = image_bytes(200, 200)
        with self.assertRaises(ValidationError) as ctx:
            decode_image(raw[: len(raw) // 2])
        self.assertEqual((ctx.exception.status, ctx.exception.code), (422, "corrupt_image"))

    def test_minimum_side_boundary(self):  # UT-V-22 (BVA: 31 / 32 px)
        side = config.MIN_IMAGE_SIDE
        decode_image(image_bytes(side, side))
        for w, h in ((side - 1, side), (side, side - 1), (1, 1)):
            with self.subTest(size=(w, h)):
                with self.assertRaises(ValidationError) as ctx:
                    decode_image(image_bytes(w, h))
                self.assertEqual(ctx.exception.code, "image_too_small")

    def test_pixel_count_boundary(self):  # UT-V-23 (BVA on width x height)
        with mock.patch.object(config, "MAX_IMAGE_PIXELS", 64 * 64):
            decode_image(image_bytes(64, 64))  # exactly the limit
            with self.assertRaises(ValidationError) as ctx:
                decode_image(image_bytes(65, 64))  # one column over
            self.assertEqual((ctx.exception.status, ctx.exception.code), (413, "image_too_large"))


class PageTests(unittest.TestCase):
    def test_defaults(self):  # UT-V-24
        self.assertEqual(parse_page(None, None), (config.PAGE_LIMIT_DEFAULT, 0))

    def test_limit_boundaries(self):  # UT-V-25 (BVA: 0, 1, 100, 101)
        self.assertEqual(parse_page(1, 0)[0], 1)
        self.assertEqual(parse_page(config.PAGE_LIMIT_MAX, 0)[0], config.PAGE_LIMIT_MAX)
        for bad in (0, config.PAGE_LIMIT_MAX + 1, -5):
            with self.subTest(limit=bad):
                with self.assertRaises(ValidationError) as ctx:
                    parse_page(bad, 0)
                self.assertEqual(ctx.exception.field, "limit")

    def test_offset_boundary(self):  # UT-V-26 (BVA: -1, 0)
        self.assertEqual(parse_page(10, 0)[1], 0)
        with self.assertRaises(ValidationError) as ctx:
            parse_page(10, -1)
        self.assertEqual(ctx.exception.field, "offset")


if __name__ == "__main__":
    unittest.main()
