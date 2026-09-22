# kill -9 Your Agent: every beat of the demo is one command.
#
#   make notebooks  the six marimo notebooks (the demo as given in the talk)
#   make act1       in-process run of the morning queue (kill during PreveriPriloge; restart => double odločba)
#   make act2       the same workflow on the Durable Task extension + DTS emulator (kill => resume from checkpoint)
#   make kill       SIGKILL the running worker right now ("referent je šel na malico")
#   make emulator   start the DTS emulator (dashboard: http://localhost:8082)
#   make reset      wipe demo state: queue counter, odločbe, ledger, DTS emulator instances
#   make act5       act2 against a Durable Task Scheduler in Azure (the worker stays here)
#
#   make act1 KILL_AT=PreveriPriloge:VL-2026-0050   auto-kill at the exact executor (deterministic kill timing)

.PHONY: setup fixtures test emulator emulator-down emulator-logs emulator-reset dashboard act1 act2 act3 act3-dvojna zig odobri zavrni kill reset warm ledger act5 act5-provision act5-dashboard act5-down act4-store act4-coach act4-apply act4-list act4-delete act4-revert act4-forget act4-snapshot act4-restore act4-clean notebooks devui

UV ?= uv

setup:                       ## uv sync + pre-pull the emulator image
	$(UV) sync
	docker pull mcr.microsoft.com/dts/dts-emulator:latest

fixtures:                    ## regenerate the fillable form PDFs
	$(UV) run python scripts/gen_obrazci.py

test:
	$(UV) run pytest -q

emulator:                    ## DTS emulator in Docker (gRPC 8080, dashboard 8082)
	docker compose up -d
	@echo "dashboard: http://localhost:8082"

emulator-down:
	docker compose down

emulator-logs:
	docker compose logs -f dts-emulator

emulator-reset:              ## wipe ALL emulator state (it lives in memory): container restart
	docker compose restart dts-emulator

dashboard:
	open http://localhost:8082

notebooks:                   ## the six marimo notebooks (pick one from the directory view)
	$(UV) run marimo edit notebooks --port 2718

devui:                       ## MAF's other generated graph view, lit up per executor during a run
	$(UV) run python scripts/devui.py

act1:                        ## Act 1: fragile baseline (in-process, non-idempotent odločba)
	$(UV) run act1

act2:                        ## Act 2: resurrection (durable worker against the emulator)
	$(UV) run act2

act3:                        ## Act 3: čakanje na žig (durable worker, parks until the phone answers)
	$(UV) run act3

act3-dvojna:                 ## Act 3 stretch: beehive permit, referent + vodja oddelka sign in parallel
	$(UV) run act3-dvojna

act4-store:                  ## Act 4: does the memory store exist? (read-only)
	$(UV) run act4 store

act4-coach:                  ## Act 4: process VL-2026-0051, then coach the referent once (awaits the extraction)
	$(UV) run act4 coach

act4-apply:                  ## Act 4: VL-2026-0052 (12-year-old document) with a fresh session
	$(UV) run act4 apply

act4-list:                   ## Act 4: the referent's memory items, verbatim
	$(UV) run act4 list

act4-delete:                 ## Act 4: delete one item live, ID=<memory_id>
	$(UV) run act4 delete $(ID)

act4-revert:                 ## Act 4: VL-2026-0053 after the rule is gone
	$(UV) run act4 revert

act4-forget:                 ## Act 4: the right to be forgotten, SCOPE=ID-TEST-005
	$(UV) run act4 forget $(SCOPE)

act4-snapshot:               ## Act 4: save the store contents, NAME=post-coaching
	$(UV) run act4 snapshot $(NAME)

act4-restore:                ## Act 4: clean + re-create from the snapshot, NAME=post-coaching
	$(UV) run act4 restore $(NAME)

act4-clean:                  ## Act 4: empty every demo scope (the store stays)
	$(UV) run act4 clean

zig:                         ## Act 3: the phone page on http://<laptop-ip>:8000 (same hotspot)
	$(UV) run zig

odobri:                      ## Act 3 without a phone: approve the first application waiting for the stamp
	$(UV) run python scripts/zig.py odobri

zavrni:                      ## Act 3 without a phone: reject it (the citizen then brings the missing attachment)
	$(UV) run python scripts/zig.py zavrni

kill:                        ## kill -9 whichever act worker is running
	$(UV) run python scripts/kill_during.py --now

reset:                       ## clean slate between runs
	$(UV) run python scripts/reset.py

warm:                        ## load the local model and check it on the demo applications
	$(UV) run python scripts/smoke_llm.py VL-2026-0047 VL-2026-0050

ledger:                      ## show fees charged so far (the double-charge proof)
	@cat out/takse.log 2>/dev/null || echo "(še nobena taksa)"
	@ls -1 out/odlocbe 2>/dev/null || true

# ---- the same act2, against a scheduler in Azure ----------------------------------------------
# The worker stays on this laptop. Only the scheduler moves, so kill -9 still lands on a local process
# and the state it was holding is provably somewhere else. Connection details come from act5/ (azd).

act5:                        ## act2 against the cloud scheduler (ACT=act3 for the pause)
	bash scripts/act5.sh $(ACT)

act5-provision:              ## create the scheduler + task hub in Azure (see act5/README.md)
	cd act5 && azd provision

act5-dashboard:              ## open the scheduler's blade in the portal
	@cd act5 && open "$$(azd env get-value DTS_DASHBOARD)"

act5-down:                   ## remove the scheduler's resource group again
	cd act5 && azd down --purge
