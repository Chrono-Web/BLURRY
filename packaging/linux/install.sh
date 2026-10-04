#!/bin/sh
# Per-user installation. Run from the extracted archive; no Python needed.
set -eu
base="$HOME/.local/opt/blurry"
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ ! -L "$base" ] || { echo "Refusing symbolic link: $base" >&2; exit 1; }
mkdir -p "$HOME/.local/opt" "$HOME/.local/share/applications"
# Stage before replacement; preferences are outside the application directory.
stage=$(mktemp -d "$HOME/.local/opt/blurry-install.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT HUP INT TERM
cp -R "$source_dir/Blurry/." "$stage/"
cp "$source_dir/uninstall.sh" "$stage/uninstall.sh"
chmod +x "$stage/Blurry" "$stage/blurry-engine" "$stage/uninstall.sh"
rm -rf -- "$base"
mv -- "$stage" "$base"
# Quote Exec paths, escaping desktop-file special characters.
escaped=$(printf '%s' "$base" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g; s/%/%%/g')
cat > "$HOME/.local/share/applications/blurry.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Blurry
Comment=Cover faces offline / Copri i volti senza rete
Exec="$escaped/Blurry"
Icon=$base/icon.png
Terminal=false
Categories=Graphics;Photography;
EOF
printf 'Blurry installed / installato: %s\n' "$base/Blurry"
