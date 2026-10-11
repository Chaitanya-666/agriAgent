#set document(title: "AgriAgent Week 1 Sprint Record", author: "AgriAgent Team")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 10pt)
#set heading(numbering: "1.")

= AgriAgent Week 1 Sprint Record

This short record summarizes the prototype work areas that began the project. It is not a completion certificate or a record of independently verified field performance.

== Work areas

1. *Vision:* connect open-vocabulary region proposals to promptable vegetation masks.
2. *Agronomy:* connect diagnosis and herbicide guidance to a structured knowledge source.
3. *Evaluation:* preserve datasets, annotation manifests, and reproducible test inputs.
4. *Application and release:* expose the prototype through a review interface and add automated checks.

== Current migration decisions

Local triage is planned with `Cloudflare/clef-flash`; local agronomy/VLM use is planned with `Qwen/Qwen3.5-4B`; Groq `qwen/qwen3.8-27b` is the only cloud model. These choices do not imply that live model execution has been completed.

The safety contract requires a deterministic final spray gate. Exported GeoJSON must come from approved mask artifacts, not raw detector boxes. A model may recommend escalation but may not be the sole authority for physical actuation.

== Current status

Some software paths are covered by unit and synthetic E2E tests. Mock results are not live model results. Hardware runtime, real-world accuracy, agronomic review, GPS alignment, and field safety validation are unfinished. See `cleanup_execution_sprint.md` for the detailed implementation plan and acceptance criteria.
