#!/bin/bash

set -euo pipefail

FILENAME=$(basename "$0")

# Use ${1-} instead of just ${1} so that the script doesn't halt if ${1} is unset
if [ "${1-}" == '--help' ]; then
  echo $'Checks that the version is valid and that the changelog has been updated\n'
  echo "Usage:./bin/${FILENAME}"
  echo "Usage:./bin/${FILENAME} --skip-exists-check"
  exit 0
fi

# Check that the script is run in the root directory
if [ ! -d .git ]; then
  echo >&2 "Please cd into the espooevents-service root directory before running this script."
  exit 1
fi

# Adapted from https://semver.org/spec/v2.0.0.html#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER_REGEX_PATTERN='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$'

VERSION=$(tr -d '\n' < VERSION)
# Gets the latest tag by checking all branches
CURRENT_LATEST_VERSION=$(git describe --tags --abbrev=0 "$(git rev-list --tags --max-count=1)")

# Trim the first "espoo-v" character so that the regexp matches
if [[ ! ${CURRENT_LATEST_VERSION:7} =~ $SEMVER_REGEX_PATTERN ]]; then
  echo "The current latest version is not a valid semantic version: ${CURRENT_LATEST_VERSION:1}"
  exit 1
fi
LATEST_MAJOR="${BASH_REMATCH[1]}"
LATEST_MINOR="${BASH_REMATCH[2]}"
LATEST_PATCH="${BASH_REMATCH[3]}"

if [[ ! $VERSION =~ $SEMVER_REGEX_PATTERN ]]; then
  echo "The given version is not a valid semantic version: $VERSION"
  exit 1
fi

MAJOR="${BASH_REMATCH[1]}"
MINOR="${BASH_REMATCH[2]}"
PATCH="${BASH_REMATCH[3]}"

if [[ "${1-}" != '--skip-exists-check' && $(git tag -l "espoo-v$VERSION") ]]; then
  echo "Version $VERSION already exists"
  exit 1
fi

# The major version has been incremented
if [[ $MAJOR -ne $LATEST_MAJOR ]]; then
  if [[ $((MAJOR - LATEST_MAJOR)) -ne 1 ]]; then
    echo "Invalid major increment: the major version should only be inremented by one"
    exit 1
  fi

  if [[ $MINOR -ne 0 || $PATCH -ne 0 ]]; then
    echo "The minor and patch versions should be reset to 0 when the major version is incremented"
    exit 1
  fi

  echo "Major version increment valid"
# The minor version has been incremented
elif [[ $MINOR -ne $LATEST_MINOR ]]; then
  if [[ $((MINOR - LATEST_MINOR)) -ne 1 ]]; then
    echo "Invalid minor increment: the minor version should only be inremented by one"
    exit 1
  fi

  if [[ $PATCH -ne 0 ]]; then
    echo "The patch version should be reset to 0 when the minor version is incremented"
    exit 1
  fi

  echo "Minor version increment valid"
# The patch version has been incremented
elif [[ $PATCH -ne $LATEST_PATCH ]]; then
  if [[ $((PATCH - LATEST_PATCH)) -ne 1 ]]; then
    echo "Invalid patch increment: the patch version should only be inremented by one"
    exit 1
  fi

  echo "Patch version increment valid"
fi

if ! grep -q "$VERSION" CHANGELOG.md; then
  echo "Changelog hasn't been updated for version $VERSION"
  exit 1
fi
