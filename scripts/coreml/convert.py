"""YuNet ONNX -> Core ML (mlprogram), input of any size multiple of 32.

ONNX -> PyTorch (onnx2torch) -> TorchScript trace -> coremltools.
Writes YuNet-fp32.mlpackage and YuNet-fp16.mlpackage in the current directory.
"""

import coremltools as ct
import numpy as np
import torch
from onnx2torch import convert

from blurry_opsec import model

OUTS = [f"{k}_{s}" for k in ("cls", "obj", "bbox", "kps") for s in (8, 16, 32)]

net = convert(str(model.MODEL_PATH)).eval()
example = torch.rand(1, 3, 640, 640) * 255
with torch.no_grad():
    traced = torch.jit.trace(net, example)
    # The trace must not have frozen the 640x640 size.
    out = traced(torch.rand(1, 3, 480, 352) * 255)
    print("traced at 480x352 ->", [tuple(o.shape) for o in out])

# 32..8192 px per side (OpenCV pads to a multiple of 32).
shape = ct.Shape(shape=(1, 3, *(ct.RangeDim(32, 8192, default=640) for _ in range(2))))

for name, precision in (("fp32", ct.precision.FLOAT32), ("fp16", ct.precision.FLOAT16)):
    ml = ct.convert(
        traced,
        inputs=[ct.TensorType(name="input", shape=shape, dtype=np.float32)],
        outputs=[ct.TensorType(name=n) for n in OUTS],
        convert_to="mlprogram",
        compute_precision=precision,
        minimum_deployment_target=ct.target.iOS17,
    )
    ml.short_description = "YuNet 2023mar face detector (MIT, Shiqi Yu, OpenCV Zoo)"
    ml.save(f"YuNet-{name}.mlpackage")
    print("saved", name)
