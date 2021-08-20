#!/bin/sh
[ -d ".venv" ] && exit 0
# setup virtual env
pip install virtualenv
pipx install poetry
python -m virtualenv .venv --download --pip 20.2
poetry update
# delete all synlinks and recreate them. 
# The symlinks were pointing to files that was not checked-in (code in built-in smartthings).
find . -type l | xargs rm
git reset --hard
git config --local core.hooksPath .githooks/