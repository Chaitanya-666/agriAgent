#import "template.typ": *
#show: doc.with(
  title: "AgriAgent Progress Report",
  subtitle: "For Prof. V. D. Dhore · everything from the proposal to 17 October 2026, and the plan to 10 November",
  date: "17 October 2026",
)

#show table: set par(justify: false)
#let fig(path, caption, width: 100%) = figure(image(path, width: width), caption: caption)

#block(inset: (bottom: 4pt))[
  *Team:* Chaitanya Shinde (231070066, Track 1, team lead) · Sumant Vetal (Track 2) · Sahil Chavan
  (Track 3) · Amit Ingle (Track 4) \
  *Guide:* Prof. V. D. Dhore, Department of Computer Engineering, VJTI \
  *Repository:* #link("https://github.com/Chaitanya-666/agriAgent")[github.com/Chaitanya-666/agriAgent]
  (about 60 commits, 7 merged pull requests, 13 issues) · *Final submission and viva:* Tuesday 10 November 2026
]

#note(title: "Why this report")[
  We have not been able to meet for the last two weeks. This report tells the whole story in one
  place: what we proposed, what we built, what went wrong and why, what we changed, what is proven
  today, how we compare with published work, and what remains. Every claim carries a status label:
  #real (run with real models on real images, evidence exists), #partial (code exists and is tested,
  not yet measured end to end), #mock (only run with fake model outputs), #planned (not built).
]

= The project today, in one page

*AgriAgent is a research prototype that asks one question: how well can zero-shot foundation models
tell weeds from crop plants in a field photo, and can a safety gate plus a reasoning model keep the
crop off the spray map?*

The system takes a field photo and a text prompt, finds and outlines plants with two pretrained
models (Grounding DINO [1] and SAM 2 [2], no training on our data), decides with plain, testable
rules which outlines may be sprayed, asks a vision-language model when it is unsure, and outputs a
spray map that should cover weeds only. It does not drive a sprayer or a drone; the output is a map
on screen and a file.

*Research questions*

#table(
  columns: (auto, 2.2fr, 1fr),
  [\#], [Question], [Status],
  [RQ1], [How well do zero-shot detection and segmentation separate weed from crop? Measured as weed recall and *the share of crop pixels that end up on the spray map*.], [first real runs done; measurement on 38 images due 25 Oct],
  [RQ2], [Does escalation help? When the deterministic gate is unsure and asks a vision-language model, is the spray map safer and more complete?], [model accuracy measured on 20 patches; effect on the map not yet measured],
  [RQ3], [Which cheap addition reduces crop on the map most (naming the crop in the prompt and subtracting crop masks, a planting-row rule, a model second opinion), and what does it cost in missed weeds?], [planned for 26 Oct – 1 Nov],
)

*What is proven on 17 October*

- The real pipeline runs on our own laptop (RTX 5050, 8 GB): both models real, 2.4 GB peak GPU memory. #real
- On a sugar beet photo, the *original* system labelled all four crop plants "weed" and sprayed them; the two real weeds were missed. #real
- After our gate fixes, low-confidence detections are withheld: the same photo now sprays nothing, so the crop is protected, but the weeds are still missed. #real
- Our earlier evaluation labels were fabricated; they were replaced with labels copied from the official datasets (38 images). #real
- On 20 labelled plant patches, a cloud vision-language model (Groq `qwen/qwen3.8-27b`) answered "crop or weed?" correctly 16 times, Cloudflare Clef Flash 14 times, a model-free row rule 13 times. #real

*Main finding so far:* text prompts alone do not separate weed from crop. This matches the published
state of the art: the best zero-shot crop-weed method we found reaches about 12% weed IoU, against
about 63% for a supervised network (Section 8). Our contribution is therefore to *measure* this
honestly on our data, add a safety gate that keeps uncertain plants off the map, and test which
cheap additions help.

= From the proposal to a research prototype

The proposal (30 September, `AgriAgent_Master_Project_Proposal`) described a much larger system. We
narrowed it because the large version could not be built and *proven* in the time and on the hardware
we have, and because our first real result showed that the core problem is unsolved.

#table(
  columns: (1fr, 1fr),
  [Proposal (30 Sep)], [Today (17 Oct)],
  [Five applications: weeds, disease, yield counting, canopy cover, nutrient stress.], [One application: weed versus crop for spot spraying. The other four are future work.],
  [Drone or tractor spray routes, GPS coordinates, PDF prescriptions, cloud deployment.], [A spray map on screen and a GeoJSON file with placeholder coordinates, clearly labelled as not GPS.],
  [System 1 = the "Laya" decision library (sub-50 ms routing).], [System 1 = plain deterministic rules (`DeterministicRouter`); Clef Flash (Cloudflare) as an advisory triage model (Section 5).],
  [System 2 = Llama-3.3-70B / Qwen3-VL / InternVL with ICAR RAG.], [System 2 = Groq `qwen/qwen3.8-27b` with the image, plus a lookup in the ICAR herbicide table for the declared crop.],
  [Built on the SmartDesk multi-agent framework (LangGraph supervisor, artifacts).], [SmartDesk agents removed; a fixed six-step pipeline remains. The shared state object and artifacts were kept.],
  [Claims: "zero retraining", "millimetre accuracy", "over 70% chemical saving", "< 40 ms".], [None of these was measured. They are replaced by measured numbers or labelled as targets.],
  [Evaluation on 100 verified cotton images with bootstrapped confidence intervals.], [Evaluation on 38 images with official labels (30 sugar beet, 8 cotton); intervals planned for the final tables.],
  [Deadline end of October; 4-week sprint.], [Submission and viva 10 November; freeze 5 November.],
)

*What we kept from the proposal:* zero-shot detection and segmentation with Grounding DINO and SAM
2; the refinement loop (re-prompt SAM 2 with a corrective point when its predicted quality is below
0.85); a deterministic safety layer as the final authority; escalation to a reasoning model; herbicide
advice grounded in the ICAR bulletin; and the cross-crop idea, now tested as "the same unchanged
pipeline on sugar beet and on cotton".

= Timeline from the repository history

#table(
  columns: (auto, 1fr),
  [Date], [What happened (commit evidence in the repository)],
  [16 Aug], [Repository created from the earlier *SmartDesk* project (an unrelated productivity assistant).],
  [30 Sep], [Proposal written; team roles locked (4 tracks); README and workspace cleaned.],
  [3 Oct], [16 commits in one day: SmartDesk agents stripped; Grounding DINO and SAM 2 wrappers with a mock mode; the workflow; the Laya router; Kaggle and Colab notebooks. *First and only real run until 17 Oct* on a Kaggle T4 GPU (Figure 1).],
  [4–5 Oct], [Teammates' pull requests: Streamlit dashboard (Amit), dataset downloader and 20 fixture images (Sahil), VLM critic, ICAR knowledge store and prescription (Sumant). GitHub Actions CI added.],
  [11 Oct], [An AI-assisted "v0.2.0" release claimed 100% completion, 227 verified tests and real metrics. A same-day review found these claims false (Section 4). Honesty reset: repository decluttered, one Project Map, status labels, model choices frozen, study guides.],
  [12 Oct], [Delivery schedule with tasks per member; Clef Flash found to be hosted by Cloudflare; model setup guide.],
  [12–14 Oct], [Repository frozen while the team studied the codebase.],
  [16 Oct], [Cycle 0 system test runbook. Amit's fresh-install test: 16 app test cases, 7 pass, 9 fail; 8 GitHub issues filed.],
  [17 Oct], [First real run on our own laptop; six faults fixed on the way; evaluation labels audited and replaced; crop-or-weed comparison; all 8 Cycle 0 issues fixed, re-tested and closed (PRs \#14, \#15, \#16).],
)

= What went wrong, and what we learned

We list our mistakes openly because each one changed how we work.

+ *Starting from an unrelated codebase.* Copying SmartDesk saved a scaffold but left mail, calendar and chat-bot code and documents that confused everyone for two weeks.
+ *AI-written documents that described intent as fact.* Several generated dossiers called Week 1 and Week 2 "100% complete" and "verified", reported 227 tests (the real count was 175), even misspelled team members' names, and presented a "0.99 IoU" that was in fact SAM 2's own confidence score, not overlap with any ground truth. *Lesson:* no status claim without a command output; every claim now carries a status label.
+ *Fabricated evaluation labels.* The 20-image evaluation set added on 11 October looked real but was a template: every sugar beet image had the same 2 crop + 6 weed boxes, and every cotton image had a cotton box although the official cotton dataset labels no cotton at all. Only 1–2 of 8 boxes matched the official labels per beet image, and none per cotton image (Figures 5 and 6). A metric reported on it (zero-shot IoU 0.089 improved to 0.0995) was meaningless. *Lesson:* ground truth is copied from official files by a script, and audited.
+ *Code that silently produced fake output.* When model weights failed to load, the vision code switched to mock boxes without telling anyone; every real SAM 2 mask got a made-up quality score of 0.88 because the code read a field that does not exist; the reasoning model never received the photo; the app showed mock diagnoses as "VERIFIED & APPROVED". *Lesson:* a real run must fail loudly, and the screen must say REAL or MOCK.
+ *A safety gate that did not use its inputs.* The gate was called with confidence and mask quality hard-coded to 1.0, so a low-confidence "weed" was always sprayed, and the herbicide lookup ignored the crop, recommending a cotton herbicide for wheat, rice and sugar beet.
+ *Changing models too often.* The plan moved from Qwen2.5 to Qwen3.5 to qwen3.8, and from Laya to Clef, partly driven by AI agents' suggestions. Model choices are now frozen and changed only by a recorded team decision.
+ *Uneven team progress.* Two of four members delivered their Week 3 tasks; the lead absorbed the missing work. The new task list (`docs/AgriAgent_Team_Tasks.pdf`) gives exact steps and adds part of Week 5 to the members who fell behind.

= Why the triage router moved from Laya to Clef Flash

The proposal's "System 1" was meant to be a fast, non-generative decision engine: it answers typed
questions (is this mask good enough? is this escalation needed?) in one pass instead of generating
text. Our first choice was *Laya*, an open-source library described as a "System One" decision model
(ConvAI Innovations, Apache 2.0). It was wrapped on 3 October with a fallback for when the package was
missing. The repository holds no record of Laya ever producing a real decision: the wrapper ran its
fallback, and the notebook cell that used it would have crashed after later changes.

In Week 2 we separated the *safety decision* from the *advisory triage*:

- The safety decision moved to `DeterministicRouter`: plain rules (confidence ≥ 0.70, mask quality ≥ 0.85, infestation ≤ 85%). Rules are instant, offline and testable, which a sprayer needs.
- Advisory triage moved behind a common router interface, with *Clef Flash* as the model. Clef Flash is Cloudflare's model built on the same "System One" idea: it takes a state and typed yes/no or multiple-choice questions and returns probabilities. Cloudflare hosts it free with image input (10,000 "neurons" per day) [16], whereas the downloadable version (6.5 GB) cannot share our 8 GB GPU with the vision models and accepts no images.

Clef Flash only advises; any error means "escalate, never spray". On our 20 labelled patches it
answered 14 correctly (Section 7). Wiring it into the workflow is task T2.8.

= The system as it is now

#grid(
  columns: (1fr),
  row-gutter: 3pt,
  stage("1. Detect: Grounding DINO-tiny (local GPU)", "Prompt 'weed . <crop> plant .' Boxes with a label taken from the prompt words and a confidence score."),
  down,
  stage("2. Segment: SAM 2-tiny (local GPU)", "Turns each box into a pixel mask with a predicted quality score; re-prompts with a corrective point if quality < 0.85."),
  down,
  stage("3. Gate: deterministic rules", "A mask is sprayed only if its label is a weed (not a crop word, not a mixed label), confidence ≥ 0.70 and quality ≥ 0.85; the whole map is suppressed above 85% infestation. Everything else is withheld and listed with a reason."),
  down,
  stage("4. Escalate: System 2 (Groq qwen3.8-27b, cloud)", "When detections are uncertain: the model looks at the photo and names crop, weed and growth stage; the herbicide comes only from the ICAR table row for the declared crop, otherwise 'no evidence'."),
  down,
  stage("5. Output: Streamlit app + GeoJSON", "REAL/MOCK banner, approved zones only, one feature per weed zone, coordinates labelled as placeholders."),
)

#table(
  columns: (1fr, auto, 1fr),
  [Component], [Status], [Evidence],
  [Grounding DINO + SAM 2 on our laptop], [#real], [3 real runs, 2.4 GB peak GPU, about 45 s per image including model loading.],
  [Deterministic gate with real confidence], [#real], [Withholds low-confidence masks on real images (Figure 3); 192 unit and 35 end-to-end tests.],
  [System 2 diagnosis with Groq], [#real], [Diagnoses real photos; the herbicide lookup runs from the built-in ICAR table, the full PDF store is not loaded in real mode yet.],
  [Clef Flash triage], [#partial], [Answers on its own (14/20 patches); not yet inside the workflow.],
  [Refinement loop], [#partial], [Works with real scores, but real masks scored 0.93–0.97, so it never triggered on our images yet.],
  [Evaluation metrics on real images], [#planned], [Labels ready (38 images); crop-on-map metric and baseline run due 25 Oct.],
)

= Evidence

#fig("images/live_real_spray_map_kaggle.jpg", [First real run (Kaggle T4, 3 October). Prompt "vegetation": one box covering the whole field; SAM 2 marked 79% of the image, cotton included. This result first showed that the problem is weed versus crop, not drawing masks.], width: 85%)

#fig("images/real_run_beet_before_gate_fix.jpg", [First run on our laptop (17 October), sugar beet, before the gate fix. The four plants in a row are the crop (official labels); Grounding DINO called all four "weed" and every one was sprayed (panel 4), while the two small real weeds were not detected.])

#fig("images/real_run_beet_after_gate_fix.jpg", [The same photo after the gate fix. One beet is now labelled "sugar beet plant" (blue), but the other three are still called "weed". All confidences are 0.36–0.47, below 0.70, so nothing is sprayed: the crop is protected, the weeds are still missed.])

#fig("images/real_run_cotton_cm11.jpg", [Cotton photo CM_11. The official label is a single ivyleaf morning glory, a weed whose leaves resemble cotton. The detector called it "weed plant"; the reasoning model called it a "cotton seedling". Look-alike weeds defeat both.])

#grid(columns: (1fr, 1fr), gutter: 8pt,
  fig("images/audit_beet_X-10-0.jpg", [Audit, beet X-10-0: our old labels (left) put a "crop" box on bare soil and "weed" boxes on the beets; official labels (right).]),
  fig("images/audit_cotton_CM_17.jpg", [Audit, cotton CM_17: none of our old boxes matches the official weed boxes; the official dataset has no cotton labels.]),
)

#fig("images/t2_2_patches.jpg", [The 20 labelled patches of the crop-or-weed comparison with each back-end's answer.], width: 80%)

#table(
  columns: (1fr, auto, auto, auto, auto),
  [Back-end (20 patches: 10 beet crop, 6 beet weed, 4 cotton weed)], [Correct], [Crop called weed], [Weed called crop], [s / patch],
  [Groq qwen3.8-27b, told the field's crop], [*16/20*], [1 of 10], [3 of 10], [1–2],
  [Cloudflare Clef Flash], [14/20], [2 of 10], [4 of 10], [1.0],
  [Row rule, no model (vegetation band of the whole photo)], [13/20], [3 of 10], [4 of 10], [0.03],
  [Majority vote of the three], [15/20], [2 of 10], [3 of 10], [-],
)

Twenty patches is a small sample; the comparison is repeated on more patches in Week 5. A bias to
report: in the sugar beet data the weeds are tiny (median 16 px across) and the crops large (median
68 px), so plant size alone separates many cases.

*Testing.* Amit's Cycle 0 run (16 Oct) executed 16 app test cases on a fresh Windows install: 7 passed,
9 failed. All 8 resulting issues were fixed and re-tested by repeating his exact steps with a script
that drives the app headlessly (9 of 9 checks pass, two in real mode). The automated suite has 192
unit and 35 end-to-end tests and runs on every push (GitHub Actions, Python 3.10 and 3.11).

= Related work and where we stand

#table(
  columns: (1.3fr, 1fr, 1.6fr),
  [Work], [Setting], [What they report],
  [Milioto, Lottes, Stachniss, ICRA 2018 [4]], [Supervised CNN, Bonn sugar beet], [Weed IoU 20.6% from RGB alone, 59.2% with 14 input channels (RGB + NIR + vegetation indices); crop IoU 60.2% / 83.7%.],
  [Chong et al., IROS 2025 [5]], [*Zero-shot*, SAM + BioCLIP features, weeds as "anomalies"], [Mean weed IoU 12.1% over four datasets, against 62.7% for a supervised ERFNet. Generic CLIP features: 9.1% weed IoU; ResNet: 1.6%.],
  [Nasir, Rehman, Hussain, Front. Plant Sci. 2026 [6]], [Six commercial VLMs, zero-shot, soybean drone images], [Weed-detection accuracy 0.15 (LLaMA-4 Scout) to 0.75 (Gemini Flash 2.5); not reliable enough alone.],
  [Singh et al., 2025 [7]], [Grounding DINO in agriculture], [Zero-shot prompting struggles with visually similar classes; few-shot adaptation without the text encoder works better.],
  [Ren et al., Grounded SAM, 2024 [3]], [Grounding DINO + SAM, general images], [48.7 mean AP on the zero-shot SegInW benchmark; the same combination we use.],
  [Rahman et al., CottonWeedDet3 [11, 12]], [Supervised detectors on the cotton dataset we use], [About 77–80% mAP\@0.5 (YOLOv5n 76.6%, RetinaNet 80.0%) after training on that dataset.],
  [Belissent et al., KBS 2024 [9]], [Transfer and zero-shot weed classification], [Best: ResNet50 pretrained on ImageNet + DeepWeeds and fine-tuned, 77.8% accuracy.],
)

*Where we stand.* Supervised methods trained on the target field reach 60–80% on their metrics; the
best published zero-shot method reaches about 12% weed IoU. Our first real runs sit in the zero-shot
regime: plants are found and outlined well, but labelled weed or crop by prompt words, not by
understanding. We do not expect to beat supervised methods without training. Our contribution is
different and testable: (1) honest zero-shot numbers on two crops with official labels; (2) a
deterministic gate that measurably keeps uncertain plants off the map, and the price in missed weeds;
(3) whether a vision-language second opinion (16/20 on patches so far) or a simple row rule reduces
crop damage. Chong et al. show that species-aware features (BioCLIP [8]) beat generic ones, which is
the natural next step if time allows.

= Did escalation do its job?

*Not yet, and we can say why.* Escalation currently runs *after* the spray map is approved (known
issue K2), and System 2 diagnoses the whole photo rather than each uncertain plant. So today it adds
an explanation and a herbicide suggestion but cannot change what is sprayed. What we know: the
reasoning model alone is right on 16 of 20 patches, which is better than the detector's labels on our
examples, but it also mistook a look-alike weed for cotton. The test planned for 26 Oct – 1 Nov
(task T1.7): move the check before the map, ask the model about each withheld plant, and compare crop
pixels on the map and weed recall with and without escalation on the same 38 images. If it does not
help, we will report that.

= Progress and what remains

#table(
  columns: (auto, 1fr, auto, auto),
  [\#], [Objective (finish line)], [Done], [Due],
  [O1], [Zero-shot detection + segmentation on our laptop], [100%], [done 17 Oct],
  [O2], [Refinement loop measured on real images], [40%], [1 Nov],
  [O3], [Safety gate: approved masks only, crop never sprayed, known gate bugs fixed], [75%], [1 Nov],
  [O4], [Escalation and herbicide advice from the ICAR bulletin, one real end-to-end call], [55%], [1 Nov],
  [O5], [Real evaluation: weed recall, crop pixels on map, savings, speed; before/after one improvement], [25%], [25 Oct / 1 Nov],
  [O6], [Demo: app in real mode, GeoJSON, recorded video], [60%], [5 Nov],
  [-], [Report, slides, viva preparation], [10%], [6–9 Nov],
)

Overall we estimate about *50%* of the finish line: the engineering is mostly done and now honest,
the measurements (O5) are the main remaining work, followed by the write-up.

= Schedule, roles and weekly test escalation

#table(
  columns: (auto, 1fr),
  [Member], [Role now],
  [Chaitanya Shinde], [Vision pipeline, safety gate, integration and reviews, evaluation runs on the GPU laptop, all report and slide writing, test sign-off.],
  [Sumant Vetal], [System tester; checks the herbicide table against the ICAR PDF; repeats the model comparison; collects report content for chapters 1–2.],
  [Sahil Chavan], [Validation tester; checks labels, hand-computes metric examples, chooses hard test images; collects report content on data and evaluation.],
  [Amit Ingle], [Tester for the app and demo: confirms fixes, regression runs, real-mode recording, demo dry run, slide skeleton.],
)

#table(
  columns: (auto, 1fr, 1fr),
  [Week], [Engineering], [Testing escalates to],
  [19–25 Oct], [Crop-on-map metric; real ICAR store; baseline run (*Checkpoint 2, 25 Oct*).], [38 official images (30 beet, 8 cotton); 3 prompt variants; team tasks due 21 Oct.],
  [26 Oct – 1 Nov], [Crop exclusion (T1.6); escalation before the map (T1.7); Clef Flash in the workflow.], [+15 hard images chosen by Sahil; 60 patches for the model comparison; gate threshold 0.5 / 0.6 / 0.7.],
  [2–5 Nov], [Fixes only; freeze and release `v1.0.0` on 5 Nov; demo video.], [All 120 beet images; cross-field split (four field sequences) and beet → cotton transfer; regression of every test case; confidence intervals.],
  [6–9 Nov], [Report and slides; mock viva.], [-],
  [10 Nov], [Submission and viva.], [-],
)

*How the question sharpens each week:* Week 4 asks "how much crop lands on the map with zero-shot
prompts?"; Week 5 asks "which cheap addition reduces it, and at what cost in missed weeds?"; Week 6
asks "does it hold on harder and unseen images, and from one crop to another?"

= What we would like from you

+ Agreement that the narrowed scope (research prototype, weed versus crop, honest negative results allowed) is acceptable for the final evaluation.
+ A short meeting in the week of 19 October to show the real runs and the baseline plan.
+ Any department requirements for the report format and the viva that we should follow.

= References

#set par(justify: false)
#set text(9pt)
+ S. Liu et al., "Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set Object Detection," ECCV 2024. arXiv:2303.05499.
+ N. Ravi et al., "SAM 2: Segment Anything in Images and Videos," arXiv:2408.00714, 2024.
+ T. Ren et al., "Grounded SAM: Assembling Open-World Models for Diverse Visual Tasks," arXiv:2401.14159, 2024.
+ A. Milioto, P. Lottes, C. Stachniss, "Real-time Semantic Segmentation of Crop and Weed for Precision Agriculture Robots Leveraging Background Knowledge in CNNs," ICRA 2018. arXiv:1709.06764.
+ Y. L. Chong, L. Nunes, F. Magistri, X. Zhong, J. Behley, C. Stachniss, "Zero-Shot Semantic Segmentation for Robots in Agriculture," IROS 2025. Code: github.com/PRBonn/WeedsAreWeird.
+ M. F. Nasir, M. U. Rehman, I. Hussain, "Vision-language models for zero-shot weed detection and visual reasoning in UAV-based precision agriculture," Frontiers in Plant Science 16:1735096, 2026. doi:10.3389/fpls.2025.1735096.
+ R. Singh, R. Bidese Puhl, K. Dhakal, S. Sornapudi, "Few-Shot Adaptation of Grounding DINO for Agricultural Domain," arXiv:2504.07252, 2025.
+ S. Stevens et al., "BioCLIP: A Vision Foundation Model for the Tree of Life," CVPR 2024.
+ N. Belissent, J. M. Peña, G. A. Mesías-Ruiz, J. Shawe-Taylor, M. Pérez-Ortiz, "Transfer and zero-shot learning for scalable weed detection and classification in UAV images," Knowledge-Based Systems 292:111586, 2024.
+ N. Chebrolu et al., "Agricultural robot dataset for plant classification, localization and mapping on sugar beet fields," International Journal of Robotics Research 36(10), 2017.
+ A. Rahman, Y. Lu, H. Wang, "CottonWeedDet3: A 3-class weed detection dataset for cotton cropping systems," Kaggle (yuzhenlu/cottonweeddet3), 2022.
+ A. Rahman, "Performance evaluation of deep learning object detectors for weed detection and real time deployment in cotton fields," M.S. thesis, Mississippi State University, 2024.
+ "sugarbeetsAndweeds," Kaggle dataset wangyongkun/sugarbeetsandweeds, 2020 (120 images, 512 × 512, sugar beet and weed boxes; origin not documented by the uploader).
+ ICAR–Directorate of Weed Research, herbicide use bulletin No. 22 (repository file `data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf`).
+ Groq API documentation and model `qwen/qwen3.8-27b` (Preview), console.groq.com/docs, accessed 17 October 2026.
+ Cloudflare Workers AI, model `@cf/cloudflare/clef-flash` (input schema read through the API), developers.cloudflare.com/workers-ai, accessed 17 October 2026.
