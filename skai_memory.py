"""skai_memory - the shared Markdown memory of SKAI (single file, standard library only).

Import it from anything that runs Python 3: scripts, LibreOffice .oxt, sk_notes, SKAI itself.
(The JavaScript twin for .xpi add-ons is skai_memory.js: same methods, same results.)

    from skai_memory import Memory
    m = Memory("sk_mail")                         # identifies the app; /var/lib/skai/SKAI_ Memory (or $SKAI_MEMORY_DIR)
    for hit in m.search("meeting with Anna"):     # reads everything, every app's notes
        print(hit["path"], hit["score"], hit["snippet"])
    m.remember("inbox", "Anna asked to move the meeting", links=["[[plugins/sk_office]]"])   # only plugins/sk_mail/**

The vault is a folder of Markdown notes that link to each other ([[wikilinks]] between notes,
ordinary links to files, URLs and skai://app/<name>). search() finds the best notes and then
hops along the links, so an answer found in one app's chat can pull in another app's context.
Reading is plain file reading (everyone may). Writing goes through the root-owned helper
``skai-memory-write`` (see README.md), never directly, and the helper lets an app change only
its own notes: ``plugins/<app>.md`` (created on first contact from a template) and ``plugins/<app>/``.
Other apps' notes are read-only to it; it links to them instead.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

__all__ = ["Memory", "MemoryError_", "DEFAULT_DIR", "WRITE_HELPER"]
__version__ = "2.0.0"

DEFAULT_DIR = "/var/lib/skai/SKAI_ Memory"
WRITE_HELPER = "/usr/lib/skai/skai-memory-write"
MARKER = ".skai-memory"

_WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_MDLINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)[^)]*\)")
_FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
_HEAD = re.compile(r"^#{1,6}\s+(.+)$", re.M)
_WORD = re.compile(r"\w{2,}", re.U)
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
# Words that say nothing about where the answer is: they never place the snippet (unless nothing else matches).
_STOP = frozenset("""
a an and are as at be but by can could did do does for from had has have how i if in into is it its me my no not
of on or our please say said she so that the their them then there these they this to us was we were what when
where which who why will with would you your about also just tell know remember
al alla alle allo ai agli anche che chi ci come con cosa da dal dalla dei del della delle di dove e ed gli ha hai
ho il in io la le lo ma mi mio mia ne nei nel nella no non o per perché più quale quando quello questa questo se
si sono su sul sulla tu un una uno va vi sai dimmi ricordi
""".split())


class MemoryError_(Exception):
    """Raised for unreadable vaults and refused writes."""


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep:
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[m.end():]


def edge_style(a: dict, b: dict) -> str:
    """'solid' | 'dashed' | 'dotted' for a link from note a to note b (see Memory.graph)."""
    if not a["app"] or not b["app"]:
        return "solid"                                   # SKAI.md, system.md ... are part of the tree
    if a["app"] != b["app"]:
        return "dotted"
    return "solid" if "app" in (a["kind"], b["kind"]) else "dashed"


def _hit(word: str, term: str) -> bool:
    """Whole-word match; a word may also extend a term of 4+ letters (meeting -> meetings)."""
    return word == term or (len(term) >= 4 and word.startswith(term))


def snippet(text: str, weights: dict[str, float], width: int = 240) -> str:
    """The part of ``text`` that best covers the query: the window holding the most (rarest) query words.

    weights  {query word: importance}, e.g. its idf; stopwords count only when nothing else matches.
    Words are matched whole (no substrings); on a tie the later window wins, since notes grow downwards
    and the newest entry of a daily chat is at the bottom."""
    terms = {t: w for t, w in weights.items() if t not in _STOP} or dict(weights)
    hits = []
    for m in _WORD.finditer(text):
        word = m.group().lower()
        for t in terms:
            if _hit(word, t):
                hits.append((m.start(), t))
                break
    pos = 0
    if hits:
        best = -1.0
        for i, (start, _) in enumerate(hits):
            seen = {t for p, t in hits[i:] if p < start + width - 40}
            score = sum(terms[t] for t in seen)
            if score >= best:
                best, pos = score, start
    return text[max(0, pos - 40): pos + width].replace("\n", " ").strip()


def slug(text: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", text.strip().lower(), flags=re.U).strip("-")
    return s[:60] or "note"


class Memory:
    def __init__(self, app: str | None = None, root: str | os.PathLike | None = None):
        """app: who is using the library (a name like "sk_mail"); needed to write, optional to read."""
        if app is not None and not _NAME.match(app):
            raise MemoryError_(f"app name must match [a-z0-9][a-z0-9_-]{{1,39}}: {app!r}")
        self.app = app
        self.root = Path(root or os.environ.get("SKAI_MEMORY_DIR") or DEFAULT_DIR)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._registered = False

    # ------------------------------------------------------------------ reading
    def available(self) -> bool:
        return self.root.is_dir()

    def notes(self) -> dict[str, dict]:
        """All notes: {rel path: {path,title,app,kind,text,links,targets,tokens,headings}}."""
        if not self.available():
            raise MemoryError_(f"memory vault not found: {self.root}")
        out, seen = {}, set()
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if not f.endswith(".md"):
                    continue
                p = Path(dirpath) / f
                rel = p.relative_to(self.root).as_posix()
                seen.add(rel)
                try:
                    mt = p.stat().st_mtime
                    c = self._cache.get(rel)
                    if not c or c[0] != mt:
                        c = (mt, self._parse(rel, p.read_text(encoding="utf-8", errors="replace")))
                        self._cache[rel] = c
                    out[rel] = c[1]
                except OSError:
                    continue
        for gone in set(self._cache) - seen:
            del self._cache[gone]
        self._resolve(out)
        return out

    @staticmethod
    def _parse(rel: str, text: str) -> dict:
        meta, body = _frontmatter(text)
        heads = _HEAD.findall(body)
        title = meta.get("title") or (heads[0] if heads else Path(rel).stem)
        parts = rel.split("/")
        plug = parts[0] == "plugins"
        app = (parts[1][:-3] if len(parts) == 2 else parts[1]) if plug and len(parts) > 1 else ""
        kind = "app" if plug and len(parts) == 2 else "chat" if plug else parts[0] if len(parts) > 1 else "hub"
        wiki = [w.strip() for w in _WIKI.findall(body)]
        ext = [u for u in _MDLINK.findall(body) if re.match(r"^(https?://|file://|skai://|/)", u)]
        return {"path": rel, "title": title, "app": app, "kind": kind, "text": body, "wiki": wiki, "external": ext,
                "headings": [h.lower() for h in heads], "tokens": _tokens(body), "title_tokens": set(_tokens(title + " " + Path(rel).stem))}

    @staticmethod
    def _resolve(notes: dict[str, dict]) -> None:
        by_name: dict[str, str] = {}
        for rel in sorted(notes):
            by_name.setdefault(Path(rel).stem.lower(), rel)
            by_name.setdefault(rel[:-3].lower(), rel)
        for n in notes.values():
            n["out"] = sorted({by_name[w.lower().removesuffix(".md")] for w in n["wiki"] if w.lower().removesuffix(".md") in by_name} - {n["path"]})
            n["back"] = []
        for n in notes.values():
            for t in n["out"]:
                notes[t]["back"].append(n["path"])

    def read(self, path: str) -> str:
        return self._abs(path).read_text(encoding="utf-8", errors="replace")

    def links(self, path: str) -> dict:
        """Where a note points: other notes, backlinks, and external targets (files, URLs, apps)."""
        n = self.notes()[self._rel(path)]
        return {"notes": n["out"], "backlinks": sorted(n["back"]), "external": n["external"]}

    def graph(self) -> dict:
        """Nodes and edges, ready to draw. Every edge has a ``style``:
        solid   the tree: SKAI → app note → its sub-chats (and the way back up)
        dashed  between two notes of the SAME app's memory
        dotted  between notes of DIFFERENT apps"""
        notes = self.notes()
        edges = []
        for n in notes.values():
            for t in n["out"]:
                edges.append({"from": n["path"], "to": t, "style": edge_style(n, notes[t])})
        return {"nodes": [{"id": n["path"], "title": n["title"], "app": n["app"], "kind": n["kind"]} for n in notes.values()], "edges": edges}

    def search(self, query: str, app: str | None = None, hops: int = 1, limit: int = 8, only_app: bool = False) -> list[dict]:
        app = app or self.app
        """Best notes for ``query`` plus the notes they link to (``hops`` links away).

        app       the caller: its own notes are preferred (its sub-chats), others still reachable.
        only_app  restrict the first matches to that app (links may still leave it).
        Every hit: path, title, app, kind, score, snippet, via (the note it was reached from, or None),
        external (links to files / URLs / apps found in that note)."""
        notes = self.notes()
        q = _tokens(query)
        if not q or not notes:
            return []
        n_docs = len(notes)
        df = {t: sum(1 for n in notes.values() if t in n["title_tokens"] or t in n["tokens"]) for t in set(q)}
        scores: dict[str, float] = {}
        for rel, n in notes.items():
            if only_app and app and n["app"] != app and n["kind"] not in ("hub", "app"):
                continue
            s = 0.0
            for t in q:
                idf = math.log(1 + n_docs / (1 + df[t]))
                tf = n["tokens"].count(t)
                s += idf * ((3 if t in n["title_tokens"] else 0) + (2 if any(t in h for h in n["headings"]) else 0) + tf / (tf + 1.2))
            if s > 0:
                scores[rel] = s * (1.5 if app and n["app"] == app else 1.0)
        seeds = sorted(scores, key=scores.get, reverse=True)[:limit]
        found = {r: (scores[r], None) for r in seeds}
        frontier = list(seeds)
        for h in range(1, max(0, hops) + 1):
            nxt = []
            for r in frontier:
                for t in notes[r]["out"] + notes[r]["back"]:
                    sc = found[r][0] * (0.5 ** h)
                    if t not in found or found[t][0] < sc:
                        if t not in found:
                            nxt.append(t)
                        found[t] = (sc, r)
            frontier = nxt
        ranked = sorted(found, key=lambda r: found[r][0], reverse=True)[: limit * 2]
        weights = {t: math.log(1 + n_docs / (1 + df[t])) for t in set(q)}
        return [{"path": r, "title": notes[r]["title"], "app": notes[r]["app"], "kind": notes[r]["kind"],
                 "score": round(found[r][0], 3), "via": found[r][1], "snippet": snippet(notes[r]["text"], weights),
                 "external": notes[r]["external"]} for r in ranked]

    # ------------------------------------------------------------------ writing
    def register(self) -> str:
        """Introduce this app: creates plugins/<app>.md from a template (once) and links it from SKAI.md."""
        self._need_app()
        self._send({"op": "register", "path": f"plugins/{self.app}.md", "caller": self.app})
        self._registered = True
        return f"plugins/{self.app}.md"

    def write(self, path: str, text: str) -> None:
        self._own(path)
        self._send({"op": "write", "path": self._rel(path), "text": text, "caller": self.app})

    def append(self, path: str, text: str) -> None:
        self._own(path)
        self._send({"op": "append", "path": self._rel(path), "text": text, "caller": self.app})

    def remember(self, chat: str, text: str, links: list[str] | None = None) -> str:
        """Add ``text`` to this app's sub-chat ``chat`` (plugins/<app>/<chat>.md, created on first use and
        listed in the app's note). ``links``: "[[other-app]]", URLs, file paths, skai://app/x.
        Returns the sub-chat's path."""
        self._need_app()
        if not self._registered and not self._exists(f"plugins/{self.app}.md"):
            self.register()
        self._registered = True
        chat_s = slug(chat)
        path = f"plugins/{self.app}/{chat_s}.md"
        if not self._exists(path):
            self.write(path, f"---\napp: {self.app}\nkind: chat\ntitle: {chat}\n---\n# {chat}\n\nSub-chat of [[plugins/{self.app}]].\n")
            self.append(f"plugins/{self.app}.md", f"- [[plugins/{self.app}/{chat_s}]]\n")
        extra = "".join(f"- {self._link(l)}\n" for l in (links or []))
        stamp = __import__("time").strftime("%Y-%m-%d %H:%M")
        self.append(path, f"\n## {stamp}\n\n{text.strip()}\n" + (f"\n{extra}" if extra else ""))
        return path

    def link(self, other_app: str, why: str = "", note: str | None = None) -> None:
        """Leave a link from this app's note to another app's memory (its note, or one of its sub-chats)."""
        self._need_app()
        if not self._registered and not self._exists(f"plugins/{self.app}.md"):
            self.register()
        target = f"plugins/{other_app}/{slug(note)}" if note else f"plugins/{other_app}"
        self.append(f"plugins/{self.app}.md", f"- [[{target}]]{(' — ' + why) if why else ''}\n")

    def _need_app(self) -> None:
        if not self.app:
            raise MemoryError_("identify the app first: Memory('your-app')")

    def _own(self, path: str) -> None:
        self._need_app()
        p = self._rel(path)
        if not (p == f"plugins/{self.app}.md" or p.startswith(f"plugins/{self.app}/")):
            raise MemoryError_(f"{self.app} may only change its own notes (plugins/{self.app}.md, plugins/{self.app}/)")

    @staticmethod
    def _link(l: str) -> str:
        if l.startswith("[[") or l.startswith("["):
            return l
        return f"[{l}]({l if '://' in l else 'file://' + l})"

    def _exists(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def _rel(self, path: str) -> str:
        p = path.replace("\\", "/").lstrip("/")
        if any(x in ("..", "") for x in p.split("/")) or not p.endswith(".md"):
            raise MemoryError_(f"not a note path: {path!r}")
        return p

    def _abs(self, path: str) -> Path:
        return self.root / self._rel(path)

    def _send(self, req: dict) -> None:
        req["dir"] = str(self.root)
        env = {**os.environ}
        if os.environ.get("SKAI_MEMORY_NO_SUDO") == "1":  # tests / single-user dev setups
            helper = [sys.executable, str(Path(__file__).resolve().with_name("skai-memory-write")), "--direct"]
        else:
            helper = ["sudo", "-n", WRITE_HELPER, "--skai"]
        r = subprocess.run(helper, input=json.dumps(req), capture_output=True, text=True, timeout=30, env=env)
        if r.returncode != 0:
            raise MemoryError_((r.stderr or r.stdout or "write refused").strip())


def main(argv: list[str] | None = None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    m = Memory(os.environ.get("SKAI_APP") or None)
    try:
        if a[:1] == ["search"] and len(a) > 1:
            app = a[a.index("--app") + 1] if "--app" in a else None
            q = " ".join(x for i, x in enumerate(a[1:], 1) if x != "--app" and a[i - 1] != "--app")
            print(json.dumps(m.search(q, app=app), indent=2, ensure_ascii=False))
        elif a[:1] == ["graph"]:
            print(json.dumps(m.graph(), indent=2, ensure_ascii=False))
        elif a[:1] == ["read"] and len(a) == 2:
            print(m.read(a[1]))
        elif a[:1] == ["remember"] and len(a) >= 3:
            print(m.remember(a[1], " ".join(a[2:])))
        else:
            print("usage: skai_memory.py search <words> [--app NAME] | graph | read <path.md> | remember <chat> <text>   (set SKAI_APP=<your-app>)")
            return 2
    except MemoryError_ as e:
        print(f"skai_memory: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
