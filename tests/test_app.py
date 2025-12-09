"""
Unit tests for FastAPI application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from preoccupied.gitsync import app
from preoccupied.gitsync.config import RootConfig, RepoConfig, GlobalConfig


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.
    """

    return TestClient(app)


@pytest.fixture
def mock_repo_config():
    """
    Create a mock RepoConfig.
    """

    return RepoConfig(
        name='test-repo',
        directory='/tmp/test-repo',
        git_url='https://github.com/test/repo.git',
        branch='master',
        webhook_secret='secret123'
    )


@pytest.fixture
def mock_config(mock_repo_config):
    """
    Create a mock RootConfig.
    """

    global_config = GlobalConfig()
    return RootConfig(
        global_=global_config,
        repos={'test-repo': mock_repo_config}
    )


class TestSyncEndpoint:
    """
    Tests for the /sync/{name} endpoint.
    """

    def test_sync_success(self, client, mock_config, mock_repo_config):
        """
        Test successful sync operation.
        """

        with patch('preoccupied.gitsync.app.get_config', return_value=mock_config), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock) as mock_sync:
            response = client.post(
                '/sync/test-repo',
                headers={'x-sync-token': 'secret123'}
            )

        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'repo': 'test-repo'}
        mock_sync.assert_called_once()

    def test_sync_repo_not_found(self, client, mock_config):
        """
        Test sync with non-existent repository.
        """

        with patch('preoccupied.gitsync.app.get_config', return_value=mock_config):
            response = client.post('/sync/nonexistent')

        assert response.status_code == 404
        assert "Repository 'nonexistent' not found" in response.json()['detail']

    def test_sync_bad_secret(self, client, mock_config, mock_repo_config):
        """
        Test sync with incorrect webhook secret.
        """

        with patch('preoccupied.gitsync.app.get_config', return_value=mock_config), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock) as mock_sync:
            response = client.post(
                '/sync/test-repo',
                headers={'x-sync-token': 'wrong-secret'}
            )

        assert response.status_code == 401
        assert response.json()['detail'] == 'Bad secret'
        mock_sync.assert_not_called()

    def test_sync_no_secret_when_required(self, client, mock_config, mock_repo_config):
        """
        Test sync without secret when repository requires one.
        """

        with patch('preoccupied.gitsync.app.get_config', return_value=mock_config), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock) as mock_sync:
            response = client.post('/sync/test-repo')

        assert response.status_code == 401
        assert response.json()['detail'] == 'Bad secret'
        mock_sync.assert_not_called()

    def test_sync_no_secret_when_not_required(self, client, mock_config):
        """
        Test sync without secret when repository doesn't require one.
        """

        repo_no_secret = RepoConfig(
            name='public-repo',
            directory='/tmp/public-repo',
            git_url='https://github.com/test/repo.git',
            branch='master',
            webhook_secret=None
        )

        config_no_secret = RootConfig(
            global_=GlobalConfig(),
            repos={'public-repo': repo_no_secret}
        )

        with patch('preoccupied.gitsync.app.get_config', return_value=config_no_secret), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock) as mock_sync:
            response = client.post('/sync/public-repo')

        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'repo': 'public-repo'}
        mock_sync.assert_called_once()

    def test_sync_exception_handling(self, client, mock_config, mock_repo_config):
        """
        Test that sync exceptions are properly handled.
        """

        with patch('preoccupied.gitsync.app.get_config', return_value=mock_config), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock, side_effect=Exception('Sync failed')):
            response = client.post(
                '/sync/test-repo',
                headers={'x-sync-token': 'secret123'}
            )

        assert response.status_code == 500
        assert 'Sync failed' in response.json()['detail']


class TestStartupEvent:
    """
    Tests for the startup event handler.
    """

    @pytest.mark.asyncio
    async def test_startup_syncs_all_repos(self, mock_config):
        """
        Test that startup event syncs all repositories.
        """

        repo1 = RepoConfig(
            name='repo1',
            directory='/tmp/repo1',
            git_url='https://github.com/test/repo1.git',
            branch='master'
        )

        repo2 = RepoConfig(
            name='repo2',
            directory='/tmp/repo2',
            git_url='https://github.com/test/repo2.git',
            branch='main'
        )

        config = RootConfig(
            global_=GlobalConfig(),
            repos={'repo1': repo1, 'repo2': repo2}
        )

        with patch('preoccupied.gitsync.app.get_config', return_value=config), \
             patch('preoccupied.gitsync.app.logger'), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock) as mock_sync:

            from preoccupied.gitsync.app import app_startup
            await app_startup()

        assert mock_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_startup_handles_sync_failure_gracefully(self, mock_config):
        """
        Test that startup continues even if one repo sync fails.
        """

        repo1 = RepoConfig(
            name='repo1',
            directory='/tmp/repo1',
            git_url='https://github.com/test/repo1.git',
            branch='master'
        )

        repo2 = RepoConfig(
            name='repo2',
            directory='/tmp/repo2',
            git_url='https://github.com/test/repo2.git',
            branch='main'
        )

        config = RootConfig(
            global_=GlobalConfig(),
            repos={'repo1': repo1, 'repo2': repo2}
        )

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception('Sync error')
            return None

        with patch('preoccupied.gitsync.app.get_config', return_value=config), \
             patch('preoccupied.gitsync.app.logger'), \
             patch('preoccupied.gitsync.config.RepoConfig.sync', new_callable=AsyncMock, side_effect=side_effect) as mock_sync:

            from preoccupied.gitsync.app import app_startup
            await app_startup()

        assert mock_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_startup_raises_on_config_load_failure(self):
        """
        Test that startup raises exception if config loading fails.
        """

        with patch('preoccupied.gitsync.app.get_config', side_effect=Exception('Config error')), \
             patch('preoccupied.gitsync.app.logger'):

            from preoccupied.gitsync.app import app_startup

            with pytest.raises(Exception, match='Config error'):
                await app_startup()


# The end.
