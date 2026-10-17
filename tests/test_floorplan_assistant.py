"""Image-derived proposals, profile symbols and upload decoding boundaries."""

from copy import deepcopy
from io import BytesIO

import pytest
from iqalarm_core.floorplan_analysis import analyze_image
from iqalarm_core.floorplan_image import prepare_image
from iqalarm_core.models import Configuration, FloorPlan, Profile
from PIL import Image, ImageDraw


def make_plan(tmp_path, *, gap=0, size=(500, 300), color="black"):
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 470, 270), outline=color, width=6)
    draw.line((250, 30, 250, 270), fill=color, width=6)
    if gap:
        draw.rectangle((245, 140, 255, 140 + gap), fill="white")
    path = tmp_path / "floor.png"
    image.save(path)
    return path


@pytest.mark.parametrize("color", ["black", "#bc4517", "#3d454e"])
def test_room_proposals_follow_separating_wall_and_normalized_geometry(tmp_path, color):
    path = make_plan(tmp_path, color=color)
    result = analyze_image(path, 0)
    assert len(result["candidates"]) == 2
    for proposal in result["candidates"]:
        FloorPlan("eg", "EG", zones={"room": proposal["points"]})
        assert 3 <= len(proposal["points"]) <= 64
        assert all(0 <= value <= 1 for point in proposal["points"] for value in point)
    assert sorted(p["center"][0] for p in result["candidates"]) == pytest.approx(
        [0.28, 0.72], abs=0.02
    )


def test_door_openings_can_be_closed_without_inventing_a_wall_in_open_space(tmp_path):
    path = make_plan(tmp_path, gap=12)
    assert len(analyze_image(path, 0)["candidates"]) == 1
    assert len(analyze_image(path, 18)["candidates"]) == 2


def test_outside_and_blank_images_never_become_rooms(tmp_path):
    for color in ("white", "black"):
        path = tmp_path / f"{color}.png"
        Image.new("RGB", (200, 150), color).save(path)
        assert analyze_image(path)["candidates"] == []


def test_concave_area_retains_more_than_a_bounding_rectangle(tmp_path):
    image = Image.new("RGB", (320, 320), "white")
    ImageDraw.Draw(image).polygon(
        [(30, 30), (290, 30), (290, 140), (140, 140), (140, 290), (30, 290)],
        outline="black",
        width=6,
    )
    path = tmp_path / "concave.png"
    image.save(path)
    proposals = analyze_image(path, 0)["candidates"]
    assert len(proposals) == 1
    assert len(proposals[0]["points"]) >= 6
    FloorPlan("eg", "EG", zones={"room": proposals[0]["points"]})


def test_image_analysis_is_bounded_and_does_not_modify_source(tmp_path):
    path = make_plan(tmp_path)
    with Image.open(path) as image:
        image.resize((2000, 1200)).save(path)
    before = path.read_bytes()
    result = analyze_image(path, 18)
    assert max(result["analysis_width"], result["analysis_height"]) <= 640
    assert len(result["candidates"]) == 2
    assert path.read_bytes() == before


def test_number_of_proposals_is_bounded(tmp_path):
    image = Image.new("RGB", (610, 410), "white")
    draw = ImageDraw.Draw(image)
    for y in range(5):
        for x in range(8):
            draw.rectangle(
                (10 + x * 73, 10 + y * 78, 75 + x * 73, 80 + y * 78), outline="black", width=4
            )
    path = tmp_path / "many.png"
    image.save(path)
    proposals = analyze_image(path, 0)["candidates"]
    assert len(proposals) == 30
    assert len({p["id"] for p in proposals}) == 30


@pytest.mark.parametrize("gap", [-1, 41, True, 18.1, "18"])
def test_invalid_analysis_setting_is_rejected(tmp_path, gap):
    with pytest.raises(ValueError):
        analyze_image(make_plan(tmp_path), gap)


def test_transparent_floorplans_use_white_background_and_keep_wall_pixels():
    image = Image.new("RGBA", (100, 80), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((10, 10, 90, 70), outline="black", width=4)
    payload = BytesIO()
    image.save(payload, "PNG")
    pixels, width, height = prepare_image(payload.getvalue())
    with Image.open(BytesIO(pixels)) as clean:
        assert clean.getpixel((0, 0)) == (255, 255, 255)
        assert clean.getpixel((10, 10)) == (0, 0, 0)
        assert (width, height) == (100, 80)


def test_phone_orientation_is_applied_before_geometry_is_created():
    image = Image.new("RGB", (60, 100), "white")
    exif = Image.Exif()
    exif[274] = 6
    payload = BytesIO()
    image.save(payload, "JPEG", exif=exif)
    pixels, width, height = prepare_image(payload.getvalue())
    assert (width, height) == (100, 60)
    with Image.open(BytesIO(pixels)) as clean:
        assert not clean.getexif()


@pytest.mark.parametrize("payload", [b"", b"<svg/>", b"not an image", b"\x89PNG\r\n\x1a\n"])
def test_corrupt_or_unsupported_uploads_are_rejected(payload):
    with pytest.raises(ValueError):
        prepare_image(payload)


@pytest.mark.parametrize(
    "name,symbol",
    [
        ("Zuhause", "home-outline"),
        ("Nacht", "weather-night"),
        ("Abwesend", "home-export-outline"),
        ("Urlaub", "palm-tree"),
        ("Besuch", "account-group-outline"),
    ],
)
def test_missing_profile_symbols_receive_appropriate_defaults(config, name, symbol):
    config.profiles["custom"] = Profile(name=name + " Test")
    migrated = Configuration.from_dict(config.to_dict())
    assert migrated.profiles["custom"].icon == "mdi:" + symbol


def test_custom_icon_and_profile_order_survive_edit_copy_and_roundtrip(config):
    config.profiles["guests"] = Profile(name="Besuch", icon="mdi:dog", motion_mode="ignore")
    config.validate()
    data = config.to_dict()
    data["profiles"]["copy"] = deepcopy(data["profiles"]["guests"])
    data["profiles"]["copy"]["name"] = "Kopie"
    migrated = Configuration.from_dict(data)
    assert list(migrated.profiles) == list(data["profiles"])
    assert migrated.profiles["copy"].icon == "mdi:dog"
    assert migrated.profiles["copy"].motion_mode == "ignore"


@pytest.mark.parametrize(
    "icon", ["<img>", 'mdi:home" onload=x', "javascript:alert", "mdi:", "MDI:home", 5]
)
def test_profile_icon_rejects_invalid_or_executable_strings(icon):
    with pytest.raises(ValueError):
        Profile(name="Test", icon=icon)
