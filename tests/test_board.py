"""图纸画板 board 路由测试：新建/笔画/填充/撤销重做/清空/底图/导出。"""
import io
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.webapp.app import app
from src.webapp.state import STATE


@pytest.fixture(autouse=True)
def fresh_board():
    STATE.board_active = False
    STATE.board_grid = None
    STATE.board_base = None
    STATE.board_base_src = None
    STATE.board_undo, STATE.board_redo = [], []
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_new_board(client):
    r = client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    assert r.status_code == 200
    assert STATE.board_grid.shape == (52, 52)
    # 非法尺寸
    assert client.post("/api/board/new", json={"size": 60}).status_code == 400


def test_state_inactive(client):
    r = client.get("/api/board/state")
    assert r.json()["active"] is False


def test_stroke_and_state(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    r = client.post("/api/board/stroke",
                    json={"cells": [[0, 0], [1, 0], [2, 2]], "code": "H1"})
    assert r.status_code == 200 and r.json()["changed"] == 3
    st = client.get("/api/board/state").json()
    assert st["active"] and st["size"] == 52
    assert st["grid"][0][0] == "H1" and st["grid"][0][1] == "H1"
    assert st["grid"][2][2] == "H1" and st["grid"][1][1] is None
    assert st["can_undo"] is True
    # BOM 只统计有豆格
    assert st["bom"]["total_beads"] == 3
    assert st["bom"]["colors"]["H1"]["count"] == 3
    # 色板下发
    assert len(st["palette"]) > 100


def test_stroke_erase_and_unknown_code(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    client.post("/api/board/stroke", json={"cells": [[0, 0]], "code": "H1"})
    r = client.post("/api/board/stroke", json={"cells": [[0, 0]], "code": None})
    assert r.json()["changed"] == 1
    assert STATE.board_grid[0, 0] is None
    # 未知色号
    assert client.post("/api/board/stroke",
                       json={"cells": [[0, 0]], "code": "ZZZ"}).status_code == 400


def test_fill_flood(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    # 全空板从 (5,5) 填充 → 整板填满（2704 格）
    r = client.post("/api/board/fill", json={"x": 5, "y": 5, "code": "F5"})
    assert r.json()["changed"] == 52 * 52
    assert STATE.board_grid[0, 0] == "F5" and STATE.board_grid[51, 51] == "F5"
    # 已同色再填 → 0 改动
    r2 = client.post("/api/board/fill", json={"x": 5, "y": 5, "code": "F5"})
    assert r2.json()["changed"] == 0


def test_undo_redo(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    client.post("/api/board/stroke", json={"cells": [[0, 0]], "code": "H1"})
    client.post("/api/board/stroke", json={"cells": [[1, 0]], "code": "F5"})
    # 撤销一步
    r = client.post("/api/board/undo")
    st = r.json()
    assert st["grid"][0][0] == "H1" and st["grid"][0][1] is None
    assert st["can_redo"] is True
    # 重做
    r2 = client.post("/api/board/redo")
    assert r2.json()["grid"][0][1] == "F5"


def test_undo_cap_5(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    for i in range(8):  # 8 笔，撤销栈 cap 5
        client.post("/api/board/stroke", json={"cells": [[i, 0]], "code": "H1"})
    n = 0
    while client.post("/api/board/undo").status_code == 200:
        n += 1
    assert n == 5  # 只能撤销 5 步


def test_clear(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    client.post("/api/board/stroke", json={"cells": [[0, 0], [1, 1]], "code": "H1"})
    r = client.post("/api/board/clear")
    st = r.json()
    assert st["bom"]["total_beads"] == 0
    # 清空可撤销
    client.post("/api/board/undo")
    assert STATE.board_grid[0, 0] == "H1"


def _png_bytes(arr):
    from src.webapp.codecs import ndarray_to_png
    return ndarray_to_png(arr)


def test_base_load_crop_options(client):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    img[:, :, 0] = 255
    r = client.post("/api/board/base/load",
                    files={"file": ("b.png", _png_bytes(img), "image/png")})
    assert r.status_code == 200
    # 裁正方形（给矩形，强制取 min 边）
    r2 = client.post("/api/board/base/crop", json={"crop": [10, 10, 90, 60]})
    assert r2.json()["side"] == 50
    assert STATE.board_base.shape == (50, 50, 3)
    # 底图可见性/透明度
    r3 = client.post("/api/board/base/options", json={"visible": False, "opacity": 0.6})
    assert r3.json()["visible"] is False and abs(r3.json()["opacity"] - 0.6) < 1e-6
    # 底图图片路由
    assert client.get("/api/board/base/image").status_code == 200
    # 清除
    client.post("/api/board/base/clear")
    assert STATE.board_base is None
    assert client.get("/api/board/base/image").status_code == 404


def test_export(client, tmp_path):
    client.post("/api/board/new", json={"size": 52, "brand": "mard"})
    client.post("/api/board/stroke", json={"cells": [[0, 0], [5, 5], [10, 10]],
                                           "code": "H1"})
    r = client.post("/api/board/export", json={
        "filename": "testboard", "output_dir": str(tmp_path),
        "bead_style": "real", "png_scale": 1.0})
    assert r.status_code == 200
    data = r.json()
    assert data["bom"]["total_beads"] == 3
    assert len(data["files"]) == 1 and data["files"][0].endswith(".png")
    import os
    assert os.path.exists(data["files"][0])
