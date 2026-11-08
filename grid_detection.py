"""Find a sudoku grid in a photo, flatten it, and cut it into 81 cell images."""
import cv2
import numpy as np

WARP_SIZE = 450  # side of the flattened grid in pixels (50 px per cell)


def preprocess(image):
    """Grayscale -> blur -> adaptive threshold (white lines on black)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    return gray, thresh


def order_corners(pts):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(pts, dtype="float32").reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(s)],  # top-left: smallest x+y
        pts[np.argmin(d)],  # top-right: smallest y-x
        pts[np.argmax(s)],  # bottom-right: largest x+y
        pts[np.argmax(d)],  # bottom-left: largest y-x
    ], dtype="float32")


def find_grid_corners(thresh):
    """Return the 4 outer corners of the largest quadrilateral, or None."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    img_area = thresh.shape[0] * thresh.shape[1]
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(cnt) < 0.1 * img_area:
            break
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            return order_corners(approx)
    # Fallback for hand-drawn or imperfect borders: use the rotated bounding box
    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < 0.1 * img_area:
        return None
    return order_corners(cv2.boxPoints(cv2.minAreaRect(biggest)))


def warp_grid(image, corners, size=WARP_SIZE):
    """Perspective-transform the grid to a flat size x size square."""
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(image, M, (size, size)), M


def remove_grid_lines(warped, line_len=25):
    """Binarize the flattened grid and erase the grid lines, leaving only digits.

    Long horizontal/vertical strokes are found with morphological opening and
    subtracted. `line_len` must be shorter than a cell (50 px) but longer than
    the straight stroke of a digit such as 1 or 7.
    """
    blur = cv2.GaussianBlur(warped, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 12
    )
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_len))
    lines = cv2.bitwise_or(
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk),
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk),
    )
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8))
    return cv2.bitwise_and(binary, cv2.bitwise_not(lines))


def _line_peaks(profile, min_gap=15, rel_thresh=0.25):
    """Positions of peaks in a 1-D line-strength profile, strongest kept per cluster."""
    p = np.convolve(profile, np.ones(5) / 5, mode="same")
    peaks = [i for i in range(2, len(p) - 2)
             if p[i] == p[i - 2: i + 3].max() and p[i] > rel_thresh * p.max()]
    merged = []
    for i in peaks:
        if merged and i - merged[-1] < min_gap:
            if p[i] > p[merged[-1]]:
                merged[-1] = i
        else:
            merged.append(i)
    return merged, p


def _complete_lines(peaks, strength, size, n=10):
    """Turn a partial list of detected line positions into exactly n positions.

    Gaps between detected lines are filled using the typical spacing, then the
    sequence is extended on whichever side of the image has more room. Falls
    back to evenly spaced lines if too few were detected.
    """
    if len(peaks) < 4:
        return list(np.linspace(0, size - 1, n))
    diffs = np.diff(peaks)
    spacing = float(np.median(diffs))
    pts = [float(peaks[0])]
    for a, b in zip(peaks[:-1], peaks[1:]):
        k = max(1, int(round((b - a) / spacing)))
        pts.extend(a + (b - a) * j / k for j in range(1, k + 1))
    while len(pts) < n:
        room_before, room_after = pts[0], (size - 1) - pts[-1]
        if room_before >= room_after:
            pts.insert(0, pts[0] - spacing)
        else:
            pts.append(pts[-1] + spacing)
    while len(pts) > n:  # drop the weaker end line
        if strength[int(np.clip(pts[0], 0, size - 1))] < strength[int(np.clip(pts[-1], 0, size - 1))]:
            pts.pop(0)
        else:
            pts.pop()
    return [float(np.clip(x, 0, size - 1)) for x in pts]


def find_line_positions(warped, detect_len=30):
    """Locate the 10 horizontal and 10 vertical grid lines in the flattened image.

    Works for hand-drawn grids with uneven spacing. Returns (ys, xs).
    """
    size = warped.shape[0]
    blur = cv2.GaussianBlur(warped, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 12
    )
    hmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (detect_len, 1)))
    vmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (1, detect_len)))
    ys, ps = _line_peaks(hmask.sum(axis=1).astype(float) / 255)
    xs, pc = _line_peaks(vmask.sum(axis=0).astype(float) / 255)
    return _complete_lines(ys, ps, size), _complete_lines(xs, pc, size)


def split_cells(image, ys=None, xs=None, margin=0.16):
    """Cut an image into a 9x9 list of cell images along the given line positions.

    Without `ys`/`xs` the grid is cut into equal squares. `margin` trims a
    fraction of each cell's own size so leftover line fragments are ignored.
    """
    size = image.shape[0]
    if ys is None:
        ys = list(np.linspace(0, size, 10))
    if xs is None:
        xs = list(np.linspace(0, size, 10))
    cells = []
    for r in range(9):
        row = []
        for c in range(9):
            ph = int((ys[r + 1] - ys[r]) * margin)
            pw = int((xs[c + 1] - xs[c]) * margin)
            y0, y1 = int(ys[r]) + ph, int(ys[r + 1]) - ph
            x0, x1 = int(xs[c]) + pw, int(xs[c + 1]) - pw
            row.append(image[y0:y1, x0:x1])
        cells.append(row)
    return cells


def is_cell_empty(clean_cell, min_ink=0.0115):
    """A cell (from the line-free binary image) is blank if it holds almost no ink."""
    return (np.count_nonzero(clean_cell) / clean_cell.size) < min_ink


def extract_cells(image):
    """Full pipeline: photo -> (warped grid, 9x9 digit-only cells, blank mask, transform).

    Returns None if no grid is found.
    """
    gray, thresh = preprocess(image)
    corners = find_grid_corners(thresh)
    if corners is None:
        return None
    warped, M = warp_grid(gray, corners)
    ys, xs = find_line_positions(warped)
    cells = split_cells(remove_grid_lines(warped), ys, xs)
    empty = [[is_cell_empty(cells[r][c]) for c in range(9)] for r in range(9)]
    return warped, cells, empty, M


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sudoku.jpeg"
    img = cv2.imread(path)
    if img is None:
        sys.exit(f"Could not read image: {path}")
    result = extract_cells(img)
    if result is None:
        sys.exit("No sudoku grid found")
    warped, cells, empty, _ = result
    cv2.imwrite("warped.png", warped)
    print("Saved warped.png")
    for r in range(9):
        print(" ".join("." if empty[r][c] else "#" for c in range(9)))
