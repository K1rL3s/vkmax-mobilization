#!/bin/sh
set -e
cd "$(dirname "$0")"
out=${OUT:-zheka}
mkdir -p build/fc-cache build/slides
node build.js "$out.pptx"
cat > build/fonts.conf <<CONF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>$HOME/Library/Fonts</dir>
  <dir>/Library/Fonts</dir>
  <dir>/System/Library/Fonts</dir>
  <dir>/usr/share/fonts</dir>
  <dir>$HOME/.local/share/fonts</dir>
  <cachedir>$PWD/build/fc-cache</cachedir>
</fontconfig>
CONF
profile=$(mktemp -d)
FONTCONFIG_FILE="$PWD/build/fonts.conf" "${SOFFICE:-soffice}" -env:UserInstallation="file://$profile" --headless --convert-to pdf --outdir "$(dirname "$out")" "$out.pptx"
rm -rf "$profile"
rm -f build/slides/*.jpg
pdftoppm -jpeg -r 100 "$out.pdf" build/slides/slide
