"""The explainer must never say anything false. These tests re-check every claim independently."""
import random
import re

import pytest

from explain import Explainer
from solver import PEERS, UNITS, find_solutions, solve
from test_checker import PUZZLE, SOLUTION, parse

HARD = parse("4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......")


def scrambled_puzzles(count=6, clues=30, seed=7):
    """Valid unique puzzles: shuffle the sample solution (digits, rows within bands, bands), then dig holes."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        perm = list(range(1, 10))
        rng.shuffle(perm)
        rows = [b * 3 + r for b in rng.sample(range(3), 3) for r in rng.sample(range(3), 3)]
        full = [[perm[SOLUTION[r][c] - 1] for c in range(9)] for r in rows]
        puzzle = [row[:] for row in full]
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


PUZZLES = [PUZZLE, HARD] + scrambled_puzzles()


def replay_and_verify(givens):
    """Replay the recorded solve from the clues, checking every step's evidence from scratch."""
    ex = Explainer(givens)
    solution = solve(givens)
    values = [givens[i // 9][i % 9] for i in range(81)]
    filled_at = {i: None for i in range(81) if values[i]}  # cell -> step index (None = given)
    for s in ex.steps:
        assert s.digit == solution[s.cell // 9][s.cell % 9], "a step deduced a digit that is not in the solution"
        assert values[s.cell] == 0
        for p in s.evidence.values():
            assert p in filled_at, "evidence cell was not filled yet"
            assert filled_at[p] is None or filled_at[p] < s.index, "evidence comes from a later step"
        if s.technique == "naked_single":
            assert set(s.evidence) == set(range(1, 10)) - {s.digit}
            for d, p in s.evidence.items():
                assert p in PEERS[s.cell] and values[p] == d
        else:
            unit = UNITS[s.unit]
            assert s.cell in unit and s.digit not in {values[i] for i in unit}
            assert set(s.evidence) == {j for j in unit if j != s.cell and not values[j]}
            for j, p in s.evidence.items():
                assert p in PEERS[j] and values[p] == s.digit, "blocker does not really block"
        values[s.cell] = s.digit
        filled_at[s.cell] = s.index
    return ex


@pytest.mark.parametrize("givens", PUZZLES)
def test_every_recorded_step_is_valid(givens):
    ex = replay_and_verify(givens)
    assert ex.steps or givens is HARD


def test_classic_puzzle_is_solved_by_singles_alone():
    assert replay_and_verify(PUZZLE).complete


def test_hard_puzzle_is_only_partly_reachable_and_that_is_reported_not_guessed():
    ex = replay_and_verify(HARD)
    assert not ex.complete
    unreached = next(i for i in range(81) if not ex.values[i])
    assert ex.explain(unreached, 1, solve(HARD)[unreached // 9][unreached % 9]) is None


@pytest.mark.parametrize("givens", PUZZLES)
def test_explanations_are_self_contained_and_references_resolve(givens):
    ex = Explainer(givens)
    solution = solve(givens)
    explained = 0
    for cell, si in ex.step_of_cell.items():
        r, c = divmod(cell, 9)
        wrong = solution[r][c] % 9 + 1
        res = ex.explain(cell, wrong, solution[r][c])
        explained += 1
        steps = res["steps"]
        assert [s["number"] for s in steps] == list(range(1, len(steps) + 1))
        # every deduced cell the target relies on is explained by one of the listed steps
        listed = {(s["row"] * 9 + s["col"]) for s in steps}
        needed = {p for p in ex.steps[si].evidence.values() if ex.placed_by[p] is not None}
        assert needed <= listed
        for s in steps:  # ...and so on all the way down: the list never leans on something unexplained
            inner = {p for p in ex.steps[ex.step_of_cell[s["row"] * 9 + s["col"]]].evidence.values()
                     if ex.placed_by[p] is not None}
            assert inner <= listed
        # "(step N below)" really points at the cell the sentence names
        for n in re.findall(r"\(step (\d+) below\)", res["explanation"]):
            s = steps[int(n) - 1]
            assert f"go at row {s['row'] + 1}, column {s['col'] + 1}" in res["explanation"]
            assert s["digit"] == wrong
        assert str(solution[r][c]) in res["explanation"]
        assert res["highlights"]
    assert explained == len(ex.steps)


@pytest.mark.parametrize("givens", PUZZLES)
def test_evidence_prefers_given_clues_so_explanations_stay_short(givens):
    """If a given clue could prove a fact, the explanation must cite it instead of an earlier deduction."""
    ex = Explainer(givens)
    for s in ex.steps:
        for key, p in s.evidence.items():
            holder_of = s.digit if s.technique == "hidden_single" else key
            target = s.cell if s.technique == "naked_single" else key
            if any(ex.given[q] and ex.values[q] == holder_of for q in PEERS[target]):
                assert ex.given[p]
