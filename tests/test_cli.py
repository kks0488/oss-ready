from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from oss_ready.cli import main
from oss_ready.scanner import RepoSnapshot


class CliTests(unittest.TestCase):
    def test_json_report_hides_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "tool"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--root", str(repo), "--format", "json"]), 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["repositories"][0]["location"], "tool")
            self.assertNotIn(temp, output.getvalue())

    def test_output_creates_report_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "reports" / "readiness.md"
            with patch("oss_ready.cli.scan_local", return_value=[RepoSnapshot("tool", "tool")]):
                self.assertEqual(main(["--root", temp, "--output", str(output)]), 0)
            self.assertIn("missing license", output.read_text(encoding="utf-8"))

    def test_runtime_failures_return_error_without_traceback(self) -> None:
        for error in (OSError("git unavailable"), subprocess.TimeoutExpired("git", 20)):
            with self.subTest(error=type(error).__name__):
                stderr = io.StringIO()
                with patch("oss_ready.cli.scan_local", side_effect=error), contextlib.redirect_stderr(stderr):
                    self.assertEqual(main(["--root", "."]), 2)
                self.assertIn("oss-ready:", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_unwritable_report_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stderr = io.StringIO()
            with patch("oss_ready.cli.scan_local", return_value=[]), contextlib.redirect_stderr(stderr):
                self.assertEqual(main(["--root", ".", "--output", temp]), 2)
            self.assertIn("oss-ready:", stderr.getvalue())
