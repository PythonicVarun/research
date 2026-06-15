import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from adb_device import ADBDevice
from image_utils import add_coordinate_grid


def connect_device() -> ADBDevice:
    """Connects to the ADB device using configurations from the environment.

    Returns:
        The connected ADBDevice instance.
    """
    load_dotenv()
    device_serial = os.getenv("ADB_DEVICE_SERIAL")
    return ADBDevice(serial=device_serial if device_serial else None)


def take_and_grid_screenshot(device: ADBDevice, output_dir: Path, step: int) -> None:
    """Captures the device screenshot and saves it with a coordinate grid overlay.

    Args:
        device: Connected ADBDevice.
        output_dir: Output directory path.
        step: Current step number.
    """
    print("Capturing screenshot...")
    raw_path = device.take_screenshot(output_dir)
    step_path = output_dir / f"cli_step_{step}.png"
    if step_path.exists():
        step_path.unlink()
    raw_path.rename(step_path)

    grid_path = add_coordinate_grid(step_path)
    print(f"Grid screenshot saved: {grid_path}")


def run_cli() -> None:
    """Runs the interactive command line interface loop for manual testing."""
    output_dir = Path("./runs/cli_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Connecting to device...")
    try:
        device = connect_device()
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return

    print("\n" + "=" * 60)
    print("Interactive ADB Tool Testing CLI")
    print("Commands:")
    print("  tap <x> <y>             - Tap at screen coordinates (x, y)")
    print("  long_press <x> <y> [ms] - Long press at coordinates (x, y) for duration [ms]")
    print("  zoom_in                 - Zoom in (pinch out gesture)")
    print("  zoom_out                - Zoom out (pinch in gesture)")
    print("  screenshot              - Capture screen and apply coordinate grid overlay")
    print("  quit / exit             - Close CLI")
    print("=" * 60 + "\n")

    step = 0
    # Take initial screenshot
    try:
        take_and_grid_screenshot(device, output_dir, step)
        step += 1
    except Exception as exc:
        print(f"Failed to capture initial screen state: {exc}")

    while True:
        try:
            cmd_input = input("\nminesweeper-cli> ").strip()
            if not cmd_input:
                continue

            parts = cmd_input.split()
            cmd = parts[0].lower()

            if cmd in ["quit", "exit"]:
                print("Exiting CLI.")
                break

            elif cmd == "tap":
                if len(parts) < 3:
                    print("Error: tap requires x and y coordinates. e.g. tap 500 1200")
                    continue
                x = int(parts[1])
                y = int(parts[2])
                device.tap(x, y)

            elif cmd in ["long_press", "press"]:
                if len(parts) < 3:
                    print("Error: long_press requires x and y coordinates. e.g. long_press 500 1200 [ms]")
                    continue
                x = int(parts[1])
                y = int(parts[2])
                duration = int(parts[3]) if len(parts) > 3 else 500
                device.long_press(x, y, duration)

            elif cmd == "zoom_in":
                device.zoom_in()

            elif cmd == "zoom_out":
                device.zoom_out()

            elif cmd == "screenshot":
                pass

            else:
                print(f"Unknown command: {cmd}")
                continue

            # Take screenshot showing new screen state
            take_and_grid_screenshot(device, output_dir, step)
            step += 1

        except ValueError as val_err:
            print(f"Argument formatting error: {val_err}. Make sure coordinates are integers.")
        except KeyboardInterrupt:
            print("\nExiting CLI.")
            break
        except Exception as exc:
            print(f"Error during command execution: {exc}")


if __name__ == "__main__":
    run_cli()
