/* 迭代 GrabCut 涂鸦叠加层：前端本地 Canvas 预览（流畅），完成后把前景/背景
   涂抹作为 mask 上传后端 refine。矩形圈选也在这里。 */
class ScribbleLayer {
  constructor(canvasEl, viewer) {
    this.canvas = canvasEl;
    this.viewer = viewer;
    this.overlay = document.createElement('canvas');
    this.overlay.style.cssText = 'position:absolute;inset:0;z-index:6;pointer-events:none;';
    canvasEl.appendChild(this.overlay);
    this.octx = this.overlay.getContext('2d');
    this.enabled = false;         // 是否处于涂抹模式
    this.brush = 'fg';            // 'fg' 前景(红) / 'bg' 背景(绿)
    this.brushSize = 12;
    this.drawing = false;
    this.strokes = [];            // [{brush, pts:[[x,y]..]}] 图像坐标系
    this._bind();
  }

  _toImage(e) {
    const v = this.viewer;
    const rect = v.viewport.getBoundingClientRect();
    const px = (e.clientX - rect.left - v.tx) / v.scale;
    const py = (e.clientY - rect.top - v.ty) / v.scale;
    // clamp 到图像范围，避免框选/涂抹越界
    const iw = v.img.naturalWidth || 0, ih = v.img.naturalHeight || 0;
    return [Math.max(0, Math.min(iw, px)), Math.max(0, Math.min(ih, py))];
  }
  _toScreen(pt) {
    const v = this.viewer;
    return [pt[0] * v.scale + v.tx, pt[1] * v.scale + v.ty];
  }

  _bind() {
    const vp = this.viewer.viewport;
    vp.addEventListener('mousedown', (e) => {
      if (!this.enabled) return;
      e.stopPropagation(); e.preventDefault();
      this.drawing = true;
      const stroke = { brush: this.brush, size: this.brushSize, pts: [this._toImage(e)] };
      this.strokes.push(stroke);
      this._redraw();
    }, true);
    window.addEventListener('mousemove', (e) => {
      if (!this.drawing) { this._hover(e); return; }
      this.strokes[this.strokes.length - 1].pts.push(this._toImage(e));
      this._redraw();
    });
    window.addEventListener('mouseup', () => { this.drawing = false; });
  }

  _hover(e) {
    if (!this.enabled) return;
    this._redraw(this._toImage(e));
  }

  enable(on) {
    this.enabled = on;
    this.overlay.style.pointerEvents = 'none';
    if (!on) this._clearCanvas();
  }
  clear() { this.strokes = []; this._clearCanvas(); }
  _clearCanvas() { this.octx.clearRect(0, 0, this.overlay.width, this.overlay.height); }

  resize() {
    const vp = this.viewer.viewport.getBoundingClientRect();
    this.overlay.width = vp.width; this.overlay.height = vp.height;
    this._redraw();
  }

  _fgCol() { return document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(248,113,113,.95)' : 'rgba(220,38,38,.95)'; }
  _bgCol() { return document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(74,222,128,.95)' : 'rgba(22,163,74,.95)'; }

  _redraw(hoverPt) {
    this.resizeIfNeeded();
    const ctx = this.octx, v = this.viewer;
    this._clearCanvas();
    // 暗色主题加浅色描边提升对比
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    for (const s of this.strokes) {
      const col = s.brush === 'fg' ? this._fgCol() : this._bgCol();
      const sSize = s.size != null ? s.size : this.brushSize;   // 每笔记录自身粗细，改滑杆不影响已画笔画
      ctx.strokeStyle = col;
      ctx.fillStyle = col;
      ctx.lineWidth = Math.max(2, sSize * v.scale);
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.shadowColor = dark ? 'rgba(255,255,255,.35)' : 'rgba(0,0,0,.25)';
      ctx.shadowBlur = 2;
      ctx.beginPath();
      s.pts.forEach((p, i) => {
        const [x, y] = this._toScreen(p);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      if (s.pts.length === 1) { const [x, y] = this._toScreen(s.pts[0]); ctx.arc(x, y, ctx.lineWidth / 2, 0, 7); ctx.fill(); }
      else ctx.stroke();
      ctx.shadowBlur = 0;
    }
    if (this.enabled && hoverPt && !this.drawing) {
      const [x, y] = this._toScreen(hoverPt);
      ctx.beginPath();
      ctx.strokeStyle = this.brush === 'fg' ? this._fgCol() : this._bgCol();
      ctx.lineWidth = 1.5;
      ctx.arc(x, y, (this.brushSize * v.scale) / 2, 0, 7);
      ctx.stroke();
    }
    // 框选矩形等临时叠加：每次重绘后调用（不被 _clearCanvas 清掉）
    if (this.onOverlay) this.onOverlay(ctx);
  }
  resizeIfNeeded() {
    const vp = this.viewer.viewport.getBoundingClientRect();
    if (this.overlay.width !== vp.width) { this.overlay.width = vp.width; this.overlay.height = vp.height; }
  }

  /* 导出前景/背景涂抹为图像尺寸的 mask Blob（用于上传 refine）。 */
  async exportMasks() {
    const img = this.viewer.img;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const build = async (brush) => {
      const c = document.createElement('canvas'); c.width = iw; c.height = ih;
      const x = c.getContext('2d');
      x.fillStyle = '#000'; x.fillRect(0, 0, iw, ih);
      x.strokeStyle = '#fff'; x.fillStyle = '#fff'; x.lineCap = 'round'; x.lineJoin = 'round';
      for (const s of this.strokes) {
        if (s.brush !== brush) continue;
        x.lineWidth = s.size != null ? s.size : this.brushSize;   // 每笔按自身粗细导出 mask
        x.beginPath();
        s.pts.forEach((p, i) => i ? x.lineTo(p[0], p[1]) : x.moveTo(p[0], p[1]));
        if (s.pts.length === 1) { x.arc(s.pts[0][0], s.pts[0][1], x.lineWidth / 2, 0, 7); x.fill(); }
        else x.stroke();
      }
      return new Promise(r => c.toBlob(r, 'image/png'));
    };
    const has = (b) => this.strokes.some(s => s.brush === b);
    return {
      fgd: has('fg') ? await build('fg') : null,
      bgd: has('bg') ? await build('bg') : null,
    };
  }

  /* 导出「第一次分割」的形状 init_mask（椭圆/自由曲线）：图像尺寸黑底白前景。
     shape='ellipse' 用 rectBox；'freehand' 用 pts 轨迹。返回 Blob 或 null。 */
  async exportShapeMask(shape, rectBox, pts) {
    const img = this.viewer.img;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    if (!iw || !ih) return null;
    const c = document.createElement('canvas'); c.width = iw; c.height = ih;
    const x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, iw, ih);
    x.fillStyle = '#fff';
    if (shape === 'ellipse') {
      if (!rectBox) return null;
      const ax = Math.min(rectBox.x1, rectBox.x2), ay = Math.min(rectBox.y1, rectBox.y2);
      const bx = Math.max(rectBox.x1, rectBox.x2), by = Math.max(rectBox.y1, rectBox.y2);
      const w = bx - ax, h = by - ay;
      if (w < 5 || h < 5) return null;
      x.beginPath();
      x.ellipse(ax + w / 2, ay + h / 2, w / 2, h / 2, 0, 0, 7);
      x.fill();
    } else if (shape === 'freehand') {
      if (!pts || pts.length < 3) return null;
      x.beginPath();
      pts.forEach((p, i) => i ? x.lineTo(p[0], p[1]) : x.moveTo(p[0], p[1]));
      x.closePath();
      x.fill();
    } else {
      return null;
    }
    return new Promise(r => c.toBlob(r, 'image/png'));
  }
}
