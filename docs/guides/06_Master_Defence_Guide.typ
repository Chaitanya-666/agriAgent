#import "../template.typ": *
#show: doc.with(
  title: "Master Defence Guide",
  subtitle: "Everything each team member needs to present, explain and defend AgriAgent at the final evaluation",
  date: "16 November 2026",
)

#note(title: "Read this first")[
This guide replaces older study notes for the final evaluation. It matches the final report
(`docs/report_latex/main.pdf`, 63 pages) and the presentation (`docs/slides/AgriAgent_FYP_Presentation.pptx`,
30 slides). Every number here is in the report. Each of us presents *separately for 15 minutes*, followed by
5–10 minutes of questions, so *every member must know the whole story*, not only their own slides.
]

= Timeline

#table(
  columns: (auto, 1fr),
  [When], [What],
  [Now – 17 Nov], [Everyone reads this guide twice. Sumant and Sahil do their small task (Section 6). Each member rehearses their 15 minutes with a timer, twice.],
  [Tue 18 Nov], [Meet Prof. Dhore in person: show the report and the PPT, get approval, plagiarism check, Head of Department's name, printing instructions (copies, binding), presentation date and slot.],
  [After approval], [Print and bind the black book (number of copies as sir says), collect signatures and seal.],
  [Evaluation day], [15 min presentation per student + Q&A. Live demo on Amit's laptop; backup video ready.],
)

= The project in two minutes (learn this by heart)

*Problem.* Spot spraying puts herbicide only on weeds instead of the whole field. It saves chemicals only if
the camera can tell a weed from the crop: a false "weed" on a crop plant damages the crop.

*Idea tested.* Supervised networks do this well but need thousands of labelled photos of the same field.
New "foundation models" promise to do it with *no training*: Grounding DINO finds objects named in a text
prompt, SAM 2 outlines any object. Chained together this is *Grounded SAM*, our base pipeline.

*What we built.* AgriAgent runs Grounded SAM on a laptop GPU and adds a safety layer around it: a
*deterministic safety gate* (the only part allowed to approve spraying), four *plant rules* (crop-mask
overlap, planting row, size relative to the crop, off-row position), one *bounded escalation agent* that
asks vision-language models about uncertain plants, and herbicide advice taken *only* from the ICAR
bulletin. Output: a spray map in a Streamlit app, a GeoJSON file, and a farmer summary in English, Hindi
or Marathi.

*What we found.* On 90 held-out sugar beet photos, Grounded SAM alone sprays *65.5% of crop pixels* while
hitting only *1.8% of weed pixels*. With our rules and gate: *77.9% weed recall at 8.8% crop sprayed*,
95% herbicide saved, 0.6 s per photo, no training. The agent never sprayed a crop plant but found no
weeds: safe, not effective.

= Numbers to memorise

#table(
  columns: (2fr, 3fr),
  [Fact], [Value],
  [Sugar beet photos (whole public dataset)], [120 = 30 development + 90 held-out],
  [Held-out plants], [363 sugar beets, 215 weeds],
  [Cotton photos (CottonWeedDet3)], [8 development photos],
  [Grounded SAM, gate 0.35, held-out], [65.5% crop sprayed, 1.8% weed recall],
  [Deployed gate 0.70], [sprays nothing (detector scores never above 0.68)],
  [*Product (rules + gate), held-out*], [*77.9% weed recall, 8.8% crop sprayed, 95% saved*],
  [Weeds hit (plant level)], [177 of 215; 95% interval 76.7–86.8% (Grounded SAM 0.5–4.0%)],
  [Beets touched (any sprayed pixel)], [104 of 363 (mostly edge specks)],
  [Development set, product], [71.5% recall, 4.6% crop sprayed],
  [Cotton weed recall], [10.4% (weeds there are not smaller than the crop)],
  [Escalation agent], [69 plants reviewed: 0 crop approved, 13/14 crop verdicts right, 0/25 weeds found],
  [VLM accuracy, 20 patches], [Qwen on Groq 16/20, Qwen on Cloudflare 12/20, Clef Flash 14/20, row rule 13/20],
  [Speed], [0.56–0.64 s per photo (RTX 5050, 8 GB); models peak ≈ 2.4 GB],
  [Tests], [270 automated (235 unit + 35 end-to-end); system test cycle 2: 24/24 pass],
  [Closest work (WaW, IROS 2025)], [weed IoU 12.1% zero-shot vs 62.7% supervised],
  [References], [35 journal/Transactions + 5 conference papers, IEEE format],
)

= How the system works, step by step

+ *Input.* A field photo and the crop name. The prompt is built automatically: `weed . sugar beet plant .`
+ *Detect (Grounding DINO-tiny, local GPU).* Returns boxes; each box gets a label from the prompt words and a confidence score.
+ *Segment (SAM 2-tiny, local GPU).* Each box becomes a precise mask, with SAM 2's own predicted quality score. If quality is below 0.85 it is re-prompted with a corrective point.
+ *Plant rules (no learning).* Every green patch in the photo (found with the excess-green index 2G − R − B and an automatic Otsu threshold) gets a verdict: crop if ≥ 30% inside a crop mask; crop if on the planting row; weed if smaller than ¼ of the median crop plant; weed if off the row when no crop was found; otherwise unsure.
+ *Safety gate (deterministic, final authority).* A detector mask is sprayed only if its label says weed and not crop, confidence ≥ 0.70, quality ≥ 0.85, and it is not more than half the photo. Rule-based weed patches are sprayed after removing every crop pixel. If more than 85% of the photo would be sprayed, nothing is (spot spraying is the wrong tool then). Any error means "do not spray".
+ *Optional escalation agent.* For withheld plants: row rule → Clef Flash → Qwen 3.8 VLM, cheapest first, under a call budget. Answers are weighted by each source's measured accuracy and combined; "weed" needs probability ≥ 0.85, so one source alone can never decide. It only advises; the gate still decides.
+ *System 2 + ICAR.* A cloud VLM names the weed and growth stage; the herbicide and dose come only from the ICAR bulletin row for that crop and weed, clamped to its maximum. No matching row → "no evidence".
+ *Output.* App with a REAL/MOCK banner, spray map, KPIs, GeoJSON download (marked "not GPS"), farmer summary.

#warn(title: "The one weakness to know cold (finding F1)")[
Rule 4 says "off the row = weed" whatever its size, and it only fires when the detector found *no* crop.
If the detector misses a big beet (e.g. the photo is rotated 90°), the whole beet is sprayed. A size limit
fixes it but cuts recall (limit 0.25 → 0.25% crop sprayed but 12.9% recall). We kept the frozen rules and
report the trade-off honestly, because no unused held-out data is left to test a changed rule fairly.
]

= Key concepts (plain language)

#table(
  columns: (auto, 1fr),
  [Term], [Meaning],
  [Zero-shot], [Using a pretrained model on a new task with no training on our data at all.],
  [Grounding DINO], [Open-set object detector: you type class names, it returns boxes for them.],
  [SAM 2], [Segment Anything Model 2: given a box or point, outlines the object; gives no class.],
  [Grounded SAM], [Grounding DINO boxes fed into SAM: text → boxes → masks. Our base pipeline.],
  [Excess green (ExG)], [2G − R − B per pixel: high for plants, low for soil.],
  [Otsu threshold], [Automatically picks the cut-off that best separates two groups (plant vs soil) in each photo.],
  [Held-out set], [Photos never looked at while designing; used once at the end to measure honestly.],
  [Weed recall], [Share of weed pixels the spray map covers. Higher is better.],
  [Crop sprayed], [Share of crop pixels the spray map covers. Lower is better (damage).],
  [IoU], [Overlap of two regions divided by their union; WaW reports weed IoU.],
  [Confidence interval], [Range in which the true value likely lies (95%). Ours do not overlap with the baseline's, so the improvement is real.],
  [VLM], [Vision-language model: takes an image and text, answers in text (Qwen 3.8, Clef Flash).],
  [Naive Bayes combination], [Multiply the odds from each source, assuming they err independently.],
  [ICAR–DWR bulletin], [Indian government herbicide guide: approved chemicals, doses, waiting periods, banned list.],
  [GeoJSON], [Standard map file format; our coordinates are placeholders, not GPS.],
  [Mock mode], [Fake model output for tests on any laptop; every screen says MOCK or REAL.],
)

= Who presents what

The project was planned in four tracks; each member presents the slides of their track and the common
spine. *When asked what you personally did, give your real role from the table below* (it is the same as
Appendix B of the report).

#table(
  columns: (auto, 1fr, auto),
  [Member], [Real role], [Track],
  [Chaitanya Shinde (lead)], [Design and methodology; the whole pipeline (vision, plant rules, gate, agent, final System 2 and ICAR store, app, GeoJSON); evaluation sets and metrics; all experiments; tests, verification and manual test cycles; report and slides.], [1 · Vision, workflow, safety gate],
  [Amit Ingle], [First Streamlit dashboard; system test cycle 0 (16 cases, fresh Windows install, 8 issues filed) and cycle 2 on the final build (24/24 pass); packaging bug report; v1.0.0 release; live demo.], [4 · App, testing, release],
  [Sumant Vetal], [First version of the System 2 agronomy module; ICAR herbicide-row check (task in Section 6).], [2 · Agronomy],
  [Sahil Chavan], [Dataset downloader; dataset check (task in Section 6).], [3 · Data],
)

== Your 15 minutes

Everyone uses the same deck. The *common spine* (about 7 minutes) is the same for all; then about 6 minutes
on your own slides; keep 2 minutes spare. Skip the slides not listed (go past them in one click).

#table(
  columns: (auto, 1fr),
  [Part], [Slides],
  [Common spine (all)], [1 Title · 2 Motivation · 3 Problem statement · 8 Gaps · 10 Objectives and RQs · 11 Architecture · 22 Headline result · 26 Conclusion],
  [Chaitanya], [12 Safety gate · 13 Plant rules · 18–19 Mathematical model · 21 RQ1 baseline · 24 Limitation F1],
  [Amit], [16 Implementation · 17 Demo (run the live demo, ~3 min) · 25 Testing and release · 23 Agent results],
  [Sumant], [4–7 Literature survey (one key paper per slide) · 9 Base paper · 14 Agent and ICAR advice],
  [Sahil], [15 Datasets · 20 Evaluation method (the fabricated set we caught) · 21 RQ1 baseline · 27 Future scope],
)

Speaker notes in the PPT (View → Notes) tell you what to say on every slide. References slides 28–30 are
shown only if asked.

= Small tasks for Sumant and Sahil (about one hour each, by 17 Nov)

== Sumant: check five ICAR herbicide rows

+ Open `data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf` and `src/agronomy/knowledge_store.py` (or ask Chaitanya for a printout of the rows).
+ In the code each row has `chemical`, `dosage_ai_g_per_ha`, `water_l_per_ha`, `waiting_period_days` and `page`. The `page` is the *printed* page number; in the PDF viewer go to *page + 8* (printed page 35 = PDF page 43).
+ Check these five rows against the table on that page: cotton Fluchloralin (page 35), cotton Pyrithiobac-sodium (page 35), wheat (page 25), wheat (page 27), rice Pyrazosulfuron-ethyl (page 33).
+ For each, write: crop, chemical, dose, water, waiting period, page, *match / mismatch*. Send the table to Chaitanya.
+ Be ready to say: "I verified five herbicide rows against the ICAR bulletin. The system never invents a dose: no matching row means it says 'no evidence'. Our team earlier found and fixed a rice row that had 20 g instead of 15 g and 75 instead of 95 waiting days."

== Sahil: check the datasets

+ Open both dataset links from slide 15: #link("https://www.kaggle.com/datasets/wangyongkun/sugarbeetsandweeds")[sugarbeetsAndweeds] and #link("https://www.kaggle.com/datasets/yuzhenlu/cottonweeddet3")[CottonWeedDet3].
+ Confirm and note: sugar beet has 120 images of 512 × 512 with Pascal VOC (XML) box labels for sugar beet and weed; CottonWeedDet3 has 848 images with three weed classes and *no cotton labels*.
+ Open one XML label file and see how a box is stored (class name and four numbers xmin, ymin, xmax, ymax).
+ Optional (if your laptop has the project set up): run `python scripts/build_eval_manifest_v2.py` and check with `git diff` that `data/manifests/eval_manifest_v2.json` does not change.
+ Be ready to say: "The labels are copied unchanged from the official files by a script. An earlier evaluation set had invented labels; it was caught by an audit and replaced. All 120 sugar beet photos are test data, because nothing is trained."

= Questions you will be asked, with answers

== Basics

*Q: What does your project do, in one sentence?* \
It measures whether zero-shot vision models can tell weeds from crop for spot spraying, and adds a
transparent safety layer that raises held-out weed recall from 1.8% to 77.9% while keeping crop damage at 8.8%.

*Q: Why not just train a model?* \
That is the research question. Training needs thousands of labelled photos per crop and field, and
supervised models lose accuracy on new fields (Weyler 2023). We test what is possible with zero labels. A
supervised model would be a different project; its published scores (e.g. 80% mAP on cotton) are our ceiling.

*Q: You used only 120 images?* \
We trained on *zero* images; the 120 photos are the complete public dataset and are used only to test. 90
were held out and evaluated once. The 95% intervals for weeds hit, 76.7–86.8% vs 0.5–4.0% for the baseline,
are far apart, so the conclusion holds. What the data cannot show is other crops, which is why we claim
results for young sugar beet only.

*Q: What is your base paper? Did you implement it?* \
Grounded SAM (Ren et al. 2024): yes, implemented with SAM 2 in place of SAM. Since it is an arXiv report, our
peer-reviewed reference is Chong et al., IROS 2025 ("Weeds are Weird"), the closest work, which argues text
prompts are ill-defined for crop and weed. We measured that claim.

*Q: Did you beat WaW?* \
We do not claim that. They report pixel IoU on pixel-labelled data; we report crop sprayed and weed recall
inside boxes on different data. A like-for-like PhenoBench run is our first future-work item.

*Q: What is new in your work?* \
The sprayer's view of a zero-shot pipeline (crop on the map, weeds hit, herbicide saved), measured on
official labels with a held-out set; a deterministic gate that is the only authority to spray; and rules
that recover most of the performance without training. Plus honest negative results for the agent.

== Method

*Q: Why did Grounding DINO fail?* \
Crop and weed are both small green plants; a text word does not separate them. It called crop plants
"weed" more often than it found weeds, and its scores never exceeded 0.68 on our photos. SAM 2's masks were
good: spraying every mask hits 97.6% of weeds. The labels are the problem, not the segmentation.

*Q: Why is the gate deterministic and not a model?* \
Because spraying a crop is the costly error. A deterministic rule can be unit tested, explained and audited;
same input, same output. Models advise; the gate decides; any error means "do not spray".

*Q: Where do 0.70, 0.85, ¼ and 30% come from?* \
They were set by design before measuring and never tuned on held-out labels. We report results at 0.35, 0.50
and 0.70 to show the trade-off. The ¼ rule is relative to the crop in the same photo, so it adapts per photo.

*Q: Explain the gate equation (slide 19).* \
A mask is sprayed if: label is weed AND not crop AND confidence ≥ 0.70 AND quality ≥ 0.85 AND it covers at most
half the photo. The spray set is the union of those masks and the rule-based weed patches; if it covers more
than 85% of the photo, it is emptied.

*Q: How does the agent decide?* \
Each answer's probability of being right is a·c + (1−a)(1−c) (a = measured accuracy, c = stated confidence).
The odds are multiplied; "weed" needs ≥ 0.85. Example: Clef (a = 0.70) and Qwen (a = 0.80) both certain → odds
2.33 × 4 = 9.33 → 0.90 → weed. One source alone reaches at most 0.80, never enough.

*Q: Why did the agent find no weeds?* \
The weeds are tiny (median 16 px across); the VLMs were often unsure, and our combination needs two sources to
agree. It was designed to be safe first. Result: no crop sprayed, but no recall added. That answers RQ2.

*Q: How do you stop the language model from inventing a dose?* \
It never gives the dose. It only names the weed; the dose comes from the ICAR bulletin row for that crop and
weed, clamped to the bulletin maximum. No row → "no evidence". Every row was checked against the PDF.

*Q: Is the GeoJSON real GPS?* \
No. The photo has no GPS, so the corner is pinned to a placeholder point and each pixel is 5 mm. The file says
so. Real GPS from drone metadata is future work.

== Data and evaluation

*Q: What was the fabricated evaluation set?* \
An early AI-generated label file had the same eight boxes on every beet photo and cotton boxes the official
data never has. An audit caught it; we withdrew its numbers and rebuilt the set from the official XML files
by script. This is why we trust our current numbers.

*Q: Why pooled metrics?* \
Pixels from all photos are summed before dividing, so a photo with many plants counts more. It avoids small
photos with one plant swinging the average.

*Q: Held-out recall (77.9%) is higher than development (71.5%). Overfitting?* \
No: overfitting would make held-out worse. The rules were frozen before the single held-out run.

*Q: Why is cotton so bad (10.4%)?* \
Rule 3 assumes weeds are smaller than the crop. In cotton close-ups one big weed fills the photo, so it looks
like the crop. The method is honestly limited to crops where that assumption holds.

== Testing and engineering

*Q: How did you test it?* \
270 automated tests (gate rules, plant rules, metrics on hand-computed grids, ICAR rows, GeoJSON), CI on every
push, two system test cycles on fresh Windows laptops (24/24 pass on the final build), a verification run
that reproduced the held-out numbers exactly, and a manual test cycle. 30 findings, each fixed or documented.

*Q: Give an example of a bug testing caught.* \
The gate once received confidence and quality hard-coded as 1.0, so every "weed" was sprayed. Or the rice
herbicide row with 20 g and 75 days instead of 15 g and 95 days: an overdose with a shorter waiting period.

*Q: How do you know a result is real and not mock output?* \
Every screen shows REAL or MOCK; a real run that cannot load a model fails with an error instead of falling
back silently.

*Q: Did you use AI tools?* \
Yes, AI coding assistants helped write code and drafts. That is why we added checks: every number comes from
running the code (source file named under each table), every reference was verified against its DOI, and the
problems AI caused (an invented label file, invented references, "100% complete" claims) were found and removed.

== Future and practical use

*Q: Can a farmer use this tomorrow?* \
No. It is a research prototype: no GPS, no sprayer connection, no field trial, sugar beet only. It shows how
far zero-shot vision gets and what a safety layer must do.

*Q: What would you do next?* \
PhenoBench weed IoU for a direct comparison; BioCLIP features instead of text labels; a size limit on rule 4;
few-shot adaptation with a handful of labelled photos; a field trial with an agronomist.

= Rules for answering

- *Never claim* we trained a model, beat WaW, used real GPS, tested in a field, or that the system is safe for real spraying.
- *Never claim* to have built a part you did not build. Say your real role, then explain the part: "That was built by Chaitanya; the idea is …".
- *Never invent a number.* Say "it is in Table 6.6 of the report" and open it.
- If you do not know: "I am not sure; the report covers it in Section …". Then point to it.
- Admit F1 and the cotton result before you are asked. Examiners respect a known limitation more than a hidden one.

= Demo plan (Amit)

+ Before the slot: laptop charged, project venv active, models already downloaded, internet on, `.env` with the Cloudflare keys.
+ `streamlit run app/app.py`. Untick "Mock Mode", choose crop "sugar beet", upload the test photo (`data/outputs/test_photos/beet_X3-130-0.png`).
+ Show the REAL banner, the spray map, the KPI cards, the "show every plant and its verdict" view, switch the summary to Hindi, download the GeoJSON.
+ If anything fails: play the backup screen recording (record it on 17 Nov, about 2 minutes).

= Checklist for 18 November (meeting with Prof. Dhore)

- Report PDF and PPT on a laptop and a pen drive.
- Ask: is the format right; changes needed; plagiarism check (who runs it, by when); Head of Department's name for the certificate; number of printed copies, binding, signatures and seal; presentation date, time, venue, examiner; demo live or video.
- Write down every answer and share it in the group the same day.
