/* 图纸画板：前端 canvas 实时绘制（与后端 _draw_bead 同心圆环+孔洞同比例），
   后端持权威网格（撤销/重做/BOM/导出）。复用 Viewer 变换（缩放/平移/适应）。
   透明占位图欺骗 Viewer 的 img.src 门槛，使缩放/平移在画板态可用；
   左键交给画板（_interactionLock=true），中键仍平移。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const viewer = window.viewer;

  /* 1×1 透明像素占位图：让 Viewer 认为「有图」从而启用缩放/平移/适应。 */
  const TRANSPARENT_PX =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

  const CELL = 30;                 // 虚拟像素/格（与后端 CHART_BEAD_PX 对齐，仅影响渲染精细度）
  const PEGBOARD = '#f5f3ee';      // 底板色（与后端 PEGBOARD(245,243,238) 一致）

  /* ---- 画板本地状态（后端为权威，这里镜像 + 待提交的增量） ---- */
  const B = {
    active: false, size: 52, brand: 'mard',
    grid: null,                     // size×size，色号 str 或 null
    palette: [],                    // [{code,name,hex}]
    tool: 'pen',                    // pen | eraser | fill | rect
    color: null,                    // 当前色号
    brush: 1,                       // 笔触粗细（格）
    style: 'real',                  // real 真实风 | square 图纸风
    base: false, baseVisible: true, baseOpacity: 0.35,
    baseImg: null,                  // 已裁剪底图 HTMLImage（叠加显示）
    baseSrcImg: null,               // 待裁剪底图原图
    cropping: false, cropBox: null, cropDrag: null,
    undo: false, redo: false,
    drawing: false, stroke: null,   // 进行中的笔画 {code, cells:Set(key), grid0}
    rectStart: null, rectEnd: null,
  };

  /* 画板专属画布：叠在 viewport 上，尺寸=size*CELL，用 Viewer 同一 transform 定位。 */
  const boardCanvas = document.createElement('canvas');
  boardCanvas.id = 'boardCanvas';
  boardCanvas.style.cssText = 'position:absolute;left:0;top:0;transform-origin:0 0;pointer-events:none;display:none;image-rendering:pixelated;';
  const bctx = boardCanvas.getContext('2d');

  /* ---- 工具 ---- */
  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    return [parseInt(h.substr(0, 2), 16), parseInt(h.substr(2, 2), 16), parseInt(h.substr(4, 2), 16)];
  }
  function shade(hex, f) {
    const [r, g, b] = hexToRgb(hex);
    return `rgb(${Math.round(r * f)},${Math.round(g * f)},${Math.round(b * f)})`;
  }
  function colorOf(code) {
    if (!code) return null;
    const c = B.palette.find(p => p.code === code);
    return c ? c.hex : '#808080';
  }
  /* 与后端 _draw_bead 完全同比例：外圈 shade(0.72) R=cell*0.46，豆体 R*0.82，
     孔缘 shade(0.55) hr=cell*0.13，孔 PEGBOARD hr*0.72。 */
  function drawBead(ctx, px, py, cell, code) {
    if (!code) return;
    const hex = colorOf(code);
    if (B.style !== 'real') { ctx.fillStyle = hex; ctx.fillRect(px, py, cell, cell); return; }
    const cx = px + cell / 2, cy = py + cell / 2;
    const r = cell * 0.46;
    ctx.fillStyle = shade(hex, 0.72); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fill();
    const ri = r * 0.82;
    ctx.fillStyle = hex; ctx.beginPath(); ctx.arc(cx, cy, ri, 0, 7); ctx.fill();
    const hr = cell * 0.13;
    ctx.fillStyle = shade(hex, 0.55); ctx.beginPath(); ctx.arc(cx, cy, hr, 0, 7); ctx.fill();
    ctx.fillStyle = PEGBOARD; ctx.beginPath(); ctx.arc(cx, cy, hr * 0.72, 0, 7); ctx.fill();
  }

  /* ---- 渲染全板 ---- */
  function render() {
    if (!B.active) return;
    const s = B.size, dim = s * CELL;
    if (boardCanvas.width !== dim) { boardCanvas.width = dim; boardCanvas.height = dim; }
    bctx.clearRect(0, 0, dim, dim);
    // 底板
    bctx.fillStyle = PEGBOARD; bctx.fillRect(0, 0, dim, dim);
    // 底图（裁剪好，拉伸铺满整块板，高透明度叠加在豆之下）
    if (B.base && B.baseVisible && B.baseImg && B.baseImg.complete) {
      bctx.save(); bctx.globalAlpha = B.baseOpacity;
      bctx.imageSmoothingEnabled = true;
      bctx.drawImage(B.baseImg, 0, 0, dim, dim);
      bctx.restore();
    }
    // 网格线（图纸风/真实风都画，助对齐）
    bctx.strokeStyle = 'rgba(0,0,0,.08)'; bctx.lineWidth = 1;
    bctx.beginPath();
    for (let i = 0; i <= s; i++) {
      bctx.moveTo(i * CELL + .5, 0); bctx.lineTo(i * CELL + .5, dim);
      bctx.moveTo(0, i * CELL + .5); bctx.lineTo(dim, i * CELL + .5);
    }
    bctx.stroke();
    // 豆
    for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
      const code = B.grid[y][x];
      if (code) drawBead(bctx, x * CELL, y * CELL, CELL, code);
    }
    // 进行中笔画（未提交，直接画，提交时后端回写后整板重渲染）
    if (B.stroke) {
      for (const key of B.stroke.cells) {
        const [x, y] = key.split(',').map(Number);
        if (B.stroke.code) drawBead(bctx, x * CELL, y * CELL, CELL, B.stroke.code);
        else { // 橡皮：擦回底板
          bctx.fillStyle = PEGBOARD; bctx.fillRect(x * CELL, y * CELL, CELL, CELL);
        }
      }
    }
    // 框选预览
    if (B.rectStart && B.rectEnd) {
      const x1 = Math.min(B.rectStart[0], B.rectEnd[0]), y1 = Math.min(B.rectStart[1], B.rectEnd[1]);
      const x2 = Math.max(B.rectStart[0], B.rectEnd[0]), y2 = Math.max(B.rectStart[1], B.rectEnd[1]);
      bctx.save();
      bctx.strokeStyle = 'rgba(124,58,237,.95)'; bctx.lineWidth = 2; bctx.setLineDash([6, 4]);
      bctx.strokeRect(x1 * CELL, y1 * CELL, (x2 - x1 + 1) * CELL, (y2 - y1 + 1) * CELL);
      bctx.restore();
    }
  }

  /* 同步画布 transform 到 Viewer（画板画布跟随缩放/平移） */
  function syncTransform() {
    boardCanvas.style.transform =
      `translate(${viewer.tx}px,${viewer.ty}px) scale(${viewer.scale})`;
  }
  /* 包装 viewer._apply：每次视图变换后同步画板画布 */
  const _apply = viewer._apply.bind(viewer);
  viewer._apply = function () { _apply(); syncTransform(); };

  /* 屏幕坐标 → 格坐标（仿 scribble._toImage，但以画板虚拟尺寸为界） */
  function toCell(e) {
    const rect = viewer.viewport.getBoundingClientRect();
    const px = (e.clientX - rect.left - viewer.tx) / viewer.scale;
    const py = (e.clientY - rect.top - viewer.ty) / viewer.scale;
    const x = Math.floor(px / CELL), y = Math.floor(py / CELL);
    if (x < 0 || y < 0 || x >= B.size || y >= B.size) return null;
    return [x, y];
  }

  /* ---- 进入画板 ---- */
  window.onEnterBoard = async function () {
    if (window.exitScribbleInteraction) window.exitScribbleInteraction();
    const vp = viewer.viewport;
    if (!boardCanvas.parentNode) vp.appendChild(boardCanvas);
    boardCanvas.style.display = 'block';
    viewer._interactionLock = true;         // 左键让给画板
    vp.classList.add('board-mode');
    syncViewToggle();
    // 占位图欺骗 Viewer img.src 门槛（缩放/平移/适应/鹰眼可用）
    if (!viewer.img.src) viewer.img.src = TRANSPARENT_PX;
    viewer.img.classList.add('has-img');
    $('emptyHint').style.display = 'none';
    await refresh(true);
  };
  /* 离开画板（切回图像转换时由 app.onViewSwitch 链触发） */
  window.onExitBoard = function () {
    boardCanvas.style.display = 'none';
    viewer._interactionLock = false;
    viewer.viewport.classList.remove('board-mode');
    B.cropping = false; B.cropBox = null;
  };

  /* 视图切换按钮：画板态显示「真实风/图纸风」，图像转换态恢复原五模式 */
  function syncViewToggle() {
    const vt = $('viewToggle');
    if (!vt) return;
    vt.innerHTML = `
      <button class="${B.style === 'real' ? 'on' : ''}" data-bstyle="real">真实风</button>
      <button class="${B.style === 'square' ? 'on' : ''}" data-bstyle="square">图纸风</button>`;
    vt.onclick = (e) => {
      const b = e.target.closest('button'); if (!b) return;
      B.style = b.dataset.bstyle;
      [...vt.children].forEach(x => x.classList.toggle('on', x === b));
      render();
    };
  }

  /* ---- 拉取/同步状态 ---- */
  async function refresh(fitView) {
    try {
      const st = await API.boardState();
      if (!st.active) { // 尚未建板：默认建 52
        await API.boardNew(52, B.brand);
        return refresh(fitView);
      }
      B.active = true; B.size = st.size; B.brand = st.brand;
      B.grid = st.grid; B.palette = st.palette;
      B.base = st.base; B.baseVisible = st.base_visible; B.baseOpacity = st.base_opacity;
      B.undo = st.can_undo; B.redo = st.can_redo;
      if (!B.color && st.palette.length) B.color = st.palette[0].code;
      if (B.base && !B.baseImg) {
        const im = new Image();
        im.onload = render; im.src = API.boardBaseImageUrl();
        B.baseImg = im;
      }
      buildToolbar();
      render();
      if (fitView) requestAnimationFrame(() => { fitBoard(); });
      syncToolbarState();
      if (st.bom && window.renderBom) { /* BOM 可在工具栏内显示，见 buildToolbar */ renderBoardBom(st.bom); }
    } catch (e) { window.fail('画板加载失败: ' + e.message); }
  }
  function fitBoard() {
    const dim = B.size * CELL;
    const r = viewer.viewport.getBoundingClientRect();
    const s = Math.min((r.width - 24) / dim, (r.height - 24) / dim, 1);
    viewer.scale = Math.max(0.05, s);
    viewer.tx = (r.width - dim * viewer.scale) / 2;
    viewer.ty = (r.height - dim * viewer.scale) / 2;
    viewer._userMoved = false;
    syncTransform();
  }

  /* ---- 提交笔画 ---- */
  async function commitStroke() {
    if (!B.stroke || !B.stroke.cells.size) { B.stroke = null; return; }
    const cells = [...B.stroke.cells].map(k => k.split(',').map(Number));
    const code = B.stroke.code;
    // 先本地应用（即时反馈），再让后端算增量入栈
    for (const [x, y] of cells) B.grid[y][x] = code;
    B.stroke = null; render();
    try {
      const r = await API.boardStroke(cells, code);
      B.undo = r.can_undo; B.redo = r.can_redo;
      syncToolbarState();
    } catch (e) { window.fail('绘制失败: ' + e.message); refresh(false); }
  }
  async function doFill(x, y) {
    const code = (B.tool === 'eraser') ? null : B.color;
    try {
      busy.start('填充中…');
      await API.boardFill(x, y, code);
      await refresh(false);
      busy.done('已填充');
    } catch (e) { window.fail('填充失败: ' + e.message); }
  }

  /* 笔画覆盖：以 (x,y) 为中心 brush 见方的格 */
  function stamp(x, y) {
    const half = Math.floor(B.brush / 2);
    for (let dy = 0; dy < B.brush; dy++) for (let dx = 0; dx < B.brush; dx++) {
      const cx = x - half + dx, cy = y - half + dy;
      if (cx >= 0 && cy >= 0 && cx < B.size && cy < B.size) B.stroke.cells.add(cx + ',' + cy);
    }
  }

  /* ---- 画布事件（捕获阶段，优先于 Viewer 平移） ---- */
  const vp = viewer.viewport;
  vp.addEventListener('mousedown', (e) => {
    if (!B.active || boardCanvas.style.display === 'none') return;
    if (B.cropping) return;                    // 裁剪态由裁剪逻辑接管
    if (e.button !== 0) return;                // 中键留给 Viewer 平移
    e.stopPropagation(); e.preventDefault();
    const c = toCell(e); if (!c) return;
    if (B.tool === 'fill') { doFill(c[0], c[1]); return; }
    if (B.tool === 'rect') { B.rectStart = c; B.rectEnd = c; render(); return; }
    // pen / eraser：起笔
    B.drawing = true;
    B.stroke = { code: (B.tool === 'eraser') ? null : B.color, cells: new Set() };
    stamp(c[0], c[1]);
    render();
  }, true);
  window.addEventListener('mousemove', (e) => {
    if (!B.active) return;
    if (B.cropping) { cropMove(e); return; }
    if (B.rectStart && !B.drawing) {           // 框选拖动
      const c = toCell(e); if (c) { B.rectEnd = c; render(); }
      return;
    }
    if (!B.drawing || !B.stroke) return;
    const c = toCell(e); if (!c) return;
    stamp(c[0], c[1]);
    render();
  });
  window.addEventListener('mouseup', async (e) => {
    if (!B.active) return;
    if (B.cropping) { cropEnd(e); return; }
    if (B.rectStart && B.rectEnd && B.tool === 'rect') {
      // 框选完成：把矩形区域作为一次笔画（填充当前色）
      const x1 = Math.min(B.rectStart[0], B.rectEnd[0]), y1 = Math.min(B.rectStart[1], B.rectEnd[1]);
      const x2 = Math.max(B.rectStart[0], B.rectEnd[0]), y2 = Math.max(B.rectStart[1], B.rectEnd[1]);
      const cells = [];
      for (let y = y1; y <= y2; y++) for (let x = x1; x <= x2; x++) cells.push([x, y]);
      B.rectStart = B.rectEnd = null;
      for (const [x, y] of cells) B.grid[y][x] = B.color;
      render();
      try {
        const r = await API.boardStroke(cells, B.color);
        B.undo = r.can_undo; B.redo = r.can_redo; syncToolbarState();
      } catch (err) { window.fail('框选失败: ' + err.message); refresh(false); }
      return;
    }
    if (B.drawing) { B.drawing = false; await commitStroke(); }
  });

  /* ---- 底图裁剪（正方形框选） ---- */
  function cropStart() {
    if (!B.baseSrcImg) return;
    B.cropping = true; B.cropBox = null; B.cropDrag = null;
    busy.set('在底图上拖出一个正方形区域，松手后填满画板');
  }
  function cropToSrc(e) {
    // 底图原图以原始像素显示在画板坐标（1 源像素 = CELL 虚拟像素，与豆格无关）
    const rect = vp.getBoundingClientRect();
    const px = (e.clientX - rect.left - viewer.tx) / viewer.scale;
    const py = (e.clientY - rect.top - viewer.ty) / viewer.scale;
    return [px, py];
  }
  function cropMove(e) {
    if (!B.cropDrag) return;
    const [px, py] = cropToSrc(e);
    B.cropDrag.x2 = px; B.cropDrag.y2 = py;
    drawCrop();
  }
  function cropEnd(e) {
    if (!B.cropDrag) return;
    const d = B.cropDrag;
    const x1 = Math.round(Math.min(d.x1, d.x2)), y1 = Math.round(Math.min(d.y1, d.y2));
    const x2 = Math.round(Math.max(d.x1, d.x2)), y2 = Math.round(Math.max(d.y1, d.y2));
    const side = Math.min(x2 - x1, y2 - y1);
    B.cropDrag = null;
    if (side < 8) { B.cropBox = null; drawCrop(); return; }
    B.cropBox = [x1, y1, x1 + side, y1 + side];   // 强制正方形
    drawCrop();
    applyCrop();
  }
  vp.addEventListener('mousedown', (e) => {
    if (!B.cropping || e.button !== 0) return;
    e.stopPropagation(); e.preventDefault();
    const [px, py] = cropToSrc(e);
    B.cropDrag = { x1: px, y1: py, x2: px, y2: py };
  }, true);
  function drawCrop() { render(); if (B.cropping) overlayCrop(); }
  function overlayCrop() {
    // 裁剪框画在 boardCanvas 之上：底图原图显示态
    const s = B.size, dim = s * CELL;
    bctx.save();
    if (B.baseSrcImg && B.baseSrcImg.complete) {
      bctx.globalAlpha = 1; bctx.imageSmoothingEnabled = true;
      bctx.drawImage(B.baseSrcImg, 0, 0, B.baseSrcImg.naturalWidth * CELL, B.baseSrcImg.naturalHeight * CELL);
    }
    if (B.cropDrag || B.cropBox) {
      const b = B.cropDrag ? [Math.min(B.cropDrag.x1, B.cropDrag.x2), Math.min(B.cropDrag.y1, B.cropDrag.y2),
        Math.max(B.cropDrag.x1, B.cropDrag.x2), Math.max(B.cropDrag.y1, B.cropDrag.y2)] : B.cropBox;
      bctx.strokeStyle = 'rgba(124,58,237,.95)'; bctx.lineWidth = 3; bctx.setLineDash([8, 5]);
      const side = Math.min(b[2] - b[0], b[3] - b[1]);
      bctx.strokeRect(b[0], b[1], side, side);
      bctx.setLineDash([]);
    }
    bctx.restore();
  }
  async function applyCrop() {
    if (!B.cropBox) return;
    try {
      busy.start('裁剪底图…');
      await API.boardBaseCrop(B.cropBox);
      B.cropping = false; B.cropBox = null;
      B.base = true; B.baseVisible = true;
      const im = new Image();
      im.onload = () => { render(); busy.done('底图已设为参考'); };
      im.src = API.boardBaseImageUrl();
      B.baseImg = im;
      buildToolbar(); syncToolbarState();
    } catch (e) { window.fail('裁剪失败: ' + e.message); }
  }

  /* ---- 工具栏（注入 #boardCards） ---- */
  function toolBtn(id, tip, svg) {
    return `<button class="tool-mini board-tool" id="${id}" data-tip="${tip}" title="${tip}">${svg}</button>`;
  }
  const ICONS = {
    pen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>',
    eraser: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 20H8L3 15a2 2 0 0 1 0-2.8l8.2-8.2a2 2 0 0 1 2.8 0l6 6a2 2 0 0 1 0 2.8L13 20"/></svg>',
    fill: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 11l-8-8-8.5 8.5a2.1 2.1 0 0 0 3 3L11 9l8 8"/><path d="M5 3l7 7"/></svg>',
    rect: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>',
    undo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/></svg>',
    redo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 15-6.7L21 13"/></svg>',
    clear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',
  };

  function buildToolbar() {
    const host = $('boardCards');
    if (!host) return;
    const sizeOpts = [52, 104].map(s =>
      `<option value="${s}" ${s === B.size ? 'selected' : ''}>${s}×${s}</option>`).join('');
    const brandOpts = Object.entries(BRAND_LABELS).map(([k, v]) =>
      `<option value="${k}" ${k === B.brand ? 'selected' : ''}>${v}</option>`).join('');
    host.innerHTML = `
      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>画板</h3>
        <div class="num-row"><label>规格</label><select id="boardSize" style="flex:1">${sizeOpts}</select></div>
        <div class="num-row"><label>品牌豆色</label><select id="boardBrand" style="flex:1">${brandOpts}</select></div>
        <div class="tool-row" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
          ${toolBtn('btPen', '画笔（左键点击/涂抹）', ICONS.pen)}
          ${toolBtn('btEraser', '橡皮擦', ICONS.eraser)}
          ${toolBtn('btFill', '填充（油漆桶）', ICONS.fill)}
          ${toolBtn('btRect', '框选填充', ICONS.rect)}
          <span style="flex:none;width:1px;background:var(--color-border);margin:0 2px"></span>
          ${toolBtn('btUndo', '撤销（5步）', ICONS.undo)}
          ${toolBtn('btRedo', '重做（5步）', ICONS.redo)}
          ${toolBtn('btClear', '清空画板', ICONS.clear)}
        </div>
        <div class="num-row" style="margin-top:8px"><label>笔触粗细</label>
          <input type="range" id="boardBrush" min="1" max="3" step="1" value="${B.brush}" style="flex:1">
          <span id="boardBrushOut" class="num-out">${B.brush}</span>
        </div>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/></svg>豆色（圆环+编号）</h3>
        <div id="boardPalette" class="board-palette"></div>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5-6 6"/></svg>参考底图</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-ghost" id="boardBaseLoadBtn" style="flex:1">导入底图…</button>
          <button class="btn btn-ghost" id="boardBaseClearBtn">清除</button>
        </div>
        <input type="file" id="boardBaseFile" accept="image/*" style="display:none">
        <div class="num-row" style="margin-top:8px"><label>显示</label>
          <input type="checkbox" id="boardBaseVis" ${B.baseVisible ? 'checked' : ''}></div>
        <div class="num-row"><label>透明度</label>
          <input type="range" id="boardBaseOp" min="0.1" max="1" step="0.05" value="${B.baseOpacity}" style="flex:1">
          <span id="boardBaseOpOut" class="num-out">${Math.round(B.baseOpacity * 100)}%</span></div>
        <p class="hint">导入后在画布上拖出正方形，裁剪铺满画板。</p>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></svg>导出图纸</h3>
        <div class="num-row"><label>风格</label>
          <select id="boardExpStyle" style="flex:1">
            <option value="real" ${B.style === 'real' ? 'selected' : ''}>真实风</option>
            <option value="square" ${B.style === 'square' ? 'selected' : ''}>图纸风</option>
          </select></div>
        <div class="num-row"><label>文件名</label>
          <input type="text" id="boardExpName" value="board" style="flex:1"></div>
        <button class="btn btn-primary" id="boardExportBtn" style="width:100%;margin-top:8px">导出 PNG + BOM</button>
        <p class="hint" id="boardExpResult">导出图纸与物料清单。</p>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>物料清单 (BOM)</h3>
        <div id="boardBomList" class="chip-row" style="gap:6px"><p class="hint">绘制后显示所需豆子。</p></div>
      </div>
    `;
    buildPalette();
    bindToolbar();
    syncToolbarState();
  }

  function buildPalette() {
    const host = $('boardPalette'); if (!host) return;
    host.innerHTML = B.palette.map(c => `
      <button class="bead-dot ${c.code === B.color ? 'sel' : ''}" data-code="${c.code}"
        title="${c.name} (${c.code})" style="--bc:${c.hex}">
        <span class="bead-ring"></span><span class="bead-code">${c.code}</span>
      </button>`).join('');
    host.querySelectorAll('.bead-dot').forEach(b => b.addEventListener('click', () => {
      B.color = b.dataset.code;
      host.querySelectorAll('.bead-dot').forEach(x => x.classList.toggle('sel', x === b));
      if (B.tool === 'eraser') setTool('pen');   // 选色自动切回画笔
    }));
  }

  function setTool(t) {
    B.tool = t;
    ['btPen', 'btEraser', 'btFill', 'btRect'].forEach(id => {
      const el = $(id); if (el) el.classList.toggle('on',
        (id === 'btPen' && t === 'pen') || (id === 'btEraser' && t === 'eraser') ||
        (id === 'btFill' && t === 'fill') || (id === 'btRect' && t === 'rect'));
    });
    vp.style.cursor = (t === 'pen' || t === 'eraser') ? 'crosshair' : '';
  }

  function syncToolbarState() {
    const u = $('btUndo'), r = $('btRedo');
    if (u) u.disabled = !B.undo;
    if (r) r.disabled = !B.redo;
  }

  function bindToolbar() {
    $('boardSize').addEventListener('change', async () => {
      const sz = +$('boardSize').value;
      if (!confirm('切换到 ' + sz + '×' + sz + ' 将清空当前画板，确定？')) { $('boardSize').value = B.size; return; }
      await API.boardNew(sz, B.brand); B.baseImg = null; await refresh(true);
    });
    $('boardBrand').addEventListener('change', async () => {
      if (!confirm('切换品牌豆色将清空当前画板（色号体系不同），确定？')) { $('boardBrand').value = B.brand; return; }
      B.brand = $('boardBrand').value; B.baseImg = null;
      await API.boardNew(B.size, B.brand); await refresh(true);
    });
    $('btPen').addEventListener('click', () => setTool('pen'));
    $('btEraser').addEventListener('click', () => setTool('eraser'));
    $('btFill').addEventListener('click', () => setTool('fill'));
    $('btRect').addEventListener('click', () => setTool('rect'));
    $('btUndo').addEventListener('click', async () => { try { await API.boardUndo(); await refresh(false); } catch (e) { busy.set(e.message); } });
    $('btRedo').addEventListener('click', async () => { try { await API.boardRedo(); await refresh(false); } catch (e) { busy.set(e.message); } });
    $('btClear').addEventListener('click', async () => {
      if (!confirm('清空整块画板？（可撤销）')) return;
      await API.boardClear(); await refresh(false);
    });
    $('boardBrush').addEventListener('input', () => {
      B.brush = +$('boardBrush').value; $('boardBrushOut').textContent = B.brush;
    });
    // 底图
    $('boardBaseLoadBtn').addEventListener('click', () => $('boardBaseFile').click());
    $('boardBaseFile').addEventListener('change', async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try {
        busy.start('导入底图…');
        await API.boardBaseLoad(f);            // 暂存后端供裁剪
        const im = new Image();                // 本地预览（原图，供框选）
        im.onload = () => {
          B.baseSrcImg = im; B.cropping = true; fitBoard(); cropStart();
          busy.done('在底图上拖出正方形区域');
        };
        im.src = URL.createObjectURL(f);
        e.target.value = '';
      } catch (err) { window.fail('导入底图失败: ' + err.message); }
    });
    $('boardBaseClearBtn').addEventListener('click', async () => {
      await API.boardBaseClear(); B.base = false; B.baseImg = null; B.baseSrcImg = null; render(); buildToolbar();
    });
    $('boardBaseVis').addEventListener('change', async () => {
      B.baseVisible = $('boardBaseVis').checked;
      await API.boardBaseOptions(B.baseVisible, B.baseOpacity); render();
    });
    $('boardBaseOp').addEventListener('input', async () => {
      B.baseOpacity = +$('boardBaseOp').value;
      $('boardBaseOpOut').textContent = Math.round(B.baseOpacity * 100) + '%';
      render();
      await API.boardBaseOptions(B.baseVisible, B.baseOpacity);
    });
    // 导出
    $('boardExportBtn').addEventListener('click', async () => {
      try {
        busy.start('导出图纸…');
        const od = (await API.getOutputDir()).output_dir;
        const r = await API.boardExport({
          filename: $('boardExpName').value || 'board',
          output_dir: od, bead_style: $('boardExpStyle').value,
        });
        $('boardExpResult').textContent = '已导出: ' + r.files[0];
        busy.done('已导出（共 ' + r.bom.total_beads + ' 豆）');
      } catch (e) { window.fail('导出失败: ' + e.message); }
    });
  }

  function renderBoardBom(bom) {
    const list = $('boardBomList'); if (!list) return;
    if (!bom || !bom.colors || !Object.keys(bom.colors).length) {
      list.innerHTML = '<p class="hint">绘制后显示所需豆子。</p>'; return;
    }
    const items = Object.entries(bom.colors).sort((a, b) => b[1].count - a[1].count);
    list.innerHTML = items.map(([code, info]) => `
      <span class="chip" style="display:inline-flex;align-items:center;gap:6px;padding:4px 12px 4px 4px">
        <span style="min-width:22px;height:22px;padding:0 5px;border-radius:999px;background:${info.hex};
          color:${(parseInt(info.hex.slice(1, 3), 16) * .3 + parseInt(info.hex.slice(3, 5), 16) * .59 + parseInt(info.hex.slice(5, 7), 16) * .11) > 140 ? '#3b0a1c' : '#fff'};
          display:inline-grid;place-items:center;font-size:9.5px;font-weight:800;white-space:nowrap">${code}</span>
        <span>×${info.count}</span></span>`).join('') +
      `<p class="hint" style="width:100%;margin-top:6px">共 ${bom.total_beads} 豆 · ${items.length} 种颜色</p>`;
  }

  const BRAND_LABELS = {
    mard: 'MARD 豆子', perler: 'Perler', hama: 'Hama',
    artkal_s: 'Artkal S-5mm', artkal_c: 'Artkal C-2.6mm',
  };

  /* 切回图像转换时退出画板：串接 onViewSwitch 链 */
  const _prevSwitch = window.onViewSwitch;
  window.onViewSwitch = function (name) {
    if (boardCanvas.style.display !== 'none') window.onExitBoard();
    if (_prevSwitch) return _prevSwitch(name);
  };

  /* 窗口尺寸变化时保持画板画布叠加层跟随（transform 已由 _apply 同步） */
  window.addEventListener('resize', () => { if (B.active) syncTransform(); });
})();
