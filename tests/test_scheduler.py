import pytest

from models import CourseRow
from scheduler import Placement, evaluate_schedule


def sample_course(**overrides):
    base = {
        "kode_mk": "MKI112201",
        "nama_mk": "Agama Islam",
        "sks": 2,
        "semester": 1,
        "kelas": "A",
        "dosen": "Dr. Maura Widya Ningsih",
        "jenis_dosen": "Tetap",
    }
    base.update(overrides)
    return CourseRow(**base)


def test_schedule_without_conflict():
    courses = [
        sample_course(kode_mk="IF101", kelas="A"),
        sample_course(kode_mk="IF102", kelas="B", dosen="Dr. Sari"),
    ]
    placements = [
        Placement(course_idx=0, day=0, start_slot=0, room_idx=0),
        Placement(course_idx=1, day=0, start_slot=2, room_idx=1),
    ]
    hard, _, summary, _ = evaluate_schedule(placements, courses)
    assert hard == 0
    assert summary.tanpa_bentrok_ruang
    assert summary.tanpa_bentrok_dosen


def test_room_conflict_detected():
    courses = [
        sample_course(kode_mk="IF101"),
        sample_course(kode_mk="IF102", kelas="B", dosen="Dr. Sari"),
    ]
    placements = [
        Placement(course_idx=0, day=1, start_slot=1, room_idx=0),
        Placement(course_idx=1, day=1, start_slot=1, room_idx=0),
    ]
    hard, _, summary, _ = evaluate_schedule(placements, courses)
    assert hard > 0
    assert not summary.tanpa_bentrok_ruang


def test_dlb_violation_flag():
    courses = [
        sample_course(kode_mk="IF201", jenis_dosen="DLB", dosen="Ir. Budi"),
    ]
    placements = [
        Placement(course_idx=0, day=2, start_slot=3, room_idx=0),
    ]
    hard, _, summary, _ = evaluate_schedule(placements, courses)
    assert hard > 0
    assert not summary.patuh_dlb

