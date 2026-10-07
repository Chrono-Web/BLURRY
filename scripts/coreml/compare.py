"""YuNet via Core ML vs the engine (cv2.FaceDetectorYN), on the same BGR pixels.

1. decode() on OpenCV DNN's raw outputs must give exactly what FaceDetectorYN
   gives: this proves the decode + NMS (to be ported to Swift) is faithful.
2. The same decode on Core ML's outputs (fp32/fp16, CPU only / all units) is
   compared box by box with the engine.
Also writes data/*.bgr + data/index.json + data/reference.json for the Swift run.
Run from the work directory that holds the .mlpackage files (prova-yunet.sh does).
Exits with an error if fp32 is not identical to the engine.
"""

import json
import sys
import time
from pathlib import Path

import coremltools as ct
import cv2
import numpy as np

from blurry_opsec import image_io, levels, model
from blurry_opsec.detect import FaceDetector

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests/fixtures"
DATA = Path("data")
STRIDES = (8, 16, 32)
OUTS = [f"{k}_{s}" for k in ("cls", "obj", "bbox", "kps") for s in STRIDES]
THRESH = levels.LEVELS[levels.MOST_SENSITIVE].confidence  # 0.5: what the engine runs at
LEVEL_THRESHOLDS = sorted({lv.confidence for lv in levels.LEVELS.values()})


def images():
    for p in sorted(FIX.glob("public/*")) + sorted(FIX.glob("private/*")):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
            bgr = cv2.cvtColor(image_io.load(p).rgb, cv2.COLOR_RGB2BGR)
            yield p.name, bgr
            h, w = bgr.shape[:2]
            half = (w // 2 + 1, h // 2 + 1)
            yield f"{p.stem}@half", cv2.resize(bgr, half, interpolation=cv2.INTER_AREA)
    # Phone-sized photo (12 MP, 4:3) and a portrait one.
    src = cv2.cvtColor(image_io.load(FIX / "public/sts125_crew.jpg").rgb, cv2.COLOR_RGB2BGR)
    yield "sts125@4032x3024", cv2.resize(src, (4032, 3024), interpolation=cv2.INTER_CUBIC)
    yield "sts125@rot90", cv2.rotate(src, cv2.ROTATE_90_CLOCKWISE)


def pad(bgr):
    h, w = bgr.shape[:2]
    ph, pw = (h - 1) // 32 * 32 + 32, (w - 1) // 32 * 32 + 32
    padded = cv2.copyMakeBorder(bgr, 0, ph - h, 0, pw - w, cv2.BORDER_CONSTANT, value=0)
    return padded, pw, ph


def blob(padded):
    return cv2.dnn.blobFromImage(padded)  # float32 NCHW, BGR, 0..255, no mean


def iou_int(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = min(ax + aw, bx + bw) - max(ax, bx)
    ih = min(ay + ah, by + bh) - max(ay, by)
    inter = iw * ih if iw > 0 and ih > 0 else 0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def nms(rects, scores, score_thr, nms_thr, top_k):
    """cv::dnn::NMSBoxes on Rect2i: score > thr, stable sort desc, top_k, IoU <= nms_thr."""
    cand = [i for i, s in enumerate(scores) if s > score_thr]
    cand.sort(key=lambda i: -scores[i])  # Python sort is stable, like std::stable_sort
    cand = cand[:top_k] if top_k > 0 else cand
    keep = []
    for i in cand:
        if all(iou_int(rects[i], rects[k]) <= nms_thr for k in keep):
            keep.append(i)
    return keep


def decode(outs, pw, ph, score_thr=THRESH):
    """FaceDetectorYN::postProcess. outs: name -> array. Returns rows [x,y,w,h,kps*10,score]."""
    rows = []
    for s in STRIDES:
        cols = pw // s
        cls = np.clip(outs[f"cls_{s}"].reshape(-1), 0, 1)
        obj = np.clip(outs[f"obj_{s}"].reshape(-1), 0, 1)
        bbox = outs[f"bbox_{s}"].reshape(-1, 4)
        kps = outs[f"kps_{s}"].reshape(-1, 10)
        score = np.sqrt(cls * obj).astype(np.float32)
        idx = np.arange(score.size)
        c = (idx % cols).astype(np.float32)
        r = (idx // cols).astype(np.float32)
        cx = (c + bbox[:, 0]) * s
        cy = (r + bbox[:, 1]) * s
        w = np.exp(bbox[:, 2]) * s
        h = np.exp(bbox[:, 3]) * s
        k = np.empty_like(kps)
        k[:, 0::2] = (kps[:, 0::2] + c[:, None]) * s
        k[:, 1::2] = (kps[:, 1::2] + r[:, None]) * s
        rows.append(np.column_stack([cx - w / 2, cy - h / 2, w, h, k, score]).astype(np.float32))
    faces = np.concatenate(rows)
    rects = [tuple(int(v) for v in f[:4]) for f in faces]  # int(): truncation, like Rect2i
    keep = nms(rects, faces[:, 14].tolist(), score_thr, levels.YUNET_NMS, levels.YUNET_TOPK)
    return faces[keep]


def clip_boxes(faces, w, h):
    """Same as FaceDetector.detect: int(), clip to the image."""
    out = []
    for f in faces:
        x, y, bw, bh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
        x, y = max(0, x), max(0, y)
        bw, bh = min(w - x, bw), min(h - y, bh)
        if bw > 0 and bh > 0:
            out.append((x, y, bw, bh, float(f[-1])))
    return out


def match(ref, got):
    """Greedy IoU match. Returns (missing, extra, max coord diff, max score diff, exact)."""
    used, dmax, smax, missing = set(), 0, 0.0, []
    for r in ref:
        best, bi = 0.0, None
        for i, g in enumerate(got):
            if i not in used and (v := iou_int(r[:4], g[:4])) > best:
                best, bi = v, i
        if bi is None or best < 0.5:
            missing.append(r)
            continue
        used.add(bi)
        g = got[bi]
        dmax = max(dmax, max(abs(a - b) for a, b in zip(r[:4], g[:4], strict=True)))
        smax = max(smax, abs(r[4] - g[4]))
    extra = [g for i, g in enumerate(got) if i not in used]
    exact = not missing and not extra and dmax == 0
    return missing, extra, dmax, smax, exact


def main():
    DATA.mkdir(exist_ok=True)
    det = FaceDetector(levels.MOST_SENSITIVE)
    dnn = cv2.dnn.readNetFromONNX(str(model.MODEL_PATH))
    variants = {
        f"{p}/{u}": ct.models.MLModel(
            f"YuNet-{p}.mlpackage", compute_units=getattr(ct.ComputeUnit, u)
        )
        for p in ("fp32", "fp16")
        for u in ("CPU_ONLY", "ALL")
    }
    index, reference = [], {}
    totals = {
        k: {"exact": 0, "missing": 0, "extra": 0, "dmax": 0, "smax": 0.0, "t": 0.0}
        for k in variants
    }
    raw_diff = {k: 0.0 for k in variants}
    n_ref = 0

    for name, bgr in images():
        h, w = bgr.shape[:2]
        bgr = np.ascontiguousarray(bgr)
        (DATA / f"{len(index):02d}.bgr").write_bytes(bgr.tobytes())
        index.append({"file": f"{len(index):02d}.bgr", "name": name, "w": w, "h": h})

        ref = det.detect(bgr)
        ref = [(b.x, b.y, b.w, b.h, b.score) for b in ref]
        reference[name] = ref
        n_ref += len(ref)

        padded, pw, ph = pad(bgr)
        x = blob(padded)
        dnn.setInput(x)
        cv_out = dict(zip(OUTS, dnn.forward(OUTS), strict=True))
        mine = clip_boxes(decode(cv_out, pw, ph), w, h)
        m = match(ref, mine)
        if not (m[4] and m[3] < 1e-6):
            sys.exit(f"decode() differs from FaceDetectorYN on {name}: {m}")

        line = [f"{name:28s} {w}x{h:<5d} faces={len(ref):2d}"]
        for k, ml in variants.items():
            t0 = time.perf_counter()
            out = ml.predict({"input": x})
            totals[k]["t"] += time.perf_counter() - t0
            ml_out = {n: np.asarray(out[n], dtype=np.float32) for n in OUTS}
            for n in ("cls_8", "obj_8", "cls_32", "obj_32"):
                raw_diff[k] = max(raw_diff[k], float(np.abs(ml_out[n] - cv_out[n]).max()))
            got = clip_boxes(decode(ml_out, pw, ph), w, h)
            missing, extra, dmax, smax, exact = match(ref, got)
            tt = totals[k]
            tt["exact"] += exact
            tt["missing"] += len(missing)
            tt["extra"] += len(extra)
            tt["dmax"] = max(tt["dmax"], dmax)
            tt["smax"] = max(tt["smax"], smax)
            tag = "=" if exact else f"Δ{dmax}px -{len(missing)} +{len(extra)}"
            if missing or extra:
                tag += " " + " ".join(
                    f"[{'-' if b in missing else '+'}{b[4]:.3f}]" for b in missing + extra
                )
            line.append(f"{k}:{tag}")
        print("  ".join(line))

    (DATA / "index.json").write_text(json.dumps(index, indent=1))
    (DATA / "reference.json").write_text(json.dumps(reference))
    print(f"\n{len(index)} images, {n_ref} faces from the engine (threshold {THRESH})")
    print("decode() on OpenCV DNN outputs == FaceDetectorYN on every image")
    for k, tt in totals.items():
        print(
            f"{k:14s} identical images {tt['exact']}/{len(index)}  missing {tt['missing']}  "
            f"extra {tt['extra']}  max Δbox {tt['dmax']}px  max Δscore {tt['smax']:.4f}  "
            f"max Δraw score {raw_diff[k]:.4f}  time {tt['t']:.1f}s"
        )
    bad = [k for k, tt in totals.items() if k.startswith("fp32") and tt["exact"] != len(index)]
    if bad:
        sys.exit(f"fp32 differs from the engine: {', '.join(bad)}")


if __name__ == "__main__":
    main()
