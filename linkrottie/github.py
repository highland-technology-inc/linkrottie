import logging
from pathlib import Path
from urllib.parse import parse_qs
import re
import time
import requests

from . import git
from .taskqueue import taskqueue

APP_CLIENT_ID='Iv23liJmy1ntxW2kskqG'

log = logging.getLogger(__name__)

class Github:
    """A class for gathering repository information from Github.
    
    A call to mirror_org_repos will cause the class to use the Github API
    to query all repositories, public and private, belonging to the organization.
    
    Any repositories not in the explicit config['ignore'] list will be added to
    the task queue for mirroring.

    If config['dry_run'] is true, only prints INFO level messages about what
    repositories would be fetched rather than fetching them.

    If new_uat is provided, updates the auth_key_file rather than read it.

    """

    def __init__(self, org: str, config: dict, new_uat:str=None):
        # Look for authentication mechanisms
        self.authentication = None
        if 'auth_key_file' in config:
            self.authentication = 'key_file'
            filename = config['auth_key_file']

            # Either write the new UAT into the key file, or read
            # the old one.
            if new_uat:
                print(f"Updating {filename} with new user access token.")
                with open(filename, 'w') as f:
                    print(new_uat, file=f)
                self.key = new_uat
            else:
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

    def _get_org_repos(self, url:str):
        """Get all repositories from a URL.

        If there's are next links, continue through those as well.
        
        Yields:
            Dicts containing repository information.
        
        """
        
        while url:
            response = self.session.get(url, params={'type': 'all'})
            response.raise_for_status()

            # First go through all the repos in this search result
            json = response.json()
            log.debug("Found %d repositories at %s", len(json), response.request.url)
            yield from json

            # Next, see if there's a "next" link on in the headers, in which case
            # there's another page of results to go through.
            url = None
            try:
                link = response.headers['link']
                mo = re.search(r'<([^>]+)>; rel="next"', link)
                if mo:
                    url = mo.group(1)
                    log.debug("Following next repo link to %s", url)
            except KeyError:
                pass

    def mirror_org_repos(self):
        """Query Github for all the repositories associated with this organization,
        and request they be mirrored.
        """
        
        tq = taskqueue()

        org = self.organization
        log.info('Getting %s repositories', org)
        url = f'https://api.github.com/orgs/{org}/repos'

        for repo in self._get_org_repos(url):
            fullname = repo['full_name']
            if repo['name'].casefold() in self.ignore:
                log.debug('Ignoring %s', fullname)
                continue
            
            ssh  = repo['ssh_url']
            local = git.local(None)

            log.info('Mirroring Github repository %s', fullname)
            if not self.dry_run:
                tq.append(local.mirror_repo, ssh, desc=f'Mirror {fullname}')
            
def github_uat() -> str:
    """Interactively get and return a new GitHub user authentication token.
    
    Uses the app device flow described at
    https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
    
    """

    session = requests.Session()
    params = {'client_id': APP_CLIENT_ID}
    r = session.post('https://github.com/login/device/code', params=params)

    qr = {
        k : v[0] if len(v) == 1 else v
            for (k, v) in parse_qs(r.text).items()
    }
    print("Follow link to", qr['verification_uri'], "to continue.")
    print("Provide user code:", qr['user_code'])

    # Keep polling to see whether the authorization is complete.
    interval = int(qr['interval'])
    params['device_code'] = qr['device_code']
    params['grant_type'] = 'urn:ietf:params:oauth:grant-type:device_code'
    while True:
        time.sleep(interval)
    
        r = session.post('https://github.com/login/oauth/access_token', params=params)
        if r.status_code != 200:
            raise ValueError(f"Bad HTTP response: {r.status_code}")

        d = parse_qs(r.text)
        if 'error' in d:
            error = d['error'][0]
            if error == 'slow_down':
                interval = int(d['interval'])
            elif error != 'authorization_pending':
                raise ValueError('Github reports error ' + error)
        else:
            return d['access_token'][0]