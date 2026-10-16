from __future__ import annotations

import json
import math
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".cache",
    ".git",
    ".idea",
    ".next",
    ".npm",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "Library",
    "backups",
    "build",
    "dist",
    "node_modules",
    "vendor",
}

SECRET_NAME_RE = re.compile(
    r"(^|/)(\.env($|\.)|id_(rsa|dsa|ecdsa|ed25519)$|credentials[^/]*\.json$|"
    r"service[-_.]?account[^/]*\.json$|[^/]+\.(pem|p12|pfx|key)$)",
    re.IGNORECASE,
)
SAFE_SECRET_SUFFIXES = (".example", ".sample", ".template", ".dist")
GITHUB_RE = re.compile(
    r"(?:github\.com[:/])(?P<owner>[^/]+?)/(?P<repo>[^/]+?)(?:\.git)?$",
    re.IGNORECASE,
)


@dataclass
class RepoSnapshot:
    name: str
    location: str
    github_slug: str | None = None
    commits: int = 0
    last_commit: str | None = None
    license: bool = False
    readme: bool = False
    tests: bool = False
    ci: bool = False
    contributing: bool = False
    code_of_conduct: bool = False
    security_policy: bool = False
    secret_like_files: list[str] = field(default_factory=list)
    public: bool | None = None
    fork: bool | None = None
    archived: bool | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    contributors: int | None = None
    releases: int | None = None
    views_14d: int | None = None
    unique_views_14d: int | None = None
    clones_14d: int | None = None
    unique_clones_14d: int | None = None
    score: int = 0
    verdict: str = "HOLD"
    blockers: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def discover_repositories(root: Path, max_depth: int = 4) -> list[Path]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"scan root is not a directory: {root}")

    repositories: list[Path] = []
    root_depth = len(root.parts)
    for current, dirs, _files in os.walk(root):
        path = Path(current)
        depth = len(path.parts) - root_depth
        dirs[:] = [
            name
            for name in dirs
            if name not in SKIP_DIRS and not (name.startswith(".") and name != ".git")
        ]
        if (path / ".git").is_dir():
            repositories.append(path)
            dirs[:] = []
            continue
        if depth >= max_depth:
            dirs[:] = []
    return sorted(repositories)


def github_slug(origin: str) -> str | None:
    sanitized = re.sub(r"https://[^/@]+:[^@]+@", "https://", origin.strip())
    match = GITHUB_RE.search(sanitized)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}"


def _has_any(repo: Path, names: Iterable[str]) -> bool:
    lowered = {item.name.lower() for item in repo.iterdir()}
    return any(name.lower() in lowered for name in names)


def _tracked_secret_like(repo: Path) -> list[str]:
    tracked = _run(["git", "ls-files", "-z"], cwd=repo).split("\0")
    findings: list[str] = []
    for filename in tracked:
        lowered = filename.lower()
        if not filename or lowered.endswith(SAFE_SECRET_SUFFIXES):
            continue
        if SECRET_NAME_RE.search(filename):
            findings.append(filename)
    return sorted(findings)


def scan_repository(repo: Path, location: str | None = None) -> RepoSnapshot:
    origin = _run(["git", "remote", "get-url", "origin"], cwd=repo)
    last_commit = _run(["git", "log", "-1", "--format=%cs"], cwd=repo) or None
    commits_text = _run(["git", "rev-list", "--count", "HEAD"], cwd=repo)
    files = {item.name.lower() for item in repo.iterdir()}
    snapshot = RepoSnapshot(
        name=repo.name,
        location=location or repo.name,
        github_slug=github_slug(origin),
        commits=int(commits_text or 0),
        last_commit=last_commit,
        license=any(name.startswith(("license", "copying")) for name in files),
        readme=any(name.startswith("readme") for name in files),
        tests=(repo / "tests").is_dir() or (repo / "test").is_dir(),
        ci=(repo / ".github" / "workflows").is_dir(),
        contributing=_has_any(repo, ["CONTRIBUTING.md", "CONTRIBUTING"]),
        code_of_conduct=_has_any(repo, ["CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT"]),
        security_policy=_has_any(repo, ["SECURITY.md", "SECURITY"]),
        secret_like_files=_tracked_secret_like(repo),
    )
    return snapshot


def scan_local(root: Path, max_depth: int = 4, show_paths: bool = False) -> list[RepoSnapshot]:
    snapshots = []
    for repo in discover_repositories(root, max_depth=max_depth):
        label = str(repo) if show_paths else repo.name
        snapshots.append(scan_repository(repo, label))
    return snapshots


REMOTE_PROGRAM = r'''
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
max_depth = int(sys.argv[2])
skip = {".cache", ".git", ".idea", ".next", ".npm", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "Library", "backups", "build", "dist", "node_modules", "vendor"}
found = []
base_depth = len(root.parts)
for current, dirs, _files in os.walk(root):
    path = Path(current)
    depth = len(path.parts) - base_depth
    dirs[:] = [d for d in dirs if d not in skip and not (d.startswith(".") and d != ".git")]
    if (path / ".git").is_dir():
        found.append(str(path))
        dirs[:] = []
    elif depth >= max_depth:
        dirs[:] = []
print(json.dumps(found))
'''


def scan_ssh(spec: str, max_depth: int = 4, show_paths: bool = False) -> list[RepoSnapshot]:
    if ":" not in spec:
        raise ValueError("SSH target must use HOST:/absolute/path")
    host, remote_root = spec.split(":", 1)
    if not host or not remote_root.startswith("/"):
        raise ValueError("SSH target must use HOST:/absolute/path")

    discovery = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "python3", "-", remote_root, str(max_depth)],
        input=REMOTE_PROGRAM,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if discovery.returncode != 0:
        raise RuntimeError(f"SSH discovery failed for {host}: {discovery.stderr.strip()}")

    remote_repos = json.loads(discovery.stdout)
    snapshots: list[RepoSnapshot] = []
    for remote_repo in remote_repos:
        # Metadata is queried remotely; no repository contents or archives are transferred.
        metadata_script = r'''
import json, subprocess, sys
from pathlib import Path
p=Path(sys.argv[1])
def run(*args):
 r=subprocess.run(args,cwd=p,capture_output=True,text=True,timeout=20)
 return r.stdout.strip() if r.returncode==0 else ""
items={x.name.lower() for x in p.iterdir()}
tracked=run("git","ls-files","-z").split("\0")
print(json.dumps({
 "name":p.name,
 "origin":run("git","remote","get-url","origin"),
 "commits":int(run("git","rev-list","--count","HEAD") or 0),
 "last_commit":run("git","log","-1","--format=%cs") or None,
 "license":any(x.startswith(("license","copying")) for x in items),
 "readme":any(x.startswith("readme") for x in items),
 "tests":(p/"tests").is_dir() or (p/"test").is_dir(),
 "ci":(p/".github"/"workflows").is_dir(),
 "contributing":"contributing.md" in items or "contributing" in items,
 "code_of_conduct":"code_of_conduct.md" in items or "code_of_conduct" in items,
 "security_policy":"security.md" in items or "security" in items,
 "tracked":tracked,
}))
'''
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", host, "python3", "-", remote_repo],
            input=metadata_script,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            continue
        data = json.loads(result.stdout)
        secrets = []
        for filename in data.pop("tracked"):
            lowered = filename.lower()
            if filename and not lowered.endswith(SAFE_SECRET_SUFFIXES) and SECRET_NAME_RE.search(filename):
                secrets.append(filename)
        origin = data.pop("origin")
        location = f"{host}:{remote_repo}" if show_paths else f"{host}:{data['name']}"
        snapshots.append(
            RepoSnapshot(
                location=location,
                github_slug=github_slug(origin),
                secret_like_files=sorted(secrets),
                **data,
            )
        )
    return snapshots


def _gh_json(path: str) -> object | None:
    output = _run(["gh", "api", path])
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def enrich_github(snapshot: RepoSnapshot) -> None:
    if not snapshot.github_slug:
        return
    data = _gh_json(f"repos/{snapshot.github_slug}")
    if not isinstance(data, dict):
        return
    snapshot.public = not bool(data.get("private"))
    snapshot.fork = bool(data.get("fork"))
    snapshot.archived = bool(data.get("archived"))
    snapshot.stars = int(data.get("stargazers_count") or 0)
    snapshot.forks = int(data.get("forks_count") or 0)
    snapshot.open_issues = int(data.get("open_issues_count") or 0)

    contributors = _gh_json(f"repos/{snapshot.github_slug}/contributors?per_page=100&anon=1")
    releases = _gh_json(f"repos/{snapshot.github_slug}/releases?per_page=100")
    snapshot.contributors = len(contributors) if isinstance(contributors, list) else None
    snapshot.releases = len(releases) if isinstance(releases, list) else None

    views = _gh_json(f"repos/{snapshot.github_slug}/traffic/views")
    clones = _gh_json(f"repos/{snapshot.github_slug}/traffic/clones")
    if isinstance(views, dict):
        snapshot.views_14d = int(views.get("count") or 0)
        snapshot.unique_views_14d = int(views.get("uniques") or 0)
    if isinstance(clones, dict):
        snapshot.clones_14d = int(clones.get("count") or 0)
        snapshot.unique_clones_14d = int(clones.get("uniques") or 0)


def _days_since(value: str | None) -> int | None:
    if not value:
        return None
    try:
        committed = date.fromisoformat(value[:10])
    except ValueError:
        return None
    return (datetime.now(timezone.utc).date() - committed).days


def score(snapshot: RepoSnapshot, owner: str | None = None) -> None:
    points = 0
    blockers: list[str] = []
    strengths: list[str] = []

    if snapshot.public:
        points += 12
        strengths.append("public repository")
    if snapshot.fork is False:
        points += 8
    elif snapshot.fork:
        blockers.append("repository is a fork")
    if owner and snapshot.github_slug and snapshot.github_slug.split("/", 1)[0].lower() != owner.lower():
        blockers.append(f"origin is not owned by {owner}")
    if snapshot.archived:
        blockers.append("repository is archived")
    if snapshot.license:
        points += 15
        strengths.append("license present")
    else:
        blockers.append("missing license")
    if snapshot.readme:
        points += 10
    else:
        blockers.append("missing README")
    if snapshot.tests:
        points += 10
        strengths.append("tests present")
    if snapshot.ci:
        points += 8
        strengths.append("CI present")
    if snapshot.contributing:
        points += 5
    if snapshot.code_of_conduct:
        points += 4
    if snapshot.security_policy:
        points += 4
    if snapshot.commits >= 10:
        points += 5
    age = _days_since(snapshot.last_commit)
    if age is not None and age <= 180:
        points += 8
        strengths.append("recent activity")
    elif age is not None and age > 365:
        blockers.append("no commit in the last year")
    points += min(8, int(math.log2(snapshot.stars + 1) * 2))
    points += min(4, snapshot.forks)
    if snapshot.contributors and snapshot.contributors > 1:
        points += min(4, snapshot.contributors - 1)
        strengths.append("multiple contributors")
    if snapshot.releases:
        points += min(5, snapshot.releases)
        strengths.append("published releases")
    if snapshot.unique_clones_14d and snapshot.unique_clones_14d >= 10:
        points += min(10, 2 + snapshot.unique_clones_14d // 20)
        strengths.append("recent clone activity")
    if snapshot.secret_like_files:
        points -= 30
        blockers.append("tracked secret-like filenames require review")

    snapshot.score = max(0, min(100, points))
    snapshot.blockers = blockers
    snapshot.strengths = strengths
    hard_block = bool(snapshot.secret_like_files or snapshot.fork or snapshot.archived)
    if snapshot.score >= 70 and not hard_block and snapshot.license and snapshot.readme:
        snapshot.verdict = "READY"
    elif snapshot.score >= 45 and not hard_block:
        snapshot.verdict = "PREP"
    else:
        snapshot.verdict = "HOLD"


def deduplicate(snapshots: Iterable[RepoSnapshot]) -> list[RepoSnapshot]:
    selected: dict[str, RepoSnapshot] = {}
    for snapshot in snapshots:
        key = (snapshot.github_slug or snapshot.location).lower()
        previous = selected.get(key)
        if previous is None or snapshot.commits > previous.commits:
            selected[key] = snapshot
    return list(selected.values())
