"""Tests for the export_evidence action."""

import csv
from pathlib import Path

import pytest

import export_evidence as ee
import save_record as sr

CYCLE = "<!-- greendisc:review-cycle -->"


def save(data: Path, issue: int, heading: str, table: str) -> None:
    """Save one record table with save_record, as the bot would.

    Parameters
    ----------
    data
        Data directory.
    issue
        Record issue number.
    heading
        Section heading, e.g. ``"Hardware"``.
    table
        Markdown table.

    """
    sr.save(f"### {heading}\n\n{table}", issue, data)


def read(path: Path) -> list[list[str]]:
    """Read a CSV file as lists of cells, header first.

    Parameters
    ----------
    path
        CSV file.

    Returns
    -------
    list of list of str
        Rows.

    """
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


@pytest.fixture
def repo(tmp_path):
    """Return a repository with two personal records, a group record and guides."""
    data = tmp_path / "data"
    save(
        data,
        43,
        "Hardware",
        "| Type | Status | Location | Asset tag |\n|---|---|---|---|\n"
        "| laptop | in use | room 1 | A1 |\n| monitor | unused | room 2 | A2 |\n",
    )
    save(
        data,
        7,
        "Hardware",
        "| Type | Status | Action |\n|---|---|---|\n"
        "| <script>alert(1)</script> | disposed | recycled |\n",
    )
    save(data, 9, "Sharing and promotion",
         "| Date | Kind | What | People reached |\n|---|---|---|---|\n"
         "| 2026-01-01 | promotion | talk | ~40 |\n"
         "| 2026-02-01 | shared resource | guide | 3 |\n")  # fmt: skip
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "e-waste.md").write_text("# E-waste\n", encoding="utf-8")
    return tmp_path


def test_members_numbered_in_record_order(repo):
    """Record numbers become member IDs, the same in every file."""
    assert ee.member_ids(repo / "data") == {"7": "member 1", "43": "member 2"}


def test_hardware_redacted_and_numbered(repo, tmp_path):
    """Location and Asset tag are dropped by default; no record numbers leak."""
    out = tmp_path / "out"
    ee.export(repo, out, drop={"location", "asset_tag"})
    rows = read(out / "csv" / "RG-01-B.csv")
    assert rows[0][:3] == ["Member", "Type", "Model"]
    assert "Location" not in rows[0] and "Asset tag" not in rows[0]
    assert [r[0] for r in rows[1:]] == ["member 1", "member 2", "member 2"]
    text = (out / "csv" / "RG-01-B.csv").read_text(encoding="utf-8")
    assert "room 1" not in text and "43" not in text


def test_keep_all_keeps_columns(repo, tmp_path):
    """With nothing to drop, Location and Asset tag are exported."""
    ee.export(repo, tmp_path / "out")
    assert "room 1" in (tmp_path / "out" / "csv" / "RG-01-B.csv").read_text()


def test_unused_equipment_filtered(repo, tmp_path):
    """RG-02-B holds only unused and disposed items."""
    ee.export(repo, tmp_path / "out")
    rows = read(tmp_path / "out" / "csv" / "RG-02-B.csv")
    types = {r[rows[0].index("Type")] for r in rows[1:]}
    assert types == {"monitor", "<script>alert(1)</script>"}


def test_group_tables_split_by_kind_without_member(repo, tmp_path):
    """Sharing rows go to G3-B or G4-B by kind, with no member column."""
    ee.export(repo, tmp_path / "out")
    g3 = read(tmp_path / "out" / "csv" / "RG-G3-B.csv")
    g4 = read(tmp_path / "out" / "csv" / "RG-G4-B.csv")
    assert g3[0][0] == "Date" and "Member" not in g3[0]
    assert [r[g3[0].index("What")] for r in g3[1:]] == ["guide"]
    assert [r[g4[0].index("People reached")] for r in g4[1:]] == ["~40"]


def test_html_escapes_cells_and_lists_every_criterion(repo, tmp_path):
    """Cell text is escaped; every criterion has a section, even when empty."""
    files = ee.export(repo, tmp_path / "out")
    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in page and "&lt;script&gt;" in page
    for cid, *_ in ee.CRITERIA:
        assert f'<section id="{cid}">' in page
    assert "No rows saved." in page  # e.g. pipelines
    assert "Guide green-computing.md not found." in page
    assert "guides/e-waste.md" in files
    assert (tmp_path / "out" / "guides" / "e-waste.md").exists()
    assert 'id="reviews"' not in page


def test_refuses_non_empty_output(repo, tmp_path):
    """An existing pack is never mixed with a new one."""
    out = tmp_path / "out"
    ee.export(repo, out)
    with pytest.raises(FileExistsError):
        ee.export(repo, out)


def test_review_history_only_cycles():
    """Only toolkit milestones count, oldest first, with check-ins done."""
    milestones = [
        {"title": "Review-2027-03", "description": CYCLE, "due_on": "2027-03-31T07:00:00Z",
         "closed_at": None, "open_issues": 1, "closed_issues": 3},
        {"title": "Review-2026-12", "description": f"x {CYCLE}", "due_on": "2026-12-15T08:00:00Z",
         "closed_at": "2027-01-05T10:00:00Z", "open_issues": 0, "closed_issues": 4},
        {"title": "Release 1.0", "description": None, "due_on": None,
         "closed_at": None, "open_issues": 0, "closed_issues": 0},
    ]  # fmt: skip
    assert ee.review_history(milestones) == [
        {"cycle": "Review-2026-12", "due": "2026-12-15", "closed": "2027-01-05",
         "check-ins done": "4 of 4"},
        {"cycle": "Review-2027-03", "due": "2027-03-31", "closed": "",
         "check-ins done": "3 of 4"},
    ]  # fmt: skip


def test_review_history_section(repo, tmp_path):
    """Given milestones, the page has a review history section."""
    ee.export(repo, tmp_path / "out", milestones=[])
    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert 'id="reviews"' in page and "No review cycles yet." in page


def test_cli_drop_columns(repo, tmp_path, capsys):
    """--drop-columns takes headers as written in the records."""
    out = tmp_path / "out"
    ee.main(["--repo-dir", str(repo), "--out", str(out), "--drop-columns", "Type"])
    header = read(out / "csv" / "RG-01-B.csv")[0]
    assert "Type" not in header and "Location" in header
    assert "Wrote" in capsys.readouterr().out
