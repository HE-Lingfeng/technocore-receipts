import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = subprocess.run([sys.executable, "examples/make_demo.py"], cwd=ROOT,
                                  capture_output=True, check=True).stdout

    def run_cli(self, *args, data=None):
        return subprocess.run([sys.executable, "-m", "technocore_receipts", *args], cwd=ROOT,
                              input=data, capture_output=True)

    def test_stdin_and_demo(self):
        result = self.run_cli("-", "--room", "demo-room", data=self.demo)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["summary"]["signatures"]["valid"], 2)
        self.assertNotIn(b"Synthetic demonstration", result.stdout)

    def test_file_and_stdin_reports_are_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.jsonl"
            path.write_bytes(self.demo)
            from_file = self.run_cli(str(path), "--room", "demo-room")
        from_stdin = self.run_cli("-", "--room", "demo-room", data=self.demo)
        self.assertEqual(from_file.stdout, from_stdin.stdout)

    def test_wrong_room_has_exit_one_and_a_report(self):
        result = self.run_cli("-", "--room", "other-room", data=self.demo)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")

    def test_empty_input_has_exit_one(self):
        result = self.run_cli("-", "--room", "demo-room", data=b"")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "incomplete")

    def test_bad_room_has_exit_two_without_report(self):
        result = self.run_cli("-", "--room", "bad|room", data=self.demo)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(json.loads(result.stderr)["error"], "invalid_room")

    def test_missing_file_has_exit_two_without_echoing_path(self):
        result = self.run_cli("does-not-exist-private-name", "--room", "demo-room")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "input_io_error")
        self.assertNotIn(b"private-name", result.stderr)

    def test_missing_room_is_usage_error(self):
        result = self.run_cli("-", data=self.demo)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
