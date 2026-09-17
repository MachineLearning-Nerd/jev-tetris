import unittest

from tetris_game import (
    ACTIONS,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    PIECE_KINDS,
    apply_move,
    apply_placement,
    fixture_next_placement,
    game_state_for_jev,
    legal_placements,
    new_game,
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

    def test_local_planner_returns_a_verifiable_placement(self) -> None:
        state = new_game(seed=1)

        candidate, confidence = fixture_next_placement(state)
        apply_placement(state, candidate["id"])

        self.assertGreater(confidence, 0.0)
        self.assertEqual(state["last_plan"]["id"], candidate["id"])
        self.assertEqual(state["last_lock"]["occupied_cells"], candidate["occupied_cells"])
        self.assertEqual(state["pieces"], 1)

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_move(new_game(seed=1), "teleport")

    def test_old_manual_actions_remain_supported(self) -> None:
        self.assertEqual(set(ACTIONS), {"left", "right", "rotate", "drop"})


if __name__ == "__main__":
    unittest.main()
