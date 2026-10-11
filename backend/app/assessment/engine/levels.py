from dataclasses import dataclass
from enum import StrEnum

from app.config.params import Params


class Grade(StrEnum):
    junior = "junior"
    middle = "middle"
    senior = "senior"


GRADE_ORDER = (Grade.junior, Grade.middle, Grade.senior)

# Рабочие уровни сложности (процесс 3.4): фаза 1 — около cut_g, фаза 2 — около cut_{g+1}
PHASE1_BAND: dict[Grade, tuple[int, ...]] = {
    Grade.junior: (1, 2, 3), Grade.middle: (2, 3, 4), Grade.senior: (3, 4, 5),
}
PHASE2_BAND: dict[Grade, tuple[int, ...]] = {
    Grade.junior: (2, 3, 4), Grade.middle: (3, 4, 5), Grade.senior: (4, 5),
}


def grade_rank(g: Grade) -> int:
    return GRADE_ORDER.index(Grade(g))


def level_b(level: int, params: Params) -> float:
    return params.b_levels[level - 1]


@dataclass(frozen=True)
class Thresholds:
    version: str
    cut_j: float
    cut_m: float
    cut_s: float
    virtual_gap: float

    @classmethod
    def from_params(cls, params: Params, version: str = "expert-1") -> "Thresholds":
        return cls(version, params.cut_j, params.cut_m, params.cut_s, params.senior_virtual_gap)

    def cut(self, g: Grade) -> float:
        return {Grade.junior: self.cut_j, Grade.middle: self.cut_m, Grade.senior: self.cut_s}[Grade(g)]

    def next_cut(self, g: Grade) -> float:
        g = Grade(g)
        if g == Grade.senior:
            return self.cut_s + self.virtual_gap
        return self.cut(GRADE_ORDER[grade_rank(g) + 1])
