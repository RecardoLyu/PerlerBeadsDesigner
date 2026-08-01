/* 视图逻辑：图像处理（加载/基本调整）与图纸生成接线。分割/导出卡片由后续模块注入。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const viewer = window.viewer;
  /* 组装 chart 请求：带 Mask 背景下拉（由 pattern.js 注入的 #maskBg 提供） */
  window._chartReq = function () {
    const mb = $('maskBg');
    return { bead_pixel_size: 18, mask_bg: mb ? mb.value : 'none' };
  };

  /* ---- 空状态提示 ---- */
  function syncEmpty() {
    const has = viewer.img && viewer.img.src && !viewer.img.src.endsWith('/');
    $('emptyHint').style.display = has ? 'none' : 'grid';
  }
  const _setImage = viewer.setImage.bind(viewer);
  viewer.setImage = (url) => { _setImage(url); setTimeout(syncEmpty, 50); };
  syncEmpty();

  /* ---- 加载图像（pywebview 原生对话框优先，浏览器降级 file input） ---- */
  const _afterLoad = async (url) => {
    viewer.setImage(url);
    await refreshStatus();
    busy.done('图像已加载');
    if (window.onImageLoaded) window.onImageLoaded();
  };
  $('loadBtn').addEventListener('click', async () => {
    // 原生文件对话框（独立程序窗口内）
    if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_file) {
      try {
        const path = await window.pywebview.api.choose_file();
        if (!path) return;
        busy.start('加载图像…');
        const url = await API.loadImagePath(path);
        await _afterLoad(url);
      } catch (err) { window.fail('加载失败: ' + err.message); }
      return;
    }
    $('loadFile').click();
  });
  $('loadFile').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      busy.start('加载图像…');
      const url = await API.loadImageFile(f);
      await _afterLoad(url);
    } catch (err) { window.fail('加载失败: ' + err.message); }
    e.target.value = '';
  });

  /* ---- 基本调整（每次应用都叠加在当前图上，可连续迭代） ---- */
  window.bindEditable('brightness', 'brightnessOut', { fmt: v => (+v).toFixed(2) });
  window.bindEditable('contrast', 'contrastOut', { fmt: v => (+v).toFixed(2) });
  window.bindEditable('blur', 'blurOut', { fmt: v => v });

  $('applyBasic').addEventListener('click', async () => {
    try {
      busy.start('应用调整…');
      const blur = +$('blur').value;
      const url = await API.basic({
        reset_first: false,
        brightness: +$('brightness').value,
        contrast: +$('contrast').value,
        blur: blur > 1 ? blur : null,
      });
      viewer.setImage(url);
      // 亮度/对比度是相对量，应用后复位为 1；高斯核保持上一步值便于继续同核迭代
      $('brightness').value = 1; $('contrast').value = 1;
      ['brightness', 'contrast'].forEach(id => $(id).dispatchEvent(new Event('input')));
      busy.done('已应用调整（可继续在当前图上迭代）');
      if (window.onImageLoaded) window.onImageLoaded();
    } catch (err) { window.fail('失败: ' + err.message); }
  });

  $('resetBtn').addEventListener('click', async () => {
    try {
      busy.start('恢复原图…');
      const url = await API.resetImage();
      viewer.setImage(url);
      $('brightness').value = 1; $('contrast').value = 1; $('blur').value = 1;
      ['brightness', 'contrast', 'blur'].forEach(id => $(id).dispatchEvent(new Event('input')));
      await refreshStatus();
      busy.done('已恢复原图');
      if (window.onImageLoaded) window.onImageLoaded();
    } catch (err) { window.fail('失败: ' + err.message); }
  });

  /* ---- 视图切换：切到图纸生成时若已有图纸则渲染，否则提示 ---- */
  window.onViewSwitch = async (name) => {
    if (window.exitScribbleInteraction) window.exitScribbleInteraction();
    if (name === '图纸生成') {
      const s = await API.status();
      if (s.has_pattern) {
        try {
          viewer.setImage(await API.patternChart(window._chartReq()));
          // 视图刚切换布局未稳定，下一帧再居中
          requestAnimationFrame(() => requestAnimationFrame(() => viewer.fit()));
        } catch (e) {}
      } else if (s.has_image) {
        busy.set('点左侧「生成图纸」以查看标准图纸');
      }
    }
  };

  /* ---- 图纸参数：宽高比例联动 + 细节/ICM 输出 ---- */
  let _imgW = 0, _imgH = 0;
  async function _refreshImgDims() {
    const s = await API.status();
    if (s.has_image) { _imgW = s.image.width; _imgH = s.image.height; syncRatio('w'); }
  }
  window.onImageLoaded = _refreshImgDims;
  function syncRatio(changed) {
    if (!$('keepRatio').checked || !_imgW || !_imgH) return;
    const ratio = _imgH / _imgW;
    if (changed === 'w') $('hBeads').value = Math.max(4, Math.round(+$('wBeads').value * ratio));
    else $('wBeads').value = Math.max(4, Math.round(+$('hBeads').value / ratio));
  }
  $('wBeads').addEventListener('input', () => syncRatio('w'));
  $('hBeads').addEventListener('input', () => syncRatio('h'));
  $('keepRatio').addEventListener('change', () => syncRatio('w'));
  window.bindEditable('salience', 'salienceOut', { fmt: v => (+v).toFixed(1) });

  /* 颜色度量下拉：切换即调用后端 */
  $('colorMetric').addEventListener('change', async () => {
    try { await API.setMetric($('colorMetric').value); busy.set('颜色度量: ' + $('colorMetric').selectedOptions[0].text); }
    catch (e) { window.fail('设置度量失败: ' + e.message); }
  });

  /* 抖动 / ICM：复选框开关对应滑块显隐与启用 */
  function _syncCombo(cbId, rowId, sliderId) {
    const on = $(cbId).checked;
    $(rowId).style.display = on ? '' : 'none';
    $(sliderId).disabled = !on;
  }
  $('dither').addEventListener('change', () => _syncCombo('dither', 'ditherRow', 'ditherStrength'));
  $('icmOn').addEventListener('change', () => _syncCombo('icmOn', 'icmRow', 'icm'));
  _syncCombo('dither', 'ditherRow', 'ditherStrength');
  _syncCombo('icmOn', 'icmRow', 'icm');
  window.bindEditable('ditherStrength', 'ditherStrengthOut', { fmt: v => (+v).toFixed(2) });
  window.bindEditable('icm', 'icmOut', { fmt: v => (+v).toFixed(2) });

  /* Mask 背景下拉（图纸参数卡）：改后若有图纸立即重渲预览 */
  $('maskBg').addEventListener('change', async () => {
    const s = await API.status();
    if (s.has_pattern) {
      try { viewer.setImage(await API.patternChart(window._chartReq())); } catch (e) {}
    }
  });

  /* 自绘玻璃下拉增强（静态卡内的两个下拉） */
  if (window.Dropdown) {
    ['colorMetric', 'maskBg'].forEach(id => { const el = $(id); if (el) window.Dropdown.enhance(el); });
  }

  /* ---- 生成图纸 ---- */
  $('genBtn').addEventListener('click', async () => {
    try {
      busy.start('生成图纸…');
      const maxc = +$('maxColors').value;
      const ditherOn = $('dither').checked, icmOn = $('icmOn').checked;
      const res = await API.patternGenerate({
        width_beads: +$('wBeads').value,
        height_beads: +$('hBeads').value,
        max_colors: maxc > 0 ? maxc : null,
        salience_strength: +$('salience').value,
        dither: ditherOn,
        dither_strength: ditherOn ? +$('ditherStrength').value : 1.0,
        icm_smooth: icmOn ? +$('icm').value : 0.0,
        use_mask: $('useMask').checked,
      });
      busy.done(`已生成 ${res.width}×${res.height} 图纸 · 共 ${res.bom.total_beads} 豆`);
      if (window.exitScribbleInteraction) window.exitScribbleInteraction();
      viewer.setImage(await API.patternChart(window._chartReq()));
      requestAnimationFrame(() => requestAnimationFrame(() => viewer.fit()));
      if (window.onPatternGenerated) window.onPatternGenerated(res);
    } catch (err) { window.fail('生成失败: ' + err.message); }
  });
})();
