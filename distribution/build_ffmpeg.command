#!/bin/zsh
set -e
cd "${0:A:h}/.."
mkdir -p build/ffmpeg media-tools/bin
media_archive="$PWD/build/ffmpeg/ffmpeg-9.0.2.tar.xz"
if [[ ! -f "$media_archive" ]]; then
 curl --fail --location --retry 2 https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz -o "$media_archive"
fi
printf '%s  %s\n' "8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e" "$media_archive" | shasum -a 256 -c -
tar -xf "$media_archive" -C build/ffmpeg
cd build/ffmpeg/ffmpeg-9.0.2
media_sdk="$(xcrun --sdk macosx --show-sdk-path)"
media_flags="-mmacosx-version-min=14.0 -isysroot $media_sdk"
./configure --cc=clang --prefix="$PWD/../installed" --disable-autodetect --enable-zlib --disable-network --disable-doc --disable-ffplay --disable-debug --enable-small --disable-avdevice --disable-videotoolbox --disable-audiotoolbox --extra-cflags="$media_flags" --extra-ldflags="$media_flags" --host-cflags="$media_flags" --host-ldflags="$media_flags"
make -j8
make install
cd ../../..
cp build/ffmpeg/installed/bin/ffmpeg build/ffmpeg/installed/bin/ffprobe media-tools/bin/
cp build/ffmpeg/ffmpeg-9.0.2/COPYING.LGPLv2.1 media-tools/
cp "$media_archive" media-tools/
cp distribution/build_ffmpeg.command media-tools/build.command
printf '%s\n' 'FFmpeg 9.0.2 · Copyright (c) 2000-2026 the FFmpeg developers · LGPL 2.1 or later.' 'Unmodified source archive and complete license included. Rebuild with distribution/build_ffmpeg.command from the source project.' > media-tools/NOTICE.txt
for media_executable in media-tools/bin/*; do
 otool -L "$media_executable"
 if otool -L "$media_executable" | /usr/bin/grep -Eq '/opt/homebrew|/usr/local'; then
  echo 'Unexpected dependency on an external library'; exit 1
 fi
done
python3 distribution/check_media_tools.py
echo 'Built offline media tools.'
