/* 后端 API 客户端：所有调用集中在此，图像走 Blob/objectURL，参数走 JSON。 */
const API = (() => {
  async function _json(path, obj) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(obj ?? {}),
    });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || ('HTTP ' + r.status)); }
    return r.json();
  }
  async function _blobUrl(path, obj) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(obj ?? {}),
    });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || ('HTTP ' + r.status)); }
    return URL.createObjectURL(await r.blob());
  }
  async function _upload(path, fields) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    const r = await fetch(path, { method: 'POST', body: fd });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || ('HTTP ' + r.status)); }
    return r;
  }
  async function _uploadUrl(path, fields) {
    const r = await _upload(path, fields);
    return URL.createObjectURL(await r.blob());
  }
  async function _get(path) {
    const r = await fetch(path);
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || ('HTTP ' + r.status)); }
    return r.json();
  }

  return {
    status: () => _get('/api/status'),
    loadImageFile: (file) => _uploadUrl('/api/image/load', { file }),
    loadImagePath: (path) => _blobUrl('/api/image/load_path', { path }),
    currentImageUrl: () => '/api/image/current',
    getSourceName: () => _get('/api/image/source_name'),
    originalImageUrl: () => '/api/image/original',
    resetImage: () => _blobUrl('/api/image/reset', {}),
    basic: (op) => _blobUrl('/api/image/basic', op),
    setMetric: (metric) => _json('/api/pattern/metric', { metric }),
    setBrand: (brand) => _json('/api/pattern/brand', { brand }),
    getOutputDir: () => _get('/api/output_dir'),
    setOutputDir: (path) => _json('/api/output_dir', { path }),
    grabcutInitRect: (x, y, w, h) => _blobUrl('/api/segment/grabcut/init/rect', { x, y, w, h }),
    grabcutInitMask: (maskBlob) => _uploadUrl('/api/segment/grabcut/init/mask', { file: maskBlob }),
    grabcutRefine: (fgdBlob, bgdBlob) => {
      const f = {}; if (fgdBlob) f.fgd = fgdBlob; if (bgdBlob) f.bgd = bgdBlob;
      return _uploadUrl('/api/segment/grabcut/refine', f);
    },
    segmentAuto: (req) => _blobUrl('/api/segment/auto', req),
    segmentMorph: (op, kernel, shape) => _blobUrl('/api/segment/morph', { op, kernel, shape }),
    segmentMorphUndo: () => _blobUrl('/api/segment/morph/undo', {}),
    segmentMorphRedo: () => _blobUrl('/api/segment/morph/redo', {}),
    maskUrl: () => '/api/segment/mask',
    appliedUrl: () => '/api/segment/applied',
    segmentApply: () => _blobUrl('/api/segment/apply', {}),
    overlayUrl: () => '/api/segment/overlay',
    patternGenerate: (req) => _json('/api/pattern/generate', req),
    patternChart: (req) => _blobUrl('/api/pattern/chart', req ?? {}),
    patternBom: () => _get('/api/pattern/bom'),
    patternPreview: (px) => '/api/pattern/preview?bead_pixel_size=' + (px || 10),
    export: (req) => _json('/api/export', req),
    getVersion: () => _get('/api/version'),
    getSettings: () => _get('/api/settings'),
    saveSettings: (settings) => _json('/api/settings', { settings }),
    updateCheck: () => _get('/api/update/check'),
    updateDownload: () => _json('/api/update/download', {}),
    updateProgress: () => _get('/api/update/progress'),
    updateApply: () => _json('/api/update/apply', {}),
    uploadSkin: async (file) => (await _upload('/api/skin/upload', { file })).json(),
    removeSkin: () => _json('/api/skin/remove', {}),
    skinImageUrl: () => '/api/skin/image?t=' + Date.now(),
    // ---- 图纸画板 board ----
    boardNew: (size, brand) => _json('/api/board/new', { size, brand }),
    boardState: () => _get('/api/board/state'),
    boardStroke: (cells, code) => _json('/api/board/stroke', { cells, code }),
    boardFill: (x, y, code) => _json('/api/board/fill', { x, y, code }),
    boardUndo: () => _json('/api/board/undo', {}),
    boardRedo: () => _json('/api/board/redo', {}),
    boardClear: () => _json('/api/board/clear', {}),
    boardBaseLoad: (file) => _upload('/api/board/base/load', { file }).then(r => r.json()),
    boardBaseImageUrl: () => '/api/board/base/image?t=' + Date.now(),
    boardBaseOptions: (visible, opacity, offx, offy, scale) => _json('/api/board/base/options', { visible, opacity, offx, offy, scale }),
    boardBaseClear: () => _json('/api/board/base/clear', {}),
    boardExport: (req) => _json('/api/board/export', req),
  };
})();
