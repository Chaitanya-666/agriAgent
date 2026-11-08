\# AgriAgent v1.0.0 Release Notes



\## What's New

\- Final release of the AgriAgent multi-agent precision agriculture prototype.

\- Integrated dual-brain architecture (System 1 Grounding DINO + SAM 2, System 2 ICAR/CIBRC RAG).

\- Fully functional local offline vision mode and cloud-based reasoning.



\## Test Cycle 2 Fixes

\- \*\*F24\*\*: Resolved stale MOCK output overlapping with REAL output during mode switches.

\- \*\*F26\*\*: Fixed "meta tensor" error and implemented model caching for faster subsequent runs.

\- \*\*F27\*\*: Added explicit wrong-crop warnings to the farmer summary (English, Hindi, Marathi).

\- \*\*F29\*\*: Ensured herbicide advice includes the statutory safety caveat and label disclaimer.

\- \*\*F28\*\*: Added the new "Show every plant" overlay to visualize sprayed vs. protected crops.



\## Known Limitations

\- Rule 4 can misclassify off-row beets as weeds if the detector misses the crop box (F1).

\- Cotton weed recall is approximately 10%; large weeds may be protected as crop.

\- Tiny sprouts inside beet boxes may cause minor over-spraying (approx. 0.05% of photo).

\- GeoJSON coordinates are placeholders near VJTI, not actual GPS coordinates.





\*Verified on Windows 11, Python 3.13.9, NVIDIA RTX 3050 (4GB) during Test Cycle 2.\*



