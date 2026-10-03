from __future__ import annotations

from typing import Tuple
from PIL import Image


def _resample() -> Image.Resampling:
    return Image.Resampling.LANCZOS


def resize_to_height(image: Image.Image, target_height: int) -> Image.Image:
    """Stage 1 of cover_height: uniform scale ONLY by height."""
    if target_height <= 0:
        raise ValueError("target_height must be greater than zero")
    if image.height <= 0 or image.width <= 0:
        raise ValueError("image must have positive dimensions")
    scale = target_height / image.height
    width = max(1, round(image.width * scale))
    if (width, target_height) == image.size:
        return image.copy()
    return image.resize((width, target_height), resample=_resample())


def expand_to_width(image: Image.Image, target_width: int, position: str = "center") -> Image.Image:
    """Stage 2 of cover_height: change canvas width WITHOUT resizing the image.

    The image pixels keep their exact dimensions. When the target is wider, the
    missing horizontal area is made by repeating the nearest edge columns.
    When narrower, the canvas is cropped. Height is never changed here.
    """
    if target_width <= 0:
        raise ValueError("target_width must be greater than zero")
    if position not in {"left", "center", "right"}:
        position = "center"

    if image.width == target_width:
        return image.copy()

    if image.width > target_width:
        if position == "left":
            x = 0
        elif position == "right":
            x = image.width - target_width
        else:
            x = (image.width - target_width) // 2
        return image.crop((x, 0, x + target_width, image.height))

    left = 0 if position == "left" else (target_width - image.width if position == "right" else (target_width - image.width) // 2)
    right = target_width - image.width - left

    # Work in RGBA/RGB/L/LA so edge replication is deterministic.
    working = image if image.mode in {"RGB", "RGBA", "L", "LA"} else image.convert("RGBA")
    canvas = Image.new(working.mode, (target_width, working.height))
    canvas.paste(working, (left, 0))

    if left:
        edge = working.crop((0, 0, 1, working.height))
        canvas.paste(edge.resize((left, working.height), Image.Resampling.NEAREST), (0, 0))
    if right:
        edge = working.crop((working.width - 1, 0, working.width, working.height))
        canvas.paste(edge.resize((right, working.height), Image.Resampling.NEAREST), (left + working.width, 0))
    return canvas


# Backward-compatible public name used by existing callers/tests.
expand_horizontal = expand_to_width


def resize_cover(image: Image.Image, target_size: Tuple[int, int], position: str = "center") -> Image.Image:
    """Traditional cover: scale uniformly, then crop to target."""
    tw, th = target_size
    if tw <= 0 or th <= 0:
        raise ValueError("target_size must contain positive dimensions")
    scale = max(tw / image.width, th / image.height)
    nw = max(1, round(image.width * scale))
    nh = max(1, round(image.height * scale))
    resized = image.resize((nw, nh), resample=_resample())

    if position not in {"top", "center", "bottom"}:
        position = "center"
    left = (nw - tw) // 2
    if position == "top":
        top = 0
    elif position == "bottom":
        top = nh - th
    else:
        top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def transform_cover_height(image: Image.Image, target_size: Tuple[int, int] = (1920, 1080), position: str = "center", allow_upscale: bool = True) -> Image.Image:
    """Scale to target HEIGHT, then expand/crop only the CANVAS width.

    Example: 600x800 -> 810x1080 -> 1920x1080.
    The second stage NEVER calls resize() on the image content.
    """
    tw, th = target_size
    if tw <= 0 or th <= 0:
        raise ValueError("target_size must contain positive dimensions")
    if not allow_upscale and image.height < th:
        # Explicitly retain old no-upscale behavior.
        canvas = Image.new(image.mode if image.mode in {"RGB", "RGBA", "L", "LA"} else "RGBA", (tw, th))
        src = image if canvas.mode == image.mode else image.convert(canvas.mode)
        x = max(0, (tw - src.width) // 2)
        y = max(0, (th - src.height) // 2)
        canvas.paste(src, (x, y), src if src.mode in {"RGBA", "LA"} else None)
        return canvas

    scaled = resize_to_height(image, th)
    # IMPORTANT: scaled.height is already exactly th. This function must not
    # resize it again; it only changes the horizontal canvas.
    result = expand_to_width(scaled, tw, "left" if position == "left" else "right" if position == "right" else "center")

    assert result.height == th, f"cover_height changed height unexpectedly: {result.size}"
    assert result.width == tw, f"cover_height changed width unexpectedly: {result.size}"
    return result


def transform_background(image: Image.Image, settings) -> Image.Image:
    if not settings or not getattr(settings, "enabled", False):
        return image
    target = tuple(getattr(settings, "target_size", (1920, 1080)))
    mode = getattr(settings, "fit_mode", "cover")
    position = getattr(settings, "crop_position", "center")
    allow_upscale = getattr(settings, "allow_upscale", True)

    if mode == "cover_height":
        return transform_cover_height(image, target, position, allow_upscale)
    if mode == "cover":
        return resize_cover(image, target, position)
    return resize_cover(image, target, position)
