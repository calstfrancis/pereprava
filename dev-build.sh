#!/usr/bin/env bash
# dev-build.sh — build and install Pereprava's flatpak locally for testing
#
# Run this after Claude has prepped the dev build (bumped to the next dev version,
# updated CHANGELOG, committed, and tagged). No arguments needed — the version
# is read from pyproject.toml.
#
# Pushes to GitHub first (flatpak-builder pulls source from branch: main),
# then builds and installs locally. Does NOT publish to the flatpak repo.

set -euo pipefail

MANIFEST="io.github.calstfrancis.pereprava.yml"

VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
echo "==> Building Pereprava $VERSION (local dev install)"

echo "==> Pushing to GitHub (flatpak-builder needs this)..."
git push origin main
git push origin "v$VERSION" 2>/dev/null || true

flatpak-builder --force-clean --user --install build-flatpak "$MANIFEST"

echo ""
echo "Done! Pereprava $VERSION is installed locally."
echo "Run it with: flatpak run io.github.calstfrancis.pereprava"
echo ""
echo "Worth checking specifically (new for this app — see CLAUDE.md's Pereprava"
echo "flatpak notes): a scheduled job actually fires and writes its log, Run Now,"
echo "Repair, the Add/Edit form's Test dry-run, pCloud OAuth setup, and an rclone"
echo "mount actually appearing as a real mount outside the sandbox."
