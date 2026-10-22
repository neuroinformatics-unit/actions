# Save Green DiSC records

This action saves Green DiSC *record issues* to CSV files. A record issue holds one Markdown table per section (personal records: Hardware, Data resources, Data cleaning, Pipelines; the group record: Compute infrastructure, Training, Sharing and promotion), created from the toolkit's record issue form.

- **A personal record belongs to whoever created it**, or, for records created by [`review_cycle`](../review_cycle/README.md), to whoever it was first assigned to. Changing the assignee later doesn't change the owner, since anyone with write access can do that.
- **Each person can have one personal record, and the repository one group record.** Only the oldest counts: `/save` on a second one replies with a link to the first. The record's label (`personal-record` or `group-record`) is added on its first save; the toolkit's issue forms also add it when the label already exists.
- **When someone comments exactly `/save`** (other comments, like `/saved it`, are ignored), the action reads every table by its column headers, validates the rows and writes them to `<data-dir>/<section>.csv` (e.g. `data/hardware.csv`), replacing the rows previously saved from that issue. It commits to the default branch, replies with a summary and removes the `unsaved changes` label. The issue stays open, so it can be updated later.
- **When a record's body is edited**, the action adds the `unsaved changes` label, so edits that were never saved are easy to find (`label:"unsaved changes"`).
- **A personal record can be saved by its owner (with write access) or a maintainer/admin; the group record, which anyone with write access can edit, only by a maintainer/admin.** The action checks the commenter's role, since the workflow's `author_association` filter also lets read-only organisation members through; anyone else gets a reply explaining why nothing was saved.
- **After a successful save**, the action ticks the record's lines in open review check-ins (issues labelled `check-in`, created by [`review_cycle`](../review_cycle/README.md)).
- **When someone closes a check-in**, the action checks it's finished: every item ticked, and every record on it saved during the review (a reply from the bot to `/save` on that record since the review's milestone was created, so a record line ticked by hand doesn't count). If not, it reopens the check-in with a reply listing what's left. Check-ins closed by someone with the Maintain or Admin role are left closed (the representative can close one that can't be finished, e.g. for a member on leave). Edits to check-ins need no run; the toolkit's workflow skips them.
- **When a record is closed** (its owner left), the action removes its rows from every CSV file, commits, and replies with what was removed, so the files hold current evidence only. Reopening the record and commenting `/save` restores them; `/save` on a closed record gets a reply asking to reopen it first.
- **If any row is invalid**, nothing is written: the reply lists each problem by section, row and column, and the `unsaved changes` label stays. The same goes for a section whose heading or table is missing while rows from it were saved before (usually a heading changed by accident); to remove a section's rows, keep its table with no rows.

Blank cells are saved as `unknown`, so missing data stays visible; `-` (or `n/a`, `na`) marks a cell that doesn't apply. Optional columns (Notes, Location, Asset tag) stay blank when blank. Missing or reordered columns are fine; unrecognised columns are ignored with a warning. Each CSV has a `record` column with the issue number, which is how a later `/save` finds the rows to replace; edits made directly to the CSV are overwritten by the next `/save` of that issue.

If another save lands at the same time, the push is retried on the latest branch (up to 5 times), so concurrent saves don't conflict.

Issue content is untrusted: it reaches the script only through environment variables and files, never through the workflow's shell code.

## Inputs

| Input | Default | Description |
|---|---|---|
| `data-dir` | `data` | Directory for the CSV files |

The action uses the job's `GITHUB_TOKEN`, so the job needs `permissions: contents: write, issues: write`. Other tokens (a personal access token or a GitHub App's) aren't supported: the check-in close check and record ownership rely on the bot's replies and records being by `github-actions[bot]`. It commits to the default branch, so branch protection that requires pull requests blocks it.

## Examples of usage

The calling workflow decides who may trigger it. The Green DiSC toolkit template ships a complete workflow (`.github/workflows/save-record.yml`); the core is:

```yaml
on:
  issues:
    types: [edited, closed]
  issue_comment:
    types: [created]

jobs:
  record:
    # Issues only (not PRs); a cheap first filter, the action checks roles.
    # Issue events: edits flag unsaved changes, closing removes the rows or
    # checks a check-in is finished. Edits to check-ins need no run.
    if: >-
      !github.event.issue.pull_request &&
      ((github.event_name == 'issues' &&
          !(github.event.action == 'edited' && contains(github.event.issue.labels.*.name, 'check-in'))) ||
        (startsWith(github.event.comment.body, '/save') &&
          contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association)))
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
      - uses: neuroinformatics-unit/actions/greendisc_toolkit/save_record@<sha> # v3.1.0
```
