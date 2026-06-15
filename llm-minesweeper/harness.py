import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv

from adb_device import ADBDevice
from image_utils import add_coordinate_grid
from single_solver import SingleModelSolver


def execute_tool_action(device: ADBDevice, name: str, args: dict) -> str:
    """Executes a single tool action on the device.

    Args:
        device: Connected ADBDevice.
        name: Name of the tool.
        args: Arguments dict for the tool.

    Returns:
        A string message indicating the result of execution.
    """
    try:
        if name == "tap":
            x, y = args["x"], args["y"]
            device.tap(x, y)
            return f"Successfully tapped coordinate ({x}, {y})."
        elif name == "long_press":
            x, y = args["x"], args["y"]
            duration = args.get("duration_ms", 500)
            device.long_press(x, y, duration)
            return f"Successfully long-pressed coordinate ({x}, {y}) for {duration}ms."
        elif name == "zoom_in":
            device.zoom_in()
            return "Successfully zoomed in."
        elif name == "zoom_out":
            device.zoom_out()
            return "Successfully zoomed out."
        else:
            return f"Error: Unknown tool name '{name}'."
    except Exception as exc:
        print(f"Action execution failed for {name} with args {args}: {exc}")
        return f"Error executing tool {name}: {exc}"


def run_benchmark(max_steps: int = 50) -> None:
    """Runs the Minesweeper benchmark loop using the tool-calling architecture.

    Args:
        max_steps: The maximum number of actions the agent is allowed to take.
    """
    # 1. Load Environment Settings
    load_dotenv()

    vision_api_key = os.getenv("VISION_API_KEY")
    vision_base_url = os.getenv("VISION_BASE_URL")
    vision_model = os.getenv("VISION_MODEL")
    device_serial = os.getenv("ADB_DEVICE_SERIAL")

    # Validate configuration
    missing_vars = []
    if not vision_api_key:
        missing_vars.append("VISION_API_KEY")
    if not vision_base_url:
        missing_vars.append("VISION_BASE_URL")
    if not vision_model:
        missing_vars.append("VISION_MODEL")

    if missing_vars:
        raise ValueError(
            f"Missing required configuration variables in environment: {', '.join(missing_vars)}. "
            "Please create a .env file based on .env.example and fill in your API details."
        )

    # 2. Setup Logging Directories
    runs_dir = Path("./runs")
    run_id = f"run_{int(time.time())}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"Starting Tool-Calling Minesweeper Benchmark Loop (Run ID: {run_id})")
    print(f"Vision/Solver Model: {vision_model}")
    print(f"Audit Trail Directory: {run_dir}")
    print("=" * 60)

    # 3. Initialize Connections
    device = ADBDevice(serial=device_serial if device_serial else None)
    solver = SingleModelSolver(api_key=vision_api_key, base_url=vision_base_url, model_name=vision_model)

    print("\nDevice connected. Launching initial screenshot capture...")

    # 4. Capture Initial Screen
    screenshot_path = device.take_screenshot(run_dir)
    step_screenshot_path = run_dir / "step_0_screenshot.png"
    screenshot_path.rename(step_screenshot_path)

    # Generate grid overlay
    step_screenshot_grid_path = add_coordinate_grid(step_screenshot_path)
    print(f"Initial screenshot grid saved to: {step_screenshot_grid_path.name}")

    # Start the solver's session
    solver.start_game(step_screenshot_grid_path)

    step = 0
    consecutive_errors = 0
    max_consecutive_errors = 3

    while step < max_steps:
        print(f"\n--- Step {step + 1} / {max_steps} ---")
        try:
            # Request next action from solver
            print("Requesting next action from Solver Agent...")
            action_dict = solver.get_next_action()

            # Log the current message history state
            messages_json_path = run_dir / f"step_{step}_messages.json"
            messages_json_path.write_text(json.dumps(solver.messages, indent=2))

            tool_calls = action_dict.get("tool_calls")

            # If no tool calls, it means the model didn't call any tools (wins, loses, or outputs text)
            if not tool_calls:
                print("\nSolver Agent chose not to call any tools (game over or stop requested).")
                print(f"Final response: {action_dict.get('content')}")
                break

            # Execute tool calls
            for tool_call in tool_calls:
                tc_id = tool_call["id"]
                name = tool_call["function"]["name"]
                args_str = tool_call["function"]["arguments"]

                try:
                    args = json.loads(args_str)
                except Exception as e:
                    error_msg = f"Error parsing arguments JSON: {e}"
                    print(f"Tool arg parse error: {error_msg}")
                    solver.add_tool_result(tc_id, name, error_msg)
                    continue

                print(f"Solver calls: {name}({args})")
                result_str = execute_tool_action(device, name, args)
                print(f"Result: {result_str}")

                solver.add_tool_result(tc_id, name, result_str)

            # Let the device render and animation play
            print("Waiting for game updates (2.0s)...")
            time.sleep(2.0)

            # Capture new screenshot for next step
            screenshot_path = device.take_screenshot(run_dir)
            step_screenshot_path = run_dir / f"step_{step + 1}_screenshot.png"
            screenshot_path.rename(step_screenshot_path)

            # Draw coordinate grid overlay
            step_screenshot_grid_path = add_coordinate_grid(step_screenshot_path)
            print(f"New screenshot grid saved to: {step_screenshot_grid_path.name}")

            # Update solver with new screen state
            solver.add_new_screenshot(step_screenshot_grid_path)

            consecutive_errors = 0
            step += 1

        except Exception as exc:
            consecutive_errors += 1
            print(f"ERROR on step {step + 1}: {exc}")
            if consecutive_errors >= max_consecutive_errors:
                print(f"Terminating run due to {max_consecutive_errors} consecutive errors.")
                break
            print("Retrying...")
            time.sleep(3.0)

    print("\n" + "=" * 60)
    print(f"Benchmark finished. Total steps executed: {step}")
    print(f"Log results saved in: {run_dir}")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
