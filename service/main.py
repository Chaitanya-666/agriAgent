"""FastAPI app for the AgriAgent Field Service.

Routes (all JSON unless noted):
  GET    /api/health                      service, database and mode status
  POST   /api/analyze                     multipart: image (PNG/JPEG), crop, mode, min_confidence
  GET    /api/sample-image                PNG of the synthetic demo field
  GET    /api/runs?limit&offset&crop      history, newest first
  GET    /api/runs/{id}                   one run
  GET    /api/runs/{id}/overlay.jpg       result image (JPEG)
  GET    /api/runs/{id}/spray-map.geojson spray zones for the sprayer (GeoJSON)
  DELETE /api/runs/{id}                   remove a run (204)
  GET    /api/stats                       totals and per-crop / per-action breakdowns
  GET    /                                the web page (web/)

Every error has the same shape: {"error": {"code", "message", "field"}}.
"""

from __future__ import annotations

import io
import logging
from typing import Annotated, Any, Dict, Optional

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.components.pipeline import create_sample_field_image
from service import __version__, config
from service.analysis import AnalysisFailed, run_analysis
from service.config import Settings, load_settings
from service.store import RunStore
from service.validation import ValidationError, decode_image, parse_crop, parse_page, parse_params

logger = logging.getLogger("agriagent.service")


def _error(status: int, code: str, message: str, field: Optional[str] = None) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message, "field": field}}
    )


def _run_links(run: Dict[str, Any]) -> Dict[str, Any]:
    run_id = run["id"]
    run["links"] = {
        "self": f"/api/runs/{run_id}",
        "overlay": f"/api/runs/{run_id}/overlay.jpg",
        "geojson": f"/api/runs/{run_id}/spray-map.geojson",
    }
    return run


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or load_settings()
    store = RunStore(settings.db_path)
    store.init()

    app = FastAPI(title="AgriAgent Field Service", version=__version__)
    app.state.settings = settings
    app.state.store = store

    @app.exception_handler(ValidationError)
    async def _on_validation(_: Request, exc: ValidationError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.field)

    @app.exception_handler(RequestValidationError)
    async def _on_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
        field = loc[-1] if loc else None
        return _error(422, "invalid_request", first.get("msg", "invalid request"), field)

    @app.exception_handler(StarletteHTTPException)
    async def _on_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        db_ok = store.ping()
        return {
            "status": "ok" if db_ok else "degraded",
            "version": __version__,
            "database": "up" if db_ok else "down",
            "modes": {"mock": True, "real": settings.allow_real_mode},
            "crops": list(config.CROPS),
            "limits": {
                "min_confidence": [config.MIN_CONFIDENCE_FLOOR, config.MIN_CONFIDENCE_CEILING],
                "max_upload_bytes": config.MAX_UPLOAD_BYTES,
                "min_image_side": config.MIN_IMAGE_SIDE,
                "max_image_pixels": config.MAX_IMAGE_PIXELS,
            },
        }

    @app.post("/api/analyze", status_code=201)
    def analyze(
        image: Annotated[Optional[UploadFile], File()] = None,
        crop: Annotated[Optional[str], Form()] = "cotton",
        mode: Annotated[Optional[str], Form()] = "mock",
        min_confidence: Annotated[Optional[str], Form()] = None,
    ) -> Dict[str, Any]:
        # A plain `def` (not async): FastAPI runs it in a worker thread, so one slow
        # analysis does not block the event loop for other requests.
        params = parse_params(crop, mode, min_confidence, settings.allow_real_mode)
        if image is None:
            raise ValidationError(422, "missing_image", "attach an image file", "image")
        raw = image.file.read(config.MAX_UPLOAD_BYTES + 1)
        picture = decode_image(raw)
        try:
            result = run_analysis(picture, raw, image.filename or "upload", params)
        except AnalysisFailed as exc:
            logger.exception("analysis failed")
            return _error(500, "analysis_failed", f"the pipeline failed: {exc}")
        run_id = store.add(result.record)
        return _run_links(store.get(run_id))

    @app.get("/api/sample-image")
    def sample_image() -> Response:
        buf = io.BytesIO()
        create_sample_field_image().save(buf, format="PNG")
        return Response(
            buf.getvalue(),
            media_type="image/png",
            headers={"Content-Disposition": 'inline; filename="sample-field.png"'},
        )

    @app.get("/api/runs")
    def list_runs(
        limit: Annotated[Optional[int], Query()] = None,
        offset: Annotated[Optional[int], Query()] = None,
        crop: Annotated[Optional[str], Query()] = None,
    ) -> Dict[str, Any]:
        limit, offset = parse_page(limit, offset)
        crop_filter = parse_crop(crop) if crop else None
        items = [_run_links(r) for r in store.list(limit, offset, crop_filter)]
        return {
            "items": items,
            "total": store.count(crop_filter),
            "limit": limit,
            "offset": offset,
        }

    def _get_or_404(run_id: int) -> Dict[str, Any]:
        run = store.get(run_id)
        if run is None:
            raise StarletteHTTPException(404, f"run {run_id} not found")
        return run

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: int) -> Dict[str, Any]:
        return _run_links(_get_or_404(run_id))

    @app.get("/api/runs/{run_id}/overlay.jpg")
    def get_overlay(run_id: int) -> Response:
        data = store.overlay(run_id)
        if data is None:
            raise StarletteHTTPException(404, f"run {run_id} not found")
        return Response(data, media_type="image/jpeg")

    @app.get("/api/runs/{run_id}/spray-map.geojson")
    def get_geojson(run_id: int) -> Response:
        text = store.geojson(run_id)
        if text is None:
            raise StarletteHTTPException(404, f"run {run_id} not found")
        return Response(
            text,
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="spray-map-run-{run_id}.geojson"'},
        )

    @app.delete("/api/runs/{run_id}", status_code=204)
    def delete_run(run_id: int) -> Response:
        if not store.delete(run_id):
            raise StarletteHTTPException(404, f"run {run_id} not found")
        return Response(status_code=204)

    @app.get("/api/stats")
    def stats() -> Dict[str, Any]:
        return store.stats()

    if config.WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")

    return app
