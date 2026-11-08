"""Grade a player's answers against a puzzle's unique solution.

Finds every wrong cell and explains it, from most to least direct:
  clash     the digit repeats one already in its row, column or box
  logic     no visible clash, but the cell's right digit follows from a chain of deductions
            (explain.py), which is walked through step by step
  mismatch  wrong, but the reasoning needs a technique the explainer doesn't have yet
The correct digit is always carried along; the UI keeps it hidden until the player asks.

Grids are lists of 9 lists of 9 ints, 0 = blank. Rows and columns in the output are 0-indexed;
the human-readable text is 1-indexed.
"""
from explain import BOX_NAMES, Explainer
from solver import PEERS, find_solutions


def _box(r, c):
    return (r // 3) * 3 + c // 3


def _shared_units(r1, c1, r2, c2):
    units = []
    if r1 == r2:
        units.append(("row", r1))
    if c1 == c2:
        units.append(("column", c1))
    if _box(r1, c1) == _box(r2, c2):
        units.append(("box", _box(r1, c1)))
    return units


def _unit_label(kind, index):
    if kind == "box":
        return f"the {BOX_NAMES[index]} box"
    return f"{kind} {index + 1}"


def _clashes(grid, givens, r, c):
    """Cells in the same row, column or box that hold the same digit as (r, c)."""
    digit = grid[r][c]
    found = []
    for p in PEERS[r * 9 + c]:
        pr, pc = divmod(p, 9)
        if grid[pr][pc] == digit:
            found.append({
                "row": pr,
                "col": pc,
                "given": bool(givens[pr][pc]),
                "units": [k for k, _ in _shared_units(r, c, pr, pc)],
            })
    # Given clues first: they are the clearest reason, and they can never be the wrong one.
    found.sort(key=lambda x: (not x["given"], x["row"], x["col"]))
    return found


def _explain_clash(grid, solution, r, c, clash):
    digit = grid[r][c]
    pr, pc = clash["row"], clash["col"]
    kind, index = _shared_units(r, c, pr, pc)[0]
    # Name the position relative to the unit, so we never say "row 1 ... at row 1, column 1".
    where = {"row": f"column {pc + 1}", "column": f"row {pr + 1}"}.get(kind, f"row {pr + 1}, column {pc + 1}")
    unit = _unit_label(kind, index)
    if clash["given"]:
        return f"{digit} can't go here: {unit} already has a {digit} at {where} (a given clue)."
    if grid[pr][pc] == solution[pr][pc]:
        return (f"{digit} can't go here: {unit} already has a {digit} at {where}, "
                f"and that one is correct.")
    return (f"You've put {digit} twice in {unit}: here and at {where}. "
            f"Neither is the right digit for its cell.")


def _explain_mismatch(digit):
    return (f"{digit} doesn't repeat anything in its row, column or box, but it isn't the digit "
            f"this puzzle's only solution needs here. Proving why takes a more advanced technique "
            f"than I can walk through yet.")


def check_answers(givens, grid):
    """Compare `grid` (givens + the player's entries) with the unique solution of `givens`.

    Raises ValueError if `grid` changes a given clue.
    Returns a dict with `status` ('ok', 'unsolvable' or 'not_unique'); when 'ok' it also carries
    the counts, `solved`, and `mistakes` (one dict per wrong cell).
    """
    for r in range(9):
        for c in range(9):
            if givens[r][c] and grid[r][c] != givens[r][c]:
                raise ValueError(f"Row {r + 1}, column {c + 1} is a given clue and can't be changed.")

    solutions = find_solutions(givens, limit=2)
    if not solutions:
        return {"status": "unsolvable",
                "message": "These clues contradict each other, so there is nothing to check against. "
                           "Go back and look for a misread or mistyped clue."}
    if len(solutions) > 1:
        return {"status": "not_unique",
                "message": "This puzzle has more than one solution, so \"the right answer\" isn't defined. "
                           "Go back and check for a missing or misread clue."}
    solution = solutions[0]

    entered = correct = blank = 0
    mistakes = []
    explainer = None  # built on first use; only needed for wrong digits that clash with nothing
    for r in range(9):
        for c in range(9):
            if givens[r][c]:
                continue
            digit = grid[r][c]
            if not digit:
                blank += 1
                continue
            entered += 1
            if digit == solution[r][c]:
                correct += 1
                continue
            clashes = _clashes(grid, givens, r, c)
            steps, technique = [], None
            highlights = [{"row": x["row"], "col": x["col"]} for x in clashes]
            if clashes:
                kind, text = "clash", _explain_clash(grid, solution, r, c, clashes[0])
            else:
                if explainer is None:
                    explainer = Explainer(givens)
                reasoning = explainer.explain(r * 9 + c, digit, solution[r][c])
                if reasoning:
                    kind, text = "logic", reasoning["explanation"]
                    steps, technique = reasoning["steps"], reasoning["technique"]
                    highlights = reasoning["highlights"]
                else:
                    kind, text = "mismatch", _explain_mismatch(digit)
            mistakes.append({
                "row": r,
                "col": c,
                "entered": digit,
                "kind": kind,
                "explanation": text,
                "technique": technique,
                "clashes": clashes,
                "highlights": highlights,
                "steps": steps,
                "correct_digit": solution[r][c],
            })

    wrong = len(mistakes)
    solved = wrong == 0 and blank == 0
    if solved:
        message = "Every answer is right. Puzzle solved!"
    elif wrong:
        message = f"{wrong} of your {entered} answer{'s' if entered != 1 else ''} " \
                  f"{'is' if wrong == 1 else 'are'} wrong."
    elif entered:
        message = f"All {entered} of your answers so far are right. {blank} cell{'s' if blank != 1 else ''} to go."
    else:
        message = "Fill in some cells, then check them."
    return {
        "status": "ok",
        "message": message,
        "solved": solved,
        "entered": entered,
        "correct": correct,
        "wrong": wrong,
        "blank": blank,
        "mistakes": mistakes,
    }
