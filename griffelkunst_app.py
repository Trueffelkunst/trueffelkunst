#!/usr/bin/env python3
"""
🐗 Trüffelkunst — Personal Collection App
Phase 1: Sammlungsübersicht mit Künstler-Details

Starten mit: streamlit run griffelkunst_app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import subprocess
import re
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from collections import OrderedDict
from PIL import Image
import base64
import io

# ─── Web-Recherche für Künstler-Bewertung ───
_ssl_ctx = ssl.create_default_context()

BLUE_CHIP_GALLERIES_SEARCH = [
    "Gagosian", "Hauser & Wirth", "Hauser&Wirth", "Pace Gallery", "Pace,",
    "David Zwirner", "Zwirner", "Marian Goodman", "Sprüth Magers",
    "Lisson", "Thaddaeus Ropac", "Ropac", "Gladstone", "White Cube",
    "neugerriemschneider", "Esther Schipper", "Buchholz", "Matthew Marks",
    "Paula Cooper", "Max Hetzler", "König Galerie", "Perrotin",
    "Petzel", "Eigen+Art", "Tanya Bonakdar"
]

MID_TIER_GALLERIES = [
    "Capitain", "Nagel Draxler", "Barbara Wien", "KOW", "Kraupa-Tuskany",
    "Galerie Crone", "Sies + Höke", "Meyer Riegger", "Galerie Gisela Capitain",
    "Nächst St. Stephan", "Johnen", "Contemporary Fine Arts", "CFA Berlin"
]

IMPORTANT_MUSEUMS = [
    "MoMA", "Museum of Modern Art", "Tate", "Guggenheim", "Centre Pompidou",
    "Pompidou", "Whitney", "Hamburger Bahnhof", "Kunsthalle", "Pinakothek",
    "Stedelijk", "Moderna Museet", "Ludwig", "MACBA", "Reina Sofia",
    "Serpentine", "Haus der Kunst", "Kunstverein", "Documenta", "documenta",
    "Biennale", "Manifesta", "Skulptur Projekte"
]

TECHNIQUE_KEYWORDS = {
    5: ["unikat", "unique", "original", "monotypie", "zeichnung auf"],
    4: ["heliogravüre", "heliogravure", "photogravure", "holzschnitt", "woodcut",
        "aquatinta", "mezzotint", "kaltnadelradierung"],
    3: ["radierung", "etching", "lithografie", "lithographie", "lithograph",
        "linolschnitt", "linocut"],
    2: ["siebdruck", "screenprint", "serigraphie", "c-print", "pigmentdruck",
        "inkjet", "giclée", "giclee"],
    1: ["offset", "digitaldruck", "poster", "plakat"]
}

def _fetch_url_quick(url, timeout=12):
    """URL abrufen, HTML als String."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

def _search_ddg_quick(query, max_results=8):
    """DuckDuckGo HTML-Suche."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        html = _fetch_url_quick(url, timeout=15)
        if not html:
            return []
        results = []
        snippets = re.findall(r'class="result__snippet">(.*?)</a>', html, re.DOTALL)
        for snippet in snippets[:max_results]:
            clean = re.sub(r'<[^>]+>', '', snippet).strip()
            if clean:
                results.append(clean)
        return results
    except Exception:
        return []

def recherche_artist(name):
    """Webrecherche zu einem Künstler, gibt RMTP-Schätzung + Fundstellen zurück."""
    findings = {"R": [], "M": [], "T": [], "P": [], "raw": []}
    r_score, m_score, t_score, p_score = 2, 2, 3, 3  # Defaults
    is_blue_chip = False

    # ── Suche 1: Galerien & Reputation ──
    snippets_r = _search_ddg_quick(f'"{name}" Galerie gallery representation')
    findings["raw"].extend(snippets_r)
    for s in snippets_r:
        s_lower = s.lower()
        for gal in BLUE_CHIP_GALLERIES_SEARCH:
            if gal.lower() in s_lower:
                r_score = max(r_score, 5)
                is_blue_chip = True
                findings["R"].append(f"Blue-Chip-Galerie: {gal}")
                break
        for gal in MID_TIER_GALLERIES:
            if gal.lower() in s_lower:
                r_score = max(r_score, 3)
                findings["R"].append(f"Galerie: {gal}")

    # ── Suche 2: Ausstellungen & Museum ──
    snippets_m = _search_ddg_quick(f'"{name}" Ausstellung exhibition museum solo')
    findings["raw"].extend(snippets_m)
    for s in snippets_m:
        s_lower = s.lower()
        for mus in IMPORTANT_MUSEUMS:
            if mus.lower() in s_lower:
                m_score = max(m_score, 4)
                findings["M"].append(f"Museum/Event: {mus}")
        if "solo" in s_lower or "einzelausstellung" in s_lower:
            m_score = max(m_score, 3)
            findings["M"].append("Solo-Ausstellung gefunden")
        if "retrospektive" in s_lower or "retrospective" in s_lower:
            m_score = max(m_score, 4)
            findings["M"].append("Retrospektive gefunden")

    # ── Suche 3: Technik ──
    snippets_t = _search_ddg_quick(f'"{name}" Druckgrafik Technik edition print etching lithograph')
    findings["raw"].extend(snippets_t)
    for s in snippets_t:
        s_lower = s.lower()
        for score_val, keywords in TECHNIQUE_KEYWORDS.items():
            for kw in keywords:
                if kw in s_lower:
                    t_score = max(t_score, score_val) if score_val > 3 else min(t_score, score_val) if score_val < 3 else t_score
                    findings["T"].append(f"Technik: {kw} (→ T={score_val})")
                    break

    # ── Suche 4: Preise / Markt ──
    snippets_p = _search_ddg_quick(f'"{name}" Auktion auction price Ergebnis Schätzpreis')
    findings["raw"].extend(snippets_p)
    price_found = False
    for s in snippets_p:
        s_lower = s.lower()
        # Hohe Preise deuten auf etablierten Markt
        for high_kw in ["€", "eur", "usd", "$", "gbp", "£", "sold for", "zuschlag", "hammer"]:
            if high_kw in s_lower:
                price_found = True
                # Versuche Preishöhe grob zu erkennen
                nums = re.findall(r'[\d.,]+(?:\s*(?:000|\.000))', s)
                if nums:
                    findings["P"].append(f"Auktionsergebnis gefunden")
                break
        if "undervalued" in s_lower or "unterbewertet" in s_lower or "emerging" in s_lower:
            p_score = max(p_score, 4)
            findings["P"].append("Potenzialsignal: emerging/unterbewertet")

    if price_found:
        p_score = max(p_score, 3)

    # Blue-Chip-Korrektur: wenn R=5, ist P eher niedrig (schon teuer)
    if r_score >= 5:
        p_score = min(p_score, 2)

    # Dedupliziere Findings
    for key in ["R", "M", "T", "P"]:
        findings[key] = list(dict.fromkeys(findings[key]))

    total = r_score + m_score + t_score + p_score
    # Liga
    if r_score >= 4 and total >= 12:
        liga = "Liga 1"
    elif total >= 12 or r_score >= 4:
        liga = "Liga 2"
    elif total >= 8:
        liga = "Liga 3"
    else:
        liga = "Liga 4"

    return {
        "R": r_score, "M": m_score, "T": t_score, "P": p_score,
        "total": total, "liga": liga, "isBlueChip": is_blue_chip,
        "findings": findings, "snippets_count": len(set(findings["raw"]))
    }

# ─── Page Config ───
# Favicon als base64 eingebettet (funktioniert überall, auch Streamlit Cloud)
_FAVICON_B64 = """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"""
try:
    _favicon_bytes = base64.b64decode(_FAVICON_B64)
    _page_icon = Image.open(io.BytesIO(_favicon_bytes))
except Exception:
    _page_icon = "🐗"
st.set_page_config(
    page_title="Trüffelkunst",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ─── Load Data ───
def load_data():
    data_path = Path(__file__).parent / "griffelkunst_data.json"
    mtime = data_path.stat().st_mtime  # cache-bust on file change
    return _load_data_cached(str(data_path), mtime)

@st.cache_data
def _load_data_cached(path_str, _mtime):
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
collection = data["collection"]
artists_data = data["artists"]

# ─── Liga dynamisch aus R+M+T+P berechnen (Reputation-gewichtet) ───
# Liga in artists_data aktualisieren
for name, info in artists_data.items():
    rmtp = info.get("rmtp", {})
    if rmtp:
        r = rmtp.get("R", 0)
        total = rmtp.get("total", 0)
        if r >= 4 and total >= 12:
            info["liga"] = "Liga 1"
        elif total >= 12 or r >= 4:
            info["liga"] = "Liga 2"
        elif total >= 8:
            info["liga"] = "Liga 3"
        elif total > 0:
            info["liga"] = "Liga 4"
        else:
            info["liga"] = ""
    else:
        info["liga"] = ""

# Liga in collection-Einträgen aktualisieren (aus Artist-Score)
for w in collection:
    artist_info = artists_data.get(w["artist"], {})
    w["liga"] = artist_info.get("liga", "")

# Stats dynamisch berechnen
stats = {
    "totalWorks": len(collection),
    "totalArtists": len(set(w["artist"] for w in collection)),
    "liga1": len(set(w["artist"] for w in collection if w["liga"] == "Liga 1")),
    "liga2": len(set(w["artist"] for w in collection if w["liga"] == "Liga 2")),
    "liga3": len(set(w["artist"] for w in collection if w["liga"] == "Liga 3")),
    "liga4": len(set(w["artist"] for w in collection if w["liga"] == "Liga 4")),
    "blueChip": len(set(w["artist"] for w in collection if w["isBlueChip"])),
}


# ─── Custom CSS — "Warmes Kabinett" Design ───
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&display=swap');
    .stApp { background-color: #F8F6F3; }
    .main .block-container { max-width: 1200px; padding-top: 2rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stHeader"] {visibility: hidden;}
    .app-header {
        font-family: 'Cormorant Garamond', Georgia, serif;
        text-align: center;
        background: #1B3A2A;
        margin: -2rem -1rem 2rem -1rem;
        padding: 2.5rem 1rem 1.5rem;
        border-radius: 0 0 2px 2px;
    }
    .app-header h1 {
        font-size: 2.4rem; font-weight: 400; letter-spacing: 0.12em;
        color: #F8F6F3; margin-bottom: 0.3rem; text-transform: uppercase;
    }
    .app-header .subtitle {
        font-size: 0.95rem; color: #B8964E; letter-spacing: 0.05em; font-style: italic;
    }
    .stats-bar {
        display: flex; justify-content: center; gap: 0;
        padding: 0; margin-bottom: 1.5rem;
        border-bottom: 1px solid #E0DDD8;
    }
    .stat-btn {
        text-align: center; padding: 1rem 1.8rem; cursor: pointer;
        border: none; background: none; transition: all 0.2s;
        border-bottom: 3px solid transparent; position: relative;
    }
    .stat-btn:hover { background: rgba(184, 150, 78, 0.06); }
    .stat-btn.active { border-bottom-color: #B8964E; background: rgba(184, 150, 78, 0.04); }
    .stat-number {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 1.8rem; font-weight: 600; color: #1A1A1A; line-height: 1;
    }
    .stat-label {
        font-size: 0.7rem; color: #8A8A8A; text-transform: uppercase;
        letter-spacing: 0.1em; margin-top: 0.2rem;
    }
    .liga-1 { color: #C44B3F; }
    .liga-2 { color: #6B7DB3; }
    .liga-3 { color: #5A9E5A; }
    .liga-4 { color: #C4993D; }
    .liga-none { color: #AAAAAA; }
    .work-card {
        background: white; border: 1px solid #E8E5E0; border-radius: 2px;
        padding: 1.2rem 1.4rem; margin-bottom: 0.8rem;
        transition: all 0.2s; position: relative;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .work-card:hover { border-color: #B8964E; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .work-card.liga-border-1 { border-left: 3px solid #C44B3F; }
    .work-card.liga-border-2 { border-left: 3px solid #6B7DB3; }
    .work-card.liga-border-3 { border-left: 3px solid #5A9E5A; }
    .work-card.liga-border-4 { border-left: 3px solid #C4993D; }
    .work-card.liga-border-none { border-left: 3px solid #E0E0E0; }
    .card-artist {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 1.15rem; font-weight: 600; color: #1A1A1A;
        letter-spacing: 0.03em; margin-bottom: 0.15rem;
    }
    .card-work { font-size: 0.85rem; color: #555555; font-style: italic; margin-bottom: 0.4rem; }
    .card-details { display: flex; justify-content: space-between; align-items: center; }
    .card-edition { font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace; font-size: 0.78rem; color: #888888; }
    .card-price { font-size: 0.8rem; color: #6B6B6B; }
    .card-date { font-size: 0.72rem; color: #AAAAAA; }
    .blue-chip-dot {
        display: inline-block; width: 7px; height: 7px; background: #B8964E;
        border-radius: 50%; margin-right: 6px; vertical-align: middle;
    }
    .liga-badge {
        display: inline-block; font-size: 0.65rem; padding: 1px 6px;
        border-radius: 2px; font-weight: 600; letter-spacing: 0.05em;
        margin-left: 8px; vertical-align: middle;
    }
    .liga-badge-1 { background: #C44B3F; color: white; }
    .liga-badge-2 { background: #6B7DB3; color: white; }
    .liga-badge-3 { background: #5A9E5A; color: white; }
    .liga-badge-4 { background: #C4993D; color: white; }
    .source-badge {
        display: inline-block; font-size: 0.6rem; padding: 1px 5px;
        border: 1px solid #E0E0E0; border-radius: 2px; color: #999;
        margin-left: 6px; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .source-maybe { border-color: #F0C040; color: #B08A00; background: #FFFBE6; }
    .artist-panel {
        background: white; border: 1px solid #E8E5E0; border-radius: 2px;
        padding: 2rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .artist-name {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 1.8rem; font-weight: 600; letter-spacing: 0.08em;
        color: #1A1A1A; text-transform: uppercase; margin-bottom: 0.3rem;
    }
    .artist-tier { font-size: 0.8rem; color: #8A8A8A; font-style: italic; margin-bottom: 1rem; }
    .artist-section-title {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em;
        color: #8A8A8A; margin-top: 1.2rem; margin-bottom: 0.4rem;
        border-bottom: 1px solid #F0EFEA; padding-bottom: 0.3rem;
    }
    .artist-tag {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #E0E0E0; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #555; background: #FAFAF8;
    }
    .artist-tag-gallery {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #D4C5E2; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #6B4F8A; background: #F5F0FA;
    }
    .artist-tag-exhibition {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #C5D4E2; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #4F6B8A; background: #F0F4FA;
    }
    .artist-tag-museum {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #C5E2C5; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #4F8A4F; background: #F0FAF0;
    }
    .artist-tag-auction {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #E2D4C5; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #8A6B4F; background: #FAF5F0;
    }
    .artist-tag-deceased {
        display: inline-block; font-size: 0.72rem; padding: 2px 8px;
        border: 1px solid #D0D0D0; border-radius: 2px; margin: 2px 3px 2px 0;
        color: #666; background: #F0F0F0; font-style: italic;
    }
    .liga-detail-badge {
        display: inline-block; font-size: 0.7rem; padding: 3px 10px;
        border-radius: 2px; font-weight: 600; letter-spacing: 0.04em; margin-right: 6px;
    }
    .liga-detail-badge-1 { background: #C44B3F; color: white; }
    .liga-detail-badge-2 { background: #6B7DB3; color: white; }
    .liga-detail-badge-3 { background: #5A9E5A; color: white; }
    .liga-detail-badge-4 { background: #C4993D; color: white; }
    .ranking-box {
        background: #FAF8F5; border-left: 3px solid #B8964E;
        padding: 0.8rem 1rem; margin: 0.5rem 0 1rem;
        font-size: 0.88rem; color: #444; line-height: 1.6; font-style: italic;
    }
    .ranking-box.liga-accent-1 { border-left-color: #C44B3F; }
    .ranking-box.liga-accent-2 { border-left-color: #6B7DB3; }
    .ranking-box.liga-accent-3 { border-left-color: #5A9E5A; }
    .ranking-box.liga-accent-4 { border-left-color: #C4993D; }
    .rmtp-bar {
        display: flex; gap: 6px; align-items: center;
        margin: 0.5rem 0 0.8rem 0; flex-wrap: wrap;
    }
    .rmtp-score-total {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1.6rem; font-weight: 700; color: #1B3A2A;
        margin-right: 8px; line-height: 1;
    }
    .rmtp-pill {
        display: inline-flex; align-items: center; gap: 3px;
        padding: 2px 8px; border-radius: 12px;
        font-size: 0.7rem; font-weight: 600; letter-spacing: 0.03em;
    }
    .rmtp-pill-r { background: #C44B3F22; color: #C44B3F; }
    .rmtp-pill-m { background: #6B7DB322; color: #6B7DB3; }
    .rmtp-pill-t { background: #5A9E5A22; color: #5A9E5A; }
    .rmtp-pill-p { background: #C4993D22; color: #C4993D; }
    .rmtp-label { font-size: 0.6rem; opacity: 0.7; }
    .editions-info {
        font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.82rem; color: #666; background: #F8F7F4;
        padding: 0.5rem 0.8rem; border-radius: 2px; margin: 0.4rem 0;
    }
    .value-summary { display: flex; gap: 1.5rem; margin: 0.6rem 0 0.3rem; }
    .value-item { font-size: 0.8rem; color: #666; }
    .value-item strong { color: #333; }
    /* ── Artist Gallery Tiles ── */
    .artist-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 1.2rem;
        margin-top: 0.5rem;
    }
    .artist-tile {
        background: white;
        border: 1px solid #E8E5E0;
        border-radius: 3px;
        overflow: hidden;
        transition: all 0.25s ease;
        cursor: pointer;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .artist-tile:hover {
        border-color: #B8964E;
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    .artist-tile-img {
        width: 100%;
        height: 200px;
        object-fit: cover;
        display: block;
        background: #EDEAE5;
    }
    .artist-tile-placeholder {
        width: 100%;
        height: 200px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #EDEAE5;
        color: #C0B8A8;
        font-size: 3rem;
        font-family: 'Cormorant Garamond', Georgia, serif;
    }
    /* ── Mobile: Portrait-Tiles responsive ── */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.3rem !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            flex: 0 0 calc(50% - 0.15rem) !important;
            min-width: calc(50% - 0.15rem) !important;
            max-width: calc(50% - 0.15rem) !important;
        }
        /* Leere Spalten am Zeilenende verstecken */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:empty {
            display: none !important;
        }
    }
    .artist-tile-info {
        padding: 0.7rem 0.8rem;
    }
    .artist-tile-name {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 0.95rem;
        font-weight: 600;
        color: #1A1A1A;
        letter-spacing: 0.02em;
        line-height: 1.2;
        margin-bottom: 0.3rem;
    }
    .artist-tile-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.7rem;
        color: #8A8A8A;
    }
    .artist-tile-score {
        font-family: 'Cormorant Garamond', serif;
        font-weight: 700;
        font-size: 0.85rem;
        color: #1B3A2A;
    }
    .artist-tile-works {
        font-size: 0.68rem;
        color: #aaa;
    }
    .css-1d391kg, [data-testid="stSidebar"] { background-color: #E8EDE5; }
    [data-testid="stSidebar"] .stMarkdown h2 {
        font-family: 'Cormorant Garamond', Georgia, serif;
        font-size: 1.1rem; letter-spacing: 0.08em; text-transform: uppercase; color: #1B3A2A;
    }
    [data-testid="stSidebar"] label { color: #1B3A2A !important; }
    .stSelectbox label, .stMultiSelect label, .stTextInput label {
        font-size: 0.8rem !important; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .dataframe { font-size: 0.85rem !important; }
    .dataframe th {
        background: #F0EDEA !important; font-size: 0.75rem !important;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)


# ─── Helper Functions ───
def compute_liga(artist_name):
    """Liga aus R+M+T+P-Score berechnen — Reputation-gewichtet.
    Liga 1: R≥4 UND Score≥12 (große Namen mit solidem Editionswert)
    Liga 2: Score≥12 ODER R≥4 (hoher Editionswert oder großer Name)
    Liga 3: Score≥8
    Liga 4: Rest
    """
    info = artists_data.get(artist_name, {})
    rmtp = info.get("rmtp", {})
    if not rmtp:
        return ""
    r = rmtp.get("R", 0)
    total = rmtp.get("total", 0)
    if r >= 4 and total >= 12:
        return "Liga 1"
    elif total >= 12 or r >= 4:
        return "Liga 2"
    elif total >= 8:
        return "Liga 3"
    elif total > 0:
        return "Liga 4"
    return ""

def get_liga_class(liga):
    if liga == "Liga 1": return "1"
    if liga == "Liga 2": return "2"
    if liga == "Liga 3": return "3"
    if liga == "Liga 4": return "4"
    return "none"

def get_liga_label(liga):
    labels = {"Liga 1": "Museumskanon", "Liga 2": "International etabliert", "Liga 3": "Aufstrebend", "Liga 4": "Weitere Position"}
    return labels.get(liga, "")

def get_source_label(source):
    labels = {"receipt": "Rechnung", "inventory": "Bestand", "catalog": "Katalog", "maybe": "Vielleicht"}
    return labels.get(source, source)

def extract_technique(work_desc):
    work_lower = work_desc.lower()
    if "mezzotinto" in work_lower: return "Mezzotinto"
    if "schadograph" in work_lower: return "Schadographie"
    if "heliograv" in work_lower: return "Heliogravüre"
    if "cyanotyp" in work_lower: return "Cyanotypie"
    if "monotyp" in work_lower: return "Monotypie"
    if "aquatinta" in work_lower: return "Aquatinta"
    if any(t in work_lower for t in ["lithograph", "litho", "farblitho"]): return "Lithographie"
    if any(t in work_lower for t in ["siebdruck", "serigraph"]): return "Siebdruck"
    if any(t in work_lower for t in ["radierung", "kaltnadel"]): return "Radierung"
    if any(t in work_lower for t in ["foto", "inkjet", "c-print", "ph a.d.n", "fotogram"]): return "Fotografie"
    if "holzschnitt" in work_lower: return "Holzschnitt"
    if any(t in work_lower for t in ["holz", "linol"]): return "Holz-/Linoldruck"
    if "multiple" in work_lower: return "Multiple"
    if any(t in work_lower for t in ["offset", "digitaler"]): return "Offsetdruck"
    if "edition" in work_lower: return "Edition"
    return "Sonstige"

# Alle einzigartigen Techniken in der Sammlung
ALL_TECHNIQUES_IN_COLLECTION = set(extract_technique(w["work"]) for w in collection if extract_technique(w["work"]) != "Sonstige")
RARE_TECHNIQUES = {"Mezzotinto", "Schadographie", "Heliogravüre", "Cyanotypie", "Monotypie", "Aquatinta", "Holzschnitt"}

# ─── Drucktechniken-Beschreibungen ───
TECHNIQUE_INFO = {
    "Radierung": "Tiefdruckverfahren: Eine Metallplatte (Kupfer/Zink) wird mit einer säurefesten Schicht überzogen. Der Künstler ritzt die Zeichnung mit einer Nadel in den Grund, dann ätzt Säure die freigelegten Linien in die Platte. Druckfarbe füllt die Vertiefungen, das Papier wird unter hohem Druck durch die Presse gezogen. Jeder Abzug ist leicht verschieden — echtes Handwerk.",
    "Lithographie": "Flachdruckverfahren: Der Künstler zeichnet mit fetthaltiger Kreide oder Tusche auf einen Kalkstein (oder eine Metallplatte). Durch chemische Behandlung nehmen nur die gezeichneten Stellen Farbe an. Ermöglicht sehr freies, malerisches Arbeiten — die Zeichnung wird fast 1:1 übertragen.",
    "Holzschnitt": "Hochdruckverfahren und eine der ältesten Drucktechniken: Der Künstler schneidet das Motiv in einen Holzblock — alles was stehen bleibt, druckt. Die erhabenen Flächen werden eingefärbt und auf Papier gepresst. Typisch: kräftige Kontraste, sichtbare Holzmaserung. Bei Farbholzschnitten wird für jede Farbe ein eigener Stock geschnitten.",
    "Siebdruck": "Durchdruckverfahren: Farbe wird durch ein feinmaschiges Sieb (Gewebe) auf Papier gedrückt. Nicht druckende Bereiche werden mit einer Schablone abgedeckt. Ermöglicht brillante Farben und große Auflagen. Bekannt durch Warhol und die Pop Art.",
    "Fotografie": "Fotografische Editionen bei Griffelkunst umfassen C-Prints, Inkjet-/Pigmentdrucke und analoge Abzüge. Jedes Blatt wird in limitierter Auflage produziert und vom Künstler signiert. Die Bandbreite reicht von dokumentarisch bis inszeniert.",
    "Offsetdruck": "Indirektes Flachdruckverfahren: Das Motiv wird von einer Druckplatte auf einen Gummizylinder und von dort auf Papier übertragen. Ermöglicht sehr hohe Auflagen bei gleichbleibender Qualität. Bei Griffelkunst oft für Editionen und Künstlerbücher verwendet.",
    "Linolschnitt": "Hochdruckverfahren wie der Holzschnitt, aber statt Holz wird Linoleum geschnitten. Das weichere Material erlaubt fließendere Linien und größere Flächen. Keine Holzmaserung — das Ergebnis ist glatter und grafischer.",
    "Aquatinta": "Tiefdruckverfahren, verwandt mit der Radierung: Feines Harzpulver wird auf die Platte gestäubt und erhitzt. Die Säure ätzt zwischen den Körnchen und erzeugt feine Tonabstufungen — fast wie eine Aquarellwirkung. Oft kombiniert mit Strichätzung.",
    "Mezzotinto": "Tiefdruckverfahren (auch Schabkunst): Die gesamte Platte wird mit einem Wiegemesser aufgeraut — sie würde tiefschwarz drucken. Der Künstler glättet dann die hellen Bereiche. Ergebnis: samtige Tiefen und feinste Tonübergänge. Extrem aufwändig und selten.",
    "Heliogravüre": "Fotografisches Tiefdruckverfahren: Ein Foto wird auf eine Kupferplatte übertragen und geätzt. Vereint die Detailtreue der Fotografie mit dem haptischen Reiz des Tiefdrucks. Die Drucke haben einen unverwechselbaren, warmen Ton. Sehr selten bei Griffelkunst.",
    "Schadographie": "Kameraloses Fotogramm-Verfahren, benannt nach Christian Schad: Gegenstände werden direkt auf lichtempfindliches Papier gelegt und belichtet. Jedes Blatt ist ein Unikat. Verwandt mit den Rayogrammen Man Rays.",
    "Cyanotypie": "Historisches Edeldruckverfahren: Eisensalze auf Papier werden durch UV-Licht belichtet. Ergebnis: charakteristisches Preußischblau. Wurde im 19. Jh. für botanische Dokumentation erfunden (Anna Atkins). Jeder Abzug ist ein Unikat.",
    "Monotypie": "Druckgrafik-Unikat: Der Künstler malt direkt auf eine glatte Platte und druckt das Motiv in einem einzigen Durchgang auf Papier ab. Jedes Blatt ist ein Unikat — die Technik liegt zwischen Malerei und Druckgrafik.",
    "Digitaldruck": "Moderne Drucktechnik: Das digitale Bild wird direkt auf Papier übertragen, ohne physische Druckform. Bei Griffelkunst meist als hochwertige Pigmentdrucke auf Büttenpapier realisiert.",
    "Sonstige": "Verschiedene Techniken, die nicht den gängigen Druckverfahren zugeordnet sind — darunter Mischtechniken, Multiples, Objekte und experimentelle Verfahren.",
    "Holz-/Linoldruck": "Hochdruckverfahren: Beim Holzdruck wird ein Holzblock als Druckstock verwendet — verwandt mit dem Holzschnitt, aber oft freier in der Bearbeitung (Sägen, Brechen, Materialdruck). Beim Linoldruck wird Linoleum geschnitten. Beide Techniken erzeugen kräftige, flächige Drucke mit starker materialer Präsenz.",
    "Edition": "Griffelkunst-Editionen sind vom Künstler signierte und nummerierte Druckgrafiken in limitierter Auflage. Die Technik variiert — häufig Siebdruck, Lithographie oder Digitaldruck. Editionen werden als Einzelblätter ausgegeben, oft in experimentelleren Formaten als die Serienblätter.",
    "Multiple": "Multiples sind Kunstobjekte in Auflage — keine klassische Druckgrafik, sondern dreidimensionale Werke oder Objekte, die in limitierter Serie produziert werden. Bei Griffelkunst oft überraschende Formate: von Keramik bis Textil.",
}

def sort_key_nachname(name):
    """Sort by last name (Nachname), German art convention."""
    # Handle special cases: "A. Paul Weber" → Weber, "Umbo (Otto Umbehr)" → Umbo
    clean = name.split("(")[0].strip()
    parts = clean.split()
    if len(parts) <= 1:
        return name.lower()
    # Skip nobility particles for sort: "von", "van", "de"
    nachname = parts[-1].lower()
    return nachname


# ─── Header ───
st.markdown('<div class="app-header"><h1>🐗 Trüffelkunst <span style="display: inline-block; transform: scaleX(-1);">🐗</span></h1><div class="subtitle">Sammlung Bodman</div></div>', unsafe_allow_html=True)

# ─── Monitoring-Updates Banner ───
monitoring_file = Path(__file__).parent / "daten" / "monitoring_updates.json"
if monitoring_file.exists():
    with open(monitoring_file, "r", encoding="utf-8") as f:
        mon_data = json.load(f)
    mon_updates = mon_data.get("updates", {})
    mon_date = mon_data.get("date", "")
    if mon_updates:
        update_count = sum(len(v) for v in mon_updates.values())
        artist_count = len(mon_updates)
        with st.expander(f"🔔 {update_count} Updates bei {artist_count} Künstler·innen — Stand {mon_date}", expanded=False):
            for artist, items in mon_updates.items():
                for item in items:
                    icon = "🏛" if item["type"] == "galerie_wechsel" else "🎨" if item["type"] == "neue_edition" else "⭐"
                    st.markdown(f"**{artist}** {icon} {item['detail']}")
                    if "snippet" in item:
                        st.caption(item["snippet"][:150])
            if st.button("✓ Updates gelesen — Banner ausblenden", key="btn_dismiss_updates"):
                import shutil
                archive = Path(__file__).parent / "daten" / f"monitoring_archive_{mon_date}.json"
                shutil.move(str(monitoring_file), str(archive))
                st.rerun()

# ─── Interactive Stats Bar ───
unique_artists = len(set(w["artist"] for w in collection))
blue_chip_count = len(set(w["artist"] for w in collection if w["isBlueChip"]))

# Meisterschüler zählen (aus Referenzdaten)
def is_meisterschueler(name):
    info = artists_data.get(name, {})
    sig = info.get("significance", "") or ""
    pot = info.get("potential", "") or ""
    text = sig + " " + pot
    return "eisterschül" in text or "chülerin" in text or "chüler " in text
meisterschueler_artists = set(w["artist"] for w in collection if is_meisterschueler(w["artist"]))
meisterschueler_count = len(meisterschueler_artists)

# Techniken zählen
technique_count = len(set(extract_technique(w["work"]) for w in collection if extract_technique(w["work"]) != "Sonstige"))

if "view" not in st.session_state:
    st.session_state.view = "künstler"
if "selected_artist" not in st.session_state:
    st.session_state.selected_artist = None
if "selected_technique" not in st.session_state:
    st.session_state.selected_technique = None

def set_view(v):
    st.session_state.view = v
    st.session_state.selected_artist = None
    st.session_state.selected_technique = None

# Zeile 1: Hauptzahlen (5 Spalten)
row1 = st.columns(5)
with row1[0]:
    if st.button(f"**{unique_artists}**\n\nKÜNSTLER", use_container_width=True, key="btn_kuenstler"):
        set_view("künstler")
with row1[1]:
    if st.button(f"**{len(collection)}**\n\nWERKE", use_container_width=True, key="btn_werke"):
        set_view("werke")
with row1[2]:
    if st.button(f"**{technique_count}**\n\nTECHNIK", use_container_width=True, key="btn_techniken"):
        set_view("techniken")
with row1[3]:
    if st.button(f"**{blue_chip_count}**\n\nBLUE CHIP", use_container_width=True, key="btn_bluechip"):
        set_view("bluechip")
with row1[4]:
    if st.button(f"**{meisterschueler_count}**\n\nMEISTERSCHÜLER", use_container_width=True, key="btn_meister"):
        set_view("meisterschueler")
# Zeile 2: Ligen + Bewerten (4 Spalten)
row2 = st.columns(4)
with row2[0]:
    if st.button(f"**{stats['liga1']}**\n\nLIGA 1", use_container_width=True, key="btn_liga1"):
        set_view("liga1")
with row2[1]:
    if st.button(f"**{stats['liga2']}**\n\nLIGA 2", use_container_width=True, key="btn_liga2"):
        set_view("liga2")
with row2[2]:
    if st.button(f"**{stats['liga3']}**\n\nLIGA 3", use_container_width=True, key="btn_liga3"):
        set_view("liga3")
with row2[3]:
    if st.button("**+**\n\nBEWERTEN", use_container_width=True, key="btn_bewerten"):
        set_view("bewerten")

st.markdown('<div style="border-bottom: 1px solid #E0DDD8; margin-bottom: 0.8rem;"></div>', unsafe_allow_html=True)

# ─── Filter — nur Suchfeld (nicht im Bewerten-Tab) ───
if st.session_state.view != "bewerten":
    search = st.text_input("🔍 Suche", placeholder="Künstler, Werk, Edition…", label_visibility="collapsed")
else:
    search = ""

# ─── Score-Legende (nicht im Bewerten-Tab) ───
if st.session_state.view != "bewerten":
  st.markdown(
    '<div style="text-align:center;margin:-0.3rem 0 0.6rem;font-family:Cormorant Garamond,Georgia,serif;'
    'color:#998E7D;letter-spacing:0.02em;">'
    # Zeile 1: Überschrift mit Buchstaben
    '<div style="display:flex;gap:1.2rem;justify-content:center;align-items:center;font-size:0.7rem;">'
    '<span><span style="font-weight:700;color:#C44B3F;">R</span> Reputation</span>'
    '<span><span style="font-weight:700;color:#6B7DB3;">M</span> Momentum</span>'
    '<span><span style="font-weight:700;color:#5A9E5A;">T</span> Technik</span>'
    '<span><span style="font-weight:700;color:#C4993D;">P</span> Potenzial</span>'
    '<span style="opacity:0.6;">— max. 20 Punkte</span>'
    '</div>'
    # Zeile 2: Erklärung was reinzählt
    '<div style="display:flex;gap:0.4rem;justify-content:center;flex-wrap:wrap;'
    'font-size:0.6rem;margin-top:0.25rem;opacity:0.75;line-height:1.4;">'
    '<span><span style="font-weight:700;color:#C44B3F;">R</span> Galerien · Museen · Kunstgeschichte</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="font-weight:700;color:#6B7DB3;">M</span> Letzte 3 J.: Solo-Shows · Biennalen · Preise</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="font-weight:700;color:#5A9E5A;">T</span> Druckwert: Unikat (5) → Offset (1)</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="font-weight:700;color:#C4993D;">P</span> Wertsteigerungschance</span>'
    '</div>'
    # Zeile 3: Liga-Berechnung
    '<div style="display:flex;gap:0.6rem;justify-content:center;flex-wrap:wrap;'
    'font-size:0.6rem;margin-top:0.35rem;opacity:0.7;line-height:1.4;">'
    '<span style="font-weight:600;">Liga:</span>'
    '<span><span style="color:#C44B3F;font-weight:700;">1</span> R≥4 + Score≥12</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="color:#6B7DB3;font-weight:700;">2</span> Score≥12 oder R≥4</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="color:#5A9E5A;font-weight:700;">3</span> Score≥8</span>'
    '<span style="opacity:0.3;">|</span>'
    '<span><span style="color:#C4993D;font-weight:700;">4</span> Rest</span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True
)

# Technik-Filter läuft über die Stats-Buttons, kein separates Dropdown nötig
selected_techniques = []
selected_sources = []
selected_ligas = []
show_blue_chip_only = False


# ─── Filter Logic ───
def matches_filter(work):
    if search:
        search_lower = search.lower()
        if not any(search_lower in str(work.get(f, "")).lower() for f in ["artist", "work", "edition"]):
            return False
    if selected_ligas:
        work_liga = work["liga"] if work["liga"] else "Ohne Liga"
        if work_liga not in selected_ligas:
            return False
    if selected_techniques:
        if extract_technique(work["work"]) not in selected_techniques:
            return False
    if selected_sources:
        if get_source_label(work["source"]) not in selected_sources:
            return False
    if show_blue_chip_only and not work["isBlueChip"]:
        return False
    return True

filtered = [w for w in collection if matches_filter(w)]
filtered.sort(key=lambda w: sort_key_nachname(w["artist"]))


# ─── Significance Parser ───
def parse_significance(sig_text):
    if not sig_text:
        return {"deceased": "", "galleries": [], "exhibitions": [], "museums": [], "auctions": [], "other": []}
    parts = [s.strip() for s in sig_text.split("|") if s.strip()]
    result = {"deceased": "", "galleries": [], "exhibitions": [], "museums": [], "auctions": [], "other": []}
    gallery_kw = ["Gagosian", "Hauser & Wirth", "Pace", "Zwirner", "Marian Goodman", "Sprüth Magers",
                   "Lisson", "Ropac", "Gladstone", "White Cube", "neugerriemschneider", "Esther Schipper",
                   "Buchholz", "Matthew Marks", "Paula Cooper", "Hetzler", "Luhring Augustine",
                   "Skarstedt", "König", "Petzel", "Tanya Bonakdar", "Eigen+Art", "Perrotin", "Galerie", "Gallery"]
    exhibit_kw = ["Venedig", "Documenta", "Turner Prize", "Pavillon", "Skulptur Projekte", "Biennale",
                  "Goldener Löwe", "Wolfgang Hahn", "Münster", "Whitney Biennial", "Berlin Biennale"]
    museum_kw = ["MoMA", "Tate", "Pompidou", "Guggenheim", "Whitney", "Ludwig", "Nationalgalerie",
                 "Neue Nationalgalerie", "Kunsthalle", "Schirn", "Hamburger", "Sammlung"]
    auction_kw = ["$", "€", "Mio", "Auktion", "Rekord", "Preis"]
    for part in parts:
        if part.startswith("†"):
            result["deceased"] = part
            continue
        matched = False
        if any(g in part for g in gallery_kw):
            result["galleries"].append(part); matched = True
        if not matched and any(a in part for a in auction_kw):
            result["auctions"].append(part); matched = True
        if not matched and any(e in part for e in exhibit_kw):
            result["exhibitions"].append(part); matched = True
        if not matched and any(m in part for m in museum_kw):
            result["museums"].append(part); matched = True
        if not matched:
            result["other"].append(part)
    return result


# ─── Artist Detail Panel ───
def show_artist_detail(artist_name):
    info = artists_data.get(artist_name)
    if not info:
        return
    liga = info.get("liga", "")
    liga_class = get_liga_class(liga)
    liga_label = get_liga_label(liga)
    liga_badge = ""
    if liga:
        liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{liga}</span>'
    bc_dot = '<span class="blue-chip-dot"></span>' if info["isBlueChip"] else ""
    gender_label = "Künstlerin" if info["gender"] == "f" else "Künstler"
    sig = parse_significance(info.get("significance", ""))
    parts = []
    parts.append('<div class="artist-panel">')
    parts.append(f'<div class="artist-name">{bc_dot}{artist_name}{liga_badge}</div>')
    liga_num = liga_class if liga_class != "none" else ""
    detail_line = f'<span class="liga-detail-badge liga-detail-badge-{liga_num}">{liga}</span> {liga_label} · {gender_label}' if liga else f'{gender_label}'
    if sig["deceased"]:
        detail_line += f' · <span class="artist-tag-deceased">{sig["deceased"]}</span>'
    parts.append(f'<div class="artist-tier">{detail_line}</div>')
    rmtp = info.get("rmtp", {})
    if rmtp:
        total = rmtp.get("total", 0)
        r, m, t, p = rmtp.get("R",0), rmtp.get("M",0), rmtp.get("T",0), rmtp.get("P",0)
        parts.append(f'''<div class="rmtp-bar">
            <span class="rmtp-score-total">{total}/20</span>
            <span class="rmtp-pill rmtp-pill-r"><span class="rmtp-label">R</span> {r}</span>
            <span class="rmtp-pill rmtp-pill-m"><span class="rmtp-label">M</span> {m}</span>
            <span class="rmtp-pill rmtp-pill-t"><span class="rmtp-label">T</span> {t}</span>
            <span class="rmtp-pill rmtp-pill-p"><span class="rmtp-label">P</span> {p}</span>
        </div>''')
    if info.get("editions"):
        parts.append(f'<div class="editions-info">Editionen: {info["editions"]}</div>')
    artist_works = [w for w in collection if w["artist"] == artist_name]
    parts.append(f'<div class="value-summary"><div class="value-item"><strong>{info["sheetCount"]}</strong> Blätter laut Referenz</div><div class="value-item"><strong>{len(artist_works)}</strong> Werke in Sammlung</div></div>')
    potential = info.get("potential", "")
    if potential:
        accent_class = f"liga-accent-{liga_class}" if liga_class in ["1","2","3","4"] else ""
        parts.append(f'<div class="artist-section-title">Einschätzung</div>')
        parts.append(f'<div class="ranking-box {accent_class}">{potential}</div>')
    if sig["galleries"]:
        parts.append('<div class="artist-section-title">Galerien</div>')
        tags = "".join(f'<span class="artist-tag-gallery">{g}</span>' for g in sig["galleries"])
        parts.append(f'<div style="margin-bottom: 0.6rem;">{tags}</div>')
    if sig["exhibitions"]:
        parts.append('<div class="artist-section-title">Ausstellungen &amp; Preise</div>')
        tags = "".join(f'<span class="artist-tag-exhibition">{e}</span>' for e in sig["exhibitions"])
        parts.append(f'<div style="margin-bottom: 0.6rem;">{tags}</div>')
    if sig["museums"]:
        parts.append('<div class="artist-section-title">Museen &amp; Sammlungen</div>')
        tags = "".join(f'<span class="artist-tag-museum">{m}</span>' for m in sig["museums"])
        parts.append(f'<div style="margin-bottom: 0.6rem;">{tags}</div>')
    if sig["auctions"]:
        parts.append('<div class="artist-section-title">Markt &amp; Auktionen</div>')
        tags = "".join(f'<span class="artist-tag-auction">{a}</span>' for a in sig["auctions"])
        parts.append(f'<div style="margin-bottom: 0.6rem;">{tags}</div>')
    if sig["other"]:
        tags = "".join(f'<span class="artist-tag">{o}</span>' for o in sig["other"])
        parts.append(f'<div style="margin-bottom: 0.6rem;">{tags}</div>')
    no_data = not any([sig["galleries"], sig["exhibitions"], sig["museums"], sig["auctions"], sig["other"]])
    if no_data and not potential:
        parts.append('<div style="font-size: 0.85rem; color: #aaa; margin: 0.5rem 0; font-style: italic;">Noch keine Detail-Daten hinterlegt</div>')
    parts.append(f'<div class="artist-section-title">Werke in der Sammlung ({len(artist_works)})</div>')
    for w in artist_works:
        source_class = "source-maybe" if w["source"] == "maybe" else ""
        technique = extract_technique(w["work"])
        # Support multiple images per work (image_urls array)
        img_urls = w.get("image_urls", [])
        if not img_urls and w.get("image_url"):
            img_urls = [w["image_url"]]
        img_html = ""
        if img_urls:
            img_parts = []
            for iu in img_urls:
                onerror = "this.style.display='none'"
                img_parts.append(f'<img src="{iu}" style="max-width: 260px; max-height: 200px; border: 1px solid #E8E5E0; border-radius: 2px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);" loading="lazy" onerror="{onerror}">')
            img_html = f'<div style="margin: 0.5rem 0; display: flex; flex-wrap: wrap; gap: 8px;">{"".join(img_parts)}</div>'
        parts.append(f'<div style="padding: 0.6rem 0; border-bottom: 1px solid #F5F4F0;">{img_html}<div style="display: flex; justify-content: space-between;"><div><span style="font-style: italic; color: #555; font-size: 0.85rem;">{w["work"]}</span> <span class="card-edition" style="margin-left: 8px;">{w["edition"]}</span> <span style="font-size: 0.65rem; color: #aaa; margin-left: 6px;">{technique}</span></div><div style="text-align: right; white-space: nowrap;"><span class="card-date">{w["date"]}</span></div></div></div>')
    parts.append('</div>')
    html = "\n".join(parts)
    st.markdown(html, unsafe_allow_html=True)


# ─── Group works by artist ───
def group_by_artist(works):
    groups = {}
    for work in works:
        if work["artist"] not in groups:
            groups[work["artist"]] = []
        groups[work["artist"]].append(work)
    return OrderedDict(sorted(groups.items(), key=lambda x: sort_key_nachname(x[0])))


# ─── Build expander label ───
def artist_label(artist_name):
    info = artists_data.get(artist_name, {})
    liga = compute_liga(artist_name)
    bc = "● " if info.get("isBlueChip") else ""
    rmtp = info.get("rmtp", {})
    total = rmtp.get("total", 0)
    score_str = f" ({total}/20)" if total > 0 else ""
    liga_str = f" · {liga}" if liga else ""
    return f"{bc}{artist_name}{liga_str}{score_str}"


# ─── Render work cards in columns ───
def render_work_cards(works):
    card_cols = st.columns(2)
    for j, w in enumerate(works):
        liga_class = get_liga_class(w["liga"])
        bc_dot = '<span class="blue-chip-dot"></span>' if w["isBlueChip"] else ""
        liga_badge = ""
        if w["liga"]:
            liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
        rmtp_badge = ""
        artist_info = artists_data.get(w["artist"], {})
        rmtp = artist_info.get("rmtp", {})
        if rmtp:
            total = rmtp.get("total", 0)
            color = "#C44B3F" if total >= 15 else "#6B7DB3" if total >= 12 else "#999"
            rmtp_badge = f'<span style="float:right;font-size:0.75rem;font-weight:700;color:{color};">{total}/20</span>'
        with card_cols[j % 2]:
            st.markdown(f'<div class="work-card liga-border-{liga_class}"><div class="card-artist">{bc_dot}{w["artist"]}{liga_badge}{rmtp_badge}</div><div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)


# ─── Main Content — View-dependent ───
view = st.session_state.view

# Apply view-based filtering on top of sidebar filters
if view == "liga1":
    view_filtered = [w for w in filtered if w["liga"] == "Liga 1"]
    view_label = "Liga 1"
elif view == "liga2":
    view_filtered = [w for w in filtered if w["liga"] == "Liga 2"]
    view_label = "Liga 2"
elif view == "liga3":
    view_filtered = [w for w in filtered if w["liga"] == "Liga 3"]
    view_label = "Liga 3"
elif view == "bluechip":
    view_filtered = [w for w in filtered if w["isBlueChip"]]
    view_label = "Blue Chip"
elif view == "meisterschueler":
    view_filtered = [w for w in filtered if is_meisterschueler(w["artist"])]
    view_label = "Meisterschüler"
elif view == "techniken":
    view_filtered = filtered
    view_label = "Techniken"
else:
    view_filtered = filtered
    view_label = None

artist_groups = group_by_artist(view_filtered)

# ── Detail View: If an artist is selected, show detail page ──
if st.session_state.selected_artist and st.session_state.selected_artist in artists_data:
    selected = st.session_state.selected_artist
    # Auto-Scroll + Browser-History für Zurück-Geste am Handy
    components.html("""
    <script>
        var pd = window.parent;
        // Scroll nach oben
        try {
            var main = pd.document.querySelector('section.main');
            if (main) main.scrollTop = 0;
            var container = pd.document.querySelector('[data-testid="stAppViewContainer"]');
            if (container) container.scrollTop = 0;
            pd.scrollTo(0, 0);
        } catch(e) {}
        // Browser-History: Zurück-Button/Swipe funktioniert
        if (!pd._trueffelHistorySet) {
            pd.history.pushState({view: 'detail'}, '', '');
            pd.addEventListener('popstate', function(e) {
                // Wenn Zurück gedrückt wird: Klick auf Zurück-Button
                var backBtn = pd.document.querySelector('[data-testid="stBaseButton-secondary"]');
                if (backBtn && backBtn.textContent.indexOf('Zurück') !== -1) {
                    backBtn.click();
                }
            });
            pd._trueffelHistorySet = true;
        }
    </script>
    """, height=0)
    if st.button("← Zurück zur Galerie", key="btn_back", use_container_width=True):
        st.session_state.selected_artist = None
        st.rerun()
    show_artist_detail(selected)
    # Zweiter Zurück-Button am Ende (wichtig für Mobile)
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    if st.button("← Zurück zur Galerie", key="btn_back_bottom", use_container_width=True):
        st.session_state.selected_artist = None
        st.rerun()

elif view == "werke":
    # ── Werke-Ansicht: alle Werke mit Abbildung als Karten ──
    st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem; letter-spacing: 0.03em;">{len(view_filtered)} Werke — sortiert nach Künstler·in (Nachname)</div>', unsafe_allow_html=True)
    card_cols = st.columns(3)
    for j, w in enumerate(view_filtered):
        liga_class = get_liga_class(w["liga"])
        bc_dot = '<span class="blue-chip-dot"></span>' if w["isBlueChip"] else ""
        liga_badge = ""
        if w["liga"]:
            liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
        technique = extract_technique(w["work"])
        img_url = w.get("image_url", "")
        img_html = ""
        if img_url:
            img_html = f'<div style="margin:0.4rem 0;"><img src="{img_url}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;" loading="lazy" onerror="this.style.display=\'none\'"></div>'
        with card_cols[j % 3]:
            st.markdown(f'<div class="work-card liga-border-{liga_class}">{img_html}<div class="card-artist">{bc_dot}{w["artist"]}{liga_badge}</div><div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span><span style="font-size: 0.65rem; color: #aaa; margin-left: 6px;">{technique}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
elif view == "techniken":
    # ── Techniken-Ansicht: Kacheln → Klick → Werke ──
    from collections import defaultdict
    tech_groups = defaultdict(list)
    for w in view_filtered:
        tech = extract_technique(w["work"])
        tech_groups[tech].append(w)

    present_techniques = set(tech_groups.keys())
    missing_rare = RARE_TECHNIQUES - present_techniques

    if st.session_state.selected_technique and st.session_state.selected_technique in tech_groups:
        # ── Detail: Werke einer Technik ──
        sel_tech = st.session_state.selected_technique
        tech_works = tech_groups[sel_tech]
        if st.button("← Zurück zu Techniken", key="btn_back_tech"):
            st.session_state.selected_technique = None
            st.rerun()
        is_rare = sel_tech in RARE_TECHNIQUES
        rare_badge = ' <span style="font-size: 0.65rem; background: #C4993D; color: white; padding: 1px 6px; border-radius: 2px; margin-left: 6px;">SELTEN</span>' if is_rare else ""
        st.markdown(f'<div style="font-family: Cormorant Garamond, Georgia, serif; font-size: 1.4rem; color: #1B3A2A; margin-bottom: 0.3rem;">{sel_tech}{rare_badge}</div>', unsafe_allow_html=True)
        # Technik-Beschreibung anzeigen
        tech_desc = TECHNIQUE_INFO.get(sel_tech, "")
        if tech_desc:
            st.markdown(
                f'<div style="font-size: 0.82rem; color: #6B6255; line-height: 1.6; '
                f'margin-bottom: 0.8rem; padding: 0.7rem 1rem; background: #F5F3EE; '
                f'border-left: 3px solid #B8964E; border-radius: 0 3px 3px 0;">'
                f'{tech_desc}</div>',
                unsafe_allow_html=True
            )
        st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem;">{len(tech_works)} Werke in der Sammlung</div>', unsafe_allow_html=True)
        card_cols = st.columns(3)
        for j, w in enumerate(tech_works):
            liga_class = get_liga_class(w["liga"])
            bc_dot = '<span class="blue-chip-dot"></span>' if w["isBlueChip"] else ""
            liga_badge = ""
            if w["liga"]:
                liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
            img_url = w.get("image_url", "")
            img_html = ""
            if img_url:
                img_html = f'<div style="margin:0.4rem 0;"><img src="{img_url}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;" loading="lazy" onerror="this.style.display=\'none\'"></div>'
            with card_cols[j % 3]:
                st.markdown(f'<div class="work-card liga-border-{liga_class}">{img_html}<div class="card-artist">{bc_dot}{w["artist"]}{liga_badge}</div><div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
    else:
        # ── Übersicht: Technik-Kacheln ──
        st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem; letter-spacing: 0.03em;">{len(present_techniques)} Techniken · {len(view_filtered)} Werke</div>', unsafe_allow_html=True)

        if missing_rare:
            missing_list = ", ".join(sorted(missing_rare))
            st.markdown(f"""<div style="background: #FFF8F0; border-left: 3px solid #C4993D; padding: 0.8rem 1rem; margin-bottom: 1.5rem; font-size: 0.85rem; color: #8A6B4F; line-height: 1.5;">
                <strong>Noch nicht in der Sammlung:</strong> {missing_list}<br>
                <span style="font-size: 0.78rem; color: #aaa;">→ Auf der Einkaufsliste vorgemerkt</span>
            </div>""", unsafe_allow_html=True)

        sorted_techs = sorted(tech_groups.items(), key=lambda x: -len(x[1]))
        TECH_COLS = 4
        for row_start in range(0, len(sorted_techs), TECH_COLS):
            row_items = sorted_techs[row_start:row_start + TECH_COLS]
            cols = st.columns(TECH_COLS)
            for idx, (tech_name, works) in enumerate(row_items):
                is_rare = tech_name in RARE_TECHNIQUES
                rare_label = " · selten" if is_rare else ""
                # Find a sample image from this technique
                sample_img = ""
                for tw in works:
                    if tw.get("image_url"):
                        sample_img = tw["image_url"]
                        break
                with cols[idx]:
                    if sample_img:
                        st.markdown(
                            f'<div style="width:100%;height:120px;overflow:hidden;border-radius:3px 3px 0 0;background:#F5F3EE;border:1px solid #E8E5E0;border-bottom:none;">'
                            f'<img src="{sample_img}" style="width:100%;height:120px;object-fit:contain;padding:4px;" loading="lazy" onerror="this.parentElement.style.display=\'none\'">'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    if st.button(f"{tech_name} ({len(works)}){rare_label}", key=f"tech_{tech_name}", use_container_width=True):
                        st.session_state.selected_technique = tech_name
                        st.rerun()
elif st.session_state.view != "bewerten":
    # ── Künstler·innen-Galerie: Portrait-Tiles im Grid ──
    filter_hint = f" — {view_label}" if view_label else ""
    st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem; letter-spacing: 0.03em;">{len(artist_groups)} Künstler·innen · {len(view_filtered)} Werke{filter_hint} — alphabetisch nach Nachname</div>', unsafe_allow_html=True)

    # Render grid — Streamlit columns with portrait tiles
    COLS_PER_ROW = 5
    artist_list = list(artist_groups.items())
    for row_start in range(0, len(artist_list), COLS_PER_ROW):
        row_items = artist_list[row_start:row_start + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)
        for idx, (artist_name, works) in enumerate(row_items):
            info = artists_data.get(artist_name, {})
            liga = info.get("liga", "")
            liga_class = get_liga_class(liga)
            rmtp = info.get("rmtp", {})
            total = rmtp.get("total", 0)
            bc_dot = "● " if info.get("isBlueChip") else ""
            liga_badge_html = ""
            if liga:
                liga_badge_html = f'<span class="liga-badge liga-badge-{liga_class}" style="margin-left:0;">{liga}</span>'
            score_html = f'<span style="font-family:Cormorant Garamond,serif;font-weight:700;font-size:0.8rem;color:#1B3A2A;">{total}/20</span>' if total > 0 else ""
            works_label = "Werk" if len(works) == 1 else "Werke"

            # Portrait für Tile (nur echte Portraits, keine Editions)
            img_src = info.get("portrait_url", "")

            with cols[idx]:
                # ── Portrait-Bild (oben) ──
                initial = artist_name[0] if artist_name else "?"
                if img_src:
                    onerror_attr = 'this.style.display=&quot;none&quot;;this.nextElementSibling.style.display=&quot;flex&quot;;'
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:4/3;overflow:hidden;border-radius:3px 3px 0 0;background:#EDEAE5;position:relative;">'
                        f'<img src="{img_src}" style="width:100%;height:100%;object-fit:cover;" loading="lazy" onerror="{onerror_attr}">'
                        f'<div style="display:none;width:100%;height:100%;align-items:center;justify-content:center;position:absolute;top:0;left:0;background:#EDEAE5;color:#C0B8A8;font-size:2.5rem;font-family:Cormorant Garamond,Georgia,serif;">{initial}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;background:#EDEAE5;color:#C0B8A8;font-size:2.5rem;font-family:Cormorant Garamond,Georgia,serif;border-radius:3px 3px 0 0;">{initial}</div>',
                        unsafe_allow_html=True
                    )
                # ── Name as clickable button ──
                if st.button(f"{bc_dot}{artist_name}", key=f"tile_{artist_name}", use_container_width=True):
                    st.session_state.selected_artist = artist_name
                    st.rerun()
                # ── Meta line: Liga + Score | Werke ──
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin:-0.3rem 0 1rem;padding:0 2px;">'
                    f'<div>{liga_badge_html} {score_html}</div>'
                    f'<div style="font-size:0.68rem;color:#aaa;">{len(works)} {works_label}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ─── Bewerten-Tab (Passwortschutz für Cloud-Version) ───
if view == "bewerten":
    # Cloud-Passwortschutz: Bewerten nur für Admins
    import os
    _admin_pw = os.environ.get("TRUEFFEL_ADMIN_PW", "")
    if _admin_pw:  # Nur in der Cloud aktiv (lokal: kein Passwort nötig)
        if "admin_unlocked" not in st.session_state:
            st.session_state.admin_unlocked = False
        if not st.session_state.admin_unlocked:
            st.markdown('<div style="font-family: Cormorant Garamond, Georgia, serif; font-size: 1.4rem; color: #1B3A2A; margin-bottom: 0.5rem;">Bewerten — geschützter Bereich</div>', unsafe_allow_html=True)
            _pw_input = st.text_input("Passwort", type="password", key="admin_pw")
            if st.button("Entsperren", key="btn_unlock"):
                if _pw_input == _admin_pw:
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("Falsches Passwort")
            st.stop()

    st.markdown('<div style="font-family: Cormorant Garamond, Georgia, serif; font-size: 1.4rem; color: #1B3A2A; margin-bottom: 0.5rem;">Künstler·in bewerten</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem;">Nachschlagen oder neuen Künstler nach dem RMTP-System bewerten und speichern.</div>', unsafe_allow_html=True)

    # Monitoring-Updates laden
    _mon_updates = {}
    _mon_file = Path(__file__).parent / "daten" / "monitoring_updates.json"
    if _mon_file.exists():
        with open(_mon_file, "r", encoding="utf-8") as f:
            _mon_data = json.load(f)
        _mon_updates = _mon_data.get("updates", {})

    # Monitoring manuell starten
    _mon_col1, _mon_col2 = st.columns([3, 1])
    with _mon_col2:
        if st.button("🔍 Monitoring starten", key="btn_run_monitoring", use_container_width=True):
            _mon_script = Path(__file__).parent / "monitoring.py"
            if _mon_script.exists():
                with st.spinner("Monitoring läuft… (ca. 2–3 Min.)"):
                    _result = subprocess.run(
                        ["python3", str(_mon_script)],
                        capture_output=True, text=True, timeout=600,
                        cwd=str(Path(__file__).parent)
                    )
                if _result.returncode == 0:
                    # Ergebnis lesen und Feedback geben
                    _mon_file_check = Path(__file__).parent / "daten" / "monitoring_updates.json"
                    _found_updates = 0
                    _checked_count = 0
                    if _mon_file_check.exists():
                        with open(_mon_file_check, "r", encoding="utf-8") as _mf:
                            _mon_result = json.load(_mf)
                        _found_updates = _mon_result.get("artists_with_updates", 0)
                        _checked_count = _mon_result.get("artists_checked", 0)
                    if _found_updates > 0:
                        st.success(f"✅ Monitoring abgeschlossen — {_found_updates} Künstler mit Updates! (von {_checked_count} geprüft)")
                    else:
                        st.info(f"✅ Monitoring abgeschlossen — keine neuen Updates gefunden. Alle {_checked_count} Künstler geprüft, alles beim Alten.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Fehler: {_result.stderr[:200]}")
            else:
                st.error("monitoring.py nicht gefunden")
    with _mon_col1:
        if _mon_file.exists():
            _mon_date = _mon_data.get("date", "unbekannt")
            _mon_count = _mon_data.get("artists_with_updates", 0)
            st.markdown(f'<div style="font-size:0.75rem;color:#8A8A8A;padding-top:0.5rem;">Letzter Check: {_mon_date} · {_mon_count} Updates</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.75rem;color:#8A8A8A;padding-top:0.5rem;">Noch kein Monitoring durchgeführt</div>', unsafe_allow_html=True)

    # Wenn Updates existieren, Künstler mit Updates oben als Quick-Buttons anzeigen
    if _mon_updates:
        st.markdown('<div style="font-size:0.8rem;color:#C44B3F;margin-bottom:0.4rem;">🔔 Künstler mit neuen Updates:</div>', unsafe_allow_html=True)
        _upd_cols = st.columns(min(len(_mon_updates), 5))
        for _i, _upd_name in enumerate(list(_mon_updates.keys())[:5]):
            with _upd_cols[_i % 5]:
                if st.button(f"📌 {_upd_name}", key=f"btn_upd_{_i}", use_container_width=True):
                    st.session_state["bewerten_prefill"] = _upd_name
                    st.rerun()
        st.markdown("---")

    # ─── Batch-Modus: Restblattliste hochladen oder einfügen ───
    with st.expander("📋 Restblattliste prüfen (Batch)", expanded=False):
        st.markdown('<div style="font-size:0.8rem;color:#8A8A8A;margin-bottom:0.5rem;">Lade eine Liste hoch oder kopiere Künstlernamen rein — ein Name pro Zeile.</div>', unsafe_allow_html=True)
        _batch_tab1, _batch_tab2 = st.tabs(["📄 Datei hochladen", "✏️ Namen einfügen"])
        _batch_names = []
        with _batch_tab1:
            _uploaded = st.file_uploader("CSV oder Textdatei", type=["csv", "txt", "tsv"], key="batch_upload")
            if _uploaded:
                _raw = _uploaded.read().decode("utf-8", errors="replace")
                # Flexibles Parsen: CSV, Tab-getrennt oder ein Name pro Zeile
                import csv, io
                _reader = csv.reader(io.StringIO(_raw))
                for _row in _reader:
                    for _cell in _row:
                        _clean = _cell.strip()
                        # Nur Strings die wie Namen aussehen (mind. 2 Buchstaben, keine reinen Zahlen)
                        if _clean and len(_clean) >= 2 and not _clean.replace(" ", "").isdigit():
                            _batch_names.append(_clean)
        with _batch_tab2:
            _text_input = st.text_area("Künstlernamen (ein Name pro Zeile)", height=150, key="batch_text",
                                       placeholder="z.B.:\nChristopher Wool\nNeo Rauch\nRosemarie Trockel")
            if _text_input:
                for _line in _text_input.strip().split("\n"):
                    _clean = _line.strip()
                    if _clean and len(_clean) >= 2:
                        _batch_names.append(_clean)

        if _batch_names:
            # Deduplizieren, Reihenfolge beibehalten
            _seen = set()
            _unique_names = []
            for _n in _batch_names:
                if _n.lower() not in _seen:
                    _seen.add(_n.lower())
                    _unique_names.append(_n)
            _batch_names = _unique_names

            st.markdown(f'<div style="font-size:0.8rem;color:#1B3A2A;font-weight:600;margin:0.5rem 0;">{len(_batch_names)} Künstler·innen erkannt</div>', unsafe_allow_html=True)

            # Abgleich mit bestehenden Daten
            _in_sammlung = []
            _nicht_in_sammlung = []
            for _bn in _batch_names:
                _found = artists_data.get(_bn)
                if not _found:
                    _matches = [n for n in artists_data if _bn.lower() in n.lower()]
                    if len(_matches) == 1:
                        _found = artists_data[_matches[0]]
                        _bn = _matches[0]
                if _found:
                    _rmtp = _found.get("rmtp", {})
                    _total = _rmtp.get("total", 0)
                    _liga = _found.get("liga", "?")
                    _bc = " ●" if _found.get("isBlueChip") else ""
                    _in_sammlung.append(f"{_bn} — {_liga} · {_total}/20{_bc}")
                else:
                    _nicht_in_sammlung.append(_bn)

            if _in_sammlung:
                st.markdown(f'<div style="font-size:0.75rem;color:#5A9E5A;margin:0.3rem 0;">✓ {len(_in_sammlung)} bereits in der Sammlung:</div>', unsafe_allow_html=True)
                for _s in _in_sammlung:
                    st.markdown(f'<div style="font-size:0.75rem;color:#666;padding-left:0.8rem;">{_s}</div>', unsafe_allow_html=True)

            if _nicht_in_sammlung:
                st.markdown(f'<div style="font-size:0.75rem;color:#C44B3F;margin:0.5rem 0;">⬡ {len(_nicht_in_sammlung)} unbekannt — einzeln bewerten:</div>', unsafe_allow_html=True)
                _new_cols = st.columns(min(len(_nicht_in_sammlung), 4))
                for _ni, _nn in enumerate(_nicht_in_sammlung[:20]):
                    with _new_cols[_ni % 4]:
                        if st.button(f"→ {_nn}", key=f"btn_batch_{_ni}", use_container_width=True):
                            st.session_state["bewerten_prefill"] = _nn
                            st.rerun()

            if not _nicht_in_sammlung and _in_sammlung:
                st.success("Alle Künstler·innen sind bereits in der Sammlung bewertet!")

    st.markdown("---")

    # Name eingeben oder aus Update-Button übernehmen
    _prefill = st.session_state.pop("bewerten_prefill", "")
    bewerten_name = st.text_input("Künstler·in", value=_prefill, placeholder="Name eingeben…", key="bewerten_name")

    if bewerten_name:
        # Check if artist exists
        existing = artists_data.get(bewerten_name)
        if not existing:
            matches = [n for n in artists_data if bewerten_name.lower() in n.lower()]
            if len(matches) == 1:
                existing = artists_data[matches[0]]
                bewerten_name = matches[0]
            elif len(matches) > 1:
                st.info(f"Mehrere Treffer: {', '.join(matches)}")

        # Monitoring-Updates für diesen Künstler laden + Score-Vorschlag berechnen
        artist_updates = _mon_updates.get(bewerten_name, [])
        suggest_r_delta = 0
        suggest_m_delta = 0
        suggest_bc = False
        update_reasons = []

        BLUE_CHIP_GALS = ["Gagosian", "Hauser & Wirth", "Hauser&Wirth", "Pace", "Zwirner",
                         "Sprüth Magers", "Ropac", "Thaddaeus Ropac"]
        for upd in artist_updates:
            if upd["type"] == "galerie_wechsel":
                for gal in BLUE_CHIP_GALS:
                    if gal.lower() in upd["detail"].lower():
                        suggest_r_delta = max(suggest_r_delta, 1)
                        suggest_bc = True
                        update_reasons.append(f"🏛 **Galeriewechsel**: {upd['detail']} → R erhöhen, Blue Chip setzen")
                        break
                else:
                    update_reasons.append(f"🏛 {upd['detail']}")
            elif upd["type"] == "wichtiges_event":
                if any(kw in upd["detail"].lower() for kw in ["biennale", "documenta", "venedig", "venice"]):
                    suggest_m_delta = max(suggest_m_delta, 1)
                    update_reasons.append(f"⭐ **Event**: {upd['detail']} → M erhöhen")
                elif "retrospektive" in upd["detail"].lower():
                    suggest_m_delta = max(suggest_m_delta, 1)
                    update_reasons.append(f"⭐ **Retrospektive**: {upd['detail']} → M erhöhen")
                else:
                    update_reasons.append(f"⭐ {upd['detail']}")
            elif upd["type"] == "neue_edition":
                update_reasons.append(f"🎨 {upd['detail']}")

        if existing:
            rmtp = existing.get("rmtp", {})
            liga = existing.get("liga", "")
            liga_label = get_liga_label(liga)
            bc = "● Blue Chip" if existing.get("isBlueChip") else ""
            total = rmtp.get("total", 0)
            st.markdown(
                f'<div style="background:#FAF8F5;padding:1rem 1.2rem;border-radius:4px;border-left:3px solid #B8964E;margin-bottom:1rem;">'
                f'<div style="font-family:Cormorant Garamond,serif;font-size:1.2rem;font-weight:700;color:#1B3A2A;">{bewerten_name} {bc}</div>'
                f'<div style="margin:0.5rem 0;font-size:0.9rem;">'
                f'<span style="color:#C44B3F;font-weight:700;">R {rmtp.get("R",0)}</span> · '
                f'<span style="color:#6B7DB3;font-weight:700;">M {rmtp.get("M",0)}</span> · '
                f'<span style="color:#5A9E5A;font-weight:700;">T {rmtp.get("T",0)}</span> · '
                f'<span style="color:#C4993D;font-weight:700;">P {rmtp.get("P",0)}</span> · '
                f'<span style="font-weight:700;">{total}/20</span></div>'
                f'<div style="font-size:0.85rem;color:#666;">{liga} · {liga_label}</div>'
                f'<div style="font-size:0.82rem;color:#888;margin-top:0.4rem;font-style:italic;">{existing.get("potential","")}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        else:
            st.markdown(f'<div style="font-size:0.85rem;color:#5A9E5A;margin-bottom:0.5rem;">✦ Neuer Künstler — Bewertung eingeben:</div>', unsafe_allow_html=True)

        # ── Web-Recherche Button ──
        _rech_col1, _rech_col2 = st.columns([3, 1])
        with _rech_col2:
            _do_recherche = st.button("🔍 Web-Recherche", key="btn_recherche", use_container_width=True,
                                      help="Sucht im Web nach Galerien, Ausstellungen, Technik und Preisen")
        if _do_recherche:
            with st.spinner(f"Recherchiere {bewerten_name}…"):
                _rech = recherche_artist(bewerten_name)
                st.session_state["recherche_result"] = _rech
                st.session_state["recherche_name"] = bewerten_name

        # Recherche-Ergebnis anzeigen (bleibt bis Name sich ändert)
        if st.session_state.get("recherche_name") == bewerten_name and "recherche_result" in st.session_state:
            _rech = st.session_state["recherche_result"]
            _liga_colors_r = {"Liga 1": "#C44B3F", "Liga 2": "#6B7DB3", "Liga 3": "#5A9E5A", "Liga 4": "#C4993D"}
            _r_col = _liga_colors_r.get(_rech["liga"], "#999")
            _bc_label = " · ● Blue Chip" if _rech["isBlueChip"] else ""

            st.markdown(
                f'<div style="background:#F0F7F2;padding:1rem 1.2rem;border-radius:4px;border-left:3px solid #5A9E5A;margin-bottom:1rem;">'
                f'<div style="font-family:Cormorant Garamond,serif;font-size:1.1rem;font-weight:700;color:#1B3A2A;">🔍 Web-Recherche: {bewerten_name}{_bc_label}</div>'
                f'<div style="margin:0.5rem 0;font-size:0.9rem;">'
                f'<span style="color:#C44B3F;font-weight:700;">R {_rech["R"]}</span> · '
                f'<span style="color:#6B7DB3;font-weight:700;">M {_rech["M"]}</span> · '
                f'<span style="color:#5A9E5A;font-weight:700;">T {_rech["T"]}</span> · '
                f'<span style="color:#C4993D;font-weight:700;">P {_rech["P"]}</span> · '
                f'<span style="font-weight:700;">{_rech["total"]}/20</span> · '
                f'<span style="color:{_r_col};font-weight:700;">{_rech["liga"]}</span></div>'
                f'<div style="font-size:0.75rem;color:#888;margin-top:0.3rem;">{_rech["snippets_count"]} Webquellen ausgewertet</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            # Fundstellen Details
            _detail_parts = []
            if _rech["findings"]["R"]:
                _detail_parts.append("**R — Reputation:** " + " · ".join(_rech["findings"]["R"]))
            if _rech["findings"]["M"]:
                _detail_parts.append("**M — Momentum:** " + " · ".join(_rech["findings"]["M"]))
            if _rech["findings"]["T"]:
                _detail_parts.append("**T — Technik:** " + " · ".join(_rech["findings"]["T"]))
            if _rech["findings"]["P"]:
                _detail_parts.append("**P — Potenzial:** " + " · ".join(_rech["findings"]["P"]))
            if _detail_parts:
                with st.expander("📋 Fundstellen", expanded=False):
                    for _dp in _detail_parts:
                        st.markdown(f'<div style="font-size:0.82rem;margin:0.3rem 0;">{_dp}</div>', unsafe_allow_html=True)
            elif not _rech["findings"]["R"] and not _rech["findings"]["M"]:
                st.markdown('<div style="font-size:0.8rem;color:#888;font-style:italic;">Wenig im Web gefunden — Score-Vorschlag basiert auf Defaults. Bitte manuell anpassen.</div>', unsafe_allow_html=True)

        # Update-Vorschläge anzeigen
        if update_reasons:
            st.markdown(
                '<div style="background:#FFF8E7;padding:0.8rem 1rem;border-radius:4px;border-left:3px solid #C4993D;margin-bottom:1rem;">'
                '<div style="font-size:0.8rem;font-weight:700;color:#C4993D;margin-bottom:0.3rem;">📋 Vorschläge aus Monitoring-Updates:</div>'
                + "".join(f'<div style="font-size:0.82rem;color:#555;margin:0.2rem 0;">{r}</div>' for r in update_reasons)
                + '</div>',
                unsafe_allow_html=True
            )
            if suggest_r_delta or suggest_m_delta or suggest_bc:
                changes = []
                if suggest_r_delta:
                    old_r = existing.get("rmtp", {}).get("R", 3) if existing else 3
                    changes.append(f"R: {old_r} → **{min(5, old_r + suggest_r_delta)}**")
                if suggest_m_delta:
                    old_m = existing.get("rmtp", {}).get("M", 3) if existing else 3
                    changes.append(f"M: {old_m} → **{min(5, old_m + suggest_m_delta)}**")
                if suggest_bc and not (existing and existing.get("isBlueChip")):
                    changes.append("Blue Chip: **● setzen**")
                st.markdown(
                    f'<div style="font-size:0.85rem;color:#1B3A2A;font-weight:600;margin-bottom:0.5rem;">'
                    f'Empfohlene Änderungen: {" · ".join(changes)}'
                    f'</div>',
                    unsafe_allow_html=True
                )

        st.markdown("##### Score anpassen" if existing else "##### Score vergeben")

        # RMTP Sliders — mit Update-Vorschlägen oder Recherche-Ergebnis als Defaults
        _has_recherche = (st.session_state.get("recherche_name") == bewerten_name and "recherche_result" in st.session_state)
        _rech_data = st.session_state.get("recherche_result", {}) if _has_recherche else {}

        if existing:
            base_r = existing.get("rmtp", {}).get("R", 3)
            base_m = existing.get("rmtp", {}).get("M", 3)
            default_r = min(5, base_r + suggest_r_delta)
            default_m = min(5, base_m + suggest_m_delta)
            default_t = existing.get("rmtp", {}).get("T", 3)
            default_p = existing.get("rmtp", {}).get("P", 3)
        elif _has_recherche:
            default_r = _rech_data.get("R", 3)
            default_m = _rech_data.get("M", 3)
            default_t = _rech_data.get("T", 3)
            default_p = _rech_data.get("P", 3)
        else:
            default_r = 3
            default_m = 3
            default_t = 3
            default_p = 3

        score_cols = st.columns(4)
        with score_cols[0]:
            r_val = st.slider("R — Reputation", 1, 5, default_r, key="slider_r",
                            help="5=Gagosian/MoMA, 4=Sprüth Magers/Tate, 3=gute Galerie, 2=Aufbau, 1=kaum")
        with score_cols[1]:
            m_val = st.slider("M — Momentum", 1, 5, default_m, key="slider_m",
                            help="5=mehrere Top-Solos aktuell, 4=2-3 Solos, 3=aktiv, 2=wenig, 1=kaum")
        with score_cols[2]:
            t_val = st.slider("T — Technik", 1, 5, default_t, key="slider_t",
                            help="5=Unikat, 4=Heliogravüre, 3=Radierung/Litho, 2=Siebdruck, 1=Offset")
        with score_cols[3]:
            p_val = st.slider("P — Potenzial", 1, 5, default_p, key="slider_p",
                            help="5=extrem unterbewertet, 4=deutlich, 3=solide, 2=stabil, 1=kein Markt")

        total_score = r_val + m_val + t_val + p_val

        # Liga berechnen
        if r_val >= 4 and total_score >= 12:
            calc_liga = "Liga 1"
        elif total_score >= 12 or r_val >= 4:
            calc_liga = "Liga 2"
        elif total_score >= 8:
            calc_liga = "Liga 3"
        else:
            calc_liga = "Liga 4"

        liga_colors = {"Liga 1": "#C44B3F", "Liga 2": "#6B7DB3", "Liga 3": "#5A9E5A", "Liga 4": "#C4993D"}
        liga_col = liga_colors.get(calc_liga, "#999")

        # Veränderung zum bisherigen Score anzeigen
        score_change = ""
        if existing and existing.get("rmtp", {}).get("total"):
            old_total = existing["rmtp"]["total"]
            old_liga = existing.get("liga", "")
            if total_score != old_total or calc_liga != old_liga:
                diff = total_score - old_total
                diff_str = f"+{diff}" if diff > 0 else str(diff)
                liga_change = f" · {old_liga} → {calc_liga}" if calc_liga != old_liga else ""
                score_change = f'<div style="font-size:0.75rem;color:#C44B3F;margin-top:0.2rem;">Änderung: {diff_str} Punkte{liga_change}</div>'

        st.markdown(
            f'<div style="text-align:center;padding:0.6rem;margin:0.5rem 0;background:#FAF8F5;border-radius:4px;">'
            f'<span style="font-family:Cormorant Garamond,serif;font-size:1.3rem;font-weight:700;">{total_score}/20</span>'
            f' · <span style="color:{liga_col};font-weight:700;">{calc_liga}</span>'
            f' · {get_liga_label(calc_liga)}'
            f'{score_change}</div>',
            unsafe_allow_html=True
        )

        # Additional fields
        detail_cols = st.columns(2)
        with detail_cols[0]:
            gender = st.selectbox("Gender", ["f", "m", "d"], index=0 if not existing else (0 if existing.get("gender") == "f" else 1), key="sel_gender")
            default_bc = suggest_bc or (existing.get("isBlueChip", False) if existing else False) or (_rech_data.get("isBlueChip", False) if _has_recherche else False)
            is_bc = st.checkbox("Blue Chip ●", value=default_bc, key="chk_bc")
        with detail_cols[1]:
            editions = st.text_input("Editionen", value=existing.get("editions", "") if existing else "", key="inp_editions")
            sheet_count = st.number_input("Blätter", min_value=0, value=existing.get("sheetCount", 1) if existing else 1, key="inp_sheets")

        significance = st.text_input("Galerien / Kontext", value=existing.get("significance", "") if existing else "",
                                    placeholder="Gagosian | MoMA | Documenta", key="inp_sig")
        potential = st.text_area("Einschätzung", value=existing.get("potential", "") if existing else "",
                               placeholder="Freitext-Bewertung…", height=80, key="inp_pot")

        # Save button
        if st.button("💾 Speichern", type="primary", key="btn_save_artist"):
            if not bewerten_name.strip():
                st.error("Bitte Name eingeben")
            else:
                new_entry = {
                    "tier": int(calc_liga.split()[-1]),
                    "liga": calc_liga,
                    "editions": editions,
                    "sheetCount": sheet_count,
                    "significance": significance,
                    "potential": potential,
                    "isBlueChip": is_bc,
                    "gender": gender,
                    "rmtp": {"R": r_val, "M": m_val, "T": t_val, "P": p_val, "total": total_score},
                    "portrait_url": existing.get("portrait_url", "") if existing else ""
                }
                # Save to JSON
                data_path = Path(__file__).parent / "griffelkunst_data.json"
                with open(data_path, "r", encoding="utf-8") as f:
                    save_data = json.load(f)
                save_data["artists"][bewerten_name.strip()] = new_entry
                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                st.success(f"✓ {bewerten_name} gespeichert — {calc_liga} · {total_score}/20")
                st.cache_data.clear()


# ─── Footer ───
st.markdown("---")
st.markdown('<div style="text-align: center; padding: 1rem 0 2rem; color: #B8964E; font-size: 0.75rem; letter-spacing: 0.08em; font-family: Cormorant Garamond, Georgia, serif;">Trüffelkunst · Sammlung Bodman</div>', unsafe_allow_html=True)
