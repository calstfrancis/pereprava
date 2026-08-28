#!/usr/bin/env bash
# publish-flatpak-local.sh — build and publish Pereprava to the personal flatpak
# repo, entirely on this machine. Fallback for when GitHub Actions is down or the
# build needs local debugging — publish-flatpak.sh (CI-published) is the normal path.
#
# Usage:
#   ./publish-flatpak-local.sh 0.7.0
#
# What this script does NOT do (Claude's job, done before running this):
#   - Write the CHANGELOG entry
#   - Update metainfo.xml release notes
#   - Bump version numbers in source files
#   - Commit and tag the release in this repo
#
# What this script DOES do:
#   1. Verify the version you pass matches what's in pyproject.toml (sanity check)
#   2. Push this repo to GitHub (flatpak-builder pulls sources from there)
#   3. Build the flatpak
#   4. Pull/clone the public flatpak repo
#   5. Export the build into it
#   6. Regenerate the OSTree summary
#   7. Commit and push the flatpak repo

set -euo pipefail

GPG_KEY="A2918A9B43B199ADF9879F934AC9D5173DE4BC41"
FLATPAK_REPO="/tmp/flatpak-checkout"
MANIFEST="io.github.calstfrancis.pereprava.yml"
APP_LABEL="Pereprava"
APP_ID="io.github.calstfrancis.pereprava"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>   e.g.  $0 0.7.0"
  exit 1
fi
VERSION="$1"

TOML_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
if [[ "$TOML_VERSION" != "$VERSION" ]]; then
  echo "ERROR: pyproject.toml says version is '$TOML_VERSION', but you passed '$VERSION'."
  echo "Did you forget to bump the version? (Ask Claude to do the version bump + docs first.)"
  exit 1
fi

echo "==> Publishing $APP_LABEL $VERSION"

echo "==> Pushing source repo to GitHub..."
git push origin main
git push origin "v$VERSION" 2>/dev/null || true

echo "==> Building flatpak (this will take a while)..."
flatpak-builder --force-clean --user --install build-flatpak "$MANIFEST"

echo "==> Syncing public flatpak repo..."
if [[ -d "$FLATPAK_REPO/.git" ]]; then
  git -C "$FLATPAK_REPO" pull
else
  git clone https://github.com/calstfrancis/flatpak "$FLATPAK_REPO"
fi

echo "==> Exporting build..."
flatpak build-export \
  --gpg-sign="$GPG_KEY" \
  "$FLATPAK_REPO" \
  build-flatpak \
  master

echo "==> Regenerating OSTree summary..."
flatpak build-update-repo \
  --gpg-sign="$GPG_KEY" \
  "$FLATPAK_REPO"

# build-export produces an unsigned commit if --gpg-sign is missing or the key
# is unavailable, and says nothing. The repo summary still signs fine, so the
# breakage only surfaces later as a GPG failure on someone else's install.
COMMIT="$(cat "$FLATPAK_REPO/refs/heads/app/$APP_ID/x86_64/master")"
if [[ ! -f "$FLATPAK_REPO/objects/${COMMIT:0:2}/${COMMIT:2}.commitmeta" ]]; then
  echo "ERROR: commit $COMMIT for $APP_ID carries no GPG signature."
  echo "Refusing to push. Re-run build-export with --gpg-sign=\"$GPG_KEY\"."
  exit 1
fi
echo "==> Signature verified for $APP_ID"

echo "==> Pushing flatpak repo..."
cd "$FLATPAK_REPO"
git add -A
git commit -m "$APP_LABEL $VERSION"
git push origin main

echo ""
echo "Done! $APP_LABEL $VERSION is live at https://calstfrancis.github.io/flatpak/"
