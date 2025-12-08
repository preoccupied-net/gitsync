"""
Git synchronization service with webhook support.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

from preoccupied.gitsync.app import app
from preoccupied.gitsync.config import get_config, get_repo_config


__all__ = ['app', 'get_config', 'get_repo_config']


# The end.
