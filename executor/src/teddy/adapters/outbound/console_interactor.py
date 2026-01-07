import sys
from teddy.core.ports.outbound.user_interactor import UserInteractor


class ConsoleInteractorAdapter(UserInteractor):
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
