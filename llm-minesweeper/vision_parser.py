import base64
import json
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI


class VisionParser:
    """Uses Gemini 3.1 Pro (via OpenAI-compatible API) to convert screenshots
    into JSON game state data.
    """

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        """Initializes the VisionParser with API credentials and model configurations.

        Args:
            api_key: The API key for the vision model.
            base_url: The base URL for the OpenAI-compatible endpoint.
            model_name: The name of the model to use (e.g. gemini-3.1-pro-preview).
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name: str = model_name

    def _encode_image(self, image_path: Path) -> str:
        """Encodes a local image file into a base64 string.

        Args:
            image_path: Path to the image file.

        Returns:
            The base64 encoded string of the image.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Screenshot file not found: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def parse_screenshot(self, image_path: Path) -> Dict[str, Any]:
        """Sends a screenshot to the vision model and parses the JSON representation.

        Args:
            image_path: Path to the screenshot file.

        Returns:
            A dictionary containing the parsed game state.
        """
        base64_image = self._encode_image(image_path)

        system_prompt = (
            "You are a computer vision assistant specializing in parsing "
            "screenshots of a Minesweeper game played on an Android device. "
            "Your output must be a single, valid JSON object containing "
            "structural board data and metadata. "
            "Do not include any markdown styling, conversational text, or "
            "wrapper block characters in your response. "
            "Here is the schema you must strictly follow:\n"
            "{\n"
            '  "game_state": "menu" | "playing" | "won" | "lost" '
            '| "ad" | "tap_to_begin",\n'
            '  "zoom_level": "zoomed_in" | "zoomed_out" | "unknown",\n'
            '  "current_mode": "dig" | "flag" | "unknown",\n'
            '  "toggle_button_center": [x, y], // The coordinate to toggle '
            "between dig and flag modes (usually at the bottom center)\n"
            '  "new_game_button_center": [x, y], // Location of "New Game" or '
            "Smiley restart button if visible\n"
            '  "close_ad_button_center": [x, y], // Location of close/skip button '
            "if an ad is displayed, otherwise null\n"
            '  "cells": [\n'
            "    {\n"
            '      "center": [x, y], // Exact screen coordinate in pixels to '
            "tap this cell\n"
            '      "status": "unrevealed" | "flagged" | "0" | "1" | "2" | "3" | '
            '"4" | "5" | "6" | "7" | "8" | "mine" | "exploded_mine",\n'
            '      "row": int, // Grid row index (topmost visible row is 0)\n'
            '      "col": int  // Grid column index (leftmost visible column is 0)\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Key Parsing Guidelines:\n"
            "1. Cell coordinates: Return the exact center [x, y] of each "
            "square cell in pixels.\n"
            "2. Grid row/col indices: Deduced from the regular spacing of "
            "cells. If zoomed in, assign relative coordinates starting at 0 "
            "for topmost/leftmost visible cell.\n"
            "3. Status classification:\n"
            "   - 'unrevealed': A solid blue or gray unclicked square.\n"
            "   - 'flagged': A square with a flag icon on it.\n"
            "   - '0': A completely flat, revealed cell with no numbers.\n"
            "   - '1'-'8': A revealed cell showing a number indicating "
            "adjacent mines.\n"
            "   - 'mine': An unexploded mine revealed at the end of the game.\n"
            "   - 'exploded_mine': A mine with a red background indicating "
            "the fatal click.\n"
            "4. Current Mode: Look at the toggle control at the bottom. "
            "Identify if the active mode is 'dig' (usually showing a shovel "
            "or dig icon highlighted) or 'flag' (showing a flag icon highlighted).\n"
            "5. Zoom level: If the cells appear very small and the entire "
            "grid is visible, it is 'zoomed_out'. If the cells are large "
            "and only a subset of the grid fits on the screen, it is 'zoomed_in'.\n"
            "6. Advertisement detection: If the screen is showing an ad "
            "(common after starting new games in free apps), identify "
            "'game_state' as 'ad' and locate the close or 'skip video' "
            "button coordinates so the system can close it.\n\n"
            "Example Output 1 (Initial Tap to Begin State):\n"
            "{\n"
            '  "game_state": "tap_to_begin",\n'
            '  "zoom_level": "unknown",\n'
            '  "current_mode": "unknown",\n'
            '  "toggle_button_center": null,\n'
            '  "new_game_button_center": null,\n'
            '  "close_ad_button_center": null,\n'
            '  "cells": [\n'
            "    {\n"
            '      "center": [500, 526],\n'
            '      "status": "unrevealed",\n'
            '      "row": 0,\n'
            '      "col": 0\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Example Output 2 (Active Game Play State):\n"
            "{\n"
            '  "game_state": "playing",\n'
            '  "zoom_level": "zoomed_in",\n'
            '  "current_mode": "flag",\n'
            '  "toggle_button_center": [570, 882],\n'
            '  "new_game_button_center": [499, 61],\n'
            '  "close_ad_button_center": null,\n'
            '  "cells": [\n'
            "    {\n"
            '      "center": [234, 403],\n'
            '      "status": "1",\n'
            '      "row": 0,\n'
            '      "col": 0\n'
            "    },\n"
            "    {\n"
            '      "center": [300, 403],\n'
            '      "status": "unrevealed",\n'
            '      "row": 0,\n'
            '      "col": 1\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            "Parse the attached screenshot of the Minesweeper Android "
            "application according to the system rules and return the "
            "JSON data."
        )

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
                raise ValueError("Received empty response from vision model.")

            # Strip markdown code block wrappers if model ignores the system
            # prompt formatting directive
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```json"):
                    clean_content = "\n".join(lines[1:-1])
                elif lines[0].startswith("```"):
                    clean_content = "\n".join(lines[1:-1])

            return json.loads(clean_content)
        except Exception as exc:
            print(f"Error parsing screenshot with vision model: {exc}")
            raise
