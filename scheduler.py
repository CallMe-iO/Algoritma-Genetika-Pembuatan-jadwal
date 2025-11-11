"""Utility functions for validating and summarizing schedules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from models import ConstraintSummary, CourseRow, DatasetSummary, DAYS, ROOMS, ScheduleEntry, ScheduleViews

SLOT_DURATION_MIN = 50


@dataclass
class Placement:
    course_idx: int
    day: int
    start_slot: int
    room_idx: int


def slot_to_time(slot: int) -> str:
    base_hour = 7
    total_minutes = base_hour * 60 + slot * SLOT_DURATION_MIN
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def dataset_summary(courses: List[CourseRow]) -> DatasetSummary:
    semesters = sorted({row.semester for row in courses})
    return DatasetSummary(
        total_matkul=len(courses),
        total_sks=sum(row.sks for row in courses),
        total_dosen=len({row.dosen for row in courses}),
        semesters=semesters,
    )


def build_entries(placements: List[Placement], courses: List[CourseRow]) -> List[ScheduleEntry]:
    entries: List[ScheduleEntry] = []
    for placement in placements:
        course = courses[placement.course_idx]
        start_time = slot_to_time(max(0, placement.start_slot))
        end_slot = placement.start_slot + course.sks
        end_time = slot_to_time(max(0, min(12, end_slot)))
        if course.sks == 0:
            continue
        entry = ScheduleEntry(
            hari=DAYS[placement.day] if 0 <= placement.day < len(DAYS) else "Tidak valid",
            jam_mulai=start_time,
            jam_selesai=end_time,
            kode_mk=course.kode_mk,
            nama_mk=course.nama_mk,
            sks=course.sks,
            semester=course.semester,
            kelas=course.kelas,
            ruang=ROOMS[placement.room_idx] if 0 <= placement.room_idx < len(ROOMS) else "TBD",
            dosen=course.dosen,
            catatan=course.catatan,
        )
        entries.append(entry)
    return entries


def _add_warning(warnings: List[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def evaluate_schedule(
    placements: List[Placement],
    courses: List[CourseRow],
    prefer_weight: float = 1.0,
) -> Tuple[float, float, ConstraintSummary, Dict[str, Any]]:
    """Return hard penalty, soft penalty, summary flags, and raw diagnostics."""
    room_map: Dict[Tuple[int, int, int], int] = {}
    lecturer_map: Dict[Tuple[int, int], set] = {}
    class_map: Dict[Tuple[str, int, int], bool] = {}
    hard_counts = {
        "room": 0,
        "lecturer": 0,
        "class": 0,
        "dlb": 0,
        "range": 0,
    }
    room_usage_counter = {room: 0 for room in ROOMS}
    class_day_loads: Dict[str, List[int]] = {}
    lecturer_slots_per_day: Dict[str, Dict[int, List[int]]] = {}
    class_slots_per_day: Dict[str, Dict[int, List[int]]] = {}
    warnings: List[str] = []
    prefer_penalty = 0.0
    gap_penalty = 0.0
    dlb_time_penalty = 0.0

    for placement in placements:
        course = courses[placement.course_idx]
        day = placement.day
        if placement.room_idx < 0 or placement.room_idx >= len(ROOMS):
            hard_counts["range"] += 1
            continue
        duration = course.sks
        slots = list(range(placement.start_slot, placement.start_slot + duration))
        if day < 0 or day >= len(DAYS):
            hard_counts["range"] += 1
            continue
        if placement.start_slot < 0 or placement.start_slot + duration > 12:
            hard_counts["range"] += 1
            continue
        if course.jenis_dosen == "DLB" and day not in (4, 5):
            hard_counts["dlb"] += 1
        kelas_label = f"Smt {course.semester}{course.kelas}"
        class_day_loads.setdefault(kelas_label, [0] * len(DAYS))
        class_day_loads[kelas_label][day] += 1
        class_slots_per_day.setdefault(kelas_label, {}).setdefault(day, []).extend(slots)
        lecturer_slots_per_day.setdefault(course.dosen, {}).setdefault(day, []).extend(slots)
        for slot in slots:
            room_key = (day, slot, placement.room_idx)
            if room_key in room_map:
                hard_counts["room"] += 1
            else:
                room_map[room_key] = placement.course_idx
            lect_key = (day, slot)
            lecturer_map.setdefault(lect_key, set())
            if course.dosen in lecturer_map[lect_key]:
                hard_counts["lecturer"] += 1
            else:
                lecturer_map[lect_key].add(course.dosen)
            class_key = (kelas_label, day, slot)
            if class_key in class_map:
                hard_counts["class"] += 1
            else:
                class_map[class_key] = True
            room_usage_counter[ROOMS[placement.room_idx]] += 1

        if course.prefer_hari and DAYS[day] not in course.prefer_hari:
            prefer_penalty += 1 * prefer_weight
        if course.prefer_sesi:
            allowed_slots = set(range(0, 12))
            if course.prefer_sesi == "Pagi":
                allowed_slots = set(range(0, 4))
            elif course.prefer_sesi == "Siang":
                allowed_slots = set(range(4, 8))
            elif course.prefer_sesi == "Sore":
                allowed_slots = set(range(8, 12))
            if not set(slots).issubset(allowed_slots):
                prefer_penalty += 1.5 * prefer_weight

        if course.jenis_dosen == "DLB" and slots and min(slots) < 4:
            dlb_time_penalty += 0.5

    # Gap penalties
    for kelas_label, days in class_slots_per_day.items():
        for day_slots in days.values():
            gap_penalty += _gaps_penalty(day_slots)
    for lecturer, days in lecturer_slots_per_day.items():
        for day_slots in days.values():
            gap_penalty += _gaps_penalty(day_slots)

    # Load distribution
    distribution_penalty = 0.0
    for kelas_label, counts in class_day_loads.items():
        non_zero = [count for count in counts if count > 0]
        if not non_zero:
            continue
        avg = sum(non_zero) / len(non_zero)
        variance = sum((count - avg) ** 2 for count in non_zero)
        distribution_penalty += variance * 0.2
        if max(counts) - min(counts) > 2:
            _add_warning(warnings, f"Sebaran jadwal belum merata untuk {kelas_label}")

    # Room utilization variance
    usage_values = list(room_usage_counter.values())
    if usage_values:
        avg_usage = sum(usage_values) / len(usage_values)
        room_variance = sum((val - avg_usage) ** 2 for val in usage_values) / len(usage_values)
    else:
        room_variance = 0.0

    soft_penalty = distribution_penalty + gap_penalty * 0.3 + prefer_penalty + dlb_time_penalty + room_variance * 0.05
    hard_penalty = sum(hard_counts.values()) * 1_000_000
    summary = ConstraintSummary(
        tanpa_bentrok_ruang=hard_counts["room"] == 0,
        tanpa_bentrok_dosen=hard_counts["lecturer"] == 0,
        tanpa_bentrok_kelas=hard_counts["class"] == 0,
        patuh_dlb=hard_counts["dlb"] == 0,
        stat_pemakaian_ruang=_room_usage_stats(room_usage_counter),
        peringatan=warnings,
    )

    diagnostics = {
        "hard_counts": hard_counts,
        "room_usage_raw": room_usage_counter,
        "class_day_loads": class_day_loads,
    }

    return hard_penalty, soft_penalty, summary, diagnostics


def _gaps_penalty(slots: Iterable[int]) -> float:
    ordered = sorted(slots)
    penalty = 0.0
    for idx in range(1, len(ordered)):
        gap = ordered[idx] - ordered[idx - 1] - 1
        if gap > 2:
            penalty += (gap - 2)
    return penalty


def _room_usage_stats(room_usage: Dict[str, int]) -> List[dict]:
    max_slots = len(DAYS) * 12
    stats = []
    for room, used in room_usage.items():
        percentage = round((used / max_slots) * 100, 1) if max_slots else 0.0
        stats.append({"ruang": room, "terpakai_slot": used, "persentase": percentage})
    stats.sort(key=lambda item: item["ruang"])
    return stats


def build_views(entries: List[ScheduleEntry]) -> ScheduleViews:
    per_kelas, per_ruang, per_dosen = [], [], []
    for entry in entries:
        base = entry.dict()
        per_kelas.append({"grup": f"Smt {entry.semester}{entry.kelas}", **base})
        per_ruang.append({"grup": entry.ruang, **base})
        per_dosen.append({"grup": entry.dosen, **base})
    sort_key = lambda item: (DAYS.index(item["hari"]) if item["hari"] in DAYS else 0, item["jam_mulai"])
    per_kelas.sort(key=sort_key)
    per_ruang.sort(key=sort_key)
    per_dosen.sort(key=sort_key)
    return ScheduleViews(per_kelas=per_kelas, per_ruang=per_ruang, per_dosen=per_dosen)
