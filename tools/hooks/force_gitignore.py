import argparse
import sys
import re
from typing import AbstractSet
from typing import Optional
from typing import Sequence

import util 


def current_branch():
    try:
        ref_name = util.cmd_output('git', 'symbolic-ref', 'HEAD')
    except util.CalledProcessError:
        return False
    chunks = ref_name.strip().split('/')
    branch_name = '/'.join(chunks[2:])
    print(f"Current branch is '{branch_name}'")
    return branch_name

def is_on_branch(
        protected: AbstractSet[str],
        patterns: AbstractSet[str] = frozenset(),
) -> bool:
    branch_name = current_branch()
    if branch_name in protected:
        print(f"Branch is one of {[p for p in protected]}")
        return True
    for p in patterns:
        if re.match(p, branch_name):
            print(f"Branch matched the pattern '{p}'")
            return True
    return False

def apply_gitignore(check_only: bool) -> int:
    files = set(util.cmd_output('git','ls-files', '-ci', '--exclude-standard').splitlines())
    if not files:
        return 0
    print(f"Invalid files: {str(files)}")
    if check_only:
        return 1
    for file in files:
        util.cmd_output('git', 'rm', '--cached', file)
        util.cmd_output('git', 'clean', '-f', file)
    return 0

def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only",action='store_true',
    help="Does not change files when specified.")
    parser.add_argument(
        '-b', '--branch', action='append',required='-p' not in argv and '--pattern' not in argv,
        help='branch to disallow commits to, may be specified multiple times',
    )
    parser.add_argument(
        '-p', '--pattern', action='append',required='-b' not in argv and '--branch' not in argv,
        help=(
            'regex pattern for branch name to disallow commits to, '
            'may be specified multiple times'
        ),
    )
    args = parser.parse_args(argv)
    
    protected = frozenset(args.branch or ())
    patterns = frozenset(args.pattern or ())
    if is_on_branch(protected, patterns):
        return apply_gitignore(args.check_only)
    else:
        print(f"Ignoring branch as it did NOT match any of the given condition(s) names: {[p for p in protected]} or patterns: {[p for p in patterns]}")
        return 0


if __name__ == '__main__':
    exit(main())
