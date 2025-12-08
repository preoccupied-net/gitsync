"""
Configuration models and loading for the gitsync application.

:author: Christopher O'Brien <obriencj@preoccupied.net>
:license: GNU General Public License v3
:ai-assistant: Auto via Cursor
"""

import logging
import os
from typing import Annotated, Any, Dict, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator

from .github import github_installation_token
from .gitsync import sync_git_repo


logger = logging.getLogger(__name__)


CONFIG_PATH = os.environ.get('CONFIG_PATH', '/config/config.yaml')


_config: Optional['RootConfig'] = None


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
    branch: str = 'master'
    webhook_secret: Optional[str] = None
    provider: Literal['git'] = 'git'


    async def sync(self) -> None:
        """
        Sync the repository.
        """

        return await sync_git_repo(
            repo_dir=self.directory,
            git_url=self.git_url,
            git_branch=self.branch,
        )


class GitHubRepoConfig(RepoConfig):
    """
    Repository configuration for GitHub repositories
    """

    provider: Literal['github']
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


    async def sync(self) -> None:
        """
        Sync the repository.
        """

        return await sync_git_repo(
            repo_dir=self.directory,
            git_url=self.git_url,
            git_branch=self.branch,
            git_token=self.github_installation_token()
        )


RepoTypes = Union[RepoConfig, GitHubRepoConfig]


class RootConfig(BaseModel):
    """
    Root configuration model
    """

    global_: GlobalConfig = Field(alias='global', default_factory=GlobalConfig)
    repos: Dict[str, Annotated[RepoTypes, Field(discriminator='provider')]] = Field(
        default_factory=dict
    )

    model_config = {'populate_by_name': True}


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
            provider = repo.setdefault('provider', 'git')

            if provider == 'github':
                repo.setdefault('github_keyfile', glbl.github_keyfile)
                repo.setdefault('github_app_id', glbl.github_app_id)
                repo.setdefault('github_installation_id', glbl.github_installation_id)

        return fixed


def get_config():
    """
    Get the global config object.
    """
    global _config

    if _config is None:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f'Config file not found: {CONFIG_PATH}')

        with open(CONFIG_PATH, 'r') as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ValueError('Config file is empty or invalid')

        _config = RootConfig.model_validate(config_data)
        logger.info(f'Loaded configuration with {len(_config.repos)} repositories')

    return _config


def get_repo_config(repo_name: str) -> Optional[Union[RepoConfig, GitHubRepoConfig]]:
    """
    Get the repository configuration for the given repository name.
    """

    return get_config().repos.get(repo_name)


# The end.
