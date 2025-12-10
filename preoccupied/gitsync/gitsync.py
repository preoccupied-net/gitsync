"""
General git utilities for the gitsync application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


async def run(*args: str, cwd: str = None) -> None:
    logger.debug(f'Running {args} in {cwd}')
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    returncode = await process.wait()
    if returncode != 0:
        stderr = await process.stderr.read()
        raise subprocess.CalledProcessError(returncode, args, stderr=stderr)


async def sync_git_repo(
        repo_dir: str,
        git_url: str,
        git_branch: str,
        git_token: Optional[str] = None) -> None:
    """
    Initial or update the sync of the repository specified by repo_name.
    """

    original_url = git_url
    if git_token:
        git_url = git_url.replace('https://', f'https://x-access-token:{git_token}@')

    repo_path = Path(repo_dir)
    git_dir = repo_path / '.git'

    if not repo_path.exists() or not git_dir.exists():
        logging.info(f'Cloning {original_url} to {repo_dir}')
        repo_path.mkdir(parents=True, exist_ok=True)
        os.makedirs(repo_dir, exist_ok=True)
        await run('git', 'clone', git_url, repo_dir)
    else:
        logging.info(f'Pulling {original_url} to {repo_dir}')
        if git_token:
            await run('git', 'remote', 'set-url', 'origin', git_url, cwd=repo_dir)
        await run('git', 'fetch', '--all', '--prune', cwd=repo_dir)
        await run('git', 'reset', '--hard', f'origin/{git_branch}', cwd=repo_dir)

    await run('git', 'log', '-1', '--oneline', cwd=repo_dir)


# The end.
