"""Tests for the review_cycle action's helpers."""

import datetime

import pytest

import review_cycle as rc
import save_record as sr

DUE = datetime.date(2026, 12, 10)


@pytest.mark.parametrize("value", ["10/12/2026", "2026-02-30", "soon"])
def test_due_must_be_iso_date(value):
    """The due date must be a real YYYY-MM-DD date."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        rc.parse_due(value)


def test_cycle_name_defaults_to_month():
    """Names have no spaces; without one, the due date's month is used."""
    assert rc.cycle_name(DUE) == "Review-2026-12"
    assert rc.cycle_name(DUE, " Winter  review ") == "Winter-review"


def body(is_rep):
    """Return a check-in body for record 8 and group record 9."""
    return rc.check_in_body("R", DUE, 8, 9, is_rep, "o/r")


def test_member_check_in_says_how_to_finish():
    """Members are told saving ticks the record and to close it themselves."""
    member = body(False)
    assert "opening pull requests" in member and "saving ticks this item" in member
    assert "then **close this check-in**" in member
    assert "As the representative" not in member
    text = sr.tick_check_in(member, 8)
    assert sr.check_in_records(member) == [8]
    assert len(sr.unticked_items(text)) == 2  # group record and guides


def test_criteria_line_only_with_sync_pr():
    """The rep is asked to merge the criteria sync only when there is one."""
    assert "criteria changed" not in body(True)
    with_pr = rc.check_in_body("R", DUE, 8, 9, True, "o/r", "42")
    assert "- [ ] #42: Green DiSC's criteria changed" in with_pr


def test_guides_line_only_when_guides_changed():
    """The rep gets a diff link per changed guide, only when guides changed."""
    assert "guides changed" not in body(True)
    changes = ("aaa...bbb", ["guides/e-waste.md"])
    rep = rc.check_in_body("R", DUE, 8, 9, True, "o/r", guide_changes=changes)
    # GitHub's anchor for a file's diff: sha256 of its path.
    anchor = "f306affd1e555ff181ffe63c6afa3b2f5f1a154fe288ab9508befa9a2946c7c5"
    link = f"https://github.com/o/r/compare/aaa...bbb#diff-{anchor}"
    assert (
        f"- [ ] The guides changed since the last review ([e-waste.md]({link}))" in rep
    )


def test_rep_check_in_tracks_both_records():
    """The rep saves both records, and may close anyone's check-in."""
    rep = body(True)
    assert "As the representative, you can close any check-in" in rep
    assert sr.check_in_records(rep) == [8, 9]
    text = sr.tick_check_in(sr.tick_check_in(rep, 8), 9)
    assert "- [x] Update the group record" in text


def test_members_are_writers_and_maintainers():
    """Everyone with Write access or above gets a record; bots and readers don't."""
    collaborators = [
        {"login": "amy", "role_name": "write", "type": "User"},
        {"login": "rep", "role_name": "maintain", "type": "User"},
        {"login": "boss", "role_name": "admin", "type": "User"},
        {"login": "reader", "role_name": "read", "type": "User"},
        {"login": "ci", "role_name": "write", "type": "Bot"},
    ]
    assert rc.members(collaborators) == ["amy", "boss", "rep"]


def test_record_owner_is_assignee_else_author():
    """A record created by a review belongs to its assignee."""
    issue = {"user": {"login": "bot"}, "assignees": [{"login": "amy"}]}
    assert rc.record_owner(issue) == "amy"
    assert rc.record_owner({"user": {"login": "amy"}, "assignees": []}) == "amy"


def test_form_body_matches_issue_rendering():
    """Textareas become ### sections with their pre-filled value."""
    form = {
        "body": [
            {"type": "markdown", "attributes": {"value": "intro"}},
            {
                "type": "textarea",
                "attributes": {"label": "Hardware", "value": "| Type |\n"},
            },
            {
                "type": "textarea",
                "attributes": {"label": "Pipelines", "value": "| Name |\n"},
            },
        ]
    }
    body = rc.form_body(form)
    assert body == "### Hardware\n\n| Type |\n\n### Pipelines\n\n| Name |"
    assert sr.record_kind(body) == "personal"


def test_orphaned_rows(tmp_path):
    """Rows from records that aren't open are found, per file."""
    (tmp_path / "hardware.csv").write_text("record,type\n8,laptop\n9,desk\n43,mouse\n")
    (tmp_path / "pipelines.csv").write_text("record,name\n8,sorter\n")
    found = rc.orphaned_rows(tmp_path, {9, 43})
    data = tmp_path.as_posix()
    assert found == {8: [f"{data}/hardware.csv", f"{data}/pipelines.csv"]}
    assert rc.orphaned_rows(tmp_path / "missing", {1}) == {}


def test_rep_check_in_lists_orphans():
    """Only the rep is asked about rows from records that aren't open, if any."""
    orphans = {8: ["data/hardware.csv"]}
    rep = rc.check_in_body("R", DUE, 43, 9, True, "o/r", "", orphans)
    link = "[hardware.csv](https://github.com/o/r/blob/HEAD/data/hardware.csv)"
    assert f"(closed, deleted or unlabelled): #8 ({link})" in rep
    assert "aren't open" not in body(True)
