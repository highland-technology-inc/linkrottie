#!/usr/bin/env python3

import requests
import json
import re
import subprocess
import pathlib

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
    
def _walk_until_git(start_path:pathlib.Path, follow_symlinks=False):
    """Walk all directories under start_path, yielding git repos.
    
    This is similar to Path.walk, but won't keep recursively looking once
    a Git repos has been found.  That's a pretty minor efficiency gain, unless
    what you're pointed at is largely git repos.
    
    Yields:
        Paths to git repositories.
    """
    
    subdirs = []
    filematch = {'config', 'description', 'HEAD'}
    dirmatch  = {'objects', 'refs'}
    for p in start_path.iterdir():
        if p.is_symlink():
            if follow_symlinks:
                subdirs.append(p)
        elif p.is_dir():
            subdirs.append(p)
            dirmatch.discard(p.name)
        elif p.is_file():
            filematch.discard(p.name)
        
        # Have we determined this to be a git repo?
        if not filematch and not dirmatch:
            if start_path.name == '.git':
                # This is a working repo
                yield start_path.parent
            else:
                # This is a bare repo
                yield start_path
            # In either case, we're done recurring
            return
    
    # We've analyzed this directory, and it's not a git repo.
    for d in subdirs:
        yield from _walk_until_git(d, follow_symlinks)
    
def local_repos(start_path, follow_symlinks=False):
    """Get all local repositories under a path.
    
    Yields:
        Paths to git respositories.
    """
    
    top = pathlib.Path(start_path)
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
    
if __name__ == '__main__':
    #print(get_repos())
    pass
