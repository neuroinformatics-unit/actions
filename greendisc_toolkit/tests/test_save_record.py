"""Tests for the save_record action's parser and CSV writer."""

import csv
from pathlib import Path

import pytest

import save_record as sr

TABLE = """\
<!--
Type: laptop, desktop, ...
Status: in use, unused, disposed
-->
| Type | Model | Supplier | Purchased | Warranty | Status | Action | Location | Asset tag |
|------|-------|----------|-----------|----------|--------|--------|----------|-----------|
| Laptop | XPS 13 | Dell | 2022 | 3 years | in use | | | |
| External  Drive | | | unknown | | Unused | donate | | |
| | | | | | | | | |
"""


def body(table: str = TABLE) -> str:
    """Return an issue body as rendered by GitHub for the record form.

    Parameters
    ----------
    table
        Content of the Hardware field.

    Returns
    -------
    str
        Body with CRLF line endings, as GitHub sends it.

    """
    text = f"### Hardware\n\n{table}\n### Notes\n\n_No response_\n"
    return text.replace("\n", "\r\n")


def read(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of rows.

    Parameters
    ----------
    path
        CSV file.

    Returns
    -------
    list of dict
        One dict per row.

    """
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_record_kind():
    """A body with a Hardware section is a personal record; others aren't."""
    assert sr.record_kind(body()) == "personal"
    assert sr.record_kind("### Something else\r\n\r\ntext") is None


def test_parse_normalises_and_skips_blank_rows():
    """Hint comments are ignored, Type and listed values are lower-cased.

    Blank Location and Asset tag stay blank (optional); other blanks are unknown.
    """
    rows, warnings = sr.parse_record(body())
    assert warnings == []
    assert rows["Hardware"] == [
        {
            "type": "laptop",
            "model": "XPS 13",
            "supplier": "Dell",
            "purchased": "2022",
            "warranty": "3 years",
            "status": "in use",
            "action": "unknown",
            "location": "",
            "asset_tag": "",
            "notes": "",
        },
        {
            "type": "external drive",
            "model": "unknown",
            "supplier": "unknown",
            "purchased": "unknown",
            "warranty": "unknown",
            "status": "unused",
            "action": "donate",
            "location": "",
            "asset_tag": "",
            "notes": "",
        },
    ]


def test_columns_matched_by_header():
    """Reordered, missing and extra columns are handled by header name."""
    table = "| Status | Type | Colour |\n|---|---|---|\n| in use | desktop | red |\n"
    rows, warnings = sr.parse_record(body(table))
    row = rows["Hardware"][0]
    assert (row["type"], row["status"], row["model"]) == (
        "desktop",
        "in use",
        "unknown",
    )
    assert warnings == ["Hardware: ignored unrecognised column 'Colour'"]


def test_empty_or_missing_section_has_no_rows():
    """Empty or missing sections of a record have no rows; non-records none."""
    rows = sr.parse_record(body("_No response_"))[0]
    assert rows == {s: [] for s in sr.RECORD_KINDS["personal"]}
    assert sr.parse_record("### Notes\r\n\r\nhi")[0] == {}


def test_invalid_rows_report_every_problem():
    """All invalid cells are reported together, with section, row and column."""
    table = (
        "| Type | Purchased | Status |\n|---|---|---|\n"
        "| phone | 22 | broken |\n| laptop | 2020 |\n"
    )
    with pytest.raises(sr.RecordError) as e:
        sr.parse_record(body(table))
    message = str(e.value)
    assert "Hardware, row 1, Status: 'broken' is not one of" in message
    assert "Hardware, row 1, Purchased: '22' is not a year" in message
    assert "Hardware, row 2: has 2 cells, expected 3" in message


def test_save_replaces_only_this_issues_rows(tmp_path):
    """Saving again replaces the issue's rows and keeps other issues' rows."""
    sr.save(body(), 5, tmp_path)
    sr.save(body("| Type |\n|---|\n| tablet |\n"), 3, tmp_path)
    one = "| Type | Status |\n|---|---|\n| laptop | disposed |\n"
    message = sr.save(body(one), 5, tmp_path)
    rows = read(tmp_path / "hardware.csv")
    assert [(r["record"], r["type"], r["status"]) for r in rows] == [
        ("3", "tablet", "unknown"),
        ("5", "laptop", "disposed"),
    ]
    assert "1 row(s)" in message and "unknown" not in message


def test_invalid_record_writes_nothing(tmp_path):
    """A record with errors leaves the CSV untouched."""
    sr.save(body(), 5, tmp_path)
    before = (tmp_path / "hardware.csv").read_bytes()
    with pytest.raises(sr.RecordError):
        sr.save(body("| Status |\n|---|\n| broken |\n"), 5, tmp_path)
    assert (tmp_path / "hardware.csv").read_bytes() == before


def test_cli_exit_status(tmp_path):
    """The CLI exits INVALID and writes the errors when the record is invalid."""
    src = tmp_path / "body.md"
    msg = tmp_path / "msg.md"
    args = ["save", "--body-file", str(src), "--issue", "1"]
    args += ["--data-dir", str(tmp_path), "--message-file", str(msg)]
    src.write_text(body("| Status |\n|---|\n| broken |\n"), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        sr.main(args)
    assert e.value.code == sr.INVALID
    assert "broken" in msg.read_text(encoding="utf-8")
    src.write_text(body(), encoding="utf-8")
    sr.main(args)
    assert "2 row(s)" in msg.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("500GB", "500 GB"),
        ("~3 tb", "~3 TB"),
        ("about 1.5 TB", "~1.5 TB"),
        ("approximately 20 mb", "~20 MB"),
        ("", "unknown"),
    ],
)
def test_size_normalised(value, expected):
    """Sizes accept an approximate marker and any case, and are tidied."""
    assert sr.validate(value, sr.SIZE, 2030) == expected


@pytest.mark.parametrize("value", ["3", "big", "3 TiB", "~ TB"])
def test_size_needs_number_and_unit(value):
    """A size without a number and a unit is rejected."""
    with pytest.raises(ValueError, match="is not a size"):
        sr.validate(value, sr.SIZE, 2030)


@pytest.mark.parametrize("value", ["2026-02-30", "13/10/2026", "20261013"])
def test_date_must_be_iso(value):
    """Dates must be real YYYY-MM-DD dates."""
    with pytest.raises(ValueError, match="is not a date"):
        sr.validate(value, sr.DATE, 2030)
    assert sr.validate("2026-10-13", sr.DATE, 2030) == "2026-10-13"


def test_sections_saved_to_own_files(tmp_path):
    """Each section of a record goes to its own CSV file."""
    text = (
        "### Hardware\n\n| Type |\n|---|\n| laptop |\n\n"
        "### Data resources\n\n| Name | Size |\n|---|---|\n| scans | ~2 tb |\n\n"
        "### Data cleaning\n\n| Date | Freed |\n|---|---|\n| 2026-09-01 | 40GB |\n\n"
        "### Pipelines\n\n| Name | Runs on |\n|---|---|\n| sort | HPC |\n"
    )
    message = sr.save(text, 7, tmp_path)
    assert read(tmp_path / "data-resources.csv")[0]["size"] == "~2 TB"
    assert read(tmp_path / "data-cleaning.csv")[0]["freed"] == "40 GB"
    assert read(tmp_path / "pipelines.csv")[0]["runs_on"] == "hpc"
    assert message.count("1 row(s)") == 4


def test_kind_from_heading():
    """A record's kind comes from its section headings."""
    assert sr.record_kind("### Data cleaning\r\n\r\n| Date |") == "personal"
    assert (
        sr.record_kind("### Training\r\n\r\n### Compute infrastructure\r\n") == "group"
    )
    assert sr.record_kind("### Notes\r\n\r\nhi") is None


def test_blank_notes_stay_blank(tmp_path):
    """Notes are optional: a blank note is not counted as unknown."""
    sr.save(body("| Type | Notes |\n|---|---|\n| laptop | |\n"), 1, tmp_path)
    assert read(tmp_path / "hardware.csv")[0]["notes"] == ""


@pytest.mark.parametrize(
    ("value", "expected"), [("12", "12"), ("~40", "~40"), ("about 40", "~40")]
)
def test_count_normalised(value, expected):
    """Counts accept an approximate marker."""
    assert sr.validate(value, sr.COUNT, 2030) == expected


@pytest.mark.parametrize("value", ["lots", "4.5", "~"])
def test_count_must_be_whole_number(value):
    """A count must be a whole number."""
    with pytest.raises(ValueError, match="is not a number"):
        sr.validate(value, sr.COUNT, 2030)


def test_group_record_saved(tmp_path):
    """A group record saves its own sections only."""
    text = (
        "### Compute infrastructure\n\n| System | Site | PUE |\n|---|---|---|\n"
        "| Cluster | Off-site | ~1.3 |\n\n"
        "### Training\n\n| Date | Title | Attendees |\n|---|---|---|\n"
        "| 2026-10-01 | Green coding | ~25 |\n\n"
        "### Sharing and promotion\n\n| Date | Kind | People reached |\n"
        "|---|---|---|\n| 2026-10-02 | Promotion | 40 |\n"
    )
    sr.save(text, 9, tmp_path)
    assert read(tmp_path / "compute.csv")[0]["site"] == "off-site"
    assert read(tmp_path / "training.csv")[0]["attendees"] == "~25"
    assert read(tmp_path / "sharing.csv")[0]["kind"] == "promotion"
    assert not (tmp_path / "hardware.csv").exists()
    assert not (tmp_path / "data-cleaning.csv").exists()


CHECK_IN = (
    "Intro\n"
    "- [ ] Your record #8 <!-- record:8 -->\n"
    "- [ ] The group record #9: add rows\n"
    "- [ ] Save the group record #9 <!-- record:9 -->\n"
)


def test_tick_check_in_ticks_only_that_records_lines():
    """Saving ticks a record's line; the other items are left to people."""
    body = sr.tick_check_in(CHECK_IN, 8)
    assert "- [x] Your record #8" in body and "- [ ] Save the group" in body
    body = sr.tick_check_in(body, 9)
    assert sr.unticked_items(body) == ["The group record #9: add rows"]


def test_check_in_records_and_unticked_items():
    """Records are checked by saving; only other unticked items are listed."""
    assert sr.check_in_records(CHECK_IN) == [8, 9]
    assert sr.unticked_items(CHECK_IN) == ["The group record #9: add rows"]
    assert sr.unticked_items(CHECK_IN.replace("- [ ]", "- [x]")) == []


@pytest.mark.parametrize("value", ["n/a", "N/A", "na", "-"])
def test_not_applicable_in_any_column(value):
    """n/a is allowed in every column and kept apart from unknown."""
    for spec in (None, sr.LOWER, sr.YEAR, sr.SIZE, sr.DATE, sr.COUNT, ["in use"]):
        assert sr.validate(value, spec, 2030) == "n/a"


def test_remove_drops_only_this_records_rows(tmp_path):
    """Closing a record removes its rows from every file and keeps others'."""
    sr.save(body(), 5, tmp_path)
    sr.save(body("| Type |\n|---|\n| tablet |\n"), 3, tmp_path)
    message = sr.remove(5, tmp_path)
    rows = read(tmp_path / "hardware.csv")
    assert [(r["record"], r["type"]) for r in rows] == [("3", "tablet")]
    assert "2 row(s) removed" in message
    assert sr.remove(5, tmp_path) == ""


def test_cli_remove_needs_no_body(tmp_path):
    """The remove command works without --body-file; others need it."""
    sr.save(body(), 5, tmp_path)
    msg = tmp_path / "msg.md"
    sr.main(
        [
            "remove",
            "--issue",
            "5",
            "--data-dir",
            str(tmp_path),
            "--message-file",
            str(msg),
        ]
    )
    assert "removed" in msg.read_text(encoding="utf-8")
    assert read(tmp_path / "hardware.csv") == []
    with pytest.raises(SystemExit):
        sr.main(["kind"])


def test_missing_section_keeps_saved_rows(tmp_path):
    """A section that lost its heading or table can't wipe its saved rows."""
    sr.save(body(), 5, tmp_path)
    before = (tmp_path / "hardware.csv").read_bytes()
    # Pipelines keeps it recognised as a personal record.
    no_heading = body().replace("### Hardware", "### Hardwear") + "### Pipelines\r\n"
    no_table = body("Nothing here.\n")
    for text in (no_heading, no_table):
        with pytest.raises(sr.RecordError, match="2 row"):
            sr.save(text, 5, tmp_path)
    assert (tmp_path / "hardware.csv").read_bytes() == before
    # An empty table removes them; a missing section is fine with nothing saved.
    sr.save(body("| Type |\n|---|\n"), 5, tmp_path)
    assert read(tmp_path / "hardware.csv") == []
    sr.save(no_heading, 6, tmp_path)
