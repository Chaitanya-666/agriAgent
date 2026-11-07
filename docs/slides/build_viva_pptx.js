// Builds docs/slides/AgriAgent_Final_Viva.pptx, the PowerPoint version of the viva deck
// (same content as the claude.ai deck "AgriAgent Final Viva").
// Needs pptxgenjs 3.12 (npm install pptxgenjs@3.12.0 in any folder, then NODE_PATH=<that>/node_modules).
// Run from the repository root:  node docs/slides/build_viva_pptx.js
// Every number on a slide comes from docs/results/ or docs/testing/ (named in the notes).

const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = path.join(__dirname, "AgriAgent_Final_Viva.pptx");
const IMG = (name) => path.join(__dirname, "images", name);

const THEME = {
  name: "AgriAgent",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1C2620", lt1: "FFFFFF", dk2: "3D4741", lt2: "F7F6F1",
    accent1: "2F6B3A", accent2: "B4501A", accent3: "25466E",
    accent4: "ECEFE8", accent5: "F2A57A", accent6: "DCE3DC",
    hlink: "2F6B3A", folHlink: "6A746D",
  },
};
const MUTED = "6A746D";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = "AgriAgent Final Viva";
pres.author = "AgriAgent team, VJTI";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const W = 13.333, M = 0.6, CW = W - 2 * M;

const titlePh = (bg) => ({
  placeholder: {
    options: { name: "title", type: "title", x: M, y: 0.85, w: CW, h: 1.0, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text1, align: "left", valign: "top", margin: 0 },
    text: "Title",
  },
});
const footer = { slideNumber: { x: W - M - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: MUTED, align: "right" } };
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.background2 }, objects: [titlePh()], ...footer });
pres.defineSlideMaster({ title: "CONTENT_ALT", background: { color: C.accent4 }, objects: [titlePh()], ...footer });
pres.defineSlideMaster({ title: "DARK", background: { color: C.text1 }, ...footer });

const eyebrow = (slide, text, color = C.accent1) =>
  slide.addText(text.toUpperCase(), { x: M, y: 0.4, w: CW, h: 0.35, fontSize: 13, bold: true, charSpacing: 2, color, margin: 0, isTextBox: true, objectName: "eyebrow" });
const card = (slide, x, y, w, h, fill = C.background1, line = C.accent6, name = "card") =>
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: line, width: 1 }, objectName: name });
const note = (slide, text) =>
  slide.addText(text, { x: M, y: 6.95, w: CW - 0.8, h: 0.35, fontSize: 11, color: MUTED, margin: 0, isTextBox: true, objectName: "source" });

// 1 Cover
pres.addSection({ title: "Problem and questions" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Problem and questions" });
s.addText("FINAL YEAR PROJECT · B.TECH COMPUTER ENGINEERING · VJTI 2026–27", { x: M, y: 0.6, w: CW, h: 0.4, fontSize: 14, bold: true, charSpacing: 2, color: "9FC7A5", margin: 0, isTextBox: true });
s.addText("AgriAgent", { x: M, y: 2.2, w: CW, h: 1.3, fontFace: "Cambria", fontSize: 66, bold: true, color: C.background2, margin: 0, isTextBox: true });
s.addText("A safety-gated zero-shot vision pipeline for crop–weed spot spraying", { x: M, y: 3.5, w: 10, h: 1.0, fontSize: 26, color: "DDE6DE", margin: 0, isTextBox: true });
s.addText([
  { text: "Chaitanya Shinde (231070066) · Sumant Vetal · Sahil Chavan · Amit Ingle", options: { breakLine: true } },
  { text: "Guide: Prof. V. D. Dhore · Department of Computer Engineering and IT · November 2026" },
], { x: M, y: 6.0, w: CW, h: 0.8, fontSize: 15, color: "BFD0C2", margin: 0, isTextBox: true });
s.addNotes("We measured how well zero-shot foundation models tell a weed from a crop plant for spot spraying, and how much a transparent safety layer recovers when they cannot. Everything was run on our own laptop GPU; every number has a file in the repository.");

// 2 Problem
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and questions" });
eyebrow(s, "The problem");
s.addText("Spot spraying works only if the camera can tell a weed from the crop", { placeholder: "title" });
[["Blanket spraying", "Herbicide on the whole field, although weeds cover only part of it."],
 ["Supervised networks", "Separate crop and weed well, but need thousands of labelled photos of the same field."],
 ["Zero-shot models", "Grounding DINO + SAM 2 segment “weeds” from a text prompt, with no training. Does that work?"]]
  .forEach(([h, b], i) => {
    const x = M + i * (CW / 3 + 0.0) + (i ? 0.1 * i : 0), w = CW / 3 - 0.2;
    card(s, x, 2.4, w, 2.5);
    s.addText(h, { x: x + 0.3, y: 2.65, w: w - 0.6, h: 0.5, fontSize: 20, bold: true, color: C.accent1, margin: 0, isTextBox: true });
    s.addText(b, { x: x + 0.3, y: 3.25, w: w - 0.6, h: 1.5, fontSize: 17, color: C.text2, valign: "top", margin: 0, isTextBox: true });
  });
note(s, "A wrong “weed” damages the crop; a missed weed survives. Both errors matter.");
s.addNotes("The hard part is not finding plants but deciding which are weeds. Supervised networks need labelled images of the same field; foundation models promise to do it from a text prompt. We test that promise.");

// 3 Research questions
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and questions" });
eyebrow(s, "Research questions");
s.addText("Three questions, each with a number", { placeholder: "title" });
[["RQ1", "How well does Grounded SAM separate weed from crop? Weed recall and crop pixels on the spray map."],
 ["RQ2", "When the gate is unsure and asks vision-language models, does the map get more complete without getting less safe?"],
 ["RQ3", "Which cheap addition keeps the crop off the map best, and what does it cost in missed weeds?"]]
  .forEach(([id, q], i) => {
    const y = 2.2 + i * 1.45;
    card(s, M, y, CW, 1.2);
    s.addText(id, { x: M + 0.35, y, w: 1.2, h: 1.2, fontFace: "Cambria", fontSize: 28, bold: true, color: C.accent2, valign: "middle", margin: 0, isTextBox: true });
    s.addText(q, { x: M + 1.7, y, w: CW - 2.0, h: 1.2, fontSize: 18, color: C.text2, valign: "middle", margin: 0, isTextBox: true });
  });
s.addNotes("RQ1 is the base pipeline, RQ2 the escalation agent, RQ3 the cheap fixes. The key metric is crop pixels sprayed, the damage a farmer cares about.");

// 4 Pipeline
pres.addSection({ title: "System and data" });
s = pres.addSlide({ masterName: "CONTENT_ALT", sectionTitle: "System and data" });
eyebrow(s, "The system");
s.addText("Models propose, rules decide", { placeholder: "title" });
const steps = [
  ["1 Detect", "Grounding DINO, prompt “weed . sugar beet plant .”", C.background1, C.accent6, C.accent1],
  ["2 Segment", "SAM 2 masks with a quality score", C.background1, C.accent6, C.accent1],
  ["3 Plant rules", "Every green patch: crop, weed or unsure", C.background1, C.accent6, C.accent1],
  ["4 Safety gate", "The only part that may approve a spray zone", "FBEBDD", C.accent2, "8A3B12"],
  ["5 Advise", "Escalation agent, Qwen diagnosis, ICAR herbicide table", "E3EBF5", "9DB3CF", C.accent3],
];
const sw = (CW - 4 * 0.35) / 5;
steps.forEach(([h, b, fill, line, hc], i) => {
  const x = M + i * (sw + 0.35);
  card(s, x, 2.3, sw, 2.3, fill, line, `step-${i + 1}`);
  s.addText(h, { x: x + 0.2, y: 2.45, w: sw - 0.4, h: 0.5, fontSize: 18, bold: true, color: hc, margin: 0, isTextBox: true });
  s.addText(b, { x: x + 0.2, y: 3.0, w: sw - 0.4, h: 1.5, fontSize: 14, color: C.text2, valign: "top", margin: 0, isTextBox: true });
  if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + sw + 0.05, y: 3.3, w: 0.25, h: 0.3, fill: { color: "9AA89E" }, line: { color: "9AA89E" } });
});
s.addText([{ text: "Local, 0.6 s per photo", options: { bold: true } }, { text: " on an RTX 5050 laptop (8 GB). No training on our data." }], { x: M, y: 5.2, w: CW / 2 - 0.2, h: 0.9, fontSize: 17, color: C.text2, margin: 0, isTextBox: true });
s.addText([{ text: "Cloud models only advise.", options: { bold: true } }, { text: " Any error or doubt means “do not spray”." }], { x: M + CW / 2 + 0.2, y: 5.2, w: CW / 2 - 0.2, h: 0.9, fontSize: 17, color: C.text2, margin: 0, isTextBox: true });
s.addNotes("Grounding DINO plus SAM 2 is Grounded SAM, our base. Gate: confidence >= 0.70, mask quality >= 0.85, no crop words, suppress the map above 85% infestation. Blue = System 2: escalation agent, Qwen 3.8 diagnosis, herbicide only from the ICAR bulletin row for the declared crop.");

// 5 Data
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "System and data" });
eyebrow(s, "Data");
s.addText("Labels copied from the official files, never drawn by us", { placeholder: "title" });
s.addText([
  { text: "Our first evaluation set was a template: the same 8 boxes on every photo. Found, withdrawn, replaced.", options: { bullet: true, breakLine: true } },
  { text: "Development set: 30 sugar beet + 8 cotton photos.", options: { bullet: true, breakLine: true } },
  { text: "Held-out set: 90 sugar beet photos, run once after the rules were frozen.", options: { bullet: true, breakLine: true } },
  { text: "Rebuilds exactly from Kaggle by script; runs are deterministic.", options: { bullet: true } },
], { x: M, y: 2.3, w: 5.6, h: 4.2, fontSize: 17, color: C.text2, paraSpaceAfter: 10, valign: "top", margin: 0, isTextBox: true });
s.addImage({ path: IMG("audit_beet_X-10-0.jpg"), x: 6.6, y: 2.4, w: 6.13, h: 2.63, altText: "Label audit of beet X-10-0: old labels left, official labels right" });
s.addText("Audit of photo X-10-0: old labels (left) vs official labels (right).", { x: 6.6, y: 5.15, w: 6.13, h: 0.4, fontSize: 12, color: MUTED, margin: 0, isTextBox: true });
s.addNotes("An AI-generated evaluation set had fabricated labels; a metric on it was meaningless. Labels are now copied by script from the official XML files, and 90 photos were kept aside and evaluated exactly once. A rerun reproduced every number.");

// 6 Baseline
pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Results" });
eyebrow(s, "RQ1 · Grounded SAM baseline, 90 held-out photos", "9FC7A5");
[["65.5%", "of crop pixels sprayed", C.accent5], ["1.8%", "of weed pixels hit", C.background2]].forEach(([n, l, c], i) => {
  const x = M + i * (CW / 2);
  s.addText(n, { x, y: 1.5, w: CW / 2 - 0.3, h: 1.9, fontFace: "Cambria", fontSize: 110, bold: true, color: c, margin: 0, isTextBox: true });
  s.addText(l, { x, y: 3.4, w: CW / 2 - 0.3, h: 0.6, fontSize: 22, color: "DDE6DE", margin: 0, isTextBox: true });
});
s.addText([{ text: "Text prompts do not separate crop from weed. SAM 2 outlines plants well; the " }, { text: "labels", options: { bold: true } }, { text: " are wrong. At the deployed 0.70 gate, nothing is sprayed at all." }],
  { x: M, y: 4.6, w: CW, h: 1.3, fontSize: 22, color: "DDE6DE", margin: 0, isTextBox: true });
s.addText("Label policy, confidence ≥ 0.35. Source: docs/results/holdout_plant_rules_v3_20261018.md", { x: M, y: 6.95, w: CW - 0.8, h: 0.35, fontSize: 11, color: "9AA89E", margin: 0, isTextBox: true });
s.addNotes("Answer to RQ1. With the detector's labels deciding, two thirds of the crop is sprayed and almost no weed. Real Grounding DINO scores never exceed 0.68, so the 0.70 gate sprays nothing. Spraying every mask hits 93% of weeds, so segmentation is fine; classification is the problem. Agrees with Chong et al., IROS 2025.");

// 7 Plant rules
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
eyebrow(s, "RQ3 · Plant rules v3");
s.addText("Four plain rules on every green patch", { placeholder: "title" });
const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent1 } } });
s.addTable([
  [hdr("#"), hdr("Verdict"), hdr("When")],
  ["1", "crop", "at least 30% of the patch is inside a SAM 2 crop mask"],
  ["2", "crop", "the photo has clear rows and the patch is on the densest row"],
  ["3", "weed", "smaller than a quarter of the median crop plant in the same photo"],
  ["4", "weed", "the photo has clear rows and the patch is off the row"],
  ["5", "unsure", "anything else: never sprayed"],
], { x: M, y: 2.2, w: CW, colW: [0.8, 1.8, CW - 2.6], fontSize: 16, color: C.text2, border: { type: "solid", pt: 0.75, color: "C9D6CB" }, fill: { color: C.background1 }, rowH: 0.5, margin: 0.08 });
s.addText("Vegetation by excess green (2G − R − B) with a per-photo Otsu threshold. No training, no model calls, no threshold tuned on labels. Frozen before the held-out run.", { x: M, y: 5.6, w: CW, h: 0.9, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
s.addNotes("The detector rarely boxes small weeds, so every connected green patch is a candidate. Rule 3 is self-calibrating against the crop plants in the same photo. Rule 4 is the strongest and our main weakness (two slides on).");

// 8 Headline
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
eyebrow(s, "Held-out headline");
s.addText("77.9%", { x: M, y: 1.0, w: 4.4, h: 1.2, fontFace: "Cambria", fontSize: 66, bold: true, color: C.accent2, margin: 0, isTextBox: true });
s.addText("weed recall (177 of 215 weeds hit)", { x: M, y: 2.2, w: 4.4, h: 0.5, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
s.addText("8.8%", { x: M, y: 3.0, w: 4.4, h: 1.2, fontFace: "Cambria", fontSize: 66, bold: true, color: C.text1, margin: 0, isTextBox: true });
s.addText("crop pixels sprayed (was 65.5%)", { x: M, y: 4.2, w: 4.4, h: 0.5, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
s.addText("95% less herbicide than blanket spraying of the same photos. Development set: 71.5% / 4.6%, so no sign of overfitting.", { x: M, y: 5.0, w: 4.4, h: 1.4, fontSize: 15, color: C.text2, margin: 0, isTextBox: true });
s.addImage({ path: IMG("tradeoff_holdout.png"), x: 5.4, y: 1.0, w: 7.33, h: 4.81, altText: "Crop pixels sprayed vs weed recall on 90 held-out photos: Grounded SAM settings near zero recall; plant rules at 77.9% recall, 8.8% crop" });
note(s, "90 held-out sugar beet photos, evaluated once. Source: docs/results/holdout_plant_rules_v3_20261018.md");
s.addNotes("Main result. On 90 unseen photos the product hits 77.9% of weed pixels and sprays 8.8% of crop pixels; every Grounded SAM setting sits on the bottom edge. Honest cost: 104 of 363 beets have at least one sprayed pixel, mostly edge specks. Cotton: only 10.4% recall.");

// 9 Verdicts
s = pres.addSlide({ masterName: "CONTENT_ALT", sectionTitle: "Results" });
eyebrow(s, "Where it fails");
s.addText("Every plant and its verdict", { placeholder: "title" });
s.addImage({ path: IMG("verdict_beet_X2-30-0.jpg"), x: M, y: 1.9, w: 5.9, h: 2.92, altText: "Beet X2-30-0 and verdict view: two of three beets red (sprayed)" });
s.addText([{ text: "Beet X2-30-0: ", options: { bold: true } }, { text: "two of three beets red (sprayed). Rule 4 calls an off-row plant a weed whatever its size." }], { x: M, y: 4.95, w: 5.9, h: 1.0, fontSize: 15, color: C.text2, margin: 0, isTextBox: true });
s.addImage({ path: IMG("verdict_cotton_CM_17.jpg"), x: 7.25, y: 1.9, w: 4.43, h: 2.92, altText: "Cotton CM_17 and verdict view: large amaranth weeds green (protected)" });
s.addText([{ text: "Cotton CM_17: ", options: { bold: true } }, { text: "the big amaranth weeds are green. The detector called them cotton, so the gate protected them." }], { x: 7.25, y: 4.95, w: 5.48, h: 1.0, fontSize: 15, color: C.text2, margin: 0, isTextBox: true });
note(s, "Red: sprayed · Green: protected as crop · Yellow: left alone. App view added 7 Nov (finding F28).");
s.addNotes("Finding F1: when the detector misses a beet's crop box, rule 4 sprays it as an off-row weed. A size limit on rule 4 cuts crop damage to 0.25% but recall to 13%; v3 stayed frozen because no unused held-out data is left. Cotton fails the other way: safe, weeds missed.");

// 10 Agent
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
eyebrow(s, "RQ2 · Escalation agent");
s.addText("Safe and precise, but not effective", { placeholder: "title" });
s.addText("Per withheld plant: row rule → Clef Flash → Qwen 3.8 VLM, under a call budget. Each answer is capped by the source’s measured accuracy; “weed” needs P ≥ 0.85, so one source alone can never decide.", { x: M, y: 2.2, w: 5.6, h: 2.4, fontSize: 17, color: C.text2, valign: "top", margin: 0, isTextBox: true });
s.addTable([
  [hdr("Plant was"), hdr("weed"), hdr("crop"), hdr("unsure")],
  ["crop (44)", "0", "13", "31"],
  ["weed (25)", "0", "1", "24"],
], { x: 6.7, y: 2.2, w: 6.03, colW: [2.1, 1.31, 1.31, 1.31], fontSize: 18, color: C.text2, border: { type: "solid", pt: 0.75, color: "C9D6CB" }, fill: { color: C.background1 }, rowH: 0.55, align: "center", margin: 0.08 });
s.addText([{ text: "Never approved a crop plant; 13 of 14 “crop” verdicts right; but " }, { text: "0 of 25 weeds", options: { bold: true } }, { text: " called weed. Spray map unchanged. Kept in the app, off by default, to explain withheld plants." }], { x: 6.7, y: 4.1, w: 6.03, h: 1.6, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
note(s, "69 withheld plants, development set. Source: docs/results/agent_v2_20261018.md");
s.addNotes("Answers RQ2. It never sprayed a crop plant but added no recall. The same Qwen model scored 16/20 on Groq and 12/20 on Cloudflare, so trust weights are tied to the provider. Plain rules beat the agent at zero model cost.");

// 11 Related work
pres.addSection({ title: "Context and conclusion" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Context and conclusion" });
eyebrow(s, "Base paper and related work");
s.addText("We implement Grounded SAM and confirm its known weakness", { placeholder: "title" });
s.addTable([
  [hdr("Work"), hdr("Setting"), hdr("Reported")],
  ["Ren et al. 2024, Grounded SAM", "Grounding DINO + SAM, zero-shot", "48.7 mAP on SegInW · our base pipeline"],
  ["Chong et al., IROS 2025 (WaW)", "SAM + BioCLIP, zero-shot", "weed IoU 12.1% vs 62.7% supervised"],
  ["Milioto et al., ICRA 2018", "supervised CNN, sugar beet", "weed IoU 20.6% RGB, 59.2% 14 channels"],
  ["Nasir et al. 2026", "6 commercial VLMs, zero-shot", "weed accuracy 0.15–0.75"],
], { x: M, y: 2.2, w: CW, colW: [4.2, 3.6, CW - 7.8], fontSize: 15, color: C.text2, border: { type: "solid", pt: 0.75, color: "C9D6CB" }, fill: { color: C.background1 }, rowH: 0.5, margin: 0.08 });
s.addText([{ text: "WaW argues text prompts are ill-defined for crop and weed; we measure it from the sprayer’s side. Different metric and data, so we " }, { text: "do not", options: { bold: true } }, { text: " claim to beat 12.1% IoU. Next: run on PhenoBench for a like-for-like number." }], { x: M, y: 5.3, w: CW, h: 1.2, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
s.addNotes("Grounded SAM is an arXiv report; Chong et al. (IROS 2025) is the peer-reviewed reference. Our numbers are vegetation pixels inside labelled boxes, not IoU against pixel masks, so not directly comparable. We add the sprayer's view.");

// 12 Testing
s = pres.addSlide({ masterName: "CONTENT_ALT", sectionTitle: "Context and conclusion" });
eyebrow(s, "Testing");
s.addText("Every finding traced to a fix or a stated limit", { placeholder: "title" });
[["270", "automated tests (235 unit, 35 end-to-end), CI on every push"],
 ["16", "system test cases on a fresh Windows install: 7 pass, 9 fail → 8 issues, all fixed"],
 ["29", "findings F1–F29 from a verification run and a manual cycle"],
 ["1×", "held-out evaluation; rerun reproduces every number exactly"]].forEach(([n, l], i) => {
  const w = (CW - 3 * 0.3) / 4, x = M + i * (w + 0.3);
  card(s, x, 2.2, w, 2.3);
  s.addText(n, { x: x + 0.25, y: 2.35, w: w - 0.5, h: 0.9, fontFace: "Cambria", fontSize: 44, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText(l, { x: x + 0.25, y: 3.3, w: w - 0.5, h: 1.4, fontSize: 14, color: C.text2, valign: "top", margin: 0, isTextBox: true });
});
s.addText("Examples: a rice herbicide dose above the ICAR maximum, corrected against the bulletin · GeoJSON upside down · Hindi summary called sugar beet “sweet potato” · a model-load crash on rerun.", { x: M, y: 4.9, w: CW, h: 1.0, fontSize: 16, color: C.text2, margin: 0, isTextBox: true });
s.addNotes("Unit and e2e tests in CI, Amit's system test cycle on fresh Windows, headless app regression, a verification run from a fresh clone, a manual cycle on six photos. Worst non-method finding: rice pyrazosulfuron stored at 20 g / 75 days vs the bulletin's 15 g / 95 days. Test cycle 2 runs to 12 Nov.");

// 13 Limits
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Context and conclusion" });
eyebrow(s, "Limitations and future work", C.accent2);
s.addText("Honest limits, and the next steps they point to", { placeholder: "title" });
const list = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
card(s, M, 2.2, CW / 2 - 0.2, 3.6);
s.addText("Limitations", { x: M + 0.3, y: 2.4, w: 5, h: 0.5, fontSize: 20, bold: true, color: C.accent2, margin: 0, isTextBox: true });
s.addText(list(["120 beet photos from one dataset; 8 cotton photos", "Box labels only: metrics are approximate", "Rules rely on weeds being smaller than the crop: 10.4% recall on cotton", "F1: whole off-row beets can be sprayed", "Held-out set now used; coordinates are not GPS; no field trial"]),
  { x: M + 0.3, y: 3.0, w: CW / 2 - 0.8, h: 3.2, fontSize: 15, color: C.text2, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
card(s, M + CW / 2 + 0.2, 2.2, CW / 2 - 0.2, 3.6);
s.addText("Future work", { x: M + CW / 2 + 0.5, y: 2.4, w: 5, h: 0.5, fontSize: 20, bold: true, color: C.accent1, margin: 0, isTextBox: true });
s.addText(list(["Weed IoU on PhenoBench, like-for-like with WaW", "BioCLIP plant features instead of text labels", "Few-shot detector adaptation with a handful of field photos", "“Safe mode” size limit on rule 4, tested on new data", "Farmer-facing conversational agent; real GPS; trial with an agronomist"]),
  { x: M + CW / 2 + 0.5, y: 3.0, w: CW / 2 - 0.8, h: 3.2, fontSize: 15, color: C.text2, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
s.addNotes("A research prototype, not a sprayer controller. Biggest limits: the rules exploit young sugar beet's size difference, so they do not carry to cotton; and F1. Next step, suggested by WaW itself: species-aware features such as BioCLIP.");

// 14 Team and contributions (counted from the repository: CONTRIBUTIONS.md)
s = pres.addSlide({ masterName: "CONTENT_ALT", sectionTitle: "Context and conclusion" });
eyebrow(s, "Team and contributions");
s.addText("Who built what, counted from the repository", { placeholder: "title" });
s.addTable([
  [hdr("Member"), hdr("Commits"), hdr("Current code"), hdr("Built")],
  ["Chaitanya Shinde (lead)", "94 of 97", "97.4%", "Design, vision pipeline, safety gate, plant rules, agent, System 2 integration, all experiments, all fixes, report and slides"],
  ["Amit Ingle", "1", "1.4%", "First dashboard (4 Oct); system test cycles 0 and 2 (8 issues filed in cycle 0)"],
  ["Sumant Vetal", "1", "1.3%", "First version of the System 2 code (5 Oct)"],
  ["Sahil Chavan", "1", "0%", "Dataset downloader and fixture sample (4 Oct)"],
], { x: M, y: 2.2, w: CW, colW: [2.9, 1.3, 1.6, CW - 5.8], fontSize: 15, color: C.text2, border: { type: "solid", pt: 0.75, color: "C9D6CB" }, fill: { color: C.background1 }, margin: 0.1, valign: "middle" });
note(s, "Commits without merges (git log); current Python code by last author (git blame); 7 Nov 2026, commit 6e2552a. Source: CONTRIBUTIONS.md");
s.addNotes("Numbers are counted, not estimated, and reproducible with scripts/contributions.py. Chaitanya designed and built the system and ran every measurement; Amit built the first dashboard and ran the system test cycles; Sumant wrote the first System 2 code; Sahil wrote the dataset downloader.");

// 15 Closing
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Context and conclusion" });
eyebrow(s, "Conclusion", "9FC7A5");
s.addText("Zero-shot prompts alone spray the crop or nothing. Transparent rules and a safety gate get to 77.9% of weeds at 8.8% crop, with no training.", { x: M, y: 1.6, w: 11.5, h: 2.6, fontFace: "Cambria", fontSize: 34, bold: true, color: C.background2, margin: 0, isTextBox: true });
s.addText("The agent stays safe but adds no recall. Every number is reproducible from the repository.", { x: M, y: 4.4, w: 11, h: 0.9, fontSize: 20, color: "DDE6DE", margin: 0, isTextBox: true });
s.addText("Live demo next · github.com/Chaitanya-666/agriAgent · Thank you", { x: M, y: 6.2, w: CW, h: 0.5, fontSize: 18, color: "BFD0C2", margin: 0, isTextBox: true });
s.addNotes("RQ1: text labels fail. RQ3: plain rules recover most of it on held-out photos. RQ2: the agent is safe but not effective. Then the app: beet X-10-0, spray map, every-plant view, Hindi summary, GeoJSON on geojson.io.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  // pptxgenjs cannot write theme colours; without this step the scheme colours fall back to
  // Office's stock palette. PPTX_SKILL_SCRIPTS = the folder holding apply_theme.js.
  if (process.env.PPTX_SKILL_SCRIPTS) {
    const { applyTheme } = require(path.join(process.env.PPTX_SKILL_SCRIPTS, "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } else {
    console.warn("PPTX_SKILL_SCRIPTS not set: theme colours not applied");
  }
  console.log(OUT);
})();
