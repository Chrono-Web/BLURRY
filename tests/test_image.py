"""Images: R3 metadata, R4 coverage, R6 formats, output rules, recall gate."""

import json
import shutil
import subprocess

import numpy as np
import pytest
from conftest import PUBLIC, need, run_blurry
from corpus import measure
from PIL import Image, ImageCms

# Recall measured on 2026-10-03 at the start of the project (level high, 56 of
# 59 hand-checked faces). CI fails if it ever drops below.
RECALL_FLOOR = 56 / 59

PRIVATE_KEYS = ("GPS", "XMP", "IPTC", "ICC", "Thumbnail", "Orientation", "Make", "Model",
                "DateTimeOriginal", "Creator", "Comment", "Description", "Copyright")  # fmt: skip


def leaked(tags: dict) -> list[str]:
    return [k for k in tags if any(p.lower() in k.lower() for p in PRIVATE_KEYS)]


def report(res) -> dict:
    return json.loads(res.stdout.strip().splitlines()[-1])


@pytest.fixture
def poisoned_jpeg(tmp_path):
    """Challenger crew, stored sideways with EXIF Orientation=6, plus GPS, XMP,
    IPTC, an ICC profile and an EXIF thumbnail of the original."""
    exiftool = need("exiftool")
    upright = Image.open(PUBLIC / "challenger_51l_crew.jpg").convert("RGB")
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    stored = upright.transpose(Image.Transpose.ROTATE_90)  # display = rotate 270 (orientation 6)
    src = tmp_path / "poisoned.jpg"
    stored.save(src, quality=92, icc_profile=icc)
    thumb = tmp_path / "thumb.jpg"
    upright.resize((160, 128)).save(thumb)
    subprocess.run(
        [exiftool, "-q", "-overwrite_original", "-Orientation#=6",
         "-GPSLatitude=45.4642", "-GPSLatitudeRef=N", "-GPSLongitude=9.19", "-GPSLongitudeRef=E",
         "-XMP:Creator=secret", "-IPTC:Keywords=secret", "-Make=Canon", "-Model=EOS R8",
         "-DateTimeOriginal=2026:01:02 03:04:05", f"-ThumbnailImage<={thumb}", str(src)],
        check=True,
    )  # fmt: skip
    return src


def test_jpeg_metadata_removed_and_orientation_applied(poisoned_jpeg, outdir):
    exif = need("exiftool")
    res = run_blurry(poisoned_jpeg, "-o", outdir, "--json")
    assert res.returncode == 0, res.stderr
    rep = report(res)
    assert rep["faces"] >= 7  # faces are only found once the image is upright
    assert {"gps", "xmp", "iptc", "exif_thumbnail", "orientation"} <= set(rep["metadata_removed"])
    out = outdir / rep["output"]
    tags = json.loads(
        subprocess.run(
            [exif, "-j", "-a", "-G1", str(out)], capture_output=True, text=True, check=True
        ).stdout
    )[0]
    assert not leaked(tags), leaked(tags)
    assert Image.open(out).size == Image.open(PUBLIC / "challenger_51l_crew.jpg").size


def test_heic_from_phone(outdir):
    exif = need("exiftool")
    res = run_blurry(PUBLIC / "sts125_gps.heic", "-o", outdir, "--json")
    assert res.returncode == 0, res.stderr
    rep = report(res)
    assert rep["output"].endswith(".jpg") and rep["faces"] >= 7
    tags = json.loads(
        subprocess.run(
            [exif, "-j", "-a", "-G1", str(outdir / rep["output"])],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )[0]
    assert not leaked(tags), leaked(tags)


def test_png_keeps_alpha_drops_text(tmp_path, outdir):
    im = Image.open(PUBLIC / "dental_squadron.jpg").convert("RGBA")
    a = np.array(im)
    a[:50, :50, 3] = 0
    from PIL import PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "secret")
    src = tmp_path / "alpha.png"
    Image.fromarray(a).save(src, pnginfo=info)
    res = run_blurry(src, "-o", outdir, "--json")
    assert res.returncode == 0, res.stderr
    out = Image.open(outdir / report(res)["output"])
    assert out.format == "PNG" and out.mode == "RGBA"
    assert not getattr(out, "text", {}) and "icc_profile" not in out.info
    assert np.array(out)[0, 0, 3] == 0


def test_solid_cover_is_black(outdir):
    res = run_blurry(PUBLIC / "dental_squadron.jpg", "-o", outdir, "--json")
    out = np.array(Image.open(outdir / report(res)["output"]))
    face = out[83 + 40 : 83 + 338 - 40, 1575 + 40 : 1575 + 223 - 40]  # inside the hand-checked box
    assert face.max() < 8  # JPEG noise only


def test_no_faces_warns_and_strict_exits_2(tmp_path, outdir):
    blank = tmp_path / "wall.png"
    Image.new("RGB", (400, 300), (128, 128, 128)).save(blank)
    res = run_blurry(blank, "-o", outdir, "--json")
    assert res.returncode == 0 and "no face found" in res.stderr
    assert any(f["kind"] == "no_faces" for f in report(res)["flags"])
    assert len(list(outdir.iterdir())) == 1
    strict_dir = tmp_path / "strict"
    strict_dir.mkdir()
    res = run_blurry(blank, "-o", strict_dir, "--strict", "--json")
    assert res.returncode == 2 and report(res)["status"] == "no_faces"
    assert not list(strict_dir.iterdir())


def test_no_faces_option_only_strips_metadata(poisoned_jpeg, outdir):
    res = run_blurry(poisoned_jpeg, "-o", outdir, "--no-faces", "--json")
    rep = report(res)
    assert res.returncode == 0 and rep.get("faces", 0) == 0
    assert "gps" in rep["metadata_removed"]
    assert "no face found" not in res.stderr


def test_never_overwrites(tmp_path):
    src = tmp_path / "photo.jpg"
    shutil.copy(PUBLIC / "dental_squadron.jpg", src)
    taken = tmp_path / "photo.blurry.jpg"
    taken.write_bytes(b"someone else's original")
    res = run_blurry(src, "--json")  # default: next to the original
    assert res.returncode == 0
    assert report(res)["output"] == "photo.blurry-2.jpg"
    assert taken.read_bytes() == b"someone else's original"
    assert src.read_bytes() == (PUBLIC / "dental_squadron.jpg").read_bytes()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]


@pytest.mark.parametrize("kind", ["gif", "webp", "png"])
def test_animated_images_refused(tmp_path, outdir, kind):
    frames = [Image.new("RGB", (64, 64), c) for c in ((255, 0, 0), (0, 255, 0))]
    src = tmp_path / f"anim.{kind}"
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=100, loop=0)
    res = run_blurry(src, "-o", outdir, "--json")
    assert res.returncode == 1 and report(res)["status"] == "error"
    assert not list(outdir.iterdir())


def test_unsupported_and_fake_files_refused(tmp_path, outdir):
    fake = tmp_path / "notes.jpg"
    fake.write_text("not an image")
    (tmp_path / "x.tiff").write_bytes(b"II*\x00")
    res = run_blurry(fake, tmp_path / "x.tiff", tmp_path / "missing.png", "-o", outdir, "--json")
    assert res.returncode == 1
    assert [json.loads(line)["status"] for line in res.stdout.splitlines()] == ["error"] * 3
    assert str(tmp_path) not in res.stderr + res.stdout  # no paths in messages


def test_watermark_is_off_by_default_and_optional(outdir, tmp_path):
    src = PUBLIC / "dental_squadron.jpg"
    plain = report(run_blurry(src, "-o", outdir, "--json"))["output"]
    marked_dir = tmp_path / "marked"
    marked_dir.mkdir()
    marked = report(run_blurry(src, "-o", marked_dir, "--watermark", "PRESS", "--json"))["output"]
    a = np.array(Image.open(outdir / plain)).astype(int)
    b = np.array(Image.open(marked_dir / marked)).astype(int)
    h, w = a.shape[:2]
    assert np.abs(a - b)[h // 2 - 20 : h // 2 + 20, w // 3 : 2 * w // 3].mean() > 5


def test_recall_does_not_regress():
    m = measure("high", 0.25)
    assert m["recall"] >= RECALL_FLOOR - 1e-9, m["files"]
    assert m["coverage"] >= RECALL_FLOOR - 1e-9, m["files"]
