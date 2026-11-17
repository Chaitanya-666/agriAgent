// Read-only study guide: understand AgriAgent from zero, with the real slides, report pages and code.
//   typst compile --root .. 09_Understand_AgriAgent.typ 09_Understand_AgriAgent.pdf
#import "../template.typ": *
#show: doc.with(
  title: "Understand AgriAgent",
  subtitle: "From zero to defending every slide: 13 short lessons with our real evidence and code",
  date: "17 November 2026",
)
#set heading(numbering: "1.")

// The four steps of every lesson.
#let idea(body) = block(width: 100%, fill: rgb("#eef5ef"), stroke: (left: 3pt + accent), inset: 8pt, radius: (right: 3pt), below: 6pt)[*The idea.* #body]
#let ev(body) = block(width: 100%, fill: luma(246), stroke: (left: 3pt + luma(150)), inset: 8pt, radius: (right: 3pt), below: 6pt)[*Our evidence.* #body]
#let why(body) = block(width: 100%, inset: (x: 2pt, y: 2pt), below: 6pt)[*Why.* #body]
#let fu(..pairs) = block(breakable: false, width: 100%, fill: rgb("#fdf6ec"), stroke: (left: 3pt + rgb("#c27c0e")), inset: 8pt, radius: (right: 3pt), below: 10pt)[
  *Examiner follow-ups.*
  #for (q, a) in pairs.pos().chunks(2) [ \ #text(fill: rgb("#8a5a00"))[*Q:* #q] \ *A:* #a ]
]
#show raw.where(block: true): set text(8.2pt)

#note(title: "How to read this")[
One lesson ≈ 10 minutes. Every lesson has the same four steps: *the idea* in plain words, *our evidence*
(slide, black-book page, or the actual code), *why* it is so, and the *follow-up questions* an examiner asks
when your first answer was fine. Read lessons 1–8 first: they cover your slides (1–3, 11–13, 17, 22, 26).
Lessons 9–13 cover everything else. "Book p. N" = printed page of the black book.
]

= The problem
#idea[Weeds steal light, water and nutrients, so farmers kill them with *herbicide*. Usually it is sprayed on
the *whole field*, although weeds grow in patches. A *spot sprayer* has a camera and opens a nozzle only above a
weed. The nozzle is cheap and solved; the hard part is the *decision*: for every plant in the photo, weed or crop?]
#ev[Slide 2; book §1.1, p. 1. Two errors, not equal: a *missed weed* survives one pass; a *crop plant called
"weed"* is sprayed with weed-killer. So our first number is *crop sprayed* (want ≈ 0) and the second is *weed
recall* (want high).]
#why[A tool that sometimes kills the crop is worse than no tool. Every design choice in AgriAgent follows from
this: when in doubt, do not spray.]
#fu(
  [Why not just spray everything?], [Cost, chemical load on soil and water; site-specific spraying treats only weed patches (Gerhards 2022, survey slide 7).],
  [So is recall unimportant?], [It matters, but second. A missed weed can be caught next pass; a sprayed beet is lost yield.],
)

= Five words you need
#table(
  columns: (auto, 1fr),
  [*Word*], [*Meaning in our project*],
  [Pixel, RGB], [A photo is a grid of pixels; each has red, green, blue values. Our beet photos are 512 × 512.],
  [Box], [A rectangle around an object, with a *label* ("weed") and a *confidence* score 0–1. The detector gives boxes.],
  [Mask], [The exact pixels of one object. A sprayer needs masks: a box also covers soil and neighbours.],
  [Zero-shot vs supervised], [*Supervised*: train a network on thousands of hand-labelled photos of *this* crop and field. *Zero-shot*: use a model pretrained by others on huge general data, with *no training on our photos*. AgriAgent trained nothing.],
  [Held-out set], [Photos locked away during design and used *once* at the end, so the score is honest (90 beet photos, run on 18 Oct).],
)

= The two models (Grounding DINO and SAM 2)
#idea[*Grounding DINO* is a detector you talk to: you give it a photo and a text prompt, and it returns boxes for
things that match the words, each with the matched phrase and a confidence. *SAM 2* ("Segment Anything 2") takes a
box and outlines the object inside it, returning a mask and a *predicted quality* score. SAM 2 knows *shapes*, not
*names*. Chaining them, text → boxes → masks, is *Grounded SAM*, our base pipeline.]
#ev[Slides 3, 9, 11. Our prompt is `weed . sugar beet plant .` (two phrases separated by dots). Code:
`src/vision/grounding_dino.py` (`GroundingDINOEngine.detect`, box threshold 0.35) and `src/vision/sam2_wrapper.py`
(`SAM2Segmenter.segment_boxes`; if quality < 0.85, `refine_with_point` re-prompts with a point). We use the *tiny*
versions: both fit in about 2.4 GB of an 8 GB laptop GPU and take ≈ 0.21 s + 0.28–0.37 s per photo (book p. 39).]
#why[They are the best-known open zero-shot detector and segmenter, so "does Grounded SAM work for weeds?" is the
question a farmer-tech team would ask first. The tiny versions keep it on a laptop.]
#fu(
  [What does "grounding" mean?], [Linking words of the text to regions of the image: the detector "grounds" each phrase in a box.],
  [Why not a bigger model?], [It must run on an 8 GB laptop GPU (objective O1); and the failure is in the labels, not the size (lesson 4).],
  [What is predicted quality?], [SAM 2's own estimate of how well its mask fits (its predicted IoU with the true object). We use it as a gate rule: ≥ 0.85.],
)

= Why the text labels fail (RQ1, slides 21–22)
#idea[Grounded SAM does two jobs: *find plants* (masks) and *name them* (labels from the text prompt). On our photos
the first job works and the second fails.]
#ev[Slide 21, 30 development photos (book Table 6.3, p. 33):
#table(columns: (1fr, auto, auto),
  [Setting], [Crop sprayed], [Weed recall],
  [Spray *every* SAM 2 mask], [93.9%], [*97.6%*],
  [Only masks *labelled weed*, confidence ≥ 0.35], [70.8%], [9.0%],
  [Same, confidence ≥ 0.70 (deployed)], [0.0%], [0.0%])
Spraying every mask hits 97.6% of the weeds, so *the masks cover the weeds*. The moment we trust the *labels*, recall
collapses to 9% and 70.8% of the crop is sprayed: the labels are often wrong, beets called "weed", tiny weeds never
boxed. Real confidences never exceeded *0.68*, so the safe 0.70 threshold sprays nothing. On slide 17 the detector
drew *one box over the whole photo* labelled "sugar beet plant" (0.58).]
#why["Weed" is not a visual category like "dog"; it means *a plant in the wrong place*. A young sugar beet and a young
weed are both small green leafy plants. A detector trained on everyday photos and captions has no idea which one the
farmer planted. This is exactly what the closest work argues (Chong et al., IROS 2025: text prompts are ill-defined
for crop vs weed); we *measured* it with sprayer metrics. Held-out: 65.5% crop sprayed for 1.8% recall (slide 22).]
#fu(
  [So is SAM 2 bad?], [No: its masks are fine (97.6% recall when all are sprayed). The problem is *which* masks to spray.],
  [Would a lower threshold help?], [No: lower thresholds buy recall only by spraying crop (70.8% at 0.35); tiling and lower box thresholds found more plants but labelled them no better (book §6.4, p. 34).],
  [Why did you set 0.70?], [A conservative default chosen before measuring; the measurement showed no detection reaches it, which is itself the RQ1 finding.],
)

= The plant rules: how we decide without labels (slide 13)
#idea[Since the detector rarely boxes small weeds, we look at *every green patch* ourselves and give it a verdict
with four plain rules. No training: the rules use only colour, the planting row, and size compared with the crop
in the same photo.]
#ev[*Step 1, find green* (`src/evaluation/crop_protection.py`):
```python
excess_green = 2 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]      # ExG = 2G - R - B
return excess_green > otsu_threshold(excess_green)  # per-photo cut-off
```
*Otsu* tries every cut-off and keeps the one that best separates two groups (soil vs plant): maximum
between-class variance. *Step 2, patches*: close small gaps (radius = 1% of the long side) so the leaves of one
plant join, then each connected blob ≥ 12 px is a patch. *Step 3, rows* (`row_profile`): add up the green pixels
along each axis, smooth over 15 px; if the profile's max ÷ mean ("peakiness") is ≥ 2 the photo has clear rows, and a
patch is *on the row* if the profile at its centre is ≥ half the max. *Step 4, the verdict*
(`src/vision/plant_candidates.py`, `classify_plants`), checked in this order:
```python
if overlap >= CROP_OVERLAP:                    # 0.3 of the patch inside a crop mask
    verdict = "crop"
elif on_row:                                   # crops are sown in rows
    verdict = "crop"
elif median_crop is not None:                  # crop masks exist: compare size
    verdict = "weed" if area < SMALL_VS_CROP * median_crop else "unsure"   # 0.25
elif on_row is False:                          # no crop masks, clear rows, off the row
    verdict = "weed"
else:
    verdict = "unsure"                         # never sprayed
```
"Crop masks" are SAM 2 masks whose label names the crop, *with whole-photo masks removed* (`crop_reference_masks`).]
#why[Each rule uses knowledge a farmer has: crops are where the detector found the crop, crops are in rows, and in
young sugar beet the weeds are tiny (median 16 px across vs 68 px for beets, book p. 37). Rule 3 compares with the
*same photo's* crop, so it calibrates itself. Rules were written on 30 photos, *frozen*, then run once on 90
(book §5.4, p. 24). Walkthrough (slide 17): the only box was the whole photo, which is removed, so there are no crop
masks; the photo has rows; so beets on the row are crop (rule 2) and small off-row patches are weeds (rule 4): 31 of
36 weeds hit, 0 of 3 beets touched.]
#fu(
  [Why Otsu and not a fixed threshold?], [Light and soil change from photo to photo; Otsu picks the best cut-off for each photo automatically.],
  [What if the field has no rows?], [Rules 2 and 4 switch off. With crop masks, rule 3 still works; without them, every patch is *unsure* → not sprayed. Safe by default.],
  [Why does cotton fail (10.4%)?], [In cotton close-ups one big weed fills the frame, so "weeds are smaller than the crop" is false; the detector even boxed big weeds as cotton.],
)

= The safety gate (slide 12)
#idea[The gate is the *only* part allowed to put anything on the spray map. It is plain code, not AI: a list of
conditions that must all pass. If anything is uncertain, missing or crashes, the answer is *do not spray*.]
#ev[In `src/workflow.py` (`spray_map_node`), for each detector mask, in order:
+ *Label policy* (`label_policy`): only a label with a weed word and *no* crop word counts. "weed sugar beet plant" mixes both → *ambiguous*, withheld.
+ *One plant*: a mask covering > 50% of the photo is a whole-scene box, not a plant → withheld.
+ *Confidence ≥ 0.70 and mask quality ≥ 0.85*, checked by `DeterministicRouter` with the mask's *own* scores.
+ *Plant rules*: patches called weed are added, after removing every crop pixel: `weed_patches &= ~crop_patches`.
+ *Infestation ceiling*: if > 85% of the photo would be sprayed, the whole map is suppressed (spot spraying makes no sense there).
Book §5.3, p. 23; as equations §6.1.6, p. 30.]
#why[Spraying the crop is the expensive error, so the decision must be *testable* (every rule has unit tests with
real values), *explainable* (each withheld mask has a written reason) and *repeatable* (same input → same output).
Story to tell: an early version passed confidence and quality as *1.0*, so every "weed" label was sprayed. We found it
in code review, fixed it before any measurement, and that is why every rule is now tested with real values.]
#fu(
  [Why 0.85 for quality, 50%, 85%?], [Conservative design defaults, set before measuring, never tuned on the held-out photos; each is unit tested.],
  [Can the AI agent override the gate?], [No. The agent only advises; the gate still decides (lesson 9).],
  [Where would a bug most likely hide?], [In label handling: Grounding DINO merges phrases ("weed plant"), which is why mixed labels are refused.],
)

= Where it goes wrong: finding F1 (slide 24)
#idea[Rule 4 ("off the row = weed") only fires when the detector found *no crop*. Then it does not look at size, so a
whole beet that happens to sit off the row is sprayed.]
#ev[Rotate photo X-10-0 by 90°: the detector finds no crop box, so the largest beet (4,410 px) is called an off-row
weed and sprayed (book Fig. 6.3, p. 38). The same mechanism appears if the user types the wrong crop (F18): no mask
names the crop, so rule 4 fires; the app now warns. Fixing it costs recall (dev set, book Table 6.9):
#table(columns: (1fr, auto, auto, auto),
  [Rule 4 size limit], [Crop %], [Recall %], [Beets sprayed],
  [0.25 × median plant], [0.25], [12.9], [0],
  [1.0 ×], [0.98], [31.3], [3],
  [none (v3, frozen)], [4.55], [71.5], [11])]
#why[Rule 4 gives most of the recall *and* most of the damage. We kept v3 frozen because the held-out set has been
used; a changed rule could only be tested honestly on *new* data. "Safe mode" is future scope.]
#fu(
  [Why not just add the size limit now?], [Then the 77.9% would no longer be an honest held-out number; it needs fresh data.],
  [How often does it happen?], [104 of 363 held-out beets have at least one sprayed pixel, mostly edge specks, some whole plants (book p. 36).],
)

= Measuring honestly (slides 20, 22)
#idea[Three numbers, all pixel ratios added up over all photos first ("pooled"): *crop sprayed* = crop pixels sprayed ÷
all crop pixels; *weed recall* = weed pixels sprayed ÷ all weed pixels; *herbicide saved* = 1 − sprayed ÷ whole photo.]
#ev[Toy 5×5 photo (a unit test, book p. 31): 6 crop px, 4 weed px; the map sprays 2 crop + 3 weed = 5 px. Crop
sprayed 2/6 = 33.3%; recall 3/4 = 75%; saved 1 − 5/25 = 80%. In code: `spray_metrics` in
`src/evaluation/crop_protection.py`. Per plant: a weed is *hit* if ≥ half its pixels are sprayed; a crop plant is
*touched* if any pixel is.
*The labels:* the first test set turned out to be *fabricated* (every beet photo had the same 2 crop + 6 weed boxes).
We withdrew it and copied every label from the official dataset files by script (`build_eval_manifest_v2.py`).
30 photos for design, 90 held out, run *once* on 18 Oct; a repeat run on 23 Oct gave identical numbers.]
#why[Pixels are what a nozzle sprays. Holding photos out stops us fooling ourselves: a rule tuned on the same photos
always looks good. The held-out result (77.9%) is even above the design set (71.5%), so the rules were not
over-fitted. The interval 76.7–86.8% is a *Wilson 95% confidence interval* for *weeds hit* (177 of 215 = 82.3%), a
different measure from pixel recall; it does not overlap Grounded SAM's 0.5–4.0%, so the improvement is not luck.]
#fu(
  [Only 120 photos?], [We trained on zero; they are the whole public dataset, all used for testing; the intervals do not overlap.],
  [Why is 77.9 outside 76.7–86.8?], [Different measures: 77.9% counts weed pixels; the interval counts whole weeds hit (82.3%).],
  [Why not IoU?], [IoU scores mask overlap; a sprayer cares about crop sprayed and weeds hit. IoU on PhenoBench is our first future step.],
)

= The escalation agent (slides 14, 19, 23)
#idea[For plants the gate withheld (up to 3 per photo, largest first), the agent asks for second opinions, cheapest
first: the *row rule* → *Clef Flash* → *Qwen 3.8 VLM* (a vision-language model on Cloudflare), within a call budget. It
combines their answers and says weed, crop or unsure. It only *advises*.]
#ev[`src/agents/escalation_agent.py`, `p_weed`:
```python
right = accuracy * e.confidence + (1 - accuracy) * (1 - e.confidence)
p = right if e.verdict == "weed" else 1 - right
odds *= p / (1 - p)                      # multiply the odds of each answer
return odds / (1 + odds)                 # P(weed); "weed" only if >= 0.85
```
Accuracies = measured on 20 labelled plant patches: Qwen 16/20 = 0.80, Clef 14/20 = 0.70, row rule 13/20 = 0.65.
Worked example (slide 19): Clef and Qwen both say weed → (0.7/0.3) × (0.8/0.2) = 9.33 → P = 0.90 ≥ 0.85 → weed.
One source alone reaches at most 0.80, so it can never decide alone. Result (book p. 37): 69 plants, no crop
approved, 13 of 14 "crop" verdicts right, but *0 of 25 weeds* called weed; 14 of 69 Groq calls hit the free-tier
rate limit.]
#why[This combination is *naive Bayes*: it treats sources as independent and multiplies their odds. It is simple and
explainable, and capping each source by its measured accuracy stops one confident model from deciding. It is safe
but adds no recall: two sources rarely agreed on "weed". The same Qwen model scored 16/20 on Groq but 12/20 on
Cloudflare, so a trust weight belongs to the provider it was measured on.]
#fu(
  [Is it really an agent?], [One bounded agent: it chooses which source to ask next under a budget and keeps a trace of its evidence. Deliberately no authority.],
  [Why keep it if it adds nothing?], [It is off by default; it explains withheld plants, and RQ2's negative answer is a result.],
)

= Herbicide advice from the ICAR bulletin (slide 14)
#idea[A cloud VLM names the weed and growth stage, but the *herbicide and dose never come from the model*: they come
only from the matching row of the ICAR–DWR bulletin (*Herbicide Use in Indian Agriculture*, 2016) for the declared
crop.]
#ev[`src/agronomy/` (`system2_node.py`, `knowledge_store.py`). Doses are clamped to the bulletin's maximum, banned or
withdrawn herbicides are rejected, and no matching row means "no evidence". Every row was checked against the PDF: a
rice row said 20 g and 75 days instead of 15 g and 95 days, an overdose, found and fixed (book §6.10, p. 38). The farmer
summary (English, Hindi, Marathi) has its safety sentences as *fixed text*, never written by the model.]
#why[Language models can invent numbers. A dose must be traceable to an official source.]
#fu([Is advice the same as spraying?], [No. Spraying is decided by the gate; System 2 only explains and suggests a product from the bulletin.])

= The app, modes and tests (slides 16, 25)
#idea[A Streamlit web app runs the pipeline on an uploaded photo and shows the spray map, numbers, the
"every plant and its verdict" view, the farmer summary and a GeoJSON download.]
#ev[Every screen says *REAL* or *MOCK*; mock mode uses fake detections so the *270 tests* (235 unit + 35 end-to-end)
run without the 1.5 GB of weights; a real run that cannot load a model fails loudly. Models load once
(`src/vision/model_cache.py`). Amit's final system test: 24 of 24 on Windows 11 with a 4 GB RTX 3050. Release v1.0.0.]
#why[Honesty rules: never show fake output as real, and keep every number reproducible from the repository.]

= Following one photo through the code
#table(
  columns: (auto, 1fr),
  [*Step*], [*Where*],
  [Start], [`app/app.py` → `src/workflow.py` · `VisionWorkflowRunner.run`],
  [Detect], [`GroundingDINOEngine.detect` (`src/vision/grounding_dino.py`)],
  [Segment], [`SAM2Segmenter.segment_boxes`, `refine_with_point` (`src/vision/sam2_wrapper.py`)],
  [Gate], [`spray_map_node`, `label_policy` (`src/workflow.py`); `DeterministicRouter` (`src/agents/deterministic_router.py`)],
  [Plant rules], [`classify_plants`, `row_profile` (`src/vision/plant_candidates.py`); `vegetation_mask` (`src/evaluation/crop_protection.py`)],
  [Agent], [`EscalationAgent.review`, `p_weed` (`src/agents/escalation_agent.py`)],
  [Advice], [`src/agronomy/system2_node.py`, `knowledge_store.py`, `farmer_summary.py`],
  [Measure], [`spray_metrics` (`src/evaluation/crop_protection.py`)],
  [Slide 17 figure], [`scripts/make_walkthrough_figure.py`],
)

= Using AI, honestly
#idea[If asked "did you use AI tools?", say yes. Our work was the *decisions*, the *measurements on official labels*,
and *catching where the AI was wrong*.]
#ev[Book §7.3, p. 41 lists six lessons: (1) AI-written status claims ("100% complete", "227 tests" when there were 175,
a "0.99 IoU" that was SAM 2's own confidence) → every claim now carries REAL / PARTIAL / MOCK / PLANNED and a command
output; (2) fabricated test labels (lesson 8); (3) references to papers that do not exist → every reference now comes
from its Crossref record; (4) silent fake output (failed model loads became mock output) → real mode fails loudly;
(5) the gate receiving 1.0 instead of real scores (lesson 6); (6) promises never measured ("over 70% saving", "under
40 ms") → only measured numbers in Chapter 6. Also the wrong rice dose (lesson 10).]
#why[An examiner trusts a team that shows how it checked its tools more than one that claims it wrote everything.]

#pagebreak()
= Check yourself (cover the answers)
#set text(9.5pt)
#table(
  columns: (1fr, 1fr),
  [*Question*], [*Answer*],
  [1. Which error matters most, and why?], [Spraying the crop: it is lost yield; a missed weed is caught next pass.],
  [2. What does Grounding DINO return?], [Boxes with a matched phrase and a confidence.],
  [3. What does SAM 2 return?], [A mask per box and a predicted quality score.],
  [4. Spray every mask: recall? What does it prove?], [97.6%: the masks are fine; the labels are the problem.],
  [5. Highest real detector confidence?], [0.68, so the 0.70 gate sprays nothing.],
  [6. ExG formula and why Otsu?], [2G − R − B; Otsu picks the best plant/soil cut-off per photo.],
  [7. The four plant rules in order?], [In crop mask → crop; on row → crop; smaller than ¼ median crop → weed; no crop masks + off row → weed; else unsure.],
  [8. Why are whole-photo masks removed?], [Otherwise one "crop" box over the photo would make every patch crop.],
  [9. Gate conditions?], [Weed-only label; ≤ 50% of photo; confidence ≥ 0.70; quality ≥ 0.85; rule weeds minus crop; ≤ 85% total; fail safe.],
  [10. What is F1?], [No crop found → rule 4 sprays an off-row beet whatever its size.],
  [11. Headline numbers?], [Held-out: 77.9% recall, 8.8% crop, 95% saved; Grounded SAM 1.8% / 65.5%.],
  [12. Toy example?], [Crop 2/6 = 33.3%, recall 3/4 = 75%, saved 80%.],
  [13. Why can no single agent source decide?], [Max weight 0.80 < 0.85.],
  [14. Where do herbicide doses come from?], [Only the ICAR–DWR bulletin row; clamped; banned rejected.],
  [15. Why was the held-out set used only once?], [So the result is an honest test; any rule change needs new data.],
)
