#!/bin/bash
#
# Check portfolio-ai service status.
#
set -eo pipefail
exec bash "${SUMMITFLOW_BACKUP_ROOT:-$HOME/summitflow}/scripts/rebuild.sh" --status portfolio-ai "$@"
