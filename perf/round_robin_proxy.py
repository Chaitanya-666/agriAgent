"""Round-robin load balancer for the Field Service (Software Testing Lab 6).

Same idea as the Node `http-proxy` balancer in the lab manual's Experiment 8: every request
goes to the next backend in the list, then the list wraps around. Requests and responses are
forwarded unchanged; the response gets an `X-Backend` header naming the server that answered.

    BACKENDS=http://127.0.0.1:8001,http://127.0.0.1:8002 \
        .venv/bin/python -m uvicorn perf.round_robin_proxy:app --port 8000
"""

from __future__ import annotations

import itertools
import logging
import os
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

BACKENDS = [
    b.strip().rstrip("/")
    for b in os.environ.get("BACKENDS", "http://127.0.0.1:8001").split(",")
    if b.strip()
]
_rotation = itertools.cycle(BACKENDS)
logger = logging.getLogger("agriagent.proxy")

# Headers that describe one connection, not the message; a proxy must not pass them on.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
    "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}

# keepalive_expiry must be SHORTER than the backend's keep-alive timeout (uvicorn: 5 s). With
# both at 5 s (httpx's default) the proxy sometimes reused a connection at the moment uvicorn
# closed it, and the request failed with ReadError -> 502 (Lab 6: 4 in ~60,000 requests).
client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_connections=500, max_keepalive_connections=200, keepalive_expiry=2.0),
)


async def forward(request: Request) -> Response:
    backend = next(_rotation)
    url = backend + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    try:
        upstream = await client.request(
            request.method, url, content=await request.body(), headers=headers
        )
    except httpx.HTTPError as exc:
        logger.warning("502 %s %s via %s: %r", request.method, request.url.path, backend, exc)
        return Response(f"bad gateway ({backend}): {exc!r}", status_code=502,
                        headers={"X-Backend": backend})
    out = {k: v for k, v in upstream.headers.items()
           if k.lower() not in HOP_BY_HOP and k.lower() != "content-encoding"}
    out["X-Backend"] = backend
    return Response(upstream.content, status_code=upstream.status_code, headers=out)


@asynccontextmanager
async def lifespan(_app: Starlette):
    yield
    await client.aclose()


app = Starlette(
    routes=[Route("/{path:path}", forward, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])],
    lifespan=lifespan,
)
