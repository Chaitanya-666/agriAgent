#import "../template.typ": *
#show: doc.with(
  title: "Test Cycle 2: brief for Amit",
  subtitle: "System and regression testing of the final build · results due Thursday 12 November 2026, 23:59",
  date: "7 November 2026",
)
#show table: set par(justify: false)
#set table(columns: (auto, 1.6fr, 1.4fr))

#note(title: "What this is")[
  This is the last test cycle before we freeze AgriAgent on Sunday 15 November. You test the
  *final build* on your own Windows laptop and report every problem. Chaitanya fixes what you find
  on 13–14 November, so the earlier you report, the better: *file each FAIL as soon as you see it*,
  don't wait until the end. Expected effort: about 5–6 hours in total, spread over the days.
]

= What you need

- The repository at the latest `main` (Chaitanya will tell you on WhatsApp when the PR with these fixes is merged). Check with `git log --oneline -1`; write that commit in every report.
- The six test photos from Drive: `agriAgentShared/shared/test_photos/`. The official labels of each photo are on the last page of this brief (green box = crop, red box = weed; they come unchanged from the dataset files).
- *Optional but recommended:* your own free Cloudflare account for the reasoning model (Hindi/Marathi summary, System 2 diagnosis). Dashboard → AI → Workers AI → "Use REST API": copy the Account ID and create a token with the "Workers AI" template, then put both in `.env`. Never send keys over WhatsApp or commit `.env`. Without keys every case still runs; cases marked *(keys)* then only check that the app says the model was not available and does not crash.
- The Google Sheet *AgriAgent Test Cycle 2* in the top of `agriAgentShared`: one row per test case below is already there. Fill in Date, Verdict (PASS / FAIL / NOTE), What you saw, Screenshot file.
- Save screenshots and recordings in Drive `agriAgentShared/Amit/cycle2/`, named after the case (for example `R2_second_run.png`).

= How to report a FAIL

Open a GitHub issue at #link("https://github.com/Chaitanya-666/agriAgent/issues")[github.com/Chaitanya-666/agriAgent/issues], title `[TC2] <case ID>: <what went wrong>`, with this body:

```
Commit:      (git log --oneline -1)
Setup:       Windows version, Python version, GPU or CPU, mock or real, keys yes/no
Steps:       1. ... 2. ... 3. ...
Expected:    (copy from this brief)
Actual:      (what you saw, exact error text)
Screenshot:  (attach, or the Drive file name)
```

Then put the issue number in the Sheet row. One issue per problem. If you are unsure whether it
is a bug, file it anyway and say so; a wrong alarm costs a minute, a missed bug costs the demo.

= Part A: install and automated checks (about 1 hour)

#table(
  [ID], [Do], [Pass if],
  [A1], [Fresh install, exactly as the README "Setup" section says, in a new folder: `python -m venv .venv`, `.venv\Scripts\activate`, `python -m pip install -r requirements-lock.txt`, `python -m pip install -e . --no-deps`, `copy .env.example .env`, `python scripts\download_models.py`. Note how long each step took.], [Every step finishes without an error. If one fails, copy the full error into the issue.],
  [A2], [`python -m unittest discover -s tests`], [Last line `OK` (about 270 tests).],
  [A3], [`python tests\e2e\runner.py --all`], [`Passed: 35`, `Failed: 0`.],
  [A4], [`python scripts\verify_cycle0_issues.py`], [Every line starts with `[PASS]`.],
  [A5], [`python scripts\verify_test_cycle1.py` (mock cases, seconds)], [ST-01 … ST-11 all `[PASS]`.],
  [A6], [*(keys)* `python scripts\check_providers.py`], [Two PASS lines (cloudflare-qwen, cloudflare). Without keys: a clear "missing key" message, no crash.],
)

= Part B: regression of the fixes made on 7 November (about 1.5 hours)

Start the app with `streamlit run app\app.py`. "Real mode" means the *Mock Mode* switch in the sidebar is off.

#table(
  [ID], [Do], [Pass if],
  [R1 (F24)], [Run the app in Mock Mode with the sample photo, so the yellow MOCK banner shows. Then switch Mock Mode *off*.], [As soon as the real run starts, the old MOCK result disappears; only the spinner is visible until the new REAL result appears. Before the fix the old MOCK page stayed visible, greyed out.],
  [R2 (F26)], [Real mode, Crop *Sugar Beet*, upload `beet_X3-130-0.png`. Time the first run with your phone's stopwatch. Then *while the spinner is still running* change Crop to Cotton, then quickly back to Sugar Beet, three times in a row. Then upload `beet_X-10-0.png` and time that run.], [No error at any point, in particular no "Cannot copy out of meta tensor". The second photo is clearly faster than the first run (the models are now loaded only once). Write both times in the Sheet.],
  [R3 (F27)], [Real mode, upload `beet_X3-130-0.png`, set Crop to *Cotton* (wrong on purpose). Scroll to "Summary for the farmer". Try English, then *(keys)* Hindi and Marathi.], [An orange warning at the top says no plant was recognised as Cotton. The farmer summary also contains the warning: English "Warning: no plant in this photo was recognised as cotton…"; Hindi contains (usually at the end) "चेतावनी: इस फ़ोटो में कोई भी पौधा कपास के रूप में नहीं पहचाना गया…", Marathi "इशारा: या फोटोमधील कोणतेही रोप कापूस म्हणून ओळखले गेले नाही…".],
  [R4 (F29)], [*(keys)* Real mode, Crop *Cotton*, tick *Force System 2*, upload `cotton_CM_17.jpg`. Read the System 2 report, then the farmer summary in English and Hindi.], [If a herbicide is shown, the summary *ends* with the caveat: English "…not an instruction: read the product label and ask your local agriculture officer before spraying.", Hindi "यह ICAR तालिका का सुझाव है, निर्देश नहीं: …". The summary never tells the farmer to spray a dose as an order. If no herbicide is shown, note "no prescription" (that is allowed).],
  [R5 (F28)], [Real mode, Sugar Beet, upload `beet_X2-30-0.png`. Under the two images tick *Show every plant and what the system decided*.], [A third image: soil darker, plants coloured red (sprayed), green (protected as crop) or yellow (left alone), with a caption giving the three percentages. Compare with the labels on the last page: expect *two of the three beets in red* (known failure F1, goes in the report) and small red specks on weeds. Screenshot it.],
  [R6], [Same as R5 with `cotton_CM_17.jpg`, Crop Cotton.], [The big palmer amaranth weeds are *green* (the detector called them cotton: known limitation), small specks red. Screenshot it; this is a report figure.],
)

= Part C: manual cases never run before (about 1 hour)

#table(
  [ID], [Do], [Pass if],
  [MT-04], [*(keys)* Sugar Beet, `beet_X3-130-0.png`. Switch the summary language English → Hindi → Marathi → English.], [Each switch is instant (no new spinner). Judge the language as a reader: correct words (चुकंदर, खरपतवार; तण, फवारणी), natural sentences, numbers same as English. Note any spelling mistakes exactly.],
  [MT-05], [Sugar Beet, `beet_X3-130-0.png`. Click *Download Field Prescription (GeoJSON)*, save as `MT-05_X3-130-0.geojson`, then drag the file onto #link("https://geojson.io")[geojson.io].], [The page does not rerun when you click download. On the map the shapes appear near VJTI, small (a few metres), the right way up (compare with the photo). Click a shape: its properties include `buffer_margin_px` and `approved_by`.],
  [MT-06], [Sugar Beet, upload `beet_X-10-0.png`; open its labels (last page).], [The coloured patches sit on the 2 red-boxed weeds, not on the 4 beets.],
  [MT-07], [Sugar Beet, upload `beet_X2-30-0.png`.], [Known failure: 2 beets touched. Describe what you see; it goes in the report as the main limitation.],
)

= Part D: exploratory testing (45 minutes, time-boxed)

Try to break it. Each idea below is one Sheet row (ID `X1`, `X2`, …); add your own.

- Your own phone photo of plants (garden, potted plant, roadside weeds). Expect no crash and a sensible result; describe it.
- A photo with no plants at all (a desk, a wall, a dark room). Expect nothing sprayed.
- A very large photo (straight from your phone camera), and a tiny one (screenshot a small part).
- Portrait and landscape photos; a PNG with transparency.
- The app open in two browser tabs at the same time, running different photos.
- Switch every sidebar control during a run; use the browser's back and refresh buttons.
- Real mode with the Wi-Fi turned off. Expect the vision part to still work and a clear message that the reasoning model was unreachable.

= Part E: demo material (about 1 hour)

#table(
  [ID], [Do], [Deliver],
  [E1], [Screen recording (Win + G or OBS) of one complete real-mode run, 3–5 minutes, with your voice explaining: upload `beet_X-10-0.png` → spray map → "show every plant" view → farmer summary in Hindi → GeoJSON download → geojson.io.], [The video in `Amit/cycle2/`. This is our backup if the live demo fails.],
  [E2], [Go through `docs/guides/04_Demo_Playbook.pdf` step by step.], [Each step marked ok / problem in the Sheet; list steps that no longer match the app.],
)

= Schedule

#table(
  columns: (auto, 1fr),
  [When], [What],
  [Sun 8 Nov], [Part A. Report install problems the same day (they block everything else).],
  [Mon 9 – Tue 10 Nov], [Parts B and C.],
  [Wed 11 Nov], [Part D.],
  [Thu 12 Nov], [Part E; Sheet complete by 23:59; WhatsApp Chaitanya "TC2 done" with the number of FAILs.],
  [Fri 13 – Sat 14 Nov], [Chaitanya fixes; you re-test only the fixed issues (comment PASS/FAIL on each issue).],
)

#pagebreak()
= Official labels of the six test photos

Green box = crop plant, red box = weed. Copied unchanged from the dataset files. Cotton photos:
the dataset labels only weeds; cotton is never boxed.

#grid(columns: (1fr, 1fr), gutter: 8pt,
  figure(image("images/labels_beet_X-10-0.jpg"), caption: [`beet_X-10-0.png`: 4 beets, 2 weeds]),
  figure(image("images/labels_beet_X2-30-0.jpg"), caption: [`beet_X2-30-0.png`: 3 beets, 25 weeds]),
  figure(image("images/labels_beet_X3-130-0.jpg"), caption: [`beet_X3-130-0.png`: 8 beets, 0 weeds]),
  figure(image("images/labels_beet_X3-430-0.jpg"), caption: [`beet_X3-430-0.png`: 9 beets, 1 weed]),
  figure(image("images/labels_cotton_CM_17.jpg"), caption: [`cotton_CM_17.jpg`: 5 palmer amaranth]),
  figure(image("images/labels_cotton_CM_11.jpg"), caption: [`cotton_CM_11.jpg`: 1 morningglory]),
)
