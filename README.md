# 🐍 Python Application Launcher

Un moderno **Application Launcher** scritto in **Python** con **PyQt5**, pensato per offrire un'interfaccia elegante, dark mode, gestione delle app preferite, e organizzazione per categorie. Supporta icone da temi di sistema e salvataggio delle preferenze utente.

---

## ✨ Caratteristiche

- ✔️ Interfaccia grafica responsive con PyQt5  
- 🌙 Modalità chiara e scura con toggle integrato  
- 📁 Categorie personalizzabili e ordinabili tramite drag-and-drop  
- ⭐ Aggiunta e visualizzazione rapida delle app preferite  
- 🔍 Scansione automatica delle applicazioni `.desktop`  
- 💾 Salvataggio delle preferenze utente in `~/.config/pylauncher_settings/`  

---

## 📦 Requisiti

- Python 3.7 o superiore  
- PyQt5  

### Installazione delle dipendenze

**Su Debian/Ubuntu:**

```bash
sudo apt install python3-pyqt5
```

**Oppure con pip:**

```bash
pip install PyQt5
```

---

## 🚀 Avvio

Clona il repository ed esegui il launcher:

```bash
git clone https://github.com/tuo-username/pylauncher2.git
cd pylauncher2
python3 launcher.py
```

> Assicurati che il percorso agli `.desktop` file sia corretto:  
> `/usr/share/applications`, `~/.local/share/applications`, ecc.

---

## 🎨 Personalizzazione

Per usare un tema di icone diverso, modifica la seguente variabile nel file `launcher.py`:

```python
ICON_DIR = "/usr/share/icons/Sours-Full-Color/apps/scalable"
```

Oppure punta ad un altro percorso contenente le icone delle applicazioni.

---

## 🗃️ Configurazioni salvate

Le configurazioni utente vengono salvate automaticamente in:

```
~/.config/pylauncher_settings/
├── preferred_apps.json       # App preferite
└── categories_order.json     # Ordine delle categorie personalizzato
```

Puoi modificarli manualmente o eliminarli per ripristinare le impostazioni iniziali.

---

## ⚙️ Funzionamento interno

- Scansione automatica dei file `.desktop` nei percorsi standard  
- Organizzazione per categoria tramite il campo `Categories=`  
- Icone supportate: assolute (`/path/to/icon.png`) o da tema (`app-icon-name`)  
- Gestione app preferite tramite click destro → “Aggiungi ai preferiti”  
- Toggle tra light e dark mode dinamico  

---

## 🔧 TODO / Idee Future

- [x] Ricerca istantanea tra le applicazioni  
- [x] Scorciatoie da tastiera personalizzabili

---

## 📄 Licenza

Distribuito sotto licenza **GPL**.  
Vedi il file `LICENSE` per i dettagli.

---

## 🤝 Contribuire

Pull request e suggerimenti sono benvenuti!

1. Fai un fork del progetto  
2. Crea un branch (`git checkout -b nuova-feature`)  
3. Effettua il commit (`git commit -am 'Aggiunta nuova feature'`)  
4. Push su GitHub (`git push origin nuova-feature`)  
5. Crea una pull request 🎉  

---

## 👤 Autore

Sviluppato da **Enrico** 🧠  
Sistema operativo: Debian 12 con KDE  
GPU: RTX 4070 – CPU: Ryzen 5  
Window Manager alternativo: i3  

---

## 📬 Contatti

Per feedback o suggerimenti: apri un’issue o scrivi un commento nel repository.

## 👥 Collaboratori
- maraMAU (per aver corretto un bug nella UI della calcolatrice)
