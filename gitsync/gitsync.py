"""
Gitsync API server.
"""

import os
import subprocess
import sys
import time

import jwt
import requests
from fastapi import FastAPI, Header, HTTPException


GIT_URL = os.environ["GIT_URL"]
GIT_BRANCH = os.environ.get("GIT_BRANCH", "master")
GIT_KEYFILE = os.environ.get("GIT_KEYFILE")  # optional shared secret
GIT_APP_ID = os.environ.get("GIT_APP_ID")
GIT_INSTALLATION_ID = os.environ.get("GIT_INSTALLATION_ID")

REPO_DIR = os.environ.get("REPO_DIR", "/work")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


def get_installation_token(
        git_keyfile: str,
        gid_app_id: str = GIT_APP_ID,
        gid_installation_id: str = GIT_INSTALLATION_ID):
    """
    Get a GitHub installation token for the given app ID GIT_APP_ID and
    installation ID GIT_INSTALLATION_ID using the private key in GIT_KEYFILE.
    Returns the installation token as a string.
    """

    if not (gid_app_id and gid_installation_id and git_keyfile):
        raise ValueError("GIT_APP_ID, GIT_INSTALLATION_ID, and GIT_KEYFILE must be set")

    with open(git_keyfile, 'r') as fk:
        private_key = fk.read()

    payload = {
        'iat': int(time.time()) - 60,
        'exp': int(time.time()) + (10 * 60),
        'iss': gid_app_id,
    }

    jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.post(
        f"https://api.github.com/app/installations/{gid_installation_id}/access_tokens",
        headers=headers,
    )
    r.raise_for_status()
    return r.json()["token"]


def run(*args: str, cwd: str = None) -> None:
    subprocess.check_call(args, cwd=cwd)


def initial_or_update_sync(
        repo_dir: str,
        git_url: str,
        git_branch: str = "master",
        git_keyfile: str = None) -> None:
    """
    Initial or update the sync of the repository.
    """

    if git_keyfile:
        git_token = get_installation_token(git_keyfile)
        git_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")

    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        # first-time clone
        os.makedirs(repo_dir, exist_ok=True)
        run("git", "clone", git_url, repo_dir)
    else:
        # update existing checkout
        if git_keyfile:
            run("git", "remote", "set-url", "origin", git_url)
        run("git", "fetch", "--all", "--prune")
        run("git", "reset", "--hard", f"origin/{git_branch}")

    # print current commit so it shows in logs
    run("git", "log", "-1", "--oneline", cwd=repo_dir)


app = FastAPI()


@app.post("/sync")
def sync(x_sync_token: str = Header(None)):
    if WEBHOOK_SECRET and x_sync_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Bad secret")

    initial_or_update_sync(
        repo_dir=REPO_DIR,
        git_url=GIT_URL,
        git_branch=GIT_BRANCH,
        git_keyfile=GIT_KEYFILE,
    )
    return {"status": "ok"}


@app.on_event("startup")
def startup_event():
    initial_or_update_sync()


# The end.
