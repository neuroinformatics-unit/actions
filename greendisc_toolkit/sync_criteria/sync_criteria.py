# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Generate criteria.yml from a local checkout of the Green DiSC criteria repo.

Only IDs, short titles, categories and versions are extracted, never the
upstream prose (which is CC BY-NC-ND 4.0).
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

TRACKS = {
    "RG": "Research Group",
    "CT": "Central Team",
    "RCI": "Research Computing Infrastructure",
}
TIERS = ["Bronze", "Silver", "Gold"]

VERSION_RE = re.compile(r"^Version:\s*(\S+)", re.MULTILINE)
# e.g. https://img.shields.io/badge/category-data%20storage-red
CATEGORY_RE = re.compile(r"img\.shields\.io/badge/category-(.+?)-[^-)]+\)")
# e.g. https://img.shields.io/badge/Criteria%20ID-(RG)%20G1--B-white
# The track in the badge is ignored: one RCI badge says (CT).
ID_RE = re.compile(r"img\.shields\.io/badge/Criteria%20ID-\(\w+\)%20(.+?)-[^-)]+\)")


class FormatError(Exception):
    """Raised when upstream files are missing or not in the expected format."""


def parse_file(path: str | Path, track: str) -> tuple[str, list[dict[str, str]]]:
    """Parse one upstream criteria file.

    Parameters
    ----------
    path
        Path to a criteria Markdown file, e.g.
        ``Criteria/Bronze/Research Group - Bronze.md``.
    track
        Track code (``"RG"``, ``"CT"`` or ``"RCI"``) used to prefix the IDs.
        The track printed in the ID badge is ignored, as upstream is not
        always consistent.

    Returns
    -------
    version : str
        The file's ``Version:`` value, e.g. ``"2.0"``.
    criteria : list of dict
        One dict per ``##`` section with keys ``id`` (e.g. ``"RG-G1-B"``),
        ``label`` (e.g. ``"criterion:RG-G1-B"``), ``title`` and ``category``.

    Raises
    ------
    FormatError
        If the version line, the ``##`` headings or a section's ID or category
        badge are missing, or if IDs are duplicated.

    """
    text = Path(path).read_text(encoding="utf-8")
    version = VERSION_RE.search(text)
    if not version:
        raise FormatError(f"{path}: no 'Version:' line")
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    if not sections:
        raise FormatError(f"{path}: no '## ' criterion headings")
    criteria = []
    for section in sections:
        title = section.splitlines()[0].strip()
        id_match, cat_match = ID_RE.search(section), CATEGORY_RE.search(section)
        if not (id_match and cat_match):
            raise FormatError(f"{path}: section {title!r} lacks ID or category badge")
        short_id = unquote(id_match.group(1)).replace("--", "-")
        cid = f"{track}-{short_id}"
        criteria.append(
            {
                "id": cid,
                "label": f"criterion:{cid}",
                "title": title,
                "category": unquote(cat_match.group(1)).replace("--", "-"),
            }
        )
    ids = [c["id"] for c in criteria]
    if len(set(ids)) != len(ids):
        raise FormatError(f"{path}: duplicate criterion IDs {ids}")
    return version.group(1), criteria


def git(upstream: str | Path, *args: str) -> str:
    """Run a git command in a repository and return its output.

    Parameters
    ----------
    upstream
        Repository to run the command in.
    *args
        Git arguments, e.g. ``"rev-parse", "HEAD"``.

    Returns
    -------
    str
        Standard output, stripped of surrounding whitespace.

    Raises
    ------
    subprocess.CalledProcessError
        If git exits with a non-zero status.

    """
    return subprocess.run(
        ["git", "-C", str(upstream), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def build(upstream: str | Path, track: str) -> dict:
    """Build the criteria data for one track from a local upstream clone.

    Parameters
    ----------
    upstream
        Local clone of the Green DiSC repo, with ``origin`` set to its URL and
        enough history to find the last commit that changed the criteria
        files (a blobless clone is enough).
    track
        Track code, one of the keys of `TRACKS`.

    Returns
    -------
    dict
        Top-level keys ``scheme``, ``track``, ``source``, ``source_commit``
        (the last upstream commit that changed this track's criteria files,
        so unrelated upstream commits don't change it), ``last_verified`` and
        ``tiers``. Each tier has ``name`` and
        ``criteria``, plus ``version`` and ``file`` when upstream has a file
        for it; tiers without one (e.g. Gold) have empty ``criteria``.

    Raises
    ------
    FormatError
        If the track is unknown, no tier has any criteria, or a file fails
        to parse (see `parse_file`).

    """
    upstream = Path(upstream)
    if track not in TRACKS:
        raise FormatError(f"unknown track {track!r}; expected one of {list(TRACKS)}")
    tiers = []
    for tier in TIERS:
        path = upstream / "Criteria" / tier / f"{TRACKS[track]} - {tier}.md"
        if path.exists():
            version, criteria = parse_file(path, track)
            tiers.append(
                {
                    "name": tier,
                    "version": version,
                    "file": path.relative_to(upstream).as_posix(),
                    "criteria": criteria,
                }
            )
        else:
            tiers.append({"name": tier, "criteria": []})
    if not any(t["criteria"] for t in tiers):
        raise FormatError(f"no criteria files for track {track} under {upstream}")
    files = [t["file"] for t in tiers if "file" in t]
    return {
        "scheme": "Green DiSC",
        "track": track,
        "source": git(upstream, "remote", "get-url", "origin"),
        "source_commit": git(upstream, "log", "-1", "--format=%H", "--", *files),
        "last_verified": datetime.datetime.now(datetime.UTC).date().isoformat(),
        "tiers": tiers,
    }


def to_yaml(data: dict) -> str:
    """Serialise the output of `build` as YAML.

    Parameters
    ----------
    data
        Criteria data as returned by `build`.

    Returns
    -------
    str
        YAML document, with every scalar double-quoted.

    """

    # ponytail: hand-rolled emitter for this fixed shape; JSON-quoted strings
    # are valid YAML, so no PyYAML needed. Use PyYAML if the shape grows.
    def q(v: str) -> str:
        return json.dumps(v, ensure_ascii=False)

    lines = ["# Generated by sync_criteria. Do not edit by hand."]
    for k, v in data.items():
        if k == "source_commit":
            lines.append(
                "# Upstream commit that last changed this track's criteria"
                " (not necessarily upstream's latest)."
            )
        if k != "tiers":
            lines.append(f"{k}: {q(v)}")
    lines.append("tiers:")
    for tier in data["tiers"]:
        lines.append(f"  - name: {q(tier['name'])}")
        for k in ("version", "file"):
            if k in tier:
                lines.append(f"    {k}: {q(tier[k])}")
        if not tier["criteria"]:
            lines.append("    criteria: []")
            continue
        lines.append("    criteria:")
        for c in tier["criteria"]:
            first, *rest = c
            lines.append(f"      - {first}: {q(c[first])}")
            lines += [f"        {k}: {q(c[k])}" for k in rest]
    return "\n".join(lines) + "\n"


def same_ignoring_date(a: str, b: str) -> bool:
    """Compare two criteria YAML documents, ignoring ``last_verified``.

    Parameters
    ----------
    a, b
        YAML documents as produced by `to_yaml`.

    Returns
    -------
    bool
        True if the documents differ at most in their ``last_verified`` line.

    """
    drop = re.compile(r"^last_verified:.*$", re.MULTILINE)
    return drop.sub("", a) == drop.sub("", b)


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface.

    Writes the criteria file, unless an existing one differs only in
    ``last_verified``, in which case it is left untouched. Exits with an
    error message if parsing or git fails.

    Parameters
    ----------
    argv
        Command-line arguments; defaults to ``sys.argv[1:]``.

    """
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--upstream", required=True, help="local clone of upstream")
    p.add_argument("--track", default="RG", choices=list(TRACKS))
    p.add_argument("--out", default="criteria.yml")
    args = p.parse_args(argv)
    try:
        data = build(args.upstream, args.track)
    except (FormatError, subprocess.CalledProcessError) as e:
        sys.exit(f"sync_criteria: {e}")
    out, new = Path(args.out), to_yaml(data)
    if out.exists() and same_ignoring_date(out.read_text(encoding="utf-8"), new):
        # Leave the file untouched so callers can open a PR only on real changes.
        print(f"{args.out} unchanged")
        return
    out.write_text(new, encoding="utf-8", newline="\n")
    counts = ", ".join(f"{t['name']} {len(t['criteria'])}" for t in data["tiers"])
    print(f"Wrote {args.out}: {counts}")


if __name__ == "__main__":
    main()
