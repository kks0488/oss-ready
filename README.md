<p align="center">
  <img src="assets/banner.png" alt="oss-ready — Know what to fix before you open source." width="100%">
</p>

<p align="center"><b>English</b> · <a href="README.ko.md"><b>한국어</b></a></p>

<h2 align="center">Find the gaps before you publish.</h2>

<p align="center">
  Audit Git repositories on your computer and SSH hosts.<br>
  Get a ranked checklist from metadata, without uploading source code.
</p>

<p align="center">
  <a href="https://github.com/kks0488/oss-ready/actions/workflows/ci.yml"><img src="https://github.com/kks0488/oss-ready/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab" alt="Python 3.10 or later">
  <img src="https://img.shields.io/badge/runtime_dependencies-0-0d9488" alt="Zero Python runtime dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3fb950" alt="MIT license"></a>
</p>

<table>
<tr>
<td width="50%" valign="top">

### See what's missing
Check for a README, license file, tests, GitHub Actions, and community policies. Get a score and items to review.

</td>
<td width="50%" valign="top">

### Keep source code where it is
Inspect Git metadata, directory names, and tracked filenames. Absolute repository paths stay hidden unless you request them.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Bring scattered repositories together
Scan multiple local roots and SSH hosts in one run. Combine copies that share a GitHub origin into one result.

</td>
<td width="50%" valign="top">

### Add GitHub context when you want it
Optionally include stars, forks, releases, contributors, and authorized traffic data. Save results as Markdown or JSON.

</td>
</tr>
</table>

## Quick start

Requires **Python 3.10+** and **Git**, with no Python runtime dependencies. GitHub enrichment needs an authenticated [GitHub CLI](https://cli.github.com/). SSH scanning needs `ssh`, Python 3, and Git on the remote host.

```bash
git clone https://github.com/kks0488/oss-ready.git
cd oss-ready
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .

# Scan this repository
oss-ready --root .

# Scan a folder containing repositories
oss-ready --root ~/projects --output reports/readiness.md
```

On Windows, activate with `.venv\Scripts\activate` instead. Windows has not been tested.

## Real terminal output

These public repositories were cloned and scanned on **2026-10-16**. This is an excerpt from the actual CLI output, using shallow clones and no GitHub enrichment:

```bash
mkdir samples
git clone --depth 1 https://github.com/pallets/click.git samples/click
git clone --depth 1 https://github.com/psf/requests.git samples/requests
oss-ready --root samples
```

```text
| Score | Verdict | Repository | Stars | 14d unique clones | License | Tests | CI |
|---:|:---:|---|---:|---:|:---:|:---:|:---:|
| 51 | PREP | pallets/click | 0 | - | yes | yes | yes |
| 21 | HOLD | psf/requests | 0 | - | yes | yes | yes |
```

Scanned commits: Click `2247b35`, Requests `611c616`. Requests receives `HOLD` because tracked test certificates match secret-like filenames, including `tests/certs/valid/server/server.key`. The tool does not read those files or determine whether they contain real secrets. Without `--github`, stars remain `0` and GitHub status and traffic remain unknown. Scores change with commits and time.

## More ways to scan

```bash
# Add GitHub metadata using your existing gh login
oss-ready --root ~/projects --github --owner YOUR_GITHUB_NAME

# Combine local and SSH roots; options can be repeated
oss-ready --root ~/projects --ssh dev:/srv/projects --max-depth 3

# JSON for your own tooling
oss-ready --root ~/projects --format json --output reports/readiness.json

# Include absolute repository paths in a private report
oss-ready --root ~/projects --show-paths
```

SSH uses non-interactive authentication (`BatchMode=yes`). Configure your key and host access first. It runs metadata collectors on the host and returns metadata and filenames; source contents are not transferred. Pass `--help` for all options.

## What the results mean

| Verdict | Meaning |
| --- | --- |
| `READY` | Score at least 70, README and license file present, and no filename, fork, or archive hold. |
| `PREP` | Score at least 45 with no filename, fork, or archive hold. Review the gaps. |
| `HOLD` | Lower score, secret-like tracked filenames, a fork, or an archived repository. |

Scores are capped at 100. Signals include documentation, activity, community files, and optional GitHub adoption data. `--owner` flags other owners for review; it does not prevent a `READY` verdict. Presence checks do not validate license terms, execute tests, or verify that CI passes. Tests are detected from top-level `test/` or `tests/`; CI is detected from `.github/workflows/`.

This is a prioritization aid, not publication approval. It does not scan source contents, secrets in Git history, personal data, or copyright provenance, and it never changes repository visibility. Use a dedicated history-aware secret scanner and review the code before publishing.

## FAQ

**Does it upload my code?** No. Local scans stay on your machine. SSH sends collector scripts and returns metadata and filenames. `--github` calls GitHub's API through `gh` using repository names and your existing credentials. Reports can still expose repository names, host names, and tracked filenames; review them before sharing.

**Is this a secret scanner?** It flags tracked filenames such as `.env`, private-key names, and credential JSON files. Files ending in `.example`, `.sample`, `.template`, or `.dist` are excluded. It does not inspect contents, so fixtures can trigger holds and secrets in ordinary files can be missed.

**Why is my traffic missing?** GitHub traffic requires permission on that repository. Unavailable traffic stays unknown. Contributors and releases use the first 100 API results each. Shallow clones also undercount commits.

**Can I scan a URL?** Clone it first, then use `--root`. Ordinary clones and Git worktrees are supported. Discovery stops at each repository and skips common dependency, build, cache, and hidden directories. Bare repositories are not discovered.

**Can I use the exit code as a release gate?** A completed scan returns `0`, including reports with `HOLD`. Invalid arguments or scan/output failures return `2`. Inspect the JSON verdicts if you need your own gate.

## Development

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

GitHub Actions installs the package, runs the tests, and exercises the installed CLI on Python 3.10, 3.12, and 3.14. SSH command quoting is tested through a local shell; a live SSH host and Windows have not been tested.

<p align="center">
  <a href="CONTRIBUTING.md">Contributing</a> · <a href="SECURITY.md">Security</a> · <a href="CODE_OF_CONDUCT.md">Code of conduct</a><br>
  <a href="LICENSE">MIT</a> © kks0488
</p>

