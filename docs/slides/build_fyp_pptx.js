// Builds docs/slides/AgriAgent_FYP_Presentation.pptx: the department-format FYP deck
// (Nov 2026 guideline: Title, Motivation, Literature Survey, Gaps, Objectives, Proposed System
// and Implementation, Mathematical Model + Results, Conclusion, Future Scope, IEEE References).
// Same title and numbers as the LaTeX report in docs/report_latex.
//
//   NODE_PATH=<folder with node_modules/pptxgenjs@3.12> PPTX_SKILL_SCRIPTS=<pptx skill>/scripts \
//     node docs/slides/build_fyp_pptx.js
//
// Equation and architecture images: docs/slides/fyp_assets/*.tex (tectonic + pdftoppm -r 300).
// References: fyp_assets/refs.json, extracted from the compiled report, so the text is identical
// to the report's IEEE list; slide numbering follows first citation in this deck.

const path = require("path");
const pptxgen = require("pptxgenjs");
const REFS = require("./fyp_assets/refs.json");

const OUT = path.join(__dirname, "AgriAgent_FYP_Presentation.pptx");
const FIG = (n) => path.join(__dirname, "..", "report_latex", "figures", n);
const ASSET = (n) => path.join(__dirname, "fyp_assets", n);

const THEME = {
  name: "AgriAgent",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1C2620", lt1: "FFFFFF", dk2: "3D4741", lt2: "F4F7F2",
    accent1: "2F6B3A", accent2: "B4501A", accent3: "25466E",
    accent4: "E8EFE6", accent5: "F2A57A", accent6: "D3DFD2",
    hlink: "2F6B3A", folHlink: "6A746D",
  },
};
const MUTED = "6A746D";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "AgriAgent: A Safety-Gated Zero-Shot Vision Pipeline for Crop-Weed Spot Spraying";
pres.author = "Chaitanya Shinde, Amit Ingle, Sumant Vetal, Sahil Chavan (VJTI)";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, M = 0.6, CW = W - 2 * M;

// ── Layouts
const titlePh = {
  placeholder: {
    options: { name: "title", type: "title", x: M, y: 0.75, w: CW, h: 0.95, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text1, align: "left", valign: "top", margin: 0 },
    text: "Title",
  },
};
const footerObjs = [
  { text: { text: "AgriAgent · B.Tech FYP · VJTI 2026–27", options: { x: M, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: MUTED, margin: 0 } } },
];
const slideNo = { slideNumber: { x: W - M - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: MUTED, align: "right" } };
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.background1 }, objects: [titlePh, ...footerObjs], ...slideNo });
pres.defineSlideMaster({ title: "CONTENT_ALT", background: { color: C.background2 }, objects: [titlePh, ...footerObjs], ...slideNo });
pres.defineSlideMaster({ title: "DARK", background: { color: C.text1 }, ...slideNo });

// ── Helpers
const order = [];
const cite = (...keys) => "[" + keys.map((k) => {
  if (!REFS[k]) throw new Error("unknown reference " + k);
  if (!order.includes(k)) order.push(k);
  return order.indexOf(k) + 1;
}).join(", ") + "]";

const eyebrow = (s, text, color = C.accent1) =>
  s.addText(text.toUpperCase(), { x: M, y: 0.35, w: CW, h: 0.32, fontSize: 13, bold: true, charSpacing: 2, color, margin: 0, isTextBox: true, objectName: "eyebrow" });
const card = (s, x, y, w, h, fill = C.background2, line = C.accent6) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: fill }, line: { color: line, width: 1 }, objectName: "card" });
const note = (s, text) =>
  s.addText(text, { x: M, y: 6.62, w: CW, h: 0.35, fontSize: 11, color: MUTED, margin: 0, isTextBox: true, objectName: "source" });
const text = (s, t, x, y, w, h, o = {}) =>
  s.addText(t, { x, y, w, h, fontSize: 16, color: C.text2, valign: "top", margin: 0, isTextBox: true, ...o });
const bullets = (s, items, x, y, w, h, size = 16) =>
  s.addText(items.map((it, i) => ({ text: it, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontSize: size, color: C.text2, valign: "top", margin: 0, isTextBox: true });
const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent1 } } });
const table = (s, rows, o) => s.addTable(rows, {
  x: M, y: 1.85, w: CW, fontSize: 13, color: C.text2, valign: "middle",
  border: { type: "solid", pt: 0.75, color: "C9D6CB" }, fill: { color: C.background1 }, margin: 0.06, ...o,
});
const boxCard = (s, x, y, w, h, head, body, headColor = C.accent1, size = 15) => {
  card(s, x, y, w, h);
  text(s, head, x + 0.25, y + 0.18, w - 0.5, 0.45, { fontSize: 18, bold: true, color: headColor });
  text(s, body, x + 0.25, y + 0.7, w - 0.5, h - 0.85, { fontSize: size });
};
// Title: fill the layout placeholder but also pin geometry, so every renderer places it the same.
const TT = () => ({ placeholder: "title", x: M, y: 0.75, w: CW, h: 0.95, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text1, align: "left", valign: "top", margin: 0 });
const slide = (master, section) => pres.addSlide({ masterName: master, sectionTitle: section });

// ════════════════════════════════════════ 1 Title
pres.addSection({ title: "Title" });
let s = slide("DARK", "Title");
s.addText("B.TECH FINAL YEAR PROJECT · DEPARTMENT OF COMPUTER ENGINEERING AND IT · VJTI · 2026–27", { x: M, y: 0.55, w: CW, h: 0.4, fontSize: 14, bold: true, charSpacing: 2, color: "9FC7A5", margin: 0, isTextBox: true });
s.addText("AgriAgent", { x: M, y: 1.6, w: CW, h: 1.2, fontFace: "Cambria", fontSize: 60, bold: true, color: C.background1, margin: 0, isTextBox: true });
s.addText("A Safety-Gated Zero-Shot Vision Pipeline for Crop–Weed Spot Spraying", { x: M, y: 2.8, w: 11.5, h: 1.0, fontFace: "Cambria", fontSize: 28, color: "DDE6DE", margin: 0, isTextBox: true });
s.addTable([
  [{ text: "Chaitanya Shinde", options: { bold: true } }, "231070066"],
  [{ text: "Amit Ingle", options: { bold: true } }, "231070020"],
  [{ text: "Sumant Vetal", options: { bold: true } }, "roll no. pending"],
  [{ text: "Sahil Chavan", options: { bold: true } }, "roll no. pending"],
], { x: M, y: 4.25, w: 5.2, colW: [2.9, 2.3], fontSize: 16, color: "DDE6DE", border: { type: "none" }, margin: 0.03, rowH: 0.36 });
s.addText([
  { text: "Project guide", options: { breakLine: true, color: "9FC7A5", fontSize: 13, bold: true } },
  { text: "Prof. V. D. Dhore", options: { fontSize: 22, bold: true, color: C.background1 } },
], { x: 7.4, y: 4.3, w: 5.3, h: 1.0, margin: 0, isTextBox: true });
s.addText("Veermata Jijabai Technological Institute, Matunga, Mumbai 400019", { x: 7.4, y: 5.4, w: 5.3, h: 0.6, fontSize: 14, color: "BFD0C2", margin: 0, isTextBox: true });
s.addNotes("Introduce the team and the guide. One sentence: we measured how well zero-shot foundation models tell a weed from a crop plant for spot spraying, and how much a transparent safety layer recovers when they cannot.");

// ════════════════════════════════════════ 2–3 Motivation
pres.addSection({ title: "Motivation" });
s = slide("CONTENT", "Motivation");
eyebrow(s, "Motivation");
s.addText("Spot spraying saves herbicide only if the camera can tell a weed from the crop", TT());
boxCard(s, M, 2.0, 3.85, 3.0, "Blanket spraying today", "Herbicide goes on the whole field although weeds are patchy. Site-specific weed management treats only weed patches " + cite("gerhards2022sswm") + ".");
boxCard(s, M + 4.1, 2.0, 3.85, 3.0, "Nozzles are cheap", "A low-cost smart sprayer with a deep detector already opens nozzles only over targets " + cite("partel2019sprayer") + ". The hard part is the decision.");
boxCard(s, M + 8.2, 2.0, 3.93, 3.0, "Decision is the bottleneck", "Reliable weed identification has been the main barrier to robotic weed control for years " + cite("slaughter2008review") + ".", C.accent2);
text(s, "Two errors, not equal: a missed weed survives one pass; a false “weed” on a crop plant damages the crop the farmer is protecting.", M, 5.35, CW, 0.9, { fontSize: 18, italic: true, color: C.text1 });
s.addNotes("Why the topic matters: chemical use, cost, environment. The nozzle side is solved; the vision decision is not. Our main measure is therefore how much crop lands on the spray map.");

s = slide("CONTENT_ALT", "Motivation");
eyebrow(s, "Motivation · why zero-shot");
s.addText("Supervised models need labels from the same field; foundation models promise none", TT());
boxCard(s, M, 2.0, 5.95, 2.4, "Supervised crop–weed networks", "Accurate after training on labelled images of the target crop " + cite("milioto2018realtime", "lottes2018fcn") + ", but labels are expensive " + cite("hasan2021survey") + " and accuracy drops on new fields " + cite("weyler2023domain") + ".", C.accent1, 16);
boxCard(s, M + 6.18, 2.0, 5.95, 2.4, "Zero-shot foundation models", "Grounding DINO finds objects named in text " + cite("liu2024groundingdino") + "; SAM 2 outlines any object " + cite("ravi2025sam2") + ". Grounded SAM chains them " + cite("ren2024groundedsam") + ": “segment the weeds”, no labels.", C.accent3, 16);
card(s, M, 4.65, CW, 1.75, C.background1, C.accent1);
text(s, [
  { text: "Problem statement. ", options: { bold: true, color: C.accent1 } },
  { text: "Given an RGB field photo and the crop name, produce a spray map that covers the weeds and leaves the crop untouched, using pretrained models only, on a laptop GPU, with every spraying decision explainable and testable." },
], M + 0.3, 4.85, CW - 0.6, 1.4, { fontSize: 18 });
s.addNotes("A small Indian farm cannot label thousands of photos per crop and field. If zero-shot worked, that cost disappears. Chong et al. 2025 argue text prompts are ill-defined for crop vs weed; we measure it.");

// ════════════════════════════════════════ 4–7 Literature survey
pres.addSection({ title: "Literature survey" });
const litSlide = (eye, title, rows, notes, alt) => {
  const sl = slide(alt ? "CONTENT_ALT" : "CONTENT", "Literature survey");
  eyebrow(sl, eye);
  sl.addText(title, TT());
  table(sl, [[hdr("Paper"), hdr("Approach"), hdr("Result / limitation")], ...rows], { colW: [3.3, 3.9, CW - 7.2], fontSize: 12.5, rowH: 0.43 });
  sl.addNotes(notes);
  return sl;
};
litSlide("Literature survey 1/4 · zero-shot and foundation models", "Zero-shot models segment plants well; text labels are the weak point", [
  ["Chong et al. 2025, IROS " + cite("chong2025zeroshot"), "SAM + BioCLIP; weeds as anomalies of the crop", "Weed IoU 12.1% vs 62.7% supervised. Closest work."],
  ["Ren et al. 2024 (Grounded SAM) " + cite("ren2024groundedsam"), "Grounding DINO boxes → SAM masks", "48.7 AP on SegInW. Pipeline we implement."],
  ["Liu et al. 2024, ECCV " + cite("liu2024groundingdino"), "Open-set detector, text prompts", "52.5 AP zero-shot on COCO; label = prompt word"],
  ["Kirillov et al. 2023, ICCV " + cite("kirillov2023sam") + "; Ravi et al. 2025 " + cite("ravi2025sam2"), "Promptable segmentation (SAM, SAM 2)", "Strong zero-shot masks, but no class"],
  ["Stevens et al. 2024, CVPR " + cite("stevens2024bioclip"), "BioCLIP: tree-of-life features", "+16–17% on fine-grained biology tasks"],
  ["Singh et al. 2025 " + cite("singh2025fewshot"), "Few-shot Grounding DINO", "Zero-shot prompts struggle on similar classes"],
  ["Belissent et al. 2024, KBS " + cite("belissent2024transfer"), "Transfer + zero-shot weed classification", "77.8% fine-tuned; zero-shot unsatisfactory"],
  ["Zhang et al. 2024, IEEE TPAMI " + cite("zhang2024vlmsurvey"), "Survey of vision-language models", "Zero-shot recognition from image–text pre-training"],
  ["Nasir et al. 2026, Front. Plant Sci. " + cite("nasir2026vlmweed"), "Six commercial VLMs on soybean UAV images", "Weed accuracy 0.15–0.75: advise, not decide"],
], "The closest work, WaW, reaches 12.1% weed IoU zero-shot and argues text prompts are ill-defined for crop/weed. Grounded SAM is what we implement. VLM studies show they are unreliable alone, which is why our VLM agent only advises.");

litSlide("Literature survey 2/4 · supervised crop–weed segmentation", "Supervised networks work, but need labelled data from each field", [
  ["Milioto et al. 2018, ICRA " + cite("milioto2018realtime"), "Real-time CNN + vegetation indices", "Weed IoU 20.6% (RGB), 59.2% (14 channels)"],
  ["Lottes et al. 2018, IEEE RA-L " + cite("lottes2018fcn"), "FCN + image sequences along the row", "Generalises to unseen fields; uses crop arrangement"],
  ["Lottes et al. 2020, J. Field Robot. " + cite("lottes2020stem"), "Joint stem detection + segmentation", "Plant-specific treatment; supervised"],
  ["Weyler et al. 2023, IEEE RA-L " + cite("weyler2023domain"), "Domain generalisation, auto labels from rows", "Models trained on one field drop on others"],
  ["Weyler et al. 2024, IEEE TPAMI " + cite("weyler2024phenobench"), "PhenoBench: UAV, pixel crop/weed labels", "Benchmark incl. an unseen field"],
  ["Chebrolu et al. 2017, IJRR " + cite("chebrolu2017sugarbeet"), "Bonn sugar beet robot dataset", "3 months, multi-sensor; one farm"],
  ["Long et al. 2017, IEEE TPAMI " + cite("long2017fcn"), "Fully convolutional networks", "Dense pixel prediction end to end"],
  ["Badrinarayanan 2017 " + cite("badrinarayanan2017segnet") + "; Chen 2018 " + cite("chen2018deeplab") + ", TPAMI", "SegNet encoder–decoder; DeepLab atrous + CRF", "Standard segmentation backbones"],
  ["Romera 2018, IEEE T-ITS " + cite("romera2018erfnet") + "; Ren 2017, TPAMI " + cite("ren2017fasterrcnn"), "ERFNet real-time seg.; Faster R-CNN", "ERFNet = WaW's supervised baseline"],
], "This is the supervised ceiling. The key gap: every one of these needs labelled data from the same crop and conditions, and Weyler 2023 shows they degrade on new fields.", true);

litSlide("Literature survey 3/4 · weed detection and classification", "Vegetation indices separate plant from soil; deep models need per-crop labels", [
  ["Woebbecke et al. 1995, Trans. ASAE " + cite("woebbecke1995color"), "Colour indices for weeds", "ExG = 2g−r−b among the best; we use it"],
  ["Hamuda et al. 2016, Comput. Electron. Agric. " + cite("hamuda2016survey"), "Survey of plant extraction", "Colour index + automatic threshold (Otsu)"],
  ["Wang et al. 2019, Comput. Electron. Agric. " + cite("wang2019review"), "Review of ground-based weed detection", "Crop vs weed similarity is the hard step"],
  ["Dyrmann et al. 2016, Biosyst. Eng. " + cite("dyrmann2016species"), "CNN, 22 crop and weed species", "86.2% accuracy"],
  ["dos Santos Ferreira 2017, Comput. Electron. Agric. " + cite("dossantos2017soybean"), "ConvNet on soybean UAV superpixels", "Soil / soybean / grass / broadleaf"],
  ["Olsen et al. 2019, Sci. Rep. " + cite("olsen2019deepweeds"), "DeepWeeds: 17,509 images, 8 species", "95.7% accuracy (ResNet-50)"],
  ["Jiang et al. 2020, Comput. Electron. Agric. " + cite("jiang2020gcn"), "Semi-supervised graph CNN", "96.5–99.4% on four weed sets"],
  ["Rahman et al. 2023, Smart Agric. Technol. " + cite("rahman2023cotton"), "13 detectors on CottonWeedDet3", "79.98% mAP@0.5; our cotton data"],
  ["Dang et al. 2023, Comput. Electron. Agric. " + cite("dang2023yoloweeds"), "25 YOLO detectors, CottonWeedDet12", "Supervised cotton benchmark"],
], "Woebbecke's excess-green index is literally the first step of our plant rules. Rahman 2023 is the source of our cotton photos; its 80% mAP is the trained ceiling for that data.");

litSlide("Literature survey 4/4 · spraying, rows, surveys, LLMs and agents", "Planting rows replace labels; language models must stay grounded", [
  ["Slaughter et al. 2008, Comput. Electron. Agric. " + cite("slaughter2008review"), "Review of robotic weed control", "Weed identification = main barrier"],
  ["Gerhards et al. 2022, Weed Res. " + cite("gerhards2022sswm") + "; Partel 2019 " + cite("partel2019sprayer"), "Site-specific weed management; smart sprayer", "71% precision, 78% recall on real plants"],
  ["Bah et al. 2018, Remote Sens. " + cite("bah2018unsupervised"), "Inter-row vegetation = weed auto-labels", "Within 1.5–6% of manual labelling"],
  ["Louargant et al. 2018, Remote Sens. " + cite("louargant2018rowcrops"), "Row position + spectral SVM", "89% weed detection rate"],
  ["Kamilaris 2018 " + cite("kamilaris2018dl") + ", Hasan 2021 " + cite("hasan2021survey") + ", Comput. Electron. Agric.", "Surveys of deep learning in agriculture / weeds", "DL beats classical; labels are the cost"],
  ["Tian 2020, Inf. Process. Agric. " + cite("tian2020cv") + "; Lu 2020 " + cite("lu2020datasets"), "Review of agri. CV; survey of 34 datasets", "Need large, varied datasets"],
  ["Yin et al. 2025, Agriculture " + cite("yin2025foundation"), "Review of agricultural foundation models", "Data shift, data acquisition challenges"],
  ["Kuska 2024 " + cite("kuska2024llm") + "; Li 2025, Artif. Intell. Agric. " + cite("li2025llmagri"), "LLMs for crop production / agri. knowledge", "Need grounding in verified knowledge"],
  ["Wang et al. 2024, Front. Comput. Sci. " + cite("wang2024agents"), "Survey of LLM-based autonomous agents", "Planning + tools; our agent is bounded"],
], "Bah and Louargant use the planting row to replace labels: our rules 2 and 4 use the same idea on single ground photos. The LLM reviews motivate our rule that every herbicide dose comes from the ICAR bulletin, not the model.", true);

// ════════════════════════════════════════ 8 Gaps
pres.addSection({ title: "Literature gaps" });
s = slide("CONTENT", "Literature gaps");
eyebrow(s, "Literature gaps");
s.addText("Five gaps the survey leaves open", TT());
const gaps = [
  ["G1", "Supervised accuracy needs labels from the same field " + cite("hasan2021survey", "weyler2023domain") + "."],
  ["G2", "Text-prompted zero-shot pipelines were argued, not measured, to fail for crop vs weed " + cite("chong2025zeroshot", "singh2025fewshot") + "."],
  ["G3", "Papers report IoU / mAP, not what a sprayer needs: crop sprayed, weeds hit, herbicide saved " + cite("milioto2018realtime", "rahman2023cotton") + "."],
  ["G4", "No deterministic, testable safety gate between models and nozzle; VLMs unreliable alone " + cite("partel2019sprayer", "nasir2026vlmweed") + "."],
  ["G5", "Language-model advice is not grounded in national herbicide regulation " + cite("li2025llmagri", "choudhury2016icar") + "."],
];
gaps.forEach(([id, t], i) => {
  const y = 1.95 + i * 0.9;
  s.addShape(pres.shapes.OVAL, { x: M, y: y + 0.05, w: 0.62, h: 0.62, fill: { color: i === 1 ? C.accent2 : C.accent1 }, line: { color: C.background1, width: 0 }, objectName: "gap-badge" });
  text(s, id, M, y + 0.13, 0.62, 0.45, { fontSize: 15, bold: true, color: C.background1, align: "center" });
  text(s, t, M + 0.9, y + 0.08, CW - 0.9, 0.7, { fontSize: 17, valign: "middle" });
});
s.addNotes("Each gap maps to an objective. G2 and G3 are the core research gap: nobody measured Grounded SAM on the sprayer's metrics. G4 is our design contribution: a gate that is the only authority.");

// ════════════════════════════════════════ 9 Base paper
s = slide("CONTENT_ALT", "Literature gaps");
eyebrow(s, "Base paper and positioning");
s.addText("We implement Grounded SAM and measure the weakness the closest work describes", TT());
boxCard(s, M, 2.0, 5.95, 3.2, "Base pipeline: Grounded SAM " + cite("ren2024groundedsam"), "Grounding DINO-tiny → SAM 2-tiny, zero-shot, prompt “weed . <crop> plant .”. arXiv report, so the peer-reviewed reference point is the closest work.", C.accent1, 16);
boxCard(s, M + 6.18, 2.0, 5.95, 3.2, "Closest work: WaW, IROS 2025 " + cite("chong2025zeroshot"), "SAM + BioCLIP features; crop = common plant, weeds = outliers. Weed IoU 12.1% vs 62.7% supervised. Argues text prompts are ill-defined for crop and weed.", C.accent3, 16);
text(s, [
  { text: "Our addition: ", options: { bold: true, color: C.accent1 } },
  { text: "the sprayer's view (crop on the map, weeds hit, herbicide saved) and a transparent safety layer, without training. We do not claim to beat WaW's IoU: different metric and data." },
], M, 5.5, CW, 1.0, { fontSize: 17 });
s.addNotes("Prof. Dhore asked: did we implement the base paper? Yes, Grounded SAM with SAM 2 in place of SAM. WaW is the comparison point; a like-for-like run on PhenoBench is the first future-work item.");

// ════════════════════════════════════════ 10 Objectives
pres.addSection({ title: "Objectives" });
s = slide("CONTENT", "Objectives");
eyebrow(s, "Objectives and research questions");
s.addText("Six objectives, three measurable questions", TT());
bullets(s, [
  "O1 Run Grounding DINO + SAM 2 zero-shot on a laptop GPU (8 GB)",
  "O2 Deterministic safety gate = the only authority to spray",
  "O3 Measure crop sprayed, weed recall, saving on official labels; held-out set used once",
  "O4 Test one bounded escalation agent on withheld plants",
  "O5 Herbicide advice only from the ICAR bulletin " + cite("choudhury2016icar"),
  "O6 Working app, GeoJSON export, farmer summary (EN/HI/MR)",
], M, 1.95, 6.2, 4.5, 16);
[["RQ1", "How well does Grounded SAM separate weed from crop (weed recall, crop pixels sprayed)?"],
 ["RQ2", "Does escalating unsure plants to VLMs make the map more complete without making it less safe?"],
 ["RQ3", "Which cheap addition (gate, crop exclusion, row and size rules) cuts crop damage most, and at what recall cost?"]]
  .forEach(([id, q], i) => boxCard(s, 7.2, 1.85 + i * 1.6, 5.53, 1.5, id, q, i === 0 ? C.accent2 : C.accent1, 14));
s.addNotes("Objectives map to gaps: O1/O3 to G1–G3, O2/O4 to G4, O5/O6 to G5. Success criteria: real models, official labels, reproducible script, headline measured once on held-out photos.");

// ════════════════════════════════════════ 11–17 Proposed system and implementation
pres.addSection({ title: "Proposed system" });
s = slide("CONTENT", "Proposed system");
eyebrow(s, "Proposed system · architecture");
s.addText("System 1 decides locally; System 2 only advises", TT());
s.addImage({ path: ASSET("arch.png"), x: M, y: 1.75, w: 5.1, h: 4.87, altText: "AgriAgent pipeline: detect, segment, plant rules, safety gate, then optional escalation agent and System 2 with ICAR, output app and GeoJSON" });
boxCard(s, 6.1, 1.85, 6.63, 2.2, "System 1 · local, deterministic", "Grounding DINO-tiny + SAM 2-tiny on the RTX 5050, plant rules, safety gate. 0.6 s per photo. Same input → same output.", C.accent1, 15);
boxCard(s, 6.1, 4.25, 6.63, 2.2, "System 2 · cloud, advisory", "Qwen 3.8 VLM and Clef Flash on Cloudflare Workers AI " + cite("doc_cloudflare") + ": diagnosis, escalation, farmer summary. Never sprays anything on its own.", C.accent3, 15);
s.addNotes("Walk the pipeline top to bottom. The yellow box, the gate, is the only component allowed to approve a spray zone. Everything blue can be wrong without causing a spray.");

s = slide("CONTENT_ALT", "Proposed system");
eyebrow(s, "Proposed system · safety gate");
s.addText("The gate withholds anything uncertain; failure means “do not spray”", TT());
table(s, [
  [hdr("Rule"), hdr("Spray a detector mask only if …")],
  ["Label policy", "its label names a weed, and not the crop (mixed labels such as “weed sugar beet plant” are withheld)"],
  ["Confidence", "detector score ≥ 0.70 (the app slider may raise it, never lower it)"],
  ["Mask quality", "SAM 2 predicted quality ≥ 0.85 (re-prompted with a corrective point below that)"],
  ["One plant", "the mask covers ≤ 50% of the photo (otherwise it is the whole field)"],
  ["Infestation", "approved zones ≤ 85% of the photo, else the whole map is suppressed"],
  ["Plant rules", "“weed” patches are approved after every crop pixel is removed; “unsure” never"],
  ["Fail safe", "any exception, missing input or missing evidence → withhold"],
], { colW: [2.4, CW - 2.4], fontSize: 15, rowH: 0.52 });
note(s, "Code: src/agents/deterministic_router.py, src/workflow.py. Each rule has unit tests with real values.");
s.addNotes("An early version passed confidence and quality as 1.0, so every weed label was sprayed. Found in code review and fixed before any measurement. That is why every rule now has a test with real values.");

s = slide("CONTENT", "Proposed system");
eyebrow(s, "Proposed system · plant rules v3 (frozen)");
s.addText("Four plain rules classify every green patch, with no training", TT());
table(s, [
  [hdr("#"), hdr("Verdict"), hdr("When (checked in this order)")],
  ["1", "crop", "≥ 30% of the patch lies inside a SAM 2 mask labelled as the crop"],
  ["2", "crop", "the photo shows clear rows and the patch is on the row band"],
  ["3", "weed", "crop masks exist and the patch is < ¼ of the median crop plant (else unsure)"],
  ["4", "weed", "no crop masks, clear rows, patch off the row " + cite("bah2018unsupervised", "louargant2018rowcrops")],
  ["5", "unsure", "anything else: never sprayed"],
], { colW: [0.7, 1.5, CW - 2.2], fontSize: 16, rowH: 0.55 });
text(s, "Patches = connected components of the excess-green mask " + cite("woebbecke1995color") + " with a per-photo Otsu threshold " + cite("hamuda2016survey") + ", leaf gaps closed. Developed on 30 photos, frozen, then run once on 90 held-out photos.", M, 5.35, CW, 1.1, { fontSize: 16 });
s.addNotes("The detector rarely boxes small weeds, so every green patch is a candidate. Rule 3 self-calibrates against crop plants in the same photo. Rule 4 is the strongest and the main weakness (F1), shown later.");

s = slide("CONTENT_ALT", "Proposed system");
eyebrow(s, "Proposed system · escalation agent and ICAR advice");
s.addText("One bounded agent, and herbicide doses only from the bulletin", TT());
boxCard(s, M, 1.95, 5.95, 4.45, "Escalation agent (optional)", "For each withheld plant, largest first, up to 3 per photo:\n\nrow rule → Clef Flash → Qwen 3.8 VLM on the plant crop, cheapest first, under a call budget.\n\nEach answer is weighted by the source's measured accuracy and combined naive-Bayes style; “weed” needs P ≥ 0.85, so one source alone never decides. Full trace kept. Advice only: the gate still decides.", C.accent3, 15);
boxCard(s, M + 6.18, 1.95, 5.95, 4.45, "System 2 + ICAR knowledge store", "The VLM names crop, weed and growth stage. The herbicide comes only from the ICAR–DWR bulletin row for the declared crop and a matching weed " + cite("choudhury2016icar") + ".\n\nDoses clamped to the bulletin maximum; banned / withdrawn herbicides rejected; no matching row → “no evidence”.\n\nFarmer summary in EN / HI / MR; safety sentences are fixed text, never left to the model.", C.accent1, 15);
s.addNotes("The agent is the only agentic part, deliberately small (fixed tools, budget, no authority), in contrast to general LLM agents. Every ICAR row was checked against the PDF; a dangerous rice dose was found and fixed.");

s = slide("CONTENT", "Proposed system");
eyebrow(s, "Proposed system · datasets");
s.addText("Two public datasets with official labels, and the ICAR bulletin", TT());
const link = (label, url) => ({ text: label, options: { hyperlink: { url }, color: C.accent3, underline: { style: "sng" } } });
table(s, [
  [hdr("Dataset"), hdr("Contents"), hdr("Link"), hdr("Used for")],
  ["sugarbeetsAndweeds " + cite("data_sugarbeets"), "120 photos, 512×512, Pascal VOC boxes (sugar beet, weed)", link("kaggle.com/datasets/wangyongkun/sugarbeetsandweeds", "https://www.kaggle.com/datasets/wangyongkun/sugarbeetsandweeds"), "30 dev + 90 held-out"],
  ["CottonWeedDet3 " + cite("data_cottonweeddet3", "rahman2023cotton"), "848 cotton-field photos, 3 weed classes; cotton not labelled", link("kaggle.com/datasets/yuzhenlu/cottonweeddet3", "https://www.kaggle.com/datasets/yuzhenlu/cottonweeddet3"), "8 dev photos"],
  ["ICAR–DWR Bulletin No. 22 " + cite("choudhury2016icar"), "Approved herbicides per crop: dose, water, waiting period; banned list", link("dwr.icar.gov.in", "https://dwr.icar.gov.in"), "System 2 knowledge store"],
  ["PhenoBench " + cite("weyler2024phenobench"), "UAV, pixel-wise crop / weed labels", link("phenobench.org", "https://www.phenobench.org"), "Future: weed IoU vs WaW"],
], { colW: [2.7, 3.6, 3.75, CW - 10.05], fontSize: 13, rowH: 0.75 });
note(s, "All labels copied unchanged from the official files by scripts/build_eval_manifest_v2.py; rebuilding from a fresh download gives an identical manifest.");
s.addNotes("The sugar beet images resemble the Bonn dataset of Chebrolu et al. but the uploader does not document the origin; we say so in the report. Cotton itself is never labelled, so crop-sprayed cannot be computed for cotton.");

s = slide("CONTENT_ALT", "Proposed system");
eyebrow(s, "Implementation");
s.addText("Python, two tiny vision models, a Streamlit app, 270 tests", TT());
table(s, [
  [hdr("Layer"), hdr("Choice")],
  ["Vision", "grounding-dino-tiny + sam2-hiera-tiny via Hugging Face Transformers " + cite("doc_transformers") + "; PyTorch 2.11, CUDA 12.8"],
  ["Reasoning", "Qwen 3.8 27B + Clef Flash on Cloudflare Workers AI (free tier); Groq " + cite("doc_groq") + " as alternative"],
  ["App and export", "Streamlit " + cite("doc_streamlit") + " dashboard; GeoJSON spray map " + cite("rfc7946") + " (marked: not GPS)"],
  ["Hardware", "RTX 5050 laptop, 8 GB; both models peak ≈ 2.4 GB; also tested on RTX 3050 4 GB"],
  ["Quality", "235 unit + 35 end-to-end tests, ruff, mypy, GitHub Actions; release v1.0.0"],
], { colW: [2.5, CW - 2.5], fontSize: 15, rowH: 0.62 });
text(s, "Honesty rules: every screen says REAL or MOCK; a real run that cannot load a model fails loudly instead of showing fake output.", M, 5.6, CW, 0.8, { fontSize: 16, italic: true, color: C.text1 });
s.addNotes("Modules: grounding_dino.py, sam2_wrapper.py, model_cache.py, plant_candidates.py, workflow.py, deterministic_router.py, escalation_agent.py, agronomy/, evaluation/, app/. Mock mode lets tests run without the 1.5 GB of weights.");

s = slide("CONTENT", "Proposed system");
eyebrow(s, "Implementation · demo");
s.addText("The application on real photos", TT());
s.addImage({ path: FIG("real_run_beet_after_gate_fix.jpg"), x: M, y: 1.8, w: 6.0, h: 1.5, sizing: { type: "contain", w: 6.0, h: 1.5 }, altText: "Real run on a sugar beet photo: photo, boxes, masks, empty spray map" });
text(s, "Baseline behaviour: detector confidences 0.36–0.47 < 0.70, so nothing is sprayed. Crop safe, weeds missed.", M, 3.4, 6.0, 0.8, { fontSize: 14 });
s.addImage({ path: FIG("verdict_beet_X2-30-0.jpg"), x: 6.9, y: 1.8, w: 5.83, h: 2.88, sizing: { type: "contain", w: 5.83, h: 2.88 }, altText: "Verdict view on beet X2-30-0: red sprayed, green protected, yellow left alone" });
text(s, "Verdict view: red sprayed, green protected as crop, yellow left alone.", 6.9, 4.75, 5.83, 0.5, { fontSize: 14 });
card(s, M, 4.4, 6.0, 2.05, C.background2, C.accent6);
text(s, [
  { text: "Live demo (≈ 2 min)", options: { bold: true, color: C.accent1, breakLine: true } },
  { text: "Upload beet photo → spray map and KPIs → every-plant view → Hindi summary → GeoJSON on geojson.io. A screen recording is kept as backup." },
], M + 0.25, 4.55, 5.5, 1.8, { fontSize: 15 });
s.addNotes("If the live demo fails, play the backup recording. Show the REAL banner first so the examiners know it is not mock output.");

// ════════════════════════════════════════ 18–19 Mathematical model
pres.addSection({ title: "Mathematical model" });
s = slide("CONTENT", "Mathematical model");
eyebrow(s, "Mathematical model 1/2 · vegetation, rows and plant rules");
s.addText("Every green patch P gets a verdict from a piecewise rule", TT());
s.addImage({ path: ASSET("eq_veg.png"), x: M, y: 1.8, w: 5.9, h: 2.04, altText: "ExG = 2G − R − B; Otsu threshold maximising between-class variance; vegetation mask and closing; row peakiness ≥ 2 and on-row test" });
s.addImage({ path: ASSET("eq_rules.png"), x: 6.8, y: 1.8, w: 5.93, h: 2.6, sizing: { type: "contain", w: 5.93, h: 2.6 }, altText: "Classifier f(P): crop if overlap ≥ 0.3; crop if on row; weed if smaller than a quarter of the median crop; unsure if crop masks exist; weed if off row and no crop masks; else unsure" });
bullets(s, [
  "ExG: excess-green index " + cite("woebbecke1995color") + "; τ*: Otsu threshold per photo",
  "Closing radius r = 1% of the long side joins leaves of one plant",
  "C: union of SAM 2 masks labelled crop; m̃: median crop size in the same photo",
  "Line 5 is reached only when C = ∅: exactly the F1 failure case",
], M, 4.6, CW, 1.9, 15);
s.addNotes("Explain each term. Vegetation, closing, components and rows are all O(HW), linear in image size. The order of the cases matters: rule 4 (off-row = weed) only applies when the detector found no crop at all.");

s = slide("CONTENT_ALT", "Mathematical model");
eyebrow(s, "Mathematical model 2/2 · gate, agent and metrics");
s.addText("The gate is a predicate; the agent combines odds; metrics are pooled ratios", TT());
s.addImage({ path: ASSET("eq_gate.png"), x: M, y: 1.8, w: 6.6, h: 1.55, sizing: { type: "contain", w: 6.6, h: 1.55 }, altText: "Gate predicate g_i and spray set S with infestation ceiling 0.85" });
s.addImage({ path: ASSET("eq_agent.png"), x: M, y: 3.5, w: 7.6, h: 1.43, sizing: { type: "contain", w: 7.6, h: 1.43 }, altText: "Agent: r = a c + (1 − a)(1 − c); odds product; P(weed) = O/(1+O); thresholds 0.85 and 0.15" });
s.addImage({ path: ASSET("eq_metrics.png"), x: M, y: 5.1, w: 9.0, h: 1.16, sizing: { type: "contain", w: 9.0, h: 1.16 }, altText: "Crop sprayed, weed recall and herbicide saved as pooled pixel ratios" });
boxCard(s, 9.0, 1.85, 3.73, 3.1, "Worked example", "Clef (a = 0.70) and Qwen (a = 0.80) both say “weed” with c = 1:\nO = (0.7/0.3)(0.8/0.2) = 9.33\nP = 0.90 ≥ 0.85 → weed.\nOne source alone: P ≤ 0.80.", C.accent2, 14);
note(s, "G_c, G_w: vegetation inside crop / weed boxes (weed minus crop). Unit-tested on hand-computed 5×5 grids, e.g. crop 2/6 = 33.3%, recall 3/4 = 75%, saving 80%.");
s.addNotes("Gate symbols: W = label names a weed, C = names the crop, s = detector confidence, q = SAM 2 quality. Agent weights row 0.65, Clef 0.70, Qwen 0.80, measured on 20 labelled patches.");

// ════════════════════════════════════════ 20–25 Results
pres.addSection({ title: "Results" });
s = slide("CONTENT", "Results");
eyebrow(s, "Evaluation method");
s.addText("We found a fabricated evaluation set, replaced it, and held 90 photos out", TT());
s.addImage({ path: FIG("audit_beet_X-10-0.jpg"), x: M, y: 1.85, w: 6.0, h: 2.6, sizing: { type: "contain", w: 6.0, h: 2.6 }, altText: "Label audit of beet X-10-0: old template labels on the left, official labels on the right" });
text(s, "Old set v1: every beet image had the same 2 crop + 6 weed boxes; cotton had cotton boxes that the official data never labels. Withdrawn.", M, 4.55, 6.0, 1.3, { fontSize: 15 });
table(s, [
  [hdr("Set"), hdr("Photos"), hdr("Labels"), hdr("Use")],
  ["v2 development", "30 beet + 8 cotton", "93 beets, 282 weeds", "every design decision"],
  ["v2 held-out", "90 beet", "363 beets, 215 weeds", "run once, 18 Oct, rules frozen"],
], { x: 6.9, y: 1.85, w: 5.83, colW: [1.5, 1.35, 1.48, 1.5], fontSize: 13, rowH: 0.7 });
text(s, "Repeat run on 23 Oct reproduced every number exactly; the pipeline is deterministic.", 6.9, 4.4, 5.83, 0.9, { fontSize: 15 });
s.addNotes("This is our main lesson on honesty: AI-generated labels looked real but were a template. All ground truth is now copied from the official XML by a script.");

s = slide("CONTENT_ALT", "Results");
eyebrow(s, "RQ1 · Grounded SAM baseline");
s.addText("Text labels fail: sprays the crop or sprays nothing", TT());
table(s, [
  [hdr("Setting (dev set, 30 beet photos)"), hdr("Crop sprayed %"), hdr("Weed recall %"), hdr("Saved %"), hdr("Beets touched")],
  ["every_mask (spray all SAM 2 masks)", "93.9", "97.6", "39.3", "87/93"],
  ["gate 0.35", "70.8", "9.0", "93.0", "45/93"],
  ["gate 0.50", "20.5", "6.8", "98.0", "8/93"],
  ["gate 0.50 + crop exclusion", "5.3", "6.8", "99.3", "2/93"],
  ["gate 0.70 (deployed)", "0.0", "0.0", "100.0", "0/93"],
], { colW: [4.6, 1.9, 1.9, 1.7, CW - 10.1], fontSize: 15, rowH: 0.52, align: "center" });
text(s, [
  { text: "Analysis. ", options: { bold: true, color: C.accent2 } },
  { text: "SAM 2 masks are good (97.6% recall when everything is sprayed); the labels are the problem. Real detector scores never exceeded 0.68, so the 0.70 gate is safe and useless. Agrees with WaW " + cite("chong2025zeroshot") + "." },
], M, 5.15, CW, 1.3, { fontSize: 16 });
note(s, "Source: docs/results/baseline_v2_20261018.md, exclusion_v2_20261018.md");
s.addNotes("Answer to RQ1. Lowering the threshold buys recall only by spraying the crop. Tiling and lower box thresholds (not shown) find more plants but label them no better: the bottleneck is classification, not detection.");

s = slide("CONTENT", "Results");
eyebrow(s, "Headline · held-out set, evaluated once");
s.addText("Plant rules: 77.9% weed recall at 8.8% crop sprayed", TT());
s.addText("77.9%", { x: M, y: 1.8, w: 4.3, h: 1.0, fontFace: "Cambria", fontSize: 60, bold: true, color: C.accent2, margin: 0, isTextBox: true });
text(s, "weed recall (177 of 215 weeds); Grounded SAM 1.8%", M, 2.8, 4.3, 0.6, { fontSize: 15 });
s.addText("8.8%", { x: M, y: 3.45, w: 4.3, h: 1.0, fontFace: "Cambria", fontSize: 60, bold: true, color: C.text1, margin: 0, isTextBox: true });
text(s, "crop pixels sprayed; Grounded SAM 65.5%", M, 4.45, 4.3, 0.6, { fontSize: 15 });
text(s, "95% herbicide saved vs blanket spraying. Dev set 71.5% / 4.6%: no sign of overfitting. Cost: 104 of 363 beets touched, mostly edge specks.", M, 5.1, 4.3, 1.4, { fontSize: 14 });
s.addImage({ path: FIG("tradeoff_holdout.png"), x: 5.2, y: 1.75, w: 7.53, h: 4.8, sizing: { type: "contain", w: 7.53, h: 4.8 }, altText: "Crop pixels sprayed vs weed recall on 90 held-out photos: Grounded SAM settings near zero recall; plant rules at 77.9% recall, 8.8% crop" });
note(s, "90 held-out sugar beet photos. Source: docs/results/holdout_plant_rules_v3_20261018.md. Cotton: only 10.4% recall (weeds there are not smaller than the crop).");
s.addNotes("Answer to RQ3: plain rules on crop overlap, rows and relative size give the best trade-off measured, with no training and no model calls, at 0.6 s per photo.");

s = slide("CONTENT_ALT", "Results");
eyebrow(s, "RQ2 · escalation agent and VLMs");
s.addText("The agent is safe and precise, but adds no recall", TT());
table(s, [
  [hdr("Plant really was"), hdr("Agent: weed"), hdr("crop"), hdr("unsure")],
  ["crop (44)", "0", "13", "31"],
  ["weed (25)", "0", "1", "24"],
], { x: M, y: 1.9, w: 5.9, colW: [2.3, 1.2, 1.2, 1.2], fontSize: 16, rowH: 0.55, align: "center" });
text(s, "69 withheld plants: never approved a crop plant; 13 of 14 “crop” verdicts right; 0 of 25 weeds called weed. Spray map unchanged.", M, 3.75, 5.9, 1.5, { fontSize: 16 });
table(s, [
  [hdr("Source (20 labelled patches)"), hdr("Correct")],
  ["Qwen 3.8 on Groq", "16/20"],
  ["Qwen 3.8 on Cloudflare", "12/20"],
  ["Clef Flash", "14/20"],
  ["Row rule, no model", "13/20"],
], { x: 6.9, y: 1.9, w: 5.83, colW: [4.3, 1.53], fontSize: 15, rowH: 0.5 });
text(s, "Same model, two providers: 16 vs 12 (F25). Trust weights belong to the provider they were measured on. Consistent with " + cite("nasir2026vlmweed") + ".", 6.9, 4.6, 5.83, 1.3, { fontSize: 15 });
note(s, "Source: docs/results/agent_v2_20261018.md, t2_2_crop_or_weed_groq_20261017.json, qwen_provider_check_20261030.md");
s.addNotes("Answer to RQ2: escalation combined conservatively is safe but not effective on this data. Kept in the app, off by default, to explain withheld plants.");

s = slide("CONTENT", "Results");
eyebrow(s, "Limitation F1");
s.addText("Rule 4 sprays a whole beet when the detector misses it", TT());
s.addImage({ path: FIG("verify_rotation_X-10-0.jpg"), x: M, y: 1.8, w: 6.2, h: 3.4, sizing: { type: "contain", w: 6.2, h: 3.4 }, altText: "Photo X-10-0 rotated 90 degrees: no crop box, the largest beet is sprayed completely" });
text(s, "X-10-0 rotated 90°: no crop box, so the largest beet (4,410 px) is called an off-row weed.", M, 5.3, 6.2, 0.9, { fontSize: 15 });
table(s, [
  [hdr("Rule 4 size limit (× median plant)"), hdr("Crop %"), hdr("Recall %"), hdr("Beets sprayed")],
  ["0.25", "0.25", "12.9", "0"],
  ["1.0", "0.98", "31.3", "3"],
  ["1.5", "1.20", "39.1", "4"],
  ["none (v3, frozen)", "4.55", "71.5", "11"],
], { x: 7.1, y: 1.85, w: 5.63, colW: [2.5, 0.95, 1.05, 1.13], fontSize: 14, rowH: 0.55, align: "center" });
text(s, "Rule 4 gives most of the recall and most of the damage. v3 stays frozen (no unused held-out data left); a size-limited “safe mode” is future scope.", 7.1, 4.8, 5.63, 1.5, { fontSize: 15 });
note(s, "Development set only. Source: scripts/experiment_f1_row_rule.py; docs/testing/Verification_Report_20261023.md");
s.addNotes("Say this before the examiners find it. The same mechanism explains F18: a wrong crop setting gives no crop masks, so rule 4 fires. The app now warns when no plant matched the declared crop.");

s = slide("CONTENT_ALT", "Results");
eyebrow(s, "Testing and release");
s.addText("270 automated tests, three manual cycles, 30 findings traced", TT());
table(s, [
  [hdr("Level"), hdr("What"), hdr("Result")],
  ["Unit + end to end", "235 unit (gate, rules, metrics, ICAR rows, GeoJSON) + 35 e2e", "all pass; CI green"],
  ["System cycle 0 (16 Oct)", "16 app cases on a fresh Windows install", "7 pass, 9 fail → 8 issues, all fixed"],
  ["Verification (23 Oct)", "fresh clone, data rebuild, held-out reproduction, edge cases", "reproduces exactly; 13 findings"],
  ["Manual cycle (30 Oct)", "MT-01…MT-10 on six labelled photos, real mode", "core cases pass; 16 findings"],
  ["System cycle 2 (7–8 Nov)", "final build, Windows 11, RTX 3050 4 GB, real mode", "24/24 pass; release v1.0.0"],
], { colW: [3.0, 5.5, CW - 8.5], fontSize: 14, rowH: 0.6 });
text(s, "Also verified: every ICAR herbicide row against the PDF; a dangerous rice dose (20 g, 75 days vs 15 g, 95 days) was found and fixed. Speed: 0.56–0.64 s per photo.", M, 5.6, CW, 0.9, { fontSize: 15 });
s.addNotes("Testing was led by Chaitanya; Amit ran both system cycles on his own laptop. F30: on a screenshot of a text page the detector saw a 'sugar beet plant' at 0.71, and the gate sprayed nothing: labels are not evidence.");

// ════════════════════════════════════════ 26 Conclusion
pres.addSection({ title: "Conclusion" });
s = slide("DARK", "Conclusion");
s.addText("CONCLUSION", { x: M, y: 0.5, w: CW, h: 0.4, fontSize: 14, bold: true, charSpacing: 2, color: "9FC7A5", margin: 0, isTextBox: true });
s.addText("Zero-shot labels cannot decide what to spray; a transparent safety layer recovers most of it", { x: M, y: 1.0, w: CW, h: 1.3, fontFace: "Cambria", fontSize: 28, bold: true, color: C.background1, margin: 0, isTextBox: true });
[["RQ1", "Grounded SAM: 65.5% crop sprayed for 1.8% weed recall held out; deployed gate sprays nothing."],
 ["RQ2", "Escalation agent: no crop approved, 13/14 crop verdicts right, 0/25 weeds found. Safe, not effective."],
 ["RQ3", "Plain rules + gate: 77.9% recall at 8.8% crop sprayed, 95% herbicide saved, 0.6 s/photo, no training."]]
  .forEach(([id, t], i) => {
    s.addText(id, { x: M, y: 2.7 + i * 1.05, w: 1.0, h: 0.8, fontSize: 22, bold: true, color: "F2A57A", margin: 0, isTextBox: true });
    s.addText(t, { x: M + 1.1, y: 2.7 + i * 1.05, w: CW - 1.1, h: 0.9, fontSize: 18, color: "DDE6DE", margin: 0, isTextBox: true });
  });
s.addText("A research prototype, not for real spraying. Every number is reproducible from the repository.", { x: M, y: 6.1, w: CW, h: 0.5, fontSize: 16, italic: true, color: "BFD0C2", margin: 0, isTextBox: true });
s.addNotes("Close with the three answers and the honesty point: we measured what zero-shot vision can and cannot do on this problem.");

// ════════════════════════════════════════ 27 Future scope
pres.addSection({ title: "Future scope" });
s = slide("CONTENT", "Future scope");
eyebrow(s, "Future scope");
s.addText("From measurement to a field-ready system", TT());
[["Like-for-like with WaW", "Weed IoU on PhenoBench " + cite("weyler2024phenobench") + " validation set"],
 ["Species-aware features", "BioCLIP " + cite("stevens2024bioclip") + " features instead of text labels, gate on top"],
 ["Safe mode for rule 4", "Size limit, tested on new held-out data"],
 ["Few-shot adaptation", "A handful of labelled photos " + cite("singh2025fewshot") + "; close the gap to supervised " + cite("dang2023yoloweeds")],
 ["Rows over time", "Image sequences " + cite("lottes2020stem") + " and auto-labelled inter-row weeds"],
 ["Real deployment", "GPS, nozzle latency, field trial with an agronomist; farmer-facing assistant in Indian languages"]]
  .forEach(([h, b], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    boxCard(s, M + col * 4.1, 1.95 + row * 2.3, 3.93, 2.1, h, b, row === 0 ? C.accent1 : C.accent3, 15);
  });
s.addNotes("The first item is the direct answer to 'can you compare with the base paper's closest work?': run on PhenoBench and report weed IoU. About one day of compute on our laptop.");

// ════════════════════════════════════════ 28–30 References
pres.addSection({ title: "References" });
const refSlides = 3;
const perSlide = Math.ceil(order.length / refSlides);
for (let r = 0; r < refSlides; r++) {
  s = slide(r % 2 ? "CONTENT_ALT" : "CONTENT", "References");
  eyebrow(s, `References (IEEE) · ${r + 1}/${refSlides}`);
  s.addText("References", TT());
  const chunk = order.slice(r * perSlide, (r + 1) * perSlide);
  const half = Math.ceil(chunk.length / 2);
  [chunk.slice(0, half), chunk.slice(half)].forEach((col, ci) => {
    s.addText(col.map((k, i) => ({
      text: `[${order.indexOf(k) + 1}] ${REFS[k]}`,
      options: { breakLine: i < col.length - 1, paraSpaceAfter: 4 },
    })), { x: M + ci * 6.15, y: 1.35, w: 5.95, h: 5.6, fontSize: 10, color: C.text2, valign: "top", margin: 0, isTextBox: true, objectName: "references" });
  });
  s.addNotes("Full IEEE references, numbered in order of first citation in this deck. The report (LaTeX) uses its own numbering in order of citation in the report.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (process.env.PPTX_SKILL_SCRIPTS) {
    const { applyTheme } = require(path.join(process.env.PPTX_SKILL_SCRIPTS, "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } else {
    console.warn("PPTX_SKILL_SCRIPTS not set: theme colours not applied");
  }
  const journals = order.filter((k) => /Transactions|Journal|Letters|Computers and Electronics|Engineering|Reports|Technology|Research|Sensing|Systems|Science|Agriculture|Intelligence|Processing/.test(REFS[k]) && !/Proc\.|Conference|arXiv|Kaggle|documentation|RFC/.test(REFS[k]));
  console.log(OUT, "| slides:", pres.slides.length, "| references:", order.length, "| journal-type:", journals.length);
})();
