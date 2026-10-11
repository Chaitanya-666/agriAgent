#import "template.typ": *
#show: doc.with(
  title: "AgriAgent Week 2 Dossier",
  subtitle: "6 – 11 October 2026 · cleanup, safety fixes, and an honest status check",
)

#note(title: "Correction")[
  An earlier Week 2 dossier claimed 100% completion, 227 verified tests, zero regressions and a
  completed Clef evaluation. Those claims were wrong: CI was failing on `main`, the test count did not
  match, and every evaluation file was generated in mock mode. This document replaces it.
]

= Summary

Week 2 did not add new features. It made the project *truthful and consistent*: it removed leftover
and contradictory code, fixed a real safety bug in the spray-map export, got CI passing, froze the
model choices, and looked honestly at the one real result we have. That result showed the main
problem we still need to solve: separating weed from crop.

= Work done

== Evaluation harness (Track 3, Track 1)

`src/evaluation/benchmark_runner.py` and `src/evaluation/ablation_runner.py` were added to run the
pipeline over a dataset manifest (`data/manifests/eval_manifest_v1.json`) and compute IoU, Dice and
herbicide savings, plus ablations (with/without refinement, router variants). The code works, but
*every result produced so far was in mock mode*. Those result files were removed because they could
be mistaken for real accuracy numbers. The harness is ready for real runs.

== Spray-map safety bug fixed (Track 1, Track 4)

*The bug.* The workflow carefully filtered masks into an approved spray map, but the GeoJSON exporter
in the app ignored that and rebuilt spray zones from the raw detector boxes, accepting any label
containing the word "weed". So the label `cropweed` was rejected by the workflow but exported anyway,
and `grass` was accepted by the workflow but not exported.

*The fix.* The exporter (`build_spray_geojson` in `app/components/pipeline.py`) now reads only the
approved zones stored in the workflow's spray-map artifact. Raw boxes can never become spray
features. If the gate suppresses the map, the export is empty.

*Proof.* `tests/test_spray_export_safety.py` checks crop labels, labels containing crop names,
`cropweed`, `grass`, `weed`, infestation above the 85% ceiling, empty masks, and that no unapproved
box reaches GeoJSON.

== Model decisions frozen (all tracks)

The model plan had changed several times. It is now fixed (details in the Project Map):

- *Detection / segmentation:* Grounding DINO-tiny and SAM 2-tiny, local.
- *Cloud reasoning:* Groq `qwen/qwen3.8-27b`.
- *Local reasoning:* `Qwen/Qwen3.5-4B` (optional).
- *Triage:* local `Cloudflare/clef-flash` adapter (`src/agents/clef_flash_router.py`). It replaced the
  Laya router, which was removed. Clef cannot run on our 8 GB GPU; the deterministic gate works without it.
- *Safety authority:* `DeterministicRouter` (`src/agents/deterministic_router.py`), plain rules.

Old references to Qwen2.5, Laya and Cloudflare's online API were removed from code and docs.

== CI fixed (Track 4)

GitHub Actions runs on Python 3.10 and 3.11: lint, formatting, compile, mypy type checking, unit
tests, end-to-end tests and a headless Streamlit start-up check.

#table(
  columns: (auto, auto, 1fr),
  [Commit], [CI result], [Note],
  [`6c1fb91` (main)], [failed], [mypy type errors in providers, workflow, evaluation.],
  [`4c5a84b`], [failed], [Same layer, after model migration.],
  [`f0e97a2`], [*passed*], [Run 38151532673: both Python versions green. Type errors fixed in code, not silenced.],
)

Re-checked independently on 11 October on Python 3.11: *175 unit tests and 35 end-to-end tests pass*,
lint and format clean. With the full ML libraries installed, mypy found 4 more errors (hidden in CI
because CI installs fewer libraries); two were fixed and two belong to an unused leftover file that is
being removed.

== Repository cleanup

Removed: the copied SmartDesk code, an outdated Qwen planning dossier, duplicate Week 1 dossiers,
seven overlapping status files in the repository root, raw web-search dumps, AI-generated "research
bible" PDFs, and mock evaluation outputs. Everything removed is still recoverable from Git history.
The documentation is now: `README.md`, the Project Map, and one dossier per week.

= The real result

#figure(
  image("images/live_real_spray_map_kaggle.png", width: 100%),
  caption: [The only real run: Grounding DINO-tiny + SAM 2-tiny on a Kaggle T4 GPU, 3 October 2026.],
)

*What happened.* Grounding DINO found one box, labelled "vegetation" with confidence 0.61, covering
the whole field. SAM 2 segmented almost everything inside it. The figure reports 78.9% weed coverage
and 19.5% "savings" — but most of what was marked is *cotton*. A real sprayer following this map
would spray the crop.

*Why.* Grounding DINO matches words to image regions. It has no idea which plants are weeds in a
cotton field unless the prompt and the label rules make that distinction. "Vegetation" matches all
plants.

*What it means for us.* The project's central research question is now clear: _can an open-vocabulary
detector + segmenter, with prompt design, deterministic rules and VLM escalation, keep the crop off the
spray map while still covering the weeds?_ We must measure crop pixels on the spray map, not just
mask quality.

= Design issues found

+ The gate in `spray_map_node` passes confidence and IoU as a hard-coded `1.0`; only the infestation
  ceiling is enforced on the final map.
+ Triage (escalation) runs after the spray map is approved and does not withdraw it.
+ The default prompt in `scripts/run_live_pipeline.py` (`"cotton weed . broadleaf plant ."`) would
  be rejected entirely by the gate's crop-name rule.
+ Weed / crop labels come from prompt words, not from any model that understands the difference.

These are Track 1's first tasks after the freeze.

= Evidence matrix

#table(
  columns: (auto, auto, 1fr, 1fr),
  [Area], [Status], [Evidence], [Remaining work],
  [Vision pipeline], [#real once], [Kaggle run, `docs/images/`], [Local real run; real metrics.],
  [Spray safety], [#partial], [`tests/test_spray_export_safety.py`, CI run 38151532673], [Fix design issues; test on real masks.],
  [Local Clef Flash], [#blocked], [Adapter code + mock tests only], [Needs > 8 GB GPU; document as future work.],
  [Local Qwen3.5-4B], [#partial], [`tests/test_providers.py` (mocked)], [Optional: 4-bit run on laptop.],
  [Groq Qwen3.8-27B], [#partial], [`tests/test_providers.py` (mocked)], [API key; one real end-to-end call.],
  [Agronomy RAG], [#partial], [ICAR bulletin ingested offline in tests], [Check prescriptions for 3–5 weeds by hand.],
  [Evaluation], [#mock], [All prior outputs had `mock_mode: true` (removed)], [Real evaluation set and metrics.],
  [Streamlit app], [#mock], [Headless start-up in CI], [A human uses it on real images.],
  [CI], [#real], [Run 38151532673 green on 3.10 + 3.11], [Keep green.],
  [Documentation], [done], [README, Project Map, Week 1, Week 2], [Final report in November.],
)

= Next week

The repository is frozen until Wednesday 14 October while the team studies the Project Map and their
own track's code. After that: the first real local run on the laptop, and opening the Streamlit app
with real weights. See the timeline in the Project Map.
