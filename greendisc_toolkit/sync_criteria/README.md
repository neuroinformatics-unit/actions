# Sync Green DiSC criteria

This action generates `criteria.yml` from the upstream [Green DiSC criteria repository](https://github.com/Cambridge-Sustainable-Computing-Lab/greenDiSC).

It clones upstream (history only, no file contents beyond the checked-out commit) into the runner's temporary directory, reads the criteria file for each tier (Bronze, Silver, Gold) of the chosen track, and writes one entry per criterion with its ID, issue label, title and category. Tiers without an upstream file yet are written as empty stubs. `source_commit` is the last upstream commit that changed this track's criteria files, so commits that only touch other upstream files don't change `criteria.yml`.

Only these short fields are extracted. The Green DiSC criteria are licensed [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) by Green DiSC; their text is never copied into your repository.

The action fails if the upstream format changes in a way it cannot parse (missing `Version:` line, headings or badges, or duplicate IDs), rather than writing a wrong file. If nothing but the `last_verified` date would change, an existing `criteria.yml` is left untouched, so a following step can open a pull request only when the criteria really changed.

## Inputs

| Input | Default | Description |
|---|---|---|
| `track` | `RG` | `RG` (Research Group), `CT` (Central Team) or `RCI` (Research Computing Infrastructure) |
| `ref` | `main` | Upstream branch, tag or commit SHA to read |
| `upstream-repo` | the Green DiSC repo | Git URL of the criteria repository |
| `output` | `criteria.yml` | Path of the generated file |

## Example output

```yaml
scheme: "Green DiSC"
track: "RG"
source: "https://github.com/Cambridge-Sustainable-Computing-Lab/greenDiSC"
source_commit: "c45acaf7916a9ccdbd809bdf9199b06bc783b140"
last_verified: "2026-10-09"
tiers:
  - name: "Bronze"
    version: "2.0"
    file: "Criteria/Bronze/Research Group - Bronze.md"
    criteria:
      - id: "RG-G1-B"
        label: "criterion:RG-G1-B"
        title: "Green DiSC Representative"
        category: "general"
      # ...
  - name: "Gold"
    criteria: []
```

IDs are the upstream ID (which already ends in the tier, `-B` or `-S`) prefixed with the track, e.g. `RG-G1-B`, because the same upstream ID appears in several tracks: `G1-B` exists for RG, CT and RCI. Note that IDs differing only in tier are unrelated criteria: RG `G1-B` is "Green DiSC Representative", RG `G1-S` is "Regularly discuss digital sustainability in group meetings".

## Examples of usage

Regenerate `criteria.yml` and open a pull request if it changed. The Green DiSC toolkit template ships a complete workflow (`.github/workflows/sync-criteria.yml`); the core is:

```yaml
jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
      - uses: neuroinformatics-unit/actions/greendisc_toolkit/sync_criteria@<sha> # v3.1.0
        with:
          track: RG
      # then commit criteria.yml and open a pull request with `gh` if it changed
```

The action installs Python with `actions/setup-python`; the script uses only the standard library.
