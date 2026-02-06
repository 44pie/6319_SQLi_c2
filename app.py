#!/usr/bin/env python3
"""6319sqli - SQLMap Monitor"""

import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import os
import json
import re
import glob
import subprocess
from datetime import datetime
import urllib.parse
import socket

st.set_page_config(page_title="6319sqli", layout="wide", initial_sidebar_state="collapsed")

# Auto-detect installation directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '.6319sqli_data')

PROXYCHAINS_PREFIX = 'proxychains4 -q'

def ensure_proxychains(cmd):
    cmd = cmd.strip()
    if not cmd:
        return cmd
    if cmd.startswith('proxychains'):
        return cmd
    if 'sqlmap' in cmd:
        if cmd.startswith('python'):
            return f'{PROXYCHAINS_PREFIX} {cmd}'
        if cmd.startswith('/') or cmd.startswith('sqlmap'):
            return f'{PROXYCHAINS_PREFIX} python3 {cmd}'
    return cmd

# Start action server in background thread
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

ACTION_SERVER_STARTED = False
ACTION_FILE = os.path.join(DATA_DIR, 'action.json')

class ActionHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        action = params.get('action', [''])[0]
        host = params.get('host', [''])[0]
        cmd = params.get('cmd', [''])[0]
        
        if action:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ACTION_FILE, 'w') as f:
                json.dump({'action': action, 'host': host, 'cmd': cmd}, f)
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.wfile.write(b'{"status":"no action"}')

def start_action_server():
    global ACTION_SERVER_STARTED
    if ACTION_SERVER_STARTED:
        return
    ACTION_SERVER_STARTED = True
    try:
        server = HTTPServer(('0.0.0.0', 5001), ActionHandler)
        server.serve_forever()
    except:
        pass

# Start server in background
threading.Thread(target=start_action_server, daemon=True).start()
os.makedirs(DATA_DIR, exist_ok=True)
RUNNING_FILE = os.path.join(DATA_DIR, 'running.json')

def get_host_output_file(host_key):
    safe_name = host_key.replace('/', '_').replace(':', '_')
    return os.path.join(DATA_DIR, f'pty_{safe_name}.txt')

params = st.query_params

# Handle actions from iframe (with underscore prefix)
if '_action' in params:
    action = params.get('_action')
    host = params.get('_host', '')
    cmd = params.get('_cmd', '')
    
    if action == 'run' and host and cmd:
        import threading
        cmd = ensure_proxychains(cmd)
        output_file = get_host_output_file(host)
        
        def run_cmd_iframe():
            with open(RUNNING_FILE, 'w') as f:
                json.dump({'running': True, 'host': host, 'cmd': cmd}, f)
            with open(output_file, 'w') as f:
                f.write(f'$ {cmd}\n')
                f.flush()
            try:
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                process = subprocess.Popen(
                    f'stdbuf -oL -eL {cmd}',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=env
                )
                import select
                import fcntl
                fd = process.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                with open(output_file, 'a') as out_f:
                    while True:
                        ready, _, _ = select.select([process.stdout], [], [], 0.5)
                        if ready:
                            try:
                                data = process.stdout.read(4096)
                                if data:
                                    out_f.write(data.decode('utf-8', errors='replace'))
                                    out_f.flush()
                            except:
                                pass
                        if process.poll() is not None:
                            try:
                                remaining = process.stdout.read()
                                if remaining:
                                    out_f.write(remaining.decode('utf-8', errors='replace'))
                                    out_f.flush()
                            except:
                                pass
                            break
                    out_f.write(f'\n[Done - exit code {process.returncode}]\n')
                    out_f.flush()
            except Exception as e:
                with open(output_file, 'a') as f:
                    f.write(f'\n[ERROR] {str(e)}\n')
            finally:
                with open(RUNNING_FILE, 'w') as f:
                    json.dump({'running': False}, f)
        
        threading.Thread(target=run_cmd_iframe, daemon=True).start()
    
    elif action == 'stop':
        try:
            subprocess.run(['pkill', '-f', 'sqlmap'], capture_output=True)
        except:
            pass
        with open(RUNNING_FILE, 'w') as f:
            json.dump({'running': False}, f)
    
    elif action == 'clear' and host:
        output_file = get_host_output_file(host)
        with open(output_file, 'w') as f:
            f.write('')
    
    st.query_params.clear()
    st.rerun()

if 'action' in params:
    action = params.get('action')
    if action == 'run':
        cmd = params.get('cmd', '')
        host = params.get('host', '')
        if cmd and host:
            import threading
            cmd = ensure_proxychains(cmd)
            output_file = get_host_output_file(host)
            
            def run_cmd():
                with open(RUNNING_FILE, 'w') as f:
                    json.dump({'running': True, 'host': host, 'cmd': cmd}, f)
                with open(output_file, 'w') as f:
                    f.write(f'$ {cmd}\n')
                    f.flush()
                try:
                    env = os.environ.copy()
                    env['PYTHONUNBUFFERED'] = '1'
                    process = subprocess.Popen(
                        f'stdbuf -oL -eL {cmd}',
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        env=env,
                        bufsize=1
                    )
                    import select
                    import fcntl
                    fd = process.stdout.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                    
                    with open(output_file, 'a') as out_f:
                        while True:
                            ready, _, _ = select.select([process.stdout], [], [], 0.5)
                            if ready:
                                try:
                                    data = process.stdout.read(4096)
                                    if data:
                                        out_f.write(data.decode('utf-8', errors='replace'))
                                        out_f.flush()
                                except:
                                    pass
                            if process.poll() is not None:
                                try:
                                    remaining = process.stdout.read()
                                    if remaining:
                                        out_f.write(remaining.decode('utf-8', errors='replace'))
                                        out_f.flush()
                                except:
                                    pass
                                break
                        out_f.write(f'\n[Done - exit code {process.returncode}]\n')
                        out_f.flush()
                except Exception as e:
                    with open(output_file, 'a') as f:
                        f.write(f'\n[ERROR] {str(e)}\n')
                finally:
                    with open(RUNNING_FILE, 'w') as f:
                        json.dump({'running': False}, f)
            
            threading.Thread(target=run_cmd, daemon=True).start()
        st.query_params.clear()
        st.rerun()
    
    elif action == 'stop':
        try:
            subprocess.run(['pkill', '-f', 'sqlmap'], capture_output=True)
        except:
            pass
        with open(RUNNING_FILE, 'w') as f:
            json.dump({'running': False}, f)
        st.query_params.clear()
        st.rerun()
    
    elif action == 'clear':
        host = params.get('host', '')
        if host:
            output_file = get_host_output_file(host)
            with open(output_file, 'w') as f:
                f.write('')
        st.query_params.clear()
        st.rerun()

# Check for pending actions from action server
if os.path.exists(ACTION_FILE):
    try:
        with open(ACTION_FILE) as f:
            action_data = json.load(f)
        os.remove(ACTION_FILE)
        
        if action_data.get('action') == 'run':
            host = action_data.get('host', '')
            cmd = action_data.get('cmd', '')
            if host and cmd:
                import threading as th
                cmd = ensure_proxychains(cmd)
                output_file = get_host_output_file(host)
                
                def run_cmd_action():
                    with open(RUNNING_FILE, 'w') as f:
                        json.dump({'running': True, 'host': host, 'cmd': cmd}, f)
                    with open(output_file, 'w') as f:
                        f.write(f'$ {cmd}\n')
                        f.flush()
                    try:
                        env = os.environ.copy()
                        env['PYTHONUNBUFFERED'] = '1'
                        process = subprocess.Popen(
                            f'stdbuf -oL -eL {cmd}',
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            env=env
                        )
                        import select
                        import fcntl
                        fd = process.stdout.fileno()
                        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        
                        with open(output_file, 'a') as out_f:
                            while True:
                                ready, _, _ = select.select([process.stdout], [], [], 0.5)
                                if ready:
                                    try:
                                        data = process.stdout.read(4096)
                                        if data:
                                            out_f.write(data.decode('utf-8', errors='replace'))
                                            out_f.flush()
                                    except:
                                        pass
                                if process.poll() is not None:
                                    try:
                                        remaining = process.stdout.read()
                                        if remaining:
                                            out_f.write(remaining.decode('utf-8', errors='replace'))
                                            out_f.flush()
                                    except:
                                        pass
                                    break
                            out_f.write(f'\n[Done - exit code {process.returncode}]\n')
                            out_f.flush()
                    except Exception as e:
                        with open(output_file, 'a') as f:
                            f.write(f'\n[ERROR] {str(e)}\n')
                    finally:
                        with open(RUNNING_FILE, 'w') as f:
                            json.dump({'running': False}, f)
                
                th.Thread(target=run_cmd_action, daemon=True).start()
                st.rerun()
        
        elif action_data.get('action') == 'stop':
            try:
                subprocess.run(['pkill', '-f', 'sqlmap'], capture_output=True)
            except:
                pass
            with open(RUNNING_FILE, 'w') as f:
                json.dump({'running': False}, f)
            st.rerun()
        
        elif action_data.get('action') == 'clear':
            host = action_data.get('host', '')
            if host:
                output_file = get_host_output_file(host)
                with open(output_file, 'w') as f:
                    f.write('')
            st.rerun()
    except:
        pass

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"],
.main, .stApp, [data-testid="stAppViewBlockContainer"],
[data-testid="stMainBlockContainer"], .stMainBlockContainer {
    margin: 0 !important; padding: 0 !important; overflow: hidden !important;
    background: #2e3440 !important; max-width: 100% !important;
}
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, [data-testid="stHeader"],
[data-testid="stBottom"], [data-testid="stSidebar"], section[data-testid="stSidebar"],
[data-testid="stHeaderActionElements"], [data-testid="stAppDeployButton"] {
    display: none !important; height: 0 !important; min-height: 0 !important;
    margin: 0 !important; padding: 0 !important; visibility: hidden !important;
    position: absolute !important; top: -9999px !important;
}
.block-container, [data-testid="stVerticalBlock"],
.stVerticalBlock, [data-testid="stElementContainer"] {
    padding: 0 !important; margin: 0 !important; gap: 0 !important;
    max-width: 100% !important; width: 100% !important;
}
</style>
""", unsafe_allow_html=True)


CONFIG_FILE = os.path.expanduser('~/.6319sqli/config.json')
PTY_OUTPUT_FILE = os.path.join(DATA_DIR, 'pty_output.json')

def load_pty_outputs():
    if os.path.exists(PTY_OUTPUT_FILE):
        try:
            with open(PTY_OUTPUT_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_pty_outputs(outputs):
    with open(PTY_OUTPUT_FILE, 'w') as f:
        json.dump(outputs, f)

def get_host_pty_content(host_key):
    output_file = get_host_output_file(host_key)
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as f:
                return f.read()
        except:
            pass
    return ''

def is_running():
    if os.path.exists(RUNNING_FILE):
        try:
            with open(RUNNING_FILE) as f:
                data = json.load(f)
                return data.get('running', False)
        except:
            pass
    return False


def get_running_info():
    if os.path.exists(RUNNING_FILE):
        try:
            with open(RUNNING_FILE) as f:
                return json.load(f)
        except:
            pass
    return {'running': False}

running_info = get_running_info()
currently_running = running_info.get('running', False)
running_host = running_info.get('host', '')

# Always autorefresh to check for pending actions or running status
st_autorefresh(interval=2000, limit=None, key="live_refresh")

pty_outputs = load_pty_outputs()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {'scan_paths': [SCRIPT_DIR, os.path.join(SCRIPT_DIR, 'ttt')]}

config = load_config()

def parse_sqlmap_log(log_path):
    result = {'injected': False, 'techniques': [], 'dbms': None, 'parameters': [], 'last_update': None, 'log_content': '', 'dumps': [], 'target_url': None, 'original_cmd': ''}
    try:
        stat = os.stat(log_path)
        result['last_update'] = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        with open(log_path, 'r', errors='ignore') as f:
            content = f.read()
        result['log_content'] = content
        if 'is vulnerable' in content or 'sqlmap identified' in content:
            result['injected'] = True
        for tech, pattern in {'time': r'time-based', 'error': r'error-based', 'union': r'UNION query', 'boolean': r'boolean-based', 'stacked': r'stacked'}.items():
            if re.search(pattern, content, re.I):
                result['techniques'].append(tech)
        dbms_match = re.search(r'back-end DBMS: ([^\n]+)', content)
        if dbms_match:
            result['dbms'] = dbms_match.group(1).strip()
        result['parameters'] = list(set(re.findall(r"Parameter: ([^\s\(]+)", content)))
        
        url_match = re.search(r"testing URL ['\"]([^'\"]+)['\"]", content)
        if not url_match:
            url_match = re.search(r'Target URL: ([^\s\n]+)', content)
        if not url_match:
            url_match = re.search(r'-u ["\']?([^"\'\s]+)', content)
        if url_match:
            result['target_url'] = url_match.group(1).strip()
        
        dump_dir = os.path.join(os.path.dirname(log_path), 'dump')
        if os.path.exists(dump_dir):
            for db in os.listdir(dump_dir):
                db_path = os.path.join(dump_dir, db)
                if os.path.isdir(db_path):
                    tables = [f.replace('.csv', '') for f in os.listdir(db_path) if f.endswith('.csv')]
                    result['dumps'].append({'db': db, 'tables': tables})
        
        target_file = os.path.join(os.path.dirname(log_path), 'target.txt')
        if os.path.exists(target_file):
            with open(target_file, 'r', errors='ignore') as f:
                lines = f.read().strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if 'sqlmap' in line and '-u' in line:
                        sqlmap_match = re.search(r'(/\S+sqlmap\S*)\s+(.+)', line)
                        if sqlmap_match:
                            result['sqlmap_bin'] = sqlmap_match.group(1)
                            result['original_cmd'] = 'proxychains4 -q python3 ' + sqlmap_match.group(1) + ' ' + sqlmap_match.group(2).strip()
                        else:
                            if not line.startswith('proxychains4'):
                                result['original_cmd'] = 'proxychains4 -q python3 ' + line
                            else:
                                result['original_cmd'] = line
                        break
    except:
        pass
    return result

def scan_hosts():
    hosts = {}
    seen_paths = set()
    paths = config.get('scan_paths', [os.getcwd()])
    for base_path in paths:
        base_path = os.path.expanduser(base_path)
        if not os.path.exists(base_path):
            continue
        for pattern in [os.path.join(base_path, 'sql_out', '*'), os.path.join(base_path, '*', 'sql_out', '*'), os.path.join(base_path, 'output', '*')]:
            for domain_dir in glob.glob(pattern):
                if not os.path.isdir(domain_dir):
                    continue
                real_path = os.path.realpath(domain_dir)
                if real_path in seen_paths:
                    continue
                seen_paths.add(real_path)
                domain = os.path.basename(domain_dir)
                if domain in ['sql_out', 'output', '.', '..']:
                    continue
                log_file = os.path.join(domain_dir, 'log')
                if os.path.exists(log_file):
                    info = parse_sqlmap_log(log_file)
                    target_file = os.path.join(domain_dir, 'target.txt')
                    if os.path.exists(target_file) and not info.get('target_url'):
                        with open(target_file) as f:
                            for line in f:
                                if line.strip().startswith('http'):
                                    info['target_url'] = line.strip().split()[0]
                                    break
                    host_key = real_path
                    hosts[host_key] = {'key': host_key, 'domain': domain, 'path': domain_dir, 'log_file': log_file, 'base_path': base_path, **info}
    return hosts

hosts = scan_hosts()
injected = {k: v for k, v in hosts.items() if v['injected']}
not_injected = {k: v for k, v in hosts.items() if not v['injected']}

hosts_html = ""
sorted_hosts = sorted(hosts.items(), key=lambda x: (not x[1]['injected'], x[1]['domain']))
for key, h in sorted_hosts:
    cls = "host injected" if h['injected'] else "host"
    badges = '<span class="badge badge-inj">INJ</span>' if h['injected'] else '<span class="badge badge-notinj">NOT</span>'
    for t in h.get('techniques', []):
        badges += f'<span class="badge badge-{t}">{t.upper()}</span>'
    
    hosts_html += f'''
    <div class="{cls}" onclick="select('{key}')">
        <div class="host-domain">{h['domain']}</div>
        <div class="host-badges-row">{badges}</div>
        <div class="host-info">
            DBMS: <span>{h.get('dbms') or 'unknown'}</span><br>
            Params: <span>{', '.join((h.get('parameters') or [])[:2]) or 'none'}</span><br>
            Updated: <span>{h.get('last_update') or 'N/A'}</span>
        </div>
    </div>'''

hosts_safe = {}
for k, v in hosts.items():
    hosts_safe[k] = {kk: vv for kk, vv in v.items()}
    hosts_safe[k]['sqlmap_output'] = get_host_pty_content(k)
    hosts_safe[k]['original_cmd'] = v.get('original_cmd', '')
    hosts_safe[k]['sqlmap_bin'] = v.get('sqlmap_bin', 'sqlmap')

html = f'''
<!DOCTYPE html>
<html>
<head>
<style>
:root {{
    --bg0: #2e3440; --bg1: #3b4252; --bg2: #434c5e; --bg3: #4c566a;
    --fg: #eceff4; --fg3: #a5b1c2; --accent: #88c0d0;
    --green: #a3be8c; --red: #bf616a; --yellow: #ebcb8b;
    --purple: #b48ead; --orange: #d08770; --cyan: #8fbcbb;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ height: 100%; width: 100%; overflow: hidden; margin: 0; padding: 0; }}
body {{ font-family: 'JetBrains Mono', monospace; background: var(--bg0); color: var(--fg); }}
.container {{ display: flex; flex-direction: column; height: 100vh; padding: 8px; overflow: hidden; }}
.header {{ display: flex; align-items: center; justify-content: space-between; background: var(--bg1); padding: 8px 16px; border-radius: 4px; margin-bottom: 8px; }}
.logo {{ color: var(--accent); font-size: 14px; font-weight: bold; }}
.stats {{ display: flex; gap: 24px; }}
.stat {{ text-align: center; }}
.stat-value {{ font-size: 20px; font-weight: bold; }}
.stat-label {{ font-size: 9px; color: var(--fg3); letter-spacing: 1px; }}
.stat-green {{ color: var(--green); }}
.stat-yellow {{ color: var(--yellow); }}
.stat-gray {{ color: var(--fg3); }}
.main {{ display: flex; gap: 8px; flex: 1; min-height: 0; overflow: hidden; }}
.hosts-panel {{ width: 320px; background: var(--bg1); border-radius: 4px; display: flex; flex-direction: column; overflow: hidden; }}
.panel-header {{ padding: 10px 12px; background: var(--bg2); font-size: 11px; letter-spacing: 2px; color: var(--fg3); display: flex; justify-content: space-between; align-items: center; }}
.filter-tabs {{ display: flex; gap: 4px; }}
.filter-tab {{ padding: 4px 10px; background: var(--bg3); border: none; color: var(--fg3); font-size: 9px; cursor: pointer; border-radius: 3px; font-family: inherit; letter-spacing: 1px; }}
.filter-tab:hover {{ color: var(--fg); }}
.filter-tab.active {{ background: var(--accent); color: var(--bg0); }}
.hosts-list {{ flex: 1; overflow-y: auto; padding: 4px; }}
.host {{ background: var(--bg2); border-radius: 4px; padding: 10px 12px; margin-bottom: 4px; cursor: pointer; border-left: 3px solid var(--yellow); position: relative; }}
.host:hover {{ background: var(--bg3); }}
.host.selected {{ background: var(--bg3); border-color: var(--accent); }}
.host.injected {{ border-left-color: var(--green); }}
.host-domain {{ font-weight: 600; font-size: 12px; margin-bottom: 2px; }}
.host-domain::before {{ content: "● "; color: var(--yellow); }}
.host.injected .host-domain::before {{ color: var(--green); }}
.host-badges-row {{ display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: 4px; }}
.host-info {{ font-size: 10px; color: var(--fg3); line-height: 1.6; clear: both; }}
.host-info span {{ color: var(--accent); }}
.badge {{ font-size: 8px; padding: 2px 5px; border-radius: 2px; font-weight: 500; }}
.badge-inj {{ background: var(--green); color: var(--bg0); }}
.badge-notinj {{ background: var(--yellow); color: var(--bg0); }}
.badge-time {{ background: var(--purple); color: var(--fg); }}
.badge-error {{ background: var(--red); color: var(--fg); }}
.badge-union {{ background: var(--accent); color: var(--bg0); }}
.badge-boolean {{ background: var(--cyan); color: var(--bg0); }}
.badge-stacked {{ background: var(--orange); color: var(--bg0); }}
.detail-panel {{ flex: 1; background: var(--bg1); border-radius: 4px; display: flex; flex-direction: column; overflow: hidden; }}
.detail-header {{ padding: 10px 16px; background: var(--bg2); display: flex; justify-content: space-between; align-items: center; }}
.detail-domain {{ font-size: 14px; font-weight: 600; }}
.detail-tabs {{ display: flex; gap: 4px; }}
.detail-tab {{ background: var(--bg3); border: none; color: var(--fg3); padding: 6px 14px; font-size: 10px; cursor: pointer; border-radius: 3px; font-family: inherit; letter-spacing: 1px; }}
.detail-tab:hover {{ background: var(--bg1); color: var(--fg); }}
.detail-tab.active {{ background: var(--accent); color: var(--bg0); }}
.detail-tab.sqlmap {{ background: var(--purple); color: var(--fg); }}
.detail-tab.sqlmap.active {{ background: var(--green); color: var(--bg0); }}
.detail-content {{ flex: 1; overflow: hidden; padding: 16px; min-height: 0; display: flex; flex-direction: column; }}
.info-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
.info-item {{ background: var(--bg2); padding: 12px; border-radius: 4px; }}
.info-label {{ font-size: 9px; color: var(--fg3); letter-spacing: 1px; margin-bottom: 4px; }}
.info-value {{ font-size: 13px; color: var(--green); word-break: break-all; }}
.info-value.yellow {{ color: var(--yellow); }}
.info-value.accent {{ color: var(--accent); }}
.empty-state {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--fg3); }}
.empty-icon {{ font-size: 48px; margin-bottom: 16px; }}
.log-box {{ background: var(--bg0); border-radius: 4px; padding: 12px; font-size: 11px; line-height: 1.5; max-height: 100%; overflow-y: auto; }}
.log-box pre {{ margin: 0; white-space: pre-wrap; word-wrap: break-word; color: var(--fg3); }}
.log-line.info {{ color: var(--accent); }}
.log-line.warning {{ color: var(--yellow); }}
.log-line.critical {{ color: var(--green); font-weight: bold; }}
.log-line.error {{ color: var(--red); }}
.dumps-list {{ display: flex; flex-direction: column; gap: 8px; }}
.dump-db {{ background: var(--bg2); border-radius: 4px; overflow: hidden; }}
.dump-db-header {{ padding: 10px 12px; background: var(--bg3); font-size: 12px; font-weight: bold; color: var(--accent); cursor: pointer; }}
.dump-tables {{ padding: 8px; display: flex; flex-wrap: wrap; gap: 6px; }}
.dump-table {{ padding: 6px 12px; background: var(--bg1); border-radius: 3px; font-size: 11px; cursor: pointer; }}
.dump-table:hover {{ background: var(--accent); color: var(--bg0); }}
.pty-container {{ display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: hidden; }}
.pty-quick {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
.pty-btn {{ padding: 6px 12px; background: var(--bg2); border: 1px solid var(--bg3); color: var(--fg3); font-size: 10px; cursor: pointer; border-radius: 3px; font-family: inherit; }}
.pty-btn:hover {{ background: var(--bg3); color: var(--fg); border-color: var(--accent); }}
.pty-terminal {{ flex: 1; background: var(--bg0); border-radius: 4px; padding: 12px; font-size: 11px; overflow-y: auto; min-height: 0; }}
.pty-output {{ white-space: pre-wrap; word-wrap: break-word; color: var(--fg3); line-height: 1.4; }}
.pty-cmd {{ color: var(--green); }}
.pty-result {{ color: var(--fg3); }}
.pty-error {{ color: var(--red); }}
.pty-success {{ color: var(--green); font-weight: bold; }}
.pty-input-row {{ display: flex; gap: 8px; margin-top: 8px; flex-shrink: 0; }}
.pty-input {{ flex: 1; background: var(--bg2); border: 1px solid var(--bg3); color: var(--fg); padding: 8px 12px; border-radius: 4px; font-family: inherit; font-size: 11px; min-height: 40px; max-height: 60px; resize: none; word-break: break-all; white-space: pre-wrap; }}
.pty-input:focus {{ outline: none; border-color: var(--accent); }}
.pty-exec {{ padding: 6px 14px; background: var(--green); border: none; color: var(--bg0); font-family: inherit; font-size: 10px; letter-spacing: 1px; cursor: pointer; border-radius: 3px; font-weight: bold; }}
.pty-exec:hover {{ background: var(--accent); }}
.pty-stop {{ padding: 6px 14px; background: var(--orange); border: none; color: var(--bg0); font-family: inherit; font-size: 10px; letter-spacing: 1px; cursor: pointer; border-radius: 3px; font-weight: bold; }}
.pty-stop:hover {{ background: var(--red); }}
.pty-clear {{ padding: 6px 14px; background: var(--bg3); border: none; color: var(--fg3); font-family: inherit; font-size: 10px; letter-spacing: 1px; cursor: pointer; border-radius: 3px; }}
.pty-clear:hover {{ background: var(--bg1); }}
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg1); }}
::-webkit-scrollbar-thumb {{ background: var(--bg3); border-radius: 3px; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
</style>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body>
<div class="container">
    <div class="header">
        <div class="logo">6319sqli</div>
        <div class="stats">
            <div class="stat"><div class="stat-value stat-green">{len(injected)}</div><div class="stat-label">INJECTED</div></div>
            <div class="stat"><div class="stat-value stat-yellow">{len(not_injected)}</div><div class="stat-label">NOT INJ</div></div>
            <div class="stat"><div class="stat-value stat-gray">{len(hosts)}</div><div class="stat-label">TOTAL</div></div>
        </div>
    </div>
    <div class="main">
        <div class="hosts-panel">
            <div class="panel-header">
                <span>HOSTS</span>
                <div class="filter-tabs">
                    <button class="filter-tab active" onclick="filter('all')">ALL</button>
                    <button class="filter-tab" onclick="filter('inj')">INJECTED</button>
                    <button class="filter-tab" onclick="filter('not')">NOT INJ</button>
                </div>
            </div>
            <div class="hosts-list" id="hostsList">{hosts_html if hosts_html else '<div class="empty-state"><div class="empty-icon">📂</div>No hosts found</div>'}</div>
        </div>
        <div class="detail-panel">
            <div class="detail-header">
                <div class="detail-domain" id="dd">Select a host</div>
                <div class="detail-tabs">
                    <button class="detail-tab active" onclick="showTab('info')">INFO</button>
                    <button class="detail-tab sqlmap" onclick="showTab('sqlmap')">SQLMAP</button>
                    <button class="detail-tab" onclick="showTab('log')">LOG</button>
                    <button class="detail-tab" onclick="showTab('dumps')">DUMPS</button>
                </div>
            </div>
            <div class="detail-content" id="dc">
                <div class="empty-state"><div class="empty-icon">📡</div>Select a host to view details</div>
            </div>
        </div>
    </div>
</div>
<script>
// Initialize Streamlit component communication
function initStreamlit() {{
    if (window.Streamlit) {{
        window.Streamlit.setComponentReady();
        window.Streamlit.setFrameHeight(window.innerHeight || document.documentElement.clientHeight || 900);
    }}
}}
window.addEventListener('load', initStreamlit);
window.addEventListener('resize', function() {{
    if (window.Streamlit) window.Streamlit.setFrameHeight(window.innerHeight || 900);
}});

// Streamlit communication function
function sendAction(data) {{
    if (window.Streamlit) {{
        window.Streamlit.setComponentValue(data);
    }}
}}

const hosts = {json.dumps(hosts_safe)};
let selected = null;
let currentTab = 'info';

function filter(f) {{
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.host').forEach(h => {{
        const isInj = h.classList.contains('injected');
        if (f === 'all') h.style.display = 'block';
        else if (f === 'inj') h.style.display = isInj ? 'block' : 'none';
        else h.style.display = isInj ? 'none' : 'block';
    }});
}}

function select(key) {{
    document.querySelectorAll('.host').forEach(h => h.classList.remove('selected'));
    event.currentTarget.classList.add('selected');
    selected = key;
    showTab(currentTab);
    document.getElementById('dd').textContent = hosts[key].domain;
}}

function showTab(tab) {{
    currentTab = tab;
    document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.detail-tab').forEach(t => {{ 
        if(t.textContent === tab.toUpperCase() || (tab === 'sqlmap' && t.classList.contains('sqlmap'))) t.classList.add('active'); 
    }});
    
    if (!selected) {{
        document.getElementById('dc').innerHTML = '<div class="empty-state"><div class="empty-icon">📡</div>Select a host to view details</div>';
        return;
    }}
    
    const h = hosts[selected];
    let html = '';
    
    if (tab === 'info') {{
        html = `
            <div class="info-grid">
                <div class="info-item"><div class="info-label">STATUS</div><div class="info-value ${{h.injected ? '' : 'yellow'}}">${{h.injected ? 'VULNERABLE' : 'NOT VULNERABLE'}}</div></div>
                <div class="info-item"><div class="info-label">DBMS</div><div class="info-value accent">${{h.dbms || 'Unknown'}}</div></div>
                <div class="info-item"><div class="info-label">TECHNIQUES</div><div class="info-value accent">${{(h.techniques || []).map(t=>t.toUpperCase()).join(', ') || 'None'}}</div></div>
                <div class="info-item"><div class="info-label">PARAMETERS</div><div class="info-value accent">${{(h.parameters || []).join(', ') || 'None'}}</div></div>
            </div>
            <div class="info-item" style="margin-top:12px"><div class="info-label">TARGET URL</div><div class="info-value accent" style="font-size:11px">${{h.target_url || 'N/A'}}</div></div>
            <div class="info-item" style="margin-top:12px"><div class="info-label">OUTPUT PATH</div><div class="info-value accent" style="font-size:11px">${{h.path || 'N/A'}}</div></div>
        `;
    }} else if (tab === 'sqlmap') {{
        let sqlmapContent = h.sqlmap_output || '';
        if (!sqlmapContent) {{
            sqlmapContent = `Waiting for sqlmap command...\\nTarget: ${{h.target_url || 'N/A'}}\\nSession: ${{h.path || 'N/A'}}`;
        }}
        const escapedContent = sqlmapContent.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html = `
            <div style="display:flex;flex-direction:column;height:100%;gap:8px">
                <div style="display:flex;flex-wrap:wrap;gap:4px">
                    <button class="pty-btn" onclick="addFlag('--dbs')">--dbs</button>
                    <button class="pty-btn" onclick="addFlag('--tables')">--tables</button>
                    <button class="pty-btn" onclick="addFlag('--columns')">--columns</button>
                    <button class="pty-btn" onclick="addFlag('--dump')">--dump</button>
                    <button class="pty-btn" onclick="addFlag('--os-shell')">--os-shell</button>
                    <button class="pty-btn" onclick="addFlag('--sql-shell')">--sql-shell</button>
                    <button class="pty-btn" onclick="addFlag('--passwords')">--passwords</button>
                    <button class="pty-btn" onclick="addFlag('--current-user')">--current-user</button>
                    <button class="pty-btn" onclick="addFlag('--current-db')">--current-db</button>
                    <button class="pty-btn" onclick="addFlag('--is-dba')">--is-dba</button>
                </div>
                <div class="log-box" style="flex:1;overflow-y:auto"><pre id="sqlmap-output">${{escapedContent}}</pre></div>
                <div style="display:flex;gap:8px;align-items:center;background:var(--bg2);padding:8px;border-radius:4px">
                    <textarea id="sqlmap-cmd" placeholder="proxychains4 -q python3 /root/sqlmap/sqlmap.py -u URL --batch ..." style="flex:1;background:var(--bg0);border:1px solid var(--bg3);color:var(--fg);padding:8px;border-radius:4px;font-family:inherit;font-size:10px;resize:vertical;min-height:60px;max-height:120px;word-break:break-all;overflow-wrap:break-word">${{h.original_cmd || ''}}</textarea>
                    <div style="display:flex;flex-direction:column;gap:4px">
                        <button onclick="runSqlmap()" style="background:var(--green);color:var(--bg0);border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-family:inherit;font-weight:bold;font-size:10px">RUN</button>
                        <button onclick="stopSqlmap()" style="background:var(--red);color:var(--fg);border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-family:inherit;font-weight:bold;font-size:10px">STOP</button>
                        <button onclick="clearOutput()" style="background:var(--bg3);color:var(--fg);border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-family:inherit;font-weight:bold;font-size:10px">CLEAR</button>
                    </div>
                </div>
            </div>
        `;
    }} else if (tab === 'log') {{
        const logContent = h.log_content || 'No log content available';
        const escapedLog = logContent.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html = `<div class="log-box"><pre>${{escapedLog}}</pre></div>`;
    }} else if (tab === 'dumps') {{
        const dumps = h.dumps || [];
        if (dumps.length === 0) {{
            html = '<div class="empty-state"><div class="empty-icon">📦</div>No dumps available</div>';
        }} else {{
            html = '<div class="dumps-list">' + dumps.map(d => `
                <div class="dump-db">
                    <div class="dump-db-header">📁 ${{d.db}}</div>
                    <div class="dump-tables">${{d.tables.map(t => `<div class="dump-table">${{t}}</div>`).join('')}}</div>
                </div>
            `).join('') + '</div>';
        }}
    }}
    
    document.getElementById('dc').innerHTML = html;
}}

function addFlag(flag) {{
    const input = document.getElementById('sqlmap-cmd');
    if (input) {{
        const current = input.value.trim();
        if (current && !current.includes(flag)) {{
            input.value = current + ' ' + flag;
        }} else if (!current) {{
            input.value = flag;
        }}
        input.focus();
    }}
}}

// Send action via Streamlit component value mechanism
function writeAction(action, host, cmd) {{
    var actionData = {{action: action, host: host || '', cmd: cmd || '', ts: Date.now()}};
    
    // Try to find Streamlit object in parent chain and use setComponentValue
    var st = null;
    try {{
        if (window.parent && window.parent.Streamlit) {{
            st = window.parent.Streamlit;
        }} else if (window.parent && window.parent.parent && window.parent.parent.Streamlit) {{
            st = window.parent.parent.Streamlit;
        }} else if (window.top && window.top.Streamlit) {{
            st = window.top.Streamlit;
        }}
    }} catch(e) {{}}
    
    if (st && st.setComponentValue) {{
        st.setComponentValue(actionData);
        return;
    }}
    
    // Fallback: use action server on port 5001
    var port = 5001;
    var url = window.location.protocol + '//' + window.location.hostname + ':' + port + '/?action=' + encodeURIComponent(action) + '&host=' + encodeURIComponent(host || '') + '&cmd=' + encodeURIComponent(cmd || '');
    fetch(url).catch(function(e){{}});
    
    // Also try postMessage
    try {{ window.parent.postMessage({{type: 'sqlmap_action', ...actionData}}, '*'); }} catch(e) {{}}
}}

function runSqlmap() {{
    const input = document.getElementById('sqlmap-cmd');
    if (!input || !selected) {{
        alert('Select a host first');
        return;
    }}
    const cmd = input.value.trim();
    if (!cmd) {{
        alert('Enter sqlmap command');
        return;
    }}
    document.getElementById('sqlmap-output').textContent = 'Starting command...';
    writeAction('run', selected, cmd);
}}

function stopSqlmap() {{
    document.getElementById('sqlmap-output').textContent += '\\n[Stopping...]';
    writeAction('stop', '', '');
}}

function clearOutput() {{
    if (selected) {{
        document.getElementById('sqlmap-output').textContent = 'Clearing...';
        writeAction('clear', selected, '');
    }}
}}

function fitToWindow() {{
    var h = window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;
    document.querySelector('.container').style.height = h + 'px';
}}
window.addEventListener('resize', fitToWindow);
window.addEventListener('load', fitToWindow);
fitToWindow();
setInterval(fitToWindow, 1000);
</script>
</body>
</html>
'''

# Render SQLMAP HTML and capture any action from component
component_value = components.html(html, height=900, scrolling=False)
st.markdown("""<style>
iframe[title="streamlit_components.v1.components.html"] {
    height:100vh!important;width:100vw!important;position:fixed!important;
    top:0!important;left:0!important;z-index:9999!important;border:none!important;
}
div:has(> iframe[title="streamlit_components.v1.components.html"]),
div[data-testid="stHtml"]:has(iframe),
div[data-testid="element-container"]:has(iframe) {
    height:100vh!important;width:100vw!important;position:fixed!important;
    top:0!important;left:0!important;z-index:9998!important;
    max-height:none!important;overflow:visible!important;
}
</style>""", unsafe_allow_html=True)

# Process action from component value
if component_value is not None and isinstance(component_value, dict):
    action = component_value.get('action', '')
    host = component_value.get('host', '')
    cmd = component_value.get('cmd', '')
    
    if action == 'run' and host and cmd:
        import threading as th2
        cmd = ensure_proxychains(cmd)
        output_file = get_host_output_file(host)
        
        def run_from_component():
            with open(RUNNING_FILE, 'w') as f:
                json.dump({'running': True, 'host': host, 'cmd': cmd}, f)
            with open(output_file, 'w') as f:
                f.write(f'$ {cmd}\n')
                f.flush()
            try:
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                process = subprocess.Popen(
                    f'stdbuf -oL -eL {cmd}',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=env
                )
                import select
                import fcntl
                fd = process.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                with open(output_file, 'a') as out_f:
                    while True:
                        ready, _, _ = select.select([process.stdout], [], [], 0.5)
                        if ready:
                            try:
                                data = process.stdout.read(4096)
                                if data:
                                    out_f.write(data.decode('utf-8', errors='replace'))
                                    out_f.flush()
                            except:
                                pass
                        if process.poll() is not None:
                            try:
                                remaining = process.stdout.read()
                                if remaining:
                                    out_f.write(remaining.decode('utf-8', errors='replace'))
                                    out_f.flush()
                            except:
                                pass
                            break
                    out_f.write(f'\n[Done - exit code {process.returncode}]\n')
                    out_f.flush()
            except Exception as e:
                with open(output_file, 'a') as f:
                    f.write(f'\n[ERROR] {str(e)}\n')
            finally:
                with open(RUNNING_FILE, 'w') as f:
                    json.dump({'running': False}, f)
        
        th2.Thread(target=run_from_component, daemon=True).start()
        st.rerun()
    
    elif action == 'stop':
        try:
            subprocess.run(['pkill', '-f', 'sqlmap'], capture_output=True)
        except:
            pass
        with open(RUNNING_FILE, 'w') as f:
            json.dump({'running': False}, f)
        st.rerun()
    
    elif action == 'clear' and host:
        output_file = get_host_output_file(host)
        with open(output_file, 'w') as f:
            f.write('')
        st.rerun()
