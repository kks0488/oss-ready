from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from oss_ready.scanner import RepoSnapshot, deduplicate, discover_repositories, github_slug, scan_repository, scan_ssh, score


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class ScannerTests(unittest.TestCase):
    def test_github_slug_accepts_https_and_ssh(self) -> None:
        self.assertEqual(github_slug("https://github.com/acme/tool.git"), "acme/tool")
        self.assertEqual(github_slug("git@github.com:acme/tool.git"), "acme/tool")
        self.assertEqual(github_slug("https://user:secret@github.com/acme/tool.git"), "acme/tool")
        self.assertIsNone(github_slug("https://gitlab.com/acme/tool.git"))
        self.assertIsNone(github_slug("https://notgithub.com/acme/tool.git"))
        self.assertIsNone(github_slug("https://example.com/github.com/acme/tool.git"))
        self.assertEqual(github_slug("ssh://git@github.com/acme/tool.git"), "acme/tool")

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

    def test_worktree_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "--allow-empty", "-qm", "initial")
            worktree = root / "worktree"
            git(repo, "worktree", "add", "-qb", "sample", str(worktree))
            self.assertEqual(discover_repositories(root), [repo.resolve(), worktree.resolve()])

    def test_deduplication_preserves_unrelated_local_repositories(self) -> None:
        first = RepoSnapshot("tool", "tool")
        second = RepoSnapshot("tool", "tool")
        older = RepoSnapshot("copy", "copy", github_slug="Acme/Tool", commits=1)
        newer = RepoSnapshot("tool", "tool", github_slug="acme/tool", commits=5)
        self.assertEqual(deduplicate([first, second, older, newer]), [first, second, newer])

    def test_discovery_depth_and_skipped_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("repo", "nested/repo", "node_modules/repo", ".cache/repo"):
                repo = root / name
                repo.mkdir(parents=True)
                git(repo, "init", "-q")
            self.assertEqual(discover_repositories(root, max_depth=0), [])
            self.assertEqual(discover_repositories(root, max_depth=1), [(root / "repo").resolve()])

    def test_ssh_quotes_paths_and_collects_metadata(self) -> None:
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repositories with spaces"
            repo = root / "tool; echo SHELL_INJECTION"
            repo.mkdir(parents=True)
            git(repo, "init", "-q")
            (repo / "README.md").write_text("# Tool\n", encoding="utf-8")
            git(repo, "add", "README.md")

            def local_ssh(args, **kwargs):
                self.assertEqual(args[0], "ssh")
                # OpenSSH sends the remote command through the host's shell.
                return real_run(["sh", "-c", args[-1]], **kwargs)

            with patch("oss_ready.scanner.subprocess.run", side_effect=local_ssh):
                snapshots = scan_ssh(f"example-host:{root}")
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].name, repo.name)
            self.assertTrue(snapshots[0].readme)
            self.assertEqual(snapshots[0].location, f"example-host:{repo.name}")

    def test_ssh_rejects_option_hosts(self) -> None:
        with patch("oss_ready.scanner.subprocess.run") as run:
            with self.assertRaises(ValueError):
                scan_ssh("-oProxyCommand=invalid:/repos")
            run.assert_not_called()

    def test_ssh_metadata_failure_is_reported(self) -> None:
        with patch("oss_ready.scanner.subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, '["/repos/tool"]', ""),
            subprocess.CompletedProcess([], 1, "", "permission denied"),
        ]):
            with self.assertRaisesRegex(RuntimeError, "metadata collection failed"):
                scan_ssh("example-host:/repos")


def date_today() -> str:
    from datetime import date

    return date.today().isoformat()


if __name__ == "__main__":
    unittest.main()
