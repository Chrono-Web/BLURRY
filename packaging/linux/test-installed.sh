#!/bin/sh
set -eu
! command -v python
! command -v python3
cd "$HOME"
tar xzf /tmp/package.tar.gz
sh Blurry-linux/install.sh
base="$HOME/.local/opt/blurry"
"$base/blurry-engine" --version
mkdir "$HOME/cli-output"
report=$("$base/blurry-engine" --json --strict -o "$HOME/cli-output" /tmp/fixture.jpg)
printf '%s' "$report" | grep -q '"status": "ok"'
test -s "$HOME/cli-output/fixture.blurry.jpg"
xvfb-run -a "$base/Blurry" __smoke-test /tmp/fixture.jpg
mkdir -p "$HOME/.config/chronocol.com"
printf '[General]\nonboarded=true\n' > "$HOME/.config/chronocol.com/blurry.conf"
# Upgrade retains onboarding; complete removal deletes it.
sh Blurry-linux/install.sh
grep -q 'onboarded=true' "$HOME/.config/chronocol.com/blurry.conf"
printf 'keep me' > "$HOME/original.jpg"
sh "$base/uninstall.sh"
test ! -e "$base"
test ! -e "$HOME/.config/chronocol.com/blurry.conf"
test ! -e "$HOME/.local/share/applications/blurry.desktop"
test -f "$HOME/original.jpg"
sh Blurry-linux/install.sh
xvfb-run -a "$base/Blurry" __smoke-test /tmp/fixture.jpg
sh "$base/uninstall.sh"
