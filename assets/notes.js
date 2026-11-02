// Runtime for generated study pages: page routing, search, progress, reading mode, printing.
// Progress and the reading mode live only in this browser (localStorage, best effort).
'use strict';
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const body = document.body;
  const storeKey = body.dataset.store || 'study-notes';
  const code = body.dataset.code || '';

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(storeKey) || '{}') || {}; } catch (e) { saved = {}; }
  const pages = $$('.page');
  const pageIds = pages.map(p => p.id);
  const lectures = pages.filter(p => p.dataset.lecture === '1').map(p => p.id);
  let completed = Array.isArray(saved.completed) ? saved.completed.filter(id => lectures.includes(id)) : [];
  let lang = saved.lang === 'zh' ? 'zh' : 'both';
  function save() {
    try { localStorage.setItem(storeKey, JSON.stringify({ completed, lang })); } catch (e) { /* storage unavailable */ }
  }

  // ---- reading mode: Chinese + English, or Chinese only ----
  const langBtn = $('#lang-toggle');
  function applyLang() {
    body.classList.toggle('zh-only', lang === 'zh');
    if (langBtn) {
      langBtn.setAttribute('aria-pressed', String(lang === 'zh'));
      langBtn.textContent = lang === 'zh' ? '显示英文' : '只看中文';
    }
  }
  if (langBtn) langBtn.addEventListener('click', () => { lang = lang === 'zh' ? 'both' : 'zh'; save(); applyLang(); });

  // ---- progress ----
  function updateProgress() {
    const total = lectures.length;
    const done = lectures.filter(id => completed.includes(id)).length;
    const text = $('#progress-text');
    if (text) text.textContent = `你的复习进度 · ${done} / ${total}`;
    const fill = $('#progress-fill');
    if (fill) fill.style.width = `${total ? done / total * 100 : 0}%`;
    const bar = $('.progressbar');
    if (bar) bar.setAttribute('aria-valuenow', String(done));
    $$('[data-complete]').forEach(b => {
      const on = completed.includes(b.dataset.complete);
      b.classList.toggle('completed', on);
      b.setAttribute('aria-pressed', String(on));
      b.textContent = on ? '✓ 已复习 · 点击撤销' : '标记本讲已复习';
    });
    lectures.forEach(id => {
      const mark = $(`#nav a[data-page="${CSS.escape(id)}"] .done`);
      if (mark) mark.textContent = completed.includes(id) ? '✓' : '';
    });
  }
  $$('[data-complete]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.complete;
    completed = completed.includes(id) ? completed.filter(x => x !== id) : [...completed, id];
    save(); updateProgress();
  }));

  // ---- routing ----
  function closeMenu() {
    body.classList.remove('menu-open');
    const t = $('.menu-toggle');
    if (t) t.setAttribute('aria-expanded', 'false');
  }
  function route() {
    let id = decodeURIComponent(location.hash.slice(1)) || pageIds[0];
    if (id === 'main') { $('#main').scrollIntoView(); return; }
    if (!pageIds.includes(id)) id = pageIds[0];
    pages.forEach(p => { p.hidden = p.id !== id; });
    $$('#nav a').forEach(a => {
      const on = a.dataset.page === id;
      a.classList.toggle('active', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    const page = document.getElementById(id);
    $('#breadcrumb').textContent = page.dataset.title;
    document.title = `${page.dataset.title} · ${code} 复习手册`;
    closeMenu();
    $('#search-results').hidden = true;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  window.addEventListener('hashchange', route);

  // in-page table of contents
  $$('[data-jump]').forEach(b => b.addEventListener('click', () => {
    const target = document.getElementById(b.dataset.jump);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));

  // menu, keyboard, start button, print
  const toggle = $('.menu-toggle');
  if (toggle) toggle.addEventListener('click', () => {
    const on = body.classList.toggle('menu-open');
    toggle.setAttribute('aria-expanded', String(on));
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeMenu(); $('#search-results').hidden = true; }
  });
  const start = $('#start');
  if (start) start.addEventListener('click', () => {
    location.hash = lectures.find(id => !completed.includes(id)) || lectures[0];
  });
  const printBtn = $('#print');
  if (printBtn) printBtn.addEventListener('click', () => window.print());
  let printState = [];
  window.addEventListener('beforeprint', () => {
    printState = $$('details').map(d => [d, d.open]);
    $$('details').forEach(d => { d.open = true; });
  });
  window.addEventListener('afterprint', () => { printState.forEach(([d, open]) => { d.open = open; }); });

  // ---- search ----
  const searchIndex = pages.filter(p => p.id !== pageIds[0]).map(p => ({
    id: p.id, title: p.dataset.title, text: p.textContent.replace(/\s+/g, ' ')
  }));
  const input = $('#search');
  const results = $('#search-results');
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    results.replaceChildren();
    results.hidden = !q;
    if (!q) return;
    let n = 0;
    searchIndex.forEach(entry => {
      const lower = entry.text.toLowerCase();
      const pos = lower.indexOf(q);
      if (pos < 0) return;
      let count = 0, i = pos;
      while (i >= 0 && count < 99) { count++; i = lower.indexOf(q, i + q.length); }
      n++;
      const a = document.createElement('a');
      a.href = '#' + entry.id;
      a.textContent = `${entry.title}（${count} 处）`;
      const s = document.createElement('small');
      s.textContent = '…' + entry.text.slice(Math.max(0, pos - 25), pos + 90) + '…';
      a.appendChild(s);
      a.addEventListener('click', () => { results.hidden = true; if (location.hash === '#' + entry.id) route(); });
      results.appendChild(a);
    });
    if (!n) {
      const p = document.createElement('p');
      p.textContent = '没有找到。换个关键词试试，比如「Adam」「softmax」或「KV 缓存」。';
      results.appendChild(p);
    }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.searchbox')) results.hidden = true; });

  applyLang();
  updateProgress();
  route();
  window.addEventListener('load', () => { if (location.hash) window.scrollTo({ top: 0, behavior: 'instant' }); });
})();
