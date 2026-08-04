/* App 骨架逻辑：主题切换、主导航、侧栏收起、状态栏忙碌、视图切换、画布接线。 */
(function () {
  const html = document.documentElement;

  /* ---- 主题（跟随系统 / 浅色 / 深色） ---- */
  const themeBtn = document.getElementById('themeBtn');
  const sun = document.getElementById('sunIcon'), moon = document.getElementById('moonIcon');
  const _sysDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  let _themeMode = localStorage.getItem('pbd-theme') || 'system';   // system | light | dark（旧值 light/dark 兼容）
  if (!['system', 'light', 'dark'].includes(_themeMode)) _themeMode = 'system';
  function applyTheme() {
    const resolved = _themeMode === 'system' ? (_sysDark && _sysDark.matches ? 'dark' : 'light') : _themeMode;
    html.setAttribute('data-theme', resolved);
    sun.style.display = resolved === 'dark' ? 'none' : 'block';
    moon.style.display = resolved === 'dark' ? 'block' : 'none';
    // 通知皮肤等依赖方按新亮暗重算（skin.js 监听）
    window.dispatchEvent(new Event('pbd-theme-changed'));
  }
  // 供设置页三选调用
  window.setThemeMode = (mode) => {
    _themeMode = ['system', 'light', 'dark'].includes(mode) ? mode : 'system';
    localStorage.setItem('pbd-theme', _themeMode);
    applyTheme();
  };
  window.getThemeMode = () => _themeMode;
  // 主题按钮：三态循环 跟随系统→浅色→深色
  themeBtn.addEventListener('click', () => {
    const order = ['system', 'light', 'dark'];
    window.setThemeMode(order[(order.indexOf(_themeMode) + 1) % order.length]);
  });
  if (_sysDark && _sysDark.addEventListener) {
    _sysDark.addEventListener('change', () => { if (_themeMode === 'system') applyTheme(); });
  }
  applyTheme();

  /* ---- 状态栏 ---- */
  const busyEl = document.getElementById('busy');
  const statusMsg = document.getElementById('statusMsg');
  const statusRight = document.getElementById('statusRight');
  const kaomojiEl = document.getElementById('kaomoji');
  /* 颜文字分场景：忙碌/完成/空闲，轮换周期 1s；完成后保留 2s 再淡出 */
  const KAOMOJI = {
    busy: ['(◕‿◕)', '(｡♥‿♥｡)', '(≧◡≦)', '(ﾉ◕ヮ◕)ﾉ', '(◠‿◠)', '(✿◠‿◠)', '(¬‿¬)', '(☆▽☆)', '(ღ˘⌣˘ღ)', '(∩^o^)⊃'],
    done: ['(✧ω✧)', 'ヽ(✿ﾟ▽ﾟ)ノ', '(๑•̀ㅂ•́)و✧', '(★ω★)', '＼(^o^)／', '(´▽`ʃ♡ƪ)'],
    idle: ['(´・ω・`)', '(¬_¬)', '( ˘ω˘ )', '(〜￣△￣)〜', '(._.)', '( ´_ゝ`)'],
  };
  let _kaoTimer = null, _kaoIdx = 0, _kaoSet = 'busy', _doneTimer = null;
  function _kaoShow() { kaomojiEl.textContent = KAOMOJI[_kaoSet][_kaoIdx]; }
  function _kaoStart(set) {
    _kaoSet = set; _kaoIdx = 0; _kaoShow();
    if (_kaoTimer) return;
    _kaoTimer = setInterval(() => {
      _kaoIdx = (_kaoIdx + 1) % KAOMOJI[_kaoSet].length;
      _kaoShow();
    }, 1000);   // 1s 轮换
  }
  function _kaoStop() { clearInterval(_kaoTimer); _kaoTimer = null; }
  window.busy = {
    start(msg) {
      busyEl.classList.add('on'); busyEl.classList.remove('done-state', 'idle-state');
      clearTimeout(_doneTimer); _doneTimer = null;
      _kaoStart('busy');
      statusMsg.textContent = msg || '处理中…';
    },
    done(msg) {
      busyEl.classList.add('on', 'done-state'); busyEl.classList.remove('idle-state');
      _kaoStart('done');
      if (msg) statusMsg.textContent = msg;
      // 完成态保留 2s 再淡出
      clearTimeout(_doneTimer);
      _doneTimer = setTimeout(() => { busyEl.classList.remove('on', 'done-state'); _kaoStop(); }, 2000);
    },
    idle(msg) {
      busyEl.classList.add('on', 'idle-state'); busyEl.classList.remove('done-state');
      clearTimeout(_doneTimer); _doneTimer = null;
      _kaoStart('idle');
      if (msg) statusMsg.textContent = msg;
    },
    set(msg) { statusMsg.textContent = msg; },
    info(msg) { statusRight.textContent = msg; },
  };
  /* 失败统一提示：状态栏 + toast */
  window.fail = function (msg) {
    busyEl.classList.remove('on', 'done-state', 'idle-state'); _kaoStop();
    clearTimeout(_doneTimer); _doneTimer = null;
    statusMsg.textContent = msg;
    if (window.toast) window.toast(msg, 'err');
  };

  /* ---- 主导航（图像转换 / 图纸画板）+ 左栏子切换（图像调整 / 图纸生成） ----
     主入口决定左栏整体内容：图像转换=参数面板（含两套子卡），图纸画板=画板工具栏。
     子切换仅在图像转换内切换「图像调整 / 图纸生成」两套参数卡（迁移自原顶部入口）。 */
  const nav = document.getElementById('nav');
  const thumb = document.getElementById('navThumb');
  const pills = [...nav.querySelectorAll('.nav-pill')];
  const canvasTitle = document.getElementById('canvasTitle');
  const subnav = document.getElementById('subnav');
  const subPills = subnav ? [...subnav.querySelectorAll('.subnav-pill')] : [];
  const viewPreprocess = document.getElementById('view-preprocess');
  const viewPattern = document.getElementById('view-pattern');
  const viewBoard = document.getElementById('view-board');   // 画板工具栏（模块四注入）

  function moveThumb(el) { thumb.style.left = el.offsetLeft + 'px'; thumb.style.width = el.offsetWidth + 'px'; }

  /* 当前主入口：'图像转换' | '图纸画板' */
  let _mainView = '图像转换';
  /* 图像转换内当前子视图：'preprocess'(图像调整) | 'pattern'(图纸生成) */
  let _subView = 'preprocess';

  /* 子切换：切换图像调整/图纸生成两套参数卡（作用与原顶部入口一致） */
  function switchSub(sub) {
    _subView = sub;
    subPills.forEach(x => x.classList.toggle('active', x.dataset.sub === sub));
    if (viewPreprocess) viewPreprocess.style.display = (sub === 'preprocess') ? '' : 'none';
    if (viewPattern) viewPattern.style.display = (sub === 'pattern') ? '' : 'none';
    // 通知业务层（沿用原名，图纸生成时渲染已有图纸）
    if (window.onViewSwitch) window.onViewSwitch(sub === 'pattern' ? '图纸生成' : '图像调整');
  }
  subPills.forEach(p => p.addEventListener('click', () => switchSub(p.dataset.sub)));

  /* 主入口切换 */
  function switchView(name) {
    _mainView = name;
    pills.forEach(x => x.classList.toggle('active', x.dataset.view === name));
    moveThumb(nav.querySelector('.active'));
    canvasTitle.textContent = name + ' · 预览画布';
    const isBoard = (name === '图纸画板');
    // 左栏：画板显示画板工具栏 + 隐藏子切换；图像转换显示子切换 + 当前子卡
    if (subnav) subnav.style.display = isBoard ? 'none' : '';
    if (viewBoard) viewBoard.style.display = isBoard ? '' : 'none';
    if (isBoard) {
      if (viewPreprocess) viewPreprocess.style.display = 'none';
      if (viewPattern) viewPattern.style.display = 'none';
      if (window.onEnterBoard) window.onEnterBoard();
    } else {
      switchSub(_subView);   // 恢复子卡显隐并通知业务层
    }
  }
  pills.forEach(p => p.addEventListener('click', () => switchView(p.dataset.view)));
  moveThumb(pills[0]);
  window.addEventListener('resize', () => { const a = nav.querySelector('.active'); if (a) moveThumb(a); });
  /* 供外部切主入口/子视图 */
  window.switchMainView = switchView;
  window.switchSubView = switchSub;

  /* ---- 设置抽屉（右侧浮窗，全局功能不占画布） ---- */
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsDrawer = document.getElementById('view-settings');
  const settingsMask = document.getElementById('settingsMask');
  const settingsClose = document.getElementById('settingsClose');
  function openSettings() {
    settingsDrawer.classList.add('show');
    settingsMask.classList.add('show');
    settingsBtn.classList.add('on');
  }
  function closeSettings() {
    settingsDrawer.classList.remove('show');
    settingsMask.classList.remove('show');
    settingsBtn.classList.remove('on');
  }
  if (settingsBtn) settingsBtn.addEventListener('click', () => {
    settingsDrawer.classList.contains('show') ? closeSettings() : openSettings();
  });
  if (settingsClose) settingsClose.addEventListener('click', closeSettings);
  if (settingsMask) settingsMask.addEventListener('click', closeSettings);
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSettings(); });
  window.closeSettings = closeSettings;

  /* ---- 侧栏收起 ---- */
  const sidebar = document.getElementById('sidebar');
  document.getElementById('collapseBtn').addEventListener('click', () => sidebar.classList.toggle('collapsed'));

  /* ---- 画布 ---- */
  const viewer = new Viewer(document.getElementById('canvas'));
  window.viewer = viewer;
  document.getElementById('zoomIn').addEventListener('click', () => viewer.zoomBy(1.2));
  document.getElementById('zoomOut').addEventListener('click', () => viewer.zoomBy(0.84));
  document.getElementById('fitBtn').addEventListener('click', () => viewer.fit());
  document.getElementById('panBtn').addEventListener('click', (e) => {
    viewer._panMode = !viewer._panMode;
    e.currentTarget.classList.toggle('on', viewer._panMode);
  });

  /* ---- 显示切换（原图 / 原图+高亮 / Mask / 应用结果）——骨架阶段先切原图/Mask ---- */
  const vt = document.getElementById('viewToggle');
  vt.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return;
    [...vt.children].forEach(x => x.classList.remove('on')); b.classList.add('on');
    const mode = b.dataset.mode;
    try {
      busy.start('切换显示…');
      if (mode === 'original') viewer.setImage(API.currentImageUrl() + '?t=' + Date.now());
      else if (mode === 'mask') viewer.setImage(API.maskUrl() + '?t=' + Date.now());
      else busy.set('「' + b.textContent + '」将在分割模块接入');
      busy.done('就绪');
    } catch (err) { busy.done('无内容: ' + err.message); }
  });

  /* ---- 状态刷新 ---- */
  async function refreshStatus() {
    try {
      const s = await API.status();
      const img = s.has_image ? `图像 ${s.image.width}×${s.image.height}` : '未加载图像';
      busy.info(`${img} · 调色板 ${s.palette_colors} 色`);
      if (!s.has_image) viewer.setImage(null);
    } catch (e) { busy.info('后端未连接'); }
  }
  window.refreshStatus = refreshStatus;
  refreshStatus();
})();
