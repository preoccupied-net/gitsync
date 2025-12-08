"""
GitHub-specific token logic for the gitsync application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Union, Dict, Tuple

import httpx
import jwt
import logging


logger = logging.getLogger(__name__)


CACHE_THRESHOLD = 50 * 60  # 50 minutes


# Cache for GitHub installation tokens, keyed by (app_id, installation_id)
_token_cache: Dict[Tuple[str, str], Dict[str, Union[str, datetime]]] = {}
_cache_lock = asyncio.Lock()


async def github_installation_token(
        github_keyfile: str,
        github_app_id: str,
        github_installation_id: str) -> str:
    """
    Get a GitHub installation token for the given app ID and
    installation ID using the private key in github_keyfile.
    Returns the installation token as a string.

    Tokens are cached and reused until they reach 75% of their
    lifetime (45 minutes), at which point a new token is requested.
    """

    if not (github_app_id and github_installation_id and github_keyfile):
        raise ValueError('github_app_id, github_installation_id, and github_keyfile must be set')

    cache_key = (github_app_id, github_installation_id)
    now = datetime.now(timezone.utc)

    # Check cache first
    async with _cache_lock:
        if cache_key in _token_cache:
            cached = _token_cache[cache_key]
            expires_at = cached['expires_at']
            # Check if token is still valid (hasn't reached 75% of lifetime)
            # Tokens expire after 60 minutes, so 75% = 45 minutes remaining
            threshold = expires_at.timestamp() - CACHE_THRESHOLD
            if now.timestamp() < threshold:
                logger.debug(f'Using cached token for {github_app_id} / {github_installation_id}')
                return cached['token']

            # Token is near expiry, remove from cache
            logger.debug(f'Token for {github_app_id} / {github_installation_id} is near expiry, removing from cache')
            del _token_cache[cache_key]

    # Cache miss or token expired, request new token
    with open(github_keyfile, 'r') as fk:
        private_key = fk.read()

    payload = {
        'iat': int(time.time()) - 60,
        'exp': int(time.time()) + (10 * 60),
        'iss': github_app_id,
    }

    jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f'https://api.github.com/app/installations/{github_installation_id}/access_tokens',
            headers=headers,
        )
        r.raise_for_status()
        response_data = r.json()

    token = response_data['token']
    expires_at_str = response_data['expires_at']

    # Parse expires_at (GitHub returns ISO 8601 format)
    expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))

    # Store in cache
    async with _cache_lock:
        _token_cache[cache_key] = {
            'token': token,
            'expires_at': expires_at,
        }

    logger.debug(f'New token for {github_app_id} / {github_installation_id} expires at {expires_at}')
    return token


# The end.
