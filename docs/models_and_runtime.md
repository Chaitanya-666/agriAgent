# Models and runtime setup

AgriAgent has three model roles. The first two are intended to run locally. Groq is the only cloud model provider.

| Role | Model | Runtime | Current evidence |
|---|---|---|---|
| Ambiguity triage | `Cloudflare/clef-flash` | Local custom typed-decision model and Transformers backbone, cache only at inference | Adapter implemented; model weights and live inference were not available in this environment. |
| Agronomy/VLM | `Qwen/Qwen3.5-4B` | Local OpenAI-compatible inference server | Provider adapter and mock tests exist; a live server/model response was not verified. |
| Cloud agronomy | `qwen/qwen3.8-27b` | Groq API | Provider configuration and mock tests exist; live API use was not verified. |

Clef Flash is not called through Cloudflare Workers AI. No Cloudflare account, token, or online endpoint is used. Its model card describes a typed decision model with a custom schema head. The local adapter uses that schema to classify ambiguity and recommend escalation; it does not treat Clef as a free-form JSON generator. It cannot approve spraying. `DeterministicRouter` remains responsible for the final spray safety decision. See the [official model card](https://huggingface.co/Cloudflare/clef-flash).

## Install and start

Install the regular project dependencies first:

```bash
python -m pip install -e '.[dev,clef]'
```

Download Clef weights to the local Hugging Face cache. The router sets `local_files_only=True` at runtime, so it will not fetch weights while starting inference:

```bash
hf download Cloudflare/clef-flash
```

Run the app or router after the weights and required hardware runtime are ready. `CLEF_FLASH_MODEL` may name the Hugging Face id or a local model directory:

```bash
export CLEF_FLASH_MODEL=Cloudflare/clef-flash
streamlit run app/app.py
```

The `clef` extra installs the published model-card-tested versions (`torch>=2.11`, `transformers>=5.10.2`) and the custom model's required support libraries. At inference the router looks only in the local Hugging Face cache. `CLEF_FLASH_REVISION` can pin a cached revision.

For Qwen, start an OpenAI-compatible local server using a release of the server that supports `Qwen/Qwen3.5-4B`. A typical vLLM command is:

```bash
vllm serve Qwen/Qwen3.5-4B --host 127.0.0.1 --port 8888
```

The provider defaults to `http://127.0.0.1:8888/v1`. Configure `LOCAL_BASE_URL`, `LOCAL_API_KEY`, and `LOCAL_MODEL_NAME` if your server differs. Compatibility of a particular inference-server release with this model is not verified by this repository.

## Environment variables

Copy `.env.example` to `.env` and set only values needed for the selected path:

- `CLEF_FLASH_MODEL`: local Clef Hugging Face id or model directory.
- `LOCAL_BASE_URL`, `LOCAL_API_KEY`, `LOCAL_MODEL_NAME`: local Qwen service settings.
- `GROQ_API_KEY`, `GROQ_MODEL_NAME`: Groq credentials and model. The model default is `qwen/qwen3.8-27b`.
- `HF_TOKEN`: optional access token for gated Grounding DINO or SAM 2 weights.

Mock behavior is enabled only when code explicitly sets `mock_mode=True`. Missing local Clef dependencies or weights produce a clear runtime error; workflow triage then escalates to System 2. Missing Qwen service and Groq credentials return provider errors. They do not silently claim a live result.

## Hardware and offline behavior

This environment's `nvidia-smi` could not communicate with an NVIDIA driver, so GPU availability and live inference could not be checked. Approximate weight-only planning: 9B BF16 weights require about 18 GB, before the vision path, activations, and runtime overhead; a 4B BF16 model needs about 8 GB before overhead. Quantized weights use less storage and memory, but runtime support and quality must be checked for the selected quantization. The Clef model card reports testing on a single H200 with `torch` 2.11 and `transformers` 5.10.2. Treat that as the only model-card hardware evidence; this project has no verified generic VRAM minimum or runtime benchmark. A downloaded Clef snapshot is about 19 GB on disk.

After weights and packages are already installed, local inference can run without network access. The Groq provider requires internet and `GROQ_API_KEY`. Grounding DINO and SAM 2 also need their weights locally or a one-time download. Without model weights, the live path is unavailable; use explicitly selected mock mode for tests only.

## Verified and unverified

Verified by repository inspection: the Clef adapter uses a local cache-only load path and the model card's custom typed-decision interface; the Qwen provider uses a configurable local endpoint; Groq is configured for the requested model; mock provider tests are present. Not verified: Clef/Qwen live outputs, model compatibility on other hardware or in the selected Qwen serving stack, GPU execution, peak memory, latency, quality, field reliability, and physical actuator behavior.
