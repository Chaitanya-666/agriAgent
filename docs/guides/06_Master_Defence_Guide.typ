#import "../template.typ": *
#show: doc.with(
  title: "AgriAgent Master Guide",
  subtitle: "Part 1: AgriAgent 101 for everyone. Part 2: what each member presents and defends",
  date: "16 November 2026",
)

#let fig(path, cap, w: 100%) = figure(image(path, width: w), caption: cap)

#note(title: "How to use this guide")[
*Everyone reads all of Part 1* (about two hours, slowly, twice). It assumes you know *nothing* about the
project: no code, no machine learning. Then read *your own chapter in Part 2*, practise your slides aloud
with a timer, and answer the questions at the end of Part 1 and of your chapter without looking.
The report (`docs/report_latex/main.pdf`) and the slides (`docs/slides/AgriAgent_FYP_Presentation.pptx`)
contain everything here in more detail; every number below is in the report.
]

#v(4pt)
#align(center, text(16pt, weight: "bold", fill: accent)[PART 1 · AGRIAGENT 101])

= The farming problem

*Weeds* are unwanted plants growing among the crop. They steal light, water and nutrients, so the farmer
kills them with *herbicide* (weed-killing chemical). Usually the herbicide is sprayed over the *whole field*
("blanket spraying"), although weeds grow only in patches. That wastes chemical and money and harms soil
and water.

*Spot spraying* is the smarter way: a camera looks at the ground, and a nozzle opens *only above a weed*.
The nozzle part is easy and cheap. The hard part is the *decision*: the computer must look at a photo and
say, for every plant, "this is a weed" or "this is the crop".

The two possible mistakes are not equal:
- *Missing a weed*: the weed survives until the next pass. Annoying, not a disaster.
- *Calling a crop plant a weed*: the crop is sprayed with weed-killer. That damages what the farmer is trying to grow.

So our most important number is *how much of the crop ends up on the spray map* (we want it near zero),
and the second is *how many weeds we hit* (we want it high).

= What a computer must do (computer vision in 10 minutes)

*An image is a grid of pixels.* Each pixel has three numbers: red (R), green (G), blue (B). Our sugar beet
photos are 512 × 512 pixels.

Computer vision gives three kinds of answers about an image:
#table(
  columns: (auto, 1fr),
  [Task], [What it outputs],
  [Classification], ["This picture contains a weed." One label for the whole image.],
  [Detection], [A *box* (rectangle) around each object, with a label and a confidence score (0 to 1).],
  [Segmentation], [A *mask*: the exact set of pixels belonging to the object. Needed for spraying, because a box also covers soil and neighbouring plants.],
)

*Training vs zero-shot.* The usual way: show a neural network thousands of *labelled* photos (someone drew
every weed by hand) until it learns. That is *supervised training*. It works well but (1) labelling is slow
and expensive, (2) a model trained on one field often fails on another field. *Zero-shot* means using a
model that was already trained by someone else on huge general data, and applying it to our task *without
any training on our photos*. AgriAgent is zero-shot: *we trained nothing*.

= The tools we use

#table(
  columns: (auto, 1fr),
  [Tool], [What it is, in one line],
  [Grounding DINO], [A detector you talk to: you type words ("weed . sugar beet plant .") and it draws boxes around things matching those words, each with a confidence. Made by IDEA-Research. We use the small "tiny" version.],
  [SAM 2], [Segment Anything Model 2, by Meta. Give it a box and it outlines the object inside precisely (a mask), and says how good it thinks its mask is (predicted quality). It does *not* know what the object is.],
  [Grounded SAM], [The combination: Grounding DINO's boxes are fed into SAM, so you get masks with word labels. *This is our base pipeline* (the "base paper").],
  [VLM (vision-language model)], [A model that looks at an image and answers questions in text, like a chatbot with eyes. We use Qwen 3.8 and Clef Flash, run in the cloud on Cloudflare (free tier).],
  [ICAR–DWR bulletin], [A government book from ICAR (Directorate of Weed Research, Jabalpur, 2016) listing which herbicide, how much, and how long to wait before harvest, for each crop and weed. Our only source of herbicide advice.],
  [Streamlit], [A Python library to make a web app quickly. Our user interface.],
  [GeoJSON], [A standard file format for maps. We export the spray zones in it.],
  [GPU], [Graphics card that runs neural networks fast. Our laptop: NVIDIA RTX 5050 with 8 GB memory.],
)

= The question we asked

If Grounded SAM can find "weeds" just from a text prompt, nobody needs to label thousands of photos. *Does
that actually work for weed versus crop?* A 2025 paper (Chong et al., "Weeds are Weird", IROS 2025) argued
it does not, because a weed and a young crop plant are both "a small green plant". We *measured* it, and we
built a safety layer to see how much can be recovered. Three research questions:

#table(
  columns: (auto, 1fr),
  [RQ1], [How well does Grounded SAM alone separate weed from crop?],
  [RQ2], [When unsure plants are sent to vision-language models for a second opinion (the "escalation agent"), does the spray map get better without getting less safe?],
  [RQ3], [Which cheap addition (stricter threshold, removing crop areas, simple rules about rows and plant size) reduces crop damage most, and what does it cost in missed weeds?],
)

= One photo through the system

#fig("../slides/fyp_assets/arch.png", [The AgriAgent pipeline. Green: runs on our laptop and is deterministic or pretrained. Yellow: the safety gate. Blue: cloud models that only advise.], w: 62%)

Follow one sugar beet photo:

+ *Input.* The user uploads the photo and says the crop is "sugar beet". The system builds the prompt `weed . sugar beet plant .`
+ *Detect.* Grounding DINO draws boxes, each labelled "weed" or "sugar beet plant" with a confidence like 0.42.
+ *Segment.* SAM 2 turns each box into a mask. If SAM's own quality score is below 0.85, it is asked again with a hint point.
+ *Plant rules.* Separately, the system finds *every* green patch in the photo (Section 6) and labels each patch crop, weed or unsure using four simple rules.
+ *Safety gate.* The gate decides what may be sprayed (Section 6). It is plain code, not AI, and it is the *only* part allowed to approve spraying.
+ *Escalation agent (optional, off by default).* For plants the gate held back, it asks up to three sources for a second opinion. Its answer is advice only.
+ *System 2 and ICAR.* A cloud VLM names the weed (e.g. _Amaranthus_). The herbicide and dose come only from the ICAR bulletin row for that crop and weed.
+ *Output.* The app shows REAL (or MOCK), the photo beside the spray map, numbers (area sprayed, herbicide saved), a summary for the farmer in English, Hindi or Marathi, and a GeoJSON file to download.

#fig("../report_latex/figures/real_run_beet_after_gate_fix.jpg", [A real run with Grounded SAM alone: photo, detector boxes, SAM 2 masks, spray map. All confidences were 0.36–0.47, below the 0.70 gate, so *nothing* was sprayed. Safe, but every weed is missed. This is the problem the plant rules solve.])

#fig("../report_latex/figures/verdict_beet_X2-30-0.jpg", [The app's "every plant and its verdict" view: red = sprayed, green = protected as crop, yellow = left alone (unsure).], w: 80%)

= The two key ideas: the safety gate and the plant rules

== The safety gate (the referee)

Think of the gate as a strict referee. A detector mask is sprayed *only if all* of these hold:
- its label says *weed* and does *not* mention the crop (the detector sometimes outputs "weed sugar beet plant"; mixed labels are refused);
- the detector's confidence is at least *0.70*;
- SAM 2's mask quality is at least *0.85*;
- the mask covers *at most half* the photo (a mask over the whole photo is the field, not a plant).

Patches the plant rules call *weed* are also sprayed, after removing every crop pixel. "Unsure" is never
sprayed. If more than *85%* of the photo would be sprayed, the whole map is cancelled (spot spraying makes
no sense on a fully infested field). *Any error or missing information means "do not spray".*

*Why plain code and not AI?* Because spraying a crop is the expensive mistake. Plain rules can be tested,
explained and give the same answer every time. AI can advise; the gate decides.

== The plant rules (why they were needed)

Grounding DINO rarely draws boxes around small weeds; it mostly boxes the big crop plants. So the system
also looks at every green patch itself:

+ *Find green.* For each pixel compute *excess green* = 2G − R − B (plants are greener than soil). Pick the cut-off automatically per photo (Otsu's method). Join leaves of one plant; then each connected blob is a *patch*.
+ *Rule 1, crop:* at least 30% of the patch lies inside a mask the detector called the crop.
+ *Rule 2, crop:* the photo has clear planting rows and the patch lies on a row (crops are sown in rows, weeds are not).
+ *Rule 3, weed:* the detector found crop plants, and this patch is smaller than ¼ of the typical (median) crop plant in the same photo. (Otherwise unsure.)
+ *Rule 4, weed:* the detector found *no* crop at all, the photo has rows, and the patch is off the row.
+ *Otherwise unsure*, never sprayed.

No rule was learned from data; they were written, tried on 30 development photos, *frozen*, then tested once
on 90 photos never seen before.

= How we measured

== The data
#table(
  columns: (auto, 1fr, auto),
  [Dataset], [What], [Use],
  [sugarbeetsAndweeds (Kaggle)], [120 photos, 512 × 512, boxes for "sugar beet" and "weed" drawn by the dataset authors], [30 development + 90 held-out],
  [CottonWeedDet3 (Kaggle, Rahman et al. 2023)], [848 cotton-field photos, 3 weed types boxed; cotton itself is *not* labelled], [8 development photos],
)

*Development set* (30 photos): used while designing. *Held-out set* (90 photos): locked away and used *once*,
on 18 October, after the rules were frozen. This is how you get an honest score: the system never "saw" those
photos during design.

*Why 120 photos is enough:* we trained nothing, so these are *test* photos only, and 120 is the *whole* public
dataset. The held-out part has 363 crop plants and 215 weeds. The improvement is so large (weeds hit: 76.7–86.8%
vs 0.5–4.0%, 95% confidence intervals that do not overlap) that more photos would only make the numbers more
precise, not change the conclusion.

== The metrics, with a toy example

Imagine a tiny photo of 25 pixels: 6 are crop, 4 are weed, the rest soil. The spray map covers 5 pixels: 2 crop
and 3 weed.
- *Crop sprayed* = crop pixels sprayed ÷ all crop pixels = 2/6 = *33.3%* (damage, lower is better).
- *Weed recall* = weed pixels sprayed ÷ all weed pixels = 3/4 = *75%* (higher is better).
- *Herbicide saved* = 1 − sprayed ÷ whole photo = 1 − 5/25 = *80%* (vs spraying everything).

This exact example is one of the automated tests of our metric code. Over a set of photos, pixels are added up
first and then divided ("pooled").

= What we found

#table(
  columns: (1.6fr, 1fr, 1fr),
  [90 held-out sugar beet photos], [Crop sprayed], [Weed recall],
  [Grounded SAM, threshold 0.35], [65.5%], [1.8%],
  [Grounded SAM, threshold 0.70 (as deployed)], [0.0%], [0.0%],
  [*AgriAgent: plant rules + gate (the product)*], [*8.8%*], [*77.9%*],
)

#fig("../report_latex/figures/tradeoff_holdout.png", [Each dot is one setting. Best is top-left (many weeds hit, little crop sprayed). All Grounded SAM settings sit on the bottom edge; the plant rules jump to 77.9% recall at 8.8% crop sprayed.], w: 75%)

*Answers:*
- *RQ1:* Grounded SAM alone fails. With a low threshold it sprays two-thirds of the crop and almost no weeds; with the safe threshold it sprays nothing. Its *masks* are good (spraying every mask hits 97.6% of weeds); its *labels* are the problem.
- *RQ2:* The escalation agent reviewed 69 withheld plants: it never approved a crop plant and was right 13 of 14 times when it said "crop", but it called *none* of the 25 weeds a weed. Safe, not effective.
- *RQ3:* The plain rules plus the gate give the best trade-off: 77.9% weed recall, 8.8% crop sprayed, 95% herbicide saved, 0.6 seconds per photo, *no training*.

= What does not work (say it before you are asked)

- *Finding F1, the whole-beet problem.* Rule 4 says "off the row = weed" whatever the size, and it only applies when the detector found no crop. When we rotated a photo by 90°, the detector found no crop, and the biggest beet was sprayed completely. A size limit fixes this but loses most of the weed recall. We kept the frozen rules and report the trade-off.
- *Cotton.* Only 10.4% weed recall: in cotton close-ups one big weed fills the photo, so "weeds are smaller than the crop" is false.
- *The agent* adds no weeds (RQ2).
- *Prototype only:* no GPS, no real sprayer, no field trial.

= The honesty story (examiners like this)

Parts of the early project were written with AI help, and some of it was wrong. We found and fixed it:
- The first evaluation file had *invented labels*: the same eight boxes on every photo. An audit caught it; it was thrown away and rebuilt from the official files by a script.
- An early reference list had *papers that do not exist*. Every reference in the report now comes from its official DOI record.
- The gate once received confidence and quality *hard-coded as 1.0*, so it sprayed every "weed". Found in code review, fixed, now tested.
- A rice herbicide row had *20 g and 75 days* instead of the bulletin's 15 g and 95 days: an overdose. Found by checking every row against the PDF.

= Six papers everyone must know

#table(
  columns: (auto, 1fr),
  [Paper], [Why it matters to us],
  [Ren et al. 2024, Grounded SAM], [The pipeline we implement (base paper).],
  [Chong et al. 2025, IROS ("Weeds are Weird")], [Closest work: zero-shot crop–weed with SAM + BioCLIP; weed IoU 12.1% vs 62.7% supervised; says text prompts are ill-defined for crop/weed, which we measured.],
  [Milioto et al. 2018, ICRA], [Supervised sugar beet segmentation on a robot; the kind of trained system we avoid needing.],
  [Bah et al. 2018, Remote Sensing], [Used crop rows to label weeds automatically: the same idea as our rule 4.],
  [Rahman et al. 2023, Smart Agric. Technol.], [Source of our cotton photos; trained detectors reach about 80% mAP: the supervised ceiling.],
  [Nasir et al. 2026, Front. Plant Sci.], [Commercial VLMs detect weeds with 15–75% accuracy: useful as advice, not as decision-maker.],
)

= Questions every member must answer

*Q: Explain the project in one minute.* Use Sections 1 and 4 and the three numbers 65.5% / 77.9% / 8.8%.

*Q: Why not train a model?* That is the research question: can we avoid labelling? Training needs thousands of labelled photos per field and fails on new fields. Published trained models (about 80% on cotton) are our ceiling.

*Q: Only 120 images?* We trained on zero. They are the whole public dataset, used only to test; 90 held out and run once; the intervals do not overlap (Section 7).

*Q: What is the base paper? Did you implement it?* Grounded SAM, yes, with SAM 2. Peer-reviewed reference: Chong et al. IROS 2025.

*Q: Did you beat that paper?* We do not claim so: they measure pixel IoU on other data; we measure crop sprayed and weed recall. A direct comparison on PhenoBench is future work.

*Q: What is novel?* Measuring the zero-shot pipeline the way a sprayer needs (crop on the map, weeds hit, herbicide saved), a gate that alone decides spraying, and rules that recover most of the performance without training. Plus honest negative results.

*Q: Can a farmer use it?* Not yet: research prototype, no GPS or sprayer, sugar beet only.

*Q: Did you use AI tools?* Yes, for code and drafts. That is why every number comes from running the code, every reference was checked against its DOI, and the AI mistakes listed in Section 10 were found and removed.

*Q: What did you personally do?* Give *your real role* from Part 2. Never claim a part you did not build.

= Glossary

#table(
  columns: (auto, 1fr),
  [Term], [Meaning],
  [Herbicide], [Chemical that kills weeds.],
  [Spot spraying], [Spraying only where a weed is.],
  [Pixel / RGB], [One dot of the image; its red, green, blue values.],
  [Box / mask], [Rectangle around an object / exact pixels of an object.],
  [Confidence], [The model's own score (0–1) for a detection.],
  [Zero-shot], [Using a pretrained model with no training on our data.],
  [Supervised training], [Teaching a model with many hand-labelled examples.],
  [Excess green], [2G − R − B: high for plants, low for soil.],
  [Otsu threshold], [Automatic cut-off that best splits plant from soil per photo.],
  [Held-out set], [Test photos locked away until the end, used once.],
  [Weed recall / crop sprayed], [Share of weed / crop pixels on the spray map.],
  [IoU], [Overlap ÷ union of two regions; another way to score segmentation.],
  [Confidence interval], [Range where the true value most likely lies (95%).],
  [Deterministic], [Same input always gives the same output.],
  [Mock mode], [Fake model output for testing without the real models; screens say MOCK.],
  [GeoJSON], [Map file format; our coordinates are placeholders, not GPS.],
)

#pagebreak()
#align(center, text(16pt, weight: "bold", fill: accent)[PART 2 · EACH MEMBER'S PART])

= The 15-minute talk (same for all)

Each of us presents *alone for 15 minutes*, then 5–10 minutes of questions, using the same 30-slide deck.
Skip slides not in your list with one click. Speaker notes in PowerPoint (View → Notes) give extra hints.

#table(
  columns: (auto, 1fr, auto),
  [Block], [Slides], [Time],
  [Common opening], [1 Title · 2 Motivation · 3 Problem statement], [3 min],
  [Common context], [8 Gaps · 10 Objectives and research questions · 11 Architecture], [3 min],
  [*Your own part*], [Your slides (your chapter below)], [6 min],
  [Common close], [22 Headline result · 26 Conclusion], [2 min],
  [Spare], [Questions, demo overrun], [1 min],
)

*Script for the common slides* (say it in your own words):
- *Slide 2:* "Herbicide is sprayed on whole fields although weeds are patchy. Spot spraying opens a nozzle only over a weed. The nozzle is cheap; deciding weed vs crop is the hard part, and spraying a crop is the costly mistake."
- *Slide 3:* "Trained models need thousands of labelled photos per field. Foundation models like Grounding DINO and SAM 2 promise to do it from a text prompt with no training. Our problem: produce a spray map that hits weeds and spares the crop, with no training, on a laptop, with every decision explainable."
- *Slide 8:* "Five gaps: trained models need labels; nobody measured the text-prompt pipeline on this task; papers report IoU, not crop sprayed; there is no testable safety gate between model and nozzle; AI advice is not tied to Indian herbicide regulation."
- *Slide 10:* "Six objectives and three research questions" (read RQ1–RQ3 from Part 1, Section 4).
- *Slide 11:* "System 1 runs locally and decides; System 2 is cloud AI that only advises. The yellow box, the gate, is the only part allowed to approve spraying."
- *Slide 22:* "On 90 photos never seen during design: 77.9% of weeds hit, 8.8% of crop sprayed, against 1.8% and 65.5% for Grounded SAM alone. 95% herbicide saved, 0.6 s per photo, no training."
- *Slide 26:* "RQ1: text labels fail. RQ2: the agent is safe but finds no weeds. RQ3: simple rules plus the gate recover most of it. It is a research prototype, and every number is reproducible."

= Chaitanya Shinde · Track 1: vision pipeline, safety gate, method

*Real role.* Design and methodology; the whole pipeline (vision, plant rules, gate, agent, final System 2 and
ICAR store, app, GeoJSON); evaluation sets and metrics; all experiments; tests, verification and manual test
cycles; report and slides.

*Your slides:* 12 Safety gate · 13 Plant rules · 18–19 Mathematical model · 21 RQ1 baseline · 24 Limitation F1.

*What to say:*
- *Slide 12:* Walk the gate table top to bottom; stress "fail safe" and the 1.0 bug that taught us to test each rule with real values.
- *Slide 13:* Why the rules were needed (the detector misses small weeds); the five verdicts; frozen before the held-out run.
- *Slide 18:* ExG and Otsu → patches → row test (peakiness ≥ 2; on-row if the row profile at the patch centre is at least half its maximum) → the piecewise rule; point out that line 5 applies only when no crop mask exists (that is F1).
- *Slide 19:* Gate predicate; the infestation ceiling; the agent's odds with the worked example; the three metric formulas.
- *Slide 21:* Spraying every mask hits 97.6% of weeds: masks are fine, labels fail. Scores never above 0.68, so the 0.70 gate sprays nothing.
- *Slide 24:* Rotated photo; the size-limit table; why v3 stays frozen (no unused held-out data).

*Deep-dive questions:*
- *Why ¼ of the median crop?* Self-calibrating per photo; set by design, never tuned on held-out labels; weeds in this data are tiny (median 16 px across vs 68 px crops).
- *Why naive Bayes for the agent?* Simple, explainable, lets a source's measured accuracy (0.65 / 0.70 / 0.80) cap its influence; it assumes independent errors, which is optimistic, so the 0.85 bar is strict.
- *Complexity?* Vegetation, closing, components and rows are linear in the number of pixels; run time is dominated by the two networks (0.21 s detection, 0.27–0.37 s segmentation).
- *Why SAM 2-tiny and DINO-tiny?* They fit in 8 GB with headroom (peak about 2.4 GB) and run in about 0.6 s per photo.

= Amit Ingle · Track 4: application, testing, release, demo

*Real role.* First Streamlit dashboard; system test cycle 0 (16 cases on a fresh Windows install, 8 issues
filed); system test cycle 2 on the final build (24 of 24 cases passed on Windows 11 with an RTX 3050 4 GB);
the packaging bug report; the v1.0.0 release; the live demo.

*Your slides:* 16 Implementation · 17 Demo (live, about 3 minutes) · 25 Testing and release · 23 Agent results.

*What to say:*
- *Slide 16:* Python; Grounding DINO-tiny + SAM 2-tiny through Hugging Face Transformers; Qwen and Clef Flash on the Cloudflare free tier; Streamlit app; GeoJSON; 270 tests. "Every screen says REAL or MOCK; if a real model cannot load, it fails loudly instead of faking output."
- *Slide 17:* Run the demo (below).
- *Slide 25:* "I installed the project from scratch on Windows twice. Cycle 0: 16 app cases, 7 passed, 9 failed, I filed 8 issues; all were fixed and retested. Cycle 2 on the final build: 24 of 24 passed, including install, regression of the latest fixes, and exploratory cases like a photo with no plants, huge and tiny images, no network, and a screenshot of a text page." Then the release.
- *Slide 23:* The agent table: 0 crops approved, 0 of 25 weeds found; the same Qwen model scored 16/20 on Groq vs 12/20 on Cloudflare.

*Cycle 0 issues you found (know three):* the app crashed on start (wrong import path); GeoJSON had herbicide
fields with System 2 off; an empty prompt silently became a default that invented weeds; the confidence slider
was not applied; mock diagnoses were shown as "verified"; a cotton herbicide was recommended for other crops;
mock mode ignored the uploaded image.

*Interesting cycle 2 finding (F30):* on a screenshot of a text document, Grounding DINO saw a "sugar beet plant"
at 0.71 confidence. The gate sprayed nothing because the label names the crop. Lesson: labels are not evidence.

*Demo script:*
+ Before: laptop charged, venv active, models downloaded, internet on, `.env` has the Cloudflare keys, app already opened once.
+ `streamlit run app/app.py`, untick "Mock Mode", crop "sugar beet", upload `data/outputs/test_photos/beet_X3-130-0.png`.
+ Point at the REAL banner, the spray map and the KPI cards; tick "show every plant and its verdict"; switch the summary to Hindi; download the GeoJSON.
+ If anything fails: "I'll show the recording" and play the backup video (record it on 17 Nov).

*Your questions:* How do you install it? (clone, Python 3.11–3.13 venv, `pip install -r requirements-lock.txt`, download the models, add the keys, `streamlit run`.) What is mock mode for? (tests and demos without the 1.5 GB of models; never calls the cloud.) What was the release blocker? (the lock file pinned Linux-only packages, so the Windows install failed; fixed and checked for Windows on Python 3.11–3.13.)

= Sumant Vetal · Track 2: literature and agronomy advice

*Real role.* The first version of the System 2 agronomy module (diagnosis and herbicide advice), later
rewritten and integrated; the ICAR herbicide-row check (your task below).

*Your slides:* 4–7 Literature survey · 9 Base paper · 14 Escalation agent and ICAR advice.

*What to say:*
- *Slides 4–7:* Do not read every row. One sentence per slide, then one key paper:
  - *4 (zero-shot):* "Zero-shot models segment plants well; text labels are the weak point." Key paper: Chong et al. 2025, weed IoU 12.1% vs 62.7% trained.
  - *5 (supervised):* "Trained networks work but need labels from each field." Key paper: Weyler et al. 2023, models degrade on new fields.
  - *6 (detection):* "Vegetation indices separate plant from soil; deep models need per-crop labels." Key paper: Woebbecke 1995, the excess-green index we use.
  - *7 (rows, LLMs):* "Planting rows can replace labels; language models must stay grounded." Key papers: Bah 2018 (rows → weed labels), Li 2025 (LLMs need verified knowledge).
- *Slide 9:* Base pipeline Grounded SAM (arXiv), peer-reviewed reference Chong et al. IROS 2025; "we do not claim to beat their IoU: different metric and data."
- *Slide 14:* The agent in one breath (cheapest source first, needs two agreeing sources, advice only). Then ICAR: "The model only names the weed. The herbicide, dose, water and waiting period come only from the ICAR bulletin row for that crop and weed, clamped to its maximum; banned herbicides are rejected; no matching row means 'no evidence'."

*How ICAR advice works (know this well):* the bulletin (Choudhury et al., ICAR–DWR, 2016, Information Bulletin
No. 22) has tables per crop. Each row we use has: crop, weeds controlled, chemical (e.g. Pyrithiobac-sodium 10%
EC), dose in grams of active ingredient per hectare, water in litres per hectare, waiting period in days (time
between spraying and harvest), and the page. Example from a real test on cotton photo CM_17: the VLM named
_Amaranthus_, and the system matched the cotton row Pyrithiobac-sodium, 75 g a.i./ha, waiting period 160 days,
bulletin page 35. The farmer summary always ends with a fixed "this is a suggestion, read the label" sentence.

*Your task (by 17 Nov, about one hour): check five ICAR rows.*
+ Open `data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf` and the rows in `src/agronomy/knowledge_store.py` (or ask Chaitanya for a printout).
+ Each row has `chemical`, `dosage_ai_g_per_ha`, `water_l_per_ha`, `waiting_period_days` and `page`. The page is the *printed* page; in the PDF viewer go to *page + 8* (printed 35 = viewer 43).
+ Check: cotton Fluchloralin (p. 35), cotton Pyrithiobac-sodium (p. 35), the wheat rows on p. 25 and p. 27, rice Pyrazosulfuron-ethyl (p. 33).
+ Write crop, chemical, dose, water, waiting period, page, match or mismatch. Send it to Chaitanya; it will be added to your role in the report.

*Your questions:* What is a waiting period? (days between spraying and harvest, so residue is safe.) Why not let the AI give the dose? (it can state a wrong dose fluently; the bulletin is the official source.) What bug was found? (rice row 20 g / 75 days instead of 15 g / 95 days.) What is the closest work and its result? (WaW: 12.1% vs 62.7%.)

= Sahil Chavan · Track 3: data and evaluation

*Real role.* The dataset downloader used to fetch the public datasets; the dataset check (your task below).

*Your slides:* 15 Datasets · 20 Evaluation method · 21 RQ1 baseline · 27 Future scope.

*What to say:*
- *Slide 15:* Two public datasets: sugar beet (120 photos, boxes for beet and weed) and CottonWeedDet3 (848 photos, three weed classes, cotton not labelled); plus the ICAR bulletin; PhenoBench for future work. Click a link to show it is real.
- *Slide 20:* "An early evaluation file had invented labels: the same eight boxes on every photo, and cotton boxes the official data never has. An audit caught it; it was withdrawn and rebuilt from the official files by a script. The 30 development photos are chosen by a fixed rule (photos with at least one crop and one weed box, 30 evenly spaced), so nobody hand-picks easy ones; the other 90 are held out and were run once. A repeat run reproduced every number exactly."
- *Slide 21:* Read the table row by row: spraying every mask hits weeds but also the crop; threshold 0.35 sprays 70.8% of crop for 9% of weeds; 0.70 sprays nothing. "The labels are the problem."
- *Slide 27:* The six future directions; the first is a fair comparison with WaW on PhenoBench.

*Data details to know:* the labels are *boxes*, not pixel masks, so "crop pixels" are the green pixels inside crop
boxes (and weed pixels the green pixels inside weed boxes, minus crop). The box format is Pascal VOC XML: each object
has a class name and four numbers (xmin, ymin, xmax, ymax). Metrics are pooled over all photos. The toy example
(2/6 = 33.3%, 3/4 = 75%, 80%) is in Part 1, Section 7.

*Your task (by 17 Nov, about one hour): check the datasets.*
+ Open both Kaggle links on slide 15. Confirm: sugar beet has 120 images of 512 × 512 with XML box labels for sugar beet and weed; CottonWeedDet3 has 848 images, three weed classes, no cotton boxes.
+ Download one XML label and find the class name and the four box numbers.
+ Optional (if the project runs on your laptop): run `python scripts/build_eval_manifest_v2.py` and check with `git diff` that `data/manifests/eval_manifest_v2.json` does not change.
+ Send a short note to Chaitanya; it will be added to your role in the report.

*Your questions:* Why is 120 photos enough? (Part 1, Section 7.) What is a held-out set and why use it once? (an honest test: the design never saw it.) Why is held-out recall (77.9%) higher than development (71.5%)? (no overfitting; overfitting would make it lower.) Why can't you compute crop sprayed for cotton? (cotton is not labelled.)

= Rules for answering (everyone)

- *Never claim* we trained a model, beat WaW, used real GPS, tested in a real field, or that it is safe for real spraying.
- *Never claim* a part you did not build. Say your role, then explain: "That part was built by Chaitanya; the idea is …".
- *Never invent a number.* "It is in the report, Table 6.6", and open it.
- If you do not know: "I'm not sure; it is covered in Section … of the report."
- Mention F1 and cotton yourself. A known limitation earns respect; a hidden one loses marks.

= Checklist

- *17 Nov:* Sumant and Sahil finish their tasks; everyone rehearses their 15 minutes twice with a timer; record the backup demo video.
- *18 Nov (Chaitanya, meeting Prof. Dhore):* report PDF and PPT on laptop and pen drive; ask about format, changes, plagiarism check, Head of Department's name, number of copies, binding, signatures and seal, presentation date and slot, live or video demo. Share his answers in the group the same day.
- *After approval:* print and bind the black book, collect signatures.
