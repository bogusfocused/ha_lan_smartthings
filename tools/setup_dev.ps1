# setup virtual env
pip install virtualenv
pipx install poetry
python -m virtualenv .venv --download --pip 20.2
poetry update
# delete all synlinks and recreate them. 
# The symlinks were pointing to files that was not checked-in (code in built-in smartthings).
Get-ChildItem . -Attributes ReparsePoint -Recurse | ForEach-Object { $_.Delete() }
git reset --hard
pre-commit install --install-hooks -t pre-commit -t pre-push -t pre-merge-commit
