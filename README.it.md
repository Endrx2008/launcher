# launcher — Skorpion Launcher

Il launcher delle app di [Skorpion OS](https://github.com/Endrx2008/skorpion_os) per le edizioni **Lite**
(Debian + i3) e **Mantis** (Arch + Hyprland), con una chat **SKAI** di lato. Nella stessa cartella ci sono
la multicalcolatrice e la guida di Skorpion OS. *English: [README.md](README.md).*

## In Skorpion OS

È già installato in `~/.launcher/`: non c'è nulla da scaricare e non esiste una release.

| Tasti | Cosa fa |
|---|---|
| Alt + F1 | apre il launcher; premuto di nuovo, lo chiude |
| Alt + F3 | apre la guida di Skorpion OS |
| scrivi ovunque | cerca tra le app (Invio apre il primo risultato) |
| Ctrl + C | apre la multicalcolatrice (Ctrl + C nella calcolatrice torna indietro) |
| Ctrl + F | va alla casella di ricerca |
| Ctrl + T | tema chiaro / scuro (condiviso con gli altri strumenti Skorpion) |
| Ctrl + I | elenca le scorciatoie |
| Esc | torna alle categorie; dalla pagina iniziale chiude il launcher |

L'edizione Cinnamon ha un suo menu: launcher, multicalcolatrice e guida non ne fanno parte.

## File

| File | Cos'è |
|---|---|
| `launcher.py` | il launcher: categorie dai file `.desktop`, preferiti, menu di spegnimento, chat SKAI |
| `multicalculator_ui.py`, `safe_math.py` | la multicalcolatrice (le espressioni sono calcolate senza `eval`) |
| `guide/visualizer.py`, `guide/index_dark.html`, `guide/index_light.html` | la guida; mostra i tasti davvero assegnati in `~/.config/hypr/hyprland.lua` o `~/.config/i3/config` |
| `skcommon.py` | temi e riconoscimento del desktop, in comune con [skai_manager](https://github.com/Endrx2008/skai_manager) |
| `skai_memory.py`, `skai_memory_bridge.py` | copie della libreria SKAI_ Memory di [sk_notes](https://github.com/Endrx2008/sk_notes): non modificarle qui |

## SKAI

La chat parla con Ollama in locale (`http://localhost:11434`) e usa il modello installato con più parametri; la
risposta arriva man mano. Senza Ollama, o senza un modello, il pannello lo dice e propone **Retry**. I
modelli li installa la procedura guidata di SKAI e si gestiscono con SKAI Manager (Alt + F9).

Se SKAI_ Memory è installata (arriva con il pacchetto `sk-notes`) la chat prima cerca cosa sanno le altre
app SKAI, poi registra lo scambio nelle note del launcher. Senza, non cambia nulla.

## Avvio a mano

```sh
python3 ~/.launcher/launcher.py
```

Servono Python 3, PySide6 e `requests`, già presenti in Skorpion OS. Le impostazioni stanno in
`~/.config/pylauncher_settings/`.

## Licenza

GPL-3.0-or-later, vedi [LICENSE](LICENSE). © 2026 Enrico Miot (EndrX), fondatore e manutentore di Skorpion OS.
