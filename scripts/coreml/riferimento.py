"""What the Python engine does, written to build/parity/ for BlurryKit's tests.

    uv run python scripts/coreml/riferimento.py

For every public fixture: the pixels as the engine decodes them (lossless PNG),
the boxes at the most sensitive level, the plan and flags at every level, and
the solid and pixel renders of those same pixels. Plus files that exercise
reading: metadata, orientation, colour profiles, alpha, refusals.
Needs exiftool for the poisoned JPEG (macOS: brew install exiftool).
"""

import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageCms, PngImagePlugin

from blurry_opsec import engine, image_io, levels, redact
from blurry_opsec.detect import FaceDetector
from blurry_opsec.files import InputError
from blurry_opsec.plan import ImagePlan

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "tests/fixtures/public"
OUT = ROOT / "build/parity"
P3 = Path("/System/Library/ColorSync/Profiles/Display P3.icc")


def box_list(boxes):
    return [[b.x, b.y, b.w, b.h, b.score] for b in boxes]


def save_png(path: Path, rgb: np.ndarray, alpha: np.ndarray | None = None) -> None:
    im = Image.fromarray(np.ascontiguousarray(rgb), "RGB")
    if alpha is not None:
        im.putalpha(Image.fromarray(alpha, "L"))
    im.save(path, "PNG")


def loaded_entry(path: Path, decoded: str | None = None) -> dict:
    """What image_io.load reports; with `decoded`, also the pixels it returns."""
    try:
        loaded = image_io.load(path)
    except InputError as exc:
        return {"error": str(exc)}
    h, w = loaded.rgb.shape[:2]
    if decoded:
        save_png(OUT / decoded, loaded.rgb, loaded.alpha)
    return {
        "decoded": decoded,
        "width": w,
        "height": h,
        "out_format": loaded.out_format,
        "out_ext": loaded.out_ext,
        "metadata_found": loaded.metadata_found,
        "has_alpha": loaded.alpha is not None,
    }


def make_extra(d: Path) -> list[Path]:
    """Files that test reading. Built here, never committed."""
    d.mkdir(parents=True, exist_ok=True)
    made = []
    upright = Image.open(PUBLIC / "challenger_51l_crew.jpg").convert("RGB")

    # Same as tests/test_image.py: stored sideways, Orientation=6, GPS, XMP,
    # IPTC, Make/Model, an sRGB ICC profile and an EXIF thumbnail.
    exiftool = shutil.which("exiftool")
    if exiftool:
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        src = d / "poisoned.jpg"
        upright.transpose(Image.Transpose.ROTATE_90).save(src, quality=92, icc_profile=icc)
        thumb = d / "thumb.tmp.jpg"
        upright.resize((160, 128)).save(thumb)
        subprocess.run(  # noqa: S603
            [exiftool, "-q", "-overwrite_original", "-Orientation#=6",
             "-GPSLatitude=45.4642", "-GPSLatitudeRef=N", "-GPSLongitude=9.19",
             "-GPSLongitudeRef=E", "-XMP:Creator=secret", "-IPTC:Keywords=secret",
             "-Make=Canon", "-Model=EOS R8", "-DateTimeOriginal=2026:01:02 03:04:05",
             "-Comment=secret", f"-ThumbnailImage<={thumb}", str(src)],
            check=True,
        )  # fmt: skip
        thumb.unlink()
        made.append(src)
    else:
        print("exiftool missing: poisoned.jpg skipped")

    # Every EXIF orientation, on a non-square crop.
    crop = upright.crop((0, 0, 1200, 700))
    stored_for = {
        2: Image.Transpose.FLIP_LEFT_RIGHT,
        3: Image.Transpose.ROTATE_180,
        4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE,
        6: Image.Transpose.ROTATE_90,
        7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_270,
    }
    for orientation, op in stored_for.items():
        exif = Image.Exif()
        exif[0x0112] = orientation
        src = d / f"orientation{orientation}.jpg"
        crop.transpose(op).save(src, quality=95, exif=exif)
        made.append(src)

    if P3.exists():
        src = d / "display_p3.jpg"
        upright.save(src, quality=95, icc_profile=P3.read_bytes())
        made.append(src)

    rgba = np.array(Image.open(PUBLIC / "dental_squadron.jpg").convert("RGBA"))
    rgba[:50, :50, 3] = 0
    rgba[50:100, :50, 3] = 128
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "secret")
    src = d / "alpha_text.png"
    Image.fromarray(rgba).save(src, pnginfo=info)
    made.append(src)
    src = d / "alpha.webp"
    Image.fromarray(rgba).save(src, lossless=True)
    made.append(src)

    gray = d / "gray.png"
    upright.convert("L").save(gray)
    made.append(gray)

    frames = [Image.new("RGB", (64, 64), c) for c in ((255, 0, 0), (0, 255, 0))]
    for kind in ("gif", "webp", "png"):
        src = d / f"anim.{kind}"
        frames[0].save(src, save_all=True, append_images=frames[1:], duration=100, loop=0)
        made.append(src)
    (d / "notes.jpg").write_text("not an image")
    (d / "x.tiff").write_bytes(b"II*\x00")
    made += [d / "notes.jpg", d / "x.tiff"]
    return made


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    for sub in ("decoded", "renders"):
        (OUT / sub).mkdir(parents=True)
    det = FaceDetector(levels.MOST_SENSITIVE)
    level = levels.get(levels.DEFAULT_LEVEL)

    fixtures = {}
    for path in sorted(PUBLIC.iterdir()):
        if path.suffix.lower() not in image_io.IMAGE_EXTENSIONS:
            continue
        loaded = image_io.load(path)
        h, w = loaded.rgb.shape[:2]
        boxes = det.detect(cv2.cvtColor(loaded.rgb, cv2.COLOR_RGB2BGR))
        plan = ImagePlan(w, h, boxes)
        plan.flags = engine.image_flags(plan, det.confidence)
        stem = path.stem
        save_png(OUT / "decoded" / f"{stem}.png", loaded.rgb)
        renders = {}
        for mode in levels.MODES:
            out = redact.apply(loaded.rgb.copy(), boxes, mode, levels.DEFAULT_PADDING, level.blocks)
            renders[mode] = f"renders/{stem}-{mode}.png"
            save_png(OUT / renders[mode], out)
        fixtures[path.name] = {
            **loaded_entry(path, f"decoded/{stem}.png"),
            "source": str(path.relative_to(ROOT)),
            "boxes": box_list(boxes),
            "plans": {
                name: {
                    "boxes": box_list(at.boxes),
                    "flags": [f.to_dict() for f in at.flags],
                }
                for name, lv in levels.LEVELS.items()
                for at in [engine.image_plan_at(plan, lv.confidence)]
            },
            "padding": levels.DEFAULT_PADDING,
            "blocks": level.blocks,
            "renders": renders,
        }

    extra = {
        p.name: loaded_entry(p, f"decoded/extra-{p.name}.png") for p in make_extra(OUT / "extra")
    }
    (OUT / "reference.json").write_text(
        json.dumps({"fixtures": fixtures, "extra": extra}, indent=1)
    )
    print(f"{len(fixtures)} fixtures, {len(extra)} extra files -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
