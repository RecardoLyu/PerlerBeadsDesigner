"""U²-Netp preprocessing, provider selection and real CPU inference tests."""
import numpy as np
import pytest

from src.utils.neural_segmentation import (
    U2NetPSegmenter,
    available_providers,
    default_model_path,
    neural_status,
    select_provider,
)


def test_provider_auto_prefers_gpu_then_cpu():
    assert select_provider('auto', ['CPUExecutionProvider',
                                    'CUDAExecutionProvider',
                                    'DmlExecutionProvider']) == 'DmlExecutionProvider'
    assert select_provider('auto', ['CPUExecutionProvider',
                                    'CUDAExecutionProvider']) == 'CUDAExecutionProvider'
    assert select_provider('auto', ['CPUExecutionProvider']) == 'CPUExecutionProvider'


def test_explicit_provider_and_unknown_backend():
    assert select_provider('cpu', ['CPUExecutionProvider']) == 'CPUExecutionProvider'
    with pytest.raises(ValueError, match='不支持'):
        select_provider('directml', ['CPUExecutionProvider'])
    with pytest.raises(ValueError, match='未知'):
        select_provider('tpu', ['CPUExecutionProvider'])


def test_preprocess_and_constant_prediction():
    image = np.full((40, 60, 3), 127, dtype=np.uint8)
    tensor = U2NetPSegmenter.preprocess(image)
    assert tensor.shape == (1, 3, 320, 320)
    assert tensor.dtype == np.float32
    normalized = U2NetPSegmenter.normalize_prediction(np.full((1, 1, 4, 4), 0.7))
    assert normalized.shape == (4, 4)
    assert np.isfinite(normalized).all()
    assert not normalized.any()


def test_model_and_cpu_inference():
    status = neural_status()
    assert status['model_available']
    assert 'CPUExecutionProvider' in available_providers()
    image = np.full((96, 128, 3), 235, dtype=np.uint8)
    image[20:80, 32:96] = (180, 40, 30)
    segmenter = U2NetPSegmenter(default_model_path(), provider='cpu')
    mask = segmenter.segment(image, threshold=0.5)
    assert mask.shape == image.shape[:2]
    assert mask.dtype == np.uint8
    assert set(np.unique(mask)).issubset({0, 255})
    assert segmenter.actual_provider == 'CPUExecutionProvider'


def test_neural_segmentation_api():
    from fastapi.testclient import TestClient
    from src.webapp.app import app
    from src.webapp.state import STATE

    client = TestClient(app)
    old_image = STATE.processor.current_image
    old_mask = STATE.mask
    try:
        STATE.processor.current_image = np.full((48, 64, 3), 220,
                                                dtype=np.uint8)
        status = client.get('/api/segment/neural/status')
        assert status.status_code == 200
        assert status.json()['model_available'] is True
        response = client.post('/api/segment/auto', json={
            'method': 'u2netp', 'provider': 'cpu', 'threshold': 0.5,
        })
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        assert STATE.mask.shape == (48, 64)
        invalid = client.post('/api/segment/auto', json={
            'method': 'u2netp', 'provider': 'cpu', 'threshold': 2.0,
        })
        assert invalid.status_code == 400
    finally:
        STATE.processor.current_image = old_image
        STATE.mask = old_mask
