import base64
import json
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI


class SingleModelSolver:
    """Uses a single vision-capable LLM (Gemini 3.1 Pro via OpenAI API) to both parse board state and decide on moves."""

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        """Initializes the SingleModelSolver with credentials and model.

        Args:
            api_key: API key for the model.
            base_url: Base URL for the OpenAI-compatible endpoint.
            model_name: Model name (e.g. gemini-3.1-pro-preview).
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name: str = model_name

    def _encode_image(self, image_path: Path) -> str:
        """Encodes an image to a base64 string.

        Args:
            image_path: Path to the image file.

        Returns:
            The base64 encoded string.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def solve(self, image_path: Path) -> Dict[str, Any]:
        """Analyzes a screenshot and decides on the next move.

        Args:
            image_path: Path to the screenshot file with grid overlay.

        Returns:
            A dictionary containing the state and chosen action details.
        """
        base64_image = self._encode_image(image_path)

        system_prompt = (
            "You are an expert Minesweeper Solver Agent. Your task is to analyze a screenshot of a Minesweeper game played on an Android device "
            "and output a single JSON object containing both your state assessment and your next move decision.\n\n"
            "The screenshot has a red coordinate grid overlay. Use the labels on the borders (X-axis at top/bottom, Y-axis at left/right) "
            "and the crosshair coordinate markers (e.g. '200,400') plotted on the screen to deduce the exact pixel coordinates [x, y] of cells and buttons.\n\n"
            "Minesweeper Rules & Reasoning:\n"
            "1. A revealed number N (1-8) indicates that exactly N of its 8 neighbors contain mines.\n"
            "2. If N already has N flagged neighbors, all other unrevealed neighbors are safe and should be DIGged.\n"
            "3. If N has N unrevealed + flagged neighbors, all those unrevealed neighbors are mines and should be FLAGged.\n"
            "4. Analyze the numbers on the board carefully. Do not flag a cell unless you are 100% sure it is a mine. Do not dig unless you are 100% sure it is safe.\n"
            "5. If no 100% safe move exists in your view:\n"
            "   - If 'zoom_level' is 'zoomed_in', execute 'ZOOM_OUT' to see more cells.\n"
            "   - If 'zoom_level' is 'zoomed_out', execute 'ZOOM_IN' on an unrevealed area to resolve details, or make a calculated guess.\n\n"
            "Response Schema:\n"
            "Your output must be a single valid JSON object. Do not wrap it in markdown block characters. Follow this schema exactly:\n"
            "{\n"
            '  "rationale": "Detailed explanation of your logical deduction, referencing the cell numbers and coordinate calculations.",\n'
            '  "game_state": "menu" | "playing" | "won" | "lost" | "ad" | "tap_to_begin",\n'
            '  "zoom_level": "zoomed_in" | "zoomed_out" | "unknown",\n'
            '  "current_mode": "dig" | "flag" | "unknown", // The mode currently selected at the bottom toggle button (usually highlighted in blue)\n'
            '  "action": "DIG" | "FLAG" | "ZOOM_IN" | "ZOOM_OUT" | "NEW_GAME" | "CLOSE_AD",\n'
            '  "target": [x, y] // Exact coordinates of the target cell/button to tap. Must be null for ZOOM_IN or ZOOM_OUT\n'
            '  "new_game_button_center": [x, y], // Coordinates of restart/smiley/new game button if visible, else null\n'
            '  "close_ad_button_center": [x, y]  // Coordinates of skip/close ad button if visible, else null\n'
            "}\n\n"
            "Example 1 (Starting the Game):\n"
            "{\n"
            '  "rationale": "The game is at \'tap_to_begin\' with no cells revealed yet. Tapping is required to start. We will Zoom In to see individual cells clearly.",\n'
            '  "game_state": "tap_to_begin",\n'
            '  "zoom_level": "unknown",\n'
            '  "current_mode": "unknown",\n'
            '  "action": "ZOOM_IN",\n'
            '  "target": null,\n'
            '  "new_game_button_center": null,\n'
            '  "close_ad_button_center": null\n'
            "}\n\n"
            "Example 2 (Safe DIG Move):\n"
            "{\n"
            '  "rationale": "The cell at [500, 1080] is \'1\' and already has a flagged neighbor at [500, 1370]. Its other unrevealed neighbor at [790, 1370] is safe to reveal.",\n'
            '  "game_state": "playing",\n'
            '  "zoom_level": "zoomed_in",\n'
            '  "current_mode": "dig",\n'
            '  "action": "DIG",\n'
            '  "target": [790, 1370],\n'
            '  "new_game_button_center": null,\n'
            '  "close_ad_button_center": null\n'
            "}\n\n"
            "Example 3 (Safe FLAG Move):\n"
            "{\n"
            '  "rationale": "The cell at [500, 1080] is \'1\' and has only one unrevealed neighbor at [500, 1370] and no flagged neighbors. Therefore, [500, 1370] must be a mine.",\n'
            '  "game_state": "playing",\n'
            '  "zoom_level": "zoomed_in",\n'
            '  "current_mode": "dig",\n'
            '  "action": "FLAG",\n'
            '  "target": [500, 1370],\n'
            '  "new_game_button_center": null,\n'
            '  "close_ad_button_center": null\n'
            "}"
        )

        user_prompt = "Analyze the attached screenshot and decide the next move. Output the result in the specified JSON format."

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Received empty response from solver model.")

            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```json"):
                    clean_content = "\n".join(lines[1:-1])
                elif lines[0].startswith("```"):
                    clean_content = "\n".join(lines[1:-1])

            return json.loads(clean_content)
        except Exception as exc:
            print(f"Error executing solver: {exc}")
            raise
