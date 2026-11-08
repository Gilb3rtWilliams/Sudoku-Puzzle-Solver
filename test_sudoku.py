import cv2
import numpy as np

from solver import solve, count_solutions, is_valid_grid
from grid_detection import extract_cells

PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0], [6, 0, 0, 1, 9, 5, 0, 0, 0], [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3], [4, 0, 0, 8, 0, 3, 0, 0, 1], [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0], [0, 0, 0, 4, 1, 9, 0, 0, 5], [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


def test_solves_and_result_is_valid():
    sol = solve(PUZZLE)
    assert sol is not None
    assert all(all(v for v in row) for row in sol)
    assert is_valid_grid(sol)
    # givens preserved
    for r in range(9):
        for c in range(9):
            if PUZZLE[r][c]:
                assert sol[r][c] == PUZZLE[r][c]


def test_unique_puzzle_counts_one():
    assert count_solutions(PUZZLE) == 1


def test_empty_grid_is_ambiguous():
    assert count_solutions([[0] * 9 for _ in range(9)]) == 2


def test_conflicting_givens_unsolvable():
    bad = [row[:] for row in PUZZLE]
    bad[0][2] = 5  # duplicates the 5 at row 0, col 0
    assert solve(bad) is None


def make_photo(puzzle):
    """Draw a sudoku, then perspective-warp it onto a bigger background."""
    s = 540
    img = np.full((s, s), 255, np.uint8)
    for i in range(10):
        t = 4 if i % 3 == 0 else 1
        cv2.line(img, (i * 60, 0), (i * 60, s), 0, t)
        cv2.line(img, (0, i * 60), (s, i * 60), 0, t)
    for r in range(9):
        for c in range(9):
            if puzzle[r][c]:
                cv2.putText(img, str(puzzle[r][c]), (c * 60 + 17, r * 60 + 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3)
    src = np.float32([[0, 0], [s, 0], [s, s], [0, s]])
    dst = np.float32([[120, 90], [700, 140], [660, 720], [80, 650]])
    M = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(img, M, (800, 800), borderValue=200)
    return cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)


def test_grid_detection_finds_blank_cells():
    result = extract_cells(make_photo(PUZZLE))
    assert result is not None
    _, _, empty, _ = result
    for r in range(9):
        for c in range(9):
            assert empty[r][c] == (PUZZLE[r][c] == 0), (r, c)
