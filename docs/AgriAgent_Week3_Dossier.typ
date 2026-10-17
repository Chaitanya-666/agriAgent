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

The step-by-step tasks for every member are in *`docs/AgriAgent_Team_Tasks.pdf`* (updated 17 Oct,
evening). Summary: everyone first sets up the project and answers ten understanding questions
(E-1, E-2); *Sahil* checks the new labels by eye, hand-computes the metric examples, writes the
validation test plan, judges the crop-or-weed patches, picks hard test images and collects report
content (SA-1 to SA-6); *Sumant* gets the report format, checks the herbicide table against the ICAR
PDF, runs the new system test cases in mock and real mode, repeats the crop-or-weed comparison and
collects report content (SU-1 to SU-6); *Amit* re-tests and confirms the closed issues, repeats his
Cycle 0 cases, records a real-mode video, dry-runs the demo and sets up the slide deck (AM-1 to AM-5).
Teammates collect evidence and fill sheets; all Typst writing is done by Chaitanya. Sahil's and
Sumant's lists include about 20% of their Week 5 work because their Week 3 deliverables were not
submitted.

= Cycle 0 bugs: all fixed, re-tested and closed

Every issue was fixed, then re-tested by repeating Amit's exact steps with
`scripts/verify_cycle0_issues.py`, which drives `app/app.py` headlessly (9 of 9 checks pass,
including two in real mode on the GPU). Each issue on GitHub has a comment with the cause, the fix
and the re-test result. Amit confirms them by hand (task AM-1).

#table(
  columns: (auto, 1fr, auto, auto),
  [Issue], [Problem → fix], [Severity], [Fixed in],
  [\#13], [Real mode crashed in SAM 2 → updated for transformers 5; fake 0.88 scores and the refinement crash fixed too.], [high], [PR \#14],
  [\#6], [Empty prompt produced weeds → refused, red error.], [high], [PR \#15],
  [\#8], [Status claimed a prescription with 0 zones → "No weed zones approved".], [medium], [PR \#15],
  [\#11], [Cotton herbicide for wheat, rice, sugar beet → only evidence for the declared crop.], [high], [PR \#15],
  [\#9], [Slider ignored by the GeoJSON → gate uses real confidence; slider raises it.], [high], [PR \#15, \#16],
  [\#7], [Herbicide in GeoJSON with System 2 off → only with a real prescription.], [high], [PR \#16],
  [\#10], [Mock diagnosis shown as "VERIFIED & APPROVED" → REAL/MOCK banner; mock never shown as approved.], [high], [PR \#16],
  [\#12], [Blank image got a spray map → mock output labelled MOCK; in real mode the blank image gets 0 sprayed zones.], [medium], [PR \#16],
  [-], [GeoJSON had 1,394 features for 3 weeds and fake GPS → one feature per zone, specks dropped, coordinates labelled as placeholders.], [medium], [PR \#16],
)
