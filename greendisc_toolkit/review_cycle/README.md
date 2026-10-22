# Start a Green DiSC review cycle

This action starts a review cycle in a repository created from the Green DiSC toolkit template. A cycle is the period leading up to one review; its milestone's due date is the review date, chosen by the team.

It:

1. checks that whoever ran the workflow has the **Maintain** or **Admin** role, and stops otherwise;
2. creates the group record if the repository has never had one (from the group record form, assigned to whoever started the review), and a personal record for each member who has never had one (people with the Write, Maintain or Admin role; not bots), from the personal record form's tables, titled `Green DiSC personal record: <username>` and assigned to them;
3. creates the cycle's milestone (default name `Review-<year>-<month>` of the due date; spaces in a given name become hyphens, because GitHub's milestone links don't quote names);
4. creates a check-in for each owner of an open personal record, assigned to them, asking them to go over their record, the group record and the guides (suggesting and reviewing changes as pull requests); the check-in of whoever started the review (the representative) also asks them to save the group record, check the README's representative section, plus, only when they apply: checking and merging the criteria sync pull request (when `criteria-pr` is given), updating any published copy of the guides (when `guides/` changed since the previous cycle started, with a link to each changed file's diff), and dealing with data rows whose record isn't open;
5. closes the previous cycle: its open check-ins are closed, then its milestone is closed;
6. writes a summary to the job summary, including records with unsaved changes.

Check-ins are to-do lists. Lines for records end with a hidden `<!-- record:N -->` marker, which [`save_record`](../save_record/README.md) ticks when record N is saved. People tick the other items and close their check-in themselves; `save_record` reopens it if an item is unticked or a record on it wasn't saved during the review, unless whoever closed it has the Maintain or Admin role (the representative, e.g. for a member on leave).

Running it again for the same cycle adds only what's missing, so a failed run can be re-run.

The workflow's inputs reach the script only through environment variables. `yq`, preinstalled on GitHub-hosted runners, converts the issue forms to JSON, so the script uses the standard library only.

## Inputs

| Input | Default | Description |
|---|---|---|
| `due` | (required) | Review date, as `YYYY-MM-DD`; the milestone's due date |
| `name` | `Review-<year>-<month>` | Cycle and milestone name |
| `criteria-pr` | (blank) | Number of an open criteria sync pull request; adds an item to the representative's check-in |
| `personal-form` | `.github/ISSUE_TEMPLATE/personal-record.yml` | Issue form used for new personal records; empty to create none |
| `group-form` | `.github/ISSUE_TEMPLATE/group-record.yml` | Issue form used for the group record if there has never been one; empty to create none |
| `data-dir` | `data` | CSV files written by `save_record`; rows whose record isn't open are listed in the representative's check-in |

The action uses the job's `GITHUB_TOKEN`, so the job needs `permissions: issues: write, contents: read` (`contents` for the guide changes). Other tokens (a personal access token or a GitHub App's) aren't supported: [`save_record`](../save_record/README.md) gives a record created by `github-actions[bot]` to whoever it was first assigned to, and one created by anyone else to its creator.

## Examples of usage

The Green DiSC toolkit template ships a complete workflow (`.github/workflows/review.yml`); the core is:

```yaml
on:
  workflow_dispatch:
    inputs:
      due:
        description: Review date (YYYY-MM-DD)
        required: true
      name:
        description: Cycle name (default Review-<year>-<month>)
        required: false

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
      - uses: neuroinformatics-unit/actions/greendisc_toolkit/review_cycle@<sha> # v3.1.0
        with:
          due: ${{ inputs.due }}
          name: ${{ inputs.name }}
```
