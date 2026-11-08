"""Human-style reasoning for a puzzle: why must this cell be this digit?

solver.py finds answers by search, which gives no reasons. This module solves a puzzle the way a
person does and records every deduction, so that each can be explained and checked.

Techniques, tried simplest first (each step is either a placement or a candidate elimination):

  naked single    a cell whose row, column and box already rule out every digit but one
  hidden single   a digit with only one cell left to go in, within a row, column or box
  pointing        inside a box a digit is confined to one line, so it leaves the rest of that line
  claiming        inside a line a digit is confined to one box, so it leaves the rest of that box
  naked pair      two cells in a unit share the same two candidates, which no other cell can use
  hidden pair     two digits in a unit fit only the same two cells, which then can't hold anything else
  x-wing          a digit confined to the same two columns in two rows (or vice versa)

Every step stores the *facts* it relies on, each of the form "cell j can't be digit d", together
with the reason: a peer cell that holds d (a given clue if possible, else the earliest deduction),
an earlier elimination step, or, for a cell in a unit the step reasons about as a whole, the fact
that it is already filled with another digit by an earlier deduction (given clues need no mention:
they are on the board). Explaining a cell is then a walk back through those reasons.

If a wrong digit is beyond all of that, `Explainer(givens, assume=(cell, digit))` supposes the digit
and runs the same techniques until something breaks: a cell with no digit left, or a digit with
nowhere to go. That contradiction is explained the same way.

Cells are flat indexes 0-80 (row * 9 + column). Text is 1-indexed and written for a player.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from solver import PEERS, UNITS

ALL = 0b111111111
ROWS = range(0, 9)       # indexes into UNITS
COLS = range(9, 18)
BOXES = range(18, 27)
BOX_NAMES = [
    "top-left", "top-middle", "top-right",
    "middle-left", "centre", "middle-right",
    "bottom-left", "bottom-middle", "bottom-right",
]
ADVANCED = ("pointing", "claiming", "naked_pair", "hidden_pair", "x_wing")


# ---------- wording helpers ----------
def _pos(i):
    r, c = divmod(i, 9)
    return f"row {r + 1}, column {c + 1}"


def _cap(text):
    return text[0].upper() + text[1:]


def _join(items, word="and"):
    items = [str(x) for x in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def _shared_kind(i, j):
    """The first unit two peer cells share: row, then column, then box."""
    (r1, c1), (r2, c2) = divmod(i, 9), divmod(j, 9)
    if r1 == r2:
        return "row"
    if c1 == c2:
        return "column"
    return "box"


def _where(kind, j):
    """Where `j` is, relative to a unit already named (so we never say 'row 1 ... at row 1')."""
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


def _positions(cells):
    return _join([_pos(c) for c in sorted(cells)])


# ---------- the recorded solve ----------
@dataclass
class Step:
    index: int
    technique: str
    cell: int | None = None        # placements (and the assumption): the cell filled
    digit: int | None = None       # placements: the digit
    unit: int | None = None        # the unit the pattern lives in
    pattern: list = field(default_factory=list)    # cells forming the pattern
    digits: tuple = ()             # digits the pattern is about (eliminations)
    eliminated: list = field(default_factory=list)  # [(cell, digit)] actually removed
    facts: list = field(default_factory=list)       # [(cell, digit, reason)]
    meta: dict = field(default_factory=dict)

    @property
    def is_placement(self):
        return self.cell is not None


class Explainer:
    """Solves `givens` with the techniques above, recording each step. Build once per puzzle.

    `assume=(cell, digit)` starts from a hypothetical instead (step 0 is the assumption) and stops
    at the first contradiction, which is kept in `self.contradiction`.
    """

    def __init__(self, givens, assume=None):
        self.values = [givens[i // 9][i % 9] for i in range(81)]
        self.given = [v != 0 for v in self.values]
        self.placed_by = [None] * 81   # step index that filled the cell; None for a given
        self.elim_by = {}              # (cell, digit) -> index of the elimination step that removed it
        self.steps = []
        self.step_of_cell = {}
        self.contradiction = None
        self.assume = assume
        self.cands = [0] * 81
        for i in range(81):
            if self.values[i]:
                continue
            m = ALL
            for p in PEERS[i]:
                if self.values[p]:
                    m &= ~(1 << (self.values[p] - 1))
            self.cands[i] = m
        if assume:
            cell, digit = assume
            self._apply(Step(0, "assumption", cell=cell, digit=digit))
        self._solve()

    # ---- state ----
    def _has(self, cell, d):
        return not self.values[cell] and bool(self.cands[cell] & (1 << (d - 1)))

    def _spots(self, u, d):
        """Empty cells in unit `u` that can still hold `d`."""
        return [i for i in UNITS[u] if self._has(i, d)]

    def _placed_in(self, u, d):
        return any(self.values[i] == d for i in UNITS[u])

    def _reason(self, j, d):
        """Why `j` can't be `d`: a peer holding it (a given if possible, else earliest) or an earlier step."""
        options = []
        for p in PEERS[j]:
            if self.values[p] == d:
                options.append(((0, 0) if self.placed_by[p] is None else (1, self.placed_by[p]), ("peer", p)))
        if (j, d) in self.elim_by:
            s = self.elim_by[(j, d)]
            options.append(((1, s), ("step", s)))
        return min(options, key=lambda o: o[0])[1]

    def _fact(self, j, d):
        return (j, d, self._reason(j, d))

    def _unit_facts(self, cells, d, skip=()):
        """Facts that `d` can't go in each of `cells` (bar `skip`): blocked, or filled by an earlier deduction.

        Cells filled by a given clue are left out (the player can see them); cells filled by a deduction
        must be cited, or an argument about "every other cell" would leave a hole.
        """
        out = []
        for j in cells:
            if j in skip:
                continue
            if not self.values[j]:
                out.append(self._fact(j, d))
            elif self.placed_by[j] is not None:
                out.append((j, d, ("filled", j)))
        return out

    def _apply(self, step):
        self.steps.append(step)
        if step.is_placement:
            self.values[step.cell] = step.digit
            self.placed_by[step.cell] = step.index
            self.cands[step.cell] = 0
            if step.technique != "assumption":
                self.step_of_cell[step.cell] = step.index
            bit = 1 << (step.digit - 1)
            for p in PEERS[step.cell]:
                self.cands[p] &= ~bit
        else:
            for cell, d in step.eliminated:
                self.cands[cell] &= ~(1 << (d - 1))
                self.elim_by[(cell, d)] = step.index

    @property
    def complete(self):
        return all(self.values)

    # ---- solving ----
    def _solve(self):
        finders = (self._naked_single, self._hidden_single, self._locked, self._naked_pair,
                   self._hidden_pair, self._x_wing)
        while True:
            if self.assume and self._find_contradiction():
                return
            for finder in finders:
                step = finder()
                if step:
                    self._apply(step)
                    break
            else:
                return

    def _find_contradiction(self):
        for i in range(81):
            if not self.values[i] and not self.cands[i]:
                facts = [self._fact(i, d) for d in range(1, 10)]
                self.contradiction = {"kind": "no_candidates", "cell": i, "facts": facts}
                return True
        for u, unit in enumerate(UNITS):
            for d in range(1, 10):
                if not self._placed_in(u, d) and not self._spots(u, d):
                    facts = self._unit_facts(unit, d)
                    self.contradiction = {"kind": "no_home", "unit": u, "digit": d, "facts": facts}
                    return True
        return False

    def _naked_single(self):
        for i in range(81):
            m = self.cands[i]
            if not self.values[i] and m and m & (m - 1) == 0:
                k = m.bit_length()
                facts = [self._fact(i, d) for d in range(1, 10) if d != k]
                return Step(len(self.steps), "naked_single", cell=i, digit=k, facts=facts)
        return None

    def _hidden_single(self):
        for u, unit in enumerate(UNITS):
            for d in range(1, 10):
                if self._placed_in(u, d):
                    continue
                spots = self._spots(u, d)
                if len(spots) == 1:
                    facts = self._unit_facts(unit, d, skip=(spots[0],))
                    return Step(len(self.steps), "hidden_single", cell=spots[0], digit=d, unit=u, facts=facts)
        return None

    def _locked(self):
        # pointing: a box's candidates for d all sit in one line
        for b in BOXES:
            for d in range(1, 10):
                if self._placed_in(b, d):
                    continue
                spots = self._spots(b, d)
                if len(spots) < 2:
                    continue
                for line_of in (lambda i: i // 9, lambda i: 9 + i % 9):
                    lines = {line_of(i) for i in spots}
                    if len(lines) != 1:
                        continue
                    line = lines.pop()
                    elim = [(j, d) for j in UNITS[line] if j not in UNITS[b] and self._has(j, d)]
                    if elim:
                        facts = self._unit_facts(UNITS[b], d, skip=spots)
                        return Step(len(self.steps), "pointing", unit=b, pattern=spots, digits=(d,),
                                    eliminated=elim, facts=facts, meta={"other": line})
        # claiming: a line's candidates for d all sit in one box
        for line in list(ROWS) + list(COLS):
            for d in range(1, 10):
                if self._placed_in(line, d):
                    continue
                spots = self._spots(line, d)
                if len(spots) < 2:
                    continue
                boxes = {(i // 27) * 3 + (i % 9) // 3 for i in spots}
                if len(boxes) != 1:
                    continue
                box = 18 + boxes.pop()
                elim = [(j, d) for j in UNITS[box] if j not in UNITS[line] and self._has(j, d)]
                if elim:
                    facts = self._unit_facts(UNITS[line], d, skip=spots)
                    return Step(len(self.steps), "claiming", unit=line, pattern=spots, digits=(d,),
                                eliminated=elim, facts=facts, meta={"other": box})
        return None

    def _mask_digits(self, i):
        return tuple(d for d in range(1, 10) if self.cands[i] & (1 << (d - 1)))

    def _naked_pair(self):
        for u, unit in enumerate(UNITS):
            pairs = [i for i in unit if not self.values[i] and bin(self.cands[i]).count("1") == 2]
            for a, b in combinations(pairs, 2):
                if self.cands[a] != self.cands[b]:
                    continue
                x, y = self._mask_digits(a)
                elim = [(j, d) for j in unit if j not in (a, b) for d in (x, y) if self._has(j, d)]
                if elim:
                    facts = [self._fact(c, d) for c in (a, b) for d in range(1, 10) if d not in (x, y)]
                    return Step(len(self.steps), "naked_pair", unit=u, pattern=[a, b], digits=(x, y),
                                eliminated=elim, facts=facts)
        return None

    def _hidden_pair(self):
        for u, unit in enumerate(UNITS):
            where = {d: self._spots(u, d) for d in range(1, 10) if not self._placed_in(u, d)}
            twos = [d for d, s in where.items() if len(s) == 2]
            for x, y in combinations(twos, 2):
                if where[x] != where[y]:
                    continue
                a, b = where[x]
                elim = [(c, d) for c in (a, b) for d in range(1, 10) if d not in (x, y) and self._has(c, d)]
                if elim:
                    facts = [f for d in (x, y) for f in self._unit_facts(unit, d, skip=(a, b))]
                    return Step(len(self.steps), "hidden_pair", unit=u, pattern=[a, b], digits=(x, y),
                                eliminated=elim, facts=facts)
        return None

    def _x_wing(self):
        for d in range(1, 10):
            for lines, cross in ((ROWS, lambda i: 9 + i % 9), (COLS, lambda i: i // 9)):
                twos = {}
                for u in lines:
                    if self._placed_in(u, d):
                        continue
                    spots = self._spots(u, d)
                    if len(spots) == 2:
                        twos[u] = spots
                for u1, u2 in combinations(sorted(twos), 2):
                    cross1 = sorted(cross(i) for i in twos[u1])
                    if cross1 != sorted(cross(i) for i in twos[u2]):
                        continue
                    corners = twos[u1] + twos[u2]
                    elim = [(j, d) for cu in cross1 for j in UNITS[cu] if j not in corners and self._has(j, d)]
                    if elim:
                        facts = [f for u in (u1, u2) for f in self._unit_facts(UNITS[u], d, skip=corners)]
                        return Step(len(self.steps), "x_wing", unit=u1, pattern=corners, digits=(d,),
                                    eliminated=elim, facts=facts, meta={"other": u2, "cross": cross1})
        return None

    # ---- explaining ----
    def _deps(self, facts):
        out = set()
        for _, _, (kind, ref) in facts:
            dep = ref if kind == "step" else self.placed_by[ref]
            if dep is not None:
                out.add(dep)
        return out

    def _closure(self, deps):
        """Indexes of every step needed to justify `deps`, directly or indirectly, in solve order."""
        seen, stack = set(), list(deps)
        while stack:
            s = stack.pop()
            if s in seen:
                continue
            seen.add(s)
            stack.extend(self._deps(self.steps[s].facts))
        return sorted(seen)

    def prerequisites(self, step_index):
        """Steps a placement relies on (excluding itself)."""
        return self._closure(self._deps(self.steps[step_index].facts))

    def _exclusions(self, cell, facts, number):
        groups = {"row": [], "column": [], "box": []}
        by_step = {}
        for j, d, (kind, ref) in facts:
            if j != cell:
                continue
            if kind == "peer":
                groups[_shared_kind(cell, ref)].append(d)
            else:
                by_step.setdefault(ref, []).append(d)
        parts = [f"its {kind} has {_join(sorted(ds))}" for kind, ds in groups.items() if ds]
        parts += [f"step {number[s]} ruled out {_join(sorted(ds))}" for s, ds in sorted(by_step.items())]
        return "; ".join(parts)

    def _blocked(self, facts, number):
        out = []
        for j, d, (kind, ref) in facts:
            if kind == "peer":
                k = _shared_kind(j, ref)
                out.append(f"{_pos(j)} already sees a {d} in its {k} (at {_where(k, ref)})")
            elif kind == "filled":
                out.append(f"{_pos(j)} has to be {self.values[j]} (step {number[self.placed_by[j]]})")
            else:
                out.append(f"{_pos(j)} was ruled out for {d} in step {number[ref]}")
        return "; ".join(out)

    def _removed(self, s):
        if len(s.digits) == 1:
            return _positions([c for c, _ in s.eliminated])
        by_cell = {}
        for c, d in s.eliminated:
            by_cell.setdefault(c, []).append(d)
        return "; ".join(f"{_pos(c)} loses {_join(sorted(ds))}" for c, ds in sorted(by_cell.items()))

    def _step_text(self, s, number):
        t = s.technique
        if t == "assumption":
            return f"Suppose {_pos(s.cell)} is {s.digit}."
        if t == "naked_single":
            return (f"{_cap(_pos(s.cell))} can only be {s.digit}. {_cap(self._exclusions(s.cell, s.facts, number))}. "
                    f"That rules out every other digit.")
        if t == "hidden_single":
            return (f"In {_unit_label(s.unit)}, the {s.digit} has only one place left: {_pos(s.cell)}. "
                    f"Every other cell there is blocked: {self._blocked(s.facts, number)}.")
        d = s.digits[0]
        if t == "pointing":
            line = _unit_label(s.meta["other"])
            return (f"In {_unit_label(s.unit)}, the {d} can only go in {line} (at {_positions(s.pattern)}), because every "
                    f"other cell in the box is blocked: {self._blocked(s.facts, number)}. So the box's {d} is in "
                    f"{line}, and no other cell in {line} can be {d}. That rules it out at {self._removed(s)}.")
        if t == "claiming":
            box = _unit_label(s.meta["other"])
            return (f"In {_unit_label(s.unit)}, the {d} can only go in {box} (at {_positions(s.pattern)}), because every "
                    f"other cell in the line is blocked: {self._blocked(s.facts, number)}. So that line's {d} is in "
                    f"{box}, and no other cell in {box} can be {d}. That rules it out at {self._removed(s)}.")
        if t == "naked_pair":
            a, b = s.pattern
            x, y = s.digits
            return (f"{_cap(_pos(a))} and {_pos(b)} can each only be {x} or {y}. "
                    f"{_cap(_pos(a))}: {self._exclusions(a, s.facts, number)}. "
                    f"{_cap(_pos(b))}: {self._exclusions(b, s.facts, number)}. "
                    f"Those two cells use up the {x} and the {y} between them, so no other cell in "
                    f"{_unit_label(s.unit)} can be {x} or {y}. That rules out: {self._removed(s)}.")
        if t == "hidden_pair":
            a, b = s.pattern
            x, y = s.digits
            return (f"In {_unit_label(s.unit)}, the {x} and the {y} can each only go in {_pos(a)} or {_pos(b)}, because "
                    f"every other cell there is blocked: {self._blocked(s.facts, number)}. So those two cells hold "
                    f"the {x} and the {y}, and nothing else can go in them. That rules out: {self._removed(s)}.")
        # x_wing
        u1, u2, cross = s.unit, s.meta["other"], s.meta["cross"]
        return (f"In {_unit_label(s.unit)} and {_unit_label(u2)}, the {d} can only go in {_unit_label(cross[0])} or "
                f"{_unit_label(cross[1])} (at {_positions(s.pattern)}), because every other cell in those two lines "
                f"is blocked: {self._blocked(s.facts, number)}. Whichever way it falls, "
                f"{_unit_label(cross[0])} and {_unit_label(cross[1])} each get their {d} from these two lines, so no other "
                f"cell in them can be {d}. That rules it out at {self._removed(s)}.")

    def _highlights(self, s):
        cells = []
        for j, _, (kind, ref) in s.facts:
            cells.append(ref if kind == "peer" else j)
        return _cells(cells)

    def _payload(self, s, number, n):
        targets = [s.cell] if s.is_placement else list(s.pattern)
        return {
            "number": n,
            "row": targets[0] // 9,
            "col": targets[0] % 9,
            "digit": s.digit,
            "technique": s.technique,
            "text": self._step_text(s, number),
            "highlights": self._highlights(s),
            "targets": _cells(targets),
            "eliminated": [{"row": c // 9, "col": c % 9, "digit": d} for c, d in s.eliminated],
        }

    def _chain(self, deps):
        steps = self._closure(deps)
        number = {s: n + 1 for n, s in enumerate(steps)}
        return steps, number

    def _payloads(self, steps, number):
        return [self._payload(self.steps[s], number, number[s]) for s in steps]

    def explain(self, cell, entered, correct):
        """Why `entered` is wrong at `cell` and `correct` is right, or None if the techniques can't reach it.

        Returns {explanation, technique, highlights, steps}. `steps` are the earlier deductions the
        argument relies on, in order, each with its own text and the cells that prove it.
        """
        si = self.step_of_cell.get(cell)
        if si is None:
            return None
        target = self.steps[si]
        if target.digit != correct:  # cannot happen for a puzzle with a unique solution
            return None
        steps, number = self._chain(self._deps(target.facts))

        text = f"Your {entered} is wrong. {self._step_text(target, number)}"
        if target.technique == "naked_single":
            _, _, (kind, ref) = next(f for f in target.facts if f[1] == entered)
            if kind == "peer":
                dep = self.placed_by[ref]
                where = " (a given clue)" if dep is None else f" (step {number[dep]} below)"
                text += f" Your {entered} is ruled out because the {entered} has to go at {_pos(ref)}{where}."
            else:
                text += f" Your {entered} is ruled out in step {number[ref]} below."
        else:
            text += f" So this cell has to be {correct}, not {entered}."
        return {
            "explanation": text,
            "technique": target.technique,
            "highlights": self._highlights(target),
            "steps": self._payloads(steps, number),
        }

    def explain_contradiction(self):
        """For an Explainer built with `assume`: the argument that the assumption is impossible."""
        c = self.contradiction
        if not c:
            return None
        a = self.steps[0]
        steps, number = self._chain(self._deps(c["facts"]))
        if c["kind"] == "no_candidates":
            tail = (f"{_cap(_pos(c['cell']))} would have no digit left: "
                    f"{self._exclusions(c['cell'], c['facts'], number)}.")
        else:
            tail = (f"In {_unit_label(c['unit'])}, the {c['digit']} would have nowhere to go: "
                    f"{self._blocked(c['facts'], number)}.")
        text = (f"Your {a.digit} is wrong. Suppose {_pos(a.cell)} is {a.digit}. That leads to a contradiction. "
                f"{tail} So {a.digit} can't go there.")
        highlights = [ref if kind == "peer" else j for j, _, (kind, ref) in c["facts"]]
        return {
            "explanation": text,
            "technique": "contradiction",
            "highlights": _cells(highlights),
            "steps": self._payloads(steps, number),
        }

    def best_hint(self):
        """The most direct next placement from this position: the one needing the fewest earlier steps."""
        best = None
        for cell, si in self.step_of_cell.items():
            steps, number = self._chain(self._deps(self.steps[si].facts))
            key = (len(steps), si)
            if best is None or key < best[0]:
                best = (key, si, steps, number)
        if best is None:
            return None
        _, si, steps, number = best
        s = self.steps[si]
        if s.technique == "naked_single":
            nudge = f"Look at {_pos(s.cell)}. Which digit is left once everything in its row, column and box is crossed out?"
            nudge_cells = [s.cell]
        else:
            nudge = f"Look at {_unit_label(s.unit)}. One digit has only one cell left where it can go."
            nudge_cells = list(UNITS[s.unit])
        return {
            "row": s.cell // 9,
            "col": s.cell % 9,
            "correct_digit": s.digit,
            "technique": s.technique,
            "nudge": nudge,
            "nudge_cells": _cells(nudge_cells),
            "explanation": self._step_text(s, number),
            "highlights": self._highlights(s),
            "targets": _cells([s.cell]),
            "steps": self._payloads(steps, number),
        }
