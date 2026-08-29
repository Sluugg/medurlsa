#!/bin/sh
# Runs as root (see Dockerfile — no USER directive before this script runs).
# Docker auto-creates a missing bind-mount source directory on the host as
# root:root, which the unprivileged medurlsa user then can't write into — so
# every start, fix ownership on the mounted volumes before dropping to
# medurlsa and exec'ing the real command. Failures here are non-fatal (e.g.
# read-only filesystem in some setups); the app still starts either way.
set -e

# Belt-and-suspenders: both paths should already exist (image build-time
# mkdir, or Docker auto-creating a missing bind-mount source) by this point,
# but don't depend on that — create them here too so this script is correct
# on its own, not just in combination with those other two mechanisms.
mkdir -p /app/data /app/backgrounds /app/branding
chown -R medurlsa:medurlsa /app/data /app/backgrounds /app/branding 2>/dev/null || true

exec gosu medurlsa "$@"
