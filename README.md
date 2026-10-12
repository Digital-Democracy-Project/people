# Open States People

![Lint YAML](https://github.com/openstates/people/workflows/Lint%20YAML/badge.svg)

This repository contains YAML files with official information on state legislators, governors, and some municipal leaders.

## Digital Democracy Project fork

[Digital Democracy Project](https://digitaldemocracyproject.org) maintains this fork. Its `main` is the public project's `main` **plus our carried fixes**, and production reads from it:

- A nightly job (`.github/workflows/ddp-sync-upstream.yml`) keeps one standing pull request open from the public project's `main` into this fork's `main`, and runs yamllint, `os-people lint` on each changed state, the duplicate-person check and the role-date check on it. A person reviews and approves it before anything reaches `main`.
- A fix is merged here through a pull request (with a green `Lint YAML`) without waiting for upstream review, and is also sent upstream. Its commit message ends with `Upstream-PR: openstates/people#N` and `Source: <url>` trailers. Do not put "fix", "fixes", "close" or "resolve" directly before an upstream reference in a PR body or commit message: GitHub would close the upstream pull request when ours merges. When upstream merges the same change, the standing pull request shows no difference for it. A fix upstream declines but our source supports stays carried here.
- The public project's `Update Database` workflow is switched off on this fork (it needs cloud credentials we do not have); `Lint YAML` stays on.
- Remotes on a DDP host: `origin` → this fork, `upstream` → the public project.

## Links

* [People Issues](https://github.com/openstates/issues/issues?q=is%3Aissue+is%3Aopen+label%3Adata%3Apeople)
* [Contributor's Guide](https://docs.openstates.org/contributing/)
* [Documentation](https://docs.openstates.org/contributing/people/)
* [Open States Discussions](https://github.com/openstates/issues/discussions)
* [Code of Conduct](https://docs.openstates.org/code-of-conduct/)


## Data Layout

All data within the data directory is organized by state.  Within a given state directory you may find the following:

  * legislature - people that are currently serving in the legislature
  * executive - people that are currently serving in the state executive (e.g. governors)
  * municipalities - people currently serving in local government (e.g. mayors)
  * retired - people not currently serving any tracked roles
  * committees - committee data

## About this Repo

A lot of inspiration was taken from the [congress-legislators](https://github.com/unitedstates/congress-legislators) project that has been maintaining this data for the United States Congress.

New as of 2021: the data/us directory is also directly ported from the congress-legislators repo, reproduced here in our schema for ease of use for people using both data sets.

Historically Open States has scraped this data, but given the relatively infrequent changes and the manual labor required to retire & merge legislators- we have decided to move in this direction in the hopes of improving the data and making it more accessible for contributors.

Also, please note that this portion of the project is in the public domain in the United States with all copyright waived via a [CC0](https://creativecommons.org/publicdomain/zero/1.0/) dedication.  By contributing you agree to waive all copyright claims.
