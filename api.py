"""FastAPI service: upload a sudoku photo, get the solution back.

Run:  uvicorn api:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import base64
import os
from contextlib import asynccontextmanager
from typing import List

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from digit_recognition import load_model, MODEL_PATH
from checker import check_answers, hint
from pipeline import solve_image, NoGridFound
from solver import find_solutions

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600  # downscale huge phone photos before processing

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    path = os.environ.get("DIGIT_MODEL_PATH", MODEL_PATH)
    if not os.path.exists(path):
        raise RuntimeError(f"Digit model not found at {path}. Run: python train_digit_model.py")
    state["model"] = load_model(path)
    yield
    state.clear()


app = FastAPI(title="Sudoku Image Solver", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_shape(g):
    if len(g) != 9 or any(len(row) != 9 for row in g):
        raise ValueError("grid must be 9 rows of 9 numbers")
    if any(not 0 <= v <= 9 for row in g for v in row):
        raise ValueError("cells must be 0 (blank) to 9")
    return g


class GridIn(BaseModel):
    grid: List[List[int]]

    @field_validator("grid")
    @classmethod
    def check_shape(cls, g):
        return _check_shape(g)


class CheckIn(BaseModel):
    givens: List[List[int]]  # the locked clues
    grid: List[List[int]]    # clues plus the player's answers

    @field_validator("givens", "grid")
    @classmethod
    def check_shape(cls, g):
        return _check_shape(g)


def _message(count, uncertain):
    if count == 1:
        return "Solved."
    if count >= 2:
        return "This puzzle has more than one solution. Check for a misread or missing digit."
    if uncertain:
        return "No solution found. Check the flagged cells; a digit was probably misread."
    return "No solution found. A digit was probably misread; check the grid."


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/solve")
def solve_photo(file: UploadFile = File(...)):
    """Upload a photo. Returns what was read, the solution, and an annotated image."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image is larger than 10 MB")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode the file as an image")
    h, w = image.shape[:2]
    if max(h, w) > MAX_SIDE:
        f = MAX_SIDE / max(h, w)
        image = cv2.resize(image, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    try:
        res = solve_image(image, state["model"])
    except NoGridFound as e:
        raise HTTPException(422, str(e))
    overlay_b64 = None
    if res["overlay"] is not None:
        ok, png = cv2.imencode(".png", res["overlay"])
        overlay_b64 = base64.b64encode(png.tobytes()).decode()
    return {
        "grid": res["grid"],
        "confidence": res["confidence"],
        "uncertain": [{"row": r, "col": c} for r, c in res["uncertain"]],
        "solution_count": res["solution_count"],
        "solution": res["solution"],
        "overlay_png_base64": overlay_b64,
        "message": _message(res["solution_count"], res["uncertain"]),
    }


@app.post("/solve-grid")
def solve_grid(body: GridIn):
    """Solve a grid directly, e.g. after the user corrects misread cells in the UI."""
    solutions = find_solutions(body.grid, limit=2)
    return {
        "solution_count": len(solutions),
        "solution": solutions[0] if solutions else None,
        "message": _message(len(solutions), []),
    }


@app.post("/check")
def check(body: CheckIn):
    """Grade the player's answers against the puzzle's unique solution."""
    try:
        return check_answers(body.givens, body.grid)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/hint")
def get_hint(body: CheckIn):
    """The best next move from the player's current board, as a nudge, then a reason, then the digit."""
    try:
        return hint(body.givens, body.grid)
    except ValueError as e:
        raise HTTPException(422, str(e))
