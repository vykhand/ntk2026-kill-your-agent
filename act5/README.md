# The same demo, against a scheduler in Azure

`03_durable` and `make act2` run against the DTS emulator in Docker. `06_azure` and `make act5` run
**the same `act2`** against a real Durable Task Scheduler in Azure. Only the scheduler moves. The worker
still runs on your laptop.

That split is the demo. `kill -9` lands on a local process exactly as before, but the state that process
was holding is now provably somewhere else. Kill the worker and the orchestration still sits in the
portal, mid-flight, on a machine you are not touching.

```
make act5-provision     # once: the scheduler and its task hub
make act5               # act2, against Azure
make act5 ACT=act3      # the pause, parked in Azure
make act5-dashboard     # the scheduler's blade in the portal
make act5-down          # remove it all again
```

## What gets created

The template creates two resources and one role assignment, in their own resource group:

| Resource | Why |
|---|---|
| `Microsoft.DurableTask/schedulers` (Consumption) | pay-per-action; one application is about nine actions |
| `schedulers/taskHubs` named `lipica` | not `default`, so a stray emulator config cannot point here by accident |
| `Durable Task Data Contributor` on the scheduler | the worker and the client run as the signed-in user |

`ipAllowlist` is open (`0.0.0.0/0`) because a conference network's egress address is not known in
advance. Tighten it for anything but a demo.

## First run

Use a subscription you can throw away resources in:

```bash
az account set --subscription <subscription-id>
az provider register --namespace Microsoft.DurableTask --wait

cd act5
azd env new act5 --subscription <subscription-id> --location swedencentral
azd env set AZURE_PRINCIPAL_ID "$(az ad signed-in-user show --query id -o tsv)"
azd provision
```

`azd provision` writes `DTS_ENDPOINT`, `DTS_TASKHUB`, `DTS_TENANT` and `DTS_DASHBOARD` back into the azd
environment. `scripts/act5.sh` reads them from there, so nothing goes into `.env` and nothing is
committed. The worker pins its credential to `DTS_TENANT`, so it keeps working when your `az` CLI holds
several logins.

## Why not an Azure Functions host

That was the first attempt, and it does not work. The Functions runtime rejects non-ASCII function names,
so `dafx-vloga-ČakanjeNaŽig`, `-IzdajOdločbo`, `-ŽigReferenta` and `-ŽigVodje` never load, and an
application stalls after two steps. The diacritics are the joke, so they stay. The Durable Task Scheduler
has no such restriction.
