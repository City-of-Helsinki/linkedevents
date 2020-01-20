#### Helper scripts to automate commit linting and security checks

The hook scripts in *.d directories were created taking the output of `gitlint` and `git-secrets` and sorting them neatly into subdirectories.

The root hook script is taken from https://gist.github.com/mjackson/7e602a7aa357cfe37dadcc016710931b and does a decent job in running the various scripts
