"""
FastAPI webhook application for the gitsync service.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

from .config import get_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def app_startup():
    """
    Startup event handler for the app
    """

    # fetch configuration for the first time
    try:
        config = get_config()
    except Exception as e:
        logger.error(f'Failed to load configuration or sync repositories: {e}', exc_info=True)
        raise

    # pre-sync all repositories
    if not config.global_.sync_on_startup:
        return

    for repo_name, repo in config.repos.items():
        try:
            logger.info(f"Syncing repository '{repo_name}' on startup...")
            await repo.sync()
            logger.info(f"Successfully synced repository '{repo_name}'")
        except Exception as e:
            logger.error(f"Failed to sync repository '{repo_name}' on startup: {e}", exc_info=True)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    Lifespan event handler for the app
    """

    logger.info('Starting up...')

    await app_startup()

    try:
        yield
    finally:

        logger.info('Shutting down...')


app = FastAPI(lifespan=app_lifespan)


@app.post('/sync/{name}')
async def sync(name: str = 'default', x_sync_token: str = Header(None)):
    """
    Sync a specific repository by name
    """

    config = get_config()

    if name not in config.repos:
        raise HTTPException(status_code=404, detail=f"Repository '{name}' not found")

    repo = config.repos[name]
    webhook_secret = repo.webhook_secret

    if webhook_secret and x_sync_token != webhook_secret:
        raise HTTPException(status_code=401, detail='Bad secret')

    try:
        await repo.sync()
        return {'status': 'ok', 'repo': name}
    except Exception as e:
        logger.error(f"Error syncing repo '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f'Sync failed: {str(e)}')


# The end.
