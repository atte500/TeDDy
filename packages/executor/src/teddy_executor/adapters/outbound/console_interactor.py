import sys

from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class ConsoleInteractorAdapter(IUserInteractor):
    def ask_question(self, prompt: str) -> str:
        """
        Presents a prompt to the user on the console and captures their input.
        Input is terminated by a single empty line on stdin.
        """
        # Print prompt to stderr so it doesn't interfere with stdout scraping in tests
        print(prompt, file=sys.stderr, flush=True)

        lines = []
        while True:
            try:
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    def confirm_action(
        self, action: ActionData, action_prompt: str
    ) -> tuple[bool, str]:
        try:
            prompt = f"{action_prompt}\nApprove? (y/n): "
            # Use stderr for prompts to not pollute stdout
            print(prompt, file=sys.stderr, flush=True, end="")
            response = input().lower().strip()

            if response.startswith("y"):
                return True, ""

            reason_prompt = "Reason for skipping (optional): "
            print(reason_prompt, file=sys.stderr, flush=True, end="")
            reason = input().strip()
            return False, reason
        except EOFError:
            # If input stream is closed (e.g., in non-interactive script),
            # default to denying the action.
            print("\n", file=sys.stderr, flush=True)  # Ensure a newline after prompt
            return False, "Skipped due to non-interactive session."
