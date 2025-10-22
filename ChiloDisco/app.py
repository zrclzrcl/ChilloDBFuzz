import os
import io
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

from flask import Flask, jsonify, render_template, send_from_directory, request, send_file, abort

# Try to import yaml, but provide a fallback parser if not available
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
CODE_DIR = os.path.join(BASE_DIR, 'code')
CHILO_MUTATE_PATH = os.path.join(CODE_DIR, 'ChiloMutate.py')
RELATIVE_BASE = os.path.dirname(CHILO_MUTATE_PATH) if os.path.exists(CHILO_MUTATE_PATH) else CODE_DIR
CONFIG_PATH = os.path.join(CODE_DIR, 'config.yaml')
# 若存在前端工程构建产物，则优先从该目录提供
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')

app = Flask(__name__, static_folder='static', template_folder='templates')


# 全局禁用静态与 API 缓存（对 JSON API 尤其重要）
@app.after_request
def add_no_cache_headers(response):
    if request_path_needs_no_cache():
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def request_path_needs_no_cache() -> bool:
    try:
        from flask import request  # lazy import to avoid top-level circularity in some tools
        p = request.path or ''
        # 对 API 与首页模板禁用缓存
        return p.startswith('/api/') or p in ('/', '/health')
    except Exception:
        return False


def _manual_parse_log_paths(cfg_path: str) -> Dict[str, str]:
    """Very small, robust parser that only extracts LOG.*_PATH values.
    Supports lines like: KEY : "./output/log/file.log" or KEY: './x.log'
    """
    log_paths: Dict[str, str] = {}
    if not os.path.exists(cfg_path):
        return log_paths
    with open(cfg_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_log = False
    for raw in lines:
        line = raw.rstrip('\n')
        if not in_log:
            # Identify the LOG section start (start-of-line 'LOG')
            if line.strip().startswith('LOG'):
                in_log = True
            continue
        # Stop if we hit an empty line or next top-level section (no indent)
        if line.strip() == '' or (not line.startswith(' ') and not line.startswith('\t')):
            if log_paths:
                break
            else:
                continue
        # Expect indented KEY : VALUE
        parts = line.strip().split(':', 1)
        if len(parts) != 2:
            continue
        key, val = parts[0].strip(), parts[1].strip()
        # Remove optional comment and quotes
        if '#' in val:
            val = val.split('#', 1)[0].strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        # Remove leading colon variations like 'KEY : value'
        if key.endswith(' '):
            key = key.strip()
        if key.endswith(':'):
            key = key[:-1].strip()
        if val.startswith(':'):
            val = val[1:].strip()
        if key and val:
            log_paths[key] = val
    return log_paths


def load_log_paths() -> Dict[str, str]:
    """Load log file paths from config.yaml (LOG section). Returns absolute paths."""
    rels: Dict[str, str] = {}
    if yaml is not None:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            logs = ((cfg or {}).get('LOG') or {})
            if isinstance(logs, dict):
                rels = {k: str(v) for k, v in logs.items()}
        except Exception:
            rels = _manual_parse_log_paths(CONFIG_PATH)
    else:
        rels = _manual_parse_log_paths(CONFIG_PATH)

    # Normalize to absolute paths relative to repo root
    abs_paths: Dict[str, str] = {}
    for k, p in rels.items():
        if not p:
            continue
        p = p.strip()
        # Support paths like ./output/log/x.log or absolute
        if not os.path.isabs(p):
            # 以 code/ChiloMutate.py 所在目录为相对路径基准（若不存在则使用 code 目录）
            p = os.path.normpath(os.path.join(RELATIVE_BASE, p))
        abs_paths[k] = p
    return abs_paths


def load_csv_paths() -> Dict[str, str]:
    """Load CSV file paths from config.yaml (CSV section). Returns absolute paths."""
    rels: Dict[str, str] = {}
    try:
        if yaml is not None:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            csvs = ((cfg or {}).get('CSV') or {})
            if isinstance(csvs, dict):
                rels = {k: str(v) for k, v in csvs.items()}
        else:
            # 简易解析：只针对 CSV 段的键值
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                in_csv = False
                for raw in f:
                    line = raw.rstrip('\n')
                    if not in_csv:
                        if line.strip().startswith('CSV'):
                            in_csv = True
                        continue
                    if line.strip() == '' or (not line.startswith(' ') and not line.startswith('\t')):
                        if rels:
                            break
                        else:
                            continue
                    parts = line.strip().split(':', 1)
                    if len(parts) != 2:
                        continue
                    key, val = parts[0].strip(), parts[1].strip()
                    if '#' in val:
                        val = val.split('#', 1)[0].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    rels[key] = val
    except Exception:
        rels = {}

    abs_paths: Dict[str, str] = {}
    for k, p in rels.items():
        if not p:
            continue
        p = p.strip()
        if not os.path.isabs(p):
            p = os.path.normpath(os.path.join(RELATIVE_BASE, p))
        abs_paths[k] = p
    return abs_paths


LOG_PATHS = load_log_paths()


def _tail_file(path: str, max_bytes: int = 120_000, max_lines: int = 500) -> Tuple[List[str], int]:
    """Read the tail of a potentially large file efficiently.
    Returns (lines, size). Lines are decoded as UTF-8 with replacement.
    """
    if not os.path.exists(path):
        return [], 0

    size = os.path.getsize(path)
    start = max(0, size - max_bytes)
    with open(path, 'rb') as f:
        if start > 0:
            f.seek(start)
        data = f.read()
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    # If we started mid-line, drop the first partial line
    if start > 0 and lines:
        lines = lines[1:]
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return lines, size


def _file_mtime_iso(path: str) -> str:
    if not os.path.exists(path):
        return ''
    ts = os.path.getmtime(path)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.isoformat()


@app.route('/')
def index():
    # 如存在前端工程构建产物（Vite dist），优先返回该入口文件
    index_html = os.path.join(FRONTEND_DIST, 'index.html')
    if os.path.exists(index_html):
        return send_from_directory(FRONTEND_DIST, 'index.html')

    # 否则回退到旧版模板（CDN 版 Vue 单页）
    panels = []
    for key, p in LOG_PATHS.items():
        panels.append({
            'key': key,
            'filename': os.path.basename(p),
        })
    panels.sort(key=lambda x: x['key'])
    return render_template('index.html', panels=panels)


# 简单的内存状态，用于给每一行分配“首次看到”的时间戳（会随进程生命周期丢失）
LOG_STATE: Dict[str, Dict[str, List[str]]] = {}


@app.route('/api/logs')
def api_logs():
    payload = {}
    now_dt = datetime.now(tz=timezone.utc)
    now_iso = now_dt.isoformat()
    for key, path in LOG_PATHS.items():
        lines, size = _tail_file(path)
        exists = os.path.exists(path)

        # 为每一行附加首次看到的时间戳（没有行内时间戳时用于前端着色）
        state = LOG_STATE.get(key) or {}
        prev_ts: List[str] = state.get('ts', []) or []
        prev_hashes: List[str] = state.get('hashes', []) or []
        prev_len = len(prev_ts)
        cur_len = len(lines)

        # 计算当前行的内容哈希（稳定对齐：按内容复用时间戳）
        def _hash_line(s: str) -> str:
            try:
                b = s.encode('utf-8', errors='replace')
            except Exception:
                b = (s or '').encode('utf-8', errors='replace')
            return _hash_bytes(b)

        cur_hashes: List[str] = [ _hash_line(s) for s in lines ]

        if cur_len == 0:
            ts_list: List[str] = []
        elif prev_len == 0 or not prev_hashes:
            # 首次或没有历史：为避免“整体同色”，按行序分配递进时间戳（越靠后越新）
            delta = 0.8  # 每行间隔秒数
            ts_list = []
            for i in range(cur_len):
                age = (cur_len - 1 - i) * delta
                t_i = (now_dt - timedelta(seconds=age)).isoformat()
                ts_list.append(t_i)
        else:
            # 基于内容哈希的多重匹配复用：为每个哈希构建时间戳队列，按出现顺序消费
            from collections import defaultdict, deque
            buckets = defaultdict(deque)
            for h, t in zip(prev_hashes, prev_ts):
                buckets[h].append(t)
            ts_list = []
            reused = 0
            for h in cur_hashes:
                if buckets[h]:
                    ts_list.append(buckets[h].popleft())
                    reused += 1
                else:
                    ts_list.append(now_iso)
            # 如对齐效果极差（例如日志轮转/重写），避免“整体同色 now”，退回阶梯分配
            if cur_len > 0:
                match_ratio = reused / float(cur_len)
                if reused == 0 or match_ratio < 0.2:
                    delta = 0.8
                    ts_list = []
                    for i in range(cur_len):
                        age = (cur_len - 1 - i) * delta
                        t_i = (now_dt - timedelta(seconds=age)).isoformat()
                        ts_list.append(t_i)

        # 记录当前状态用于下一轮对齐
        LOG_STATE[key] = {'ts': ts_list, 'lines': lines, 'hashes': cur_hashes}

        # 组装带时间戳的行对象
        line_objs = [{'s': s, 't': ts_list[i]} for i, s in enumerate(lines)]

        payload[key] = {
            'path': path,
            'exists': exists,
            'size': size,
            'mtime': _file_mtime_iso(path),
            'lines': line_objs,
        }
    resp = jsonify({
        'now': now_iso,
        'logs': payload,
    })
    # 明确禁用缓存，确保前端无需刷新即可得到最新内容
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/health')
def health():
    ok = bool(LOG_PATHS)
    return jsonify({'status': 'ok' if ok else 'no-log-paths', 'count': len(LOG_PATHS)})


# Allow serving favicon if placed in static
@app.route('/favicon.ico')
def favicon():
    # 优先从前端构建产物读取 favicon（如果存在）
    dist_fav = os.path.join(FRONTEND_DIST, 'favicon.ico')
    if os.path.exists(dist_fav):
        return send_from_directory(FRONTEND_DIST, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# 提供前端 Vite 构建产物中的静态资源（/assets/*）
@app.route('/assets/<path:filename>')
def vite_assets(filename: str):
    assets_dir = os.path.join(FRONTEND_DIST, 'assets')
    if os.path.exists(assets_dir):
        return send_from_directory(assets_dir, filename)
    # 若无构建产物，返回 404
    from flask import abort
    return abort(404)


def _manual_parse_fuzz_output_dir(cfg_path: str) -> str:
    out = ''
    if not os.path.exists(cfg_path):
        return out
    with open(cfg_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('OUTPUT_DIR'):
                # handle formats like: OUTPUT_DIR: "..." or OUTPUT_DIR : '...'
                parts = line.split(':', 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    if '#' in val:
                        val = val.split('#', 1)[0].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    out = val
                    break
    return out


def load_fuzz_output_dir() -> str:
    """Read code/fuzz_config.yaml and return OUTPUT_DIR as absolute path.
    Relative paths are resolved against RELATIVE_BASE (code/ChiloMutate.py dir or code).
    """
    cfg_path = os.path.join(CODE_DIR, 'fuzz_config.yaml')
    value = ''
    if os.path.exists(cfg_path):
        if yaml is not None:
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                    v = (y or {}).get('OUTPUT_DIR')
                    if isinstance(v, str):
                        value = v
            except Exception:
                value = _manual_parse_fuzz_output_dir(cfg_path)
        else:
            value = _manual_parse_fuzz_output_dir(cfg_path)
    if not value:
        return ''
    p = value.strip()
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(RELATIVE_BASE, p))
    return p


def _plotdata_path() -> str:
    base = load_fuzz_output_dir()
    if not base:
        return ''
    # prefer default/plot_data, fallback to defaut/plot_data, then legacy names plotdata (compat)
    cand = [
        os.path.join(base, 'default', 'plot_data'),
        os.path.join(base, 'defaut', 'plot_data'),
        os.path.join(base, 'default', 'plotdata'),
        os.path.join(base, 'defaut', 'plotdata'),
    ]
    for p in cand:
        if os.path.exists(p):
            return p
    # 如果都不存在，则返回首选路径（便于前端展示正确预期路径）
    return cand[0]


def _tail_read_lines(path: str, max_bytes: int = 256_000) -> List[str]:
    if not os.path.exists(path):
        return []
    size = os.path.getsize(path)
    start = max(0, size - max_bytes)
    with open(path, 'rb') as f:
        if start > 0:
            f.seek(start)
        data = f.read()
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    return lines


def _parse_plotdata(lines: List[str], limit: int = 2000) -> Dict[str, List[float]]:
    # Prepare arrays
    result = {
        't': [],
        'map_size': [],
        'edges_found': [],
        'corpus_count': [],
        'cycles_done': [],
        'cur_item': [],
        'saved_crashes': [],
        'max_depth': [],
        'total_execs': [],
        'pending_total': [],
        'pending_favs': [],
        'execs_per_sec': [],
    }
    rows: List[List[str]] = []
    for raw in lines:
        if not raw or raw.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in raw.split(',')]
        if len(parts) < 12:
            continue
        rows.append(parts)
    # limit to last N
    rows = rows[-limit:]

    def to_int(s: str) -> int:
        try:
            return int(float(s))
        except Exception:
            return 0

    def to_float(s: str) -> float:
        try:
            return float(s)
        except Exception:
            return 0.0

    for cols in rows:
        # indices per AFL++ header in issue
        # 0 rel_time, 1 cycles_done, 2 cur_item, 3 corpus_count, 4 pending_total, 5 pending_favs,
        # 6 map_size(%) 7 saved_crashes 8 saved_hangs 9 max_depth 10 execs_per_sec 11 total_execs
        # 12 edges_found 13 total_crashes 14 servers_count
        try:
            rel_t = to_float(cols[0])
            result['t'].append(rel_t)
            result['cycles_done'].append(to_int(cols[1]))
            result['cur_item'].append(to_int(cols[2]))
            result['corpus_count'].append(to_int(cols[3]))
            result['pending_total'].append(to_int(cols[4]))
            result['pending_favs'].append(to_int(cols[5]))
            ms = cols[6].strip()
            if ms.endswith('%'):
                ms = ms[:-1]
            result['map_size'].append(to_float(ms))
            result['saved_crashes'].append(to_int(cols[7]))
            # saved_hangs (cols[8]) currently not used in visuals
            result['max_depth'].append(to_int(cols[9]))
            result['execs_per_sec'].append(to_float(cols[10]))
            result['total_execs'].append(to_int(cols[11]))
            if len(cols) > 12:
                result['edges_found'].append(to_int(cols[12]))
            else:
                result['edges_found'].append(0)
        except Exception:
            # skip bad row
            continue
    return result


# 全局维护 .cur_input 内容变更的起始时间（用于计时）
CUR_INPUT_STATE = {
    'last_hash': None,
    'since_ts': time.time(),
}


def _fuzz_output_dir() -> str:
    """读取 code/fuzz_config.yaml 中的 OUTPUT_DIR（相对路径相对 RELATIVE_BASE 解析）。"""
    cfg_path = os.path.join(CODE_DIR, 'fuzz_config.yaml')
    output_dir = ''
    try:
        if yaml:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            output_dir = str(data.get('OUTPUT_DIR', '')).strip()
        else:
            # 简易解析：找以 OUTPUT_DIR 开头的行
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    for raw in f:
                        line = raw.strip()
                        if line.startswith('OUTPUT_DIR'):
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                output_dir = parts[1].strip().strip("'\"")
                            break
    except Exception:
        output_dir = ''
    if not output_dir:
        return ''
    # 相对路径相对 RELATIVE_BASE
    if not os.path.isabs(output_dir):
        output_dir = os.path.abspath(os.path.join(RELATIVE_BASE, output_dir))
    return output_dir


def _plotdata_path() -> str:
    """基于 fuzz_config.yaml 的 OUTPUT_DIR 推导 plot_data 路径（兼容旧名 plotdata）。"""
    out_dir = _fuzz_output_dir()
    if not out_dir:
        return ''
    # 优先 default/plot_data 与 defaut/plot_data；回退到 legacy 名称 plotdata 以兼容旧环境
    candidates = [
        os.path.join(out_dir, 'default', 'plot_data'),
        os.path.join(out_dir, 'defaut', 'plot_data'),
        os.path.join(out_dir, 'default', 'plotdata'),
        os.path.join(out_dir, 'defaut', 'plotdata'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def _cur_input_path() -> str:
    out_dir = _fuzz_output_dir()
    if not out_dir:
        return ''
    p1 = os.path.join(out_dir, 'default', '.cur_input')
    p2 = os.path.join(out_dir, 'defaut', '.cur_input')
    return p1 if os.path.exists(p1) else p2


def _read_text_file(path: str, max_bytes: int = 512_000) -> str:
    if not path or not os.path.exists(path):
        return ''
    size = os.path.getsize(path)
    start = max(0, size - max_bytes)
    with open(path, 'rb') as f:
        if start > 0:
            f.seek(start)
        data = f.read()
    try:
        text = data.decode('utf-8', errors='replace')
    except Exception:
        text = ''
    return text


def _hash_bytes(b: bytes) -> str:
    try:
        import hashlib
        return hashlib.sha256(b).hexdigest()
    except Exception:
        return str(len(b))


@app.route('/api/plot')
def api_plot():
    # plot_data
    path = _plotdata_path()
    exists = bool(path and os.path.exists(path))
    meta = {
        'path': path or '',
        'exists': exists,
        'size': os.path.getsize(path) if exists else 0,
        'mtime': _file_mtime_iso(path) if exists else '',
    }
    series = {k: [] for k in ['t','map_size','edges_found','corpus_count','cycles_done','cur_item','saved_crashes','max_depth','total_execs','pending_total','pending_favs','execs_per_sec']}
    if exists:
        lines = _tail_read_lines(path, max_bytes=512_000)
        series = _parse_plotdata(lines, limit=2000)

    # .cur_input 内容读取与计时
    cur_path = _cur_input_path()
    cur_exists = bool(cur_path and os.path.exists(cur_path))
    cur_meta = {
        'path': cur_path or '',
        'exists': cur_exists,
        'size': os.path.getsize(cur_path) if cur_exists else 0,
        'mtime': _file_mtime_iso(cur_path) if cur_exists else '',
    }
    cur_text = ''
    since_sec = 0.0
    now_ts = time.time()
    if cur_exists:
        # 读取文本并计算 hash
        size = os.path.getsize(cur_path)
        start = max(0, size - 512_000)
        with open(cur_path, 'rb') as f:
            if start > 0:
                f.seek(start)
            cur_bytes = f.read()
        cur_text = cur_bytes.decode('utf-8', errors='replace')
        h = _hash_bytes(cur_bytes)
        last_h = CUR_INPUT_STATE.get('last_hash')
        if last_h != h:
            CUR_INPUT_STATE['last_hash'] = h
            CUR_INPUT_STATE['since_ts'] = now_ts
        since_sec = max(0.0, now_ts - float(CUR_INPUT_STATE.get('since_ts') or now_ts))

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    payload = {
        'now': now_iso,
        'meta': meta,
        'series': series,
        'cur_input': {
            'meta': cur_meta,
            'content': cur_text,
            'since_sec': since_sec,
        }
    }
    resp = jsonify(payload)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/plot')
def plot_page():
    # 若存在前端工程构建产物（未来可将 plot 集成 SPA），此处仍回退到服务端模板页
    return render_template('plot.html')


# ————— 下载页面与下载 API —————
@app.route('/downloads')
def downloads_page():
    return render_template('downloads.html')


@app.route('/api/download/plot_data')
def download_plot_data():
    path = _plotdata_path()
    if not path or not os.path.exists(path):
        return abort(404, description='plot_data 不存在')
    # 使用 send_file 以附件形式下载
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route('/api/download/csv/list')
def list_csvs():
    csv_paths = load_csv_paths()
    items = []
    for k, p in csv_paths.items():
        exists = os.path.exists(p)
        items.append({
            'key': k,
            'path': p,
            'exists': exists,
            'size': os.path.getsize(p) if exists else 0,
            'mtime': _file_mtime_iso(p) if exists else ''
        })
    return jsonify({'items': items})


@app.route('/api/download/csv')
def download_csv():
    key = request.args.get('key') or ''
    csv_paths = load_csv_paths()
    if key not in csv_paths:
        return abort(404, description='未知的 CSV key')
    p = csv_paths[key]
    if not p or not os.path.exists(p):
        return abort(404, description='CSV 文件不存在')
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))


@app.route('/api/download/log')
def download_log():
    key = request.args.get('key') or ''
    log_paths = LOG_PATHS
    if key not in log_paths:
        return abort(404, description='未知的 LOG key')
    p = log_paths[key]
    if not p or not os.path.exists(p):
        return abort(404, description='日志文件不存在')
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))


@app.route('/api/download/csv/zip')
def download_csv_zip():
    import zipfile
    buf = io.BytesIO()
    csv_paths = load_csv_paths()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for k, p in csv_paths.items():
            if p and os.path.exists(p):
                arcname = os.path.basename(p) or (k + '.csv')
                try:
                    zf.write(p, arcname=arcname)
                except Exception:
                    # 如果写入失败，写入一个占位文本
                    zf.writestr(arcname or (k + '.csv'), '')
    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'chilo_csv_{ts}.zip')


def load_file_paths() -> Dict[str, str]:
    """Load file paths from config.yaml (FILE_PATH section). Returns absolute paths."""
    rels: Dict[str, str] = {}
    try:
        if yaml is not None:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            file_paths = ((cfg or {}).get('FILE_PATH') or {})
            if isinstance(file_paths, dict):
                rels = {k: str(v) for k, v in file_paths.items()}
        else:
            # 简易解析
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                in_section = False
                for raw in f:
                    line = raw.rstrip('\n')
                    if not in_section:
                        if line.strip().startswith('FILE_PATH'):
                            in_section = True
                        continue
                    if line.strip() == '' or (not line.startswith(' ') and not line.startswith('\t')):
                        if rels:
                            break
                        else:
                            continue
                    parts = line.strip().split(':', 1)
                    if len(parts) != 2:
                        continue
                    key, val = parts[0].strip(), parts[1].strip()
                    if '#' in val:
                        val = val.split('#', 1)[0].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    rels[key] = val
    except Exception:
        rels = {}

    abs_paths: Dict[str, str] = {}
    for k, p in rels.items():
        if not p:
            continue
        p = p.strip()
        if not os.path.isabs(p):
            p = os.path.normpath(os.path.join(RELATIVE_BASE, p))
        abs_paths[k] = p
    return abs_paths


@app.route('/api/download/folder/parsed_sql')
def download_parsed_sql():
    import zipfile
    file_paths = load_file_paths()
    folder_path = file_paths.get('PARSED_SQL_PATH', '')
    if not folder_path or not os.path.exists(folder_path):
        return abort(404, description='ParsedSQL 文件夹不存在')
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                try:
                    zf.write(file_path, arcname=arcname)
                except Exception:
                    pass
    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'chilo_parsed_sql_{ts}.zip')


@app.route('/api/download/folder/generated_mutator')
def download_generated_mutator():
    import zipfile
    file_paths = load_file_paths()
    folder_path = file_paths.get('GENERATED_MUTATOR_PATH', '')
    if not folder_path or not os.path.exists(folder_path):
        return abort(404, description='GeneratedMutator 文件夹不存在')
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                try:
                    zf.write(file_path, arcname=arcname)
                except Exception:
                    pass
    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'chilo_generated_mutator_{ts}.zip')


@app.route('/api/download/folder/structural_sql')
def download_structural_sql():
    import zipfile
    file_paths = load_file_paths()
    folder_path = file_paths.get('STRUCTURAL_MUTATE_PATH', '')
    if not folder_path or not os.path.exists(folder_path):
        return abort(404, description='StructuralMutateSQL 文件夹不存在')
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                try:
                    zf.write(file_path, arcname=arcname)
                except Exception:
                    pass
    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'chilo_structural_sql_{ts}.zip')


@app.route('/api/download/all')
def download_all():
    import zipfile
    buf = io.BytesIO()
    
    # 获取所有路径
    csv_paths = load_csv_paths()
    log_paths = load_log_paths()
    file_paths = load_file_paths()
    
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # CSV文件
        for k, p in csv_paths.items():
            if p and os.path.exists(p):
                arcname = os.path.join('csv', os.path.basename(p))
                try:
                    zf.write(p, arcname=arcname)
                except Exception:
                    pass
        
        # 日志文件
        for k, p in log_paths.items():
            if p and os.path.exists(p):
                arcname = os.path.join('logs', os.path.basename(p))
                try:
                    zf.write(p, arcname=arcname)
                except Exception:
                    pass
        
        # 文件夹
        for folder_key in ['PARSED_SQL_PATH', 'GENERATED_MUTATOR_PATH', 'STRUCTURAL_MUTATE_PATH']:
            folder_path = file_paths.get(folder_key, '')
            if folder_path and os.path.exists(folder_path):
                folder_name = os.path.basename(folder_path.rstrip('/\\'))
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(folder_name, os.path.relpath(file_path, folder_path))
                        try:
                            zf.write(file_path, arcname=arcname)
                        except Exception:
                            pass
        
        # plot_data
        plot_path = _plotdata_path()
        if plot_path and os.path.exists(plot_path):
            try:
                zf.write(plot_path, arcname=os.path.join('plot', os.path.basename(plot_path)))
            except Exception:
                pass
    
    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'chilo_all_output_{ts}.zip')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)
