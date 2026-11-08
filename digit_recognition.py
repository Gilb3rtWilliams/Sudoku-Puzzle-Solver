"""Recognize the digits in the cells produced by grid_detection.extract_cells.

Pipeline per cell: clean binary cell -> MNIST-style 28x28 vector -> classifier.
The classifier is a scikit-learn model saved with joblib (see train_digit_model.py).
"""
import cv2
import numpy as np

MODEL_PATH = "digit_model.joblib"


def preprocess_digit(cell, out_size=28, digit_size=20, min_area=15):
    """Turn a binary cell (ink = 255) into a flat 784-vector in MNIST style.

    Steps: drop specks and components whose centre is near the cell edge (line leftovers),
    crop to the ink's bounding box, scale the longer side to `digit_size`,
    and centre by centre of mass inside an `out_size` square.
    Returns None if no ink is left.
    """
    binary = (cell > 0).astype(np.uint8) * 255
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    h, w = binary.shape
    keep = np.zeros_like(binary)
    for i in range(1, n):
        area = stats[i][4]
        cx, cy = centroids[i]
        # Digit strokes sit near the middle; leftover line fragments hug the edges.
        central = 0.2 * w <= cx <= 0.8 * w and 0.2 * h <= cy <= 0.8 * h
        if area >= min_area and central:
            keep[labels == i] = 255
    ys, xs = np.nonzero(keep)
    if len(ys) == 0:
        return None
    crop = keep[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    ch, cw = crop.shape
    scale = digit_size / max(ch, cw)
    crop = cv2.resize(crop, (max(1, round(cw * scale)), max(1, round(ch * scale))),
                      interpolation=cv2.INTER_AREA)
    canvas = np.zeros((out_size, out_size), np.uint8)
    ch, cw = crop.shape
    y0, x0 = (out_size - ch) // 2, (out_size - cw) // 2
    canvas[y0: y0 + ch, x0: x0 + cw] = crop
    # Shift so the centre of mass sits at the centre (as in MNIST)
    m = cv2.moments(canvas, binaryImage=False)
    if m["m00"] > 0:
        shift_x = out_size / 2 - m["m10"] / m["m00"]
        shift_y = out_size / 2 - m["m01"] / m["m00"]
        M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        canvas = cv2.warpAffine(canvas, M, (out_size, out_size))
    return (canvas.astype(np.float32) / 255.0).ravel()


def load_model(path=MODEL_PATH):
    import joblib
    return joblib.load(path)


def recognize_grid(cells, empty, model, min_confidence=0.6):
    """Read a 9x9 grid of cells.

    Returns (grid, confidence, uncertain):
      grid       9x9 ints, 0 for blank
      confidence 9x9 floats (1.0 for blanks)
      uncertain  list of (row, col) the model is unsure about, or where no
                 clean digit could be isolated, for the user to check
    """
    grid = [[0] * 9 for _ in range(9)]
    conf = [[1.0] * 9 for _ in range(9)]
    uncertain = []
    for r in range(9):
        for c in range(9):
            if empty[r][c]:
                continue
            vec = preprocess_digit(cells[r][c])
            if vec is None:
                uncertain.append((r, c))
                continue
            proba = model.predict_proba(vec.reshape(1, -1))[0]
            best = int(np.argmax(proba))
            grid[r][c] = int(model.classes_[best])
            conf[r][c] = float(proba[best])
            if conf[r][c] < min_confidence:
                uncertain.append((r, c))
    return grid, conf, uncertain
