#!/usr/bin/env bash
# Act 5: the same act, against the Durable Task Scheduler in Azure instead of the emulator.
#
#   scripts/act5.sh            # act2: the kill and the resurrection, on a cloud scheduler
#   scripts/act5.sh act3       # the pause, parked in Azure
#
# The worker still runs here. That is the point: kill -9 lands on a local process, and the state it was
# holding is demonstrably not on this laptop — the portal shows it while the worker is dead.
# Connection details come from the azd deployment (act5/), so there is nothing to keep in .env.
set -eu
cd "$(dirname "$0")/.."
eval "$(bash scripts/act5_env.sh)"
echo "razporejevalnik: $DTS_ENDPOINT  ·  taskhub ${DTS_TASKHUB:-default}"
exec uv run "${1:-act2}"
