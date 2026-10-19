# ICAR herbicide table check (K12, task SU-2), 20 Oct 2026

Every herbicide row and dose ceiling in the code was compared with the bulletin itself,
`data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf` (121 pages; printed page = PDF page - 8),
by reading the rendered table pages. Code: `CANONICAL_ICAR_TABLE_ROWS` in
`src/agronomy/knowledge_store.py`, `BANNED_HERBICIDES` and `STATUTORY_DOSAGE_CEILINGS_G_PER_HA`
in `src/agronomy/prescription.py`. Where the bulletin gives a range, the code stores the upper
value; "not stated" (the bulletin's "-") is now stored as empty, not 0.

## Crop rows

| Crop | Herbicide | Bulletin (printed page) | Code before | Verdict / fix |
|---|---|---|---|---|
| cotton | Alachlor 50% EC | 2-2.5 kg, 250-500 L, 210-240 d (p. 34) | 2500 g, 500 L, 240 d | correct |
| cotton | Alachlor 10% Gr | 2.0-2.5 kg, water -, waiting - (p. 34) | water 0, waiting 0 | **0 replaced by "not stated"** |
| cotton | Diuron 80% WP | 0.75-1.5 kg, 625 L, waiting - (p. 34) | waiting 0 | **0 replaced by "not stated"** |
| cotton | Fenoxaprop-P-ethyl 9.3% EC | 67.5 g, 375-500 L, 87 d (p. 34) | 67.5 g, 500 L, 87 d | correct |
| cotton | Fluchloralin 45% EC | 0.9-1.2 kg, 500-800 L, 180 d (p. 35) | 1200 g, 800 L, 180 d | correct |
| cotton | Glufosinate-ammonium 13.5% SL | 375-450 g, 500 L, 96 d (p. 35) | 450 g, 500 L, 96 d | correct |
| cotton | Pendimethalin 30% EC | 0.75-1.25 kg, 500-700 L, 150 d (p. 35) | 1250 g, 700 L, 150 d | correct |
| cotton | Pyrithiobac-sodium 10% EC | 62.5-75 g, 500 L, 160 d (p. 35) | 75 g, 500 L, 160 d | correct |
| cotton | Quizalofop-ethyl 5% EC | 50.5 g, 500 L, 94 d (p. 35) | 50.5 g, 500 L, 94 d | correct |
| wheat | Sulfosulfuron 75% WG | 25 g, 200-250 L, 110 d; *Phalaris minor, Chenopodium* sp., *Melilotus alba* (p. 27) | 300 L, p. 25, weeds *P. minor, C. album* | **water 250 L, page 27, weeds as bulletin** |
| wheat | Clodinafop-propargyl 15% WP | 60 g, 375-400 L, 110 d; *Phalaris minor* only (p. 25) | 375 L, plus *Avena ludoviciana* | **water 400 L; extra weed removed** |
| rice | Pyrazosulfuron-ethyl 10% WP | **10-15 g**, 500-600 L, **95 d**; *Cyperus iria, C. difformis, Fimbristylis miliacea, Monochoria vaginalis, Ludwigia parviflora* (p. 33) | **20 g, 75 d**, *Echinochloa* spp., *Cyperus* spp., p. 28 | **dose 15 g, 95 d, 600 L, weeds and page as bulletin** |
| beet root | Pendimethalin 30% EC | 1.0 kg, 400-600 L, waiting -; *Digitaria sanguinalis, Echinochloa crus-galli, Chenopodium* sp., *Argemone mexicana, Amaranthus spinosus, Portulaca* sp. (p. 47) | 500 L, **60 d**, other weed names | **600 L, waiting "not stated", weeds as bulletin** |

The rice row was the dangerous one: an overdose (20 g against a 15 g maximum) together with a
waiting period 20 days shorter than approved.

## Banned, withdrawn and refused herbicides (Table 3.3, p. 18)

Banned: nitrofen, paraquat dimethyl sulphate, metoxuron. Withdrawn: dalapon, simazine. Refused:
2,4,5-T, ammonium sulphamate, calcium arsenate, TCA. **All nine match `BANNED_HERBICIDES`.** Not
listed in the code: the restriction "dazomet is not permitted on tea" (not one of our crops).

## Dose ceilings

| Crop | Herbicide | Bulletin maximum | Code before | Fix |
|---|---|---|---|---|
| cotton | all ten entries | as in the crop rows | same | correct |
| wheat | 2,4-D dimethyl amine salt | 0.50-0.75 kg (p. 25) | 500 g | **750 g** |
| wheat | pendimethalin | 1.0 / 1.25 / 1.5 kg by soil (p. 27) | 1000 g | **1500 g** (heavy soil) |
| wheat | isoproturon | 1.0 kg (p. 26) | 1000 g | correct |
| rice | pyrazosulfuron-ethyl | 10-15 g (p. 33) | 20 g | **15 g** |
| rice | bispyribac-sodium | 20 g (p. 29) | 25 g | **20 g** |
| rice | butachlor | 1.25-2.0 kg (p. 29) | 1500 g | **2000 g** |
| rice | pretilachlor | 0.50-0.75 kg (p. 33) | 750 g | correct |
| beet root | pendimethalin | 1.0 kg (p. 47) | 1000 g | correct |

Regression tests: `TestIcarTableMatchesBulletin` in `tests/test_prescription_safety.py` (all four
fail on the old values).
