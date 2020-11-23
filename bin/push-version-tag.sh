#!/bin/bash

set -euo pipefail

FILENAME=$(basename "$0")

# Use ${1-} instead of just ${1} so that the script doesn't halt if ${1} is unset
if [ "${1-}" == '--help' ]; then
  echo $'Creates the version tag and pushes it to GitHub\n'
  echo "Usage:./bin/${FILENAME}"
  exit 0
fi

# Check that the script is run in the root directory
if [ ! -d .git ]; then
  echo >&2 "Please cd into the espooevents-service root directory before running this script."
  exit 1
fi

./bin/check-version.sh

VERSION="espoo-v$(tr -d '\n' < VERSION)"

# Create an annotated tag which contains, e.g., author metadata
git tag -a "$VERSION" -m "$VERSION"
git push --no-verify origin "$VERSION"
