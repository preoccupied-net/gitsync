"""
Unit tests for gitsync module.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import asyncio
import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from preoccupied.gitsync import gitsync


@pytest.mark.asyncio
class TestRun:
    """
    Tests for the run() function with mocked subprocess.
    """

    async def test_run_success(self):
        """
        Test successful subprocess execution.
        """

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b'')

        with patch('preoccupied.gitsync.gitsync.asyncio.create_subprocess_exec', return_value=mock_process):
            await gitsync.run('git', 'status')

        mock_process.wait.assert_called_once()

    async def test_run_with_cwd(self):
        """
        Test run() with working directory specified.
        """

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b'')

        with patch('preoccupied.gitsync.gitsync.asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            await gitsync.run('git', 'status', cwd='/tmp/test')

        mock_exec.assert_called_once_with(
            'git', 'status',
            cwd='/tmp/test',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def test_run_failure_raises_error(self):
        """
        Test that run() raises CalledProcessError on non-zero exit.
        """

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=1)
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b'error message')

        with patch('preoccupied.gitsync.gitsync.asyncio.create_subprocess_exec', return_value=mock_process):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                await gitsync.run('git', 'invalid-command')

        assert exc_info.value.returncode == 1
        assert exc_info.value.args == (1, ('git', 'invalid-command'))
        assert exc_info.value.stderr == b'error message'


@pytest.mark.asyncio
class TestSyncGitRepo:
    """
    Tests for sync_git_repo() with mocked run() function.
    """

    async def test_sync_new_repo_clones(self, temp_dir):
        """
        Test that sync_git_repo clones a new repository.
        """

        repo_dir = os.path.join(temp_dir, 'new-repo')
        git_url = 'https://github.com/test/repo.git'
        git_branch = 'master'

        with patch('preoccupied.gitsync.gitsync.run', new_callable=AsyncMock) as mock_run, \
             patch('preoccupied.gitsync.gitsync.os.path.isdir', return_value=False), \
             patch('preoccupied.gitsync.gitsync.os.makedirs') as mock_makedirs:

            await gitsync.sync_git_repo(repo_dir, git_url, git_branch)

            mock_makedirs.assert_called_once_with(repo_dir, exist_ok=True)
            mock_run.assert_any_call('git', 'clone', git_url, repo_dir)
            mock_run.assert_any_call('git', 'log', '-1', '--oneline', cwd=repo_dir)

    async def test_sync_existing_repo_fetches_and_resets(self, temp_dir):
        """
        Test that sync_git_repo fetches and resets an existing repository.
        """

        repo_dir = os.path.join(temp_dir, 'existing-repo')
        git_url = 'https://github.com/test/repo.git'
        git_branch = 'main'

        with patch('preoccupied.gitsync.gitsync.run', new_callable=AsyncMock) as mock_run, \
             patch('preoccupied.gitsync.gitsync.os.path.isdir', return_value=True):

            await gitsync.sync_git_repo(repo_dir, git_url, git_branch)

            mock_run.assert_any_call('git', 'fetch', '--all', '--prune')
            mock_run.assert_any_call('git', 'reset', '--hard', 'origin/main')
            mock_run.assert_any_call('git', 'log', '-1', '--oneline', cwd=repo_dir)

    async def test_sync_with_token_injects_token_in_url(self, temp_dir):
        """
        Test that sync_git_repo injects token into git URL when provided.
        """

        repo_dir = os.path.join(temp_dir, 'token-repo')
        git_url = 'https://github.com/test/repo.git'
        git_branch = 'master'
        git_token = 'test-token-123'

        with patch('preoccupied.gitsync.gitsync.run', new_callable=AsyncMock) as mock_run, \
             patch('preoccupied.gitsync.gitsync.os.path.isdir', return_value=False), \
             patch('preoccupied.gitsync.gitsync.os.makedirs'):

            await gitsync.sync_git_repo(repo_dir, git_url, git_branch, git_token=git_token)

            expected_url = 'https://x-access-token:test-token-123@github.com/test/repo.git'
            mock_run.assert_any_call('git', 'clone', expected_url, repo_dir)

    async def test_sync_existing_repo_with_token_updates_remote(self, temp_dir):
        """
        Test that sync_git_repo updates remote URL when token is provided for existing repo.
        """

        repo_dir = os.path.join(temp_dir, 'existing-token-repo')
        git_url = 'https://github.com/test/repo.git'
        git_branch = 'main'
        git_token = 'test-token-456'

        with patch('preoccupied.gitsync.gitsync.run', new_callable=AsyncMock) as mock_run, \
             patch('preoccupied.gitsync.gitsync.os.path.isdir', return_value=True):

            await gitsync.sync_git_repo(repo_dir, git_url, git_branch, git_token=git_token)

            expected_url = 'https://x-access-token:test-token-456@github.com/test/repo.git'
            mock_run.assert_any_call('git', 'remote', 'set-url', 'origin', expected_url)
            mock_run.assert_any_call('git', 'fetch', '--all', '--prune')
            mock_run.assert_any_call('git', 'reset', '--hard', 'origin/main')

    async def test_sync_existing_repo_without_token_skips_remote_update(self, temp_dir):
        """
        Test that sync_git_repo does not update remote URL when no token is provided.
        """

        repo_dir = os.path.join(temp_dir, 'no-token-repo')
        git_url = 'https://github.com/test/repo.git'
        git_branch = 'master'

        with patch('preoccupied.gitsync.gitsync.run', new_callable=AsyncMock) as mock_run, \
             patch('preoccupied.gitsync.gitsync.os.path.isdir', return_value=True):

            await gitsync.sync_git_repo(repo_dir, git_url, git_branch)

            calls = [call[0] for call in mock_run.call_args_list]
            assert ('git', 'remote', 'set-url', 'origin', git_url) not in calls
            assert ('git', 'fetch', '--all', '--prune') in calls
            assert ('git', 'reset', '--hard', 'origin/master') in calls


# The end.
