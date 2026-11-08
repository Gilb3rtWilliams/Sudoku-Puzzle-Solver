"""Human-style reasoning for a puzzle: why must this cell be this digit?

The solver in solver.py finds answers by search, which gives no reasons. This module solves a
puzzle the way a person does, using only two techniques, and records every deduction together
with the cells it relied on:

  naked single   a cell whose row, column and box already contain every digit but one
  hidden single  a digit that has only one cell left to go in, within a row, column or box

Every step stores its *evidence*: for each fact it uses, one specific cell that proves it,
preferring given clues over earlier deductions so that explanations stay short. Explaining a cell
is then just walking back through the steps its evidence depends on.

Cells are flat indexes 0-80 (row * 9 + column). Text is 1-indexed and written for a player.
If a puzzle needs a technique beyond these two, the cells it can't reach have no explanation
(`explain` returns None) and the caller falls back to something more general.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from solver import PEERS, UNITS

ALL = 0b111111111
BOX_NAMES = [
    "top-left", "top-middle", "top-right",
    "middle-left", "centre", "middle-right",
    "bottom-left", "bottom-middle", "bottom-right",
]


# ---------- wording helpers ----------
def _pos(i):
    r, c = divmod(i, 9)
    return f"row {r + 1}, column {c + 1}"


def _cap(text):
    return text[0].upper() + text[1:]


def _join(items):
    items = [str(x) for x in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _shared_kind(i, j):
    """The first unit two peer cells share: row, then column, then box."""
    (r1, c1), (r2, c2) = divmod(i, 9), divmod(j, 9)
    if r1 == r2:
        return "row"
    if c1 == c2:
        return "column"
    return "box"


def _where(kind, j):
    """Where `j` is, relative to a unit we have already named (so we never say 'row 1 ... at row 1')."""
    r, c = divmod(j, 9)
    if kind == "row":
        return f"column {c + 1}"
    if kind == "column":
        return f"row {r + 1}"
    return f"row {r + 1}, column {c + 1}"


def _unit_label(u):
    if u < 9:
        return f"row {u + 1}"
    if u < 18:
        return f"column {u - 8}"
    return f"the {BOX_NAMES[u - 18]} box"


def _cells(indexes):
    return [{"row": i // 9, "col": i % 9} for i in sorted(set(indexes))]


# ---------- the recorded solve ----------
@dataclass
class Step:
    index: int                 # position in the solve order
    technique: str             # 'naked_single' | 'hidden_single'
    cell: int
    digit: int
    unit: int | None = None    # hidden singles: index into UNITS
    # naked single: {excluded digit: a peer cell holding it}
    # hidden single: {other empty cell in the unit: a peer cell that blocks `digit` there}
    evidence: dict = field(default_factory=dict)


class Explainer:
    """Solves `givens` with singles only, recording each step. Build once per puzzle."""

    def __init__(self, givens):
        self.values = [givens[i // 9][i % 9] for i in range(81)]
        self.given = [v != 0 for v in self.values]
        self.placed_by = [None] * 81   # step index that filled the cell, None for a given
        self.steps = []
        self.step_of_cell = {}
        self._solve()

    # -- solving --
    def _solve(self):
        cands = [0] * 81
        for i in range(81):
            if self.values[i]:
                continue
            m = ALL
            for p in PEERS[i]:
                if self.values[p]:
                    m &= ~(1 << (self.values[p] - 1))
            cands[i] = m

        while True:
            found = self._find_naked(cands) or self._find_hidden(cands)
            if not found:
                return
            technique, cell, digit, unit = found
            evidence = self._evidence(technique, cell, digit, unit)
            self._place(cands, Step(len(self.steps), technique, cell, digit, unit, evidence))

    def _find_naked(self, cands):
        for i in range(81):
            m = cands[i]
            if not self.values[i] and m and m & (m - 1) == 0:
                return "naked_single", i, m.bit_length(), None
        return None

    def _find_hidden(self, cands):
        for u, unit in enumerate(UNITS):
            present = {self.values[i] for i in unit}
            for d in range(1, 10):
                if d in present:
                    continue
                bit = 1 << (d - 1)
                spots = [i for i in unit if not self.values[i] and cands[i] & bit]
                if len(spots) == 1:
                    return "hidden_single", spots[0], d, u
        return None

    def _best_peer(self, cell, digit):
        """A peer of `cell` holding `digit`: a given clue if possible, else the earliest deduction."""
        holders = [p for p in PEERS[cell] if self.values[p] == digit]
        return min(holders, key=lambda p: (self.placed_by[p] is not None, self.placed_by[p] or 0))

    def _evidence(self, technique, cell, digit, unit):
        if technique == "naked_single":
            return {d: self._best_peer(cell, d) for d in range(1, 10) if d != digit}
        return {
            j: self._best_peer(j, digit)
            for j in UNITS[unit]
            if j != cell and not self.values[j]
        }

    def _place(self, cands, step):
        self.steps.append(step)
        self.step_of_cell[step.cell] = step.index
        self.values[step.cell] = step.digit
        self.placed_by[step.cell] = step.index
        cands[step.cell] = 0
        bit = 1 << (step.digit - 1)
        for p in PEERS[step.cell]:
            cands[p] &= ~bit

    @property
    def complete(self):
        return all(self.values)

    # -- explaining --
    def prerequisites(self, step_index):
        """Indexes of every step the given step relies on, directly or indirectly (excluding itself)."""
        seen, stack = set(), [step_index]
        while stack:
            s = stack.pop()
            for p in self.steps[s].evidence.values():
                dep = self.placed_by[p]
                if dep is not None and dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return sorted(seen)

    def _step_text(self, s):
        k, cell = s.digit, s.cell
        if s.technique == "naked_single":
            groups = {"row": [], "column": [], "box": []}
            for d, p in s.evidence.items():
                groups[_shared_kind(cell, p)].append(d)
            parts = [f"its {kind} has {_join(sorted(ds))}" for kind, ds in groups.items() if ds]
            return (f"{_cap(_pos(cell))} can only be {k}. {_cap('; '.join(parts))}. "
                    f"That rules out every other digit.")
        blocked = [
            f"{_pos(j)} already sees a {k} in its {_shared_kind(j, p)} (at {_where(_shared_kind(j, p), p)})"
            for j, p in s.evidence.items()
        ]
        return (f"In {_unit_label(s.unit)}, the {k} has only one place left: {_pos(cell)}. "
                f"Every other empty cell there is blocked: {'; '.join(blocked)}.")

    def _highlights(self, s):
        return _cells(s.evidence.values())

    def explain(self, cell, entered, correct):
        """Why `entered` is wrong at `cell` and `correct` is right, or None if this solver can't reach it.

        Returns {explanation, technique, highlights, steps}. `steps` are the earlier deductions the
        argument relies on, in order, each with its own text and the cells that prove it.
        """
        si = self.step_of_cell.get(cell)
        if si is None:
            return None
        target = self.steps[si]
        if target.digit != correct:  # cannot happen for a puzzle with a unique solution
            return None

        prereq = self.prerequisites(si)
        number = {s: n + 1 for n, s in enumerate(prereq)}

        text = f"Your {entered} is wrong. {self._step_text(target)}"
        if target.technique == "naked_single":
            p = target.evidence[entered]
            dep = self.placed_by[p]
            ref = f" (step {number[dep]} below)" if dep is not None else " (a given clue)"
            text += f" Your {entered} is ruled out because the {entered} has to go at {_pos(p)}{ref}."
        else:
            text += f" So this cell has to be {correct}, not {entered}."

        steps = [
            {
                "number": number[s],
                "row": self.steps[s].cell // 9,
                "col": self.steps[s].cell % 9,
                "digit": self.steps[s].digit,
                "technique": self.steps[s].technique,
                "text": self._step_text(self.steps[s]),
                "highlights": self._highlights(self.steps[s]),
            }
            for s in prereq
        ]
        return {
            "explanation": text,
            "technique": target.technique,
            "highlights": self._highlights(target),
            "steps": steps,
        }
