(() => {
  'use strict';

  const VERSION = 'app-nav-v1';
  const SAFE_PATHS = new Set(['/beranda', '/cari', '/layanan', '/pesanan', '/profil']);
  const IDLE_PREFETCH_PATHS = new Set(['/cari', '/layanan', '/pesanan', '/profil']);
  const PARTIAL_SOURCE_VIEWS = new Set(['home', 'search']);
  const CACHE_TTL_MS = 30000;
  const CACHE_LIMIT = 6;
  const pageCache = new Map();
  let navigationController = null;
  let navigationSequence = 0;

  function normalizeUrl(value) {
    try {
      return new URL(value, window.location.href);
    } catch (_) {
      return null;
    }
  }

  function isSafeUrl(url) {
    return Boolean(
      url &&
      url.origin === window.location.origin &&
      SAFE_PATHS.has(url.pathname)
    );
  }

  function currentView() {
    return document.documentElement.dataset.bdAppView ||
      document.querySelector('meta[name="bd-app-view"]')?.content ||
      '';
  }

  function canPartialFromCurrentView() {
    return PARTIAL_SOURCE_VIEWS.has(currentView());
  }

  function cacheKey(url) {
    return `${url.pathname}${url.search}`;
  }

  function trimCache() {
    while (pageCache.size > CACHE_LIMIT) {
      const first = pageCache.keys().next().value;
      pageCache.delete(first);
    }
  }

  function getFreshEntry(key) {
    const entry = pageCache.get(key);
    if (!entry) return null;
    if ((Date.now() - entry.createdAt) > CACHE_TTL_MS) {
      pageCache.delete(key);
      return null;
    }
    return entry;
  }

  async function requestPage(url, {signal, prefetch = false} = {}) {
    const key = cacheKey(url);
    const cached = getFreshEntry(key);
    if (cached?.html) return cached;
    if (cached?.promise && cached.prefetch) return cached.promise;
    if (cached?.promise && prefetch) return cached.promise;

    const promise = fetch(url.href, {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'follow',
      signal,
      headers: {
        'X-BD-App-Nav': VERSION,
        'Accept': 'text/html,application/xhtml+xml'
      }
    }).then(async (response) => {
      const html = await response.text();
      const entry = {
        html,
        responseUrl: response.url || url.href,
        ok: response.ok,
        createdAt: Date.now()
      };
      pageCache.set(key, entry);
      trimCache();
      if (prefetch) warmStaticImages(html);
      return entry;
    }).catch((error) => {
      const active = pageCache.get(key);
      if (active?.promise === promise) pageCache.delete(key);
      throw error;
    });

    if (prefetch) {
      pageCache.set(key, {promise, prefetch: true, createdAt: Date.now()});
      trimCache();
    }
    return promise;
  }

  function warmStaticImages(html) {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection?.saveData) return;
    if (String(connection?.effectiveType || '').includes('2g')) return;

    let doc;
    try {
      doc = new DOMParser().parseFromString(html, 'text/html');
    } catch (_) {
      return;
    }

    const urls = [];
    doc.querySelectorAll('img[src]').forEach((img) => {
      const src = img.getAttribute('src');
      if (src && src.startsWith('/static/perf/') && !urls.includes(src)) urls.push(src);
    });

    urls.slice(0, 4).forEach((src) => {
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.as = 'image';
      link.href = src;
      link.dataset.bdNavPrefetch = '1';
      link.addEventListener('load', () => link.remove(), {once: true});
      link.addEventListener('error', () => link.remove(), {once: true});
      document.head.appendChild(link);
      window.setTimeout(() => link.remove(), 10000);
    });
  }

  function prefetchUrl(value) {
    const url = normalizeUrl(value);
    if (!isSafeUrl(url)) return;
    if (url.pathname === window.location.pathname && url.search === window.location.search) return;
    requestPage(url, {prefetch: true}).catch(() => {});
  }

  function pageDocument(entry) {
    if (!entry?.ok || !entry.html) return null;
    const doc = new DOMParser().parseFromString(entry.html, 'text/html');
    if (!doc.querySelector('meta[name="bd-app-nav"][content="v1"]')) return null;
    if (!doc.querySelector('[data-bd-app-root]')) return null;
    if (!doc.querySelector('[data-bd-bottom-nav]')) return null;
    if (!doc.querySelector('style[data-bd-page-style]')) return null;
    return doc;
  }

  function syncPageStyle(doc) {
    const current = document.querySelector('style[data-bd-page-style]');
    const next = doc.querySelector('style[data-bd-page-style]');
    if (!current || !next) return false;
    current.textContent = next.textContent;
    return true;
  }

  function syncHead(doc) {
    document.title = doc.title || document.title;

    const nextTheme = doc.querySelector('meta[name="theme-color"]');
    const currentTheme = document.querySelector('meta[name="theme-color"]');
    if (nextTheme && currentTheme) currentTheme.content = nextTheme.content;

    doc.querySelectorAll('link[rel="stylesheet"][href]').forEach((link) => {
      const href = link.getAttribute('href');
      if (!href || href.includes('/static/nav/app-nav-v1.css')) return;
      const absolute = new URL(href, window.location.href).href;
      const exists = Array.from(document.querySelectorAll('link[rel="stylesheet"][href]'))
        .some((existing) => existing.href === absolute);
      if (!exists) {
        const copy = document.createElement('link');
        copy.rel = 'stylesheet';
        copy.href = absolute;
        if (link.crossOrigin) copy.crossOrigin = link.crossOrigin;
        document.head.appendChild(copy);
      }
    });

    const view = doc.querySelector('meta[name="bd-app-view"]')?.content || '';
    if (view) {
      document.documentElement.dataset.bdAppView = view;
      const currentViewMeta = document.querySelector('meta[name="bd-app-view"]');
      if (currentViewMeta) currentViewMeta.content = view;
    }
  }

  function syncAttributes(current, target, marker) {
    Array.from(current.attributes).forEach((attr) => {
      if (attr.name !== marker) current.removeAttribute(attr.name);
    });
    Array.from(target.attributes).forEach((attr) => {
      if (attr.name !== marker) current.setAttribute(attr.name, attr.value);
    });
    current.setAttribute(marker, '1');
  }

  function syncPersistentShell(doc) {
    const currentRoot = document.querySelector('[data-bd-app-root]');
    const targetRoot = doc.querySelector('[data-bd-app-root]');
    const currentNav = document.querySelector('[data-bd-bottom-nav]');
    const targetNav = doc.querySelector('[data-bd-bottom-nav]');
    if (!currentRoot || !targetRoot || !currentNav || !targetNav) return false;

    const targetNavInsideRoot = targetNav.parentElement === targetRoot;
    targetNav.remove();
    targetRoot.querySelectorAll('script').forEach((script) => script.remove());

    currentNav.remove();

    syncAttributes(currentRoot, targetRoot, 'data-bd-app-root');
    const children = Array.from(targetRoot.childNodes).map((node) => document.importNode(node, true));
    currentRoot.replaceChildren(...children);

    syncAttributes(currentNav, targetNav, 'data-bd-bottom-nav');
    currentNav.innerHTML = targetNav.innerHTML;

    if (targetNavInsideRoot) {
      currentRoot.appendChild(currentNav);
    } else {
      currentRoot.insertAdjacentElement('afterend', currentNav);
    }

    return true;
  }

  function runInlinePageScripts(doc, url) {
    const scripts = Array.from(doc.querySelectorAll('body script:not([src])'))
      .filter((script) => !script.type || script.type === 'text/javascript' || script.type === 'application/javascript');

    for (const script of scripts) {
      const code = script.textContent || '';
      if (!code.trim()) continue;
      const runner = new Function(`${code}\n//# sourceURL=${url.pathname.replace(/\W+/g, '_')}_partial.js`);
      runner();
    }
  }

  function saveCurrentScrollState() {
    const state = Object.assign({}, history.state || {}, {
      bdAppNav: VERSION,
      scrollY: window.scrollY
    });
    history.replaceState(state, '', window.location.href);
  }

  function restoreScroll(url, scrollY) {
    requestAnimationFrame(() => {
      if (url.hash) {
        const target = document.getElementById(url.hash.slice(1));
        if (target) {
          target.scrollIntoView({block: 'start'});
          return;
        }
      }
      window.scrollTo({top: Number(scrollY || 0), left: 0, behavior: 'auto'});
    });
  }

  function fallbackNavigate(value, {replace = false} = {}) {
    if (replace) {
      window.location.replace(value);
      return;
    }
    window.location.assign(value);
  }

  async function navigate(value, {historyMode = 'push', scrollY = 0} = {}) {
    const url = normalizeUrl(value);
    if (!isSafeUrl(url)) {
      fallbackNavigate(url?.href || value);
      return;
    }

    if (
      historyMode === 'push' &&
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      url.hash === window.location.hash
    ) {
      restoreScroll(url, 0);
      return;
    }

    if (navigationController) navigationController.abort();
    const controller = new AbortController();
    navigationController = controller;
    const sequence = ++navigationSequence;
    document.documentElement.classList.add('bd-nav-loading');

    const started = performance.now();

    try {
      const entry = await requestPage(url, {signal: controller.signal});
      if (sequence !== navigationSequence) return;
      const finalUrl = normalizeUrl(entry.responseUrl) || url;
      if (
        url.hash &&
        finalUrl.pathname === url.pathname &&
        finalUrl.search === url.search
      ) {
        finalUrl.hash = url.hash;
      }
      const doc = pageDocument(entry);
      if (!doc || !isSafeUrl(finalUrl)) {
        fallbackNavigate(entry.responseUrl || url.href, {replace: historyMode === 'pop'});
        return;
      }

      if (!syncPageStyle(doc)) {
        fallbackNavigate(finalUrl.href, {replace: historyMode === 'pop'});
        return;
      }
      syncHead(doc);

      if (!syncPersistentShell(doc)) {
        fallbackNavigate(finalUrl.href, {replace: historyMode === 'pop'});
        return;
      }

      if (historyMode === 'push') {
        saveCurrentScrollState();
        history.pushState({bdAppNav: VERSION, scrollY: 0}, '', finalUrl.href);
      }

      try {
        runInlinePageScripts(doc, finalUrl);
      } catch (scriptError) {
        console.error('[BantuDulu nav] page init failed; using full navigation.', scriptError);
        fallbackNavigate(finalUrl.href, {replace: true});
        return;
      }

      restoreScroll(finalUrl, historyMode === 'pop' ? scrollY : 0);
      document.dispatchEvent(new CustomEvent('bd:app-navigated', {
        detail: {
          url: finalUrl.href,
          durationMs: Math.round(performance.now() - started)
        }
      }));
      scheduleIdlePrefetch();
    } catch (error) {
      if (error?.name !== 'AbortError') {
        console.warn('[BantuDulu nav] partial navigation failed; using full navigation.', error);
        fallbackNavigate(url.href, {replace: historyMode === 'pop'});
      }
    } finally {
      if (sequence === navigationSequence) {
        navigationController = null;
        document.documentElement.classList.remove('bd-nav-loading');
      }
    }
  }

  function anchorFromEvent(event) {
    const target = event.target;
    return target instanceof Element ? target.closest('a[href]') : null;
  }

  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const anchor = anchorFromEvent(event);
    if (!anchor || anchor.target || anchor.hasAttribute('download') || anchor.dataset.noAppNav !== undefined) return;

    const url = normalizeUrl(anchor.href);
    if (!isSafeUrl(url)) return;
    if (!canPartialFromCurrentView()) return;
    if (url.hash && url.pathname === window.location.pathname && url.search === window.location.search) return;

    event.preventDefault();
    navigate(url.href);
  });

  document.addEventListener('pointerover', (event) => {
    if (!canPartialFromCurrentView()) return;
    const anchor = anchorFromEvent(event);
    if (anchor) prefetchUrl(anchor.href);
  }, {passive: true});

  document.addEventListener('touchstart', (event) => {
    if (!canPartialFromCurrentView()) return;
    const anchor = anchorFromEvent(event);
    if (anchor) prefetchUrl(anchor.href);
  }, {passive: true, capture: true});

  document.addEventListener('focusin', (event) => {
    if (!canPartialFromCurrentView()) return;
    const anchor = anchorFromEvent(event);
    if (anchor) prefetchUrl(anchor.href);
  });

  window.addEventListener('popstate', (event) => {
    const url = normalizeUrl(window.location.href);
    if (!isSafeUrl(url) || !canPartialFromCurrentView()) {
      window.location.reload();
      return;
    }
    navigate(url.href, {
      historyMode: 'pop',
      scrollY: event.state?.scrollY || 0
    });
  });

  window.addEventListener('pagehide', () => {
    pageCache.clear();
    if (navigationController) navigationController.abort();
  });

  function idle(callback) {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(callback, {timeout: 1500});
    } else {
      window.setTimeout(callback, 700);
    }
  }

  function scheduleIdlePrefetch() {
    if (!canPartialFromCurrentView()) return;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection?.saveData || String(connection?.effectiveType || '').includes('2g')) return;

    idle(() => {
      const urls = Array.from(document.querySelectorAll('[data-bd-bottom-nav] a[href]'))
        .map((anchor) => normalizeUrl(anchor.href))
        .filter((url) => isSafeUrl(url) && IDLE_PREFETCH_PATHS.has(url.pathname))
        .filter((url) => url.pathname !== window.location.pathname || url.search !== window.location.search);

      urls.slice(0, 3).forEach((url, index) => {
        window.setTimeout(() => prefetchUrl(url.href), index * 350);
      });
    });
  }

  document.documentElement.dataset.bdAppNav = VERSION;
  const initialView = document.querySelector('meta[name="bd-app-view"]')?.content || '';
  if (initialView) document.documentElement.dataset.bdAppView = initialView;
  history.replaceState(Object.assign({}, history.state || {}, {
    bdAppNav: VERSION,
    scrollY: window.scrollY
  }), '', window.location.href);
  scheduleIdlePrefetch();
})();
