"""Train the digit classifier and save it to digit_model.joblib.

  python train_digit_model.py --source mnist     # needs internet (fetch_openml)
  python train_digit_model.py --source builtin   # offline: sklearn digits + synthetic fonts

Add your own labelled cell crops with --extra samples.npz (arrays X [N,784], y [N]).
"""
import argparse

import cv2
import joblib
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split

from digit_recognition import preprocess_digit, MODEL_PATH

FONTS = [cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_PLAIN, cv2.FONT_HERSHEY_DUPLEX,
         cv2.FONT_HERSHEY_COMPLEX, cv2.FONT_HERSHEY_TRIPLEX,
         cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, cv2.FONT_HERSHEY_SCRIPT_COMPLEX,
         cv2.FONT_HERSHEY_COMPLEX_SMALL]


def _augment(img, rng):
    """Random rotation, shear, scale and stroke thickness on a binary image."""
    h, w = img.shape
    ang = rng.uniform(-15, 15)
    shear = rng.uniform(-0.25, 0.25)
    s = rng.uniform(0.85, 1.1)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, s)
    M[0, 1] += shear
    out = cv2.warpAffine(img, M, (w, h))
    k = rng.integers(0, 3)
    if k == 1:
        out = cv2.dilate(out, np.ones((2, 2), np.uint8))
    elif k == 2:
        out = cv2.erode(out, np.ones((2, 2), np.uint8))
    return (out > 100).astype(np.uint8) * 255


def synthetic_font_digits(n_per_digit, rng):
    X, y = [], []
    for d in range(1, 10):
        for _ in range(n_per_digit):
            canvas = np.zeros((72, 72), np.uint8)
            font = FONTS[rng.integers(len(FONTS))]
            scale = rng.uniform(1.2, 2.2)
            thick = int(rng.integers(1, 4))
            (tw, th), _ = cv2.getTextSize(str(d), font, scale, thick)
            cv2.putText(canvas, str(d), ((72 - tw) // 2, (72 + th) // 2), font, scale, 255, thick)
            vec = preprocess_digit(_augment(canvas, rng))
            if vec is not None:
                X.append(vec)
                y.append(d)
    return np.array(X), np.array(y)


def sklearn_handwritten(rng, repeats=6):
    """The 1,797 small handwritten digits bundled with scikit-learn (8x8), upscaled."""
    from sklearn.datasets import load_digits
    data = load_digits()
    X, y = [], []
    for img, label in zip(data.images, data.target):
        if label == 0:
            continue
        big = cv2.resize((img / 16.0 * 255).astype(np.uint8), (64, 64), interpolation=cv2.INTER_CUBIC)
        binary = (big > 90).astype(np.uint8) * 255
        for _ in range(repeats):
            vec = preprocess_digit(_augment(binary, rng))
            if vec is not None:
                X.append(vec)
                y.append(int(label))
    return np.array(X), np.array(y)


def mnist_digits(rng, limit=None):
    from sklearn.datasets import fetch_openml
    mn = fetch_openml("mnist_784", version=1, as_frame=False)
    X, y = mn.data, mn.target.astype(int)
    keep = y != 0
    X, y = X[keep], y[keep]
    if limit:
        X, y = X[:limit], y[:limit]
    out_X, out_y = [], []
    for img, label in zip(X, y):
        vec = preprocess_digit((img.reshape(28, 28) > 90).astype(np.uint8) * 255)
        if vec is not None:
            out_X.append(vec)
            out_y.append(label)
    return np.array(out_X), np.array(out_y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["builtin", "mnist"], default="builtin")
    ap.add_argument("--extra", help="npz with your own samples: X [N,784], y [N]")
    ap.add_argument("--out", default=MODEL_PATH)
    args = ap.parse_args()
    rng = np.random.default_rng(0)

    parts = []
    if args.source == "mnist":
        parts.append(mnist_digits(rng))
    parts.append(sklearn_handwritten(rng))
    parts.append(synthetic_font_digits(1500, rng))
    if args.extra:
        e = np.load(args.extra)
        parts.append((e["X"], e["y"]))
    X = np.vstack([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    print(f"training samples: {len(y)}")

    Xtr, Xva, ytr, yva = train_test_split(X, y, test_size=0.1, random_state=0, stratify=y)
    model = MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=80, early_stopping=True,
                          random_state=0)
    model.fit(Xtr, ytr)
    print(f"validation accuracy (same distribution as training): {model.score(Xva, yva):.3f}")
    joblib.dump(model, args.out)
    print("saved", args.out)


if __name__ == "__main__":
    main()
