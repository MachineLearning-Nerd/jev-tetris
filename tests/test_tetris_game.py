import json
import unittest

from tetris_game import (
    ACTIONS,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    PIECE_KINDS,
    _animation_path,
    apply_move,
    apply_placement,
    can_place_on_board,
    choose_next_placement,
    fixture_next_placement,
    game_state_for_jev,
    decision_trace_export,
    jev_request_for_placement,
    legal_placements,
    new_game,
    render_board,
)


class TetrisGameTests(unittest.TestCase):
    def test_drop_locks_piece_and_spawns_next_piece(self) -> None:
        state = new_game(seed=1)
        first_piece = state["kind"]

        apply_move(state, "drop")

        self.assertEqual(state["pieces"], 1)
        self.assertEqual(state["last_lock"]["kind"], first_piece)
        self.assertTrue(any(first_piece in row for row in state["board"]))
        self.assertFalse(state["game_over"])

    def test_initial_sequence_is_a_seven_bag(self) -> None:
        state = new_game(seed=1)

        first_bag = [state["kind"], *state["queue"][:6]]

        self.assertCountEqual(first_bag, PIECE_KINDS)

    def test_rotation_uses_floor_kick(self) -> None:
        state = new_game(seed=1)
        state["kind"] = "T"
        state["rotation"] = 0
        state["x"] = 3
        state["y"] = 18

        apply_move(state, "rotate")

        self.assertEqual(state["rotation"], 1)
        self.assertLess(state["y"], 18)
        self.assertFalse(state["game_over"])

    def test_legal_placements_have_exact_coordinates_and_afterstates(self) -> None:
        state = new_game(seed=1)

        candidates = legal_placements(state)

        self.assertGreater(len(candidates), 10)
        self.assertEqual(
            [candidate["id"] for candidate in candidates],
            [f"p{index:02d}" for index in range(1, len(candidates) + 1)],
        )
        for candidate in candidates:
            self.assertEqual(len(candidate["occupied_cells"]), 4)
            self.assertTrue(
                all(
                    0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT
                    for x, y in candidate["occupied_cells"]
                )
            )
            self.assertEqual(len(candidate["afterstate"]), BOARD_HEIGHT)
            self.assertTrue(all(len(row) == BOARD_WIDTH for row in candidate["afterstate"]))
            self.assertIn("holes", candidate["features"])
            self.assertIn("next_best_score", candidate)

    def test_jev_state_exposes_one_atomic_placement_choice(self) -> None:
        state = new_game(seed=1)

        jev_state = game_state_for_jev(state)

        self.assertEqual(len(jev_state["board"]), BOARD_HEIGHT)
        self.assertTrue(all(len(row) == BOARD_WIDTH for row in jev_state["board"]))
        self.assertEqual(
            jev_state["allowed_placements"],
            [candidate["id"] for candidate in jev_state["legal_placements"]],
        )
        self.assertIn("rotation", jev_state["instruction"])
        self.assertEqual(jev_state["coordinate_system"]["columns"], "0 through 9, left to right")

    def test_jev_request_is_json_serializable(self) -> None:
        request = jev_request_for_placement(new_game(seed=1))

        json.dumps(request)
        self.assertEqual(request["questions"]["placement"]["type"], "Choice")
        self.assertEqual(
            set(request["questions"]["placement"]["criteria"]),
            set(request["state"]["allowed_placements"]),
        )

    def test_decision_trace_exports_request_and_response(self) -> None:
        state = new_game(seed=1)
        candidate, confidence, probabilities, source, trace = choose_next_placement(
            state,
            use_live=False,
        )

        exported = json.loads(decision_trace_export([trace]))
        decision = exported["decisions"][0]

        self.assertEqual(source, "local planner")
        self.assertEqual(decision["request"]["state"]["active_piece"]["kind"], state["kind"])
        self.assertFalse(decision["request_sent"])
        self.assertEqual(decision["response"]["placement"]["choice"], candidate["id"])
        self.assertEqual(decision["response"]["placement"]["confidence"], confidence)
        self.assertEqual(decision["response"]["placement"]["probabilities"], probabilities)

    def test_local_planner_returns_a_verifiable_placement(self) -> None:
        state = new_game(seed=1)

        candidate, confidence = fixture_next_placement(state)
        apply_placement(state, candidate["id"])

        self.assertGreater(confidence, 0.0)
        self.assertEqual(state["last_plan"]["id"], candidate["id"])
        self.assertEqual(state["last_lock"]["occupied_cells"], candidate["occupied_cells"])
        self.assertEqual(state["pieces"], 1)

    def test_placement_animation_path_stays_collision_checked(self) -> None:
        state = new_game(seed=1)

        for candidate in legal_placements(state):
            path = _animation_path(state, candidate)

            self.assertEqual(path[0], (state["rotation"], state["x"], state["y"]))
            self.assertEqual(
                path[-1],
                (candidate["rotation"], candidate["origin_x"], candidate["origin_y"]),
            )
            self.assertTrue(
                all(
                    can_place_on_board(state["board"], state["kind"], rotation, x, y)
                    for rotation, x, y in path
                )
            )

    def test_placement_animation_does_not_rotate_after_the_drop_starts(self) -> None:
        state = new_game(seed=1)

        for candidate in legal_placements(state):
            path = _animation_path(state, candidate)
            drop_started = False
            rotation_steps = 0
            for previous_pose, next_pose in zip(path, path[1:]):
                previous_rotation, _, previous_y = previous_pose
                rotation, _, next_y = next_pose
                if rotation != previous_rotation:
                    rotation_steps += 1
                if rotation == previous_rotation and next_y > previous_y:
                    drop_started = True
                if drop_started:
                    self.assertEqual(rotation, previous_rotation)
            self.assertLessEqual(
                rotation_steps,
                (candidate["rotation"] - state["rotation"]) % 4,
            )

    def test_line_clear_animation_marks_every_cell_in_a_full_row(self) -> None:
        state = new_game(seed=1)
        board = [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        board[-1] = ["I" for _ in range(BOARD_WIDTH)]

        rendered = render_board(
            state,
            board=board,
            show_active=False,
            flash_rows={BOARD_HEIGHT - 1},
        )

        self.assertEqual(rendered.count("line-clear"), BOARD_WIDTH)

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_move(new_game(seed=1), "teleport")

    def test_old_manual_actions_remain_supported(self) -> None:
        self.assertEqual(set(ACTIONS), {"left", "right", "rotate", "drop"})


if __name__ == "__main__":
    unittest.main()
