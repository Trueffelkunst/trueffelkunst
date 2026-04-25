#!/usr/bin/env python3
"""
Trüffelkunst Monitoring — Prüft monatlich auf Änderungen bei Sammlungskünstlern.

Quellen (kostenlos, kein API-Key nötig):
- griffelkunst.de: neue Editionen, Technik-Updates
- DuckDuckGo: Galeriewechsel, Ausstellungen, Preise

Ergebnis: updates.json → wird von der Streamlit-App gelesen und als Banner angezeigt.
"""

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, date
import ssl
import time

DATA_DIR = Path(__file__).parent
DATA_FILE = DATA_DIR / "griffelkunst_data.json"
UPDATES_FILE = DATA_DIR / "daten" / "monitoring_updates.json"
HISTORY_FILE = DATA_DIR / "daten" / "monitoring_history.json"

# SSL-Kontext für macOS
ctx = ssl.create_default_context()

BLUE_CHIP_GALLERIES = [
    "Gagosian", "Hauser & Wirth", "Hauser&Wirth", "Pace Gallery", "Pace,",
    "David Zwirner", "Zwirner", "Marian Goodman", "Sprüth Magers",
    "Lisson", "Thaddaeus Ropac", "Ropac", "Gladstone", "White Cube",
    "neugerriemschneider", "Esther Schipper", "Buchholz", "Matthew Marks",
    "Paula Cooper", "Max Hetzler", "König Galerie", "Perrotin",
    "Petzel", "Eigen+Art", "Tanya Bonakdar"
]

IMPORTANT_EVENTS = [
    "documenta", "Documenta", "Biennale", "biennale", "Venedig", "Venice",
    "Retrospektive", "retrospective", "Retrospective",
    "Museum Solo", "Einzelausstellung", "solo exhibition",
    "Turner Prize", "Wolfgang-Hahn", "Marcel Duchamp"
]


def fetch_url(url, timeout=15):
    """URL abrufen, HTML als String zurückgeben."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def check_griffelkunst_page(artist_name):
    """Prüft die Griffelkunst-Künstlerseite auf neue Editionen."""
    # URL-Slug erzeugen
    nachname = artist_name.split()[-1].lower()
    # Umlaute und Sonderzeichen
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                   "é": "e", "è": "e", "ë": "e", "ø": "o", "å": "a"}
    slug = nachname
    for old, new in replacements.items():
        slug = slug.replace(old, new)

    url = f"https://www.griffelkunst.de/kuenstler-innen/{slug}"
    html = fetch_url(url)
    if not html:
        return None

    # Editionen extrahieren — nur 3-stellige Serien (200+) und E/P-Editionen (100+)
    editions = set()
    for m in re.finditer(r'[EP]\s*(\d{3,4})', html):
        num = int(m.group(1))
        if num >= 100:  # Echte Editionen sind >100
            normalized = f"E {m.group(1)}" if m.group().startswith("E") else f"P {m.group(1)}"
            editions.add(normalized)
    for m in re.finditer(r'(\d{3})\s+[ABC]\d?', html):
        num = int(m.group(1))
        if num >= 200:  # Serien sind 200+
            editions.add(m.group().strip())

    return {
        "url": url,
        "editions_found": sorted(editions),
        "page_exists": True
    }


def search_ddg(query, max_results=5):
    """DuckDuckGo HTML-Suche (kein API-Key nötig)."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        html = fetch_url(url, timeout=20)
        if not html:
            return []

        results = []
        # Einfaches Parsen der DuckDuckGo HTML-Ergebnisse
        snippets = re.findall(r'class="result__snippet">(.*?)</a>', html, re.DOTALL)
        for snippet in snippets[:max_results]:
            clean = re.sub(r'<[^>]+>', '', snippet).strip()
            if clean:
                results.append(clean)
        return results
    except Exception:
        return []


def check_artist_updates(name, info):
    """Prüft einen Künstler auf relevante Veränderungen via Web-Suche."""
    updates = []

    # Web-Suche nach aktuellen Ereignissen
    year = date.today().year
    snippets = search_ddg(f"{name} Ausstellung Galerie {year}")

    for snippet in snippets:
        # Blue-Chip-Galerie-Check
        for gallery in BLUE_CHIP_GALLERIES:
            if gallery.lower() in snippet.lower() and not info.get("isBlueChip"):
                sig = info.get("significance", "")
                if gallery.lower() not in sig.lower():
                    updates.append({
                        "type": "galerie_wechsel",
                        "detail": f"Mögliche Blue-Chip-Galerie entdeckt: {gallery}",
                        "source": "Web-Suche",
                        "snippet": snippet[:200]
                    })

        # Wichtige Events
        for event in IMPORTANT_EVENTS:
            if event.lower() in snippet.lower():
                updates.append({
                    "type": "wichtiges_event",
                    "detail": f"Relevantes Event: {event}",
                    "source": "Web-Suche",
                    "snippet": snippet[:200]
                })

    # Deduplizieren
    seen = set()
    unique_updates = []
    for u in updates:
        key = u["type"] + u["detail"]
        if key not in seen:
            seen.add(key)
            unique_updates.append(u)

    return unique_updates


def run_monitoring():
    """Hauptfunktion: Alle Künstler durchprüfen."""
    print(f"🐗 Trüffelkunst Monitoring — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    artists = data["artists"]

    all_updates = {}
    checked = 0
    total = len(artists)

    for name, info in artists.items():
        checked += 1
        print(f"  [{checked}/{total}] {name}...", end=" ", flush=True)

        try:
            updates = check_artist_updates(name, info)
            if updates:
                all_updates[name] = updates
                print(f"→ {len(updates)} Update(s)!")
            else:
                print("✓")
        except Exception as e:
            print(f"✗ Fehler: {e}")

        time.sleep(0.3)  # Höflich bleiben

    # Ergebnis speichern
    result = {
        "timestamp": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "artists_checked": total,
        "artists_with_updates": len(all_updates),
        "updates": all_updates
    }

    UPDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPDATES_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Historie ergänzen
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append({
        "date": date.today().isoformat(),
        "artists_checked": total,
        "updates_found": len(all_updates)
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print()
    print(f"Ergebnis: {len(all_updates)} Künstler mit Updates von {total} geprüft.")
    print(f"Gespeichert: {UPDATES_FILE}")

    return result


if __name__ == "__main__":
    run_monitoring()
