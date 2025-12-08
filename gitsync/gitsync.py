"""
Gitsync API server.
"""

import logging
import os
import subprocess
import time
from typing import Any, Dict, Optional

import jwt
import requests
import yaml
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load configuration
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")


# Global config storage
_config: Optional["RootConfig"] = None


def run(*args: str, cwd: str = None) -> None:
    subprocess.check_call(args, cwd=cwd)


class GlobalConfig(BaseModel):
    """
    Global configuration settings
    """

    github_app_id: Optional[str] = None
    github_installation_id: Optional[str] = None
    github_keyfile: Optional[str] = None


class RepoConfig(BaseModel):
    """
    Repository configuration
    """

    name: str
    directory: str
    git_url: str
    branch: str = "master"
    webhook_secret: Optional[str] = None


    def sync(self) -> None:
        """
        Sync the repository.
        """

        return sync_git_repo(
            repo_dir=self.directory,
            git_url=self.git_url,
            git_branch=self.branch,
        )


class GitHubRepoConfig(RepoConfig):
    """
    Repository configuration
    """

    # Optional per-repo overrides
    github_app_id: Optional[str] = None
    github_installation_id: Optional[str] = None
    github_keyfile: Optional[str] = None


    def github_installation_token(self) -> Optional[str]:
        """
        Get a GitHub installation token for the given repository.
        """

        if not self.github_keyfile:
            return None

        return github_installation_token(
            github_keyfile=self.github_keyfile,
            github_app_id=self.github_app_id,
            github_installation_id=self.github_installation_id
        )


    def sync(self) -> None:
        """
        Sync the repository.
        """

        return sync_git_repo(
            repo_dir=self.directory,
            git_url=self.git_url,
            git_branch=self.branch,
            git_token=self.github_installation_token()
        )


class RootConfig(BaseModel):
    """
    Root configuration model
    """

    global_: GlobalConfig = Field(alias="global", default_factory=GlobalConfig)
    repos: Dict[str, GitHubRepoConfig] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


    @model_validator(mode='before')
    def apply_global_defaults(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply global config defaults to repos that don't have them set.
        """

        fixed = {}
        glbl = fixed['global'] = GlobalConfig.model_validate(v.get('global', {}))

        repos = fixed['repos'] = v.get('repos', {})
        for repo_name, repo in repos.items():
            repo = repos[repo_name] = repo.copy()
            repo.setdefault('name', repo_name)
            repo.setdefault('github_keyfile', glbl.github_keyfile)
            repo.setdefault('github_app_id', glbl.github_app_id)
            repo.setdefault('github_installation_id', glbl.github_installation_id)
            repo.setdefault('global', glbl)

        return fixed


def get_config():
    """
    Get the global config object.
    """
    global _config

    if _config is None:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

        with open(CONFIG_PATH, 'r') as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ValueError("Config file is empty or invalid")

        # Parse and validate with Pydantic
        _config = RootConfig.model_validate(config_data)
        logger.info(f"Loaded configuration with {len(_config.repos)} repositories")

    return _config


def get_repo_config(repo_name: str) -> RepoConfig:
    """
    Get the repository configuration for the given repository name.
    """

    return get_config().repos.get(repo_name)


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
        raise ValueError("github_app_id, github_installation_id, and github_keyfile must be set")

    with open(github_keyfile, 'r') as fk:
        private_key = fk.read()

    payload = {
        'iat': int(time.time()) - 60,
        'exp': int(time.time()) + (10 * 60),
        'iss': github_app_id,
    }

    jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.post(
        f"https://api.github.com/app/installations/{github_installation_id}/access_tokens",
        headers=headers,
    )
    r.raise_for_status()
    return r.json()["token"]


def sync_git_repo(
        repo_dir: str,
        git_url: str,
        git_branch: str,
        git_token: Optional[str] = None) -> None:
    """
    Initial or update the sync of the repository specified by repo_name.
    """

    if git_token:
        git_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")

    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        # first-time clone
        os.makedirs(repo_dir, exist_ok=True)
        run("git", "clone", git_url, repo_dir)
    else:
        # update existing checkout
        if git_token:
            run("git", "remote", "set-url", "origin", git_url)
        run("git", "fetch", "--all", "--prune")
        run("git", "reset", "--hard", f"origin/{git_branch}")

    # print current commit so it shows in logs
    run("git", "log", "-1", "--oneline", cwd=repo_dir)


app = FastAPI()


@app.post("/sync/{name}")
def sync(name: str, x_sync_token: str = Header(None)):
    """
    Sync a specific repository by name
    """

    config = get_config()

    if name not in config.repos:
        raise HTTPException(status_code=404, detail=f"Repository '{name}' not found")

    repo = config.repos[name]
    webhook_secret = repo.webhook_secret

    if webhook_secret and x_sync_token != webhook_secret:
        raise HTTPException(status_code=401, detail="Bad secret")

    try:
        repo.sync()
        return {"status": "ok", "repo": name}
    except Exception as e:
        logger.error(f"Error syncing repo '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.on_event("startup")
def startup_event():
    """
    Load config and sync all repositories on startup
    """

    try:
        config = get_config()
    except Exception as e:
        logger.error(f"Failed to load configuration or sync repositories: {e}", exc_info=True)
        raise

    # Sync all configured repositories
    for repo_name, repo in config.repos.items():
        try:
            logger.info(f"Syncing repository '{repo_name}' on startup...")
            repo.sync()
            logger.info(f"Successfully synced repository '{repo_name}'")
        except Exception as e:
            logger.error(f"Failed to sync repository '{repo_name}' on startup: {e}", exc_info=True)


# The end.
