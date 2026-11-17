// AgriAgent presentation kit for the external examiners (Thu 19 Nov 2026).
// One source, two PDFs:
//   typst compile --root .. --input who=team 07_Presentation_Kit.typ 07_Presentation_Kit_Team.pdf
//   typst compile --root .. --input who=me   07_Presentation_Kit.typ 07_Presentation_Kit_Chaitanya.pdf
// Slide pictures: docs/guides/img/slides/s-NN.png, rendered from docs/slides/AgriAgent_FYP_Presentation.pptx.
// Page numbers ("Book p.") are the printed page numbers of docs/report_latex/main.pdf.
#import "../template.typ": *

#let who = sys.inputs.at("who", default: "team")
#let me = who == "me"

#show: doc.with(
  title: if me { "Examiner Day Guide (Chaitanya)" } else { "AgriAgent Presentation Kit" },
  subtitle: "How to present the 30-slide deck in 15 minutes and defend the black book",
  date: "17 November 2026",
)
#set heading(numbering: none)

#let green = rgb("#2f8f46")
#let blue = rgb("#1f6fb2")
#let grey = rgb("#7a7f87")
#let tag(t) = {
  let c = if t == "EXPLAIN" { green } else if t == "QUICK" { blue } else { grey }
  badge(t, c)
}

// One slide card: picture on the left, what to say on the right.
#let slide(n, t, secs, title, say, ask: none, book: none) = block(breakable: false, width: 100%, below: 7pt)[
  #grid(
    columns: (5.3cm, 1fr),
    column-gutter: 9pt,
    image("img/slides/s-" + (if n < 10 { "0" } else { "" }) + str(n) + ".png", width: 100%),
    [
      #text(10pt, weight: "bold")[#n · #title] #h(4pt) #tag(t) #h(3pt) #text(8.5pt, fill: muted)[#secs s]
      #v(-4pt)
      #set text(9.3pt)
      #say
      #if ask != none [ \ #text(fill: accent)[*If asked:*] #ask ]
      #if book != none [ \ #text(8.5pt, fill: muted)[Black book: #book] ]
    ],
  )
]

// ─────────────────────────── PAGE 1 ───────────────────────────
#set text(10pt)
#set par(leading: 0.55em)
#note(title: "If you read only one page, read this one")[
*Thursday 19 Nov:* external examiners see the presentation, the demo and the black book.
Each student gets at most *15 min to present + 5–10 min of questions* (department rule), using the same
30-slide deck: `docs/slides/AgriAgent_FYP_Presentation.pptx`. The black book is
`docs/report_latex/main.pdf` (63 pages). Everything below quotes those two files.
]

== The project in 4 sentences (learn these by heart)
+ Farmers spray weed-killer over the whole field; a *spot sprayer* sprays only the weeds, but only if a camera can tell a *weed* from the *crop*, and spraying the crop is the costly mistake.
+ We tested whether *zero-shot* models (no training at all), Grounding DINO + SAM 2 = *Grounded SAM*, can make that decision from a text prompt. They cannot: on 90 unseen photos they sprayed *65.5% of the crop* and hit only *1.8% of the weeds*.
+ We added a *safety gate* (plain code, the only part allowed to approve spraying) and *four simple plant rules* (crop overlap, planting row, size, off-row). Result: *77.9% of weeds hit, 8.8% of crop sprayed, 95% herbicide saved*, 0.6 s per photo on a laptop, no training.
+ An AI *escalation agent* that asks vision-language models about unsure plants was *safe but found no extra weeds*, and herbicide doses come *only from the ICAR bulletin*. It is a research prototype, not a product.

== The numbers to remember
#table(
  columns: (1fr, auto, auto),
  align: (left, center, center),
  [90 held-out sugar beet photos], [*Weeds hit (recall)*], [*Crop sprayed*],
  [Grounded SAM alone (base pipeline)], [1.8%], [65.5%],
  [AgriAgent: plant rules + safety gate], [*77.9%*], [*8.8%*],
)

== What examiners care about, so what you stress
#table(
  columns: (auto, 1fr),
  [Point], [Where and what to say],
  [*1. The problem*], [Slides 2–3: why weed vs crop is hard and why crop damage matters most.],
  [*2. What is ours*], [Slides 9, 11–13: the gate + plant rules + measuring the way a sprayer needs. We implement Grounded SAM (base paper) and measure its weakness.],
  [*3. Results*], [Slides 21–22: the numbers above, measured once on photos never seen during design.],
  [*4. It works*], [Slide 17: one real photo through all five steps (or the live demo).],
  [*5. Honesty*], [Slides 20 and 24: fabricated labels found and replaced; the known failure F1. Say them before you are asked.],
)

== The 15-minute plan at a glance
#table(
  columns: (auto, 1fr, auto),
  [*Tag*], [*Slides*], [*Time*],
  [#tag("EXPLAIN")], [2, 3, 4, 8, 9, 10, 11, 12, 13, 17, 20, 21, 22, 26: talk properly], [≈ 10 min],
  [#tag("QUICK")], [1, 5, 6, 7, 14, 15, 16, 18, 19, 23, 24, 25, 27: one or two sentences], [≈ 4 min],
  [#tag("SKIP")], [28–30 references: one sentence, click past], [5 s],
)
*Clock checks:* finish slide 10 by *5:00*, slide 17 by *9:30*, slide 22 by *12:30*, end at *≈ 14:20*.
Running late? Drop to one sentence on 14, 18, 19, 23, 25. Never skip 12, 13, 21, 22.

#pagebreak()
#set text(10.5pt)
#set par(leading: 0.62em)

// ─────────────────────────── SLIDE BY SLIDE ───────────────────────────
= The talk, slide by slide
#text(9pt, fill: muted)[Say it in your own words; the lines below are the safe version. Speaker notes in
PowerPoint (View → Notes) hold the same hints. "Book" = page in the printed black book.]

== Opening and motivation (0:00 – 1:45)

#slide(1, "QUICK", 15, "Title",
  ["Good morning. We are Chaitanya Shinde, Amit Ingle, Sumant Vetal and Sahil Chavan, guided by Prof. V. D. Dhore. Our project is *AgriAgent: a safety-gated zero-shot vision pipeline for crop–weed spot spraying*."],
  book: "title page (same title as the deck, a department rule)")

#slide(2, "EXPLAIN", 45, "Motivation",
  ["Farmers spray herbicide on the whole field although weeds grow in patches. A spot sprayer opens a nozzle only above a weed. The nozzle is cheap; *the decision is the bottleneck*. And the two errors are not equal: a missed weed survives one pass, but a crop plant called 'weed' gets sprayed. So our main number is *how much crop lands on the spray map*."],
  ask: [Why is crop damage worse? A missed weed is caught on the next pass; a sprayed crop plant is lost yield.],
  book: "§1.1, p. 1")

#slide(3, "EXPLAIN", 45, "Why zero-shot + problem statement",
  ["Trained networks do this well but need *labelled photos from the same field*, and drop on new fields. Zero-shot models promise no labels: Grounding DINO finds objects named in text, SAM 2 outlines them; chained, they are *Grounded SAM*." Then read the *problem statement* box.],
  ask: [What is zero-shot? Using a model pretrained by others on huge general data, with *no training on our photos*. We trained nothing.],
  book: "§1.2–1.3, pp. 1–2")

== Literature survey and gaps (1:45 – 4:00)

#slide(4, "EXPLAIN", 40, "Survey 1/4: zero-shot models",
  ["Four survey slides; this is the key one. *Closest work: Chong et al., IROS 2025*: zero-shot with SAM + BioCLIP reaches *12.1% weed IoU vs 62.7% supervised* and argues text prompts are ill-defined for crop vs weed. *Ren et al. 2024, Grounded SAM*, is the pipeline we implement. VLM studies show 0.15–0.75 accuracy, so VLMs may advise, not decide."],
  book: "Ch. 2, pp. 3–17; summary Table 2.1, p. 16")

#slide(5, "QUICK", 15, "Survey 2/4: supervised",
  ["Supervised crop–weed networks (Milioto, Lottes, Weyler) work, but need labels per field; Weyler 2023 shows they drop on new fields."],
  book: "§2.6–2.11, pp. 6–8")

#slide(6, "QUICK", 15, "Survey 3/4: weed detection",
  ["Woebbecke's *excess-green index* is the first step of our plant rules; Rahman 2023 is the source of our cotton photos (80% mAP when trained)."],
  book: "§2.17–2.23, pp. 11–14")

#slide(7, "QUICK", 15, "Survey 4/4: rows, spraying, LLMs",
  ["Bah and Louargant use the *planting row* instead of labels; our rules 2 and 4 use the same idea. LLM reviews say advice must be grounded, so our doses come only from the ICAR bulletin."],
  book: "§2.12–2.16, pp. 9–11")

#slide(8, "EXPLAIN", 40, "Literature gaps",
  ["Five gaps. G1: accuracy needs labels from the same field. G2: the text-prompt pipeline was *argued, not measured*, to fail. G3: papers report IoU, not what a sprayer needs. G4: no testable safety gate between model and nozzle. G5: AI advice not tied to Indian herbicide rules. *G2 and G3 are our research gap; G4 is our design contribution.*"],
  book: "Ch. 3, p. 18")

== Base paper and objectives (4:00 – 5:00)

#slide(9, "EXPLAIN", 30, "Base paper and positioning",
  ["*Base paper: Grounded SAM.* We implement it, with SAM 2 instead of SAM. The peer-reviewed reference point is WaW (IROS 2025). We add the sprayer's view and a safety layer, without training. *We do not claim to beat WaW's IoU*: different metric and data."],
  ask: [Did you beat it? Different question and data; a like-for-like run on PhenoBench is future-scope item 1.],
  book: "§3.1, p. 19")

#slide(10, "EXPLAIN", 30, "Objectives and research questions",
  ["Six objectives, three questions. *RQ1:* how well does Grounded SAM separate weed from crop? *RQ2:* does asking AI models about unsure plants help without making it less safe? *RQ3:* which cheap addition cuts crop damage most, at what cost? The rest of the talk answers these three."],
  book: "Ch. 4, pp. 20–21")

== Proposed system (5:00 – 8:00)

#slide(11, "EXPLAIN", 50, "Architecture",
  [Point and walk top to bottom: "Photo + crop name → Grounding DINO boxes → SAM 2 masks → plant rules → *safety gate (yellow)* → app and GeoJSON. *System 1* runs on the laptop, 0.6 s per photo, same input same output. *System 2* (blue, cloud) only advises. *The yellow gate is the only part allowed to approve spraying.*"],
  ask: [Why two systems? Local plain code decides; cloud AI can be wrong, so it may only advise.],
  book: "§5.2, p. 23, Fig. 5.1")

#slide(12, "EXPLAIN", 40, "Safety gate",
  ["The gate is plain code, not AI. A mask is sprayed only if its label says weed and not the crop, confidence ≥ 0.70, mask quality ≥ 0.85, it covers ≤ 50% of the photo; if more than 85% would be sprayed, nothing is; any error → do not spray. An early version passed confidence as 1.0 and sprayed every 'weed'; we found it, fixed it, and now every rule has a test with real values."],
  ask: [Why not AI here? Spraying the crop is the costly mistake; rules can be tested and explained and always give the same answer.],
  book: "§5.3, p. 23; equations §6.1.6, p. 30")

#slide(13, "EXPLAIN", 45, "Plant rules v3 (frozen)",
  ["The detector rarely boxes small weeds, so we check *every green patch* (excess green + Otsu threshold). In order: *1* crop if ≥ 30% inside a crop mask; *2* crop if on the planting row; *3* weed if smaller than ¼ of the median crop plant; *4* weed if no crop was found and it is off the row; else *unsure, never sprayed*. Written on 30 photos, frozen, then run once on 90 new photos."],
  ask: [Why ¼? It calibrates itself per photo; set by design, never tuned on the held-out photos.],
  book: "§5.4, p. 24")

#slide(14, "QUICK", 30, "Escalation agent and ICAR",
  ["The *escalation agent* asks up to three sources (row rule, Clef Flash, Qwen) about withheld plants, cheapest first, and needs 85% agreement for 'weed'; it only advises. *System 2* names the weed, but the herbicide and dose come only from the *ICAR–DWR bulletin*; banned herbicides are rejected. Summary in English, Hindi, Marathi."],
  ask: [Is it really an agent? One bounded agent: it chooses which source to ask next under a call budget and keeps a trace; it has no authority.],
  book: "§5.5–5.7, pp. 24–25")

#slide(15, "QUICK", 20, "Datasets (with links)",
  ["Public data with links: *sugarbeetsAndweeds* (120 photos: 30 design + 90 held out), *CottonWeedDet3* (8 photos), the *ICAR bulletin*, and PhenoBench for future work. Labels copied unchanged from the official files by a script."],
  ask: [Why sugar beet? It is public data where both crop and weeds are labelled; cotton labels only weeds, so crop damage cannot be measured there.],
  book: "§5.8, p. 26, Table 5.2")

#slide(16, "QUICK", 15, "Implementation",
  ["Python; the two tiny models through Hugging Face on an 8 GB laptop GPU (peak ≈ 2.4 GB); Qwen and Clef on Cloudflare's free tier; Streamlit app; *270 automated tests*; release v1.0.0. Every screen says REAL or MOCK."],
  book: "§5.9–5.11, pp. 26–27")

== Demo, maths, evaluation (8:00 – 12:30)

#slide(17, "EXPLAIN", 75, "System walkthrough (or live demo)",
  [Walk the five panels left to right: "① A real photo, crop sugar beet. ② Grounding DINO draws *one box over the whole photo*, 'sugar beet plant' 0.58: its labels are useless here. ③ SAM 2 makes it one mask. ④ Our *plant rules* check every green patch: plants on the row protected (green), small off-row patches are weeds (red). ⑤ The gate sprays only those, minus every crop pixel. Against the official labels: *31 of 36 weeds hit, 0 of 3 beets touched*, 98% saved." Held-out average: 77.9% / 8.8%.],
  ask: [Is it real? Real run on 17 Nov with the real models (`scripts/make_walkthrough_figure.py`); the app always shows REAL or MOCK.],
  book: "§5.12, pp. 27–28")

#slide(18, "QUICK", 30, "Maths 1/2: vegetation and rules",
  ["The full model is in §6.1. Excess green = 2G − R − B; *Otsu* picks the plant/soil threshold per photo; rows come from the vegetation profile. The classifier is a piecewise function; line 5 applies only when no crop was found, which is our known failure F1."],
  ask: [Otsu? Tries every threshold and keeps the one that best separates the two pixel groups (maximum between-class variance).],
  book: "§6.1.2–6.1.5, pp. 29–30")

#slide(19, "QUICK", 30, "Maths 2/2: gate, agent, metrics",
  ["The gate is an AND of conditions. The agent multiplies odds: Clef (0.70) and Qwen (0.80) both say weed → odds 9.33 → *P = 0.90 ≥ 0.85*, so weed; one source alone tops out at 0.80. Metrics are pixel ratios, tested on a 5×5 toy grid: crop 2/6 = 33.3%, recall 3/4 = 75%, saved 80%."],
  book: "§6.1.6–6.1.8, pp. 30–31")

#slide(20, "EXPLAIN", 30, "Evaluation method",
  ["Honesty slide. The first test set had *fabricated labels*: the same 2 crop + 6 weed boxes on every photo. We caught it, withdrew it and rebuilt every label from the official files by script. 30 photos for design; *90 held out and run once* (18 Oct); a repeat run (23 Oct) gave identical numbers."],
  book: "§6.2, pp. 32–33, Fig. 6.1")

#slide(21, "EXPLAIN", 40, "RQ1: Grounded SAM baseline",
  ["Spraying every SAM 2 mask hits 97.6% of weeds, so *the masks are fine*. Using the text labels: threshold 0.35 sprays 70.8% of the crop for 9% of weeds; the deployed 0.70 sprays nothing, because real scores never pass 0.68. *Text labels cannot separate crop from weed*, as WaW argued."],
  book: "§6.3–6.4, pp. 33–34, Table 6.3")

#slide(22, "EXPLAIN", 45, "Headline (held-out, run once)",
  ["On 90 photos never used in design: *77.9% weed recall at 8.8% crop sprayed*, against 1.8% and 65.5% for Grounded SAM. 95% herbicide saved. 95% confidence intervals for weeds hit, 76.7–86.8% vs 0.5–4.0%, do not overlap. Cotton is weaker: 10.4%."],
  ask: [Only 120 images? We trained nothing; it is the whole public dataset, used only for testing; the intervals do not overlap. What is limited is generality beyond young sugar beet.],
  book: "§6.6, pp. 35–36, Table 6.6, Fig. 6.2")

== Results, limits, close (12:30 – 14:20)

#slide(23, "QUICK", 25, "RQ2: escalation agent",
  ["69 withheld plants: it *never approved a crop plant*, was right 13 of 14 times when it said crop, but called *0 of 25 weeds* weeds. Safe, not effective. The same Qwen model scored 16/20 on Groq and 12/20 on Cloudflare."],
  book: "§6.7–6.8, p. 37")

#slide(24, "QUICK", 30, "Limitation F1",
  ["Say it before they find it: rotate a photo 90°, the detector finds no crop, so rule 4 calls the largest beet an off-row weed and sprays it. A size limit fixes that but loses most of the recall (table). Rules stay frozen; a 'safe mode' is future work."],
  book: "§6.9, p. 38, Fig. 6.3")

#slide(25, "QUICK", 15, "Testing and release",
  ["270 automated tests, three manual cycles, final system test 24 of 24 on Windows. Every ICAR row was checked against the PDF; a dangerous rice dose was found and fixed."],
  book: "§6.10–6.12, pp. 38–40")

#slide(26, "EXPLAIN", 30, "Conclusion",
  [Read the three answers: "*RQ1* text labels fail. *RQ2* the agent is safe but finds no weeds. *RQ3* simple rules plus the gate: 77.9% recall at 8.8% crop, 95% saved, no training. A research prototype, not for real spraying; every number is reproducible from the repository."],
  book: "Ch. 7, pp. 41–42")

#slide(27, "QUICK", 15, "Future scope",
  ["Next: a like-for-like comparison with WaW on PhenoBench, species-aware BioCLIP features instead of text labels, a safe mode for rule 4, few-shot adaptation, and a field trial with GPS and an agronomist."],
  book: "Ch. 8, p. 43")

#slide(28, "SKIP", 5, "References 1/3 (also 29, 30)",
  ["*51 references in IEEE format*, with volume, pages and DOI; the report lists them in full." Click to the end and say "Thank you, we are happy to take questions."],
  book: "References, pp. 44–48")

#pagebreak()

// ─────────────────────────── BLACK BOOK ───────────────────────────
= The black book in one page
The examiner may flip through it while you talk. Know where these are:

#table(
  columns: (auto, auto, 1fr, auto),
  [*Part*], [*Pages*], [*What is there*], [*Slides*],
  [Front matter], [i–xii], [Statement of candidate, approval sheet, certificate, acknowledgement, *abstract (p. v)*, contents, lists, abbreviations], [1],
  [1 Motivation], [1–2], [Why spot spraying, why zero-shot, *problem statement*, scope, contributions], [2–3],
  [2 Literature survey], [3–17], [*25 papers*, each with authors, venue, DOI, introduction, solution, results, gap, relevance; summary table p. 16], [4–7],
  [3 Literature gaps], [18–19], [Gaps G1–G5; *base paper* §3.1], [8–9],
  [4 Objectives], [20–21], [O1–O6, RQ1–RQ3, success criteria], [10],
  [5 Proposed system], [22–28], [Requirements, architecture, gate, rules, agent, ICAR, *datasets with links*, stack, app, GeoJSON], [11–17],
  [6 Model + results], [29–40], [*Mathematical model* (§6.1), evaluation, RQ1, *headline Table 6.6 p. 35*, RQ2, F1, ICAR check, speed, testing], [18–25],
  [7 Conclusion], [41–42], [Answers to RQs, base paper, lessons, limitations], [26],
  [8 Future scope], [43], [Next steps], [27],
  [References], [44–48], [IEEE format, 35 journal + 5 conference papers + datasets/docs], [28–30],
  [Appendix A, B], [49–50], [How to run; *team roles* (Table B.1)], [–],
)

== Format check against the department rules (done 17 Nov)
#table(
  columns: (1fr, auto),
  [Department rule], [Status],
  [Report in LaTeX (`docs/report_latex/`)], [#real done],
  [Same section order as the department list (Motivation … Future scope, References)], [#real done],
  [≥ 25–30 Transactions / journal papers, IEEE format, full volume/pages/DOI], [#real 35 journal + 5 conf.],
  [Every paper cited in the survey or gaps chapter], [#real checked],
  [Same title in report and PPT], [#real done],
  [Datasets slide with links], [#real slide 15, Table 5.2],
  [PPT 25–30 slides], [#real 30],
  [Demo video *or* results in the slot], [#real results on slide 17],
  [Mentor pre-approval of report + PPT], [#planned pending],
  [Plagiarism < 30% (mentor runs the check)], [#planned pending],
  [Hard copies: one per student + one for the guide + one for the department], [#planned after approval],
  [Signatures and dates (front matter, by hand after printing)], [#planned after printing],
)

#pagebreak()

// ─────────────────────────── QUESTIONS ───────────────────────────
= The 16 questions most likely to come
#set text(9.6pt)
#let qa(q, a) = block(breakable: false, below: 6pt)[*Q: #q* \ #a]

#qa[Explain the project in one minute.][Use the 4 sentences on page 1 and the numbers 65.5% → 8.8% crop, 1.8% → 77.9% weeds.]
#qa[What is new in your work?][(1) We *measured* the zero-shot pipeline the way a sprayer needs: crop sprayed, weeds hit, herbicide saved. (2) A *safety gate* that alone decides spraying. (3) Simple rules that recover most of the performance *without training*. (4) Honest negative results (RQ2, F1).]
#qa[What is your base paper? Did you implement it?][Grounded SAM (Ren et al. 2024). Yes, with SAM 2 instead of SAM. Peer-reviewed reference: Chong et al., IROS 2025 (slide 9, p. 19).]
#qa[Why not just train YOLO or a CNN?][That is the research question: can we avoid labelling? Training needs thousands of labelled photos per field and drops on new fields (Weyler 2023). Trained results (about 80% mAP on cotton, Rahman 2023) are the ceiling we compare against.]
#qa[Only 120 images?][We trained on zero. 120 is the whole public dataset, used only to test; 90 held out and run once; confidence intervals 76.7–86.8% vs 0.5–4.0% do not overlap (p. 35).]
#qa[What is your mathematical model?][§6.1, pp. 29–32: excess green and Otsu threshold → patches → row test → piecewise classifier → gate as a logical AND → agent's odds formula → three pixel-ratio metrics. Show slide 19's worked example.]
#qa[Why is the gate plain code and not AI?][Spraying the crop is the expensive mistake. Plain rules can be unit tested, explained, and give the same answer every time. AI advises; the gate decides.]
#qa[What if the field has no rows?][Rules 2 and 4 need clear rows. Without rows, rules 1 and 3 still work when the detector finds crop plants; everything else becomes *unsure*, which is never sprayed. It fails safe.]
#qa[Does it need internet in the field?][No for spraying decisions: System 1 runs locally. Only System 2's advice (weed name, summary) uses the cloud.]
#qa[Is it real time? Can a farmer use it?][0.6 s per photo on a laptop GPU. Not field-ready: no GPS, no sprayer, tested on young sugar beet. It is a research prototype (slide 26).]
#qa[Why sugar beet and not an Indian crop?][It is the public dataset where both crop and weed are labelled, so crop damage can be measured. Cotton (Indian crop) labels only weeds. Indian field data is future work.]
#qa[What is IoU and why don't you use it?][Overlap ÷ union of predicted and true regions. A sprayer cares about crop sprayed and weeds hit, so we report those; IoU on PhenoBench is our first future step to compare with WaW.]
#qa[Biggest weakness?][F1 (slide 24): with no crop found, rule 4 can spray a whole beet. Also cotton recall 10.4%, and only one crop really tested.]
#qa[Did you use AI tools? What about plagiarism?][Yes, for code and drafts. That is why every number comes from running the code, every reference was checked against its DOI, and AI mistakes (fake labels, bad references, the 1.0 gate bug, a wrong rice dose) were found and removed. The mentor runs the plagiarism check.]
#qa[Why is this number so high / so low?][Use the next section: every number on the slides with its source and the reason.]
#qa[What did *you* do?][Give *your* line from Table B.1 (p. 50) and the next section. Never claim a part you did not build.]
#set text(10.5pt)

#pagebreak()

// ─────────────────────────── NUMBERS ───────────────────────────
= Every number on the slides, and why it is that value
Seniors' advice: examiners point at a number and ask "where does this come from?" and "why so high / so low?".
Rule: *our* numbers come from running the code (result files in `docs/results/`); *survey* numbers are the papers' own results on their own data.
#set text(9pt)
#let nt(..rows) = { show raw: set text(7.5pt); table(columns: (2.7cm, 1fr, 1.25fr), [Number (slide)], [What it is · source], [Why that value], ..rows) }

== Our headline results
#nt(
  [*77.9%* weed recall (22)], [Share of weed *pixels* on the spray map, 90 held-out photos. `holdout_plant_rules_v3`], [Rules 3 and 4 catch small and off-row weeds that the detector never boxes. Not 100% by design: anything ambiguous becomes *unsure*, and unsure is never sprayed (safety first).],
  [*8.8%* crop sprayed (22)], [Share of crop pixels sprayed. Same file. 104 of 363 beets touched], [Report §6.6: mostly small specks at a beet's edge, but some whole beets through F1 (slide 24). Not 0 because the rules use no training.],
  [*1.8%* / *65.5%* (22)], [Grounded SAM alone, threshold 0.35, same 90 photos. Same file], [The detector mostly boxes the big beets and often labels them "weed", so it sprays crop and misses small weeds.],
  [*95%* saved (22)], [1 − sprayed area ÷ whole photo. Same file (94.96)], [Weeds are small; only about 5% of each photo is sprayed.],
  [*76.7–86.8%* vs *0.5–4.0%* (22)], [95% Wilson interval for the share of *weeds hit*: 177/215 = 82.3% vs 3/215 = 1.4%. Report §6.6], [It counts weeds (hit or not), not pixels, so 77.9% need not lie inside it. The two ranges do not overlap: the gain is not luck.],
  [*71.5% / 4.6%* dev (22)], [Same rules on the 30 design photos. `plant_rules_v3`], [Held-out is *not worse* than dev, so the rules were not over-fitted to the design photos.],
  [*10.4%* cotton (22)], [Weed recall on 8 cotton photos (7 of 19 weeds). Same file], [Cotton close-ups: one big weed fills the frame, so "weeds are smaller than the crop" is false; the detector even boxed big weeds as cotton.],
)

== Grounded SAM baseline, dev set (21)
#nt(
  [*97.6%* recall, every mask], [Spray every SAM 2 mask. `baseline_v2`], [Masks cover nearly all plants, so *segmentation is fine*; but it also sprays 93.9% of crop.],
  [*70.8% / 9.0%*, gate 0.35], [Spray only masks labelled weed, score ≥ 0.35], [Labels are wrong: many beets are called "weed".],
  [*0.0 / 0.0*, gate 0.70], [The deployed threshold], [Real scores never pass *0.68*: Grounding DINO is unsure about the vague word "weed". 0.70 was a safe design default set before measuring.],
  [*5.3%* + crop exclusion], [Remove pixels inside "crop" boxes. `exclusion_v2`], [Protects beets but adds no weeds (recall stays 6.8%).],
)

== Agent and models (14, 19, 23)
#nt(
  [*69* plants: *0* crops approved, *13/14*, *0/25*], [Agent on withheld plants, dev set. `agent_v2`], [It needs P ≥ 0.85 for "weed", which takes two sources agreeing; they rarely agreed on "weed". Also 14 of 69 Groq calls hit the free-tier rate limit and counted as no answer.],
  [*16 / 14 / 13 / 12* of 20], [Crop-or-weed accuracy on 20 labelled plant patches: Qwen on Groq / Clef / row rule / Qwen on Cloudflare], [Small sample; same model differs by provider (16 vs 12), so trust is per provider.],
  [Weights *0.80 / 0.70 / 0.65*], [Agent's trust in Qwen / Clef / row rule], [Exactly the measured accuracies above: 16/20, 14/20, 13/20.],
  [*0.85* and *0.90* (19)], [Decision bar; worked example], [Chosen so that no single source (max 0.80) can decide alone; two agreeing sources give 0.90.],
)

== Design thresholds (12, 13, 18): set by design, frozen, never tuned on the held-out photos
#nt(
  [0.70 · 0.85 · 50% · 85%], [Gate: confidence, mask quality, one-plant size, infestation ceiling], [Conservative defaults: spraying crop is the costly error. Each has a unit test.],
  [30% · ¼ · 2 · 0.5 · 1%], [Rules: crop-mask overlap, size vs median crop, row peakiness, on-row level, closing radius], [Set on the 30 design photos, then frozen before the single held-out run (18 Oct).],
)

== System and data (15, 16, 20, 25)
#nt(
  [*0.6 s* per photo], [Median after the first photo; 0.21 s detect + 0.28–0.37 s segment, RTX 5050], [Tiny models; first photo ≈ 1.1–1.5 s and model loading ≈ 4 s are not counted.],
  [*2.4 GB* peak], [GPU memory, both models], [Tiny versions; also runs on a 4 GB RTX 3050.],
  [*120* photos (30 + 90)], [The whole sugarbeetsAndweeds dataset, 512×512], [Test data only: we trained nothing.],
  [*93 / 282* and *363 / 215*], [Beets / weeds labelled in dev and held-out sets], [Copied from the official XML files by script.],
  [*270* tests], [235 unit + 35 end-to-end], [Every gate rule, plant rule, metric, ICAR row and GeoJSON field.],
  [*7/16*, *24/24*, *30* findings], [System test cycle 0, cycle 2; findings F1–F30], [Cycle 0 found 8 issues, all fixed; cycle 2 is the final build.],
)

== Survey numbers (4–7): the papers' own results, not ours
#nt(
  [12.1% vs 62.7%], [WaW: zero-shot vs supervised weed IoU, IROS 2025], [Even the best zero-shot method is far below trained models.],
  [48.7 AP · 52.5 AP], [Grounded SAM on SegInW · Grounding DINO zero-shot on COCO], [Good on everyday objects, not on crop vs weed.],
  [0.15–0.75], [Nasir 2026: commercial VLMs' weed accuracy], [Too unreliable to decide; fine to advise.],
  [79.98% mAP], [Rahman 2023: trained detectors on our cotton data], [The supervised ceiling for that data.],
  [95.7% · 86.2% · 96.5–99.4%], [DeepWeeds · Dyrmann · Jiang: supervised classification], [Need labelled data; whole-image class, not a spray map.],
)
#text(8.5pt, fill: muted)[Unsure about a survey number? Say: "That is the authors' result on their data, reported in their paper; the summary is in Chapter 2 of our report."]
#set text(10.5pt)

#pagebreak()
= How it is built: a one-page code tour
#text(9pt, fill: muted)[Examiners ask "how did you implement it?". Overview in the talk; this is for the questions. Follow one photo:]
#{ show raw: set text(7.5pt); table(
  columns: (2cm, 6.2cm, 1fr),
  [*Step*], [*File · function*], [*What happens*],
  [1 Start], [`app/app.py` → `src/workflow.py` · `VisionWorkflowRunner.run`], [Streamlit takes the photo and crop; the runner calls the nodes in order.],
  [2 Detect], [`src/vision/grounding_dino.py` · `GroundingDINOEngine.detect`], [Prompt `weed . sugar beet plant .` → boxes, labels, scores (box threshold 0.35).],
  [3 Segment], [`src/vision/sam2_wrapper.py` · `SAM2Segmenter.segment_boxes`, `refine_with_point`], [One mask per box with a quality score; re-prompted with a point if quality < 0.85.],
  [4 Plant rules], [`src/vision/plant_candidates.py` · `row_profile`, `classify_plants`], [Green patches (ExG + Otsu from `src/evaluation/crop_protection.py`) → crop / weed / unsure.],
  [5 Gate], [`src/workflow.py` · `label_policy`, `spray_map_node`; `src/agents/deterministic_router.py` · `verify_spray_safety`], [Applies the gate rules; builds the spray map; anything uncertain is withheld.],
  [6 Agent (opt.)], [`src/agents/escalation_agent.py` · `EscalationAgent.review`, `p_weed`], [Asks row rule → Clef → Qwen; combines odds; advice only.],
  [7 Advice], [`src/agronomy/` · `system2_node.py`, `knowledge_store.py`, `farmer_summary.py`], [VLM names the weed; dose only from the ICAR row; summary EN/HI/MR.],
  [8 Measure], [`src/evaluation/crop_protection.py` · `spray_metrics`], [Crop sprayed, weed recall, saving: pooled pixel ratios.],
) }
Models load once (`src/vision/model_cache.py`); *mock mode* swaps in fake detections so the 270 tests run without the 1.5 GB of weights.

#pagebreak()

// ─────────────────────────── WHO PRESENTS WHAT ───────────────────────────
= Who presents which slides (locked 17 Nov)
We present together, in slide order. Everyone uses the "say this" lines of their slides (pages 2–7, or the speaker notes).
If the department evaluates each student *alone* for 15 minutes, ignore this split and use the whole-deck plan on page 1.

#table(
  columns: (auto, 1fr, auto),
  [*Presenter*], [*Slides*], [*Time*],
  [*Chaitanya* (9)], [1 Title · 2 Motivation · 3 Problem statement · 11 Architecture · 12 Safety gate · 13 Plant rules · 17 Walkthrough · 22 Headline · 26 Conclusion], [≈ 6.5 min],
  [*Sumant* (8)], [4–7 Literature survey · 8 Gaps · 9 Base paper · 10 Objectives · 14 Agent + ICAR advice], [≈ 3.5 min],
  [*Amit* (7)], [15 Datasets · 16 Implementation · 18–19 Mathematical model · 23 Agent results · 24 Limitation F1 · 25 Testing; runs the live demo during 17], [≈ 3 min],
  [*Sahil* (6)], [20 Evaluation method · 21 RQ1 baseline · 27 Future scope · 28–30 References], [≈ 1.5 min],
)
*Speaking order:* Chaitanya 1–3 → Sumant 4–10 → Chaitanya 11–13 → Sumant 14 → Amit 15–16 → Chaitanya 17 → Amit 18–19 → Sahil 20–21 → Chaitanya 22 → Amit 23–25 → Chaitanya 26 → Sahil 27–30. *Hand-off line:* "… and now X will explain …".
#note(title: "If someone is absent")[Chaitanya takes their slides with the same lines; nothing else changes.]

#pagebreak()

// ─────────────────────────── AUDIENCE-SPECIFIC ───────────────────────────
#if me [
= Your slides: the light, visual parts of your own work
*1 · 2 · 3 · 11 · 12 · 13 · 17 · 22 · 26* (9 slides), about 6.5 minutes: the opening story plus the core. Each is a story, a diagram, a table of plain rules, the photo walkthrough or big numbers: read the card on pages 2–7 aloud twice and you have it.
#table(
  columns: (auto, 1fr),
  [*Slide*], [*Your one line if you blank*],
  [1], ["We are …, guided by Prof. Dhore; AgriAgent, a safety-gated zero-shot vision pipeline for spot spraying."],
  [2], ["Weeds grow in patches but we spray the whole field; the hard part is telling weed from crop, and spraying the crop is the costly mistake."],
  [3], ["Trained models need labelled photos per field; we test zero-shot models that need none: photo + crop name → safe spray map, on a laptop."],
  [11], ["Top to bottom: detect, segment, plant rules, gate. *The yellow gate is the only thing allowed to spray.*"],
  [12], ["The gate is plain code: spray only if every rule passes; any doubt → do not spray."],
  [13], ["Every green patch: crop if in a crop mask or on the row, weed if small or off-row, else unsure → never sprayed."],
  [17], ["One real photo: the detector's label is useless, the rules protect the beets and spray 31 of 36 weeds."],
  [22], ["90 unseen photos: 77.9% of weeds hit, 8.8% of crop, against 1.8% and 65.5% for Grounded SAM."],
  [26], ["Text labels fail, the agent is safe but adds nothing, simple rules + the gate recover most of it."],
)
Questions will still come to you on anything (you are the lead). Use the numbers section and these deep-dive answers:

#qa[Why ¼ of the median crop plant?][It calibrates itself per photo and was set by design, never tuned on the held-out labels. Weeds in this data are tiny (median about 16 px across vs 68 px for crops).]
#qa[Why naive Bayes in the agent?][Simple and explainable; each source's measured accuracy (row 0.65, Clef 0.70, Qwen 0.80) caps its influence. It assumes independent errors, which is optimistic, so the 0.85 bar is strict.]
#qa[Complexity?][Vegetation, closing, components and rows are linear in the number of pixels; run time is dominated by the two networks (≈ 0.21 s detection, 0.27–0.37 s segmentation).]
#qa[Why the tiny models?][Both fit in 8 GB with headroom (peak ≈ 2.4 GB) and run in about 0.6 s per photo; also verified on Amit's 4 GB RTX 3050.]
#qa[Where is the gate in the code?][`src/agents/deterministic_router.py` and `src/workflow.py`; each rule has unit tests.]

= Your checklist before Thursday
#table(
  columns: (auto, 1fr),
  [When], [What],
  [*Tue 17 eve*], [Read page 1 twice, then *your 9 slide cards* with the deck open. CPAD exam prep comes first (other session).],
  [*Wed 18 morning*], [Meet Prof. Dhore *before the CPAD exam (13:30)*. Show the report PDF + PPT. Ask: (1) approval of both; (2) plagiarism check (< 30%); (3) how many black-book copies; (4) Thursday's time and whether each student presents separately; (5) *tell him your Deep Learning lab exam is Thu 19, 9:00–17:30* and ask for a slot that fits.],
  [*Wed 18 after CPAD*], [Send me any changes he asks for; I rebuild the PDF. Then print and bind (front matter pages i–iv get signatures by hand).],
  [*Thu 19*], [Before your slot: read page 1 and the 16 questions once. Laptop charged, deck opened in presenter view.],
)
#warn(title: "Clash")[Your DL lab exam (Lab 1B, 9:00–17:30) is on the same day as the external examiners. Sort out the timing with Prof. Dhore and the DL faculty on Wednesday.]
] else [
= Your part and what you may claim
Present your slides from the table on the previous page, then answer questions on your own part.
Claim only your real role, exactly as printed in the black book (Table B.1, p. 50):

#table(
  columns: (auto, 1fr, auto),
  [*Member*], [*Role in the black book*], [*Expect questions on*],
  [Chaitanya Shinde (lead)], [Research questions and method; vision pipeline, safety gate, plant rules, escalation agent, System 2 and ICAR store, app, evaluation, experiments, tests, report and slides.], [everything; 1–3, 11–13, 17, 22, 26],
  [Amit Ingle], [First Streamlit dashboard; system test cycles 0 and 2 (24/24 on Windows 11, RTX 3050); packaging bug report; v1.0.0 release; live demo.], [15–19, 23–25],
  [Sumant Vetal], [First version of the System 2 agronomy module (diagnosis and herbicide advice), later rewritten and integrated.], [4–10, 14, ICAR],
  [Sahil Chavan], [The dataset downloader used to fetch the public datasets.], [15, 20–21],
)

= How to prepare in 90 minutes
+ *15 min:* page 1 of this kit, twice. Say the 4 sentences aloud without looking.
+ *40 min:* open the deck next to this kit; read every card once, then say *your own slides'* lines aloud three times.
+ *15 min:* time your own slides; know who speaks before and after you (speaking order).
+ *20 min:* the 16 questions: cover the answers and answer aloud. Then read your row in the table above and the black-book pages for your slides.

#note(title: "Golden rules in front of the examiner")[
- Say "we measured", not "we proved". Every number is in the black book; never invent one.
- If you do not know: "I'd have to check; it is in the report, section …" is better than guessing.
- Mention the weaknesses (slides 20, 24) yourself; examiners respect it.
- It is a *research prototype*, not a product for real spraying.
]
]
