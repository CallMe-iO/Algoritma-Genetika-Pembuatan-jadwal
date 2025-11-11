"""Genetic Algorithm implementation for jadwal penjadwalan."""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List

from models import DAYS, CourseRow, GAParameters, ROOMS
from scheduler import Placement, build_entries, evaluate_schedule


class GeneticAlgorithm:
    def __init__(self, courses: List[CourseRow], params: GAParameters):
        self.courses = courses
        self.params = params
        self.random = random.Random(params.seed)

    def run(self) -> Dict[str, Any]:
        population = [self._random_chromosome() for _ in range(self.params.ukuran_populasi)]
        scored = [self._evaluate(chromosome) for chromosome in population]
        initial_best = max(scored, key=lambda item: item["fitness"])
        best_overall = self._clone_entry(initial_best)
        best_generation_index = 0
        stagnation = 0
        stagnation_limit = max(30, self.params.jumlah_generasi // 5)
        start_time = time.time()
        generations_run = 0

        for generation in range(1, self.params.jumlah_generasi + 1):
            generations_run = generation
            new_population: List[Dict[str, Any]] = []
            elite_count = min(self.params.elitisme, len(scored))
            elites = sorted(scored, key=lambda item: item["fitness"], reverse=True)[:elite_count]
            new_population.extend(self._clone_entry(entry) for entry in elites)

            while len(new_population) < self.params.ukuran_populasi:
                parent1 = self._tournament_pick(scored)
                parent2 = self._tournament_pick(scored)
                child = self._crossover(parent1["chromosome"], parent2["chromosome"])
                self._mutate(child)
                if self.params.percepat_perbaikan:
                    self._repair(child)
                child_entry = self._evaluate(child)
                new_population.append(child_entry)

                if self.params.batas_waktu and (time.time() - start_time) > self.params.batas_waktu:
                    break

            scored = new_population[: self.params.ukuran_populasi]
            best_generation = max(scored, key=lambda item: item["fitness"])
            if best_generation["fitness"] > best_overall["fitness"]:
                best_overall = self._clone_entry(best_generation)
                best_generation_index = generation
                stagnation = 0
            else:
                stagnation += 1

            if self.params.batas_waktu and (time.time() - start_time) > self.params.batas_waktu:
                break
            if stagnation >= stagnation_limit:
                break

        entries = build_entries(best_overall["chromosome"], self.courses)
        return {
            "fitness": best_overall["fitness"],
            "generasi": best_generation_index or generations_run,
            "chromosome": best_overall["chromosome"],
            "summary": best_overall["summary"],
            "diagnostics": best_overall["diagnostics"],
            "entries": entries,
        }

    def _random_chromosome(self) -> List[Placement]:
        chromosome: List[Placement] = []
        for idx, course in enumerate(self.courses):
            day = self.random.choice(self._day_choices(course))
            start_slot = self._sample_slot(course)
            room_idx = self.random.randrange(len(ROOMS))
            chromosome.append(Placement(course_idx=idx, day=day, start_slot=start_slot, room_idx=room_idx))
        return chromosome

    def _sample_slot(self, course: CourseRow) -> int:
        max_start = max(0, 12 - course.sks)
        if course.prefer_sesi == "Pagi":
            return self.random.randint(0, min(3, max_start))
        if course.prefer_sesi == "Siang":
            return self.random.randint(4, min(7, max_start))
        if course.prefer_sesi == "Sore":
            lower = min(8, max_start)
            return self.random.randint(lower, max_start)
        return self.random.randint(0, max_start)

    def _day_choices(self, course: CourseRow) -> List[int]:
        if course.jenis_dosen == "DLB":
            return [4, 5]
        if course.prefer_hari:
            indices = [idx for idx, name in enumerate(DAYS) if name in course.prefer_hari]
            if indices:
                # Bias selection towards preferred days.
                weighted = indices * 3 + list(range(len(DAYS)))
                return weighted
        return list(range(len(DAYS)))

    def _crossover(self, parent1: List[Placement], parent2: List[Placement]) -> List[Placement]:
        if self.random.random() > self.params.laju_crossover:
            return [Placement(**gene.__dict__) for gene in parent1]
        child: List[Placement] = []
        for gene1, gene2 in zip(parent1, parent2):
            source = gene1 if self.random.random() < 0.5 else gene2
            child.append(Placement(**source.__dict__))
        return child

    def _mutate(self, chromosome: List[Placement]) -> None:
        if self.random.random() > self.params.laju_mutasi:
            return
        gene = self.random.choice(chromosome)
        course = self.courses[gene.course_idx]
        action = self.random.choice(["day", "slot", "room"])
        if action == "day":
            gene.day = self.random.choice(self._day_choices(course))
        elif action == "slot":
            gene.start_slot = self._sample_slot(course)
        else:
            gene.room_idx = self.random.randrange(len(ROOMS))

    def _repair(self, chromosome: List[Placement]) -> None:
        for gene in chromosome:
            course = self.courses[gene.course_idx]
            if course.jenis_dosen == "DLB" and gene.day not in (4, 5):
                gene.day = self.random.choice([4, 5])
            max_start = max(0, 12 - course.sks)
            if gene.start_slot > max_start:
                gene.start_slot = max_start
            if gene.start_slot < 0:
                gene.start_slot = 0

    def _evaluate(self, chromosome: List[Placement]) -> Dict[str, Any]:
        prefer_weight = 2.0 if self.params.utamakan_preferensi else 1.0
        hard_penalty, soft_penalty, summary, diagnostics = evaluate_schedule(
            chromosome,
            self.courses,
            prefer_weight=prefer_weight,
        )
        fitness = -(hard_penalty + soft_penalty)
        return {
            "chromosome": [Placement(**gene.__dict__) for gene in chromosome],
            "fitness": fitness,
            "summary": summary,
            "diagnostics": diagnostics,
        }

    def _tournament_pick(self, population: List[Dict[str, Any]]) -> Dict[str, Any]:
        k = min(self.params.ukuran_turnamen, len(population))
        contestants = self.random.sample(population, k)
        return max(contestants, key=lambda item: item["fitness"])

    def _clone_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        cloned = entry.copy()
        cloned["chromosome"] = [Placement(**gene.__dict__) for gene in entry["chromosome"]]
        return cloned


def optimize(courses: List[CourseRow], params: GAParameters) -> Dict[str, Any]:
    ga = GeneticAlgorithm(courses, params)
    return ga.run()
