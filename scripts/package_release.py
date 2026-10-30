"""Build the source package for submission from one git commit or tag, and check it for secrets.

Usage:
    python scripts/package_release.py                  # package HEAD
    python scripts/package_release.py --ref v1.0.0     # package the frozen tag (the submission)

Writes dist/AgriAgent-<version>-<ref>-source.zip and a .sha256 file next to it. Only files
tracked by git at that ref go in (git archive), so .env, datasets, model weights and outputs are
never included. The zip is then scanned: it must not contain an .env file, a known key pattern,
or any value from your local .env. Values are compared, never printed. Exit code 1 means the
zip must not be shared.
"""

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_PATTERNS = [
    re.compile(rb"gsk_[A-Za-z0-9]{20,}"),  # Groq
    re.compile(rb"hf_[A-Za-z0-9]{30,}"),  # Hugging Face
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),  # OpenAI-style
    re.compile(rb"AKIA[0-9A-Z]{16}"),  # AWS
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
EXPECTED = ["README.md", "requirements-lock.txt", "app/app.py", "src/workflow.py", ".env.example"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def read_env(path: Path) -> dict:
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip().strip("'\"")
    return pairs


def local_env_values(env: Path) -> list:
    """Values of secret keys (KEY, TOKEN, SECRET, PASSWORD, ACCOUNT) in the local .env, 8+
    characters, skipping any still equal to the .env.example placeholder."""
    placeholders = read_env(ROOT / ".env.example")
    secret_name = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|ACCOUNT")
    return [
        value.encode()
        for key, value in read_env(env).items()
        if secret_name.search(key) and len(value) >= 8 and value != placeholders.get(key)
    ]


def scan(zip_path: Path, env: Path) -> list:
    """Problems found in the zip, described without showing any secret."""
    problems = []
    secrets = local_env_values(env)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for name in names:
            base = name.rsplit("/", 1)[-1]
            if base == ".env" or (base.endswith(".env") and base != ".env.example"):
                problems.append(f"{name}: an .env file is in the package")
            if name.endswith("/"):
                continue
            data = zf.read(name)
            for pattern in KEY_PATTERNS:
                if pattern.search(data):
                    problems.append(f"{name}: matches the key pattern {pattern.pattern[:12]!r}...")
            if any(value in data for value in secrets):
                problems.append(f"{name}: contains a value from your local .env")
        stripped = {n.split("/", 1)[1] for n in names if "/" in n}
        for path in EXPECTED:
            if path not in stripped:
                problems.append(f"{path}: expected file missing")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD", help="commit or tag to package (default HEAD)")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output folder (default dist/)")
    parser.add_argument("--env", default=str(ROOT / ".env"), help="local .env whose values must not leak")
    args = parser.parse_args()

    commit = git("rev-parse", "--short", args.ref)
    version = re.search(r'^version = "([^"]+)"', git("show", f"{args.ref}:pyproject.toml"), re.M)
    name = f"AgriAgent-{version.group(1) if version else 'unknown'}-{args.ref if args.ref != 'HEAD' else commit}"
    if git("status", "--porcelain"):
        print("Note: the working tree has uncommitted changes; they are NOT in the package.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{name}-source.zip"
    git("archive", "--format=zip", f"--prefix={name}/", "-o", str(zip_path), args.ref)

    problems = scan(zip_path, Path(args.env))
    with zipfile.ZipFile(zip_path) as zf:
        files = [i for i in zf.infolist() if not i.filename.endswith("/")]
    pdfs = sum(1 for i in files if i.filename.endswith(".pdf"))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    Path(f"{zip_path}.sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")

    print(f"Package  {zip_path}")
    print(f"Commit   {commit} ({args.ref})")
    print(f"Contents {len(files)} files, {pdfs} PDFs, {zip_path.stat().st_size / 1e6:.1f} MB")
    print(f"SHA-256  {digest}")
    if problems:
        print("\nFAIL: do not share this package.")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPASS: no .env file, no key patterns, no local .env values; expected files present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
