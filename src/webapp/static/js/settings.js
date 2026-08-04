/* 设置中心：外观（主题三选）、图纸/分割默认参数（持久化 settings.json）、
   关于（版本号 + 使用指南 + 检查更新/在线更新）。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const root = $('settingsBody');
  if (!root) return;

  const IN = 'padding:7px 10px;border-radius:12px;border:1px solid var(--color-border);background:var(--color-surface-strong);color:var(--color-foreground);font-family:var(--font-body);font-size:13px';

  root.innerHTML = `
    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>外观</h3>
      <div class="chip-row" id="setTheme">
        <span class="chip" data-t="system" data-tip="跟随操作系统的浅色/深色设置">跟随系统</span>
        <span class="chip" data-t="light" data-tip="始终浅色">浅色</span>
        <span class="chip" data-t="dark" data-tip="始终深色">深色</span>
      </div>
    </div>

    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c-5 0-9 3.6-9 8 0 4.4 4 8 9 8 .9 0 1.6-.7 1.6-1.6 0-.4-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1 0-.9.7-1.6 1.6-1.6h1.9c2.6 0 4.7-2.1 4.7-4.7C21 5.6 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10.5" cy="7.5" r="1.2"/><circle cx="14.5" cy="7.5" r="1.2"/></svg>自定义主题</h3>
      <div style="display:flex;gap:10px;align-items:center">
        <div id="skinThumbWrap" style="width:64px;height:64px;border-radius:14px;overflow:hidden;border:1px solid var(--color-border);background:var(--color-muted);flex:none;display:grid;place-items:center">
          <img id="skinThumb" alt="" style="width:100%;height:100%;object-fit:cover;display:none">
          <span id="skinNone" style="font-size:11px;color:var(--color-muted-fg)">未设置</span>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;gap:6px">
          <button class="btn btn-primary" id="skinImportBtn" style="width:100%">导入图片</button>
          <button class="btn btn-ghost" id="skinRemoveBtn" style="width:100%;display:none">移除皮肤</button>
        </div>
      </div>
      <input type="file" id="skinFile" accept="image/png,image/jpeg,image/bmp,image/webp" style="display:none">
      <p class="hint" id="skinHint" style="margin-top:8px">导入图片作半透明背景，并自动提取主体颜色定制整套主题色。</p>
      <div id="skinOpArea" style="display:none;margin-top:6px">
        <div class="slider-row"><label>背景不透明度</label><input type="range" id="skinOpacity" min="5" max="40" step="1"><output id="skinOpacityOut"></output></div>
        <div class="slider-row"><label>背景模糊</label><input type="range" id="skinBlur" min="0" max="2" step="1"><output id="skinBlurOut"></output></div>
      </div>
    </div>

    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 3v18"/></svg>图纸默认参数</h3>
      <div class="num-row"><label>默认宽度(豆)</label><input type="number" id="sWidth" min="4" max="400" style="flex:1;${IN}"></div>
      <div class="check-row"><input type="checkbox" id="sKeepRatio"><label for="sKeepRatio">保持图像比例</label></div>
      <div class="num-row"><label>颜色上限</label><input type="number" id="sMaxColors" min="0" max="221" style="flex:1;${IN}" data-tip="0 表示不限制"></div>
      <div class="slider-row"><label>细节保留</label><input type="range" id="sSalience" min="0" max="2" step="0.1"><output id="sSalienceOut"></output></div>
      <div class="num-row"><label>颜色度量</label>
        <select class="sel" id="sMetric">
          <option value="weighted">加权距离</option>
          <option value="euclidean">欧氏距离</option>
          <option value="lab">Lab色空</option>
          <option value="ciede76">CIE76</option>
          <option value="ciede2000">CIEDE2000</option>
        </select>
      </div>
      <div class="num-row"><label>品牌</label>
        <select class="sel" id="sBrand">
          <option value="mard">MARD 曼德</option>
          <option value="perler">Perler</option>
          <option value="hama">Hama</option>
          <option value="artkal_s">Artkal S-5mm</option>
          <option value="artkal_c">Artkal C-2.6mm</option>
        </select>
      </div>
      <div class="check-row"><input type="checkbox" id="sDither"><label for="sDither">抖动</label></div>
      <div class="check-row"><input type="checkbox" id="sIcm"><label for="sIcm">高阶优化(ICM)</label></div>
    </div>

    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/></svg>分割默认参数</h3>
      <div class="num-row"><label>默认方法</label>
        <select class="sel" id="sSegMethod">
          <option value="grabcut_rect">GrabCut矩形</option>
          <option value="watershed">分水岭</option>
          <option value="otsu">Otsu</option>
          <option value="slic">SLIC</option>
        </select>
      </div>
      <div class="slider-row"><label>笔触粗细</label><input type="range" id="sBrushSize" min="4" max="40" step="2"><output id="sBrushSizeOut"></output></div>
    </div>

    <div class="panel-card glass">
      <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9.2"/><path d="M12 10v6M12 7v.2"/></svg>关于</h3>
      <div class="num-row"><label>当前版本</label><span id="aboutVersion" style="color:var(--color-foreground);font-weight:700">…</span></div>
      <button class="btn btn-ghost" id="helpBtn2" style="width:100%;margin-top:6px">查看使用指南</button>
      <hr style="border:none;border-top:1px solid var(--color-border);margin:12px 0">
      <div id="updArea">
        <button class="btn btn-primary" id="checkUpdBtn" style="width:100%">检查更新</button>
        <p class="hint" id="updStatus" style="margin-top:8px"></p>
        <div id="updBarWrap" style="display:none;height:8px;border-radius:99px;background:var(--color-surface);overflow:hidden;margin-top:8px">
          <div id="updBar" style="height:100%;width:0%;background:var(--color-primary,#2563eb);transition:width .2s"></div>
        </div>
        <div id="updActions" style="display:none;flex-direction:column;gap:6px;margin-top:8px">
          <button class="btn btn-primary" id="dlUpdBtn" style="width:100%">下载并更新</button>
          <button class="btn btn-primary" id="applyUpdBtn" style="width:100%;display:none">重启以完成更新</button>
        </div>
      </div>
    </div>
  `;

  /* ---- 主题三选 ---- */
  const themeChips = [...$('setTheme').children];
  function syncThemeChips() {
    const m = window.getThemeMode ? window.getThemeMode() : 'system';
    themeChips.forEach(c => c.classList.toggle('on', c.dataset.t === m));
  }
  $('setTheme').addEventListener('click', (e) => {
    const c = e.target.closest('.chip'); if (!c) return;
    if (window.setThemeMode) window.setThemeMode(c.dataset.t);
    syncThemeChips();
    save({ theme: c.dataset.t });
  });
  syncThemeChips();

  /* ---- 背景皮肤（图片换肤）---- */
  let _skinStamp = Date.now();   // 壁纸缓存戳：每次导入成功后刷新，确保背景/缩略图换新图
  // 透明度单一共用值（跟随当前亮度初始化；旧 skinOpacityLight/Dark 迁移读取）
  function _skinOp() {
    if (_settings.skinOpacity != null) return _settings.skinOpacity;
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    const legacy = dark ? _settings.skinOpacityDark : _settings.skinOpacityLight;
    return legacy != null ? legacy : (dark ? 0.25 : 0.15);
  }
  function _skinBlur() { return _settings.skinBlur != null ? _settings.skinBlur : 1; }
  function _skinCfg() {
    return {
      url: _settings.skinImage ? ('/api/skin/image?t=' + _skinStamp) : '',
      color: _settings.skinColor || '',
      accent: _settings.skinAccent || '',
      op: _skinOp(),
      blur: _skinBlur(),
    };
  }
  function _applySkinNow() { if (window.skinApply) window.skinApply(_skinCfg()); }
  function _syncSkinUI() {
    const on = !!_settings.skinImage;
    $('skinThumb').style.display = on ? '' : 'none';
    $('skinThumb').src = on ? '/api/skin/image?t=' + _skinStamp : '';
    $('skinNone').style.display = on ? 'none' : '';
    $('skinRemoveBtn').style.display = on ? '' : 'none';
    $('skinImportBtn').textContent = on ? '更换图片' : '导入图片';
    $('skinOpArea').style.display = on ? '' : 'none';
    const op = _skinOp();
    $('skinOpacity').value = Math.round(op * 100);
    $('skinOpacityOut').textContent = Math.round(op * 100) + '%';
    if ($('skinBlur')) {
      $('skinBlur').value = _skinBlur();
      $('skinBlurOut').textContent = ['无', '中', '高'][_skinBlur()];
    }
    $('skinHint').innerHTML = _settings.skinColor
      ? `已识别主体颜色 <span style="display:inline-block;width:12px;height:12px;border-radius:4px;background:${_settings.skinColor};border:1px solid var(--color-border);vertical-align:-1px"></span> <b>${_settings.skinColor}</b>，整套主题色已跟随适配。`
      : (on ? '未识别到主体颜色，仅更换了背景。' : '导入图片作半透明背景，并自动提取主体颜色定制整套主题色。');
  }
  $('skinImportBtn').addEventListener('click', () => $('skinFile').click());
  $('skinFile').addEventListener('change', async () => {
    const f = $('skinFile').files && $('skinFile').files[0];
    $('skinFile').value = '';
    if (!f) return;
    try {
      if (window.busy) window.busy.start('导入皮肤…');
      const r = await API.uploadSkin(f);
      _settings.skinImage = 'custom_skin.jpg';
      _settings.skinColor = r.color || '';
      _settings.skinAccent = (r.colors && r.colors[1]) || '';
      _skinStamp = Date.now();   // 刷新缓存戳：skin.js 检测到 URL 变化才会重设背景
      await save({ skinImage: _settings.skinImage, skinColor: _settings.skinColor, skinAccent: _settings.skinAccent });
      _syncSkinUI();
      _applySkinNow();
      if (window.busy) window.busy.done('皮肤已应用');
    } catch (e) {
      if (window.fail) window.fail('皮肤导入失败: ' + e.message);
    }
  });
  $('skinRemoveBtn').addEventListener('click', async () => {
    try { await API.removeSkin(); } catch (e) { /* 静默 */ }
    _settings.skinImage = ''; _settings.skinColor = ''; _settings.skinAccent = '';
    await save({ skinImage: '', skinColor: '', skinAccent: '' });
    _syncSkinUI();
    _applySkinNow();
  });
  window.bindEditable('skinOpacity', 'skinOpacityOut', { fmt: v => v + '%', onChange: (v) => {
    _settings.skinOpacity = v / 100;
    save({ skinOpacity: _settings.skinOpacity });
    _applySkinNow();
  }});
  /* 背景模糊三档吸附滑块（无/中/高）：step=1 天然吸附，切档即时生效 */
  if ($('skinBlur')) {
    $('skinBlur').addEventListener('input', () => {
      const lvl = Math.round(parseFloat($('skinBlur').value));
      $('skinBlurOut').textContent = ['无', '中', '高'][lvl];
    });
    $('skinBlur').addEventListener('change', () => {
      const lvl = Math.round(parseFloat($('skinBlur').value));
      _settings.skinBlur = lvl;
      save({ skinBlur: lvl });
      _applySkinNow();
    });
  }
  /* 皮肤文件缺失（被外部删除等）→ 清配置并同步卡片（skin.js 探测到 onerror 调用） */
  window.onSkinMissing = () => {
    _settings.skinImage = ''; _settings.skinColor = ''; _settings.skinAccent = '';
    save({ skinImage: '', skinColor: '', skinAccent: '' });
    _syncSkinUI();
  };

  /* ---- 默认参数：读 / 存 settings.json ---- */
  let _settings = {};
  function _fillForm(s) {
    $('sWidth').value = s.width;
    $('sKeepRatio').checked = !!s.keepRatio;
    $('sMaxColors').value = s.maxColors;
    $('sSalience').value = s.salience;
    $('sSalienceOut').textContent = (+s.salience).toFixed(1);
    $('sMetric').value = s.metric;
    $('sBrand').value = s.brand;
    $('sDither').checked = !!s.dither;
    $('sIcm').checked = !!s.icm;
    $('sSegMethod').value = s.segMethod;
    $('sBrushSize').value = s.brushSize;
    $('sBrushSizeOut').textContent = s.brushSize;
  }
  function _collect() {
    return {
      width: +$('sWidth').value, keepRatio: $('sKeepRatio').checked,
      maxColors: +$('sMaxColors').value, salience: +$('sSalience').value,
      metric: $('sMetric').value, brand: $('sBrand').value,
      dither: $('sDither').checked, icm: $('sIcm').checked,
      segMethod: $('sSegMethod').value, brushSize: +$('sBrushSize').value,
      theme: window.getThemeMode ? window.getThemeMode() : 'system',
    };
  }
  async function save(partial) {
    _settings = { ..._settings, ...(partial || _collect()) };
    try { await API.saveSettings(_settings); } catch (e) { /* 静默 */ }
  }
  window.saveSettings = save;   // 供 app.js 等非设置模块持久化单项（如豆子风格）
  /* 把默认参数灌进图纸/分割参数卡（首次加载取一次快照） */
  function _applyDefaultsToPanels(s) {
    const set = (id, v) => { const el = $(id); if (el == null || v == null) return;
      if (el.type === 'checkbox') el.checked = !!v; else el.value = v;
      el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); };
    set('wBeads', s.width); set('keepRatio', s.keepRatio); set('maxColors', s.maxColors);
    set('salience', s.salience); set('colorMetric', s.metric); set('brandSel', s.brand);
    set('dither', s.dither); set('icmOn', s.icm); set('maskBg', s.maskBg);
    set('beadStyle', s.beadStyle);
    set('segMethod', s.segMethod); set('brushSize', s.brushSize);
  }
  async function loadSettings() {
    try {
      const r = await API.getSettings();
      _settings = r.settings || {};
      _fillForm(_settings);
      _applyDefaultsToPanels(_settings);
      // 主题以 settings.json 为准（若与 localStorage 不一致）
      if (_settings.theme && window.setThemeMode) { window.setThemeMode(_settings.theme); syncThemeChips(); }
      // 皮肤：同步卡片 UI 并按配置即时应用（免重启生效）
      _syncSkinUI();
      _applySkinNow();
    } catch (e) { /* 后端未就绪 */ }
  }

  // 设置项改动即保存
  ['sWidth','sKeepRatio','sMaxColors','sMetric','sBrand','sDither','sIcm','sSegMethod']
    .forEach(id => $(id).addEventListener('change', () => save()));
  window.bindEditable('sSalience', 'sSalienceOut', { fmt: v => (+v).toFixed(1), onChange: () => save() });
  window.bindEditable('sBrushSize', 'sBrushSizeOut', { fmt: v => v, onChange: () => save() });

  /* ---- 关于：版本 + 使用指南 ---- */
  (async () => {
    try { const r = await API.getVersion(); $('aboutVersion').textContent = 'v' + r.version; }
    catch (e) { $('aboutVersion').textContent = '未知'; }
  })();
  $('helpBtn2').addEventListener('click', () => {
    // 指南 modal 层级低于设置抽屉，先收起设置再呼出指南，避免被挡住
    if (window.closeSettings) window.closeSettings();
    if (window.openHelp) window.openHelp();
  });

  /* ---- 检查更新 / 在线更新 ---- */
  const updStatus = $('updStatus');
  const isPywebview = !!(window.pywebview && window.pywebview.api);
  $('checkUpdBtn').addEventListener('click', async () => {
    updStatus.textContent = '正在检查更新…';
    $('updActions').style.display = 'none';
    try {
      const r = await API.updateCheck();
      if (r.has_update) {
        updStatus.innerHTML = `发现新版本 <b>v${r.latest}</b>（当前 v${r.current}）` +
          (r.notes ? `<br><span style="white-space:pre-wrap">${r.notes.slice(0, 400)}</span>` : '');
        if (r.asset_url && isPywebview) {
          $('updActions').style.display = 'flex';
          $('dlUpdBtn').style.display = '';
          $('applyUpdBtn').style.display = 'none';
        } else if (r.asset_url) {
          updStatus.innerHTML += `<br><a href="${r.release_url}" target="_blank">前往下载页面手动更新</a>`;
        } else {
          updStatus.innerHTML += '<br>未找到 Windows 安装包，请前往 Release 页面下载。';
        }
      } else {
        updStatus.textContent = `已是最新版本（v${r.current}）`;
      }
    } catch (e) { updStatus.textContent = '检查失败: ' + e.message; }
  });
  $('dlUpdBtn').addEventListener('click', async () => {
    try {
      await API.updateDownload();
      $('dlUpdBtn').style.display = 'none';
      $('updBarWrap').style.display = 'block';
      pollProgress();
    } catch (e) { updStatus.textContent = '下载失败: ' + e.message; }
  });
  async function pollProgress() {
    const t = setInterval(async () => {
      try {
        const p = await API.updateProgress();
        $('updBar').style.width = (p.percent || 0) + '%';
        if (p.status === 'ready') {
          clearInterval(t);
          updStatus.textContent = `新版本 v${p.latest} 已就绪`;
          $('applyUpdBtn').style.display = '';
        } else if (p.status === 'error') {
          clearInterval(t);
          updStatus.textContent = '下载出错: ' + p.error;
          $('dlUpdBtn').style.display = '';
        } else {
          updStatus.textContent = p.status === 'extracting' ? '正在解压…' : `下载中 ${p.percent}%`;
        }
      } catch (e) { clearInterval(t); updStatus.textContent = '进度查询失败: ' + e.message; }
    }, 500);
  }
  $('applyUpdBtn').addEventListener('click', async () => {
    updStatus.textContent = '正在重启并应用更新…';
    try { await API.updateApply(); } catch (e) { /* 进程退出，连接断开属正常 */ }
  });

  loadSettings();
})();
