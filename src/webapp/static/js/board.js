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
    baseImg: null,                  // 整幅底图 HTMLImage（叠加显示，按偏移+缩放裁切）
    baseOffX: 0, baseOffY: 0,       // 底图偏移（画板格坐标，可为负）
    baseScale: 1,                   // 底图缩放：1 源像素渲染为 baseScale 格（等比例）
    baseAdjust: false,              // 「调整底图」模式开关（与涂色互斥，画布缩放锁定）
    baseAdjustSnap: null,           // 进入调整时快照 {scale,offx,offy}，取消时回滚
    baseDrag: null,                 // 拖动底图中 {sx,sy,ox,oy}（屏幕像素）
    undo: false, redo: false,
    drawing: false, stroke: null,   // 进行中的笔画 {code, cells:Set(key), grid0, last:[x,y]}
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
    if (B.style !== 'real') {
      // 图纸风：实心方格 + 中央印色号（对齐图像转换图纸预览），按亮度选字色
      ctx.fillStyle = hex; ctx.fillRect(px, py, cell, cell);
      const [r, g, b] = hexToRgb(hex);
      const lum = r * .3 + g * .59 + b * .11;
      ctx.fillStyle = lum > 128 ? 'rgba(0,0,0,.85)' : 'rgba(255,255,255,.92)';
      ctx.font = `700 ${Math.round(cell * 0.4)}px sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(code, px + cell / 2, py + cell / 2);
      return;
    }
    const cx = px + cell / 2, cy = py + cell / 2;
    const r = cell * 0.46;
    ctx.fillStyle = shade(hex, 0.72); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fill();
    const ri = r * 0.82;
    ctx.fillStyle = hex; ctx.beginPath(); ctx.arc(cx, cy, ri, 0, 7); ctx.fill();
    const hr = cell * 0.13;
    ctx.fillStyle = shade(hex, 0.55); ctx.beginPath(); ctx.arc(cx, cy, hr, 0, 7); ctx.fill();
    ctx.fillStyle = PEGBOARD; ctx.beginPath(); ctx.arc(cx, cy, hr * 0.72, 0, 7); ctx.fill();
  }

  /* ---- 渲染全板 ----
     画布含左侧/顶部 MARGIN 边距用于横纵标号；豆格原点偏移 (MARGIN,MARGIN)。 */
  const MARGIN = Math.round(CELL * 1.4);   // 坐标标号边距
  function render() {
    if (!B.active) return;
    const s = B.size, dim = s * CELL, full = dim + MARGIN;
    if (boardCanvas.width !== full) { boardCanvas.width = full; boardCanvas.height = full; }
    bctx.clearRect(0, 0, full, full);
    bctx.save();
    bctx.translate(MARGIN, MARGIN);        // 豆格坐标系
    // 底板
    bctx.fillStyle = PEGBOARD; bctx.fillRect(0, 0, dim, dim);
    // 底图（整图按偏移叠加在豆之下，超出画板自动 clip 裁切）
    if (B.base && B.baseVisible && B.baseImg && B.baseImg.complete) {
      bctx.save();
      bctx.globalAlpha = B.baseOpacity;
      bctx.imageSmoothingEnabled = true;
      bctx.beginPath(); bctx.rect(0, 0, dim, dim); bctx.clip();   // 只画板内
      // 1 源像素 = baseScale 格（等比例）；偏移以「格」计 → 乘 CELL
      bctx.drawImage(B.baseImg, B.baseOffX * CELL, B.baseOffY * CELL,
        B.baseImg.naturalWidth * B.baseScale * CELL, B.baseImg.naturalHeight * B.baseScale * CELL);
      bctx.restore();
    }
    // 网格线：浅细线 + 每 5 格深色加粗（对齐图像转换图纸预览 major_every=5）
    const MAJOR = 5, majorW = CELL >= 16 ? 3 : 2;
    bctx.lineWidth = 1; bctx.strokeStyle = 'rgba(0,0,0,.08)';
    bctx.beginPath();
    for (let i = 0; i <= s; i++) {
      if (i % MAJOR === 0) continue;
      bctx.moveTo(i * CELL + .5, 0); bctx.lineTo(i * CELL + .5, dim);
      bctx.moveTo(0, i * CELL + .5); bctx.lineTo(dim, i * CELL + .5);
    }
    bctx.stroke();
    bctx.lineWidth = majorW; bctx.strokeStyle = 'rgba(90,90,90,.55)';
    bctx.beginPath();
    for (let i = 0; i <= s; i += MAJOR) {
      bctx.moveTo(i * CELL, 0); bctx.lineTo(i * CELL, dim);
      bctx.moveTo(0, i * CELL); bctx.lineTo(dim, i * CELL);
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
    bctx.restore();                        // 回到含边距坐标系
    // 横纵标号：左 + 上每 5 格印坐标数字（画在边距内）
    bctx.fillStyle = 'rgba(40,40,40,.85)';
    bctx.font = `600 ${Math.round(CELL * 0.5)}px sans-serif`;
    bctx.textAlign = 'center'; bctx.textBaseline = 'middle';
    for (let i = MAJOR; i <= s; i += MAJOR) {
      bctx.fillText(String(i), MARGIN + i * CELL - CELL / 2, MARGIN / 2);   // 顶部列号
      bctx.fillText(String(i), MARGIN / 2, MARGIN + i * CELL - CELL / 2);   // 左侧行号
    }
    // 画板内容变化 → 鹰眼实时刷新（缩略图源已切到 boardCanvas）
    if (viewer._updateMini) viewer._updateMini();
  }

  /* 同步画布 transform 到 Viewer（画板画布跟随缩放/平移） */
  function syncTransform() {
    boardCanvas.style.transform =
      `translate(${viewer.tx}px,${viewer.ty}px) scale(${viewer.scale})`;
  }
  /* 包装 viewer._apply：每次视图变换后同步画板画布 + 刷新鹰眼 */
  const _apply = viewer._apply.bind(viewer);
  viewer._apply = function () { _apply(); syncTransform(); };

  /* 鹰眼图像源：画板态返回 boardCanvas（含整板像素），缩略图实时对应画板内容。 */
  const _prevMiniSource = viewer._miniSource.bind(viewer);
  viewer._miniSource = function () {
    if (B.active && boardCanvas.style.display !== 'none' && boardCanvas.width > 1) {
      return { src: boardCanvas, w: boardCanvas.width, h: boardCanvas.height };
    }
    return _prevMiniSource();
  };

  /* 屏幕坐标 → 格坐标（仿 scribble._toImage，但以画板虚拟尺寸为界） */
  function toCell(e) {
    const rect = viewer.viewport.getBoundingClientRect();
    const px = (e.clientX - rect.left - viewer.tx) / viewer.scale - MARGIN;
    const py = (e.clientY - rect.top - viewer.ty) / viewer.scale - MARGIN;
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
    if (viewer._updateMini) viewer._updateMini();   // 切到画板 → 鹰眼切到 boardCanvas
  };
  /* 离开画板（切回图像转换时由 app.onViewSwitch 链触发） */
  window.onExitBoard = function () {
    boardCanvas.style.display = 'none';
    viewer._interactionLock = false;
    viewer.viewport.classList.remove('board-mode');
    B.baseDrag = null; B.drawing = false;
    // 清掉画板态写入的透明占位，交还画布给图像转换
    if (viewer.img.src === TRANSPARENT_PX) { viewer.img.removeAttribute('src'); viewer.img.classList.remove('has-img'); }
    // 恢复图像转换视图（重建五模式按钮 + 按记忆模式重设 img.src）
    if (window.restoreConversionView) window.restoreConversionView();
    if (viewer._updateMini) viewer._updateMini();
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
      B.baseOffX = (st.base_offx != null) ? st.base_offx : B.baseOffX;
      B.baseOffY = (st.base_offy != null) ? st.base_offy : B.baseOffY;
      B.baseScale = (st.base_scale != null) ? st.base_scale : 1;
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
    const dim = B.size * CELL + MARGIN;
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

  /* Bresenham 走线：(x0,y0)→(x1,y1) 沿途所有整格（含端点）。
     快速滑动时 mousemove 跨多格，用它在相邻采样点间插值，保证线条 8-连通连续。 */
  function lineCells(x0, y0, x1, y1) {
    const out = [];
    let dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx - dy, x = x0, y = y0;
    for (;;) {
      out.push([x, y]);
      if (x === x1 && y === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; x += sx; }
      if (e2 < dx) { err += dx; y += sy; }
    }
    return out;
  }

  /* ---- 底图调整状态机 ----
     进入：快照 → 画布复位+锁定缩放 → 工具栏切三态；期间中键拖底图、滚轮缩底图（等比例）。
     保存：持久化 scale+offx+offy；取消：回滚快照（不发请求）。 */
  function enterBaseAdjust() {
    if (!B.active || !B.base || !B.baseImg) return;
    B.baseAdjustSnap = { scale: B.baseScale, offx: B.baseOffX, offy: B.baseOffY };
    B.baseAdjust = true;
    B.drawing = false; B.stroke = null; B.rectStart = B.rectEnd = null;   // 退出进行中的绘制
    fitBoard();                            // 画布强制恢复默认缩放并居中
    viewer._boardAdjustLock = true;        // 锁定画布缩放/平移（兜底，拦截为主）
    buildToolbar(); syncToolbarState();
    vp.style.cursor = 'grab';
    render();
  }
  function cancelBaseAdjust() {
    if (B.baseAdjustSnap) {
      B.baseScale = B.baseAdjustSnap.scale;
      B.baseOffX = B.baseAdjustSnap.offx;
      B.baseOffY = B.baseAdjustSnap.offy;
    }
    B.baseAdjustSnap = null; B.baseDrag = null; B.baseAdjust = false;
    viewer._boardAdjustLock = false;
    buildToolbar(); syncToolbarState();
    vp.style.cursor = '';
    render();
  }
  async function saveBaseAdjust() {
    B.baseAdjustSnap = null; B.baseDrag = null; B.baseAdjust = false;
    viewer._boardAdjustLock = false;
    buildToolbar(); syncToolbarState();
    vp.style.cursor = '';
    render();
    try { await API.boardBaseOptions(null, null, B.baseOffX, B.baseOffY, B.baseScale); }
    catch (e) { window.fail('底图保存失败: ' + e.message); }
  }

  /* ---- 画布事件（捕获阶段，优先于 Viewer 平移） ---- */
  const vp = viewer.viewport;
  vp.addEventListener('mousedown', (e) => {
    if (!B.active || boardCanvas.style.display === 'none') return;
    // 调整底图模式：左键不涂色；中键拖底图（抢在 Viewer 平移前）
    if (B.baseAdjust) {
      if (!B.base || !B.baseImg) return;
      if (e.button === 1) {
        e.stopPropagation(); e.preventDefault();
        B.baseDrag = { sx: e.clientX, sy: e.clientY, ox: B.baseOffX, oy: B.baseOffY };
        vp.style.cursor = 'grabbing';
      } else if (e.button === 0) {
        e.stopPropagation(); e.preventDefault();   // 调整期左键封锁涂色，防误操作
      }
      return;
    }
    if (e.button !== 0) return;                // 中键留给 Viewer 平移
    e.stopPropagation(); e.preventDefault();
    const c = toCell(e); if (!c) return;
    if (B.tool === 'fill') { doFill(c[0], c[1]); return; }
    if (B.tool === 'rect') { B.rectStart = c; B.rectEnd = c; render(); return; }
    // pen / eraser：起笔（记 last 供 Bresenham 走线插值，防快速滑动断线）
    B.drawing = true;
    B.stroke = { code: (B.tool === 'eraser') ? null : B.color, cells: new Set(), last: c };
    stamp(c[0], c[1]);
    render();
  }, true);
  /* 滚轮缩放底图（捕获阶段抢在 Viewer 画布缩放前），仅调整底图模式生效。 */
  vp.addEventListener('wheel', (e) => {
    if (!B.active || !B.baseAdjust || !B.base || !B.baseImg) return;
    e.stopPropagation(); e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const ns = Math.min(40, Math.max(0.02, B.baseScale * factor));
    // 以光标为锚缩放底图（等比例）：保持光标下的图点不动
    const c = toCell(e);   // 光标所在画板格坐标（可能出界，仍可用作锚）
    const k = ns / B.baseScale;
    if (c) {
      B.baseOffX = c[0] - (c[0] - B.baseOffX) * k;
      B.baseOffY = c[1] - (c[1] - B.baseOffY) * k;
    }
    B.baseScale = ns;
    render();
  }, { capture: true, passive: false });
  window.addEventListener('mousemove', (e) => {
    if (!B.active) return;
    if (B.baseAdjust && B.baseDrag) {          // 中键拖动底图
      const dx = (e.clientX - B.baseDrag.sx) / viewer.scale / CELL;
      const dy = (e.clientY - B.baseDrag.sy) / viewer.scale / CELL;
      B.baseOffX = B.baseDrag.ox + dx; B.baseOffY = B.baseDrag.oy + dy;
      render();
      return;
    }
    if (B.baseAdjust) return;                  // 调整期不进入任何绘制分支
    if (B.rectStart && !B.drawing) {           // 框选拖动
      const c = toCell(e); if (c) { B.rectEnd = c; render(); }
      return;
    }
    if (!B.drawing || !B.stroke) return;
    const c = toCell(e); if (!c) return;
    // Bresenham 走线：last→当前沿途整格全 stamp，快速滑动不断线（自然满足 8-连通）
    const last = B.stroke.last || c;
    lineCells(last[0], last[1], c[0], c[1]).forEach(([x, y]) => stamp(x, y));
    B.stroke.last = c;
    render();
  });
  window.addEventListener('mouseup', async (e) => {
    if (!B.active) return;
    if (B.baseAdjust) {                        // 结束底图拖动（持久化由保存按钮统一提交）
      if (B.baseDrag) { B.baseDrag = null; vp.style.cursor = 'grab'; }
      return;
    }
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
        <div class="num-row"><label>规格</label><select class="sel" id="boardSize">${sizeOpts}</select></div>
        <div class="num-row"><label>拼豆品牌</label><select class="sel" id="boardBrand">${brandOpts}</select></div>
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
        <div class="slider-row"><label>笔触粗细</label>
          <input type="range" id="boardBrush" min="1" max="3" step="1" value="${B.brush}">
          <output id="boardBrushOut">${B.brush}</output>
        </div>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3a9 9 0 1 0 0 18c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.4A3.6 3.6 0 0 0 21 10.8C20.6 6.4 16.7 3 12 3z"/><circle cx="7.5" cy="11.5" r="1.2"/><circle cx="11" cy="7.5" r="1.2"/><circle cx="15.5" cy="8.5" r="1.2"/></svg>色板</h3>
        <div id="boardPalette" class="chip-row" style="max-height:280px;overflow-y:auto;gap:6px"></div>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5-6 6"/></svg>参考底图</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-ghost" id="boardBaseLoadBtn" style="flex:1">上传底图</button>
          <button class="btn btn-ghost" id="boardBaseClearBtn">清除</button>
        </div>
        <input type="file" id="boardBaseFile" accept="image/*" style="display:none">
        ${B.baseAdjust
          ? `<div style="display:flex;gap:6px;margin-top:6px">
              <button class="btn btn-ghost" id="boardBaseCancelBtn" style="flex:1">取消</button>
              <button class="btn btn-primary" id="boardBaseSaveBtn" style="flex:1">保存调整</button>
            </div>
            <p class="hint">调整中：滚轮缩放底图 · 中键拖动平移底图 · 画板缩放已锁定。</p>`
          : `<button class="btn btn-ghost" id="boardBaseAdjustBtn" style="width:100%;margin-top:6px" ${B.base ? '' : 'disabled'}>调整底图</button>`}
        <div class="slider-row"><label>不透明度</label>
          <input type="range" id="boardBaseOp" min="0.1" max="1" step="0.05" value="${B.baseOpacity}">
          <output id="boardBaseOpOut">${Math.round(B.baseOpacity * 100)}%</output></div>
        <p class="hint">上传整图等比例铺满画板；点「调整底图」后滚轮缩放、中键拖动，保存生效、取消还原。</p>
      </div>

      <div class="panel-card glass">
        <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></svg>导出图纸</h3>
        <div class="num-row"><label>风格</label>
          <select class="sel" id="boardExpStyle">
            <option value="real" ${B.style === 'real' ? 'selected' : ''}>真实风</option>
            <option value="square" ${B.style === 'square' ? 'selected' : ''}>图纸风</option>
          </select></div>
        <div class="num-row" style="flex-wrap:nowrap"><label>文件名</label>
          <input type="text" id="boardExpName" value="board" style="flex:1;min-width:0;padding:7px 10px;border-radius:12px;border:1px solid var(--color-border);background:var(--color-surface-strong);color:var(--color-foreground);font-family:var(--font-body);font-size:13px"></div>
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
    // 下拉走 gsel 玻璃拟态（与图像转换一致）
    ['boardSize', 'boardBrand', 'boardExpStyle'].forEach(id => {
      const el = $(id); if (el && window.Dropdown) window.Dropdown.enhance(el);
    });
    // 滑块走可编辑虚线框（与图像转换一致）
    if (window.bindEditable) {
      window.bindEditable('boardBrush', 'boardBrushOut', { fmt: v => String(v), onChange: v => { B.brush = v; } });
      window.bindEditable('boardBaseOp', 'boardBaseOpOut', {
        fmt: v => Math.round(parseFloat(v) * 100) + '%',
        parse: t => parseFloat(t) > 1 ? parseFloat(t) / 100 : parseFloat(t),   // 允许输 35 或 0.35
        onChange: v => { B.baseOpacity = v; render(); API.boardBaseOptions(true, v); },
      });
    }
    syncToolbarState();
  }

  /* 与 BOM 一致的实色圆徽章 chip（色号印在徽章上，按亮度选字色）。
     徽章宽度按本品牌最长色号动态定宽，保证同一品牌内各色块尺寸一致。 */
  function beadChipHtml(c, sel, badgeW) {
    const lum = parseInt(c.hex.slice(1, 3), 16) * .3 + parseInt(c.hex.slice(3, 5), 16) * .59 + parseInt(c.hex.slice(5, 7), 16) * .11;
    const fg = lum > 140 ? '#3b0a1c' : '#fff';
    return `<button class="chip bead-chip${sel ? ' on' : ''}" data-code="${c.code}" title="${c.name} (${c.code})"
      style="display:inline-flex;align-items:center;padding:3px;border-radius:999px;${sel ? '' : 'background:var(--color-surface);'}">
      <span style="width:${badgeW}px;height:26px;padding:0;border-radius:999px;background:${c.hex};color:${fg};
        display:inline-grid;place-items:center;font-size:10px;font-weight:800;white-space:nowrap">${c.code}</span>
    </button>`;
  }

  function buildPalette() {
    const host = $('boardPalette'); if (!host) return;
    // 同一品牌内统一徽章宽度（容纳最长色号），修复 MARD 2/3 字符混排导致的尺寸不一
    const maxLen = Math.max(2, ...B.palette.map(c => c.code.length));
    const badgeW = 10 + maxLen * 7;
    host.innerHTML = B.palette.map(c => beadChipHtml(c, c.code === B.color, badgeW)).join('');
    host.querySelectorAll('.bead-chip').forEach(b => b.addEventListener('click', () => {
      B.color = b.dataset.code;
      host.querySelectorAll('.bead-chip').forEach(x => x.classList.toggle('on', x === b));
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
      const ok = await window.uiConfirm('切换到 ' + sz + '×' + sz + ' 将清空当前画板，确定？', { title: '切换规格', danger: true });
      if (!ok) {
        if ($('boardSize')._gsel) $('boardSize')._gsel.setValue(B.size, false); else $('boardSize').value = B.size; return;
      }
      await API.boardNew(sz, B.brand); B.baseImg = null; await refresh(true);
    });
    $('boardBrand').addEventListener('change', async () => {
      const ok = await window.uiConfirm('切换拼豆品牌将清空当前画板（色号体系不同），确定？', { title: '切换品牌', danger: true });
      if (!ok) {
        if ($('boardBrand')._gsel) $('boardBrand')._gsel.setValue(B.brand, false); else $('boardBrand').value = B.brand; return;
      }
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
      const ok = await window.uiConfirm('清空整块画板？（可撤销）', { title: '清空画板', danger: true });
      if (!ok) return;
      await API.boardClear(); await refresh(false);
    });
    // 底图（透明度滑块已由 bindEditable 接管，见 buildToolbar）
    $('boardBaseLoadBtn').addEventListener('click', () => $('boardBaseFile').click());
    $('boardBaseFile').addEventListener('change', async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try {
        busy.start('导入底图…');
        const r = await API.boardBaseLoad(f);   // 后端整图存底图 + 返回居中偏移
        const im = new Image();
        im.onload = () => {
          B.base = true; B.baseVisible = true;
          B.baseImg = im;
          B.baseScale = (r.scale != null) ? r.scale : 1;
          B.baseOffX = r.offx; B.baseOffY = r.offy;
          render(); buildToolbar(); syncToolbarState();
          busy.done('底图已铺满画板（点「调整底图」可缩放/移动）');
        };
        im.src = URL.createObjectURL(f);
        e.target.value = '';
      } catch (err) { window.fail('导入底图失败: ' + err.message); }
    });
    // 底图调整三态按钮（buildToolbar 按 B.baseAdjust 渲染其中一套）
    if ($('boardBaseAdjustBtn')) $('boardBaseAdjustBtn').addEventListener('click', enterBaseAdjust);
    if ($('boardBaseCancelBtn')) $('boardBaseCancelBtn').addEventListener('click', cancelBaseAdjust);
    if ($('boardBaseSaveBtn')) $('boardBaseSaveBtn').addEventListener('click', saveBaseAdjust);
    $('boardBaseClearBtn').addEventListener('click', async () => {
      await API.boardBaseClear();
      B.base = false; B.baseImg = null; B.baseAdjust = false; B.baseDrag = null;
      B.baseAdjustSnap = null; viewer._boardAdjustLock = false;
      B.baseOffX = 0; B.baseOffY = 0; B.baseScale = 1;
      render(); buildToolbar();
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
    // 徽章宽度按最长色号统一，与色板徽章同规范
    const bomMaxLen = Math.max(2, ...items.map(([code]) => code.length));
    const bomBadgeW = 10 + bomMaxLen * 7;
    list.innerHTML = items.map(([code, info]) => `
      <span class="chip" style="display:inline-flex;align-items:center;gap:6px;padding:4px 12px 4px 4px">
        <span style="width:${bomBadgeW}px;height:22px;padding:0;border-radius:999px;background:${info.hex};
          color:${(parseInt(info.hex.slice(1, 3), 16) * .3 + parseInt(info.hex.slice(3, 5), 16) * .59 + parseInt(info.hex.slice(5, 7), 16) * .11) > 140 ? '#3b0a1c' : '#fff'};
          display:inline-grid;place-items:center;font-size:9.5px;font-weight:800;white-space:nowrap">${code}</span>
        <span>×${info.count}</span></span>`).join('') +
      `<p class="hint" style="width:100%;margin-top:6px">共 ${bom.total_beads} 豆 · ${items.length} 种颜色</p>`;
  }

  const BRAND_LABELS = {
    mard: 'MARD', perler: 'Perler', hama: 'Hama',
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
