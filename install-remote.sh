#!/bin/bash
# One-line remote installer:
#   curl -fsSL https://raw.githubusercontent.com/calstfrancis/pereprava/main/install-remote.sh | bash
#
# Fetches the latest GitHub release tarball, extracts it, and runs install.sh
# from inside it. Safe to re-run to update to a newer release.
set -euo pipefail

REPO="calstfrancis/pereprava"
SRC_DIR="$HOME/.local/share/pereprava-src"

echo "Looking up the latest Pereprava release..."
TAG="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"

if [ -z "$TAG" ]; then
  echo "Could not determine the latest release tag. Check:" >&2
  echo "  https://github.com/$REPO/releases" >&2
  exit 1
fi

echo "Latest release: $TAG"

TMP_TARBALL="$(mktemp -u).tar.gz"
curl -fsSL "https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz" -o "$TMP_TARBALL"

rm -rf "$SRC_DIR"
mkdir -p "$SRC_DIR"
tar -xzf "$TMP_TARBALL" -C "$SRC_DIR" --strip-components=1
rm -f "$TMP_TARBALL"

echo "Installing..."
cd "$SRC_DIR"
./install.sh

echo
echo "Done. Source kept at $SRC_DIR (re-run this installer any time to update)."
