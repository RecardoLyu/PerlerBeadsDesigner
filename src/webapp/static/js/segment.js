/* 图像处理 · 分割模块：迭代 GrabCut 三步流程 + 自动分割 + 形态学 + 显示切换联动。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const viewer = window.viewer;
  const canvas = document.getElementById('canvas');
  const scribble = new ScribbleLayer(canvas, viewer);
  window.scribble = scribble;
  window.addEventListener('resize', () => scribble.resize());

  /* 视图重绘时同步涂鸦层（缩放/平移后重画） */
  const _apply = viewer._apply.bind(viewer);
  viewer._apply = function () { _apply(); scribble._redraw(); };

  /* ---- 注入分割卡片 ---- */
  $('segCards').innerHTML = `
    <div class="panel-card glass">
      <h3 style="cursor:help" data-tip="两步：① 初始分割——框选前景大致区域后点「初始分割」；② 迭代分割——用红(前景)/绿(背景)涂抹误分区域后点「迭代分割」精修。"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>迭代 GrabCut</h3>
      <div class="chip-row">
        <span class="chip on" data-step="rect">初始分割</span>
        <span class="chip" data-step="mark">迭代分割</span>
      </div>
      <div id="rectRow" style="margin-top:8px">
        <div class="num-row"><label>形状</label>
          <select class="sel" id="igcShape">
            <option value="rect" data-tip="拖拽框出矩形前景区域">矩形 ▭</option>
            <option value="ellipse" data-tip="拖拽框出椭圆前景区域，按住 Shift 为正圆">椭圆 ⬭</option>
            <option value="freehand" data-tip="按住左键自由勾勒前景轮廓，松手闭合">自由曲线 ✎</option>
          </select>
        </div>
      </div>
      <div id="markRow" style="margin-top:8px;display:none">
        <div class="slider-row"><label>笔触粗细</label><input type="range" id="brushSize" min="4" max="40" step="2" value="12" data-tip="涂抹笔刷的直径（像素），用于精修分割边界。"><output id="brushSizeOut">12</output></div>
        <div class="chip-row">
          <span class="chip on" data-brush="fg" data-tip="把误分成背景的区域涂回前景"><i class="brush-dot fg"></i>前景</span>
          <span class="chip" data-brush="bg" data-tip="把误分成前景的区域涂回背景"><i class="brush-dot bg"></i>背景</span>
          <span class="chip" id="clearStroke" data-tip="清除所有未提交的涂抹">清除涂抹</span>
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px">
        <button class="btn btn-primary" id="segActionBtn" style="flex:1" data-tip="点一下进入框选，在图上拖出前景范围后按钮变为「进行分割」，再点执行首次分割">开始框选</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn btn-ghost" id="applySegBtn" style="flex:1" data-tip="保留原图与 Mask，生成图纸仅用前景、背景不计入 BOM">应用分割结果</button>
      </div>
    </div>

    <div class="panel-card glass">
      <h3 style="cursor:help" data-tip="一键自动分割：从四种算法（GrabCut矩形/分水岭/Otsu/SLIC）中选一种，点「执行分割」自动抠出前景，无需手动框选或涂抹。执行后可在「Mask / 原图+高亮」查看，再点「应用分割结果」把 Mask 保留为独立层（生成图纸仅用前景、背景不计入 BOM）。"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>自动分割</h3>
      <div class="num-row"><label>方法</label>
        <select class="sel" id="segMethod" data-tip="自动分割算法选择">
          <option value="grabcut_rect" data-tip="以矩形框选初始化做迭代分割，适合边界清晰的主体">GrabCut矩形</option>
          <option value="watershed" selected data-tip="按亮度梯度漫水分割，适合前景居中、对比明显的图">分水岭</option>
          <option value="otsu" data-tip="自动阈值二值化，适合明暗反差大的图">Otsu</option>
          <option value="slic" data-tip="超像素聚类分割，适合颜色块分明的图">SLIC</option>
        </select>
      </div>
      <div class="slider-row" id="wsRow"><label>前景比例</label><input type="range" id="fgRatio" min="0.1" max="0.9" step="0.05" value="0.4" data-tip="分水岭：估计前景占图像的比例，用于定位种子点。前景越大调越大。"><output id="fgRatioOut">0.40</output></div>
      <div class="slider-row" id="slicRow" style="display:none"><label>超像素数</label><input type="range" id="nSeg" min="50" max="400" step="10" value="150" data-tip="SLIC：把图像聚成多少个超像素块，越多越精细、越慢。"><output id="nSegOut">150</output></div>
      <button class="btn btn-primary" id="autoSegBtn" style="width:100%;margin-top:8px" data-tip="按所选方法自动分割出前景 Mask">执行分割</button>
      <button class="btn btn-ghost" id="autoApplyBtn" style="width:100%;margin-top:6px" data-tip="保留原图与 Mask，生成图纸仅用前景、背景不计入 BOM">应用分割结果</button>
    </div>

    <div class="panel-card glass">
      <h3 style="cursor:help" data-tip="对已有 Mask 做形态学修整：开/闭运算去噪补洞、腐蚀/膨胀收放边界；可调核大小与结构元素形状，每次在上一步结果上迭代，最多可撤销/重做 3 步。"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17M3.5 12h17"/></svg>形态学</h3>
      <div class="num-row"><label>操作</label>
        <select class="sel" id="morphOp" data-tip="形态学操作选择">
          <option value="open" data-tip="先腐蚀后膨胀：去除前景小噪点、断开细小粘连">开运算</option>
          <option value="close" data-tip="先膨胀后腐蚀：填补前景小洞、连接邻近区域">闭运算</option>
          <option value="erode" data-tip="收缩前景边界，去掉毛边细刺">腐蚀</option>
          <option value="dilate" data-tip="扩张前景边界，放大前景区域">膨胀</option>
        </select>
      </div>
      <div class="slider-row"><label>核大小</label><input type="range" id="morphK" min="1" max="21" step="2" value="5" data-tip="结构元素尺寸（像素），越大作用越强、边缘越平滑。"><output id="morphKOut">5</output></div>
      <div class="num-row"><label>结构元素</label>
        <select class="sel" id="morphShape" data-tip="结构元素形状，决定膨胀/腐蚀的方向性。">
          <option value="ellipse" selected data-tip="各向均匀，边缘平滑圆润，最常用">椭圆 ●</option>
          <option value="rect" data-tip="各向均匀但边角方正，作用更强">矩形 ■</option>
          <option value="cross" data-tip="只沿横竖方向作用，保留斜边">十字 ┼</option>
          <option value="vline" data-tip="只沿垂直方向作用">垂直线 │</option>
          <option value="hline" data-tip="只沿水平方向作用">水平线 ─</option>
          <option value="diag1" data-tip="只沿主对角线 \ 方向作用">斜线 \</option>
          <option value="diag2" data-tip="只沿副对角线 / 方向作用">斜线 /</option>
          <option value="diamond" data-tip="各向均匀但比椭圆略方，介于椭圆与矩形之间">菱形 ◆</option>
        </select>
        <span class="kernel-preview" id="kernelPreview" aria-hidden="true"></span>
      </div>
      <button class="btn btn-primary" id="morphApplyBtn" style="width:100%;margin-top:8px" data-tip="按所选操作/核/形状对当前 Mask 做形态学处理，每次都在上一步结果上迭代">应用形态学</button>
      <div style="display:flex;gap:8px;margin-top:6px">
        <button class="btn btn-ghost" id="morphUndoBtn" style="flex:1" data-tip="撤销上一步形态学，最多保留 3 步">↺ 撤销</button>
        <button class="btn btn-ghost" id="morphRedoBtn" style="flex:1" data-tip="重做已撤销的形态学，最多保留 3 步">↻ 重做</button>
      </div>
    </div>
  `;

  /* ---- 通用 chip 单选 ---- */
  function singleSelect(containerId, attr, onPick) {
    const c = $(containerId);
    c.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip'); if (!chip) return;
      if (!chip.dataset[attr]) return;
      [...c.querySelectorAll('.chip')].forEach(x => x.classList.remove('on'));
      chip.classList.add('on');
      onPick(chip.dataset[attr]);
    });
  }
  window.bindEditable('brushSize', 'brushSizeOut', { fmt: v => v, onChange: v => { scribble.brushSize = v; updateBrushDots(v); } });
  window.bindEditable('fgRatio', 'fgRatioOut', { fmt: v => (+v).toFixed(2) });
  window.bindEditable('nSeg', 'nSegOut', { fmt: v => v });
  window.bindEditable('morphK', 'morphKOut', { fmt: v => v });

  /* 涂抹前景/背景圆点：真实大小预览（对齐移动端 10~26px 固定映射） */
  function updateBrushDots(v) {
    const d = Math.max(10, Math.min(26, 8 + (v / 40) * 18));
    document.querySelectorAll('#markRow .brush-dot').forEach(el => {
      el.style.width = d + 'px'; el.style.height = d + 'px';
    });
  }
  updateBrushDots(+$('brushSize').value);

  function setInteractionLock(on) { viewer._interactionLock = on; }

  /* 合并按钮的框选态文案管理（rect 步骤下 segActionBtn 复用为 框选/分割 一体按钮） */
  function setActionLabel(t) { const b = $('segActionBtn'); if (b) b.textContent = t; }
  function _hasShape() {
    const s = curShape();
    return s === 'freehand' ? shapePts.length >= 3 : !!rectBox;
  }

  /* ---- 统一收尾：退出一切框选/涂抹交互，防止泄露为可涂鸦 ---- */
  function exitInteraction() {
    rectMode = false; rectDrawing = false; shapeStart = null; shapePts = [];
    rectBox = null;
    scribble.enable(false);
    scribble.clear();
    setInteractionLock(false);
    scribble._redraw();   // 清掉 onOverlay 残留的圈选框
    setActionLabel('开始框选');
  }
  window.exitScribbleInteraction = exitInteraction;

  /* ---- 步骤切换（初始分割 / 迭代分割），同步动作按钮文案与提示 ---- */
  let rectMode = false;
  function syncActionBtn(step) {
    const b = $('segActionBtn'); if (!b) return;
    if (step === 'mark') {
      b.textContent = '迭代分割';
      b.dataset.tip = '迭代分割：根据涂抹的红(前景)/绿(背景)标记迭代精修分割';
    } else {
      b.textContent = '开始框选';
      b.dataset.tip = '点一下进入框选，在图上拖出前景范围后按钮变为「进行分割」，再点执行首次分割';
    }
  }
  singleSelect('segCards', 'step', (step) => {
    $('rectRow').style.display = step === 'rect' ? '' : 'none';
    $('markRow').style.display = step === 'mark' ? '' : 'none';
    syncActionBtn(step);
    if (step === 'mark') {
      // 进入涂抹：清掉框选态 + 退裁剪（交互防护）
      window.exitCropInteraction?.();
      rectMode = false; rectDrawing = false; shapeStart = null; shapePts = [];
      scribble.enable(true);
      setInteractionLock(true);
    } else {
      // 回到初始分割或切走：退出涂抹
      scribble.enable(false);
      scribble.clear();
      setInteractionLock(step === 'rect' && rectMode);
      if (step !== 'rect') { exitInteraction(); }
    }
  });
  // 让 segCards 内 step chips 也单选
  $('segCards').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip[data-step]'); if (!chip) return;
    [...$('segCards').querySelectorAll('.chip[data-step]')].forEach(x => x.classList.remove('on'));
    chip.classList.add('on');
  });

  /* 笔触切换 */
  $('markRow').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    if (chip.dataset.brush) {
      [...$('markRow').querySelectorAll('[data-brush]')].forEach(x => x.classList.remove('on'));
      chip.classList.add('on');
      scribble.brush = chip.dataset.brush;
    } else if (chip.id === 'clearStroke') {
      scribble.clear();
    }
  });

  /* ---- 前景框选（矩形/椭圆/自由曲线；松手即定，叠画不被涂鸦重绘清掉） ---- */
  let rectBox = null;      // {x1,y1,x2,y2} 图像坐标（未排序），矩形/椭圆用
  let rectDrawing = false;
  let shapeStart = null;   // 拖拽起点（图像坐标）
  let shapePts = [];       // 自由曲线轨迹（图像坐标）
  const curShape = () => ($('igcShape') ? $('igcShape').value : 'rect');

  // 切换形状时清掉已画，避免残留
  if ($('igcShape')) $('igcShape').addEventListener('change', () => {
    rectBox = null; rectDrawing = false; shapeStart = null; shapePts = [];
    scribble._redraw();
    setActionLabel(rectMode ? '在图上拖拽框选…（再点取消）' : '开始框选');
  });

  const vp = viewer.viewport;
  vp.addEventListener('mousedown', (e) => {
    if (!rectMode) return;
    e.stopPropagation(); e.preventDefault();
    const p = scribble._toImage(e);
    const shape = curShape();
    if (shape === 'freehand') { shapePts = [p]; }
    else { rectBox = { x1: p[0], y1: p[1], x2: p[0], y2: p[1] }; shapeStart = p; }
    rectDrawing = true;
    scribble._redraw();
  }, true);
  window.addEventListener('mousemove', (e) => {
    if (!rectMode || !rectDrawing) return;
    const p = scribble._toImage(e);
    if (curShape() === 'freehand') { shapePts.push(p); }
    else if (rectBox) { rectBox.x2 = p[0]; rectBox.y2 = p[1]; }
    scribble._redraw();
  });
  window.addEventListener('mouseup', () => {
    if (!rectMode || !rectDrawing) return;
    rectDrawing = false;   // 松手即结束框选，固定形状
    scribble._redraw();
    setActionLabel('进行分割');
    busy.set('区域已选，点「进行分割」执行首次分割');
  });

  // 形状叠画：挂到涂鸦层，每次重绘后绘制，不会被 _clearCanvas 清掉
  scribble.onOverlay = (ctx) => {
    const shape = curShape();
    ctx.save();
    ctx.strokeStyle = 'rgba(37,99,235,.95)'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    if (shape === 'freehand') {
      if (shapePts.length > 1) {
        ctx.beginPath();
        shapePts.forEach((p, i) => {
          const [x, y] = scribble._toScreen(p);
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.stroke();
      }
    } else if (rectBox) {
      const ax = Math.min(rectBox.x1, rectBox.x2), ay = Math.min(rectBox.y1, rectBox.y2);
      const bx = Math.max(rectBox.x1, rectBox.x2), by = Math.max(rectBox.y1, rectBox.y2);
      const [sx1, sy1] = scribble._toScreen([ax, ay]);
      const [sx2, sy2] = scribble._toScreen([bx, by]);
      if (shape === 'ellipse') {
        ctx.beginPath();
        ctx.ellipse((sx1 + sx2) / 2, (sy1 + sy2) / 2, Math.abs(sx2 - sx1) / 2, Math.abs(sy2 - sy1) / 2, 0, 0, 7);
        ctx.stroke();
      } else {
        ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);
      }
    }
    ctx.setLineDash([]);
    ctx.restore();
  };

  /* ---- 显示切换联动（高亮模式） ---- */
  const vt = $('viewToggle');
  /* 图纸预览：有图纸则渲染标准图纸，无图纸则提示并回退到原图高亮 */
  async function _showChart(btn) {
    const s = await API.status();
    if (!s.has_pattern) {
      busy.set('尚未生成图纸，请先到「图纸生成」视图点「生成图纸」');
      [...vt.children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'original'));
      viewer.setImage(API.currentImageUrl() + '?t=' + Date.now());
      return;
    }
    viewer.setImage(await API.patternChart(window._chartReq()));
    requestAnimationFrame(() => requestAnimationFrame(() => viewer.fit()));
  }
  async function showMode(mode, btn) {
    try {
      busy.start('切换显示…');
      if (mode === 'original') viewer.setImage(API.currentImageUrl() + '?t=' + Date.now());
      else if (mode === 'mask') viewer.setImage(API.maskUrl() + '?t=' + Date.now());
      else if (mode === 'highlight') viewer.setImage(API.overlayUrl() + '?t=' + Date.now());
      else if (mode === 'applied') viewer.setImage(API.appliedUrl() + '?t=' + Date.now());
      else if (mode === 'chart') { await _showChart(btn); busy.done('就绪'); return; }
      busy.done('就绪');
    } catch (err) { window.fail('无内容: ' + err.message); }
  }
  // 覆盖 shell 里的默认切换（加上高亮支持）
  vt.replaceWith(vt.cloneNode(true));
  $('viewToggle').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    [...$('viewToggle').children].forEach(x => x.classList.remove('on')); b.classList.add('on');
    showMode(b.dataset.mode, b);
  });
  /* 供 app.js 在生成图纸 / 切到图纸视图后，把「图纸预览」设为当前选中 */
  window.setChartViewActive = () => {
    [...$('viewToggle').children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'chart'));
  };

  /* ---- 一体动作按钮：
     rect 步骤 = 框选/分割 一体（开始框选 → 框完「进行分割」→ 执行）；
     mark 步骤 = 迭代分割（涂抹）。 ---- */
  $('segActionBtn').addEventListener('click', async () => {
    const step = document.querySelector('#segCards .chip[data-step].on')?.dataset.step || 'rect';
    if (step === 'mark') {
      /* 迭代分割（涂抹） */
      window.exitCropInteraction?.();   // 进入新交互先退裁剪
      const { fgd, bgd } = await scribble.exportMasks();
      if (!fgd && !bgd) { busy.set('请先涂抹前景或背景'); return; }
      try {
        busy.start('迭代分割中…');
        const url = await API.grabcutRefine(fgd, bgd);
        viewer.setImage(url);
        scribble.clear();
        busy.done('迭代分割完成');
        setMaskView();
      } catch (err) { window.fail('失败: ' + err.message); }
      return;
    }
    /* rect 步骤：框选/分割 一体按钮 */
    const shape = curShape();
    // 态1：还没进入框选也没框出形状 → 进入框选态
    if (!rectMode && !_hasShape()) {
      window.exitCropInteraction?.();   // 进入框选前先退裁剪
      rectMode = true;
      rectBox = null; rectDrawing = false; shapeStart = null; shapePts = [];
      setInteractionLock(true);
      setActionLabel('在图上拖拽框选…（再点取消）');
      busy.set('拖拽框出前景区域');
      return;
    }
    // 态2：框选中但还没框出有效形状 → 取消框选
    if (rectMode && !_hasShape()) {
      rectMode = false; rectDrawing = false; shapeStart = null; shapePts = [];
      rectBox = null;
      setInteractionLock(false);
      scribble._redraw();
      setActionLabel('开始框选');
      busy.set('已取消框选');
      return;
    }
    // 态3：已有有效形状 → 执行初始分割
    try {
      busy.start('初始分割中…');
      if (shape === 'rect') {
        const x1 = Math.min(rectBox.x1, rectBox.x2), y1 = Math.min(rectBox.y1, rectBox.y2);
        const w = Math.abs(rectBox.x2 - rectBox.x1), h = Math.abs(rectBox.y2 - rectBox.y1);
        if (w < 5 || h < 5) { busy.idle('矩形太小，请重新框选'); return; }
        await API.grabcutInitRect(Math.round(x1), Math.round(y1), Math.round(w), Math.round(h));
      } else {
        const blob = await scribble.exportShapeMask(shape, rectBox, shapePts);
        if (!blob) { busy.idle(shape === 'ellipse' ? '请先拖出椭圆' : '请先用自由曲线勾勒前景'); return; }
        await API.grabcutInitMask(blob);
      }
      exitInteraction();
      // 初始分割后直接显示 原图+高亮（非 mask）
      setMaskView();
      viewer.setImage(API.overlayUrl() + '?t=' + Date.now());
      busy.done('初始分割完成，切到「迭代分割」涂抹修正');
    } catch (err) { window.fail('分割失败: ' + err.message); }
  });

  /* ---- 自动分割（方法下拉 + 参数区显隐） ---- */
  $('segMethod').addEventListener('change', () => {
    const m = $('segMethod').value;
    $('wsRow').style.display = m === 'watershed' ? '' : 'none';
    $('slicRow').style.display = m === 'slic' ? '' : 'none';
  });
  $('segMethod').dispatchEvent(new Event('change'));
  $('autoSegBtn').addEventListener('click', async () => {
    const m = $('segMethod').value;
    window.exitCropInteraction?.();   // 进入新交互先退裁剪
    try {
      busy.start('自动分割中…');
      const req = { method: m, fg_ratio: +$('fgRatio').value, n_segments: +$('nSeg').value };
      await API.segmentAuto(req);   // 触发后端分割；返回值是 mask blob，不直接显示
      // 自动分割后显示 原图+高亮（非 mask），与初始分割对齐
      setMaskView();
      viewer.setImage(API.overlayUrl() + '?t=' + Date.now());
      busy.done('自动分割完成');
    } catch (err) { window.fail('失败: ' + err.message); }
  });
  $('autoApplyBtn').addEventListener('click', async () => {
    try {
      busy.start('应用分割 Mask…');
      await API.segmentApply();
      exitInteraction();
      await refreshStatus();
      setAppliedView();
      viewer.setImage(API.appliedUrl() + '?t=' + Date.now());
      busy.done('Mask 已生效：背景不计入图纸');
    } catch (err) { window.fail('失败: ' + err.message); }
  });

  /* ---- 形态学（操作/结构元素下拉 + 示意图 + 应用按钮） ---- */
  const KERNEL_GLYPHS = {
    ellipse: ['01110', '11111', '11111', '11111', '01110'],
    rect: ['11111', '11111', '11111', '11111', '11111'],
    cross: ['00100', '00100', '11111', '00100', '00100'],
    vline: ['00100', '00100', '00100', '00100', '00100'],
    hline: ['00000', '00000', '11111', '00000', '00000'],
    diag1: ['10000', '01000', '00100', '00010', '00001'],
    diag2: ['00001', '00010', '00100', '01000', '10000'],
    diamond: ['00100', '01110', '11111', '01110', '00100'],
  };
  function drawKernelPreview() {
    const shape = $('morphShape').value;
    const grid = KERNEL_GLYPHS[shape] || KERNEL_GLYPHS.ellipse;
    const c = document.createElement('canvas');
    const n = 5, s = 7; c.width = n * s; c.height = n * s;
    const x = c.getContext('2d');
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    x.clearRect(0, 0, c.width, c.height);
    for (let r = 0; r < n; r++) for (let col = 0; col < n; col++) {
      if (grid[r][col] !== '1') continue;
      x.fillStyle = dark ? '#A78BFA' : '#7C3AED';
      x.beginPath();
      x.roundRect(col * s + 0.5, r * s + 0.5, s - 1, s - 1, 1.5);
      x.fill();
    }
    const kp = $('kernelPreview');
    kp.innerHTML = ''; kp.appendChild(c);
  }
  $('morphShape').addEventListener('change', drawKernelPreview);
  drawKernelPreview();
  // 应用形态学：逐步迭代（每次在上一步 mask 基础上处理），应用后默认显示 mask
  $('morphApplyBtn').addEventListener('click', async () => {
    try {
      busy.start('形态学处理…');
      await API.segmentMorph($('morphOp').value, +$('morphK').value, $('morphShape').value);
      setMaskOnlyView();
      viewer.setImage(API.maskUrl() + '?t=' + Date.now());
      busy.done('已应用形态学（可撤销）');
    } catch (err) { window.fail('失败: ' + err.message); }
  });
  // 撤销 / 重做（各最多 3 步），刷新 mask 显示
  $('morphUndoBtn').addEventListener('click', async () => {
    try {
      busy.start('撤销…');
      await API.segmentMorphUndo();
      setMaskOnlyView();
      viewer.setImage(API.maskUrl() + '?t=' + Date.now());
      busy.done('已撤销');
    } catch (err) { busy.set(err.message); }
  });
  $('morphRedoBtn').addEventListener('click', async () => {
    try {
      busy.start('重做…');
      await API.segmentMorphRedo();
      setMaskOnlyView();
      viewer.setImage(API.maskUrl() + '?t=' + Date.now());
      busy.done('已重做');
    } catch (err) { busy.set(err.message); }
  });

  /* ---- 应用分割结果（保留原图 + Mask 独立层，不烘焙；应用后显示黑底前景结果） ---- */
  $('applySegBtn').addEventListener('click', async () => {
    try {
      busy.start('应用分割 Mask…');
      await API.segmentApply();
      exitInteraction();
      await refreshStatus();
      setAppliedView();
      viewer.setImage(API.appliedUrl() + '?t=' + Date.now());
      busy.done('Mask 已生效：背景不计入图纸');
    } catch (err) { window.fail('失败: ' + err.message); }
  });

  /* 切到 高亮 / Mask 视图辅助 */
  function setMaskView() {
    [...$('viewToggle').children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'highlight'));
  }
  function setMaskOnlyView() {
    [...$('viewToggle').children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'mask'));
  }
  function setAppliedView() {
    [...$('viewToggle').children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'applied'));
  }
  function setOriginalView() {
    [...$('viewToggle').children].forEach(x => x.classList.toggle('on', x.dataset.mode === 'original'));
  }

  /* ---- 自绘玻璃下拉增强（逐选项悬停出 tooltip） ---- */
  if (window.Dropdown) {
    ['igcShape', 'segMethod', 'morphOp', 'morphShape'].forEach(id => {
      const el = $(id); if (el) window.Dropdown.enhance(el);
    });
    // morphShape 自绘下拉 change 后联动示意图
    if ($('morphShape')) $('morphShape').addEventListener('change', drawKernelPreview);
  }
})();
