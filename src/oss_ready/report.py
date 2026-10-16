from __future__ import annotations

import json
from datetime import datetime, timezone

from .scanner import RepoSnapshot


def render_json(snapshots: list[RepoSnapshot]) -> str:
    return json.dumps(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repositories": [item.to_dict() for item in snapshots],
        },
        indent=2,
        ensure_ascii=False,
    ) + "\n"


def render_markdown(snapshots: list[RepoSnapshot]) -> str:
    lines = [
        "# OSS Readiness Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "> This is a prioritization aid, not proof that a repository is safe to publish.",
        "> Review copyright, personal data, credentials, and git history before changing visibility.",
        "",
        "| Score | Verdict | Repository | Stars | 14d unique clones | License | Tests | CI |",
        "|---:|:---:|---|---:|---:|:---:|:---:|:---:|",
    ]
    for item in snapshots:
        repo = item.github_slug or item.name
        clones = "-" if item.unique_clones_14d is None else str(item.unique_clones_14d)
        lines.append(
            f"| {item.score} | {item.verdict} | {repo} | {item.stars} | {clones} | "
            f"{'yes' if item.license else 'no'} | {'yes' if item.tests else 'no'} | {'yes' if item.ci else 'no'} |"
        )

    lines.extend(["", "## Details", ""])
    for item in snapshots:
        repo = item.github_slug or item.name
        lines.extend([f"### {repo}", "", f"- Location: `{item.location}`", f"- Score: {item.score}/100 ({item.verdict})"])
        if item.strengths:
            lines.append(f"- Strengths: {', '.join(item.strengths)}")
        if item.blockers:
            lines.append(f"- Review: {', '.join(item.blockers)}")
        if item.secret_like_files:
            lines.append(f"- Secret-like tracked filenames: {', '.join(f'`{name}`' for name in item.secret_like_files)}")
        lines.append("")
    return "\n".join(lines)

