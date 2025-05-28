import logging
from pathlib import Path
import requests

from . import git
from .taskqueue import taskqueue

log = logging.getLogger(__name__)

class Github:
    """A class for gathering repository information from Github.
    
    A call to mirror_org_repos will cause the class to use the Github API
    to query all repositories, public and private, belonging to the organization.
    
    Any repositories not in the explicit config['ignore'] list will be added to
    the task queue for mirroring.

    If config['dry_run'] is true, only prints INFO level messages about what
    repositories would be fetched rather than fetching them.
    """

    def __init__(self, org: str, config: dict):
        # Look for authentication mechanisms
        self.authentication = None
        if 'auth_key_file' in config:
            self.authentication = 'key_file'
            with open(config['auth_key_file'], 'r') as f:
                self.key = f.readline().strip()
        
        self.organization = org
            
        self.session = requests.Session()
        self.session.headers.update({
            'Accept' : 'application/vnd.github+json',
            'Authorization' : f'Bearer {self.key}', 
            'X-Github-Api-Version' : '2022-11-28',
        })
        
        self.dry_run = config.get('dry_run', False)
        self.ignore = [x.casefold() for x in config.get('ignore', [])]
        
        log.debug("Github getter created with %s authorization", self.authentication)

    def _get_org_repos(self, org:str):
        """Get all repositories available to this organization.
        
        Yields:
            Dicts containing repository information.
        
        """
        

    def mirror_org_repos(self):
        """Query Github for all the repositories associated with this organization,
        and request they be mirrored.
        """
        
        tq = taskqueue()

        org = self.organization
        log.info('Getting %s repositories', org)
        url = f'https://api.github.com/orgs/{org}/repos'
        while True:
            response = self.session.get(url)
            response.raise_for_status()

            # First go through all the repos in this search result
            for repo in response.json():
                fullname = repo['full_name']
                if repo['name'].casefold() in self.ignore:
                    log.debug('Ignoring %s', fullname)
                    continue

                ssh  = repo['ssh_url']
                local = git.local(None)

                log.info('Mirroring Github repository %s', fullname)
                if not self.dry_run:
                    tq.append(local.mirror_repo, ssh, desc=f'Mirror {fullname}')

            # Next, see if there's a "next" link on in the headers, in which case
            # there's another page of results to go through.
            try:
                link = response.headers['link']
                mo = re.search(r'<([^>]+)>; rel="next"')
                if not mo:
                    raise ValueError('invalid link header: ' + link)
                url = mo.groups(1)
            except KeyError:
                break