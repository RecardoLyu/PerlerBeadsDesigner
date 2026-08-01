/* 图纸生成视图：导出选项卡 + BOM 物料芯片列表，对接图纸/导出/BOM API。 */
(function () {
  const $ = (id) => document.getElementById(id);

  /* BOM 文字颜色：深色豆用白字、浅色豆用黑字 */
  function textOn(hex) {
    const h = hex.replace('#', '');
    const r = parseInt(h.substr(0, 2), 16), g = parseInt(h.substr(2, 2), 16), b = parseInt(h.substr(4, 2), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140 ? '#3b0a1c' : '#ffffff';
  }

  /* ---- 注入导出 + BOM 卡片 ---- */
  $('patternCards').innerHTML = `
    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></svg>导出</h3>
      <div class="num-row"><label>文件名</label><input type="text" id="expName" value="pattern" style="flex:1;padding:7px 10px;border-radius:12px;border:1px solid var(--color-border);background:var(--color-surface-strong);color:var(--color-foreground);font-family:var(--font-body);font-size:13px"></div>
      <div class="slider-row"><label>PNG缩放</label><input type="range" id="expScale" min="0.5" max="3" step="0.25" value="1" data-tip="导出 PNG 的缩放倍数：小于 1 缩小，大于 1 放大，越大越清晰、文件越大。"><output id="expScaleOut">1×</output></div>
      <div class="num-row"><label>Mask背景</label>
        <select class="sel" id="maskBgExp" data-tip="导出图纸时被 Mask 掉的背景格怎么显示：淡化=向白减淡，纯白/纯黑=填纯色。背景不计入 BOM、不渲染色号。">
          <option value="none" data-tip="背景格向白色减淡显示，保留隐约轮廓">淡化</option>
          <option value="white" data-tip="背景格填纯白色">纯白</option>
          <option value="black" data-tip="背景格填纯黑色">纯黑</option>
        </select>
      </div>
      <div class="chip-row" id="paperSel">
        <span class="chip on" data-p="A4">A4</span>
        <span class="chip" data-p="Letter">Letter</span>
      </div>
      <div class="check-row"><input type="checkbox" id="expPng" checked><label for="expPng">导出 PNG</label></div>
      <div class="check-row"><input type="checkbox" id="expPdf" checked><label for="expPdf">导出 PDF</label></div>
      <div class="num-row"><label>输出路径</label>
        <input type="text" id="outDir" readonly style="flex:1;padding:7px 10px;border-radius:12px;border:1px solid var(--color-border);background:var(--color-surface-strong);color:var(--color-muted-fg);font-family:var(--font-body);font-size:11px">
        <button class="btn btn-ghost" id="chooseDirBtn" data-tip="选择图纸导出的保存目录（独立窗口内用系统对话框，浏览器中请直接键入路径）">选择</button>
      </div>
      <button class="btn btn-primary" id="exportBtn" style="width:100%;margin-top:6px">一键导出</button>
      <p class="hint" id="expResult">文件将保存到上方输出路径。</p>
    </div>
    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>物料清单 (BOM)</h3>
      <div id="bomList" class="chip-row" style="gap:6px">
        <p class="hint">生成图纸后显示所需豆子颜色与数量。</p>
      </div>
    </div>
  `;

  window.bindEditable('expScale', 'expScaleOut', { fmt: v => v + '×', parse: t => parseFloat(t.replace('×', '')) });
  // 导出卡 mask 背景下拉：默认同步图纸参数卡的值，自绘增强
  if (window.Dropdown && $('maskBgExp')) window.Dropdown.enhance($('maskBgExp'));
  if ($('maskBg') && $('maskBgExp')) $('maskBgExp').value = $('maskBg').value;
  $('paperSel').addEventListener('click', (e) => {
    const c = e.target.closest('.chip'); if (!c) return;
    [...$('paperSel').children].forEach(x => x.classList.remove('on')); c.classList.add('on');
  });

  /* ---- 输出路径：初始读取 + 原生/手动选择 ---- */
  async function _refreshOutDir() {
    try { const r = await API.getOutputDir(); $('outDir').value = r.output_dir; } catch (e) {}
  }
  _refreshOutDir();
  $('chooseDirBtn').addEventListener('click', async () => {
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_dir) {
        const p = await window.pywebview.api.choose_dir();
        if (!p) return;
        const r = await API.setOutputDir(p);
        $('outDir').value = r.output_dir;
        busy.set('输出路径: ' + r.output_dir);
      } else {
        // 浏览器降级：可编辑文本框
        $('outDir').removeAttribute('readonly');
        $('outDir').focus(); $('outDir').select();
        busy.set('请直接键入输出路径，回车确认');
      }
    } catch (err) { window.fail('设置输出路径失败: ' + err.message); }
  });
  $('outDir').addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter' || $('outDir').readOnly) return;
    try {
      const r = await API.setOutputDir($('outDir').value);
      $('outDir').value = r.output_dir;
      $('outDir').setAttribute('readonly', '');
      busy.set('输出路径: ' + r.output_dir);
    } catch (err) { window.fail('设置输出路径失败: ' + err.message); }
  });

  /* ---- 渲染 BOM 芯片 ---- */
  function renderBom(bom) {
    const list = $('bomList');
    if (!bom || !bom.colors) { list.innerHTML = '<p class="hint">无 BOM 数据</p>'; return; }
    const items = Object.entries(bom.colors).sort((a, b) => b[1].count - a[1].count);
    list.innerHTML = items.map(([code, info]) => `
      <span class="chip" title="${info.name} · ${info.percentage.toFixed(1)}%" style="
        display:inline-flex;align-items:center;gap:6px;padding:4px 12px 4px 4px;cursor:default">
        <span style="width:22px;height:22px;border-radius:999px;background:${info.hex};color:${textOn(info.hex)};
          display:grid;place-items:center;font-size:9px;font-weight:800;flex:none">${code}</span>
        <span style="color:var(--color-foreground)">×${info.count}</span>
      </span>`).join('') +
      `<p class="hint" style="width:100%;margin-top:6px">共 ${bom.total_beads} 豆 · ${items.length} 种颜色</p>`;
  }
  window.renderBom = renderBom;

  /* 图纸生成成功后刷新 BOM（app.js 会调用 onPatternGenerated） */
  window.onPatternGenerated = (res) => { if (res && res.bom) renderBom(res.bom); };

  /* ---- 一键导出 ---- */
  $('exportBtn').addEventListener('click', async () => {
    const png = $('expPng').checked, pdf = $('expPdf').checked;
    if (!png && !pdf) { busy.set('请至少勾选一个导出格式'); return; }
    try {
      busy.start('导出中…');
      const res = await API.export({
        filename: $('expName').value || 'pattern',
        png_scale: +$('expScale').value,
        paper: $('paperSel').querySelector('.on').dataset.p,
        export_png: png,
        export_pdf: pdf,
        mask_bg: $('maskBgExp') ? $('maskBgExp').value : $('maskBg').value,
      });
      $('expResult').textContent = '已导出到 ' + res.output_dir + ': ' + res.files.map(f => f.split(/[\\/]/).pop()).join('、');
      busy.done('导出完成');
    } catch (err) {
      $('expResult').textContent = '导出失败: ' + err.message;
      busy.done('导出失败');
    }
  });
})();
