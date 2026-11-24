#!/usr/bin/env python3
"""List Maine legislators whose file lacks the name roll calls print for them.

Maine roll calls (LawMakerWeb rollcall.asp) carry no district and no member id: every
member is printed as "SURNAME of Town" in the House and "SURNAME of County" in the
Senate, and that string is the only key core's resolve_person() has. It matches the
string against a person's name and other_names, so a member resolves only if their
file holds the exact printed form. OPEN-697 (Senate) and OPEN-812 (House, 17 members,
8.8% of Maine's votes unmatched) were both this gap.

This check reads a saved House roll call and a saved Senate roll call (under
fixtures/me/) and, for each legislator seated in that chamber on the roll call's date,
looks among the file's name and other_names for a printed name carrying the file's
family_name. A member with none is listed, with the printed name(s) carrying their
surname that no other seated member already holds, as the likely fix. A printed name
held by two seated members of the chamber is listed too (core could not pick between
them). Exit status is 1 when anything is listed.
Tribal representatives (a district that is not a number) do not vote and are skipped.

Members seated after the saved roll call are not covered (they are counted at the end):
when one takes a seat, refresh the saved roll calls from a recent vote (the source is in
each fixture's file name: LawMakerWeb/rollcall.asp?ID=<id>&serialnumber=<n>) and run
this again.

With --current (OPEN-854; what CI runs on every change) no saved roll call is read, so
nothing goes stale: every member seated today (a voting House or Senate seat with no end
date, or one ending today or later) must hold at least one name "SURNAME of <anything>"
built from their own family_name, and no printed-style name ("SURNAME of ...") may be on
two current members of the same chamber. That catches a missing printed name but not a
wrong town or county; the default mode (above) and the after-import unmatched-voter
alert (OPEN-855) catch those.

Usage:
    python .github/scripts/check_me_rollcall_names.py            # saved roll calls
    python .github/scripts/check_me_rollcall_names.py --current  # current members
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import lxml.html
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
PERSON_DIRS = [REPO_ROOT / "data" / "me" / d for d in ("legislature", "retired")]
FIXTURES = SCRIPTS_DIR / "fixtures" / "me"
ROLLCALLS = {
    "lower": FIXTURES / "house-rollcall-280096138-828.html",
    "upper": FIXTURES / "senate-rollcall-280095566-963.html",
}


def read_rollcall(path: Path) -> tuple[str, list[str]]:
    """A saved roll call's date (ISO) and the member names it prints, read as the Maine
    scraper (scrapers/me/bills.py scrape_vote) reads them."""
    page = lxml.html.fromstring(path.read_bytes())
    date_text = page.xpath("//td[text() = 'Date:']")[0].xpath(
        "string(following-sibling::td)"
    )
    try:
        date = datetime.datetime.strptime(date_text, "%B %d, %Y")
    except ValueError:
        date = datetime.datetime.strptime(date_text, "%b. %d, %Y")
    member_cell = page.xpath("//td[text() = 'Member']")[0]
    names = [
        row.xpath("string(td[2])").strip() for row in member_cell.xpath("../../tr")[1:]
    ]
    return date.date().isoformat(), [name for name in names if name]


def surname_of(printed: str) -> str:
    """'TALBOT ROSS of Cumberland' -> 'TALBOT ROSS'."""
    return printed.split(" of ", 1)[0]


def voting_roles(person: dict, chamber: str) -> list[tuple[str, str]]:
    """(start, end) of the person's voting seats in the chamber ("" end: still open)."""
    return [
        (str(role.get("start_date") or ""), str(role.get("end_date") or ""))
        for role in person.get("roles") or []
        if role.get("type") == chamber and str(role.get("district", "")).isdigit()
    ]


def all_names(person: dict) -> set[str]:
    names = {person.get("name", "")}
    names.update(other["name"] for other in person.get("other_names") or [])
    return names


def find_missing() -> tuple[list[str], int]:
    rollcalls = {chamber: read_rollcall(path) for chamber, path in ROLLCALLS.items()}
    printed = {chamber: names for chamber, (_, names) in rollcalls.items()}
    members: list[tuple[str, Path, dict]] = []
    seated_later = 0
    for path in sorted(p for d in PERSON_DIRS for p in d.glob("*.yml")):
        person = yaml.safe_load(path.read_text())
        for chamber, (on, _) in rollcalls.items():
            roles = voting_roles(person, chamber)
            if any(start <= on and (not end or end >= on) for start, end in roles):
                members.append((chamber, path, person))
            elif any(start > on and not end for start, end in roles):
                seated_later += 1

    # Who holds each printed name. One already on a member seated in that chamber is
    # spoken for, so it is never offered to a second member with the same surname.
    held: dict[tuple[str, str], list[str]] = {}
    for chamber, _, person in members:
        for name in all_names(person) & set(printed[chamber]):
            held.setdefault((chamber, name), []).append(person["name"])

    missing: list[str] = []
    for (_chamber, name), holders in sorted(held.items()):
        if len(holders) > 1:
            missing.append(f'"{name}" is on {len(holders)} seated members: {holders}')
    for chamber, path, person in members:
        family = (person.get("family_name") or "").upper()
        if any(
            surname_of(n) == family for n in all_names(person) & set(printed[chamber])
        ):
            continue
        candidates = [
            name
            for name in printed[chamber]
            if surname_of(name) == family and (chamber, name) not in held
        ]
        house = "House" if chamber == "lower" else "Senate"
        hint = (
            " or ".join(f'"{c}"' for c in candidates)
            or "no unheld printed name with that surname"
        )
        missing.append(
            f"{house}: {person['name']} ({path.name}) lacks its printed name; "
            f"roll call: {hint}"
        )
    return missing, seated_later


def find_current_missing(today: str) -> list[str]:
    """Current members (seated on `today`) without a "SURNAME of ..." name of their own
    surname, and any such name held by two current members of one chamber."""
    held: dict[tuple[str, str], list[str]] = {}
    missing: list[str] = []
    for path in sorted(p for d in PERSON_DIRS for p in d.glob("*.yml")):
        person = yaml.safe_load(path.read_text())
        for chamber in ("lower", "upper"):
            if not any(
                start <= today and (not end or end >= today)
                for start, end in voting_roles(person, chamber)
            ):
                continue
            # Every printed-style name counts towards a collision, whoever's surname
            # it carries: core would match it to each holder.
            for name in all_names(person):
                if re.fullmatch(r"[^a-z]+ of \S.*", name):
                    held.setdefault((chamber, name), []).append(person["name"])
            family = (person.get("family_name") or "").upper()
            if not family or not any(
                re.fullmatch(rf"{re.escape(family)} of \S.*", n)
                for n in all_names(person)
            ):
                house = "House" if chamber == "lower" else "Senate"
                where = "<town>" if chamber == "lower" else "<county>"
                missing.append(
                    f"{house}: {person['name']} ({path.name}) has no name "
                    f'"{family or "<no family_name>"} of {where}"'
                )
    for (_chamber, name), holders in sorted(held.items()):
        if len(holders) > 1:
            missing.append(f'"{name}" is on {len(holders)} current members: {holders}')
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--current",
        action="store_true",
        help="check today's members for a printed-style name; no saved roll call",
    )
    args = parser.parse_args()

    if args.current:
        missing = find_current_missing(datetime.date.today().isoformat())
        for line in missing:
            print(line)
        print(f"{len(missing)} current Maine roll-call name problem(s)")
        return 1 if missing else 0

    missing, seated_later = find_missing()
    for line in missing:
        print(line)
    print(f"{len(missing)} Maine roll-call name problem(s)")
    if seated_later:
        print(
            f"{seated_later} seated after the saved roll call, not covered: "
            "refresh fixtures/me/ from a later vote"
        )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
