from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from oss_ready.scanner import RepoSnapshot, discover_repositories, github_slug, scan_repository, score


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class ScannerTests(unittest.TestCase):
    def test_github_slug_accepts_https_and_ssh(self) -> None:
        self.assertEqual(github_slug("https://github.com/acme/tool.git"), "acme/tool")
        self.assertEqual(github_slug("git@github.com:acme/tool.git"), "acme/tool")
        self.assertEqual(github_slug("https://user:secret@github.com/acme/tool.git"), "acme/tool")
        self.assertIsNone(github_slug("https://gitlab.com/acme/tool.git"))

    def test_discovery_and_secret_filename_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "tool"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("# Tool\n", encoding="utf-8")
            (repo / ".env.example").write_text("TOKEN=example\n", encoding="utf-8")
            (repo / "private.pem").write_text("not-a-real-key\n", encoding="utf-8")
            git(repo, "add", "README.md", ".env.example", "private.pem")
            git(repo, "commit", "-qm", "initial")

            self.assertEqual(discover_repositories(root), [repo.resolve()])
            snapshot = scan_repository(repo)
            self.assertEqual(snapshot.secret_like_files, ["private.pem"])
            self.assertTrue(snapshot.readme)

    def test_scoring_blocks_secret_like_files(self) -> None:
        snapshot = RepoSnapshot(
            name="tool",
            location="tool",
            public=True,
            fork=False,
            license=True,
            readme=True,
            tests=True,
            ci=True,
            contributing=True,
            code_of_conduct=True,
            security_policy=True,
            commits=100,
            last_commit=date_today(),
            stars=100,
            releases=3,
            contributors=3,
            secret_like_files=["prod.key"],
        )
        score(snapshot, owner="acme")
        self.assertEqual(snapshot.verdict, "HOLD")
        self.assertIn("tracked secret-like filenames require review", snapshot.blockers)


def date_today() -> str:
    from datetime import date

    return date.today().isoformat()


if __name__ == "__main__":
    unittest.main()
