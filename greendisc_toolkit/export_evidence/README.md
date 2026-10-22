# Export Green DiSC evidence

This action (and the script behind it) turns a Green DiSC toolkit repository's saved records into an **evidence pack** to attach to a Green DiSC submission. Auditors come from other institutions and can't open a private repository, so the evidence has to leave it as files.

> [!NOTE]
> Exporting is optional: you can also submit the files in `data/` as they are (but they name record numbers and include locations). Nothing runs automatically; run it when you prepare a submission, either from a local clone or with the template's **Export Green DiSC evidence** workflow.

The pack holds:

- `index.html`: one section per criterion, with its table and links, plus the review history. Open it in a browser; attach it to the submission with the CSV files.
- `csv/RG-<id>.csv`: each criterion's rows, for auditors who prefer a spreadsheet.
- `guides/`: the guides that serve as evidence (`e-waste.md`, `green-computing.md`).

By default it leaves out the **Location** and **Asset tag** columns, and replaces record numbers with `member 1`, `member 2`, … (numbered in record order, the same in every file), so the pack shows what the group has without saying who has it. Group tables (compute, training, sharing) have no member column. `G1-B` and `G2-B` aren't in the pack: their evidence (the representative's profile, your onboarding material) lives outside the repository.

## Running it locally

From a clone of your Green DiSC repository, with [uv](https://docs.astral.sh/uv/) installed (the script needs only Python's standard library):

```sh
uv run --script https://raw.githubusercontent.com/neuroinformatics-unit/actions/<sha>/greendisc_toolkit/export_evidence/export_evidence.py
```

This writes `greendisc-evidence/` in the current directory; open `greendisc-evidence/index.html`. Without uv, download the script and run it with Python 3.13 or later: `python export_evidence.py`.

Options:

| Option | Default | Description |
|---|---|---|
| `--repo-dir` | `.` | Clone of the repository |
| `--out` | `greendisc-evidence` | Output directory; must not exist or be empty |
| `--data-dir` | `data` | CSV files, relative to `--repo-dir` |
| `--guides-dir` | `guides` | Guides, relative to `--repo-dir` |
| `--drop-columns` | `Location,Asset tag` | Columns to leave out, as headed in the records |
| `--keep-all` | off | Leave no columns out (members are still numbered) |
| `--with-reviews` | off | Add the review history; needs the [GitHub CLI](https://cli.github.com/), logged in (`gh auth login`) |

Examples (with `export_evidence.py` standing for the `uv run --script <url>` command above):

```sh
# Add the review history (cycles, dates, check-ins done)
gh auth login
export_evidence.py --with-reviews

# Also leave out suppliers
export_evidence.py --drop-columns "Location,Asset tag,Supplier"

# Keep every column, e.g. for your own records
export_evidence.py --keep-all --out evidence-full

# Run from elsewhere, writing to a dated folder
export_evidence.py --repo-dir ~/greendisc --out ~/greendisc-evidence-2027-03
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `data-dir` | `data` | CSV files written by `save_record` |
| `guides-dir` | `guides` | Guides |
| `drop-columns` | `Location,Asset tag` | Columns to leave out, as headed in the records |
| `keep-all` | `false` | `true` leaves no columns out |
| `with-reviews` | `true` | `false` leaves out the review history |
| `out` | a new directory under the runner's temp directory | Output directory; must not exist or be empty |
| `token` | `github.token` | Token with `issues: read`, for the review history |

Output: `path`, the directory holding the pack.

## Examples of usage

The Green DiSC toolkit template ships a complete workflow (`.github/workflows/export-evidence.yml`); the core is:

```yaml
on:
  workflow_dispatch:

jobs:
  export:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: read # review history
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
      - id: export
        uses: neuroinformatics-unit/actions/greendisc_toolkit/export_evidence@<sha> # v3.1.0
      - uses: actions/upload-artifact@<sha> # v7.0.2
        with:
          name: greendisc-evidence
          path: ${{ steps.export.outputs.path }}
          retention-days: 7
```

Leaving out another column, or keeping them all:

```yaml
      - id: export
        uses: neuroinformatics-unit/actions/greendisc_toolkit/export_evidence@<sha> # v3.1.0
        with:
          drop-columns: Location,Asset tag,Supplier
          # keep-all: true
```

Without the review history (the job then needs only `contents: read`):

```yaml
        with:
          with-reviews: false
```

## How it works

Each criterion maps to a table and a filter: `01-B` is every hardware row, `02-B` the hardware rows with status `unused` or `disposed`, `G3-B` and `G4-B` the sharing rows of kind `shared resource` and `promotion`, `03-B` and `HPC3-B` add their guides. Columns are read from the CSV headers, so columns added to the records later are exported too. Every value is HTML-escaped in `index.html`. Only open records' rows are in `data/`, since closing a record removes them, so the pack shows the current state.

The review history lists the milestones created by [`review_cycle`](../review_cycle/README.md) (recognised by a marker in their description), with due and closed dates and how many check-ins were done.

The output directory must be new or empty, so a pack never mixes with files from an earlier export.
