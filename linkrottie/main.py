import sys
import tomllib
import argparse
from pathlib import Path

from . import git, version
from .github import Github, github_uat
from .taskqueue import taskqueue

import logging
log = logging.getLogger(__name__)

def main(argv = None):
    
    parser = argparse.ArgumentParser(
        prog='linkrottie',
        description='Git repo backup automator'
    )
    parser.add_argument('--config', help='Configuration file, default is to search ./linkrottie.toml then $HOME/.config/linkrottie/linkrottie.toml')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument('--authorize-github', action='store_true', help='Create a GitHub user authorization key.')
    parser.add_argument('--version', action='version', version=f"%(prog)s {version.__version__}")
    argns = parser.parse_args(argv)
    
    # Configure logging
    rootlogger = logging.getLogger('')
    rootlogger.setLevel(logging.DEBUG)
    if argns.verbose:
        filelog = logging.FileHandler('linkrottie.log')
        filelog.setFormatter(
            logging.Formatter('%(levelname)-8s:%(asctime)-24s:%(name)-12s: %(message)s')
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
    if argns.config:
        configfiles = [Path(argns.config)]
    else:
        configfiles = [
            Path('linkrottie.toml'),
            Path.home() / '.config/linkrottie/linkrottie.toml'
        ]

    for cfg in configfiles:    
        log.debug('Trying configuration file %s', cfg)
        try:
            with cfg.open('rb') as f:
                config_data = tomllib.load(f)
            log.info('Configuration data: %s', cfg)
            break
        except FileNotFoundError:
            pass
    else:
        print("unable to find configuration file linkrottie.toml", file=sys.stderr)
        return 2
    
    tq = taskqueue()
    local = git.local(config_data['local'])
    
    if argns.authorize_github:
        print('Contacting GitHub for user authorization token')
        new_uat = github_uat()
    else:
        new_uat = None

    # Handle Github
    try:
        github_gather = config_data['gather']['github']
        log.debug('Configuring gather.github')
        for org, config in github_gather.items():
            gh = Github(org, config, new_uat=new_uat)
            tq.append(gh.mirror_org_repos)
    except KeyError:
        pass
        
    # Handle explicit remotes
    remotes = config_data['gather'].get('remotes', [])
    for url in remotes:
        tq.append(local.mirror_repo, url)
    
    # Run the taskqueue
    tq.runall()

    return 0

if __name__ == '__main__':
    sys.exit(main())
