# AgriAgent v1.0.0

Final release of the AgriAgent final-year project (VJTI, 2026–27): a safety-gated zero-shot vision
pipeline for crop–weed spot spraying. Research prototype; it must not drive a real sprayer.

## What it is

- **System 1 (local GPU):** Grounding DINO + SAM 2 (the Grounded SAM pipeline), frozen plant rules v3
  and a deterministic safety gate that alone decides what is sprayed.
- **System 2 (cloud, advice only):** Qwen 3.8 diagnosis on Cloudflare Workers AI, herbicide advice only
  from the ICAR bulletin table for the declared crop, one optional escalation agent for withheld plants.
- **Application:** Streamlit dashboard with REAL/MOCK banner, spray map, "show every plant" view,
  GeoJSON export (placeholder coordinates, not GPS) and a farmer summary in English, Hindi and Marathi.

## Headline result

Held-out sugar beet set (90 photos, evaluated once): **77.9% weed recall at 8.8% crop pixels
sprayed**, against 1.8% / 65.5% for the Grounded SAM label policy. Details in
`docs/thesis/AgriAgent_Final_Report.pdf` and `docs/results/`.

## Fixes verified in Test Cycle 2

Made on 7 November and re-tested by Amit Ingle on Windows (cases R1–R6, all PASS):

- **F24:** the previous (even MOCK) result no longer stays on screen during a new run.
- **F26:** models load once per process under a lock: no more "Cannot copy out of meta tensor"; later runs are faster.
- **F27:** the wrong-crop warning is part of the farmer summary in English, Hindi and Marathi.
- **F28:** new "Show every plant and what the system decided" view (sprayed / protected as crop / left alone).
- **F29:** herbicide advice always ends with the fixed "suggestion, not an instruction; read the label" caveat.

Also in this release: the lock file installs on Windows (Linux-only packages marked), the end-to-end
runner works from any folder, and `scripts/package_release.py` accepts branch names with `/`
(reported by Amit Ingle in Test Cycle 2).

## Test Cycle 2 (7–8 November 2026)

Windows 11, Python 3.13.9, NVIDIA RTX 3050 (4 GB), real mode with Cloudflare keys, commit `b9f6364`:
24 of 24 executed cases PASS (install and automated checks A1–A6, regression R1–R6, manual MT-04–07,
exploratory X1–X8). Results: `AgriAgent Test Cycle 2` sheet; screenshots in the team Drive.

## Requirements

Python 3.11, 3.12 or 3.13 (3.10 cannot install the locked versions). Install with
`python -m pip install -r requirements-lock.txt` and `python -m pip install -e . --no-deps`, then
`python scripts/download_models.py`. Runs on a 4 GB GPU (peak about 2.6 GB) or on the CPU (10–20 s per
photo). Cloudflare Workers AI keys in `.env` are needed only for the diagnosis and the Hindi/Marathi summary.

## Known limitations

- **F1:** rule 4 can mark a whole off-row beet as a weed when the detector misses its crop box.
- Cotton weed recall is about 10%: large weeds can be protected as crop.
- Tiny sprouts inside beet boxes can be sprayed (about 0.05% of a photo).
- The escalation agent is safe but adds no weed recall (off by default).
- GeoJSON coordinates are placeholders near VJTI, not GPS.

## Package

`AgriAgent-1.0.0-v1.0.0-source.zip`, built by `scripts/package_release.py --ref v1.0.0` from the tag
and checked for secrets; model weights and datasets are not included (downloaded by script).
