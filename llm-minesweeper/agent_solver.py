import json
from typing import Any, Dict

from openai import OpenAI


class AgentSolver:
    """Uses a Large Language Model (via OpenAI-compatible API) to solve the
    Minesweeper board.
    """

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        """Initializes the AgentSolver with API credentials and model configurations.

        Args:
            api_key: The API key for the solver model.
            base_url: The base URL for the OpenAI-compatible endpoint.
            model_name: The name of the model to use (e.g. gpt-4o, gemini-2.5-flash).
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name: str = model_name

    def decide_move(self, board_state: Dict[str, Any]) -> Dict[str, Any]:
        """Formulates a move decision based on the board's JSON representation.

        Args:
            board_state: A dictionary containing the parsed board state and cell list.

        Returns:
            A dictionary containing the chosen action, target coordinates,
            and reasoning.
        """
        system_prompt = (
            "You are an expert Minesweeper Solver Agent. "
            "Your goal is to play and win Minesweeper on an Android device.\n"
            "You will be given a JSON representation of the screen and board state.\n\n"
            "Minesweeper Rules & Reasoning Guidelines:\n"
            "1. Each cell has an [x, y] coordinate representing its screen center, "
            "and a status: 'unrevealed', 'flagged', '0', or '1'-'8'.\n"
            "2. A revealed number N (1-8) indicates that exactly N "
            "of its 8 neighbors contain mines.\n"
            "3. If a cell with number N already has exactly N flagged neighbors, "
            "all other unrevealed neighbors are safe and should be DIGged.\n"
            "4. If a cell with number N has exactly N unrevealed + flagged "
            "neighbors, all those unrevealed neighbors must be mines "
            "and should be FLAGged.\n"
            "5. Look at adjacent cells to make logical deductions. "
            "Do not flag a cell unless you are 100% sure it contains a mine. "
            "Do not dig a cell unless you are 100% sure it is safe.\n"
            "6. If no 100% certain moves are possible in your current view:\n"
            "   - If 'zoom_level' is 'zoomed_in', execute 'ZOOM_OUT' "
            "to look at other parts of the board for safe moves.\n"
            "   - If 'zoom_level' is 'zoomed_out', choose 'ZOOM_IN' "
            "on a region with unrevealed cells to resolve them better, "
            "or make a calculated guess on the cell with the "
            "lowest mine probability.\n\n"
            "Action Space:\n"
            "- 'DIG': Tap a cell to reveal it. "
            "You must specify its exact [x, y] coordinates in 'target'.\n"
            "- 'FLAG': Toggle a flag on a cell. "
            "You must specify its exact [x, y] coordinates in 'target'.\n"
            "- 'ZOOM_IN': Simulate a pinch-out gesture to zoom in "
            "and see cells more clearly. Set 'target' to null.\n"
            "- 'ZOOM_OUT': Simulate a pinch-in gesture to zoom out "
            "and see more of the board. Set 'target' to null.\n"
            "- 'NEW_GAME': Tap the restart button or Smiley face "
            "to begin a new game. Set 'target' to the "
            "'new_game_button_center' coordinates.\n"
            "- 'CLOSE_AD': Tap the close button to dismiss an ad. "
            "Set 'target' to the 'close_ad_button_center' coordinates.\n\n"
            "Response Format:\n"
            "Your output must be a single valid JSON object. "
            "Do not wrap it in markdown block characters. "
            "Follow this schema:\n"
            "{\n"
            '  "rationale": "Detailed explanation of your logical deduction, '
            'referencing the cell numbers and coordinate math.",\n'
            '  "action": "DIG" | "FLAG" | "ZOOM_IN" | "ZOOM_OUT" '
            '| "NEW_GAME" | "CLOSE_AD",\n'
            '  "target": [x, y] // Must be the exact [x, y] center coordinate '
            "of the target cell/button, or null if action is ZOOM_IN or ZOOM_OUT\n"
            "}\n\n"
            "Example Output 1 (ZOOM_IN to start):\n"
            "{\n"
            "  \"rationale\": \"Game is currently at 'tap_to_begin' with no board cells provided, so we must start the game by tapping the only actionable element. The screen state does not include the button coordinates yet, so this agent must request zoom-in/initial view; however the only valid action without coordinates is ZOOM_IN to reveal the board UI. After that, coordinates for 'new_game' or a start button should become available.\",\n"
            '  "action": "ZOOM_IN",\n'
            '  "target": null\n'
            "}\n\n"
            "Example Output 2 (DIG a cell):\n"
            "{\n"
            '  "rationale": "The game is at the initial state \'tap_to_begin\' with only one unrevealed cell shown at center [500, 526]. With no numbers revealed yet, there are no logical deductions possible; we must start by digging this cell to obtain information.",\n'
            '  "action": "DIG",\n'
            '  "target": [500, 526]\n'
            "}\n\n"
            "Example Output 3 (ZOOM_OUT when no move found):\n"
            "{\n"
            "  \"rationale\": \"Zoomed in region shows numbers but the only clearly actionable constraint would be from an unrevealed cell's neighboring numbers. At (500,557) = 2, its neighbors are: (434,557)=unrevealed, (567,557)=1, (634,557)=1, (500,526)=1, (434,526)=1, (567,526)=1, (500,588)=2, (434,588)=1, (567,588)=unrevealed. There are 2 unrevealed neighbors among those (434,557) and (567,588), so the 2 would imply exactly those two are mines only if all other neighboring cells were not mines; but adjacent numbered cells already indicate those other neighbors' mine statuses are not fully determined from the visible info. No other revealed number has a satisfied 'N flags equals N' or 'N unrevealed equals N' condition that allows a 100% safe dig or a 100% certain flag right now. Since zoomed_in limits visibility and no forced move is available, zoom out to reveal more of the board for deterministic deductions.\",\n"
            '  "action": "ZOOM_OUT",\n'
            '  "target": null\n'
            "}"
        )

        user_prompt = (
            f"Here is the current game JSON state:\n"
            f"{json.dumps(board_state, indent=2)}\n\nDecide the next move."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Received empty response from solver agent.")

            # Strip markdown formatting if returned
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```json"):
                    clean_content = "\n".join(lines[1:-1])
                elif lines[0].startswith("```"):
                    clean_content = "\n".join(lines[1:-1])

            return json.loads(clean_content)
        except Exception as exc:
            print(f"Error getting decision from solver agent: {exc}")
            raise
