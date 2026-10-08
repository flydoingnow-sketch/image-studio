"""Build the Apple Silicon .app and .pkg without copying any user data."""
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/package-build'
OUT=ROOT/'dist'
APP=WORK/'payload/影像工作台.app'
RES=APP/'Contents/Resources'
BASE_PY=Path(os.environ['IMAGE_STUDIO_PYTHON_RUNTIME']).resolve()
SITE=Path(os.environ.get('IMAGE_STUDIO_SITE_PACKAGES',ROOT/'.venv/lib/python3.12/site-packages')).resolve()
VENDOR=ROOT/'vendor/social-auto-upload'
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','.git','cookies','data','db','logs','media','videos','*.egg-info','__editable__*','direct_url.json')
OUT.mkdir(exist_ok=True)
RES.mkdir(parents=True,exist_ok=True)
media=ROOT/'media-tools'
if not (media/'bin/ffmpeg').is_file() or not (media/'bin/ffprobe').is_file():
 raise RuntimeError('Build the bundled media tools first')
if (RES/'media-tools').exists():shutil.rmtree(RES/'media-tools')
shutil.copytree(media,RES/'media-tools')
for name in ('server.py','launcher.py','workspaces.html','brand-switch.js','brand-switch.css'):
 shutil.copy2(ROOT/name,RES/name)
for name in ('core','tutorial'):
 if (RES/name).exists():shutil.rmtree(RES/name)
 if (ROOT/name).exists():shutil.copytree(ROOT/name,RES/name,ignore=IGNORE)
vend=RES/'vendor/social-auto-upload';vend.mkdir(parents=True,exist_ok=True)
for name in ('LICENSE','README.md','pyproject.toml','sau_cli.py','__init__.py'):
 if (VENDOR/name).exists():shutil.copy2(VENDOR/name,vend/name)
for name in ('uploader','myUtils','utils'):
 if (vend/name).exists():shutil.rmtree(vend/name)
 shutil.copytree(VENDOR/name,vend/name,ignore=IGNORE)
(vend/'conf.py').write_text("from pathlib import Path\nBASE_DIR = Path(__file__).parent.resolve()\nLOCAL_CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'\nLOCAL_CHROME_HEADLESS = True\nDEBUG_MODE = False\nXHS_SERVER = 'http://127.0.0.1:11901'\nYT_PROXY = None\n")
runtime=RES/'runtime'
if not runtime.exists():
 (runtime/'bin').mkdir(parents=True)
 shutil.copy2(BASE_PY/'bin/python3.12',runtime/'bin/python3.12')
 (runtime/'bin/python3').symlink_to('python3.12')
 shutil.copytree(BASE_PY/'lib',runtime/'lib',ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc'),symlinks=True)
 shutil.copytree(SITE,runtime/'lib/python3.12/site-packages',ignore=IGNORE,symlinks=True)
if (runtime/'lib/pkgconfig').exists():shutil.rmtree(runtime/'lib/pkgconfig')
macos=APP/'Contents/MacOS';macos.mkdir(parents=True,exist_ok=True)
launcher=macos/'ImageStudio'
launcher.write_text('''#!/bin/zsh
set -e
app_resources="${0:A:h}/../Resources"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHOME="$app_resources/runtime"
export PYTHONPATH="$app_resources/runtime/lib/python3.12/site-packages"
export PATH="$app_resources/media-tools/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
exec "$app_resources/runtime/bin/python3" "$app_resources/launcher.py" "$@"
''');launcher.chmod(0o755)
info={'CFBundleName':'影像工作台','CFBundleDisplayName':'影像工作台','CFBundleIdentifier':'com.imagestudio.workbench','CFBundleVersion':'1.0.1','CFBundleShortVersionString':'1.0.1','CFBundlePackageType':'APPL','CFBundleExecutable':'ImageStudio','LSMinimumSystemVersion':'14.0','LSUIElement':True,'NSHighResolutionCapable':True}
(APP/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
# No user directories, symlinks to the original machine, or API key stores may enter the app.
for path in APP.rglob('*'):
 if path.is_symlink() and path.readlink().is_absolute():raise RuntimeError('Absolute symlink in app: '+str(path))
 if path.name in ('studio.db','shared.db'):raise RuntimeError('User database in app')
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHOME':str(runtime),'PYTHONPATH':str(runtime/'lib/python3.12/site-packages')}
subprocess.run([str(launcher),'--check'],env=env,check=True)
for cache in list(APP.rglob('__pycache__')):
 if cache.is_dir():shutil.rmtree(cache)
subprocess.run(['codesign','--force','--deep','--sign','-',str(APP)],check=True)
subprocess.run(['pkgbuild','--root',str(WORK/'payload'),'--identifier','com.imagestudio.workbench','--version','1.0.1','--install-location','/Applications','--ownership','recommended',str(OUT/'影像工作台-AppleSilicon-1.0.1.pkg')],check=True)
shutil.copy2(ROOT/'distribution/安装运行环境.command',OUT/'安装运行环境.command')
print('Built:',OUT)
