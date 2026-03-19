#!/bin/bash
#
# Restart portfolio-ai services (full rebuild).
#
set -eo pipefail
exec bash "${SUMMITFLOW_BACKUP_ROOT:-$HOME/summitflow}/scripts/rebuild.sh" portfolio-ai "$@"
