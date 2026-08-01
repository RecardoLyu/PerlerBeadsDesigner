/* 自绘玻璃拟态下拉：原生 <select> 无法逐 option 悬停显示 tooltip。
   Dropdown.enhance(selectEl) 读取原生 <option value data-tip> 生成 .gsel，
   隐藏原生 select 保留作值源；选中后 dispatchEvent('change') 兼容现有逻辑。
   option 带 data-tip，悬停时由 ui.js 的 tooltip 委托自动显示说明（呼出即见）。 */
(function () {
  function enhance(sel) {
    if (!sel || sel.dataset.gselEnhanced) return null;
    sel.dataset.gselEnhanced = '1';

    const wrap = document.createElement('div');
    wrap.className = 'gsel';
    wrap.id = sel.id ? sel.id + 'Gsel' : '';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'gsel-btn sel';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.innerHTML = '<span class="gsel-label"></span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg>';

    const list = document.createElement('ul');
    list.className = 'gsel-list glass';
    list.setAttribute('role', 'listbox');

    const label = btn.querySelector('.gsel-label');
    const opts = [...sel.options].map((o) => {
      const li = document.createElement('li');
      li.className = 'gsel-opt' + (o.selected ? ' on' : '');
      li.setAttribute('role', 'option');
      li.dataset.value = o.value;
      li.textContent = o.textContent;
      if (o.dataset.tip) li.dataset.tip = o.dataset.tip;
      li.addEventListener('click', (e) => {
        e.stopPropagation();
        setValue(o.value, true);
        close();
      });
      list.appendChild(li);
      return li;
    });

    function setValue(v, fire) {
      sel.value = v;
      opts.forEach(li => li.classList.toggle('on', li.dataset.value === String(v)));
      const cur = [...sel.options].find(o => o.value === String(v));
      label.textContent = cur ? cur.textContent : v;
      if (fire) sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
    /* 列表挂 <body> 用 fixed 定位：脱离 panel-card 的 stacking context，
       否则下方兄弟卡片（backdrop-filter）会盖在下拉之上（置顶显示）。 */
    function place() {
      const r = btn.getBoundingClientRect();
      list.style.left = r.left + 'px';
      list.style.width = r.width + 'px';
      // 默认在按钮下方；若下方空间不足且上方更空则翻到上方
      const below = window.innerHeight - r.bottom;
      const need = Math.min(list.offsetHeight || 240, 240);
      if (below < need + 12 && r.top > below) {
        list.style.top = Math.max(6, r.top - need - 6) + 'px';
      } else {
        list.style.top = (r.bottom + 6) + 'px';
      }
    }
    function open() {
      closeAll();
      wrap.classList.add('open');
      document.body.appendChild(list);   // 提升层级，fixed 定位
      list.classList.add('open');
      place();
      // 悬停当前选中项的说明，呼出即见
      const on = list.querySelector('.gsel-opt.on') || list.querySelector('.gsel-opt');
      if (on && on.dataset.tip) {
        on.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      }
    }
    function close() {
      wrap.classList.remove('open');
      list.classList.remove('open');
      if (list.parentNode === document.body) wrap.appendChild(list);  // 归还，避免遗留
    }
    function toggle() { wrap.classList.contains('open') ? close() : open(); }

    btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });
    document.addEventListener('click', (e) => { if (!wrap.contains(e.target) && !list.contains(e.target)) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
    // 滚动/缩放时若开着则重定位（保持贴合按钮）
    window.addEventListener('resize', () => { if (wrap.classList.contains('open')) place(); });
    document.addEventListener('scroll', (e) => {
      if (wrap.classList.contains('open') && !list.contains(e.target)) place();
    }, true);

    // 初始标签
    setValue(sel.value, false);

    // 插入组件并隐藏原生 select（保留作值源/兼容）
    sel.style.display = 'none';
    sel.parentNode.insertBefore(wrap, sel.nextSibling);
    wrap.appendChild(btn);
    wrap.appendChild(list);

    // 暴露句柄
    sel._gsel = { setValue, open, close, wrap };
    return sel._gsel;
  }

  function closeAll() {
    document.querySelectorAll('.gsel.open').forEach(g => g.classList.remove('open'));
    document.querySelectorAll('.gsel-list.open').forEach(l => l.classList.remove('open'));
  }

  // 自动增强所有 .sel 下拉（页面加载后）
  function enhanceAll(root) {
    (root || document).querySelectorAll('select.sel').forEach(enhance);
  }

  window.Dropdown = { enhance, enhanceAll, closeAll };
})();
