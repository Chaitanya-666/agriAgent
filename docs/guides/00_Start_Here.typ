#import "../template.typ": *
#show: doc.with(
  title: "Guide 0 · Start Here",
  subtitle: "How to use these guides to learn, defend and demonstrate AgriAgent",
)

= Why these guides exist

Most of this codebase was written with AI help, fast. That is not a crime, but it creates one real risk:
*you can be asked about code you have never understood.* An examiner does not care who typed a line;
they care whether you can explain why it is there, what happens if it is wrong, and how you know it works.

These guides close that gap. They are written to be read *next to the code*, with the file open.

= The guides

#table(
  columns: (auto, 1fr, auto),
  [Guide], [What it gives you], [Time],
  [1 · Concepts], [Every idea the project rests on, in plain language: detection, segmentation, Grounding DINO, SAM 2, IoU, VLMs, RAG, mock vs real.], [2 h],
  [2 · Codebase Walkthrough], [The code in reading order. One image traced through every function. The 12 known issues with line numbers.], [3–4 h],
  [3 · Viva Defence], [The questions you will be asked, with strong answers, including the uncomfortable ones.], [2 h + practice],
  [4 · Demo Playbook], [How to run the demo, what to say at each step, what can go wrong, and the backup plan.], [1 h + rehearsal],
  [5 · Code Reading Drills], [A method for understanding any codebase fast, practised hands-on: eight drills with the terminal open, from tracing the pipeline to breaking the safety gate on purpose and writing the missing tests.], [8 sessions],
)

Also keep open: `docs/AgriAgent_Project_Map.pdf` (the plan) and the Week 1–4 dossiers (history and measured results).

= How to study (the method)

Reading is not understanding. Use this loop for every section:

+ *Read* the guide section.
+ *Open* the file it points to and find the lines.
+ *Close both* and explain it out loud, or on paper, as if to a friend who is not technical.
+ *Check* where you got stuck. That gap is exactly what an examiner will find. Go back and fix it.

Each guide ends with *self-check questions*. If you cannot answer one without looking, you are not done
with that section.

= Study plan until the viva (Tuesday 10 November)

Updated 20 October. The first plan (11–14 October) is done. Features are now frozen, so the code
you study will not change under you except for bug fixes.

#table(
  columns: (auto, 1fr),
  [When], [Do],
  [Week of 21 Oct], [Guide 5, Drills 1–2 (pipeline, safety gate), each with the matching part of Guide 2. Refresh Guide 1 where a drill shows a gap.],
  [Week of 26 Oct], [Drills 3–5 (plant rules, metrics, escalation agent) next to the Week 4 dossier's results.],
  [Week of 2 Nov], [Drills 6–7 (System 2 and ICAR, library code). Guide 3: answer every question out loud. Drill 8 on an unseen project.],
  [Thu 5 – Mon 9 Nov], [Guide 4 rehearsal on the frozen `v1.0.0`; mock viva on Fri 6 Nov.],
)

= The five sentences you must always be able to say

If you remember nothing else, remember these. Every viva answer grows out of one of them.

+ AgriAgent turns a field photo into a map of only the weed areas, so herbicide is not sprayed on the crop.
+ It uses Grounding DINO to find candidate plants from a text prompt and SAM 2 to outline them pixel by pixel, with no training on our data.
+ A deterministic safety gate, plain testable rules, decides what may go on the spray map; AI models can only advise.
+ When the system is unsure, it escalates to a reasoning model, and any herbicide advice comes from the official ICAR bulletin, never from the model's imagination.
+ Our one real run showed the hard problem is telling weed from crop, so our evaluation measures how much crop ends up on the spray map.

= Honesty rules for the viva

- Never call something "verified" or "real" unless it ran with real models on real images.
- Say "mock mode" out loud when you show mock output. Examiners respect it; they punish being caught.
- If you do not know, say: "I don't know yet; here is how I would find out." That is a strong answer.
- Weaknesses you name yourself are research findings. Weaknesses the examiner finds are failures.
