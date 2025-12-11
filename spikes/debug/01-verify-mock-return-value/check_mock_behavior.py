from unittest.mock import MagicMock, Mock


# 1. Define dummy classes to simulate the real ones
class ActionFactory:
    def create_action(self, action_type: str, params: dict):
        # In real life, this would return a dataclass instance
        pass


class PlanService:
    def __init__(self, action_factory: ActionFactory):
        self.action_factory = action_factory

    def execute(self, parsed_actions: list):
        actions = [
            self.action_factory.create_action(
                action_type=item["action"], params=item.get("params", {})
            )
            for item in parsed_actions
        ]

        print(f"Type of object returned by factory: {type(actions[0])}")

        for action in actions:
            # This is the crucial check that fails in the real code
            if action.action_type == "execute":
                print("Dispatch logic for 'execute' would run here.")
            else:
                print("Dispatch logic for 'execute' was SKIPPED.")
                # We can prove the attribute doesn't exist
                try:
                    _ = action.action_type
                except AttributeError as e:
                    print(f"Caught expected error: {e}")


# 2. Recreate the test scenario
print("--- SCENARIO 1: The Failing Case (Unconfigured Mock) ---")
mock_action_factory = MagicMock(spec=ActionFactory)
plan_service = PlanService(action_factory=mock_action_factory)

parsed_actions = [{"action": "execute", "params": {"command": "echo"}}]
plan_service.execute(parsed_actions)

print("\n--- SCENARIO 2: The Correct Case (Configured Mock) ---")
# To fix this, we need to tell the mock what to return.
# We can use another mock or a simple object. A Mock is cleaner.
configured_return_action = Mock()
configured_return_action.action_type = "execute"
configured_return_action.params = {"command": "echo"}

mock_action_factory_fixed = MagicMock(spec=ActionFactory)
mock_action_factory_fixed.create_action.return_value = configured_return_action

plan_service_fixed = PlanService(action_factory=mock_action_factory_fixed)
plan_service_fixed.execute(parsed_actions)
