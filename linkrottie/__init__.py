from .version import __version__

def cmdline():
    from . import main
    main.main()
