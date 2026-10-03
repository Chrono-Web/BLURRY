"""Bundled YuNet face detection model (MIT, Shiqi Yu, OpenCV Zoo)."""

from pathlib import Path

MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_PATH = Path(__file__).with_name(MODEL_FILENAME)
