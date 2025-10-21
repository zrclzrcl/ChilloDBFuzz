const { createApp, onMounted, ref, reactive, watch, nextTick } = Vue;

createApp({
  setup(){
    const interval = ref(500);
    const maxLines = ref(500);
    const panels = reactive([]);
    let timer = null;

    const tsRegex = /(\b\d{4}[-\/]\d{2}[-\/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b)|(\b\d{2}:\d{2}:\d{2}\b)/g;

    function hueForAge(ageSec){
      if (ageSec <= 2) return 140;       // 0–2s（鲜绿）
      if (ageSec <= 5) return 105;       // 2–5s（青绿→黄绿），拉开与首档差距
      if (ageSec <= 10) return 80;       // 5–10s（黄绿→黄）
      if (ageSec <= 20) return 60;       // 10–20s（黄→橙黄）
      if (ageSec <= 40) return 40;       // 20–40s（橙）
      if (ageSec <= 60) return 25;       // 40–60s（橙红）
      if (ageSec <= 90) return 12;       // 60–90s（红偏橙）
      return 0;                          // ≥90s（红）
    }
    // 发光强度：越新发光越强，越旧越弱
    function glowForAge(ageSec){
      if (ageSec <= 2) return { blur: 12, alpha: 0.9 };
      if (ageSec <= 5) return { blur: 10, alpha: 0.8 };
      if (ageSec <= 10) return { blur: 8, alpha: 0.7 };
      if (ageSec <= 20) return { blur: 6, alpha: 0.6 };
      if (ageSec <= 40) return { blur: 4, alpha: 0.45 };
      if (ageSec <= 60) return { blur: 3, alpha: 0.35 };
      if (ageSec <= 90) return { blur: 2, alpha: 0.25 };
      return { blur: 0, alpha: 0 };
    }
    function bucketLabel(ageSec){
      if (ageSec <= 2) return '0–2秒';
      if (ageSec <= 5) return '2–5秒';
      if (ageSec <= 10) return '5–10秒';
      if (ageSec <= 20) return '10–20秒';
      if (ageSec <= 40) return '20–40秒';
      if (ageSec <= 60) return '40–60秒';
      if (ageSec <= 90) return '60–90秒';
      return '≥90秒';
    }
    function humanSize(bytes){
      if (!bytes || bytes < 0) return '—';
      if (bytes < 1024) return bytes + ' B';
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      const val = (bytes / Math.pow(1024, i)).toFixed(1);
      return val + ' ' + ['B','KB','MB','GB','TB'][i];
    }
    function fmtTime(iso){
      if (!iso) return '—';
      try{ const d = new Date(iso); return d.toLocaleString(); } catch(e){ return iso; }
    }
    function escapeHtml(s){
      return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
    }

    function parseLineAgeSecFromContent(line, now){
      const m = line.match(tsRegex);
      if (!m) return null;
      for (const t of m){
        let d = null;
        if (/^\d{2}:\d{2}:\d{2}$/.test(t)){
          const today = new Date(now);
          const y = today.getFullYear();
          const mo = String(today.getMonth()+1).padStart(2,'0');
          const da = String(today.getDate()).padStart(2,'0');
          d = new Date(`${y}-${mo}-${da}T${t}`);
        }else{
          d = new Date(t.replace(' ', 'T'));
        }
        if (!isNaN(d)){
          return Math.max(0, (now - d)/1000.0);
        }
      }
      return null;
    }

    function colorizeLineObj(lineObj, fallbackHue, now){
      // 严格清洗行首：BOM、CR/LF、各类不可见与全角空白，仅作用于行首，保留行内格式
      const raw = (lineObj?.s ?? '');
      const text = raw
        .replace(/^\uFEFF/, '')                 // BOM
        .replace(/^[\r\n]+/, '')               // 开头换行
        .replace(/^[\s\t\u00A0\uFEFF\u2000-\u200B\u3000]+/, ''); // 行首空白
      let ageSec = null;
      if (lineObj && lineObj.t){
        const dt = new Date(lineObj.t);
        if (!isNaN(dt)) ageSec = Math.max(0, (now - dt)/1000.0);
      }
      if (ageSec == null){
        ageSec = parseLineAgeSecFromContent(text, now);
      }
      const hue = hueForAge(ageSec ?? 999999);
      const effectiveHue = (ageSec == null) ? fallbackHue : hue;
      const glow = glowForAge(ageSec ?? 999999);
      const color = `hsl(${effectiveHue} 100% 55%)`;
      const inner = glow.blur;
      const outer = Math.round(glow.blur * 2);
      const alpha1 = glow.alpha;
      const alpha2 = Math.max(0, Math.min(1, glow.alpha * 0.6));
      const shadow = (glow.blur > 0)
        ? `0 0 ${inner}px hsla(${effectiveHue} 100% 60% / ${alpha1}), 0 0 ${outer}px hsla(${effectiveHue} 100% 60% / ${alpha2})`
        : 'none';
      const escaped = escapeHtml(text);
      const withTs = escaped.replace(tsRegex, (m) => `<span class="timestamp" style="color:${color}; text-shadow:${shadow}">${m}</span>`);
      return `<span style="color:${color}; text-shadow:${shadow}">${withTs}</span>`;
    }

    function rebuildPanelsFromLogs(logs){
      const keys = Object.keys(logs).sort();
      const map = new Map(panels.map(p => [p.key, p]));
      const next = [];
      for (const k of keys){
        const old = map.get(k);
        next.push(old ?? { key:k, filename:'', hue:120, accent:'hsl(120 100% 55%)', bucketLabel:'', mtimeText:'—', sizeText:'—', html:'(加载中...)', visibleRows: null });
      }
      panels.splice(0, panels.length, ...next);
    }


    async function fetchLogs(){
      try{
        const r = await fetch('/api/logs?t='+Date.now(), { cache:'no-store' });
        const data = await r.json();
        const now = new Date(data.now);
        const logs = data.logs || {};
        rebuildPanelsFromLogs(logs);
        await nextTick();
        for (const panel of panels){
          const info = logs[panel.key];
          if (!info) continue;
          panel.filename = (info.path || '').split(/[/\\]/).pop() || '';
          const exists = !!info.exists;
          panel.sizeText = exists ? humanSize(info.size||0) : '不存在';
          panel.mtimeText = exists ? fmtTime(info.mtime) : '—';

          let ageSec = 999999;
          if (exists && info.mtime){
            const mt = new Date(info.mtime);
            ageSec = Math.max(0, (now - mt)/1000.0);
          }
          const hue = hueForAge(ageSec);
          panel.hue = hue;
          panel.accent = `hsl(${hue} 100% 55%)`;
          panel.bucketLabel = bucketLabel(ageSec);

          const all = Array.isArray(info.lines) ? info.lines : [];
          const sliced = all.slice(-Math.min(all.length, maxLines.value));
          const html = sliced.map(obj => colorizeLineObj(obj, hue, now)).join('\n');
          panel.html = html || '<span style="color:#7a8aa3">(空)</span>';
        }
      }catch(e){
        console.error('fetch logs error', e);
      }
    }

    function start(){
      stop();
      timer = setInterval(fetchLogs, interval.value);
    }
    function stop(){ if (timer) { clearInterval(timer); timer=null; } }

    watch(interval, () => start());
    watch(maxLines, () => fetchLogs());

    onMounted(() => {
      fetchLogs();
      start();
      // 移除 computeVisibleRows，避免未定义导致错误；如需在窗口变化时刷新，可仅调用 fetchLogs。
      window.addEventListener('resize', () => {
        fetchLogs();
      });
    });

    return { interval, maxLines, panels };
  }
}).mount('#app');
