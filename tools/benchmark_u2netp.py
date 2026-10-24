"""Reproducible U²-Netp end-to-end benchmark (preprocess + inference + mask)."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.neural_segmentation import (
    U2NetPSegmenter,
    clear_session_cache,
    default_model_path,
)


def load_image(path: str | None) -> np.ndarray:
    if path:
        data = np.fromfile(path, dtype=np.uint8)
        bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(f"无法读取图片: {path}")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # Fixed 1280×720 sample for comparable smoke benchmarks, not quality scoring.
    image = np.full((720, 1280, 3), 235, dtype=np.uint8)
    cv2.rectangle(image, (350, 130), (880, 650), (180, 40, 30), -1)
    cv2.ellipse(image, (615, 360), (180, 160), 0, 0, 360,
                (30, 120, 180), -1)
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="cpu",
                        choices=["auto", "cpu", "directml", "cuda"])
    parser.add_argument("--image", help="可选真实图片；缺省使用固定 1280×720 合成图")
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1 or args.warmup < 0:
        raise ValueError("runs 至少为 1，warmup 不能为负数")

    image = load_image(args.image)
    clear_session_cache()
    segmenter = U2NetPSegmenter(default_model_path(), provider=args.provider)
    started = time.perf_counter()
    mask = segmenter.segment(image)
    cold_ms = (time.perf_counter() - started) * 1000
    for _ in range(args.warmup):
        segmenter.segment(image)
    timings = []
    for _ in range(args.runs):
        started = time.perf_counter()
        mask = segmenter.segment(image)
        timings.append((time.perf_counter() - started) * 1000)
    result = {
        "provider_requested": args.provider,
        "provider_actual": segmenter.actual_provider,
        "image": str(Path(args.image)) if args.image else "synthetic",
        "image_size": [image.shape[1], image.shape[0]],
        "input_size": [320, 320],
        "cold_ms": round(cold_ms, 2),
        "warmup_runs": args.warmup,
        "measured_runs": args.runs,
        "warm_mean_ms": round(statistics.mean(timings), 2),
        "warm_median_ms": round(statistics.median(timings), 2),
        "warm_min_ms": round(min(timings), 2),
        "warm_p95_ms": round(float(np.percentile(timings, 95)), 2),
        "warm_max_ms": round(max(timings), 2),
        "foreground_pixels": int(np.count_nonzero(mask)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
