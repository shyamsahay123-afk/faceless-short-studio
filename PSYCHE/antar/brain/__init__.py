"""
ANTAR - the brain.

Everything that thinks: picking a topic, checking it is something people
actually search, writing the Hindi script, and auditing it with numbers.

Two rules run through all of it:

  1. The strongest model a key is entitled to must write every script.
     A weak model answering must never stop the engine reaching a strong one.

  2. No judgement is made by matching a string against another string.
     Searchability is checked against live search data. Script quality is
     checked by counting words, objects, positions and echoes.
"""

from . import audit, models, objects, providers, topics, writer  # noqa: F401

__all__ = ["audit", "models", "objects", "providers", "topics", "writer"]
