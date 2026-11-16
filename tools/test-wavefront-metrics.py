#!/usr/bin/env python3
"""Synthetic event tests: a fast success-only score cannot excuse lost work."""
import unittest
from wavefront_metrics import summarize


def round_record():
    return {"t0": 5.0, "t1": 35.0, "deadline": 37.0, "requests": [
        {"id": "warmup", "phase": "warmup", "started_at": 0.0,
         "completed_at": 5.0, "status": "success"},
        *[{"id": str(i), "phase": "measurement", "started_at": 5.0 + i * 0.25,
           "completed_at": 5.125 + i * 0.25, "status": "success"}
          for i in range(120)]]}


class MetricsTests(unittest.TestCase):
    def test_valid_serial_round(self):
        result = summarize(round_record())
        self.assertTrue(result["valid"])
        self.assertEqual(result["throughput_fps"], 4.0)
        self.assertEqual(result["median_seconds"], 0.125)
        self.assertEqual(result["p95_seconds"], 0.125)

    def test_tail_latency_retained_without_counting_as_throughput(self):
        record = round_record()
        record["requests"][-1]["completed_at"] = 36.0
        result = summarize(record)
        self.assertTrue(result["valid"])
        self.assertEqual(result["success_by_deadline"], 120)
        self.assertEqual(result["success_in_window"], 119)

    def test_exact_window_end_excluded_from_throughput(self):
        record = round_record()
        record["requests"][-1]["completed_at"] = 35.0
        result = summarize(record)
        self.assertTrue(result["valid"])
        self.assertEqual(result["success_in_window"], 119)

    def test_tail_counts_toward_latency_quantile(self):
        record = round_record()
        record["requests"] = record["requests"][:31]
        record["requests"][-2].update(started_at=34.0, completed_at=34.8)
        record["requests"][-1].update(started_at=34.8, completed_at=37.0)
        result = summarize(record)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["p95_seconds"], 0.8)
        self.assertEqual(result["success_by_deadline"], 30)
        self.assertEqual(result["success_in_window"], 29)

    def test_unexpected_cancel_cannot_pass_with_99_percent_throughput(self):
        record = round_record()
        record["requests"][-1]["status"] = "cancelled"
        result = summarize(record)
        self.assertGreater(result["throughput_fps"] / 4.0, 0.95)
        self.assertLess(result["median_seconds"], 0.2)
        self.assertFalse(result["valid"])
        self.assertTrue(result["statistics_are_diagnostic_only"])

    def test_warmup_cancel_invalidates_round(self):
        record = round_record()
        record["requests"][0]["status"] = "cancelled"
        self.assertFalse(summarize(record)["valid"])

    def test_failure_invalidates_round(self):
        record = round_record()
        record["requests"][4]["status"] = "failure"
        self.assertFalse(summarize(record)["valid"])

    def test_timeout_never_backfilled_by_late_success(self):
        for status in ("timeout", "success", "pending"):
            with self.subTest(status=status):
                record = round_record()
                record["requests"][-1].update(status=status, completed_at=37.001)
                result = summarize(record)
                self.assertFalse(result["valid"])
                self.assertEqual(result["success_by_deadline"], 119)

    def test_missing_completion(self):
        record = round_record()
        record["requests"][-1]["completed_at"] = None
        self.assertFalse(summarize(record)["valid"])

    def test_no_submission_at_or_after_window_end(self):
        record = round_record()
        record["requests"][-1].update(started_at=35.0, completed_at=35.1)
        self.assertFalse(summarize(record)["valid"])

    def test_overlap_rejected(self):
        record = round_record()
        record["requests"][1]["completed_at"] = 6.0
        self.assertFalse(summarize(record)["valid"])

    def test_warmup_must_drain(self):
        record = round_record()
        record["requests"][0]["completed_at"] = 5.01
        self.assertFalse(summarize(record)["valid"])

    def test_empty_and_insufficient_samples(self):
        for count in (0, 29):
            with self.subTest(count=count):
                record = round_record()
                record["requests"] = record["requests"][:count + 1]
                result = summarize(record)
                self.assertFalse(result["valid"])
        self.assertIsNone(summarize({**round_record(), "requests": []})["p95_seconds"])

    def test_duplicate_id_rejected(self):
        record = round_record()
        record["requests"][-1]["id"] = "0"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize(record)

    def test_malformed_times_and_status_rejected(self):
        for field, value in (("started_at", float("nan")),
                             ("completed_at", float("inf")),
                             ("completed_at", -1), ("status", "unknown")):
            with self.subTest(field=field, value=value):
                record = round_record()
                record["requests"][1][field] = value
                with self.assertRaises(ValueError):
                    summarize(record)

    def test_fixed_window_and_deadline(self):
        for field, value in (("t1", 36.0), ("deadline", 38.0)):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    summarize({**round_record(), field: value})


if __name__ == "__main__":
    unittest.main()
