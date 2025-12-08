"""
General git utilities for the gitsync application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import os
import subprocess
from typing import Optional


def run(*args: str, cwd: str = None) -> None:
    subprocess.check_call(args, cwd=cwd)


def sync_git_repo(
        repo_dir: str,
        git_url: str,
        git_branch: str,
        git_token: Optional[str] = None) -> None:
    """
    Initial or update the sync of the repository specified by repo_name.
    """

    if git_token:
        git_url = git_url.replace('https://', f'https://x-access-token:{git_token}@')

    if not os.path.isdir(os.path.join(repo_dir, '.git')):
        os.makedirs(repo_dir, exist_ok=True)
        run('git', 'clone', git_url, repo_dir)
    else:
        if git_token:
            run('git', 'remote', 'set-url', 'origin', git_url)
        run('git', 'fetch', '--all', '--prune')
        run('git', 'reset', '--hard', f'origin/{git_branch}')

    run('git', 'log', '-1', '--oneline', cwd=repo_dir)


# The end.
