#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'Floating-branch updates are disabled in this fork.' 'Use: sudo python3 /repo/install_reviewed.py --device host|superbird --commit FULL_COMMIT_SHA' >&2
exit 1
