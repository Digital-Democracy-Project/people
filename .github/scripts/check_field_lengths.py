#!/usr/bin/env python3
"""Fail a people file whose text field is longer than the database column it loads into.

OPEN-877: Nebraska's people load failed in production with `value too long for type
character varying(300)` because one source `note:` was 350 characters. The load
(openstates-core utils/people/to_database.py) writes these fields into varchar columns
(openstates/data/models/people_orgs.py, base.py) and one oversized value cancels the
whole jurisdiction's load. `os-people lint` does not know the column widths, so this
does. Only fields the loader writes with a length limit are listed below. A limit is a
number of characters, as in Postgres. Exit status is 1 when any value is over its limit.

Usage:
    python .github/scripts/check_field_lengths.py                  # every people file
    python .github/scripts/check_field_lengths.py --changed-files F  # only these
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PERSON_DIRS = ("legislature", "retired", "executive", "municipalities")

# top-level field -> limit
TOP_LIMITS = {
    "name": 300,
    "email": 300,
    "given_name": 100,
    "family_name": 100,
    "gender": 100,
}
# list field -> {sub-field: limit}
LIST_LIMITS = {
    "sources": {"note": 300},
    "links": {"note": 300},
    "offices": {"address": 300, "name": 200, "voice": 30, "fax": 30},
    "other_names": {"name": 500, "note": 500},
    "other_identifiers": {"scheme": 300, "identifier": 300},
}


def over_limit(data: dict[str, Any]) -> list[tuple[str, int, int]]:
    """(field path, length, limit) for each value in `data` longer than its limit."""
    found = []
    for field, limit in TOP_LIMITS.items():
        value = data.get(field)
        if isinstance(value, str) and len(value) > limit:
            found.append((field, len(value), limit))
    for field, subs in LIST_LIMITS.items():
        for i, item in enumerate(data.get(field) or []):
            if not isinstance(item, dict):
                continue
            for sub, limit in subs.items():
                value = item.get(sub)
                if isinstance(value, str) and len(value) > limit:
                    found.append((f"{field}[{i}]/{sub}", len(value), limit))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default=REPO_ROOT / "data", type=Path)
    parser.add_argument("--changed-files", nargs="*", default=None)
    args = parser.parse_args()

    if args.changed_files is None:
        files = sorted(
            f for kind in PERSON_DIRS for f in args.data_dir.glob(f"*/{kind}/*.yml")
        )
    else:
        files = [Path(f) for f in args.changed_files if f.startswith("data/")]
    failures = 0
    for path in files:
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            continue
        for field, length, limit in over_limit(data):
            failures += 1
            print(f"{path}: {field} is {length} characters, the column holds {limit}")
    if failures:
        print(f"{failures} value(s) over the database column length", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
