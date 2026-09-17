from __future__ import annotations

import json
import os
import random
import time
from collections import deque
from collections.abc import Mapping
from typing import Any

import streamlit as st


BOARD_WIDTH = 10
BOARD_HEIGHT = 20
ROTATION_NAMES = ("0", "R", "2", "L")
PIECE_KINDS = ("I", "O", "T", "J", "L", "S", "Z")
ACTIONS = ("left", "right", "rotate", "drop")

SHAPES = {
    "I": (
        ((0, 1), (1, 1), (2, 1), (3, 1)),
        ((2, 0), (2, 1), (2, 2), (2, 3)),
        ((0, 2), (1, 2), (2, 2), (3, 2)),
        ((1, 0), (1, 1), (1, 2), (1, 3)),
    ),
    "O": (
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
    ),
    "T": (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    "J": (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (2, 2)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    "L": (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (1, 2), (2, 2)),
        ((0, 1), (1, 1), (2, 1), (0, 2)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
    "S": (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((1, 0), (1, 1), (2, 1), (2, 2)),
        ((1, 1), (2, 1), (0, 2), (1, 2)),
        ((0, 0), (1, 0), (1, 1), (2, 1)),
    ),
    "Z": (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((2, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (1, 2), (2, 2)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
}

# SRS tables use a positive-up y axis. The board converts those offsets to its
# positive-down y axis when trying a rotation.
_JLSTZ_KICKS = {
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}
_I_KICKS = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}

PIECE_COLORS = {
    "I": "cyan",
    "O": "yellow",
    "T": "purple",
    "J": "blue",
    "L": "orange",
    "S": "green",
    "Z": "red",
}


def _empty_board() -> list[list[str | None]]:
    return [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]


def _new_bag(rng: random.Random) -> list[str]:
    bag = list(PIECE_KINDS)
    rng.shuffle(bag)
    return bag


def new_game(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    queue = _new_bag(rng) + _new_bag(rng)
    return {
        "board": _empty_board(),
        "kind": queue.pop(0),
        "rotation": 0,
        "x": 3,
        "y": 0,
        "queue": queue,
        "_rng": rng,
        "pieces": 0,
        "lines": 0,
        "score": 0,
        "game_over": False,
        "last_event": "Ready. Choose a placement or ask Jev.",
        "last_plan": None,
        "last_lock": None,
    }


def _ensure_queue(state: dict[str, Any], minimum: int = 5) -> None:
    while len(state["queue"]) < minimum:
        state["queue"].extend(_new_bag(state["_rng"]))


def next_pieces(state: dict[str, Any], count: int = 5) -> list[str]:
    _ensure_queue(state, count)
    return state["queue"][:count]


def piece_cells(kind: str, rotation: int, x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in SHAPES[kind][rotation % 4]]


def current_cells(state: dict[str, Any]) -> list[tuple[int, int]]:
    return piece_cells(state["kind"], state["rotation"], state["x"], state["y"])


def can_place_on_board(
    board: list[list[str | None]],
    kind: str,
    rotation: int,
    x: int,
    y: int,
    *,
    allow_above_board: bool = True,
) -> bool:
    for cell_x, cell_y in piece_cells(kind, rotation, x, y):
        if cell_x < 0 or cell_x >= BOARD_WIDTH or cell_y >= BOARD_HEIGHT:
            return False
        if cell_y < 0:
            if allow_above_board:
                continue
            return False
        if board[cell_y][cell_x] is not None:
            return False
    return True


def can_place(
    state: dict[str, Any],
    *,
    dx: int = 0,
    dy: int = 0,
    rotation: int | None = None,
    x: int | None = None,
    y: int | None = None,
) -> bool:
    selected_rotation = state["rotation"] if rotation is None else rotation
    selected_x = state["x"] + dx if x is None else x
    selected_y = state["y"] + dy if y is None else y
    return can_place_on_board(
        state["board"],
        state["kind"],
        selected_rotation,
        selected_x,
        selected_y,
    )


def _kick_tests(kind: str, from_rotation: int, to_rotation: int) -> tuple[tuple[int, int], ...]:
    if kind == "O":
        return ((0, 0),)
    table = _I_KICKS if kind == "I" else _JLSTZ_KICKS
    return table[(from_rotation, to_rotation)]


def _rotate_clockwise(state: dict[str, Any]) -> bool:
    from_rotation = state["rotation"] % 4
    to_rotation = (from_rotation + 1) % 4
    for kick_x, kick_y_up in _kick_tests(state["kind"], from_rotation, to_rotation):
        candidate_x = state["x"] + kick_x
        candidate_y = state["y"] - kick_y_up
        if can_place(state, rotation=to_rotation, x=candidate_x, y=candidate_y):
            state["rotation"] = to_rotation
            state["x"] = candidate_x
            state["y"] = candidate_y
            state["last_event"] = (
                f"Rotated {state['kind']} to {ROTATION_NAMES[to_rotation]} "
                f"with SRS kick ({kick_x}, {kick_y_up})."
            )
            return True
    return False


def _drop_y_for_board(
    board: list[list[str | None]],
    kind: str,
    rotation: int,
    x: int,
    start_y: int = 0,
) -> int | None:
    if not can_place_on_board(board, kind, rotation, x, start_y):
        return None
    y = start_y
    while can_place_on_board(board, kind, rotation, x, y + 1):
        y += 1
    if not can_place_on_board(board, kind, rotation, x, y, allow_above_board=False):
        return None
    return y


def hard_drop_y(state: dict[str, Any]) -> int | None:
    return _drop_y_for_board(
        state["board"],
        state["kind"],
        state["rotation"],
        state["x"],
        state["y"],
    )


def apply_move(state: dict[str, Any], action: str) -> None:
    if action not in ACTIONS:
        raise ValueError(f"Unknown Tetris action: {action}")
    if state["game_over"]:
        return

    if action == "left" and can_place(state, dx=-1):
        state["x"] -= 1
        state["last_event"] = "Moved left."
        return
    if action == "right" and can_place(state, dx=1):
        state["x"] += 1
        state["last_event"] = "Moved right."
        return
    if action == "rotate":
        _rotate_clockwise(state)
        return
    if action == "drop":
        target_y = hard_drop_y(state)
        if target_y is None:
            state["game_over"] = True
            return
        state["y"] = target_y
        _lock_piece(state)


def _lock_board(
    board: list[list[str | None]],
    kind: str,
    cells: list[tuple[int, int]],
) -> tuple[list[list[str | None]], int]:
    next_board = [row[:] for row in board]
    for x, y in cells:
        if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
            raise ValueError("A placement contains a cell outside the board")
        if next_board[y][x] is not None:
            raise ValueError("A placement overlaps a locked cell")
        next_board[y][x] = kind

    remaining_rows = [row for row in next_board if not all(cell is not None for cell in row)]
    lines_cleared = BOARD_HEIGHT - len(remaining_rows)
    return [[None for _ in range(BOARD_WIDTH)] for _ in range(lines_cleared)] + remaining_rows, lines_cleared


def _board_strings(board: list[list[str | None]]) -> list[str]:
    return ["".join(cell or "." for cell in row) for row in board]


def _board_from_strings(rows: list[str]) -> list[list[str | None]]:
    return [[None if cell == "." else cell for cell in row] for row in rows]


def _board_features(board: list[list[str | None]], lines_cleared: int = 0) -> dict[str, int]:
    heights: list[int] = []
    holes = 0
    for x in range(BOARD_WIDTH):
        first_filled = next(
            (y for y in range(BOARD_HEIGHT) if board[y][x] is not None),
            BOARD_HEIGHT,
        )
        height = BOARD_HEIGHT - first_filled if first_filled < BOARD_HEIGHT else 0
        heights.append(height)
        if first_filled < BOARD_HEIGHT:
            holes += sum(board[y][x] is None for y in range(first_filled, BOARD_HEIGHT))

    bumpiness = sum(abs(left - right) for left, right in zip(heights, heights[1:]))
    return {
        "lines_cleared": lines_cleared,
        "aggregate_height": sum(heights),
        "max_height": max(heights, default=0),
        "holes": holes,
        "bumpiness": bumpiness,
    }


def _placement_score(features: Mapping[str, int], next_score: float = 0.0) -> float:
    return (
        features["lines_cleared"] * 8.0
        - features["holes"] * 5.0
        - features["aggregate_height"] * 0.35
        - features["max_height"] * 0.4
        - features["bumpiness"] * 0.5
        + next_score * 0.25
    )


def _enumerate_placements(
    board: list[list[str | None]],
    kind: str,
) -> list[dict[str, Any]]:
    placements: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()
    rotation_count = 1 if kind == "O" else 4

    for rotation in range(rotation_count):
        for origin_x in range(-2, BOARD_WIDTH + 2):
            origin_y = _drop_y_for_board(board, kind, rotation, origin_x)
            if origin_y is None:
                continue
            cells = piece_cells(kind, rotation, origin_x, origin_y)
            cell_key = tuple(sorted(cells))
            if cell_key in seen:
                continue
            seen.add(cell_key)
            afterstate, lines_cleared = _lock_board(board, kind, cells)
            features = _board_features(afterstate, lines_cleared)
            placements.append(
                {
                    "rotation": rotation,
                    "rotation_name": ROTATION_NAMES[rotation],
                    "origin_x": origin_x,
                    "origin_y": origin_y,
                    "column": min(x for x, _ in cells),
                    "landing_row": min(y for _, y in cells),
                    "bottom_row": max(y for _, y in cells),
                    "occupied_cells": [[x, y] for x, y in sorted(cells)],
                    "lines_cleared": lines_cleared,
                    "features": features,
                    "afterstate": _board_strings(afterstate),
                }
            )

    placements.sort(key=lambda item: (item["rotation"], item["column"], item["landing_row"]))
    for index, placement in enumerate(placements, start=1):
        placement["id"] = f"p{index:02d}"
    return placements


def legal_placements(state: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = _enumerate_placements(state["board"], state["kind"])
    next_kind = next_pieces(state, 1)[0]
    for candidate in candidates:
        next_candidates = _enumerate_placements(
            _board_from_strings(candidate["afterstate"]),
            next_kind,
        )
        next_score = max(
            (_placement_score(item["features"]) for item in next_candidates),
            default=-100.0,
        )
        candidate["next_piece"] = next_kind
        candidate["next_best_score"] = round(next_score, 2)
        candidate["decision_score"] = round(
            _placement_score(candidate["features"], next_score),
            2,
        )
    return candidates


def game_state_for_jev(state: dict[str, Any]) -> dict[str, Any]:
    candidates = legal_placements(state)
    return {
        "coordinate_system": {
            "columns": "0 through 9, left to right",
            "rows": "0 through 19, top to bottom",
            "column_definition": "column is the leftmost occupied cell of the placed piece",
            "occupied_cells": "exact [column, row] pairs are provided for every candidate",
        },
        "board": _board_strings(state["board"]),
        "active_piece": {
            "kind": state["kind"],
            "rotation": ROTATION_NAMES[state["rotation"] % 4],
            "origin": [state["x"], state["y"]],
            "occupied_cells": [[x, y] for x, y in sorted(current_cells(state))],
        },
        "next_pieces": next_pieces(state, 5),
        "score": state["score"],
        "lines": state["lines"],
        "legal_placements": candidates,
        "allowed_placements": [candidate["id"] for candidate in candidates],
        "instruction": (
            "Choose exactly one legal_placements.id. Select a complete final placement, "
            "including its rotation and coordinate, not a low-level button action. "
            "Optimize for cleared lines while avoiding holes, high stacks, and rough "
            "surfaces; use next_piece_score as a tiebreaker."
        ),
    }


def fixture_next_placement(state: dict[str, Any]) -> tuple[dict[str, Any], float]:
    candidates = legal_placements(state)
    if not candidates:
        raise RuntimeError("No legal placements are available")
    return max(candidates, key=lambda item: item["decision_score"]), 0.9


def fixture_next_move(state: dict[str, Any]) -> tuple[str, float]:
    fixture_next_placement(state)
    return "drop", 0.9


_PLACEMENT_QUESTION = (
    "Choose exactly one candidate ID from the legal placements. "
    "The ID is the only valid answer. Prefer a strong afterstate and "
    "future flexibility over an immediate line clear that creates holes."
)


def jev_request_for_placement(
    state: dict[str, Any],
    model: str = "jev-latest",
) -> dict[str, Any]:
    jev_state = game_state_for_jev(state)
    criteria = {
        candidate["id"]: (
            f"Place {state['kind']} in rotation {candidate['rotation_name']} with "
            f"leftmost column {candidate['column']}, landing row {candidate['landing_row']}, "
            f"and occupied cells {candidate['occupied_cells']}. It clears "
            f"{candidate['lines_cleared']} line(s); afterstate holes="
            f"{candidate['features']['holes']}, max_height="
            f"{candidate['features']['max_height']}, bumpiness="
            f"{candidate['features']['bumpiness']}, next-piece score="
            f"{candidate['next_best_score']}."
        )
        for candidate in jev_state["legal_placements"]
    }
    return {
        "model": model,
        "state": jev_state,
        "questions": {
            "placement": {
                "type": "Choice",
                "instructions": _PLACEMENT_QUESTION,
                "criteria": criteria,
            }
        },
    }


def _placement_trace(
    *,
    source: str,
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    confidence: float,
    probabilities: Mapping[str, float],
    request_sent: bool,
) -> dict[str, Any]:
    return {
        "source": source,
        "request_sent": request_sent,
        "request": request,
        "response": {
            "placement": {
                "choice": candidate["id"],
                "confidence": confidence,
                "probabilities": dict(probabilities),
            }
        },
        "resolved_candidate": candidate,
    }


def live_next_placement(
    state: dict[str, Any],
    model: str = "jev-latest",
    *,
    request: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], float, dict[str, float]]:
    from typesafe_sdk import Choice, TypeSafeClient

    request = jev_request_for_placement(state, model) if request is None else request
    question = request["questions"]["placement"]
    questions = {
        "placement": Choice(
            instructions=question["instructions"],
            criteria=question["criteria"],
        )
    }
    with TypeSafeClient() as client:
        response = client.system_one(
            state=request["state"],
            questions=questions,
            model=request["model"],
        )

    candidates = request["state"]["legal_placements"]
    answers = getattr(response, "answers", {})
    answer = answers.get("placement")
    if answer is None:
        answer = getattr(response, "choices", {}).get("placement")
    placement_id = getattr(answer, "choice", None)
    candidate_by_id = {candidate["id"]: candidate for candidate in candidates}
    if placement_id not in candidate_by_id:
        raise RuntimeError(f"Jev returned an invalid placement ID: {placement_id!r}")
    return (
        candidate_by_id[placement_id],
        float(getattr(answer, "confidence", 0.0)),
        dict(getattr(answer, "probabilities", {})),
    )


def choose_next_placement(
    state: dict[str, Any],
    *,
    use_live: bool,
) -> tuple[dict[str, Any], float, dict[str, float], str, dict[str, Any]]:
    request = jev_request_for_placement(state)
    if use_live:
        candidate, confidence, probabilities = live_next_placement(state, request=request)
        source = "live Jev"
        return (
            candidate,
            confidence,
            probabilities,
            source,
            _placement_trace(
                source=source,
                request=request,
                candidate=candidate,
                confidence=confidence,
                probabilities=probabilities,
                request_sent=True,
            ),
        )

    candidate, confidence = fixture_next_placement(state)
    source = "local planner"
    return (
        candidate,
        confidence,
        {},
        source,
        _placement_trace(
            source=source,
            request=request,
            candidate=candidate,
            confidence=confidence,
            probabilities={},
            request_sent=False,
        ),
    )


def decision_trace_export(history: list[Mapping[str, Any]]) -> str:
    return json.dumps(
        {
            "format": "jev-tetris-decision-trace-v1",
            "decisions": history,
        },
        indent=2,
        ensure_ascii=False,
    )


def _record_decision_trace(
    history: list[dict[str, Any]],
    trace: dict[str, Any],
    state: Mapping[str, Any],
    mode: str,
) -> dict[str, Any]:
    recorded_trace = dict(trace)
    recorded_trace["sequence"] = len(history) + 1
    recorded_trace["mode"] = mode
    recorded_trace["application"] = {
        "verified": True,
        "locked": True,
        "pieces": state["pieces"],
        "score": state["score"],
        "lines": state["lines"],
        "last_lock": state["last_lock"],
    }
    history.append(recorded_trace)
    return recorded_trace


def apply_placement(state: dict[str, Any], placement: str | Mapping[str, Any]) -> None:
    if state["game_over"]:
        return
    placement_id = placement if isinstance(placement, str) else placement.get("id")
    candidate = next(
        (item for item in legal_placements(state) if item["id"] == placement_id),
        None,
    )
    if candidate is None:
        raise ValueError(f"Placement {placement_id!r} is not legal for the current board")

    state["rotation"] = candidate["rotation"]
    state["x"] = candidate["origin_x"]
    state["y"] = candidate["origin_y"]
    actual_cells = sorted(current_cells(state))
    expected_cells = sorted(tuple(cell) for cell in candidate["occupied_cells"])
    if actual_cells != expected_cells or not can_place(state):
        raise RuntimeError("Placement verification failed before locking the piece")

    state["last_plan"] = {
        "id": candidate["id"],
        "kind": state["kind"],
        "rotation": candidate["rotation_name"],
        "column": candidate["column"],
        "landing_row": candidate["landing_row"],
        "occupied_cells": candidate["occupied_cells"],
        "lines_cleared": candidate["lines_cleared"],
    }
    _lock_piece(state)
    state["last_event"] = (
        f"Placed {state['last_plan']['kind']} in rotation "
        f"{state['last_plan']['rotation']} at column {state['last_plan']['column']}."
    )


def _lock_piece(state: dict[str, Any]) -> None:
    locked_kind = state["kind"]
    locked_rotation = state["rotation"]
    locked_cells = current_cells(state)
    state["board"], lines_cleared = _lock_board(state["board"], locked_kind, locked_cells)
    state["lines"] += lines_cleared
    state["score"] += (0, 100, 300, 500, 800)[min(lines_cleared, 4)]
    state["pieces"] += 1
    state["last_lock"] = {
        "kind": locked_kind,
        "rotation": ROTATION_NAMES[locked_rotation % 4],
        "occupied_cells": [[x, y] for x, y in sorted(locked_cells)],
        "lines_cleared": lines_cleared,
    }
    _spawn_next_piece(state)
    state["last_event"] = f"Locked {locked_kind}; cleared {lines_cleared} line(s)."


def _spawn_next_piece(state: dict[str, Any]) -> None:
    _ensure_queue(state, 5)
    state["kind"] = state["queue"].pop(0)
    state["rotation"] = 0
    state["x"] = 3
    state["y"] = 0
    if not can_place(state):
        state["game_over"] = True


def render_tetris_app() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="tetris-kicker">JevExperiment / Tetris Lab</div>
            <div class="hero-row">
                <div>
                    <h1>Jev plays <span>Tetris.</span></h1>
                    <p>Fast typed judgment meets deterministic game physics.</p>
                </div>
                <div class="hero-signal">
                    <span class="signal-dot"></span> SYSTEM ONE<br>
                    <strong>PLACEMENT MODE</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 8% 0%, rgba(64, 87, 220, 0.18), transparent 32rem),
                radial-gradient(circle at 100% 8%, rgba(31, 213, 181, 0.1), transparent 28rem),
                #070a12;
        }
        [data-testid="stHeader"] { background: transparent; }
        .block-container {
            max-width: 1180px;
            padding-top: 2.7rem;
            padding-bottom: 4rem;
        }
        .hero { padding: 0.4rem 0 1.7rem; }
        .tetris-kicker {
            color: #66f6d2;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .hero-row {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 2rem;
        }
        .hero h1 {
            margin: 0.35rem 0 0.35rem;
            color: #f8fafc;
            font-size: clamp(2.7rem, 6vw, 4.7rem);
            line-height: 0.98;
            letter-spacing: -0.06em;
        }
        .hero h1 span { color: #66f6d2; }
        .hero p {
            margin: 0;
            color: #94a3b8;
            font-size: 1rem;
        }
        .hero-signal {
            min-width: 9.5rem;
            padding: 0.75rem 0.9rem;
            border: 1px solid rgba(102, 246, 210, 0.24);
            border-radius: 14px;
            color: #94a3b8;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.11em;
            line-height: 1.7;
            text-align: right;
        }
        .hero-signal strong { color: #e2e8f0; font-size: 0.68rem; }
        .signal-dot, .status-dot {
            display: inline-block;
            width: 0.45rem;
            height: 0.45rem;
            margin-right: 0.35rem;
            border-radius: 50%;
            background: #66f6d2;
            box-shadow: 0 0 12px rgba(102, 246, 210, 0.9);
        }
        .board-frame {
            width: max-content;
            padding: 0.9rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 22px;
            background: linear-gradient(145deg, rgba(22, 29, 51, 0.96), rgba(9, 13, 24, 0.98));
            box-shadow: 0 22px 70px rgba(0, 0, 0, 0.34), 0 0 60px rgba(45, 212, 191, 0.06);
        }
        .board-frame-top, .board-frame-bottom {
            display: flex;
            justify-content: space-between;
            gap: 2rem;
            color: #64748b;
            font-size: 0.62rem;
            font-weight: 800;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }
        .board-frame-top { padding: 0 0.15rem 0.7rem; color: #cbd5e1; }
        .board-frame-bottom { padding: 0.7rem 0.15rem 0.05rem; }
        .tetris-board {
            display: grid;
            grid-template-columns: repeat(10, 24px);
            gap: 3px;
            width: max-content;
            padding: 0.65rem;
            border: 1px solid rgba(71, 85, 105, 0.65);
            border-radius: 15px;
            background: #0b1221;
            box-shadow: inset 0 0 30px rgba(2, 6, 23, 0.8);
        }
        .tetris-cell {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            background: #172238;
            box-shadow: inset 0 0 0 1px rgba(71, 85, 105, 0.48);
        }
        .tetris-cell.filled { box-shadow: inset 0 0 0 2px rgba(255,255,255,0.28), 0 0 13px rgba(255,255,255,0.12); }
        .tetris-cell.ghost { opacity: 0.26; outline: 1px dashed rgba(226,232,240,0.8); filter: saturate(0.8); }
        .tetris-cell.line-clear {
            background: linear-gradient(135deg, #ffffff, #66f6d2 48%, #ffffff) !important;
            box-shadow: 0 0 20px rgba(255,255,255,0.95), inset 0 0 0 2px rgba(255,255,255,0.9);
            animation: lineClearPulse 120ms ease-in-out infinite alternate;
        }
        @keyframes lineClearPulse {
            from { filter: brightness(1); transform: scale(0.94); }
            to { filter: brightness(1.8); transform: scale(1.04); }
        }
        .tetris-cell.cyan { background: linear-gradient(135deg, #67e8f9, #0891b2); }
        .tetris-cell.yellow { background: linear-gradient(135deg, #fde047, #ca8a04); }
        .tetris-cell.purple { background: linear-gradient(135deg, #d8b4fe, #9333ea); }
        .tetris-cell.blue { background: linear-gradient(135deg, #93c5fd, #2563eb); }
        .tetris-cell.orange { background: linear-gradient(135deg, #fdba74, #ea580c); }
        .tetris-cell.green { background: linear-gradient(135deg, #86efac, #16a34a); }
        .tetris-cell.red { background: linear-gradient(135deg, #fca5a5, #dc2626); }
        .control-panel {
            padding: 1.15rem;
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 22px;
            background: rgba(15, 23, 42, 0.66);
            box-shadow: 0 22px 70px rgba(0, 0, 0, 0.2);
        }
        .panel-kicker, .stat-label, .card-label {
            color: #64748b;
            font-size: 0.62rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .stat-card {
            padding: 0.75rem 0.8rem;
            border: 1px solid rgba(148, 163, 184, 0.13);
            border-radius: 13px;
            background: rgba(2, 6, 23, 0.3);
        }
        .stat-value {
            display: block;
            margin-top: 0.18rem;
            color: #f8fafc;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.04em;
        }
        .active-card, .next-card {
            margin-top: 0.85rem;
            padding: 0.85rem 0.95rem;
            border: 1px solid rgba(148, 163, 184, 0.13);
            border-radius: 15px;
            background: rgba(2, 6, 23, 0.28);
        }
        .piece-line { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.55rem; color: #cbd5e1; font-size: 0.86rem; }
        .piece-chip, .next-piece {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            color: #fff;
            font-weight: 900;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.25), 0 0 14px rgba(255,255,255,0.08);
        }
        .piece-chip { width: 2rem; height: 2rem; }
        .next-piece { width: 1.8rem; height: 1.8rem; margin-right: 0.35rem; font-size: 0.75rem; }
        .piece-chip.cyan, .next-piece.cyan { background: #0891b2; }
        .piece-chip.yellow, .next-piece.yellow { background: #ca8a04; }
        .piece-chip.purple, .next-piece.purple { background: #9333ea; }
        .piece-chip.blue, .next-piece.blue { background: #2563eb; }
        .piece-chip.orange, .next-piece.orange { background: #ea580c; }
        .piece-chip.green, .next-piece.green { background: #16a34a; }
        .piece-chip.red, .next-piece.red { background: #dc2626; }
        .next-pieces { display: flex; align-items: center; margin-top: 0.65rem; }
        .microcopy { margin-top: 0.65rem; color: #64748b; font-size: 0.72rem; line-height: 1.5; }
        .animation-status { margin-top: 0.8rem; color: #94a3b8; font-size: 0.76rem; }
        .animation-status .signal-dot { width: 0.35rem; height: 0.35rem; }
        .decision-card {
            margin-top: 1rem;
            padding: 0.95rem 1rem;
            border: 1px solid rgba(102, 246, 210, 0.25);
            border-radius: 15px;
            background: linear-gradient(135deg, rgba(20, 71, 73, 0.28), rgba(15, 23, 42, 0.58));
        }
        .decision-card code { color: #66f6d2; }
        div.stButton > button {
            min-height: 2.65rem;
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.78);
            color: #e2e8f0;
            font-weight: 700;
            transition: all 120ms ease;
        }
        div.stButton > button:hover {
            border-color: rgba(102, 246, 210, 0.65);
            color: #66f6d2;
            transform: translateY(-1px);
        }
        div.stButton > button[kind="primary"],
        [data-testid="stBaseButton-primary"] {
            border-color: rgba(102, 246, 210, 0.7);
            background: linear-gradient(135deg, #66f6d2, #2dd4bf);
            color: #06231f;
            box-shadow: 0 0 22px rgba(45, 212, 191, 0.18);
        }
        div.stButton > button[kind="primary"]:hover,
        [data-testid="stBaseButton-primary"]:hover {
            border-color: #b9ffed;
            background: linear-gradient(135deg, #b9ffed, #66f6d2);
            color: #06231f;
        }
        div[data-testid="stAlert"] { border-radius: 14px; }
        .move-card {
            border: 1px solid rgba(102, 246, 210, 0.25);
            border-radius: 15px;
            padding: 0.95rem 1rem;
            background: linear-gradient(135deg, rgba(20, 71, 73, 0.28), rgba(15, 23, 42, 0.58));
        }
        .mode-card {
            margin-top: 1rem;
            padding: 0.85rem 0.95rem;
            border: 1px solid rgba(102, 246, 210, 0.16);
            border-radius: 15px;
            background: rgba(8, 47, 53, 0.2);
        }
        .mode-title { color: #e2e8f0; font-size: 0.86rem; font-weight: 800; }
        .mode-copy { margin-top: 0.25rem; color: #94a3b8; font-size: 0.72rem; line-height: 1.45; }
        .mode-caption { margin: 0.5rem 0 0.15rem; color: #64748b; font-size: 0.67rem; line-height: 1.4; }
        @media (max-width: 720px) {
            .hero-row { align-items: flex-start; flex-direction: column; gap: 1rem; }
            .hero-signal { text-align: left; }
            .board-frame { transform-origin: left top; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    render_tetris_controls()


@st.fragment(run_every="1s", key="tetris_game_loop")
def render_tetris_controls() -> None:
    if "tetris_state" not in st.session_state:
        st.session_state["tetris_state"] = new_game()
    if "tetris_trace_history" not in st.session_state:
        st.session_state["tetris_trace_history"] = []
    state = st.session_state["tetris_state"]

    if state["game_over"]:
        st.session_state["tetris_auto_play"] = False
    auto_running = bool(st.session_state.get("tetris_auto_play", False))

    if st.button("New game", key="tetris_new_game"):
        state = new_game()
        st.session_state["tetris_state"] = state
        st.session_state.pop("tetris_suggestion", None)
        st.session_state.pop("tetris_auto_error", None)
        st.session_state["tetris_trace_history"] = []
        st.session_state["tetris_auto_play"] = False
        auto_running = False

    board_column, control_column = st.columns([1.1, 0.9], gap="large")
    with board_column:
        board_view = st.empty()
        board_view.markdown(render_board(state), unsafe_allow_html=True)
        animation_status = st.empty()
        if state["game_over"]:
            st.error("Game over — start a new game.")
        else:
            controls = st.columns(4)
            for column, label, action in zip(
                controls,
                ("←", "↻", "→", "DROP"),
                ("left", "rotate", "right", "drop"),
            ):
                if column.button(
                    label,
                    key=f"tetris_{action}",
                    disabled=auto_running,
                ):
                    if action == "drop":
                        animate_drop(state, board_view, animation_status)
                    apply_move(state, action)
                    st.rerun(scope="fragment")
        animation_status.markdown(
            f'<div class="animation-status"><span class="signal-dot"></span>{state["last_event"]}</div>',
            unsafe_allow_html=True,
        )

    with control_column:
        st.markdown('<div class="panel-kicker">Control deck / live state</div>', unsafe_allow_html=True)
        score_column, lines_column, pieces_column = st.columns(3)
        for column, label, value in (
            (score_column, "Score", state["score"]),
            (lines_column, "Lines", state["lines"]),
            (pieces_column, "Pieces", state["pieces"]),
        ):
            column.markdown(
                f'<div class="stat-card"><span class="stat-label">{label}</span>'
                f'<span class="stat-value">{value}</span></div>',
                unsafe_allow_html=True,
            )

        active_kind = state["kind"]
        active_color = PIECE_COLORS[active_kind]
        active_rotation = ROTATION_NAMES[state["rotation"] % 4]
        st.markdown(
            f'<div class="active-card"><div class="card-label">Active piece</div>'
            f'<div class="piece-line"><span class="piece-chip {active_color}">{active_kind}</span>'
            f'<span>rotation <code>{active_rotation}</code> · origin '
            f'<code>({state["x"]}, {state["y"]})</code></span></div></div>',
            unsafe_allow_html=True,
        )
        upcoming = "".join(
            f'<span class="next-piece {PIECE_COLORS[kind]}">{kind}</span>'
            for kind in next_pieces(state, 5)
        )
        st.markdown(
            f'<div class="next-card"><div class="card-label">Next queue / five pieces</div>'
            f'<div class="next-pieces">{upcoming}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="microcopy">Columns 0–9 left-to-right · rows 0–19 top-to-bottom · '
            f'<strong>{len(legal_placements(state))}</strong> legal final placements</div>',
            unsafe_allow_html=True,
        )

        has_key = bool(os.getenv("TYPESAFE_API_KEY"))
        use_live = st.toggle(
            "Use live Jev",
            key="tetris_live",
            value=has_key,
            disabled=not has_key,
            help="Ask Jev to choose one verified placement. The key stays server-side.",
        )
        if has_key:
            st.markdown('<div class="microcopy"><span class="signal-dot"></span>Live Jev is available.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="microcopy">No key detected. Local planner is available.</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="mode-card"><div class="mode-title">Choose Jev\'s control mode</div>'
            '<div class="mode-copy">One move at a time for inspection, or let Jev keep playing until you pause.</div></div>',
            unsafe_allow_html=True,
        )
        ask_column, auto_column = st.columns(2, gap="small")
        with ask_column:
            ask_clicked = st.button(
                "Ask Jev for Placement",
                key="tetris_suggest",
                disabled=state["game_over"] or auto_running,
                use_container_width=True,
            )
        with auto_column:
            auto_clicked = st.button(
                "Pause Jev" if auto_running else "Jev Playing Tetris",
                key="tetris_auto",
                type="secondary" if auto_running else "primary",
                disabled=state["game_over"],
                use_container_width=True,
            )
        st.markdown(
            '<div class="mode-caption">Placement asks for one typed decision. Playing Tetris makes one '
            'verified decision per tick and stays responsive between moves.</div>',
            unsafe_allow_html=True,
        )

        auto_error = st.session_state.get("tetris_auto_error")
        if auto_error:
            st.error(auto_error)

        if auto_clicked:
            st.session_state["tetris_auto_play"] = not auto_running
            st.session_state.pop("tetris_auto_error", None)
            st.rerun(scope="fragment")

        if ask_clicked:
            try:
                candidate, confidence, probabilities, source, trace = choose_next_placement(
                    state,
                    use_live=use_live,
                )
                animate_placement(state, candidate, board_view, animation_status)
                apply_placement(state, candidate["id"])
                trace = _record_decision_trace(
                    st.session_state["tetris_trace_history"],
                    trace,
                    state,
                    "single",
                )
                st.session_state["tetris_suggestion"] = {
                    "source": source,
                    "candidate": candidate,
                    "confidence": confidence,
                    "probabilities": probabilities,
                    "trace": trace,
                }
                st.rerun(scope="fragment")
            except Exception as exc:
                st.error(f"Could not choose a placement: {exc}")

        if auto_running and not state["game_over"]:
            try:
                candidate, confidence, probabilities, source, trace = choose_next_placement(
                    state,
                    use_live=use_live,
                )
                animate_placement(state, candidate, board_view, animation_status)
                apply_placement(state, candidate["id"])
                trace = _record_decision_trace(
                    st.session_state["tetris_trace_history"],
                    trace,
                    state,
                    "automatic",
                )
                st.session_state["tetris_suggestion"] = {
                    "source": f"{source} · auto",
                    "candidate": candidate,
                    "confidence": confidence,
                    "probabilities": probabilities,
                    "trace": trace,
                }
            except Exception as exc:
                st.session_state["tetris_auto_play"] = False
                st.session_state["tetris_auto_error"] = f"Jev paused after an error: {exc}"

        suggestion = st.session_state.get("tetris_suggestion")
        if suggestion is not None:
            candidate = suggestion["candidate"]
            confidence = suggestion["confidence"]
            confidence_text = "" if confidence is None else f" · confidence {confidence:.0%}"
            st.markdown(
                f"<div class=\"decision-card\"><div class=\"card-label\">{suggestion['source']}</div>"
                f"Placed <code>{candidate['id']}</code>: "
                f"rotation <code>{candidate['rotation_name']}</code>, "
                f"column <code>{candidate['column']}</code>, "
                f"landing row <code>{candidate['landing_row']}</code>"
                f"{confidence_text}<br>"
                f"Cleared {candidate['lines_cleared']} line(s); "
                f"afterstate holes={candidate['features']['holes']}, "
                f"max height={candidate['features']['max_height']}, "
                f"bumpiness={candidate['features']['bumpiness']}.</div>",
                unsafe_allow_html=True,
            )
            probabilities = suggestion["probabilities"]
            if probabilities:
                alternatives = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]
                st.caption(
                    "Jev alternatives: "
                    + " · ".join(f"{label} {probability:.0%}" for label, probability in alternatives)
                )

        trace_history = st.session_state["tetris_trace_history"]
        if trace_history:
            latest_trace = trace_history[-1]
            request_label = "sent to Jev" if latest_trace["request_sent"] else "preview only — local planner"
            st.markdown(
                '<div class="panel-kicker">Decision trace</div>',
                unsafe_allow_html=True,
            )
            export_column, trace_info_column = st.columns([0.42, 0.58], gap="small")
            with export_column:
                st.download_button(
                    "Export JSON trace",
                    data=decision_trace_export(trace_history),
                    file_name="jev-tetris-decision-trace.json",
                    mime="application/json",
                    key="tetris_trace_download",
                    type="primary",
                    use_container_width=True,
                )
            with trace_info_column:
                st.caption(
                    f"{len(trace_history)} decision(s) · latest: {request_label}. "
                    "Export includes this game's full history."
                )
            with st.expander("View JSON input · state and question", expanded=False):
                st.json(latest_trace["request"], expanded=1)
            with st.expander("View JSON output · Jev response", expanded=True):
                st.json(latest_trace["response"], expanded=True)

        st.markdown(
            '<div class="microcopy">The ghost piece shows the collision-checked landing position. '
            'Jev selects the final placement; the engine verifies its exact cells before locking.</div>',
            unsafe_allow_html=True,
        )


def _board_with_piece(
    board: list[list[str | None]],
    kind: str,
    cells: list[tuple[int, int]],
) -> list[list[str | None]]:
    preview = [row[:] for row in board]
    for x, y in cells:
        if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
            preview[y][x] = kind
    return preview


def _show_animation_frame(
    board_view: Any,
    animation_status: Any,
    state: dict[str, Any],
    message: str,
    *,
    pose: tuple[str, int, int, int] | None = None,
    board: list[list[str | None]] | None = None,
    show_active: bool = True,
    flash_rows: set[int] | None = None,
    delay: float = 0.04,
) -> None:
    board_view.markdown(
        render_board(
            state,
            board=board,
            active_pose=pose,
            show_active=show_active,
            show_ghost=False,
            flash_rows=flash_rows,
        ),
        unsafe_allow_html=True,
    )
    animation_status.markdown(
        f'<div class="animation-status"><span class="signal-dot"></span>{message}</div>',
        unsafe_allow_html=True,
    )
    time.sleep(delay)


def _animation_path(
    state: dict[str, Any],
    candidate: Mapping[str, Any],
) -> list[tuple[int, int, int]]:
    kind = state["kind"]
    board = state["board"]
    start = (state["rotation"] % 4, state["x"], state["y"])
    goal = (candidate["rotation"], candidate["origin_x"], candidate["origin_y"])
    if start == goal:
        return [start]

    # Keep rotation in the setup phase so the animation never twists while falling.
    required_rotations = (goal[0] - start[0]) % 4
    start_key = (*start, False, 0)
    frontier = deque([start_key])
    previous: dict[
        tuple[int, int, int, bool, int], tuple[int, int, int, bool, int] | None
    ] = {start_key: None}
    while frontier:
        rotation, x, y, drop_started, rotation_steps = frontier.popleft()
        neighbors = [
            (rotation, x - 1, y, drop_started, rotation_steps),
            (rotation, x + 1, y, drop_started, rotation_steps),
            (rotation, x, y + 1, True, rotation_steps),
        ]
        if not drop_started and rotation_steps < required_rotations:
            next_rotation = (rotation + 1) % 4
            neighbors.extend(
                (next_rotation, x + kick_x, y - kick_y_up, False, rotation_steps + 1)
                for kick_x, kick_y_up in _kick_tests(kind, rotation, next_rotation)
            )
        for next_key in neighbors:
            if next_key in previous:
                continue
            next_r, next_x, next_y, _, _ = next_key
            if not can_place_on_board(board, kind, next_r, next_x, next_y):
                continue
            previous[next_key] = (rotation, x, y, drop_started, rotation_steps)
            if next_key[:3] == goal:
                path = [goal]
                current_key = next_key
                while current_key != start_key:
                    current_key = previous[current_key]
                    path.append(current_key[:3])
                return list(reversed(path))
            frontier.append(next_key)

    return [start, goal]


def _animate_line_clear(
    state: dict[str, Any],
    locked_board: list[list[str | None]],
    board_view: Any,
    animation_status: Any,
) -> None:
    full_rows = {
        row_index
        for row_index, row in enumerate(locked_board)
        if all(cell is not None for cell in row)
    }
    if not full_rows:
        return

    _show_animation_frame(
        board_view,
        animation_status,
        state,
        f"Clearing {len(full_rows)} line(s)…",
        board=locked_board,
        show_active=False,
        flash_rows=full_rows,
        delay=0.22,
    )
    cleared_board = [
        [None for _ in range(BOARD_WIDTH)] if row_index in full_rows else row[:]
        for row_index, row in enumerate(locked_board)
    ]
    _show_animation_frame(
        board_view,
        animation_status,
        state,
        "Lines cleared — settling the board…",
        board=cleared_board,
        show_active=False,
        delay=0.14,
    )


def animate_drop(state: dict[str, Any], board_view: Any, animation_status: Any) -> None:
    target_y = hard_drop_y(state)
    if target_y is None:
        return
    for y in range(state["y"], target_y + 1):
        _show_animation_frame(
            board_view,
            animation_status,
            state,
            f"Dropping {state['kind']}…",
            pose=(state["kind"], state["rotation"], state["x"], y),
            delay=0.025,
        )
    locked_board = _board_with_piece(
        state["board"],
        state["kind"],
        piece_cells(state["kind"], state["rotation"], state["x"], target_y),
    )
    _show_animation_frame(
        board_view,
        animation_status,
        state,
        "Locking piece…",
        board=locked_board,
        show_active=False,
        delay=0.16,
    )
    _animate_line_clear(state, locked_board, board_view, animation_status)


def animate_placement(
    state: dict[str, Any],
    candidate: Mapping[str, Any],
    board_view: Any,
    animation_status: Any,
) -> None:
    kind = state["kind"]
    label = candidate["id"]

    _show_animation_frame(
        board_view,
        animation_status,
        state,
        f"Jev chose {label}: rotating to {candidate['rotation_name']}, "
        f"moving to column {candidate['column']}…",
        pose=(kind, state["rotation"], state["x"], state["y"]),
        delay=0.1,
    )

    path = _animation_path(state, candidate)
    for previous_pose, next_pose in zip(path, path[1:]):
        previous_rotation, previous_x, previous_y = previous_pose
        rotation, x, y = next_pose
        if rotation != previous_rotation:
            message = f"Rotating {kind} to {ROTATION_NAMES[rotation]}…"
        elif x != previous_x:
            message = f"Moving to column {candidate['column']}…"
        else:
            message = f"Dropping to row {candidate['landing_row']}…"
        _show_animation_frame(
            board_view,
            animation_status,
            state,
            message,
            pose=(kind, rotation, x, y),
            delay=0.035,
        )

    locked_board = _board_with_piece(
        state["board"],
        kind,
        [tuple(cell) for cell in candidate["occupied_cells"]],
    )
    _show_animation_frame(
        board_view,
        animation_status,
        state,
        f"Locking {kind} at rotation {candidate['rotation_name']}, "
        f"column {candidate['column']}…",
        board=locked_board,
        show_active=False,
        delay=0.18,
    )
    _animate_line_clear(state, locked_board, board_view, animation_status)


def render_board(
    state: dict[str, Any],
    *,
    board: list[list[str | None]] | None = None,
    active_pose: tuple[str, int, int, int] | None = None,
    show_active: bool = True,
    show_ghost: bool = True,
    flash_rows: set[int] | None = None,
) -> str:
    visible_board = state["board"] if board is None else board
    flash_rows = flash_rows or set()
    if active_pose is None:
        active_kind = state["kind"]
        active_rotation = state["rotation"]
        active_x = state["x"]
        active_y = state["y"]
    else:
        active_kind, active_rotation, active_x, active_y = active_pose

    active_cells = (
        set(piece_cells(active_kind, active_rotation, active_x, active_y))
        if show_active
        else set()
    )
    ghost_y = (
        _drop_y_for_board(visible_board, active_kind, active_rotation, active_x, active_y)
        if show_active and show_ghost
        else None
    )
    ghost_cells = (
        set(piece_cells(active_kind, active_rotation, active_x, ghost_y))
        if ghost_y is not None and not state["game_over"]
        else set()
    )
    cells: list[str] = []
    for y, row in enumerate(visible_board):
        for x, locked_kind in enumerate(row):
            if (x, y) in active_cells:
                kind = active_kind
                extra_class = " filled"
            elif (x, y) in ghost_cells:
                kind = active_kind
                extra_class = " ghost"
            else:
                kind = locked_kind
                extra_class = " filled" if kind else ""
                if kind and y in flash_rows:
                    extra_class += " line-clear"
            color = PIECE_COLORS.get(kind, "")
            cells.append(f'<div class="tetris-cell {color}{extra_class}"></div>')
    return '<div class="tetris-board">' + "".join(cells) + '</div>'
