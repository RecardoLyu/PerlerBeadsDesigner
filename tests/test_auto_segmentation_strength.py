"""Automatic-segmentation foreground-strength contract tests."""
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.webapp.app import _strength_complement, app
from src.webapp.state import STATE


@pytest.mark.parametrize(("strength", "threshold"), [
    (0.0, 1.0),
    (0.25, 0.75),
    (0.6, 0.4),
    (1.0, 0.0),
])
def test_strength_is_inverse_of_internal_threshold(strength, threshold):
    assert _strength_complement(strength) == pytest.approx(threshold)


def test_watershed_strength_increases_foreground_and_validates_range():
    client = TestClient(app)
    old_image = STATE.processor.current_image
    old_mask = STATE.mask
    try:
        image = np.full((96, 128, 3), 235, dtype=np.uint8)
        image[16:80, 24:104] = (180, 40, 30)
        STATE.processor.current_image = image

        def run(strength):
            response = client.post('/api/segment/auto', json={
                'method': 'watershed', 'foreground_strength': strength,
            })
            assert response.status_code == 200
            return int(np.count_nonzero(STATE.mask))

        areas = [run(value) for value in (0.0, 0.25, 0.6, 0.9, 1.0)]
        assert areas == sorted(areas)
        assert areas[-1] > areas[0]

        invalid = client.post('/api/segment/auto', json={
            'method': 'watershed', 'foreground_strength': 1.01,
        })
        assert invalid.status_code == 400
        assert '前景强度' in invalid.json()['detail']
    finally:
        STATE.processor.current_image = old_image
        STATE.mask = old_mask


def test_default_model_parameters_are_synchronized_immediately():
    source = (Path(__file__).parents[1] / 'src' / 'webapp' / 'static' /
              'js' / 'segment.js').read_text(encoding='utf-8')
    assert '<option value="u2netp" selected' in source
    assert 'id="neuralStrength" min="0" max="1" step="0.01"' in source
    assert 'id="watershedStrength" min="0" max="1" step="0.01"' in source
    assert source.count('前景强度') >= 2
    assert '前景阈值' not in source
    assert '前景比例' not in source
    initial_sync = source.index('  syncAutoSegParams();')
    async_refresh = source.index('  async function refreshNeuralStatus()')
    assert initial_sync < async_refresh
