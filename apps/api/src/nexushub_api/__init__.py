"""nexushub-api — the NexusHub API gateway.

A FastAPI layer in front of the nexusagent runtime: agents, chat sessions,
runs and API keys, persisted to SQL and streamed over SSE.

The gateway owns persistence and transport; the engine owns agent
behaviour. Everything the gateway knows about running agents comes from the
``nexusagent`` public API — the runtime is never re-implemented here.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
