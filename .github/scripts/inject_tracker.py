import re
from pathlib import Path

TRACKER_SCRIPT: str = (
    '<script async src="https://trackerbea.pythonicvarun.me/tracker.js" data-trackerbea-server="https://trackerbea.pythonicvarun.me" data-trackerbea-domain-id="fa4b848f-8fd3-446b-8b13-d50c1defcdb6" data-trackerbea-opts=\'{"detailed":true}\'></script>'
)


def inject_tracker_into_file(file_path: Path) -> None:
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as exc:
        print(f"Skipping {file_path} due to error: {exc}")
        return

    # Avoid duplicate injection
    if "trackerbea.pythonicvarun.me/tracker.js" in content:
        print(f"Tracker already present in {file_path}")
        return

    # Look for </head> tag
    head_match = re.search(r"</head>", content, re.IGNORECASE)
    if head_match:
        pos = head_match.start()
        # Add tracker before </head>
        new_content = f"{content[:pos]}\n    {TRACKER_SCRIPT}\n{content[pos:]}"
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Injected tracker into {file_path} before </head>")
        return

    # Fallback to </body>
    body_match = re.search(r"</body>", content, re.IGNORECASE)
    if body_match:
        pos = body_match.start()
        new_content = f"{content[:pos]}\n    {TRACKER_SCRIPT}\n{content[pos:]}"
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Injected tracker into {file_path} before </body>")
        return

    print(f"Could not find </head> or </body> in {file_path}, skipping.")


def process_directory(directory: Path) -> None:
    for path in directory.rglob("*.html"):
        if any(part.startswith(".") for part in path.parts):
            continue

        inject_tracker_into_file(path)


def main() -> None:
    base_dir = Path(".")
    process_directory(base_dir)


if __name__ == "__main__":
    main()
