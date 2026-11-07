#import "template.typ": *
#show: doc.with(
  title: "AgriAgent: project update and questions",
  subtitle: "For Prof. V. D. Dhore · work since 30 October 2026, final submission, packaging and publication",
  date: "7 November 2026",
)
#show table: set par(justify: false)
#let qtable(..rows) = {
  show table.cell.where(y: 0): set text(weight: "regular")
  table(columns: (auto, 1fr), ..rows)
}

#block(inset: (bottom: 4pt))[
  *Team:* Chaitanya Shinde (231070066, lead) · Sumant Vetal · Sahil Chavan · Amit Ingle \
  *Repository:* #link("https://github.com/Chaitanya-666/agriAgent")[github.com/Chaitanya-666/agriAgent] (public; 31 pull requests merged) \
  *Previous updates:* written progress report of 17 October; WhatsApp of 30 October (base paper and report format).
]

#note(title: "Why this document")[
  On 30 October we asked about the base paper and the department's report format. We have
  continued meanwhile, and the project is now close to final: code frozen except for fixes, final
  report drafted, slides ready, last test cycle running. We publish the release on *Wednesday 11
  November* and finish everything by *Friday 13 November* (lab exams start on 16 November), so we need your decisions on the questions in Section 7. Each
  question has a number, so a short reply such as "Q1 Monday 23 Nov, Q4 yes" is enough.
]

= Status in one page

#table(
  columns: (1.3fr, auto, 2fr),
  [Part], [Status], [Evidence],
  [Vision pipeline (Grounding DINO + SAM 2) on our laptop GPU], [#real], [0.6 s per photo on an RTX 5050 (8 GB); deterministic; reproduces exactly from a fresh clone.],
  [Safety gate + plant rules (the product)], [#real], [Held-out 90 photos, evaluated once: *77.9% weed recall, 8.8% crop pixels sprayed* (Grounded SAM baseline: 1.8% / 65.5%).],
  [Escalation agent (RQ2)], [#real], [Measured on 69 plants: never sprayed a crop plant, but added no weeds. Safe, not effective.],
  [ICAR herbicide advice], [#real], [Every table row checked against the bulletin PDF; a wrong rice dose found and fixed; first real prescription on a test photo.],
  [Application (Streamlit) + GeoJSON + farmer summary in EN/HI/MR], [#real], [Manual test cycle on six photos; 29 findings fixed or documented.],
  [Final report], [#partial], [33-page draft (Typst/PDF). Waiting for the department format and roll numbers.],
  [Viva slides], [#real], [14 slides with speaker notes, PowerPoint and web versions.],
  [Last system test cycle], [#partial], [Amit Ingle, 7–10 November; fixes and release on 11 November.],
  [Research paper], [#planned], [Not started; depends on your answer to Q14–Q20.],
)

*Main finding.* Text-prompted zero-shot segmentation (Grounded SAM) does not separate crop from
weed: on held-out photos it sprays two thirds of the crop while hitting almost no weeds, and with our
0.70 confidence gate it sprays nothing. A small set of transparent rules (crop-mask overlap, planting
row, size relative to the crop) with a deterministic safety gate recovers most of it, with no
training and no model calls. This agrees with the closest published work (Chong et al., IROS 2025:
zero-shot weed IoU 12.1% against 62.7% supervised).

= What we did since 30 October

#table(
  columns: (auto, 1fr),
  [Date], [Work (each item is a merged pull request with tests)],
  [30 Oct], [Reasoning model moved from Groq to Cloudflare Workers AI (same Qwen 3.8 model): Groq's free tier returned rate-limit errors on back-to-back runs. Photos are now resized before upload (one photo had cost 12,349 tokens).],
  [30 Oct], [Manual test cycle MT-01 … MT-10 on six photos with official labels, in real mode. Fixed: GeoJSON map upside down and at a wrong scale (1.1 m per pixel turned a close-up into a 560 m field); a warning when the declared crop does not match the photo; the app re-running the models on every click; Hindi summary calling sugar beet "sweet potato" (glossary added).],
  [30 Oct], [Bibliography checked against the sources: several AI-generated references could not be found and were removed; Grounded SAM and PhenoBench added. Cotton photo CM_17 produced the first real ICAR prescription (pyrithiobac-sodium 75 g a.i./ha, bulletin p. 35).],
  [7 Nov], [Fixes F24–F29: models now load once per process under a lock (an intermittent crash, "Cannot copy out of meta tensor", and 14 s saved per run); the previous result no longer stays on screen during a new run; the wrong-crop warning and "this is a suggestion, read the label" are fixed translated sentences that the language model cannot drop; a new view colours every plant by its verdict (sprayed / protected as crop / left alone), which makes failures visible.],
  [7 Nov], [Final report draft (33 pages), viva slides (14), Test Cycle 2 guide for Amit (results due 10 November).],
)

Automated tests: 270 (235 unit, 35 end-to-end), run on every push on Python 3.10 and 3.11.

*Earlier, for context (18–23 October, after the 17 October report):* baseline on 38 photos with
official labels; crop-mask exclusion and detector variants measured; plant rules developed, frozen and
run once on 90 held-out photos; escalation agent measured; ICAR table checked against the bulletin;
verification run from a fresh clone (held-out numbers reproduced exactly; 13 findings).

= Key results

#table(
  columns: (1.6fr, auto, auto, auto),
  [Held-out sugar beet, 90 photos (363 beets, 215 weeds)], [Crop pixels sprayed], [Weed recall], [Beets touched],
  [Grounded SAM label policy, confidence ≥ 0.35], [65.5%], [1.8%], [242],
  [Grounded SAM, deployed gate 0.70], [0.0%], [0.0%], [0],
  [Grounded SAM + crop-mask exclusion, 0.50], [5.5%], [0.0%], [24],
  [*Plant rules v3 + gate (our product)*], [*8.8%*], [*77.9%*], [104 (mostly edge specks)],
)

- *Cotton* (8 photos): the rules reach only 10.4% weed recall, because they assume weeds are smaller than the crop, true for young sugar beet, not for cotton close-ups.
- *Escalation agent* (69 withheld plants): 0 crop plants approved for spraying, 13 of 14 "crop" verdicts right, but 0 of 25 weeds called weed.
- *Same model, two providers:* Qwen 3.8 answered 16/20 labelled patches correctly on Groq and 12/20 on Cloudflare.
- *Main known weakness (F1):* a whole beet off the planting row is sprayed when the detector misses its crop box. A size limit cuts crop damage to 0.25% but recall to 13%; we kept the frozen rules and report the trade-off.

= Problems we faced, and what we did

#table(
  columns: (1.2fr, 1.6fr),
  [Problem], [What we did],
  [AI-written documents and code early in the project claimed results that did not exist ("100% complete", 227 tests, a "0.99 IoU" that was a confidence score).], [Every claim now carries a status label (REAL / PARTIAL / MOCK / PLANNED) and a command output; earlier claims withdrawn in the report.],
  [The first evaluation set had fabricated labels (the same boxes on every photo).], [Replaced by labels copied by script from the official dataset files; a held-out set evaluated exactly once.],
  [Failed model loads silently switched to fake output; the safety gate received confidence hard-coded as 1.0.], [Real mode now fails loudly; every gate rule has tests with real values; REAL/MOCK banner on every screen.],
  [Text prompts cannot separate crop from weed (the research problem itself).], [Measured honestly as RQ1; added plant rules; reported the trade-off.],
  [Hardware: 8 GB GPU; RTX 5050 needs CUDA 12.8; transformers 5.x changed the SAM 2 API.], [Tiny model variants (2.4 GB peak); pinned lock file of the tested versions; code updated.],
  [Free cloud tiers: rate limits (Groq), different answers per provider.], [Moved to Cloudflare; agent off by default; trust weights tied to the provider measured.],
  [Errors in the herbicide table (rice dose 20 g against a 15 g maximum, waiting period 20 days short).], [Every row checked against the bulletin pages; regression tests.],
  [Small public datasets; the sugar beet uploader does not document its origin; cotton labels only weeds.], [Stated as a limitation; metrics designed for box labels.],
  [Translation quality in Hindi/Marathi (wrong crop word, dropped safety sentence).], [Glossary; safety sentences as fixed text.],
)

= What is ready for the final submission

#table(
  columns: (auto, 1fr),
  [Item], [State],
  [Final report], [`docs/thesis/AgriAgent_Final_Report.pdf`, 33 pages: certificate, declaration, abstract, 8 chapters (introduction, literature review with base paper, design, implementation, data and method, results, testing, discussion and conclusion), references (only checked sources), appendices.],
  [Slides], [`docs/slides/AgriAgent_Final_Viva.pptx`, 14 slides with speaker notes (about 20 minutes plus demo).],
  [Source code], [Public GitHub repository; `scripts/package_release.py` builds a source zip from a tagged commit and checks it for secrets (no keys, data or model weights inside). Planned tag: `v1.0.0` on 11 November.],
  [Reproducibility], [Lock file of exact versions; script downloads the model weights (1.7 GB); scripts rebuild the evaluation sets from Kaggle; every result table names its result file.],
  [Demo], [Live app on our laptop (needs internet only for the Hindi/Marathi summary and diagnosis); a recorded backup video by 10 November.],
)

= Who did what

Counted from the repository at commit `6e2552a` (7 November): commits without merge commits
(`git log`), current Python code by its last author (`git blame`), pull requests and issues on
GitHub. The same record is Appendix B of the report, a slide in the deck, and `CONTRIBUTIONS.md` in
the repository (regenerated by `scripts/contributions.py`).

#table(
  columns: (1fr, auto, auto, auto, 2.2fr),
  [Member], [Commits], [Current code], [PRs / issues], [Contribution],
  [Chaitanya Shinde (lead)], [94 of 97], [97.4%], [21 / 1], [Research questions and direction; vision pipeline on the local GPU; safety gate; plant rules; escalation agent; System 2 integration; ICAR table check; farmer summary; GeoJSON; evaluation sets from official labels; all measurements; verification and manual test cycles; fixes F1–F29; final report, slides and all documents.],
  [Amit Ingle], [1], [1.4%], [1 / 8], [First Streamlit dashboard (4 Oct); system test cycle 0 on a fresh Windows install (8 issues filed); test cycle 2 on the final build (7–10 Nov), fixes and release (11 Nov).],
  [Sumant Vetal], [1], [1.3%], [1 / 0], [First version of the System 2 code (VLM critic, ICAR store, prescription; 5 Oct).],
  [Sahil Chavan], [1], [0%], [1 / 0], [Dataset downloader and a small fixture sample (4 Oct).],
)

= Questions for you

*Report and submission (repeated from 30 October)*

#qtable(
  [Q1], [What are the dates of the final submission and of the viva? (We planned around 10 November earlier; we now release on 11 November and finish by 13 November.)],
  [Q2], [Is there a department report template or format: page size, margins, font, line spacing, page limit, chapter list (e.g. SRS, UML diagrams, Gantt chart, cost estimate), certificate wording? May we submit our own typeset PDF if it follows that format, or must it be in Word?],
  [Q3], [How many printed copies, binding type, and to whom? Is a soft copy (PDF) uploaded somewhere?],
  [Q4], [Is a plagiarism check required? With which tool and what maximum similarity?],
  [Q5], [Is our base paper choice acceptable: *Grounded SAM* (Ren et al., 2024, arXiv 2401.14159) as the pipeline we implement, and *Chong et al., "Zero-Shot Semantic Segmentation for Robots in Agriculture", IROS 2025* as the peer-reviewed comparison point? Do you expect us to reproduce the base paper's own numbers?],
  [Q6], [Is the narrowed scope acceptable for evaluation (weed versus crop only; disease, yield, canopy and nutrient stress from the proposal as future work), and are honest negative results (escalation agent not effective) acceptable as answers to research questions?],
)

*Viva and demo*

#qtable(
  [Q7], [Viva format: presentation length, demo expected, does each member present a part, who is on the panel (external examiner)?],
  [Q8], [Is a live demo on our own laptop fine, with a recorded video as backup? Will internet be available in the room (needed only for the cloud reasoning model)?],
  [Q9], [How are individual contributions assessed in the viva and in the marks? Is the evidence-based table in Section 6 (also Appendix B of the report) the right way to show them, or do you need a separate signed contribution statement per member?],
)

*Packaging and keeping the project available*

#qtable(
  [Q10], [What form should the code be submitted in: GitHub link, source zip, CD/DVD, or the department's drive? We propose the tagged GitHub release `v1.0.0` plus the source zip.],
  [Q11], [The repository is public but has no licence yet. May we add an open-source licence (we suggest MIT), or does the institute need to approve, or keep rights?],
  [Q12], [Model weights (1.7 GB) and datasets are not in the repository (downloaded by script; the datasets are third-party Kaggle uploads). Is that acceptable, or must they be submitted on media?],
  [Q13], [Should we archive the release with a permanent DOI (e.g. Zenodo, free, linked to GitHub) so it can be cited in a paper?],
)

*Research paper and publication*

#qtable(
  [Q14], [Is a research paper (published or submitted) required for the final-year project or for grading? If not required, do you recommend writing one?],
  [Q15], [If yes: which venue do you suggest: an IEEE or Springer conference (which one, and its deadline), a Scopus-indexed journal, or a VJTI / student conference? We want to avoid paid or predatory venues.],
  [Q16], [Is our contribution enough for a paper: an honest evaluation of Grounded SAM for spot spraying, a transparent rule-based safety layer (77.9% weed recall at 8.8% crop on held-out photos), and a negative result for VLM escalation?],
  [Q17], [For a paper we would add one experiment comparable to the literature: weed IoU on the public PhenoBench validation set (772 pixel-labelled images), about one day of work. Should we do this before 13 November, or after the exams?],
  [Q18], [Authorship: author order, and may we include your name as guide and corresponding author?],
  [Q19], [Format and length: IEEE two-column, about 6 pages? Should the paper be submitted before or after the viva, and may it reuse text from the report?],
  [Q20], [Should we post a preprint on arXiv after submission, or wait for acceptance?],
)

*Method decisions*

#qtable(
  [Q21], [Finding F1 (whole off-row beets can be sprayed): keep the frozen rules and report the trade-off (our choice, because no unused held-out data is left), or add the "safe mode" size limit as an option evaluated on the development set only?],
  [Q22], [Is the small evaluation (120 sugar beet + 8 cotton photos from public datasets) acceptable, or should we add more photos (for example PhenoBench) before submission?],
  [Q23], [Anything you want added to or removed from the report or slides before we freeze?],
)

#v(6pt)
We are available for a short call or a meeting at any time before 13 November; even a two-minute
call to answer Q1–Q4 would unblock the report.

*Attached / in the repository:* final report draft (PDF), slides (PPTX), this document.
