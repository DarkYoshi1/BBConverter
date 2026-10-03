from PIL import Image
from src.background_scaler import (
    expand_horizontal,
    resize_cover,
    transform_background,
    transform_cover_height,
)
from src.models import BackgroundTransform


def test_cover_600x800_to_1920x1080():
    src = Image.new("RGB", (600, 800), "red")
    out = resize_cover(src, (1920, 1080), position="center")
    assert out.size == (1920, 1080)


def test_cover_produces_exact_target_size():
    src = Image.new("RGB", (100, 50), "blue")
    out = resize_cover(src, (320, 240), position="center")
    assert out.size == (320, 240)


def test_cover_height_600x800_scales_only_to_810x1080_before_expansion():
    src = Image.new("RGB", (600, 800), (5, 10, 15))
    scaled = transform_cover_height(src, (810, 1080))
    assert scaled.size == (810, 1080)


def test_cover_height_600x800_expands_canvas_to_1920_without_horizontal_scaling():
    # Use a unique vertical gradient so horizontal scaling would alter the
    # original 810-pixel region. The central source must remain 810 pixels wide.
    src = Image.new("RGB", (600, 800))
    for y in range(800):
        for x in range(600):
            src.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))

    out = transform_cover_height(src, (1920, 1080), "center")
    assert out.size == (1920, 1080)

    # 600 * (1080/800) = 810 exactly.
    left = (1920 - 810) // 2
    right = left + 810

    # The center 810x1080 region must be exactly the vertically scaled image.
    expected = src.resize((810, 1080), Image.Resampling.LANCZOS)
    assert out.crop((left, 0, right, 1080)).tobytes() == expected.tobytes()

    # The image reaches the top and bottom; there is no vertical padding.
    assert out.getpixel((left, 0)) == expected.getpixel((0, 0))
    assert out.getpixel((left, 1079)) == expected.getpixel((0, 1079))


def test_expand_horizontal_does_not_resize_original_content():
    src = Image.new("RGB", (4, 2))
    for x in range(4):
        for y in range(2):
            src.putpixel((x, y), (x * 40, y * 80, 10))
    out = expand_horizontal(src, 10, "center")
    assert out.size == (10, 2)
    assert out.crop((3, 0, 7, 2)).tobytes() == src.tobytes()
    assert out.getpixel((0, 0)) == src.getpixel((0, 0))
    assert out.getpixel((9, 0)) == src.getpixel((3, 0))


def test_disabled_transformation_returns_original():
    src = Image.new("RGB", (300, 200), "navy")
    settings = BackgroundTransform(enabled=False)
    out = transform_background(src, settings)
    assert out.size == src.size
    assert out.tobytes() == src.tobytes()


def test_1920x1080_is_not_unnecessarily_resized():
    src = Image.new("RGB", (1920, 1080), "black")
    settings = BackgroundTransform(enabled=True, target_size=(1920, 1080))
    out = transform_background(src, settings)
    assert out.size == (1920, 1080)
    assert out.tobytes() == src.tobytes()


def test_no_upscale_pads_center():
    src = Image.new("RGB", (4, 3), (10, 20, 30))
    settings = BackgroundTransform(enabled=True, target_size=(8, 6), allow_upscale=False)
    out = transform_background(src, settings)
    assert out.size == (8, 6)
    left = (8 - 4) // 2
    top = (6 - 3) // 2
    assert out.getpixel((left, top)) == (10, 20, 30)


def test_cover_height_output_reaches_both_vertical_edges():
    src = Image.new("RGB", (600, 800), (5, 10, 15))
    settings = BackgroundTransform(
        enabled=True,
        target_size=(1920, 1080),
        fit_mode="cover_height",
        crop_position="center",
    )
    out = transform_background(src, settings)
    assert out.size == (1920, 1080)
    assert out.height == 1080
    # Every row exists from y=0 through y=1079; no top/bottom padding is added.
    assert out.getpixel((960, 0)) == (5, 10, 15)
    assert out.getpixel((960, 1079)) == (5, 10, 15)

def test_cover_height_exact_legacy_geometry():
    src = Image.new("RGB", (600, 800), "red")
    out = transform_cover_height(src, (1920, 1080), "center")
    assert out.size == (1920, 1080)
    # The source-derived image is exactly 810x1080, so it reaches y=0 and y=1079.
    assert out.height == 1080
