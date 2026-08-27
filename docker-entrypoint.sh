#!/bin/sh
# Runs as root (see Dockerfile — no USER directive before this script runs).
# Docker auto-creates a missing bind-mount source directory on the host as
# root:root, which the unprivileged webshare user then can't write into — so
# every start, fix ownership on the mounted volumes before dropping to
# webshare and exec'ing the real command. Failures here are non-fatal (e.g.
# read-only filesystem in some setups); the app still starts either way.
set -e

chown -R webshare:webshare /app/data /app/backgrounds 2>/dev/null || true

exec gosu webshare "$@"
