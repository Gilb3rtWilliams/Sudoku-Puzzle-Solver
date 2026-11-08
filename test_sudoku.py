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


def test_digit_recognition_end_to_end():
    """Photo -> cells -> digits on a synthetic perspective-warped puzzle."""
    import numpy as np
    from digit_recognition import recognize_grid
    from train_digit_model import synthetic_font_digits, sklearn_handwritten
    from sklearn.neural_network import MLPClassifier

    rng = np.random.default_rng(0)
    parts = [synthetic_font_digits(300, rng), sklearn_handwritten(rng, repeats=2)]
    X = np.vstack([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    model = MLPClassifier(hidden_layer_sizes=(128,), max_iter=60, random_state=0).fit(X, y)

    _, cells, empty, _ = extract_cells(make_photo(PUZZLE))
    grid, _, _ = recognize_grid(cells, empty, model)
    correct = sum(grid[r][c] == PUZZLE[r][c] for r in range(9) for c in range(9))
    assert correct >= 77  # allow a few of 81 cells to be wrong


# ---------- API ----------
import pytest


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    import joblib
    from fastapi.testclient import TestClient
    from sklearn.neural_network import MLPClassifier
    from train_digit_model import synthetic_font_digits, sklearn_handwritten

    rng = np.random.default_rng(0)
    parts = [synthetic_font_digits(400, rng), sklearn_handwritten(rng, repeats=3)]
    X = np.vstack([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    model = MLPClassifier(hidden_layer_sizes=(128,), max_iter=80, random_state=0).fit(X, y)
    path = tmp_path_factory.mktemp("m") / "model.joblib"
    joblib.dump(model, path)
    os.environ["DIGIT_MODEL_PATH"] = str(path)
    from api import app
    with TestClient(app) as c:
        yield c


def test_api_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_api_solve_grid(client):
    r = client.post("/solve-grid", json={"grid": PUZZLE})
    body = r.json()
    assert r.status_code == 200
    assert body["solution_count"] == 1
    assert body["solution"][0] == [5, 3, 4, 6, 7, 8, 9, 1, 2]


def test_api_solve_grid_rejects_bad_shape(client):
    assert client.post("/solve-grid", json={"grid": [[0] * 9] * 8}).status_code == 422
    assert client.post("/solve-grid", json={"grid": [[10] * 9] * 9}).status_code == 422


def test_api_solve_photo(client):
    ok, png = cv2.imencode(".png", make_photo(PUZZLE))
    r = client.post("/solve", files={"file": ("p.png", png.tobytes(), "image/png")})
    body = r.json()
    assert r.status_code == 200
    assert body["solution_count"] == 1
    assert body["solution"][0] == [5, 3, 4, 6, 7, 8, 9, 1, 2]
    assert body["overlay_png_base64"]


def test_api_rejects_non_image_and_blank_image(client):
    r = client.post("/solve", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    ok, png = cv2.imencode(".png", np.full((400, 400, 3), 255, np.uint8))
    r = client.post("/solve", files={"file": ("b.png", png.tobytes(), "image/png")})
    assert r.status_code == 422
