#set document(title: "AgriAgent Research Project Proposal", author: "AgriAgent Team")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 10pt)
#set heading(numbering: "1.")

= AgriAgent: Research Project Proposal

== Problem and goal

We propose a research prototype for selective weed-management support. The system will process field images, find candidate vegetation, create masks, and prepare a spray-map artifact for human review. The research will evaluate whether this approach can support more targeted decisions than a uniform image-space mask.

The proposal is not a deployment claim. Model performance, agronomic suitability, geographic alignment, and physical spray safety require separate evidence.

== Proposed system

1. Grounding DINO proposes image regions using a generic weed-oriented prompt.
2. SAM 2 predicts instance masks for candidate regions.
3. A mask refinement step can request another segmentation when quality is inadequate.
4. A deterministic gate checks label policy, mask state, and infestation limits.
5. Agronomy guidance uses a local model and a maintained knowledge source; cloud assistance is limited to Groq.
6. The review interface visualizes results and can export zones derived from approved mask artifacts.

Local model plan: `Cloudflare/clef-flash` for ambiguity triage and `Qwen/Qwen3.5-4B` for agronomy/VLM reasoning. The only cloud model is Groq `qwen/qwen3.8-27b`. Model weights are downloaded separately and are never committed.

== Safety and human review

Raw detector boxes are proposals and must not become spray features directly. A model may identify uncertainty and request review but cannot authorize a physical spray action. The deterministic safety gate must be the final software authority. Suppressed results must contain no exportable zones.

Current map coordinates are placeholders. Any equipment integration requires surveyed positioning, calibration, independent interlocks, controlled trials, and qualified review.

== Evaluation plan

Use versioned image/annotation manifests and report detection and segmentation metrics against reviewed ground truth. Record model revision, inference software, device, precision, prompt, mock/live mode, and output artifact. Keep model confidence distinct from ground-truth overlap. Label synthetic or mocked tests as software contract checks, not field performance.

== Expected outcome and limits

The immediate outcome is a reproducible software prototype and evaluation workflow. The project does not promise a particular savings percentage, response time, accuracy, or field-readiness level. Those outcomes can be stated only after measured, reproducible experiments and safety review.

== Historical note

SmartDesk was the historical starting point for the original scaffold. It is not part of the current AgriAgent runtime.
