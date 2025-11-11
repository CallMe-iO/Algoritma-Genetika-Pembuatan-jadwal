"""Data models for the penjadwalan kuliah application."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, validator

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
ROOMS = [f"TI-{idx}" for idx in range(1, 7)]
SESSION_MAP = {
    "Pagi": range(0, 4),
    "Siang": range(4, 8),
    "Sore": range(8, 12),
}


class CourseRow(BaseModel):
    """Normalized representation of a single mata kuliah entry."""

    kode_mk: str
    nama_mk: str
    sks: int
    semester: int
    kelas: str
    dosen: str
    jenis_dosen: str
    prefer_hari: Optional[List[str]] = None
    prefer_sesi: Optional[str] = None
    catatan: Optional[str] = None

    @validator("kode_mk", "nama_mk", "dosen", pre=True)
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @validator("sks")
    def validate_sks(cls, value: int) -> int:
        if value <= 0 or value > 4:
            raise ValueError("SKS harus antara 1 sampai 4")
        return value

    @validator("semester")
    def validate_semester(cls, value: int) -> int:
        if value < 1 or value > 7:
            raise ValueError("Semester harus antara 1 sampai 7")
        return value

    @validator("kelas")
    def validate_kelas(cls, value: str) -> str:
        if value.upper() not in {"A", "B"}:
            raise ValueError("Kelas harus A atau B")
        return value.upper()

    @validator("jenis_dosen")
    def validate_jenis_dosen(cls, value: str) -> str:
        if value not in {"Tetap", "DLB"}:
            raise ValueError("jenis_dosen harus Tetap atau DLB")
        return value

    @validator("prefer_hari", pre=True, always=True)
    def normalize_prefer_hari(cls, value):
        if not value:
            return None
        if isinstance(value, str):
            tokens = [item.strip().capitalize() for item in value.split(",") if item.strip()]
        else:
            tokens = [str(item).strip().capitalize() for item in value if str(item).strip()]
        filtered = [token for token in tokens if token in DAYS]
        return filtered or None

    @validator("prefer_sesi", pre=True, always=True)
    def normalize_prefer_sesi(cls, value):
        if not value:
            return None
        token = str(value).strip().capitalize()
        if token not in SESSION_MAP:
            raise ValueError("prefer_sesi harus Pagi, Siang, atau Sore")
        return token


class DatasetSummary(BaseModel):
    total_matkul: int
    total_sks: int
    total_dosen: int
    semesters: List[int]


class GAParameters(BaseModel):
    ukuran_populasi: int = 150
    jumlah_generasi: int = 500
    laju_crossover: float = 0.9
    laju_mutasi: float = 0.15
    elitisme: int = 2
    ukuran_turnamen: int = 3
    batas_waktu: int = 20
    seed: Optional[int] = None
    percepat_perbaikan: bool = False
    utamakan_preferensi: bool = False

    @validator("ukuran_populasi", "jumlah_generasi", "elitisme", "ukuran_turnamen")
    def positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("parameter harus bernilai positif")
        return value

    @validator("laju_crossover", "laju_mutasi")
    def probability(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("laju harus antara 0 dan 1")
        return value

    @validator("batas_waktu")
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("batas_waktu tidak boleh negatif")
        return value


class ScheduleEntry(BaseModel):
    hari: str
    jam_mulai: str
    jam_selesai: str
    kode_mk: str
    nama_mk: str
    sks: int
    semester: int
    kelas: str
    ruang: str
    dosen: str
    catatan: Optional[str] = None


class ScheduleViews(BaseModel):
    per_kelas: List[dict]
    per_ruang: List[dict]
    per_dosen: List[dict]


class ConstraintSummary(BaseModel):
    tanpa_bentrok_ruang: bool
    tanpa_bentrok_dosen: bool
    tanpa_bentrok_kelas: bool
    patuh_dlb: bool
    peringatan: List[str]
    stat_pemakaian_ruang: List[dict]


class OptimizationPayload(BaseModel):
    status: str
    fitness_best: float
    generasi_tercapai: int
    ringkasan: ConstraintSummary
    jadwal: ScheduleViews

