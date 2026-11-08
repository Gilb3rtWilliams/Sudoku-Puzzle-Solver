import random

import pytest

from checker import check_answers
from solver import PEERS, solve

PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0], [6, 0, 0, 1, 9, 5, 0, 0, 0], [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3], [4, 0, 0, 8, 0, 3, 0, 0, 1], [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0], [0, 0, 0, 4, 1, 9, 0, 0, 5], [0, 0, 0, 0, 8, 0, 0, 7, 9],
]
SOLUTION = solve(PUZZLE)


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


def test_mismatch_without_any_visible_clash():
    # Find a wrong digit that repeats nothing in the cell's row, column or box.
    r, c = 0, 2
    peer_digits = {PUZZLE[p // 9][p % 9] for p in PEERS[r * 9 + c]}
    digit = next(d for d in range(1, 10) if d != SOLUTION[r][c] and d not in peer_digits)
    m = mistake_at(check_answers(PUZZLE, with_answers(r0c2=digit)), r, c)
    assert m["kind"] == "mismatch" and m["clashes"] == []
    assert "only solution" in m["explanation"]


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
