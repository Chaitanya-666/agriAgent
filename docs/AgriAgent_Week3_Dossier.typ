#import "template.typ": *
#show: doc.with(
  title: "AgriAgent Week 3 Dossier",
  subtitle: "12 – 18 October 2026 · first real run, trusted ground truth, and the team hand-off",
  date: "17 October 2026",
)

#show table: set par(justify: false)

#note(title: "Read this first")[
  Sections 1–4 record what Week 3 produced and what it showed. *Section 5 is the hand-off: every
  member's tasks with a hard deadline of Wednesday 21 October.* Section 6 lists the open bugs with
  severity and owner. Everything marked #real below was run on 17 October and checked by eye by
  Chaitanya; the command and output files are named so anyone can repeat it.
]

= Summary

Week 3 had two goals: run the vision models for real on our own laptop, and find out whether our
evaluation labels can be trusted. Both are done, and both changed the project.

- *The real pipeline runs on the team laptop* (RTX 5050, 2.4 GB peak GPU memory). Getting there
  needed six fixes, including two places where the code silently produced fake numbers.
- *Our old evaluation labels were fabricated.* `eval_manifest_v1` matches almost none of the official
  dataset labels. It is replaced by `eval_manifest_v2`, copied from the official files.
- *The core problem is confirmed on our own hardware.* On a sugar beet image, Grounding DINO called
  all four beet plants "weed" and the old gate sprayed every one of them, while the two real weeds
  were missed. Separating weed from crop is the research question for the rest of the project.

= Evidence

#table(
  columns: (auto, auto, 1fr),
  [Item], [Status], [Evidence (17 Oct)],
  [T1.1 laptop environment], [#real], [`~/.venvs/agriagent`, torch 2.11 + CUDA 12.8 sees the RTX 5050; DINO-tiny and SAM 2-tiny cached (1.6 GB).],
  [T1.2 first real local run], [#real], [`scripts/run_live_pipeline.py` on 3 images: both models REAL (printed), no mock fallback, peak 2.4 GB GPU, about 45 s per image including model loading. Figures and logs in `data/outputs/real_*`.],
  [Gate on real images (after fixes)], [#real], [Re-run on official `X-10-0.png` and `CM_17.jpg`: low-confidence masks withheld with reasons, status "No weed zones approved", System 2 told the declared crop. Checked by Chaitanya.],
  [Real mode fails loudly (T1.3)], [#real], [With no model cache the script stops with "Real mode requested but Grounding DINO … could not be loaded". Checked by Chaitanya.],
  [Groq `qwen/qwen3.8-27b`], [#real], [Text and image calls answer; System 2 diagnoses real photos (`check_providers.py`: PASS).],
  [Cloudflare Clef Flash], [#real], [Answers with images through the "choice" question (`check_providers.py`: PASS). Not yet inside the workflow (T2.8).],
  [Local Qwen / local Clef], [#planned], [Dropped by team decision (Section 4). Code stays as an unused fallback.],
  [Annotation audit (T3.1)], [#real], [`scripts/audit_eval_manifest.py`: side-by-side figures in `data/outputs/audit/`. v1 fails (Section 3).],
  [Evaluation set v2 (T3.2, T3.4)], [#real], [`data/manifests/eval_manifest_v2.json`: 38 images, 93 crop and 324 weed boxes, from official files only.],
  [Crop-or-weed check (T2.2)], [#real], [`scripts/compare_crop_or_weed.py` on 20 labelled patches (Section 3.3).],
  [Tests], [#real], [190 unit + 35 end-to-end tests pass, also with torch hidden as in CI; ruff and mypy clean.],
)

= What we learned

== The real pipeline had hidden faults

Six problems sat between "the code exists" and "the code runs for real". Two of them produced
believable but fake output, which is why every claim must be checked by running it:

+ *SAM 2 crashed on transformers 5* (issue \#13, TC-15). Fixed.
+ *Every real mask got a made-up quality score of 0.88*: the code read a field that does not exist. The refinement loop could never trigger. Fixed; real scores are 0.93–0.97.
+ *Refinement would have crashed in real mode* without Meta's `sam2` package. Fixed.
+ *System 2 only worked with a local server we do not run*, and *Groq never received the photo*: its diagnosis was blind. Fixed: System 2 uses Groq with the image.
+ *The script and the app never loaded `.env`*, so the Groq key was never used. Fixed.
+ *The script's "spray map" picture painted crop masks red* even when the gate had excluded them. Fixed: panel 3 shows all masks by label, panel 4 the map the gate approved.

== Our old labels were fabricated

`eval_manifest_v1` (added by an AI-written commit on 11 October) was compared box by box with the
official dataset files:

- *Sugar beet:* every image carries the same template, 2 crop and 6 weed boxes; the official labels
  vary (2–4 crop, 0–2 weed). Only 1–2 of 8 boxes match per image. In `X-10-0` a "crop" box sits on
  bare soil and the "weed" boxes sit on the beet plants.
- *Cotton:* no box matches at all. CottonWeedDet3 labels weed species only (morning glory, Palmer
  amaranth); it has *no cotton labels*, yet v1 contained a cotton box in every image.
- Two cotton photos are byte-identical copies in the official dataset itself (`CM_11` = `CM_29`,
  `CM_36` = `CM_40`); v2 keeps one of each.

*Consequence for the report:* crop protection (crop pixels on the spray map) can only be measured on
sugar beet. Cotton images measure weed detection only. v2 labels are boxes, not pixel masks.

== Who can tell crop from weed?

20 patches cut from official labels (10 beet crop, 6 beet weed, 4 cotton weed), each back-end asked
"crop or weed?" with the field's crop named:

#table(
  columns: (1fr, auto, auto, auto, auto),
  [Back-end], [Correct], [Crop called weed (crop sprayed)], [Weed called crop (weed missed)], [s / patch],
  [Groq qwen3.8-27b], [*16/20*], [1 of 10], [3 of 10], [about 1–2],
  [Cloudflare Clef Flash], [14/20], [2 of 10], [4 of 10], [1.0],
  [Row rule (no model)], [13/20], [3 of 10], [4 of 10], [0.03],
)

No back-end is reliable alone, and they fail on different patches (a simple majority vote reaches
15/20). On the real cotton photo Groq called an ivyleaf morning glory (a known cotton look-alike) a
"cotton seedling". *20 patches is too few for a final choice*; T2.5 repeats this on more patches.
A dataset bias to report: beet weeds are tiny (median 16 px across) and beet crops large (median
68 px), so size alone separates many of them.

== The GeoJSON export is not yet usable

A mock run exported *1,394 spray features for 3 weeds*: 3 real polygons and 1,391 specks (median
26 px) from jagged mask edges, each with its own nozzle id. Coordinates are a fixed point near VJTI
plus 0.00001° (about 1.1 m) per pixel, so a phone photo of about one metre of soil becomes a field of
about 4.5 × 3.4 km. Both go to Amit (Section 6).

= Decisions taken on 17 October

- *Final submission and viva: Tuesday 10 November.* Code freeze stays Thursday 5 November.
- *Models:* only Grounding DINO-tiny and SAM 2-tiny run locally. Reasoning uses Groq and Cloudflare.
  Local Qwen and local Clef are dropped. No Kaggle compute; Kaggle is only used to download files.
- *Evaluation set:* `eval_manifest_v2` (30 sugar beet + 8 cotton) is frozen. Nobody edits it.
- *Testing roles:* Sahil = validation tester ("is the output correct?"), Sumant = system tester
  ("does it work for a user?"). Amit moves to development (app fixes, demo, slides) and still
  re-tests and closes the issues he filed.
- *Crop-or-weed model:* decided by measurement (T2.5), not by one picture.
- *Known issues* from Guide 2 §10 are called *K1–K12* from now on, so they are never confused with
  GitHub issue numbers.

= Hand-off: tasks until Wednesday 21 October

Chaitanya and Claude did Week 3 and part of Week 4 so the rest of the team can work without a GPU or
coding tools. *Hard deadline for everything in this section: Wednesday 21 October, 23:59.* Post
evidence (screenshot, link or file) in the group for each item.

== Everyone (Sat 18 Oct)

+ Pull `main`; set up Python as in the README; create *your own* Groq key (console.groq.com/keys) and
  put it in `.env`; run `python scripts/check_providers.py groq` and post the PASS line (hide the key).
+ Read this dossier, then Guide 2 §10 (K1–K12) and Guide 4 (demo playbook).

== Sahil: validation tester

#table(
  columns: (auto, 1fr, 1fr),
  [ID], [Task], [Done when],
  [V1], [Check `eval_manifest_v2` by eye: for 10 beet and 4 cotton images, draw the official boxes (ask Chaitanya for the figure script) and confirm they sit on the right plants.], [Table image / ok / problem, posted.],
  [V2], [Hand-compute 3 crop-on-spray-map examples on paper (crop pixels sprayed ÷ all crop pixels) for tiny 10×10 masks.], [Photo of the working; used as unit-test values for T3.5.],
  [V3], [Validation test plan: 12–15 cases (input, expected result, how measured), starting from Chaitanya's Lab02 sheet.], [Typst or sheet shared.],
  [V4], [Run test D: open the 20 patches in `data/outputs/t2_2/` (Chaitanya sends them) and judge each yourself before looking at the model answers.], [Your 20 answers next to the three back-ends.],
  [V5], [Execute the validation cases on `main` once the baseline numbers exist (Sun 25); file a GitHub issue for every failure.], [Results sheet; issues filed.],
  [V6], [Report chapter 6 (results) outline and chapter 4c (data and evaluation) first draft, using Section 3 of this dossier.], [Draft in `docs/report/`.],
)

== Sumant: system tester and report lead

#table(
  columns: (auto, 1fr, 1fr),
  [ID], [Task], [Done when],
  [S1], [Get the department's report format; send it to Chaitanya, who commits the report skeleton.], [Format file posted.],
  [S2], [T2.4: from `data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf`, a table of 5 cotton weeds: herbicide, dose (g a.i./ha), water volume, waiting period, *page number*. Then compare with the rows in `src/agronomy/knowledge_store.py` and the banned list in `src/agronomy/prescription.py` (K12).], [Table posted; every mismatch filed as an issue.],
  [S3], [System test cycle 1 on `main` (app in mock mode): every case of Amit's TC-01…16 plus test C: clear the prompt box (\#6), prompt `cotton . weed .` (\#8), Force System 2 with Wheat, Rice, Sugar Beet (\#11).], [Results sheet pass/fail; issues filed.],
  [S4], [Add 6–8 system test cases for real mode (untick Mock Mode; needs no GPU, only patience on CPU): what the screen must say, error messages, timing.], [Cases added to the sheet.],
  [S5], [Report chapters 1 (introduction, problem) and 2 (literature: Grounding DINO, SAM 2, Chong et al. IROS 2025) first draft.], [Draft in `docs/report/`.],
)

== Amit: development and demo

#table(
  columns: (auto, 1fr, 1fr),
  [ID], [Task], [Done when],
  [A1], [T4.3: REAL / MOCK badge on every result screen, read from the mode the models actually ran in, not from the checkbox. Remove "VERIFIED & APPROVED" when the diagnosis is mock (\#10).], [PR merged, screenshot of both modes.],
  [A2], [T4.4: no herbicide fields in the GeoJSON unless a real prescription exists (\#7); the confidence slider passes its value into the workflow (\#9); label coordinates as pixel-based, not GPS (K9).], [PR merged with e2e tests.],
  [A3], [GeoJSON fragments: one feature per approved zone (MultiPolygon) and drop pieces smaller than a nozzle footprint (Section 3.4).], [PR merged; the same mock run exports 3 features.],
  [A4], [Re-test and close \#6, \#8, \#11, \#13 on `main` (fixed on 17 Oct). Reopen with a comment if any fails.], [Issues closed or reopened.],
  [A5], [Slide deck skeleton in one style; each member's 2–3 slides as placeholders.], [Deck link posted.],
)

== Chaitanya and Claude (in parallel, Week 4–5 core)

T3.5 crop-on-spray-map metric (with Sahil's V2 values) · T3.6 baseline real run over v2 on the laptop
GPU (*Checkpoint 2, Sun 25*) · real ICAR knowledge store in real mode (prescriptions are empty today) ·
T1.6 crop-exclusion improvement · T1.7 triage before the map · T2.8 Clef adapter · T2.5 crop-or-weed
comparison on more patches · report skeleton and PR reviews.

== Rules that still apply

- One pull request per task, from your own branch; CI must be green; someone else reviews.
- The tester who filed a defect closes it; developers never close their own defects.
- No "done", "verified" or "100%" without a pasted command output or screenshot.
- Do not change models, add dependencies or edit `eval_manifest_v2` without a team decision.
- AI agents: one at a time, and read their changes before you push.

= Open bugs: severity and owner

#table(
  columns: (auto, 1fr, auto, auto, auto),
  [Issue], [Problem], [Severity], [Owner], [Status],
  [\#13], [Real mode crashed in SAM 2 (TC-15).], [high], [Chaitanya], [fixed, Amit re-tests],
  [\#6], [Empty prompt still produced weeds.], [high], [Chaitanya], [fixed, Amit re-tests],
  [\#8], [Status claimed a prescription with 0 zones.], [medium], [Chaitanya], [fixed, Amit re-tests],
  [\#11], [Cotton herbicide recommended for wheat, rice, sugar beet.], [high], [Chaitanya], [fixed, Amit re-tests],
  [\#9], [Confidence slider ignored by the GeoJSON.], [high], [Amit (app) + Chaitanya (gate, fixed)], [app part open],
  [\#7], [Herbicide in GeoJSON with System 2 off.], [high], [Amit], [open (A2)],
  [\#10], [Mock diagnosis shown as "VERIFIED & APPROVED".], [high], [Amit], [open (A1)],
  [\#12], [Blank image gets a spray map. A blank JPG is a valid image; the real fault is mock boxes on any image (as \#10).], [medium], [Amit], [open (A1)],
  [new], [GeoJSON exports 1,394 features for 3 weeds; fake GPS scale.], [medium], [Amit], [open (A3, A2)],
)
