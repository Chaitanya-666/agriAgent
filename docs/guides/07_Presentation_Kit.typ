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
  [*4. It works*], [Slide 17: demo (live or the screenshots on the slide).],
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

#slide(17, "EXPLAIN", 75, "Demo",
  [Live demo (if the laptop is ready) *or* talk over the two screenshots: "Left: Grounded SAM alone. Scores 0.36–0.47 are below 0.70, so *nothing is sprayed: crop safe, weeds missed*. Right: our verdict view: *red sprayed, green protected crop, yellow left alone*." The department allows results instead of a video.],
  ask: [Is it real? The app shows a REAL banner; mock output is always labelled MOCK.],
  book: "§5.12, pp. 27–28, Figs. 5.2–5.3")

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
= The 15 questions most likely to come
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
#qa[What did *you* do?][Give *your* line from Table B.1 (p. 50) and the next section. Never claim a part you did not build.]
#set text(10.5pt)

#pagebreak()

// ─────────────────────────── AUDIENCE-SPECIFIC ───────────────────────────
#if me [
= Your part: vision pipeline, workflow, safety gate
You are the team lead (Table B.1). Expect the hardest questions on *slides 11–13, 18–22, 24*. Deep-dive answers:

#qa[Why ¼ of the median crop plant?][It calibrates itself per photo and was set by design, never tuned on the held-out labels. Weeds in this data are tiny (median about 16 px across vs 68 px for crops).]
#qa[Why naive Bayes in the agent?][Simple and explainable; each source's measured accuracy (row 0.65, Clef 0.70, Qwen 0.80) caps its influence. It assumes independent errors, which is optimistic, so the 0.85 bar is strict.]
#qa[Complexity?][Vegetation, closing, components and rows are linear in the number of pixels; run time is dominated by the two networks (≈ 0.21 s detection, 0.27–0.37 s segmentation).]
#qa[Why the tiny models?][Both fit in 8 GB with headroom (peak ≈ 2.4 GB) and run in about 0.6 s per photo; also verified on Amit's 4 GB RTX 3050.]
#qa[Where is the gate in the code?][`src/agents/deterministic_router.py` and `src/workflow.py`; each rule has unit tests.]

= Your checklist before Thursday
#table(
  columns: (auto, 1fr),
  [When], [What],
  [*Tue 17 eve*], [Read page 1 twice, then slides 1–13 of this guide with the deck open. CPAD exam prep comes first (other session).],
  [*Wed 18 morning*], [Meet Prof. Dhore *before the CPAD exam (13:30)*. Show the report PDF + PPT. Ask: (1) approval of both; (2) plagiarism check (< 30%); (3) how many black-book copies; (4) Thursday's time and whether each student presents separately; (5) *tell him your Deep Learning lab exam is Thu 19, 9:00–17:30* and ask for a slot that fits.],
  [*Wed 18 after CPAD*], [Send me any changes he asks for; I rebuild the PDF. Then print and bind (front matter pages i–iv get signatures by hand).],
  [*Thu 19*], [Before your slot: read page 1 and the 15 questions once. Laptop charged, deck opened in presenter view.],
)
#warn(title: "Clash")[Your DL lab exam (Lab 1B, 9:00–17:30) is on the same day as the external examiners. Sort out the timing with Prof. Dhore and the DL faculty on Wednesday.]
] else [
= Your part and what you may claim
Every member presents the whole deck with the plan above, then answers questions on their own part.
Claim only your real role, exactly as printed in the black book (Table B.1, p. 50):

#table(
  columns: (auto, 1fr, auto),
  [*Member*], [*Role in the black book*], [*Expect questions on*],
  [Chaitanya Shinde (lead)], [Research questions and method; vision pipeline, safety gate, plant rules, escalation agent, System 2 and ICAR store, app, evaluation, experiments, tests, report and slides.], [11–13, 18–22, 24],
  [Amit Ingle], [First Streamlit dashboard; system test cycles 0 and 2 (24/24 on Windows 11, RTX 3050); packaging bug report; v1.0.0 release; live demo.], [16, 17, 25],
  [Sumant Vetal], [First version of the System 2 agronomy module (diagnosis and herbicide advice), later rewritten and integrated.], [14, ICAR],
  [Sahil Chavan], [The dataset downloader used to fetch the public datasets.], [15, 20],
)

= How to prepare in 90 minutes
+ *15 min:* page 1 of this kit, twice. Say the 4 sentences aloud without looking.
+ *40 min:* open the deck next to this kit; go slide by slide and say the lines aloud.
+ *15 min:* one full run with a timer. Check the clock marks (slide 10 by 5:00, 17 by 9:30, 22 by 12:30).
+ *20 min:* the 15 questions: cover the answers and answer aloud. Then read your row in the table above and the black-book pages for your slides.

#note(title: "Golden rules in front of the examiner")[
- Say "we measured", not "we proved". Every number is in the black book; never invent one.
- If you do not know: "I'd have to check; it is in the report, section …" is better than guessing.
- Mention the weaknesses (slides 20, 24) yourself; examiners respect it.
- It is a *research prototype*, not a product for real spraying.
]
]
