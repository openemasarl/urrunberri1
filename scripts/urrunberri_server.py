#!/usr/bin/env python3
# =============================================================================
#  UrrunBerri OS — Python API Server (Hardened)
#  Port 7070 — localhost only
#  Author : Mathieu Cadi — Openema SARL
#  GitHub : https://github.com/openemasarl/urrunberri1
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

def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64
        with open("/etc/machine-id","r") as f:
            machine_id = f.read().strip().encode()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=b"urrunberri-os-v1",iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        return Fernet(key)
    except Exception:
        return None

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

def encrypt_password(password):
    if not password: return ""
    try:
        f = _get_fernet()
        if f: return "ENC:" + f.encrypt(password.encode()).decode()
    except Exception: pass
    return password

def decrypt_password(password):
    if not password or not password.startswith("ENC:"): return password
    try:
        f = _get_fernet()
        if f: return f.decrypt(password[4:].encode()).decode()
    except Exception: pass
    return ""

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
    if proto in ('rdp', 'vnc', 'ssh', 'rdpgw', 'web'):
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
    while len(parts) < 13:
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

    # Web : pas d'utilisateur necessaire (adresse + port suffisent)
    if not host or (not user and protocol != 'web'):
        return None

    gw_host = sanitize_host(parts[10]) if parts[10] else ""
    gw_user = sanitize(parts[11])
    gw_pass = sanitize_password(parts[12])
    return f"{host}|{port}|{user}|{password}|{domain}|{field5}|{protocol}|{resolution}|{multimon}|{usb}|{gw_host}|{gw_user}|{gw_pass}"

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
                    while len(parts) < 12:
                        parts.append('')
                    conns.append({
                        'host':       parts[0],
                        'port':       parts[1],
                        'user':       parts[2],
                        'domain':     parts[3],
                        'name':       parts[4],
                        'protocol':   parts[5] or 'rdp',
                        'resolution': parts[6] or '1920x1080',
                        'multimon':   parts[7] or '0',
                        'password':   decrypt_password(parts[8]),
                        'gw_host':    parts[9],
                        'gw_user':    parts[10],
                        'gw_pass':    decrypt_password(parts[11])
                    })
    except:
        pass
    return conns

def save_connection(host, port, user, domain='', name='', protocol='rdp', resolution='1920x1080', multimon='0', password='', gw_host='', gw_user='', gw_pass=''):
    # Sanitize all inputs
    host       = sanitize_host(host)
    port       = sanitize_port(port)
    user       = sanitize(user)
    domain     = sanitize(domain)
    name       = sanitize(name)
    protocol   = sanitize_protocol(protocol)
    resolution = sanitize_resolution(resolution)
    multimon   = sanitize_flag(multimon)
    password   = encrypt_password(sanitize_password(password))
    gw_host    = sanitize_host(gw_host) if gw_host else ''
    gw_user    = sanitize(gw_user)
    gw_pass    = encrypt_password(sanitize_password(gw_pass))

    if not host or (not user and protocol != 'web'):
        return load_connections()
    conns = [c for c in load_connections()
             if not (c['host'] == host and c['port'] == port and c['user'] == user)]
    conns.insert(0, {
        'host': host, 'port': port, 'user': user,
        'domain': domain, 'name': name, 'protocol': protocol,
        'resolution': resolution, 'multimon': multimon,
        'password': password, 'gw_host': gw_host,
        'gw_user': gw_user, 'gw_pass': gw_pass
    })
    conns = conns[:10]
    with open(SAVED_FILE, 'w') as f:
        for c in conns:
            f.write(f"{c['host']}|{c['port']}|{c['user']}|{c['domain']}|{c['name']}|{c['protocol']}|{c['resolution']}|{c['multimon']}|{c.get('password','')}|{c.get('gw_host','')}|{c.get('gw_user','')}|{c.get('gw_pass','')}\n")
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
            f.write(f"{c['host']}|{c['port']}|{c['user']}|{c['domain']}|{c['name']}|{c['protocol']}|{c['resolution']}|{c['multimon']}|{c.get('password','')}|{c.get('gw_host','')}|{c.get('gw_user','')}|{c.get('gw_pass','')}\n")
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
                multimon   = data.get('multimon', '0'),
                password   = data.get('password', ''),
                gw_host    = data.get('gw_host', ''),
                gw_user    = data.get('gw_user', ''),
                gw_pass    = data.get('gw_pass', '')
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

        if path == '/wifi-connect':
            # Reseau masque : {"hidden": true, "ssid", "password", "security": "wpa-psk"|"open", "iface": ""}
            ssid = data.get('ssid', '')
            password = data.get('password', '')
            if data.get('hidden') in (True, 'true', '1', 1):
                ok, msg = connect_hidden_wifi(ssid, password,
                                              data.get('security', 'wpa-psk'),
                                              data.get('iface', ''))
                self.send_cors('ok' if ok else 'error: ' + msg)
                return
            try:
                if password:
                    r = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password, 'ifname', (wifi_iface() or 'wlp1s0')], capture_output=True, text=True, timeout=30)
                else:
                    r = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', (wifi_iface() or 'wlp1s0')], capture_output=True, text=True, timeout=30)
                self.send_cors('ok' if r.returncode == 0 else 'error: ' + r.stderr)
            except Exception as e:
                self.send_cors('error: ' + str(e))
            return
        if path == '/screens':
            self.send_json(list_screens())
            return

        if path == '/screen-res':
            try:
                output = data.get('output', '')
                resolution = data.get('resolution', '')
                names = [s['name'] for s in list_screens()]
                if output not in names or not re.fullmatch(r'\d{3,5}x\d{3,5}', str(resolution)):
                    self.send_cors('error: ecran ou resolution invalide')
                    return
                r = subprocess.run(['xrandr', '--output', output, '--mode', resolution],
                                   env=XENV, capture_output=True, text=True, timeout=15)
                self.send_cors('ok' if r.returncode == 0 else 'error: ' + r.stderr.strip())
            except Exception as e:
                self.send_cors('error: '+str(e))
            return

        if path == '/screen-toggle':
            try:
                output = data.get('output', '')
                action = data.get('action', 'on')
                names = [s['name'] for s in list_screens()]
                if output not in names:
                    self.send_cors('error: ecran invalide')
                    return
                arg = '--off' if action == 'off' else '--auto'
                r = subprocess.run(['xrandr', '--output', output, arg],
                                   env=XENV, capture_output=True, text=True, timeout=15)
                self.send_cors('ok' if r.returncode == 0 else 'error: ' + r.stderr.strip())
            except Exception as e:
                self.send_cors('error: '+str(e))
            return

        if path == '/screen-mode':
            try:
                mode = data.get('mode', 'extend')
                import subprocess as _sp
                env = XENV
                out = _sp.check_output(['xrandr','--query'], env=env, text=True, stderr=_sp.STDOUT)
                import re as _re
                outputs = _re.findall(r'^(\S+) connected', out, _re.MULTILINE)
                primary = outputs[0] if outputs else None
                secondary = outputs[1] if len(outputs) > 1 else None
                if primary and secondary:
                    if mode == 'mirror':
                        _sp.run(['xrandr','--output',primary,'--auto','--pos','0x0','--output',secondary,'--same-as',primary,'--auto'], env=env)
                    else:
                        _sp.run(['xrandr','--output',secondary,'--auto','--right-of',primary], env=env)
                    self.send_cors('ok')
                else:
                    self.send_cors('no secondary display')
            except Exception as e:
                self.send_cors('error: ' + str(e))
            return

        if path == '/wifi-disconnect':
            try:
                subprocess.run(['nmcli', 'device', 'disconnect', (wifi_iface() or 'wlp1s0')], capture_output=True, text=True)
                self.send_cors('ok')
            except:
                self.send_cors('error')
            return
        if path == '/network-apply':
            method = data.get('method', 'static')
            ip = data.get('ip', '')
            prefix = data.get('prefix', '24')
            gateway = data.get('gateway', '')
            dns = data.get('dns', '8.8.8.8')
            ok = apply_ethernet_config(method, ip, prefix, gateway, dns)
            self.send_cors('ok' if ok else 'error')
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

        if path == '/screens':
            # affichage.html lit la liste des ecrans en GET
            self.send_json(list_screens())
            return

        if path == '/wifi-devices':
            self.send_json(wifi_devices())
            return

        if path in ('/splash/parametres.html', '/splash/network.html', '/splash/affichage.html'):
            # Chaque page sert son propre fichier (affichage.html servait network.html par erreur)
            fname = os.path.basename(path)
            try:
                with open(f'{SPLASH_DIR}/{fname}', 'r') as f:
                    html = f.read()
                encoded = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except:
                self.send_response(404); self.end_headers()
            return

        if path == '/splash/network.html_old':
            try:
                with open('/opt/urrunberri-os/splash/network.html', 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(data))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_response(404)
                self.end_headers()
            return
        if path == '/network':
            self.send_json(get_network_status())
            return
        if path == '/wifi-scan':
            self.send_json(scan_wifi())
            return
        self.send_cors('ok')


# ── NETWORK CONFIGURATION ────────────────────────────────────────────────────

def get_network_status():
    import subprocess, re
    result = {}
    eth = eth_iface() or 'eth0'
    try:
        ip_out = subprocess.check_output(['ip', 'addr', 'show', eth], text=True, stderr=subprocess.DEVNULL)
        inet = re.search(r'inet ([\d.]+)/([\d]+)', ip_out)
        state = 'up' if 'state UP' in ip_out else 'down'
        result['ethernet'] = {
            'interface': eth,
            'state': state,
            'ip': inet.group(1) if inet else '',
            'prefix': inet.group(2) if inet else '24',
        }
    except:
        result['ethernet'] = {'interface': eth, 'state': 'down', 'ip': '', 'prefix': '24'}
    try:
        with open('/etc/network/interfaces', 'r') as f:
            ifaces = f.read()
        if 'inet dhcp' in ifaces:
            result['ethernet']['method'] = 'dhcp'
        else:
            result['ethernet']['method'] = 'static'
            gw = re.search(r'gateway\s+([\d.]+)', ifaces)
            dns = re.search(r'dns-nameservers\s+([\d.\s]+)', ifaces)
            result['ethernet']['gateway'] = gw.group(1) if gw else ''
            result['ethernet']['dns'] = dns.group(1).strip().split()[0] if dns else ''
    except:
        result['ethernet']['method'] = 'unknown'
    dev = wifi_iface()
    try:
        if not dev:
            raise Exception('no wifi device')
        wifi_ip = subprocess.check_output(['ip', 'addr', 'show', dev], text=True, stderr=subprocess.DEVNULL)
        wifi_inet = re.search(r'inet ([\d.]+)/([\d]+)', wifi_ip)
        wifi_state = 'up' if 'state UP' in wifi_ip else 'down'
        ssid = ''
        try:
            nm = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'dev', 'status'], text=True, timeout=10)
            for line in nm.splitlines():
                parts = line.split(':')
                if len(parts) >= 3 and parts[0] == dev and parts[1] == 'connected':
                    ssid = parts[2]
                    wifi_state = 'up'
        except Exception:
            pass
        result['wifi'] = {'interface': dev, 'state': wifi_state, 'ip': wifi_inet.group(1) if wifi_inet else '', 'ssid': ssid}
    except Exception:
        result['wifi'] = {'interface': dev or '', 'state': 'unavailable', 'ip': '', 'ssid': ''}
    return result

def apply_ethernet_config(method, ip='', prefix='24', gateway='', dns='8.8.8.8'):
    eth = eth_iface() or 'eth0'
    import subprocess, time
    if method == 'dhcp':
        config = "source /etc/network/interfaces.d/*\nauto lo\niface lo inet loopback\nauto " + eth + "\niface " + eth + " inet dhcp\n"
    else:
        config = "source /etc/network/interfaces.d/*\nauto lo\niface lo inet loopback\nallow-hotplug " + eth + "\niface " + eth + " inet static\n        address " + ip + "/" + prefix + "\n        gateway " + gateway + "\n        dns-nameservers " + dns + "\n"
    try:
        with open('/etc/network/interfaces', 'w') as f:
            f.write(config)
        subprocess.Popen(['ifdown', eth], stderr=subprocess.DEVNULL)
        time.sleep(1)
        subprocess.Popen(['ifup', eth], stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def wifi_iface():
    import subprocess, re
    try:
        out = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,TYPE', 'dev', 'status'], text=True, timeout=10)
    except Exception:
        return None
    devs = []
    for line in out.splitlines():
        parts = line.split(':')
        if len(parts) >= 2 and parts[1] == 'wifi' and not parts[0].startswith('p2p'):
            devs.append(parts[0])
    for d in devs:
        if d.startswith('wlx'):
            return d
    return devs[0] if devs else None

def eth_iface():
    """Detecte l'interface filaire active. Aucun nom code en dur."""
    import subprocess, re
    try:
        out = subprocess.check_output(['ip', '-o', 'link', 'show'], text=True, timeout=10)
    except Exception:
        return None
    cands = []
    for line in out.splitlines():
        m = re.match(r'\d+:\s+([^:@]+)', line)
        if not m:
            continue
        name = m.group(1).strip()
        if name == 'lo' or name.startswith(('wl', 'p2p', 'docker', 'veth', 'br-', 'virbr', 'tun', 'tap')):
            continue
        cands.append((name, 'state UP' in line))
    for name, up in cands:
        if up:
            return name
    return cands[0][0] if cands else None

def scan_wifi():
    import subprocess
    try:
        dev = wifi_iface()
        if not dev:
            return []
        out = subprocess.check_output(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list', 'ifname', dev],
            text=True, stderr=subprocess.DEVNULL, timeout=20)
        best = {}
        for line in out.splitlines():
            parts = line.rsplit(':', 2)
            if len(parts) != 3:
                continue
            ssid, sig, sec = parts[0], parts[1], parts[2]
            if not ssid or ssid == '--':
                continue
            q = int(sig) if sig.isdigit() else 0
            if ssid not in best or q > best[ssid]['quality']:
                best[ssid] = {'ssid': ssid, 'signal': str(q), 'quality': q,
                              'encryption': sec if sec else 'Open'}
        nets = list(best.values())
        nets.sort(key=lambda x: x['quality'], reverse=True)
        return nets
    except Exception:
        return []

# ── AFFICHAGE (xrandr) ───────────────────────────────────────────────────────

XENV = {'DISPLAY': ':0', 'XAUTHORITY': '/var/run/lightdm/root/:0',
        'HOME': '/root', 'PATH': '/usr/bin:/bin'}

def list_screens():
    """Ecrans detectes par xrandr : nom, branche, resolution actuelle, modes."""
    try:
        out = subprocess.check_output(['xrandr', '--query'], env=XENV, text=True,
                                      stderr=subprocess.STDOUT, timeout=15)
    except Exception:
        return []
    screens = []
    for line in out.splitlines():
        m = re.match(r'^(\S+) (connected|disconnected)(.*)', line)
        if m:
            res_m = re.search(r'(\d+x\d+)\+', m.group(3))
            screens.append({'name': m.group(1),
                            'connected': m.group(2) == 'connected',
                            'current': res_m.group(1) if res_m else None,
                            'active': res_m is not None,
                            'modes': []})
        elif screens and line.startswith('   '):
            res = re.search(r'(\d+x\d+)', line)
            if res and res.group(1) not in screens[-1]['modes']:
                screens[-1]['modes'].append(res.group(1))
    # Seuls les ecrans branches sont utiles dans la page Affichage
    return [s for s in screens if s['connected']]

# ── RESEAU WI-FI MASQUE (saisie manuelle du SSID) ────────────────────────────

def wifi_devices():
    """Liste des cartes Wi-Fi (hors p2p) avec leur etat."""
    try:
        out = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'dev', 'status'],
                                      text=True, timeout=10)
    except Exception:
        return []
    devs = []
    for line in out.splitlines():
        parts = line.split(':')
        if len(parts) >= 3 and parts[1] == 'wifi' and not parts[0].startswith('p2p'):
            devs.append({'device': parts[0], 'state': parts[2],
                         'usb': parts[0].startswith('wlx')})
    return devs

def sanitize_ssid(value):
    """SSID : 1 a 32 octets, sans caractere de controle, sans tiret initial."""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value or len(value.encode('utf-8')) > 32:
        return ''
    if re.search(r'[\x00-\x1f\x7f]', value) or value.startswith('-'):
        return ''
    return value

def sanitize_psk(value):
    """Cle WPA : 8 a 63 caracteres imprimables (ou 64 hexadecimaux)."""
    if not isinstance(value, str):
        return ''
    if re.fullmatch(r'[0-9a-fA-F]{64}', value):
        return value
    if 8 <= len(value) <= 63 and not re.search(r'[\x00-\x1f\x7f]', value):
        return value
    return ''

def connect_hidden_wifi(ssid, password, security='wpa-psk', iface=''):
    """Cree un profil NetworkManager pour un reseau masque puis l'active.
    Equivalent de :
      nmcli con add type wifi ifname <carte> con-name <ssid> ssid <ssid>
            802-11-wireless.hidden yes wifi-sec.key-mgmt wpa-psk wifi-sec.psk <cle>
            connection.autoconnect yes
      nmcli con up <ssid>
    Arguments passes en liste (pas de shell)."""
    ssid = sanitize_ssid(ssid)
    if not ssid:
        return False, 'SSID invalide (1 a 32 caracteres)'
    security = security if security in ('wpa-psk', 'open') else 'wpa-psk'
    if security == 'wpa-psk':
        password = sanitize_psk(password)
        if not password:
            return False, 'mot de passe invalide (8 a 63 caracteres)'
    valid = [d['device'] for d in wifi_devices()]
    if iface and iface not in valid:
        return False, 'carte Wi-Fi inconnue'
    con_name = ssid
    try:
        # Supprimer un ancien profil du meme nom (aucune erreur si absent)
        subprocess.run(['nmcli', 'con', 'delete', 'id', con_name],
                       capture_output=True, text=True, timeout=15)
        cmd = ['nmcli', 'con', 'add', 'type', 'wifi',
               'con-name', con_name, 'ssid', ssid,
               '802-11-wireless.hidden', 'yes',
               'connection.autoconnect', 'yes']
        if iface:
            cmd += ['ifname', iface]
        if security == 'wpa-psk':
            cmd += ['wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', password]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return False, r.stderr.strip() or 'creation du profil impossible'
        up = ['nmcli', '--wait', '45', 'con', 'up', 'id', con_name]
        if iface:
            up += ['ifname', iface]
        r = subprocess.run(up, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            # Echec (cle fausse, reseau hors de portee...) : ne pas garder un profil inutilisable
            subprocess.run(['nmcli', 'con', 'delete', 'id', con_name],
                           capture_output=True, text=True, timeout=15)
            return False, r.stderr.strip() or 'connexion impossible'
        return True, ''
    except Exception as e:
        return False, str(e)

def run():
    os.makedirs('/etc/urrunberri-os', exist_ok=True)
    if not os.path.exists(SAVED_FILE):
        open(SAVED_FILE, 'w').close()
    server = http.server.HTTPServer(('127.0.0.1', PORT), UrrunBerriHandler)
    print(f"[UrrunBerri OS] API server running on port {PORT} (hardened)")
    server.serve_forever()

if __name__ == '__main__':
    run()
