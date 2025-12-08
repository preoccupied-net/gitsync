"""
GitHub-specific token logic for the gitsync application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import time

import jwt
import requests


def github_installation_token(
        github_keyfile: str,
        github_app_id: str,
        github_installation_id: str) -> str:
    """
    Get a GitHub installation token for the given app ID and
    installation ID using the private key in github_keyfile.
    Returns the installation token as a string.
    """

    if not (github_app_id and github_installation_id and github_keyfile):
        raise ValueError('github_app_id, github_installation_id, and github_keyfile must be set')

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

    r = requests.post(
        f'https://api.github.com/app/installations/{github_installation_id}/access_tokens',
        headers=headers,
    )
    r.raise_for_status()
    return r.json()['token']


# The end.
