"""Glue between an extension/app and SKAI_ Memory (library skai_memory). Stdlib only.

    result, model = around_turn("sk_libre_writer", request, ask_turn)

Before the turn it looks in the shared memory for what other SKAI apps know about the user's
message and hands it to the model as one extra system message; after the turn it keeps a short
record of the exchange in this app's own sub-chat. Every failure here is swallowed: the memory
may be missing, locked or not writable for this user, and the app must work all the same."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)
_warned = set()


def _open(app):
    try:
        import skai_memory
        mem = skai_memory.Memory(app)
        return mem if mem.available() else None
    except Exception as exc:  # noqa: BLE001 - library missing, bad app name, ...
        if "open" not in _warned:
            _warned.add("open")
            log.info("SKAI_ Memory not used: %s", exc)
        return None


def recall_text(mem, query, k=3):
    """The memory block for the model ('' when nothing relevant)."""
    try:
        hits = mem.search(query, hops=1, limit=k)[:k]
    except Exception as exc:  # noqa: BLE001
        log.info("SKAI_ Memory search failed: %s", exc)
        return ""
    if not hits:
        return ""
    lines = []
    for h in hits:
        ext = f" Links: {', '.join(h['external'][:3])}" if h["external"] else ""
        lines.append(f"- [{h['title']}] ({h['path']}) {h['snippet']}{ext}")
    return "Shared SKAI memory (what other SKAI apps know; use it only when it helps):\n" + "\n".join(lines)


def remember_turn(mem, app, question, reply):
    try:
        mem.remember("chat " + time.strftime("%Y-%m-%d"), f"**Q:** {question[:600]}\n\n**A:** {reply[:900]}")
    except Exception as exc:  # noqa: BLE001
        if "write" not in _warned:  # one line in the log, not one per turn
            _warned.add("write")
            log.info("SKAI_ Memory not written: %s", exc)


def around_turn(app, request, ask):
    """Run ask(request) with the memory block added to the user message, then record the exchange."""
    mem = _open(app)
    question = str(request.get("user_message", ""))
    req = request
    if mem and question:
        ctx = recall_text(mem, question)
        if ctx:
            # Appended to the user's message, not put in the history: the apps trim the history to the last
            # user turn, which would silently drop a system message placed there.
            req = dict(request, user_message=question + "\n\n[" + ctx + "]")
    result, model = ask(req)
    if mem and question and isinstance(result, dict) and result.get("message"):
        remember_turn(mem, app, question, str(result["message"]))
    return result, model


open_memory = _open  # public name for apps that call recall_text / remember_turn themselves
