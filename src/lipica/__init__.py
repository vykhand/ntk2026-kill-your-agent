"""Upravna enota Zgornja Lipica: demo workflow for the NTK 2026 talk "kill -9 za AI agente"."""

import os

# The gRPC C core logs "Other threads are currently calling into gRPC, skipping fork() handlers"
# to stderr when the auto-kill helper forks. Harmless, but it lands in the middle of the stage
# output. The knob is read once at core init, so it has to be set before anything imports grpc.
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
