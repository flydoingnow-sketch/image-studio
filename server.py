"""Local publishing workbench with independent, customizable workspaces."""
import importlib.util
import json
import os
import re
import threading
import sqlite3
import shutil
import sys
import uuid
from html import escape
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('CAMERA_PORT', '8769'))
LEGACY_BRANDS = {}
BRANDS = {}
PACKAGED = True
DATA_ROOT = Path(os.environ.get('CAMERA_DATA_DIR', Path.home() / 'Library/Application Support/ImageStudio'))
ACTIVE_PORT = PORT
WORKSPACE_LOCK = threading.RLock()
STUDIOS = {}
HANDLERS = {}
BROWSER_LOCK = threading.Lock()
PUBLISH_LOCK = threading.Lock()
SETTINGS_LOCK = threading.RLock()
SHARED_DB = ROOT / 'data/shared.db'


def shared_key():
    with SETTINGS_LOCK, sqlite3.connect(SHARED_DB) as c:
        row = c.execute("SELECT value FROM shared WHERE id='api_key'").fetchone()
    return row[0] if row else ''


def set_shared_key(key):
    with SETTINGS_LOCK, sqlite3.connect(SHARED_DB) as c:
        c.execute("INSERT OR REPLACE INTO shared(id,value) VALUES('api_key',?)", (key,))


def initialize_shared_key(path, source=None):
    global SHARED_DB
    SHARED_DB = Path(path)
    SHARED_DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(SHARED_DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS shared(id TEXT PRIMARY KEY,value TEXT)')
        configured = c.execute("SELECT 1 FROM shared WHERE id='api_key'").fetchone()
    SHARED_DB.chmod(0o600)
    if configured: return
    legacy = {brand: module.get('settings', 'main', {}).get('api_key', '') for brand, module in STUDIOS.items()}
    candidates = set(legacy.values()) - {''}
    if source in legacy:
        set_shared_key(legacy[source])
    elif len(candidates) <= 1:
        set_shared_key(next(iter(candidates), ''))
    else:
        # Keep legacy credentials on disk; never silently choose between distinct keys.
        set_shared_key('')


def brand_settings(module):
    result = module.DEFAULT_SETTINGS | module.get('settings', 'main', {})
    result['api_key'] = shared_key()
    return result


def save_settings(module, values):
    with SETTINGS_LOCK:
        settings = brand_settings(module)
        for key in ('brand', 'content_direction', 'tone', 'base_url', 'vision_model', 'audio_model', 'image_model'):
            if key in values: settings[key] = str(values[key]).strip()[:2000]
        if not settings['brand']: raise module.AppError('品牌名称不能为空')
        if settings['base_url']:
            parsed = urlparse(settings['base_url'])
            if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise module.AppError('AI 服务地址请使用不带用户名和查询参数的 HTTPS 地址')
        new_key = None
        if values.get('api_key'): new_key = str(values['api_key']).strip()
        if values.get('clear_key'): new_key = ''
        settings.pop('api_key', None)
        module.put('settings', 'main', settings)
        if new_key is not None: set_shared_key(new_key)
        return module.public_settings()


def prefix_media(value, prefix):
    if isinstance(value, list): return [prefix_media(v, prefix) for v in value]
    if isinstance(value, dict):
        return {k: prefix + v if k == 'url' and isinstance(v, str) and v.startswith('/media/') else prefix_media(v, prefix) for k, v in value.items()}
    return value


def index_html(module, brand):
    prefix = '/b/' + brand
    html = (module.ROOT / 'static/index.html').read_text()
    html = re.sub(r'<div class="brand-switch">[^\n]*</div>', '<!-- brand-slot -->', html, count=1)
    # The original card closes its inner label and outer card, followed by no extra wrapper.
    if '<!-- brand-slot -->' not in html:
        raise RuntimeError('Missing brand switch slot')
    name = escape(module.settings()['brand'])
    mark = escape(BRANDS[brand][1])
    card = f'''<div class="brand-picker"><button type="button" id="brand-switch-toggle" class="brand-switch" aria-expanded="false" aria-controls="brand-options" aria-label="切换品牌，当前{name}"><span class="brand-avatar">{mark}</span><span class="brand-current"><strong id="side-brand">{name}</strong><small>品牌空间 · 点击切换</small></span><svg class="brand-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button><div id="brand-options" class="brand-options" hidden><div class="brand-icons">'''
    for key, (label, initial, _) in list(BRANDS.items()):
        label = escape(STUDIOS[key].settings()['brand']); initial = escape(initial)
        card += f'<a class="brand-choice {"selected" if key == brand else ""}" href="/b/{key}/" data-brand="{key}" aria-label="切换到{label}工作台" {"aria-current=page" if key == brand else ""}><span class="brand-avatar">{initial}</span><span>{label.replace("相机", "")}</span></a>'
    card += '</div><a class="add-workspace" href="/new" data-brand="new">+ 新增工作区</a><p>账号与内容独立保存</p></div></div>'
    html = html.replace('哈苏', name)
    html = html.replace('>H<span>', '>'+mark+'<span>').replace('>H</span>', '>'+mark+'</span>')
    html = html.replace('<!-- brand-slot -->', card)
    html = html.replace('<label>文案语气', '<label>内容方向<textarea name="content_direction" rows="2" maxlength="500" placeholder="例如：城市街拍、旅行影像与创作心得"></textarea></label><label>文案语气')
    html = html.replace('<label>API Key<input', '<label>共用 API Key <span class="subtle">全部工作区</span><input')
    html = html.replace('密钥仅保存在本机。', '所有工作区共用同一个 API Key，密钥仅保存在本机。')
    html = html.replace('id="clear-key" class="text-btn">清除已保存密钥', 'id="clear-key" class="text-btn">清除所有工作区的共用密钥')
    html = re.sub(r'<strong>[^<]*工作台</strong>', '<strong>影像工作台</strong>', html, count=1)
    html = html.replace('<span class="version">FIRST EDITION</span>', '<a class="tutorial-entry" href="/tutorial/" target="_blank" rel="noopener">使用教程 ↗</a>')
    html = html.replace('素材与登录状态保存在本机</small>', '素材与登录状态保存在本机<br><a href="/tutorial/" target="_blank" rel="noopener">使用教程 ↗</a></small>')
    html = html.replace('href="/favicon.svg"', f'href="{prefix}/favicon.svg"').replace('href="/style.css"', f'href="{prefix}/style.css"').replace('src="/app.js"', f'src="{prefix}/app.js"')
    return html


def app_js(module, brand):
    source = (module.ROOT / 'static/app.js').read_text()
    source = source.replace("['brand','tone','base_url'", "['brand','content_direction','tone','base_url'")
    source = source.replace("'哈苏','摄影','影像日记','光影','日常记录'", "state.settings.brand,'创作分享','日常记录'")
    source = source.replace("'哈苏'", "'我的品牌'")
    source = source.replace('已保存；留空保持原密钥','共用密钥已保存；留空保持原密钥').replace('密钥已保存在本机，不会显示在页面中。','所有工作区共用此密钥；已保存在本机，不会显示在页面中。').replace('尚未配置密钥。','尚未配置共用密钥。在任意品牌填写一次即可。').replace("toast('已清除密钥')","toast('已清除所有工作区的共用密钥')")
    source = source.replace("fetch('/api/'+path", "fetch(studioBase+'/api/'+path")
    source = source.replace("xhr.open('POST','/api/upload?kind='", "xhr.open('POST',studioBase+'/api/upload?kind='")
    source = re.sub(r"\$\('\.identity strong'\)\.textContent=[^;]+;", "$('.identity strong').textContent='影像工作台';", source)
    extra = (ROOT / 'brand-switch.js').read_text()
    return "'use strict';\nconst studioBase=" + json.dumps('/b/' + brand) + ';\nconst studioBrand=' + json.dumps(brand) + ';\n' + source + '\n' + extra


def make_handler(module, brand):
    prefix = '/b/' + brand
    class BrandHandler(module.Handler):
        server_version = 'CameraStudio/0.1'
        def do_POST(self):
            if urlparse(self.path).path != '/api/settings': return super().do_POST()
            try:
                self.guard(True)
                self.json(save_settings(module, self.read_json()))
            except module.AppError as error: self.json({'error': error.message}, error.status)
            except (BrokenPipeError, ConnectionResetError): pass
            except Exception: self.json({'error':'设置未保存，请重试'}, 500)
        def json(self, value, status=200):
            super().json(prefix_media(value, prefix), status)
        def serve_file(self, path):
            if path.parent == module.ROOT / 'static' and path.name in ('index.html', 'app.js', 'style.css'):
                if path.name == 'index.html': content = index_html(module, brand)
                elif path.name == 'app.js': content = app_js(module, brand)
                else: content = path.read_text() + '\n' + (ROOT / 'brand-switch.css').read_text()
                raw = content.encode()
                self.send_response(200)
                self.send_header('Content-Type', {'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[path.name] + '; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers(); self.wfile.write(raw)
            else: super().serve_file(path)
    return BrandHandler


def environment_info():
    chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    user_chrome = Path.home() / 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    missing = []
    if not (chrome.exists() or user_chrome.exists()): missing.append('Google Chrome')
    if not all((ROOT/'media-tools/bin'/name).is_file() or shutil.which(name) for name in ('ffmpeg','ffprobe')): missing.append('FFmpeg')
    return {'missing': missing}


def workspace_list():
    return [{'id': key, 'name': module.settings()['brand'], 'icon': BRANDS[key][1],
             'content_direction': module.settings().get('content_direction', '')}
            for key, module in list(STUDIOS.items())]


def load_workspace(key, record):
    path = ROOT / 'core/server.py'
    spec = importlib.util.spec_from_file_location('camera_' + key, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.PORT = ACTIVE_PORT
    module.DATA = DATA_ROOT / 'workspaces' / key
    module.VENDOR = module.DATA / 'uploader'
    template = ROOT / 'vendor/social-auto-upload'
    if not module.VENDOR.exists():
        shutil.copytree(template, module.VENDOR, ignore=shutil.ignore_patterns('cookies','logs','media','videos','db','__pycache__','*.pyc','.git','*.egg-info'))
    for directory in ('cookies','logs','media','videos','db'): (module.VENDOR / directory).mkdir(exist_ok=True)
    chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if not chrome.exists(): chrome = Path.home() / 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    (module.VENDOR / 'conf.py').write_text("from pathlib import Path\nBASE_DIR = Path(__file__).parent.resolve()\nLOCAL_CHROME_PATH = " + repr(str(chrome)) + "\nLOCAL_CHROME_HEADLESS = True\nDEBUG_MODE = False\nXHS_SERVER = 'http://127.0.0.1:11901'\nYT_PROXY = None\n")
    module.ACCOUNT = key
    module.PYTHON = Path(sys.executable)
    module.DEFAULT_SETTINGS.update(brand=record['name'], content_direction=record.get('content_direction',''), tone=record.get('tone') or '真实、自然、清晰。只依据素材生成内容，不编造细节或夸大效果。')
    module.BROWSER_LOCK = BROWSER_LOCK; module.PUBLISH_LOCK = PUBLISH_LOCK
    module.init()
    module.settings = lambda module=module: brand_settings(module)
    BRANDS[key] = (record['name'], record['icon'], 0)
    STUDIOS[key] = module; HANDLERS[key] = make_handler(module, key)
    return module


def create_workspace(values):
    name = str(values.get('name','')).strip()
    if not name or len(name) > 40: raise ValueError('请填写 1–40 字的工作区名称')
    icon = str(values.get('icon','')).strip() or name[0]
    if len(icon) > 2 or not all(c.isalnum() for c in icon): raise ValueError('图标请使用 1–2 个字母或汉字')
    direction = str(values.get('content_direction','')).strip()
    tone = str(values.get('tone','')).strip()
    if len(direction)>500 or len(tone)>2000: raise ValueError('内容方向或文案语气过长，请缩短')
    with WORKSPACE_LOCK:
        if len(BRANDS)>=100: raise ValueError('最多创建 100 个工作区')
        key = 'w' + uuid.uuid4().hex[:16]
        record = {'id':key,'name':name,'icon':icon,'content_direction':direction,'tone':tone}
        module = load_workspace(key, record)
        # Copy non-secret provider/model defaults as a convenience; never account data.
        for existing in STUDIOS.values():
            settings = existing.settings()
            if existing is not module and settings.get('base_url'):
                module.put('settings','main',{k:settings.get(k,'') for k in ('base_url','vision_model','audio_model','image_model')})
                break
        with sqlite3.connect(SHARED_DB) as c:
            c.execute('INSERT INTO workspaces(id,value) VALUES(?,?)',(key,json.dumps(record,ensure_ascii=False)))
        return record


def load_studios(data_root=None, port=PORT):
    global DATA_ROOT, ACTIVE_PORT
    ACTIVE_PORT = port
    if data_root is not None: DATA_ROOT = Path(data_root)
    STUDIOS.clear(); HANDLERS.clear(); BRANDS.clear()
    DATA_ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    initialize_shared_key(DATA_ROOT / 'shared.db')
    with sqlite3.connect(SHARED_DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,value TEXT)')
        rows = c.execute('SELECT value FROM workspaces ORDER BY rowid').fetchall()
        seeded = c.execute("SELECT value FROM shared WHERE id='workspace_seeded'").fetchone()
        if not seeded:
            c.execute("INSERT INTO shared(id,value) VALUES('workspace_seeded','1')")
            rows = c.execute('SELECT value FROM workspaces ORDER BY rowid').fetchall()
    for row in rows:
        record=json.loads(row[0]);load_workspace(record['id'],record)


class Router(BaseHTTPRequestHandler):
    server_version = 'CameraStudio/0.1'
    def log_message(self, *args): pass
    def dispatch(self):
        path = urlparse(self.path).path
        if self.command == 'GET' and path == '/':
            self.send_response(302); self.send_header('Location', '/b/'+next(iter(BRANDS))+'/' if BRANDS else '/new'); self.end_headers(); return
        if path == '/api/shutdown' and self.command == 'POST':
            if not self.local_guard(True):self.output({'error':'无效请求'},status=403);return
            for module in STUDIOS.values():
                busy = any(any(r['status'] in ('queued','running') for r in j.get('results',{}).values()) for j in module.all_docs('jobs'))
                busy = busy or any(a.get('status') in ('connecting','checking') for a in module.all_docs('accounts'))
                busy = busy or any(o.get('status')=='running' for o in module.all_docs('operations'))
                if busy:self.output({'error':'仍有任务执行中，请完成后再停止'},status=409);return
            self.output({'stopped':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
        if path in ('/new', '/api/workspaces'):
            self.workspace_request(path); return
        if path.startswith('/tutorial/'):
            self.tutorial_request(path); return
        match = re.match(r'^/b/([a-z0-9]+)(/.*)?$', self.path)
        if not match: self.send_error(404, 'Workspace not found'); return
        brand, tail = match.groups()
        if brand not in HANDLERS: self.send_error(404,'Workspace not found'); return
        if not tail:
            self.send_response(302); self.send_header('Location', '/b/' + brand + '/'); self.end_headers(); return
        # Delegate parsed request and streams to the original isolated brand handler.
        delegate = object.__new__(HANDLERS[brand])
        delegate.__dict__ = self.__dict__.copy()
        delegate.path = tail
        getattr(delegate, 'do_' + self.command)()
        self.close_connection = delegate.close_connection
    def local_guard(self, write=False):
        hosts = {f'127.0.0.1:{ACTIVE_PORT}', f'localhost:{ACTIVE_PORT}'}
        if self.headers.get('Host') not in hosts: return False
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in hosts}: return False
        return not write or self.headers.get('X-Hasu-Client')=='studio'
    def output(self, data, kind='application/json', status=200):
        raw = data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def workspace_request(self, path):
        if not self.local_guard(self.command=='POST'):self.output({'error':'仅允许本机工作台请求'},status=403);return
        if self.command=='GET':
            if path=='/new':self.output((ROOT/'workspaces.html').read_bytes(),'text/html')
            else:self.output({'workspaces':workspace_list(),'environment':environment_info()})
            return
        if path!='/api/workspaces':self.send_error(404);return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>16384:raise ValueError('请求过大')
            values=json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(values,dict):raise ValueError('请求格式错误')
            self.output(create_workspace(values),status=201)
        except (ValueError,TypeError):self.output({'error':'请检查名称、图标和内容方向；名称最多 40 字，图标最多 2 字。'},status=400)
        except Exception:self.output({'error':'工作区创建失败，请重试'},status=500)
    def tutorial_request(self,path):
        if not self.local_guard():self.send_error(403);return
        name=path[len('/tutorial/'):]
        if not name:name='index.html'
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):self.send_error(404);return
        target=ROOT/'tutorial'/name
        if not target.is_file():self.send_error(404);return
        import mimetypes
        self.output(target.read_bytes(),mimetypes.guess_type(target)[0] or 'application/octet-stream')
    do_GET = dispatch
    do_POST = dispatch


def legacy_handler(brand):
    class Legacy(BaseHTTPRequestHandler):
        server_version = 'CameraStudio/0.1'
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', f'http://127.0.0.1:{PORT}/b/{brand}/')
            self.end_headers()
        def do_POST(self):
            self.send_error(409, 'Please reload the integrated workspace before saving')
    return Legacy


if __name__ == '__main__':
    load_studios()
    aliases = []
    for brand, (_, _, old_port) in list(BRANDS.items()):
        if not old_port: continue
        try:
            server = ThreadingHTTPServer(('127.0.0.1', old_port), legacy_handler(brand))
            threading.Thread(target=server.serve_forever, daemon=True).start(); aliases.append(server)
        except OSError: print(f'原入口 {old_port} 已被占用；统一入口仍可使用', flush=True)
    print(f'影像工作台 http://127.0.0.1:{PORT}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Router).serve_forever()
