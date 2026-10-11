#import "../template.typ": *
#show: doc.with(
  title: "Guide 4 · Demo Playbook",
  subtitle: "How to run AgriAgent, what to show, what to say, and what to do when it breaks",
)

#warn(title: "Golden rule")[
  Always say out loud whether what you are showing is *mock* or *real*. If a real model fails to load,
  the code silently switches to mock (known issue 5). Check the terminal log before claiming real output.
]

= Setup (once)

```bash
cd finalYearProjectAgriAgent
python3.11 -m venv .venv && source .venv/bin/activate     # Python 3.10 or 3.11
python -m pip install -e '.[dev]'
cp .env.example .env          # put GROQ_API_KEY=... here for real reasoning
```

Checked on 11 October 2026: the app starts and runs in mock mode on the team laptop.

= Rehearsal 1: mock mode (works today)

```bash
streamlit run app/app.py      # opens http://localhost:8501
```

+ The sidebar has *Mock Mode* ticked by default. Leave it ticked.
+ Keep "use sample field photo" ticked. The sample is a *synthetic* image.
+ You should see: three boxes, three coloured masks, infestation about 9.4%, savings about 87.8%,
  and a GeoJSON download with about 10 polygons.
+ Tick *Force System 2*: a prescription card appears (mock diagnosis, Pyrithiobac-sodium for cotton).

*What to say:* "This is mock mode: fixed stand-in outputs that let us test the pipeline and the safety
logic on any laptop. These numbers are not accuracy results."

= Rehearsal 2: show the safety logic (works today)

This is your strongest live moment, because it shows the rules working.

In mock mode every box takes the *first* phrase of the prompt as its label. Verified results:

#table(
  columns: (auto, auto, auto),
  [Prompt], [Labels], [Sprayed],
  [`weed . cotton .`], [weed ×3], [9.4%, 10 polygons],
  [`cotton . weed .`], [cotton ×3], [0%, no polygons],
  [`cotton weed .`], [cotton weed ×3], [0%, no polygons],
)

+ Run `weed . cotton .` → weeds are sprayed.
+ Run `cotton . weed .` → labels say "cotton" → nothing is sprayed. The gate never sprays crop.
+ Run `cotton weed .` → still nothing: the label *contains* a crop word, so the gate excludes it.
  Fail-closed: when in doubt, don't spray.
+ Show the GeoJSON file: only approved weed zones, and say why it is built from masks, not boxes.
+ Optional, in a terminal: `PYTHONPATH=. python -m unittest tests.test_spray_export_safety -v`.

*What to say:* "Models only propose. These rules, which we test automatically, decide what may be
sprayed."

= Rehearsal 3: real models (to be done after the freeze)

```bash
python scripts/run_live_pipeline.py --image path/to/field.jpg --prompt "weed . grass ."
```

- First run downloads weights from Hugging Face (needs internet and a few GB of disk).
- *Do not use the script's default prompt*: `"cotton weed . broadleaf plant ."` is rejected by the gate,
  so nothing is sprayed (known issue 4).
- In the log, confirm you see "Grounding DINO initialized successfully" and *no* "Falling back to
  mock_mode" line. If you see that line, the output is mock.
- In the app: untick Mock Mode, upload a real photo.

= The demo script (final version, about 6 minutes)

#table(
  columns: (auto, 1fr, 1fr),
  [Min], [Show], [Say],
  [0–1], [Title slide, field photo], [Problem: blanket spraying. Goal: spray only weeds.],
  [1–2], [Pipeline diagram], [Five stages; models advise, rules decide.],
  [2–4], [App on a real image (or recorded video)], [Boxes → masks → spray map → savings. Point out crop excluded.],
  [4–5], [Safety moment (Rehearsal 2)], [Change prompt; crop labels never sprayed; tests prove it.],
  [5–6], [Results table + the real Kaggle failure], [Crop-on-map metric, before vs after our improvement. Honest limits.],
)

= What can go wrong, and the backup

#table(
  columns: (1fr, 1fr),
  [Problem], [Do this],
  [No internet / Groq down], [Show mock System 2 and say so; explain the RAG design.],
  [GPU or weights fail], [Play the recorded demo video of a real run. Record it the week before.],
  [App crashes], [Use `scripts/run_live_pipeline.py` output images saved earlier.],
  [Examiner asks to try their own photo], [Allow it in real mode; if results are poor, explain why. That is the research finding.],
  [Laptop dies], [Keep the video and slides on a USB stick and in the cloud.],
)

= Checklist (the day before)

- `git pull` on `main`; all tests pass.
- Real-mode run works offline (weights already downloaded).
- Demo video recorded and copied to two places.
- 3–5 good real images and 1–2 hard ones ready in a folder.
- `.env` with a working Groq key, or a plan to show mock System 2.
- Each team member has rehearsed their part out loud.
