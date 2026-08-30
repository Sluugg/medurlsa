#!/usr/bin/env python3
"""
Runs as root (see Dockerfile — no USER directive before this script runs).
Docker auto-creates a missing bind-mount source directory on the host as
root:root, which the unprivileged app user then can't write into — so every
start, fix ownership on the mounted volumes, then drop to that user and
exec the real command.

Python-native equivalent of the previous shell + gosu entrypoint: os.setuid
et al. do the same privilege drop gosu did, without needing a separate
apt-get-installed binary (and its build-time network dependency) at all.
"""

import os
import pwd
import sys

_USER = "medurlsa"
_MANAGED_DIRS = ("/app/data", "/app/backgrounds", "/app/branding")


def _chown_tree(path: str, uid: int, gid: int) -> None:
    try:
        for root, dirs, files in os.walk(path):
            os.chown(root, uid, gid)
            for name in dirs:
                os.chown(os.path.join(root, name), uid, gid)
            for name in files:
                os.chown(os.path.join(root, name), uid, gid)
    except OSError:
        pass  # non-fatal, e.g. a read-only filesystem in some setups


def main() -> None:
    for path in _MANAGED_DIRS:
        os.makedirs(path, exist_ok=True)

    pw = pwd.getpwnam(_USER)
    uid, gid = pw.pw_uid, pw.pw_gid

    for path in _MANAGED_DIRS:
        _chown_tree(path, uid, gid)

    # Drop privileges: supplementary groups first, then gid, then uid — this
    # order matters, since setuid() before setgid() would fail once no
    # longer root.
    os.setgroups([gid])
    os.setgid(gid)
    os.setuid(uid)

    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
