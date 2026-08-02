"""
FastAPI backend for PerlerBeadsDesigner v2 (web frontend + Python backend).

Wraps the existing tkinter-free core modules as a local HTTP API. Images travel
as PNG bytes; parameters and state travel as JSON. The frontend static files
under ``static/`` are served at the root.
"""
import os

import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .state import STATE, _resource_path
from .codecs import ndarray_to_png, png_to_ndarray
from src.core.pattern_generator import PatternConfig
from src.utils import segmentation as segmod


def _err(fn, *a, **k):
    """Run fn(*a, **k) converting ValueError into a 400 HTTPException."""
    try:
        return fn(*a, **k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _png(arr) -> Response:
    # no-store：图像内容随操作不断变化，禁止 WebView2/浏览器启发式缓存。
    # 否则不带 cache-buster 的引用（如鹰眼缩略图 miniImg.src 用原始 URL）
    # 会一直显示第一次缓存的旧图，看起来像「鹰眼/图像不更新」。
    return Response(content=ndarray_to_png(arr), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


def _mask_bg(value):
    """Map 'none'|'white'|'black' to None / (r,g,b) for render_standard_chart."""
    if value == "white":
        return (255, 255, 255)
    if value == "black":
        return (0, 0, 0)
    return None


app = FastAPI(title="PerlerBeadsDesigner v2 API")


# --------------------------------------------------------------------------
# Status / health
# --------------------------------------------------------------------------
@app.get("/api/status")
def status():
    has = STATE.has_image()
    info = STATE.processor.get_image_info() if has else {}
    return {
        "ok": True,
        "has_image": has,
        "has_mask": STATE.mask is not None,
        "has_pattern": STATE.generator.pattern is not None,
        "palette_colors": len(STATE.color_manager.palette.colors),
        "image": info,
        "metric": STATE.color_manager.get_color_metric(),
        "output_dir": STATE.output_dir,
    }


class OutputDirReq(BaseModel):
    path: str


@app.get("/api/output_dir")
def get_output_dir():
    return {"ok": True, "output_dir": STATE.output_dir}


@app.post("/api/output_dir")
def set_output_dir(req: OutputDirReq):
    p = os.path.abspath(req.path.strip())
    if not p:
        raise HTTPException(400, detail="输出路径不能为空")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError as e:
        raise HTTPException(400, detail=f"无法创建/访问输出目录: {e}")
    STATE.output_dir = p
    return {"ok": True, "output_dir": p}


@app.get("/api/help")
def help_doc():
    from fastapi.responses import PlainTextResponse
    from .state import _resource_path
    path = _resource_path('HELP.md')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return PlainTextResponse(f.read())
    except OSError:
        return PlainTextResponse('# 帮助文档缺失\n\n未找到 HELP.md。')


# --------------------------------------------------------------------------
# Image loading + basic processing
# --------------------------------------------------------------------------
@app.post("/api/image/load")
async def load_image(file: UploadFile = File(...)):
    data = await file.read()
    arr = _err(png_to_ndarray, data)
    STATE.processor.original_image = arr.copy()
    STATE.processor.current_image = arr.copy()
    STATE.processor.image_path = file.filename
    STATE.set_mask(None)
    STATE.generator.pattern = None
    STATE.bead_mask = None
    return _png(STATE.processor.current_image)


@app.get("/api/image/current")
def current_image():
    return _png(_err(STATE.require_image))


class LoadPathReq(BaseModel):
    path: str


@app.post("/api/image/load_path")
def load_image_path(req: LoadPathReq):
    """Load an image from a filesystem path (native pywebview file dialog)."""
    p = req.path.strip()
    if not p or not os.path.isfile(p):
        raise HTTPException(400, detail=f"文件不存在: {p or '(空)'}")
    with open(p, 'rb') as f:
        data = f.read()
    arr = _err(png_to_ndarray, data)
    STATE.processor.original_image = arr.copy()
    STATE.processor.current_image = arr.copy()
    STATE.processor.image_path = p
    STATE.set_mask(None)
    STATE.generator.pattern = None
    STATE.bead_mask = None
    return _png(STATE.processor.current_image)


@app.get("/api/image/original")
def original_image():
    return _png(_err(STATE.processor.get_original_image))


@app.post("/api/image/reset")
def reset_image():
    STATE.set_mask(None)
    STATE.bead_mask = None               # 派生遮罩一并失效，避免旧遮罩残留渲染
    STATE.generator.bead_mask = None
    return _png(_err(STATE.processor.reset_to_original))


class BasicOp(BaseModel):
    brightness: float | None = None
    contrast: float | None = None
    blur: int | None = None          # gaussian kernel (px)
    rotate: int | None = None        # 90 / -90 / 180
    flip: str | None = None          # 'h' / 'v'
    grayscale: bool = False
    crop: list[int] | None = None    # [x1,y1,x2,y2]
    reset_first: bool = False        # apply from original


@app.post("/api/image/basic")
def image_basic(op: BasicOp):
    with STATE.lock:
        if op.reset_first:
            _err(STATE.processor.reset_to_original)
        if op.crop is not None and len(op.crop) == 4:
            _err(STATE.processor.crop_region, *op.crop)
        if op.brightness is not None:
            _err(STATE.processor.adjust_brightness, float(op.brightness))
        if op.contrast is not None:
            _err(STATE.processor.adjust_contrast, float(op.contrast))
        if op.blur is not None:
            _err(STATE.processor.apply_gaussian_blur, int(op.blur))
        if op.grayscale:
            _err(STATE.processor.convert_to_grayscale)
        if op.rotate == 90:
            _err(STATE.processor.rotate_90, True)
        elif op.rotate == -90:
            _err(STATE.processor.rotate_90, False)
        elif op.rotate == 180:
            _err(STATE.processor.rotate_180)
        if op.flip == "h":
            _err(STATE.processor.flip_horizontal)
        elif op.flip == "v":
            _err(STATE.processor.flip_vertical)
        STATE.set_mask(None)
        STATE.bead_mask = None           # 派生遮罩一并失效，避免旧遮罩残留渲染
        STATE.generator.bead_mask = None
        return _png(STATE.require_image())


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------
class RectReq(BaseModel):
    x: int
    y: int
    w: int
    h: int


@app.post("/api/segment/grabcut/init/rect")
def grabcut_init_rect(req: RectReq):
    s = STATE.new_grabcut_session()
    mask = _err(s.segment_rect, (req.x, req.y, req.w, req.h))
    STATE.set_mask(mask)
    return _png(mask)


@app.post("/api/segment/grabcut/init/mask")
async def grabcut_init_mask(file: UploadFile = File(...)):
    init = _err(png_to_ndarray, await file.read(), True)
    s = STATE.new_grabcut_session()
    mask = _err(s.segment_mask, init)
    STATE.set_mask(mask)
    return _png(mask)


@app.post("/api/segment/grabcut/refine")
async def grabcut_refine(fgd: UploadFile | None = File(None),
                         bgd: UploadFile | None = File(None)):
    s = STATE.get_grabcut_session()
    fgd_ann = _err(png_to_ndarray, await fgd.read(), True) if fgd is not None else None
    bgd_ann = _err(png_to_ndarray, await bgd.read(), True) if bgd is not None else None
    mask = _err(s.refine, fgd_ann, bgd_ann)
    STATE.set_mask(mask)
    return _png(mask)


class AutoSegReq(BaseModel):
    method: str                      # grabcut_rect | watershed | otsu | slic
    rect: list[int] | None = None    # grabcut_rect [x1,y1,x2,y2]
    fg_ratio: float = 0.4            # watershed
    n_segments: int = 150            # slic


@app.post("/api/segment/auto")
def segment_auto(req: AutoSegReq):
    img = _err(STATE.require_image)
    s = segmod.ImageSegmentation()
    if req.method == "grabcut_rect":
        r = req.rect or [10, 10, img.shape[1] - 20, img.shape[0] - 20]
        mask = _err(s.grabcut_rect, img, r[0], r[1], r[2], r[3])
    elif req.method == "watershed":
        mask = _err(s.watershed_auto, img, float(req.fg_ratio))
    elif req.method == "otsu":
        mask = _err(s.otsu_segment, img)
    elif req.method == "slic":
        mask = _err(s.slic_segment, img, int(req.n_segments))
    else:
        raise HTTPException(400, detail=f"未知分割方法: {req.method}")
    STATE.set_mask(mask)
    return _png(mask)


class MorphReq(BaseModel):
    op: str                          # open | close | erode | dilate
    kernel: int = 5
    shape: str = "ellipse"


@app.post("/api/segment/morph")
def segment_morph(req: MorphReq):
    if STATE.mask is None:
        raise HTTPException(400, detail="尚无分割 mask")
    s = segmod.ImageSegmentation()
    fn = {"open": s.morph_open, "close": s.morph_close,
          "erode": s.morph_erode, "dilate": s.morph_dilate}.get(req.op)
    if fn is None:
        raise HTTPException(400, detail=f"未知形态学操作: {req.op}")
    # normalize to clean 0/255 before morph so odd/even kernels behave predictably
    base = np.where(STATE.mask > 127, 255, 0).astype(np.uint8)
    mask = _err(fn, base, int(req.kernel), req.shape)
    mask = np.where(mask > 127, 255, 0).astype(np.uint8)
    STATE.push_mask_history()          # 快照旧 mask 供撤销
    STATE.set_mask(mask)
    STATE.bead_mask = None             # 派生 bead_mask 失效
    STATE.generator.pattern = None
    return _png(mask)


@app.post("/api/segment/morph/undo")
def segment_morph_undo():
    if not STATE.undo_mask():
        raise HTTPException(400, detail="无可撤销的形态学步骤")
    STATE.bead_mask = None
    STATE.generator.pattern = None
    return _png(np.where(STATE.mask > 127, 255, 0).astype(np.uint8))


@app.post("/api/segment/morph/redo")
def segment_morph_redo():
    if not STATE.redo_mask():
        raise HTTPException(400, detail="无可重做的形态学步骤")
    STATE.bead_mask = None
    STATE.generator.pattern = None
    return _png(np.where(STATE.mask > 127, 255, 0).astype(np.uint8))


@app.get("/api/segment/mask")
def get_mask():
    if STATE.mask is None:
        raise HTTPException(404, detail="尚无分割 mask")
    mask = STATE.mask
    img = STATE.processor.current_image
    if img is not None and mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    # normalize to a clean single-channel 0/255 image for standalone display
    mask = np.where(mask > 127, 255, 0).astype(np.uint8)
    return _png(mask)


@app.get("/api/segment/overlay")
def get_overlay():
    """Original image with the foreground mask highlighted (orange), blended."""
    img = _err(STATE.require_image)
    if STATE.mask is None:
        raise HTTPException(404, detail="尚无分割 mask")
    mask = STATE.mask
    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    fg = mask > 127
    # 高亮 = 前景保留原色、背景 ×0.3 压暗（对齐手机端 compositeMask 的 highlight 分支）
    blended = img.astype(np.float32) * 0.3
    blended[fg] = img[fg].astype(np.float32)
    return _png(np.clip(blended, 0, 255).astype(np.uint8))


@app.get("/api/segment/applied")
def get_applied():
    """Foreground kept in colour, background pure black (the 'applied' preview)."""
    img = _err(STATE.require_image)
    if STATE.mask is None:
        raise HTTPException(404, detail="尚无分割 mask")
    mask = STATE.mask
    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    fg = mask > 127
    # 应用结果 = 前景保留原色、背景转灰再提亮 gray*0.4 + 255*0.6
    # （对齐手机端 compositeMask 的 applied 分支：灰度压暗背景）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg = gray * 0.4 + 255.0 * 0.6
    out = np.repeat(bg[..., None], 3, axis=2)      # 背景灰度扩展到 3 通道
    out[fg] = img[fg].astype(np.float32)           # 前景保留原色
    return _png(np.clip(out, 0, 255).astype(np.uint8))


@app.post("/api/segment/apply")
def segment_apply():
    """Confirm the mask as a working layer WITHOUT baking it into the image.

    Keeps the original image and the mask as separate layers so the user can
    still review 原图/Mask/高亮, and so pattern generation can exclude the
    masked background from the BOM. Only invalidates the derived bead_mask and
    any previously generated pattern (forcing a rebuild on next generate).
    """
    with STATE.lock:
        _err(STATE.require_image)
        if STATE.mask is None:
            raise HTTPException(400, detail="尚无分割 mask")
        STATE.bead_mask = None
        STATE.generator.pattern = None
        return _png(STATE.require_image())


# --------------------------------------------------------------------------
# Pattern generation
# --------------------------------------------------------------------------
class PatternReq(BaseModel):
    width_beads: int
    height_beads: int
    max_colors: int | None = None
    salience_strength: float = 1.0
    dither: bool = False
    dither_strength: float = 1.0
    icm_smooth: float = 0.0
    use_mask: bool = True


@app.post("/api/pattern/generate")
def pattern_generate(req: PatternReq):
    with STATE.lock:
        img = _err(STATE.require_image)
        cfg = PatternConfig(
            width_beads=int(req.width_beads),
            height_beads=int(req.height_beads),
            max_colors=int(req.max_colors) if req.max_colors else None,
            salience_strength=float(req.salience_strength),
            dither=bool(req.dither),
            dither_strength=float(req.dither_strength),
            icm_smooth=float(req.icm_smooth),
        )
        # 同步图纸宽，供后续分割下采样目标（4×图纸宽）使用
        STATE.grid_width = int(req.width_beads)
        gen = STATE.generator
        pattern, bom = _err(gen.generate_pattern, img,
                            STATE.color_manager.palette, cfg,
                            STATE.color_manager)
        # Build bead_mask from the working mask when requested. Unconditionally
        # clear first so a stale mask never lingers when the user regenerates
        # with use_mask off or after the mask was cleared (else chart/export
        # would keep fading/excluding the old background → "换不回原图计算").
        STATE.bead_mask = None
        gen.bead_mask = None
        bead_mask = None
        if req.use_mask and STATE.mask is not None:
            bm = (STATE.mask > 127)
            bead_mask = cv2.resize(bm.astype(np.uint8),
                                   (cfg.width_beads, cfg.height_beads),
                                   interpolation=cv2.INTER_NEAREST).astype(bool)
            gen.bead_mask = bead_mask
            STATE.bead_mask = bead_mask
            gen.rebuild_bom_with_mask(bead_mask, STATE.color_manager.palette)
            bom = gen.bom
        return {"ok": True, "bom": bom,
                "width": cfg.width_beads, "height": cfg.height_beads,
                "has_mask": bead_mask is not None}


class ChartReq(BaseModel):
    bead_pixel_size: int = 30
    major_every: int = 5
    fade_masked: bool = True
    mask_bg: str = "none"            # none | white | black


@app.post("/api/pattern/chart")
def pattern_chart(req: ChartReq):
    gen = STATE.generator
    if gen.pattern is None:
        raise HTTPException(400, detail="尚未生成图案")
    # 渲染遮罩跟随当次 pattern 的生命周期（gen.bead_mask，generate 时对称清写），
    # 不读游离的 STATE.bead_mask，避免取消勾选后旧遮罩仍残留渲染。
    chart = _err(gen.render_standard_chart,
                 int(req.bead_pixel_size), int(req.major_every),
                 STATE.color_manager.palette, gen.bead_mask, bool(req.fade_masked),
                 mask_bg=_mask_bg(req.mask_bg))
    return _png(chart)


class MetricReq(BaseModel):
    metric: str                      # weighted|euclidean|lab|ciede76|ciede2000


@app.post("/api/pattern/metric")
def pattern_metric(req: MetricReq):
    valid = {'weighted', 'euclidean', 'lab', 'ciede76', 'ciede2000'}
    if req.metric not in valid:
        raise HTTPException(400, detail=f"未知颜色度量: {req.metric}")
    STATE.color_manager.set_color_metric(req.metric)
    return {"ok": True, "metric": req.metric}


@app.get("/api/pattern/bom")
def pattern_bom():
    if STATE.generator.bom is None:
        raise HTTPException(400, detail="尚未生成图案")
    return {"ok": True, "bom": STATE.generator.bom}


@app.get("/api/pattern/preview")
def pattern_preview(bead_pixel_size: int = 10):
    gen = STATE.generator
    if gen.pattern is None:
        raise HTTPException(400, detail="尚未生成图案")
    img = _err(gen.render_pattern_image, int(bead_pixel_size))
    return _png(img)


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
class ExportReq(BaseModel):
    filename: str = "pattern"
    output_dir: str | None = None
    png_scale: float = 1.0
    paper: str = "A4"                # A4 | Letter
    export_png: bool = True
    export_pdf: bool = True
    mask_bg: str = "none"            # none | white | black


@app.post("/api/export")
def export(req: ExportReq):
    gen = STATE.generator
    if gen.pattern is None:
        raise HTTPException(400, detail="尚未生成图案")
    from src.utils.export import PatternExporter
    outdir = req.output_dir or STATE.output_dir
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    STATE.output_dir = outdir
    exporter = PatternExporter(outdir)
    chart = _err(gen.render_standard_chart, 30, 5, STATE.color_manager.palette,
                 gen.bead_mask, True, mask_bg=_mask_bg(req.mask_bg))
    base = os.path.join(outdir, req.filename)
    made = []
    if req.export_png:
        made.append(exporter.export_png_standard(chart, req.filename,
                                                 float(req.png_scale)))
    if req.export_pdf:
        try:
            made.append(exporter.export_pdf(chart, gen.bom, req.filename,
                                            req.paper))
        except Exception as e:
            raise HTTPException(400, detail=f"PDF 导出失败: {e}")
    return {"ok": True, "files": made, "output_dir": outdir}


# --------------------------------------------------------------------------
# Static frontend (served last so /api wins)
# --------------------------------------------------------------------------
# frozen (PyInstaller) 下 __file__ 解析不可靠，统一走 state._resource_path
# （含 sys._MEIPASS 兜底），否则 app.mount 被跳过、根路径无路由 → exe 拒绝连接。
_STATIC = _resource_path('src', 'webapp', 'static')
if os.path.isdir(_STATIC):
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
