import unittest

from courtroom import Evaluation, route_decision


def evaluation(
    *,
    task_completed: float,
    permission_breach: float,
    false_success: float,
    customer_satisfied: float,
    review_priority: float,
    confidence: float = 0.9,
) -> Evaluation:
    return Evaluation(
        source="test",
        nouls={
            "task_completed": task_completed,
            "permission_breach": permission_breach,
            "false_success": false_success,
            "customer_satisfied": customer_satisfied,
        },
        scores={"review_priority": review_priority},
        choices={},
        probabilities={},
        confidence={"review_priority": confidence},
        raw={},
    )


class RouteDecisionTests(unittest.TestCase):
    def test_permission_breach_pages_on_call(self) -> None:
        decision = route_decision(
            evaluation(
                task_completed=0.8,
                permission_breach=0.9,
                false_success=0.1,
                customer_satisfied=0.4,
                review_priority=2.8,
            )
        )

        self.assertEqual(decision.action, "page_on_call")

    def test_false_success_files_bug(self) -> None:
        decision = route_decision(
            evaluation(
                task_completed=0.1,
                permission_breach=0.1,
                false_success=0.9,
                customer_satisfied=0.1,
                review_priority=2.4,
            )
        )

        self.assertEqual(decision.action, "file_bug")

    def test_unresolved_user_gets_human_review(self) -> None:
        decision = route_decision(
            evaluation(
                task_completed=0.3,
                permission_breach=0.1,
                false_success=0.1,
                customer_satisfied=0.2,
                review_priority=1.0,
            )
        )

        self.assertEqual(decision.action, "human_review")

    def test_clean_run_auto_closes(self) -> None:
        decision = route_decision(
            evaluation(
                task_completed=0.98,
                permission_breach=0.01,
                false_success=0.01,
                customer_satisfied=0.98,
                review_priority=0.1,
            )
        )

        self.assertEqual(decision.action, "auto_close")

    def test_uncertain_priority_is_reviewed(self) -> None:
        decision = route_decision(
            evaluation(
                task_completed=0.9,
                permission_breach=0.1,
                false_success=0.1,
                customer_satisfied=0.9,
                review_priority=0.3,
                confidence=0.4,
            )
        )

        self.assertEqual(decision.action, "human_review")


if __name__ == "__main__":
    unittest.main()
