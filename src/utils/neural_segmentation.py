"""Lightweight U²-Netp salient-object segmentation through ONNX Runtime.

The runtime is imported lazily so classical segmentation remains usable when an
optional GPU runtime is misconfigured. PyTorch is only needed to re-export the
model, never to run or package the desktop app.
"""
from functools import lru_cache
import os
import sys
from typing import Dict, List

import cv2
import numpy as np


INPUT_SIZE = 320
PROVIDERS = {
    'cpu': 'CPUExecutionProvider',
    'directml': 'DmlExecutionProvider',
    'cuda': 'CUDAExecutionProvider',
}
PROVIDER_LABELS = {
    'CPUExecutionProvider': 'CPU',
    'DmlExecutionProvider': 'DirectML（GPU）',
    'CUDAExecutionProvider': 'CUDA（NVIDIA GPU）',
}


def default_model_path() -> str:
    """Resolve the bundled model in source and PyInstaller environments."""
    override = os.environ.get('PBD_U2NETP_MODEL', '').strip()
    if override:
        return os.path.abspath(override)
    root = getattr(sys, '_MEIPASS', None)
    if root is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    return os.path.join(root, 'src', 'assets', 'models', 'u2netp.onnx')


def _runtime():
    try:
        import onnxruntime as ort
        return ort
    except ImportError as exc:
        raise ValueError('未安装 ONNX Runtime，无法使用 U²-Netp 神经分割') from exc


def available_providers() -> List[str]:
    """Return recognized execution providers without creating a session."""
    try:
        available = _runtime().get_available_providers()
    except ValueError:
        return []
    return [name for name in PROVIDERS.values() if name in available]


def neural_status(model_path: str | None = None) -> Dict:
    """Serializable capability information for the desktop UI."""
    path = model_path or default_model_path()
    providers = available_providers()
    return {
        'model': 'u2netp',
        'model_available': os.path.isfile(path),
        'runtime_available': bool(providers),
        'providers': providers,
        'provider_labels': PROVIDER_LABELS,
        'input_size': INPUT_SIZE,
    }


def select_provider(requested: str, available: List[str]) -> str:
    """Resolve auto/cpu/directml/cuda to an installed execution provider."""
    requested = (requested or 'auto').lower()
    if requested == 'dml':
        requested = 'directml'
    if not available:
        raise ValueError('ONNX Runtime 没有可用的 CPU／GPU 计算后端')
    if requested == 'auto':
        for name in ('DmlExecutionProvider', 'CUDAExecutionProvider',
                     'CPUExecutionProvider'):
            if name in available:
                return name
    elif requested in PROVIDERS:
        name = PROVIDERS[requested]
        if name in available:
            return name
        raise ValueError(f'当前运行时不支持 {PROVIDER_LABELS[name]}，请更换后端或安装对应 ONNX Runtime')
    else:
        raise ValueError(f'未知分割计算后端: {requested}')
    raise ValueError('未找到可用的 ONNX Runtime 计算后端')


@lru_cache(maxsize=6)
def _load_session(model_path: str, requested: str):
    """Cache sessions by model/backend; ONNX sessions are safe for concurrent runs."""
    if not os.path.isfile(model_path):
        raise ValueError('U²-Netp 模型文件缺失，请检查 src/assets/models/u2netp.onnx')
    ort = _runtime()
    available = available_providers()
    selected = select_provider(requested, available)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = [selected]
    if selected != 'CPUExecutionProvider':
        providers.append('CPUExecutionProvider')
    try:
        session = ort.InferenceSession(model_path, sess_options=options,
                                       providers=providers)
    except Exception as exc:
        if requested == 'auto' and selected != 'CPUExecutionProvider':
            selected = 'CPUExecutionProvider'
            session = ort.InferenceSession(
                model_path, sess_options=options,
                providers=['CPUExecutionProvider'])
        else:
            raise ValueError(f'U²-Netp {PROVIDER_LABELS[selected]} 初始化失败: {exc}') from exc
    return session, selected


def clear_session_cache() -> None:
    """Release cached sessions (used by tests and future model switching)."""
    _load_session.cache_clear()


class U2NetPSegmenter:
    """Run the fixed 320×320 U²-Netp model and return a binary 0/255 mask."""

    def __init__(self, model_path: str | None = None, provider: str = 'auto'):
        self.model_path = os.path.abspath(model_path or default_model_path())
        self.provider = provider
        self.actual_provider = None

    @staticmethod
    def preprocess(image: np.ndarray) -> np.ndarray:
        if image is None or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError('请提供有效的 RGB 图像')
        resized = cv2.resize(image, (INPUT_SIZE, INPUT_SIZE),
                             interpolation=cv2.INTER_AREA)
        tensor = resized.astype(np.float32) / 255.0
        tensor -= np.array([0.485, 0.456, 0.406], dtype=np.float32)
        tensor /= np.array([0.229, 0.224, 0.225], dtype=np.float32)
        return np.ascontiguousarray(tensor.transpose(2, 0, 1)[None])

    @staticmethod
    def normalize_prediction(prediction: np.ndarray) -> np.ndarray:
        """Match official min-max normalization without producing NaN."""
        prediction = np.squeeze(prediction).astype(np.float32)
        if prediction.ndim != 2:
            raise ValueError(f'U²-Netp 输出形状异常: {prediction.shape}')
        low, high = float(prediction.min()), float(prediction.max())
        if high - low < 1e-8:
            return np.zeros_like(prediction, dtype=np.float32)
        return (prediction - low) / (high - low)

    def segment(self, image: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        threshold = float(threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError('神经分割阈值必须在 0 到 1 之间')
        session, selected = _load_session(self.model_path, self.provider)
        tensor = self.preprocess(image)
        try:
            output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
        except Exception as exc:
            raise ValueError(f'U²-Netp 推理失败: {exc}') from exc
        self.actual_provider = selected
        probability = self.normalize_prediction(output)
        h, w = image.shape[:2]
        probability = cv2.resize(probability, (w, h),
                                 interpolation=cv2.INTER_LINEAR)
        return np.where(probability >= threshold, 255, 0).astype(np.uint8)
