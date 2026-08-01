/* 画布查看器：缩放（Ctrl+滚轮/按钮）、平移（拖拽/中键）、适应窗口、鹰眼 minimap。 */
class Viewer {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.viewport = canvasEl.querySelector('.viewport');
    this.img = canvasEl.querySelector('img');
    this.minimap = canvasEl.querySelector('.minimap');
    this.miniImg = this.minimap?.querySelector('img') || null;
    this.vp = this.minimap?.querySelector('.vp') || null;
    this.scale = 1; this.tx = 0; this.ty = 0;
    this.panning = false; this._ps = null; this._pstart = null;
    this._miniDrag = null;
    this._bind();
    this._bindMiniDrag();
  }

  _bind() {
    this.viewport.addEventListener('wheel', (e) => {
      if (!this.img.src) return;
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 0.89;
      const rect = this.viewport.getBoundingClientRect();
      const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
      const ns = Math.min(20, Math.max(0.05, this.scale * factor));
      // zoom about cursor
      const k = ns / this.scale;
      this.tx = cx - (cx - this.tx) * k;
      this.ty = cy - (cy - this.ty) * k;
      this.scale = ns;
      this._apply();
    }, { passive: false });

    const start = (e) => {
      if (!this.img.src) return;
      if (this._interactionLock) return;   // 涂鸦/框选时让位
      if (e.button === 1 || e.button === 0 || this._panMode) {
        this.panning = true; this.viewport.classList.add('panning');
        this._ps = { x: e.clientX, y: e.clientY };
        this._pstart = { x: this.tx, y: this.ty };
        if (e.button === 1) e.preventDefault();
      }
    };
    const move = (e) => {
      if (!this.panning) return;
      this.tx = this._pstart.x + (e.clientX - this._ps.x);
      this.ty = this._pstart.y + (e.clientY - this._ps.y);
      this._apply();
    };
    const end = () => { this.panning = false; this.viewport.classList.remove('panning'); };
    this.viewport.addEventListener('mousedown', start);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', end);
    this.viewport.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  setImage(url) {
    if (!url) { this.img.removeAttribute('src'); this._hideMini(); return; }
    this.img.onload = () => { this.fit(); if (this.miniImg) this.miniImg.src = url; };
    this.img.src = url;
  }

  _apply() {
    this.img.style.transform = `translate(${this.tx}px,${this.ty}px) scale(${this.scale})`;
    this._updateMini();
  }

  fit() {
    if (!this.img.naturalWidth) return;
    const r = this.viewport.getBoundingClientRect();
    const iw = this.img.naturalWidth, ih = this.img.naturalHeight;
    const s = Math.min((r.width - 24) / iw, (r.height - 24) / ih, 1);
    this.scale = Math.max(0.05, s);
    this.tx = (r.width - iw * this.scale) / 2;
    this.ty = (r.height - ih * this.scale) / 2;
    this._apply();
  }

  zoomBy(f) {
    const r = this.viewport.getBoundingClientRect();
    const cx = r.width / 2, cy = r.height / 2;
    const ns = Math.min(20, Math.max(0.05, this.scale * f));
    const k = ns / this.scale;
    this.tx = cx - (cx - this.tx) * k;
    this.ty = cy - (cy - this.ty) * k;
    this.scale = ns;
    this._apply();
  }

  _updateMini() {
    if (!this.minimap || !this.img.src || !this.miniImg) return;
    const r = this.viewport.getBoundingClientRect();
    const iw = this.img.naturalWidth, ih = this.img.naturalHeight;
    if (!iw) return;
    // visible image rect (image coords)
    const vx = -this.tx / this.scale, vy = -this.ty / this.scale;
    const vw = r.width / this.scale, vh = r.height / this.scale;
    // the inner box renders the image with object-fit:contain — find that rect
    const inner = this.minimap.querySelector('.inner');
    const ir = inner.getBoundingClientRect();
    const mScale = Math.min(ir.width / iw, ir.height / ih);
    const offX = (ir.width - iw * mScale) / 2;
    const offY = (ir.height - ih * mScale) / 2;
    // project visible rect into inner-box pixels, clamped to image bounds
    const x1 = offX + Math.max(0, vx) * mScale;
    const y1 = offY + Math.max(0, vy) * mScale;
    const x2 = offX + Math.min(iw, vx + vw) * mScale;
    const y2 = offY + Math.min(ih, vy + vh) * mScale;
    this.vp.style.left = (x1 / ir.width * 100) + '%';
    this.vp.style.top = (y1 / ir.height * 100) + '%';
    this.vp.style.width = Math.max(4, (x2 - x1) / ir.width * 100) + '%';
    this.vp.style.height = Math.max(4, (y2 - y1) / ir.height * 100) + '%';
    this.minimap.classList.add('show');
  }
  _hideMini() { this.minimap?.classList.remove('show'); }

  /* 鹰眼拖动：在画布内自由拖动，松手吸附到最近角（距边 14px） */
  _bindMiniDrag() {
    if (!this.minimap) return;
    const EDGE = 14;
    this.minimap.addEventListener('mousedown', (e) => {
      e.preventDefault(); e.stopPropagation();
      const cr = this.canvas.getBoundingClientRect();
      const mr = this.minimap.getBoundingClientRect();
      this._miniDrag = {
        dx: e.clientX - mr.left, dy: e.clientY - mr.top,
        cr, w: mr.width, h: mr.height,
      };
      this.minimap.classList.add('dragging');
    });
    window.addEventListener('mousemove', (e) => {
      if (!this._miniDrag) return;
      const d = this._miniDrag;
      let x = e.clientX - d.cr.left - d.dx;
      let y = e.clientY - d.cr.top - d.dy;
      x = Math.max(0, Math.min(d.cr.width - d.w, x));
      y = Math.max(0, Math.min(d.cr.height - d.h, y));
      this._miniPos(x, y, d.cr, true);
    });
    window.addEventListener('mouseup', () => {
      if (!this._miniDrag) return;
      const d = this._miniDrag; this._miniDrag = null;
      this.minimap.classList.remove('dragging');
      // snap to nearest corner
      const x = parseFloat(this.minimap.style.left) || 0;
      const y = parseFloat(this.minimap.style.top) || 0;
      const snapX = (x + d.w / 2 < d.cr.width / 2) ? EDGE : d.cr.width - d.w - EDGE;
      const snapY = (y + d.h / 2 < d.cr.height / 2) ? EDGE : d.cr.height - d.h - EDGE;
      this._miniPos(snapX, snapY, d.cr, true);
    });
  }
  _miniPos(x, y, cr, animate) {
    this.minimap.style.left = x + 'px';
    this.minimap.style.top = y + 'px';
    this.minimap.style.right = 'auto';
    this.minimap.style.bottom = 'auto';
  }
}
