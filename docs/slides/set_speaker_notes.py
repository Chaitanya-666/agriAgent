"""Write the presenter pointers in fyp_assets/speaker_notes.json into the deck's speaker notes.

Run after build_fyp_pptx.js:   uv run --with python-pptx python docs/slides/set_speaker_notes.py
The pointers are the same "say this" lines as docs/guides/07_Presentation_Kit.typ.
"""

import json
from pathlib import Path

from pptx import Presentation

HERE = Path(__file__).resolve().parent
DECK = HERE / "AgriAgent_FYP_Presentation.pptx"
NOTES = json.loads((HERE / "fyp_assets" / "speaker_notes.json").read_text(encoding="utf-8"))

pres = Presentation(DECK)
assert len(pres.slides) == len(NOTES), (len(pres.slides), len(NOTES))
for number, slide in enumerate(pres.slides, start=1):
    slide.notes_slide.notes_text_frame.text = NOTES[str(number)]
pres.save(DECK)
print(f"speaker notes written on {len(NOTES)} slides")
