import logging
import subprocess
import re
from collections import namedtuple
from pathlib import Path

log = logging.getLogger(__name__)

def mirror_repo(remote:str, local:Path):
    if not local.is_dir():
        parent = local.parent
        if not parent.is_dir():
            log.info('Creating directory %s', parent)
            parent.mkdir(parents=True, exist_ok=True)
        
        log.info('Cloning %s to %s', remote, local)
        result = subprocess.run(
            ['git', 'clone', '--mirror', remote, local.name],
            capture_output=True, text=True,
            cwd = parent
        )
        if result.returncode:
            log.error("git clone --mirror %s %s returned with %s: %s",
                remote, local.name, result.returncode, result.stderr
            )
            
        
    else:
        log.info('Updating %s', local)
        result = subprocess.run(
            ['git', 'remote', 'update'],
            capture_output=True, text=True,
            cwd = local
        )
        if result.returncode:
            log.error("git remote update %s returned with %s: %s",
                local.name, result.returncode, result.stderr
            )

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
