"""
Shared pytest fixtures for gitsync tests.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from preoccupied.gitsync.config import RootConfig, RepoConfig, GitHubRepoConfig, GlobalConfig


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for tests.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_config():
    """
    Create a mock RootConfig for testing.
    """

    global_config = GlobalConfig()
    repo_config = RepoConfig(
        name='test-repo',
        directory='/tmp/test-repo',
        git_url='https://github.com/test/repo.git',
        branch='master'
    )
    return RootConfig(
        global_=global_config,
        repos={'test-repo': repo_config}
    )


@pytest.fixture
def mock_github_repo_config():
    """
    Create a mock GitHubRepoConfig for testing.
    """

    return GitHubRepoConfig(
        name='test-github-repo',
        directory='/tmp/test-github-repo',
        git_url='https://github.com/test/repo.git',
        branch='main',
        provider='github',
        github_app_id='12345',
        github_installation_id='67890',
        github_keyfile='/tmp/test-key.pem'
    )


@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Clear and optionally set environment variables for testing.
    """

    env_vars_to_clear = [
        'CONFIG_PATH',
        'GITSYNC_GITHUB_APP_ID',
        'GITSYNC_GITHUB_INSTALLATION_ID',
        'GITSYNC_GITHUB_KEYFILE',
        'GITSYNC_WEBHOOK_SECRET',
        'GITSYNC_REPO_NAME',
        'GITSYNC_REPO_DIRECTORY',
        'GITSYNC_REPO_GIT_URL',
        'GITSYNC_REPO_BRANCH',
        'GITSYNC_REPO_PROVIDER'
    ]

    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    return monkeypatch


# The end.
