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


def resize_contain(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Fit the complete image inside a target canvas and pad the rest black."""
    tw, th = target_size
    if tw <= 0 or th <= 0:
        raise ValueError("target_size must contain positive dimensions")
    if image.width <= 0 or image.height <= 0:
        raise ValueError("image must have positive dimensions")
    if image.size == (tw, th) and image.mode == "RGB":
        return image.copy()

    scale = min(tw / image.width, th / image.height)
    nw = max(1, min(tw, round(image.width * scale)))
    nh = max(1, min(th, round(image.height * scale)))
    resized = image.resize((nw, nh), resample=_resample())

    # The surrounding area is deliberately opaque black. Composite alpha onto
    # black too, so transparent source pixels cannot reveal a non-black border.
    rgba = resized.convert("RGBA")
    black = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    black.alpha_composite(rgba, ((tw - nw) // 2, (th - nh) // 2))
    return black.convert("RGB")


def transform_cover_height(image: Image.Image, target_size: Tuple[int, int] = (1920, 1080), position: str = "center", allow_upscale: bool = True) -> Image.Image:
    """Backward-compatible name for fitting the whole image with black bars."""
    return resize_contain(image, target_size)


def transform_background(image: Image.Image, settings) -> Image.Image:
    if not settings or not getattr(settings, "enabled", False):
        return image
    target = tuple(getattr(settings, "target_size", (1920, 1080)))
    mode = getattr(settings, "fit_mode", "cover")
    position = getattr(settings, "crop_position", "center")

    if mode in {"contain", "cover_height"}:
        # cover_height is accepted for compatibility with previously saved
        # settings; the requested behavior is whole-image contain with black bars.
        return transform_cover_height(image, target, position)
    if mode == "cover":
        return resize_cover(image, target, position)
    return resize_cover(image, target, position)
