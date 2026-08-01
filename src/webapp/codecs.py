"""
ndarray <-> PNG bytes codecs shared by the webapp API.
"""
import io
import cv2
import numpy as np


def ndarray_to_png(arr: np.ndarray) -> bytes:
    """Encode an RGB or grayscale ndarray to PNG bytes."""
    if arr is None:
        raise ValueError("空图像")
    if len(arr.shape) == 2:
        img = arr
    else:
        img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("PNG 编码失败")
    return buf.tobytes()


def png_to_ndarray(data: bytes, to_gray: bool = False) -> np.ndarray:
    """Decode PNG bytes to an ndarray.

    Color images are returned as RGB. With to_gray=True returns a single-channel
    array (used for binary masks / scribble annotations)."""
    arr = np.frombuffer(data, dtype=np.uint8)
    flag = cv2.IMREAD_GRAYSCALE if to_gray else cv2.IMREAD_COLOR
    img = cv2.imdecode(arr, flag)
    if img is None:
        raise ValueError("无法解码图像数据")
    if not to_gray:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img
