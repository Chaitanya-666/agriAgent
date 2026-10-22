# Verification run, 23 October 2026 (before the Sunday 25 October test day)

Everything below was run on `main` = `19339fd` on the team laptop (RTX 5050, torch 2.11+cu128,
transformers 5.20.1), real models unless marked mock. Purpose: check that what is merged works as
intended, before the Sunday decisions. Nothing in `src/` or `app/` was changed by this run.

## Verdict

The product works end to end and fails safe. Every automated check passes, the held-out result
reproduces exactly, and no input tried crashed it. The findings below are mostly wording, demo and
release issues. One is a real method weakness (F1), already part of the measured crop damage,
that needs a decision because the method is frozen.

## What was run

| Check | How | Result |
|---|---|---|
| CI checks locally | `ruff check .`, `ruff format --check .`, `mypy src/`, 240 unit tests, 35 e2e tests | all pass |
| Fresh clone | `git clone` from GitHub into an empty folder, both test suites | all pass |
| Secrets | tracked files and all history searched for Groq / GitHub / HF / AWS key patterns; `.env` ignored | none found |
| Live providers | `scripts/check_providers.py` | Groq PASS (5.3 s), Cloudflare clef-flash PASS (1.3 s) |
| Data rebuild | `scripts/build_eval_manifest_v2.py` in the fresh clone (Kaggle CLI) | `eval_manifest_v2` identical (38 items; only `created_at` differs) |
| Held-out set rebuild | every sugar beet image not in v2, boxes from the official XML | identical to `eval_manifest_v2_holdout` (90 images, same boxes) |
| Held-out reproduction | `scripts/run_baseline.py --manifest …holdout` | every setting identical to `holdout_plant_rules_v3_20261018` (plant rules 8.84% crop / 77.93% weed recall / 104 of 363 beets / 177 of 215 weeds); the product's own path `pipeline_plant_rules` gives the same numbers |
| Determinism | first 10 held-out images run twice | 0 differences over 8 settings |
| Speed | same run | 0.64 s per image after the first, model load 12.5 s |
| Test cycle 1, mock | `scripts/verify_test_cycle1.py` (new) | ST-01 to ST-11: 11 PASS |
| Test cycle 1, real | `scripts/verify_test_cycle1.py --real` | ST-12, 13, 16, 17, 19, 20, 21/22 PASS; ST-15, 18 measured; ST-14 FAIL (see F11) |
| CLI on the 6 test photos | `scripts/run_live_pipeline.py` | all exit 0, 19 to 31 s each including model load |
| Edge-case images | 12 inputs through the app's real-mode path, cloud keys blanked | no crash; black, noise, solid green, 1×1, grayscale: nothing sprayed |

Edge cases: grayscale PNG, RGBA PNG, palette PNG, 32×32, 1×1, 6000×4000, 384×1024 portrait, all
black, solid green, random noise, overexposed, rotated 90°. No network (all proxies to a closed
port) and an empty `GROQ_API_KEY`: vision runs, System 2 records its error, the farmer summary
falls back to the template, exit 0.

## Findings

Severity: **high** = can put herbicide on the crop; **medium** = misleading output or a release
or demo risk; **low** = cosmetic or maintenance.

| ID | Severity | Finding | Evidence | Proposed action (decide Sunday) |
|---|---|---|---|---|
| F1 | high (method) | The plant rules call any plant whose centre is off the crop row a weed, whatever its size. A large beet is saved only when Grounding DINO happens to box it as the crop. | X-10-0 rotated 90°: the detector returns no crop box and the largest beet (4,410 px) is sprayed completely, 41.8% of crop pixels (`images/verify_rotation_X-10-0.jpg`). Rules alone, both orientations: that beet is "weed: off the crop row". Same failure as X2-30-0 (2 of 3 beets sprayed). Part of the measured 104/363 held-out beets touched. | Option A: keep v3 frozen and report it as the main limitation (honest, no new measurement). Option B: change the rule to "off the row but not small → unsure", measure on the development set only, and report that the held-out set was already used once for v3. |
| F2 | medium (release) | All requirements are lower bounds only, and some are wrong (`transformers>=4.40.0`; the SAM 2 code needs 5.x). A fresh install today resolves to untested versions: torch 2.14.1, huggingface-hub 2.2.0, Pillow 13.0.0. | `uv pip compile requirements.txt` | Commit a lock file of the working environment for `v1.0.0`; fix the transformers lower bound; README installs from the lock file. |
| F3 | medium (demo) | Groq's free tier (8,000 tokens per minute) returns 429 on back-to-back real runs. In the app, real mode also runs the escalation agent, up to 12 more calls per photo. | 429 on the 4th and 5th of 6 back-to-back CLI runs; ST-18: agent 6 reviews, all "unsure", 70 s. Fail-safe works (no crash, template summary). | Space demo runs about 1 minute apart; consider the agent off by default in the app (measured: safe, not effective); optional retry with back-off for System 2. |
| F4 | medium (honesty) | The farmer summary's "N plants were not sprayed because the system was unsure; check them by eye" counts masks the gate withheld, even when the plant rules then called those plants crop, or sprayed them as weeds. | X3-430-0: summary says 6 unsure; plant rules: 18 crop, 1 unsure. `build_facts` uses `withheld_masks`. | When the plant rules ran, report their "unsure" count. Small fix plus a test. |
| F5 | medium (demo) | Approved weed patches are often a few pixels, invisible in the 4-panel figure and the app overlay, so a correct result looks like "nothing sprayed". | X-10-0 panel 4 | Draw an outline or marker around each approved patch. |
| F6 | low | Withheld reason says "Escalating to VLM critic" even when no per-plant escalation runs (agent off). | CLI output, `deterministic_router.py:115,183` | Reword to "withheld for review". |
| F7 | low | CLI prints `None None g/ha` when there is no prescription. | `run_live_pipeline.py:298` | Print "no prescription". |
| F8 | low (K8) | Forced System 2 path in the app still falls back to the weed name "Trianthema". | `app/components/pipeline.py:294,296` | Remove the fallback, with a test. |
| F9 | low | The app uses Streamlit's deprecated `use_container_width`; works on 1.66, may break on a later Streamlit. | warnings in every AppTest run | Covered by F2's lock file; replace with `width=`. |
| F10 | info | No real ICAR prescription appeared on any of the 6 test photos: sugar beet has no row in the bulletin table (correct), and cotton CM_11, labelled one morningglory weed, was diagnosed by the model as "cotton seedling with powdery mildew". The prescription path is shown only by unit tests and mock mode. | CLI runs | Pick one cotton photo for the demo where the model names a weed in the ICAR cotton rows, or state the limit. |
| F11 | info (test doc) | ST-14's expected result ("no colour on beets") is stricter than box labels can measure. X3-130-0: 0.05% painted (0.68% with the 10 px buffer), no main beet touched, two small sprouts inside beet boxes sprayed. | `images/verify_st14_X3-130-0.jpg` | Reword ST-14: "below 2%; at most small specks next to beets". |
| F12 | info (cotton) | On CM_11 the only plant is a large morningglory weed; the rules take the largest plant for the crop, so it is not sprayed. | CLI run | Known cotton limit; already in the Week 4 dossier. |
| F13 | low (docs) | Guide 2's known-issue table is out of date: K2, K10, K11, K12 are fixed or measured. The held-out manifest has no build script (it rebuilds exactly by its rule). | this run | Update the table; optional `--holdout` option for the builder. |

Log noise that is expected: "You are using a model of type `sam2_video` to instantiate a model of
type `sam2`" (the image model loads from the video checkpoint) and Grounding DINO's
`labels`→`text_labels` FutureWarning.

## F1 measured: what protecting large off-row plants costs

`scripts/experiment_f1_row_rule.py`, development set only (the held-out set was not read). Rule 4
("off the crop row → weed", used when a photo has no crop masks) was changed to "off the row → weed
only if smaller than LIMIT × the median plant on the row, otherwise unsure". Both rule versions are
applied to the same detections, in the product's own way, with the 10 px buffer. Every photo is
scored as taken and rotated 90° (labels rotated). The v3 rows reproduce the committed development
result exactly (`pipeline_plant_rules_dev_20261020`).

Sugar beet, 30 photos, 93 beets, 282 weeds ("mostly sprayed" = at least half of the beet's pixels;
"weeds hit" = at least half of the weed's pixels):

| Rule | View | Crop pixels sprayed | Weed recall | Beets touched | Beets mostly sprayed | Weeds hit |
|---|---|---|---|---|---|---|
| **v3 (frozen)** | as taken | 4.55% | **71.47%** | 21 | 11 | 219 |
| v3 | rotated | 8.46% | 71.47% | 23 | 14 | 219 |
| limit 0.25 | as taken | 0.25% | 12.92% | 9 | 0 | 150 |
| limit 0.5 | as taken | 0.32% | 21.97% | 10 | 1 | 172 |
| limit 1.0 | as taken | 0.98% | 31.30% | 14 | 3 | 191 |
| limit 1.5 | as taken | 1.20% | 39.08% | 16 | 4 | 202 |
| limit 1.5 | rotated | 4.28% | 39.08% | 17 | 6 | 202 |

Cotton (8 photos): v3 10.40% weed recall; limits 0.25 to 1.0 give about 4.2%; limit 1.5 is the same as v3.

What this shows:

- There is no free fix. Rule 4 produces most of v3's weed recall *and* most of its crop damage:
  many real weeds in this dataset are not smaller than the beets on the row. Protecting large
  off-row plants removes the fully sprayed beets (11 → 0 to 4) but loses 32 to 59 points of weed
  recall.
- Crop damage depends on whether Grounding DINO happens to box the crop: the same photos rotated
  give 4.55% → 8.46% crop sprayed under v3, while weed recall is unchanged (the row test itself
  works in both orientations).
- Recommendation: **option A**. Keep v3 frozen (its held-out numbers stay valid), report F1 as the
  main limitation, and report this table as the safety-versus-recall trade-off of the row rule. A
  stricter "safe mode" setting (limit 1.5) is possible future work; adopting it now would need a new
  held-out test that we no longer have.

## For Sunday

1. F1: option A (recommended, see the measurement above) or B.
2. Which of F2–F9 to fix before the code freeze (all small; F2, F4 and F5 matter most).
3. ST-14 wording (F11), so the team's results are judged against what can be measured.
4. A demo photo that shows a real prescription (F10), or say why there is none.

New in this run: `scripts/verify_test_cycle1.py` (automates ST-01 to ST-22 where possible; AppTest
cannot upload files, so photo cases call `run_pipeline_on_image`, the function the app runs after an
upload). Run outputs: `data/outputs/baseline/verify_holdout_20261023/` and
`verify_holdout_repeat10_20261023/` (not in git).
