"""Smoke-test the image formats promised by the bundled media tools."""
import base64
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path


def png_fixture(alpha=False):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    pixel = bytes((50, 100, 150, 180)) if alpha else bytes((50, 100, 150))
    raw = b''.join(b'\x00' + pixel * 4 for _ in range(4))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 6 if alpha else 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def check(ffmpeg, ffprobe):
    fixtures = {'rgb.png': png_fixture(), 'alpha.png': png_fixture(True), 'image.webp': base64.b64decode('UklGRh4AAABXRUJQVlA4TBEAAAAvA8AAAAdQssrUsv+BiOh/AAA=')}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for name, raw in fixtures.items():
            source = root / name; source.write_bytes(raw)
            target = root / (name + '.jpg')
            subprocess.run([str(ffmpeg), '-v', 'error', '-y', '-i', str(source), '-frames:v', '1', '-vf', 'scale=1920:1920:force_original_aspect_ratio=decrease', str(target)], check=True, capture_output=True, timeout=30)
            assert target.read_bytes().startswith(b'\xff\xd8'), name
            result = subprocess.run([str(ffprobe), '-v', 'error', '-show_streams', '-of', 'json', str(target)], check=True, capture_output=True, timeout=30)
            stream = json.loads(result.stdout)['streams'][0]
            assert stream['width'] > 0 and stream['height'] > 0, name
        # Re-read the converted JPEG as another user-uploaded cover.
        subprocess.run([str(ffmpeg), '-v', 'error', '-y', '-i', str(target), '-frames:v', '1', str(root/'jpeg-input.jpg')], check=True, capture_output=True, timeout=30)
    print('Image formats passed: RGB PNG, transparent PNG, WebP, JPEG')


if __name__ == '__main__':
    media = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'media-tools/bin'
    check(media/'ffmpeg', media/'ffprobe')
