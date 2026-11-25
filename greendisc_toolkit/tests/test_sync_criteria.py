"""Tests for the sync_criteria action, run against the real upstream files."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

import sync_criteria as sc

# Real upstream files, fetched once into a gitignored cache (never committed:
# the criteria are CC BY-NC-ND 4.0). Bump the SHA to test against new upstream.
UPSTREAM_URL = "https://github.com/Cambridge-Sustainable-Computing-Lab/greenDiSC"
UPSTREAM_SHA = "c45acaf7916a9ccdbd809bdf9199b06bc783b140"
UPSTREAM = Path(__file__).parents[1] / ".cache" / "greendisc-criteria"


def git(*args: str) -> None:
    """Run a git command in the upstream cache directory.

    Parameters
    ----------
    *args
        Git arguments.

    """
    subprocess.run(["git", "-C", str(UPSTREAM), *args], check=True)


if not (UPSTREAM / "Criteria").is_dir():
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("remote", "add", "origin", UPSTREAM_URL)
    git("fetch", "-q", "--filter=blob:none", "origin", UPSTREAM_SHA)
    git("checkout", "-q", "FETCH_HEAD")


# Expected upstream content per track, checked against the raw ID badges.
# Tiers not listed must be empty stubs.
EXPECTED = {
    "RG": {
        "Bronze": ("2.0", ["G1-B", "G2-B", "G3-B", "G4-B", "01-B", "02-B", "03-B",
                           "DS1-B", "DS2-B", "HPC1-B", "HPC2-B", "HPC3-B"]),
        "Silver": ("1.0", ["G1-S", "G2-S", "G5-S", "O1-S", "O2-S", "DS1-S",
                           "DS2-S", "C1-S", "C2-S", "C3-S", "C4-S", "C5-S"]),
    },
    "CT": {
        "Bronze": ("2.0", ["G1-B", "G2-B", "G3-B", "G4-B", "O1-B", "O2-B",
                           "DS1-B", "DS2-B", "DS3-B", "HPC1-B", "HPC2-B"]),
    },
    "RCI": {
        # The badge of RCI6 says (CT); it must still get an RCI ID.
        "Bronze": ("1.0", ["G1-B", "G2-B", "G3-B", "G4-B", "G5-B", "O1-B",
                           "DS1-B", "DS2-B", "DS3-B", "RCI1-B", "RCI2-B",
                           "RCI3-B", "RCI4-B", "RCI5-B", "RCI6-B"]),
    },
}  # fmt: skip


# Last commit touching each track's criteria files as of UPSTREAM_SHA (a merge
# commit), checked against the GitHub commits API.
SOURCE_COMMITS = {
    "RG": "ba489984e043b5150bb2030bc1c2bc80c2d20f86",
    "CT": "a79a0c069fd828223c1f047f857902b0d68f112d",
    "RCI": "bac158889df116e350c0d43bafa7e07b29e1722e",
}


@pytest.mark.parametrize("track", EXPECTED)
def test_track(track):
    """Each track's tiers, versions, IDs and fields match upstream and parse as YAML."""
    data = yaml.safe_load(sc.to_yaml(sc.build(UPSTREAM, track)))
    assert data["track"] == track
    assert data["source_commit"] == SOURCE_COMMITS[track]
    assert "greenDiSC" in data["source"]
    for tier in data["tiers"]:
        if tier["name"] not in EXPECTED[track]:
            assert tier == {"name": tier["name"], "criteria": []}
            continue
        version, short_ids = EXPECTED[track][tier["name"]]
        assert tier["version"] == version
        assert [c["id"] for c in tier["criteria"]] == [
            f"{track}-{i}" for i in short_ids
        ]
    criteria = {c["id"]: c for t in data["tiers"] for c in t["criteria"]}
    assert criteria[f"{track}-G1-B"] == {
        "id": f"{track}-G1-B",
        "label": f"criterion:{track}-G1-B",
        "title": "Green DiSC Representative",
        "category": "general",
    }
    # Category comes from the badge URL, not the alt text ("Category general").
    assert criteria[f"{track}-DS1-B"]["category"] == "data storage"


def write(tmp_path: Path, body: str) -> Path:
    """Write a fake Research Group Bronze criteria file.

    Parameters
    ----------
    tmp_path
        Directory acting as the upstream repo root.
    body
        File content.

    Returns
    -------
    pathlib.Path
        Path to the written file.

    """
    f = tmp_path / "Criteria" / "Bronze" / "Research Group - Bronze.md"
    f.parent.mkdir(parents=True)
    f.write_text(body, encoding="utf-8")
    return f


GOOD = """Version: 1.0

## A criterion
![x](https://img.shields.io/badge/category-general-blue)
![x](https://img.shields.io/badge/Criteria%20ID-(RG)%20G1--B-white)
"""


@pytest.mark.parametrize(
    "body, msg",
    [
        ("# no version\n## A\n", "Version"),
        ("Version: 1.0\nno headings\n", "headings"),
        ("Version: 1.0\n## A criterion\nno badges\n", "badge"),
        (GOOD + GOOD.split("\n", 2)[2], "duplicate"),
    ],
)
def test_format_changes_fail_loudly(tmp_path, body, msg):
    """Format changes raise FormatError instead of producing a wrong file."""
    with pytest.raises(sc.FormatError, match=msg):
        sc.parse_file(write(tmp_path, body), "RG")


def test_no_files_for_track_fails(tmp_path):
    """A checkout without any criteria files for the track raises FormatError."""
    with pytest.raises(sc.FormatError, match="no criteria files"):
        sc.build(tmp_path, "RG")


def test_rerun_leaves_file_untouched_if_only_date_differs(tmp_path):
    """Re-running without upstream changes does not rewrite the file."""
    out = tmp_path / "criteria.yml"
    sc.main(["--upstream", str(UPSTREAM), "--out", str(out)])
    stale = re.sub(
        r"^last_verified: .*$",
        'last_verified: "1999-01-01"',
        out.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert "1999-01-01" in stale
    out.write_text(stale, encoding="utf-8")
    sc.main(["--upstream", str(UPSTREAM), "--out", str(out)])
    assert out.read_text(encoding="utf-8") == stale
