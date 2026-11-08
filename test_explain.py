"""The explainer must never say anything false. These tests re-check every claim independently.

`verify` replays a recorded solve with its own candidate bookkeeping (it trusts nothing the engine
stored except the steps themselves) and checks, for every step:
  - every fact "cell j can't be d" is true at that moment, and its stated reason is real;
  - the facts cover everything the explanation claims (e.g. *every* other cell in the unit);
  - the conclusion has the right shape for its technique;
  - the conclusion agrees with the puzzle's true solution.
"""
import random
import re
from collections import Counter

import pytest

from explain import ADVANCED, Explainer
from solver import PEERS, UNITS, find_solutions, solve
from test_checker import PUZZLE, SOLUTION, parse

HARD = parse("4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......")
INKALA = parse("8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..")
STALLED = [parse(p) for p in [
    "5...........8.4.5....69.2.149.....1.6.87.........8...4...1..7...62.....581..6.9..",
    ".85..........12.3.9.....48......5....98.2..4...79..5...29.3...81..6..7.3.........",
    "8..2......2...3...9......17..68..17...1.....4...9..56..3..8....65..91..8.7....4..",
]]
# Small puzzles that each need one of the advanced techniques.
BY_TECHNIQUE = {
    "naked_pair": "...5.8.9...9.4....8..1...7.6..3.17...8..62..95......469.........1...7.63.23......",
    "x_wing": ".......42.143.5........813...2.19.67.73.5..........9..45.........1..3.5...8.9.4..",
    "hidden_pair": "8.37...5....6.21.....35...9.54......31..29.....9.....25.1...4..43..1....6.823....",
}
EXTRA = [parse(p) for p in BY_TECHNIQUE.values()] + [parse("1.....569492.561.8.561.924...964.8.1.64.1....218.356.4.4.5...169.5.614.2621.....5")]


def scrambled_puzzles(count=5, clues=30, seed=7):
    """Valid unique puzzles: shuffle the sample solution's digits and rows, then dig holes."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        perm = list(range(1, 10))
        rng.shuffle(perm)
        rows = [b * 3 + r for b in rng.sample(range(3), 3) for r in rng.sample(range(3), 3)]
        puzzle = [[perm[SOLUTION[r][c] - 1] for c in range(9)] for r in rows]
        cells = [(r, c) for r in range(9) for c in range(9)]
        rng.shuffle(cells)
        left = 81
        for r, c in cells:
            if left <= clues:
                break
            keep, puzzle[r][c] = puzzle[r][c], 0
            if len(find_solutions(puzzle, limit=2)) == 1:
                left -= 1
            else:
                puzzle[r][c] = keep
        out.append(puzzle)
    return out


PUZZLES = [PUZZLE, HARD, INKALA] + STALLED + EXTRA + scrambled_puzzles() + scrambled_puzzles(3, 24, seed=3)


# ---------------------------------------------------------------- the independent verifier
class Verifier:
    def __init__(self, givens):
        self.values = [givens[i // 9][i % 9] for i in range(81)]
        self.filled_at = {i: None for i in range(81) if self.values[i]}
        self.elim = set()          # (cell, digit) removed by elimination steps so far

    def cand(self, i):
        if self.values[i]:
            return set()
        held = {self.values[p] for p in PEERS[i]}
        return {d for d in range(1, 10) if d not in held and (i, d) not in self.elim}

    def needs_fact(self, j):
        """A cell an argument about 'every other cell' must account for: empty, or filled by a deduction."""
        return not self.values[j] or self.filled_at[j] is not None

    def spots(self, u, d):
        return [i for i in UNITS[u] if d in self.cand(i)]

    def placed_in(self, u, d):
        return any(self.values[i] == d for i in UNITS[u])


def check_fact(v, ex, step, fact):
    j, d, (kind, ref) = fact
    if kind == "filled":
        assert ref == j and v.values[j] and v.values[j] != d, "a 'filled' fact about a cell that is not filled"
        assert v.filled_at[j] is not None and v.filled_at[j] < step.index, "cited fill must be an earlier deduction"
        return
    assert not v.values[j], "a fact is about a filled cell"
    assert d not in v.cand(j), f"fact says cell {j} can't be {d}, but it can"
    if kind == "peer":
        assert ref in PEERS[j] and v.values[ref] == d, "the cited peer does not hold that digit"
        assert v.filled_at[ref] is None or v.filled_at[ref] < step.index
    else:
        assert ref < step.index and (j, d) in ex.steps[ref].eliminated, "the cited step did not remove that"


def fact_set(step):
    return {(j, d) for j, d, _ in step.facts}


def verify(ex, givens, solution=None):
    """Replay `ex` from scratch. `solution` is None for hypothetical (assumption) runs."""
    v = Verifier(givens)
    for s in ex.steps:
        for fact in s.facts:
            check_fact(v, ex, s, fact)
        t = s.technique
        if t == "assumption":
            assert v.values[s.cell] == 0 and s.digit in v.cand(s.cell)
        elif t == "naked_single":
            assert v.cand(s.cell) == {s.digit}
            assert fact_set(s) == {(s.cell, d) for d in range(1, 10) if d != s.digit}
        elif t == "hidden_single":
            assert not v.placed_in(s.unit, s.digit) and v.spots(s.unit, s.digit) == [s.cell]
            assert fact_set(s) == {(j, s.digit) for j in UNITS[s.unit] if j != s.cell and v.needs_fact(j)}
        elif t in ("pointing", "claiming"):
            d = s.digits[0]
            assert not v.placed_in(s.unit, d)
            spots = v.spots(s.unit, d)
            assert sorted(spots) == sorted(s.pattern) and len(spots) >= 2
            other = UNITS[s.meta["other"]]
            assert all(c in other for c in spots), "pattern is not inside the other unit"
            for c, e in s.eliminated:
                assert e == d and c in other and c not in UNITS[s.unit] and d in v.cand(c)
            assert fact_set(s) == {(j, d) for j in UNITS[s.unit] if v.needs_fact(j) and j not in spots}
        elif t == "naked_pair":
            a, b = s.pattern
            assert v.cand(a) == v.cand(b) == set(s.digits) and len(s.digits) == 2
            assert a in UNITS[s.unit] and b in UNITS[s.unit]
            for c, e in s.eliminated:
                assert c in UNITS[s.unit] and c not in (a, b) and e in s.digits and e in v.cand(c)
            assert fact_set(s) == {(c, d) for c in (a, b) for d in range(1, 10) if d not in s.digits}
        elif t == "hidden_pair":
            a, b = s.pattern
            x, y = s.digits
            assert sorted(v.spots(s.unit, x)) == sorted(v.spots(s.unit, y)) == sorted([a, b])
            for c, e in s.eliminated:
                assert c in (a, b) and e not in s.digits and e in v.cand(c)
            assert fact_set(s) == {(j, d) for j in UNITS[s.unit] if j not in (a, b) and v.needs_fact(j) for d in (x, y)}
        elif t == "x_wing":
            d = s.digits[0]
            u1, u2, cross = s.unit, s.meta["other"], s.meta["cross"]
            assert sorted(v.spots(u1, d) + v.spots(u2, d)) == sorted(s.pattern) and len(s.pattern) == 4
            assert all(any(c in UNITS[x] for x in cross) for c in s.pattern)
            for c, e in s.eliminated:
                assert e == d and any(c in UNITS[x] for x in cross) and c not in s.pattern and d in v.cand(c)
            assert fact_set(s) == {(j, d) for u in (u1, u2) for j in UNITS[u]
                                   if v.needs_fact(j) and j not in s.pattern}
        else:
            raise AssertionError(f"unknown technique {t}")

        if solution is not None:  # the conclusions must be true of the real solution
            if s.is_placement:
                assert s.digit == solution[s.cell // 9][s.cell % 9]
            for c, e in s.eliminated:
                assert solution[c // 9][c % 9] != e, "eliminated the digit the solution needs"

        if s.is_placement:
            v.values[s.cell] = s.digit
            v.filled_at[s.cell] = s.index
        else:
            assert s.eliminated, "an elimination step that eliminates nothing"
            v.elim.update(s.eliminated)

    c = ex.contradiction
    if c:  # a claimed contradiction must really be one
        for fact in c["facts"]:
            check_fact(v, ex, type("End", (), {"index": len(ex.steps)})(), fact)
        if c["kind"] == "no_candidates":
            assert not v.values[c["cell"]] and not v.cand(c["cell"])
        else:
            assert not v.placed_in(c["unit"], c["digit"]) and not v.spots(c["unit"], c["digit"])
            assert {f[0] for f in c["facts"]} == {j for j in UNITS[c["unit"]] if v.needs_fact(j)}


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("givens", PUZZLES)
def test_every_recorded_step_is_valid_and_true(givens):
    verify(Explainer(givens), givens, solve(givens))


def test_all_advanced_techniques_are_exercised():
    seen = Counter(s.technique for g in PUZZLES for s in Explainer(g).steps)
    assert set(ADVANCED) <= set(seen), f"never exercised: {set(ADVANCED) - set(seen)}"


@pytest.mark.parametrize("technique", list(BY_TECHNIQUE))
def test_the_named_puzzles_really_use_their_technique(technique):
    assert any(s.technique == technique for s in Explainer(parse(BY_TECHNIQUE[technique])).steps)


def test_advanced_techniques_solve_what_singles_cannot():
    assert Explainer(HARD).complete  # needs pointing pairs
    assert not Explainer(INKALA).complete  # beyond every technique here; reported, not guessed


def mapping(ex, cell):
    target = ex.steps[ex.step_of_cell[cell]]
    return target, *ex._chain(ex._deps(target.facts))


@pytest.mark.parametrize("givens", PUZZLES)
def test_explanations_are_self_contained_and_references_resolve(givens):
    ex = Explainer(givens)
    solution = solve(givens)
    for cell in ex.step_of_cell:
        r, c = divmod(cell, 9)
        wrong = solution[r][c] % 9 + 1
        res = ex.explain(cell, wrong, solution[r][c])
        target, idx, number = mapping(ex, cell)
        steps = res["steps"]
        assert [s["number"] for s in steps] == list(range(1, len(steps) + 1))
        assert set(idx) == {s for s in idx} and len(idx) == len(steps)
        for s in idx:  # closed under dependencies: nothing leans on an unlisted step
            assert ex._deps(ex.steps[s].facts) <= set(idx)
        # a step may only refer back to earlier-numbered steps
        for st in steps:
            assert all(int(n) < st["number"] for n in re.findall(r"step (\d+)", st["text"]))
        # references in the headline point at what the sentence says they do
        for n in re.findall(r"\(step (\d+) below\)", res["explanation"]):
            ref = ex.steps[idx[int(n) - 1]]
            assert ref.is_placement and ref.digit == wrong
            assert f"go at {_pos(ref.cell)}" in res["explanation"]
        for n in re.findall(r"ruled out in step (\d+) below", res["explanation"]):
            assert (cell, wrong) in ex.steps[idx[int(n) - 1]].eliminated
        assert str(solution[r][c]) in res["explanation"] and res["highlights"]


def _pos(i):
    return f"row {i // 9 + 1}, column {i % 9 + 1}"


def test_evidence_prefers_given_clues_so_explanations_stay_short():
    """If a given clue could prove a fact, the explanation cites it rather than a deduction."""
    for givens in PUZZLES:
        ex = Explainer(givens)
        for s in ex.steps:
            for j, d, (kind, ref) in s.facts:
                if kind != "filled" and any(ex.given[p] and ex.values[p] == d for p in PEERS[j]):
                    assert kind == "peer" and ex.given[ref]


# ---------------------------------------------------------------- contradictions
def wrong_digits(givens, cell, solution):
    r, c = divmod(cell, 9)
    held = {givens[p // 9][p % 9] for p in PEERS[cell]}
    return [d for d in range(1, 10) if d != solution[r][c] and d not in held]


@pytest.mark.parametrize("givens", STALLED + [INKALA, HARD])
def test_contradictions_are_real_and_only_claimed_for_wrong_digits(givens):
    solution = solve(givens)
    proven = 0
    for cell in range(81):
        if givens[cell // 9][cell % 9]:
            continue
        for d in wrong_digits(givens, cell, solution):
            ex = Explainer(givens, assume=(cell, d))
            verify(ex, givens)  # every step valid under the assumption, and the contradiction is genuine
            res = ex.explain_contradiction()
            if res:
                proven += 1
                assert f"Suppose {_pos(cell)} is {d}" in res["explanation"]
                assert res["steps"][0]["technique"] == "assumption"
    assert proven > 0 or givens is INKALA


def test_a_correct_digit_never_yields_a_contradiction():
    """Soundness the other way round: supposing the *true* digit must never 'prove' anything."""
    for givens in STALLED + [HARD]:
        solution = solve(givens)
        for cell in range(0, 81, 3):
            if not givens[cell // 9][cell % 9]:
                ex = Explainer(givens, assume=(cell, solution[cell // 9][cell % 9]))
                assert ex.contradiction is None
