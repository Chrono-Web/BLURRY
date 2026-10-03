"""Image reading and clean writing, entirely in memory.

Reading applies the EXIF orientation to the pixels and converts any colour
profile to sRGB. Writing re-encodes the pixels only: no EXIF (and so no EXIF
thumbnail, which can hold the uncovered original), no XMP, IPTC, ICC or text
chunks.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pi_heif
from PIL import ExifTags, Image, ImageCms, ImageOps

from blurry_opsec.files import InputError, check_regular_file

pi_heif.register_heif_opener()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_PIXELS = 120_000_000
MAX_FILE_BYTES = 300 * 1024 * 1024

# Pillow format name -> output format and extension.
_OUTPUT = {
    "JPEG": ("JPEG", "jpg"),
    "HEIF": ("JPEG", "jpg"),
    "WEBP": ("JPEG", "jpg"),
    "PNG": ("PNG", "png"),
}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)


@dataclass
class LoadedImage:
    rgb: np.ndarray  # HxWx3 uint8, display orientation, sRGB
    alpha: np.ndarray | None
    source_format: str
    out_format: str
    out_ext: str
    metadata_found: list[str] = field(default_factory=list)


def _metadata_found(im: Image.Image) -> list[str]:
    found: set[str] = set()
    exif = im.getexif()
    if len(exif):
        found.add("exif")
        if exif.get_ifd(ExifTags.IFD.GPSInfo):
            found.add("gps")
        if ExifTags.Base.Orientation in exif and exif[ExifTags.Base.Orientation] != 1:
            found.add("orientation")
        try:
            if exif.get_ifd(ExifTags.IFD.IFD1):
                found.add("exif_thumbnail")
        except (KeyError, AttributeError):
            pass
    info = im.info
    if info.get("exif"):
        found.add("exif")
    if info.get("xmp") or info.get("XML:com.adobe.xmp"):
        found.add("xmp")
    if info.get("photoshop") or any(m == "APP13" for m, _ in getattr(im, "applist", [])):
        found.add("iptc")
    if info.get("icc_profile"):
        found.add("icc_profile")
    if info.get("comment"):
        found.add("comment")
    if getattr(im, "text", None):
        found.add("text_chunks")
    if info.get("thumbnails"):
        found.add("embedded_thumbnails")
    if info.get("depth_images"):
        found.add("depth_map")
    return sorted(found)


def _to_srgb(im: Image.Image) -> Image.Image:
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        dst = ImageCms.createProfile("sRGB")
        out_mode = "RGBA" if im.mode == "RGBA" else "RGB"
        if im.mode not in ("RGB", "RGBA", "CMYK", "L"):
            im = im.convert(out_mode)
        return ImageCms.profileToProfile(im, src, dst, outputMode=out_mode)
    except (ImageCms.PyCMSError, OSError, ValueError):
        # A broken profile only affects colours, never what is covered.
        return im


def load(path: Path) -> LoadedImage:
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise InputError("unsupported image type (accepted: JPEG, PNG, WebP, HEIC)")
    check_regular_file(path, MAX_FILE_BYTES)
    data = path.read_bytes()
    try:
        im = Image.open(io.BytesIO(data))
    except Image.DecompressionBombWarning as exc:
        raise InputError("image too large") from exc
    except (Image.DecompressionBombError, OSError) as exc:
        raise InputError("not a readable image") from exc

    fmt = im.format or ""
    if fmt == "GIF":
        raise InputError("GIF is not supported")
    if fmt not in _OUTPUT:
        raise InputError("unsupported image format (accepted: JPEG, PNG, WebP, HEIC)")
    if fmt in ("PNG", "WEBP") and getattr(im, "is_animated", False):
        raise InputError("animated images are not supported")
    if im.width * im.height > MAX_PIXELS:
        raise InputError("image too large")

    found = _metadata_found(im)
    try:
        im.load()
    except (OSError, Image.DecompressionBombWarning) as exc:
        raise InputError("image is damaged or too large") from exc

    im = ImageOps.exif_transpose(im) or im
    if im.mode in ("P", "PA", "LA", "La", "I", "I;16", "F", "1"):
        im = im.convert("RGBA" if "A" in im.mode or "transparency" in im.info else "RGB")
    im = _to_srgb(im)

    alpha = None
    if im.mode == "RGBA":
        alpha_plane = np.array(im.getchannel("A"))
        if alpha_plane.min() < 255:
            alpha = alpha_plane
    rgb = np.array(im.convert("RGB"))
    out_format, out_ext = _OUTPUT[fmt]
    if out_format == "JPEG" and alpha is not None:
        # JPEG has no transparency: flatten on white, like most viewers show it.
        a = alpha.astype(np.float32)[..., None] / 255.0
        rgb = (rgb.astype(np.float32) * a + 255.0 * (1.0 - a) + 0.5).astype(np.uint8)
        alpha = None
    return LoadedImage(rgb, alpha, fmt, out_format, out_ext, found)


def encode(rgb: np.ndarray, alpha: np.ndarray | None, out_format: str) -> bytes:
    """Encode pixels only. A brand-new Image carries no info dict, so nothing
    from the source can leak into the file."""
    im = Image.fromarray(np.ascontiguousarray(rgb), "RGB")
    if alpha is not None:
        im.putalpha(Image.fromarray(alpha, "L"))
    buf = io.BytesIO()
    if out_format == "JPEG":
        im.save(buf, "JPEG", quality=95, optimize=True)
    else:
        im.save(buf, "PNG")
    return buf.getvalue()
