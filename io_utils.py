"""Utilities for I/O: reading uploads, creating templates, and exports."""
from __future__ import annotations

import io
from datetime import datetime
from typing import List, Tuple

import pandas as pd
from models import CourseRow
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

REQUIRED_COLUMNS = [
    "kode_mk",
    "nama_mk",
    "sks",
    "semester",
    "kelas",
    "dosen",
    "jenis_dosen",
]
OPTIONAL_COLUMNS = ["prefer_hari", "prefer_sesi", "catatan"]


def _clean(value, default=None):
    if pd.isna(value) or value is None:
        return default
    return value


def _normalize_jenis(value) -> str:
    cleaned = _clean(value, "Tetap")
    if not cleaned:
        return "Tetap"
    token = str(cleaned).strip().upper()
    if "DLB" in token or "LUAR" in token:
        return "DLB"
    return "Tetap"


def load_courses_from_upload(filename: str, raw_bytes: bytes) -> List[CourseRow]:
    extension = filename.lower().split(".")[-1]
    buffer = io.BytesIO(raw_bytes)
    if extension == "csv":
        df = pd.read_csv(buffer)
    elif extension in {"xlsx", "xls"}:
        df = pd.read_excel(buffer)
    else:
        raise ValueError("Format file harus CSV atau XLSX")

    df.columns = [str(col).strip().lower() for col in df.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(missing)}")

    courses: List[CourseRow] = []
    for _, row in df.iterrows():
        if pd.isna(row.get("kode_mk")):
            continue
        sks_val = row.get("sks")
        sem_val = row.get("semester")
        payload_sks = int(float(sks_val)) if pd.notna(sks_val) else 0
        payload_sem = int(float(sem_val)) if pd.notna(sem_val) else 0
        payload = {
            "kode_mk": _clean(row.get("kode_mk"), ""),
            "nama_mk": _clean(row.get("nama_mk"), ""),
            "sks": payload_sks,
            "semester": payload_sem,
            "kelas": _clean(row.get("kelas"), "A"),
            "dosen": _clean(row.get("dosen"), ""),
            "jenis_dosen": _normalize_jenis(row.get("jenis_dosen")),
            "prefer_hari": _clean(row.get("prefer_hari")),
            "prefer_sesi": _clean(row.get("prefer_sesi")),
            "catatan": _clean(row.get("catatan")),
        }
        courses.append(CourseRow(**payload))
    if not courses:
        raise ValueError("File tidak memiliki baris data yang valid")
    return courses


def generate_template_workbook() -> bytes:
    data = {
        "kode_mk": ["IF101", "IF201"],
        "nama_mk": ["Matematika Diskrit", "Struktur Data"],
        "sks": [3, 3],
        "semester": [1, 3],
        "kelas": ["A", "B"],
        "dosen": ["Dr. Andi", "Ir. Budi"],
        "jenis_dosen": ["Tetap", "DLB"],
        "prefer_hari": ["Senin,Rabu", ""],
        "prefer_sesi": ["Pagi", "Sore"],
        "catatan": ["", ""],
    }
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="template")
    buffer.seek(0)
    return buffer.read()


def export_view(view_name: str, rows: List[dict], fmt: str) -> Tuple[bytes, str, str]:
    filename = f"jadwal_{view_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
    if fmt == "csv":
        buffer = io.StringIO()
        pd.DataFrame(rows).to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8"), "text/csv", filename
    if fmt == "xlsx":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=view_name)
        buffer.seek(0)
        return buffer.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename
    if fmt == "pdf":
        return _export_pdf(view_name, rows, filename)
    raise ValueError("Format unduhan tidak dikenal")


def _export_pdf(view_name: str, rows: List[dict], filename: str) -> Tuple[bytes, str, str]:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Pratinjau Jadwal - {view_name.title()}", styles["Heading2"])]
    if rows:
        columns = list(rows[0].keys())
        table_data = [columns]
        for row in rows:
            table_data.append([str(row.get(col, "")) for col in columns])
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Tidak ada data jadwal.", styles["BodyText"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.read(), "application/pdf", filename


def generate_demo_courses() -> List[CourseRow]:
    demo = [
        {
            "kode_mk": "IF101",
            "nama_mk": "Algoritma Genetika",
            "sks": 3,
            "semester": 5,
            "kelas": "A",
            "dosen": "Dr. Maura Widya Ningsih",
            "jenis_dosen": "Tetap",
            "prefer_hari": "Senin,Rabu",
            "prefer_sesi": "Pagi",
        },
        {
            "kode_mk": "RPL312305",
            "nama_mk": "Pemrograman Web",
            "sks": 3,
            "semester": 3,
            "kelas": "B",
            "dosen": "Lili Rusdiana, M.Kom.",
            "jenis_dosen": "Tetap",
            "prefer_hari": "Selasa",
            "prefer_sesi": "Siang",
        },
        {
            "kode_mk": "MTS112202",
            "nama_mk": "Aljabar Linear dan Matriks",
            "sks": 3,
            "semester": 3,
            "kelas": "A",
            "dosen": "Rudini, M.Pd.",
            "jenis_dosen": "DLB",
            "prefer_hari": "Jumat,Sabtu",
            "prefer_sesi": "Sore",
        },
    ]
    return [CourseRow(**item) for item in demo]
