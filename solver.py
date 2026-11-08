"""Sudoku solver: bitmask constraint propagation + minimum-remaining-values backtracking.

A grid is a list of 9 lists of 9 ints, with 0 meaning empty.
"""
from copy import deepcopy

ALL = 0b111111111  # bits 0-8 stand for digits 1-9

# Precompute the 20 peers (same row, column or box) of each of the 81 cells
PEERS = []
for _r in range(9):
    for _c in range(9):
        _p = set()
        for k in range(9):
            _p.add(_r * 9 + k)
            _p.add(k * 9 + _c)
        br, bc = 3 * (_r // 3), 3 * (_c // 3)
        for dr in range(3):
            for dc in range(3):
                _p.add((br + dr) * 9 + bc + dc)
        _p.discard(_r * 9 + _c)
        PEERS.append(sorted(_p))

UNITS = (
    [[r * 9 + c for c in range(9)] for r in range(9)]
    + [[r * 9 + c for r in range(9)] for c in range(9)]
    + [[(br + dr) * 9 + bc + dc for dr in range(3) for dc in range(3)]
       for br in (0, 3, 6) for bc in (0, 3, 6)]
)


def is_valid_grid(grid):
    """True if no digit repeats in any row, column or box (blanks ignored)."""
    for unit in UNITS:
        seen = set()
        for idx in unit:
            v = grid[idx // 9][idx % 9]
            if v:
                if v in seen:
                    return False
                seen.add(v)
    return True


def _assign(cands, idx, digit):
    """Set cell idx to digit and propagate. Returns False on contradiction."""
    bit = 1 << (digit - 1)
    cands[idx] = bit
    for p in PEERS[idx]:
        if cands[p] & bit:
            cands[p] &= ~bit
            if cands[p] == 0:
                return False
            if cands[p] & (cands[p] - 1) == 0:  # one candidate left
                if not _assign(cands, p, cands[p].bit_length()):
                    return False
    # Hidden singles: a digit with only one possible home in a unit
    for unit in UNITS:
        if idx not in unit:
            continue
        for d in range(9):
            b = 1 << d
            spots = [i for i in unit if cands[i] & b]
            if not spots:
                return False
            if len(spots) == 1 and cands[spots[0]] != b:
                if not _assign(cands, spots[0], d + 1):
                    return False
    return True


def _initial_candidates(grid):
    cands = [ALL] * 81
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if v:
                if not _assign(cands, r * 9 + c, v):
                    return None
    return cands


def _search(cands, solutions, limit):
    if len(solutions) >= limit:
        return
    # Pick the unsolved cell with the fewest candidates
    best, best_n = None, 10
    for i, m in enumerate(cands):
        n = bin(m).count("1")
        if 1 < n < best_n:
            best, best_n = i, n
            if n == 2:
                break
    if best is None:
        solutions.append([[cands[r * 9 + c].bit_length() for c in range(9)] for r in range(9)])
        return
    m = cands[best]
    for d in range(1, 10):
        if m & (1 << (d - 1)):
            trial = cands[:]
            if _assign(trial, best, d):
                _search(trial, solutions, limit)
                if len(solutions) >= limit:
                    return


def find_solutions(grid, limit=2):
    """Return up to `limit` distinct solutions (a list of grids)."""
    if not is_valid_grid(grid):
        return []
    cands = _initial_candidates(grid)
    if cands is None:
        return []
    solutions = []
    _search(cands, solutions, limit)
    return solutions


def solve(grid):
    """Return a solved copy of the grid, or None if it has no solution."""
    sols = find_solutions(grid, limit=1)
    return sols[0] if sols else None


def count_solutions(grid, limit=2):
    """Count solutions, stopping at `limit`. 0 = unsolvable, 1 = unique, 2 = ambiguous."""
    return len(find_solutions(grid, limit))


def format_grid(grid):
    lines = []
    for r in range(9):
        if r and r % 3 == 0:
            lines.append("------+-------+------")
        row = []
        for c in range(9):
            if c and c % 3 == 0:
                row.append("|")
            row.append(str(grid[r][c]) if grid[r][c] else ".")
        lines.append(" ".join(row))
    return "\n".join(lines)


if __name__ == "__main__":
    puzzle = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9],
    ]
    print(format_grid(puzzle))
    print()
    result = solve(puzzle)
    print(format_grid(result) if result else "No solution")
    print("solutions (up to 2):", count_solutions(puzzle))
