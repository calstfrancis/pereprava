#!/usr/bin/env bash
# publish-flatpak.sh — push a release; GitHub Actions builds and publishes it
#
# Usage:
#   ./publish-flatpak.sh 0.7.0
#
# What this script does NOT do (Claude's job, done before running this):
#   - Write the CHANGELOG entry / metainfo release note
#   - Bump the version / commit / tag
#
# What this script DOES do:
#   1. Verify the version you pass matches pyproject.toml (sanity check)
#   2. Push main and the version tag to GitHub
#
# Pushing the tag is what triggers .github/workflows/release-flatpak.yml, which does
# everything this script used to do locally: build the flatpak, export it into the public
# repo, GPG-sign it, and push. Watch it at:
#   https://github.com/calstfrancis/pereprava/actions/workflows/release-flatpak.yml
#
# Needs CI to have already passed for this commit — release-flatpak.yml checks this itself
# and refuses to publish otherwise. If GitHub Actions is down or you need to debug the
# build locally, use publish-flatpak-local.sh instead (does the full build+publish here,
# same as this script used to before Pereprava's flatpak was set up CI-published).
#
# Until RELEASE-CI-SETUP.md's three secrets are set on this repo, the workflow will push
# the tag fine but every job after "Import GPG signing key" will fail — use
# publish-flatpak-local.sh in the meantime.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>   e.g.  $0 0.7.0"
  exit 1
fi
VERSION="$1"

TOML_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
if [[ "$TOML_VERSION" != "$VERSION" ]]; then
  echo "ERROR: pyproject.toml says '$TOML_VERSION', but you passed '$VERSION'."
  echo "Did you forget the version bump? (Ask Claude to do the version bump + docs first.)"
  exit 1
fi

echo "==> Publishing Pereprava $VERSION"
git push origin main
git push origin "v$VERSION"

echo ""
echo "Done! GitHub Actions is building and publishing $VERSION now:"
echo "  https://github.com/calstfrancis/pereprava/actions/workflows/release-flatpak.yml"
