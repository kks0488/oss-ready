# OSS Ready

Privacy-first readiness auditing for Git repositories scattered across local folders and SSH hosts.

`oss-ready` helps maintainers answer two separate questions:

1. Which repositories are worth investing in as open source?
2. Which repositories need licensing, community, provenance, or secret-file work before publication?

It inspects repository metadata and tracked filenames. It does **not** upload source code, print
credential values, or change repository visibility.

## What it checks

- README and open-source license
- tests and GitHub Actions workflows
- contribution, conduct, and security policies
- commit count and freshness
- GitHub stars, forks, releases, contributors, and 14-day traffic (when authorized)
- tracked filenames that look like credentials or private keys
- repository ownership, forks, and archived state

The score is a prioritization aid. A high score is not proof that code is legally or technically safe
to publish; copyright, personal data, secrets, and full Git history still require human review.

## Quick start

Requires Python 3.10+ and Git. GitHub enrichment additionally requires an authenticated
[GitHub CLI](https://cli.github.com/).

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

# Local repositories
oss-ready --root ~/projects --github --owner YOUR_GITHUB_NAME

# Local and remote repositories together
oss-ready \
  --root ~/projects \
  --ssh dev:/home/dev/projects \
  --github \
  --owner YOUR_GITHUB_NAME \
  --output reports/readiness.md
```

Absolute paths are hidden by default. Add `--show-paths` only for a private report.

## Privacy and threat model

For local repositories, `oss-ready` reads Git metadata, top-level names, and tracked filenames.
For SSH repositories, it runs a small Python metadata collector on the host. Source contents are not
copied or retained. GitHub enrichment calls `gh api` and relies on the permissions of your existing
GitHub CLI session.

The filename check intentionally produces false positives rather than reading suspected secret
contents. `.env.example`, `.sample`, `.template`, and `.dist` files are treated as documentation,
not secrets. Use a dedicated history-aware secret scanner before publication.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

MIT

