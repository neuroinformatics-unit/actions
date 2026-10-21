# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Export Green DiSC evidence for submission.

Reads the CSV files written by ``save_record`` and the guides, and writes an
evidence pack that an auditor outside the repository can open: one CSV per
criterion, the guides, and an ``index.html`` with a section per criterion.
Sensitive columns are dropped and record numbers become ``member 1..N``, so
the pack shows what the group has without saying who has it.

Runs from a local clone (``uv run --script export_evidence.py``) or in the
toolkit's workflow; only ``--with-reviews`` needs the GitHub CLI.
"""

import argparse
import csv
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CYCLE_MARKER = "<!-- greendisc:review-cycle -->"
DEFAULT_DROP = "Location,Asset tag"
# Column headers that capitalising doesn't get right.
HEADERS = {"pue": "PUE"}

# Research Group Bronze criteria evidenced by the records and guides. A table is
# (CSV file, column, allowed values), with column None for every row. G1-B and
# G2-B evidence (profile, onboarding material) lives outside the repository.
CRITERIA = [
    ("RG-G3-B", "Resources are shared with other groups",
     [("sharing.csv", "kind", {"shared resource"})], []),
    ("RG-G4-B", "Green DiSC dissemination",
     [("sharing.csv", "kind", {"promotion"})], []),
    ("RG-01-B", "Computing hardware inventory",
     [("hardware.csv", None, None)], []),
    ("RG-02-B", "Unused computing equipment inventory",
     [("hardware.csv", "status", {"unused", "disposed"})], []),
    ("RG-03-B", "E-waste processing streams and institution/group policy",
     [], ["e-waste.md"]),
    ("RG-DS1-B", "Data resource inventory",
     [("data-resources.csv", None, None)], []),
    ("RG-DS2-B", "Data directory cleaning",
     [("data-cleaning.csv", None, None)], []),
    ("RG-HPC1-B", "Computing infrastructure inventory",
     [("compute.csv", None, None)], []),
    ("RG-HPC2-B", "Computing pipeline inventory",
     [("pipelines.csv", None, None)], []),
    ("RG-HPC3-B", "Green computing best practices",
     [("training.csv", None, None)], ["green-computing.md"]),
]  # fmt: skip
# Files written only from the group record: their record column says nothing.
GROUP_FILES = {"compute.csv", "training.csv", "sharing.csv"}


def column_key(header: str) -> str:
    """Return the CSV column name for a header, as ``save_record`` writes it.

    Parameters
    ----------
    header
        Column header, e.g. ``"Asset tag"``.

    Returns
    -------
    str
        Lower-case name with underscores, e.g. ``"asset_tag"``.

    """
    return re.sub(r"\W+", "_", header.strip().lower()).strip("_")


def header_label(key: str) -> str:
    """Return a readable header for a CSV column name.

    Parameters
    ----------
    key
        CSV column name, e.g. ``"people_reached"``.

    Returns
    -------
    str
        E.g. ``"People reached"``.

    """
    return HEADERS.get(key, key.replace("_", " ").capitalize())


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file, or return no rows if it doesn't exist.

    Parameters
    ----------
    path
        CSV file.

    Returns
    -------
    list of dict
        One dict per row.

    """
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def member_ids(data_dir: Path) -> dict[str, str]:
    """Give each personal record with saved rows a member ID.

    Parameters
    ----------
    data_dir
        Directory with the CSV files.

    Returns
    -------
    dict of str to str
        Record number to ``"member N"``, numbered in record order so the same
        person has the same ID in every file of one export.

    """
    numbers = {
        int(r["record"])
        for path in data_dir.glob("*.csv")
        if path.name not in GROUP_FILES
        for r in read_csv(path)
        if r.get("record")
    }
    return {str(n): f"member {i}" for i, n in enumerate(sorted(numbers), start=1)}


def evidence_rows(
    rows: list[dict[str, str]],
    column: str | None,
    allowed: set[str] | None,
    drop: set[str],
    members: dict[str, str] | None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Filter and anonymise the rows of one table.

    Parameters
    ----------
    rows
        Rows read from a CSV file written by ``save_record``.
    column, allowed
        Keep only rows whose `column` is in `allowed`; None keeps every row.
    drop
        CSV column names to leave out.
    members
        Record number to member ID, replacing the ``record`` column; None
        leaves the column out (group tables).

    Returns
    -------
    columns : list of str
        Output column names, ``member`` first when `members` is given.
    rows : list of dict
        Output rows.

    """
    if column is not None:
        rows = [r for r in rows if r.get(column) in allowed]
    keys = [k for k in (rows[0] if rows else {}) if k != "record" and k not in drop]
    out = []
    for r in rows:
        row = {k: r[k] for k in keys}
        if members is not None:
            row = {"member": members.get(r["record"], "member ?"), **row}
        out.append(row)
    columns = (["member"] if members is not None and rows else []) + keys
    return columns, out


def review_history(milestones: list[dict]) -> list[dict[str, str]]:
    """Summarise review cycles from their milestones.

    Parameters
    ----------
    milestones
        Milestones from the GitHub API; only those made by ``review_cycle``
        (with the cycle marker in their description) count.

    Returns
    -------
    list of dict
        Per cycle, oldest first: name, due date, closed date (blank if open)
        and check-ins closed out of all.

    """
    cycles = [m for m in milestones if CYCLE_MARKER in (m.get("description") or "")]
    return [
        {
            "cycle": m["title"],
            "due": (m.get("due_on") or "")[:10],
            "closed": (m.get("closed_at") or "")[:10],
            "check-ins done": (
                f"{m['closed_issues']} of {m['closed_issues'] + m['open_issues']}"
            ),
        }
        for m in sorted(cycles, key=lambda m: m.get("due_on") or "")
    ]


def fetch_milestones(repo_dir: Path) -> list[dict]:
    """Fetch every milestone of the repository with the GitHub CLI.

    Parameters
    ----------
    repo_dir
        Local clone; ``gh`` takes the repository from it (or from ``GH_REPO``).

    Returns
    -------
    list of dict
        Milestones, open and closed.

    """
    result = subprocess.run(
        ["gh", "api", "--paginate", "repos/{owner}/{repo}/milestones?state=all",
         "--jq", ".[]"],
        cwd=repo_dir, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if result.returncode:
        sys.exit(f"Couldn't read the review history with gh:\n{result.stderr}")
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def html_table(columns: list[str], rows: list[dict[str, str]]) -> str:
    """Render rows as an HTML table, escaping every value.

    Parameters
    ----------
    columns
        Column names, in order.
    rows
        Rows to render.

    Returns
    -------
    str
        HTML.

    """
    head = "".join(f"<th>{html.escape(header_label(c))}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(r[c])}</td>" for c in columns) + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write rows to a CSV file with readable headers.

    Parameters
    ----------
    path
        Output file.
    columns
        Column names, in order.
    rows
        Rows to write.

    """
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([header_label(c) for c in columns])
        writer.writerows([r[c] for c in columns] for r in rows)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Green DiSC evidence</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 70rem; margin: 2rem auto;
  padding: 0 1rem; line-height: 1.5; color: #1a1a1a; background: #fff; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; margin: 0.5rem 0; }}
th, td {{ border: 1px solid #ccc; padding: 0.3rem 0.5rem; text-align: left;
  vertical-align: top; }}
th {{ background: #f2f2f2; }}
section {{ margin-top: 2rem; }}
.note {{ color: #555; }}
</style>
</head>
<body>
<h1>Green DiSC evidence</h1>
<p class="note">Exported {date} from the group's Green DiSC records. {redaction}</p>
<nav><ul>{toc}</ul></nav>
{sections}
</body>
</html>
"""


def export(
    repo_dir: Path,
    out: Path,
    data_dir: str = "data",
    guides_dir: str = "guides",
    drop: set[str] | None = None,
    milestones: list[dict] | None = None,
) -> list[str]:
    """Write the evidence pack.

    Parameters
    ----------
    repo_dir
        Repository clone.
    out
        Output directory; must not exist or be empty, so a pack never mixes
        with files from an earlier export.
    data_dir, guides_dir
        Data and guides directories, relative to `repo_dir`.
    drop
        CSV column names to leave out; None leaves out nothing.
    milestones
        Milestones for the review history; None leaves the section out.

    Returns
    -------
    list of str
        Files written, relative to `out`.

    Raises
    ------
    FileExistsError
        If `out` exists and isn't empty.

    """
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} isn't empty: choose a new directory")
    drop = drop or set()
    data = repo_dir / data_dir
    guides = repo_dir / guides_dir
    members = member_ids(data)
    (out / "csv").mkdir(parents=True, exist_ok=True)
    written, toc, sections = [], [], []
    for cid, title, tables, pages in CRITERIA:
        parts = []
        for file, column, allowed in tables:
            group = file in GROUP_FILES
            columns, rows = evidence_rows(
                read_csv(data / file), column, allowed, drop, None if group else members
            )
            if not rows:
                parts.append('<p class="note">No rows saved.</p>')
                continue
            name = f"csv/{cid}.csv" if len(tables) == 1 else f"csv/{cid}-{file}"
            write_csv(out / name, columns, rows)
            written.append(name)
            parts.append(
                f'<p>{len(rows)} row(s); also as <a href="{name}">{name}</a>.</p>'
                + html_table(columns, rows)
            )
        for page in pages:
            if (guides / page).exists():
                (out / "guides").mkdir(exist_ok=True)
                shutil.copyfile(guides / page, out / "guides" / page)
                written.append(f"guides/{page}")
                parts.append(f'<p>Guide: <a href="guides/{page}">{page}</a>.</p>')
            else:
                parts.append(
                    f'<p class="note">Guide {html.escape(page)} not found.</p>'
                )
        heading = html.escape(f"{cid} {title}")
        toc.append(f'<li><a href="#{cid}">{heading}</a></li>')
        sections.append(
            f'<section id="{cid}"><h2>{heading}</h2>{"".join(parts)}</section>'
        )
    if milestones is not None:
        history = review_history(milestones)
        toc.append('<li><a href="#reviews">Review history</a></li>')
        table = (
            html_table(list(history[0]), history)
            if history
            else '<p class="note">No review cycles yet.</p>'
        )
        sections.append(
            '<section id="reviews"><h2>Review history</h2>'
            "<p>Each review is a cycle in which every member goes over their record."
            "</p>" + table + "</section>"
        )
    redaction = (
        "Left out: " + ", ".join(header_label(c) for c in sorted(drop)) + ". "
        if drop
        else ""
    ) + "Members are numbered instead of named."
    (out / "index.html").write_text(
        PAGE.format(
            date=datetime.datetime.now(datetime.UTC).date().isoformat(),
            redaction=html.escape(redaction),
            toc="".join(toc),
            sections="\n".join(sections),
        ),
        encoding="utf-8",
    )
    return ["index.html", *written]


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface.

    Parameters
    ----------
    argv
        Command-line arguments; defaults to ``sys.argv[1:]``.

    """
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--repo-dir",
        type=Path,
        default=Path("."),
        help="clone of the Green DiSC repository (default: .)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("greendisc-evidence"),
        help="output directory (default: greendisc-evidence)",
    )
    p.add_argument(
        "--data-dir",
        default="data",
        help="CSV files, relative to --repo-dir (default: data)",
    )
    p.add_argument(
        "--guides-dir",
        default="guides",
        help="guides, relative to --repo-dir (default: guides)",
    )
    p.add_argument(
        "--drop-columns",
        default=DEFAULT_DROP,
        help=f"comma-separated columns to leave out (default: {DEFAULT_DROP})",
    )
    p.add_argument(
        "--keep-all",
        action="store_true",
        help="leave no columns out (members are still numbered)",
    )
    p.add_argument(
        "--with-reviews",
        action="store_true",
        help="add the review history; needs the GitHub CLI, logged in",
    )
    args = p.parse_args(argv)  # fmt: skip
    drop = (
        set()
        if args.keep_all
        else {column_key(c) for c in args.drop_columns.split(",") if c.strip()}
    )
    milestones = fetch_milestones(args.repo_dir) if args.with_reviews else None
    try:
        files = export(
            args.repo_dir, args.out, args.data_dir, args.guides_dir, drop, milestones
        )
    except FileExistsError as e:
        sys.exit(str(e))
    print(f"Wrote {len(files)} file(s) to {args.out}: open {args.out / 'index.html'}")


if __name__ == "__main__":
    main()
