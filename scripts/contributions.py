"""Write CONTRIBUTIONS.md: who built what in AgriAgent, with numbers taken from the repository.

Usage:
    python scripts/contributions.py            # rewrite CONTRIBUTIONS.md from the current history
    python scripts/contributions.py --check    # exit 1 if CONTRIBUTIONS.md is out of date

Numbers are counted, never typed: commits (without merge commits) from `git log`, the current code
by author from `git blame` over every tracked Python file in src/, app/, tests/ and scripts/, and
pull requests and issues from GitHub (`gh`, skipped when it is not available). The component table
below is the record of who owns which part; change it only by a team decision.
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "CONTRIBUTIONS.md"

# One entry per member: display name, git author emails, GitHub logins.
MEMBERS = [
    (
        "Chaitanya Shinde (lead)",
        {"orionck545@gmail.com", "chaitanyashinde545@gmail.com"},
        {"Chaitanya-666"},
    ),
    ("Amit Ingle", {"aringle_b23@ce.vjti.ac.in"}, {"Amit123-coder"}),
    ("Sumant Vetal", {"vetsum5@gmail.com"}, {"vetsum5", "snvetalb23-afk"}),
    ("Sahil Chavan", {"sahilchavangithub@gmail.com"}, {"sahilchavan94"}),
]

# Component ownership (the locked record). Owner = who built the current version.
COMPONENTS = [
    ("Research questions, scope, methodology", "Chaitanya", ""),
    (
        "Vision pipeline: Grounding DINO, SAM 2, refinement, model loading (`src/vision/`)",
        "Chaitanya",
        "",
    ),
    (
        "Deterministic safety gate (`src/agents/deterministic_router.py`, spray map in `src/workflow.py`)",
        "Chaitanya",
        "",
    ),
    ("Plant rules v3 (`src/vision/plant_candidates.py`)", "Chaitanya", ""),
    ("Escalation agent and evidence sources (`src/agents/`)", "Chaitanya", ""),
    (
        "System 2: diagnosis, ICAR knowledge store, prescription, providers (`src/agronomy/`)",
        "Chaitanya",
        "first version by Sumant (5 Oct); rewritten, checked against the bulletin and integrated by Chaitanya",
    ),
    ("Farmer summary in English, Hindi, Marathi", "Chaitanya", ""),
    ("Streamlit application (`app/`)", "Chaitanya", "first dashboard by Amit (4 Oct)"),
    ("GeoJSON export", "Chaitanya", ""),
    (
        "Evaluation sets from official labels, label audit, metrics (`src/evaluation/`)",
        "Chaitanya",
        "dataset downloader by Sahil (4 Oct)",
    ),
    ("All experiments and results (`docs/results/`)", "Chaitanya", ""),
    ("Unit and end-to-end tests, CI, verification run, manual test cycle", "Chaitanya", ""),
    ("System test cycle 0 (16 cases, fresh Windows install, 8 issues filed)", "Amit", ""),
    ("System test cycle 2 on the final build (7-12 Nov)", "Amit", ""),
    ("Fixes for all findings F1-F29", "Chaitanya", ""),
    ("Final report, slides, guides and all project documents (`docs/`)", "Chaitanya", ""),
]


def run(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def member_of_email(email: str) -> str:
    for name, emails, _ in MEMBERS:
        if email.lower() in emails:
            return name
    return "other"


def member_of_login(login: str) -> str:
    for name, _, logins in MEMBERS:
        if login in logins:
            return name
    return "other"


def commits() -> Counter:
    out = run("git", "log", "--all", "--no-merges", "--format=%ae")
    return Counter(member_of_email(e) for e in out.split())


def code_lines() -> Counter:
    files = [
        f
        for f in run("git", "ls-files", "src", "app", "tests", "scripts").split("\n")
        if f.endswith(".py")
    ]
    lines: Counter = Counter()
    for f in files:
        for row in run("git", "blame", "--line-porcelain", "HEAD", "--", f).split("\n"):
            if row.startswith("author-mail "):
                lines[member_of_email(row[len("author-mail ") :].strip("<>"))] += 1
    return lines


def github(kind: str) -> Counter | None:
    try:
        out = run("gh", kind, "list", "--state", "all", "--limit", "500", "--json", "author")
    except (OSError, subprocess.CalledProcessError):
        return None
    return Counter(member_of_login(item["author"]["login"]) for item in json.loads(out))


def render() -> str:
    head = run("git", "log", "-1", "--format=%h %cs").split()
    c, lines, prs, issues = commits(), code_lines(), github("pr"), github("issue")
    total_c, total_l = sum(c.values()), sum(lines.values())
    rows = []
    for name, _, _ in MEMBERS:
        rows.append(
            f"| {name} | {c[name]} of {total_c} | {lines[name]:,} ({100 * lines[name] / total_l:.1f}%) | "
            f"{prs[name] if prs is not None else '-'} | {issues[name] if issues is not None else '-'} |"
        )
    comp = [f"| {what} | {owner} | {note} |" for what, owner, note in COMPONENTS]
    return "\n".join(
        [
            "# Contributions",
            "",
            f"Record of who built what in AgriAgent, generated by `scripts/contributions.py` from the "
            f"repository at commit `{head[0]}` ({head[1]}). Numbers are counted from git and GitHub, not typed; "
            "the component table is the team's record of ownership and changes only by a team decision.",
            "",
            "## Counted from the repository",
            "",
            "| Member | Commits (no merges) | Current Python code (git blame) | Pull requests | Issues |",
            "| --- | --- | --- | --- | --- |",
            *rows,
            "",
            "Current Python code = lines in tracked `.py` files under `src/`, `app/`, `tests/`, `scripts/` "
            "at that commit, attributed by `git blame` to the last author of each line.",
            "",
            "## Components and owners",
            "",
            "| Component | Owner | Note |",
            "| --- | --- | --- |",
            *comp,
            "",
            "## Summary",
            "",
            "- **Chaitanya Shinde** (lead) designed and built the system, ran every measurement, fixed every "
            "finding and wrote the report, the slides and the documents.",
            "- **Amit Ingle** built the first dashboard and ran the system test cycles (cycle 0 and cycle 2).",
            "- **Sumant Vetal** wrote the first version of the System 2 code (5 October).",
            "- **Sahil Chavan** wrote the dataset downloader and added the fixture sample (4 October).",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        # The commit line changes with every commit; compare the rest.
        strip = lambda t: "\n".join(t.split("\n")[3:])  # noqa: E731
        return 0 if strip(current) == strip(text) else 1
    OUT.write_text(text, encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
