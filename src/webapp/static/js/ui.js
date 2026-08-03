/* toast 提示 + help 帮助模态（渲染 HELP.md 的轻量 markdown）。 */
(function () {
  /* ---- toast ---- */
  const wrap = document.getElementById('toastWrap');
  window.toast = function (msg, kind = 'info', ms = 2600) {
    const el = document.createElement('div');
    el.className = 'toast' + (kind === 'err' ? ' err' : kind === 'ok' ? ' ok' : '');
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, ms);
  };

  /* ---- 轻量 markdown -> html（HELP.md 用） ---- */
  function mdToHtml(md) {
    const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const inline = (s) => esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const lines = md.split(/\r?\n/);
    let html = '', inList = false, para = [];
    const flushPara = () => { if (para.length) { html += '<p>' + para.map(inline).join('<br>') + '</p>'; para = []; } };
    const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };
    /* 表格辅助：切分 | 单元行（去首尾空单元），跳过分隔行 |---| */
    const splitRow = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    const isSep = (l) => /^\|?[\s:|-]+\|?$/.test(l) && l.includes('-');
    const isTableRow = (l) => l.includes('|') && splitRow(l).length > 1;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trimEnd();
      if (!line.trim()) { flushPara(); closeList(); continue; }
      /* ``` 代码块 */
      if (/^```/.test(line.trim())) {
        flushPara(); closeList();
        const buf = [];
        for (i++; i < lines.length && !/^```/.test(lines[i].trim()); i++) buf.push(lines[i]);
        html += '<pre>' + esc(buf.join('\n')) + '</pre>';
        continue;
      }
      /* | 表格（连续表格行聚合成 <table>） */
      if (isTableRow(line)) {
        flushPara(); closeList();
        const rows = [];
        while (i < lines.length && lines[i].trim() && isTableRow(lines[i].trimEnd())) {
          const l = lines[i].trimEnd();
          if (!isSep(l)) rows.push(splitRow(l));
          i++;
        }
        i--;                                        // for 循环会再 +1
        if (rows.length) {
          html += '<table><thead><tr>' + rows[0].map(c => '<th>' + inline(c) + '</th>').join('') + '</tr></thead><tbody>'
                + rows.slice(1).map(r => '<tr>' + r.map(c => '<td>' + inline(c) + '</td>').join('') + '</tr>').join('')
                + '</tbody></table>';
        }
        continue;
      }
      /* > 引用块 */
      if (/^>\s?/.test(line.trim())) {
        flushPara(); closeList();
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i].trim())) { buf.push(lines[i].trim().replace(/^>\s?/, '')); i++; }
        i--;
        html += '<blockquote>' + buf.map(inline).join('<br>') + '</blockquote>';
        continue;
      }
      const h = line.match(/^(#{1,6})\s+(.*)/);
      if (h) { flushPara(); closeList(); const lv = Math.min(3, h[1].length); html += `<h${lv}>${inline(h[2])}</h${lv}>`; continue; }
      if (/^(---|\*\*\*)$/.test(line.trim())) { flushPara(); closeList(); html += '<hr>'; continue; }
      const li = line.match(/^[-*]\s+(.*)/) || line.match(/^\d+\.\s+(.*)/);
      if (li) { flushPara(); if (!inList) { html += '<ul>'; inList = true; } html += '<li>' + inline(li[1]) + '</li>'; continue; }
      closeList(); para.push(line);
    }
    flushPara(); closeList();
    return html;
  }

  /* ---- 可编辑滑块：bindOut 基础上，点击 <output> 变 <input> 手动键入 ----
     bindEditable(sliderId, outId, {min,max,step,fmt,parse,onChange})
     - 拖动滑块 -> output 显示 fmt(value)
     - 点击 output -> 变 input，键入后回车/失焦 clamp 回写滑块并触发 onChange */
  window.bindEditable = function (sliderId, outId, opt = {}) {
    const s = document.getElementById(sliderId);
    const o = document.getElementById(outId);
    if (!s || !o) return;
    const min = opt.min !== undefined ? opt.min : +s.min;
    const max = opt.max !== undefined ? opt.max : +s.max;
    const step = opt.step !== undefined ? opt.step : +s.step || 1;
    const fmt = opt.fmt || ((v) => v);
    const parse = opt.parse || ((txt) => parseFloat(txt));
    const clamp = (v) => Math.min(max, Math.max(min, v));
    const show = () => { o.textContent = fmt(s.value); };
    s.addEventListener('input', () => { show(); if (opt.onChange) opt.onChange(+s.value); });
    o.classList.add('editable');
    o.title = '点击可手动输入';
    o.addEventListener('click', () => {
      if (o.querySelector('input')) return;
      const cur = s.value;
      const inp = document.createElement('input');
      inp.type = 'text'; inp.value = cur; inp.className = 'out-edit';
      o.textContent = ''; o.appendChild(inp);
      inp.focus(); inp.select();
      let done = false;
      const commit = (apply) => {
        if (done) return; done = true;
        if (apply) {
          const v = parse(inp.value);
          if (!isNaN(v)) {
            // snap to step
            const snapped = clamp(Math.round((clamp(v) - min) / step) * step + min);
            s.value = snapped;
            s.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }
        show();
      };
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { commit(true); }
        else if (e.key === 'Escape') { commit(false); }
      });
      inp.addEventListener('blur', () => commit(true));
    });
    show();
  };

  /* ---- 轻量 tooltip：任何带 data-tip 的元素，悬停 400ms 浮层显示 ---- */
  (function tooltips() {
    let tip = null, timer = null, anchor = null;
    const DELAY = 400;
    function ensure() {
      if (tip) return tip;
      tip = document.createElement('div');
      tip.className = 'tooltip';
      document.body.appendChild(tip);
      return tip;
    }
    function place(el) {
      const t = ensure();
      const r = el.getBoundingClientRect();
      t.style.visibility = 'hidden';
      t.style.left = '0px'; t.style.top = '0px';
      // measure
      const tw = t.offsetWidth, th = t.offsetHeight;
      let x = r.left + r.width / 2 - tw / 2;
      let y = r.top - th - 8;
      if (y < 6) y = r.bottom + 8;                 // flip below if no room above
      x = Math.max(6, Math.min(window.innerWidth - tw - 6, x));
      t.style.left = x + 'px'; t.style.top = y + 'px';
      t.style.visibility = 'visible';
    }
    function show(el) {
      const text = el.getAttribute('data-tip');
      if (!text) return;
      const t = ensure();
      t.textContent = text;
      t.classList.add('show');
      place(el);
    }
    function hide() {
      clearTimeout(timer); timer = null; anchor = null;
      if (tip) tip.classList.remove('show');
    }
    document.addEventListener('mouseover', (e) => {
      const el = e.target.closest('[data-tip]');
      if (el === anchor) return;
      hide();
      if (!el) return;
      anchor = el;
      timer = setTimeout(() => show(el), DELAY);
    });
    document.addEventListener('mousedown', hide);
    document.addEventListener('scroll', hide, true);
  })();

  /* ---- help 模态 ---- */
  const modal = document.getElementById('helpModal');
  const body = document.getElementById('helpBody');
  let loaded = false;
  async function openHelp() {
    modal.classList.add('show');
    if (loaded) return;
    try {
      const md = await (await fetch('/api/help')).text();
      body.innerHTML = mdToHtml(md);
      loaded = true;
    } catch (e) { body.innerHTML = '<p>帮助加载失败: ' + e.message + '</p>'; }
  }
  function closeHelp() { modal.classList.remove('show'); }
  window.openHelp = openHelp;   // 供设置页「查看使用指南」复用（顶栏帮助按钮已并入设置）
  const helpBtn = document.getElementById('helpBtn');
  if (helpBtn) helpBtn.addEventListener('click', openHelp);
  document.getElementById('helpClose').addEventListener('click', closeHelp);
  modal.addEventListener('click', (e) => { if (e.target === modal) closeHelp(); });
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeHelp(); });
})();
