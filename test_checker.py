import random

import pytest

from checker import check_answers, hint
from solver import PEERS, solve

PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0], [6, 0, 0, 1, 9, 5, 0, 0, 0], [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3], [4, 0, 0, 8, 0, 3, 0, 0, 1], [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0], [0, 0, 0, 4, 1, 9, 0, 0, 5], [0, 0, 0, 0, 8, 0, 0, 7, 9],
]
SOLUTION = solve(PUZZLE)


def parse(line):
    """An 81-character puzzle string ('.' or '0' = blank) as a grid."""
    digits = [0 if ch in ".0" else int(ch) for ch in line]
    return [digits[r * 9:(r + 1) * 9] for r in range(9)]


def with_answers(**cells):
    """PUZZLE plus answers given as r{row}c{col}=digit (0-indexed)."""
    grid = [row[:] for row in PUZZLE]
    for key, digit in cells.items():
        r, c = int(key[1]), int(key[3])
        grid[r][c] = digit
    return grid


def mistake_at(result, r, c):
    return next(m for m in result["mistakes"] if (m["row"], m["col"]) == (r, c))


def test_no_answers_yet():
    res = check_answers(PUZZLE, PUZZLE)
    assert res["status"] == "ok"
    assert (res["entered"], res["wrong"], res["solved"]) == (0, 0, False)
    assert "Fill in some cells" in res["message"]


def test_correct_answers_so_far():
    res = check_answers(PUZZLE, with_answers(r0c2=4, r0c3=6))
    assert (res["entered"], res["correct"], res["wrong"]) == (2, 2, 0)
    assert res["blank"] == sum(v == 0 for row in PUZZLE for v in row) - 2
    assert not res["solved"]
    assert "right" in res["message"]


def test_full_solution_is_solved():
    res = check_answers(PUZZLE, SOLUTION)
    assert res["solved"] and res["wrong"] == 0 and res["blank"] == 0
    assert "solved" in res["message"].lower()


def test_clash_with_a_given_clue():
    res = check_answers(PUZZLE, with_answers(r0c2=5))  # row 1 already has a given 5
    m = mistake_at(res, 0, 2)
    assert m["kind"] == "clash"
    assert m["correct_digit"] == 4 and m["entered"] == 5
    assert "row 1" in m["explanation"] and "given clue" in m["explanation"]
    assert m["clashes"][0]["given"] is True


def test_wrong_digit_without_a_clash_gets_a_logical_explanation():
    # Find a wrong digit that repeats nothing in the cell's row, column or box.
    r, c = 0, 2
    peer_digits = {PUZZLE[p // 9][p % 9] for p in PEERS[r * 9 + c]}
    digit = next(d for d in range(1, 10) if d != SOLUTION[r][c] and d not in peer_digits)
    m = mistake_at(check_answers(PUZZLE, with_answers(r0c2=digit)), r, c)
    assert m["kind"] == "logic" and m["clashes"] == []
    assert m["technique"] in ("naked_single", "hidden_single")
    assert f"Your {digit} is wrong" in m["explanation"]
    assert m["highlights"]
    assert m["correct_digit"] == SOLUTION[r][c]


def all_wrong(puzzle):
    """The puzzle with a wrong digit in every blank cell, and its solution."""
    sol = solve(puzzle)
    grid = [row[:] for row in puzzle]
    for r in range(9):
        for c in range(9):
            if not puzzle[r][c]:
                grid[r][c] = sol[r][c] % 9 + 1
    return grid


STALLED = parse("5...........8.4.5....69.2.149.....1.6.87.........8...4...1..7...62.....581..6.9..")
INKALA = parse("8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..")


def test_advanced_techniques_explain_a_puzzle_singles_cannot_solve():
    hard = parse("4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......")
    kinds = {m["kind"] for m in check_answers(hard, all_wrong(hard))["mistakes"]}
    assert "mismatch" not in kinds and "logic" in kinds


def test_beyond_the_chain_a_contradiction_is_shown():
    mistakes = check_answers(STALLED, all_wrong(STALLED))["mistakes"]
    contradictions = [m for m in mistakes if m["kind"] == "contradiction"]
    assert contradictions
    m = contradictions[0]
    assert m["technique"] == "contradiction" and m["steps"][0]["technique"] == "assumption"
    assert f"Suppose row {m['row'] + 1}, column {m['col'] + 1} is {m['entered']}" in m["explanation"]
    assert m["highlights"] and m["correct_digit"] == solve(STALLED)[m["row"]][m["col"]]


def test_when_nothing_can_be_argued_the_message_is_honest():
    mistakes = check_answers(INKALA, all_wrong(INKALA))["mistakes"]
    fallback = [m for m in mistakes if m["kind"] == "mismatch"]
    assert fallback  # an extreme puzzle: some wrong digits can't be argued with these techniques
    for m in fallback:
        assert "deeper argument" in m["explanation"] and m["steps"] == []
        assert m["correct_digit"] == solve(INKALA)[m["row"]][m["col"]]


def test_two_wrong_answers_clashing_with_each_other():
    res = check_answers(PUZZLE, with_answers(r0c2=2, r0c3=2))
    assert res["wrong"] == 2
    for cell in [(0, 2), (0, 3)]:
        m = mistake_at(res, *cell)
        assert m["kind"] == "clash"
        assert "twice" in m["explanation"] and "Neither" in m["explanation"]


def test_clash_with_a_correct_answer_blames_only_the_wrong_one():
    res = check_answers(PUZZLE, with_answers(r0c2=4, r0c5=4))
    assert res["wrong"] == 1
    m = mistake_at(res, 0, 5)
    assert "correct" in m["explanation"] and m["correct_digit"] == 8


def test_changing_a_given_is_rejected():
    with pytest.raises(ValueError):
        check_answers(PUZZLE, with_answers(r0c0=9))


def test_not_unique_and_unsolvable_puzzles_are_not_graded():
    empty = [[0] * 9 for _ in range(9)]
    assert check_answers(empty, empty)["status"] == "not_unique"
    bad = [row[:] for row in PUZZLE]
    bad[0][2] = 5  # duplicates the 5 at row 0, col 0
    assert check_answers(bad, bad)["status"] == "unsolvable"


def test_random_answers_are_graded_exactly():
    """Whatever the player enters, every wrong cell is reported once with the true digit."""
    rng = random.Random(1)
    blanks = [(r, c) for r in range(9) for c in range(9) if not PUZZLE[r][c]]
    for _ in range(200):
        grid = [row[:] for row in PUZZLE]
        for r, c in rng.sample(blanks, rng.randint(1, len(blanks))):
            grid[r][c] = rng.randint(1, 9)
        res = check_answers(PUZZLE, grid)
        expected = {(r, c) for r, c in blanks if grid[r][c] and grid[r][c] != SOLUTION[r][c]}
        got = [(m["row"], m["col"]) for m in res["mistakes"]]
        assert set(got) == expected and len(got) == len(expected)
        for m in res["mistakes"]:
            assert m["correct_digit"] == SOLUTION[m["row"]][m["col"]] != m["entered"]
            # a clash must be real: the clashing cell holds the same digit
            for cl in m["clashes"]:
                assert grid[cl["row"]][cl["col"]] == m["entered"]
            assert (m["kind"] == "clash") == bool(m["clashes"])
        assert res["entered"] == res["correct"] + res["wrong"]


# ---------- hints ----------
def test_hint_points_at_a_blank_cell_with_the_true_digit_and_tiers():
    h = hint(PUZZLE, PUZZLE)
    assert h["status"] == "ok" and h["wrong_entries"] == 0
    assert PUZZLE[h["row"]][h["col"]] == 0 and h["correct_digit"] == SOLUTION[h["row"]][h["col"]]
    assert h["nudge"].startswith("Look at")
    assert h["nudge_cells"], "the nudge must say where to look"
    assert h["explanation"] and h["technique"] in ("naked_single", "hidden_single")
    assert {"row": h["row"], "col": h["col"]} in h["targets"]


def test_hint_builds_on_correct_answers_and_ignores_wrong_ones():
    grid = with_answers(r0c2=4, r0c3=6, r0c5=9)   # two right, one wrong
    h = hint(PUZZLE, grid)
    assert h["wrong_entries"] == 1
    assert (h["row"], h["col"]) not in [(0, 2), (0, 3)]          # never re-suggests what is already right
    assert h["correct_digit"] == SOLUTION[h["row"]][h["col"]]


def test_hint_on_a_finished_or_invalid_board():
    assert hint(PUZZLE, SOLUTION)["status"] == "complete"
    with pytest.raises(ValueError):
        hint(PUZZLE, with_answers(r0c0=9))
    empty = [[0] * 9 for _ in range(9)]
    assert hint(empty, empty)["status"] == "not_unique"


def test_hint_is_honest_when_no_step_exists():
    h = hint(INKALA, INKALA)
    assert h["status"] == "ok" and h["technique"] is None and h["steps"] == []
    assert h["correct_digit"] == solve(INKALA)[h["row"]][h["col"]]
    assert "deeper argument" in h["explanation"]


def test_random_boards_always_get_a_true_hint():
    rng = random.Random(4)
    blanks = [(r, c) for r in range(9) for c in range(9) if not PUZZLE[r][c]]
    for _ in range(60):
        grid = [row[:] for row in PUZZLE]
        for r, c in rng.sample(blanks, rng.randint(0, len(blanks) - 1)):
            grid[r][c] = SOLUTION[r][c] if rng.random() < 0.8 else rng.randint(1, 9)
        h = hint(PUZZLE, grid)
        if h["status"] == "complete":
            continue
        assert h["correct_digit"] == SOLUTION[h["row"]][h["col"]]
        assert grid[h["row"]][h["col"]] != SOLUTION[h["row"]][h["col"]]   # it is a cell still to get right
        assert [s["number"] for s in h["steps"]] == list(range(1, len(h["steps"]) + 1))
