#!/usr/bin/env bash
# Print the Act 5 connection details as shell exports, straight from the azd deployment.
#   eval "$(bash scripts/act5_env.sh)"
# Exits non-zero with a message on stderr if the scheduler has not been provisioned yet.
set -eu
cd "$(dirname "$0")/.."

command -v azd >/dev/null 2>&1 || { echo "azd not found — see act5/README.md" >&2; exit 1; }
if ! VALUES=$(cd act5 && azd env get-values 2>/dev/null); then
  echo "no azd environment yet. Run:  cd act5 && azd provision" >&2; exit 1
fi

ENDPOINT=$(printf '%s\n' "$VALUES" | sed -n 's/^DTS_ENDPOINT="\(.*\)"$/\1/p')
[ -n "$ENDPOINT" ] || { echo "the azd environment has no DTS_ENDPOINT — run:  cd act5 && azd provision" >&2; exit 1; }
# durabletask needs a scheme; ARM returned one on 2026-09-07, but do not depend on that.
case "$ENDPOINT" in http*) ;; *) ENDPOINT="https://$ENDPOINT" ;; esac

printf 'export DTS_ENDPOINT=%s\n' "$ENDPOINT"
for k in DTS_TASKHUB DTS_TENANT DTS_DASHBOARD; do
  v=$(printf '%s\n' "$VALUES" | sed -n "s/^$k=\"\(.*\)\"$/\1/p")
  [ -n "$v" ] && printf 'export %s=%s\n' "$k" "$v"
done
# The subscription picks which az login answers (hosts/durable.py); the tenant alone does not.
v=$(printf '%s\n' "$VALUES" | sed -n 's/^AZURE_SUBSCRIPTION_ID="\(.*\)"$/\1/p')
[ -n "$v" ] && printf 'export DTS_SUBSCRIPTION=%s\n' "$v"
exit 0
