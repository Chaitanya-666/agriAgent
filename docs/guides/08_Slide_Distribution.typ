// Who presents which slide at the FYP external evaluation (Thu 19 Nov 2026), and where every file lives.
//   typst compile --root .. 08_Slide_Distribution.typ 08_Slide_Distribution.pdf
#import "../template.typ": *
#show: doc.with(
  title: "AgriAgent: Slide Distribution and Files",
  subtitle: "Who presents what on Thursday 19 November, and where to find everything",
  date: "17 November 2026",
)
#set heading(numbering: none)
#set text(9.6pt)
#let gh(path) = link("https://github.com/Chaitanya-666/agriAgent/blob/chaitanya/blackbook-latex/" + path)[GitHub]

= The files
#table(
  columns: (auto, 1fr, auto),
  [*File*], [*What it is*], [*Online*],
  [`AgriAgent_FYP_Presentation.pptx`], [The deck: 30 slides, department order. *Speaker notes* on every slide hold the lines to say (PowerPoint → presenter view). PDF copy: `AgriAgent_FYP_Presentation.pdf`.], [#gh("docs/slides/AgriAgent_FYP_Presentation.pptx")],
  [`AgriAgent_FYP_Report.pdf`], [The black book, 63 pages, LaTeX. Print and sign *after* Prof. Dhore approves it.], [#gh("docs/report_latex/main.pdf")],
  [`AgriAgent_Presentation_Kit_Team.pdf`], [Preparation kit: every slide with what to say, the likely questions, every number explained, the black-book map.], [#gh("docs/guides/07_Presentation_Kit_Team.pdf")],
  [`AgriAgent_Slide_Distribution.pdf`], [This page.], [#gh("docs/guides/08_Slide_Distribution.pdf")],
)
#text(8.5pt, fill: muted)[Repository: github.com/Chaitanya-666/agriAgent, branch `chaitanya/blackbook-latex`. In the repo: deck `docs/slides/`, report `docs/report_latex/main.pdf`, kits `docs/guides/07_Presentation_Kit_*.pdf`. If the department evaluates each student *alone* for 15 minutes, everyone presents all 30 slides with the plan on page 1 of the kit instead.]

= Who presents what
*Speaking order:* Chaitanya 1–3 → Sumant 4–10 → Chaitanya 11–13 → Sumant 14 → Amit 15–16 → Chaitanya 17 (Amit runs the demo) → Amit 18–19 → Sahil 20–21 → Chaitanya 22 → Amit 23–25 → Chaitanya 26 → Sahil 27–30. Hand over with "… and now X will explain …".

#let part(name, count, time, rows) = block(breakable: false, below: 8pt)[
  #text(11pt, weight: "bold", fill: accent)[#name] #h(4pt) #text(9pt, fill: muted)[#count slides · about #time]
  #table(columns: (auto, auto, 1fr), [*Slide*], [*Title*], [*Main points*], ..rows)
]

#part("Chaitanya Shinde", 9, "6.5 min", (
  [1], [Title], [Introduce the four members and Prof. V. D. Dhore; the project title.],
  [2], [Motivation], [Whole-field spraying though weeds are patchy; the decision weed-or-crop is the bottleneck; spraying the crop is the costly mistake.],
  [3], [Why zero-shot + problem], [Trained models need labels per field; Grounded SAM promises none; read the problem statement.],
  [11], [Architecture], [Detect → segment → plant rules → *safety gate* → app/GeoJSON; System 1 decides locally, System 2 only advises.],
  [12], [Safety gate], [Plain code; spray only if every rule passes (weed label, ≥ 0.70, ≥ 0.85, ≤ 50%, ≤ 85%); any doubt → no spray.],
  [13], [Plant rules], [Crop if in a crop mask or on the row; weed if small or off-row; else unsure, never sprayed; frozen, tested once.],
  [17], [System walkthrough], [One real photo, five steps; 31 of 36 weeds hit, 0 of 3 beets touched.],
  [22], [Headline result], [90 unseen photos: 77.9% weeds hit, 8.8% crop sprayed vs 1.8% / 65.5%; 95% herbicide saved.],
  [26], [Conclusion], [Labels fail; agent safe but adds nothing; rules + gate recover most; research prototype.],
))

#part("Sumant Vetal", 8, "3.5 min", (
  [4], [Survey 1/4], [Closest work WaW: 12.1% vs 62.7% weed IoU; Grounded SAM = our pipeline; VLMs 0.15–0.75, advise only.],
  [5], [Survey 2/4], [Supervised networks need labels per field; they drop on new fields.],
  [6], [Survey 3/4], [Excess-green index = our first step; our cotton data comes from Rahman 2023.],
  [7], [Survey 4/4], [Planting rows replace labels; AI advice must be grounded, so doses only from ICAR.],
  [8], [Literature gaps], [G1–G5; G2 and G3 = our research gap; G4 = our design contribution.],
  [9], [Base paper], [Grounded SAM, implemented with SAM 2; we do not claim to beat WaW.],
  [10], [Objectives], [Six objectives; research questions RQ1–RQ3.],
  [14], [Agent + ICAR advice], [Agent asks row rule → Clef → Qwen, advice only; doses only from the ICAR bulletin; EN/HI/MR summary.],
))

#part("Amit Ingle", 7, "3 min + live demo", (
  [15], [Datasets], [Sugar beet 120 photos (30 + 90), cotton 8, ICAR bulletin; links on the slide.],
  [16], [Implementation], [Python; tiny models on an 8 GB GPU; Cloudflare free tier; Streamlit; 270 tests; v1.0.0.],
  [17], [Live demo], [During Chaitanya's slide: upload photo → spray map → every-plant view → Hindi summary.],
  [18], [Maths 1/2], [ExG = 2G − R − B; Otsu threshold; row test; the piecewise rules.],
  [19], [Maths 2/2], [Gate as an AND; agent odds example 0.70 & 0.80 → 0.90; the 5×5 metric example.],
  [23], [Agent results], [69 plants: no crop approved, 13/14 right, 0/25 weeds; Groq 16/20 vs Cloudflare 12/20.],
  [24], [Limitation F1], [Rotated photo: no crop found → largest beet sprayed; size-limit trade-off.],
  [25], [Testing], [270 tests; three manual cycles; 24/24 on Windows; rice dose fix.],
))

#part("Sahil Chavan", 6, "1.5 min", (
  [20], [Evaluation method], [Fabricated labels found and replaced; 30 design photos + 90 held out, run once.],
  [21], [RQ1 baseline], [Masks hit 97.6% of weeds but labels fail: 70.8% crop at 0.35, nothing at 0.70.],
  [27], [Future scope], [PhenoBench comparison, BioCLIP, safe mode, few-shot, field trial.],
  [28–30], [References], ["51 references in IEEE format." Then: "Thank you, we are happy to take questions."],
))

= Everyone, before Thursday
- Read page 1 of the kit, then say *your* slides' lines aloud three times with the deck open; time yourself.
- Bring *your own printed, signed black book* (department rule); the team also brings one for Prof. Dhore and one for the department.
- In questions, claim only your role as printed in Table B.1 (p. 50). If unsure: "It is in the report, section …".
- If someone is absent, Chaitanya presents their slides with the same lines.
