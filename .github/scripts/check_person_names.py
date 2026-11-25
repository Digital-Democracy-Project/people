#!/usr/bin/env python3
"""Fail a people file whose name is a note, or a second copy of a shorter name.

OPEN-891: Montana's roster prints "Resigned from HD29 on 2023-01-10 and replaced
by ..." under a member's name; the scraper took the whole cell as the name, so a
retired file named "<Name> Resigned From Hd29 On 2023-01-10 And Replaced By
<Name>" sat next to the real record and showed in a legislator list. Two rules,
both about a bad `name:`:

1. note-like name: a digit, a colon, a status word (resigned, replaced, vacated,
   vacancy, deceased, died) or more than 60 characters. A nickname in
   parentheses ("Fred (Coach) Plump") is a legitimate name and passes.
2. longer-name copy: in one state, two files share an email or a link and a
   chamber and district, and one name is the other's words plus more words.
   (Two files with the SAME name are check_duplicate_people.py's job.)

Without --changed-files every file is checked (a report of what is there
today). With it, only findings that involve a touched file; with --base-ref as
well, a touched file counts only if it is new or its name differs from its name
at that revision, so a long-standing finding does not fail a change that merely
edits or moves the file (the reasoning of check_duplicate_people.py). Exit
status is 1 on any finding.

Usage:
    python .github/scripts/check_person_names.py                  # every file
    python .github/scripts/check_person_names.py --changed-files F --base-ref SHA
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from _git_base import read_at_base

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PERSON_DIRS = ("legislature", "retired", "executive", "municipalities")
NOTE_WORD = re.compile(
    r"\b(resign(?:ed|s|ation)|replaced|vacated|vacancy|deceased|died)\b", re.I
)
MAX_NAME = 60

Person = tuple[Path, dict[str, Any]]


def note_reason(name: str) -> str | None:
    """Why `name` reads like a note, or None."""
    if re.search(r"\d", name):
        return "has a digit"
    if ":" in name:
        return "has a colon"
    if NOTE_WORD.search(name):
        return "has a status word"
    if len(name) > MAX_NAME:
        return f"is {len(name)} characters"
    return None


def words(name: str) -> list[str]:
    return re.sub(r"[^\w]+", " ", str(name).casefold()).split()


def extends(longer: list[str], shorter: list[str]) -> bool:
    """`longer` holds `shorter`'s words in order, plus at least one more word."""
    n = len(shorter)
    if len(longer) <= n or n == 0:
        return False
    return any(longer[i : i + n] == shorter for i in range(len(longer) - n + 1))


def seats(data: dict[str, Any]) -> set[tuple[str, str]]:
    roles = [r for r in data.get("roles") or [] if isinstance(r, dict)]
    return {(str(r.get("type")), str(r.get("district"))) for r in roles}


def link_keys(data: dict[str, Any]) -> set[str]:
    """The email and every link or source URL, as keys two files can share."""
    keys = set()
    if data.get("email"):
        keys.add("email:" + str(data["email"]).strip().casefold())
    for field in ("links", "sources"):
        for item in data.get(field) or []:
            if isinstance(item, dict) and item.get("url"):
                url = str(item["url"]).strip().casefold()
                keys.add("url:" + re.sub(r"^https?://(www\.)?", "", url).rstrip("/"))
    return keys


def load(data_dir: Path, states: set[str] | None) -> dict[str, list[Person]]:
    """Person files by state (only `states` when given: a change reads its own)."""
    by_state: dict[str, list[Person]] = defaultdict(list)
    for kind in PERSON_DIRS:
        for path in sorted(data_dir.glob(f"*/{kind}/*.yml")):
            state = path.parent.parent.name
            if states is not None and state not in states:
                continue
            data = yaml.safe_load(path.read_text())
            if isinstance(data, dict):
                by_state[state].append((path, data))
    return by_state


def name_is_new(path: Path, base_ref: str | None) -> bool:
    """True when `path` is new or has a different name than at `base_ref`."""
    if not base_ref:
        return True
    old = read_at_base(base_ref, path)
    if old is None:
        return True
    old_data = yaml.safe_load(old)
    if not isinstance(old_data, dict):
        return True
    return old_data.get("name") != yaml.safe_load(path.read_text()).get("name")


def note_findings(people: list[Person], touched: set[Path] | None) -> list[str]:
    out = []
    for path, data in people:
        reason = note_reason(str(data.get("name") or ""))
        if reason and (touched is None or path.resolve() in touched):
            out.append(f"{path}: name {data['name']!r} {reason}: a note, not a name")
    return out


def copy_findings(people: list[Person], touched: set[Path] | None) -> list[str]:
    """Pairs sharing a key and a seat, where one name extends the other."""
    by_key = defaultdict(list)
    for index, (_, data) in enumerate(people):
        for key in link_keys(data):
            by_key[key].append(index)
    pairs = {(i, j) for idx in by_key.values() for i in idx for j in idx if i < j}
    out = []
    for i, j in sorted(pairs):
        (pa, da), (pb, db) = people[i], people[j]
        if touched is not None and not {pa.resolve(), pb.resolve()} & touched:
            continue
        if not seats(da) & seats(db):
            continue
        wa, wb = words(da.get("name") or ""), words(db.get("name") or "")
        if extends(wb, wa):
            (pa, da), (pb, db) = (pb, db), (pa, da)
        elif not extends(wa, wb):
            continue
        out.append(
            f"{pa}: name {da['name']!r} is {pb.name} with extra words (same email "
            "or link, same seat): a second copy of one person"
        )
    return out


def findings(
    data_dir: Path, changed: set[Path] | None, base_ref: str | None = None
) -> list[str]:
    """One line per finding; with `changed`, only those a touched file is in."""
    touched = None
    states = None
    if changed is not None:
        touched = {
            p.resolve() for p in changed if p.is_file() and name_is_new(p, base_ref)
        }
        states = {p.parent.parent.name for p in touched}
    out = []
    for people in load(data_dir, states).values():
        out += note_findings(people, touched)
        out += copy_findings(people, touched)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default=REPO_ROOT / "data", type=Path)
    parser.add_argument("--changed-files", nargs="*", default=None)
    parser.add_argument("--base-ref", default=None)
    args = parser.parse_args()
    changed = None
    if args.changed_files is not None:
        changed = {Path(f) for f in args.changed_files if f.startswith("data/")}
    found = findings(args.data_dir, changed, args.base_ref)
    for line in found:
        print(line)
    if found:
        print(f"{len(found)} person name problem(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
