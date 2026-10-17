"""Configuration, file formats and the command line."""
import contextlib
import io
import os
import tempfile
import unittest

from quanta.cli import main
from quanta.config import PRESETS, build_settings, load_overrides, parse_assignments
from quanta.io.csvio import Table, column_means, describe_columns, read_table, write_table
from quanta.io.jsonio import diff_reports, load_report, save_report
from quanta.io.report import Report, bar, format_table
from quanta.stats.resample import ar1_series, confidence_interval, percentile
from quanta.stats.table import make_sales_table, normalise_column, revenue_by_region
from quanta.util.iterutil import chunked, coerce_cell, combine_counts, extrema, first_peak, make_decay
from quanta.util.rng import Lcg


class Config(unittest.TestCase):
    def test_presets_order_by_amount_of_work(self):
        self.assertLess(PRESETS["tiny"].queens_n, PRESETS["small"].queens_n)
        self.assertLess(PRESETS["small"].queens_n, PRESETS["full"].queens_n)

    def test_overrides_from_file_and_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "q.ini")
            with open(path, "w") as fh:
                fh.write("[scale]\nqueens_n = 7\nbogus = 1\n")
            self.assertEqual(load_overrides(path), {"queens_n": 7})
            cfg = build_settings("tiny", path, ["fannkuch_n=5"])
        self.assertEqual((cfg.scale.queens_n, cfg.scale.fannkuch_n), (7, 5))

    def test_bad_assignment_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_assignments(["no_equals_sign"])
        with self.assertRaises(ValueError):
            build_settings("tiny", None, ["not_a_key=3"])


class Files(unittest.TestCase):
    def test_csv_round_trip(self):
        table = Table(["id", "name", "score"], [[1, "ann", 0.5], [2, "bob", 1.25]])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.csv")
            self.assertEqual(write_table(path, table), 2)
            loaded = read_table(path)
        self.assertEqual(loaded.rows, [[1, "ann", 0.5], [2, "bob", 1.25]])
        self.assertEqual(describe_columns(loaded), {"id": "int", "name": "text", "score": "float"})
        self.assertEqual(column_means(loaded, ["score"]), {"score": 0.875})

    def test_ragged_rows_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.csv")
            with open(path, "w") as fh:
                fh.write("a,b\n1,2\n3\n4,5\n")
            self.assertEqual(len(read_table(path)), 2)

    def test_missing_and_empty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                read_table(os.path.join(tmp, "nope.csv"))
            empty = os.path.join(tmp, "empty.csv")
            open(empty, "w").close()
            with self.assertRaises(ValueError):
                read_table(empty)

    def test_json_report_round_trip_and_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.json")
            save_report(path, {"a": {"x": 1}, "b": 2})
            self.assertEqual(load_report(path), {"a": {"x": 1}, "b": 2})
        self.assertEqual(diff_reports({"a": {"x": 1}, "b": 2}, {"a": {"x": 3}, "b": 2}),
                         {"a": {"x": {"old": 1, "new": 3}}})

    def test_report_rendering(self):
        rep = Report("T")
        sec = rep.section("s")
        rep.record(sec, "pi", 3.14159265)
        self.assertEqual(rep.render().splitlines()[-1], "pi:                      3.14159")
        self.assertEqual(format_table(["a", "bb"], [[1, 2.5]]).splitlines()[0], "a  bb ")
        self.assertEqual(bar(5, 10, 10), "#####")


class Stats(unittest.TestCase):
    def test_sales_table_is_reproducible(self):
        t1, t2 = make_sales_table(Lcg(4), 50), make_sales_table(Lcg(4), 50)
        self.assertEqual(t1.rows, t2.rows)
        self.assertAlmostEqual(sum(revenue_by_region(t1).values()), sum(t1.float_column("revenue")))

    def test_normalise_column_has_unit_variance(self):
        z = normalise_column([1.0, 2.0, 3.0, 4.0, 10.0])
        self.assertAlmostEqual(sum(z), 0.0)
        self.assertAlmostEqual(sum(v * v for v in z) / len(z), 1.0)

    def test_percentile_and_interval(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 50), 2.5)
        lo, hi = confidence_interval(Lcg(2), [1.0, 2.0, 3.0, 4.0, 5.0], 200)
        self.assertLess(lo, 3.0)
        self.assertGreater(hi, 3.0)

    def test_ar1_level_shift(self):
        series = ar1_series(Lcg(8), 400, 0.5, shift_at=200, shift=5.0)
        self.assertGreater(sum(series[200:]) / 200, sum(series[:200]) / 200 + 3.0)


class Helpers(unittest.TestCase):
    def test_iteration_helpers(self):
        self.assertEqual([list(c) for c in chunked([1, 2, 3, 4, 5], 2)], [[1, 2], [3, 4], [5]])
        self.assertEqual(extrema([3, 1, 4]), (1, 4))
        self.assertEqual(first_peak([0, 1, 5, 2, 9], 3), 2)
        self.assertIsNone(first_peak([0, 1, 2], 3))
        self.assertEqual(combine_counts({"a": 1}, {"a": 2, "b": 1}), {"a": 3, "b": 1})

    def test_decay_closure_keeps_state(self):
        decay = make_decay(0.5)
        self.assertEqual((decay(8.0), decay(8.0)), (4.0, 2.0))

    def test_coerce_cell(self):
        self.assertEqual([coerce_cell(c) for c in ("7", "2.5", " x ")], [7, 2.5, "x"])


class CommandLine(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_single_job_prints_its_section(self):
        code, text = self.run_cli("--tiny", "puzzles")
        self.assertEqual(code, 0)
        self.assertIn("fannkuch(6):", text)
        self.assertIn("queens(6):", text)

    def test_runs_are_deterministic_and_seeded(self):
        a = self.run_cli("--tiny", "graph")[1]
        self.assertEqual(a, self.run_cli("--tiny", "graph")[1])
        self.assertNotEqual(a, self.run_cli("--tiny", "--seed", "5", "graph")[1])

    def test_suite_covers_every_job_and_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.json")
            code, text = self.run_cli("--tiny", "--json", path)
            self.assertEqual(code, 0)
            results = load_report(path)
        self.assertEqual(sorted(results), ["graph", "linalg", "optimisation", "puzzles", "signals and statistics",
                                           "simulation", "text"])
        self.assertIn("section", text)

    def test_list_and_bad_arguments(self):
        self.assertIn("scales:", self.run_cli("list")[1])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["--tiny", "--set", "oops"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
