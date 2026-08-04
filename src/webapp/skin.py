"""
图片换肤：自定义背景图存取 + 主体颜色提取。

皮肤图存安装目录 ``custom_skin.jpg``（与 settings.json 同级）；
提取算法与移动端 lib/theme/skin.dart 保持同一套规则：
降采样 64 → k=4 kmeans（k-means++ 播种）→ 剔除近白/近黑/灰簇 →
score = 簇像素数 × 饱和度降序，取前 MAX_COLORS 个；无存活簇返回 []（只换背景不换色）。
"""
import os
from typing import Optional

import numpy as np
import cv2

from .state import AppState

SKIN_FILENAME = "custom_skin.jpg"
MAX_SIDE = 1920          # 存储前最长边
SAMPLE = 64              # 取色降采样最长边
K = 4                    # kmeans 簇数（主色+辅色+背景 各留余地）
MAX_COLORS = 3           # 最多返回的颜色数（主色 + 辅助色）
L_WHITE, L_BLACK, S_GRAY = 0.95, 0.08, 0.18   # 近白/近黑/灰 剔除阈值


def skin_path() -> str:
    return os.path.join(AppState._install_dir(), SKIN_FILENAME)


def _rgb_to_hsl(r: float, g: float, b: float):
    """0-255 RGB → (h 0-360, s 0-1, l 0-1)。"""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6.0 if g < b else 0.0)
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    return h * 60.0, s, l


def extract_dominant(bgr: np.ndarray) -> list:
    """提取主体颜色列表（score 降序，≤MAX_COLORS 个 '#RRGGBB'）；无彩色返回 []。

    用 KMEANS_PP_CENTERS 自动播种（k-means++），对手动分桶播种在真实照片
    （色桶数 > K*3）下产生越界初始标签导致 cv2.kmeans 抛错被吞成 None 的崩溃免疫。
    """
    h, w = bgr.shape[:2]
    scale = SAMPLE / float(max(h, w))
    if scale < 1.0:
        small = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))),
                           interpolation=cv2.INTER_AREA)
    else:
        small = bgr
    pixels = small.reshape(-1, 3).astype(np.float32)

    try:
        _, labels, centers = cv2.kmeans(
            pixels, K, None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5),
            5, cv2.KMEANS_PP_CENTERS)
    except cv2.error:
        return []
    labels = labels.reshape(-1)

    scored = []  # (score, (r,g,b))
    for i in range(K):
        cnt = int((labels == i).sum())
        if cnt == 0:
            continue
        cb, cg, cr = (float(v) for v in centers[i])
        _, s, l = _rgb_to_hsl(cr, cg, cb)
        if l >= L_WHITE or l <= L_BLACK or s < S_GRAY:
            continue                      # 近白/近黑/灰簇剔除
        scored.append((cnt * s, (cr, cg, cb)))
    scored.sort(key=lambda x: -x[0])

    out = []
    for _, (cr, cg, cb) in scored[:MAX_COLORS]:
        r = min(255, max(0, int(round(cr))))
        g = min(255, max(0, int(round(cg))))
        b = min(255, max(0, int(round(cb))))
        out.append('{:02X}{:02X}{:02X}'.format(r, g, b))
    return out


def save_skin(data: bytes) -> list:
    """解码→缩到 ≤1920→JPEG q85 落盘→取色。返回主体色 hex 列表（可能空表）。"""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片，请换一张试试")
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:
        s = MAX_SIDE / float(max(h, w))
        img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))),
                         interpolation=cv2.INTER_AREA)
    colors = extract_dominant(img)
    if not cv2.imwrite(skin_path(), img, [int(cv2.IMWRITE_JPEG_QUALITY), 85]):
        raise ValueError("皮肤图保存失败（目录不可写）")
    return colors


def remove_skin():
    try:
        os.remove(skin_path())
    except OSError:
        pass
