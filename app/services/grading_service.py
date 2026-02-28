"""
OpenCV-based crop image grading service.

Pipeline:
1. CLAHE illumination normalization (LAB color space)
2. Otsu binarization for background segmentation
3. HSV freshness analysis (green_ratio − 2×brown_ratio)
4. Laplacian variance for sharpness
5. Optional DNN INT8 path via cv2.dnn (loaded from grading_model.onnx if present)
"""
from pathlib import Path

import cv2
import numpy as np

_MODEL_PATH = Path(__file__).parent.parent / "models_ml" / "grading_model.onnx"
_dnn_net = None


def _load_dnn_net():
    global _dnn_net
    if _MODEL_PATH.exists() and _dnn_net is None:
        try:
            _dnn_net = cv2.dnn.readNetFromONNX(str(_MODEL_PATH))
        except Exception:
            _dnn_net = None
    return _dnn_net


def grade_crop_image_bytes(image_bytes: bytes) -> tuple[str, float]:
    """
    Grade a crop image from raw bytes.
    Returns (grade: "A"|"B"|"C", confidence_score: float 0-1).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return "C", 0.0

    # ------------------------------------------------------------------
    # Step 1: Illumination normalisation via CLAHE on LAB L-channel
    # ------------------------------------------------------------------
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_norm = clahe.apply(l_channel)
    lab_norm = cv2.merge([l_norm, a_channel, b_channel])
    img_norm = cv2.cvtColor(lab_norm, cv2.COLOR_LAB2BGR)

    # ------------------------------------------------------------------
    # Step 2: Otsu binarization — segment produce from background
    # ------------------------------------------------------------------
    gray = cv2.cvtColor(img_norm, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    total_pixels = mask.size
    foreground_pixels = int(np.count_nonzero(mask))
    if foreground_pixels == 0:
        foreground_pixels = total_pixels  # safety guard

    # ------------------------------------------------------------------
    # Step 3: HSV freshness analysis (restricted to foreground)
    # ------------------------------------------------------------------
    hsv = cv2.cvtColor(img_norm, cv2.COLOR_BGR2HSV)

    green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
    brown_mask = cv2.inRange(hsv, np.array([10, 40, 20]), np.array([30, 255, 150]))

    green_ratio = int(np.count_nonzero(cv2.bitwise_and(green_mask, mask))) / foreground_pixels
    brown_ratio = int(np.count_nonzero(cv2.bitwise_and(brown_mask, mask))) / foreground_pixels

    freshness_score = max(0.0, green_ratio - 2.0 * brown_ratio)

    # ------------------------------------------------------------------
    # Step 4: Sharpness via Laplacian variance
    # ------------------------------------------------------------------
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # ------------------------------------------------------------------
    # Step 5: Optional DNN path
    # ------------------------------------------------------------------
    net = _load_dnn_net()
    if net is not None:
        try:
            blob = cv2.dnn.blobFromImage(
                img_norm,
                scalefactor=1.0 / 255.0,
                size=(224, 224),
                swapRB=True,
                crop=False,
            )
            net.setInput(blob)
            outputs = net.forward()
            # Expect outputs shape (1, 3) for classes A/B/C
            probs = outputs[0]
            grade_idx = int(np.argmax(probs))
            confidence = float(probs[grade_idx])
            grade = ["A", "B", "C"][min(grade_idx, 2)]
            return grade, round(confidence, 3)
        except Exception:
            pass  # Fall through to classical path

    # ------------------------------------------------------------------
    # Classical grade decision
    # ------------------------------------------------------------------
    if freshness_score > 0.30 and sharpness > 100:
        grade = "A"
        confidence = min(1.0, (freshness_score + sharpness / 500) / 2)
    elif freshness_score > 0.10 or sharpness > 50:
        grade = "B"
        confidence = min(0.75, freshness_score + sharpness / 1000)
    else:
        grade = "C"
        confidence = max(0.0, 1.0 - freshness_score)

    return grade, round(confidence, 3)
