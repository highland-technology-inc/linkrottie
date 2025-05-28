import logging
import subprocess
import re
from collections import namedtuple
from pathlib import Path
from urllib.parse import urljoin
from typing import Self

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

        repo = RemoteRepo.parse_url(remote)
        local = self.path / repo.host / repo.path.lstrip('/')
        
        if local in self.already_mirrored:
            log.debug('Already evalulated %s', local)
            return

        if not local.is_dir():
            self._clone(remote, local)
        else:
            self._update(local)    
        self.already_mirrored.append(local)
        
        tq = taskqueue()
        for url in self._get_submodules(local):
            if url.startswith('..') or url.startswith('/'):
                # This is a local reference, rather than an absolute one.
                # Slap it together with the existing remote URL to get an
                # absolute one instead.
                log.debug('%s has relative submodule %s', remote, url)
                url = repo.join_url(url).deparse()

            log.debug('Found submodule %s', url)
            tq.append(self.mirror_repo, url, desc='Submodule ' + url)

class RemoteRepo:
    """Represents the parts of a remote repository."""
    def __init__(self, scheme, user, host, port, path):
        self.scheme = scheme or ''
        self.user = user or ''
        self.host = host or ''
        self.port = port or ''
        self.path = path or ''

    def __repr__(self) -> str:
        return "{}({},{},{},{},{})".format(
            type(self).__name__,
            self.scheme,
            self.user,
            self.host,
            self.port,
            self.path
        )

    @staticmethod
    def parse_url(url:str) -> Self:
        """Parse a URL that points to a remote git repository into
        constituent parts."""
        
        # Look for URL specified locations
        mo = re.match(r'''
            (\w+)://                # scheme,   exclude ://
            ([^/?#@:]+@)?           # user,     include @
            ([^/?#@:]+)             # host
            (:\d+)?                 # port,     include :
            (/.*)                   # path
        ''', url, re.X)
        
        if mo:
            # Extract and clean the parts of the URL
            return RemoteRepoUrl(*mo.groups())

        # Look for SCP specified locations, translate them
        # into SSH style
        mo = re.match(r'''
            ([^/?#@:]+@)?           # user,     include @
            ([^/?#@:]*)             # host
            :
            (.*)                    # path
        ''', url, re.X)
        if mo:
            scheme = port = None
            user, host, path = mo.groups()
            return RemoteRepoScp(scheme, user, host, port, path)
            
        # Look for local file specified locations
        if url.startswith('file://'):
            return RemoteRepoFile('file://', '', '', '', url[7:])
        return RemoteRepoFile('', '', '', '', url)

    def deparse(self):
        raise NotImplementedError('deparse')
    
    def join_url(self, relative:str):
        p = self.path
        if relative.startswith('/'):
            relative = relative[1:]
            p = ''
        
        while relative.startswith('../'):
            relative = relative[3:]
            p, _, _ = p.rpartition('/')

        if relative:
            p = p + '/' + relative
        
        return type(self)(self.scheme, self.user, self.host, self.port, p)

class RemoteRepoUrl(RemoteRepo):
    """Represents the parts of a remote repository in URL format."""

    def deparse(self):
        return f'{self.scheme}://{self.user}{self.host}{self.port}{self.path}'

class RemoteRepoScp(RemoteRepo):
    """Represents the parts of a remote repository in SCP format."""

    def deparse(self):
        return f'{self.user}{self.host}:{self.path}'

class RemoteRepoFile(RemoteRepo):
    """Represents the parts of a remote repository in file format."""

    def deparse(self):
        return self.host + self.path

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
        ['git', 'show', 'HEAD:.gitmodules'],
        capture_output=True,
        cwd=repo_path,
        encoding='utf-8'
    )
    if result.returncode:
        if "'.gitmodules' does not exist" in result.stderr:
            # No submodules
            return None
        
        if "invalid object name 'HEAD'" in result.stderr:
            # No commits
            return None
        
        if 'not a git repository' in result.stderr:
            raise FileNotFoundError(f'Not a git repository: {repo_path}')
        
        log.error('unknown error in get_submodules_file(%s): %s', repo_path, result.stderr)
        result.check_returncode()

    return result.stdout

_local = None
def local(config:dict):
    """Return the singleon Local object."""
    global _local
    if not _local:
        _local = Local(config)
    return _local
