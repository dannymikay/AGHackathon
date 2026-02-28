"""
Crop image grading service.

Primary:  Google Cloud Vision API — label detection + image properties.
Fallback: OpenCV CLAHE + Otsu + HSV pipeline (works with no API key).

Public interface:
    grade_crop_image_bytes(image_bytes: bytes) -> tuple[str, float]
Returns (grade, confidence) where grade is "A", "B", or "C".
"""
import logging

logger = logging.getLogger(__name__)

# ── Vision API keyword sets ────────────────────────────────────────────────
_DAMAGE_KEYWORDS = {
    "damaged", "rotten", "bruised", "moldy", "mouldy",
    "discolored", "discoloured", "wilted", "spoiled", "decayed",
    "overripe", "blemished", "wrinkled", "shriveled",
}
_PREMIUM_KEYWORDS = {
    "fresh", "ripe", "healthy", "vibrant", "organic",
    "clean", "bright", "crisp", "firm", "juicy",
}


def _grade_with_vision_api(image_bytes: bytes) -> tuple[str, float] | None:
    """
    Use Google Cloud Vision API to grade produce.

    Returns (grade, confidence) mapped to AgriMatch A/B/C scale, or None if
    the API key is absent, the import fails, or the request errors out.
    The caller falls back to OpenCV when None is returned.
    """
    from app.config import settings

    if not settings.GOOGLE_CLOUD_VISION_API_KEY:
        return None

    try:
        from google.cloud import vision  # type: ignore[import-untyped]

        client = vision.ImageAnnotatorClient(
            client_options={"api_key": settings.GOOGLE_CLOUD_VISION_API_KEY}
        )
        image = vision.Image(content=image_bytes)
        response = client.annotate_image({
            "image": image,
            "features": [
                {"type_": vision.Feature.Type.LABEL_DETECTION, "max_results": 10},
                {"type_": vision.Feature.Type.IMAGE_PROPERTIES},
            ],
        })

        if response.error.message:
            # Log type only — avoid leaking API key in error detail strings
            logger.warning("Vision API error (code %s)", response.error.code)
            return None

        labels = {label.description.lower() for label in response.label_annotations}

        damage_score = sum(1 for kw in _DAMAGE_KEYWORDS if kw in labels)
        premium_score = sum(1 for kw in _PREMIUM_KEYWORDS if kw in labels)

        if damage_score == 0 and premium_score >= 1:
            return "A", 0.90
        elif damage_score >= 1:
            return "B", 0.85
        else:
            # Uncertain — default B (conservative; better to under-promise grade)
            return "B", 0.70

    except Exception as exc:
        # Log class name only — exc.__str__ may contain request URLs with the API key
        logger.warning("Vision API unavailable (%s), falling back to OpenCV", type(exc).__name__)
        return None


def _grade_with_opencv(image_bytes: bytes) -> tuple[str, float]:
    """
    OpenCV CLAHE + Otsu binarisation + HSV freshness analysis.

    Pipeline:
      1. CLAHE illumination normalisation (LAB L-channel)
      2. Otsu binarisation — segment produce from background
      3. HSV freshness score (green_ratio − 2 × brown_ratio)
      4. Laplacian variance for sharpness
      5. Optional DNN INT8 path via cv2.dnn (grading_model.onnx)
    """
    from pathlib import Path

    import cv2
    import numpy as np

    _MODEL_PATH = Path(__file__).parent.parent / "models_ml" / "grading_model.onnx"

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return "C", 0.0

    # Step 1: CLAHE normalisation
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_norm = clahe.apply(l_channel)
    img_norm = cv2.cvtColor(
        cv2.merge([l_norm, a_channel, b_channel]), cv2.COLOR_LAB2BGR
    )

    # Step 2: Otsu binarisation
    gray = cv2.cvtColor(img_norm, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    foreground_pixels = int(np.count_nonzero(mask)) or mask.size

    # Step 3: HSV freshness
    hsv = cv2.cvtColor(img_norm, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    brown_mask = cv2.inRange(hsv, (10, 40, 20), (30, 255, 150))
    green_ratio = int(np.count_nonzero(cv2.bitwise_and(green_mask, mask))) / foreground_pixels
    brown_ratio = int(np.count_nonzero(cv2.bitwise_and(brown_mask, mask))) / foreground_pixels
    freshness_score = max(0.0, green_ratio - 2.0 * brown_ratio)

    # Step 4: Sharpness
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Step 5: Optional DNN — flatten output to handle variable shape (1,3) or (1,1,3)
    if _MODEL_PATH.exists():
        try:
            net = cv2.dnn.readNetFromONNX(str(_MODEL_PATH))
            blob = cv2.dnn.blobFromImage(
                img_norm, scalefactor=1.0 / 255.0, size=(224, 224),
                swapRB=True, crop=False,
            )
            net.setInput(blob)
            outputs = net.forward()
            probs = outputs[0].flatten()  # safe regardless of (1,3) or (1,1,3) shape
            grade_idx = int(np.argmax(probs))
            grade = ["A", "B", "C"][min(grade_idx, 2)]
            return grade, round(float(probs[grade_idx]), 3)
        except Exception:
            pass

    # Classical grade decision
    if freshness_score > 0.30 and sharpness > 100:
        return "A", round(min(1.0, (freshness_score + sharpness / 500) / 2), 3)
    elif freshness_score > 0.10 or sharpness > 50:
        return "B", round(min(0.75, freshness_score + sharpness / 1000), 3)
    else:
        return "C", round(max(0.0, 1.0 - freshness_score), 3)


def grade_crop_image_bytes(image_bytes: bytes) -> tuple[str, float]:
    """
    Grade a crop image from raw bytes.
    Returns (grade: "A"|"B"|"C", confidence_score: float 0–1).

    Tries Google Cloud Vision API first; falls back to OpenCV if the key
    is absent or the API call fails.
    """
    result = _grade_with_vision_api(image_bytes)
    if result is not None:
        return result
    return _grade_with_opencv(image_bytes)
