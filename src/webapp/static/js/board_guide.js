/* 图纸画板新手引导：首次进入自动显示，也可从画板工具栏再次打开。 */
(function () {
  const KEY = 'pbd-board-guide-seen-v1';
  const pages = [
    {
      icon: '＋', title: '上传与更换底图',
      body: '在左侧「参考底图」中点「上传底图」。已有底图时，同一按钮会显示「更换底图…」，选择新图片即可替换。',
      gesture: '鼠标操作：左键点按钮并选择图片。',
    },
    {
      icon: '↔', title: '调透明度与底图位置',
      body: '拖动「不透明度」滑块改变底图深浅。点「调整底图」后，滚轮缩放底图、按住鼠标中键拖动平移；点「保存调整」生效，点「取消」还原。',
      gesture: '鼠标操作：左键拖滑块；滚轮缩放；中键拖动。',
    },
    {
      icon: '✎', title: '绘制、换色与撤销',
      body: '左键点击或拖动绘制，中键拖动平移、滚轮缩放画板。工具区可换画笔／橡皮／填充／框选；拖「笔触粗细」换笔触，点色板换颜色。画错点撤销，也可重做。',
      gesture: '鼠标操作：左键绘制和选色；中键只移动视野。',
    },
    {
      icon: '⇩', title: '导出图纸',
      body: '在「导出图纸」中勾选真实风／图纸风，填写文件名；需要独立清单可勾选 BOM CSV。最后点「导出 PNG」，文件保存到当前输出目录。',
      gesture: '鼠标操作：逐项左键选择，最后点导出按钮。',
    },
  ];
  let index = 0;

  function ensureModal() {
    let mask = document.getElementById('boardGuideModal');
    if (mask) return mask;
    mask = document.createElement('div');
    mask.id = 'boardGuideModal';
    mask.className = 'modal-mask board-guide-mask';
    mask.innerHTML = `
      <section class="board-guide glass" role="dialog" aria-modal="true" aria-labelledby="boardGuideTitle">
        <header><h2>图纸画板 · 新手引导</h2><button class="icon-btn" id="boardGuideClose" aria-label="关闭引导">×</button></header>
        <div class="board-guide-icon" id="boardGuideIcon"></div>
        <h3 id="boardGuideTitle"></h3>
        <p id="boardGuideBody"></p>
        <div class="board-guide-gesture" id="boardGuideGesture"></div>
        <div class="board-guide-dots" id="boardGuideDots"></div>
        <footer><button class="btn btn-ghost" id="boardGuidePrev">跳过</button><button class="btn btn-primary" id="boardGuideNext">下一步</button></footer>
      </section>`;
    document.body.appendChild(mask);
    const close = () => { mask.classList.remove('show'); localStorage.setItem(KEY, '1'); };
    document.getElementById('boardGuideClose').addEventListener('click', close);
    mask.addEventListener('click', e => { if (e.target === mask) close(); });
    document.getElementById('boardGuidePrev').addEventListener('click', () => {
      if (index === 0) close();
      else { index--; render(); }
    });
    document.getElementById('boardGuideNext').addEventListener('click', () => {
      if (index === pages.length - 1) close();
      else { index++; render(); }
    });
    return mask;
  }

  function render() {
    const p = pages[index];
    document.getElementById('boardGuideIcon').textContent = p.icon;
    document.getElementById('boardGuideTitle').textContent = p.title;
    document.getElementById('boardGuideBody').textContent = p.body;
    document.getElementById('boardGuideGesture').textContent = p.gesture;
    document.getElementById('boardGuideDots').innerHTML = pages.map((_, i) =>
      `<span class="${i === index ? 'on' : ''}"></span>`).join('');
    document.getElementById('boardGuidePrev').textContent = index ? '上一步' : '跳过';
    document.getElementById('boardGuideNext').textContent = index === pages.length - 1 ? '开始绘制' : '下一步';
  }

  function show() {
    index = 0;
    ensureModal().classList.add('show');
    render();
  }

  window.BoardGuide = {
    show,
    showIfFirstUse() {
      if (localStorage.getItem(KEY) === '1') return;
      show();
    },
  };
})();
