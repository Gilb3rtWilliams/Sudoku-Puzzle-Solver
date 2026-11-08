"""Photo of a sudoku -> read digits -> solve -> overlay. Also a small CLI."""
import cv2
import numpy as np

from grid_detection import analyze_image
from digit_recognition import recognize_grid
from solver import find_solutions


class NoGridFound(Exception):
    """The image doesn't contain a recognizable sudoku grid."""


def draw_solution(image, solution, given, analysis, color=(0, 160, 0)):
    """Draw solved digits onto the original photo, only in cells that were blank.

    Cell centres are computed in the flattened grid, then mapped back to the
    photo with the inverse of the perspective transform.
    """
    out = image.copy()
    ys, xs, M = analysis["ys"], analysis["xs"], analysis["M"]
    inv = np.linalg.inv(M)
    for r in range(9):
        for c in range(9):
            if given[r][c]:
                continue
            cx, cy = (xs[c] + xs[c + 1]) / 2, (ys[r] + ys[r + 1]) / 2
            w, h = xs[c + 1] - xs[c], ys[r + 1] - ys[r]
            pts = np.float32([[[cx, cy], [cx + w, cy], [cx, cy + h]]])
            (px, py), (qx, qy), (sx, sy) = cv2.perspectiveTransform(pts, inv)[0]
            cell_w = np.hypot(qx - px, qy - py)
            cell_h = np.hypot(sx - px, sy - py)
            scale = max(0.4, min(cell_w, cell_h) / 38.0)
            thick = max(2, int(scale * 2))
            text = str(solution[r][c])
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
            cv2.putText(out, text, (int(px - tw / 2), int(py + th / 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)
    return out


def solve_image(image, model, min_confidence=0.6):
    """Run the whole pipeline on a BGR image (as loaded by cv2).

    Returns a dict:
      grid, confidence, uncertain   what was read from the photo
      solution_count                0 = unsolvable as read, 1 = unique, 2 = more than one
      solution                      the first solution found, or None
      overlay                       the photo with solved digits drawn on, or None
    Raises NoGridFound if no grid is detected.
    """
    analysis = analyze_image(image)
    if analysis is None:
        raise NoGridFound("No sudoku grid found in the image")
    grid, conf, uncertain = recognize_grid(analysis["cells"], analysis["empty"], model,
                                           min_confidence)
    solutions = find_solutions(grid, limit=2)
    solution = solutions[0] if solutions else None
    overlay = draw_solution(image, solution, grid, analysis) if solution else None
    return {
        "grid": grid,
        "confidence": conf,
        "uncertain": uncertain,
        "solution_count": len(solutions),
        "solution": solution,
        "overlay": overlay,
    }


if __name__ == "__main__":
    import sys
    from digit_recognition import load_model
    from solver import format_grid

    path = sys.argv[1] if len(sys.argv) > 1 else "sudoku.jpeg"
    img = cv2.imread(path)
    if img is None:
        sys.exit(f"Could not read image: {path}")
    try:
        res = solve_image(img, load_model())
    except NoGridFound as e:
        sys.exit(str(e))
    print("Read from the photo ('.' = blank):")
    print(format_grid(res["grid"]))
    if res["uncertain"]:
        print("\nCheck these cells (row, col, 1-indexed):",
              [(r + 1, c + 1) for r, c in res["uncertain"]])
    print(f"\nSolutions found (up to 2): {res['solution_count']}")
    if res["solution"]:
        print(format_grid(res["solution"]))
        cv2.imwrite("solved.png", res["overlay"])
        print("\nSaved solved.png")
    else:
        print("No solution: at least one digit was probably misread. Check the cells above.")
