"""Penalty-based Genetic Algorithm timetabling engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple, Set
import random

import pandas as pd

DAYS: List[str] = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
ROOMS: List[str] = [f"T{i}" for i in range(1, 7)]
START_TIMES: List[int] = [7 * 60, 9 * 60, 10 * 60, 13 * 60]
END_OF_DAY: int = 17 * 60
SKS_DURATION_MIN: Dict[int, int] = {1: 50, 2: 100, 3: 150}

DLB_LECTURERS = {
    "Pdt. Dr. Kilat Kasanang, S.Pd., M.Th.",
    "Dr. I. Gede Dharman Gunawan, M.Pd.H.",
    "Yustinus Dwi Andriyanto, S.Ag., M.M.",
    "Dr. Joko Santoso, S.Ag., M.M.",
    "Ir. Hj. Siti Maryamah, M.M.",
    "Moch. Ichsan, S.T., M.Kom.",
    "Dewanto Zulkarnaim, M.Pd.",
}


@dataclass(frozen=True)
class Course:
    """Represents a single course section that must be scheduled."""

    index: int
    hari: str
    mata_kuliah: str
    sks: int
    smt: int
    kelas: str
    dosen: str


@dataclass
class Assignment:
    """Schedule decision for a course gene."""

    course: Course
    day: str
    start: int
    end: int
    room: str

    def duration(self) -> int:
        return self.end - self.start

    def copy(self) -> "Assignment":
        return Assignment(self.course, self.day, self.start, self.end, self.room)

    def overlaps(self, other: "Assignment") -> bool:
        return self.start < other.end and other.start < self.end


def minutes_to_str(value: int) -> str:
    hours = value // 60
    minutes = value % 60
    return f"{hours:02d}:{minutes:02d}"


class GeneticScheduler:
    """Runs the GA search over possible timetables."""

    def __init__(
        self,
        courses: Sequence[Course],
        pop_size: int,
        gens: int,
        cx_rate: float,
        mut_rate: float,
        rng: random.Random,
    ) -> None:
        self.courses = list(courses)
        self.pop_size = pop_size
        self.gens = gens
        self.cx_rate = cx_rate
        self.mut_rate = mut_rate
        self.rng = rng

    # GA helpers ---------------------------------------------------------
    def _random_day(self, course: Course) -> str:
        allowed = ["Jumat", "Sabtu"] if course.dosen in DLB_LECTURERS else DAYS
        return self.rng.choice(allowed)

    def _random_start(self, course: Course) -> int:
        duration = SKS_DURATION_MIN[course.sks]
        valid_starts = [s for s in START_TIMES if s + duration <= END_OF_DAY]
        return self.rng.choice(valid_starts)

    def _random_assignment(self, course: Course) -> Assignment:
        start = self._random_start(course)
        return Assignment(
            course=course,
            day=self._random_day(course),
            start=start,
            end=start + SKS_DURATION_MIN[course.sks],
            room=self.rng.choice(ROOMS),
        )

    def _clone(self, chromosome: Sequence[Assignment]) -> List[Assignment]:
        return [gene.copy() for gene in chromosome]

    def random_chromosome(self) -> List[Assignment]:
        return [self._random_assignment(course) for course in self.courses]

    def evaluate(self, chromosome: Sequence[Assignment]) -> float:
        return compute_penalty(chromosome)

    def tournament_selection(
        self,
        population: Sequence[List[Assignment]],
        fitnesses: Sequence[float],
        size: int = 3,
    ) -> List[Assignment]:
        indices = [self.rng.randrange(len(population)) for _ in range(size)]
        best_idx = min(indices, key=lambda idx: fitnesses[idx])
        return self._clone(population[best_idx])

    def uniform_crossover(
        self, parent_a: Sequence[Assignment], parent_b: Sequence[Assignment]
    ) -> Tuple[List[Assignment], List[Assignment]]:
        child_a: List[Assignment] = []
        child_b: List[Assignment] = []
        for gene_a, gene_b in zip(parent_a, parent_b):
            if self.rng.random() < 0.5:
                child_a.append(gene_a.copy())
                child_b.append(gene_b.copy())
            else:
                child_a.append(gene_b.copy())
                child_b.append(gene_a.copy())
        return child_a, child_b

    def mutate(self, chromosome: List[Assignment]) -> None:
        for gene in chromosome:
            if self.rng.random() >= self.mut_rate:
                continue
            choice = self.rng.choice(["day", "start", "room"])
            if choice == "day":
                gene.day = self._random_day(gene.course)
            elif choice == "start":
                start = self._random_start(gene.course)
                gene.start = start
                gene.end = start + SKS_DURATION_MIN[gene.course.sks]
            else:
                gene.room = self.rng.choice(ROOMS)

    def run(self, progress: bool = False) -> Tuple[List[Assignment], List[float]]:
        population = [self.random_chromosome() for _ in range(self.pop_size)]
        fitnesses = [self.evaluate(chromo) for chromo in population]

        best_idx = min(range(self.pop_size), key=lambda i: fitnesses[i])
        best = self._clone(population[best_idx])
        best_fitness = fitnesses[best_idx]
        history = [best_fitness]

        for generation in range(1, self.gens + 1):
            new_population: List[List[Assignment]] = []
            while len(new_population) < self.pop_size:
                parent1 = self.tournament_selection(population, fitnesses)
                parent2 = self.tournament_selection(population, fitnesses)
                if self.rng.random() < self.cx_rate:
                    child1, child2 = self.uniform_crossover(parent1, parent2)
                else:
                    child1, child2 = parent1, parent2
                self.mutate(child1)
                self.mutate(child2)
                new_population.append(child1)
                if len(new_population) < self.pop_size:
                    new_population.append(child2)
            population = new_population[: self.pop_size]
            fitnesses = [self.evaluate(chromo) for chromo in population]

            gen_best_idx = min(range(self.pop_size), key=lambda i: fitnesses[i])
            gen_best = population[gen_best_idx]
            gen_best_score = fitnesses[gen_best_idx]
            if gen_best_score < best_fitness:
                best = self._clone(gen_best)
                best_fitness = gen_best_score
            history.append(best_fitness)
            if progress and generation % 10 == 0:
                print(f"Generation {generation}: best {best_fitness:.2f}")

        return best, history


def compute_penalty(assignments: Sequence[Assignment]) -> float:
    hard_penalty = 0.0
    soft_penalty = 0.0

    # Hard constraints -------------------------------------------------
    buckets: Dict[Tuple[str, str], List[Assignment]] = {}
    lecturer_buckets: Dict[Tuple[str, str], List[Assignment]] = {}
    cohort_buckets: Dict[Tuple[str, str, str], List[Assignment]] = {}

    for assignment in assignments:
        buckets.setdefault((assignment.day, assignment.room), []).append(assignment)
        lecturer_buckets.setdefault((assignment.day, assignment.course.dosen), []).append(
            assignment
        )
        cohort_buckets.setdefault(
            (assignment.day, assignment.course.smt, assignment.course.kelas), []
        ).append(assignment)
        if assignment.course.dosen in DLB_LECTURERS and assignment.day not in {"Jumat", "Sabtu"}:
            hard_penalty += 1000
        if assignment.start < START_TIMES[0] or assignment.end > END_OF_DAY:
            hard_penalty += 1000

    hard_penalty += _overlap_penalty(buckets.values())
    hard_penalty += _overlap_penalty(lecturer_buckets.values())
    hard_penalty += _overlap_penalty(cohort_buckets.values())

    # Soft constraints --------------------------------------------------
    cohort_days: Dict[Tuple[int, str], Set[str]] = {}

    for (day, smt, kelas), day_assignments in cohort_buckets.items():
        sorted_assignments = sorted(day_assignments, key=lambda a: a.start)
        prev_end = None
        idle = 0.0
        for assignment in sorted_assignments:
            cohort_days.setdefault((assignment.course.smt, assignment.course.kelas), set()).add(day)
            if prev_end is not None and assignment.start > prev_end:
                idle += assignment.start - prev_end
            prev_end = assignment.end
        soft_penalty += 0.1 * idle

    for cohort, days in cohort_days.items():
        if len(days) > 1:
            soft_penalty += 25 * (len(days) - 1)

    return hard_penalty + soft_penalty

def _overlap_penalty(groups: Iterable[Sequence[Assignment]]) -> float:
    penalty = 0.0
    for group in groups:
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda a: a.start)
        for first, second in zip(ordered, ordered[1:]):
            if first.overlaps(second):
                penalty += 1000
    return penalty

def solve_timetable(
    df: pd.DataFrame,
    pop_size: int = 60,
    gens: int = 200,
    cx_rate: float = 0.8,
    mut_rate: float = 0.2,
    seed: int = 42,
    progress: bool = False,
) -> Dict[str, object]:
    required_columns = {"Hari", "MataKuliah", "SKS", "SMT", "Kelas", "Dosen"}
    if not required_columns.issubset(df.columns):
        missing = ", ".join(sorted(required_columns - set(df.columns)))
        raise ValueError(f"Missing required columns: {missing}")

    courses: List[Course] = []
    for i, row in df.iterrows():
        sks = int(row["SKS"])
        if sks not in SKS_DURATION_MIN:
            raise ValueError(f"Unsupported SKS value {sks} at row {i}")
        courses.append(
            Course(
                index=i,
                hari=row["Hari"],
                mata_kuliah=row["MataKuliah"],
                sks=sks,
                smt=int(row["SMT"]),
                kelas=str(row["Kelas"]),
                dosen=str(row["Dosen"]),
            )
        )

    if not courses:
        raise ValueError("Input dataset is empty")

    rng = random.Random(seed)
    scheduler = GeneticScheduler(courses, pop_size, gens, cx_rate, mut_rate, rng)
    best_assignments, history = scheduler.run(progress=progress)

    records = [
        {
            "Hari": assignment.day,
            "Mulai": minutes_to_str(assignment.start),
            "Selesai": minutes_to_str(assignment.end),
            "Ruang": assignment.room,
            "SMT": assignment.course.smt,
            "Kelas": assignment.course.kelas,
            "MataKuliah": assignment.course.mata_kuliah,
            "SKS": assignment.course.sks,
            "Dosen": assignment.course.dosen,
        }
        for assignment in best_assignments
    ]

    result_df = pd.DataFrame(records)
    if not result_df.empty:
        result_df = result_df.sort_values(
            by=["Hari", "Mulai", "Ruang", "SMT", "Kelas"]
        ).reset_index(drop=True)

    return {
        "result": result_df,
        "fitness_history": history,
        "best_fitness": history[-1],
    }
