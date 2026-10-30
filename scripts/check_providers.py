"""Check that each model provider in .env answers a real request.

Usage:
    python scripts/check_providers.py              # what we use: cloudflare-qwen, cloudflare (Clef Flash)
    python scripts/check_providers.py groq         # one provider: cloudflare-qwen, cloudflare, groq, local, clef-local

Since 30 Oct 2026 the reasoning model (Qwen) runs on Cloudflare; Groq is kept but switched off
(REASONING_PROVIDER=groq brings it back), so it is checked only when named.

The local llama-server back-ends are not part of our plan (team decision, 17 Oct), so they
are checked only when named explicitly.

Keys are read from .env (see .env.example) and are never printed.
"""

import argparse
import os
import sys
import time
from typing import Callable, Dict, Tuple

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

TIMEOUT = 60
TRIAGE_QUESTION = {
    "is_weed": {
        "type": "noul",
        "instructions": "Is the plant described in the state a weed in a cotton field?",
    }
}


def check_groq() -> Tuple[bool, str]:
    key = os.getenv("GROQ_API_KEY", "")
    if not key or key.startswith("gsk_your"):
        return False, "GROQ_API_KEY is not set in .env (create one at console.groq.com/keys)."
    model = os.getenv("GROQ_MODEL_NAME", "qwen/qwen3.8-27b")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with the single word OK."}],
            "max_tokens": 20,
            "reasoning_effort": "none",
        },
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    text = resp.json()["choices"][0]["message"]["content"].strip()
    left = resp.headers.get("x-ratelimit-remaining-requests", "?")
    return True, f"{model} replied {text!r}; requests left today: {left}"


def check_cloudflare_qwen() -> Tuple[bool, str]:
    """The reasoning model through the provider the app uses (HostedCloudflareProvider)."""
    from src.agronomy.provider_contract import LLMRequest
    from src.agronomy.providers import HostedCloudflareProvider

    provider = HostedCloudflareProvider()
    resp = provider.generate(LLMRequest(user_prompt="Reply with the single word OK.", timeout_seconds=TIMEOUT))
    if resp.error:
        return False, resp.error[:300]
    return True, f"{provider.model_name} replied {resp.text_content.strip()!r}"


def check_cloudflare() -> Tuple[bool, str]:
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    if not account or not token or account.startswith("your_"):
        return False, "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN are not set in .env."
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/clef-flash"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model": "clef-flash",
            "state": "A small grass plant growing between two cotton rows.",
            "questions": TRIAGE_QUESTION,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    result = resp.json().get("result", resp.json())
    return True, f"clef-flash answers: {result.get('answers')}"


def check_local() -> Tuple[bool, str]:
    base = os.getenv("LOCAL_BASE_URL", "http://127.0.0.1:8888/v1").rstrip("/")
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            json={
                "model": os.getenv("LOCAL_MODEL_NAME", "Qwen/Qwen3.5-4B"),
                "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                "max_tokens": 20,
            },
            timeout=TIMEOUT,
        )
    except requests.ConnectionError:
        return (
            False,
            f"Nothing is listening at {base}. Start llama-server first (see the schedule, Appendix A).",
        )
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return True, f"local server at {base} replied {text!r}"


def check_clef_local() -> Tuple[bool, str]:
    base = os.getenv("CLEF_LOCAL_URL", "http://127.0.0.1:8090").rstrip("/")
    try:
        resp = requests.post(
            f"{base}/v1/systemone",
            json={
                "state": "A small grass plant growing between two cotton rows.",
                "questions": TRIAGE_QUESTION,
            },
            timeout=TIMEOUT,
        )
    except requests.ConnectionError:
        return False, f"Nothing is listening at {base}. Start llama-server with Clef Flash first."
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    return True, f"local clef answers: {resp.json().get('answers')}"


CHECKS: Dict[str, Callable[[], Tuple[bool, str]]] = {
    "cloudflare-qwen": check_cloudflare_qwen,
    "cloudflare": check_cloudflare,
    "groq": check_groq,
    "local": check_local,
    "clef-local": check_clef_local,
}
CLOUD_CHECKS = ["cloudflare-qwen", "cloudflare"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("provider", nargs="?", choices=[*CHECKS, "all"], default="all")
    args = parser.parse_args()

    names = CLOUD_CHECKS if args.provider == "all" else [args.provider]
    if args.provider == "all":
        print("[SKIP] groq, local, clef-local: switched off; name one explicitly to check it")
    failures = 0
    for name in names:
        start = time.time()
        try:
            ok, message = CHECKS[name]()
        except requests.RequestException as exc:
            ok, message = False, f"request failed: {exc}"
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name:<11} {time.time() - start:5.1f}s  {message}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
