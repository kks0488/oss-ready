from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .report import render_json, render_markdown
from .scanner import deduplicate, enrich_github, scan_local, scan_ssh, score


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="oss-ready",
        description="Audit local and SSH-hosted Git repositories without reading file contents.",
    )
    result.add_argument("--root", action="append", default=[], help="Local root to scan; repeatable")
    result.add_argument("--ssh", action="append", default=[], metavar="HOST:/PATH", help="SSH root to scan; repeatable")
    result.add_argument("--max-depth", type=int, default=4, help="Maximum directory depth (default: 4)")
    result.add_argument("--github", action="store_true", help="Enrich GitHub repos through authenticated gh CLI")
    result.add_argument("--owner", help="Expected GitHub owner; other origins are flagged")
    result.add_argument("--show-paths", action="store_true", help="Include absolute paths in output")
    result.add_argument("--format", choices=("markdown", "json"), default="markdown")
    result.add_argument("--output", type=Path, help="Write report to a file instead of stdout")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.root and not args.ssh:
        parser().error("provide at least one --root or --ssh target")
    if args.max_depth < 0:
        parser().error("--max-depth must be non-negative")
    if args.github and shutil.which("gh") is None:
        parser().error("--github requires the GitHub CLI (gh)")

    snapshots = []
    try:
        for root in args.root:
            snapshots.extend(scan_local(Path(root), args.max_depth, args.show_paths))
        for target in args.ssh:
            snapshots.extend(scan_ssh(target, args.max_depth, args.show_paths))
        snapshots = deduplicate(snapshots)
        for snapshot in snapshots:
            if args.github:
                enrich_github(snapshot)
            score(snapshot, owner=args.owner)
        snapshots.sort(key=lambda item: (-item.score, item.github_slug or item.name))

        rendered = render_json(snapshots) if args.format == "json" else render_markdown(snapshots)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"oss-ready: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

