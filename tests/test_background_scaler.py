from PIL import Image
from src.background_scaler import (
    expand_horizontal,
    resize_cover,
    resize_contain,
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


def test_contain_600x800_scales_to_810x1080_before_padding():
    src = Image.new("RGB", (600, 800), (5, 10, 15))
    scaled = transform_cover_height(src, (810, 1080))
    assert scaled.size == (810, 1080)


def test_contain_600x800_adds_black_bars_without_horizontal_distortion():
    # Use a unique gradient to prove the image content is uniformly scaled.
    src = Image.new("RGB", (600, 800))
    for y in range(800):
        for x in range(600):
            src.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))

    out = transform_cover_height(src, (1920, 1080), "center")
    assert out.size == (1920, 1080)

    # 600 * (1080/800) = 810 exactly.
    left = (1920 - 810) // 2
    right = left + 810

    # The center 810x1080 region must be exactly the uniformly scaled image.
    expected = src.resize((810, 1080), Image.Resampling.LANCZOS)
    assert out.crop((left, 0, right, 1080)).tobytes() == expected.tobytes()

    # The full image reaches the top and bottom; bars only occupy the sides.
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


def test_cover_height_reaches_target_even_with_legacy_no_upscale_setting():
    src = Image.new("RGB", (4, 3))
    for y in range(3):
        for x in range(4):
            src.putpixel((x, y), (x * 40, y * 80, 20))
    settings = BackgroundTransform(
        enabled=True,
        target_size=(8, 6),
        fit_mode="contain",
        allow_upscale=False,
    )

    out = transform_background(src, settings)
    expected = src.resize((8, 6), Image.Resampling.LANCZOS)
    assert out.size == (8, 6)
    assert out.tobytes() == expected.tobytes()


def test_copy_assets_writes_transformed_background(tmp_path):
    from src.convert_mod import copy_assets

    source_dir = tmp_path / "legacy"
    release_dir = tmp_path / "release"
    source_dir.mkdir()
    src = Image.new("RGB", (4, 6))
    for y in range(6):
        for x in range(4):
            src.putpixel((x, y), (x * 40, y * 80, 20))
    source_path = source_dir / "background.png"
    src.save(source_path)
    parsed = {"initial_data": {"background": "background.png"}}
    settings = BackgroundTransform(
        enabled=True,
        target_size=(8, 6),
        fit_mode="contain",
        allow_upscale=False,
    )

    copied, missing, conflicts, logs = copy_assets(
        parsed,
        str(source_dir),
        str(release_dir),
        background_transform=settings,
        background_refs={"background.png"},
    )

    output_path = release_dir / "images" / "background.png"
    with Image.open(output_path) as result:
        expected = resize_contain(src, (8, 6))
        assert result.size == (8, 6)
        assert result.tobytes() == expected.tobytes()
        assert result.getpixel((0, 3)) == (0, 0, 0)
        assert result.getpixel((7, 3)) == (0, 0, 0)
    assert copied == ["images/background.png"]
    assert missing == []
    assert conflicts == []
    assert logs and "Scaled image: 4x6" in logs[0]


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
    # Full portrait content is scaled to 810x1080 and centered on black.
    assert out.crop((555, 0, 1365, 1080)).getbbox() == (0, 0, 810, 1080)
    assert out.getpixel((0, 540)) == (0, 0, 0)
    assert out.getpixel((960, 540)) == (255, 0, 0)


def test_contain_scales_full_image_and_adds_black_side_bars():
    src = Image.new("RGB", (600, 800))
    for y in range(src.height):
        for x in range(src.width):
            src.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))

    out = resize_contain(src, (1920, 1080))
    scaled = src.resize((810, 1080), Image.Resampling.LANCZOS)
    left = (1920 - 810) // 2

    assert out.size == (1920, 1080)
    assert out.crop((left, 0, left + 810, 1080)).tobytes() == scaled.tobytes()
    assert out.getpixel((0, 540)) == (0, 0, 0)
    assert out.getpixel((1919, 540)) == (0, 0, 0)
