"""
Unit tests for GitHub module.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import jwt
import pytest

from preoccupied.gitsync import github


@pytest.fixture(autouse=True)
def clear_token_cache():
    """
    Clear the GitHub token cache before and after each test.
    """

    github._token_cache.clear()
    yield
    github._token_cache.clear()


class TestGitHubInstallationToken:
    """
    Tests for github_installation_token function.
    """

    @pytest.mark.asyncio
    async def test_github_installation_token_missing_params(self):
        """
        Test that ValueError is raised when required parameters are missing.
        """

        with pytest.raises(ValueError, match='github_app_id, github_installation_id, and github_keyfile must be set'):
            await github.github_installation_token(
                github_keyfile='',
                github_app_id='12345',
                github_installation_id='67890'
            )

    @pytest.mark.asyncio
    async def test_github_installation_token_missing_app_id(self):
        """
        Test ValueError when github_app_id is missing.
        """

        with pytest.raises(ValueError, match='github_app_id, github_installation_id, and github_keyfile must be set'):
            await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='',
                github_installation_id='12345'
            )

    @pytest.mark.asyncio
    async def test_github_installation_token_success(self):
        """
        Test successful token retrieval.
        """

        private_key = '-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----'
        mock_response_data = {
            'token': 'ghs_test_token_12345',
            'expires_at': '2024-01-01T12:00:00Z'
        }

        with patch('builtins.open', mock_open(read_data=private_key)), \
             patch('preoccupied.gitsync.github.httpx.AsyncClient') as mock_client_class, \
             patch('preoccupied.gitsync.github.jwt.encode', return_value='mock_jwt_token'), \
             patch('preoccupied.gitsync.github.time.time', return_value=1000):

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            token = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='12345',
                github_installation_id='67890'
            )

        assert token == 'ghs_test_token_12345'
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert 'https://api.github.com/app/installations/67890/access_tokens' in str(call_args)
        assert 'Authorization' in call_args[1]['headers']
        assert call_args[1]['headers']['Authorization'] == 'Bearer mock_jwt_token'

    @pytest.mark.asyncio
    async def test_github_installation_token_caches_result(self):
        """
        Test that tokens are cached and reused.
        """

        private_key = '-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----'
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_response_data = {
            'token': 'ghs_cached_token',
            'expires_at': expires_at.isoformat().replace('+00:00', 'Z')
        }

        with patch('builtins.open', mock_open(read_data=private_key)), \
             patch('preoccupied.gitsync.github.httpx.AsyncClient') as mock_client_class, \
             patch('preoccupied.gitsync.github.jwt.encode', return_value='mock_jwt_token'), \
             patch('preoccupied.gitsync.github.time.time', return_value=1000), \
             patch('preoccupied.gitsync.github.datetime') as mock_datetime:

            mock_now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.return_value = expires_at

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # First call - should make HTTP request
            token1 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='12345',
                github_installation_id='67890'
            )

            # Second call - should use cache
            token2 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='12345',
                github_installation_id='67890'
            )

        assert token1 == 'ghs_cached_token'
        assert token2 == 'ghs_cached_token'
        assert token1 is token2
        # Should only make one HTTP call
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_github_installation_token_refreshes_near_expiry(self):
        """
        Test that tokens are refreshed when near expiry.
        """

        private_key = '-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----'

        # Create a token that expires in 20 minutes (less than 50 minute threshold)
        expires_at_soon = datetime.now(timezone.utc) + timedelta(minutes=20)
        mock_response_data_old = {
            'token': 'ghs_old_token',
            'expires_at': expires_at_soon.isoformat().replace('+00:00', 'Z')
        }

        expires_at_new = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_response_data_new = {
            'token': 'ghs_new_token',
            'expires_at': expires_at_new.isoformat().replace('+00:00', 'Z')
        }

        with patch('builtins.open', mock_open(read_data=private_key)), \
             patch('preoccupied.gitsync.github.httpx.AsyncClient') as mock_client_class, \
             patch('preoccupied.gitsync.github.jwt.encode', return_value='mock_jwt_token'), \
             patch('preoccupied.gitsync.github.time.time', return_value=1000), \
             patch('preoccupied.gitsync.github.datetime') as mock_datetime:

            mock_now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.side_effect = [expires_at_soon, expires_at_new]

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.side_effect = [mock_response_data_old, mock_response_data_new]
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # First call - creates token expiring soon
            token1 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='12345',
                github_installation_id='67890'
            )

            # Second call - should refresh because token is near expiry
            token2 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='12345',
                github_installation_id='67890'
            )

        assert token1 == 'ghs_old_token'
        assert token2 == 'ghs_new_token'
        # Should make two HTTP calls (one for initial, one for refresh)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_github_installation_token_http_error(self):
        """
        Test that HTTP errors are properly raised.
        """

        private_key = '-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----'

        with patch('builtins.open', mock_open(read_data=private_key)), \
             patch('preoccupied.gitsync.github.httpx.AsyncClient') as mock_client_class, \
             patch('preoccupied.gitsync.github.jwt.encode', return_value='mock_jwt_token'), \
             patch('preoccupied.gitsync.github.time.time', return_value=1000):

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                'Error', request=MagicMock(), response=MagicMock()
            )
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await github.github_installation_token(
                    github_keyfile='/path/to/key.pem',
                    github_app_id='12345',
                    github_installation_id='67890'
                )

    @pytest.mark.asyncio
    async def test_github_installation_token_different_app_ids_cached_separately(self):
        """
        Test that tokens for different app/installation IDs are cached separately.
        """

        private_key = '-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----'
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_response_data1 = {
            'token': 'ghs_token_app1',
            'expires_at': expires_at.isoformat().replace('+00:00', 'Z')
        }
        mock_response_data2 = {
            'token': 'ghs_token_app2',
            'expires_at': expires_at.isoformat().replace('+00:00', 'Z')
        }

        with patch('builtins.open', mock_open(read_data=private_key)), \
             patch('preoccupied.gitsync.github.httpx.AsyncClient') as mock_client_class, \
             patch('preoccupied.gitsync.github.jwt.encode', return_value='mock_jwt_token'), \
             patch('preoccupied.gitsync.github.time.time', return_value=1000), \
             patch('preoccupied.gitsync.github.datetime') as mock_datetime:

            mock_now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.return_value = expires_at

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.side_effect = [mock_response_data1, mock_response_data2]
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            token1 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='app1',
                github_installation_id='inst1'
            )

            token2 = await github.github_installation_token(
                github_keyfile='/path/to/key.pem',
                github_app_id='app2',
                github_installation_id='inst2'
            )

        assert token1 == 'ghs_token_app1'
        assert token2 == 'ghs_token_app2'
        # Should make two HTTP calls for different app/installation IDs
        assert mock_client.post.call_count == 2


# The end.
