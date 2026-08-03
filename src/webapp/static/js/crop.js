/* 图像处理 · 裁剪模块：框选要保留的区域，可拖动边框/四角/整体微调，应用后裁剪结果成为新「原图」。
   复用 scribble 层的 _toImage/_toScreen 坐标换算与 overlay 画布；交互锁让位 viewer 平移。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const viewer = window.viewer;
  const scribble = window.scribble;

  let cropMode = false;          // 是否处于裁剪模式
  let box = null;                // {x1,y1,x2,y2} 图像坐标（未排序）
  let drag = null;               // 当前拖拽：{kind, sx, sy, box0}
  // kind: 'new' 新建 | 'move' 整体移动 | 'l'/'r'/'t'/'b' 边 | 'tl'/'tr'/'bl'/'br' 角

  const HIT = 14;                // 手柄命中半径（屏幕像素）
  const MIN = 8;                 // 最小裁剪边长（图像像素）

  /* ---- 工具 ---- */
  const norm = (b) => b ? {
    x1: Math.min(b.x1, b.x2), y1: Math.min(b.y1, b.y2),
    x2: Math.max(b.x1, b.x2), y2: Math.max(b.y1, b.y2),
  } : null;
  const scr = (p) => scribble._toScreen(p);
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

  function imgSize() {
    return [viewer.img.naturalWidth || 0, viewer.img.naturalHeight || 0];
  }

  /* 命中检测：返回 'tl/tr/bl/br/l/r/t/b/move/new'（screen 坐标系判断） */
  function hitKind(e, b) {
    const n = norm(b); if (!n) return 'new';
    const p = [e.clientX - viewer.viewport.getBoundingClientRect().left,
               e.clientY - viewer.viewport.getBoundingClientRect().top];
    const c1 = scr([n.x1, n.y1]), c2 = scr([n.x2, n.y2]);
    const [sx1, sy1] = c1, [sx2, sy2] = c2;
    const mx = (sx1 + sx2) / 2, my = (sy1 + sy2) / 2;
    // 四角优先
    if (dist(p, [sx1, sy1]) <= HIT) return 'tl';
    if (dist(p, [sx2, sy1]) <= HIT) return 'tr';
    if (dist(p, [sx1, sy2]) <= HIT) return 'bl';
    if (dist(p, [sx2, sy2]) <= HIT) return 'br';
    // 四边中心
    if (dist(p, [mx, sy1]) <= HIT) return 't';
    if (dist(p, [mx, sy2]) <= HIT) return 'b';
    if (dist(p, [sx1, my]) <= HIT) return 'l';
    if (dist(p, [sx2, my]) <= HIT) return 'r';
    // 框线附近吸附：点在某条边附近（横坐标在框内、纵向靠近边）也算拖该边
    const inX = p[0] >= sx1 - HIT && p[0] <= sx2 + HIT;
    const inY = p[1] >= sy1 - HIT && p[1] <= sy2 + HIT;
    if (inX && Math.abs(p[1] - sy1) <= HIT) return 't';
    if (inX && Math.abs(p[1] - sy2) <= HIT) return 'b';
    if (inY && Math.abs(p[0] - sx1) <= HIT) return 'l';
    if (inY && Math.abs(p[0] - sx2) <= HIT) return 'r';
    // 框内=移动，框外=新建（已有框时调用方会忽略 'new'）
    if (p[0] >= sx1 && p[0] <= sx2 && p[1] >= sy1 && p[1] <= sy2) return 'move';
    return 'new';
  }

  /* ---- 进入 / 退出 ---- */
  function enter() {
    if (!imgSize()[0]) { busy.set('请先加载图像'); return; }
    cropMode = true;
    box = null; drag = null;
    viewer._interactionLock = true;
    $('cropBtn').style.display = 'none';
    $('cropActions').style.display = 'flex';
    busy.set('在图上拖拽框出要保留的区域，可拖动边框微调');
    scribble._redraw();
  }
  function exit(silent) {
    cropMode = false; box = null; drag = null;
    viewer._interactionLock = false;
    $('cropBtn').style.display = '';
    $('cropActions').style.display = 'none';
    scribble._redraw();
    if (!silent) busy.set('已退出裁剪');
  }
  window.exitCropInteraction = () => { if (cropMode) exit(true); };

  /* 视图切换/涂鸦收尾时同步退出裁剪：串接到 exitScribbleInteraction 链 */
  const _prevExit = window.exitScribbleInteraction;
  window.exitScribbleInteraction = () => { if (cropMode) exit(true); if (_prevExit) _prevExit(); };

  /* ---- 事件 ---- */
  const vp = viewer.viewport;
  vp.addEventListener('mousedown', (e) => {
    if (!cropMode) return;
    if (e.button !== 0) return;          // 只响应左键；中键留给 viewer 平移视图
    e.stopPropagation(); e.preventDefault();
    const p = scribble._toImage(e);
    if (!box) {
      // 尚无框：首次拖拽新建框
      box = { x1: p[0], y1: p[1], x2: p[0], y2: p[1] };
      drag = { kind: 'new', sx: p[0], sy: p[1] };
    } else {
      const kind = hitKind(e, box);
      // 已有框：点框外不再重新框选，只能拖手柄/拖框内调整（带吸附容错）
      if (kind === 'new') return;
      drag = { kind, sx: p[0], sy: p[1], box0: { ...norm(box) } };
    }
    scribble._redraw();
  }, true);

  window.addEventListener('mousemove', (e) => {
    if (!cropMode || !drag) return;
    const p = scribble._toImage(e);
    const [iw, ih] = imgSize();
    const clamp = (v, m) => Math.max(0, Math.min(m, v));
    if (drag.kind === 'new') {
      box.x2 = p[0]; box.y2 = p[1];
    } else {
      const b = { ...drag.box0 };
      const dx = p[0] - drag.sx, dy = p[1] - drag.sy;
      const k = drag.kind;
      if (k === 'move') {
        const w = b.x2 - b.x1, h = b.y2 - b.y1;
        let nx1 = clamp(b.x1 + dx, iw), ny1 = clamp(b.y1 + dy, ih);
        nx1 = Math.max(0, Math.min(iw - w, nx1));
        ny1 = Math.max(0, Math.min(ih - h, ny1));
        b.x1 = nx1; b.x2 = nx1 + w; b.y1 = ny1; b.y2 = ny1 + h;
      } else {
        if (k.includes('l')) b.x1 = clamp(b.x1 + dx, iw);
        if (k.includes('r')) b.x2 = clamp(b.x2 + dx, iw);
        if (k.includes('t')) b.y1 = clamp(b.y1 + dy, ih);
        if (k.includes('b')) b.y2 = clamp(b.y2 + dy, ih);
      }
      box = b;
    }
    scribble._redraw();
  });

  window.addEventListener('mouseup', () => {
    if (!cropMode || !drag) return;
    const n = norm(box);
    // 过滤过小框
    if (n && (n.x2 - n.x1 < MIN || n.y2 - n.y1 < MIN)) { box = null; }
    else if (n) box = n;
    drag = null;
    scribble._redraw();
  });

  /* ---- 叠画：外部半透明遮罩 + 裁剪框 + 8 手柄 ---- */
  function draw(ctx) {
    if (!cropMode) return;
    const n = norm(box);
    const [iw, ih] = imgSize();
    const tl = scr([0, 0]), br = scr([iw, ih]);
    const ix = tl[0], iy = tl[1], iwS = br[0] - tl[0], ihS = br[1] - tl[1];

    // 遮罩：整图半透明，框内掏空（中心清晰）
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,.42)';
    ctx.beginPath();
    ctx.rect(ix, iy, iwS, ihS);
    if (n) {
      const c1 = scr([n.x1, n.y1]), c2 = scr([n.x2, n.y2]);
      ctx.rect(c1[0], c1[1], c2[0] - c1[0], c2[1] - c1[1]);
    }
    ctx.fill('evenodd');
    ctx.restore();

    if (!n) return;
    const c1 = scr([n.x1, n.y1]), c2 = scr([n.x2, n.y2]);
    const [sx1, sy1] = c1, [sx2, sy2] = c2;
    const mx = (sx1 + sx2) / 2, my = (sy1 + sy2) / 2;

    // 框边（白描边 + 蓝主线，深浅主题都清晰）
    ctx.save();
    ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.9)';
    ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);
    ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(37,99,235,.95)';
    ctx.setLineDash([7, 5]);
    ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);
    ctx.setLineDash([]);

    // 8 手柄
    const pts = [
      [sx1, sy1], [mx, sy1], [sx2, sy1],
      [sx1, my], [sx2, my],
      [sx1, sy2], [mx, sy2], [sx2, sy2],
    ];
    for (const [hx, hy] of pts) {
      ctx.beginPath();
      ctx.fillStyle = '#fff';
      ctx.strokeStyle = 'rgba(37,99,235,.95)';
      ctx.lineWidth = 1.6;
      ctx.arc(hx, hy, 5, 0, 7);
      ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }

  // 挂到 scribble 的 overlay 链（与分割框选共存：串接旧钩子）
  const _prev = scribble.onOverlay;
  scribble.onOverlay = (ctx) => { if (_prev) _prev(ctx); draw(ctx); };

  /* ---- 按钮接线 ---- */
  $('cropBtn').addEventListener('click', () => {
    if (window.exitScribbleInteraction) window.exitScribbleInteraction();
    enter();
  });
  $('cropCancelBtn').addEventListener('click', () => exit(false));
  $('cropApplyBtn').addEventListener('click', async () => {
    const n = norm(box);
    if (!n || n.x2 - n.x1 < MIN || n.y2 - n.y1 < MIN) { busy.set('请先在图上框选要保留的区域'); return; }
    try {
      busy.start('裁剪中…');
      const url = await API.basic({ crop: [Math.round(n.x1), Math.round(n.y1), Math.round(n.x2), Math.round(n.y2)] });
      exit(true);
      viewer.setImage(url);
      await refreshStatus();
      busy.done('已裁剪，结果成为新「原图」');
      if (window.onImageLoaded) window.onImageLoaded();
    } catch (err) { window.fail('裁剪失败: ' + err.message); }
  });
})();
