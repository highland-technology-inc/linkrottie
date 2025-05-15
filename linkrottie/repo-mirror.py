#!/usr/bin/env python3

import requests
import json
import re
import subprocess
from pathlib import Path
import os

from collections import namedtuple

def get_api_key() -> str:
    with open('API_KEY', 'r') as f:
        key = f.readline().strip()
    return key
    
API_KEY = get_api_key()

def github_org_repos(organization = 'highland-technology-inc'):
    """Get all repositories available to this organization.
    
    Yields:
        Dicts containing repository information.
    
    """
    
    sesh = requests.Session()
    sesh.headers.update({
        'Accept' : 'application/vnd.github+json',
        'Authorization' : f'Bearer {API_KEY}', 
        'X-Github-Api-Version' : '2022-11-28',
    })
    
    url = f'https://api.github.com/orgs/{organization}/repos'
    while True:
        response = sesh.get(url)
        response.raise_for_status()
        yield from response.json()
        
        try:
            link = response.headers['link']
            mo = re.search(r'<([^>]+)>; rel="next"')
            if not mo:
                raise ValueError('invalid link header: ' + link)
            url = mo.groups(1)
        except KeyError:
            break
    
def _is_git_dir(start_path:Path) -> bool:
    """Determine if p is a git directory.
    
    This is taken from the comments on is_git_directory() in the git source, 
    though a slightly looser version since we'll only look for HEAD and not try 
    to validate it.
    
    Basically, this assumes a non-hostile filesystem with git repos that
    want to be found.
    """

    head = start_path / 'HEAD'
    try:
        objects = os.environ['GIT_OBJECT_DIRECTORY']
    except KeyError:
        objects = start_path / 'objects'
    refs = start_path / 'refs'
    
    return (
        (head.is_file() or head.is_symlink()) and
        objects.is_dir() and
        refs.is_dir()
    )
    
def _walk_until_git(start_path:Path, follow_symlinks=False):
    """Walk all directories under start_path, yielding git repos.
    
    This is similar to Path.walk, but won't keep recursively looking once
    a Git repos has been found.  That's a pretty minor efficiency gain, unless
    what you're pointed at is largely git repos, which in our case it's likely
    to be.
    
    Yields:
        Paths to git repositories.
    """
    
    # First, check to see if this is a git directory.
    # If it is, we're done.
    #
    if _is_git_dir(start_path):
        # Should only be a git directory if it's a bare repo; if this is
        # a .git subdirectory it's an error (because we started in what is
        # already a subdirectory of the repo.
        #
        if start_path.name == '.git':
            raise ValueError('start_path is .git subdirectory')
            
        yield start_path
        return
    
    # See if there is a .git subdirectory that makes this a working copy.
    git_subdir = start_path / '.git'
    if git_subdir.is_dir() and _is_git_dir(git_subdir):
        yield start_path
        return
        
    # Nope, recursion is called for.  Go down through any subdirectories.
    for p in start_path.iterdir():
        if (p.is_symlink() and follow_symlinks):
            p = p.resolve(strict=True)
            
        if p.is_dir():
            yield from _walk_until_git(p, follow_symlinks)
    
def local_repos(start_path, follow_symlinks=False):
    """Get all local repositories under a path.
    
    Yields:
        Paths to git respositories.
    """
    
    top = Path(start_path)
    yield from _walk_until_git(top)
    
def get_submodules_file(repo_path) -> str:
    """Gets the Git .gitmodules file from the head of repo.
    
    This file describes all submodules used by the repository.  This
    function works properly on both working and bare repositories.
    
    Returns:
        The text of the file, or None if the file is not present.
        
    Raises:
        FileNotFoundError if the path is not a git repository, or a
        CalledProcessError if things fail for some other reason.
    """
    
    
    result = subprocess.run(
        ['git', 'show', '@:.gitmodules'],
        capture_output=True,
        cwd=repo_path,
        encoding='utf-8'
    )
    if result.returncode:
        if "'.gitmodules' does not exist" in result.stderr:
            return None
        if 'not a git repository' in result.stderr:
            raise FileNotFoundError(f'Not a git repository: {repo_path}')
        result.check_returncode()

    return result.stdout


RemoteRepo = namedtuple('RemoteRepo', 'scheme user host port path'.split())

def parse_url(url: str):
    """Parse a URL that points to a remote git repository into
    constituent parts."""
    
    # Look for URL specified locations
    mo = re.match(r'''
        (\w+)://                # scheme,   exclude ://
        (?:([^/?#@:]+)@)?       # user,     exclude @
        ([^/?#@:]*)             # host
        (?::(\d+))?             # port,     exclude :
        (/.*)                   # path
    ''', url, re.X)
    
    if mo:
        # Extract and clean the parts of the URL
        return RemoteRepo(*mo.groups())
    
    # Look for SCP specified locations
    mo = re.match(r'''
        (?:([^/?#@:]+)@)?       # user,     exclude @
        ([^/?#@:]*)             # host
        :
        (.*)                    # path
    ''', url, re.X)
    if mo:
        scheme = port = None
        user, host, path = mo.groups()
        return RemoteRepo(scheme, user, host, port, path)
        
    # Look for local file specified locations
    return RemoteRepo('', '', '', '', url)

if __name__ == '__main__':
    #print(get_repos())
    pass
