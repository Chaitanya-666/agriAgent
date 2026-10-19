#import "template.typ": *
#show: doc.with(
  title: "AgriAgent Week 4 Dossier",
  subtitle: "18 – 20 October 2026 · baseline, two measured improvements, the escalation answer, feature freeze",
  date: "20 October 2026",
)

#show table: set par(justify: false)

#note(title: "Read this first")[
  Week 4's goal was the first honest metrics table (Checkpoint 2, due Sunday 25 October). It was
  reached on 18 October, and the remaining research questions were answered by 20 October. Every
  number below is #real: Grounding DINO-tiny and SAM 2-tiny on the team laptop (RTX 5050), scored
  against the official dataset labels. Raw files are in `docs/results/`; each one names the command
  that produced it. *Features are frozen from 22 October* (Section 6).
]

= Summary

#table(
  columns: (auto, 1fr),
  [Question], [Answer (measured)],
  [RQ1: do text prompts separate weed from crop?], [*No.* On the 30 sugar beet evaluation photos the label policy alone sprays 70.8% of crop pixels and hits 9.0% of weed pixels. On 90 held-out photos: 65.5% crop, 1.8% weeds. Grounding DINO boxes mostly the large crop plants and almost never the small weeds.],
  [RQ2: does escalation to a reasoning model help?], [*Safe, not effective.* The escalation agent reviewed 69 withheld plants: it never approved spraying a crop plant and 13 of its 14 "crop" verdicts were right, but it left 24 of 25 real weeds withheld. The spray map did not change.],
  [RQ3: which cheap addition helps most?], [*A rule-based plant classifier.* Every green patch is a candidate; crop if inside a crop mask or on the crop row, weed if much smaller than the crop plants. Held-out 90 photos: weed recall *1.8% → 77.9%*, crop pixels sprayed 8.8%. Crop exclusion alone: 20.5% → 5.3% crop sprayed. Tiling: no gain.],
  [Speed], [0.56 s per image after warm-up (detection 0.21 s, segmentation 0.28 s); model loading 5 s.],
)

= Metrics and data

- *Metrics* (`src/evaluation/crop_protection.py`): crop pixels sprayed ÷ all crop pixels (lower is
  better), weed pixels sprayed ÷ all weed pixels (weed recall), herbicide saved, and plant counts
  (crop plants touched, weeds at least half covered). The spray area includes the 10-pixel nozzle
  buffer. Labels are boxes, so plant pixels are the vegetation inside each box (excess green above
  a per-image Otsu threshold); a pixel in both a crop and a weed box counts as crop.
- *Data:* `eval_manifest_v2` (30 sugar beet + 8 cotton, official labels) for development, and
  `eval_manifest_v2_holdout` (the other 90 sugar beet photos of the same Kaggle dataset; 363 crop
  plants, 232 weeds; 66 photos contain no weeds) used *once*, with the rules frozen.
- *K10 fixed:* the spray buffer no longer depends on whether OpenCV is installed.

= Results

== Baseline: the zero-shot pipeline (`docs/results/baseline_v2_20261018`)

#table(
  columns: (1fr, auto, auto, auto, auto),
  [Sugar beet, 30 photos], [Crop sprayed], [Weed recall], [Crop plants touched], [Saved],
  [Every SAM 2 mask, no gate], [93.9%], [97.6%], [87/93], [39%],
  [Label policy only (gate 0.35)], [70.8%], [9.0%], [45/93], [93%],
  [Gate 0.50], [20.5%], [6.8%], [8/93], [98%],
  [Gate 0.70 (deployed)], [0.0%], [0.0%], [0/93], [100%],
)

Real detector scores never exceed 0.68, so the deployed 0.70 limit, set on mock data, sprays
nothing. The 97.6% of the first row comes from whole-photo masks: without masks covering more than
half the photo, all masks together cover only 9.1% of weed pixels.

== Improvements

#table(
  columns: (1fr, auto, auto, auto),
  [Setting (sugar beet)], [Crop sprayed], [Weed recall], [Source],
  [Gate 0.50 + crop exclusion (T1.6)], [5.3%], [6.8%], [`exclusion_v2_20261018`],
  [Tiled detection 2 × 2 + exclusion], [8.4%], [0.4%], [`detector_variants_20261018`],
  [*Plant rules v3, evaluation set*], [*4.6%*], [*71.5%*], [`plant_rules_v3_20261018`],
  [*Plant rules v3, held-out 90 photos*], [*8.8%*], [*77.9%*], [`holdout_plant_rules_v3_20261018`],
  [Plant rules v3, cotton (8 photos)], [-], [10.4%], [`plant_rules_v3_20261018`],
)

The plant rules rely on two facts of young sugar beet: weeds are smaller than the crop, and the crop
grows in rows. Neither holds for the cotton close-ups, where one large weed fills the photo.

== Escalation agent (`docs/results/agent_v2_20261018`)

#table(
  columns: (1fr, auto, auto, auto),
  [Plant really was], [Agent: weed], [Agent: crop], [Agent: unsure],
  [crop (44)], [0], [13], [31],
  [weed (25)], [0], [1], [24],
)

One source can never decide alone (answers are capped by each source's measured accuracy and
combined by naive Bayes); with Clef Flash often lukewarm and 14 of 69 Groq calls rate-limited, most
plants stayed "unsure". Running time about 40 minutes for 38 photos on the free tier.

= Other work

- *Plant rules in the product* (PR \#22): real mode in the app and `scripts/run_live_pipeline.py`
  uses them; the GeoJSON export keeps weeds down to 16 px. Reproduces the measured numbers.
- *Farmer summary* (`src/agronomy/farmer_summary.py`): two or three plain sentences in English,
  Hindi or Marathi; the model only rewords the pipeline's facts, otherwise a template is used.
- *ICAR table checked against the bulletin* (K12, PR \#23, `docs/results/icar_table_check_20261020`):
  cotton rows and the banned list were right; the rice row was an overdose (20 g, maximum 15 g) with a
  waiting period 20 days short, a beet-root waiting period was invented, blank values were stored as
  "0 days"; five dose ceilings were wrong. All fixed with regression tests.
- *Safety rule:* a single mask covering more than half the photo is withheld as "not one plant".

= Decisions on 20 October

+ *Feature freeze from Thursday 22 October.* After it, only bug fixes, tests, clean-up and
  documentation. The method (plant rules v3) is frozen since the held-out test.
+ *One last measurement before the freeze:* the frozen rules on an independent public dataset from
  other fields, measured without any tuning, to test whether the result transfers.
+ *Testing is the team's responsibility:* test cycle 1 by Tuesday 27 October, regression cycle by
  Wednesday 4 November (`docs/AgriAgent_Team_Tasks.pdf`).
+ *Code freeze and release `v1.0.0`: Thursday 5 November.* Submission and viva: Tuesday 10 November.

= Limits to state in the report

- Labels are boxes; plant pixels are estimated, the same way for every method.
- One sugar beet dataset: the held-out photos are new to the rules but come from the same fields.
- The plant rules use crop-specific facts and do not transfer to the cotton close-ups.
- About 29% of crop plants have at least one pixel inside the spray area on the held-out set.
- Published numbers use other metrics and datasets; they are context, not a ranking.
