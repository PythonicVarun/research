import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from adb_device import ADBDevice
from agent_solver import AgentSolver
from image_utils import add_coordinate_grid
from vision_parser import VisionParser


def run_benchmark(max_steps: int = 50) -> None:
    """Runs the Minesweeper play benchmark loop.

    Args:
        max_steps: The maximum number of actions the agent is allowed to take.
    """
    # 1. Load Environment Settings
    load_dotenv()

    vision_api_key = os.getenv("VISION_API_KEY")
    vision_base_url = os.getenv("VISION_BASE_URL")
    vision_model = os.getenv("VISION_MODEL")
    agent_api_key = os.getenv("AGENT_API_KEY")
    agent_base_url = os.getenv("AGENT_BASE_URL")
    agent_model = os.getenv("AGENT_MODEL")
    device_serial = os.getenv("ADB_DEVICE_SERIAL")

    # Validate configuration
    missing_vars = []
    if not vision_api_key:
        missing_vars.append("VISION_API_KEY")
    if not vision_base_url:
        missing_vars.append("VISION_BASE_URL")
    if not vision_model:
        missing_vars.append("VISION_MODEL")
    if not agent_api_key:
        missing_vars.append("AGENT_API_KEY")
    if not agent_base_url:
        missing_vars.append("AGENT_BASE_URL")
    if not agent_model:
        missing_vars.append("AGENT_MODEL")

    if missing_vars:
        raise ValueError(
            "Missing required configuration variables in environment: "
            f"{', '.join(missing_vars)}. "
        )

    # 2. Setup Logging Directories
    runs_dir = Path("V:/Codes/research/llm-minesweeper/runs")
    run_id = f"run_{int(time.time())}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"Starting Minesweeper Benchmark Loop (Run ID: {run_id})")
    print(f"Vision Model: {vision_model}")
    print(f"Solver Model: {agent_model}")
    print(f"Audit Trail Directory: {run_dir}")
    print("=" * 60)

    # 3. Initialize Connections
    device = ADBDevice(serial=device_serial if device_serial else None)
    vision_parser = VisionParser(
        api_key=vision_api_key, base_url=vision_base_url, model_name=vision_model  # type: ignore[bad-argument-type] # reason: all of the params will be defined checked above
    )
    agent_solver = AgentSolver(
        api_key=agent_api_key, base_url=agent_base_url, model_name=agent_model  # type: ignore[bad-argument-type] # reason: all of the params will be defined checked above
    )

    print("\nDevice connected. Launching benchmark session loop...")

    step = 0
    consecutive_errors = 0
    max_consecutive_errors = 3

    while step < max_steps:
        print(f"\n--- Step {step + 1} / {max_steps} ---")
        try:
            # a. Capture Device Screen
            print("Capturing device screenshot...")
            screenshot_path = device.take_screenshot(run_dir)
            # Rename screenshot to a step-specific name
            step_screenshot_path = run_dir / f"step_{step}_screenshot.png"
            screenshot_path.rename(step_screenshot_path)
            print(f"Screenshot saved to: {step_screenshot_path.name}")

            # b. Vision Analysis (with grid overlay pre-processing)
            print("Generating coordinate grid overlay...")
            step_screenshot_grid_path = add_coordinate_grid(step_screenshot_path)
            print(f"Grid overlay screenshot saved to: {step_screenshot_grid_path.name}")

            print("Analyzing screenshot with vision model...")
            board_state = vision_parser.parse_screenshot(step_screenshot_grid_path)

            # Save parsed state
            state_json_path = run_dir / f"step_{step}_state.json"
            state_json_path.write_text(json.dumps(board_state, indent=2))

            # Print parsed summary
            game_state = board_state.get("game_state", "unknown")
            zoom_level = board_state.get("zoom_level", "unknown")
            current_mode = board_state.get("current_mode", "unknown")
            cells_count = len(board_state.get("cells", []))

            print(f"Detected Game State: {game_state.upper()}")
            print(f"Zoom Level: {zoom_level.upper()}")
            print(f"Active Mode: {current_mode.upper()}")
            print(f"Visible Grid Cells Detected: {cells_count}")

            # Terminate if the game is over and no restart is triggered
            # (or if it's menu and no new game starts)
            if game_state in ["won", "lost"]:
                print(f"Game finished! State: {game_state.upper()}")

            # c. Get Next Action Decision
            print("Requesting next move from Solver Agent...")
            move_decision = agent_solver.decide_move(board_state)

            # Save move decision
            move_json_path = run_dir / f"step_{step}_move.json"
            move_json_path.write_text(json.dumps(move_decision, indent=2))

            action = move_decision.get("action")
            rationale = move_decision.get("rationale", "No rationale provided.")
            target = move_decision.get("target")

            print(f"Solver Rationale: {rationale}")
            print(f"Chosen Action: {action} on target {target}")

            # Reset error counter upon successful cycle
            consecutive_errors = 0

            # d. Execute Move
            if action == "DIG":
                if not target or len(target) != 2:
                    print(
                        "Error: Target coordinates are required for DIG action "
                        "but not specified. Skipping."
                    )
                    step += 1
                    continue
                tx, ty = target[0], target[1]
                # Check mode compatibility. If current mode is flag, switch to dig first.
                if current_mode == "flag":
                    device.set_mode("dig")
                device.tap(tx, ty)

            elif action == "FLAG":
                if not target or len(target) != 2:
                    print(
                        "Error: Target coordinates are required for FLAG "
                        "action but not specified. Skipping."
                    )
                    step += 1
                    continue
                tx, ty = target[0], target[1]
                # Check mode compatibility. If current mode is dig, switch to flag first.
                if current_mode == "dig":
                    device.set_mode("flag")
                device.tap(tx, ty)

            elif action == "ZOOM_IN":
                device.zoom_in()

            elif action == "ZOOM_OUT":
                device.zoom_out()

            elif action == "NEW_GAME":
                # Use provided target coordinates or fallback to detected
                # new_game_button_center
                bt = target
                if not bt:
                    bt = board_state.get("new_game_button_center")

                if bt and len(bt) == 2:
                    print(f"Starting new game by tapping at {bt}...")
                    device.tap(bt[0], bt[1])
                else:
                    print(
                        "Error: Cannot start new game. No restart button "
                        "coordinate found. Skipping."
                    )

            elif action == "CLOSE_AD":
                at = target
                if not at:
                    at = board_state.get("close_ad_button_center")

                if at and len(at) == 2:
                    print(f"Closing advertisement by tapping at {at}...")
                    device.tap(at[0], at[1])
                else:
                    print(
                        "Error: Cannot close ad. No close button coordinate "
                        "found. Skipping."
                    )

            else:
                print(f"Unknown action type: {action}. Skipping.")

            # Let board update and render
            print("Waiting for game updates...")
            time.sleep(2.0)
            step += 1

        except Exception as exc:
            consecutive_errors += 1
            print(f"ERROR on step {step + 1}: {exc}")
            if consecutive_errors >= max_consecutive_errors:
                print(
                    f"Terminating run due to {max_consecutive_errors} "
                    "consecutive errors."
                )
                break
            print("Retrying next step...")
            time.sleep(3.0)
            step += 1

    print("\n" + "=" * 60)
    print(f"Benchmark finished. Total steps executed: {step}")
    print(f"Log results saved in: {run_dir}")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
