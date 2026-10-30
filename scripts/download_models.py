"""Download the model weights real mode needs, or check they are already on this machine.

Usage:
    python scripts/download_models.py           # download what is missing (about 1.7 GB the first time)
    python scripts/download_models.py --check   # offline check: can every model load without a network?

Run --check before a demo away from home: real mode then starts without downloading anything.
Weights go to the Hugging Face cache (~/.cache/huggingface/hub, or $HF_HOME). The cloud
providers (Groq, Cloudflare) still need a network; without one the app says so and continues.
"""

import argparse
import sys

MODELS = [
    ("IDEA-Research/grounding-dino-tiny", "detection (src/vision/grounding_dino.py)"),
    ("facebook/sam2-hiera-tiny", "segmentation (src/vision/sam2_wrapper.py)"),
    ("BAAI/bge-small-en-v1.5", "ICAR table search (src/agronomy/knowledge_store.py)"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only check the local cache; never download")
    args = parser.parse_args()

    from huggingface_hub import snapshot_download

    missing = 0
    for repo_id, use in MODELS:
        try:
            path = snapshot_download(repo_id, local_files_only=args.check)
            print(f"OK       {repo_id:36s} {use}\n         {path}")
        except Exception as err:  # offline and not cached, or a network error while downloading
            missing += 1
            print(f"MISSING  {repo_id:36s} {use}\n         {type(err).__name__}: {err}")
    if missing:
        hint = "run without --check while online" if args.check else "check the network and retry"
        print(f"\n{missing} model(s) not available; {hint}.")
        return 1
    print("\nAll models are on this machine; real mode can start offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
