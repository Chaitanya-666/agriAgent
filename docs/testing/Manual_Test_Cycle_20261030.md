# Manual test cycle, 30–31 October 2026 (branch chaitanya/fixes-20261030)

Save every result here as `MT-0N_<photo>.pdf` (browser: Ctrl+P → Save as PDF) and, when the
test says so, `MT-0N_<photo>.geojson`. Write the verdict in the table at the bottom.

**Photos:** `data/outputs/test_photos/` (originals), with the official boxes drawn in
`data/outputs/test_photos/official_labels/<name>_labels.png` (green = crop, red = weed, copied
unchanged from the dataset files; nobody on the team drew them).

| Photo | Crop | Official labels | Set |
|---|---|---|---|
| `beet_X-10-0.png` | sugar beet | 4 sugar beet, 2 weed | held-out |
| `beet_X2-30-0.png` | sugar beet | 3 sugar beet, 25 weed | v2 (development) |
| `beet_X3-430-0.png` | sugar beet | 9 sugar beet, 1 weed | v2 (development) |
| `beet_X3-130-0.png` | sugar beet | 8 sugar beet, 0 weed | held-out |
| `cotton_CM_17.jpg` | cotton | 5 palmer amaranth (weed); cotton is never labelled | v2 |
| `cotton_CM_11.jpg` | cotton | 1 morningglory (weed); cotton is never labelled | v2 |

**Start the app (fish):**

```fish
cd /mnt/Windows_D/College-work/finalYearProjectAgriAgent
git switch chaitanya/fixes-20261030
source ~/.venvs/agriagent/bin/activate.fish
streamlit run app/app.py
```

Reasoning now runs on Cloudflare (no Groq rate limit). Real runs take about 15 s, or about
40 s with the agent on.

## Test cases

| ID | Setup | Do | Pass if |
|---|---|---|---|
| MT-01 | Mock Mode **on**, Cotton | Upload any photo; set Language to Hindi | Yellow MOCK banner; an orange note says Hindi needs real mode (F17) |
| MT-02 | Mock **off**, **Sugar Beet**, agent off | Upload `beet_X3-130-0.png` | REAL banner; about 0.05% sprayed; no beet coloured; tiny patches have a magenta ring (F5) |
| MT-03 | Same photo, switch Crop to **Cotton** | Wait for the rerun | A warning says no plant was recognised as Cotton (F18). The beets are sprayed: that is the known limitation F1 |
| MT-04 | Back to Sugar Beet (instant: cached) | Language Hindi, then Marathi | Each switch is instant (no rerun, F20); text in Hindi/Marathi; **judge it**: correct words (चुकंदर, खरपतवार / तण), natural, numbers right (F23) |
| MT-05 | Sugar Beet | Click Download GeoJSON; save as `MT-05_X3-130-0.geojson`; drop on geojson.io | Page does not rerun; shapes appear the right way up, about 2.6 m across, at VJTI; properties say `buffer_margin_px` (F14–F16) |
| MT-06 | Sugar Beet | Upload `beet_X-10-0.png`; open its `_labels.png` next to it | Coloured patches sit on the 2 red-boxed weeds, not on the 4 beets |
| MT-07 | Sugar Beet | Upload `beet_X2-30-0.png` | Known failure: 2 beets touched. Note what you see; this goes in the report |
| MT-08 | Sugar Beet, tick **Review unsure plants** | Upload `beet_X3-430-0.png` | Agent box lists reviews with qwen_vlm answers, no 429/error lines; summary count matches plants left unsure (F4) |
| MT-09 | **Cotton** | Upload `cotton_CM_17.jpg` | System 2 shows a diagnosis; herbicide only if an ICAR cotton row matches, otherwise "no evidence" |
| MT-10 | Terminal | `python scripts/check_providers.py` | Two PASS lines (cloudflare-qwen, cloudflare) |

## Results

| ID | Date | Verdict (PASS / FAIL / note) | Files saved |
|---|---|---|---|
| MT-01 | 30 Oct 21:25 | PASS: MOCK banner; language switch instant, download did not rerun (F20); Hindi note shown; no agent toggle; magenta outlines; GeoJSON buffer_margin_px, approved_by, 5 mm/px (blobs about 0.5 m), lower blob further south | MT-01-00-MOCK.png, MT-01-00-02-MOCK.png, MT-01-00-MOCK.geojson |
| MT-02 | 30 Oct 21:40 | PASS with findings: REAL banner; 0.05%; no beet filled; magenta rings make the 2 specks visible (one sits inside the top-left beet, the known ST-14 speck); summary no longer claims 7 unsure plants (F4). F24: during the run the old MOCK page stays visible greyed. F25: Cloudflare Qwen said weed (0.85) for 3 beets that Groq Qwen called crop; the agent still kept all unsure. Marathi has typos (सखर, फववववणी); Hindi verdict pending | MT01-01-00-REAL.png, MT-01-01-01.png, MT-01-01-DASHBOARD.pdf, MT-01-01-GEOJSON.geojson |
| MT-03 | 30 Oct 21:50 | PASS: wrong-crop warning shown (F18); 2.3% sprayed, bottom-right beet filled (known F1). Hindi summary natural (कपास, खरपतवार) but silent about the wrong crop (F27). F26: one earlier run failed loading Grounding DINO ('Cannot copy out of meta tensor'); the rerun worked | MT-03-00-REAL.png, MT-03-01-DASHBOARD.pdf, MT-03-02-GEOJSON.geojson |
| MT-04 | | | |
| MT-05 | | | |
| MT-06 | | | |
| MT-07 | | | |
| MT-08 | 30 Oct 21:40 | Covered in MT-02 (agent ticked): 6 reviews, all qwen_vlm answers from Cloudflare, no 429. F25: Cloudflare Qwen 12/20 on the T2.2 patches vs 16/20 on Groq (beets called crop 5/10 vs 9/10); agent kept all unsure | see MT-02 files; data/outputs/t2_2_cloudflare_20261030/ |
| MT-09 | | | |
| MT-10 | 30 Oct 21:03 | PASS (run by Claude): cloudflare-qwen replied OK in 6.1 s; Clef Flash answered | terminal |

Earlier, before the fixes (30 Oct, 20:16–20:31): `AgriAgent Dashboard.pdf` runs in ~/Downloads
showed F14–F21 (mock GeoJSON at VJTI upside down; wrong crop sprays beets; Hindi lost to Groq 429).
