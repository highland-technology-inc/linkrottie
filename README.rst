===========
Link Rottie
===========

A very good dog who fetches! Because "the cloud" is just someone else's
computer.

Link Rottie, (Link Rottweiler if you're feeling formal) takes your GitHub repos
and backs them up locally.  It takes your git submodules in the cloud, and backs
them up locally.  It takes their submodules, and their submodules, and their
submodules, and backs them up locally.  It takes anything for which the only
authoritative version seems to live somewhere you don't own, and it backs it up
locally on something you do.

Configuration
=============
If you only had a repo or two to back up you'd just do it manually, so the
assumption of Link Rottie is that you've got a bunch of them.  That being
the case, a whole mess of command-line arguments to configure the backup
gets out of hand quickly.  Instead, Link Rottie uses configuration file
`linkrottie.toml` assumed to be in the execution directory.  TOML is
an increasingly popular configuration language, see https://toml.io/en/
for details.

Rob Gaddi, Highland Technology, 29-May-2025