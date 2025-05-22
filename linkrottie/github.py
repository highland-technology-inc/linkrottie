import logging
from pathlib import Path
import requests

from . import git
from .taskqueue import taskqueue

log = logging.getLogger(__name__)

class Github:
    def __init__(self, config: dict):
        # Look for authentication mechanisms
        self.authentication = None
        if 'auth_key_file' in config:
            self.authentication = 'key_file'
            with open(config['auth_key_file'], 'r') as f:
                self.key = f.readline().strip()
        
        try:
            organization = config['organization']
            if not isinstance(organization, list):
                organization = list(organization)
            self.organization = organization
        except KeyError:
            self.organization = []
            
        self.session = requests.Session()
        self.session.headers.update({
            'Accept' : 'application/vnd.github+json',
            'Authorization' : f'Bearer {self.key}', 
            'X-Github-Api-Version' : '2022-11-28',
        })
            
        log.debug("Github getter created with %s authorization", self.authentication)
    
    def _get_org_repos(self, org:str):
        """Get all repositories available to this organization.
        
        Yields:
            Dicts containing repository information.
        
        """
        
        log.info('Getting %s repositories', org)
        url = f'https://api.github.com/orgs/{org}/repos'
        while True:
            response = self.session.get(url)
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

    def mirror_org_repos(self):
        tq = taskqueue()
        import pprint
        for org in self.organization:
            for repo in self._get_org_repos(org):
                fullname = repo['full_name']
                ssh  = repo['ssh_url']
                local = git.local()
                tq.append(local.mirror_repo, ssh, desc=f'Mirror {fullname}')
