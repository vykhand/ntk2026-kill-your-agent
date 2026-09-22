"""scheduler.py: `pending_executors` degrades to an empty set on a transient gRPC hiccup, the same way
`zadnja_aktivnost`/`stanja_dag` already guard their own history fetch. No real emulator, no model."""

from lipica.stage import scheduler


class _RaisingClient:
    def get_pending_hitl_requests(self, iid):
        raise RuntimeError("emulator unreachable")


class _WorkingClient:
    def __init__(self, pending):
        self._pending = pending

    def get_pending_hitl_requests(self, iid):
        return self._pending


def test_pending_executors_is_empty_not_raised_on_a_client_error():
    assert scheduler.pending_executors(_RaisingClient(), "VL-2026-0048") == set()


def test_pending_executors_reads_source_executor_id_when_the_client_works():
    client = _WorkingClient([{"source_executor_id": "ČakanjeNaŽig"}, {"other": "x"}])
    assert scheduler.pending_executors(client, "VL-2026-0048") == {"ČakanjeNaŽig"}


def test_stanja_dag_survives_a_client_that_cannot_reach_anything():
    class _DeadRaw:
        def get_orchestration_history(self, iid):
            raise RuntimeError("emulator unreachable")

    assert scheduler.stanja_dag(_RaisingClient(), _DeadRaw(), "VL-2026-0048") == {}
