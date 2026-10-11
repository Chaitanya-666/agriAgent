#set document(title: "AgriAgent Week 1 Technical Dossier", author: "AgriAgent Team")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 10pt)
#set heading(numbering: "1.")

= AgriAgent Week 1 Technical Dossier

*Purpose:* concise record of the original prototype foundation. This is a historical project document, not a claim that all components were live-verified.

== Project

AgriAgent explores how open-vocabulary object detection and promptable segmentation can support selective weed-management research. The software accepts an image, creates candidate regions and masks, applies a deterministic safety policy, and prepares a spray-map artifact for review.

== Prototype flow

#align(center)[
  #block(fill: rgb("#eef6ee"), inset: 12pt, width: 100%)[
    Field image -> Grounding DINO proposals -> SAM 2 masks -> mask refinement -> deterministic spray gate -> review artifact
  ]
]

Grounding DINO output is a proposal, not an actuation command. The downstream application must use only mask zones approved by the workflow. The current output coordinates are placeholders and are not validated against a physical field.

== Safety boundary

The deterministic gate is the final authority for spray decisions. A generative model can help describe ambiguity or recommend escalation, but it cannot approve a physical spray action. High infestation, poor mask quality, crop-like labels, and uncertain classification require suppression, refinement, or human review according to the configured rules.

== Model/runtime status

The target model configuration is local `Cloudflare/clef-flash` for triage, local `Qwen/Qwen3.5-4B` for agronomy/VLM work, and Groq `qwen/qwen3.8-27b` as the only cloud model. Unit tests can use mock responses. A passing mock test is not live model evidence. GPU and model execution were not verified as part of this document.

== Limitations

The repository is a research prototype. It does not establish field accuracy, robust weed/crop separation, safe nozzle timing, surveyed GPS alignment, regulatory approval, or readiness for autonomous spraying. See `models_and_runtime.md` and `AgriAgent_Week2_Master_Technical_Dossier.typ` for the current runtime and evidence record.
