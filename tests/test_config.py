"""
Unit tests for configuration module.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import os
import tempfile
import yaml
from unittest.mock import AsyncMock, patch, mock_open

import pytest

from preoccupied.gitsync.config import (
    GlobalConfig, RepoConfig, GitHubRepoConfig, RootConfig,
    get_config, _config_from_env
)


class TestGlobalConfig:
    """
    Tests for GlobalConfig model.
    """

    def test_global_config_defaults(self):
        """
        Test GlobalConfig with default values.
        """

        config = GlobalConfig()
        assert config.github_app_id is None
        assert config.github_installation_id is None
        assert config.github_keyfile is None
        assert config.webhook_secret is None

    def test_global_config_with_values(self):
        """
        Test GlobalConfig with provided values.
        """

        config = GlobalConfig(
            github_app_id='12345',
            github_installation_id='67890',
            github_keyfile='/path/to/key.pem',
            webhook_secret='secret123'
        )
        assert config.github_app_id == '12345'
        assert config.github_installation_id == '67890'
        assert config.github_keyfile == '/path/to/key.pem'
        assert config.webhook_secret == 'secret123'


class TestRepoConfig:
    """
    Tests for RepoConfig model.
    """

    def test_repo_config_defaults(self):
        """
        Test RepoConfig with default branch.
        """

        config = RepoConfig(
            name='test-repo',
            directory='/tmp/repo',
            git_url='https://github.com/test/repo.git'
        )
        assert config.name == 'test-repo'
        assert config.directory == '/tmp/repo'
        assert config.git_url == 'https://github.com/test/repo.git'
        assert config.branch == 'master'
        assert config.provider == 'git'

    @pytest.mark.asyncio
    async def test_repo_config_sync(self):
        """
        Test RepoConfig.sync() calls sync_git_repo with correct parameters.
        """

        config = RepoConfig(
            name='test-repo',
            directory='/tmp/repo',
            git_url='https://github.com/test/repo.git',
            branch='main'
        )

        with patch('preoccupied.gitsync.config.sync_git_repo', new_callable=AsyncMock) as mock_sync:
            await config.sync()

        mock_sync.assert_called_once_with(
            repo_dir='/tmp/repo',
            git_url='https://github.com/test/repo.git',
            git_branch='main'
        )


class TestGitHubRepoConfig:
    """
    Tests for GitHubRepoConfig model.
    """

    def test_github_repo_config(self):
        """
        Test GitHubRepoConfig creation.
        """

        config = GitHubRepoConfig(
            name='github-repo',
            directory='/tmp/github-repo',
            git_url='https://github.com/test/repo.git',
            branch='main',
            provider='github',
            github_app_id='12345',
            github_installation_id='67890',
            github_keyfile='/path/to/key.pem'
        )
        assert config.provider == 'github'
        assert config.github_app_id == '12345'
        assert config.github_installation_id == '67890'
        assert config.github_keyfile == '/path/to/key.pem'

    @pytest.mark.asyncio
    async def test_github_installation_token_without_keyfile(self):
        """
        Test github_installation_token returns None when keyfile is not set.
        """

        config = GitHubRepoConfig(
            name='github-repo',
            directory='/tmp/github-repo',
            git_url='https://github.com/test/repo.git',
            branch='main',
            provider='github',
            github_keyfile=None
        )

        token = await config.github_installation_token()
        assert token is None

    @pytest.mark.asyncio
    async def test_github_installation_token_with_keyfile(self):
        """
        Test github_installation_token calls github_installation_token function.
        """

        config = GitHubRepoConfig(
            name='github-repo',
            directory='/tmp/github-repo',
            git_url='https://github.com/test/repo.git',
            branch='main',
            provider='github',
            github_app_id='12345',
            github_installation_id='67890',
            github_keyfile='/path/to/key.pem'
        )

        with patch('preoccupied.gitsync.config.github_installation_token', new_callable=AsyncMock, return_value='token123') as mock_token:
            token = await config.github_installation_token()

        assert token == 'token123'
        mock_token.assert_called_once_with(
            github_keyfile='/path/to/key.pem',
            github_app_id='12345',
            github_installation_id='67890'
        )

    @pytest.mark.asyncio
    async def test_github_repo_config_sync_with_token(self):
        """
        Test GitHubRepoConfig.sync() includes token in sync call.
        """

        config = GitHubRepoConfig(
            name='github-repo',
            directory='/tmp/github-repo',
            git_url='https://github.com/test/repo.git',
            branch='main',
            provider='github',
            github_keyfile='/path/to/key.pem'
        )

        with patch('preoccupied.gitsync.config.github_installation_token', new_callable=AsyncMock, return_value='token123'), \
             patch('preoccupied.gitsync.config.sync_git_repo', new_callable=AsyncMock) as mock_sync:

            await config.sync()

        mock_sync.assert_called_once_with(
            repo_dir='/tmp/github-repo',
            git_url='https://github.com/test/repo.git',
            git_branch='main',
            git_token='token123'
        )


class TestRootConfig:
    """
    Tests for RootConfig model.
    """

    def test_root_config_apply_global_defaults(self):
        """
        Test that global defaults are applied to repos.
        """

        config_data = {
            'global': {
                'webhook_secret': 'global-secret'
            },
            'repos': {
                'repo1': {
                    'directory': '/tmp/repo1',
                    'git_url': 'https://github.com/test/repo1.git'
                }
            }
        }

        config = RootConfig.model_validate(config_data)
        assert config.repos['repo1'].webhook_secret == 'global-secret'
        assert config.repos['repo1'].name == 'repo1'
        assert config.repos['repo1'].branch == 'master'

    def test_root_config_github_defaults(self):
        """
        Test that GitHub global defaults are applied to GitHub repos.
        """

        config_data = {
            'global': {
                'github_app_id': '12345',
                'github_installation_id': '67890',
                'github_keyfile': '/path/to/key.pem'
            },
            'repos': {
                'github-repo': {
                    'directory': '/tmp/github-repo',
                    'git_url': 'https://github.com/test/repo.git',
                    'provider': 'github'
                }
            }
        }

        config = RootConfig.model_validate(config_data)
        repo = config.repos['github-repo']
        assert isinstance(repo, GitHubRepoConfig)
        assert repo.github_app_id == '12345'
        assert repo.github_installation_id == '67890'
        assert repo.github_keyfile == '/path/to/key.pem'

    def test_root_config_repo_overrides_global(self):
        """
        Test that repo-specific values override global defaults.
        """

        config_data = {
            'global': {
                'webhook_secret': 'global-secret'
            },
            'repos': {
                'repo1': {
                    'directory': '/tmp/repo1',
                    'git_url': 'https://github.com/test/repo1.git',
                    'webhook_secret': 'repo-secret'
                }
            }
        }

        config = RootConfig.model_validate(config_data)
        assert config.repos['repo1'].webhook_secret == 'repo-secret'


class TestConfigFromEnv:
    """
    Tests for _config_from_env function.
    """

    def test_config_from_env_empty(self, mock_env_vars):
        """
        Test _config_from_env with no environment variables.
        """

        config = _config_from_env()
        assert config == {'global': {}}

    def test_config_from_env_global_vars(self, mock_env_vars):
        """
        Test _config_from_env with global environment variables.
        """

        mock_env_vars.setenv('GITSYNC_GITHUB_APP_ID', '12345')
        mock_env_vars.setenv('GITSYNC_GITHUB_INSTALLATION_ID', '67890')
        mock_env_vars.setenv('GITSYNC_WEBHOOK_SECRET', 'secret123')

        config = _config_from_env()
        assert config['global']['github_app_id'] == '12345'
        assert config['global']['github_installation_id'] == '67890'
        assert config['global']['webhook_secret'] == 'secret123'

    def test_config_from_env_repo_vars(self, mock_env_vars):
        """
        Test _config_from_env with repository environment variables.
        """

        mock_env_vars.setenv('GITSYNC_REPO_NAME', 'env-repo')
        mock_env_vars.setenv('GITSYNC_REPO_DIRECTORY', '/tmp/env-repo')
        mock_env_vars.setenv('GITSYNC_REPO_GIT_URL', 'https://github.com/test/env-repo.git')
        mock_env_vars.setenv('GITSYNC_REPO_BRANCH', 'develop')

        config = _config_from_env()
        assert 'repos' in config
        assert 'env-repo' in config['repos']
        assert config['repos']['env-repo']['name'] == 'env-repo'
        assert config['repos']['env-repo']['directory'] == '/tmp/env-repo'
        assert config['repos']['env-repo']['git_url'] == 'https://github.com/test/env-repo.git'
        assert config['repos']['env-repo']['branch'] == 'develop'

    def test_config_from_env_repo_defaults_name(self, mock_env_vars):
        """
        Test that repo name defaults to 'default' if not provided.
        """

        mock_env_vars.setenv('GITSYNC_REPO_DIRECTORY', '/tmp/repo')
        mock_env_vars.setenv('GITSYNC_REPO_GIT_URL', 'https://github.com/test/repo.git')

        config = _config_from_env()
        assert 'repos' in config
        assert 'default' in config['repos']
        assert config['repos']['default']['name'] == 'default'


class TestGetConfig:
    """
    Tests for get_config function.
    """

    def test_get_config_from_env_only(self, mock_env_vars):
        """
        Test get_config with environment variables only.
        """

        mock_env_vars.setenv('GITSYNC_REPO_NAME', 'env-repo')
        mock_env_vars.setenv('GITSYNC_REPO_DIRECTORY', '/tmp/env-repo')
        mock_env_vars.setenv('GITSYNC_REPO_GIT_URL', 'https://github.com/test/env-repo.git')

        import preoccupied.gitsync.config as config_module
        config_module._config = None

        with patch('preoccupied.gitsync.config.os.path.exists', return_value=False):

            config = get_config()
            assert 'env-repo' in config.repos

    def test_get_config_from_file(self, mock_env_vars, temp_dir):
        """
        Test get_config loading from YAML file.
        """

        config_file = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'global': {
                'webhook_secret': 'file-secret'
            },
            'repos': {
                'file-repo': {
                    'directory': '/tmp/file-repo',
                    'git_url': 'https://github.com/test/file-repo.git'
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        mock_env_vars.setenv('CONFIG_PATH', config_file)

        import preoccupied.gitsync.config as config_module
        config_module._config = None

        with patch('preoccupied.gitsync.config.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):

            config = get_config()
            assert 'file-repo' in config.repos
            assert config.repos['file-repo'].webhook_secret == 'file-secret'

    def test_get_config_env_overrides_file(self, mock_env_vars, temp_dir):
        """
        Test that environment variables override file config.
        """

        config_file = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'global': {
                'webhook_secret': 'file-secret'
            },
            'repos': {}
        }

        mock_env_vars.setenv('CONFIG_PATH', config_file)
        mock_env_vars.setenv('GITSYNC_WEBHOOK_SECRET', 'env-secret')

        import preoccupied.gitsync.config as config_module
        config_module._config = None

        with patch('preoccupied.gitsync.config.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):

            config = get_config()
            assert config.global_.webhook_secret == 'env-secret'

    def test_get_config_caches_result(self, mock_env_vars):
        """
        Test that get_config caches the result.
        """

        import preoccupied.gitsync.config as config_module
        config_module._config = None

        with patch('preoccupied.gitsync.config.os.path.exists', return_value=False):

            config1 = get_config()
            config2 = get_config()

            assert config1 is config2


# The end.
