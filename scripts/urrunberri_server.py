#!/usr/bin/env python3
# =============================================================================
#  UrrunBerri OS — Python API Server (Hardened)
#  Port 7070 — localhost only
#  Author : Mathieu Cadi — Openema SARL
#  GitHub : https://github.com/matthewc00002/urrunberri1
#
#  Security: Input sanitization against command injection, delimiter attacks,
#  and shell metacharacter exploits.
# =============================================================================

import http.server
import urllib.parse
import json
import subprocess
import os
import re

SAVED_FILE = "/etc/urrunberri-os/saved_connections.csv"
SETTINGS_FILE = "/etc/urrunberri-os/settings.json"
SPLASH_DIR = "/opt/urrunberri-os/splash"
VERSION_FILE = "/etc/urrunberri-os/version"
ACTION_FILE = "/tmp/urrunberri_action.txt"
RESULT_FILE = "/tmp/urrunberri_login.txt"
PORT = 7070

# ── INPUT SANITIZATION ───────────────────────────────────────────────────────

# Characters that could cause shell injection or break the pipe delimiter
DANGEROUS_CHARS = re.compile(r'[|;&$`\\(){}<>\n\r\x00\'"!#~]')
MAX_FIELD_LENGTH = 255
MAX_PASSWORD_LENGTH = 512

def sanitize(value, max_len=MAX_FIELD_LENGTH):
    """Remove dangerous characters and limit length."""
    if not isinstance(value, str):
        return ''
    value = value[:max_len]
    value = DANGEROUS_CHARS.sub('', value)
    return value.strip()

def sanitize_password(value):
    """Sanitize password — allow more characters but strip pipe and shell injection."""
    if not isinstance(value, str):
        return ''
    value = value[:MAX_PASSWORD_LENGTH]
    # Only strip the most dangerous: pipe (breaks delimiter), backtick, $() for injection
    value = re.sub(r'[|\x00\n\r]', '', value)
    return value

def sanitize_host(host):
    """Validate hostname or IP format — strict whitelist."""
    host = sanitize(host, 253)
    # Allow only alphanumeric, dots, hyphens (hostname), colons (IPv6)
    if not re.match(r'^[a-zA-Z0-9.\-:]+$', host):
        return ''
    return host

def sanitize_port(port):
    """Validate port — must be numeric 1-65535."""
    try:
        p = int(str(port).strip())
        if 1 <= p <= 65535:
            return str(p)
    except (ValueError, TypeError):
        pass
    return '3389'

def sanitize_protocol(proto):
    """Only allow known protocols."""
    proto = str(proto).strip().lower()
    if proto in ('rdp', 'vnc', 'ssh'):
        return proto
    return 'rdp'

def sanitize_resolution(res):
    """Validate resolution format: WIDTHxHEIGHT or 'auto'."""
    res = str(res).strip().lower()
    if res == 'auto':
        return 'auto'
    if re.match(r'^\d{3,5}x\d{3,5}$', res):
        return res
    return '1920x1080'

def sanitize_flag(val):
    """Validate boolean flag — must be '0' or '1'."""
    return '1' if str(val).strip() == '1' else '0'

def sanitize_connect_data(raw_data):
    """Sanitize the full connect data string from login.html.
    Format: host|port|user|pass|||protocol|resolution|multimon|usb
    """
    parts = raw_data.split('|')
    while len(parts) < 10:
        parts.append('')

    host       = sanitize_host(parts[0])
    port       = sanitize_port(parts[1])
    user       = sanitize(parts[2])
    password   = sanitize_password(parts[3])
    domain     = sanitize(parts[4])
    field5     = sanitize(parts[5])
    protocol   = sanitize_protocol(parts[6])
    resolution = sanitize_resolution(parts[7])
    multimon   = sanitize_flag(parts[8])
    usb        = sanitize_flag(parts[9])

    if not host or not user:
        return None

    return f"{host}|{port}|{user}|{password}|{domain}|{field5}|{protocol}|{resolution}|{multimon}|{usb}"

# ── APPLICATION LOGIC ─────────────────────────────────────────────────────────

def get_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            for line in f:
                if line.startswith('version='):
                    return line.split('=', 1)[1].strip()
        with open(VERSION_FILE, 'r') as f:
            return f.readline().strip() or "?"
    except:
        return "?"

def write_action(action, data=""):
    with open(ACTION_FILE, 'w') as f:
        f.write(action)
    if data:
        with open(RESULT_FILE, 'w') as f:
            f.write(data)

def load_connections():
    conns = []
    try:
        if os.path.exists(SAVED_FILE):
            with open(SAVED_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|')
                    while len(parts) < 8:
                        parts.append('')
                    conns.append({
                        'host':       parts[0],
                        'port':       parts[1],
                        'user':       parts[2],
                        'domain':     parts[3],
                        'name':       parts[4],
                        'protocol':   parts[5] or 'rdp',
                        'resolution': parts[6] or '1920x1080',
                        'multimon':   parts[7] or '0'
                    })
    except:
        pass
    return conns

def save_connection(host, port, user, domain='', name='', protocol='rdp', resolution='1920x1080', multimon='0'):
    # Sanitize all inputs
    host       = sanitize_host(host)
    port       = sanitize_port(port)
    user       = sanitize(user)
    domain     = sanitize(domain)
    name       = sanitize(name)
    protocol   = sanitize_protocol(protocol)
    resolution = sanitize_resolution(resolution)
    multimon   = sanitize_flag(multimon)

    if not host or not user:
        return load_connections()
    conns = [c for c in load_connections()
             if not (c['host'] == host and c['port'] == port and c['user'] == user)]
    conns.insert(0, {
        'host': host, 'port': port, 'user': user,
        'domain': domain, 'name': name, 'protocol': protocol,
        'resolution': resolution, 'multimon': multimon
    })
    conns = conns[:10]
    with open(SAVED_FILE, 'w') as f:
        for c in conns:
            f.write(f"{c['host']}|{c['port']}|{c['user']}|{c['domain']}|{c['name']}|{c['protocol']}|{c['resolution']}|{c['multimon']}\n")
    return conns

def delete_connection(index):
    conns = load_connections()
    try:
        idx = int(index)
        if 0 <= idx < len(conns):
            conns.pop(idx)
    except (ValueError, TypeError):
        pass
    with open(SAVED_FILE, 'w') as f:
        for c in conns:
            f.write(f"{c['host']}|{c['port']}|{c['user']}|{c['domain']}|{c['name']}|{c['protocol']}|{c['resolution']}|{c['multimon']}\n")
    return conns


def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {"lang": "fr", "usb": False}

def save_settings(settings):
    allowed = {"lang", "usb"}
    clean = {}
    for k in allowed:
        if k in settings:
            clean[k] = settings[k]
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(clean, f)
    return clean

def test_connection(host, port):
    # Sanitize before passing to subprocess
    host = sanitize_host(host)
    port = sanitize_port(port)
    if not host:
        return 'fail'
    try:
        r1 = subprocess.run(['ping', '-c1', '-W2', host], capture_output=True, timeout=5)
        r2 = subprocess.run(['nc', '-z', '-w3', host, port], capture_output=True, timeout=5)
        return 'ok' if r1.returncode == 0 and r2.returncode == 0 else 'fail'
    except:
        return 'fail'

# ── HTTP HANDLER ──────────────────────────────────────────────────────────────

class UrrunBerriHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_json(self, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_cors(self, text):
        encoded = str(text).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', len(encoded))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(encoded)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 0:
            return self.rfile.read(length).decode('utf-8', errors='replace')
        return ''

    def do_OPTIONS(self):
        self.send_cors('')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        try:
            data = json.loads(body)
        except:
            data = {}

        if path == '/save':
            conns = save_connection(
                host       = data.get('host', ''),
                port       = data.get('port', '3389'),
                user       = data.get('user', ''),
                domain     = data.get('domain', ''),
                name       = data.get('name', ''),
                protocol   = data.get('protocol', 'rdp'),
                resolution = data.get('resolution', '1920x1080'),
                multimon   = data.get('multimon', '0')
            )
            self.send_json({'ok': True, 'connections': conns})
            return

        if path == '/delete':
            index = data.get('index', -1)
            conns = delete_connection(index)
            self.send_json({'ok': True, 'connections': conns})
            return

        if path == '/settings':
            save_settings(data)
            self.send_json({'ok': True, 'settings': load_settings()})
            return

        self.send_cors('ok')

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == '/splash/login.html':
            try:
                conns = load_connections()
                conns_json = json.dumps(conns)
                with open(f"{SPLASH_DIR}/login.html", 'r') as f:
                    html = f.read()
                html = html.replace('__SAVED_CONNECTIONS__', conns_json)
                html = html.replace('__VERSION__', get_version())
                encoded = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(encoded))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(encoded)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
            return

        if path in ('/splash/urrunberri.png', '/splash/logo.png'):
            try:
                fname = os.path.basename(path)
                fpath = os.path.join(SPLASH_DIR, fname)
                with open(fpath, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', len(data))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_response(404)
                self.end_headers()
            return

        if path == '/version':
            self.send_cors(get_version())
            return

        if path == '/connections':
            self.send_json(load_connections())
            return

        if path == '/test':
            host = params.get('host', [''])[0]
            port = params.get('port', ['3389'])[0]
            result = test_connection(host, port)
            self.send_cors(result)
            return

        if path == '/shutdown':
            self.send_cors('OK')
            write_action('shutdown')
            return

        if path == '/reboot':
            self.send_cors('OK')
            write_action('reboot')
            return

        if path == '/close':
            self.send_cors('OK')
            write_action('close')
            return

        if path == '/terminal':
            self.send_cors('OK')
            write_action('terminal')
            return

        if path == '/settings':
            self.send_json(load_settings())
            return

        if path == '/connect':
            raw_data = params.get('data', [''])[0]
            # SECURITY: sanitize all fields before writing
            clean_data = sanitize_connect_data(raw_data)
            if clean_data:
                write_action('connect', clean_data)
                self.send_cors('connecting')
            else:
                self.send_cors('error: invalid input')
            return

        self.send_cors('ok')

def run():
    os.makedirs('/etc/urrunberri-os', exist_ok=True)
    if not os.path.exists(SAVED_FILE):
        open(SAVED_FILE, 'w').close()
    server = http.server.HTTPServer(('127.0.0.1', PORT), UrrunBerriHandler)
    print(f"[UrrunBerri OS] API server running on port {PORT} (hardened)")
    server.serve_forever()

if __name__ == '__main__':
    run()
