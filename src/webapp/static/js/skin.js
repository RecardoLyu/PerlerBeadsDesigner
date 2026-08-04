/* 图片换肤：按 settings.json 的皮肤配置即时应用/移除。
   - 主题色：inline setProperty 覆盖 11 个 CSS 变量（优先级高于 :root 与
     [data-theme=dark] 样式表规则；tokens.css 禁止 !important，见其头注释）。
   - 亮/暗各推导一套值：由基色 HSL 出发，色相不变、夹取饱和/明度
     （与移动端 lib/theme/skin.dart 的 deriveSkinPalette 同一套规则）。
   - 背景：fixed 壁纸层 cover + blur(3px)，透明度为单一共用值 op（亮暗同值）。
   依赖：shell.js 的 applyTheme 在每次切换后 dispatch 'pbd-theme-changed'。 */
(function () {
  const root = document.documentElement;

  /* 皮肤状态（由 settings.js 通过 window.skinApply 注入）；
     op 单一共用不透明度，blur 模糊档 0/1/2，accent 辅助色 */
  let _skin = { url: '', color: '', accent: '', op: 0.15, blur: 1 };

  /* ---- 颜色工具 ---- */
  function hexToRgb(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim());
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    if (mx === mn) return [0, 0, l];
    const d = mx - mn, s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
    let h;
    if (mx === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (mx === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    return [h * 60, s, l];
  }
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const hsl = (h, s, l, a) => {
    h = ((h % 360) + 360) % 360;
    const ss = (clamp(s, 0, 1) * 100).toFixed(1) + '%', ll = (clamp(l, 0, 1) * 100).toFixed(1) + '%';
    return a == null ? `hsl(${h.toFixed(1)} ${ss} ${ll})` : `hsl(${h.toFixed(1)} ${ss} ${ll} / ${a})`;
  };
  function hslToRgb(h, s, l) {
    h = ((h % 360) + 360) % 360 / 360;
    if (s === 0) { const v = Math.round(l * 255); return [v, v, v]; }
    const q = l < .5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    const f = (t) => {
      if (t < 0) t += 1; if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    return [f(h + 1 / 3), f(h), f(h - 1 / 3)].map(v => Math.round(v * 255));
  }

  /* ---- 推导规则（与移动端一致）----
     rgbMain 主色定主题；rgbAccent（可选辅助色）调和面板/卡片底色与投影色，
     让多彩图的玻璃卡片不再单调偏红。shadow 变量供 shell.css 的 box-shadow 用。 */
  function derive(rgbMain, dark, rgbAccent) {
    const [h, s, l] = rgbToHsl(rgbMain[0], rgbMain[1], rgbMain[2]);
    let s2, l2;
    if (dark) { s2 = clamp(s, .40, .75); l2 = clamp(l, .60, .72); }
    else { s2 = clamp(s, .45, .80); l2 = clamp(l, .38, .50); if (l > .78) l2 = .45; }
    const pRgb = hslToRgb(h, s2, l2);
    const onPrimary = l2 <= .62 ? '#FFFFFF' : '#26131B';
    // 染色目标色：主色向辅助色调和 30%（无辅助色则纯主色）
    const tint = rgbAccent
      ? [0, 1, 2].map(i => Math.round(pRgb[i] + (rgbAccent[i] - pRgb[i]) * 0.30))
      : pRgb;
    const tintCss = `rgb(${tint[0]},${tint[1]},${tint[2]})`;
    // 面板底：原表面色向主/辅色调和一点（亮 .08 / 暗 .12，与移动端 deriveSkinPalette 一致），
    // 轻染色保玻璃通透感、不重染偏红
    const surfBase0 = dark ? [46, 22, 32] : [255, 255, 255];
    const surfStrongBase0 = dark ? [58, 28, 40] : [255, 255, 255];
    const tTint = dark ? .12 : .08;
    const surfBase = mixRgb(surfBase0, tint, tTint);
    const surfStrongBase = mixRgb(surfStrongBase0, tint, tTint);
    // 投影色基：主色（含辅色调和），明暗两版
    const shadowRgb = hslToRgb(h, clamp(s2, .4, .8), dark ? .60 : .50);
    return {
      '--color-primary': hsl(h, s2, l2),
      '--color-on-primary': onPrimary,
      '--color-secondary': hsl(h + 8, s2, clamp(l2 + (dark ? .12 : .18), 0, .8)),
      '--color-violet': hsl(h - 18, clamp(s2, .45, .85), dark ? .72 : .66),
      '--color-violet-deep': hsl(h + 10, s2, dark ? .60 : .52),
      '--color-ring': hsl(h, s2, l2),
      '--color-border': hsl(h, s2, l2, dark ? .22 : .18),
      '--color-bg': hsl(h, clamp(s2 * .6, 0, .5), dark ? .08 : .965),
      '--color-bg-2': hsl(h, clamp(s2 * .7, 0, .55), dark ? .11 : .945),
      '--color-surface': `rgba(${surfBase[0]},${surfBase[1]},${surfBase[2]},${dark ? .45 : .55})`,
      '--color-surface-strong': `rgba(${surfStrongBase[0]},${surfStrongBase[1]},${surfStrongBase[2]},${dark ? .60 : .75})`,
      '--shadow-violet-rgb': `${shadowRgb[0]},${shadowRgb[1]},${shadowRgb[2]}`,
      '--shadow-primary-rgb': `${shadowRgb[0]},${shadowRgb[1]},${shadowRgb[2]}`,
      '--shadow-deep-rgb': `${Math.round(shadowRgb[0]*.3)},${Math.round(shadowRgb[1]*.3)},${Math.round(shadowRgb[2]*.3)}`,
      _rgb: pRgb, _tintCss: tintCss,
    };
  }
  /* 两色按比例混合（t=0 全 a，t=1 全 b） */
  function mixRgb(a, b, t) {
    return [0, 1, 2].map(i => Math.round(a[i] + (b[i] - a[i]) * t));
  }

  /* ---- 壁纸层 ---- */
  let _bg = null;
  /* 模糊三档（0=无/1=中/2=高）对应的 px；高斯核不同 */
  const BLUR_PX = [0, 4, 9];

  function ensureBgLayer() {
    if (_bg) return _bg;
    _bg = document.createElement('div');
    _bg.id = 'skinBg';
    // inset 负边 + scale 吃掉高模糊档位的边缘羽化漏光
    _bg.style.cssText = 'position:fixed;inset:-16px;z-index:-1;pointer-events:none;' +
      'background-size:cover;background-position:center;' +
      'transform:scale(1.04);transition:opacity .3s';
    document.body.appendChild(_bg);
    return _bg;
  }

  const VARS = ['--color-primary', '--color-on-primary', '--color-secondary', '--color-violet',
    '--color-violet-deep', '--color-ring', '--color-border', '--color-bg', '--color-bg-2',
    '--color-surface', '--color-surface-strong',
    '--shadow-violet-rgb', '--shadow-primary-rgb', '--shadow-deep-rgb'];

  function resolvedDark() { return root.getAttribute('data-theme') === 'dark'; }

  /* 只清主题色 inline 变量（保留壁纸层与 data-skin），主题落回 tokens.css 默认 */
  function clearThemeVars() {
    VARS.forEach(v => root.style.removeProperty(v));
  }

  function clearSkin() {
    root.removeAttribute('data-skin');
    clearThemeVars();
    if (_bg) _bg.style.display = 'none';
  }

  function apply() {
    if (!_skin.url) { clearSkin(); return; }
    const dark = resolvedDark();
    root.setAttribute('data-skin', 'on');
    // 壁纸先行（即使取色失败/基色为空也能只换背景）
    const bg = ensureBgLayer();
    bg.style.display = '';
    bg.style.opacity = _skin.op;
    const px = BLUR_PX[Math.max(0, Math.min(BLUR_PX.length - 1, _skin.blur))];
    bg.style.filter = px > 0 ? `blur(${px}px)` : 'none';
    if (bg.dataset.src !== _skin.url) {
      bg.dataset.src = _skin.url;
      bg.style.backgroundImage = `url("${_skin.url}")`;
      // 用 offscreen Image 探测加载失败（文件被删等）→ 降级清除，不白屏
      const probe = new Image();
      probe.onerror = () => {
        if (_skin.url && bg.dataset.src === _skin.url) {
          window.skinApply({ url: '' });
          try { if (window.onSkinMissing) window.onSkinMissing(); } catch (err) { /* 静默 */ }
        }
      };
      probe.src = _skin.url;
    }
    // 主题色（基色无效则清变量落回默认糖果主题，壁纸仍保留显示——与移动端一致）
    const rgb = hexToRgb(_skin.color);
    if (!rgb) { clearThemeVars(); return; }
    const accent = hexToRgb(_skin.accent);
    const pal = derive(rgb, dark, accent);
    VARS.forEach(v => root.style.setProperty(v, pal[v]));
  }

  /* ---- 对外接口 ---- */
  window.skinApply = (cfg) => {
    _skin = {
      url: (cfg && cfg.url) || '',
      color: (cfg && cfg.color) || '',
      accent: (cfg && cfg.accent) || '',
      op: (cfg && cfg.op != null) ? cfg.op : 0.15,
      blur: (cfg && cfg.blur != null) ? cfg.blur : 1,
    };
    apply();
  };
  window.skinRefresh = apply;   // 滑杆等只改状态后重绘
  window.skinState = () => ({ ..._skin });

  /* 主题切换后按新亮暗重算一套推导值 */
  window.addEventListener('pbd-theme-changed', apply);

  apply();   // 初始化先 apply 一次（首次 applyTheme 早于本脚本加载）
})();
