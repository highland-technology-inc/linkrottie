import logging
import subprocess
import re
from collections import namedtuple
from pathlib import Path

from .taskqueue import taskqueue

log = logging.getLogger(__name__)

class Local:
    """Represents locally stored git repositories.
    
    Args:
        path: The root directory for local git repositories
    """
    
    def __init__(self, config:dict):
        self.path = Path(config.get('git', 'git'))
        self.aliases = config.get('aliases', {})
        self.already_mirrored = []
    
    def _clone(self, remote:str, local:Path):
        """Make a mirror clone of the git repository at remote."""
        
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
            
    def _update(self, local:Path):
        """Perform an update of the existing mirror clone at local."""
        
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
    
    def _get_submodules(self, local:Path):
        """Yield all submodule URLs from the head of the local repo."""
        
        submodules_file = get_submodules_file(local)
        if not submodules_file:
            return
        
        for line in submodules_file.splitlines():
            mo = re.match(r'\s+url\s*=\s*', line)
            if mo:
                url = line[mo.end():]
                yield url
    
    def mirror_repo(self, remote:str):
        """Create a local mirror clone of the git repository at remote.
        
        Local path is self.path / host / path, so for instance if self.path is
        ./local and remote = git@github.com:highland-technology-inc/linkrottie.git
        the mirror will be at
        ./local/github.com/highland-technology-inc/linkrottie.git
        
        """

        # First, map the remote URL against any aliases that might apply
        for original, replacement in self.aliases.items():
            if remote.startswith(original):
                remote = remote.replace(original, replacement)
                break

        repo = parse_url(remote)
        local = self.path / repo.host / repo.path.lstrip('/')
        
        if not local.is_dir():
            self._clone(remote, local)
        else:
            self._update(local)    
        self.already_mirrored.append(local)
        
        tq = taskqueue()
        for url in self._get_submodules(local):
            log.debug('Found submodule %s', url)
            tq.append(self.mirror_repo, url, desc='Submodule ' + url)

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

def get_submodules_file(repo_path:Path) -> str:
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

_local = None
def local(config:dict):
    """Return the singleon Local object."""
    global _local
    if not _local:
        _local = Local(config)
    return _local
