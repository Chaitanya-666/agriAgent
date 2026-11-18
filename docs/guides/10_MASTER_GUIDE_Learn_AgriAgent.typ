// THE master learning guide: AgriAgent from zero, for someone who knows nothing about the project.
//   cd docs/guides && typst compile --root .. 10_MASTER_GUIDE_Learn_AgriAgent.typ 10_MASTER_GUIDE_Learn_AgriAgent.pdf
// Replaces 09_Understand_AgriAgent (folded in here). Presentation-only material stays in 07/08.
#import "../template.typ": *
#show: doc.with(
  title: "MASTER GUIDE: Learn AgriAgent from Zero",
  subtitle: "Every part of the project, explained simply: the idea, our real evidence, the code, and the questions you will be asked",
  date: "18 November 2026",
)
#set heading(numbering: "1.")

#let line1(body) = block(width: 100%, fill: rgb("#e3efe5"), inset: 8pt, radius: 3pt, below: 8pt)[#text(weight: "bold", fill: accent)[In one line:] #body]
#let ev(body) = block(width: 100%, fill: luma(246), stroke: (left: 3pt + luma(150)), inset: 8pt, radius: (right: 3pt), below: 8pt)[*Where you can see it.* #body]
#let ask(..pairs) = block(breakable: false, width: 100%, fill: rgb("#fdf6ec"), stroke: (left: 3pt + rgb("#c27c0e")), inset: 8pt, radius: (right: 3pt), below: 8pt)[
  *If the examiner asks*
  #for (q, a) in pairs.pos().chunks(2) [ \ #text(fill: rgb("#8a5a00"))[*Q:* #q] \ *A:* #a ]
]
#let pic(path, cap, w: 100%) = figure(image(path, width: w), caption: text(9pt)[#cap])
#show raw.where(block: true): set text(8.3pt)

// ───────────────────────── COVER PAGE ─────────────────────────
#note(title: "What this is")[
The *one* guide for learning AgriAgent from nothing. It assumes no knowledge of the project, the code, or machine
learning. Every section opens with *"In one line"*: read only those boxes and you already have the whole story.
]

#table(
  columns: (auto, 1fr),
  [*This file*], [`docs/guides/10_MASTER_GUIDE_Learn_AgriAgent.pdf` in the repository; copy in `labworksdepot/FYP_AgriAgent/`],
  [*Report (black book)*], [`docs/report_latex/main.pdf`, 52 pages. "Book p. N" below = its printed page N.],
  [*Slides*], [`docs/slides/AgriAgent_FYP_Presentation.pptx`, 30 slides with speaker notes],
  [*To present*], [`docs/guides/07_Presentation_Kit_*.pdf` (what to say per slide) and `08_Slide_Distribution.pdf` (who presents what)],
  [*Online*], [github.com/Chaitanya-666/agriAgent, branch `chaitanya/blackbook-latex`],
)

#heading(level: 2, numbering: none)[How to read it]
#table(
  columns: (auto, 1fr, auto),
  [*Time you have*], [*Read*], [*Sections*],
  [15 minutes], [Only the green "In one line" boxes, all of them], [1–24],
  [2 hours], [Parts A and B fully: the basics and how the system decides], [1–10],
  [Half a day], [Everything, then the self-check at the end without looking], [1–24],
)

#table(
  columns: (auto, 1fr),
  [*Part A · The basics*], [1 The farming problem · 2 How a computer sees a photo · 3 What a "model" is · 4 Our two models],
  [*Part B · How AgriAgent decides*], [5 The big picture · 6 One photo, step by step · 7 Why text labels fail · 8 The plant rules · 9 The safety gate · 10 Where it goes wrong (F1)],
  [*Part C · Proving it works*], [11 The data · 12 How we measure · 13 The results · 14 The AI second-opinion agent · 15 Herbicide advice (ICAR)],
  [*Part D · The software*], [16 Tools and technologies · 17 Map of the project folders · 18 One photo through the code · 19 Run it yourself · 20 Testing],
  [*Part E · Defending it*], [21 Using AI, honestly · 22 Our research questions and answers · 23 Glossary · 24 Check yourself],
)

// ═════════════════════════ PART A ═════════════════════════
#pagebreak()
#align(center, text(15pt, weight: "bold", fill: accent)[PART A · THE BASICS])

= The farming problem
#line1[Farmers spray weed-killer on the whole field; we want a camera to tell *weeds* from *crop* so only weeds are sprayed, and *spraying the crop is the worst mistake*.]

*Weeds* are plants nobody planted. They steal light, water and nutrients from the crop, so farmers kill them with
*herbicide* (weed-killer). Usually it is sprayed over the *whole field*, although weeds grow only in patches. That
wastes money and puts chemicals into soil and water.

A *spot sprayer* is smarter: a camera looks at the ground, and a nozzle opens *only above a weed*. Nozzles are cheap
and already solved. The hard part is the *decision*: looking at a photo and saying, for every plant, "weed" or "crop".

There are two possible mistakes, and they are *not equal*:
- *Miss a weed*: it survives until the next pass. Annoying, not a disaster.
- *Call a crop plant a weed*: the crop is sprayed with weed-killer. That damages what the farmer is growing.

So our *first* number is *crop sprayed* (want near 0%) and our *second* is *weed recall* (share of weeds hit, want high).
#ev[Slide 2; book §1.1, p. 1.]

= How a computer sees a photo
#line1[A photo is a grid of coloured dots; a computer can draw *boxes* around things or colour their exact pixels (*masks*); a sprayer needs masks.]

- *Pixel*: one dot of the photo. Each has three numbers: red (R), green (G), blue (B), from 0 to 255. Our sugar beet photos are 512 × 512 pixels.
- *Box*: a rectangle around an object, with a *label* ("weed") and a *confidence* (0 to 1: how sure the computer is).
- *Mask*: the exact pixels of one object. A box also covers soil and neighbouring plants, so for spraying we need masks.

#pic("../slides/fyp_assets/walkthrough.png", [Our real run on one photo (slide 17). Panel 2 shows a *box*; panel 4 shows every plant coloured by its verdict (red weed, green crop).])

= What a "model" is
#line1[A model is a program that *learned* from examples instead of being written by hand; *zero-shot* means using someone else's trained model on our photos *without any training*.]

A *neural network* is a large function with millions of adjustable numbers. *Training* means showing it many examples
(photos with the right answers drawn by people) and adjusting the numbers until its answers match. The trained result
is a *model*.

- *Supervised* (the usual way): train on *thousands of hand-labelled photos* of *your* crop in *your* field. Accurate, but labelling is slow and costly, and a model trained on one field often fails on another.
- *Zero-shot* (our way): take a model that big labs already trained on *huge general data* (millions of everyday photos and captions), and use it directly on our photos. *We trained nothing.*

The research question of the whole project: *can zero-shot models do the weed-vs-crop decision without any labels?*

#ask(
  [Why not train your own model?], [Because that is exactly what we are testing: whether labelling can be avoided. Trained models on the same cotton data reach about 80% (Rahman 2023): that is the ceiling we compare with.],
)

= Our two models: Grounding DINO and SAM 2
#line1[*Grounding DINO* draws boxes around things you name in words; *SAM 2* outlines the exact shape inside each box; together they are *Grounded SAM*, our base pipeline.]

- *Grounding DINO* (by IDEA-Research) is a detector you *talk to*. You give it the photo and a text *prompt*. Ours is `weed . sugar beet plant .` (phrases separated by dots). It returns boxes, each with the matching phrase as its label and a confidence. "Grounding" = linking each word to a region of the image.
- *SAM 2* ("Segment Anything Model 2", by Meta) takes a box and returns the *mask* of the object inside, plus its own *quality score* (how well it thinks the mask fits). SAM 2 knows *shapes*, not *names*: it never says what the object is.
- *Grounded SAM* (Ren et al. 2024) = text → boxes (DINO) → masks (SAM). This is our *base paper*.

We use the *tiny* versions: both fit in about 2.4 GB of our 8 GB laptop graphics card (GPU) and take about 0.6 s per photo.
#ev[Slides 3, 10, 16; book §4.2, p. 12. Code: `src/vision/grounding_dino.py`, `src/vision/sam2_wrapper.py`.]

// ═════════════════════════ PART B ═════════════════════════
#pagebreak()
#align(center, text(15pt, weight: "bold", fill: accent)[PART B · HOW AGRIAGENT DECIDES])

= The big picture
#line1[*System 1* (on the laptop) finds plants and decides what to spray with plain rules; *System 2* (cloud AI) only *advises*; the yellow *safety gate* is the only thing allowed to approve spraying.]

#pic("../slides/fyp_assets/arch.png", [The pipeline (slide 11; book Fig. 4.1). Green: local; yellow: the safety gate; blue: cloud models that only advise.], w: 78%)

Why two systems? System 1 is fast, runs offline and gives the *same answer every time* for the same photo, so it can be
tested. System 2 uses big cloud AI models that can be wrong, so they may *explain and suggest*, never spray.

= One photo, step by step
#line1[Photo + crop name → boxes → masks → every green patch gets a verdict → the gate keeps only the weeds → spray map.]

Follow the five panels of the walkthrough figure (section 2, slide 17), a real development photo:
+ *Photo + crop name.* The user says the crop is "sugar beet"; the prompt becomes `weed . sugar beet plant .`.
+ *Detect.* Grounding DINO draws *one box over the whole photo*, labelled "sugar beet plant" (0.58). Useless: the whole photo is not one plant.
+ *Segment.* SAM 2 turns that box into one mask covering everything.
+ *Plant rules.* Our own code finds *every green patch* and gives each a verdict: beets on the planting row → *crop* (green); small patches off the row → *weed* (red).
+ *Safety gate.* Only the weed patches, minus every crop pixel, go on the spray map: 1.8% of the photo.

Checked against the dataset's official labels: *31 of 36 weeds hit, 0 of 3 beets touched*, 98% herbicide saved.

= Why the text labels fail (research question 1)
#line1[Grounding DINO's *masks* cover the weeds fine, but its *labels* ("weed" or "crop") are wrong, so trusting them either sprays the crop or sprays nothing.]

The test (slide 21; book Table 5.3, p. 23), 30 photos:
#table(columns: (1fr, auto, auto),
  [What we spray], [Crop sprayed], [Weed recall],
  [*Every* SAM 2 mask], [93.9%], [*97.6%*],
  [Only masks *labelled "weed"*, confidence ≥ 0.35], [70.8%], [9.0%],
  [Same, confidence ≥ 0.70 (our safe setting)], [0.0%], [0.0%])

Read it like a detective:
- Spraying *every* mask hits 97.6% of the weeds → the masks *do* cover the weeds. *Finding plants works.*
- Trusting the *labels* drops recall to 9% and sprays 70.8% of the crop → beets are often called "weed", tiny weeds are never boxed. *Naming plants fails.*
- The detector was never more than *0.68* sure, so our safe threshold 0.70 sprays nothing at all.

*Why?* "Weed" is not something you can *see* like "dog" or "car". It means *a plant in the wrong place*. A young sugar
beet and a young weed are both small green leafy plants. The model learned from everyday photos and has no idea which
one the farmer planted. The closest research paper (Chong et al., IROS 2025) argued exactly this; *we measured it*.
#ask(
  [So is SAM 2 bad?], [No, its masks are fine (97.6%). The problem is deciding *which* masks are weeds.],
  [Why 0.70?], [A safe default chosen before measuring. That no detection reached it *is* the finding.],
)

= The plant rules: deciding without labels
#line1[We find every green patch by colour, then decide with four plain rules: *in a crop mask → crop; on the row → crop; much smaller than the crop → weed; off the row when no crop was found → weed;* anything else is *unsure* and never sprayed.]

*Step 1: find the green.* For each pixel compute *excess green*, ExG = 2G − R − B. A leaf pixel (R 60, G 140, B 50)
gives 2×140 − 60 − 50 = *170*; a soil pixel (R 150, G 130, B 100) gives 260 − 250 = *10*. Plants score high, soil low.
The cut-off between "plant" and "soil" is chosen *per photo* by *Otsu's method*: try every cut-off and keep the one
that best splits the pixels into two groups. Code (`src/evaluation/crop_protection.py`):
```python
excess_green = 2 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]
return excess_green > otsu_threshold(excess_green)
```
*Step 2: patches.* Join leaves that belong to one plant (small gaps closed), then every connected green blob of at
least 12 pixels is a *patch*.

*Step 3: rows.* Crops are sown in straight rows; weeds are not. Add up the green pixels along each line of the photo:
if one band stands out (its peak is at least 2× the average, "peakiness ≥ 2"), the photo has clear rows, and a patch on
that band is *on the row*.

*Step 4: the verdict*, checked in this order (`src/vision/plant_candidates.py`, `classify_plants`):
#table(columns: (auto, auto, 1fr),
  [*Rule*], [*Verdict*], [*When*],
  [1], [crop], [at least 30% of the patch is inside a mask the detector labelled as the crop],
  [2], [crop], [the photo has clear rows and the patch is on the row],
  [3], [weed], [the detector found crop plants, and this patch is smaller than ¼ of the typical (median) crop plant in *the same photo*; otherwise unsure],
  [4], [weed], [no crop plants were found, the photo has rows, and the patch is off the row],
  [–], [unsure], [anything else: *never sprayed*])
Masks covering the whole photo are thrown away before rule 1; otherwise one giant "crop" box would make everything crop.

*Why it works on sugar beet:* the weeds there are tiny (median 16 px across) and the beets large (68 px), book p. 27.
*Why it fails on cotton (10.4%):* one big weed fills the close-up photo, so "weeds are smaller" is false.
The rules were written on 30 photos, *frozen*, then tested once on 90 new photos (book §4.4, p. 14).
#ask(
  [Why Otsu and not a fixed number?], [Light and soil change between photos; Otsu finds the best cut-off for each photo automatically.],
  [What if a field has no rows?], [Rules 2 and 4 switch off; rule 3 still works if crop plants were found; otherwise everything is unsure, so nothing is sprayed. Safe by default.],
)

= The safety gate
#line1[A short list of plain rules that *all* must pass before anything is sprayed; any doubt or error means *do not spray*.]

For each detector mask (`spray_map_node` in `src/workflow.py`):
+ *Label check*: the label must contain a weed word and *no* crop word ("weed sugar beet plant" mixes both → refused).
+ *One plant*: a mask covering more than half the photo is the whole scene, not a plant → refused.
+ *Confidence* ≥ 0.70 and *mask quality* ≥ 0.85.
+ *Plant-rule weeds* are added after removing every crop pixel.
+ *Infestation ceiling*: if more than 85% of the photo would be sprayed, nothing is (spot spraying makes no sense there).
+ *Fail safe*: any error, missing input or missing evidence → withhold.

*Why plain code, not AI?* Spraying the crop is the expensive mistake, so the decision must be testable (every rule has
unit tests), explainable (each refused mask gets a written reason) and repeatable.
*A story to tell:* an early version passed confidence and quality as *1.0*, so every "weed" label was sprayed. We found it
in code review and fixed it before measuring anything. Book §4.3, p. 13.

= Where it goes wrong (finding F1)
#line1[If the detector finds *no* crop, rule 4 calls every off-row plant a weed, even a whole beet.]
#pic("../report_latex/figures/verify_rotation_X-10-0.jpg", [Book Fig. 5.3: photo X-10-0 rotated 90°. No crop box, so the largest beet is sprayed.], w: 70%)
A size limit fixes it but loses most of the recall (book Table 5.9): limit 0.25 × median → 0.25% crop but 12.9% recall;
no limit → 4.55% crop, 71.5% recall. We kept the rules frozen because the held-out photos were already used; a "safe
mode" needs new test data (future scope). Typing the wrong crop name (F18) triggers the same failure; the app warns.

// ═════════════════════════ PART C ═════════════════════════
#pagebreak()
#align(center, text(15pt, weight: "bold", fill: accent)[PART C · PROVING IT WORKS])

= The data
#line1[Public photos whose labels were drawn by the dataset authors; 30 to design with, 90 locked away and used *once*.]

#table(columns: (auto, 1fr, auto),
  [*Dataset*], [*What*], [*Our use*],
  [sugarbeetsAndweeds (Kaggle)], [120 photos, 512 × 512, boxes for "sugar beet" and "weed"], [30 design + 90 held out],
  [CottonWeedDet3 (Kaggle)], [848 cotton photos, 3 weed types boxed; cotton itself not labelled], [8 design photos],
  [ICAR–DWR bulletin No. 22], [Approved herbicides per crop, dose, waiting period, banned list], [herbicide advice],
  [PhenoBench], [Drone photos with pixel labels], [future work])
*A lesson in honesty:* the first test set turned out to be *fabricated*: every beet photo had the same 2 crop + 6 weed
boxes. We threw it away and copied every label from the official files by script (`scripts/build_eval_manifest_v2.py`).
#pic("../report_latex/figures/audit_beet_X-10-0.jpg", [Book Fig. 5.1: old invented labels (left) vs official labels (right).], w: 62%)

= How we measure
#line1[Three percentages over pixels: *crop sprayed* (lower is better), *weed recall* (higher is better), *herbicide saved*.]

Toy example (it is one of our automated tests, book p. 22): a tiny 5 × 5 photo has 6 crop pixels and 4 weed pixels. The
spray map covers 5 pixels: 2 crop + 3 weed.
- *Crop sprayed* = crop pixels sprayed ÷ all crop pixels = 2/6 = *33.3%*
- *Weed recall* = weed pixels sprayed ÷ all weed pixels = 3/4 = *75%*
- *Herbicide saved* = 1 − sprayed ÷ whole photo = 1 − 5/25 = *80%*
Over many photos the pixels are added up first and divided at the end ("pooled"). Per plant: a weed is *hit* when at
least half its pixels are sprayed; a beet is *touched* when any pixel is. Code: `spray_metrics` in
`src/evaluation/crop_protection.py`.

*Why hold photos out?* If you design rules while looking at the test photos, the score fools you. The 90 held-out
photos were run *once*, on 18 October, after the rules were frozen; a repeat run on 23 October gave identical numbers.

= The results
#line1[On 90 unseen photos, AgriAgent hits *77.9%* of weeds while spraying *8.8%* of crop; Grounded SAM alone: 1.8% and 65.5%.]

#pic("../report_latex/figures/tradeoff_holdout.png", [Book Fig. 5.2 (slide 22): best is top-left. Every Grounded SAM setting sits near zero recall; the plant rules jump up.], w: 70%)
- *95%* herbicide saved compared with spraying everything; *0.6 s* per photo; no training.
- Design photos 71.5% / 4.6%: held-out is *not worse*, so the rules were not tuned to the design photos.
- *Is 90 photos enough?* We trained nothing, so all 120 are test photos. The 95% confidence intervals for weeds hit, *76.7–86.8%* vs *0.5–4.0%*, do not overlap: the gain is not luck.
- *Careful:* that interval counts *whole weeds hit* (177 of 215 = 82.3%), not pixels, so 77.9% need not lie inside it.
- *The cost:* 104 of 363 beets got at least one sprayed pixel, mostly tiny edge specks, a few whole beets (F1). Cotton: only 10.4%.

= The AI second-opinion agent (research question 2)
#line1[For plants the gate held back, an agent asks up to three "experts" (row rule, Clef Flash, Qwen VLM) and combines their answers; it was *safe* (never approved a crop) but found *no extra weeds*.]

A *VLM* (vision-language model) is a chatbot that can look at images. The agent asks the cheapest expert first and stops
when it is sure. Each answer is trusted only as much as that expert's *measured accuracy* on 20 labelled plant crops:
Qwen 16/20 = *0.80*, Clef 14/20 = *0.70*, row rule 13/20 = *0.65*. The answers are combined by multiplying their odds
(*naive Bayes*): `odds *= p / (1 - p)`, then P(weed) = odds / (1 + odds). It says "weed" only if P ≥ *0.85*.

Worked example (slide 19): Clef and Qwen both say weed → (0.7/0.3) × (0.8/0.2) = 9.33 → P = 0.90 ≥ 0.85 → weed. One
expert alone reaches at most 0.80, so *no single model can ever decide alone*.

Result (book p. 27): 69 plants reviewed, *0 crops approved*, 13 of 14 "crop" answers right, but *0 of 25 weeds* called
weed (two experts rarely agreed on "weed"; 14 of 69 Groq calls also hit the free-tier rate limit). The same Qwen model
scored 16/20 on Groq but 12/20 on Cloudflare: trust belongs to the provider it was measured on. Code:
`src/agents/escalation_agent.py`.

= Herbicide advice from the ICAR bulletin
#line1[The AI names the weed, but the *herbicide and dose come only from the official ICAR bulletin*, never from the AI.]

The bulletin (ICAR–Directorate of Weed Research, *Herbicide Use in Indian Agriculture*, 2016) lists approved
herbicides per crop. Doses are capped at the bulletin's maximum; banned herbicides are rejected; no matching row →
"no evidence". We checked every row against the PDF and found a *dangerous rice dose* (20 g, 75 days instead of 15 g,
95 days) and fixed it (book §5.10, p. 28). The farmer summary comes in English, Hindi and Marathi; its safety sentences
are fixed text, never written by the AI. Code: `src/agronomy/`.

// ═════════════════════════ PART D ═════════════════════════
#pagebreak()
#align(center, text(15pt, weight: "bold", fill: accent)[PART D · THE SOFTWARE])

= Tools and technologies
#line1[Python with PyTorch on a laptop GPU for the models, Hugging Face to load them, Cloudflare for the cloud AI, Streamlit for the app.]
#table(columns: (auto, 1fr),
  [*Tool*], [*What it is and what we use it for*],
  [Python 3.11+], [The programming language of the whole project.],
  [PyTorch 2.11 + CUDA 12.8], [Runs neural networks; CUDA lets it use the NVIDIA graphics card (RTX 5050, 8 GB).],
  [Hugging Face Transformers], [Library that downloads and runs Grounding DINO-tiny and SAM 2-tiny.],
  [NumPy], [Fast maths on pixel arrays: ExG, masks, metrics.],
  [Cloudflare Workers AI], [Cloud service (free tier) running Qwen 3.8 and Clef Flash for System 2. Groq is the alternative.],
  [Streamlit], [Turns a Python script into a web app: our user interface.],
  [GeoJSON], [Standard map file; the spray zones are exported in it (coordinates are placeholders, not GPS).],
  [Typst / LaTeX], [Typst for guides; LaTeX (Tectonic) for the black book, as the department requires.],
  [Git + GitHub Actions], [Version history; every push runs the tests automatically (CI).])

= Map of the project folders
#line1[`app/` is the screen, `src/` is the brain, `scripts/` run experiments, `tests/` check everything, `docs/` hold the report, slides and guides.]
#table(columns: (auto, 1fr),
  [*Folder*], [*What is inside*],
  [`app/`], [`app.py` (the Streamlit app), `components/ui.py` (screens such as the every-plant view)],
  [`src/workflow.py`], [The pipeline in order: detect → segment → refine → spray map (the gate) → System 2],
  [`src/vision/`], [`grounding_dino.py`, `sam2_wrapper.py`, `plant_candidates.py` (plant rules), `model_cache.py` (load models once)],
  [`src/agents/`], [`deterministic_router.py` (gate thresholds), `escalation_agent.py` (the agent), `evidence.py` (its experts)],
  [`src/agronomy/`], [System 2: diagnosis, ICAR knowledge store, prescriptions, farmer summary],
  [`src/evaluation/`], [`crop_protection.py` (ExG, Otsu, metrics), `iou_dice.py`, benchmark runners],
  [`scripts/`], [`run_baseline.py` (the measurements), `run_live_pipeline.py` (one photo), `build_eval_manifest_v2.py`, `make_walkthrough_figure.py`],
  [`data/manifests/`], [The test sets: `eval_manifest_v2.json` (30 + 8 design), `eval_manifest_v2_holdout.json` (90)],
  [`docs/results/`], [Every result file named in the report],
  [`tests/`], [Unit tests and `e2e/` end-to-end tests],
  [`config/`], [`thresholds.yaml`, `prompts.yaml`])

= One photo through the code
#line1[`VisionWorkflowRunner.run` calls detect → segment → spray map; the spray map node is where the gate and the plant rules live.]
#table(columns: (auto, 1fr),
  [*Step*], [*Function (file)*],
  [Start], [`VisionWorkflowRunner.run` (`src/workflow.py`), called by the app or `scripts/run_live_pipeline.py`],
  [Detect], [`GroundingDINOEngine.detect` (`src/vision/grounding_dino.py`)],
  [Segment], [`SAM2Segmenter.segment_boxes`; if quality < 0.85, `refine_with_point` (`src/vision/sam2_wrapper.py`)],
  [Gate], [`spray_map_node` + `label_policy` (`src/workflow.py`); thresholds in `DeterministicRouter`],
  [Plant rules], [`classify_plants`, `row_profile` (`src/vision/plant_candidates.py`); `vegetation_mask` (`src/evaluation/crop_protection.py`)],
  [Agent], [`EscalationAgent.review`, `p_weed` (`src/agents/escalation_agent.py`)],
  [Advice], [`system2_node.py`, `knowledge_store.py`, `farmer_summary.py` (`src/agronomy/`)],
  [Measure], [`spray_metrics` (`src/evaluation/crop_protection.py`)])

= Run it yourself
#line1[Activate the environment, start the app, untick Mock Mode, upload a beet photo, and look at the REAL banner and the every-plant view.]
```bash
source ~/.venvs/agriagent/bin/activate.fish       # fish shell; the project's Python environment
cd /mnt/Windows_D/College-work/finalYearProjectAgriAgent
streamlit run app/app.py                            # opens the app in the browser
```
In the app: untick *"Mock Mode (Fast Laptop Demo)"*, choose crop *sugar beet*, upload
`data/outputs/test_photos/beet_X3-130-0.png`, check the *REAL* banner, the spray map and numbers, tick *"Show every
plant and what the system decided"*, switch the summary to Hindi, download the GeoJSON.
One photo from the terminal: `python scripts/run_live_pipeline.py --image <photo> --crop "sugar beet"`.

= Testing
#line1[270 automated tests run on every change, plus three rounds of manual testing; the final system test passed 24 of 24.]
- *Unit tests* (235) check one piece each: every gate rule, plant rule, metric (incl. the 5 × 5 toy example), ICAR row, GeoJSON field.
- *End-to-end tests* (35) run the whole pipeline in mock mode.
- Run them: `PYTHONPATH=. python3 -m unittest discover -s tests`.
- *Manual cycles:* cycle 0 (16 Oct, 7 pass / 9 fail → 8 issues fixed), verification (23 Oct), manual cycle (30 Oct), Amit's cycle 2 (24 of 24 on Windows 11, RTX 3050). 30 findings F1–F30 traced (book §5.12, pp. 29–30).

// ═════════════════════════ PART E ═════════════════════════
#pagebreak()
#align(center, text(15pt, weight: "bold", fill: accent)[PART E · DEFENDING IT])

= Using AI, honestly
#line1[Yes, we used AI tools for code and drafts; our work was the decisions, the honest measurement, and catching where the AI was wrong.]
Book §6.3 (p. 31) lists what went wrong and how we fixed it:
+ AI-written status claims ("100% complete", "227 tests" when there were 175) → every claim now carries REAL / PARTIAL / MOCK / PLANNED.
+ Fabricated test labels → rebuilt from the official files by script.
+ References to papers that do not exist → every reference now comes from its official Crossref record.
+ Silent fake output when a model failed to load → real mode now fails loudly.
+ The gate receiving 1.0 instead of real scores → each rule tested with real values.
+ Promises never measured ("over 70% saving", "under 40 ms") → only measured numbers in the report.
Plus the wrong rice dose (section 15).

= Our research questions and answers
#table(columns: (auto, 1fr, 1fr),
  [*RQ*], [*Question*], [*Answer*],
  [RQ1], [How well does Grounded SAM separate weed from crop?], [Badly: held-out 65.5% crop sprayed for 1.8% recall; at the safe 0.70 it sprays nothing.],
  [RQ2], [Does asking AI models about unsure plants help, without making it less safe?], [Safe (no crop approved, 13/14 right) but no help (0/25 weeds).],
  [RQ3], [Which cheap addition cuts crop damage most?], [Plain plant rules + gate: 77.9% recall at 8.8% crop, 95% saved, 0.6 s, no training.])
*Base paper:* Grounded SAM (Ren et al. 2024), implemented with SAM 2. *Closest research:* Chong et al., IROS 2025
(12.1% vs 62.7% weed IoU). We do not claim to beat it: different measure and data; a direct comparison on PhenoBench is future work.

= Glossary
#table(columns: (auto, 1fr),
  [*Term*], [*Meaning*],
  [Herbicide], [Weed-killing chemical.],
  [Spot spraying], [Spraying only where a weed is.],
  [Zero-shot], [Using a pretrained model with no training on our data.],
  [Prompt], [The text given to Grounding DINO: `weed . sugar beet plant .`],
  [Confidence], [The model's own score (0–1) for a box.],
  [Mask quality (predicted IoU)], [SAM 2's own estimate of how well its mask fits.],
  [ExG], [Excess green, 2G − R − B: high for plants, low for soil.],
  [Otsu threshold], [Automatic cut-off that best splits plant from soil in each photo.],
  [Patch], [One connected blob of green pixels: usually one plant.],
  [Held-out set], [Test photos locked away and used once.],
  [Recall], [Share of the weeds that were hit.],
  [IoU], [Overlap ÷ union of two regions: another way to score masks.],
  [Confidence interval], [The range where the true value most likely lies (95%).],
  [VLM], [Vision-language model: a chatbot that can look at images.],
  [Naive Bayes], [Combining independent pieces of evidence by multiplying their odds.],
  [Deterministic], [Same input always gives the same output.],
  [Mock mode], [Fake detections for tests and quick demos; always labelled MOCK.],
  [GeoJSON], [Map file format; our coordinates are placeholders, not GPS.])

= Check yourself
#set text(9.5pt)
Cover the right column and answer aloud.
#table(columns: (1fr, 1fr),
  [*Question*], [*Answer*],
  [1. Which mistake matters most?], [Spraying the crop.],
  [2. Box vs mask?], [Rectangle vs exact pixels; sprayers need masks.],
  [3. What does zero-shot mean?], [Pretrained by others, no training on our photos.],
  [4. What does each model give?], [DINO: boxes + label + confidence. SAM 2: masks + quality.],
  [5. Every-mask recall, and what it proves?], [97.6%: finding plants works, naming them fails.],
  [6. Highest detector confidence?], [0.68, so the 0.70 gate sprays nothing.],
  [7. ExG of a leaf (60, 140, 50)?], [170.],
  [8. The four plant rules?], [In crop mask; on row; smaller than ¼ median crop; off row with no crop found. Else unsure.],
  [9. Gate rules?], [Weed-only label; ≤ 50% of photo; ≥ 0.70; ≥ 0.85; rule weeds minus crop; ≤ 85% total; fail safe.],
  [10. What is F1?], [No crop found → rule 4 sprays an off-row beet whatever its size.],
  [11. Headline?], [77.9% recall, 8.8% crop, 95% saved; Grounded SAM 1.8% / 65.5%.],
  [12. Toy example?], [33.3% / 75% / 80%.],
  [13. Why can no single AI expert decide?], [Its trust is at most 0.80, below 0.85.],
  [14. Where do doses come from?], [Only the ICAR bulletin.],
  [15. Why was the held-out set used once?], [To keep the score honest; changes need new data.],
)
