# Preoccupied Git Sync

Preoccupied Git Sync is a Python package and containerized service for automatically synchronizing Git repositories. It provides a FastAPI-based webhook endpoint that can trigger repository synchronization on demand, and automatically syncs all configured repositories on startup. The service supports both standard Git repositories and GitHub repositories with App-based authentication.

## Purpose

The Preoccupied Git Sync Python package provides a lightweight service for maintaining local copies of remote Git repositories. It can be deployed as a container and configured either through environment variables for simple single-repository deployments, or via a YAML configuration file for more complex multi-repository setups. The service exposes a webhook endpoint that allows external systems to trigger repository synchronization, with optional secret-based authentication.

## Environment Variable Deployment

For simple single-repository deployments, Preoccupied GitSync can be configured entirely through environment variables. Here's an example `docker-compose.yml`:

```yaml
version: "3.9"

services:
  gitsync:
    image: ghcr.io/preoccupied-net/gitsync
    restart: unless-stopped

    environment:
      - GITSYNC_REPO_NAME=my-repo
      - GITSYNC_REPO_DIRECTORY=/repos/my-repo
      - GITSYNC_REPO_GIT_URL=https://github.com/user/my-repo.git
      - GITSYNC_REPO_BRANCH=main
      - GITSYNC_REPO_PROVIDER=git
      - GITSYNC_WEBHOOK_SECRET=your-secret-here
      - GITSYNC_GITHUB_APP_ID=123456
      - GITSYNC_GITHUB_INSTALLATION_ID=789012
      - GITSYNC_GITHUB_KEYFILE=/path/to/key.pem

    volumes:
      - ./repos:/repos

    ports:
      - "8080:8080"
```

### Environment Variables

**Required for repository configuration:**
- `GITSYNC_REPO_NAME` - Repository name
- `GITSYNC_REPO_DIRECTORY` - Directory path for the repository
- `GITSYNC_REPO_GIT_URL` - Git repository URL

**Optional repository settings:**
- `GITSYNC_REPO_BRANCH` - Git branch (default: 'master')
- `GITSYNC_REPO_PROVIDER` - Provider type: 'git' or 'github' (default: 'git')
- `GITSYNC_WEBHOOK_SECRET` - Global webhook secret for authentication

**Optional global GitHub settings:**
- `GITSYNC_GITHUB_APP_ID` - Global GitHub App ID
- `GITSYNC_GITHUB_INSTALLATION_ID` - Global GitHub Installation ID
- `GITSYNC_GITHUB_KEYFILE` - Global GitHub keyfile path

## Configuration File Deployment

For more complex deployments with multiple repositories, use a YAML configuration file. Environment variables can still be used to set global defaults (such as GitHub credentials or webhook secrets) that will apply to all repositories unless overridden.

Example configuration file (`/config/config.yaml`):

```yaml
global:
  github_app_id: "123456"
  github_installation_id: "789012"
  github_keyfile: "/path/to/github-key.pem"
  webhook_secret: "global-secret-for-all-repos"

repos:
  my-project:
    directory: /repos/my-project
    git_url: https://github.com/user/my-project.git
    branch: main
    provider: git
    webhook_secret: "specific-secret-for-this-repo"

  github-repo:
    directory: /repos/github-repo
    git_url: https://github.com/org/github-repo.git
    branch: develop
    provider: github
    github_app_id: "987654"
    github_installation_id: "345678"
    github_keyfile: "/path/to/repo-specific-key.pem"
```

In this example, `my-project` uses the standard Git provider and has its own webhook secret that overrides the global one. The `github-repo` uses GitHub App authentication with repository-specific credentials, while still inheriting the global webhook secret since it doesn't specify its own.

## Contact

Author: Christopher O'Brien <obriencj@preoccupied.net>

Original Repository: https://github.com/preoccupied-net/gitsync

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
