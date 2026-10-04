#!/bin/sh
# Removes this user's fixed application location and preferences only.
set -eu
base="$HOME/.local/opt/blurry"
self=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ "$self" = "$base" ] && [ ! -L "$base" ] || exit 1
if [ "$#" -gt 0 ]; then
    case "$1" in *[!0-9]*|'') exit 1;; esac
    while kill -0 "$1" 2>/dev/null; do sleep 1; done
fi
config="${XDG_CONFIG_HOME:-$HOME/.config}/chronocol.com"
[ ! -L "$config" ] || exit 1
rm -f -- "$config/blurry.conf" "$HOME/.local/share/applications/blurry.desktop"
rm -rf -- "$base"
printf 'Blurry removed / disinstallato.\n'
