#set document(title: "AgriAgent Week 1 Prototype Summary", author: "AgriAgent Team")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 10pt)
#set heading(numbering: "1.")

= AgriAgent Week 1 Prototype Summary

This source preserves the Week 1 integration summary in a shorter, evidence-conscious form. It describes project intent and prototype structure, not a completed field deployment.

== Goal

Study an image-based pipeline that can identify candidate weeds, segment vegetation, and prepare a selective spray map for human review.

== Components

- Grounding DINO proposes regions from field images.
- SAM 2 generates masks from those proposals.
- Refinement can request a new mask when the current quality estimate is low.
- Agronomy reasoning uses a provider interface and a statutory knowledge store.
- A deterministic gate controls whether spray zones may be prepared.
- The Streamlit application visualizes results and provides a research GeoJSON export.

== Safety and evidence

Model proposals and masks are uncertain. Raw boxes do not authorize spray features. The deterministic gate must remain the final authority, and unsafe or uncertain results must be suppressed or sent for review. Mock mode is useful for software tests but does not verify live models or field performance.

The current model plan uses local `Cloudflare/clef-flash`, local `Qwen/Qwen3.5-4B`, and cloud-only Groq `qwen/qwen3.8-27b`. Exact setup and unverified requirements are documented in `models_and_runtime.md`.

== Work still needed

Live model compatibility, ground-truth evaluation, independent agronomy review, reliable location alignment, real hardware interlocks, and field trials remain future work. This prototype must not be described as field-ready.
