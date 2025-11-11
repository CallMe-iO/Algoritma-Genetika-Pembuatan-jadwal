"""FastAPI application for Sistem Penjadwalan Kuliah berbasis Algoritma Genetika."""
from __future__ import annotations

import io
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from ga import optimize
from io_utils import export_view, generate_demo_courses, generate_template_workbook, load_courses_from_upload
from models import GAParameters
from scheduler import build_views, dataset_summary

app = FastAPI(title="Penjadwalan Kuliah GA")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _ensure_state() -> Dict[str, Any]:
    if not hasattr(app.state, "store"):
        app.state.store = {
            "courses": None,
            "summary": None,
            "result": None,
        }
    return app.state.store


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    params = GAParameters()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_params": params.dict(),
        },
    )


@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File tidak ditemukan")
    raw_bytes = await file.read()
    try:
        courses = load_courses_from_upload(file.filename, raw_bytes)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    store = _ensure_state()
    store["courses"] = courses
    summary = dataset_summary(courses)
    store["summary"] = summary.dict()
    store["result"] = None
    return {"status": "ok", "summary": summary.dict()}


@app.post("/demo")
async def load_demo():
    courses = generate_demo_courses()
    store = _ensure_state()
    store["courses"] = courses
    summary = dataset_summary(courses)
    store["summary"] = summary.dict()
    store["result"] = None
    return {"status": "ok", "summary": summary.dict(), "pesan": "Data demo berhasil dimuat"}


@app.post("/optimize")
async def optimize_schedule(payload: Dict[str, Any]):
    store = _ensure_state()
    if not store.get("courses"):
        raise HTTPException(status_code=400, detail="Unggah data terlebih dahulu.")
    try:
        params = GAParameters(**payload)
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=err.errors())
    result = optimize(store["courses"], params)
    entries = result["entries"]
    views = build_views(entries)
    store["result"] = {
        "views": views.dict(),
        "summary": result["summary"].dict(),
        "fitness": result["fitness"],
        "generasi": result["generasi"],
    }
    response = {
        "status": "ok",
        "fitness_best": result["fitness"],
        "generasi_tercapai": result["generasi"],
        "ringkasan": result["summary"].dict(),
        "jadwal": views.dict(),
    }
    return JSONResponse(response)


@app.get("/download")
async def download_file(format: str, view: str = "kelas"):
    store = _ensure_state()
    if not store.get("result"):
        raise HTTPException(status_code=400, detail="Belum ada jadwal untuk diunduh.")
    view_key = f"per_{view}"
    views = store["result"]["views"]
    if view_key not in views:
        raise HTTPException(status_code=400, detail="View tidak dikenal.")
    rows = views[view_key]
    try:
        content, media_type, filename = export_view(view, rows, format)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(content), headers=headers, media_type=media_type)


@app.get("/template")
async def download_template():
    content = generate_template_workbook()
    headers = {"Content-Disposition": 'attachment; filename="template_penjadwalan.xlsx"'}
    return StreamingResponse(
        io.BytesIO(content),
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
