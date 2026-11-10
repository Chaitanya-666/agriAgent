"""`python -m service [--host H] [--port P]` starts the Field Service with uvicorn."""

import argparse

import uvicorn

from service.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="AgriAgent Field Service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
