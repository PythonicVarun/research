import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

import uiautomator2 as u2


class ADBDevice:
    """Manages ADB and uiautomator2 interactions with the connected Android device."""

    def __init__(self, serial: Optional[str] = None) -> None:
        """Initializes connection to an Android device.

        Args:
            serial: Optional device serial number. If None, auto-detects.
        """
        self.serial: Optional[str] = serial
        self.u2_device = None
        self._init_device()

    def _init_device(self) -> None:
        """Initializes connection details and establishes uiautomator2 connection."""
        if not self.serial:
            self.serial = self._detect_single_device()

        # Verify ADB is working and device is connected
        self._run_adb_cmd(["shell", "echo", "ping"])

        # Connect to device via uiautomator2
        print(f"Connecting to device '{self.serial}' via uiautomator2...")
        self.u2_device = u2.connect(self.serial)
        print("Successfully connected via uiautomator2.")

    def _detect_single_device(self) -> str:
        """Detects a connected device and returns its serial.

        Raises:
            RuntimeError: If no devices or multiple devices are connected
                and no serial is specified.
        """
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split("\n")[1:]
        devices = [
            line.split()[0] for line in lines if line.strip() and "device" in line
        ]

        if not devices:
            raise RuntimeError(
                "No Android devices connected via ADB. "
                "Please connect a device or start an emulator."
            )
        if len(devices) > 1:
            raise RuntimeError(
                f"Multiple devices detected: {devices}. "
                "Please specify target device serial in the configuration."
            )

        print(f"Auto-detected device: {devices[0]}")
        return devices[0]

    def _run_adb_cmd(self, args: list[str]) -> str:
        """Runs an ADB command for the selected device.

        Args:
            args: Command arguments to pass to adb.

        Returns:
            The stdout from the command.

        Raises:
            subprocess.CalledProcessError: If the command fails.
        """
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as exc:
            print(f"ADB Command Failed: {' '.join(cmd)}")
            print(f"Stderr: {exc.stderr}")
            raise

    def get_screen_size(self) -> Tuple[int, int]:
        """Gets the screen dimensions (width, height) of the device.

        Returns:
            A tuple of (width, height) in pixels.
        """
        output = self._run_adb_cmd(["shell", "wm", "size"])
        # Expected output: "Physical size: 1080x2400"
        size_str = output.split(":")[-1].strip()
        w_str, h_str = size_str.split("x")
        return int(w_str), int(h_str)

    def get_current_package(self) -> str:
        """Retrieves the package name of the app currently in the foreground.

        Returns:
            The package name as a string.
        """
        # dumpsys window displays is robust across different Android versions
        output = self._run_adb_cmd(["shell", "dumpsys", "window", "displays"])
        for line in output.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                # Example: mCurrentFocus=Window{c18ca80 u0
                # com.android.minesweeper/com.android.minesweeper.MainActivity}
                parts = line.split(" ")
                for part in parts:
                    if "/" in part:
                        # Extract the package name before '/'
                        pkg = part.split("/")[0]
                        # Clean up surrounding brackets or braces if any
                        clean_pkg = pkg.split("{")[-1].split("}")[0]
                        return clean_pkg
        return "unknown"

    def launch_app(self, package_name: str) -> None:
        """Launches an app using its package name.

        Args:
            package_name: The package identifier of the target app.
        """
        print(f"Launching app: {package_name}...")
        self._run_adb_cmd(
            [
                "shell",
                "monkey",
                "-p",
                package_name,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ]
        )
        time.sleep(3)  # Wait for launch animation to complete

    def take_screenshot(self, output_dir: Path) -> Path:
        """Captures a screenshot from the device and saves it locally.

        Args:
            output_dir: Local Path to save the screenshot.

        Returns:
            The Path to the saved screenshot file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        local_path = output_dir / f"screenshot_{int(time.time())}.png"

        # We use adb exec-out screencap to stream png data directly
        # to avoid needing on-device storage space
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(["exec-out", "screencap", "-p"])

        try:
            with open(local_path, "wb") as f:
                subprocess.run(cmd, stdout=f, check=True)
            return local_path
        except Exception as exc:
            print(f"Failed to capture screenshot: {exc}")
            raise

    def tap(self, x: int, y: int) -> None:
        """Performs a tap gesture at the given coordinates.

        Args:
            x: X screen coordinate.
            y: Y screen coordinate.
        """
        print(f"Tapping screen at ({x}, {y})")
        self._run_adb_cmd(["shell", "input", "tap", str(x), str(y)])
        time.sleep(1)  # Let the app react

    def long_press(self, x: int, y: int, duration_ms: int = 500) -> None:
        """Performs a long press gesture at the given coordinates.

        Args:
            x: X screen coordinate.
            y: Y screen coordinate.
            duration_ms: Duration of press in milliseconds.
        """
        print(f"Long-pressing screen at ({x}, {y}) for {duration_ms}ms")
        # Swipe from (x, y) to (x, y) performs a long press
        self._run_adb_cmd(
            [
                "shell",
                "input",
                "swipe",
                str(x),
                str(y),
                str(x),
                str(y),
                str(duration_ms),
            ]
        )
        time.sleep(1)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """Performs a swipe from (x1, y1) to (x2, y2).

        Args:
            x1: Start X coordinate.
            y1: Start Y coordinate.
            x2: End X coordinate.
            y2: End Y coordinate.
            duration_ms: Swipe duration in milliseconds.
        """
        print(f"Swiping from ({x1}, {y1}) to ({x2}, {y2}) over {duration_ms}ms")
        self._run_adb_cmd(
            [
                "shell",
                "input",
                "swipe",
                str(x1),
                str(y1),
                str(x2),
                str(y2),
                str(duration_ms),
            ]
        )
        time.sleep(1)

    def zoom_in(self) -> None:
        """Simulates a pinch-out gesture to zoom in on the board."""
        if self.u2_device is None:
            print("Error: uiautomator2 device not initialized. Cannot perform zoom.")
            return

        print("Executing Zoom In (Pinch Out)...")
        self.u2_device(className="android.widget.FrameLayout").pinch_out(
            percent=100, steps=15
        )
        time.sleep(1.5)

    def zoom_out(self) -> None:
        """Simulates a pinch-in gesture to zoom out on the board."""
        if self.u2_device is None:
            print("Error: uiautomator2 device not initialized. Cannot perform zoom.")
            return

        print("Executing Zoom Out (Pinch In)...")
        self.u2_device(className="android.widget.FrameLayout").pinch_in(
            percent=100, steps=15
        )
        time.sleep(1.5)

    def set_mode(self, mode: str) -> None:
        """Sets the play mode of the Minesweeper app (either 'dig' or 'flag').

        Args:
            mode: Desired mode ('dig' or 'flag').
        """
        w, h = self.get_screen_size()
        if mode == "dig":
            # Click the left side of the toggle capsule (approx 43% of width, 88% of height)
            tx, ty = int(w * 0.43), int(h * 0.88)
            print(f"Setting mode to DIG (tapping at {tx}, {ty})...")
            self.tap(tx, ty)
        elif mode == "flag":
            # Click the right side of the toggle capsule (approx 57% of width, 88% of height)
            tx, ty = int(w * 0.57), int(h * 0.88)
            print(f"Setting mode to FLAG (tapping at {tx}, {ty})...")
            self.tap(tx, ty)
        time.sleep(0.5)
