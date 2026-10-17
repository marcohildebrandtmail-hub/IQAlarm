"""Bounded floorplan decoding, orientation, transparency and atomic image files."""

import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 10 * 1024 * 1024


def prepare_image(payload: bytes) -> tuple[bytes, int, int]:
    """Keep only bounded PNG/JPEG pixels, discarding metadata and extra frames."""
    if not payload or len(payload) > MAX_UPLOAD:
        raise ValueError("Grundriss muss zwischen 1 Byte und 10 MB groß sein")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                if image.format not in {"PNG", "JPEG"}:
                    raise ValueError("Nur PNG oder JPEG sind erlaubt")
                width, height = image.size
                if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 32_000_000:
                    raise ValueError("Bild maximal 8192 Pixel pro Seite und 32 Megapixel")
                image.load()
                image = ImageOps.exif_transpose(image)
                output = BytesIO()
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    background.paste(image.convert("RGB"))
                background.save(output, format="PNG")
                return output.getvalue(), background.width, background.height
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as err:
        raise ValueError("Ungültiges oder zu großes Bild") from err


def write_image(directory: Path, filename: str, payload: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / (filename + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(directory / filename)
    finally:
        temporary.unlink(missing_ok=True)
