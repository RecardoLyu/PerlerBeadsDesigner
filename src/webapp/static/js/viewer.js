/* 画布查看器：缩放（Ctrl+滚轮/按钮）、平移（拖拽/中键）、适应窗口、鹰眼 minimap。 */
class Viewer {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.viewport = canvasEl.querySelector('.viewport');
    this.img = canvasEl.querySelector('img');
    this.minimap = canvasEl.querySelector('.minimap');
    // 迷你图用 <canvas>，直接 drawImage(主图 img) 取已渲染好的像素 —— 彻底绕开
    // WebView2 对第二张 <img> 不触发合成/解码导致「白色背景」的缺陷。
    this.miniCanvas = this.minimap?.querySelector('canvas') || null;
    this.miniCtx = this.miniCanvas ? this.miniCanvas.getContext('2d') : null;
    this.vp = this.minimap?.querySelector('.vp') || null;
    this.scale = 1; this.tx = 0; this.ty = 0;
    this.panning = false; this._ps = null; this._pstart = null;
    this._miniDrag = null;
    this._userMoved = false;   // 用户手动平移/缩放后置位；fit 重置，窗口 resize 仅在未手动操作时 refit
    this._bind();
    this._bindMiniDrag();
    // viewport 尺寸变化（窗口缩放 / 侧栏折叠）时重新 fit，保持图纸居中。
    // 已手动平移/缩放则保留用户视角不打扰。
    if (typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(() => { if (this.img.src && !this._userMoved) this.fit(); });
      this._ro.observe(this.viewport);
    } else {
      window.addEventListener('resize', () => { if (this.img.src && !this._userMoved) this.fit(); });
    }
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
      this._userMoved = true;
      this._apply();
    }, { passive: false });

    const start = (e) => {
      if (!this.img.src) return;
      // 涂鸦/框选/裁剪时让位：左键交给交互层，但中键仍允许平移视图（放大时调整整体 ROI）
      if (this._interactionLock && e.button !== 1) return;
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
      this._userMoved = true;
      this._apply();
    };
    const end = () => { this.panning = false; this.viewport.classList.remove('panning'); };
    this.viewport.addEventListener('mousedown', start);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', end);
    this.viewport.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  async setImage(url) {
    if (!url) { this.img.removeAttribute('src'); this.img.classList.remove('has-img'); this._hideMini(); return; }
    // 给同源 URL 追加时间戳，强制刷新缓存（data:/blob: 不含 '?' 原样返回）。
    const busted = this._bust(url);
    // 主图加载完成后：显示 + 适应 + 画鹰眼（迷你图直接 drawImage 主图像素）。
    this.img.onload = () => { this.img.classList.add('has-img'); this.fit(); this._updateMini(); };
    this.img.src = busted;
    // 缓存命中时已 complete，onload 不再触发 → 立即补一次
    if (this.img.complete && this.img.naturalWidth) { this.img.classList.add('has-img'); this.fit(); this._updateMini(); }
  }

  _bust(url) {
    if (typeof url !== 'string' || url.startsWith('blob:') || url.startsWith('data:')) return url;
    return url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
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
    this._userMoved = false;
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
    this._userMoved = true;
    this._apply();
  }

  _updateMini() {
    if (!this.minimap || !this.img.src || !this.miniCtx) return;
    const iw = this.img.naturalWidth, ih = this.img.naturalHeight;
    if (!iw) return;
    const r = this.viewport.getBoundingClientRect();
    // 用 CSS 内容盒尺寸（减 padding），而不是量 getBoundingClientRect ——
    // minimap 在「未 show」时是 display:none，量出来是 0，会导致永远加不上 show。
    const cs = getComputedStyle(this.minimap);
    const iwCss = (parseFloat(cs.width)  || 124) - (parseFloat(cs.paddingLeft)  || 0) - (parseFloat(cs.paddingRight)  || 0);
    const ihCss = (parseFloat(cs.height) || 88)  - (parseFloat(cs.paddingTop)   || 0) - (parseFloat(cs.paddingBottom) || 0);
    if (iwCss < 2 || ihCss < 2) return;

    // 用主图当前已渲染好的像素画到迷你 canvas。devicePixelRatio 适配，保证缩略图锐利不糊。
    const dpr = window.devicePixelRatio || 1;
    const cw = Math.max(2, Math.round(iwCss * dpr));
    const ch = Math.max(2, Math.round(ihCss * dpr));
    if (this.miniCanvas.width !== cw || this.miniCanvas.height !== ch) {
      this.miniCanvas.width = cw; this.miniCanvas.height = ch;
    }
    const ctx = this.miniCtx;
    ctx.clearRect(0, 0, cw, ch);
    const mScale = Math.min(iwCss / iw, ihCss / ih);
    const drawW = iw * mScale * dpr, drawH = ih * mScale * dpr;
    const offX = (cw - drawW) / 2, offY = (ch - drawH) / 2;
    try { ctx.drawImage(this.img, offX, offY, drawW, drawH); } catch { return; }

    // visible image rect (image coords) → 投影到 inner 盒子百分比
    const vx = -this.tx / this.scale, vy = -this.ty / this.scale;
    const vw = r.width / this.scale, vh = r.height / this.scale;
    const offXp = (iwCss - iw * mScale) / 2;
    const offYp = (ihCss - ih * mScale) / 2;
    const x1 = offXp + Math.max(0, vx) * mScale;
    const y1 = offYp + Math.max(0, vy) * mScale;
    const x2 = offXp + Math.min(iw, vx + vw) * mScale;
    const y2 = offYp + Math.min(ih, vy + vh) * mScale;
    this.vp.style.left = (x1 / iwCss * 100) + '%';
    this.vp.style.top = (y1 / ihCss * 100) + '%';
    this.vp.style.width = Math.max(4, (x2 - x1) / iwCss * 100) + '%';
    this.vp.style.height = Math.max(4, (y2 - y1) / ihCss * 100) + '%';
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
      // 先把当前实际渲染位置（可能来自 CSS 的 right/bottom 定位）写进 style.left/top。
      // 否则首次点击时 style.left/top 为空，松手吸附 parseFloat(...)||0 → 0 → 闪到左上角。
      if (!this.minimap.style.left) {
        this.minimap.style.left = (mr.left - cr.left) + 'px';
        this.minimap.style.top = (mr.top - cr.top) + 'px';
        this.minimap.style.right = 'auto';
        this.minimap.style.bottom = 'auto';
      }
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
