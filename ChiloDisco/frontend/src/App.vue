<template>
  <div class="layout">
    <aside class="sidenav">
      <div class="nav-brand">
        <span class="logo">⚡</span>
        <span class="title">ChiloDisco</span>
      </div>
      <nav class="nav-links">
        <a class="active" href="/">日志监控</a>
        <a href="/plot">数据大屏</a>
        <a href="/downloads">结果下载</a>
        <a href="#">系统设置</a>
      </nav>
    </aside>

    <div class="content">
      <header class="app-header">
        <div class="brand">
          <span class="subtitle">AFL++ Custom Mutator · 实时日志监控</span>
        </div>
        <div class="controls">
          <label>刷新频率</label>
          <select v-model.number="interval">
            <option :value="200">0.2s</option>
            <option :value="500">0.5s</option>
            <option :value="1000">1s</option>
            <option :value="2000">2s</option>
            <option :value="5000">5s</option>
            <option :value="10000">10s</option>
          </select>
          <label>显示行数</label>
          <select v-model.number="maxLines">
            <option :value="200">200</option>
            <option :value="300">300</option>
            <option :value="500">500</option>
            <option :value="800">800</option>
          </select>
        </div>
      </header>

      <main class="grid">
        <section class="card" v-for="panel in panels" :key="panel.key" :style="{ '--h': panel.hue }">
          <header class="card-header">
            <div class="name">{{ getDisplayName(panel.key) }}</div>
            <div class="file">{{ panel.filename }}</div>
            <div class="meta">
              <span class="mtime" :title="'最近修改：' + panel.mtimeText">{{ panel.mtimeText }}</span>
              <span class="size" :title="'大小：' + panel.sizeText">{{ panel.sizeText }}</span>
              <span class="recency-dot" :title="'新鲜度：' + panel.bucketLabel" :style="{ color: panel.accent }"></span>
            </div>
          </header>
          <pre class="log-body"><code class="log-lines" v-html="panel.html"></code></pre>
        </section>
      </main>

      <footer class="app-footer">
        <div class="legend">
          <span>数据新鲜度：</span>
          <span class="legend-dot" style="--h:140">0–2s</span>
          <span class="legend-dot" style="--h:105">2–5s</span>
          <span class="legend-dot" style="--h:80">5–10s</span>
          <span class="legend-dot" style="--h:60">10–20s</span>
          <span class="legend-dot" style="--h:40">20–40s</span>
          <span class="legend-dot" style="--h:25">40–60s</span>
          <span class="legend-dot" style="--h:12">60–90s</span>
          <span class="legend-dot" style="--h:0">≥90s</span>
        </div>
        <div class="copyright">© 2025 ChiloDisco</div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, watch, nextTick, onBeforeUnmount } from 'vue'

const interval = ref(2000)
const maxLines = ref(500)
const panels = reactive([])
let timer = null

// 日志键名中文映射
const logNameMap = {
  'LLM_LOG_PATH': 'LLM日志',
  'MAIN_LOG_PATH': '主日志',
  'MUTATOR_FIXER_LOG_PATH': '修复日志',
  'MUTATOR_GENERATOR_LOG_PATH': '生成器日志',
  'PARSER_LOG_PATH': '解析器日志',
  'STRUCTURAL_MUTATOR_LOG_PATH': '结构变异日志'
}

function getDisplayName(key) {
  return logNameMap[key] || key
}

// —— 滚动 & 首次看到时间（会话级）持久化 ——
const STICK_KEY_PREFIX = 'cd_stick_'
const FS_KEY_PREFIX = 'cd_fs_'

function getStick(key){
  try{ const v = sessionStorage.getItem(STICK_KEY_PREFIX + key); return v === null ? true : v === '1' }catch(_){ return true }
}
function setStick(key, val){
  try{ sessionStorage.setItem(STICK_KEY_PREFIX + key, val ? '1' : '0') }catch(_){ /* ignore */ }
}
function loadFS(key){
  try{ const s = sessionStorage.getItem(FS_KEY_PREFIX + key); return s ? JSON.parse(s) : {} }catch(_){ return {} }
}
function saveFS(key, obj){
  try{ sessionStorage.setItem(FS_KEY_PREFIX + key, JSON.stringify(obj)) }catch(_){ /* ignore */ }
}
function isAtBottom(el){ if(!el) return true; return (el.scrollHeight - el.scrollTop - el.clientHeight) <= 8 }
function scrollToBottom(el){ if(!el) return; el.scrollTop = el.scrollHeight }

const tsRegex = /(\b\d{4}[-\/]\d{2}[-\/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b)|(\b\d{2}:\d{2}:\d{2}\b)/g

function hueForAge(ageSec){
  if (ageSec <= 2) return 140 // 0–2s（鲜绿）
  if (ageSec <= 5) return 105 // 2–5s（青绿→黄绿），拉开与首档差距
  if (ageSec <= 10) return 80 // 5–10s（黄绿→黄）
  if (ageSec <= 20) return 60 // 10–20s（黄→橙黄）
  if (ageSec <= 40) return 40 // 20–40s（橙）
  if (ageSec <= 60) return 25 // 40–60s（橙红）
  if (ageSec <= 90) return 12 // 60–90s（红偏橙）
  return 0                    // ≥90s（红）
}
// 发光强度：越新发光越强，越旧越弱
function glowForAge(ageSec){
  if (ageSec <= 2) return { blur: 12, alpha: 0.9 }
  if (ageSec <= 5) return { blur: 10, alpha: 0.8 }
  if (ageSec <= 10) return { blur: 8, alpha: 0.7 }
  if (ageSec <= 20) return { blur: 6, alpha: 0.6 }
  if (ageSec <= 40) return { blur: 4, alpha: 0.45 }
  if (ageSec <= 60) return { blur: 3, alpha: 0.35 }
  if (ageSec <= 90) return { blur: 2, alpha: 0.25 }
  return { blur: 0, alpha: 0 }
}
function bucketLabel(ageSec){
  if (ageSec <= 2) return '0–2秒'
  if (ageSec <= 5) return '2–5秒'
  if (ageSec <= 10) return '5–10秒'
  if (ageSec <= 20) return '10–20秒'
  if (ageSec <= 40) return '20–40秒'
  if (ageSec <= 60) return '40–60秒'
  if (ageSec <= 90) return '60–90秒'
  return '≥90秒'
}
function humanSize(bytes){
  if (!bytes || bytes < 0) return '—'
  if (bytes < 1024) return bytes + ' B'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const val = (bytes / Math.pow(1024, i)).toFixed(1)
  return val + ' ' + ['B','KB','MB','GB','TB'][i]
}
function fmtTime(iso){
  if (!iso) return '—'
  try{ const d = new Date(iso); return d.toLocaleString(); } catch(e){ return iso; }
}
function escapeHtml(s){
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]))
}

function parseLineAgeSecFromContent(line, now){
  const m = line.match(tsRegex)
  if (!m) return null
  for (const t of m){
    let d = null
    if (/^\d{2}:\d{2}:\d{2}$/.test(t)){
      const today = new Date(now)
      const y = today.getFullYear()
      const mo = String(today.getMonth()+1).padStart(2,'0')
      const da = String(today.getDate()).padStart(2,'0')
      d = new Date(`${y}-${mo}-${da}T${t}`)
    }else{
      d = new Date(t.replace(' ', 'T'))
    }
    if (!isNaN(d)){
      return Math.max(0, (now - d)/1000.0)
    }
  }
  return null
}

function colorizeLineObj(lineObj, fallbackHue, now){
  // 去除可能的 BOM、行首异常空白（含 NBSP、FEFF、Tab）、以及首部多余换行；保留行内空白
  const raw = (lineObj?.s ?? '')
  const cleaned = raw
    .replace(/^\uFEFF/, '')              // 去 BOM
    .replace(/^[\s\u00A0\uFEFF\t]+/, '') // 去行首空白（空格/Tab/NBSP/FEFF）
    .replace(/^[\r\n]+/, '')            // 去首部多余换行
  const text = cleaned
  let ageSec = null
  if (lineObj && lineObj.t){
    const dt = new Date(lineObj.t)
    if (!isNaN(dt)) ageSec = Math.max(0, (now - dt)/1000.0)
  }
  if (ageSec == null){
    ageSec = parseLineAgeSecFromContent(text, now)
  }
  const hue = hueForAge(ageSec ?? 999999)
  const effectiveHue = (ageSec == null) ? fallbackHue : hue
  const glow = glowForAge(ageSec ?? 999999)
  const color = `hsl(${effectiveHue} 100% 55%)`
  const inner = glow.blur
  const outer = Math.round(glow.blur * 2)
  const alpha1 = glow.alpha
  const alpha2 = Math.max(0, Math.min(1, glow.alpha * 0.6))
  const shadow = (glow.blur > 0)
    ? `0 0 ${inner}px hsla(${effectiveHue} 100% 60% / ${alpha1}), 0 0 ${outer}px hsla(${effectiveHue} 100% 60% / ${alpha2})`
    : 'none'
  const escaped = escapeHtml(text)
  const withTs = escaped.replace(tsRegex, (m) => `<span class=\"timestamp\" style=\"color:${color}; text-shadow:${shadow}\">${m}</span>`)
  return `<span style=\"color:${color}; text-shadow:${shadow}\">${withTs}</span>`
}

function rebuildPanelsFromLogs(logs){
  const keys = Object.keys(logs).sort()
  const map = new Map(panels.map(p => [p.key, p]))
  const next = []
  for (const k of keys){
    const old = map.get(k)
    next.push(old ?? { key:k, filename:'', hue:120, accent:'hsl(120 100% 55%)', bucketLabel:'', mtimeText:'—', sizeText:'—', html:'(加载中...)' })
    if (sessionStorage.getItem(STICK_KEY_PREFIX + k) === null) setStick(k, true)
  }
  panels.splice(0, panels.length, ...next)
}

function bindScrollHandlers(){
  const scrollers = document.querySelectorAll('pre.log-body')
  scrollers.forEach((el, idx) => {
    if (el.__cd_bound) return
    el.__cd_bound = true
    el.addEventListener('scroll', () => {
      const p = panels[idx]
      if (!p) return
      const stick = isAtBottom(el)
      setStick(p.key, stick)
    }, { passive: true })
  })
  scrollers.forEach((el, idx) => {
    const p = panels[idx]
    if (!p) return
    if (getStick(p.key)) scrollToBottom(el)
  })
}


async function fetchLogs(){
  try{
    const r = await fetch('/api/logs?t='+Date.now(), { cache:'no-store' })
    const data = await r.json()
    const now = new Date(data.now)
    const nowIso = data.now
    const logs = data.logs || {}
    rebuildPanelsFromLogs(logs)
    await nextTick()

    const scrollers = document.querySelectorAll('pre.log-body')
    const prevStates = panels.map((p,i)=>{
      const el = scrollers[i]
      return { key:p.key, el, top: el?el.scrollTop:0, wasAtBottom: isAtBottom(el), stick: getStick(p.key) }
    })

    for (const [idx, panel] of panels.entries()){
      const info = logs[panel.key]
      if (!info) continue
      panel.filename = (info.path || '').split(/[\/\\]/).pop() || ''
      const exists = !!info.exists
      panel.sizeText = exists ? humanSize(info.size||0) : '不存在'
      panel.mtimeText = exists ? fmtTime(info.mtime) : '—'

      let ageSec = 999999
      if (exists && info.mtime){
        const mt = new Date(info.mtime)
        ageSec = Math.max(0, (now - mt)/1000.0)
      }
      const hue = hueForAge(ageSec)
      panel.hue = hue
      panel.accent = `hsl(${hue} 100% 55%)`
      panel.bucketLabel = bucketLabel(ageSec)

      const all = Array.isArray(info.lines) ? info.lines : []
      const rows = maxLines.value
      const sliced = all.slice(-Math.min(rows, maxLines.value))
      const fs = loadFS(panel.key)
      const enriched = sliced.map(o => { let t=o.t; if(!t){ t = fs[o.s] || nowIso; fs[o.s]=t } return { s:o.s, t } })
      const newFS = {}
      for (const row of enriched){ newFS[row.s] = row.t }
      saveFS(panel.key, newFS)

      const html = enriched.map(obj => colorizeLineObj(obj, hue, now)).join('\n')
      panel.html = html || '<span style="color:#7a8aa3">(空)</span>'
    }

    await nextTick()
    const after = document.querySelectorAll('pre.log-body')
    prevStates.forEach((st,i)=>{
      const el = after[i]
      if (!el) return
      if (st.stick || st.wasAtBottom) scrollToBottom(el)
      else el.scrollTop = st.top || 0
    })

    bindScrollHandlers()
  }catch(e){
    console.error('fetch logs error', e)
  }
}

function start(){
  stop()
  timer = setInterval(fetchLogs, interval.value)
}
function stop(){ if (timer) { clearInterval(timer); timer=null; } }

watch(interval, () => start())
watch(maxLines, () => fetchLogs())

  onMounted(() => {
  fetchLogs()
  start()
  // 去除 computeVisibleRows 引用，避免未定义导致错误；如需在窗口变化时刷新，可仅调用 fetchLogs。
  window.addEventListener('resize', () => {
    fetchLogs()
  })
})
</script>
