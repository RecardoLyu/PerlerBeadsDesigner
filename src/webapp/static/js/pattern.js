/* 图纸生成视图：BOM 物料芯片列表，对接图纸/BOM API。导出控件已并入图纸参数卡（index.html），绑定逻辑在 app.js。 */
(function () {
  const $ = (id) => document.getElementById(id);

  /* BOM 文字颜色：深色豆用白字、浅色豆用黑字 */
  function textOn(hex) {
    const h = hex.replace('#', '');
    const r = parseInt(h.substr(0, 2), 16), g = parseInt(h.substr(2, 2), 16), b = parseInt(h.substr(4, 2), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140 ? '#3b0a1c' : '#ffffff';
  }

  /* ---- 注入 BOM 卡片 ---- */
  $('patternCards').innerHTML = `
    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>物料清单 (BOM)</h3>
      <div id="bomList" class="chip-row" style="gap:6px">
        <p class="hint">生成图纸后显示所需豆子颜色与数量。</p>
      </div>
    </div>
  `;

  /* ---- 渲染 BOM 芯片 ---- */
  function renderBom(bom) {
    const list = $('bomList');
    if (!bom || !bom.colors) { list.innerHTML = '<p class="hint">无 BOM 数据</p>'; return; }
    const items = Object.entries(bom.colors).sort((a, b) => b[1].count - a[1].count);
    list.innerHTML = items.map(([code, info]) => `
      <span class="chip" title="${info.name} · ${info.percentage.toFixed(1)}%" style="
        display:inline-flex;align-items:center;gap:6px;padding:4px 12px 4px 4px;cursor:default">
        <span style="min-width:22px;height:22px;padding:0 5px;border-radius:999px;background:${info.hex};color:${textOn(info.hex)};
          display:inline-grid;place-items:center;font-size:9.5px;font-weight:800;flex:none;white-space:nowrap">${code}</span>
        <span style="color:var(--color-foreground)">×${info.count}</span>
      </span>`).join('') +
      `<p class="hint" style="width:100%;margin-top:6px">共 ${bom.total_beads} 豆 · ${items.length} 种颜色</p>`;
  }
  window.renderBom = renderBom;

  /* 图纸生成成功后刷新 BOM（app.js 会调用 onPatternGenerated） */
  window.onPatternGenerated = (res) => { if (res && res.bom) renderBom(res.bom); };
})();
