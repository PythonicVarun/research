import base64
from pathlib import Path
from typing import Any, Dict, List, cast
from openai import OpenAI


class SingleModelSolver:
    """Uses a single vision-capable LLM (Gemini 3.1 Pro via OpenAI API) to play Minesweeper using tool calling."""

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        """Initializes the solver with client config, minimal prompts, and tool definitions.

        Args:
            api_key: The API key to access the model.
            base_url: The base URL of the OpenAI compatible API endpoint.
            model_name: The name of the LLM to use.
        """
        self.client: OpenAI = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name: str = model_name
        self.messages: List[Dict[str, Any]] = []

        self.system_prompt: str = (
            "You are playing Minesweeper on an Android screen.\n"
            "Analyze the current grid-overlaid screenshot and use your tools to play the game.\n"
            "If you win or lose the game, do not call any more tools and output a message explaining the final result."
        )

        self.tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "tap",
                    "description": "Tap at screen coordinates (x, y).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "The X coordinate in pixels."},
                            "y": {"type": "integer", "description": "The Y coordinate in pixels."}
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "long_press",
                    "description": "Long press at screen coordinates (x, y) for duration_ms.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "The X coordinate in pixels."},
                            "y": {"type": "integer", "description": "The Y coordinate in pixels."},
                            "duration_ms": {"type": "integer", "description": "Duration of press in milliseconds.", "default": 500}
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_in",
                    "description": "Zoom in on the board.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_out",
                    "description": "Zoom out on the board.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]

    def _encode_image(self, image_path: Path) -> str:
        """Encodes an image to a base64 string.

        Args:
            image_path: Path to the image file.

        Returns:
            The base64 encoded image string.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def start_game(self, image_path: Path) -> None:
        """Initializes the chat history with the system prompt and the starting screenshot.

        Args:
            image_path: Path to the initial screenshot.
        """
        base64_image = self._encode_image(image_path)
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is the starting screen of the game. Choose your first move."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]

    def get_next_action(self) -> Dict[str, Any]:
        """Requests the next action from the model and appends the assistant response to the message history.

        Returns:
            A dictionary representation of the assistant's message.
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=cast(Any, self.messages),
            tools=cast(Any, self.tools),
            tool_choice="auto"
        )
        assistant_message = response.choices[0].message

        msg_dict: Dict[str, Any] = {
            "role": "assistant"
        }
        if assistant_message.content is not None:
            msg_dict["content"] = assistant_message.content
        if assistant_message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name, # type: ignore[missing-attribute]
                        "arguments": tc.function.arguments # type: ignore[missing-attribute]
                    }
                }
                for tc in assistant_message.tool_calls
            ]

        self.messages.append(msg_dict)
        return msg_dict

    def add_tool_result(self, tool_call_id: str, tool_name: str, result_content: str) -> None:
        """Appends the tool output message to the message history.

        Args:
            tool_call_id: The ID of the tool call.
            tool_name: The name of the tool function.
            result_content: The result content string of the tool execution.
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result_content
        })

    def add_new_screenshot(self, image_path: Path) -> None:
        """Appends the new screenshot to the message history and prunes previous screenshots.

        Args:
            image_path: Path to the new screenshot.
        """
        base64_image = self._encode_image(image_path)
        self.messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "Here is the new screen state after executing your action."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                }
            ]
        })
        self._prune_history()

    def _prune_history(self) -> None:
        """Prunes previous screenshots from the message history to minimize context size."""
        # Find the index of the last user message
        last_user_idx = -1
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i]["role"] == "user":
                last_user_idx = i
                break

        # Convert all other user messages to text-only placeholders
        for i, msg in enumerate(self.messages):
            if msg["role"] == "user" and i != last_user_idx:
                if isinstance(msg["content"], list):
                    msg["content"] = "Here is the screen state at this step. [Previous screenshot grid omitted to optimize context]"
