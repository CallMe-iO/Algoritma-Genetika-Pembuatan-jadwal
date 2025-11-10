"""FastAPI application exposing the GA timetabling engine."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from ag_timetabling_engine import DAYS, solve_timetable


def create_app() -> FastAPI:
    description = (
        "Genetic Algorithm microservice for course timetabling. Upload a dataset and "
        "tune GA parameters to generate conflict-free schedules."
    )
    return FastAPI(title="GA Course Timetabling", version="1.0.0", description=description)


app = create_app()


INDEX_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <title>GA Course Timetabling</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; }
    form { display: grid; gap: 1rem; max-width: 520px; }
    label { font-weight: 600; }
    input[type='number'] { width: 120px; }
    .buttons { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    button { padding: 0.6rem 1.2rem; border: none; background: #2563eb; color: #fff; border-radius: 4px; cursor: pointer; }
    button.secondary { background: #16a34a; }
    button.tertiary { background: #7c3aed; }
    pre { background: #0f172a; color: #e2e8f0; padding: 1rem; border-radius: 6px; min-height: 200px; overflow: auto; }
  </style>
</head>
<body>
  <h1>Genetic Algorithm Timetabling</h1>
  <p>Upload a CSV/XLSX file with the required columns, adjust GA parameters, then run the optimizer.</p>
  <form id=\"ga-form\">
    <div>
      <label for=\"file\">Dataset (CSV/XLSX)</label><br />
      <input id=\"file\" name=\"file\" type=\"file\" accept=\".csv,.xlsx,.xls\" required />
    </div>
    <div>
      <label>Population Size</label><br />
      <input name=\"pop_size\" type=\"number\" min=\"10\" value=\"60\" />
    </div>
    <div>
      <label>Generations</label><br />
      <input name=\"gens\" type=\"number\" min=\"10\" value=\"200\" />
    </div>
    <div>
      <label>Crossover Rate</label><br />
      <input name=\"cx_rate\" type=\"number\" min=\"0\" max=\"1\" step=\"0.05\" value=\"0.8\" />
    </div>
    <div>
      <label>Mutation Rate</label><br />
      <input name=\"mut_rate\" type=\"number\" min=\"0\" max=\"1\" step=\"0.05\" value=\"0.2\" />
    </div>
    <div>
      <label>Seed</label><br />
      <input name=\"seed\" type=\"number\" value=\"42\" />
    </div>
    <div class=\"buttons\">
      <button type=\"button\" data-endpoint=\"json\">Run ? JSON</button>
      <button type=\"button\" class=\"secondary\" data-endpoint=\"csv\">Run ? CSV</button>
      <button type=\"button\" class=\"tertiary\" data-endpoint=\"pdf\">Run ? PDF</button>
    </div>
  </form>
  <h2>JSON Output</h2>
  <pre id=\"json-output\">Ready.</pre>
<script>
const form = document.getElementById('ga-form');
const output = document.getElementById('json-output');

async function runOptimizer(target) {
  const endpoint = target.dataset.endpoint;
  const formData = new FormData(form);
  try {
    const response = await fetch(`/optimize/${endpoint}`, { method: 'POST', body: formData });
    if (!response.ok) {
      const errText = await response.text();
      throw new Error(errText || 'Request failed');
    }
    if (endpoint === 'json') {
      const payload = await response.json();
      output.textContent = JSON.stringify(payload, null, 2);
    } else {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = endpoint === 'csv' ? 'jadwal_hasil.csv' : 'hasil_run_penjadwalan.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    }
  } catch (err) {
    output.textContent = `Error: ${err.message}`;
  }
}

document.querySelectorAll('button[data-endpoint]').forEach((button) => {
  button.addEventListener('click', () => runOptimizer(button));
});
</script>
</body>
</html>"""


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML)


async def read_dataset(upload: UploadFile) -> pd.DataFrame:
    if upload is None:
        raise HTTPException(status_code=400, detail="File upload is required")
    filename = upload.filename or "dataset.csv"
    suffix = Path(filename).suffix.lower()
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    buffer = io.BytesIO(content)
    if suffix == ".csv":
        df = pd.read_csv(buffer)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(buffer)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use CSV or XLSX.")
    return df


def validate_ga_params(pop_size: int, gens: int, cx_rate: float, mut_rate: float) -> None:
    if pop_size < 2:
        raise HTTPException(status_code=400, detail="Population size must be >= 2")
    if gens < 1:
        raise HTTPException(status_code=400, detail="Generations must be >= 1")
    if not 0 <= cx_rate <= 1:
        raise HTTPException(status_code=400, detail="Crossover rate must be between 0 and 1")
    if not 0 <= mut_rate <= 1:
        raise HTTPException(status_code=400, detail="Mutation rate must be between 0 and 1")


async def run_engine(
    file: UploadFile,
    pop_size: int,
    gens: int,
    cx_rate: float,
    mut_rate: float,
    seed: int,
) -> Dict[str, Any]:
    validate_ga_params(pop_size, gens, cx_rate, mut_rate)
    df = await read_dataset(file)
    return solve_timetable(df, pop_size=pop_size, gens=gens, cx_rate=cx_rate, mut_rate=mut_rate, seed=seed)


@app.post("/optimize/json")
async def optimize_json(
    file: UploadFile = File(...),
    pop_size: int = Form(60),
    gens: int = Form(200),
    cx_rate: float = Form(0.8),
    mut_rate: float = Form(0.2),
    seed: int = Form(42),
) -> Dict[str, Any]:
    result = await run_engine(file, pop_size, gens, cx_rate, mut_rate, seed)
    schedule = result["result"].to_dict(orient="records")
    return {
        "best_fitness": result["best_fitness"],
        "fitness_history": result["fitness_history"],
        "schedule": schedule,
    }


@app.post("/optimize/csv")
async def optimize_csv(
    file: UploadFile = File(...),
    pop_size: int = Form(60),
    gens: int = Form(200),
    cx_rate: float = Form(0.8),
    mut_rate: float = Form(0.2),
    seed: int = Form(42),
) -> StreamingResponse:
    result = await run_engine(file, pop_size, gens, cx_rate, mut_rate, seed)
    buffer = io.StringIO()
    result["result"].to_csv(buffer, index=False)
    headers = {"Content-Disposition": "attachment; filename=jadwal_hasil.csv"}
    csv_bytes = buffer.getvalue().encode("utf-8")
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv", headers=headers)


@app.post("/optimize/pdf")
async def optimize_pdf(
    file: UploadFile = File(...),
    pop_size: int = Form(60),
    gens: int = Form(200),
    cx_rate: float = Form(0.8),
    mut_rate: float = Form(0.2),
    seed: int = Form(42),
) -> StreamingResponse:
    result = await run_engine(file, pop_size, gens, cx_rate, mut_rate, seed)
    dataset_name = file.filename or "dataset"
    pdf_bytes = build_pdf(
        result["result"], result["best_fitness"], result["fitness_history"], dataset_name
    )
    headers = {"Content-Disposition": "attachment; filename=hasil_run_penjadwalan.pdf"}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


def build_pdf(schedule: pd.DataFrame, best_fitness: float, history: List[float], dataset_name: str) -> bytes:
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        _add_summary_page(pdf, dataset_name, best_fitness, schedule)
        _add_history_page(pdf, history)
        _add_day_tables(pdf, schedule)
    buffer.seek(0)
    return buffer.getvalue()


def _add_summary_page(pdf: PdfPages, dataset_name: str, best_fitness: float, schedule: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    text = [
        f"Dataset: {dataset_name}",
        f"Entries: {len(schedule)}",
        f"Best fitness: {best_fitness:.2f}",
        "",
        "Hard constraints:",
        "- No room/lecturer/cohort overlaps",
        "- DLB lecturers only on Friday/Saturday",
        "- Sessions must remain within 07:00-17:00",
        "",
        "Soft objectives:",
        "- Minimize idle minutes per cohort/day",
        "- Minimize distinct teaching days per cohort",
    ]
    ax.text(0.05, 0.95, "\n".join(text), va="top", fontsize=12)
    ax.set_title("GA Timetabling Summary", loc="center", fontsize=16)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _add_history_page(pdf: PdfPages, history: List[float]) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.plot(history, color="#2563eb", linewidth=2)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Penalty (fitness)")
    ax.set_title("Fitness Progression")
    ax.grid(alpha=0.3)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _add_day_tables(pdf: PdfPages, schedule: pd.DataFrame) -> None:
    if schedule.empty:
        return
    for day in DAYS:
        day_df = schedule[schedule["Hari"] == day]
        if day_df.empty:
            continue
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title(f"Jadwal {day}")
        table_data = [[
            row["Mulai"],
            row["Selesai"],
            row["Ruang"],
            f"SMT {row['SMT']} / {row['Kelas']}",
            f"{row['MataKuliah']} ({row['Dosen']})",
        ] for _, row in day_df.iterrows()]
        column_labels = ["Mulai", "Selesai", "Ruang", "SMT/Kelas", "Mata Kuliah (Dosen)"]
        table = ax.table(cellText=table_data, colLabels=column_labels, loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.4)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
