import re
import yaml

from teddy_executor.core.domain.models import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError


class YamlPlanParser(IPlanParser):
    """
    A service responsible for parsing a YAML plan string into a structured domain object.
    """

    def parse(self, plan_content: str) -> Plan:
        """
        Reads and parses the specified YAML plan string.
        """
        if not plan_content.strip():
            raise InvalidPlanError("Plan content cannot be empty.")

        # Pre-process to handle unquoted colons in single-line command values,
        # which is a common issue with git commands.
        processed_lines = []
        for line in plan_content.splitlines():
            # This more specific regex looks for the key 'command', a colon, and a value
            # that is not quoted and contains a colon.
            match = re.match(r"^(?P<key>\s*command:\s*)(?P<value>[^\"'].*:.*)$", line)
            if match:
                parts = match.groupdict()
                # Use double quotes for safety with backslashes, and escape internal quotes.
                value = parts["value"].strip().replace('"', '\\"')
                processed_lines.append(f'{parts["key"]}"{value}"')
            else:
                processed_lines.append(line)
        processed_content = "\n".join(processed_lines)

        try:
            parsed_yaml = yaml.safe_load(processed_content)
        except yaml.YAMLError as e:
            raise InvalidPlanError(f"Plan contains invalid YAML: {e}")

        actions_data = []
        raw_actions = []

        if isinstance(parsed_yaml, dict) and "actions" in parsed_yaml:
            raw_actions = parsed_yaml["actions"]
            if not isinstance(raw_actions, list):
                raise InvalidPlanError("'actions' key must contain a list.")
        elif isinstance(parsed_yaml, list):
            raw_actions = parsed_yaml
        else:
            raise InvalidPlanError(
                "Plan must be a list of actions or a dictionary with an 'actions' key."
            )

        for action_dict in raw_actions:
            if not isinstance(action_dict, dict):
                raise InvalidPlanError(
                    f"Action item is not a dictionary: {action_dict}"
                )
            action_type = action_dict.get("type") or action_dict.get("action")
            if not action_type:
                raise InvalidPlanError(
                    f"Action is missing a 'type' or 'action' key: {action_dict}"
                )

            description = action_dict.get("description")

            if "params" in action_dict:
                action_params = action_dict["params"]
            else:
                action_params = action_dict.copy()
                action_params.pop("action", None)
                action_params.pop("type", None)
                action_params.pop("description", None)

            actions_data.append(
                ActionData(
                    type=action_type, params=action_params, description=description
                )
            )

        if not actions_data:
            raise InvalidPlanError("Plan must contain at least one action.")

        return Plan(title="YAML Plan", actions=actions_data)
