# Qwen on Groq vs Qwen on Cloudflare: crop or weed? (30 October 2026, finding F25)

Same 20 labelled patches as task T2.2 (`scripts/compare_crop_or_weed.py`, official labels from
`eval_manifest_v2.json`), same prompt, same model name (Qwen 3.8 27B), two providers.

| Qwen served by | Correct | Beets called crop | Weeds called weed | File |
|---|---|---|---|---|
| Groq (`qwen/qwen3.8-27b`, October run) | 16 / 20 (0.80) | 9 / 10 | 7 / 10 | `t2_2_crop_or_weed_groq_20261017.json` |
| Cloudflare (`@cf/qwen/qwen3.8-27b`, 30 Oct) | 12 / 20 (0.60) | 5 / 10 | 7 / 10 | `t2_2_crop_or_weed_cloudflare_20261030.json` |

Clef Flash (14 / 20) and the row rule (13 / 20) gave the same scores in both runs. In the column
named `groq` of the Cloudflare file, the answers come from Cloudflare (the evidence source now
uses the configured provider).

**What it means.** The same model name behaves differently depending on who serves it (serving
stack or quantisation, or how thinking is switched off; not yet known). The escalation agent's
trust weight for Qwen (0.80) was measured on Groq. In manual test MT-02 the Cloudflare Qwen
called three beets weeds at 0.85 confidence, but the row rule and Clef Flash disagreed, so the
combined P(weed) stayed between 0.55 and 0.72, below the 0.85 needed: nothing was sprayed. Open
decision: weight Qwen by the measured accuracy of the serving provider (0.60 on Cloudflare), or
let the agent alone use Groq.
