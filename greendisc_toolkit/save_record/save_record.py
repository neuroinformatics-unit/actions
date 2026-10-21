# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Save a Green DiSC record issue to CSV files.

A record issue holds one Markdown table per section (e.g. ``### Hardware``).
Tables are read by column header, validated, and written to
``<data-dir>/<section>.csv``, replacing the rows previously saved from the same
issue. Validation is all-or-nothing: if any row is invalid, nothing is written.
Closing a record removes its rows, so the CSV files hold current evidence only.
"""

import argparse
import csv
import datetime
import re
import sys
from pathlib import Path

UNKNOWN = "unknown"
NOT_APPLICABLE = "n/a"
YEAR = "year"
LOWER = "lower"
SIZE = "size"
DATE = "date"
OPTIONAL = "optional"
COUNT = "count"
SIZE_RE = re.compile(
    r"(?P<approx>~|about|approx\.?|approximately)?\s*"
    r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>[kmgtp]b)",
    re.IGNORECASE,
)
# Review check-in lines: an unticked item, and the marker of a record's line.
UNTICKED = re.compile(r"\s*- \[ \] (.*)")
RECORD_MARKER = re.compile(r"<!-- record:(\d+) -->")
COUNT_RE = re.compile(
    r"(?P<approx>~|about|approx\.?|approximately)?\s*(?P<number>\d+)", re.IGNORECASE
)

# Section heading -> CSV file and columns. A column is either free text (None),
# free text lower-cased (LOWER, for values counted in summaries), a list of
# allowed values, YEAR, SIZE (e.g. "~3 TB"), DATE (YYYY-MM-DD), COUNT (e.g.
# "~40") or OPTIONAL (free text that may stay blank). "unknown" is always allowed, and other blank cells
# are stored as "unknown".
SECTIONS = {
    "Hardware": {
        "file": "hardware.csv",
        "columns": {
            # ponytail: free text; spelling variants split summary counts,
            # add a synonym map in export_summary if that ever matters.
            "Type": LOWER,
            "Model": None,
            "Supplier": None,
            "Purchased": YEAR,
            "Warranty": None,
            "Status": ["in use", "unused", "disposed"],
            "Action": None,
            # Left blank in repositories that are or could become public.
            "Location": OPTIONAL,
            "Asset tag": OPTIONAL,
            "Notes": OPTIONAL,
        },
    },
    "Data resources": {
        "file": "data-resources.csv",
        "columns": {
            "Name": None,
            "Hosted by": ["us", "external"],
            "Location": OPTIONAL,
            "Size": SIZE,
            "If lost": ["easy to replace", "hard to replace", "irreplaceable"],
            "Status": ["in use", "archived", "deleted"],
            "Notes": OPTIONAL,
        },
    },
    "Data cleaning": {
        "file": "data-cleaning.csv",
        "columns": {
            "Date": DATE,
            "Scope": None,
            "Freed": SIZE,
            "Next": DATE,
            "Notes": OPTIONAL,
        },
    },
    "Compute infrastructure": {
        "file": "compute.csv",
        "columns": {
            "System": None,
            "Site": ["on-site", "off-site"],
            "Provider": None,
            "Region": None,
            "PUE": None,
            "Electricity": None,
            "Hardware": None,
            "Reason": None,
            "Status": ["in use", "retired"],
            "Notes": OPTIONAL,
        },
    },
    "Training": {
        "file": "training.csv",
        "columns": {
            "Date": DATE,
            "Title": None,
            "Format": LOWER,
            "Attendees": COUNT,
            "Materials": None,
            "Notes": OPTIONAL,
        },
    },
    "Sharing and promotion": {
        "file": "sharing.csv",
        "columns": {
            "Date": DATE,
            "Kind": ["shared resource", "promotion"],
            "What": None,
            "How": None,
            "People reached": COUNT,
            "Link": None,
            "Notes": OPTIONAL,
        },
    },
    "Pipelines": {
        "file": "pipelines.csv",
        "columns": {
            "Name": None,
            "Runs on": LOWER,
            "Runtime": None,
            "Resources": None,
            "Frequency": None,
            "Status": ["active", "retired"],
            "Notes": OPTIONAL,
        },
    },
}
# Record kind -> its sections. A kind is recognised by a heading that no other
# kind has, so kinds could share a section.
RECORD_KINDS = {
    "personal": ["Hardware", "Data resources", "Data cleaning", "Pipelines"],
    "group": ["Compute infrastructure", "Training", "Sharing and promotion"],
}


class RecordError(Exception):
    """Raised when a record issue's tables are invalid."""


def column_key(header: str) -> str:
    """Return the CSV column name for a table header.

    Parameters
    ----------
    header
        Column header as written in the issue, e.g. ``"Asset tag"``.

    Returns
    -------
    str
        Lower-case name with underscores, e.g. ``"asset_tag"``.

    """
    return re.sub(r"\W+", "_", header.strip().lower()).strip("_")


def split_sections(body: str) -> dict[str, str]:
    """Split an issue form body into its ``### `` sections.

    Parameters
    ----------
    body
        Issue body as rendered by a GitHub issue form.

    Returns
    -------
    dict of str to str
        Section heading to section text.

    """
    parts = re.split(r"^### +(.+?)\s*$", body, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def record_kind(body: str) -> str | None:
    """Identify which kind of record an issue is from its section headings.

    Parameters
    ----------
    body
        Issue body.

    Returns
    -------
    str or None
        A key of `RECORD_KINDS`, or None if the issue is not a record.

    """
    headings = split_sections(body)
    for kind, sections in RECORD_KINDS.items():
        others = {s for k, ss in RECORD_KINDS.items() if k != kind for s in ss}
        if any(s in headings and s not in others for s in sections):
            return kind
    return None


def parse_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse a Markdown table.

    Parameters
    ----------
    text
        Section text containing a pipe table; other lines are ignored.

    Returns
    -------
    headers : list of str
        Column headers.
    rows : list of list of str
        Cell values, stripped, excluding the separator line.

    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    cells = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines]
    cells = [r for r in cells if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    if not cells:
        return [], []
    return cells[0], cells[1:]


def validate(value: str, spec: list[str] | str | None, year_max: int) -> str:
    """Normalise one cell and check it against its column spec.

    Parameters
    ----------
    value
        Cell text.
    spec
        Column spec: None (free text), `LOWER`, a list of allowed values,
        `YEAR`, `SIZE`, `DATE`, `COUNT` or `OPTIONAL`.
    year_max
        Latest acceptable year.

    Returns
    -------
    str
        The normalised value; blank becomes ``"unknown"`` unless `OPTIONAL`,
        and ``n/a``, ``na`` or ``-`` become ``"n/a"`` in any column.

    Raises
    ------
    ValueError
        If the value is not allowed.

    """
    value = " ".join(value.split())
    if value.lower() in {"n/a", "na", "-"}:
        return NOT_APPLICABLE
    if spec == OPTIONAL:
        return value
    if not value or value.lower() == UNKNOWN:
        return UNKNOWN
    if spec == LOWER:
        return value.lower()
    if isinstance(spec, list):
        if value.lower() not in spec:
            raise ValueError(f"'{value}' is not one of: {', '.join(spec)}, unknown")
        return value.lower()
    if spec == YEAR and not (
        value.isdigit() and len(value) == 4 and 1980 <= int(value) <= year_max
    ):
        raise ValueError(f"'{value}' is not a year (e.g. 2023)")
    if spec == SIZE:
        m = SIZE_RE.fullmatch(value)
        if not m:
            raise ValueError(f"'{value}' is not a size (e.g. 500 GB, ~3 TB)")
        approx = "~" if m["approx"] else ""
        return f"{approx}{m['number']} {m['unit'].upper()}"
    if spec == COUNT:
        m = COUNT_RE.fullmatch(value)
        if not m:
            raise ValueError(f"'{value}' is not a number (e.g. 12, ~40)")
        return f"{'~' if m['approx'] else ''}{m['number']}"
    if spec == DATE:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            datetime.date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"'{value}' is not a date (e.g. 2026-10-13)") from None
    return value


def parse_record(body: str) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    """Parse and validate the sections of a record issue's kind.

    Parameters
    ----------
    body
        Issue body.

    Returns
    -------
    rows : dict of str to list of dict
        Section heading to validated rows (CSV column name to value). Blank
        rows are skipped; sections that are missing or empty have no rows.
    warnings : list of str
        Non-fatal problems, such as unrecognised columns.

    Raises
    ------
    RecordError
        If any row is invalid; the message lists every problem found.

    """
    year_max = datetime.datetime.now(datetime.UTC).year + 1
    sections = split_sections(body)
    result, warnings, errors = {}, [], []
    for name in RECORD_KINDS.get(record_kind(body), []):
        columns = SECTIONS[name]["columns"]
        headers, rows = parse_table(sections.get(name, ""))
        known = {h.lower(): h for h in columns}
        for h in headers:
            if h.lower() not in known:
                warnings.append(f"{name}: ignored unrecognised column '{h}'")
        result[name] = []
        for n, cells in enumerate(rows, start=1):
            if not any(cells):
                continue
            if len(cells) != len(headers):
                errors.append(
                    f"{name}, row {n}: has {len(cells)} cells, expected {len(headers)}"
                )
                continue
            given = {h.lower(): c for h, c in zip(headers, cells, strict=True)}
            row = {}
            for col, spec in columns.items():
                try:
                    row[column_key(col)] = validate(
                        given.get(col.lower(), ""), spec, year_max
                    )
                except ValueError as e:
                    errors.append(f"{name}, row {n}, {col}: {e}")
            result[name].append(row)
    if errors:
        raise RecordError("\n".join(f"- {e}" for e in errors))
    return result, warnings


def write_csv(path: Path, issue: int, columns: list[str], rows: list[dict]) -> None:
    """Replace one issue's rows in a CSV file, keeping all other rows.

    Parameters
    ----------
    path
        CSV file; created if missing.
    issue
        Issue number, stored in the ``record`` column.
    columns
        CSV column names after ``record``. Columns missing from existing rows
        are filled with ``"unknown"``.
    rows
        New rows for this issue.

    """
    header = ["record", *columns]
    kept = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["record"] != str(issue)]
    new = [{"record": str(issue), **r} for r in rows]
    all_rows = sorted(kept + new, key=lambda r: int(r["record"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, header, restval=UNKNOWN, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)


def unticked_items(body: str) -> list[str]:
    """Return the unticked items of a review check-in, other than records.

    Record lines are left out: what counts for them is whether the record was
    saved, not their tick (see `check_in_records`).

    Parameters
    ----------
    body
        Check-in issue body.

    Returns
    -------
    list of str
        Text of each unticked ``- [ ]`` line without a record marker.

    """
    return [
        m[1].strip()
        for m in (UNTICKED.match(ln) for ln in body.splitlines())
        if m and not RECORD_MARKER.search(m[1])
    ]


def check_in_records(body: str) -> list[int]:
    """Return the records a review check-in asks to save.

    Parameters
    ----------
    body
        Check-in issue body.

    Returns
    -------
    list of int
        Record numbers from the ``<!-- record:N -->`` markers, in order.

    """
    return [int(n) for n in RECORD_MARKER.findall(body)]


def tick_check_in(body: str, record: int) -> str:
    """Tick a record's lines in a review check-in.

    Check-in lines for records end with ``<!-- record:N -->``; saving record
    N ticks them. People tick the other lines and close the check-in.

    Parameters
    ----------
    body
        Check-in issue body.
    record
        Number of the record that was saved.

    Returns
    -------
    str
        Body with that record's lines ticked.

    """
    marker = f"<!-- record:{record} -->"
    lines = [
        ln.replace("- [ ]", "- [x]", 1) if marker in ln else ln
        for ln in body.splitlines()
    ]
    return "\n".join(lines) + "\n"


def save(body: str, issue: int, data_dir: Path) -> str:
    """Validate a record issue and write its rows to the CSV files.

    Parameters
    ----------
    body
        Issue body.
    issue
        Issue number.
    data_dir
        Directory holding the CSV files.

    Returns
    -------
    str
        Markdown summary for the reply comment.

    Raises
    ------
    RecordError
        If any row is invalid; nothing is written.

    """
    result, warnings = parse_record(body)
    lines = []
    for name, rows in result.items():
        section = SECTIONS[name]
        columns = [column_key(c) for c in section["columns"]]
        write_csv(data_dir / section["file"], issue, columns, rows)
        lines.append(
            f"- **{name}**: {len(rows)} row(s) in `{data_dir.as_posix()}/"
            f"{section['file']}`"
        )
    lines += [f"- {w}" for w in warnings]
    return "\n".join(lines)


def remove(issue: int, data_dir: Path) -> str:
    """Remove a closed record's rows from the CSV files.

    Parameters
    ----------
    issue
        Issue number of the closed record.
    data_dir
        Directory holding the CSV files.

    Returns
    -------
    str
        Markdown summary for the reply comment; empty if the record had no
        saved rows.

    """
    lines = []
    for name, section in SECTIONS.items():
        path = data_dir / section["file"]
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            count = sum(r["record"] == str(issue) for r in csv.DictReader(f))
        if count:
            columns = [column_key(c) for c in section["columns"]]
            write_csv(path, issue, columns, [])
            lines.append(
                f"- **{name}**: {count} row(s) removed from "
                f"`{data_dir.as_posix()}/{section['file']}`"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface.

    ``kind`` prints the record kind (or nothing). ``save`` writes the CSV
    files and the reply message; it exits with status 1 and writes the errors
    to the message file if the record is invalid. ``tick`` ticks record
    ``--issue``'s lines in the check-in body file, in place. ``remove``
    deletes record ``--issue``'s rows from the CSV files and writes the reply
    message (empty if it had none); it needs no ``--body-file``.
    ``unticked`` prints a check-in's unticked items, one per line, and
    ``records`` the numbers of the records it asks to save, space-separated.

    Parameters
    ----------
    argv
        Command-line arguments; defaults to ``sys.argv[1:]``.

    """
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command", choices=["kind", "save", "tick", "remove", "unticked", "records"]
    )
    p.add_argument("--body-file", type=Path)
    p.add_argument("--issue", type=int)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--message-file", type=Path)
    args = p.parse_args(argv)
    if args.command == "remove":
        message = remove(args.issue, args.data_dir)
        args.message_file.write_text(message, encoding="utf-8")
        return
    if args.body_file is None:
        p.error(f"{args.command} needs --body-file")
    body = args.body_file.read_text(encoding="utf-8")
    if args.command == "kind":
        print(record_kind(body) or "")
        return
    if args.command == "tick":
        args.body_file.write_text(tick_check_in(body, args.issue), encoding="utf-8")
        return
    if args.command == "unticked":
        print("\n".join(unticked_items(body)))
        return
    if args.command == "records":
        print(" ".join(str(n) for n in check_in_records(body)))
        return
    try:
        message = save(body, args.issue, args.data_dir)
    except RecordError as e:
        args.message_file.write_text(str(e), encoding="utf-8")
        sys.exit(1)
    args.message_file.write_text(message, encoding="utf-8")


if __name__ == "__main__":
    main()
