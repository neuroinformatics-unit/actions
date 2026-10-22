# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Start a Green DiSC review cycle.

Creates the cycle's milestone and one check-in per record owner (the
representative's also covers the group record, guides and README), then closes the
previous cycle. Safe to re-run: anything that already exists in the
cycle's milestone is left alone.
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CYCLE_MARKER = "<!-- greendisc:review-cycle -->"
CHECK_IN_LABEL = "check-in"


def record_marker(record: int) -> str:
    """Return the hidden marker that ties a check-in line to a record.

    Parameters
    ----------
    record
        Record issue number.

    Returns
    -------
    str
        HTML comment, e.g. ``<!-- record:8 -->``.

    """
    return f"<!-- record:{record} -->"


def parse_due(due: str) -> datetime.date:
    """Parse the review date.

    Parameters
    ----------
    due
        Date as ``YYYY-MM-DD``.

    Returns
    -------
    datetime.date
        The date.

    Raises
    ------
    ValueError
        If `due` is not a real ``YYYY-MM-DD`` date.

    """
    due = due.strip()
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            raise ValueError
        return datetime.date.fromisoformat(due)
    except ValueError:
        raise ValueError(
            f"'{due}' is not a date as YYYY-MM-DD, e.g. 2026-12-10"
        ) from None


def cycle_name(due: datetime.date, name: str = "") -> str:
    """Return the milestone name for a cycle.

    Parameters
    ----------
    due
        Review date.
    name
        Name given by the user; blank for the default.

    Returns
    -------
    str
        `name` with spaces replaced by hyphens, or ``Review-<year>-<month>``
        of the due date. GitHub's milestone links don't quote names, so a name
        with spaces leads to a broken search.

    """
    return "-".join(name.split()) or f"Review-{due:%Y-%m}"


def parse_pr(pr: str) -> str:
    """Parse a pull request number.

    Parameters
    ----------
    pr
        Number, optionally with a leading ``#``; blank for none.

    Returns
    -------
    str
        The number, or blank.

    Raises
    ------
    ValueError
        If `pr` is not a number.

    """
    pr = pr.strip().removeprefix("#")
    if pr and not pr.isdigit():
        raise ValueError(f"'{pr}' is not a pull request number, e.g. 42")
    return pr


def record_owner(issue: dict) -> str:
    """Return a record's owner: whoever created it, or its assignee if a bot did.

    The same rule as ``save_record``'s duplicate check. Records created by a
    review (the bot) belong to whoever they were assigned to; for any other,
    the assignee doesn't count, since anyone with write access can change it.

    Parameters
    ----------
    issue
        Record issue from the GitHub API.

    Returns
    -------
    str
        GitHub username.

    """
    assignees = issue.get("assignees") or []
    if issue["user"].get("type") == "Bot" and assignees:
        return assignees[0]["login"]
    return issue["user"]["login"]


def members(collaborators: list[dict]) -> list[str]:
    """Return who should have a personal record.

    Parameters
    ----------
    collaborators
        Repository collaborators from the GitHub API, with ``role_name``.

    Returns
    -------
    list of str
        GitHub usernames of people with the Write, Maintain or Admin role
        (which includes whoever starts the review). Bots are left out. Anyone who doesn't need a record has it
        closed once, and it is never recreated.

    """
    logins = [
        c["login"]
        for c in collaborators
        if c.get("role_name") in {"write", "maintain", "admin"}
        and c.get("type") != "Bot"
    ]
    return sorted(logins)


def form_body(form: dict) -> str:
    """Render an issue form's pre-filled fields as GitHub renders an issue body.

    Parameters
    ----------
    form
        Parsed issue form.

    Returns
    -------
    str
        One ``### <label>`` section per textarea, with its pre-filled value.

    """
    return "\n\n".join(
        f"### {b['attributes']['label']}\n\n{b['attributes'].get('value', '').strip()}"
        for b in form.get("body", [])
        if b.get("type") == "textarea"
    )


def orphaned_rows(data_dir: Path, records: set[int]) -> dict[int, list[str]]:
    """Find saved rows whose record isn't open.

    Parameters
    ----------
    data_dir
        Directory with the CSV files written by ``save_record``.
    records
        Numbers of the open record issues.

    Returns
    -------
    dict of int to list of str
        Other record number to the CSV files (paths as ``<data_dir>/<name>``)
        that still have its rows.

    """
    found: dict[int, list[str]] = {}
    for path in sorted(data_dir.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            numbers = {int(r["record"]) for r in csv.DictReader(f) if r.get("record")}
        for n in sorted(numbers - records):
            found.setdefault(n, []).append(f"{data_dir.as_posix()}/{path.name}")
    return found


def check_in_body(
    cycle: str,
    due: datetime.date,
    record: int | None,
    group: int | None,
    is_rep: bool,
    repo: str,
    criteria_pr: str = "",
    orphans: dict[int, list[str]] | None = None,
    guide_changes: tuple[str, list[str]] | None = None,
) -> str:
    """Return the body of a member's check-in.

    Lines for records end with a hidden record marker, which a successful
    ``/save`` of that record ticks. People tick the other lines and close the
    check-in themselves; ``save_record`` reopens it if anything is unticked or
    a record wasn't saved during the review.

    Parameters
    ----------
    cycle
        Cycle name.
    due
        Review date.
    record
        The member's personal record, if they have one.
    group
        The group record, if there is one.
    is_rep
        Whether this check-in is the representative's.
    repo
        ``owner/name``, for links to the guides and README.
    criteria_pr
        Number of an open criteria sync pull request, if any.
    orphans
        Saved rows whose record isn't open (see `orphaned_rows`).
    guide_changes
        Commit range (``base...head``) and the guide files that changed in it
        since the previous cycle started, if any; the representative is asked
        to update any published copy, with a link to each file's diff.

    Returns
    -------
    str
        Markdown body.

    """
    site = f"https://github.com/{repo}"
    lines = [
        (
            f"**{cycle}, due {due:%Y-%m-%d}.** Please go over these and make "
            "sure everything is up to date:"
        ),
        "",
    ]
    if record:
        lines.append(
            f"- [ ] Update your personal record (#{record}), then comment "
            f"`/save` on it; saving ticks this item. {record_marker(record)}"
        )
    if group and is_rep:
        lines.append(
            f"- [ ] Update the group record (#{group}) and review members' "
            "changes, then comment `/save` on it; saving ticks this item. "
            f"{record_marker(group)}"
        )
    elif group:
        lines.append(f"- [ ] Update the group record (#{group}).")
    # Everyone, the representative included, looks after the guides.
    lines.append(
        f"- [ ] [Guides]({site}/tree/HEAD/guides): go over them, opening pull "
        "requests to make changes as needed, and review any "
        f"[open pull requests]({site}/pulls) to update the guides."
    )
    if is_rep:
        lines += [
            (
                f"- [ ] [README]({site}#your-green-disc-representative): check the "
                "*Your Green DiSC representative* section is up to date."
            ),
        ]
        if criteria_pr:
            lines.append(
                f"- [ ] #{criteria_pr}: Green DiSC's criteria changed; check the "
                "upstream changes and merge it."
            )
        if guide_changes:
            # GitHub's compare view can't be limited to a folder, but its
            # #diff-<sha256 of path> anchors jump to one file's diff.
            commits, paths = guide_changes
            links = ", ".join(
                f"[{Path(p).name}]({site}/compare/{commits}"
                f"#diff-{hashlib.sha256(p.encode()).hexdigest()})"
                for p in paths
            )
            lines.append(
                f"- [ ] The guides changed since the last review ({links}): if you "
                "publish them elsewhere, such as your website, update that copy."
            )
        if orphans:
            where = "; ".join(
                f"#{n} ("
                + ", ".join(f"[{Path(f).name}]({site}/blob/HEAD/{f})" for f in files)
                + ")"
                for n, files in sorted(orphans.items())
            )
            lines.append(
                "- [ ] Rows in the data files belong to records that aren't open "
                f"(closed, deleted or unlabelled): {where}. Usually, delete those "
                "rows (the ones with that `record` number); editing these files by "
                "hand is fine here, since no record will overwrite them. If a record "
                "was closed by mistake, reopen it and comment `/save` instead. If it "
                "was deleted by mistake, the next review creates a new one for its "
                "owner to fill in; delete the old rows once they have."
            )
    lines += [
        "",
        (
            "Tick the other items as you do them, then **close this check-in**. "
            "If anything is unticked, or a record above wasn't saved during this "
            "review, it's reopened with a note of what's left."
        ),
    ]
    if is_rep:
        lines += [
            "",
            (
                "As the representative, you can close any check-in, including a "
                "member's that can't be finished, e.g. while they're on leave."
            ),
        ]
    return "\n".join(lines) + "\n"


def gh(*args: str, data: dict | None = None) -> str:
    """Run the GitHub CLI.

    Parameters
    ----------
    *args
        Arguments after ``gh``.
    data
        JSON request body, passed on stdin with ``--input -``.

    Returns
    -------
    str
        Standard output.

    """
    if data is not None:
        args = (*args, "--input", "-")
    result = subprocess.run(
        ["gh", *args],
        input=json.dumps(data) if data is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        sys.exit(f"gh {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def api_list(path: str) -> list[dict]:
    """Return every item of a paginated GitHub API list.

    Parameters
    ----------
    path
        API path, e.g. ``repos/o/r/milestones?state=all``.

    Returns
    -------
    list of dict
        All items across pages.

    """
    out = gh("api", "--paginate", path, "--jq", ".[]")
    return [json.loads(line) for line in out.splitlines() if line]


def issues_with(repo: str, query: str) -> list[dict]:
    """Return issues (not pull requests) matching an issues API query.

    Parameters
    ----------
    repo
        ``owner/name``.
    query
        Query string for the issues API, e.g. ``labels=check-in&state=open``.

    Returns
    -------
    list of dict
        Issues.

    """
    items = api_list(f"repos/{repo}/issues?per_page=100&{query}")
    return [i for i in items if "pull_request" not in i]


def start_cycle(
    repo: str,
    due: datetime.date,
    name: str,
    actor: str,
    criteria_pr: str,
    personal_form: dict | None,
    group_form: dict | None,
    data_dir: Path,
    summary: Path | None,
) -> None:
    """Create a review cycle on GitHub and close the previous one.

    Parameters
    ----------
    repo
        ``owner/name``.
    due
        Review date.
    name
        Cycle name; blank for the default.
    actor
        Who started the review: the representative, whose check-in also covers
        the group record, the guides and the README.
    criteria_pr
        Number of an open criteria sync pull request, or blank.
    personal_form
        Parsed personal record issue form, used as the body of records
        created for members who don't have one; None to create none.
    group_form
        Parsed group record issue form, used if the repository has never had
        a group record; None to create none.
    data_dir
        Directory with the saved CSV files, checked for rows whose record no
        longer exists.
    summary
        File to append a Markdown summary to (e.g. the job summary), if any.

    """
    cycle = cycle_name(due, name)
    report = [f"## {cycle}, due {due:%Y-%m-%d}", ""]

    milestones = api_list(f"repos/{repo}/milestones?state=all&per_page=100")
    current = next((m for m in milestones if m["title"] == cycle), None)
    if current is None:
        current = json.loads(
            gh(
                "api",
                f"repos/{repo}/milestones",
                "-X",
                "POST",
                data={
                    "title": cycle,
                    "due_on": f"{due:%Y-%m-%d}T12:00:00Z",
                    "description": f"Green DiSC review. {CYCLE_MARKER}",
                },
            )
        )
        report.append(f"Created milestone **{cycle}**.")
    elif current["state"] != "open":
        # Reusing a past cycle's name would revive it and close the real one.
        raise ValueError(f"Milestone {cycle} is closed; choose another name")
    else:
        report.append(f"Milestone **{cycle}** already exists; adding what's missing.")
        if (current.get("due_on") or "")[:10] != f"{due:%Y-%m-%d}":
            gh(
                "api",
                f"repos/{repo}/milestones/{current['number']}",
                "-X",
                "PATCH",
                "-f",
                f"due_on={due:%Y-%m-%d}T12:00:00Z",
            )
            report.append(f"Changed its due date to {due:%Y-%m-%d}.")
    number = current["number"]
    in_cycle = issues_with(repo, f"milestone={number}&state=all")

    def create(
        title: str, body: str, labels: list[str], assignees=(), in_milestone=True
    ) -> dict:
        data = {
            "title": title,
            "body": body,
            "labels": labels,
            "assignees": list(assignees),
        }
        if in_milestone:
            data["milestone"] = number
        return json.loads(gh("api", f"repos/{repo}/issues", "-X", "POST", data=data))

    # One check-in per record owner; the representative's also covers saving
    # the group record.
    gh("label", "create", CHECK_IN_LABEL, "--color", "C5DEF5", "--force")
    # Everyone with access gets a personal record once; one that was closed
    # (someone who left, or doesn't need one) is never recreated.
    personal = issues_with(repo, "labels=personal-record&state=all")
    if personal_form:
        gh("label", "create", "personal-record", "--color", "2E7D32", "--force")
        owned = {record_owner(r) for r in personal}
        people = members(
            api_list(f"repos/{repo}/collaborators?affiliation=all&per_page=100")
        )
        created = []
        for login in people:
            if login in owned:
                continue
            issue = create(
                f"Green DiSC personal record: {login}",
                form_body(personal_form),
                ["personal-record"],
                [login],
                in_milestone=False,
            )
            personal.append(issue)
            created.append(f"#{issue['number']} ({login})")
        if created:
            report.append(f"Created personal records: {', '.join(created)}.")
    # The group record too, once, assigned to the representative.
    group_records = issues_with(repo, "labels=group-record&state=all")
    if group_form and not group_records:
        gh("label", "create", "group-record", "--color", "2E7D32", "--force")
        issue = create(
            "Green DiSC group record",
            form_body(group_form),
            ["group-record"],
            [actor],
            in_milestone=False,
        )
        group_records.append(issue)
        report.append(f"Created the group record, #{issue['number']}.")
    records = [i for i in personal if i["state"] == "open"]
    groups = [i for i in group_records if i["state"] == "open"]
    # Closing a record removes its rows, so rows from records that aren't open
    # (deleted, unlabelled, or closed before that) would otherwise stay in the
    # data forever: ask the representative about them.
    orphans = orphaned_rows(data_dir, {i["number"] for i in records + groups})
    if orphans:
        report.append(
            "Saved rows from records that aren't open: "
            + ", ".join(f"#{n}" for n in orphans)
            + "."
        )
    # Guides published elsewhere (e.g. a website) are copied by hand: ask the
    # representative when they changed since the previous cycle started.
    guide_changes = None
    previous = max(
        (
            m
            for m in milestones
            if m["number"] != number and CYCLE_MARKER in (m.get("description") or "")
        ),
        key=lambda m: m["created_at"],
        default=None,
    )
    if previous:
        since = previous["created_at"]
        commits = api_list(f"repos/{repo}/commits?path=guides&since={since}")
        # Newest first; the range starts at the parent of the oldest.
        if commits and commits[-1]["parents"]:
            span = f"{commits[-1]['parents'][0]['sha']}...{commits[0]['sha']}"
            files = json.loads(gh("api", f"repos/{repo}/compare/{span}"))["files"]
            paths = [
                f["filename"] for f in files if f["filename"].startswith("guides/")
            ]
            if paths:
                guide_changes = (span, paths)
                report.append(f"Guides changed since {since[:10]}: {', '.join(paths)}.")
    group = min((g["number"] for g in groups), default=None)
    owners = {}
    for r in sorted(records, key=lambda r: r["number"]):
        owners.setdefault(record_owner(r), r["number"])
    owners.setdefault(actor, None)
    # By title, not assignee: someone may have been unassigned, or have left.
    existing = {
        i["title"]
        for i in in_cycle
        if CHECK_IN_LABEL in {lb["name"] for lb in i["labels"]}
    }
    created = 0
    for login, record in owners.items():
        title = f"{cycle} check-in: {login}"
        if title in existing:
            continue
        create(
            title,
            check_in_body(
                cycle,
                due,
                record,
                group,
                login == actor,
                repo,
                criteria_pr if login == actor else "",
                orphans if login == actor else None,
                guide_changes if login == actor else None,
            ),
            [CHECK_IN_LABEL],
            [login],
        )
        created += 1
    report.append(f"Created {created} check-in(s).")

    unsaved = [
        f"#{i['number']}"
        for i in records + groups
        if "unsaved changes" in {lb["name"] for lb in i["labels"]}
    ]
    if unsaved:
        report.append(f"Records with unsaved changes: {', '.join(unsaved)}.")

    # Close earlier cycles, pointing leftovers to their replacements.
    for m in milestones:
        if (
            m["state"] != "open"
            or m["number"] == number
            or CYCLE_MARKER not in (m.get("description") or "")
        ):
            continue
        # Only check-ins: closing a record this way would leave its rows in
        # the data, since closes by GITHUB_TOKEN trigger no workflow.
        query = f"milestone={m['number']}&state=open&labels={CHECK_IN_LABEL}"
        for i in issues_with(repo, query):
            comment = f"Replaced by {cycle}'s check-ins."
            gh(
                "issue",
                "close",
                str(i["number"]),
                "--repo",
                repo,
                "--reason",
                "not planned",
                "--comment",
                comment,
            )
        gh(
            "api",
            f"repos/{repo}/milestones/{m['number']}",
            "-X",
            "PATCH",
            "-f",
            "state=closed",
        )
        report.append(f"Closed the previous cycle, **{m['title']}**.")

    text = "\n".join(report) + "\n"
    print(text)
    if summary:
        with summary.open("a", encoding="utf-8") as f:
            f.write(text)


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface.

    Parameters
    ----------
    argv
        Command-line arguments; defaults to ``sys.argv[1:]``.

    """
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--due", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--criteria-pr", default="")
    p.add_argument(
        "--personal-form", type=Path, help="personal record issue form as JSON"
    )
    p.add_argument("--group-form", type=Path, help="group record issue form as JSON")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    args = p.parse_args(argv)
    try:
        due = parse_due(args.due)
        start_cycle(
            os.environ["GITHUB_REPOSITORY"],
            due,
            args.name,
            os.environ["GITHUB_ACTOR"],
            parse_pr(args.criteria_pr),
            json.loads(args.personal_form.read_text(encoding="utf-8"))
            if args.personal_form
            else None,
            json.loads(args.group_form.read_text(encoding="utf-8"))
            if args.group_form
            else None,
            args.data_dir,
            Path(os.environ["GITHUB_STEP_SUMMARY"])
            if os.environ.get("GITHUB_STEP_SUMMARY")
            else None,
        )
    except ValueError as e:
        sys.exit(f"::error::{e}")


if __name__ == "__main__":
    main()
