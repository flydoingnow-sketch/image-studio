"""Desktop launcher: start one local server and open its browser workspace."""
import os
import sys
import time
import subprocess
from pathlib import Path
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('CAMERA_DATA_DIR', Path.home()/'Library/Application Support/ImageStudio'))
PORT = int(os.environ.get('CAMERA_PORT','8769'))
URL = f'http://127.0.0.1:{PORT}/'
if '--check' in sys.argv:
    import requests, cv2, patchright, playwright, loguru, qrcode, segno
    print('Bundled runtime ready')
    raise SystemExit(0)
DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
opener=build_opener(ProxyHandler({}))
def ready():
    try:
        with opener.open(URL,timeout=2) as response:
            return response.headers.get('Server','').startswith('CameraStudio/')
    except Exception:return False
if not ready():
    log=(DATA/'application.log').open('ab')
    env=dict(os.environ)
    env['PATH']=str(ROOT/'media-tools/bin')+':/opt/homebrew/bin:/usr/local/bin:'+env.get('PATH','')
    env['CAMERA_DATA_DIR']=str(DATA)
    process=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
    for _ in range(100):
        if ready():break
        if process.poll() is not None:raise SystemExit('启动失败，请查看 '+str(DATA/'application.log'))
        time.sleep(.1)
    else:raise SystemExit('工作台启动超时，请查看 '+str(DATA/'application.log'))
if os.environ.get('IMAGE_STUDIO_NO_BROWSER')!='1':
    import webbrowser
    webbrowser.open(URL)
print(URL)
