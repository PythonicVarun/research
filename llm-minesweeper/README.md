# Android Minesweeper LLM Benchmark Harness

This benchmark harness evaluates a Large Language Model's capability to play Minesweeper on an Android device (physical or emulator).

The system leverages:

1. **Gemini 3.1 Pro (via OpenAI-compatible API)** as the **Vision Parser** to analyze screenshots and extract game state, cell statuses, and coordinate maps.
2. An **LLM (via OpenAI-compatible API)** as the **Solver Agent** to make logical deductions (DIG, FLAG, ZOOM_IN, ZOOM_OUT, etc.).
3. **ADB (Android Debug Bridge)** and optionally **`uiautomator2`** to interact with the device.

---

## Architecture and Components

- [harness.py](file:///V:/Codes/research/llm-minesweeper/harness.py): The main orchestrator that runs the loop, captures screenshots, stores audit logs, and maps decisions back to the device.
- [adb_device.py](file:///V:/Codes/research/llm-minesweeper/adb_device.py): Wraps ADB and `uiautomator2` to handle screen captures, touch events, and simultaneous two-finger zoom gestures.
- [vision_parser.py](file:///V:/Codes/research/llm-minesweeper/vision_parser.py): Connects to the OpenAI-compatible vision endpoint to map screenshots to structured JSON board representations.
- [agent_solver.py](file:///V:/Codes/research/llm-minesweeper/agent_solver.py): Formulates logic prompts for the solver LLM and interprets action outputs (DIG, FLAG, ZOOM, NEW_GAME).

---

## Setup Instructions

### 1. Pre-requisites

- **Python 3.10+**: Ensure Python is installed.
- **ADB (Android Debug Bridge)**: Must be installed and available in your system `PATH`. Verify this by running:
    ```powershell
    adb devices
    ```
- **Android Device or Emulator**:
    - If using a physical phone, enable **USB Debugging** in Developer Options.
    - If using an emulator, start it from Android Studio or the command line.

### 2. Install Python Dependencies

Install the required packages in your python environment:

```powershell
pip install -r requirements.txt
```

_(Optional)_ If you want to use the most reliable multi-touch zoom gestures, ensure `uiautomator2` is installed. When the harness runs for the first time, it will initialize the necessary agent services on your connected device automatically.

### 3. Configuration

Copy the `.env.example` file to `.env`:

```powershell
cp .env.example .env
```

Fill in the following details in `.env`:

- `VISION_API_KEY`: Your Gemini/Google API Key.
- `VISION_BASE_URL`: OpenAI-compatible endpoint URL for Gemini (e.g. `https://generativelanguage.googleapis.com/v1beta/openai/`).
- `VISION_MODEL`: The model name (e.g. `gemini-3.1-pro-preview` or your specific version).
- `AGENT_API_KEY`: API key for the solver model.
- `AGENT_BASE_URL`: Base URL for the solver model's OpenAI-compatible endpoint.
- `AGENT_MODEL`: Model name for the solver (e.g. `gpt-4o`, `gemini-2.5-flash`).
- `ADB_DEVICE_SERIAL`: (Optional) If you have multiple devices connected, specify the target serial here (found via `adb devices`).

---

## How to Play / Run the Benchmark

1. Make sure your Android device is connected and displaying the Minesweeper game screen.
2. Run the harness:
    ```powershell
    python harness.py
    ```
3. The harness will automatically:
    - Identify your connected device.
    - Start a benchmark run under `runs/run_<timestamp>/`.
    - Take screenshots at each step.
    - Call the Vision LLM to locate cells and controls.
    - Ask the Solver LLM for a move (handling toggle modes between DIG and FLAG automatically).
    - Execute the move and log the results.

---

## Benchmarking Logs

Each run creates a dedicated folder under `runs/run_<timestamp>/` containing:

- `step_{N}_screenshot.png`: The device screen at step N.
- `step_{N}_state.json`: The game state parsed by the Vision model.
- `step_{N}_move.json`: The decision, reasoning, and target coordinate selected by the Solver model.

This structured audit log allows you to evaluate and analyze the accuracy of both the Vision Parser and the Solver Agent at every stage of the game.
