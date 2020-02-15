#!/bin/bash

# Script to handle multiple scripts to the same git hook

# Safety check this script is being run in even remotely right place
for DIR in .git .githooks
do
    if [ ! -d "$DIR" ]; then
        echo "Directory $DIR not found, exiting."
        exit 1
    fi
done

# Safety check that we will not overwrite any possibly existing hooks
for FILE in pre-commit commit-msg prepare-commit-msg
do
    if [ -f ".git/hooks/$FILE" ]; then
        echo "$FILE exists, will not overwrite. Exiting."
	exit 1
    fi
done

echo "Registering AWS defaults for git-secrets."
git secrets --register-aws

echo "Setting scripts to be executable."
find .githooks -type f -print0 | xargs chmod +x

echo "Copying files to Git Hooks directory."
cp -R .githooks/. .git/hooks/

echo "Done!"
