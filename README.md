# launcher — Skorpion Launcher

The app launcher of [Skorpion OS](https://github.com/Endrx2008/skorpion_os) for the **Lite** (Debian + i3)
and **Mantis** (Arch + Hyprland) editions, with a **SKAI** chat on the side. The same folder holds the
multicalculator and the Skorpion OS guide. *Italiano: [README.it.md](README.it.md).*

## In Skorpion OS

Already installed in `~/.launcher/`: nothing to download, and there is no release.

| Keys | Does |
|---|---|
| Alt + F1 | opens the launcher; pressed again, closes it |
| Alt + F3 | opens the Skorpion OS guide |
| type anywhere | searches the apps (Enter opens the first result) |
| Ctrl + C | opens the multicalculator (Ctrl + C in the calculator goes back) |
| Ctrl + F | goes to the search box |
| Ctrl + T | light / dark theme (shared with the other Skorpion tools) |
| Ctrl + I | lists the shortcuts |
| Escape | back to the categories; on the home page it closes the launcher |

The Cinnamon edition has its own menu: launcher, multicalculator and guide are not part of it.

## Files

| File | What it is |
|---|---|
| `launcher.py` | the launcher: categories from the `.desktop` files, favourites, power menu, SKAI chat |
| `multicalculator_ui.py`, `safe_math.py` | the multicalculator (expressions are evaluated without `eval`) |
| `guide/visualizer.py`, `guide/index_dark.html`, `guide/index_light.html` | the guide; it shows the keys really bound in `~/.config/hypr/hyprland.lua` or `~/.config/i3/config` |
| `skcommon.py` | themes and desktop detection, shared with [skai_manager](https://github.com/Endrx2008/skai_manager) |
| `skai_memory.py`, `skai_memory_bridge.py` | copies of the SKAI_ Memory library from [sk_notes](https://github.com/Endrx2008/sk_notes): do not edit them here |

## SKAI

The chat talks to the local Ollama (`http://localhost:11434`) and uses the installed model with the most parameters; the
answer is streamed. Without Ollama, or without a model, the panel says so and offers **Retry**. Models
are installed by the SKAI setup wizard and managed with SKAI Manager (Alt + F9).

When SKAI_ Memory is installed (it comes with the `sk-notes` package) the chat first looks up what the
other SKAI apps know, then records the exchange in the launcher's own notes. Without it nothing changes.

## Run by hand

```sh
python3 ~/.launcher/launcher.py
```

Needs Python 3, PySide6 and `requests`, all part of Skorpion OS. Settings are kept in
`~/.config/pylauncher_settings/`.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). © 2026 Enrico Miot (EndrX), founder and maintainer of Skorpion OS.
