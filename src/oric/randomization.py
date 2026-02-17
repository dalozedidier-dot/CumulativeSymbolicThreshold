from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple
import random


@dataclass
class Condition:
    name: str
    params: Dict[str, float]


class RandomizationEngine:
    """Deterministic randomization engine for experiments.

    It provides:
    - seed generation
    - condition assignment
    - optional blocking by scenario id
    """

    def __init__(self, master_seed: int = 42) -> None:
        self.master_seed = master_seed
        self._rng = random.Random(master_seed)

    def seeds(self, n: int) -> List[int]:
        return [self._rng.randrange(1, 2**31 - 1) for _ in range(n)]

    def assign_conditions(self, seeds: Sequence[int], conditions: Sequence[Condition]) -> List[Tuple[int, str]]:
        """Assign each seed to a condition, round-robin then shuffled deterministically."""
        if not conditions:
            raise ValueError("conditions must be non-empty")
        pairs = [(seeds[i], conditions[i % len(conditions)].name) for i in range(len(seeds))]
        self._rng.shuffle(pairs)
        return pairs
