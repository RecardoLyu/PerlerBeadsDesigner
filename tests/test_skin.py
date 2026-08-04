"""图片换肤后端单元测试。

覆盖：
- extract_dominant：纯红/50%灰(→None)/白底红块(score 加权)/纯黑(→None)
- save_skin：超大图缩到 ≤1920、损坏字节抛 ValueError
- API 全链路：upload → GET 200 jpeg → remove → GET 404 → 坏数据 400
- settings 白名单含 4 个皮肤键
皮肤文件路径用 tmp_path 隔离，不污染真实安装目录。
"""
import os

import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient

from src.webapp.state import AppState
from src.webapp import skin


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _solid(color_bgr, w=100, h=100):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = color_bgr
    return img


@pytest.fixture()
def install_tmp(tmp_path, monkeypatch):
    """把安装目录（皮肤图落盘处）指到临时目录。"""
    monkeypatch.setattr(AppState, "_install_dir", staticmethod(lambda: str(tmp_path)))
    return tmp_path


# ---------------------------------------------------------------------------
# extract_dominant（返回 score 降序 hex 列表，无 '#', ≤MAX_COLORS 个）
# ---------------------------------------------------------------------------
def _hex_r(hexstr):
    return int(hexstr[0:2], 16)


def test_extract_pure_red():
    got = skin.extract_dominant(_solid((0, 0, 255)))
    assert got and _hex_r(got[0]) > 200


def test_extract_gray_returns_empty():
    assert skin.extract_dominant(_solid((128, 128, 128))) == []


def test_extract_black_returns_empty():
    assert skin.extract_dominant(_solid((0, 0, 0))) == []


def test_extract_white_returns_empty():
    assert skin.extract_dominant(_solid((255, 255, 255))) == []


def test_extract_red_block_on_white_uses_score_weighting():
    """白底(8400px) + 中心红块(1600px)：红簇像素少但饱和度高，score=count*s 应选红。"""
    img = _solid((255, 255, 255))
    img[30:70, 30:70] = (0, 0, 255)
    got = skin.extract_dominant(img)
    assert got and _hex_r(got[0]) > 200, f"期望提取到红色主体，得到 {got}"


def test_extract_realistic_photo_not_empty():
    """回归：真实多彩照片（色桶数 > K*3）下旧手动播种会越界崩溃返回 None。
    蓝天/绿草/红花三色块，KMEANS_PP_CENTERS 必须取到彩色簇。"""
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    img[:100, :] = (203, 164, 111)      # 天空蓝 BGR
    img[100:, :150] = (60, 140, 71)     # 草绿
    img[100:, 150:] = (40, 40, 200)     # 红花
    got = skin.extract_dominant(img)
    assert got, "真实多彩照片应能取到主体色（回归手动播种崩溃）"
    assert len(got) <= skin.MAX_COLORS
    # 主色应是三色之一（带明显饱和度）
    assert any(max(int(c[i:i+2], 16) for i in (0, 2, 4)) -
               min(int(c[i:i+2], 16) for i in (0, 2, 4)) > 40 for c in got)


def test_extract_returns_at_most_max_colors():
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    img[:, :40] = (203, 164, 111)
    img[:, 40:80] = (60, 140, 71)
    img[:, 80:] = (40, 40, 200)
    got = skin.extract_dominant(img)
    assert len(got) <= skin.MAX_COLORS


# ---------------------------------------------------------------------------
# save_skin
# ---------------------------------------------------------------------------
def test_save_skin_downsizes_and_returns_color(install_tmp):
    big = _solid((255, 128, 0), w=3000, h=2000)   # 蓝橙(255,128,0)=橙色系
    ok, buf = cv2.imencode('.png', big)
    assert ok
    colors = skin.save_skin(buf.tobytes())
    assert colors                          # 橙色系应取到颜色列表
    saved = cv2.imread(skin.skin_path())
    assert saved is not None
    assert max(saved.shape[:2]) <= skin.MAX_SIDE


def test_save_skin_corrupt_bytes_raises(install_tmp):
    with pytest.raises(ValueError):
        skin.save_skin(b'this is not an image')


def test_remove_skin(install_tmp):
    ok, buf = cv2.imencode('.png', _solid((0, 200, 0)))
    assert ok
    skin.save_skin(buf.tobytes())
    assert os.path.isfile(skin.skin_path())
    skin.remove_skin()
    assert not os.path.isfile(skin.skin_path())
    skin.remove_skin()   # 重复删不报错


# ---------------------------------------------------------------------------
# API 全链路
# ---------------------------------------------------------------------------
@pytest.fixture()
def client(install_tmp):
    from src.webapp.app import app
    return TestClient(app)


def test_api_skin_full_cycle(client):
    ok, buf = cv2.imencode('.jpg', _solid((0, 0, 230)))
    assert ok
    # 上传
    r = client.post('/api/skin/upload',
                    files={'file': ('skin.jpg', buf.tobytes(), 'image/jpeg')})
    assert r.status_code == 200
    body = r.json()
    assert body['ok']
    assert isinstance(body.get('colors'), list) and body['colors']
    assert body['color'] == body['colors'][0]   # 主色 = 列表首元素
    # 读取
    r = client.get('/api/skin/image')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('image/jpeg')
    assert r.headers.get('cache-control') == 'no-store'
    # 移除 → 404
    assert client.post('/api/skin/remove').status_code == 200
    assert client.get('/api/skin/image').status_code == 404


def test_api_skin_upload_bad_data(client):
    r = client.post('/api/skin/upload',
                    files={'file': ('x.jpg', b'garbage', 'image/jpeg')})
    assert r.status_code == 400


def test_settings_include_skin_keys():
    s = dict(AppState.DEFAULT_SETTINGS)
    assert s['skinImage'] == ''
    assert s['skinColor'] == ''
    assert s['skinAccent'] == ''
    assert s['skinOpacity'] == 0.15
    assert s['skinBlur'] == 1


def test_settings_skin_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(AppState, "_install_dir", staticmethod(lambda: str(tmp_path)))
    st = AppState()
    st.save_settings({'skinImage': 'custom_skin.jpg', 'skinColor': '#1E90FF',
                      'skinAccent': '#FF9D00', 'skinOpacity': 0.2, 'skinBlur': 2})
    s = st.load_settings()
    assert s['skinImage'] == 'custom_skin.jpg'
    assert s['skinColor'] == '#1E90FF'
    assert s['skinAccent'] == '#FF9D00'
    assert s['skinOpacity'] == 0.2
    assert s['skinBlur'] == 2
