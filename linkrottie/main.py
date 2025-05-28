import sys
import tomllib
import argparse
from pathlib import Path

from . import git
from .github import Github
from .taskqueue import taskqueue

import logging
log = logging.getLogger(__name__)

def main(argv = None):
    
    parser = argparse.ArgumentParser(
        prog='linkrottie',
        description='Git repo backup automator'
    )
    parser.add_argument('--config', default='linkrottie.toml')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    argns = parser.parse_args(argv)
    
    # Configure logging
    rootlogger = logging.getLogger('')
    rootlogger.setLevel(logging.DEBUG)
    if argns.verbose:
        filelog = logging.FileHandler('linkrottie.log')
        filelog.setFormatter(
            logging.Formatter('%(levelname)-8s:%(asctime)-24s:%(name)s: %(message)s')
        )

        level = logging.INFO if argns.verbose == 1 else logging.DEBUG
        filelog.setLevel(level)

        rootlogger.addHandler(filelog)
    
    consolelog = logging.StreamHandler()
    consolelog.setFormatter(
        logging.Formatter('%(levelname)s:%(name)s: %(message)s')
    )
    consolelog.setLevel(logging.INFO if argns.verbose else logging.WARNING)
    rootlogger.addHandler(consolelog)
    
    # Read the options file
    log.debug('Parsing configuration file %s', argns.config)
    with open(argns.config, 'rb') as f:
        config_data = tomllib.load(f)
    
    tq = taskqueue()
    local = git.local(config_data['local'])
    
    # Handle Github
    try:
        github_gather = config_data['gather']['github']
        log.debug('Configuring gather.github')
        for org, config in github_gather.items():
            gh = Github(org, config)
            tq.append(gh.mirror_org_repos)
    except KeyError:
        pass
        
    # Handle explicit remotes
    remotes = config_data['gather'].get('remotes', [])
    for url in remotes:
        tq.append(local.mirror_repo, url)
    
    # Run the taskqueue
    tq.runall()

if __name__ == '__main__':
    main()
