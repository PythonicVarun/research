from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def add_coordinate_grid(image_path: Path) -> Path:
    """Overlays a coordinate grid onto a screenshot for visual reference.

    Draws red lines every 100px, logs X/Y labels on margins, and plots coordinate text
    labels (e.g. "200,400") at major 200px intersections.

    Args:
        image_path: Path to the original screenshot file.

    Returns:
        The Path to the generated screenshot with the grid overlay.
    """
    if not image_path.exists():
        raise FileNotFoundError(
            f"Source screenshot for grid overlay not found: {image_path}"
        )

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Setup font with multiple fallbacks
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()

    grid_spacing = 100
    line_color = (255, 0, 0, 120)  # Semi-transparent red
    text_color = (255, 0, 0)

    # 1. Draw vertical lines and X-axis labels
    for x in range(grid_spacing, w, grid_spacing):
        draw.line([(x, 0), (x, h)], fill=line_color, width=1)
        # Draw labels near top and bottom margins
        draw.text((x + 3, 10), str(x), fill=text_color, font=font)
        draw.text((x + 3, h - 30), str(x), fill=text_color, font=font)

    # 2. Draw horizontal lines and Y-axis labels
    for y in range(grid_spacing, h, grid_spacing):
        draw.line([(0, y), (w, y)], fill=line_color, width=1)
        # Draw labels near left and right margins
        draw.text((10, y + 3), str(y), fill=text_color, font=font)
        draw.text((w - 50, y + 3), str(y), fill=text_color, font=font)

    # 3. Draw intersection coordinates (crosshairs) every 200 pixels
    label_spacing = 200
    for x in range(label_spacing, w, label_spacing):
        for y in range(label_spacing, h, label_spacing):
            # Plot center dot
            draw.ellipse(
                [(x - 3, y - 3), (x + 3, y + 3)],
                fill=(255, 255, 255),
                outline=(255, 0, 0),
            )
            # Text coordinate label
            coord_str = f"{x},{y}"
            draw.text(
                (x + 5, y + 5),
                coord_str,
                fill=(0, 0, 0),
                font=font,
                stroke_width=1,
                stroke_fill=(255, 255, 255),
            )

    grid_path = image_path.parent / f"{image_path.stem}_grid.png"
    img.save(grid_path)
    return grid_path
