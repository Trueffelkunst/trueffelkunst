#!/usr/bin/env python3
"""
Trüffelkunst — Personal Collection App
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
from collections import OrderedDict, Counter
from PIL import Image
import base64
import io

# ─── Web-Recherche für Künstler-Bewertung ───
_ssl_ctx = ssl.create_default_context()

BLUE_CHIP_GALLERIES_SEARCH = [
    "Gagosian", "Hauser & Wirth", "Hauser&Wirth", "Pace Gallery", "David Zwirner", "Zwirner",
    "Marian Goodman", "Sprüth Magers", "Sprüth", "Lisson", "Thaddaeus Ropac", "Ropac",
    "Gladstone", "White Cube", "neugerriemschneider", "Esther Schipper", "Buchholz",
    "Matthew Marks", "Paula Cooper", "Max Hetzler", "König Galerie", "Perrotin", "Petzel",
    "Eigen+Art", "Tanya Bonakdar", "Sadie Coles", "Konrad Fischer", "Karsten Greve",
    "Templon", "Almine Rech", "Peter Kilchmann", "carlier gebauer", "Capitain Petzel", "MASSIMODECARLO",
]

MID_TIER_GALLERIES = [
    "Capitain", "Nagel Draxler", "Barbara Wien", "KOW", "Kraupa-Tuskany", "Galerie Crone",
    "Sies + Höke", "Meyer Riegger", "Galerie Gisela Capitain", "Nächst St. Stephan", "Johnen",
    "Contemporary Fine Arts", "CFA Berlin", "Kleindienst", "LEVY", "Whitestone", "COSAR",
    "Loock", "Klemm's", "Anton Kern", "Produzentengalerie", "Jo van de Loo", "Rüdiger Schöttle",
    "Petra Rinck", "Bartha", "Michèle Didier", "Robert Morat", "Galerie b2", "Kicken",
]

IMPORTANT_MUSEUMS = [
    "MoMA", "Museum of Modern Art", "Tate", "Guggenheim", "Centre Pompidou", "Pompidou",
    "Whitney", "Hamburger Bahnhof", "Kunsthalle", "Pinakothek", "Stedelijk", "Moderna Museet",
    "Ludwig", "MACBA", "Reina Sofia", "Serpentine", "Haus der Kunst", "Kunstverein", "Städel",
    "Sprengel Museum", "Kupferstichkabinett", "Albertina", "Metropolitan", "Art Institute",
    "LACMA", "SMK", "Louisiana", "Kunstmuseum", "Neue Nationalgalerie", "Nationalgalerie",
    "Deichtorhallen", "MdbK", "Museum Ludwig", "V&A", "Victoria and Albert", "Städel Museum",
]

AWARDS_SEARCH = [
    "turner prize", "golden lion", "goldener löwe", "silberner löwe", "silver lion",
    "leone d'oro", "hasselblad", "macarthur", "wolf prize", "praemium imperiale",
    "preis der nationalgalerie", "käthe kollwitz", "wolfgang hahn", "max mara",
    "meret oppenheim", "prix marcel duchamp", "lichtwark", "villa romana",
    "villa massimo", "aachener kunstpreis", "max-und-moritz", "kandinsky prize",
]

BIENNALES_SEARCH = [
    "venice biennale", "venedig", "biennale di venezia", "documenta", "manifesta",
    "skulptur projekte", "whitney biennial", "berlin biennale", "são paulo",
    "sydney biennale", "istanbul biennial", "gwangju",
]

TECHNIQUE_KEYWORDS = {
    5: ["unikat", "monotypie", "handabzug", "monotype"],
    4: ["heliogravüre", "heliogravür", "heliogravure", "photogravüre", "photogravure",
        "holzschnitt", "woodcut", "aquatinta", "mezzotint", "kaltnadelradierung", "kaltnadel"],
    3: ["radierung", "etching", "lithografie", "lithographie", "lithograph",
        "linolschnitt", "linocut"],
    2: ["siebdruck", "screenprint", "serigraphie", "c-print", "pigmentdruck",
        "inkjet", "giclée", "giclee", "fotografie", "photographie", "photograph",
        "s/w-foto", "algraphie", "handoffset", "handabzug"],
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

def _search_ddg_quick(query, max_results=10):
    """DuckDuckGo HTML-Suche — gibt Liste von dicts {title, snippet, url} zurück."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        html = _fetch_url_quick(url, timeout=15)
        if not html:
            return []
        results = []
        # Titel extrahieren
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        # Snippets: <a class="result__snippet" href="...">TEXT</a>  ODER  <td class="result__snippet">.....</td>
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', html, re.DOTALL)
        # URLs
        urls = re.findall(r'class="result__url"[^>]*>([^<]+)<', html)
        n = min(max_results, max(len(titles), len(snippets)))
        for i in range(n):
            title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
            res_url = urls[i].strip() if i < len(urls) else ""
            combined = f"{title} — {snippet} — {res_url}"
            if combined.strip(" —"):
                results.append({"title": title, "snippet": snippet, "url": res_url, "text": combined})
        return results
    except Exception:
        return []

def _fetch_wikipedia(name):
    """Wikipedia-Artikel (DE bevorzugt, dann EN) → (plaintext, url)."""
    for lang in ("de", "en"):
        slug = urllib.parse.quote(name.replace(" ", "_"))
        api = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
        raw = _fetch_url_quick(api, timeout=10)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if data.get("type") == "standard" and data.get("extract"):
            text = data.get("extract", "")
            url = data.get("content_urls", {}).get("desktop", {}).get("page",
                    f"https://{lang}.wikipedia.org/wiki/{slug}")
            full = _fetch_url_quick(f"https://{lang}.wikipedia.org/wiki/{slug}", timeout=12)
            if full:
                text = text + " " + re.sub(r'<[^>]+>', ' ', full)
            return text, url
    return "", ""

def recherche_artist(name):
    """Webrecherche (Wikipedia + DuckDuckGo) → RMTP-Schätzung + Fundstellen."""
    import time
    findings = {"R": [], "M": [], "T": [], "P": [], "raw": []}
    r_score, m_score, t_score, p_score = 2, 2, 3, 2
    is_blue_chip = False

    # ── Wikipedia (verlässliche Primärquelle) ──
    wiki_text, wiki_url = _fetch_wikipedia(name)
    if wiki_url:
        r_score = max(r_score, 3)
        findings["R"].append("Wikipedia-Artikel vorhanden")

    # ── DuckDuckGo (ergänzend) ──
    queries = [
        f'{name} artist gallery represented by',
        f'{name} exhibition 2024 2025 museum biennale',
        f'{name} auction price print edition',
    ]
    all_results = []
    for q in queries:
        all_results.extend(_search_ddg_quick(q))
        time.sleep(0.4)
    findings["raw"] = all_results
    ddg_text = " ".join((r.get("text", "") if isinstance(r, dict) else str(r)) for r in all_results)

    combined_text = (wiki_text + " " + ddg_text).lower()

    # ── R: Reputation ──
    bc_hits = [g for g in BLUE_CHIP_GALLERIES_SEARCH if g.lower() in combined_text]
    if bc_hits:
        r_score = max(r_score, 5 if len(bc_hits) >= 2 else 4)
        is_blue_chip = True
        for g in bc_hits[:4]:
            findings["R"].append(f"Blue-Chip-Galerie: {g}")
    for gal in MID_TIER_GALLERIES:
        if gal.lower() in combined_text:
            r_score = max(r_score, 3)
            findings["R"].append(f"Galerie: {gal}")
    mus_hits = [m for m in IMPORTANT_MUSEUMS if m.lower() in combined_text]
    if mus_hits:
        r_score = max(r_score, 4 if len(mus_hits) >= 2 else 3)
        for m in mus_hits[:5]:
            findings["R"].append(f"Sammlung/Institution: {m}")
    for aw in AWARDS_SEARCH:
        if aw in combined_text:
            r_score = max(r_score, 5)
            findings["R"].append(f"Bedeutender Preis: {aw}")

    # ── M: Momentum (Aktualität; jüngste Jahre stärker gewichtet) ──
    very_recent = any(y in combined_text for y in ["2025", "2026"])
    recent = very_recent or any(y in combined_text for y in ["2023", "2024"])
    _mpts = 0
    if recent and any(k in combined_text for k in ["solo", "einzelausstellung", "solo show", "solo exhibition"]):
        _mpts += 1; findings["M"].append("Einzelausstellung (aktuell)")
    if recent and any(k in combined_text for k in ["museum", "kunsthalle", "kunstverein"])        and any(k in combined_text for k in ["solo", "einzelausstellung", "retrospekt", "survey"]):
        _mpts += 1; findings["M"].append("Museums-/Institutionsausstellung")
    _bi = [b for b in BIENNALES_SEARCH if b in combined_text]
    if _bi:
        _mpts += 2 if recent else 1
        findings["M"].append("Biennale/Großausstellung: " + ", ".join(_bi[:2]))
    if "retrospektive" in combined_text or "retrospective" in combined_text or ("survey" in combined_text and recent):
        _mpts += 2; findings["M"].append("Retrospektive/Survey")
    if recent and any(a in combined_text for a in AWARDS_SEARCH):
        _mpts += 1; findings["M"].append("Aktueller Preis/Auszeichnung")
    if recent and any(k in combined_text for k in ["now represented", "represented by", "joins ", "wechselt zu", "neu bei der galerie", "signed by"]):
        _mpts += 1; findings["M"].append("Neue Galerievertretung")
    if recent and any(k in combined_text for k in ["auction record", "auktionsrekord", "record price", "sold for", "rekordpreis"]):
        _mpts += 1; findings["M"].append("Auktions-/Markttrend")
    if recent and any(k in combined_text for k in ["art basel", "frieze", "art cologne", "armory", "fiac", "art düsseldorf", "abc art"]):
        _mpts += 1; findings["M"].append("Messepräsenz (aktuell)")
    if very_recent and _mpts:
        _mpts += 1  # Bonus für sehr aktuelle Aktivität (2025/2026)
    if _mpts:
        m_score = max(m_score, min(5, 2 + _mpts))
    elif recent and any(k in combined_text for k in ["exhibition", "ausstellung"]):
        m_score = max(m_score, 3)

    # ── T: Technik ──
    for score_val, keywords in TECHNIQUE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined_text:
                if score_val > 3:
                    t_score = max(t_score, score_val)
                elif score_val < 3:
                    t_score = min(t_score, score_val)
                findings["T"].append(f"Technik: {kw} (→ T={score_val})")

    # ── P: Wertsteigerungschance (Upside) ──
    # Profi-Logik (ArtRank PASSRS / MoMAA): Potenzial = Karrierestand
    # + institutionelle Anerkennung, die dem Marktpreis vorauseilt
    # + Top-Galerie-Förderung + Marktsignale. Alter ist nur EIN Faktor.
    deceased = ("†" in wiki_text) or any(k in combined_text for k in ["died", "gestorben", "verstorben"])
    birth = None
    for pat in [r'geboren[^0-9]{0,14}((?:19|20)\d{2})', r'born[^0-9]{0,14}((?:19|20)\d{2})',
                r'\*\s*((?:19|20)\d{2})', r'\(b\.\s*((?:19|20)\d{2})', r'\(\s*((?:19|20)\d{2})\s*[-–]']:
        mm = re.search(pat, combined_text)
        if mm:
            birth = int(mm.group(1)); break
    p_score = 2  # Basis
    # Karrierestand (ein Faktor, nicht dominierend)
    if birth and birth >= 1985:
        p_score += 2; findings["P"].append(f"Junge Position (*{birth}) → Karriere-Upside")
    elif birth and birth >= 1975:
        p_score += 1; findings["P"].append(f"Mittlere Karriere (*{birth})")
    # Kernidee ArtRank: institutionelle Anerkennung eilt dem Markt voraus
    if m_score >= r_score + 1:
        p_score += 1; findings["P"].append("Momentum > Reputation → Anerkennung eilt dem Markt voraus")
    # Top-Galerie fördert (noch) jüngere Position
    if is_blue_chip and birth and birth >= 1975:
        p_score += 1; findings["P"].append("Top-Galerie-Förderung einer jüngeren Position")
    # Marktsignale
    if any(k in combined_text for k in ["emerging", "rising star", "unterbewertet", "undervalued", "one to watch"]):
        p_score = max(p_score, 4); findings["P"].append("Signal: emerging/rising")
    if any(k in combined_text for k in ["sold for", "zuschlag", "hammer price", "auction record",
           "artnet", "sotheby", "christie", "phillips"]):
        p_score = max(p_score, 3); findings["P"].append("Aktiver Auktionsmarkt (Nachfrage/Liquidität)")
    p_score = min(5, p_score)
    # Deckel: begrenztes prozentuales Upside an der etablierten Spitze
    # (nicht bei jungen Positionen — die können trotz R5 noch steigen)
    _young = bool(birth and birth >= 1975)
    if r_score >= 5 and (deceased or not _young):
        p_score = min(p_score, 2); findings["P"].append("Etablierte Spitze → begrenztes weiteres Upside")
    elif deceased and r_score >= 4 and m_score <= 2:
        p_score = min(p_score, 2)

    for key in ["R", "M", "T", "P"]:
        findings[key] = list(dict.fromkeys(findings[key]))

    total = r_score + m_score + p_score  # Künstler-Score = R+M+P (max. 15)
    liga = liga_from_rmp(r_score, total) or "Liga 4"

    # ── Gesamteinschätzung (Prosa) ──
    def _top(key, n=3):
        return [ (x.split(": ", 1)[-1] if ": " in x else x) for x in findings[key][:n] ]
    _r_lbl = {5:"herausragende",4:"hohe",3:"solide",2:"im Aufbau befindliche",1:"geringe"}.get(r_score,"")
    _m_lbl = {5:"sehr starkes",4:"starkes",3:"moderates",2:"verhaltenes",1:"geringes"}.get(m_score,"")
    _p_lbl = {5:"sehr hohes",4:"hohes",3:"moderates",2:"begrenztes",1:"geringes"}.get(p_score,"")
    _seg = []
    _rev = ", ".join(_top("R"))
    _seg.append(f"{_r_lbl} Reputation" + (f" (u. a. {_rev})" if _rev else ""))
    _mev = ", ".join(_top("M", 2))
    _seg.append(f"{_m_lbl} Momentum" + (f" ({_mev})" if _mev else ""))
    _pev = ", ".join(_top("P", 1))
    _seg.append(f"{_p_lbl} Aufwärtspotenzial" + (f" ({_pev})" if _pev else ""))
    _tev = ", ".join(_top("T", 1))
    _tnote = f" Druckwert des Blattes: T{t_score}" + (f" ({_tev})" if _tev else "") + " — fließt nicht in die Künstler-Liga ein."
    summary = "; ".join(s for s in _seg if s) + f". Künstler-Score {total}/15 → {liga}." + _tnote
    if not (findings["R"] or findings["M"]):
        summary = "Wenig belastbare Web-Belege gefunden — der Vorschlag beruht auf Grundwerten. Bitte manuell prüfen und anpassen."

    return {
        "R": r_score, "M": m_score, "T": t_score, "P": p_score,
        "total": total, "liga": liga, "isBlueChip": is_blue_chip,
        "summary": summary,
        "findings": findings, "snippets_count": len(findings["raw"])
    }

# ─── Page Config ───
# Favicon als base64 eingebettet (funktioniert überall, auch Streamlit Cloud)
_FAVICON_B64 = """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"""
_FAV_CEAL_B64 = "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"
try:
    _page_icon = Image.open(io.BytesIO(base64.b64decode(_FAV_CEAL_B64)))
except Exception:
    _page_icon = "📓"
st.set_page_config(
    page_title="Trüffelkunst",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Passwortschutz (nur in der Cloud aktiv) ───
import os
_app_pw = os.environ.get("TRUEFFEL_PW", "")
if _app_pw:
    if "app_unlocked" not in st.session_state:
        st.session_state.app_unlocked = False
    if not st.session_state.app_unlocked:
        st.markdown("""
        <style>
        [data-testid="stAppViewContainer"], .stApp {
            background-image: linear-gradient(rgba(18,26,22,0.14), rgba(18,26,22,0.38)),
                              url('https://www.griffelkunst.de/galleryimages/_xlarge/263C1-91ROTH.jpg');
            background-size: cover; background-position: center; background-repeat: no-repeat;
        }
        [data-testid="stHeader"] { background: transparent; }
        </style>
        <div style="display:flex;align-items:center;justify-content:center;min-height:48vh;">
        <div style="text-align:center;max-width:360px;">
        <div style="font-family:Cormorant Garamond,Georgia,serif;font-size:2.7rem;color:#F2ECDD;letter-spacing:0.02em;text-shadow:0 2px 10px rgba(0,0,0,0.55);">Trüffelkunst</div>
        <div style="font-family:Georgia,serif;font-size:0.8rem;letter-spacing:0.22em;color:#DCC78F;margin-top:1.0rem;margin-bottom:1.4rem;text-shadow:0 1px 5px rgba(0,0,0,0.55);">SAMMLUNG BODMAN</div>
        </div></div>
        """, unsafe_allow_html=True)
        _col1, _col2, _col3 = st.columns([1, 2, 1])
        with _col2:
            _pw = st.text_input("Passwort", type="password", key="app_pw_input", label_visibility="collapsed", placeholder="Passwort eingeben…")
            if st.button("Öffnen", key="btn_app_unlock", use_container_width=True):
                if _pw == _app_pw:
                    st.session_state.app_unlocked = True
                    st.rerun()
                else:
                    st.error("Falsches Passwort")
        st.stop()

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


# ─── Externe Sammlung (nicht Griffelkunst) ───
_PFROMMER_IMG = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBAUEBAYFBQUGBgYHCQ4JCQgICRINDQoOFRIWFhUSFBQXGiEcFxgfGRQUHScdHyIjJSUlFhwpLCgkKyEkJST/2wBDAQYGBgkICREJCREkGBQYJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCT/wAARCAI0AiIDASIAAhEBAxEB/8QAHQAAAAcBAQEAAAAAAAAAAAAAAQIDBAUGBwAICf/EAE8QAAEDAgQDBQUGAwYDBgUDBQECAxEABAUSITEGQVEHEyJhcRQygZGhCCNCscHwFVLRFiQzYuHxF3KCJTRDU2OSGCeDosJzo9JEdJOksv/EABoBAAMBAQEBAAAAAAAAAAAAAAABAgMEBQb/xAAyEQACAQMDBAICAQMDBQEBAAAAAQIDESEEEjETMkFRFCIFYUIjUnGBofAGM5Gx4WLB/9oADAMBAAIRAxEAPwD0mvUaJJHTpSZKCBIOnntXA6RJEdU71T+0/iO/4V4WdxTD30NPNuABSkBWY5VEJg9SB56VzpNuyLbsrsuAXHnO1GUoq2OfrPKvNrHbnxnbPlLzdvcJBIGVgpCuhEzMa6edSVr25cUrYDirK2Uo/wDmQkDqCAiZPl1rb40/Rg9VTXk9Bd6VJgqAHXpXZkjQpTPU1grXbdxOSpZsbMIiACqYPOTkpNrtt4wQlCXbLDFHMo5YPiTJKUgxoQMoJ1mCY1gP4tT0Hy6Xs37KgiVD0rkBKMy0gnNrPSsGPbtxI4pShYW7KOQJSsJ05+EGKSf7eeLg9mawnCe6gnunc+YmNNQev0pfGqeg+TTfDPQPeke8nN5kVwdVM6nrXny17fuLlW1yH8MwTv8AdlbIcCR5KBUZHxFPW/tBYyyfvuGbZU5cqkPEa5fFM+e3l50vj1PQ1qYezdi4lI1QqfKhDmYQVH0NYYv7RWJJabUeEGlGPH/fCE7j3RlM86TX9pS9Q6+RwelTYENH2shWbln8MAb7TS6E/Q+vH2boQdiJNEBcKh92rL1rE/8A4l1hAC+DniSRteRpz/CdfL60CvtILS2pTXCz4AAyJN0mD6+GZ35fnS6M/Q3Wh4ZuOwkJV/WuBkjWD1PKsVP2jworI4Vu05UCMzqfGufIaDeis/aRYK8t1w1dtjQy26klWuoiNI38/KjoT9C60fZtqjmOYEE+QiaLmkyrNpzrHEfaSwhDqg5gmKFAVCSEpEjkd9PlSi/tNYEFQjA8WdTJBUkIEb7gnn+vlR0pLktVEbBqQCmTPlQgkamfUHasiZ+0lwzcf94wrFrdI2Km0mTzAyztP0pK9+0nw5aPFFrgeL36AAS40pCUgnlCyCT8IpdOV+B9SPs2IKEGFGaDMFjxHXrWLf8AxO4KZI4Ux+fNy36f8+1OLf7TvDKyj2jAuIrYHcBlpYHyXR0peg6kTXVlCZSkCOpFAiNdI5TWZf8AxGcDeFJbxqCdf7gfAOp8W3p0Ncr7RXAWRSw9i+kQn+Hqk+mtLZL0G9PyaiFIcJECfpQyIhBKfhWZNfaC7PlBPeYhiLM7lVksxp5T6aU7V299nQZbcONPALTmATZuqV6EBMg+R5RU7H6C6NBJB8KiQeh3NAt0pRlQAPMHasyH2hezwLVGLX0AkGMOfOaP+nUU7R27dnbyW1jHVoC9AF2jySNJ1GX6mnsfoNyNAbuCTBE9fOjJdMlIUB61nzPbd2dvIUscSpQkLyHNaPgz/wCzbzpye17gTulkcRsKSkgEltyNdvw+vyNPZL0G9ey9JuSgEEE+popdkyAdecbVQF9tHANv3Qd4mt0qXGhacJRMQVeHwjUb9ddqVPbP2fo0XxTh7cmCVd4I9ZTp67UbJeg3R9l5UtQEySaKhaUoiQgkzAHOqmntQ4KWh1aeJcPKGQVuujNlbGmqjEDcb9R1pRPaRwku0F83xDau22cILzYUttMkCSoCAPEkTpGYeVLax3Ra8yjpmKuoFCVEn3gDtE71XX+OeF7dwNO8Q4SFlQRHtSJn50ta8U4FdvOsW2MWbjzJAdQlerUpzAq6AjUHSY50rDuidJJEFwekb0UuFR0gxzNQ7fEWCu2ftjWK2rtslIX3qXMyVJOykke8NRqJ3o/9o8HJukpxOy/uc9+SsQ1G+bpFFguS4eUgQqSOWlE70qEDn51BXnG3DGH3Tdrd8RYPbXC9Q07dISVaaaE1JNYhZOth/wBttXEK0StLySlR6AzRYLjwuKnc+hFcFCfDCfMA1HrxnDWkNLcxC2Qh0w2VugZ/TrS5u7ZKkoU82FKjKCqM3IR12+hoC44Cko/GI8qEuJUCSsGec71FLx7CWQVPYphyUid7hHKZ5+R+VLWmIYdiBPsl9avk/hZcCjy6etFgH6HiBBSYGwiuL7hMpBEeVNWbyzfCgy+yooUUnKsGFDceu3zo6723Za7xVywlAMZlOQJ/rRYBdMkTsr0oAtJVGYyeQpp/FMPURN7YFY1Evp6770W4xWxtSn2jEMPZkFQzPJSSImdT0osIkCqCP60UqSTBcAjUADc+tRaeIsFV3QGK4avvwC0RdNnvARIy66z5TNHaxrC3kBxrGMN7sqICk3DZEjcTPLnRYdyUKiE7mPM6VyXU6JKin0O9Ry8ewlAUV4xh4y6KzXKBl9ddKBGN4W84hprE8PW6r3UJuWyoz0E0rCuShdRoAR6mu71M6EmeQ1qNaxrDF54xSwVkUUqAuW/CraDrp6Uo7jGH2rXeO4hZNJP413CAD8SaLASQcEe/QpOdOplNQQ4nwQ+EY1g5V/8A3jZJ/wDuo7XEeDLUcuMYaqN4vGz+tG0MEs+jvh4SKbm0UFZyFz1FMf7UYOg5jjWEp8jeNf1oh4xwVKZVjmDhPU3zQ/8Ayp2C5IgFJ8IVJ8t6UKFEDwweZNRiOK8LeKgzi2FrUInLdtnL0nxabUf+N2pgnErDXYe0o/rRYdyUSkJQnKAP1opyiZCf6VGqx6wSY/iGHTtpco36b0CMXs3ycl/ZLyaqy3CDl9daLBckErAEAwJmJrivUgwZ5kVGOcQYO0ooXi+GIVEwbxtJj50VfEWCNZlKxrCU5dwq8bET18WlFmFyRWoTABkcxQgTuJHSd6jGcewl93uWMYw51w7IRdtqPyBp0MRswYF5anr9+nT60NCuOgoAgSPhypQFKuYPrypim6Zec7tm5t1L18KXEqVp5b05QD/MI8qBi8I/mHyrqIEoj3BXUAJahQMmR0NZr9oNSh2cOkJmMRs51IkKcy/LX6VpEpUdzt1rNvtC3DbPZm+FqdSXb23bBQJVmKjl/wDujWtKXciZr6sxbu2+9K8gzETJHi+e9KABCCTCEpnnAj41As4+u2T3V3ZuofQI0EZj6ULVjiWLBLlw6GbeJCEncfvrXs9RPhHzzptdzJ5VxbrGjzRn8IUCKUCm1aoAUB01qDHC1qkEKdKZOhIBqEvLQWV+5bslZCSIMamR5etJzlHLRUaUZYUi8ZQqRHyG9JvWzb4hST5HUx+/6VSl3F7ahKXHbpqOSiRRRf3ImLp8f/UM/nUOv+ilpXfEi8MMssq8II2BgjUUJtkqAhRiRoRqTyqj/wAQvCB/eH45/eH+tL2+OYhbKlNx3qRulzUR+f1oVdehvSy5TLi/blJkjwqmOppi5aPkL7l1IBjRSNPzpnY8UtrGW8bLRj3wSsf1H1qeRiWE+zodtrlu5KkjMhZy5VeUHWPOK1UoyXJi4zg8oiFWeIJVKfZ3NNAZGv5VCu3t0w+UvIAKTq2tOk1bkuJWklBSBMgA5kn0NI3FizdAB9tCwNidVT5VMqd+BwrpP7Ig2uJELaU3c265Oymjv8K5WO2C4lh1R+GnWnrnDNmSShTqQTPv7Ugrhdj/AM56PMCKjbUNd9F5Gj+PoKVIbtgpJ90udP8Aeo9y9WsKkwSZOXSKm2OGbQypb7xTvAEH60qjAsPSc4Qtc8lKn6VLpTfJa1FKPBXPaSE5SSZ01NKN+0v+FplS9dQhNWdOH2aAQbdjN0KQTThuGgEIDbaU6eERTVB+WJ6pWwiCZwG6dI71aG0R6mpZnB7G2RlKO9BHvLOtKl0wrSfSkLm6Sw0XXAshI1gSfhWqpxiYOvUl5Du2VopXjRl6QNKT9gscpKWRPU6nnUGriO5Uo5GmwCdJkkCk14/drkZm0/8ATWbnTNY0qvsmXcLtnICbdIJMCJ2+VIKwG1SB4ikAnTNpFQi8UulyS8pI6AwKJ/enz/4rxV1lU1DnF8I2VOS5kTSsJwlKlZrkBXm4NK5pGCMq1dbKpmSSST8iKik2F4U+G2XBOwGtccPvAkzbqIGh0pN24Q9qtmRPKxHC8pSm4SkA7JBg+grkYhhY1VchWvn9NKrK2XGTDrTiQNdtKnxwBxGu3bfFgClacwSFiQN9eW3nR1JehKlH2PPbMIXB79gc9vzpN7FsNbGVCirkfAoz6aVB3mD4rhpSLvD7lidlFuQfiJFMQ/IBBB9BS6sg+PF+SdViuFpAy2oJEiS0NudMn8QYUythi3CGVkkpiAonmQNJ218hUf7xOsjnpRu8ABA101mpc2y401HKYUWrLuVCW0AzpCdj5fSnyMFxBy7N827dtXKp+/D6g501VM+VM23ihwLSdUK36EVPNcQW62/7w2tKwIGVMj1ohGL7h1Kk4q8UMLrD+ILizRbXeMPOsMpLbQgBSEkklOYAEp/ykx5aUhZWHE1hnNjij1uXVZlrS7JJgiZ8woz1qcGP4a2kIHeQOqDApZrHsOKtFhB/zoIAFa9KD8mPyavhFTu+G7y4Tlu3bm4SFFUKXmEmBoDO8ep60W2wi6sXGlW6nmgz40Q3qhREFQPXb0+NXtD1rc5i2426OUKzD/T/AHrgFhySpWo0SNvnT+OmT8ya5RRHP4stTj7mL3zlxkUyHVPLzd2fwnXby2pNxWPPPNOu47fOuMtpbbcU8sqbSBEAzoKvzoSE6pSokfiTUpgvBGEYqw3cYhcJZSpRMNrAJjlAEjWZM/OamenNI62/KMiGEXCnHHXLnVwyQCQVHnNSmGrvsJSRaX9wgyCB3pCZBnaYMyZEaiK3FHCfCIyIat7QgGAopkkb7H0pK67MOGrhoq7hbS1GEltyCOmlStO/Bb1aMXssRxvDG7pNvjNyhy5UVLWhxSSJUSRMnQEk+utP0p4mxxaF3PEGK9wlalkqfVJB3A1Eg6+W8VqDXZTgNsoqSbtwn3Q64JHltpUqngfCgES0+udMilc4/elXHTL+RE9U7fQyj2NVnbIQb29UhqShvvVJETOUARzn11pliL9zfW7jDycRdYdMr711eVXKTrzgfKtVx9HD/Dbea4tLUZyAnOmVGPUxyNVVfaL4ciU4e03/ACIbKgPKedOVOFzKFap5uyp2lsFqtwe/atrVAS22XFEDSARrpEmOlPU4JhzWbuGO5CkkLSlSgFg7lQmFfGamRx/nVOXDla6BVtA89aTxLiNrGQk9xZMKSZK2dFK+dChFIcp1L3ITEMGdfIbt3nUNIScie9UCJ1PPnAph7DiTAltd6hTZhCkPq0VAiNfIfIVOi4ZyD7xAy7eLfrQ+0MFo5lIg/hJBpSpwvcI6mouclZuWsavQpF5iGJXZUiIccUoJIEAjXlHOo+54SXcK7x9F06EpjMsZjPxq9277IQoIcbKlGNwNdP8ASlAcxzoUlc9Igf1pqjFjesl6M2PDti0kpUyc8aFaQI+EUKMGtUqCg1ASSUxrlPlWjlhJSFLZQrSCoo19Ypk/w9ZuxJWwsc0aj41L078FLWr+RSBhIKitSkmSCZEkgdetLOWgUsKSstpSAMqDAq1f2UQpXhulZR10/SjDhBsEZrtcc4TU9CXov5kPZUxbZJDVzcomJAX+/Ojeznug0H7spC84++I1iJj0q4jhSwASMz5KYJhXvUsjhvDoA7hU9VmZ9aa00iHrolISw4UFs3dyEkD/AMRXSOtCu2YUSpIUFHSQSnN1mN6vgwLDEmfZUGN426bUH9nsOICzbpjprVfGYvnRXspbwfxMd0pSliAO6ZGVEfy5RpG3yqSteC7EMA3TIU8TMEbdBI1q1MMW7B/u6WWucIFctKilRSlKuYA51UaCjyZT1spYRXnuHWFthhppbKCnKUsqKQRvBG3T5DpTRvgixbdORpwygpKVL0VO81PLdxUIX3dvaA8szyifoKj3bfiS4UfvWWgdwiB+YqnTivARrzeN1h5wp7TwTjFldYdcLZbS4gu96e8KvEAoJk6SAAYiYAr13gGIDFcLtb9OhfRng8txy9K8bWmHv2+I2zz9xcOXLKwUnvlBtJnQxsTXrfs8thbcFYI0DnAtUKmeuv61wayCik0jv0dWUm4t3LLJ6iuro9fnXVxHfcZeGYMz+VZJ9pgrRwLhKEq0XjtqFAHcZXD+cGtfBAiRp51j/wBpopTwHhZCspGOWxAHTK5WtJ/ZCn2syB+8DRVJTqSBIEgjlSasRcS6IED/ADJMgf6/pSIvrdVw4sDvkydBBn961zl8yspUG0AASBl28ififlXr7jwnB+hw3iKzAyETCcxEAEnmemo1pyw684wm6XaOIaXKUuxKFgdD6iody4bdScyFgIRJDem3rTe1x28w8n2NRaKwpJ1kQoQdNtRoaW+3IdHdxyWJVw2+Ch1AWggiHBmpm9g+HuhSi1k00Ug5fpUUzj76fCtpDgHMEppw1xIhM5rIg+SgY/rT6kHyLpVI9occLW5MN3DqZ1kpBo44VYB1vlzqNEChXxMy4CCy6SORgfrSQ4mbSfBbLJ6E8qV6Qf1xU8K26SM1y/McgNfSlmOHsObkLbW8erh0+VRy+J3N0W6QZO69AabucR4k4SpK20DeEok/WhzprhD2VmrNlptmGbVtLbLYbQnkNAJpZUqTkyqATyqlfxrEFSk3qzrJIAn8qTGKX5J/vb41o669Ga0kublwctg4rMta0EaAIURp5gVHP4fftKUq0vHF/wCR4yn4TUArFb+JN27PTQ/pThniHEmyAVpc/wCdER8RH7NLqxbLVGcVgmU2uLKLQ9rZQOYCJA9PPelH8OuSApd9cqVoDkCRP0pinipaW4VaKKyRsrT50a7xbGLlBYYs/Zyd1EzA8uX51W6PgnZO+bIdtWyffC7hRH/mOE5o6gU4QpISlRXyHP8ASoD+CuICVXF44hSyZyAkH40c8PMAZhcOSR72UGPhTUn6HKEG8yJe4vrS2QkuvDpoJ+lIs3tpeJKUrCxqkokgkR06RUa5w82w2t1d1ASM0hI2+dQ6VuAhbclQ1CgJI86iVRp5RcKMGsMnHOHWlLV3L60AGYUMwHoaBGC27WXvluOa8tB8akW34s2rl5YZKkBSvI6VGXeMWynDlS4SeYEf60SjBZFFzawSNnhrVw4G7Sy7xR1KUozH9/1qYPDmLI3sVpSCBGZOn1/etQeEY6bd8PWV6tm4gjXz5a6EHTStKw3tMtXbf+/57ZxBmPfQfORr8x8TQrCe7yUC7t77DVH23D79CTok91mSesFM1Hpx6zEiFjWDA1Fa25x/w2fuzdtuc4KSf00qFxYcBY8e9uW2EPqgd61nSox1gQfj0pyfpitHymUFrGbR5aR3pRvq4mNfWpuwx/EsKQ2bW8V3SR4WleNsJ6AHYelP04Z2d2ysyUuPAHUHvVx+Q+tL+3cEWUptsKecC/EoNsgA9YzGnH9ilb+I9te0RDjiWsUsW1MnTMklRGnQ6x6Gj3FxwNiq0G6smXCEgFxbCgY23AH+tDbcYcOsBDbeB+ztHwlQaQZHmAqakGxwpjalhu3Y7wGQEeBR840J06VSSJUmhiOA+BsRgMBCc0Qpt3Q+sHSmNxwBwOgOocu1NkAlM3Os8tJ/Snl92fsXCFKscR7r+dFwjMPgRBEefzqqYph93w7doYX7PdoIzSwvUDlKT5edLZFPgrqT9kg9wjwFbhSTf3rqoAAZWpQ+MCq7j2CYOtbTWBN3CMslx25cnvPIDX5+W1Efx+zbWcyVqUNCnKZn6CprhjjHArZJtb6zDzbrklSwJTpGx3jrPPaoapvBSnVWbFY/suvJq+lOuwSTP1pRrhdSkeO60G0JrSL/AIVtsTshf4CtpbaUnwSfGem+/rWeYleYvhr3dPWC7dSToVIKgfQp8J+tDp048ocZ1anDHFjgycPfLnflSgIjZJHP40/yicydvlqaq38ZxOI70hR5BA0p5hmHcSY26BaNXiuWdScqQD5x+VEaqWEglRm3eTJ/KkwTH/UdqbXCEN7FBn00/c0zxjhLH8CsFXl/cBCWVgKSHvdKjpGu53jeNdqrbinFqJW4tZJkyZJPxodb9BHTeblrLjX/AIi2+W8cqfs4+/ZICGcUcQ3yHebegnSqM1bO3CwhlpS1b6JpR+yftwC42W8xidyflS6z9F/HXG40Wy46vrYFK7m3ukAz95AVPqn+lWWx7QbR9tJvkOM5zBynOk+cjX6ViAbURmykecSBRmnHGSS24pMDcGJpdd+g+N6ZuOP4HhvF+FLQxcsuk+Jt0K2Pn8/z5GsixHgviDCs/teFXCkoUUlxpBWmeojWPOkrXH720dDucBQHvtkoUR8Ks+G9pmJMIyqvdIAyvozAehG3xpScZhHqU1xcorrDrBhxtxvWPGkp1ohEgT4j+VXTiXGMU4gsShy4SptRC+7bSAlWvUyfrVRSfZH4cZBy6KQvnWco2Z0RqbkIHIUgH4zXBMjwp+Mb1Mpxu3SfvMOQo6CdCY6aijLx9gaJsQmBoCRoae2PsjfL+0hUtqc0CSqDrCZp1b4ffqUFMtLQeRKshmpVviNgJkW6kmIOUDWk1cSpRq3bqPm4qPoKdoryTKc/7QE4djhUP7z83N+nKpbCmb62Dgvnw9mIPh1UOo29PlUH/F8TvFAM5UDo2mSPKTRXbfF7hGRXfrToQnMI+VXGSWUmZyg5q0mkWHFsaRhzHJbpByCdFHqfKohOP4o7LzdmlxvqlCjI9QaXseH33lIdxJZWQIS2VZtPM/pVibLaU5UFSRGwED0rVKUsvBi3CnhK5WRxLiIHjw8b7hC06dD/AFrlcWvJBDlgAP8AnIj5irQkoVorrGYmZorrTUCSDpsRJ+VPbJfyIVSD/iVtzjFEfdWip/zuDfntRP7YOSP7mmCRJLmw5xoPOpo2GFPDx21u5HkNa7+BYUdVWjGTlE0Wn7KUqX9pHO8W2ndKyofUtIMBSQAfjOnypEcW2xKiq2fEREQZ+PKpj+CYUCIsmV67RMj503XguEpJm2Y9E5hH1otU9iTo+mMv7U2JToHgYJjL+dFPE9iU6KdkHmj/AF2p4vAcL29l2IObMfF5RNJOYLhaQYtknmCVGflR/U9j/op+Rvw/jeH4pxlg2Guoe9nur5tp1SRGVJOsc9q9m2NszZsM2tsym3t2EhDaEaBCQIAFeNOGLS3w/i7Bb3DrVtF6i6DjRUqACAZB6aTrXs2yvGr60avGSA2+nOkHkDXmaxy3K562i2bfoh1H+b611J6fyKrq4ztEFQDqQOQJNY19por/ALLcPNye7XjrOcDcw04R+X1rZInTJoeVY99ptCv7G4K7KgpGNskf/wCN0aitafchT7WYdfYcM63rZYJmVIkT8KaM3q0KGcZwk8zTli6SV5lFCFAzBET6dKM/ZrvMq2iyFwRmKuVenbyjyFK2JDZ3ECttSG2i2Fc5nSmkztIJp6qwU2JVcNSdwNzSiMKQ7IS6ok7GBHrUNSZopRSwRqUmJA1nfYV2RUkEQDsZ2qdtsCtSYcuVn/LlCSfQmnbOEYSBlUHFkHUlZA0q1RkQ9TAq2XWCTIEyBQAaE9NNqtiOH8NdAyKURqcwcn60I4Ss1ye+eSehMjajoS8E/KgVAA6E6SelSODN2r15lu8pTshJ2UrpUyOEGA4B7Q6Uzr4RB+NPLTBbKxIebSoqTstSpkdfzqo0JXyTPUwcbIIbDD7gQq3bRlG6UwBTN3h7DikqbD8zonNIJ+FOcVYur8qtbVtxCSqFOKIygeUHrRmcEYYYQlZU8qNFFZgmeQrVxu7WOeM3FX3Ed/Zy2QQFOnPvAOg02mnbGDWds8hz2cKya+M/sU8dWzYMnMAlAGkwDNV3FMcXctFq3QWmj7yjufhUy2Q8Fw6lTF8Eve41bWwyKUEgkjKjWPOmCsYtFLUpThGw1Sr6aVFWtjc3hIabkDc7An1q28PcB2zb7VzxDd2zNqsHKyVlKl7EHTWN9Ocg7b59Sb4NXTpRVm8kJd480Ahq3OdxAIEj98qRjiG51RYX0qIjJbK/OK0u7xjhvB+6ZwywauPCTCIbQJJ8MgD46fGmKuPsXzhTTdoGxs0hskfnVWb5ZEZxWEinJ4Q4pxBOd6yebaiVLeUEBPmQNYHpypa3wq4wc3No/ap9qZcKFqGs7H5a7VZX+N8cfC0BVsyVaS23rPUZpg0XAuKGsDZuB7G48+s94p4LTMgECSRIg6yOtCjtdwnNyViq37QurYsA92kQoKAmo5ODOOjV5pJiR51PXDj1w+5dOFC3H1FZUEwASTI+tJ9ylMKygDmQNzz0pOKk7sIzlFWiQ4wVxGpfbA6waVTgBcJz3A0/yyQfnT5xTGbulOICZ1QVCaXBWMiAQpJkyBHyNCpofVn5Iw8PJMoTdeIciimdxhLrIWEEO5NVZdwPSp4pcPvgoB6pMHWkrh63aAIdbS4v4kc9aJQj4BVZIgG7i4t5T3zrf+VR1oiHn5zC4dzbnxGrG4tpaAHFI/ylWxn/AHFKosLVCCS03B0JgQTU9J+GadaPlFdTiFygeG4WZ011pdGOX7Z8TgcBOoUgRU6uxsnG+6W22CP5TBmq5fWrdvclLRzInw6zp0mlKMo5uEJQm7WJZjideXu7kugf5Vkg/A05t8csFPZM+TPsSmJNVpAGfnIGsihQw48lwpAGROYmJkU41ZDnpoPJaLm3w2+bBdWyrKoHwuAH86TRgmFl8FCC4jfKFaTUHh2DvYoVFspQEbqUdKk08JXKRPtjY/5QefStE3LKiYyiqeN5Y8PuX8KATh7vsoH4Uq8J9RtS93jmLXIGe8TlmSnukKED/mBjrVNe4ZxFkANlL2bWUqj6H40gcPxVAy9zcBHXMTP11pub8xJjTXMZF5tuMf4QsF5GHugCQHWwDvM6b/GjXnavcLa7m3XbW4nUoQTAjbp+dZ25aXDaSXbdxIGp8MaUkUqOoSY6xIrKVR+EbxoxfLuWLEOIRjas15c5z7ozCMomTA5Tz50di5scy15WCmMo151WUklMgzOggU+sLOyeaUu6ecSsaJSlP1/KiNRiqUoqOGThcQfcWlMfhSd+lHaUVgStWVJgzrNRBwrD0FITcvqG4hBP6UDeG2IHixIxMeExpVqUjHYvDJsZe8VIzJ/CBoBTe4tbZ5Ki5bsk5pk6ED4UW2tnmkJQxdFSJIHeozaHnM7E04QhZZJcKFLRooJnXlpVvKJbSwRVxgLLigpl4tCPd3HzqMucOuLZRUpOZA2WmSKtBa70QG1tkmNd9KH2dSZynYfWs+kpcGka84vOSr2OI3FgQEkqb2LZ2+HSpNeN2byQHmVKMwoFKT9ak1WpLQKmwT0iY+NcrCmggnI2SR7scvy61SpyWLjdWEndohvbsMdc8VuUkDUkb/AGaUUrB3RrlTyM6EegNSirK18SPZmztp3YEfGkXMCsnmpSyptZ2yqIM+lLY/0EZwXtDNNtgxGndL03K4pdLuD2qQpItUDTaFE03d4TuFQpp1ISRs6mD57UZvg9wAqXdIGn4U86lRmvA3Om+ZDr+PWCSAl0RP8AKdPPQU2e4nabzBplalSYUQE6fn9KUa4Vt0oLtxcrKQJ0AA+ZoqWuHmjqptwggSXCfWrvUXLsTal4uxAcR3b5UGLILMeaoHwiji/4hW191ZJSkGdGT+ppb+0tiygNsWzuX/KlKZ/WhTxbbAwq3fSnmQQoD60r+5ClF+IBG2uJbhJIebYBHLKk/QSKIeFXHDmur9S1q1MAqM+pNSDXEWHPETcd2TuFJI/Q0dWMYYiYumSDrpPOqtTfLM3KpF4Vv9CLc4SyKHdXOXrmAkH1EUCuHcSnIMTWUHcFa9vnUn/HsP1IuEA8iRJPwps5xPZNqKUhxzzQIHwmk1TXkanVfgVw7CHbJMe3OrQdShQEfXWKkdEpzKRlgczP5VX18WBP+DbTrrmMUH9qwoSq1VmkbL00pqrBYTE6FVu7RKXCbhavuHUspM5vuwo+XyqPubfFjJZv0rRt4mwJ+Vc3xPaOKyuNOtJUNVEA/lQKxezI+7u0wVe6sHT0puUZeSo05ReUG4EwzFV9oWBourlpTC3/AByjMlJAJmI11ivZWHWfsFmzbFST3SQgmBGleR+AEh/jjCe4X3qnHlJIROZUtrnbyr1tZW6rSzt2FkZ2mkIOXaQIrzNXZSwerpMptoefAfKuomY9PpXVyHYJZYUCDJ6RWU/aUZ73gGwyFOZONWYEkAa5xv01rVQSDKlR5Vk32l1qTwDh6QBC8atcxHKA4R8ZArWm/shT7WYiOF7gtkoeYUvkkg+L0NMFYRftv9yllWYHSDoacDiC8ASk5FFI3VzPXSDRHOIMRV7r4RyhKR+ZmvTbpnjpVvNhZHC104Atx5CDzBnT661GXFqbK5U2paSU7lBkUorELtwgru3id/fgfSkJg6nNB+J61DcXwawU1dyZYcDc9vZDbilqUgwVFOhEb1KHDmNYXy1AMfveodjH7S1Y7pllSI/ygD03py1xFZraPekMnUGUyfXSa6YSilZs4alOpubSwKMYBbsZltXN0hStfu1AAeg504GGuNwfbbkpgGRlBP8ArUNdcRpT/wB0YKyD77io+NNHuI795BQlxtvYEpRr8CZih1ILgFSqvkuC22pSnN4h73LTnTW/ubW1+6fuQguA5RMGOelUz2q7dBQH7hfUBZOvoKL7JcQpJtXU9fBUuu3wjSOlS5ZZE47YMJ0dccUkyCmSTv5VHXfEjjkeztKbgH/EM6eUVFezvAg9woSOYO1E7tSPCtKhuZIrKVWZtChTT9it1eP3Syp9wq/yg6Ckmk5lpASVmYgnfXzo2WABAI8zOlclAKgFGEkwrwyQPTnWVzoSS4Lk487wq73F5Z3GGuvtqSA6kLSpJgKAIkcwD6iiLxyzunAt6/LqgCAp13MQOgn4VUnFuLSlK3nHUI8DedROUdBr4fSkgg5iFaHkK1VZo5paaL8lqViWH5gEqQ4s+FKEiVKJ/rU/a8A4xfNIX39lZgHxBxKlFI+g6VnDZ7tU5WzyyqEgjzqwWPFqbNttCGX21iAVIX+u9XGqn3ESouPYrl3b7Mr1SktuY/adyTKg21qfSTpy603xvh/BsKaFhbPLuH0KlTillUa6hWgHPQAT1PKq5/bkrMrdvEqywYXM+W9J/wBpLJcqKnQfNH1q1KHsxlGrxtLBgvDqMSfVbh5DUQcpILih/lBPSfppU/iXZjY3FohFvibzUkSVpzBRnqAIqgOcS2gQCnMszMJSZBn9/SiXfHV47lKVXCymQlS3leGk5R8MUaVX0WD/AILXslSMatFSYCS0dPXWjO9jF4w2kN4+0l+ZyhsgEabQZqrf24xwIUEXryJ5hxWnSJNAON8ZcUkvPrcSCf8AxFAkR1n9KyvD0b2rE3cdmHEzjqWlXtu+0TOYOE5f+mJmobE+CMQwu4LLrrKnEpCiCMp1HQmaY3HE2KvpyC9dbTOiULVp6E0yF5cRBfdI5+M6mpbiapVHzYTdbUw4Wl5c6FQQk13iH4laf5jXZytZlZUeZO5NCUEmSRPSag2S9gpcdM/eK8jJmixJJOpGnpQhKtNyomIHM1YE8B8RKsDfGwKWYnxKAMegpqLYnKMeWQGYAbEDeiKWSnb6VLJ4XxBQ8XdgDc5pp2zwiSAXbmCdYA51apSfgzdemuWV9LzqPcddQJmEqKauXDd3c3NoEXCFlSYCVrHvjkdd+ddZ8PYfbeIpLqh+JZ0+URUi9dW9k2XHFNtpMAkwkRXRSpODu2cWorxmtsUJv4nZWxHe3LaSdpP5UzHEGGKV/wB4SeuhnpppFGGHYZfvLuwyHSuBnBkEDpyoLnhzCiO6AyqA99CtRVtzfBko0liVwl5j2HIQAlYe5+AST5f702/tHhwyZULQnnDex8zzoF8IWxPhvHUpIE6TApBzhJEAC9SN5KhuPKs26no2iqHFyQ/jOHZCQ40oGCRlyn4iPWm/9ocLZUpIbXl8myQfSmC+GSpxATfs93lGadyecU7RhGBsDK7ctqWNyXdd+YpKU/I3GkuG2O0Y1hxEB9vb8Ux6DSlHLnBLhISp21VpyIBOu1QVzZYOp5Rtr8JB3SNR8KiX0IQ6tKVhaZ0JG4pSqyXhFw08XlNotC8DtElRZxFds2dSEuQmoTEWmLYpLGKLuCdFALOnxGlNLOzTd3TTS1d2lSozlNWNvhS0SjO6+6sRMIVqR8RpUZmsIttUn9pXK2i7uGVhTVw8k6/jP60+ViuIut94JKBupLQ35VLm24esj/iMrO/iVnP570jc8SWzTRbsbeQDCQpACU+fWjZt5kDq7u2BEjF79BlVwsmRopI09NNK5eJ4jfEJS64B0ZTlH0HpTizxG2eeXcXdu5c3B90IAygRG3+9Tzd9cITDWDYgiB+C2gRyNJJPmRUnt4hdkBb4Di1+T3iHG0D8Ty4k0uOGsVa1buUJgaQ6QKnf4ldg5ThGLEzI/uxmOY9KO27iuVRTw9i3d8yLfxT6TWihT9mMqlZ+CHYsOI8uQYgtvLskkE+smjrwviRwqR/EVZTIkLygj5Ua54kcts7TmH3TLoBPduJymDz60xTxHijifCwhY8kK/MGn/TXkSVV5sh01wm+8pPt98XU/yhRVr6mnT3CdmtUspKYERmMfP51X3MZxVdwHe8Ugo1ShKITHp/WpCz4rygC5ZJUJILex/wCknTn1ojKn5QShW5THK+EbVMfeqKVc5OlHTwhZJazLcdUdfxaHXSlBxHh7oBLqUmNQpJBjprThGL2vgU3dsFR/Dmk+UVaVNmMp1lyNP7J4bABD8xyXr+UVHXXCrgWV2joU2T7ixqKsKrgAeEiNdc2mvP8AfnSRuF+GEOKJOX9+VDhBlQqVEVz+ymIEkS1l3melcnhW8WnMHWIOoAk6fKrY6oJtCFEpIETGWTUTaPLUzkQ4qUwSoH13rOVKCLWoqSRA3OAvW6c3fMr8tUyemtMH2HbcgOIKOckb/Gp25ClZW3C7n1Wk+8Nzvp5U8Crdp771TTjiwZBQYB8qh014NlXklkqCpnUbHnprSasuU+Lw7mrWplkE9+CZOgygJPT1ppcpZDiJZtymdcyQCN+m9Lp28mirX8D3sYWlvtXwEl3ID38CNvuVj5a17QWUgnQwdq8g9kzNn/xYwVTKWwhKXu8ynQktqAg7bmvXxgKJ1FefqMSsejQd4Ad2eh+ddXf9S66sDYTEczyrJ/tLJSezqzWYlOM2kAeecfrWr6AakeVZT9pJ0tdnDCRA7zF7NJnpmUfjt8q1grSQp9rPOixyJkRyO1FkpAB9J6CgV4jChI864pAGmUHmJrt8nACTmEE6zoTyFKNsuPu92gJWtR5HSkpkjSROhAiKOw/cWzveMrUlcEaCSRTS9g+MEz/Zst5e+uCgqG/Oekf607tsFw7uwqFLVuSTvVfuMVu7gpK3iYEaCJrk39ymPvV6VqpwXg5XSqyWZFl/h2HgEC2Rp5n+tKNYbZBvP7GyYOoUAfzqri/u0qn2hc/DegVfXZABfcI9avrx9E/Hn5kXdpxhnLk7pKj0Hy/SjPYj3cFRQUGSOn7/AKVQV3Dy9VPLJHVVJqWtW6lEDkTMfOj5NuET8LN2y6vcR2LJzF5JI/kAJ+FVjGL5F7dqcagIGoyiJJ3pgeZMHpQTuc08xrsaylVclZnRT08YO6BCyTBTv06UOck6aDY9KCBBBTvA11kUGoACUwKzNgSFEkg/LauJUmY+HSgyxuJPrXaQY8IHTnQBxBABkydNdaBeioOw28jRgokyFbnl1oWWXbhwMstqdWSPAgSaAClMAdaEqiNdJ013qet+AOJrpCXE4Q8kLAUO8GWRE02xPhHG8ICVXeHPJSdJQM+p221/Sm4tE717ImVKGm/OuKirTLr9KlLDAH7oJW66GER7oHiPwo15gDzX+A8l4RqD4TPTzqunK1yOtC9rkTmCp151YOHuCMT4kZNxZrt22gvu1KcX4gY/lGv5VDMpVaPhbtsVpSfccTpPyqxWPGSbJ7vmEuMEwD3cQP60QjH+QVJyXYrkhd9kOLsOoQzeWz5WRqUlIGmvMnSlF9juOoaWtNzZOLSkqCEhXjPSYp8z2pLAyKfSZ/EpBBmkkdol4HZbv0RyQpAj61rsp+zm69X0Uq/wHEcMuVsXFk626k6+EkHoRFMShaVwtCkHooRV2f4kau31OP3KVuq1JJ+NQOP3GHvEC30dCvwjQDn+lROnGKumaU685OzQywu+TY3AdW33idJndPpWhYV2gvWxypvPaGj7yFq1APSs2bsrl4EssuOAaSlMihcsrtA1tXoPRBIP0pQnKKKrU4TeXk2VvibhjEDN1aM94uCopTET1yzRjinDFo6hTDDSlJVOZSFKBH/L/rWJ5XEqyqzJIPuxFOTiF5kKDePBOgjOdelX12ZPSXd0zR8e4ntb492w0wyykgh1aUtnpA6DfSoG6fw3FGALh5hSJPiCx4Yqln3iZBned5/c0OWNQdJ1nrR8h8WBaNcplhca4bsnQsK74gkjuyVAeu9Ks4hg7qgg3N0ymPxLUBM9elVmDrqI6V2hMGRyGlT1X6Nfj4yy3u4db3JJYxO5QrYAuEianuAMOtba8ffxK7N04NGm+9BKRy8B111k+lZq2y64T3CHFLGso309Kl0WGO3MffOyE5h3ij12M+tXu3ZSMnBwVnI1TFv7G2C8t9Y2C0wJQ2gqIO+uSQPPWaqePq4NxNlpvDrK2YOYEqR4MoE6HqTI9MtVlzAr19IFzfJJSZIzSE+tIq4eCVZRdIKz1RAP71oe7yiLK3dkl1KwWySChq3zaakSfjQt4hhjkBYtUrSZlYAEczNV1WE3CDCVNrJE75T9aR/h13nKMgCgdyoQPQmh1ZJ8FxowlG+4u3d2V40FFFs4DzjQ9INdb4G3dOg5M4iTmeBAiY0Jk1VLVjE20hpl1SEyTlDgyzz0qRF1jICUrt2nYHJwa9edaKe7lGMqTjwyzK4Bwm6DVxiGKN2YInI0UgrnlMz9OdSdjw/2fYasAtKvFiQVOEuQPIR/XnVRRe36PGvDApWuiFgzB3FNnsRxRfhasCmeepjy/Z5VO2PIb5vCf+5o44g4cw5Ck2GHJaEwO7YDYgDz39aTXxy4pOS3s20nTVS8x09BrWWuWOL3xV3hUomJClAJoGrLGbNfdtSAjbKqR8BSUreC3Tf9+TUGuMrlACTaMrIM5sxg/MGhRxjdh4qdtm1A+9l0V8+tUBq+xhCU97aNuGY0JSfXbzp4nGUNhIft7hBUYJKcwT6xyrVNHPKE/wDJZL3G2sRvC7cYeyGsqoGUFWu0k+fy9ahn7lhsqzdy2FHc6adKTcxG11WpxGU9Ff1/elRd23gt253yngpaoGjgB9NT6U27cChBvuJQX1oSJW2FeoppduYKoj2hVpM8lCR8qYPcN2S2+8trkoBJ0V4v3zqFvsPXYOJSpYcziQRyrKdRrlI6KdKLdoyZMODhpQyoUJ8pEdN6g79m0S8E2jinEAeIq1APkaSkDadR86IrIST+QrnlPd4OyFLb5uBCQdAP61xUQZzGRsZ1FcTPzoANYAk1JpYV799SAhT7pSNklZgfCaBLziJhahO+u9FgpGqVCeZFBM6afCjIJJcBy88DPer9c2v51wurhHuuuD0UaIYABExQEigNqDKfeWZU64f+o0gSJ3nnO5o5nl6URY0gmgZd+xJKFdpeGpJhIaeJlObZIOnQ+fLzr2EsrUsnSvH/AGF26Xe0+wUufu7d9xJjXMEiPzr1+QSVAKSIO01yV+466PaGnzHyrq7KP5jXVgaiJSs65yf1rI/tMLKeAcPRr95jNsJ6ZQ4f0rW8qRrmI86yf7SqGx2d26lrgpxizUkRObVcjy0n5VrDuQp9rPOaj4tCAfWdaeYcm3U8C+JGspOk9KaHJ019aDSIGx0jpXenZnntXRYirDEJCXGEBWk5o/Wlre9wdnOO7tkkCRomfSqqmI00nWOVCVeEHYTrrV9Z+jB6dPyyVxm4w67IXa27aHSfEpCcoHrA/cVFp2Eq3oFeIkj4+dBJ3An10FZyludzaEdqsg0nQnT40BndR16zRQIgmImT0riSreBSKBI5x6azIrjoII+R2oIO/MbweVdOkzp1igAdIiNBroaAFUwRpuOdBITpmk7kVwURAIGYiNOdABlHnPKIIgxXAySEnNOkRrNBBHI9TrXSQZEAjUK5g+VCAf2eC3V8oBsJiPeOgT/rTx7hS5RATdNLVroUkT+9ab2+PXFu0G/F1zAxHppRXcfv1oSlKw2UiBlJk+etarp2OZqq5Y4HDPDq/ZnC6gBzN4VIeAHoUx+VXbhnEcP4ZwVAatUuYkAoB1SNlcyDO3TSdedZ2MVvG0lPfqAA01rl4reuGTcKUB8NfShSiuEEqdR8s0U8b4w+4FB9tlRmcyc0addtvKnFv2iYq2pxm9ZtbpAGwJQfM8x9BWYrxS8XoXvkIpIvOLkKdXJ13O1U6qIjprFvxXFDiN29craZa70RkaUeXMknUnmaaurZBlx5KkGCqCTFVaCTE7xzoVEncyBoZNT1S1p15J24xVhhCm7VRU4rnyBqEUcxUogGTMcpooUDpl1opKgNB9aiU3I2hBQVkcVAJ0O3SjLStIAUkiRIzCDHWlmMQurcNIS5LbKs6EKQCkHqQRB+NJFalkKUokiEyTJA6a1FiwBuZIjfeKFOVQIKdd81dA1I3nXSuHMjaKAJjCccNkyWHG5bE5TzH7NO0cTIEBQVr1qvbwevWhBCTqfDMz1rSNWSwjB6eDd2T93jtndaLt0OmNCpOo/frUC6pJWcrYyzI6miqECNuQNFPvRlJ8/OlKblyaQpqPBwHNSZ5npQFYBiNucUMEzrpyNCtRgAnpUlgGMsKTXTpJ0BOnnXE59zIB50A8Ok+I/GgA7T7zCittbjZ5FJialGuJrxtIS8A6TpJGpHr86iTqDpr1og30FOMmuCJwjLuRMKx/M6F9yoJ2gK/wBK5WNNOA5mFK05nSahzmmPjqN6HUwowI5VXUkT0YMkkYxBClW/LU5pJFLN4zaFJ7y2XAMgDWDUOQVGCRvJ02NconUjUxprSVRg6MWSn8YbKtGVASZIVShx5IRpbFKp94HWP35VDyAABtzPWhAjQT8afUkDowJtviMJOja0wImRQL4jW54ShZ5kZ4n96VCjmdNK7fcelN1ZMXx4ckmjGlIgJaBEajNvSn8fBMlopVzIO1RPUyYOwopzARFT1JDdGD8E4jFWlqQk3TqEgzlKdPnUgcRb7lI7xBBOmX8IqqGVDXaOdARI3k+lWqzREtNF8FldvLI5g8lvINAevlUBdhq4ulC3LaEESkLVAJ6etI5RMwJiKkWru3Uy02GW2ikZeualKe7kqNPYsZLQ52X4rbsOJssSbJCoW1myyRAJjTT3o0PKkkdmGKrJNzeMoCeeUn/SmNvjWKWbXdW2IOpaiQ3mzIA/5TIFTfDyMWx9p32nHV2Vm3KVlCEhXXSBpvvTSRnvfIk/2ZWNu2O+xG47yRKQEimVxwfgFuhRXjJhKZJUtBJ843+nKrZbYRwXZFZub62unFghan7lK1R5amaQd/4e2LvfpatnFz7qElY67aitNqJVSTZXrDs/w/FWhcWWLtXDA0KkpnKZ2OoNSKOzU2KVPM4hbAnUKWlSQUj5wae33aBgjDEWVmp9SQEoT/hpSOhn9BVE4hx9zHrpLz7wCESEsp8SUD9dt6l7FwUt8sEjibNjZ4dchm6t30Ie7tMNKAnnHI8zM1EIdbaQlC1AlSpIKIJB6afTyph3jfdhOdZOuw3+tC0WC4hLi4QZCiUzHoKzbTyaRi0h7faOlr7lJ3ylOidJnnqf0pK2s+8aVlRmKhlClEJg8/lpXOXNqq8Dy0/cKXK251On1504TjltaJi2bKsxM50gROwnny+VNWJbl4QzdtFlSUkNyYHh186eP4NFkALaXhzTpI6mmDuL3LqpSpCNTASkUi5dXJBl9zTzileJWybzcvXZRZJseOMLet3sj7wUgBYKvCqARA13Ir1lBWInQHavJ32fnnF9qVqlx9wq9ld8M+adZ9K9awQJIMda4tQ05YO/TpqOWBBrqDN/lT/7q6uc3EwkCJ36Gst+0e0XezQZY8GKWSjrBA7wjnz1rUCTOpBPkKy77R9wGezPKU5g9itkjcCIcKv/AMYrWHchT4Z5snMPeBMfEUHeDQwDy8qKogKzAafOgIk8p32rtZwINOaQRFCFEbDWem9EkCRp8ooQSBJM+RoAHbYfMUAUUgQmR5UOYmSRuOtFkaGdaAOzJJgCB5UIVAkCKKSJAAj0oJM6q0igAxUNRrpy610kHXQ8tKKSEAExl5ydqkLHh7F8SZS5aYZeOsqnK6ls5D/1bUWE5JcjEqGka6dK4qUE6EedSz3COOMNKduMPebbSYKijT57Uyewy7ZQFraOX+ZJmPWKrayVUi/I3Ggk/ShykyQAeelFTp56kGaMBJAyDXbWpLA0APhkk8uddl3IgRymaEAJnSNOddERJAB2mgDvCQBPyMUHukk7HmdK6TuR9a4qJ0ykn00oA5IEyIOs0YKjQjQnnRZn8MCPlXZgCY1/IUACqZJE6fM0OeQJ0PSikkpgCNdTQAgCSqQetAAnUAgCPI0EndQiNvSunwkAa9DXDeAPpvQAJUCRz3oEKJOUaDrNAVbyQBtBoRr08tadmAdRiCdfSuK4V4dxzmhAB1hJV86KInVJBHypWAUU4t1ZW4pSiSZVOpNcqSRA0HM0mPI+lHV7u8a6HfWgAwVJmCCKKRO4mOlBuCBHn6UXSQUq26CgASsjf5ETQgTBI0oJMk/hn5UBTmAzDQDcaa0gHFhYOX7wZbJzwSITIkddf61LI4WfdAX3gbREqSUyU/1qKt75VmWlWyO6dQmFqmQv4UdWL35BSX1p1nTStYuCWTKaqN/Vl2wDsyt8VR3zt8oNghSjMFKZjWJjnUwns0wW2eBVfWPdoIAWtYOuvKf061m5x/Ezam0OIXAtyc3d5/DO8xRW8YvLeIeGUbZkgiqU4ejGVGq1mRoz/ZbaupJtb3D7ltSjBCSCnXaQah8R7LsQZSVMW3tCEjU2zgVHOYPIVWWuIblshQTlX/M0cpqUsO0bGMPJDVy+tATGV0BwD56/I03KD8CjTqRIvEeEsWwoA3Fm8nNrCkEH+hqH8ckZYOxBFW/HePbjHkhi4dKWAQrIlqCSBOp1OhJgTFM2MFXjYbDFu4pbnuqACc3TTnWbin2mqqSj3ornMdfWh1P4hM1d7bsmxS48Kr6xt+qFrKiB5xQXPZNjbMLZfYuk+LRmZ09f1pbJei+tD2UtlhTrmRCZUT6aUrcWjlvBUULSTEo2FTquFsRwtC0vWFw2skBSlI132HypJCVtklMlGsCrVPGTJ1mnggCqNlCa4FQiREfzCDU8lCCmSy2s/wA+XWZ2P75UolhZdlREH+YTI8p/elHSK65XQqYkSaEkAzE/CKkMStGm094gpSZhSRsajlGRp5CsmrYNYzUldHEx5GgVqBFOrTDXLpBdLyG0gwJkk/CjLw3KNX515J/1qlBvIb0NEuOoPhVoNcv++lLJxB1EBWRYHVM0ZNi2VgFbhk6xApY4YxmjvHYny/pTUZEtxERibwCu7CUlfzpsta3DKllRMzJ2p+rCW5Ke9dB2AgUk/hzbLJc74picoWPePTShxkClHhDEHfn8aDaKHROnwNAd4OgqDQ7NodPrXGAZPpXdI+NEJ1oAPETP9aIfKZoSZ05mgHTegARAB1mhjpGu9FncVwJ0INAF77APD2pWpByRbvHN11SI8hryr1uACRBMDzryT2Eqc/4oYehoEksOZo5JlIn5xXrYajlXJX7jro9opr/IfnXUnkT/ACr+ddWBqEUCDIGvWdqyr7R7aFdmqVKCsycWsimeucj9TWqkSNJ+dZj9ohsq7LbkgxkxCyVP/wBYD9a2j3IU+GeZJgwdgI0opVrMGDpqda7OQdRtoQOlACCo7xOgrsZwIHMdx6VxJHu7cwaBIM8tPzrs3830oA6QqAAZ3Gm1BATCSoyBzBGtWPhHCcJxvEvY7m6XbFbf3aQqC4sTIzHQaagc+ukHVMP7PeGrdLaTh6Ftj/xXmgok8gSua0jTbyjKVXbyjB86fdJnX8KhRgtCT94MyAY8R1Nborh7hFlZ75jDs417tbTKQRMcx5eVFuLHgfDLZ25dZw9ttCCFLCGQdeQKRr8JPKjp/snrfooPCPEfCuEMuHEcMzPZpS4GA4QI0g7gzPLWd9KtQ7VOHhH9zcdMRDjWo+f5VmOKrwt65uHMPFw2hTiihKkwACeh2qPKiAdCRtRvaDpKWTXXu0/Ari2KXbZ5ROih3KDnTzBOfY/QgGs/YxVllxa3XlrTJA/ErLylW8xUAFdAAaFayBKToOulLqSYOhEcXl0i5uFOtshsHdIESfhScyNQJPQa0jmmIj8hFHTKleFPrFRybKyVhQEQZO3QUB00EkDmRRfWPWukaz8OdA7hgZEwIG+m1DoARO9FKiTAG9ApQSNJjeCN6ADyTPTy6UUK1Ec9IiZrhMHWB67UdtxKVpUqDqDG1CBhm2HFiUNnxaidIpxa4Yp+MziUxp1NFOIZT9ylIERrrQIxC4SVELMkidKtbTP7P9D8WNiyYc71eUQpRM/IU2Um2K1AMFsKiBBIA/OkziLiwQ4ls69INLW17Z5fvszao1VEifhV3iyNso/sbpW00spzIIIH4daBLrSV5ipSkjSAI+f0qUZuLJITlVbqypAGdAlXrS7WM2LC5IZM/wAiJAPyo2r2S5yv2kbbo718f3ZSxMytuBHmTT5vD7UlSnUMBJBISDBT6xSt1jlstDeTYQVgpOo8qYNXmFpXJs8w9CQB8f3pT+qxcn7vwx0bGwcCgy2VjUZgTpA5fKmJYHdpIQ37x2nN8qlrfEbR8pZaWUqjRJTlB9I/etFfw9bqQkiIEyDpvy/fOm0nwJTlHkiLpy3DPdtpJUDIUExApmTBywVeQ3q7YZwrd3iG22sMQEKIBcWjSDznzqxW3B9ph7ZVil9bWiRoEkDMYPIe99I86npX5Y3qVHCRlRtXSkKTbukdQkxQpt3jr3Luv+Q1tlna8KXyEguPN5CEKCnA2V6aGCakXXOH8Ct+9tmWSsaNAKStZPpM/E6flVdFJkvV+kYM60FGbdh9LcbLGYz6gCjM2F5dr7tmzuXVkaJS2a0BTri1rccSMylFRI2k7+m9WDhzHMLwa2C4X7QsQ6e6zmByTqBFVKjYla1vwZpa8EcQXye8bwu4QmYlYy/Q0pifAHEeGtB5zD1PtK2LJzEH00+laPc8fYgXyq3ZShvcBSiY6bR9KYX3GuMLaIacbYWgHK40VZm5/l1iY0nXeh0EJauTfBkygUK8QIMbbGgJOqQR6mrTe2rOI3RfvO8XcO6rWVmSY03+HypgbDDCopZSXClZQvMTMzymPP5Vg6bR0x1EWQp5aajnUvhfFOL4QctpeqLYTlDbzaXUJHkFgx8IpviVjb26lLYcEAjwBUj60xJiQTNQ1Y1jLcrk09xlxK8hDa8dxDukE5UJeKUidToI0/LYU/wjtHxzDAUOPG6bMCH5JHooEH6kVVgNOfxrid9dvkaE2gcIvlGnp7YGbqzNpd2DwIyyQpKkqI9RpPXWqU/ijLzjjzhSAtRV3bSMqZJkgAbDlUKCRoRt8K6QRPI1fUZCoxQ+uMSzyWU5U7gc6aKfdUfE6Ty0VApM76ADyNcYSNdfhzqXJstRS4BUsr95SiRzJoFab8zQFWmhNdm2A5a0ig6HnWsuV0gDYTpSqsQcgJ0V1URrNN9wolQCgJCdfFRMxGhM0JtCsn4HXtriTOVGmwihGIvJ1Pdg9SNTTXOIBHxopWDr5U9zDah6MWuUEErSROoI0PrTZ24cfWFLVmH4QDSKiSJkaU/Ywdx63S+VpGYE5c0Kj0oV2L6xyNMi+6U8Uw2lQQVf5iJj5A0SSoGBoOZ60/cwkNLShy8RECfAQBSzOBsO3DTXtiPvEFQVEAmevxqlTkyOtEhw5MxuacN2dy813iWjlndRifSnv9nb1PhytvtKJQl1pUwZ0meX9aZPIvMPWtl9t9goMFKgY/p/vS2tcorenwwzmHONLKFPMBQ0gq59NqKzh9zcupaaQlSyYCQrfzoibtYIMAxO4ncRTyxxpdm8HCwlwpIEgwQOm2tCSE3JLAdfC+IMt968GWmwTKlLmI9K5OA98T3N22oDScpifWpS84psryxfZ7h1tbg0CtUhU76GkcNeCmSUPJLih4gOWlbbIXsjmU6u28lYtHYVb/w3tSQ6sl6bFbENAmSpxBzR0Ea7V6oAUSSIivLHYmMvaQXFMPvfcqAhM/iTCj5COWtepkgJ/CT8687UpKeD1NLJuGQ+vWursyuivnXVzHSIwArQn0nSs3+0MtLfZXfJgkm9shvt9+j+n1rRQZ2j4Gs3+0Qkudll2YCcuIWRmf8A1kj9a1h3IUu1nl9SpIJj40CAXVhKElSidAATNCc2oA/1pW0u3LN9DzYEpkdJHSu62Tz/AAODguIhIWWkpCuSlihGB4iojIyk+YWNaeHiG3X4lMOBc7CAPSaQXxAvTuWG0KGmZRkEela2pnOpVvQyu7F+xITcISCfdKVZh8/lSS7t9TYbNxcKSNQkuKIHpJoHrh24WC6srIECRsPKKJ57+UcqydvB0RvbJwCInu06DUQNa5ITIUlKdtdIoAqCBMR9KEZnVZW8ylEe6BNLI725HNobMuD2oOZT+JCoy+o51JMWmEFY++WvrmX+mnlSFrw5d3IzLKWQRIz7mlzwo8VAB9oGNzWyhL0c06sG+4eOWGHFsLTaoImCoK08ue9GscMtEpU4u3ZCfwFUGfpSDPCuRpM32VShoEDQeuopG5wLFkHumXO/RPu54J84rVXXMTDDwpEyLa0OaLZlIGkQBSgbt0NkJabA3lI0qrOs4jh5SXUvNpTr7xIGvrSTmIXjhjv3VchB19KTq28D6HlMsr1vYOIVbrQ03mBAWmAUz6+lQy8Aue9ytFpxs6d5mAAHmP6URHDmJ3Ce8LSRAIha9fSlhwxfpATCSSZ8KhGnxqXeX8S4SUMbhteYM/ZtKdW40YOyVTNMWkqccS2iTmMARFSbnDOJDUNIWnr3giaXb4YugR3r7TSh/L4iKh02+EaqtFLLHuGdnHEmLW/fM2rSG4kd65lkabU/V2PcTBEpOHuK5th4yOnLWpHDcUxmztW7QYk8WUpCc2VJPlrvpS17juKtNlTd+6co/mkJ+FaqjG12c3ypXsio4jwBxPhkrdwt5xI3LEL/AC1qEfbet1Zbhp1lce64gpMehrQ7fjjH7Igs3q3B7xS62FCNtdJHzoMdxZ7ihDCr6ztgtqRoCSZjmSdNKjo34NVqGu5GdSmP9NhXSFT4p+mlWd7AWHUpR7MEEfiQdZpNPDlogy6t06aCQmKXRZa1ESvSJyyCDrFDA/m5fWrM1hmHNghtltSpgqWZ1o/8AtFlSjbwJ3BiBR0JB8mJVwpPnr15UcqnYgAbirY1w/hq0AFlZ5QVkzS6OH8JMoFrPSCfzprTyJ+XAqFq8lp9Dqmw4EKkoVpNSauI1BWlskz/ADEnTpUkOFrFObO86SSfDPu9NqZO8JLJhq7bUZ2UmDT6c44RLrUamWL/ANv8W78OtvuocCMgX3pBgagaDamh4puZzBlsuE5iSo6/Sm+KcPP4YwH1uocSTBAG3nUVEH3tSIrOU5xeTSFOlNXRODiq7lQ7psDloYpqriHEcpQh1Cc0+6jX01qPEHUq1HUzpXDwiQNZnTpU9SXstUYLhD7+M4glSv70vXpEflSn9ob/AE+8Sox/JBqNMGEzqOcUJhSPDpPTlRvl7K6UPRI/x2/IBLiSYnVOlAriC9y5CtJzHcCmBEJKjHn5milRAJKpnyjWjfL2LpQ9Dx/F712T33lp0pubh1cZ3CZGvQ0nPhE60UGCIVpPxmpbb5KjFR4DT4iddfrQiAnTn150UKCjqI8xyoToYpFBjAT/AEoI5AQDvpXFQzHWBXSD8KYHSZgesmuzHUAyKAmdY+NcInXT9aAOJInz86KIkGuWvaFc6KToSTOmoigAwPn8AaKSZmf9a6DGlcdRG0a/CgBT2R8gHuVwrYgSD8aTLT2py7aEaUKHltaIcUlPQH9KXS8hxP3iUhUaKGk+VNWJyIpt3ciVgJCVbeIaGgdZcYSlS4OaYgz8KkLe1U4ZSAoDcjWRThbFuwpLlysBpOqUqHvHkYqlG5k6rRCBC1yUoUrnoJp1bWWIPqHdIcBndRyx8al/4nbuNfcBKADBOkxTVd42gkLfQEmQr8RI/cU9i9i6smsIcW1jctqUq8vG3E5CnICVHTz02qRsbJhaO8CVpM6AHbqNetQz2PpCUBhgZkCM5MZvh8qMeKrnu0oTbMBCRsdauMoxMpU6ksonxahlX92LrIAy91MjfeJnr86PiFsV2ja3oVkgEqBJifKoBjitSHe9ds2yuIzJVBinquMbR0EKZuUmdJynfedf3NaqpCxjKjUTWBtiOFW4fGVKQCnwISn3ldD0FNMPwZvEFqQHFtQlJAiZJ3+UU9d4gwt77p2ycW2nUFQH5TpR2OIsNRkCUvJSkRt5+VZ2g3ybXqqOFkRu+DnmgO4uA5/MFIIgeVQr9ld2hzOtKQQYCxt86tDmO2VwtaW77uUZRBIgKJOo1puu+ZJIL6HE7anQxRKEPAqdWqu8tv2bHX1do99mW4tJwtWpOifvE16fEnmQPKvNvYI0gcfO3Fm1r7E4HkoggAkQSeWtejG3Y1IB+NeZqFaZ7Gnd4JoXzDor/wBtdRM3l9K6sDYSUorjOsKPM1m/2g1f/KnEec3lkP8A/YRWkyAZVCidhFZ52/JKuy/EG0hIU9d2TaSoSJNwjptzrWHchT7WeVyTryHKKCSdNYiKsbnCzJYCW7sJfgETqCY10ozXCLARL15nWNwgQI9N69N0JXPIepgiDw2xViNx3fettkCSVn8hzqaXwtZMt947euKUR7uUAfvQ1KsWGG27BZbS2psjWRJnrPI1G3KcCaUpDr6l7ZkqdkTGmn9K0VNRWTCVaU5YuitoaLz3dWwL4BMK6jr5VMWnCdzdNoWp1KUrE5k6gD5/pTr+0djbKy2to8pI3UDH50X+17aSB7M6NtlA1MY01yy5zrNWjEe2/ClkyUh5angACZMT9f0qRRb27Kh3TLaCZA0ExUS3xfZKblbbza06BBE/KP3rTC84pdckMIyyfeWJMDyrVTpxWDm6dao7SJy6xezsllt54IcAmIJ/So97imzS2vuguSdAGyBPxqsPuLuXVOrJzL3J/TyqTwfAk4ggvPv90zOm2ZXoToKz6spOyN3poU1ukJHHr4u96HEkyfCUCI6daVueJbt1wKaKGdIIyhfykGKk3LXhu1A7xAVlmJczE/XX5Uq1imCMBTae4S2RoEtAR8YmizXMg3RfECuv4teXTSmnH8yFbjKB9QPpSLLNwmLlltYDagrPEgfPerOMcwVsENpaBA1ORUH6U0xbiJm4s1W9olSSvQnIAmPzqXFc7jTe3hQsM2uI8QRILiFgHmiDThHFd02vOWWlEagUxwvC2b9QDl4hlR2QB4jUg5wm4RmYukLjkRrSTqWwElRi7NCDnFV86kqKWkKOygNqaqxq/cnNcKE/ygD9Kf2vCV2659+oMpB3jVQ9D8KnMH4V4faukOYpdXS2E6qQlBGY+onSmo1HyLqUYuyKiziN4yoLQ+oKB2IkUsviDEnWCyXypJ3hIkVp6sE7O2VF1GHLdUof4IWtR/8Aadviae2/EGG4UylGH4Q222gApGVKdRHIT0GtVGnL2TKvS9GZ4bw3xTiyA5Z2d0tKjKSshsKHUZokTFN7+0x7hy5S1foftlqkhJWCFddia0S+48xN9c2rNvbo90gjPPPnAEelVjivFV4lh4cxO4W+6AS1MDKT0AgDnyo2O17gq6bttISw4kuGFZLoF1E9BIqWFzY40AmEub+FQjLVRO/xPOuT11HSDFZxqtYeTaenjLKwy42OGWTKgsWiErBgCSoifPajv4Q7chwe2upSuQEkAhIqvWGPXlktCcyXUT7qxrtsD/vT1XFl1BKWEJV1JJ0+FbKpBrJzSoVE8C44Uv2VFSLyEjYpKgY5aTTzD8Bct3kOuYjcLUDGQEwoec/vWopPFWIFySllWmuhH605a4tcRo8wQZ3bXAn0I/WhSpp3CVOu1ZljuGC42pCFLbccSfEnl86qhY4iaKw2Lp4QCCgd5mE8t/2afK4qw91nIptw5hJQEapIOmo8wDvS9tx+5YBw2SH2VuABS0BIOnQ7jczFOpKMle5FKNSDf1uMnOHOL8UAbOE3hBOYjIESdhNGRwRcMBScTddtXcshvJsfM1KWfaPxE6tTOG+13b5PhQ6O9T8eY+YrU8M9sxTCbU4nZd06tMrbDhUUTvqRIPTU+lZRUW/ZrOpNLC2mA4rg7+FwpxxLjZMBSeR8xTEwlM6n9a9BYvwDYXjC0W6A2+POQd5gH6iqlcdjHvqReMtoifxADXzJ20onRz9SqepVrSMsSv8A28qCROWdztFXrEuyy5whlVw7ibLjQjRKDm3A9OdEs8Hw2yKRkQXdTLhknltSVBvkuWqguMso6vDKSCI106UUrkZRsfkK0RL1i42GptcpmNUn9agcdwnD0MvPsuJaWkZsuYeI/wC1EqNle4qep3O1isjTYfHeuJJkFIA2oM0ASNKA+LyPLzrE6gUKknz5ilAmdANqSEHUgxO8b0dJIMiDPlQAbNBEfE9KFGd1wIQjOpWgSBrRSfB5xtG9aV2ZY7hwtBhztmhp9tYV32VMLMyFZlGAdIKdjA8xTiruxM57VczY6KgjUaHyoDykGd/StKxfsnXcuLusOuwlS5cDCkGF67oVtGu21Vp7ga6swfaluoE7hvQfHaq6cjL5ELXKxprArgopETEdKtmH8JsvPBppl+8diciUz8YG1W3AuAcKYsDeYo17LJIyuiFJA566dfpVKk/JL1UfCMlBjn6munXQzFbJc8O8HvDI3iKEgxJUtOn79KY3HZfaXaQ5ausvMHVDjZEfEgxQ6LRK1cfKMo5E8hudqAEQYVuK1PD+z1vh+5VfvWSMRaaQoqQTmLQES4JGUx59eW9TD17wrjNqlnErVa1tjK0HmyvINPd3gb86OixvVxRjNrcrtHAtpRnoNc1OLkX2JPd97K4BGiQgwBWqN4Lw6mEYfdt28g5Q4IP11oXeGMQJQWe6ekSFNq0jyPOtI0MZZjLVpO6iZUMExJwAptHANjmIH507b4VvVpC1raAmITrWh3GCG0a7zEbhNsCk5W0eJaj5VElgqY0Xk1OXLrlPx0MGrVCKeTOWrm8opy+GbpJAD7Cj0Mg/vahRwtiC9gyOni1NW1aColbiQVBIBJEFXyrm0qzBQSrbkIo6ESVq5lSXwni6Roy16BwafOjJ4Sv8v3i2EKn3SqfrVweeQ0lK3XS0j+Zw5RO1N3rplaEoBUSuYUPiJ+hodGCGtVUZUnuG8SYISltt0ci2sfrSCcGxBS4Fo4FagBUAn061cWH0l0IWnNljPynT9KdZfvELUM3NKokienT4edLoRLWrnHlFVtuFLlxvvLh8MpJEQkqJot1wwG2kqFypYUYEoiD561cG7SHCVDUydaRvHkIQWlLQhREBR025VboxSM1q5ykPOwNxvhvjh56+eQ0xc2vsjatSFOqUIG2lenkgj8QHkRrXmXgG6VacYYc4cjoW82lKFmY+8G06TXp1KY2UVDzrydXBRng9vR1HOLv4OyeSvnXUf4/SurlOsbZZOqRpWc/aBCx2XXq2yc6b6yUjKfdIuEQT5a8/KtGOqQCdOtZ52+pWrspxYsnVD9otRmMoFw3Pr6VrDuQp9rPPV/ZY1dMQhTDiUkGWoSo9BvP1qAuDdMqLVwp1tY0KFLP9anWeLUt26A8ysORBUBv/AMpn0qNuri44hvIYZ8KNJJkx5n4bV6s9rX15PEpOcW96wRyiDuZPnrQSdth0FTauFLiP8YTllQAO/wDTaoa4ZXauqaWkhQP4ulZSjKPJvCrCTwwuh6+UV2iZ2nmfKlLbuVrPtDpQ3EyBJJ6VL2r+CoTJbQof+ppRGNxzqbfBBjMRP4Rzj9aDUneal7zGrdxKkM2qdRl1Ecv9vlUQVknkPpSaS4HCTau0CFEGTOtCVnJlz+H+WZFEzcvlNDmAHvfWpuVYkMIvWrF1RdbQtpQ1SoA/mKlmcRwV0lTlqy0RqFAZarQVI2EjqN6CY00n1rRVGjOdGMndlnub/BmLf7tvvlxHgVG/Sq14cyiD4TsOlBPma6dSCBJ5zSc78jhTUMInLDAmbpIcav0kDeDEH5SKeDhxxsksYm7I1GVZJ/Sqw24tpXgUpBH8pIpZF9dABKbh4R/mqlOK8GU6U27plkcaxhi1LrWIM3DISVjOjx89DUMrHb8mO/yk/wAqQKaOXtw4IcuXFjoVkik9CJn8qUql+CqdGy+w5bxG7aXmS+4COuulSVpxRcMoUl9HeGPCoGPWR/SoTNHL68qHRUcjUqcl5LdKDVmiUXxDcFyUNJAmU9KYXN09dLzukqJEdYFIkq3EiNN96GcwgfnRvY404x4RydhECDoTyNG11BP0osjWCT6iuUJAIMVJYZKiNNJ6xSzbaFNLcL7aVg6IUdSKbkmAPDI0864LSFdIgERQgYqJB5Krl5dT4vSaJIUQNidvKhUqZkyfTegDgN8ug8+lFOh3BG3pRgQRoTIHpFEhKjJgdCKALhb9ot3YYbb2GGYZh1k2hADqspWp1Q/ERIA9Nd96BPajxQlwLF5bKCRAQq0QUj5iR86qRgbDQ10agAECORp7mQ6cXyi4M9qXEqLgul63UgmSyprwfCDp8KueBdsWHXhDGM2r1ms6962rO0FfLMAfQiscUSNAPnRgqRKoJ6GrjVkjN6eD8G/vpwrixh24w7GUvKWoAobfBhQ2lEx8oqqXvCd2zdFt7DlOrSNFgSCD5HUfLrWVQCQYCiDpptUracU45YIDdti942lOoQV50j4KnetI1/Zi9J5TJ3FGMMw1amb62badKJSlxJ1TJEiJB1BHwNV5jh66vEF9lqEK91JEqynYnpyocbx++4hfS9fOIKkA5QhAShE6nKOUnU+ZqRtOLW7e1ShVsoLEz3cQr4n48j8aSlGTvIbpzpr6ZI1/h3EbdGZTRKo2E/0/c1GracaOVxCkKGhChEVNvcYXi1yhppKZ0BJJ+elRmIYk5iDyXnQhCgI8MgfGTUSUX2m8HU/mhJb6nkpQpUhAhOkQKKNOs+dAht14Hu0LUDtlTM1J2vDGMXYzN2LoRpC1J8OvnUWbKc4rLZHxmMn/AFp3YYm9h5PdhCkHdKudTDPZ/jj5IRbkaaApMfOm91wPjlssoVZuKV7xCQSYq1CSyQ6tOWGyRw3jNdoQtm5uLRwaDKTlH6fSrdY9ol4WFKCbO5M/4pn6gGJ+VZI8yq3Wpp1K0OJMKQdCDRRMkhUHYwarq5yYy00X2s2BXaPeNiV2dhERABTHnrNQeL8aOYoQq9v7cI0Iba0SfXWT+VZ2VZ9VEEjQTrQSQDGn0o6vpDWlXllx/jljpN0BpuTH0FGZ4gsLNUs3a/FEqaz5j8RVNnUADTzrj4jOb9KXWkV8SCLxd8dpuWe5fvr51tOgR4o+PX40y/tXYJOjb5nnl29daqgUQdxpzpZi0du1q7lJ00lUkU+tLwTLS07XZZzxXh4Hh9oKtj93Ijyk0u1xhaIbIaeuGDsMqFAfIVAjhbElKSO6SAQSSTAFCrhHEpQlIQrMOR0+NWpVX4MXS068k2vi6xUouLunnV9S2qYpK84vtmmUqYAeWo+6AUwOZMim+GcFKXeNDEboM2xJ7xTYkjTTXXnHLrVwsOzfhRa0LViC38hkoLwhWmx2p7qthbNPcoiOKbxxxWS2Qoq1gkmP3rVswTh/iDErbv7i2Ys2le73rviUNIMAHly33qxt8D8NWSz7NcJQowFJS6N48/0qQOApCSm0xa+yBOoLuaPTTaPMU4qT5ZMnC+Fgp99w3j7bLhasEXaViJQsAx6GNfQ1BvOYph7a3LzBb1DA6JCgn1g6CtBu77EsBcl2+tzbqeS2FviFAq0BOUa66SDzipq2ZubgTe3FotYQQvKnMUA68zIPXSm078ijt8xMZZ4ls1pyuIeaGsEa+Wh1NSNvxBhraUKU8lBAH4hJ0jrNWjivh/BGH7vJbsu3d0AlTWXKpskGFHmOW2p+tZziXDVzhqS6FB5pKQSSIUB+VTuqRyabKM3a9mWQcR4eAYuGxuR4xP0qpY3eovrvM2orbQIB1gmSSR8wPhTAmeennQAbgVlOtKSszppaaNN3Rq32cH2HOPHbe6Z9oJsnF25WAoNLSQSYPMjbp8a9P5soJnTrXln7OiT/AMSkEq92wuDH82idK9QmQRXnV+49Oj2g943511DlHPNNdWRqInUECPjvWedv3eDsqxRKVBOe4s0RB8U3DemlaEFADQCelZ/2+LI7KcWWW8wbfs1EAxEXLetaQ7kKfazz7fXlhZKQy+yQ06N0N7gRofpUha3Vi2ylbJt0NkH3SJAPLyqF4ou7NX3fdqW8VT4V6JHU+dV5aG80ghQjciK9d1NjweBCj1I3d0TmNcROuurZtFFKNQpQPva8vKoVx1dwsuOrU4o6kqMk0Qwnnyopyxvpy0rGUm+Trp04wVkG08hNcN5B0oog6zPWuCSucoKvMCpLf7DHaNRRJ1iD8d5p0MKvlIC02zqgoSI8WnwNLt4BijoGW2WJ18RAp7GyXUiuWR0zoOXlQ5pJmI5VNMcH4tcLCGktrWR7qFFZHwE1YLLsgx26ID79taAiVZiVkeoG1HTl6F14eyjZoERpQZuUfTUVpCew/ElqP/atvsNmj/Xalh2H3KQCrF2o5kNc+m9PpSI+TAzIAE9DNCRI5GtYY7E7QJUX8UfMHWAlMeupp6jsRwYrCk4jfLQBuMsKPyp9GQvlQXJjYMwJoZM1syuyPhcpQkX12lwaLV3yYPMjaIoB2S8N5Zavn1QIyqg7+msUdGQfKh4MaKtQJE9CYrgVCNN9q2Y9meFNt/3e8YNukgK7xO/zNQeN8A4daKC2n7RxsmJZdCVT6Sd6fQZPy4+UZsSYA5eVARP4j+dWi94MEhVncqObdDiY18jzpjhWGW7d6q2xRKUvRmQlTgCVDaBt4t9D1qXSknZlrUQauiGzAwNZjrFACmJj9Kv1jwPZcQPhiwIaUUgqVOiBtPn6VLq7EmEqIONOqIOqQ0AfqabotBHUwf6MskHnp9aEmBpBNahd9ijeQ+w4w4VRI71oHN8oqCuuyDiZlcNCzfbnRwPEaeYIqXTl6LjWg/JSyREzQpManUxFWJ7s54maMKsO8/5Fgz6RTG64Tx+zSpx7Bb9CRuoMkgD4TScGWpxfDIyeh130oSoKnQkdetAoKQoocSpCk+8FAgigOqRBIEfOpKuDPhOUz5dKAkJkT6kc6LklXuxHlvRwCFanXyoAAKAjw/SgPPNOhk+dGjwkmIG81qPBfYkeKuC2uKX8ebwpoKdKkXTMN5EnwqzlQgE8zpSbS5HGLfBloIOmg3EE6afs0+awTFH7Ri7Zwu/eYuFFDLyGFKQ4obhJAgnUUTB+0my4ZY7l/hfhvH1ZlrQbxpfeWroVEKKTlcQYBA1335V6W7JftCcM8bJwzAHkKwvH3myk2yGSm3WtIJIaUCRqASAfTWolUa4RqqV+TzG8FMOuNPNrYcbOVbbiSlSCORB2NJpdSRoqdd53FT3H3EjfDHbZxNcYlYM4gGMUceQw+jO07IGVKxI8OUzVbvO0JviC/Xc4jheFYe4pZUgYfaIYaGsnOBJWdkidAJ5mrTuyHBq/6HKGVvqCWW3HVGIShBUSeQgVdeHuyPF8VS3cX7zWG2xIlLmrsdI2HxqJ4f7RcMsb32ss9+EoltxchQURBPLUbaHSanMU7XLu8QBZ94yANO5OQ7R7xKj8orZKPk4ZzqPiNiy3XZ7wbw7bFeJZlKbkqLjxMk6hOhEk+SdjrFRP8T4UtEBGEYHY/wCd64KFT6J8X1M1nV/iFxidyp+5WVKKiRm1iTO+5PmdTTY6zMdPOhTSd0hqjKS+0jXsJ40aw2M1laC3zFSkNJCSkq3jQjfr1qXf7R8KZQe6sy4sR4VBCMvzzT9KwrKkboBijNNKeVkabUtW0JTOtNVfSJ+L5cja3O1WxZSA7bsozbD2lAKRM9Kr+MdqftAV3BQFEQChvOpI8ioAfGKoLWC4g5tarSPOBVm4d7L8UxwJefuWLO3MgT4lqgwYFXvm/Bm6FNZciqYriTmKXq7p0FKl76yT5k9aazBgctTIrZsO7H8At1KVc3V5eKTukq7tPnomCacXHBnCWG2q+5K7YIM5lEqJ5jQ+8fhyqOm27s1eojBWRiaUOESlCzPQHWgUSCQRBHLnWk3q7SQi3SQ2nw5iQVL5zA0HpSeFjBRibbmLobNrBklIMkxvzj+lVKj+yY6u74M6zDTy2iuzDlvWk8VI4DZtu9s3LVb2aAywJURzmNh00rP8Ruba4fAtLVLDSZgc1+ZrKUbeTeFbe+BtPmI86M3cOMSGnXESIORUSPhRNeYop6gCoNmP2cdxG3TlTdKUk8lCadDii/ACs7e+o1j0qGBkcwfWh5Ea/pVKUl5M3Tg/BMnim/UNQzoeeY/rTZXEOIqkd+md/wDCSfzFRx9fWukjbU0Ocn5F0oeiSt+Ib5kAEtun+ZSYPpoRUjZcVoQYu7cCfxNjr5VXNY3236VxiN/nTVSSFKhTl4NFYurXFrTuQ6X7dYBKVLJRMaSJgn1p5ZXL+FILNo99yoAd04MwQByHMDyrMra5etHO8t3FNnTY6H1qxWPFgzEXTQb82tRHx1/OuiNWMu5HFPTVIZg7ovaMZaVcBy6wyzU5MrcQmVOeoXPlzpV3EsDvWUtXeGBYOhCWkpUJHVBE+VQDN61dhKkPIdAgk5gY6bUdISpEocWk7Rz+VbqKtg5HOV88kFjnCdmHM+DqWlsky29PhHlOtRS+GMSRMIbVG+Ve1XELCJCk6p/FzoFOnKsAwnlpr5msnRidEdZUHfYLYX1n2nWaXGC2lVvcpWSNCnJsD6gV6fJSDz8hXnTszcUjjnByhS0S+U7e8kpIPwr0WEZ9SOegmvK1cNs7I9rQ1nUp3aDa+fyrqL4//T/91dXKdgks6yokT5Vn3b0AOyHiFS0lQQm3Wk/5g+3FX8QDEacqonbunN2RcSCQD3LUeZ75uB67VrDuQpcM8rowq/fAcRaOKSrUE6T561McN8IuYvfrtL542OgyBRSC4qdgToPjvTh3iOxbaGVzvFZfwp1GlNP7WOzCbcKRtlUYP5V6u2C5Z4rnVlxHBcD2LpcaJaxVwrjYpTof5YMfMxSzPYlbIbSp/E33JBkoypH67VVrXtHxqzSltq4fQhGiEB6UpHkFJOlPWu1S+WCLhbyCkeFaW21foKadMmTrl6teyzhW3QoOWpuSDmzPOKJPqQf6UZ7gnh1EJt2mrWB4ShRUJ8wdqzS/7Qbm90m6cSeTjkD/ANo0pieKlqOYsKPkHAB//wA1e+C4M+nWlll/xvhtOCBDwuEuIcOUkJEmZPI1GZQoDKQNOe3qJqkOcTYmtIQh1LSAZCUgkD5mKTRxDiIge0z6pB/ShaiKIejm8ml4Xj11g7Tjdshs59QVgz8wdqXc4qxd1JC7ppJ0PgbEn57VmaOJ8Sa1C2landG09IIpvc4rf3oIefXkO4R4AfUCqdaNuAWkm3Zs0scS4iVx7e/1BgfHlVrwBrF1Wq37tl5aVZShfeAQPT4zXn4qUdMy/mSKlLHivG8NsxZWmJvssJBCUAglAJ1CSRIHkKzeoXo0Wja8m6Yhc2uHWxusTxoWbaTKlIfIPoDMSfLWoF3j3gt5OR27VcpnN3TpcKVHlMzP1rF7h525dU8+8484okqccWVKJ6yaJBqHXfg2jpY+TXHMe7PrlRCbj2UqOi2krSE8tZTB+VNL+/4OYYcXbcQofVGbuw2fEobcuf61l4J0lQHmTvVw4UxHg1hCE4xYOG5SNHHkFxlSupyyRy/AaarNinpY8ohrjiW4NytbPcC3khKVtzmHXeaO1xVeJP8Agtn/AJSQf1q8N9pnDTQVa3GB+0sJGXKltBbPLwJIGkfzQaM5xj2cPAZsCfb8m2AAn5L1I6+dJPN1InauNhRhxRd+JXcpzKGhWtRjSOUVFuXBu7tLt4sFKlALyiAEzyA5VZcS4gwhCXhZMZkKWe7QseJKTtJjSBVabsby4Unu7O4WpyFJDbRVmnXSBSm/3cumopN7bFvwaztsHW3f2l5cokZgUOEIKTO492PWn57R3mQWxi1xlK857uYJHoIqlXPD2L2SgLrC71iRmBWyQCPXamyrZ9tWQsPTqNEGDVdRrwStPGTu3c0iw41uLxZDWNHvCNEKUlPyBAqbtONcQYYyr7u5ynRWUyPinQ/KsXICplKTB5q2rkhIAM+saU1Xfol6P0zcT2g3SV+Oya1GxX73/wBtD/by5X7loyVRIzKKoHTQCfiaw+MpBClAjYgkVJ2+P4lbBKfaC6gaQ74jHQHf601XT5RMtJLwy+YitOKXLlze27S1r8SgGwlOmg/IVPYf2bYA2j2jFLdsvFOctJ0Q2PM6T84/Os8tuMAtwJuGlIRv4TI/r1qbtsT/AIg0jI6txlPuI7yQkeQrW8J4RzSjUpO8i3vcDcDXKEtst2SJ1KkPpzn0kx8CKirzslwNxAcTirls2To7KAmI6k5Z9Kh1iSJQnTTXX58qTWgZkgoy5ScsbdNRQ6SsEdRK97j7hjhnhHhviW9v+I7lWL4HYWBuC02wXi4vOAZCNIQIVM89aa9rv2jrHivgm3wPhVh/Ckvuu297bONJy+yZMqUjSBmzTCdU5d+tZ4ltbi/LAYbeWhxxLcoSYU4rwpTI3UZgCtk7LewjAeHLW3xTHMKTc4y82sPW93lcYtxn0CUEEZoSNZO+leVq6kKTuz6DQqdWPB5ZwLg/HuIgXsNw25ftW0qK7ktq7ltKUkqJXEQAJrReEuy26u+zFvjzhK/xRzidq/UywxZAQhqchgRmCoUTI2B+NeuSpLae6RkDcH7tKQEj4dKbBCGmw2whtptOyW0BI+Q0rzpfkL5SPVhoM5Z4a4s4T4v/ALRrYxiwxFzF30hx9VysKW6s/iKiSJIjSeVV0YbcovBZvWt0h9JyloNw5OwAB3MxpX0CWZWk5EqUmcpIBim6mLZ66aun7O1dfaJLbi2kqWgnmCRM01+RXlFP8a/EjwfZWKXbxOG3TiLV8qLCvalFCWVTChEeE6Qc3Xyq/tcH4k2stIs1hISO7bStK84MhMKBgyUmANTFa12o9h/Bz/C+M4xh9kjDcUbbVdJue/WGyoGVZ0mRBE7Aa1j/AA5xhxBw5aHC8YtFv4daXLbPtDbfeuWy+7KkIbIMEqDYUDJ0k9a7KVdTW6JwV9O4S2yGtjYXmIPZLa2WtWgMiIPT1q64X2X360By9SloFOaXlhtCfU9f607wm5OHXl1iFq8hzulhTQfQAtZcTMlKTumTPmPOKaY1j7suXF8+64teydxI5ARAGo2ECa9KMFbceDWrS3bIkm/wBh2G2yLoXmFvJylRl4GT0AnxfCmqbdphIDbaWknonKfL9+dV1riO8dJUxYOpTOmZUfDak7viDE2RlLBYmBK/FB+grRVIJGPSqTxf/cnb3ELbDms7jkbDTxT6D4GoU8eY0yVN4ddP2LOYqytqkq9QdB5x86gbh926cDjyytcQJ0AHkOVE00gGeka1jOo5YR1UtLGK+xZ3+0DGbpsNvPrUnaO9XHyBqORjLt3fs+1XCre2LiQ4ppOqUTqdZ/YppZYZdX7n3TRSkaFaxASKmGeFEIWkv3aSlJClpy6K193edf1pRU3lA+jD/JdL7gLDcQcQLTiN5pED7tTolUiRlG6gRPiFRjvZBclasmKMqQBIUUGQPM8qnL3E2cWsTh+DWVtYhLYSpx3KmZIlKU6yQBAiNwQKp6eE+IMQbSHFvJQrZAUEyNOUgneqaXozU2+HYknuDeGMFwq4Ve4qi5u1Iyt5FpCUK5kQSOm5PprVAdCQ6vICEyciVGTHKtAsey27uDBtCUgEFxxZA08gPhVjtOze3aID7jTSZ1UkDePiZ+FGy/6CNaMPN2Y4zaPXRhphxzkYECfWprD+CsWxBQQhsJJOgGsD12rXEs8MYNKnLi3fcSAkELkgjnGo5dBSV72i4NhaSG0SBrokICj/ANX70o6ajkHqZt/UquFdjuZs+33jiVKiEtRI/f7NTf8AwbwQIRleuTpBK1Tm/KKav9stmnX2R5cGEoQR85MU0uu2ZK2sjGF3Ac5LW6N+sD8ppvprgSVV+x472N4clo91cOEkyO8O0b7EfnUO72X+ySs2bj6BolSHVEfLQzTMdqWIhcnvgOYARrUladtDrbXd3Vg86ea21JSY56a04uC5FsrDO27Ok37wbYs7qdjqUAR5qob/ALNm7BK3Hg4EzGZDshJ6U8ue2l1xlTbGFlCiYC3XQSB5QN/nVavePb+9e759htwHQBx1RI9IgD4Cm50/QnSr+GMMT4ZurIZ2ZeZn31aEH9+lQyVSJB86nneLXVtKDdtlUdZW6pQHwgfnUCVqJJMyTJrCe3+J2Uepa0xRl922c71pxbS+ZQSJ9am1YtjOEoSLqHA4JSpRmZ8x/SoNkNqeSHlKS2feKRJj0qfbZ4eecIeuXlLVuXVEfCTFXTv4JrbVbcroWt+LGC3Fy282oESEQsH0mNfWkX+LlkkW1qpAjUrWJPyHpzp0cEwJw+B6Qdsjun505bw/BLbUWyVE7FQKvTetfu8XOVqksqLLP2EXhxztBYauWm4Yt37lJKj74AAP/wB016ZERlJkV5w7KVrTxzhZw9RSpalB5KE7NR4p8tPyr0eRm3rzNWmp5Z62icXT+qsHhP8AKr5iupPIn+UfOurlOwbaGUhafM1Re3If/KTiU54IYbIkaH75vT/Wr2TB0GX0qi9uWVXZFxR4s391R8PvUa1rDuQpcHlhnBMSu1ISzZvLW4QEgQCqdtCatTHZHjT9s06Li37xSMym0tqUG1fyFXM+kjWnLSHlLQlCCpITolA8ROmkcqs1ve8W+BtDS3cgGVbyUZgOQJ3+dewqCPBeqk+Cknsl4tzqQm0tnAPxJej8wD9KcDse4iHifXZswJ0UpZHlCRFWTFcX4+YSSxatQkkK8CdPOSY+dVR/i3ipLF29eY0qzft1pR7IohtxRO8AAbefwrNxjFlxnOa5JA9i2MZcxxG0SOimyCB560ZvsVv1rCXMatUA66NE/LX0qJa7TMebSlC71S4ESpKFE+UlM9KK52jYy9ocQu2tRHdobED1AmmtnI2qqLdZdjWEs63+KP3Khv3YDaU/CCfrTwdk/C8GV3cggEl4hINUl3j25ea7tzEMTdHvSFlOvQxrUe9xTmbS0lt5wJEferJHWdSTVf014ITqln4z4SwDhu3CGlAvSmGipWZIMyVAz5RtuKrisMw9xCXUtkpMJASYKj+ulM/7QAjIbQLSds6wf/xn60m9j762gyllptI0k6mPWobiUlUvkXu8Cs0Kz+2eyoUnMkOoJ9QCKi3LdlAUW7tLxHIIImiP3Lr0F5wrgaSdKcWWEXmIFKmGwUH8ROkVLSfCNo/RfdjMgAaaz50HlMip9PB13p3lyyg80ZVZh86Se4UvEJlt5p48kgEE0ulL0JV4N2uQsnlNDniQToeu1Hdt3bdwtvNLQtJIUlSYNB+I+GD6VmbLIAKZPLpTrC7B/F79iwtAFvvqyoBJ384n8qXsbyztUqLtqp13TKSRlqTa4ot2lfd2QQofiSBI6a1ooryzKc5J4jcmv7L8P8Fst3vETq8SfcVLNq2mErjqg7gcyogbCJmpdntpt2mgzb4O42hIKULdcBA0jVKB6aTFVB7ixq5cLj9mpwqgFSyFHSm7mPWTiAP4cD6xA9PrV8cMwac19okri/aTf4oAzH3YUCGkICUrPnHiJ6Saf8P9peI4UlDRwlV3ZyrvEBEKgzMK289RUNY4tg5UZtE2yvw50gj1B1/SrtwtivD6GT7VllcjvENhwLEyACJyxHIa9aqzt3GMrRxtIw4tgHGXEAReBGEZ0jW4QlCniNNCJSDrzM6VPX3ZBhV9CbS7fYdOu2cR8gaf3OH8I8RpVbI9gK1GUJ7vu1ExEEkA/IR5VB3vZOptyMMxZduCPCkLKcpHlOvwFNp2yrhCor4diPe7GX0Zu7xm3XHJLfL5/pUBdcFps3VW71ypt1BhSVEeW2nMH8qc3/BvGli73bd0/cCYStm+VEehUCKjLjhviFt8m7U+h5Ugl11QUr4neoSS/ibbpf3jbF+H14Yz3yHkrToChXvg9ajbe8ubRwO27hSvy2PrUpeYZjhtsq33X2RugLmPWdxUS4y4wcjqFtnkFCPlUzTTusG1NqStJ3LhhPEDN7lDig3cEEZZ/TnT83TSFFTjqSoe6opyzWekJAkj0rj40jOokeZkCrWpaVmjF6KLd0y/cPcXOL4/4SwW8xVRwRrE1XCbdCApAuMp7sqgTJUpImYEn1r08SIUCAkSdANa8FYy08XGnEpCG0GM6VRrBj8vpyr2/wAOpeTw/hiX1KXcCzY7wqMqKu7TJJ5k14X5PMlI+k/FK0NpB8dXnHlsGBwXheD3icpW+b54oWIPuJAIBzCRM6VneO/aFx3hN9GHcRdny8PxFTedKF3wCFAzCgcplO/Otlt8Wwy4uF27WIWLr6FlCm0PoUtKh+EpmQfKqv2i4TwDcvYbe8bW2HFwPdxau3WYFatT3cp3HODpXJQlHtnC53VYy7oTMsHbdj+J3LqneIuEcEZSlJSlu0ub4JJ3CnEDKDH70q+9mnaBacSocsbzijB8XxUrU60m0tnLcloAT4VjUgzsdiKv7Nja2bHs1raW1u1t3LLSUJ+QEUhaWFk3crdt7S2buB4HFtNJC084UQJ6GDTnVpyTSjYunTqRablcDEcMtcdw+5wq/bWu0u21MvIQsoUUEawoajlrXmvF8JwbhlV7gicZS3e4di6cPvzcLHjZSc9u+ClM5UpBStIObTTQxXpXFnHrfDL24tlBL7Nu4tsqTIzhBI0Oh1FeJ765vMUuXuK8YbKl4pcKuE3CE5UvO7uhMaCCpMg9RW/4+7Tucv5K25WNJtOJuHl2lzg2GW7ZeL4Uh9tISwWUlSQpsTmhUAxy130oPb7IQ0X2AZ90qGlZCnFEWuKvPKaCW3ISsIMhJgaz16+e1Wywwm9xZKjZWi30pHiKU6J0nnHKPnXuU6zUbHzVfSpy3XsXdT4YQQ02pTs+62gAz1P+9RmJW+JYsgNdyGEqXmVnMknntp9aaN4piuGLTY3GH3HeoEABJKiCNxoQdDvtSDisdJU9bWuLJY01cbUsEesVtKomrHPChKLuh5ZcLIQQLtxS1FWyAAI/OpdmxsbJGZhhCTG8ZletVF3GcSY8Dzy2VHSHGwg/IikV391c6uXDi9MsZoHyFTGpFcIt0aknmWC1P4za2qylVy2Fg6gDMfpRE8UWjhLSWnSBPiCPFA51VW2XX4S00V/8qdBT604cxC+SFBpIbJ0KzAo6knwhSoUor7M0XDu1iytrdDTNi22UpCSUnKCI2jIfWlLntLxS9bz4ccPaUqBnIK1J+IyxVGb4OdSPvrtCDGuVJMfvSoy9tf4Zclpq5DpgELQqIo3yXcEaVOfYy4Yp2kcUNoyLbZayme9U0VQD0nTedahbrjTEL5BD6c7xEFbjqlAD0NN8PvcYxd1vDLVDdyt3wJC0A/EnbrVqw7sZxNbg/iV83aNHdTaASPXMR58ulTl8FbIRf3sU5zHr9YKe+Qg6aoQAfmaj1qUtRUpRKjqSTJ+dWriXs9veHrT2pF2i9aLmQd22QdieUjQCTrsarpwvEO5U8LG6LSQVFYaMBI3PprvUST8m0Nniw1Mp6zsK7aTBoszsRQnWY086g1AChEgaHnXEnkPlQFYGqtup0pVm0urkD2e1uXwQI7tlSp89B60BcT3J5CuA1J1muebct3O5uG3WXd8jiChXyOtGatLm4SpbFtcOJSCVKQ0opSBuSYgUCukFG0n8qCRMA7b+tPLLCbm6uGmVZbdKzHeukZUz1/Y3q7f8HbsspWjFWFq/EhLUT0iVD6+VUoNkuolyZ8DpEVxJM671cbrswxNpCizeW7ixolLrTjebpBAUn61Gu8EYxauf3lthpmJVcd+C2keZMUWY90X5K/lzfhEelBttp6DSlrhCWXnGkPoeShUd4iSlXp5Un4p2gedK7HZGq/ZtSpfaHcLGycMezSddVtj416eCwRrA868z/ZpUU8dXwHu/wxc7f+Y3FemNZEI5cq4a/edlFLaBmH8v1rqCV/yr/wDdXVjc1E4MSDE9aovbkUJ7IeKs3hmzAGvPvER9avKkZjrPrOgqh9ubaHuyPiZKlKOW2QtIB0kPII+sVtDuQpcGOYNxQ1hTKLZ5hC7gwpGYSV+WpFJ8Q9pWOB7LhVgWWIkuupBlfUJTGX4lVVTEsUwu/sfvAfaAISgJ8aD5fGoVvEL1HgRdv9AMxMj0NevKovDPBp0na9v/ACT7HaRxZaPLX/FFuEqMtPNIUkT5QCPhUbxFxJc8SXLdxeM27TracmZpJBUPMkmf9abs4XfXaS9lhJ/E4qM3nRhgd4Uye5AkDeay2yZ0KVOLwMQdI2Io7DDt08li3ZceeXolttJUo+g3qcw/hVTywq6UA2NwgnX41o/BVngOAMG4U5bM3S5SpanAMiZ8Ig6nSCesjpVKlJkT1MFhZM4a4B4pcAV/B32wR/4jiEEeoKtPjSFxwljli6lN9g9+0gEZ1Ntd5A/6ZrTMf7V8PtLg29hd9+tGilpbUpseQiMx+nrUQz2qOSE+1MPGIHeslGUnzBH1mq2R9kfIn6IfDuARjFsty2D9uUyB7QFIKjH8pE/GIpnZ8HJZcc9vdQ7lUQgNmUHoZFabZcbcPY6hVs9ett3GQIdYW4IWNJgnwn4a+VPVnhi0RmcNsMiZATl8Q6np6b1ooQeTKdSo1ZFFwvg9rEFg2lkgjk4pOgPy1+FT6MJseCbdy6S+bm9WlXdW5hKEqO8RsJA1M6E6axXXvaAtTarfBcNKFTkS5cJKEhM6mJkjTbw8tapFzhGNXV0Lm6xdx1RIU4STqnoB+lN57UZJWWZElYtY5j2IuB9i2Ljx3ZVCUbanoB1qNx26vMIuzZ+zl25b0ztJzIPIiQfLbetK4KRamweClNB50lCkyNxtMbCNuWu9U/HmV4TiNym6UhtWcuKXMlWYzJPnz9DQ/Vwi7u7Rnl4/dXTgcus8jQSkiOcfnSKEpkBRVEgEjUgdY9Kmccxr+IJ9maSkNTJVzVH7NQ22kzFck0kz0qTe3KsW7hTgBOP2vtt7iBs7U6pUlObSSAVE6JBIMTOxqynsRafWPZceUpCgVAlhJkeuYa/CsszykoJORRBUmYBI2JHlJ+dKMXT1of7u6trnCdQDTUo+UElP+LNCf7F7thw/9tWmUiRnQUH4iTSSuxnE4Hd4tYKKxKZQoSJjQnf4VRl4ndLVnW+VL6lKf6U9teKscsWi1a4pcstqOYoQQBPpECi8PRFqvss9x2P4tZtLW7cNy3rokgqGm3LrHXWoxjhhdsr7q/dbdJjwiJPpFIDtB4pDQa/jlyEnnCM2vQ5ZBp1heKWBJT3zyXVKKiq4XJUonUzOtaQ2NmdRVUsu4xucXxjC3TbXJQ5tlUpAAUKmMN46cLQZcvrizgCEh1RT6AjYeRinfsVliCWWrzultkyTkg+o+GtStvwHwQWVtrxNwOkSlXf69fJI+NW4yT+pzqdNq01ZjNniR9ZlOJulR0I73NJ6RqKlbbiVeVq2vmUXrOeVy2EuDz5A/ET5iqpxN2bXmFsqvcLi/tEJlWQhShEyRHvDTbffeqi3d3LHhQ+82BySojX0pda2JI0WmUswkWziTErnDMRLtkQuwcPgDgIWOoJzHTeDrvr5w+IY9a4hbKb9khZGiiB4T1B+dRt1iF1eICX3lOAagwB+Qq8cKYVw9ZYei+xBTV/fTpbrQVIQPSMpjqTUbnJ2Rp0400pSWf0Z8FpJACwfjQjU8ieQnWtvuMZ4bxBj2K6wxKGgPAlq3QAkD/LJ/KqtivZfZXqPaeHsSYKDJLa1qKR5bZkwes/CplRa4LhqoPnBntvhysVfZtG2i8t1YQhrKVZ1GRsBrvXrXiVVgzwXiH8bvnMKskWJTc3FsohVukpCTkiTMmABPKvN2HcO4jgeL213clNv7JctPFUlJGVQPhO3LcGvVTr2GY/hqlJZZurG8aSopdSlxDiTrBGxH9K8n8jFxcJPg9r8ZUU1OMXk8XcXvdnrNtZ2vCGGYym9S53q8SvrjxrGuiW06CTrMgjXSp7gzFeIu1XjlvCb/Fbpx161AF02oQwq3SVMPkR+FehO6u8PM1t3bFwVw7i/AuIXb1lZ2L2E2qnLR9lCG1NhEqS0DGiFExlG5NVv7NvZ/dYHh97xTilt7PcYmhLNo0rRaGAZKiOUqAEbwnlNL5EXTc0dHxpKooS/2M97Qu0rtWsC1hHEzjmEOHMQq2ZDHtQSYzBST40yORA8qj+GMR7P37JdvjOJ8bYdfXBzXT9m6hbCoM94UgZoHmDFaL25YNhfFfGVjhFyHMI4hVbpGGXtyoew4kmSSytW6FhUpSdR4hMSKYdivZVxhZ3H8bOOfwIJeVa3VotgruSGl6tLCoTlVr10VOtUpx6ak8EuEnUcVk2dvE7Cy4Ccv0YicfsbXDXHPayUuG8Shs6qI0JMQfOa8b4va3f9m7Vy0Td3OF2zhU68GVi3trh0AltE6SAlHimT6AT7js7G1tmk2rFsw1bzoy22EognUZQI1kz1k1heDuYbcdknaNwxc3TFq3ZYldqY+/QgPePM2kCZMKQARHQDy59JPbusvKN9ZT7bvwebrABd8wgic7iQBMa5t69GYdj9vhOHtIw6w9guUwpSGgksKBACtNFEkAamVbeLSsb4GwRDmLt3l4EoSwApCViDmj3o5/13rSXhbutwXllJTrAg/lz8q9/Tx5bPmNdUyoxLIrjh8oQn2ezQtIPiIJ19ND+frSaeNrpWZRtrA+IGEoKfj70c6oeLYfZsNuXDV6/3h1CVLJ+utQovLtOibm43j/EMfnVSntdrGMKDmrqRrzXFNldN9zf4JbuN7ZWjoR5JVp9aavt8F3gl3BimDICGwPhIVP1rKheXSTKbl8Ef5zrUpbcS3DYSm4QhxEQSnQj+v0ojOL5G6NWPay3XIsm1r/h9vlZCobS6QFZfyqLuTjiXVhHsqkgkJyST6aGgY4mw54BC190JAhxP1nb60+F/aOIBD6NdoIOhrdOLWGcjU4vMblSxR7FFZkXpcSiZKAITHKaj4gAJETVvxnFMNSwWXkJcUoeFKUhRj9NudVBB55Znaa5Kqs+T0dO21dqw6w/EbzC7hFzZ3CmHW1BQUmOXUHQ+hqZ/t/xDkITepzEESWk8zMxGX6VXhHnprQSDoR+lZqTNXTi+UWLD+NsQZu7Z3EcmJNtrlaXRBUDyBGkjfaKvjHa3w68EsXuHPJbgJSvuAoj1gn5ishComDEUX3iZkGqVSSJdCD8GqYlZ9nWLtoQziFtbOr0QLcEKAjYgCB8qas8B8GoPeP4887G7SDBn0CJFZ20tpBUFtFwFManUUIvbppoIRcPZRoBMj4VSmm7tGcqUkrQZrtqeC8GQBZ4My53YnvXWsy/UqWZ/e1GVxm+tZcYtk5UxISpSoHnArIV4perIJunJT/KAn8hSb15cXejz7zqf5VuEj5bVfViuEZ/Hm3mRqt3xtgN+0VX1laIeb1Q+HApQIM/82pGsA7nSlbTtU4abtvZl2LzACT4kMjLPPbU69UiedZB4UGSAnnpWhI7LO5wA3t1duIuA2p7wjKiAmQPEATqImR7w0qd7eUPoQj3Mir3i7C7i/uHG8KUm3KiWoSgEJ6QRpz50qxxpbMslq3F9bJ/lQlMeoIUI+VV63wHErm5Swi0VmJjOsgIjcnN0p3inCWMYWJXaqeSElSlMpUrIBvMpB89tqOpMro0nwSbnGLRIh2+mIkLy/IA6VH4nj1vfsuI7h951WnePqzZR11JPSKgoJk5VDzAGtBuAJOlQ6ki40IRd0DB3PPXWuPLWunciTpXZSACUkEjY71BubD9mMIVxpiq1CVpwzwztq6if0r0ioKKuXqSa88/ZeW0nHuIUkp732NkpGUTHeGdekxpXoUgEQCfiK4q3edlHtBgfzGuoIHX6f6V1ZGgjzBkg+tUPt2Gbsh4oVJ0tkEkcwHkaVfCQDqMp9KovboueyDivN4T7EIJOh+8R9a0jygfB5vteG7YALuVKcVOw0Gu3OpO3w3D7MZmmQgnrEz8Kr73EtyQUNMttgJy5veJ03/Oo1+8fu1S88tzlqdB8BpXsKcYrCPBdGpNu7sXcJYu3w09iNrZtHVTjqvCkef751JWFpwSpfdP4+44pQhIUvuk+gUQB8CfnWY5U9AI68qEBOoiNNIGlJ1m2XHS25ZuOHcG4EVSzibtwlQ9zvRoekiJjyNPHuHuGrcTdtWiUkAAkkAmOck8h/vWBI+6UFNEtqE+JByqHoRrXK8cZyXI2zknb1o636D4y9m33nDPB18yW7RnDyt0QQggqHQgDWazF/g51CyBcoCU76TqOVV4JSoSEgQd+npUhaY3f2QIQ6HExEOAn5GQaW+L5Q+jKPayUsuFrQqT7UtxwgTGyPIE/vapltzC8FaUoezW0ATlRqY6czqaq68cxG8IZbgLUdMgknTbXSnNlwpfYgO/uHQ3mJGY+I/n+4q4T8QRzVaXmrInk8RYe4600m8DjizCAlJASehPn/SlcRTcP2rjdk9DpT4VKA0MjcdYn6VXLzhC5Z/wX23hAmREn9xSFw5jeH26F3D7gQDk8XiUB08SddJqurJYkiFRhLNORP4LZYxhV17U/fLKwPBk1IMcp9SKtzuNYXi9ibfHbAuupRlS8lJVOkdZT+U9BVM/tNh7TGjpWuNEgST6g7Go9PFrveEqt5bzaePxflReC8i2VZtysSlnwbgbl9ku7+4tLdWqXCUgTI0J22k78qeYh2Ul1pT2B4g1eIiQkrEn0iZ+dMW+J8OUDnWUkgjUEfDWpXDL1q2S45hd0i2WspWtTIACo1Exoeeu41pOEJcFdWpDuuUR7BcSZWtK7N0KR7yRy+dEVhN822XV2rqWwJMgbfOrfxVxVfi8beXZMIChqQtRKj0M7xrBmdagLviq9u2VNIQ0wFCFKAUpUa9T51i4wXk6YTqPPghgUxsTy1FSeC4O1iiHVLuC0W1QdNh1On7io2I+dHYfetnM7D621kRKTuOh/1rKLSeTonFyjZOzLI7wS7kCmbhJURIBMg/QVDv4JfWZOdhSiJ9wz8acWnEV9bCFlD6d5KcqgfUf0p2zxfcIc+8Z8J1OVQJj5Ct/6cl6OdOvDDyiFafurYFKHHWx/IoQJ9DT5nHr5qUrWhwRMKTv5aGl8T4hYxK2U0q0IXuhegg8ietQQkyIgDWelZt7eGbQjvX3jkvfCPaKcMf8AZL62Hsz6gkONqP3KiQM0HlsTBnSatuP9nWDcRsO4hYvJTdPKU4p1CiSVK1IMnX5TrzrGkpU54RrJ1NSq7LH+EFW9yF3mFLvWVLb7tZQpbYMHMAdBrMHkRUvURVoz5Y1pJO7p4sLY1wZiGEPFoglQ1yE6kdQY1FQjTj9i8S2VtLB8QI0kdRV1su1J9Vsi2xnDGsWCUlJdW5C1K1AUQQROu4j61WsYxW2xJ/vWrFDRzzvEidE89PU1bceURT332zVxRjia6aILrTa0zJyeEn86k7TjBFu8h5jv2HG9QtAgjrsagsLwm7xrEG7OzYW4+6uEtoGp12ArZuC+wlFuU3vEuRakKOWzaWIjkVqH5D4msamr6S+zOinoOs7RRVsK7RrlwdwcNXfrXEBDIClDoQJB2GpHWr32UcY/2lfxDDU2blqi1Sl1vMZSmSQpIAjLB2HrV9wjBMNwRGTDcPt7QH/yUAKPqdz8azLsdYtsP7Se0TD8Pvl3tsl5lzN3akpDhW5nSZ0zJKss84kV59XXdeEklwenR/GrS1IyvyL/AGg+KVcP8HMWNslDmI4ldpRbhSM5a7uFlaR/MDkAMHU+VVDA+OeKeyjh3CcOb4SvcWtLq0/iT95cFxJbdcJU4nMEqCUp097WSSTrT3tQebV26cOXF68GcPwSwTiN0teoabQtbilAbqJypAHUiqt2ndvjvaJgbnDmA8O3low8+lx15x7O88hOoSEJGkncSrQVFGl9IxtdPLOivW/qSlezWEVfjTtexbtCw97DscwzDrhXtAdw95lBQ5YyrxISfxhQhJmDoDW4dgnaHiGM295whxO7cJ4hwpRCBeL+9ea/l11KkbehB868yWV9bsYTdYfieAh5150LTiClONu2oiDlSPCoayQRypdrjfiBjiWz4kRiLxxe1yBF26lJX4E5BmkeLweHXcb10VaEZw2I5adeUJ73ye3cf4gwnh+zdcxPGrPCVd0pSVuupC0iD4koJlUb6A7V4wu7IYXdptb/ANjffU6677a2SVPhRHhJOhG6gQN1EE1YbHHsGxPjZeLcaYwMcunmkd2tbOezudSktKAAUhA0y5QNUkGN6vvHPZBgnZ9hK8Xvb1fENzZ3FrbWmELdS0y13v8A4S3PfU2Y092UgydSanTUlRX2d2ytRVlWeMJFa/4V8WGwt79GEOuWz7SXmy2Qo5SJBIGo0ioLGOG8cwJxP8Rsr61SvZTiVJT8633s97WLTiXAm7jHEYfw++bxeH2zRuAGrlSEie5KtwJCdJ1jUzV7uGWrlstXDaHW1e8hxAUJ9DWUtdOnK0omsfxlOrHdCWTxlusKUqSN+dDJnf0NeoMY7LeEcXkuYWm3cUCAu2OSPPLt9KzbirsGxDD2faOGrj+JgAldu5CHBpyMwr6elb09dTnhuxzVfxtamr2uv0ZSVDME7qOwGpPwqVueGcXtbJN2uweUzupbfjiQCJA2/wBda0HB8X4O4Mw5LftSbi7aKi4y03NwtwCCFmPAZ0CZAA3kg1CY52r32KJUzb2SWGIICnHCXAnbLI0A9Bz3Nd9o25PJdSf8YlEIIMEx15UJA1OUTtNTTnFC3UkexMhSgRmJBgnmBFFwTAhiii+85laSqCANVH4bDeq23doj6louU1Yh0ZQImOgo09YArTEMcE2NmyL+2S0CkhSZUCFdZ6TtrOu1O/8Ah9wPjtsm6wjGFMZpADbudKddAoKnKY6xvQ6b9kR1CavbBlBInQxQyTWhYn2O3iUB3CsUtrrQkpX5f5kz06VVWeC8fe70pw9f3TpZUFOJTCxumSd9KjazZTT4ZDxtME0UjeOtLXlncYe+q3umHGHkxKVjX1HIjzFIKJUREmelSWGBUOcHlrvQqJ23+NAhBIUczaconVUZj0HU0EEDl8qABJM67mg21BiDNIXNw5b5clu+9P8AJBA+ZpxgdpiXEF77LaYetCwkEqeUEpAnnEx8qAt5APiUTlQmeSRp8qlW+J8bRZpshil17OgAJbKvCANh9Pyqz4d2T3b7ffXeJ24QRoLdOfXTQqVA+lGvOy7+6LescUcU6k+Fm5tSnMNfxIKo5co86rZIzcoPkq1nxJiljc+0N3iy5BBzAGQRBHXY1cGu1l24syziFoC4VJMgkpVEQR01ExVWPBmPJBy4cp0jcNOoWR/0g5vpUKtJSshaFJUNIIIiqU5Il0oS4RLGzwe7Ur2e5LC4lKHBlCviY/OmzuDXSWy4xkuG/wCZsgmmPKdiDtFGaedYWVMuLbPVJip3J8ora1wwhlCilWhG9CNNBp+tSD79riDAU6e4ukjVRGi/jUed4Pwik1YqLua/9mUgcYYupTmU/wAOgJ/n+9Tr8P1r0mFeEeNRB5RXmv7MziU8aYo0oJ71eGHuyrcQ6iY+Yn0r0pKlEDLrzk1w1u87qPaGj1+ddQ90joPnXVkaCCYI5JqgdvISvsg4l1E9y0R6B9ur2dDoQaovbmkHsj4oywclqg7f+sjWtI9yCXB5Zw/DHMTu1NIKUBOqlHkKstrw5ZWqVJeYS8oCSVJ3PrvVWZvX7RSyy5lncQFD4TRncVvXm1JXcryqAkbT/pXrRlGOWsni1aU5uydkBiZYRfvJt/cCsonl1386UtsOU8Ercdbbb5nMCY9KZD3d/lQTlAmfWazvm5vZ2sW+zwPBFM944hSv8yXJA9eXKml/Y8MNry+1vMuwJSlYXl+Qj61D4fg7uKFWQspAOXMs1J/wTC8MbQ5iN5mzjwpSgnUHy+FaqV12nDJbJWc3/ghyyHbhTdqlbyQfCSNfU9PWuFs+ZhkrCTByiQD08jUsMZtnCizwy2FoFrjvXBJSOsDnVgwy0t8NtAYiU5ipR3mJ13n/AGojSUvJrPUuCu0VDDLu4srgussd6tI1QpBMfLUVLucTYisFLmHlSojdcSdjH+tOW+KrP2ooU0UIBOV0kx9P6Ua54vtAItwpxRkeFJH5x+vOmrRXcZzcptPYQDuNYmglo3KmDOobSEH0ka/WmCjmUSolSj+Ikkn50q+6u5fcdXlBWok5dvQUDTDlw8GWUBSz7o61hJ3OuEFFehMCAR8q7WNR8jRrlly1dLLyMixrAUDRM2nLpPSosaKSaug2YAayfhXKgAwBrzG9FSFLKsgKsokxrA86CSNue1NNoWGGCjBBWpWswSYmhCgZg/WiZpEbTrQg6aAH40XBJJYBVp4oMelTNvw2+5aLuVvIQUgFKAJnSYOvp/WoTnrz1gDlS7d9ctNdwi6fQ1/IlwhOvlTjZcimpPtADhUAecbHpTuwwrFcdcetcGsHb67aYVcqaQtCMrSIzqlREwDsNd6ZJ90wIHOrhgHB3EymWMXwgKtlOJUkPIWArKoFKgBOoIJB5a/LCtXhSW6bsdOnoVK0tsI3Kta27t0EBlBUpcZQkTmJ2gc5q/8ADfZS/cvd7j/e2rCQClptQDjnMg75B66+Qq/8OcPWfC+EW1laNZnG2ghdysJ7xw85I5dAIG1SpIBmP9a+b1f5uUrxo4Xs+r0X/T8I2nXd368ELgfB+B8OrDtlaJVcQfv34WvU8tAAeUgT51W+1+2Tc4dh1zkHei4LAWrchaSYmdpTNX5CvLeoPjTDbe+4bvBcNFwMJF0AmMw7s5lBJgwSkKE+deXp9TN1o1ZyuerqNJTVCVOnG2DDsMwbEMWue4tLNx5wmAG0lRJmOnpV7w/sO4nfQlVym1tQSJS4sFQB6x+VbXwrhWC4fhbL2B2rTDNy2ledAla0kSJVudD9amYE6TFfTVPyEn2I+XpfiYr/ALjIHgrhC04Nw0WloQu4XBfussKdPpyAGkCrGox4QvxEQD0NJB3xaD61CcaY43wxwjjGMurKRaWji0AbqcIKUAHqVFIrhu6k7vk9FwjShjCRkXFXbFxGx2P4VijJYRi2JXVzh11cJRBR3ZUCpAB8KiMuvLlUf9k/EcQe4px7DFYgtbNzZC7XbqSVd66lwDPm/CoBRk/inyqsYHxlYW/ZvY8M4n2fXmN9y+7dt3vfuIQpxcyoFCCQYgbkabVA9nXFWP8AAPGjTuGM31mq5JZVZ9yMzqXNG2/vORXkhR9fKvYhSSjKNuTw51m2pXPR3a72Q/8AEux9qt7pqwxqwIQ1cXBV3TrWYy0oCfxQoGDBBHOvN3EXBnF/ZXj9rKrli9yuP2t5hqyStCB4lJUNRAmQQCBvoa9z21jcu4PaW+I3IXdttNi6cQIDjoSAs9ACqTXnP7UvaE9guJ4Zwng+Zl1m2cuLm6gFS0vtqayJnUeAqk/5h51FBST2eEVXlCf38lA7Jb7G+0TtCas8U4sx1TTyFv3U3Sgq5SlBlGqoAOg0BME7RNB2y9lY4Bx527wK0dcwP2Zp+XHO89mUpZRkJOqtYjfQ67VnWFC8w1+yxFu8XhozKXb3jZJKHG9dMuoVJA/6gdqv3FnbZjt3xgnFMPulP21gwbfDxfsA5CpoNruO7271RzKkzGaIrezU7rixjui4WayWbs14Ce4AwzDu1DEcNTjuEvYc6+05bEleF3GqULcbJBcTyJAgZp5SaLxhw7xtd8dXGCYyi4v+I7xTTjyWYc74qSMq9IGWI3iNZ8/Vf2e7ayv+w/ArZxlm4YdafbeaKApK5eXmSoHeec1WcAda/wDiI42SkJ7tOGW6GlDkkBvRP+WDt6VE6u1N24KpU90lH2ZNc2GP8N3juK43w6lvGMNt27bAsPu0BVpY27KMzl2VTkXlIEAnxLcJgwBWh9gmOcd8R/xW84mxJ17D2soabuEIDxddAcmQJCchBA0Hi02rVscwLDOI8NcwzF7Jq9snspcYd1SSDIPlB6dKwLsfs7Thrtz4pwFDjyW227hi1beWSpwJcSRudSEa9YFcnWValJWyjvjRdCrHOGehFqylIiSdBvFJqbClyZ02j+tLTJ1B9KDL4j4a8xNp3R6zimrMp3GvZjg3HUvLUqzxUJypvWkzmA2C0mMw+IPnXnvHuEsa4dxW4wy9snQ+wM8oTIW2ZhxJ5pME+UGRpXrgeFMRJO0CqxxtfYEjBLoYxi1lh4tAHFOuuAlsk6BSR4yFbQkTrImvQ0eqlFqEsr/0eV+Q0UZp1I4f/s8rQQYI1kzpqKk8FxdeGPZFeJhR8QiSk9foNKu7nCWD8cBWLYNdoaCyUOKQ4FoLmolU6x4d9JB66VVcf4FxrhtU3Vt3jH/nNSU78xuPyr3Y3j9kfMy2y+kiZcfw/HWg0t1pYUYGVYlJ3OkzG1djPZre4XYDEbK9afV73dtaKSJjRUyNdp301qkFskkLBmdjT9PEOKoYatjfOuMMf4bbhCwjSNJnp9KuVRS7kYwoyp9jwJ3V/iK3ALq9vHFteEZ7hainWYEnTXWpXCePcbwoKR7WblpWqkOpBVMATmIOunOeVQKlqdcLilZlEkkk6k0TQCQKz3W4OiUFJZRqmB43hHHjIw7GQly+7zvW7ZcJS8oJ0IOgzEFSdIOgMaVSeIcCw/BsUdtGcQW4gOlKS4BITr7wA8J5GeYOlQjTgadQ5lSoIIVlOxqWUMKxYFzvRhrogFJUkIVpuCY/SqX2X7MWum/Ng1thmD3JLYxMBwcyoJB+cfSp7C+zFu+sEXtzxBb2zJSFqUoJyhJ55s0eUmNZqHbucKwJPe27gu7owjMhQOnOTrHLb/Wou+x69xBpbDvdJYWcym0pIBM6HUnXzqntXIRdSXHBJcR4Xw7hbQRhGOuYpchwJVkSO7yxqZGm8Rqd+UVFWVziFg8nELFx1py3MpeQYykUxLiUlKVK+B/SnFvfXFshxtpwpQ4IUmAQfPXas73ZvZpewl5iGPXTqrtWJF64KitK3VqIn0kj6R5UNn2lYphFwi3xK3bzJIh62X3cjrppoekbbUXNsYnzpteWFpfge0ICzyI0IpJtZTBwhLEkbT2f8ZscQ983id0z36AS13sFx5BSeZ3EnppGvkTjfhRWJs21/b3LSkW1q8hRWArOYzeE5iYA2B6Vgz3D91bErsb1Sgn3EOfpyqbwXiviKwYGH3d/dtheiEleZKhzSOnmBE1SqX7kZuhszBizzLluvu3UZVROhkEeR50UaaA61OZmeImu7CU2902M0EyFnnFQS0FpZbUBmBik424KhNvEsMMJEzsT8zXZQrnqPKaLG3r8KFOoJ1P5RUmhtn2X27dePcQLUEl5FoxlUU6hJcVMHpITp5CvREkQEgSa86/ZeUlOP8RDL/8A0LJzTGzh0+teigsxOWAfIVxVu466PaKaeVdScp/nHyrqxsajU6gyCPMiqP24E/8ACHiopClH2Mbf/qIq+LSc2ix5AHeqF26qSjsj4mBzDMw2mRyl5sVtHuQPg8lkiVab9dYoNAdhPlXTAiNOUjWhbShbqUuKSlBVqToAK9DyeawhVrodPLlXBQzaQBvE1YFYDYXYBtb1sOc0oczJEbwD4ooWuDnMoJuQpX+UAEfD5VfSl4MevHzgryFLTqlRQT+JKiNP3NP7TD8RxpSCFLdQDkDry/DPQfSnV3gd5Yraub1BubRtYzhsAKyg6+Gl3OKrZi3CcPsi2uAkKcSAkDnAHWqUbdwpT3L+nliL3CeIsjM2WlqmBlMGfKmC8Rv0IVbruXMiCUkSCfSd+tOzxZfqSQsMzsFQZT6a1EZ5KlEkk7nqamTj/EqlGdrVAQAmN4o+kAyYPSpj+EWK8I9rbdJWE5tDMGNoqHEc5E1Li0XGSlwCN4/Olra5dtH0PskBxGqSUhQ25g6GkM20bedcFbaH4VJRKnHVPDJfWlvcoj8IKVA9QalcJwDAccKlpvjYpAGYOn3SeX58+VVaRufhQtOuMOZ2XFIXEZkmNDyq1L3kzlS/tdjXbfs/bs7NCbG4tLyY0WiCRzgnQ/DrUJi3ZotBXcO2jtoiCpZCkhKQOfltVRsuKsUw9OVp1J5BUQqPOIn4+VLYhxtieIpUl5RGYDdalQRzA2+laOcLcHL0akZYYyxuzsrF5DFo4txQEuAz4eg9ab2PsPekXvfpQdlNpGlNlnN4pJJMkzvU3a4VhK20rdxFC1ESUhYjbzINZWu7o6m9kbMM3ZcP3KQEYg4yefeykg/ERUXe2S7C5UwpRURzCYkdalHuGW3GFuWVwX8uojXTnMbf6VDFJaJRAkHL6Gia9k0ZXeGSXDWFqxvG7KwRB711IMjRInWa3LAMdtLm8xLARbO2zmCqQye8075BHhcA/lP61Q+xnDUv4re35bSoMNZEqI2UTrHw3/1qV7T1XfD15h3F9kkzboVZ3MqhK0KIKQvqPeA8yk8q+X/KVFWr9FeOP8n234el0dOqzxd5/wAcf/S/PBSFQNhzoApOQGTrzppgd4zjPDlhiVsp9VvctBxtTw8cTsrzB+lOC3n5wdgOtfN1YThJpn08JRkrpgpcTmjlFKNuZ1gBJUZEConGsTtcAs1XV2opypJQ0CA48QPdQDuay7HuPeIMRZftRfWuDJWkd3btqV7W5JBAGXxTBG2Wa10+mqVOMIw1OohTXtl34Y7YcE4QubnhXiFTtqnD7h23au0JLjQbSohAVl1BCYGxGlKcafaQ4Xwqwdb4bWvGcSUMrf3K22G/8ylKAKgNDAGvUVkTHDTBQm4v2iwhOinbxYaUtwCdRrlBmIGZwnkKprrKLlJdR3wC1BLalIOQknqPhHr8a+p09Km3k+V1VWtFYNd4K+0piOHl634rtV4sHHc7d1bltpbQI1Rk0SUgjTUETzqRvcWxL7ROKWeH2tldYPwZhzvfYldOOJBeWJhM7TGiRrElR2ArIVcNNuIIafUnl4kgil2MFuRb+wOYk6u3LgcTZoClNLURElJVvAEGJrvlp4xe+KszzYaqU7Qk7o9q2TIsLJmztGizbW7aWmm0gwlIEAV5z+1Nhdk1i+FY25fZ715k2rloFjMlDas6SROYTnIkjkIqg2t9xLh7ZtrbivFmUIGRIS+4nugOgzaH06VGDAGnXV3NzeXL1wokl2YUT1JMmfWs6OklCW69zSvroThsUbHszhjj5ziHstPFWHYBiVv3dk44xYrEuOltGgbP4kkjQ6SOVeHOKuK8a4wv2cUx25N3dC3RbB9SIK0tiBJ5nXU860fg/tH4r7PrdNtgV+lbCErlm7C3UrJEIHvaBGsBMCSZmqVxHjtsrhux4ZawbD0XNrcKuV4k2VKuX1KBCkrkmAfCYGgjzrpjBxdzj3qXBU5Vlymcu/lU4xdYvxTiy1XmJLuLpds4lb96orCWm2yqJIMABOh5GKmwvh67auWBw4vxqsHG7hbqmVMhtoJuGwACCFqnxHbeJq39jfHPAnZy7jmI4zh1xc4kcOUyi3uEBSH1qdMtIBBhOTJKlb+LTkWwTR6A7GWXuD+w7C7w4Pctvpt3L5doVALcKlE5gVkBIUmFQSAB0rzv/E7/AIK41xG8wXFLdy6U4pxq4t0KNs+24kHwpWAVNE7HUSnQ86n8T+19jt/gpw08KYIQ6hTT4cW4tpxogjIESI0IG52rJsCYxBD49paUW0t5G1LUTkTM5U66CSTFTCHO4c5NK68HqLs07XXeMMSRgeI4SbTEfZ1Ol9pwKYfKSJyg+JJIM5ddjrVR+0ZwXd2dxZ9oeDLdtrmyUhi6Xb+Bxsgnu35HQ+Ez/lrFr3HkW6wzavKFwVAIeaVBZVMTmB0I30q3Xnajj1jwk/w/i9+1j2GvhLa2L9ZD7icwMB1BC4kTrmrD4uypvpceUdK1u+nsq8+GeiOy3iHEeLuAsKxvFbcMXdwhQUEiA6EqKQ4ByzATFLcWca4dwky0H0u3WIXRy2eG2qc9xeKmIQkcuqjoPpWK8PdvuPvYTZ4Nw5wnhVom1Qhhhd1duLQhAECSYJjmSa2FKsimMRvLXDFY57Klh++tW9wNSlCj4skkwJ515WqUaEt9Th8I9jSTlqF06Tu1yyp3OD8ccarRccV4weGcFUorGC4W4falp5B14aA+QnfYU9wTgrhbhta3MLwK2TcKPiu7qX3lf9a5j4RUstwumSSQOtJF5KNcyVcoJrx6/wCTqSxF7Y/o9uh+LpwzL7P9jfEMEw7EHUOrtiy8jZ61PcqjfUp3160wds8SskH793F7VIKVMPJSl7JPJWy46KEnkQdKmEO94qSqlFFJGWVHqKmh+Tr0neMw1H4nS1rqcFf2ZjjWDcH46+TaYxb2FypRSlt2UGRyIUBB0OnpVBvcLetL163ZIu0IVlDzBzJV8Roa0vtH4FcxUqxnCWc1xl/vNsB4nf8AOnTU9Rziaq3CXHSOE0lhzBmrhOU5lIVkdknXNIIjbpEV9notbDVU1Lh+T4L8h+PqaKo4pXXgqBBSrKQQpPI7igP09K0S+7ReHcVJN3weglWisjzZPqJbOvy3qtXWIcOqeccZwh5CDqlsuDwn11+W2tdjivDOGM5NZiQGw8J3M7UPMaQOc9ac3a7NRHsrLjQ3UXF5jPQbafXWmpPKZFJ4L5AMzr9aTdlPiSmfKKVkq0JJopAiYNLkY1UghalGAuZ846H986ksNw26xW5FvZNF1yM2hgASBJ6CSPmKcYfgb2KsrcYW2XG92gJXHXTWnvCWOf2axly5fW6hBaWw4ltGZW4IIkjYgH9Kq1uTNu/HI3xPhrGMFAN7ZLRmT3kp8YSmSJMbDTfbzqMG0kbfCrfxTx+5xHausNJuWQtQGiyM7espXBgg+ExG4PlVPjbT0M0nbwVG9shkkzO/50m/bt3QSHEzkWFpg7EbGnuGWKb+7DLlwGU5Sc0ST5AUXEbE4fchlRSTGYdRRZ2Dct1hFRKVDSDuDt8q5Tq3D41yqIzHU0RSiQU54HSJFciELClpCgDsedIYYbST8TQzP9OtApWZRWEJSCZCU7DyoCrodT9KBmz/AGZFqPFeMySQrD0CTOuVxMfIV6OBkz+VedfswWi38dxy4JUltq1bSDqQFKXJ02mEDWvRYVy8J9a4q3edlHtOkdPrXUfOf5EfKurI0GwAiFJCifOs+7erdSuyPiQIUUQy0pUidA+2SB56b1oJE+FSRvuDVA7dVFvsi4oKQpX92RoNY+9Rr8N60j3IJcHksqgxEj1mgUYVI6VyRlBjTz60WZ3P11r0TzjlZVDxBBEa6TTq2xO4sxDbqsuXLGciB03puUoDBczwrME5IOoj3p/SpDh7AbviB5SLZl14IOVRaTMH12pq6ZErWyNrjF725SEF9zKPwhRimjlym0t3HlwU5cyiYJ+E1d7rskx0NuONgEIVBQSD9QdarF/wTirDilXeHuOJb2SoGE+eU/nVOLeWRTqU+EyFs8TavHFNhpxJ5SJB+I0p046tsAtN94Z1GbLQpXGWDHIRpHpUsuyTxDh5S0rubxvXMhUKUAOtTZs0lNLPgacOcQpyvNu26g2FZXG18jzpa9sVsHvmUly1XqlY8WXyMbc6q+J2GL4Jee1HO4lYTmhMZhy239alcK4qtWRKHkpM6odVlApJ+JA6ed9PNxcL9NdvOjqYdAKiy6lA1KiggD6U+Y4zwpDqChu1YU4oB5xCgogTqUgeU1qOI4XgmIcP3LFuWw+Uqh7u/cT+FYk8tCQJMGr2xfDMnOaaujKMPtGr24DK3e6zpPdwJBUOX5/GjYlg9zhSk9/qlWyspT8waZYdjqMMxltbLjQvrJ8Hu3BKStKtRruJBrcbfD8G7QMBD1oGmnlSpSMvuq5oM7froaUYqWAqzlBpvgw/kREetASeYnUTHOrrxR2Y3uAMKuWbhl5AUElsGDJ2A318qqDlhfMaqtX0jkchilKDRcasZK9wb95h9/NbM922BABAknzjSkARGutdqSrOmFc50NO2LFBZ7526aYTMBJMrJ6Zd6lXbKukriDT7rC8zDqmlHQlBilEurU8h12HFJ3z7K9Y3p7hXDmJ8Q4kMPwiyubt9UQMhSAP5iTokeZrWuGvs+ltTNxxBiSCnKFOW9rMkz7pUdIjmNelZVa8Kfczoo6edXMF/qVzs/wAVx67bOBcK2Lbl88tT13iF2j+7WSDPhAHvKmDBPMaGa0XAeyGwRiH8V4lvLriW8SmG1YivM02T7xS17qfIaxFW60awbhm1Ywu1XY4cwBLbCnEt5up1MqPU6mq1jnbRwLw9ersrjF/a7pCcymrBpVzlP8pUkZc3lNeG4uc3KnHk+mjJQpqNWXFl/iwy7TrjiLhn+FYrgGHIu8Cs0OoxLD2DkJQcpStOUeEpgwQNJ1EE1kXGvG2MY4m24j4dxa/ZwS6bU37M0ru3rZbcFzOlJiYIMg7KHKrbcfaqZt7ha2+C78tEBTJeuQ2paealDIQB6E1j3Cd3b4orGGYdt2xcJv0W7JKghgrLb6ANJ+7dB9EV0Q0icd1SOUcstX9tsJYf+xaMPbxDESymxYvLVGVR7/vP7wuRJLtyrwNJJJOVHi20JpxhWFNouU21mhN5fhWdXsQytNJJMLeeXqmTzUpOgHgNMsNXcJwG2tMVxVAtbBlwtsW7v3yUFZzFxWoaSdfdBcVMRzpldcU3mILFjYlzCMJcWe6s7UEOPKIjPl94kiPEpWnU1g6fo7epxcsd24yoIt12qMYvLVK1+zsgKtUbkLObc7kZyJ5Nnc11/FxiOQXC2T7OgoSi3YSWw7B0JGhUOcAActYps8y7hzAw66V3KUwV2LDpWHFKGpfcEAq2GROmmvmzuH3G2wGBnCEwhlBCABOw5CunT6RStJ8f84/5/qcWs1+xuFs+f/v/AD/QcLeWqeX+UCJ/fnSFtdh9xSIdbdR7yFb/AA8qiG8TxnP48PStM7JMH5yacPi7v2Ulu17i4GocWv3flv8ASvVPA2tMlSY0g+XlQDeNdNT1pLDl3N2GkqLRKvArUpKV7GQZ0312in+JYbeYLfvYffMLt7llULQRr5EHmCIII0IilcVnyRl7cpYAQS4C5KQUJJIEb6fCmGGNNNOhLVkpIUTL9xotXpz1+FXTgbAzjPGeD21yyu9s3bhKXbMJIDqNleIEEaGZkARrUJiWGM4ZjV9bZmXnbR9bJLT3fBsSfCF7GBoSN4mi+bFWtG6GuKXLlnZuXDQZCkCR3m3+p6VSHnFOOrW5otRJVpGvpV4/tbf8GYxYYphyUe0thzwvtJdaWlQyqSpChqCCROhE6GnTN5/azisYzhPDVjhLjy20WeHWbZW2VxBISoHMVE9PhpNJt3sXTsoXZRcOslXdwgeAISQpRWdI6VarkNNguuC6eSo5S2gFQj0GkVej2T8VMoccu8EuLBpLa3Gu8t1K71Qj7sBIMKMmM0A8qh8bwW8wVq1axDB8Rw27KfEq4SpKHhJIIBTIOoBExAGlOLjbDJqOV+CnXWM2xQmzt7FZfK0pbQ6gJTHpv0irhhPAfEGP2Tt7/CGSwxoVOLn1IBTt+oqEwr2vEeI/ZcIw+1vrttpSlKeUQEAHXUdP1irVg3EPHwxY8P4jYOoYUFEoaSAmAZKsypJSIKvD02q4pPkyqSaX1JLs/uOG7biCzYvHm7hp3M2pxaYaQ9slJB2E+usTpWxvJUqQozv5VjPHHAl7gWGKuMKs7ZQLkJDq4WUGYIAO+hkcuvKrF2R8e3vEdqrh7HB/2rZtlxt5Q8d20DqBHvKTIJ6p/wCUz4H57QzqpVY+PB9J/wBN66nTbpS/k+S/JlMgiiLaSToNfKnGUoTtM9DSaikStxQQmJmdhzr43Zbk+4UvImywpMBKhNKhsokrWkAb5lRH9Kymy45x3jTiFyww15i3tiUtW9qHu6VcqUsJlbg8cBJKiERsBrvWj4b2F8PBhwcQuXONPrObL3zjNs1/lbbSrbzUVE716tP8ZZf1JW/3PMqfk1/BXF14/gtssd/jWFtGYld22IPzrOePcXwBvHQnD3be5FxbB+4VbLztZlKIGxg5gJMdK1NfYt2dKt+6PCWH5YiQpzP8801jfH3Zi9wDdvO4fZr/AIC6v7l9JCy1IHhcI1BB0BO8V7P47SUYVLxk7ng/ldZVnRacMfp8EG85gbqc4QtrWAhsGfXpUdcN2yFBVs+4sHcKQQQPWkjqJJk67iiEmdq+jcmz5KNPb5BzQInnMUBIIyj6Vw8ZAEamPjT/APgN4l5KHEhCTuoagClGLY3NR5I/WJ/OiKG/Q+U1J4ph1taIz274VsMqyM089KjYM6R6mhqwRkmroAEiSJmNxpQBRO9DBMCdK7ce960hgpEnTrprXJgEkjTl5UZOmuY6a6VMNcKYw7hJxNu2BZSFKyFaQ6UjUrDfvFMc/KntYPBEoUpJlsKB5FP6VIMYG/coLq3EsqP4V+FR8zMedNLO7VZXCHkgKKeRNPxxNeZnO9Qy626YDZGg5QN5nzk+dVG3EjKpv/iK3GAWiLRx5q8WtbQKl5ogR5DUT9ahBAIHzp0+m3eI9kYeYUQS42tXhTGu/wAt6aEwInSlK3guF7ZB0G21AmBJHwp4nBb5TId7oBJ5KWAY9KRftn7YNl9IT3iSpIncTE/MGltZSknwbl9lx1zveJmRPd5LZZgx4pcH5VvwQidCB+tYJ9l20Wu34lu0rHd57dnQfiAWTr6EVvIzAHMkBNcNbvZ20u1BpV1TXUbvF9HPlXVjc0EM+XkI61nX2hLpy27IcfyNFZdFuyoJ/AlTyAVVogUBolWX41Qe3hRR2Q8SrQpJV3LaVSJkF5AI6czrWsO5BLg8kqSVSZM+lE23ihVOgJ/1/evyosEnU6V6LPNJbAg37R3d3bKWw5qha0wEr5GTp/tVzTxBiDODtsYdcWLztv8Ad26y0ElkHllHhPrHLWaz9d6+42EqcUUhIABAoGL+9tf8B/JOp8IP5itFNcNGE6Um9yZrXDmI4liDCEnH3hdtIQHkAIGRR11SU7TznKTzFTntnEtqtbTuHtXoTEPNnulnpI6+nzrGbTifFmnbcoeaS6hYIeCYWNRzmBV/Z4rxKxsSUss3IynQOFsjntqPgABWsJXWDmqU1fKsRfG/BF1kcxlmz7q4WoruLZA93qYHnz2rPmXnLVzvUKWhaZg7EfvpWis9sV2Au3usKzsDSBdnOlWxIJRvTO9bwXiFa75FspHeEqgOAEHSZPXUEjzqNqm/qaqo6cbTV0F4Qx/AF27rPEq86wfugppRSRAiSARvMyOe9DxpgfZ8WWLywbYcW+fChtQWSmCVE5IiDETvJqNc4PQoy0+83IBSFt6R60ieD7gT3b6FnoE6n4zFDhLyrh1YXvF2KdfXeGYJcqbtLNxOecigRny+ZNapZ9quBDhtpyyw5trELdCgzbsBUoWElIhSkQEz4p6EgzsaJdYGrCrhbbjISpySVoGquvxoigSSDtsQob1jlHU1GaTeSp3ODYq+6u5cQFuOLK1FKhqomT5b1Z+GcaxvCFFxC3bV/uyn2hJBzp6Ea6ilyCRrp1AFRpwVKXVuMXlwznJUpIMgq56RU2ayjRy3K0ixv8X4wu6auby5cvkoUCUOAKTEyRAGgMaxBrQ8G7VODrqybQ/b2zThkOtKcUhTW5yhJGonQRGlZpwd2b3vF2MossIS8p1Wr1ytasrKealEafCvU/BfZbwrwI2lzDcLZexEoAexC6h59wxqQVaIGmyQPjWVbWKj3PJpS/H9fhf6nnXi7EcN4lxW1Y4dw094SQpVu2SXlKjwpA1MdSBrNaLwj2BXSUN3vFFwGHCZ9itYW6ryWsyB6DXzrR+L+OOEuzHDRd4oq1s8yiGrW0aR37ijvlQI+JMDz1E4f2l/aLXxVaM4HwSu9w1q7EXd9cANuJB/AjKTl81AydhXJ8mrW7FZezsjo6NH/uO9vBtd5c8J9kuAO3l6+3h1qo+8sDvLhcEhKUjVR8vmayq++03fXiUq4e4RQG9T3uI3OiukJRHlzrHGbJKQhVw47evIkJcuFFeX0BMCnSlecAchpVx0cW91TLJlr2o7aSshri1jccR37+KY5iVxeYhcrK3XZ0k/hSCNANht6UUKbwe1DCi43bxAfQiCP+aOvWP61PcP4Dd8R3jjFotlIaaLzzry8qW2wJJ6n0ANWS67LbprDHLw4hbuJCVKyFAAIAJMyqRoOldqhjBwSqNv7MoqW7K7bzJc79K0BB0CsyZBy79Rtyik7LD3cHxVGJYNfP2FyhJShaNTCgUqHlKSR8aZqwJLTwfw+4VaL5iMyT86Xu7ldqk94otpCdH2NNfNOtKy8lKTi/qx9aN2dheKVfXuH+yupMNXeYqR4grMUJ3gjQTB8tqXwq/Zu7xSsDCWniAlx8KJWuBGZRUdJ3jblyqltcQXqc6O+b/yrU0J+lWvhXD04tds2FhdNKuHjLriCBlndRA5eVYR08G85Outq6ihjD9l+4f4Fwtu3Vi3FGJIbYUnvAjMATpOZR69BuehqQF12Xv27qG2EtAIKStRWhRgn3RoTPL65TUha8GYRw7YNu8QYgu/JKghlYzIQVJjwokiYGumnXaqrd4dwtcY0i2sGu5bfWlCUOPFZBJ1MJ0HoTy2rvUbKySPG6m93u2QAwR7FLq6GBW9zeWjJlKoghJ1CTMSRr8qa32EX2GqSm+sn7cr90qTofjtW04pcXlgxa4Xw20zbMoUnOpACglIVORIOqioyNdBKiaS46vsMtOGlsYgpt8rBSltCwhbiwJhMiTqR6aHlUuFkWqrbMWtrpVtcJctlKZuGyHELyglJnRQBBB289ta0rAMc4v418OLXuFYrbpKgg32FsrcLiQPDKcpSPFvrryrNO+xC6ZtrFh1tSUulSWlNBZzqAScp94TlTpMSNqn3rnijgVNraXTL9gcRt1OdzctJIUEKyhQSfEkwqJ9d+WDjFv7HYnOMXt4Jjjqxx/htL68N4mXZW95ms7q3tmGmlQpAUEoUhM5CJB1kQJ3qgWtqxZtBphGVI5A6k9T1pfjLivGsVFu88pl5xH3LTLbOVKBqfClOknmTqdKRt+9Ns2XtHCkFYA2NPak8C3Sau2Mccwz+I2oWM3esglOnveX0pDhx2+tVNONYg40+y4FBlSiFIAOikncEbgjpUneOXDNqpVuyHnR7qCYmqTd3T928V3Dq1LSYE/h8gOVJ4Lp3asaLxJxxjWOpQzj3GeLPoQdGBcBIE9QgCfiKr4xlWO4tZYTiPEeJNYM2uUKeuluoZXlIBAUYTyE8gSdqqexkaRXEyZqcLhGtm+WaTwbxPhHZbxJiKH+7xll5Ce7ubNxDhbgk5TrlMkiSCfdEbkVLX/aqriziFF63Y3bLDbZSkqWBCtPEopiToNOVZZhdoi4um+/8LBJBUdATExO07VdmwkNpDcJSnSAIq4yaWDCrTi3drJL4/jTmNLb7y8uXUIJIS6VEImNpPlTOzvrnDrxi8s7h1i5YWFtvIMKbUNlJP7512HYbeYpcC3sWlOukTA5DrNTeKdnfEmFWwuHbLv0ZQpQYJWUjTlz35a6HSqabyzGLUMLBo+B9qOAYraheL3lrg1/BLjLpKWiRupCiIggTl3Bka6GoHi3ja04jwhA4axmyZT7QUXCrt0MpfYKTqJ1KZ3ToryrOrfDr+4V3TdhcuqEqIDCiABvygRSLmbMUOJKSnQpWmCPKOVeTL8RR39SJ9BD8/WUOnNX/aw//wCkn2eY9hPCfHWHY5iqmhatKcbW7ZpU4xbhSSAqZJMHoCBO5Nep+HeIsG4swxOJYJiDN9aleQuNH3VD8JB1B5615FLignQpEiOs0hwvxxj/AARxSMUwZgIQSGLm1JHd3aR4ilQGxjYjUfStK+hU43i8mOn/ACLUmpLB7Xyjz6U2uGGn0OMPNtvNOAoW04kLStPQg6EeRqucB9pGBdoVkXcLfLV0yhKrmxekPW5M/wDuHLMPptVrAQpMjX15140oyhKzwz24TjON1lHnrtX7LTws8cZwa3cXgrpKnWkpJFionaf/ACzyPLY8qiOE+ErPiW1Fwg5HmySWkKSpa438KlCE6j1r00o5gfAFJgiCJBHMEV5+484CvuB7q+xXCLJV1w2EF9YSoFVkZ1B5lA0gwRBg7Sfa0OtU/pU5Pnfyf4+cf6lLgh+KuAHsOR/EbRaTbrMRlCS2qdEqAJjcCZOuhjnV047iKGgz7SSiIAKEnTptU2z2p3C7NNvZXBWUt5EpUEKA10BO6kjfKdJioPDLJ3H8ZZtXLmHblalLdcMkkAqPqoxoOZIr1G/7WePCMnia4GbjpddLiyVKWSSTuTVg4G4esOI8cTZX946yiM6UNg5nomUg8j5RJ5RVu4twLhLC+ELt3DWWHXSEpZeA8Xel2JCj4j4QolJ1EbdcuQpTa0qSshSTmSUmCD61HDyaJ7ljBoHaNwvwzgDaTZqcYvVlAQ004pSCmNVKQrxI2PPXkIrPwSeU+caxStxe3FyhKXn1upSSRmMmdASTudhXXDLbTVutFy08XW8620AgsqkjKqRqYE6TSlyOCaVmxfDH7e3uSq5SVIynKAmdeU+VXjiDtQs75ppmwwqQllSczxCEpWpBTmATOaCZExrWdbfi+lCJ6/SnvdrAoK+5klw/hCcbxhmx+8bZWZWWhmUlIiYnetYwrgSw4OtBdXdt314UlRecMkD+VAEGSNNIBMa1mXBmNW+AY4i+fccZUhJCHkIKy2emX8WaMvlM04xrj7FcYtE2pCLVvJlc7paipwabknQSAdPmacWiJxk3h4I/iHEDiGIuukt6klRa92SZgHmBoPhpUXpEGf60ta3XsilPJYDiwMraliUpPWDvpPzqUw7GGzb3VxesvuuogreSR4pPhTOmXYARyBowy77Y4yI2GKtItyzeOXBDYlAbAJWI90k7ctYOhphiN/7U+u4U3kSAEpQnWEpEAA89vma5hpNxb3T6nEtdyEKyQTmKlQEg/AnXpSKhJIgR57GhyYKCXBvn2V7i3VZcRCPv3HWlpOs91ER00UZ/6ta3mekJHLSvNf2ZLbu8fxS4zZQhhDOTOI1JUCE8/dVr6V6TJ5EAn0rz6y+zPQpdiDx5V1dH7iurGxYjqTIgH0rP+3xLrvZBxIlpsrzNNZ50hIdQVH1ABMVfsySSACfWs7+0Iy+eyLHg2oNf92U4ZIlAfRKfiK2h3IJcHlRNwtLK2gqW1kKUg7ZhsfXU/OklBB1gk8tYApw5h90LD+IFom170s97IgLABgjcaHSdN6bJhWu4+legeacAdY2oj7yWGytbqW07SogCaf4TZtXd+208oZFAnKVZc55JBjSf0p7jmDYKwhlsOqU6FpDmRUqyk6lIMxpP+tUotq5LmlLayse3NLCUi8tis/5hr5Vd+G8bU6Ba3S0F3ZKirVfQeZ29apfEvD1u86z/AA++DiEoMheoBnrv8D0pr/F3MMaDN8yovJToQAQ4PXlRGTg7jlSjVhg0jEOGmcRWXWD3ThHL3SfP51G2lri3D92i4slocLbgUW+qk9Qf0M0HZ1idziGFuKungo98pLQmSkaGPqaueHYLjeJOOtu2BtmkKSlPtEhTsgyqI0Ag7n51vaMkpI4W505OHNgbDtm4cxG/Rg9zYu2zjxDSkKZ7wB1RAyJKSCdeZE0644wz+B2ScUtLa49hgZ0KDraZJAGqkb6jSdfzrXEHZbiNu6/d2DFo+FkuOIbWMyiAZOvp8aqtzaYtaJLV7Z4hahUFSH0KSk9JJ8J201rNzlHBqqVKok0R9zxNb3V47ct3qGn5KUd5JCPKTuN/iah7/HsXeu1KbeavNiVssjL6aVOfwRN6C8LAPDWV93mHzA1qf4N7Psb4yf8AZcDsB3KVZXLlQyMNequvkJNYTk0rtnbTUeIq5TMOxLFcUxG2sLfCrl5+5WGkNNIKluLOwSIGtbDgXYJxbe4lb2+LMNYXaqbS8+93qXFNAnVuEz955bCd60rgjsQwbhR1nEMSfVi+KsqC21CUMMqGxCNyR1Pyq28RcX4Jwth11eYziVtaot0lxaC6nvFGJCQiZKjyFedV1rvtpZPUpaBNbquELcO8N4XwvhzWE4LaC2t0nUkypxX8y1czXnLtL+0lxJ/G77COGQ3hFrZurtzcLaC7h1SSQVeKUoEgwInzpnjXblx5j/Eb13g+Ir4dw1gQxaobQ4YI0LkgyuDPQaQOdZlfcPPXF09dXOJIUt1wuLcc1UpSjJJOgJJP1p0dI196mWFbWRxTpYSC2FoviJ26xDELq6euFrlTy1yta9ySTJNFu+HLxyXkXPfqSNARlVpsBTnDre9wd02wZTdsOnOFoI05TU3KVHVQB9K7lFHnSm0yB4Z4WxTifG2MLJumW0+O4uChShbtDdRExA25amnOI8Wss43dG2s1NWQVkYbUcykoiAo5hqVDxa8z6VKhWSU5j4xlUAYkdKSLbKVe6gSACQnlTSsLfd5R2GcTIsL9i5w+7Ui6BlATqdd0qHTeQd6nsY4x4gx2wbscQxBx+1anK2QBpoYJ3UkRoDVZxRxtq2JFp7SVGAhKQdetVhvGcQtkBnvSQnQBaZI8tabn7EoKWS2KvWkqLYfa7zbKpWXX41CYliuK2aii4ZtwhwEJgEiPnSDfErpbLdzbMvJ6xH5zSjb2D3xLjyVNLQJyKXCSPKle5aht5E+HLG1vlPe0IK1IAKRyqxYbas4Q731ijuXP5zJn5zpUXY45333NnhpJSJhKgBHrGlSynFhCSltJWQJBVsfWKcUiajbLRZPYrjiUurfduWWCGUodUQhCDvJ21JA666VIM4Fg9i65d47j2H2pSmO7QBKZ5K1npvqRE1V7LBMaxwuW6Ww3bnxG3S4UhZ06nXYDb40yxbBcZsHFW91hNzZMBYSVBvMHddkxyPnV3dzBQTxckL7iO4axV61tsSWU5iGXLMqbDqI96BBA5eL4UlZ2F9i933Vq0/dvExAOYmfMmjYPwjiV3dvX9w260HUgJt2m87sctfdH71rROEuH8RTitvcN2bVjZsqPeC4SCpQKSIiIESNTvVRhJvJnUqQh2GdC4xvg7ipLySmzvLBoXDK3WgtCFmQFQdFaTvpIp5hL+JdpXGNs5ieLKxbELpaLVVwvK2lpoakJiEgAFSv13px2vYmcT4kumcOacfysBgKQAUpIJKsx6iY9agOG8IuE+yW6bclOZPfNNyouA+8FERCSJnXbSQKxqRs2zqpTcopPz4NTssG7P8RxTjW3wZy4xPDMEwVV1/EHHcuS5SpeiFJgKQRAJI1KdDG+P2AeeWu6uXCp0QlISo92kZdQBzPU1dOL+JMBVhWJ8H8CYejDsHubsOYhiZcKlXxQfcaT+FkHUAn9ZhOHhhthiVgcQtnX8NZdR37TZ8amp8UecGaypqVm2bVnG6jEgb7DsQv2gy6u2SkKzBxCVT+dR97gTGF26br2gqWgg5XEyFq6RW0cS9kacPwC+4owXiDD8QwBhpVyw6VK7xxsGAnQQVcuWvIGslvb/DbouW106Mja4KZIk+WlXGUZ8EuM4OzQi/YN4vZpvX7srcDZUA0gAADcAbmKZMYCm2tzd4kvI2gZu6HvHyJ86kWsWwvCG1ixWM6k5FBoHMsHcEncfGmd3xIi6Crf2cBpcDM7rHmQP60WBOXjgQbYu8cW6LZKWbQuBRBiEkCPWY+FTuE4aMLt1o77vCsyVEQkUyw7DcPW0pli/dWqAV925lk9Y8qufADfC+C3yX8Yfu0KYXnazrK2lgoUFJKQNySDJ/OqirkVZpISwtrGWLVV7hrN0hlKs/tLUpykRqFeX751MYL2wY5Zp7lHdXbRJzEIU2BrrJBy78gmrNecYM4hb2+F8MWr1w44P+8FBZSN5V4tVKMzJGnIE1R7ns8xPAHS27cjItSlJQ64M3IkwRmglWhO+taWkndHJFwae4tV32zYmkZbTD7ZYyxmuV667iEITp0qjY1f3GNY3cYq73LHtGqrdpPhBgCZ3mBr61eF9kGImwTd/wAWtCsQ13SWTGaB4Z5nlMakVV7jhZy0z99fW6EtkpWYIyxvSak+SoTh/EgnGwsZQpxMagpVGtJN2KEvB5a3HFp93OokJ9Bt/vTq6Swy+pth4PJAHjiB8KIpIQEqLiCVJzQCZB6HTf8ArUtWNlJ2wOMGxG44Zx614gwwJRf2qwvfKHkfiQr1EifOvVfB3GOGcc4K1iuFLGRXheYUR3ls5zQscj57EaivJObUDnNWDs840d4A4qRiLhcVhlykMYg2lUfdk6OAHSUkz1ietcWs0yqxuuUejoNW6UtsuGes0gRlKopJxttaVBTbbyFAoU2tMpWkiCCDuPKjsqQ4gONlK0KSFpWkyFJIkEeUVykx8NZrwFhn0mGeOu0jgAcGccYq1hwV3KXE3NkykjRpwSEmeQJKfRNRWGG+yrdvIQ7nlCUkeADbbzrXPtKYFcDEsIxxi1eeQ60bFS2F5SlYUpaQesgmPQ1g9ziuLWdwGFpUlZjK2tvxa7DYSa+k09TfTUmfLaqltqygi1POvXby3XXHrh91WZa1ErUtXUncmiLQ4wrI42pBGsHeKHhrGcRtku3FzhqkIEBThBAiYkSDzgdNanLWzc4meLz6ghpv7tLLUqIMT8zvXXFJ/wCTzpycHngY4lgOJ4UR7ZalsKTnCgQQU9fnpTFttbrgbbQVKOyRT/HLEWVwkKvFPuRlWl05nEgRE+W8elDh+Jt4exLLJ9qk/elQIA5EAjcUnHOR7m1eIF1glxY2Sbq4UhtKlBITOpJ5CmyGCpvRJCpnMogCKlcL4nXh4e9pwuxxR13Tv7zMtxKOaQTIAPlEefJpjV7h99ee02Fo7ad5KnULWFJzEz4Y2A+HoKTa8Dhut9hkRB3B8wZpJLqFrWgHxNmFpjYxI/MUcEkHz50Z1pVusJUpKtAZSREVLLOauC0HG9AhYAUcsmPLpQ3d2H0JZZbDVulQIbA1PmT1gmo64xK0tld266AoDUZTp+lMnsUun3W0WNstxvMMzikHKR0p3BR9E43iLX8NdwxKYdNym4UoDZIQUgeepJ+JpBuQokqkbQd5qPw+yukXD13eKAWsZQgbAVIAocbUkiVAgoKTGvnO49KQ7ZsjZfszBR4txJSc0ezImCByd35n0r0pEwSdKwH7LmGNL/jOJd6sXCVNsKRqmUwogxtzVrvtXoKOWoBrirO8jspK0UBlP+aupTuz0VXVkWNgAYCkjSs/7fUj/hDxEXErKUoZIKVAa983EnXSYkdOlX1IzHRRBHKNKoXbyf8A5PcTgqIBt2x4ZJJ71ECtY9yCXB5GcT4jA3IJ5Akf7n51wGoJmaTcWpT6kgac53pVIVIA6T1r0GeaCQBIOoPLea7JB0ygeVCTzA2865JmYH1ouAVYbQgqcMJ5knnVexHB3H1OPMurU0gFalOgoSPJM6mrKE6A6xPWaOq3dcACe4KdwVtlRSfLl9DSeVYuErO4w4Dwzimwu2Mbw+3FtZNOBRu8RlqxJH86lEBUanKmTptWxWisd4isWmbftE7OrEqAErceDiydJ+9RKee0VnN3iF/iCmV4niV5fG3b7lhLq5SyjQBKRskQBoBFW3hLso4k4yYTc2lm1b2SvduLpRQhZHJI94+oEedZue1ZdjTbGpLEbsuQ7Gu0Kzet12XFmG3DTgCi+y+sJTzHhykqHMR1qfPZRxBjFs1ZcScSYe7aIcBc9jsvvXkjbMpWgI05T51duB+HH+GOFcOwh279rct2yC4mcgkk5Uc8omBNTq2VJbz5gE/rXl1NfUu1FnqUvxtHEpLJULDsn4OsVJmwcuwmABcukgD0ED4RSvGfGeB9l3DKbpy1Um3Cu4tbKzaAU84QSEgAQJgkny585rHsfwjhqwVf43iNrh1qlObPcOBJUP8AKN1E7QBvXlTj/tfV2g4uy7ctu2fDtk6pyyswYXcKjL3jkHxKiYA2k9SaVKFSvL7vBVV0dNFumvsTWPduHH/EbSre19mwBheuTDkFy6IjbvFbHzAG1Z29hl6la314O49cKUVqubhQeeWo/iMEyr5a1J4T2l4VZ40wlXDjtxYk/eNiA4vzCR4Z05zWit9s+F2Vu2XcJds7bQAhpsKIO51MTGkc43FevTo04q0TxKtetPuX+5jYRdWl0hdw+3a2yTq27HeLPPN5zSt6wziKEBLYuEz+F4ISPWN6sXH3GPDfFKF3WA8NPoxBTgWq6dbSlC0RsoTJPoQNNqplvcKS+2hzDmbNRVmW4U+Ex0G0+pp2s7FK7V7WJe1s22W0q9maacEjKg5gPjFR97a4ytedh9oD3cjYyx56zUw24laQpBlB2M10b/7VTSJUnyReEXbjbSbW+7xt8KgFz8fSDzNPLixZuYL6M4iBJkD4US+KSAl+379g+9lEqQesdPTWkgvDkytT24zALeP5T+lLaU88Dy1YSw3kStxSZlIUZjyphi2FNvNuLeK8zih3S1zDfWABt19KIniJhDy0ezvd2D4Xk+6R11j9ipJu7ZuIU26lWYTIMz+9aSFZooKkhK1JzTlMSBvVu4J7MsX40d+5y2zGUKS44Izgk6jyEGSfrQ4nZKcP93tLNwGdXEwQesjerBwD2n32GOYdgZty6ttxLXeBQWkpTOWEAA5gPCCFiQT1qYpX+xpKcnBuHIyxPsex/hvF2re5eSq1WoBVxbqIJTvA/wA0axWhcAcFcOtoft3mHFuIcDiXHglwnQDRKtwDPhg7zyq3P4Pc8T2SF4hcM2TYIIbb9+YjcyYMmB086qWP8EXeFNu3+D488pDZKw1cODOmNglY3O3IetdWyMcpHmuvUniTsSnFPZba2zysWssfxDDbpCVJORxSQpJ1ICTpy90ACPnWa472t49a2D2Dtqt7taTlcvu5KZI0zJTOUHQTGk7Uvc41jibR7EX2bi5bY/xnFIlXUlRJEnzqhYpjaMT7wJ9r8ezYICevIEmsqkl4wdVCEmvvlGocJdsDGHYQi1btb6/xDu5WsNIQgua+8qdB6A6RpO7jFu07HsTt1stLFi2v/wAlas3wVp+U1TOGGLRuxaav0LtVKE50AaHlmH7irJZcKqxPEWLa1vWlMuf+KTmymPL96VScnEiapxlwQBUQSSoyrcgyT61ylPLYdtm7q+ZYfTkdaYfUhDoPJYBhQ9atOL9m+OYcVLabTetpXlCmgQIidzpMbiZ8qrjSPZ7pv2y3eDaVgrQUFKimRIE896zlxk1g84JfBmeEuG7FOJcaJvlWrg7qzw6xOV9/kXJMAITtM6k6TBquMOhwZkofQkqJQl4DPlnTNHOI+NbF9p3DWlcM8LYxZMMhm1fW02oDxZCznbT/AMv3Z+dYzc4kmztBcvSElIGUbyeUVz0J71vOnU0tjVPks3/EH+E9m+N8ItOqunMUeby5VBTVkzMu5iDoVFIgeZ8pyzC7JWKXwS53hQSVOLTuP2asK7/D8SsF27dwGhl0SrwlBGoPw0pLg6zvblb6w24UOEfeKBgnXWf1q1BJ48i6r258DK54eurR9K7FSliCJMApkRPpv51YMD4aS4pu0YtkXFw7Eqdy6T1J0ApwtJQohcpUgkEEQRQpWR7qiCRGhjStFGxj1HJEmcEw/hS9CrmwSb1TXhLYHdqSToqFQQT6DSpHgnFba2xlab7DUXdo4C4pLZAWwRsUTuNYKTvVamSTvJkzR7e4VbXCHmjCkGRruKtMynG9y74VxTcM8U3K7W1t0MoTlZYAyEwQQqYVqTlnyAiIpXizE8T4puGloz2aUKzPOd6CqBIRomANCZ66HSIqpW+KtnF0XjqC0nYx1PPSKt6QHWyUgAKA8QVt0M10QSkjhqSdNoTusU4nvLRmzVjSrdDKAkqtk9244dsy1SSfhHXfWoYcEYlfoSW31XDq1BKMyicy5iOvSgusIxBh8rsr85CZCe9Oh+NchviKwcRfC8KlJ8QSFe6RsQBEGeYg1LivKHGT8SQxxPg3HcIQldzYlxCwSF260ugACTOXXQc9t6hilSScwII5ERFblhXFV8vDgcfw123hKM8ALbJOhUUjxIMRJTpJ11pvjfZ3hmJJNxYNNhegUic0TGmg1HRQ+VZ9L0arUtYkjFFJSUmYAPKKZXN2hhp3PlU37q0lJP0+dWLiDCxhmNrsHS22G+7S6pGqEyAZ0HIH6UvivAq0s3N1ZKcumBAOVCjCYmUmMqgNZIjUECYNZShdnbTq2V0aD2E9sCX023A/EDmS4bQG8Mu1qH3zeuVlfRYEBJ5xG8TuxGXw6HTnXkrhjs6scTYur/GX7uytrVAWh5IyKa38Y6xHxISOdejezXilHGnBlliRUVXKAba7lOVQfRoSRyzCFf8AVXja/S7H1I+T3vxmt6l6b8EjxBg7PEWD3mFOIbKn2lBtbiZDTgHgX8FQdPOvJnGVxjGEPvWF7h9mziNo93DichORRP4TmiDIIMagivY6JClJkQelZ52t9mp42w8Yjh7KFYzap7vIpWUXTI1yH/MN0nTmOlRoNVseyXDNPyWk6lqsVlHlHE+J8bu+7w64uE2yGoRkbASB6kfCn2DfxuSGblNwlw5AEuHxp5kKHIefQ1NYvwXjPCz4VifC91h4UspS++gBC1RMIXqCfjUNdBu1cLhsrtte4dtTBn/pI1r2oyvm54Mkl9bWJe7YVhhi7ytFSc8k6RTROJ2StRdsQP8AONKHD8NbxvvrhA9sebAK1XSypU6wDO2x5UAwlXheuv4c6kkpShpsEpj11+lXnkxVlhvILuI2TQOd9sf9Q1rkX9m4JRcNkc/FNcvDLJaQlVmxHkgD8qZO8L4e4PAHWzv4VTHlrU3LW3yP2ry3cVCH2jGnhM60R3EbRtagu4QlQ3BUB+dM08MYcmCrvjpHvj50pa4JY2oSpDXeOJnxua8942ouw+oJvwtXdsWjz5nfu4TPqYpQPX2bW2CRG4dBmnM68/61xBB1UI2NBLYUKUQPdmNR0pNUBUqJSIO3KlPe0+HlRFpBSSUBWhAnagFg9CfZSfQ5h3EBTGdDzSVqEAK8JgxvMCJO/wAK30JCog6VhX2T7W3b4Rxt8NQ8rEEtLUUxoGkkDfkSfnW7FJBgx6iuCr3M7oP6oNC+prqUjyP0rqzsVcYAEjc+lUXtySn/AIR8Sy13g7huRJGneo19RvFXseHXz3POqP22Zj2VcSZQVxboUoD+XvUSd9o+Nax5QS4Z4+Ug96pZM6ZR6fuKEp2BAn1oFz3k5oiumDqfjXonmg5VczNAgmf3FcpPOfhXJTsdfTlSAWQ0t1WVtClrnQIBUZ9BTteE4lboSt6zumG3DCVvILaSZ2lUAfGKleEeJUYFctldmt4ZoAaUApU6HXkRMg+QqY7XeObVfDarNrDypd9LZdByAbEFQ5nTQDTTercUo3IjNue1opFs6Hlui3PeJZJSX0GW8w6fzDz29atD/aLxle4QjCLjitdvhjLBZLdo03bZm491S0jNEaaEaGs/wXEP4o2bVxgtstIAGRUDpHrudKmHG0KQwh0qUzbIysNqJUltMk+EbTJNYySla6Ojc4Nm02XbRg/BPZnhWGcP4i1jmPhkNN2y0uBq0BJJzkgQlI2TMk+VDd9uOJcPdmKL3FHrO/4rvHVtWDaUAFaZALq20jwBM6A+9p51htziLgvLexti624+CpVwAARAJKUiNOUk7eVHwjhDiLEb+4/gjab1a1JDtw+oAtTvJVvuD102rB6WDfHk6lrJpXvbAbGsWeur04rjty7imMvAFTz3jWSBASlI0SB5RSFrbssqF3fOoL61eJ2IyJnZIO36nnVgx3soxjhuxTi93crcOXxvtqTlA6AHl8KpdzhuJXCl5w5c2491C3QknzgaV07duLHKpKfDNkwPhPgHHba3NtjCri4bJl1Kx3kcwpEgp9I+J3p7inZ9ghSli04juCUqIQw+E7iRABMn961lnA68Kae7u9fZwN1KsqHn2VL78GZBVGg2ETOxFXvELTh25tkpVxbYutuH/DZQsKHrpHL6itYuO046sJKV0V7jKzs+HSixdu1ZsgcCmyEIUmdFFJk61R2cZxDELtSLJhvugSErWFQB1J/Srw7Y8MWzqkJdNygHQhOivp+4qu8Q3dmwFoYeNk0o5UQmVAc9B+9amfs3otcWCs27qlFVxdd6sbttwlIPnz+Zrmbh1Kil8oLhOjLYkpHWT+sVAM4jaYS/ntFuXKXAe8z6Enly9ak2scsLhvKp9TC1jUgZSk+u1KLVjVwZKoWVe82pB5AkH8jRsoOpAnrG9NRaoeDRS+ruUJAQlC4k9SoamnjFs46ShkZiBMZoJ9J3NDXozeAikpWIUgEcpFJ2PCjWMXTiLOxDrsZyAYgTG3WeQo7neoQrukBShp4zHzpfAOIXcCxqyxBTIaubdzMhKjKHBBCgFeYJGuutCVxPdb6ltwjsZx1zDXn2ha2ZVANuuSVaAwSJAO2mu3KqpxFwZfcOlZv8DCSRBdSBk12k6RJjer8ntfuV3SAq0KbUEaKVnVIj3kiAU8tNdZ12rR7/ANk4rwlu2Bt30XDK0oJUlxLkiB5QdfTXYjTVU4yWOTmdepB/ZYPL3BvHl/w1eLt7q+vV4e6ktLZDxUlvXQhMxHpWkWTbfFzKhg9+QQiZZWEZdNN9Oex1qxXXZFhuFvLvW2xeqCQFMZmx3aSQPDOhUZPhJ1HpVM4s7Pce4Ged4m4Vecw2zQxmuGwpaCsjVYCDMo0BhR/SlFzpqzWCpqnXkpJ2kHe7GOMsZuO6xHG0JwkKzkqUfqkAJKo0zTyqG4iwfC+CnrfDW8VYduFjOttCCgJGwJUesc999olvYdtGNIdaFzd3JaBEhKUCOpBAB03q4ItcM40S0Js8Q9oWQlSiDlKup3CtTvrSSjLt5HKdSm0qix+ikpWlcKSoKE7gzPyoWX1NO940soWk+8kxWhWHYvhXCOJNYhiGILctD/4GfwFZ0G0kjYaidfKrhZ8L8D4mwpu3tLXvukBKz6J3OnQURpsmpqIrjJl9j2s8VYC4zbNoRizTg7vLcqIypGsApg/OR5Va8M7V8DxBLv8Aa7AH2cic7TjSU3SVL/CCmEkAdYNO8Z7F7S7Qp/BcQKSBlQ08ATPMDYjlzrK+I8GxfhnEVW2I2wSkKyDwmF8pSrY+hg0pqUeSqTpztZZNGfwLCu1Vqzv0cZ3133K/DaLu1OJQuIP3StUfABMVXeKexPHpeTbXzD1sk7GAR0E8tj/Ws9ucJtLq2U9h4DVw2cychIII5RyNPOH+2HjLh55pScWdvmmk5AzekujL0ze8PgazTilZo6NlST3Rl/5GFz2f4vZPqYumXmXQdEllSpEbymRVzwviVFi2zZu2aEhhIQEIckgAaCFCYp0n7SGILV/eeG8OWCAD3bqwdDp72YfMGp6z7auAscYUnHsFdtlGMyF2qbhBG3hIIM89RyqoOMXeLIrRqTVpRIR1zCMZfcyuJtnXAIUpJSQQOR2+FJvcH36UlbBD2WZSUkGfWrS3i3ZQ9fMvYY+FhpYWkiyWhGYagHXUDoUkGBVosu0Lhgr9ntkBxtCB/hMuKUSIgALCYA3Gu/KtVaXJyS3U+3wY2vCb5swbZap5o1BoicOvT7lm/oYPgMVoXEWM2qGfbLCydabSmVoMIUsqVuY0ETGlVF/i24WoltsoTySVSB9KHCK5HCtUlwhm1w9iToKhakaSQVQa5TuKYS2WB3zTYnlKRO/pQLx7EXlFffBJOoyoGnx1qUw3iZJa9mxGDAEKIkK9Y2P09KI7X5sOUqiX2SYxtb27u1JT/F32nT7ocXlQfTl+VFbxfEsLu9Xg4pKgSCBBgyDMT0p+uzwPEyvubjuXJkhChHyO/wAKbu8KXaE5mFocSdQNjFNxlbAlOEu40fAu0jC8Ys0WV+0Wlp2bcAhBI1UhY2EzoRz1MV183jHD9wxe4c8xd4MqSUON5mmmz7ziSCC2RuUA5dyOcZYnAsQczzbplEeFShJPkKdp4pxNnBV4N7Q+ETkGYiENjTIBExScnwxqnHiOS2cK3OG4zjmPYZdON3a7shTK1NpUh5KEhJAGsbJ1kjKSZ0mnrYx7gSzvW8Kt2rvCFK722buy4CyVJzLRAACoM6q6TvNZpYXjmG3rd0yoBxogggwR6Hl61L49xtimP2qLd9aGmgnKoIHidEgwonlImBAqbq1/Jrtd7WwQfGXF/FWOoARdKFpm7xduwhKEEjYlIEqjzmr19mril/DuK7zDcTdQi3xptCWQk+H2lHug/wApKSoT1AHSoLg/g93i26caTchlDZSk/wAyyo7D03qT427LLzhNkYzgnEDqsQsD7UEEpGUNnNPhGh0EZtCdN4nnrUepBpnVp68ac0lyj0+80pCjA0J3oEtrEAiQTvSWDYinGcIssQbfauE3LCHO9a91aikEwOWs6HUU5S462cq0hQg18y4bXZn10Km6KaGOJ4Xa4xZXFje2ttdsvIJ7l9OZBMaT015jWvOvCOD8NY9jF1wxxfY3PCmOA9009b3ANulwboUhySlRER4iFToRIr00mFBPhAjSs97UOz3CeOlN2lvc2FrxKllTrIcUM1ywnQpWkalIJ0VrlPlIrr0dXbeD8/7HDraG/wC6V2jz7xjwdf8ABvEVxhWIqcZuWkyi4t1lKX2SfCodQY2OxBFVlOAoTcKfRf3Ta1mVrEGf61oPGPEuKMcPp4U4twa6dxfCHkCxvC797btqIztuTPeNlMFJE7DpNVEiNAQD+Ve3Btx+x4NT6v6jS9scYtQF4e6nEWRCiCj7wjnoP9/Wgtry8cRL2HuNK6Zh+pqQZfct1940ohQEBQ0NEKjqY189KrBlf2FzqAlSI02OpFdp1+ulG1560Q77jX5CgABOo+QoqpCjzowPiMj0ou5kK1oADf3jvofSiuKQ03mUdB0E0plgEkwKIsgalII6HrQB6Z+yxakcC4lflRi7xJaQk7jIlKZ+Mn5VsylGQAQQOZFYv9lpQXwBiTeXRGKOb8yUIJ/P41s++yYG8TXBU72d0O1BvgK6jd76V1QUNCsJ3+UVTu2BIX2WcU5Yk2JnX/MmrhJjQk/CqD28YmcN7KcbUG8/tAYtTyyhx5Azf6VrHuQpcM8kuQDOnrQJTO4P7/YoYBJ02864RJ1NegecgZBTA35edMuEjf8AEN6vD0BkvoSVS66luROslRA0pa7P3JKXu4VplXGx86YWTlxY8TNXSHFW10hAcadZUR4xuflOh+tLyXFJpm0cMdk2KOW6Ltx62bW5IGUlaSnrMgRIEGTVV437NMdWsv4s8O4ZzQ4jVIT/ADFOmokflNN1cd4+uCbxsDkAymBPkdI8gKVw7HbnHMTt7bHMYdbsG/vCgLSyhxSRokkCBPUgxWl01tOZRkpb7lkwPsRsV4YF4ZiN46h1HeNuqymSQI0lJAMbQSNp0NMsd4P46ZxK2evm14mmzt/ZrUJyJQ01OoATl1JGpMk6a11vxU/gF4m0wrEra9bbUHEd9CkqkapzIgj1B9RUk/2y4jZDKvALhBiFEXCVJMbH3NR8aajG1yHOpd55KBj9pfN8R2jl/hBt0It1FCQ4VBwq0hJExEbcudazw/xVgfCXD7bTD6EutMwohv3lHXSdRqTqd+e1UXEe1rHMbbWx7Fb2zGyS62C56DfSnXCXC9jxs0+5eYwbe9TKQ2spSlGoCTGpI3GsDWOVEXZ4CpFtK/CI3jfjt/jPDzhrBNgCCm7V3veF+SCnw5U5BoNhrVUw2wcsGS2u6W/t72oT6fTTyq58Y9ml1gDSrwD2phEFNwhQlsAwVAg+ISdRAInYiTVEetsXTLbd5bKTJ8akeID4CKiV75OmntasngsmD4Dc8Q3C7e2WwkpRmJdXAIJA0+JHpVhHYhcrBy4zYsEkAdzdlIVPQCqXhnfYeEup7y4WglTjjiZE/wD4j0irtwzfp4huTYqebtH1JJRnJhZ6JjnGuvSnGKfJjVqTj2i7XYDfocWFcUhKAowErKlE9IOk/Gq7xH2T2eD3iG7vGGLp1aCpSXVlLjQ5BQzGJ5eh2q7472XXow1y/bx526eXLgR3hLcBJJSAPSJ2A3rO0cPYkvUWZgnWVCfjTlTs7WIjXly5Ededn1opAKcUYabbEwEidT/NMncfOq3f8LXFupXsjibpA5jQ1e18OXLbZWp9gFInKFSf0qL+IVHMc6icV6OilWk/Nyj291eYa8UNqWys6FKtB8jUvY8UKzhu9QmCf8RHL4VPPMMXAyvNNujeFJmmF7wzh62E+zpW06pJJlRISZ6dIios1wb74vDRJNOpeSFoUFJUJBGxFGLXfIKVJSr/ACkedNuz1vC7C+xNjHn7VvI2Awi4cytFxWytwenpMnalr515bU2drbtuCAczilJiri7mco2dgrFqwwSW2G0k8wkCpzh7ia/4cuQ7aurLSpzsE+FXmOhmDVa/iDiFRcWjyDvKCFj+v0pO6x1u2UUhp90D3ihBASPjFNtp3JlT3KzRu/D/AGiO8Q4g3a2zLIcU2cylrKCnl85IG5HOjdpisSx/CTguHNt5LgZXniZASDqcsgkGBBJ+dY9gWOv2Dov8Juihwpy50jQiQYII2kD5VesN7X7y3ZyYhaW5XJUu5SCkR1UJP0itFVurSON0XB7olOw7sJxVVxmu1qXbgxKE5ZPmomBU7c9ib/Cds3xLYYqybmwUHTZuNKMkagHUeXzFOn+3pnBb9MuLxJBBzJtiAE7xCjvry2g1Y7bG8W7V7Bm7Qw9heCh0OOK7wF+5jTKCBCEzz1Pn0W2nxEt1a6W+eEZFxlj/ABVxJdF9y6bDCTmTasDIlJgAkg7nTc/CKhcL40xXBXS0+VaEZgR+mx+nrW2Y52ZXuJFx2zS2rLBbWkk5hG0xG/5VnHFPZ/jdnaqViuF3NuhBhNzkzJSfUHb1rOUZJ3RrTrU5q0kTeDdr9ohBQu9ctiRORwFbRPoRp8vjV+wfjvCuKcLNtftWt9ZKzNEkEtrUNdQRKd9xPLSK823PD98yuG2+/SRIUj+lSeBKx/hx72m0aSttUd6wpQhY8/PzGtVCs72msCnooWvTdma5xV2Jm9fVi3CN77MsNyu1elaSNxlUJJEHcSNOVZg72c4vaXjzWJWTucqJzW6gUjnMcx6SKuvDvbijAXmmL3DbwNK3AiUSRMHSRv01APUVoTnaJwfj9kV3DjbQKQUKcKwocwMuQEnl86bjTk8Mjfqaa4PPF3wXc240cUFESA4iAR602XgbGRCS66w9ACwpOZE9ZHKtltMfwxzFGvabVV1h7hJbdWPAnUxnTE7iCRIBPOr3ifA3DnEWGL9ktGrZQSNCAmOfvctDv5jcaVPRXg0hrJW+6PLSsGxGxPfW6kuAAnM0vWPT/erRwnjyzkuSVZmiEPeGZGmvTz+FOuJMAc4UxhdlcuezXKoW04RCHk8jGxjYxrp0IrsM4hvsJz2qG2B7TIUpIJDZj3xtEjTWRqKiP1lg3qPfGzLRxNd95YthtSFJcCAT5HYfIflVfs1psMSR35SEo96E5tx/tSNm0084Gn7gW7QBgmdPIfvlT/EMHZtLYXDN4lzT3D+I+UVtKTl9jihFUls9nXlvgt06X03TiUvHMtEqKgrynl8KiRbIYW6lu4ceaKsyFLSAQOmgHnRjrOk10DrEee1Zt3OiEXFWbuTltatv4Ibdp9ll94FCVrEqJmdiRBGkTpTVD2JWba0PYrZXCkDLokZvzJNRvhOp1866B0+Yqt5CpZzwTjPFt2hISttCogaE/rMfCom6fVd3Lj6gApw5lRtSU6SU/WukTtI86JSb5KjTjF3SOnzoDroP964qFdMe6n4VBY8wvF7/AAW4U9YPqaLie7cTulxO8KHOCARzBEgiicWcWv8AEGF9xiuIvMupVmbShZS3I/EQDKlQANZ8iKg8QxO1ZWGHrpbKzqSlE6fI0yWyxd5XkWj9+VDV1SwgAdBy67AUOXgqNPKkyX4G4u4m4WcW5gfFTth7Q4UuWifEXFRIWW1goIMe9vO/WvU3ZJ2ko7QMH/h+Iusp4hskzcBCcouW5gPJHLcApGx8iK8oWWC43g9ui5u8Lu7TCblxBYubm3WhDmcSlLa9iSAdNdquXZ1j44W4/wACxdy57i3Tcez3TpEgMujKqZ2ElJnlE1x19PGpB4ydtHUSpVEvBuOB9pmIjiy64c4lwNGHOpu1sMXLT+ZChu1nBEjMmIUCQTyFMO2fsyxjihVjxfwjePs8S4QjK02yuO+bCiYSqdFpJVp+KYq49oXCTXF+B99ZIt3b9tActX5BDiNy3mGhSobcpAOled8Cv8c7LsWOIYYpx+0YuVPXGD3Ki2nNBQrKY8ChmUOYmJnSuajSU11KWGuUdVbUyg+nWynw/wDno0vhvFcL7duHnsH4ptW7HifDWswftyPCFad8gTtIhbZ0B6SIxTGsLdwPGb/Cnnra5esnywty3cztqI1kEeREjkdOVWTtZ4n4B4qtrDiHBXV2OLXzq2sTw9aVNrScs94oDwzIgqSfFmBIqk2otG2ALUoLcTIVNddCLSb8evRx6md7J8+/YjeYpbWK0JuStObYgTTpKwtCVoMpIkEGZFFubS2v7ct3DWfaBO3nNHt7ZthhDaDCWxlSFc66UjkbSWBD2+3C+7LgQsclAgH0n4Us4tCE5lqyp6kxUwriFtxgtrwiw7yI7xOcR6pKik1FFDSyA63nbUfEmNxzptLwQp3V2hPO2fdVtrvRHnQ22pROYbBKRJJ6DrzoMY4QwRy29pw+8DDqvdYBUuNfxSNDv+I0W1tnbNtDYDRAAEpMSPlUstbXww7KHFJC3UZCdcm8Ck3E5jJUoeU05SlY98zI19flRFBvXvE5kEagmNfUUCPSH2WMqOB8WKBKTiZ16/dI+dbSM6iAEmsb+y4wEdn+IqSgjPizpAM6QhA325Vsog68+prgqdzO+Hag2ZzoPnXUEr6fWurO5Q256H5Vn3b4la+yfHQEoVBtj4hJEXDevrWhEJPIj9KoPbwtLfZDxKteiUstGef+O3W0e5CllM8kTrM+VcTqYpC4C37Ym1dCVGFIUDoefypna4q+taWrixfQ5OUqSglPrXoN5PPjF2JNQCkkESk7iNxULijbmHvMXzalOIaOUoVyB/3/ACqaSBPlRXWkPIU0tOZCt6TQRdncPZf39AXbqSpKhIVsPOpU4GAyCu7QhwicpSYj1+VUl5vEeHStVm6tVqsyR0PnG3qKcWfFiZT34cbXsVoJI9YpqceGOVKTd4cEnb45b4ZiwDzOcsLCglzRLvUA/v0rZcERwvxThAu22VNALhx5tOQ25UknKtIGpkchBmZgRWSM8RWrgTL1uvY5swB+I607Vd27qkvZihY/G14VjoZFUsGNSN8WLvd9mLt6pblrdWLqlE5VoeA7zpCRIg/CqlfYViXC9zKy4y6lSgFAxmAMEg8xPp8K6zxrEMOc7yyx24a8l/eD/wBqpFJ41i9zjjouMQvWXnEphIYYCE6+QgdOXKqdnkzhFrljlfGmOPYcvD3r0O26kwA4hK1o80rIzA789iahc0mT9KFlpTy0toAkmBUqvhm6CQW3UKVBzJjaOX76VCTZrKcYckjwK9hxv1sYrcNt2uXMlDpgLUSAdfIagHQ/SrLxLhXATmHOX9niAtrgeFhNssfeOAmFQmRvqScp9KzZ1p1hwtutqQuNlDeiGJmBMbgcqrdizIdNN3TLXc3vEt7botv40XWkpTKUKCCqBAzGJV8d+dRN8MYtWgbp9zKTGhGvrUahbiSEoWsTySSNaBa3HDDji1lJjxKJj51LlgcYNO7DF5yCC4szrqox8aJrXbakxQedSapWDbgdaKvCl4uw9bd2pxITnVlIBSBz1oQdiCKA+IQRPPUUDRS8Vwm4wt2HBmbUfC5G/kfOgs8YvLJGRp2UbhKtQPSr5ZrtkPj2pnvGTIUIBI8xPMHWoLHOGLV+5U/hT2VCzJbcRlA9PrpUuLWUaxqpvbJBLTii2eTFynuFD1INSFti1jeLCG3kKUdknQn51WF8O4igwGQv/lUP1o1vw7fLeQHmShufErMNBSUpeRuMOUy2htAEJ8IM6JMU0ucHtrsKDy7glXV0kA+m1I21himHXKfZnE3jE6sOq1I6TThF+sKULuzfsykkStJKP/dtpp86vD5M0mnhleuOGb5t3KylLqCdFSBA8xW7dm3aBw5w3wla4ZiOLMsXLAKXGe8gII8iJ130nesyQ+2pHeJWFJP4hqKaXuBN40wX2GlrWEk962JTtzoi9mYiqWqLbPg19/tmZucTJskqXZBKkJdKyAudlQPdHkRPPSnVxxx/H8EctHSHnVkEqbPhgnSZMjmPPTpXmcG5sHiUlxlxJgxp/vVjwPi9xh4B9QbUdM490/8AMK0hXzkwq6HF4M3vA+AcFxhlu4v0Mu957iG/By1EjnSXEHBHCTDD1jYWN0LpOVWdBKimeZJ/D5Tr051SsG48atXUPIeDZIBlEKBHmBuN6sll2yYaHU2lxbNuvZSCpQkgnnG8eVbboM4enVWMlexDgCyW3ldLyUqktukxJGgIMb1G2vCOJJtWw6+w47BBKRAOv57VqA7RMBvEf3m2bdHJBCYPpB/pUJivEfDt4pK7MKZdBMStITr5T+dGym2LrVoY5/0KDh+MXeEPKZUmUJVCmnE7HnB/YMbVa8J43LJy210LRWYQl1Jj00IBE8uU03xKyw3iFqWnm23x+NBAIqm3uF4thCHVOW5uWE/jbHi+R0I9Khpw/wAG8NtR5wy1cbYlfY53Dt7aWTiWCT7S2J7ydgQdo2qrQjOVJbbQTpCEwKhn+KmrdHdoauCrSW1nKB8KIOLLXT7h0een9awckd0KU0icCtYOtBlAPuR5io5niHD30iXQ2o6FK0kH57UqcZsEuIbNy2SsSFBUgeRPKi49r9D3WNK4QJH0ooWFKyhQkUcKIKgPyn9/60COESdQPKgEbzQEToSD586AkDXQACgQY6axQRJ86Revbe2/xn20GJGZQE/Co53iexaWQnvXfNKRH1obsUot8EudNta7bn8ahDxZaRow9PoP60RfEb7pJs7Bxxv+ZSSfypbkPpyJtbbbkBbaFRtmTIFG0AgRHSoyxxk3RQyuxuUukmTslI+P71qUYwPH7wqXaO4c42D7pWSrymBvVRV+CJfXnAm4gPJaS6pxxtlWdtpTii2lXUJmJ1OsUZSUupUlYlKgQoHnNHvGncNCjeNqZy6TBInoDTFGMWCom5b6jMY/Oh4GrvzcufC/ahxnwbw7/Z3BLvDxZIcUtl26t1Ov24OpQmTlInUSNKr99ieI4neXN/jGIv3t3cuF1x10JTKiADoIA25Coe4v7V+Q1iIa0g5VJ1+f6UzwvD7i9bKsRcuC2k+BtRjN5n6VmoRi24rLNXKUo/Z4RJ3C7XE0+z98hSkHMkoUCtsjmKiE8JCf++Sn/wDT/wBakLy0wu0ZLr9u0hKdsqRJPlUGcbubi9ZUkKSy2sENtiTA/PSh28hG/wDFkxa8Ot2wBTdvhY3KVZQT1AqxWeINW9om0fw8OqRI76ArMOWnhM/H4VGMXL1wpKk2qm2layrT6TPWnGw1q1gyqfZWkNrkXjt66u0DFvak+BC0qUr135/SjD2tA8Rbd1HupjTnz1py2lTyw222pxZMQBqaUftX7UjvmijNMTRYW5cCCFZtiD8KPOkAz6UXLJrgIH+tIo4jzpNekkjQeVHJ5QKDYQN6LCPQf2UsUVccM45hbiir2S+D4UdCQ4nQfNKjNbmkQdJjrFYF9lMsi14mTlKX1PMrIiREEAz5mdPXzrfx0NcFXE2d1N/RHSrpXV0jqa6syxsSAd1GfSKzP7SN0u27GOICjIorNs0qdYCnkT+VaaToCTPwrM/tF2yrvsdx5pCTmKrYjTn7Q3HwrSPKB8Hjnhd/DkN3Dd9iL1o5EskozNAwdxvv0I+O1SKMWtXFKb9oazJVlBCpCvQmJFSGB4fgzduiyv7RhSjp7QsGFEkTmO4HQ8udN+KOz5FkybrDFOyCJt1QrMNpSqdetejsko3R5zrU3PbLAYGRIIM7aa0blufhVawjF1MuqbvH1hA2zAkg9DVgbfZe8TTyFDqDSTvkcouLsw7jSXmy2v3VDXzqvO8Lv96e6faLfIqmfyqxTNCVQCSaGkwjJx4K9h92nDnBY4gygBJ8DhTPP8t6sDSm1ICm8hSRKcu0eVM3V4dioLDim1rSSAJhQPl1qP8A4PiFmo+wXRKNwlRj89KV2imlL9MngRO5o0adabWSbkMD2txKneeUUsXEtCVLSB5mIqkr5M8cC7DzlstDraglSFBY0nUaitmwC9wrjrCS6optrpmBcJWo/dKJMKCySQhWsEyAdCDoawtWLWTfv3LccoIUT8BNSOB8QPYfcpvMNukFWXIoRmS4g7oWk+8k8waqMmjOrSUllF04s4Xft3lWzoII/wAJz+beAdOnT1FUO9L9ih1PcKceb/8ADmJ+lbHwzxphnEVkbC7aLRQ2QWJlTaSoQlv+dsTt7yZ571EcR8DJcWq8tMt1bqVlBQIdQRPhI6+W+nOtGtyOeEpUnZ5RkNnxHa3BKHkm3WOSzp6T/tUkzctXLSVsuJWgggEUtjHALb7q1hZZXuFxAXrzB567imzGFpwVHspSUmSVKmcx61g4yi8nYqlOS+otPnQzQt90tf3ii2nqkTrUs1wvdXTS3LNaX0tJ7xak+IBJ2Mjb46zTSuJyS5IghQAJEA7Vw1O9C8ktqUl3RSNDrI+dE7xA8JWkGAdxoKBhp0HT0qQssHViNsly1fSt0aKaIgpP66VHZwNQofOnVhfv2FwHmnDB95IOihTi15IqKVrxEFIU2tSFpyqToQetFGg0FSmNsIey4myczT4GaNIV+/yqLBoaswhJSX7BzFBn3T5VaOGeMRhyV2GLM+12Lych0lSOpHqND1qrAZRBOnSZoSSOvnSTKlG5oLfDPAGONpfsblrDrhKsq2lvpazAnfz1O4EaVXeIuGUcMlz+DY6hlbuYOtNvBaHhzCkjXnr116VXyEndP0oQBJ29Jiq3J8oiNOSd7iLlv7SwWrru3MwhQSCAfnqKpuLWBsLpTaQruzqlRGnpNXnbUGk32GrhOR9pK07woTFQ43RvCbiyhMW9w74mGnV5T7yEkx8qe2OGYj7Wy6LZxJCwvM4CBvzq3sMMWzQbYRkQDOVI0mlFCQobSPnU7C5VX4RCYlwxxJZk3TpeDazKFSoJWJ5E6c9qYJx3ErBwN3bQXHJYgn4jStVwHjRu3sk4VjFqi9sNB49SkQRpzp272fcK8SMl2xxXwnxBp4jwA6RMSDvrVum3mLOeNe2KqMna4uW26hxNv3cH3kOHMPSpzDeMDcEBF44FKOrbxmac8Udh3EWDIN3hyG8StN/ulgrT8J1rO37Z+1cU1cMuMuJMFC0lJB9DWblKPJuqdKorxNdwq44XxC5LnFFlnDQBbDLWbOeYVGoG1SOKPdmD+Fv29pw+4h5SSEO9zlUDyMgwPP8AKsWt7q9UsNs3DoKtI7yAfmalG7LHXk5xcnTl3wP5VXU/RDoNPErInl4ThaVq7u0QEa5c4kx50g7gmGOmSwlPkhUVFHCMccUVOXcE6kl8/pSD2FESb7FmQRyzlZ+VTf8ARol/+iVcawi2AZXcDKCDk70kA+k0RWMYPZklltKnAYltvU/E1A22GOX92pizPepGuciBHWrJY8DKaZN1fLBQBIQTln9T9KFKT4CeyPcxg9xYYi2tgFHm4Z+goU2uNYolLjj3szZMgapMeg1+dTdvh1lbQ6w0024DEBPijrS5kmQRNVtfknel2ohGeFmJz3L7jzhMqjQH151Iow2xZSCi0akdUAmnRMHU/rVm4Y4eZunmXsSW2w0pUy8cqUpAJk9CYgTVRhfgxq1tqyyOfwjDrDBm3nrO2N25+MpByT5eQk/A1Zbzhp7C+DDijbTAYjIkrahayRvBHqaumK8FYLd4eot2blzc/gRqEhWoGx+uwGuvOq9peLX+G2Nnwyu6YuWUtAr+5yubCD7xCc0nbXTlNa4Xg5YuUrJszVxt9xWVt0idAlKQr86In+I2mZdneBLsRBTExy0qwYJjFvhaVtu2uZS9S4mJHQUGPYnZ4iEFhkB0alwJIkdKjarXTN97c9rWBhZcZloez49gqiARNywkrEbSRy5mR8qTv+LODnVlarN66PUsAq+aiP2aIZ2VB8jTd7D7S4VmdtmlGI1GtTukadOF72a/wV+74iZTdLXhmHW9qyT4QpMqHxFR5xi/LneG7dzeRgfLarUMAwxRkWqJH+dX9aFOCYaF5haomZgkx8prPazoU4rwV21tsQx1aS864ppJ1Wofl1NWTD8LtcOSe5SVLO61ak/0p0hIQkIQkBAHugaAU+wnD2cQu1MvOljKnNEQVAbxPMaH0BqowMala2fAyKue3pSttaO3jvdNgExmKiYCRzJNWV/AMPtkA91cKUDqU5jA6xG9Rl1iV0ww5aYFgrqnl6By6SlAB/mCJMnaMxPoK1lC3cc8aymvoKN3COHrfKhLbt06JkpJCZ2V6dBz3Om8XcXlxeKSbm4W6UggZj7vWKattYqHnDi3d+0OHMUoJKvU670p6bVDZpGnbLydJPw2rgNya4nkKAmNDFIs7maKokGjb84opSJE7UMZu/2Wm3lv8RLKlBlCWNBoColXzMD616CQJI8Qg6bVh32WkK/gvEbkAIN2wBB10QqfzrcYBgFWnrXnVu9ndS7EGyq6/WuoZT1rqyLGc5TqNtpIkfKqN25GeybiQHxZWWTE/wDrt1dyNNCPPrVB7dCW+ybHyFqOZLCYIB3fbE1tHlCn2s8kyuFREjUJ2kT1qVwnHFWaQxckrtyfAvUlnSIjbLtPoI6VEpUQokE5qFJQSA4mUk6lIggeXKvVi7O6PJlBThZkrxdwQxiPe3dmypl5ABWEEKknXUDyOhms5fwu8tV/4SzGyka/7Vs7Dlp/Cgq2fcZYT4k928oREDUg6KiJBql3CIfXk1GY88xHr1orU03dE6TUTScZeCmNYtfMmU3Cz/zGZ+ddeYm/elCnCElP8sifrU3dXWEouVtXLKM495Rb5/CuOD4W+kqaByx7yFyB+dc+1+GehvjzYrQUQrMCc0zM6zT5jHL1g/4gcT0WP6a04ucEYQkuNXqcsxCxrTb+HtpU2C4tzPyQmI9ZqVCSG5wfIsviO+WkpHdpJ0kJ1HzNHssKusRWV3qn0NpEArmSegmnrFvaWDyAlpteUSpxRlQ845fCny8SZQkkEkgjyieZ8qtQbyzN1EsRQa0tLK2WUW7TQdSJJmVfOnXdNKWF923nH4o1pJlYeShcgyIJA3padiTVmV35DQDyEjX41acH7RscwpCkLd9slISh5xRDzYA0AWNxtoQdOlVYLBiAaNm3FFxNJ8mqYV2lYViiD/GWLdL5hJTdNShW4KgtIgH/AJkjfepZrBuFuJMOV7PaJdKgmfZXA6UnLJKgkg7a+7yrE1KCQSsgJTuToEimf8YsUr0um8x0zAj86tT9mToJu6NNxvswDNykYcl15KhKUapVO+gMTOsCAdNtqrSuGX21q9meWlaVEe9qkg6gxBnf5Uzw7inGsObUnD8Yv7dCgUkNXCoIIgwJgacxR7nifE766Ny++2p0xmUGUAGBExG+lCcXyQ6c12snsEt/4E1LvD+F4m+k50uXTihHlA/rR8Z7R8fuJaNnhliFe73bBWoAaQFLUraOlVk45iRbLYuilJOYhCQkz1kCabPXr74T7Q84+EkkBxZVrRLb4HBT/kSWH48bfEfbcQYt8RSNVW7raUhZ5apAiDrpTq9QvHnEqssDbtCokuOqMkk89gE/Kaj7BeGF9LlwFNpQkHKSSCqdxUhi+PJebSm0uAFDQZUGI5U4pJXbFUlJvbBBsZt2LLC02wWFEAJAnmD/AL1XpMb/AFijvXL1yvM84pwxAk7fD4CiFQ6TUzld4NKUHFZ5B1HPSumP9aAkHcCfrXZuYTPxqDQ4kztP5UM70BUYnL8q4HScsDz0oANAjXTymuKtP9aAdYrpoAGSehqPxQ4nGWwQ2UkQST4h6TpFP66T03qmroE7O40wtd6q3IvW8jiTA/zDrT1Di21ZkLKVDYgkUQzrETymuSSJzJ+RpLAOzZJWfEmMWDqXGMTuAQIgqJB8ooL/AIivcVKV4im2ulJBCVLZAPxiJqOBSdOdM71q8uYTh6nRcfhShMgidZ0+tO7J2xuOHmLd/wATjDSufuCKUYssGUAl7DghUyXWVwselO8H4R4yvWUrf4dvAD7qoAzn0NJX1jeYY+li/tHrN5QJDbyYOh1/T5jrSKfNkxtd4Hg145Jvb9AgDJmlPqZn4xXN8PcN2yNW7i4UBuqd/wAt6PIPn60PlyFGPQXfFwyLly3CmrBluxbzaKQJcI9ToKZuM3jqSh2/UUEzmKRmHpy+lOZk6An01pe1w+9xFRRZWV7cqjZlha4+QoEmlkb2LFrYrJWy5cBZBWVOHMfjT21dwwuD2i3fCSdSlwkD4UW8wjEcN1vcOvLZJ5uskD503CxEaelHAO0vJZeHrnhKzxDPidvdXLHIlOcA9SmRpvJGu0CrxeXnBt3hzt7aXzdtAUQ0m4AKY/yqIUZ6R5VkYkmAkk8oFHtmXLy5at2GlOvOqCEITuVHSBVqbXBk6MeWyfuO0LH37UWrd2LdpOgW0nK5GwBVM7adY0nSoVm9yLedebTdOPCCt0kq15z+9qvFp2WjDLMXnElyWFFOcWzBzK10CZ0kzvqAAKice4cw5u0SrB2LxToP3hdUMoTP/MZ/086dpPNgU6axcq5t3UsB8srDWsLI8NL4bh1xiboQyjwzCnBsPL8qkGuIrjDGvYrmwYcyiClZifONQdKSd4nulNd0xbWtsJ0KUlRj4mPpRaK5ZEqlRp2RIjhTD2FA3N+6JOXZKZV0E7mnDPDuFd3lRncJjVRkx5fI01bxrDcXtQziYQhxI/FpBA5GkbdvhphzMpwv6aJVmgfIa1r9fCRzrqPlu4jieCYfbpddtL9BgEhBcQduQ1moYagEzPSacYg9b3d1/c7XukckpHiV8BTu24Wx68bW4xg98pKIzEtFP0MHlWEuTtpq0cskuHr3DLKxJuHmGXlZkrKm1qcMnkAIimGKY0i4dZVaM+JlfeB58eNZiIgSAny1NRam1tqKFoKFjdKhBFc204+8lptCluK2SBJNPqO1iehFNybLdZcV2Smm0Lubm3U2AkJeazJ06KQZ+aaSveLmUMBuz9pWs+9kWW0R03JPyFVRaVIJSoQoGDPKg5SabrSZEdJTTuHecLjq3MqElas2VI0HpSaVpUVAEaGDFCRIrrVLabhsukloKkjqPhWZ08cC7Flc3Cc7bKlI6xv6UidFEEQpJIM71Nr4gtVtBZYWt1AhppPgQP8AMojUx051CuuLfdU64oqcWSpSjzNVJLwRByfKC6HnqKAwfhQKMnUGKBRk7VBZ6M+y2Anh3iE55/vrQKZOg7vf99K2xKgBr8qxD7LIcGBcRK/8NV4wBqPe7syI9I1/pW4pzCMoHmCK8+t3s76XYhbvE/8Alj5iupPKr+X6V1ZljRQWDqAB6Vnnb+4GeyXGlBITmctU685uG60LMQNM1Zx9oRwJ7JcYlKv8a01I2/vDdawV5IU+1nk/eQK4a1w0BB2HzoFpQ8nKoSOYmJr0zzY8BHbpm3kquENKPMqg/LnSV04BYqWpK7gRJW0RJPWRv50q3asNe4w2kbTlE/Ok3cPt3NQFMlQhXdKySPONKTb8FJREMKt7LHWB34Lr6RC8y/vJ2kGZP6VFYhh11w/cBxp4LaUYS4nY84Ip2eH1suJds7koWgyCrl8qfFxx1k2+IW6ikiCpHiQr9U61k1fnk0UrPDuhKxxK0xFoocCG3CPEk6SeooXbM2rKne8WpzYmMs8gPyqHvsPtEoW9aXTakp1yKWJjypo1cXWpbW6oI8RGpAHU0Kbjhj6almI9btXlqLjiykk6REn0qTsbF1t14qVLTviEa6z586b2XFCW1hVxb+IbrbA18oNXOxXhWPpQQ22gkkpLZUknnAjoJ3rWDUsIyquUMtEEhhTaFNhZCPwxqRQsFclLjZED3uv70qYxXB/YfvmHg6yrWPxJHnUYk5gBm03nrSaa5M4TU1dCgIO3x5107z8KAHTQ/Su8W8zUlnOoQ+2ppacyVCFA8xUNdcLsLM27ymvIjMKmupFdOsGKTSfJSk1wVj+HYthxULYlaDvk1B+Bp/Y4rfB9tm8ti2hfhCwkjXzqY0jY1wgnfbyoUbcDdRvlAkwdTURxDgVy5ZLxYJcLKYA10icuYDpIj1BqXbUlLgKxmA1jTWtL4Y4ywa+YXh+Iot8OQ1boWl916UrybtJBACQScwTBHvg76U43wZ9TY7o89219dWqpYeWn/LMg/Cpk8VLSoBVnAA1BXz+VajxH2Ltpu1YpwzfM5V+JTBb8KZE6AkRuIFUq94fxWzcKLm7sExqJSTmHI1HTlHk161OYzsMctL0hsEtOEgBK+fp1qQkRE69OdQyeGW3HFOXD6lKUZIaASKeN4Oywkd0/cojo4fyqlfyS9r4HxzGOk9K6RqennTT2S4SCGrxU8ipAP5U1fVjaJyC3UU6yEmVU2JK/kknXmmE948sNpBAkmNaKzeW1yCWnG3ANCQdaqd24+7eIOKpeQg8gIgeU1K21vgSXEPs3ABTqApyNfQ61G40cLInMwAJ2nrXJUXFJQ2M5VoAkSZ8qsfZzgdlxRiqg6vv2GdSEEFJ0JMnYaDn1q34rx3hfCt//AA7C8PacQgS46hCO8kpOyzP4oMR8a0UcXOac7OyM1uLC+tXu4fs7lp0xlSpsiZEiiuW1ww33jzKwgmCZG9XR/tfxlxASizswE6y6M5P5a0zuuPnsacbZv7SyaZK5LiUxlPmf5ar6+yLz5sVKeZ1+ldoP6VO4rw+EJ9os9QfGpEggTroRUDJBObQgweWtKcXHDLpzU1dBkgEifDJiTtVxwZw8OXDV3Z26VOAJKkZvEeuY7iY0qlkhVP8ADMXuMKuWrhIQ8htQUWHJyL8uo+FOEkuRVacpcGoudrrdkym2vcLuoWNTAyK21mdY5wKrvFPFmC8SFhd8guhqS2BqsEgAmRBGgAj/AFqRRj3BXF1kpnEWU4dcuGEkqylEbHMISQI8vSofE+DsFwp9KrfExiLTglKARmQI1UYMbxWzcn/g40kubpkYnh61xdj2vDy4yiPcWZzHaNdtqkeEezTEOI70IfdRb2zS4dWnxaCPCPMz8PlQWGIWdkyxY2zrRLiw0kKnMFHQE9RtpWzYBbsYdhbVuwnOju8uYaEkbqJ/e1JxiEatXPoh3OHeDuB2TcOWVuAlISbh8e4TO6td+m+mlVXFO2plodzg+HrW2g5Uqe+7TyghIg/M/CrVxK5wo+FN47c2bWpyB5ScySQJ0mdgNfrVQb7LsIxaHcKxNh9oE6NOZlJ6SQTPSYokmsR4Ki4rvuGwbtZuMTd9ivbC3VmlSVp8Cx6K1+RFVXEuHbnGeKe4wywDbV4uUZElQQIlS1R8zEDXQVZ7Hsiumbhm6Yv2SWlTCjOtXCztML4Pw166v7lHeLlLlwFBCEL3ypVO/pJ1oUdyyCqOM/6fBiOPYHccO4kqwu1NqdCAvwHryPnIPypzgHEDuD43YYgoAi2OUwNcp0P5mjca43b47xC/e2s9zAbSs6Z4J1A5DX10nyqN/ht8bc3BtnQ0BJKhFYLnB2Ss1k1a7xf+2N/boS6pq2dVKWxBCiRoehPT5bmkMY7O8fsnS/hGJpuEEAht8SVGeSgJAO8HbrWaYdd3lp3qrVxJyDMW1ag6zIHX0q34N2wYtZrR7dbtX7aR7zbncrPmYBST8K1VRPLOXoSjhWaBZsMQxNCmsVwJSVJOpQAtKjrOqSSDpzNK2fZy3iaiWrdxoEwFEkAGdhUqO26yW8HVYReNzqQVNOz9E/rTHiHtiGIYW5aYfh6mXXJAceyhLcggkJBMmDpJgTMGnvj5yQqVRu8cFKx2ys8NftxaHMFAqIUoqBEiD6HX5VHEKvLspZZGd1WjaJIHkKlcH4Yxzix9bliw4/Jhx90kIBPKefwHLlWhcOdnDOBNO3WMPtJCEFTrgJytpG6pMQAPnPPaotuf6NZVOmrXyRWF8CN4JgFxxFiDqyu2Z79CWlwpAEkEAGCToIVIiTG1Dado7dpgDzrlwz/EnlrVb2tu0E90dklSssaankTA051A8RcaP37N7hVioIwhxyG0raBcyBRUBnPiA206fKoa3xl20w52xt2LZsPwXXsmZxcGQASYSPQVEnnBtTjJq8xkta3XFOOOLecVqpxaiVKPUk0LD7ts8l5hwocTMKG4omg2rqk1aBccU64pxfvrOZUaa0XSZJoZ5RQc9qAB0pJQV3oBRmB1zE6DypUaigmTtQAUba9d6EyBpQx1rtt6ACkEgH50EwaMRNFiNYmgD0d9ljXhniHWYxBsf/tD+tbWZ2ketYn9lhwjhziJPS+a5dW623X3gon9K8+t3s76XYgMif5q6hzo6n511ZXLGsx1+WlZ12+KV/wsxVsJB7560bnpNwjb5fWtDMmqF25tLd7MsTBMhL1qoCDyuEfvpW0O5E1MRZ5ut+zvGry2duGO5WlsEgEjMojkNdY+FMLjhDGbYS9bBPQTBmtHwDixvC7VGHKnMu40U64lCTI0BJ21G8fi3G9XNk22KWyjdsdw0tOfVtIlIO4GoOvPnFe06UeLnzsa8zzq9hV+wApy3cyH8SNQfSNabD/eK2S/wMXOJZcMQj2dUlSgZaSRuARPxAGnSk7vs1ZxJJU8LcOK1QWklJI6zM7+VN0MYZUNY07SRkAI2+dDy1P0qc4k4RuuHV5lz3f/AKmix/WoOD5fGueStg7ac1JXQm4wy8JcZaWP8yBtTN7CbJJ8NqqVHL4FKA/On/nQmd6lpPk0u1wyBvOHQltblspZUNQ2dT6TUSzdXNks9y64yoHUJJGtXOPX503Vhtou59oLKS4dTMxPWKzcPRpGq+JZG9rxviNig2t7bNuAiCVJKV0pb4zYvJCi+EEn3V6Glb2wZv0ZXgFKjRQ0UmoxXC6Svw3JCfNMn86d5cEqNN5tYlVYlZJEm7Z+CxTV3iC0StKGwt9RMQ2P9pojXDdkkgqU84ehIAPyFSDFnb2sdwy235xqfjTW5h9F+xYKkJMFJImOlDuZmgjXU713meVBIIAEa/OkX7NL5SvvFtLT7q0GDHQ8iPWlp6H0rhJ8v1ppgQuIXV7hlw2pb6nrdWipAn4aVMW7qHmkutqzIUJBpdjDWsWDtm8UAuNkNqVrlVy161VWLbF8FvfZ1tKQM+UhYJbPxHWOVS7p3KupL9ou1jxFiuGICLPELhtI0CM0hPoDtsKLiGNYjjKkrvrpTxR7sgAJ9AABSVviNhed1bOWK2luiEXDKpb05E/TUUitpTS1JV7ySRvVsyjzwduRrXQNSZ1oDp0oCREb9aRRxjzj1roHLT1pe3uGU+B1hDieUjWhVatOFS27lpKeSVzIFOxO63I0dZbuGyh1CFp6KGlMLfhKwu7oIL7jCVEkmRCR8qlrhtpohDbmePeVsJ8hSY1HOalpeS4ya4LHhvEi+F8G/guGJStIb7tT0AT4iqSI1MnmeQ5Cq4VKcUpalFSlEkkmST1NcVGYJ1612Uak7zTv4JUc3DSP3zoAFKVCQVK5JSJM+VcQQBrz+lGtnlW1w28iCpCpAOk/vWhA8LBc8EtrhrC2UXKVB3NlCZ1j8I/L6VM4V2Qfxa6dvMQunWWnDn9nbEL16qOg9BrrVl7PrSyv8HbxhSkuvKRn8ZACVAkZZ9Qeh0pDiPEeI1kJwu7tUBS4hpouOSUzBSRA2iBpFdjSaR5acoybeLhH+yvAe4dZYfYS8gQCtWYHoToB+VZvifA7+HXrjbdwFuAAjcpUCJ0+FdiVxxdh7me9ucXZzmSsLWgKPwinnC9vi71w468HnSoAoDkrWY3MchED5VjFJu1jeV6cd0ZXEmOzbHrqzF0w3avoIn7twqHTcCNI1pS07MOIHWXFuWfdEe6AtOvmdauGG43f4CPZjaltkKk94hQ97l0A3MdaeX3aF7MlAAFqgCSXlwPhAHl1q+klkl6lyVrZK3hHZM8i4bexV8M27RC1pVBzjeAB/XrQdqXbA3gDJwLAVld4BDji4UlgayPNXTTTfpUxcdoFziDJYsLizU6sGCpWcCdzl0NZlifZlc4jdu3jj6FOXCy4VpcjMTqYBH70rOpGVrQRrQqQveqykq4qv1OqccDTilGVFUkq9TOtTeD8Qi4WPZ3XLW5TqAhZST6EU9e7LnUMuJQtJcAlMLlX5RVXPD+J4ZiTKHWlNELBC9hH7/OudqceTuUqNRWiy9NcT49bklGN4ilJkQq5URr6mgtsLxniG6ACbm5cVqHblw5QCd5VsNdT50fA8NF26q4cShSG9kkxK9Inyq/YJa31rYXmJW9wEgNqShKmyQMsmUmYBACtY0jWN62ULq5wzq7ZbYrJ2G8EYDwlYt4rxFdNuvNhAWCMyGVLMiGxqowFQVCCd42ql4/xIvEri5RYoVb2jilZAo+MInQaaDSJ/OovEsQfxW9cvH1qWpxRVKiSdaQ23FLfZWRrGlfMuRewvXcOvGrplDalI5OJlJBEEfInWnWPYsjGsTcvGrNFm0oAIZCyvL6qOpO/5VHHlrMV3OpNreSWwHB2r5Srm5UkW7fvIzQVfvX5VNPvYNgxCRbsJd0ICkFSo6mB+dVa3v7q1aLTLxQhWsACR6GNKRzEqUSZnUnmT1rSM1FYWTmlQcpZeC7M9pbmF2imcOtWlqUSQp1GVKJ6CfEfURUDjvF+M8RDJf3WZkkHum0hKdNtBvFQxgmTFdp61Lm2aQoxjkMNt6KdJ86HaBGlBzqDUE6CD9DQaHSK6eX+9C22t1xLbac61GAKYAbelFKhGpipa04eedcSLp5Fs2d5In6xHP5UuLjh+0WptLK7gDTOkE5vQmKrb7MnWV7RVyDBmDXSPhU05f4KsQ3hzyATBOVJ/wDypfEeGmg2l2yJCliQ0TMaSf8Afyp7PKEqyvaSsV7au3MRQAiNOdd5fWszY6gOsaaUNAdtNqAPQ32X+8HDvEKkmE+3M6//AEzP6VtoXnEJj41if2XlAcOcRJJ2vmj82v8AQ1tCUeLTQivOrd7O+l2Icd16/OuouZ3/AC11Z2LG4PU/KqJ25SOyniBSRqlLBHr37dX1S1HTMY9az7t4fSx2TY7n17z2dpMfzF9uK2h3IU+1nnfhrtC/hDSrS/wpi9tVKzLUkfe7RuTBHkfnUte9q1pcMN29thlzapTlT3zikOEISIAAERppvtPWs4kaka+lDMkCBXq72eOqMWjRme0J+7uAy1fIaChkQAzkAA2GsgH4xUg1iFyh/wBsU+ta9MxUT5aEdKpnBvDa8Zuw+p+2YZaJguJUuVDnAER5k7xWlL4MvfZ0rYeaeUkTtofQz+ldNGpuWTz9TR2P6ivH+E3/ABBw2h2xZFy+3CihwAnJySBO+grEXm1tH75txpU7OJKdZ8/j8q2ROOYlw62li4ZcUEjK3M5fMSBB+NLXPGOGXgWnEsKQ4FwhStCmD1SYmKipSu7o1o6jYrMxLvEpPvJn1FFWFKjI4U6ztMit+ssA4ZxWzS5Z2NmEe6e6zDKY25ajoay7j/h234dvCm3bLSFKAA5n4bTttWTptK51QrqTsVWTEgKoCoJAzGPMmKvPA3ANtxKnvXHy4lASVhJgImfDpz0Mz0+NX9fBPCmBWynH7Bls5RmdUZVqSNBr+WlJUm8inqFF2MJ06fGa4bEfrW2O8P8AZ9cIBWxYKOkrLhSsesAVC3/Zpw5ibkcP4sCpI8TTbqXSk+YJ286UqTQ4amLMunl+tDMRpVixrgHHMFBdcaS9bzHfNkkAbyroPWq66lTKsryS2YBhekg7EVFmb7kdIB0ETQyDpRAoKGhketK27Lty4GmGytZ5RyosDkllhehFDPzpS6srqxMXDC0ecSPnSMg6g0rApJ8ApMEKG8zI01qQYxu9t0wVpeSNg6nNHnO/1qPzEbaUZKHXJUhtxYAkwgmBTTFJJ8khdYubpsoNnbJnWQDv8aYE5tdZ86LJCoIIIG3OK7NvPwovfkcUlwD5nWhkUUK5GunXWmUGVqNRP6UG2tFiNqMCaBHQIGu9CDv0oJ1rok0rDDSSYNcdIANFkgeQoSdPrSYgee9Dy0+lFmQZrp5CkBY+FuNL3hdDlu2gu2jy86282U+cfIem81ck9s2BMMoVfWt20EDICUpy9YACtvKsrnXem97ZtXrJaeEpmQeYNUpPwQ6UW8mtXvbZwYq2Nu40l5pXvJyKAUQRyTMddZqNZ7aeDcKBcsG7hDikwe7tiSPKSRNY69wqRPc3IPQKT+tPLPh20t0AvgvuH+bRM0dWZaoUVwaNe9rzXErqbfD7dTNqjKlxTyYUUncaE9N5Ogp3fW9tilull5OfT7pxP4TH0/Ks/Yt2bYFLLSEJj8NS+FY9c4Y63qHWkKByKE7R9NBpWkKmLSOWvQ/lTxYQvMNvcKUlx5p9pKTmae7spSYOhB5VYbTimzFo0XFud4EjMIME8yIq+YH2j2V6yrvmTkAlKBCwnQCCIkH9zUcvs3RxJcvYi1at2jVwSvxfdmeWnUmtFFx7GYTlGf8A3ERPBV+zxJxA5hrrK+6UyVoWlUHRSZKtdNCY86tnFWEWGD8CYjcN2zLjoayoW+2CQpSQkq9QSY6RUjwrwJhnCCjeurQl0JjvCqVLHMJA1ifIk6VUO1Pjhq+Zc4cw1QWA9FwpOsxBAnbNO41iI32JNqP2CKTmumrGZtPvMT3T7rYPvZVETThWMYgbRdocQuO4c99HeGFeR8vLaotrgrivim6WLO1U3be62paihLsckjdR3mBAjerQz9n/AIntMOXdfxu1tnkoLi21FQQD0zDXX/lrlu/R6LpwSvJ5ZAzrvNCOtVTFDjGAYq/aXb6lPMOFtcKzIUQdYqy4HdsYtauOO3KGFtonKUE51fy6bTrrtSTvgtwaVxYGeQodOVFkHQCgOxIAmmQCVAAyQI3k0kq8tUEBT7acxhMq1NRmKYM7eNuOquXVuCShvQIB6AVBowbEM4ysKSrcHMNPrUuT9GkYxeblzU4gDMVJAHMa0LbqHU5kLCx1BmoO1wO5d1xG6WpMz3QUYJ86mWWGbdJSwylpJMwkQKpXJaS8isxrNd9KKnMTpqB0Sa4KBiDTsRcME5lBO0mJiYqaawFLa2u7xNpL2igpDyElIjkJBn41CSDtQZExsIFOLsKcZPhk6/heMXSCl29U80f/ADFlUpnnvR0cM2rCe8vLo9IJSgb9SZjX61E29jntXrlxa20IT4NPePIehJFNjKjmUSpW5JMmaq68oySk7qLsTbz+FYWsJtmUXNwlXvBcpSP+aNfh03pleYze3gUlbiUNqSU5GxAy9J3j40wMDlQx11pOXouNNJfbIGwGkfpXGeQoyS3rnKgBtlFATJkVBoBFARsAY8qGgMHU8qAPQX2XFf8AY3EiCNPbGDPP/DV/QfXpW4pbJMgn1J1rEvsrMpOFcSvFuVe0sIK+oCFGPmT863IjLsd68+t3s76XYgMqfOuofga6szQZzBis1+0W4GeyPF3FbJftFK0kx36P9K0oHLtWX/aUP/yZx1ISf8S1M8v8dFaw7kKXB5NaxO1egpeSmdPFoTTxMHUfSo6x4BxPE8CRidkC68VuBVrlhYCSkaE7k5tugPpUZe2+M4GpDd4zcWxUnMjvEbjqD8Dt0ruVTGUcfST7WWQRAGhjUeVTuE8a47gxT3F4txpJnunfGP8ASazc4zfEAd+dPIVwv759SUpdUtatgAJ/KmqyXBEtM5cm92vbG06gi+wxfiAzZYOw5bU9Z4/4JuCl11godPNdspRB8zBH1rz4X8WTJKXxl3lvb6VIYXdYhcLT36crSZJWpMFXlWq1LeLHPLRRir3N7Palwxbr7xn2hWVJShKWyCkcoER+96zHi7iJ7izE/a38wYbgMtORKRuZjczP0FRAncmu8oOvSm5t4YQpKOUPsHxzEMAuxdYc/wBysgBacshaZBgj1HLXzrS8K7YLbE3Db47aJtUq8XetkqQTOo2kSOsjzFZNrNDMUKbXATpRlmRteK8I4bi9sm5wpy3JcOZDbkZVztlKdCPMfKoF7gvGxkcfspUPdKVJAE9DVAwviDFcFUf4diNxapJktoVKFeqDKT8RU2z2ncUW0ZbtiQISruYKfQggfSqVX2c0tN/aXXB7HinDmhbNh0oKvcWtLjafISTBPODUziCnsKs1Xt3heDG8SEpKxKVwT7ubN4tN4+ZrLne03i5/MFYsUZjOZtlAPwMSKRwbjO8w3EVXd203iIWnKvvoKxrOZKiD4vWQelHUj6J+PP2WbFWMLxZsf9jYay4VBReYQQoxOm+opK3trexbKWWm0SfEtMA/Sp207R8DxFICsPHeLScyVIazEc52k/1pd5/gdKUKduUsBYzDO/kUNNikqB8v1raLgsmEozeGyAXlX4XAFpUNiNAAaTR2Z3OK23tdlbdwwsyHVqhIE7gbmekGrZb41wBaOpfRiVkFgyMzpcy9DEnXTpzpjj3ahYYxb+w4ZcKSV+AurCmyf+VJ3mSN/htSk4sqMKkFdFYwLge0ViyW8QvWy00SSh05EOkGAmeUnmSNB6VqYf4e4TsUsNMWw8Pu5ApalxOwJn4mPOs2Q6y2FQ4hMGCZH5Upbxcupt7dXfOO+FOQDxHy/fI01TijOVWTwy4Ymvg/iZltrEW0tlKpDqkKSpPkI2HWDVeuOx/DL1ZdwniCG1ahC0hwCehBmPWTT2x4PxG7RmWlptH80lZV6BO/TU9acf2Aue8Kl3rCXACUpCMylQfWlKEWXCrUiVDF+yfGbJoPYe6ziSNQoIGRWmmg1nnzHxqoX9jd4XcG2vrZ21eicrqcsg7Ecj8K2A8PcQ4SlRtHlLywpaELjN08J0V86M5jyzaex8QYUzdMLSQCpAhwc5GxPoZrN0fR0R1dsSRik0MzoEya1LEuzjhjGYVw/iZsHyJDS8ziF/5cqoUD6aetVjFuy/iXDVTb2zeJsq/8S0cBj1SYI+tZ7GjqjVjLyVRJkTBH50IMb/CpocD8TlQSMEvCfMJH60yucAxeydDVzhty0tQzJCkgZhMSDsRII9anJTml5GU+X0o7HcqfR7QVpZKvFlEkDyqXwzhe5fdCruGGgdU7qV6RTXELRGD4g3JQ82VZ0JO5g7VexrLMnVUntRpWDdk2GpZDmKKdGdMjxap+W5qk8acIv8NX7ikIWqwWv7twx4ZnwxvGhg/Derjwt2p21vhi0Yi8tDqJAZSicyZkQozJ5Rp8qqHF3Hl9xQtTQCmrNWU92sJUokGdwPCJjQbxqTTnsawTSVRP7Fa0mImug5hKpH5UE864mNPnNZWOlosCMGwtyzDpvvCAZWCBJG++v0+FJNN8PMKClvO3EfgIIB9YFQg9K4SZjbn1qtyXgx6Tv3MuGGY3wkpS0Ynw8HcxgOqUfd6gJ1B+PSpfE+zvDsfw7+L8HXKXUrBIsiSRpuApWoI6H5CazcZSRmOUEyTyA6xV14QTcYI49c2uIJIdAR4dUEDXxCaqP2xYzq/01dMqt7YXuE3Jt722dtngIyqGih5HY/ClcPxzEsIfQ/YX1xbuJmClZI13BSdCPhWu3XEeEY+wbfGcOQ6kNhMqSCCZ6pk+hiRVaueBeFbl1Jt8VurBskDVSVjzHjiP96JU2uBw1EWslXxPjnH8Vt1sP3qWWnQA6LRlDHeQI8RQASPLbfSk+FcNYxLFrW3uFJtkPK8D6wQ2gCcx8yKtN92c4BgyO/xPiNCLZSS4hYWnO5vCUJTmJ1idPlVA9qfJMOuIBSUwDAAO4AG2wmOlRe3JpZSWDaca7Q8H4XtjaMBy4vSlClNs+FQBHuqKh4AEwIgq8hvWfYn2k4zeZxaKFl3hJLjcd5G0BUSkRVTJMUbaKHJhGjFZELy0avmlNvoCpmFn3ges0zwPC14ahxTpBcc6HYVJ+mtchtx1xDTaVKWtQQkdVEwP0qLeTbc0rATA20npSCsQtEKhV0ylXQrE1qFn2MqVYocxTFksPOAQGwkpHlJ1OvPSqlxX2M3eCF9/2cXDbSS6vuyQvIDBWEicyRzI2kSOdU1JZsZwqwk7NlcGJ2c/95Z+Cwf1qSbxiybs1W7Fpbd64kpXcOrK1kGCAkaJTEHWDvVaTwvbKMl1wAmdCIA+WtLq4cshZlltBD+fOLkuHMBEZcu0TJnfXeouza0fZK5gTooTvSltbqurhLCAfEdY6VVrqzxm0SMjynkDbLqfiKNhXEWN4S48pljvFPDKe8ZMj0iKN9nkfSbX1Zo2KOIwS1bYt0lt1xIWglsEKE6nX0HzNM3nMNxJpGZTdpcq97cAHzMQZ03qjJw3FsSuTdXtwthRMyVeIegG1TLNs80YVcqdTyncevL6c606l/Bz9BRXOSwo4YfcTmTcNk+7Eaz5CdaUUxhGErWHlquX0D3E6+L8hz/pUM1dP26FIZfeQk7pQsgH4U1XddwEpWy5r/KkqAp3XhEqlJvLJO/xZ/EFZVBLbQIIbTPwk86aEwN96jl43boQT3b5UPwhtQP5UzXjd4qAzh7smYzpOorNy9m8abSwTkwIBrpiZOtQiH8ZuRlQwi2UoSVk7AdAZNGZYxttXiuLZxPPOD+gFK5Wz2yYkDpXEgCmgTfc1WZPUBQoqrJ12C7duhX/AKXhA/r8aqxNh9NFVA9KBAKUgEyYgnrRplJBHLSkB6K+yutJwDiNMai9ZOb1aP8AQ1uIMGTEVg32Ulh3hviJ7KpLhv22yDEaNbD0JOu31rd0ZhoYA6RXn1u9ndS7EHyo6V1B4On1rqyuWR5IOulZl9ot9LPZhcIUTL9/ZtpCRMnvQqPSEmtMUOcyazH7RTaXOy65JBQpvELNY9e9j9a2p9yFPhmZcAYvheH4QlDt6w24hxzO2rMVQcsGI8jrVotb7BcZcNs21b3C9V5QhO380GOVYzw61i9yp5vDLE35SAVNJ0CfMnbrueVTrfD/ABe+5Jwpm0yoK0lK0rWjpoFb+de3GStZnz04yvdFt4j7HeFuIh3luwmxfggG2AQPlsT+5rN8Q7FsawQAtMN4i0oEoeaBSpQiZjU/L6VemuLeKcJbs2rq3bdy+B155Bacd1n/AJSoA9JMDferRZca2N2kpfUlkCJ9pA06BKhp01MVHSi82LWpnH6qR5wvHb7DCfaLV0tKmDl9yOR5dOlMlcRaeFozy5a/WvVLqMFxQd3dexvlQyqUMiyfkdag73st4ccfC2wW8+6HWwVH0Kk6j4ms3Rl4ZvHUxfMcnnGwxS+uHQjIlaVGCogwmpvMdPTetxHZbgidG7gwfdGRn3unuUyuOx21WlSkXFtJnUMZSOhkLHxojSkuRPVQb4sYy6+hpBWtQShO5NR95jKW281u2XeWYg5U/wBa0zFuyfFLZou2y2bgtk+CdVJ6iR/WqbfYbdYa6tm8tlNKbIBzJ0121pSi+DWFWDfsrKLbFr4FxTq20nYKUUg+gFFJxLCDnUoraJE65h6eVWAQD/SuUgKBzJCkqEEETp51lsRt1f0JWl63eMB1uPNJPumkP4qhq7VbPqQjmlQMgjoelM3cDdadz2L5TI1BUQR8RRm+HEFADjq+8O5G1H24F9ObkyQFDUA+UUEBO0Cd4qJTh2JWnht7lDiBslf70+lFTdY0k5fZQYMaiR85qlL2T0r5TJoGRHlzNcrWJ22ioxF5iklKrJK1J3UFxNHRbYg+SXX0M+TQk/M6D4Ubl4G4W5ZKJubhO1w8mBEJcIgfOji7uknw3VwCnaHFCPrUWLK4bPhu1rPLOJ19RBpRti8CvFcJy84SZ+pq1IzdNeC0W3HfEtrZJs2sWfKEApQtfiWgHklRk6ax0kxFMxxNjgUD/GMQJkGDcKM/Wo0BQAnehynmKW4WyPotln2nY/ZOAG5763TshaQVoEclDX4Gr1hXG1vfstjEWGCF+6+jxAgeW88p18xWMwSN4pazvH7FzOyvQ+8hWqF+o/ZrWNW3JhU098xNxXwthWLNpesXFMOveNKm1ykHqBt8oo9phWPYTmbTcm4a0M5CojrqDI9BWY4Nxs5aGC87arVupBlsnqRr9Z9atltxtiFynM1dWqvNCBt0MVtFqXBxSi4P7Ivtm5djO5erbUBIkJKZGkaHny86rnEmJYZiF3btuhvu2niXUg+IDLB1Hnqr0HOq9cY3f3I+8vlqClaJSYE69BTSAY0hWwCTV2Ic0aY7hOF3VsHV2TMpT+IJEH4cukaU1fwjBMTs14e7ZMBRBQQSNZ00I+h61U8D4gewrwLPf2s5Qnco9PKf9PO6Buzxm3K2X0rXM521xkVMzp+/hUtFRkuTHuKOArjAnlqYWVtRKQoGSf5Z676fI1VFIKFFC0qSobhQg16CuX7nDrhXtNib9iApK2vHAmYUkn5EaeQpimw4a4yt12j9owHyD4XGg260f5kkQrT1PmKxlS9HVT1NsSML2rucVouPdlKbU5sNeuFCAe6WUqPSUnTMOcGD61UbnhXEbV1TagjOk5SDKSD0INZ7JHSq8H5IeDMGuVoDvPlUkjhzElyS0lP/AFT/AFpy1wnfLPjeaROxAKvnRsl6B14LyQcEkQTB+lHQ4tpQLa1IV/MkkGKkbnh2+thmADqYnwaGo0HKSCnUaEEVLTiVGcZrA9bxnEWkgC7UqBoFQr8xSTuIXb5Cnbl1caDxR+VN80xEDXpXA+h1pb2CpxXCDlalqzLUVE/iO9FUrmNDQDnXSDyFIsHcaH11oJA5UFCTtpSAkVcP3gs03TYDjZGbTcCJomBupaxiycUUwh1KxnMJJGoB9SBVj4bus2DITn1bKkTGsT/T8qQZwC3RfruivOiSptvT3q6HS4aOH5LvKMjU+IsUu7zhU3+F3D9utDWQOCO8Q2SJ9diCeeU8qi+DuPxjDqMMxIJs8VYIyGQQVTo40SSdj4kSZBMSJAzu94vxbDVPWFq6WbZZhaNw5/T4R51AX16rEnAtxtlACdY2PmSamU7cDpUm1Zl+474IwqweucRsLti0ZW8kqYUohLZWJAQVQCmUqIGigDzAmqd/ArpxBVbrZuABMNrCjHwmo5d0+8hpDtw64hMltCnCoJ9BOlECoUFCAobEb1GDo2zXkWcYeaJS4ysH0kVasB7Lcbxu2Re5WLRheudaphOniPIaHYmfKqivGXmBlcvrhA5FS1AfM6RU1ace45a2Ldo1etrQlBS0660hxaEmPdUQdoEHUid6WBtVLFsV2RpsYVd4vbPbq7m3UFOKA5wY0jU76A1V/wCD4M1hj19c4sppTileysMozOLSFQFQRqk7ySmPWoy6x7Fb7MLrE7x0KGUpLpCVDoQNKZBQ3k7RSbCMWstirhazQ2VlP+YAH6E/s0WZ2osgV2Y9PP0FBoEfedSr7m2Lg3nOBFA0nEHsxbswQJ1EqiNSTA5CKk2uH8ceYafYwfEnGXhLa27VxSVgjdMDUGk37XFMPbCn7TEbVDiCcy2XGwpOx1IGnLpTVhpkc00+HVLeU3JEFKE/LU/H50uIFEDgMlNDPzpAw0iuO1F/OhmBSEcDAAoZnfSihR3AroChvpQM9LfZWUTwZjWchQ/ihCfBH/hImDz/AE2raSdNQflWG/ZWeJ4a4htiow3iDbgEyAFNjbpOWtxEQBuN5rzavezvp9qOzeddRsvr866s7lkfEq0IJPnUVxJw3hvFmD3GDYzaG6sn4zICyghSTIUkiCFA7EVKAKOsmgKiNj/7q1Az7A+xfCuG7Z21wzFb4NOLLn36G3FpJAEZoEiAN9d9damG+z9Cm4fxR0qGpLbKR+ZNStpjYvsZVh9uwpTaLYvqfJgHx5EgDmDCjOnu6Urhd+7fuXZLSW0NOlDcKlS0iRKtNDKVCNdI86269VLk53pqUndogn+zPCrhBQ/cOrSrRSe6R4qhrzsK4bubjvxe4jb/APpsloJJ+KCaul7irdvdItgvuylIeuHViUMtSR/7lEQB6nYUvaX9tfha7Z4Od2QF7gpJEiQYIkUder7EtLSX8TO3ewHBVpT/ANsYlAOykNkK+QFOW+w3B2VtvJx3HmXW5yll5DY1EagJ1/2q/s3jTzjrTTjanGVZXEzJSf3+VOJzaGfjQ9RU4bCOkop3UShI7JWEkhXE+PlMSE94jQ/EGndl2atWYCXMdxC4SBADzLJHzAB+tXLloNfKmTl+EXSbdaHmyseBwp8Cz/KFfzeRo+RV9h8Sj/aRKeBbFIhd5cOR/NFRGM9kPDmOpQ3dOXaQ1P8AhuAFQP4VEgk1cbO+ZvEKLSl+GAoOIKFD1CgCKTGKWXelguoQ4FLTlV4ZyjU9I9fOk61R8sFpKKd9pnavs4dny15k2uKNz+FOJOAClUfZz7PEgzYYoo+eJOa1fnsStreydvwrvLdCSczRnY6j502XiSL23t+4fes1vvqYQpKEuha0Akidik5Tr5aVO+fs12R9FNT9nfs5ST/2dfz0OIOmPrXL+zr2drUojD8SQTslOIOQn0k1oIxC2N0u2U8hLyMkpMD3pgDqdDTrcanSl1Jex7I+jNB9m/s8yibXFfOL9dGR9nTs6QZNjiKx/Kq+c/QitBurpVutlplguuukhCUqCQYEkknQAD40C8S/vBtmmVvXCEpW4kKADSVTEqPMwYHlyp9SfsFCPoztX2b+zxSlkW+KthY0Sm/XCfMSD9a4fZy7PAogWuK68/4gvw1fWMWS/jN9aKeaShjuUIQogKUspKlRzIgp+tC8hNyu+aYxJ5t8BHeZFT7MjfQHRKiAdTrr6Ub5+w2R9FEH2b+z7MFey4qRvHt64/KknPs2cBKWVJbxhAgCE35I9dUnWtQtnm3GG3GyFtOJCklX4gRpTQ4xZJavLgrV7NZlQecCDlzJ95IjUkeQOvpS6k/YunH0Z039m/gAgEt4u7BjTEDv8BS7H2duztCwpdjiDgTuFYg4R8QCJq24Hi9q3w01e3ClNkjvngUEQtxRVAkCdVAb09RjCBae1O212w2XA2gKSCXJMAjXaTuY2p75+wUI+imXH2euzl5SFJwq7bKQAUtX7qQfM6701X9m3s+dTCLfF0GZlF+s/DUGtQQqUAqTB6EiarfFlxZOO2lm6u6bceMuO26nSplgHUwjmogJEjmelJVJN2uPpx9FOc+zRwGVQFY0CDqDej/+Fc39mzghlwLZuseaX+JSbxOv/wBm1XhKsBwGz9uQwm1QqdmVBxcCTodTprr0p27jdmh5DAWtTi20O5UNqJCFbKUI0E86fUmuGLpw9FIX2D8NJyhq/wAYCQI1dQonXrko6ewfh0JI9vxnX/1Ef/xq8uXqbcOPreZ9nQQ34PEsOTBT6zAjehYxu2feaaBX3jhcASpEe4AVE+XiAnqYqvkVP7jF6Si32oog7BeHiRGJYujXX7xBB+GWBRmuwvBbdzvWcYxptYmVJWhJ+iavt/jFtYBPepKitJWkIGY5Rufr8ZoLjFWGrkWhWtdyUhQZQklZSZ1jkNOZpfJq/wBwvh0f7UUs9juGLCQce4hGUGYuR4v/ALaSPYbw8uFJxXGAsGe8U8hSp/8AbpVxxG5aTdslx0tsWjar24AGqR7qBHqVaeVIXnECEYam5tGXi66tbbSVN6pyzmWRMZUgE766dafyKnsfxKP9pXEdkGHdyW1cR485yWEvJAMCNRBpsvsK4feUVnFcYWtRzElxJKj5+GrxYO29upFk26VLS0l4qI9/Oo+I+aiCYpy2tRfeBLeUFISEHxAxqF+cxHkaXyKq/kHxKL5ijOj2DYFrlxTFgeoUggfCKA9guAJUQjFsWQFRoe7P1y1pwnWRr1priF8xh9uXHllKY0SkFS3D0SBqo+Q1p/Kq/wBwnoqH9qM8HYPgQVpjOLlJG3gHTy8qbt/Zw4DTdd++nGrglWZTa70hCjM/hSPTetHbv2S+i3k9+pOYtgSUaTCo0SfU07kkQY+dTKvUlyzSnp6cO1GYq+zl2eklRs8TSDmOUXy412j05fWabK+zRwJKsr+OCY2uwY328H7itYGbaQR5mgBJJ1IPOp6kvZfTj6MnP2aeBogOY6k/zG9H5ZPjSY+zLwYFAG/x5Ubp9pbBP/7fxrXEkHeaGUxsfWjqy9j6cfRkzf2aOBs3jex5UASPbED46I/cVzn2ZuB1uHu38dQmNB7WDB66orWgoTBmPXehOp0iOvSjqz9h04+jKWfs88OWbSGbPEsVbaBJcC1JWpRJ3BgAcuXLzpx/wC4adYDb99iy1Z8ylIeSjMnknQGPUQa0l64aYTLzzbKZAzOKCRPxqBt8USmzvcRYu2lv4ncBuzQggkCMjZj0BWenwquvUta5l8elu3bclOuPs6cBXrrbzacVSlJOZv25S0uEKnXNJEajQjnPWk2fsycBIHiTirilBIWV3Z1AOoGmgUND9IOtafZ2rGHMNWjPuspgTqo9VfEmT605SsnRRj1FQ6kvZqoR9GXPfZ44FcsE2gaxFASolK03ErTJBiSDO2kzuaj0fZh4K7t0C7xkvK/w3XH0qLZiJjLB+NbAHEplMajeOdARI0HzoVSS8hsj6M7s+xfgTC7ZuwubO1eSNU+1d3nJI8R5bwNI61EXH2Y+BnHn3mF4pbF4HKW3kqDckEBMpJjlqSTV9xDD28Wx5pnuGD7E13q3XbbvJUsFISJI2GYweooLG3daw1ZsX7gWtsHDbJEffqneNg3OgSNIM9Ke6Xse2Poz3/4YOFe5cSMXxbMqCFlKPAQOkag7n05U3/8Ahd4eiBj+Kn0bbg1tAcEJCwEFUaTz6Ck0OIdJKFJVBUjTqDBHwNHUn7J6cPRhz/2WcPCV+z8V3qVfh7yzQoD1hQmmZ+y3coQvuOMG5UMsKsTBHQ+P0r0AFp0MjXbzoxIJ0p9afsOlD0YyjsJx9iyhjtDvvaUOeAOtBTSW8uo1BMyTEddqcXnY7xbcWybZjtAebYWCLgG2QFr0AEEJG+s+UVrIebW4W0uNqcT7yMwzJ9RRFX9qh4MKfaS4dkZhNPrz9idGHo8+s/ZbxIpaD3ElmrLKCEMKTCeWUkfTXnQXH2W8UQh4sY/alQUO6C0HKU883OZmK9FBQiRTK6uXmUOuOv21pbIghxSCtR8okazy1o60/YdGJ50X9mHicFYRjGFECchJWM3rpofnSafsycVl2F4lhAbE6pcWVK000KYEnTU16Kw69uPZHbjEMrTeaW1KRkWUQNVJkwSZgbxE08tb23vGEP27iXG17KH6jlR15h0Y+jzg59m/ituMl9YKbaDa0pytqUtegWNQnQDUBUg84mab3v2a+M/aVqtnsIW0o505rju1AnkUhMCPLSvR6sXabu2rdxm5C3l5EAtzy94wSQnTcgbjrXP4oEd4tu2ubhDJyuKYQFZT0iZMc4o68xOjEz/sQ7Osd7PrbFxjblpmvVtd2zbuZwkICvETAGuY6eVaiDzIPlUfZ4tb3qgltNwFdHGFo+ZIipJCRpM+lYzk27s1SSVkDHma6jd2rr9a6ouBGKWAf9KbXVs1eISh5RLUgqRMJX5K6p8udOVQE6aAUUKG9bDIFz2kd7iNwh5i3eu/v27Yw8bVtJQ2PCM2plZCdYVTqyatuHsDW63Z9wmFOqbnxqJJypJJMq1SmetSo0Vpt5U3uLRFw4ypSMwZdDqQdswGh+Ez8Ke6/IhDB7VywZW5dZE31yrvrpSFFQz7ZQf5UgBI8h50xwG6QvvhY3S8VSpKnXrl1CUZniPCnMAJJGhA90AVOD3YKRQaJAkEdKLhYi8ItnWSw66lxLiGl9646RnfcWQpUpEgJB2E1MTJmaKhSRMqrpgyATPMUm7jBKsm6hPmaj76zF26y859+i2+8btD4UOPDVClHfQ7chM6kCnwy55EkjrQyVCFbHaKAGtlaqYQt19wOXb57x1wnc9B/lSNAPLXegODYeoLzWluvvHhdLzpBzuAQFHzHLlToqCdBuOVCFSOlAWGv8MaUm8adQHWb1anHkL1CsyQkj0ITXIwxCLe3YNw+4lh0OMlwglqBASNNo01k607kGSJ+dCgpVrpp9KLisMb/BbO8F0Q00i5uGu6W+EDOAPd18jqPSnyElCQFGfPqetCSABtHWuMaQfrU8jIzE8NdxB9lQxB5hDS0rS222gnOCfEFESDBKfQnrTp2waW8u4SXWXVBKVKaVlCgNp6704MJOkyeQo0BQMlXpTuKwzVhFs428FsDPcZe8dSn7xRT7pKt5HKlkYfbN3r14loh95OVxWY+IeY25UuBoR7vWhSZGsHzmPpRewEcxg7Vm939u46hzuSzmdWXCUyCnQmPDGnqa5jClItL+3Vc5helZXkRkCCpOVRA89/WpIZSNda4amYIHWaLgJLt2n7X2V1OZrKEFJPIDT02Hyprc4aq4tRbvXt4qUZFKziXBP4pEE+flUiJKANT5UUwTv8hQmACEmEyZgAZidfWmeHW6kuXF482W7i5VEEyUtpkIT+aj5qNPxEDYetFylOoA360rgNMQwxrEDbrUpBctnO9bzoC0kxBBB5f0o6MOAxRzFFrh923Rbry+74VFUjnuo86dyE8oJ30oEgHQzO+pouwGTuDW71k9aqAyPuKeJifGVZs3Tf8qURhlopVs5cWbK3rZGRCw1lSkaTA2AMDSnaVdPzoSkgTH13oCwxRhqGQwbZaW3GMwQSJSQokkEdJ26Uum0Qbr2tcd/3IZUtOgKZmPgdvWlswSk6BP1ofeGxIoCwz/h7Kn7t5z70XaENuJVtkSCAPqaA4a1cNdzdqXeoSqW++MlGkETzHrTstpJ109aNoB7ogeVADC9wS0vnO9ctm1PgJSl7KMyAlUiD5GkFYbdJTihZdaS5fvqXmWD4ElsJEZYgiKloJO8T1oDoJ3B8tqAY3srY2Vq2zlbCgAFZSYJjWJoH7Rw3bF024pt5gKCZAIUlUSCPhyIpwIUYgesVxGUQBA6DnQAxw/DzhQLFu8o2hkoaXqWyeityD5zT+YnNpRQkTKYofHyg+VAHJGsTI9a7OFjUq09a6FAmU5T0neu8I1mfjSA4kEQVAjzrjJPIevOuBIHhPxruX+tABteeWPWhkzGojkOlJnWJmuJBEJUQfSgCO4gZauMKuLd5lDwfyM5VoCgkqUEzB6ST8KQtsJtLXiBr2Kzt7Vi1tCpIaaSJWtRSDtySkj/qqYCgoczXQAZ06U7gQyMAvG7hi9/iZXcsOBwy0EB4bKCzqrUHqACBpRsPwzEMMas2f4o5cpbWUrSpoAKQSSSZk5tdIPlFTCQmZn5GuiBMkzRcCKbN+7jKlvNXAsy2MjanEZGnBzhKpXmnntFS4QRqdPSipSAenx3rhCZg+tAERiNlc2+FYkpGJOsrcLtyXUISVBIR7gkHkmJpCwwN9XDP8PcxO6V7TY9zLiUnuipEaQBtJqZvLRN6yph3MW1jxAGMw6HypY66mQaLgQFzwfYXV1hdyVON+wN913aB4XESlWXXVPiSDp6daeqwSzcfL7veuLDi1oJWR3ef3kpiPCqST/oKkRAoZ60XYEScG7oMizuVWfdLdUMiQYS5ukdIiaWtcOetXLdX8Qurju8wWX15itMaCBAkHnvT8kE7gDzE0AKokdelILEc1h7lnijl00wl5Nz77i1wtrqAI1SSB50bDcJbwt2/Ww4pSb25VdKSoABCiACkdRInXqakCsETNdE9aYAyTuZpjiNkq97haH+5ftnQ62vLnEwQQpPMEEjqKe8on6UBMDQ60ANbu1cummczqQ606l5Kgjw5htKZ21NJ2dq61fXF2+4yS8EAtNJITKZGYydzIHwFPRM6z89qHMSP0NLxYBjhmHnDHH1B5LpfWVqccR96QTITmBggbDTai21tcIvAtLQtbfxlbaX8yHFE6KCY0PP4/GpGZGhoYpXAMkTvr5k7UohUq0P0pNKugUPU0cabyakYeD1FdRZHT6V1TtYDAk0Vs55murq6GByfAJTpzrisyP8AMJNdXUgQDJ73VWtHWAlKSABNdXUmDCNKzEylM+lHWkJTmG5rq6hCQGmVKo1oxE11dTYwsaDU/Oikz866upgHjzNcrQ11dSYBQs+HQa0aZHwrq6hADJBEEiuzK6k+tdXUAHyiRQlRIkxXV1SAYmEz8aBsBSdeddXUCAUTrrEUGYzXV1UhixTDaVySfOiFRrq6kByVmCPKj7JBFdXUACSYB6mKItRB05V1dSAMB11jrQ9Ryrq6gAq/DEUKDmMaDWurqBA7k+VGyw3mkyfOurqBhSrlRUeLfrXV1ABnEpSoECJow0bKhvXV1AgFAZssQJok67DSurqBhgJBPMUChEV1dQByk85OvnXDpXV1ABSY1FABm3Jrq6gRxMAxRgI039a6uoBAfHauB0iurqAABkkdKHXrXV1AAgmKKa6uoA5HiOpo6W0qBJnSurqACDSTA2rk7murqAOX7szRDXV1Aw0mK4amurqGINzro1iSK6upAdtrueppVJJEya6upAg2vU11dXUDP//Z"
EXTERNAL_WORKS = [
    {
        "artist": "Hans Pfrommer",
        "work": "Mein schönstes Ferienerlebnis",
        "technique": "Farblinolschnitt",
        "edition": "15/30",
        "size": "27,5 × 26,5 cm",
        "year": "2025",
        "price": "170 €",
        "gallery": "Emmanuel Walderdorff Galerie, Molsberg",
        "acquired": "08.12.2025",
        "image_url": _PFROMMER_IMG,
    },
]


def technique_value(work_text):
    """Druckwert (T, 1–5) eines einzelnen Blattes aus seiner Technik. Unikat(5) → Offset(1)."""
    t = (work_text or "").lower()
    best = None
    for val, kws in TECHNIQUE_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                best = val if best is None else (max(best, val) if val > 3 else min(best, val) if val < 3 else best)
    return best if best is not None else 3  # unbekannt → mittel

def artist_total(info):
    """Künstler-Score = R + M + P (technikunabhängig, max. 15) — Basis für die Liga."""
    r = info.get("rmtp", {})
    return r.get("R", 0) + r.get("M", 0) + r.get("P", 0)

def rang_score(info):
    """Rang-Score = R×2 + M + P (reputationsgeführt, max. 20). Nur für die 'beste zuerst'-Reihenfolge."""
    r = info.get("rmtp", {})
    return r.get("R", 0) * 2 + r.get("M", 0) + r.get("P", 0)

def rang_sortkey(info):
    """Sortierschlüssel 'beste zuerst': Rang-Score, dann R, dann Blue-Chip, dann M+P."""
    r = info.get("rmtp", {})
    return (rang_score(info), r.get("R", 0), 1 if info.get("isBlueChip") else 0,
            r.get("M", 0) + r.get("P", 0))

def blatt_value(info, work_text):
    """Blatt-Wert = Künstler-Score (R+M+P) + Druckwert (T) dieses Blattes (max. 20)."""
    return artist_total(info) + technique_value(work_text)

def liga_from_rmp(r, art):
    if r >= 4 and art >= 10:
        return "Liga 1"
    elif art >= 9 or r >= 4:
        return "Liga 2"
    elif art >= 5:
        return "Liga 3"
    elif art > 0:
        return "Liga 4"
    return ""

# ─── Liga dynamisch aus R+M+P berechnen (technikunabhängig) ───
# Liga in artists_data aktualisieren
for name, info in artists_data.items():
    rmtp = info.get("rmtp", {})
    if rmtp:
        r = rmtp.get("R", 0)
        art = rmtp.get("R", 0) + rmtp.get("M", 0) + rmtp.get("P", 0)
        info["liga"] = liga_from_rmp(r, art)
    else:
        info["liga"] = ""

# Spitze der Sammlung: reputationsgewichteter Rang (R×2+M+P) ≥ 17
SPITZE_RANG_MIN = 17

# Liga + Spitze in collection-Einträgen aktualisieren (aus Artist-Score)
for w in collection:
    artist_info = artists_data.get(w["artist"], {})
    w["liga"] = artist_info.get("liga", "")
    w["isSpitze"] = bool(artist_info.get("rmtp")) and rang_score(artist_info) >= SPITZE_RANG_MIN

# Stats dynamisch berechnen
stats = {
    "totalWorks": len(collection),
    "totalArtists": len(set(w["artist"] for w in collection)),
    "liga1": len(set(w["artist"] for w in collection if w["liga"] == "Liga 1")),
    "liga2": len(set(w["artist"] for w in collection if w["liga"] == "Liga 2")),
    "liga3": len(set(w["artist"] for w in collection if w["liga"] == "Liga 3")),
    "liga4": len(set(w["artist"] for w in collection if w["liga"] == "Liga 4")),
    "blueChip": len(set(w["artist"] for w in collection if w["isBlueChip"])),
    "spitze": len(set(w["artist"] for w in collection if w.get("isSpitze"))),
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
        background: linear-gradient(rgba(0,0,0,0.18), rgba(0,0,0,0.36)), url('https://www.griffelkunst.de/galleryimages/_galleryimages/E417-Tal-R.jpg');
        background-size: 130%; background-position: center; background-color: #1B3A2A;
        margin: -2rem -1rem 2rem -1rem;
        padding: 3.4rem 1rem 1.8rem;
        border-radius: 0 0 2px 2px;
    }
    .app-header h1 {
        font-size: 2.7rem; font-weight: 400; letter-spacing: 0.12em;
        color: #F8F6F3; margin-bottom: 0.3rem; text-transform: uppercase; text-shadow: 0 2px 10px rgba(0,0,0,0.45);
    }
    .app-header .subtitle {
        font-size: 1.1rem; color: #E8CE92; letter-spacing: 0.05em; font-style: italic; text-shadow: 0 1px 6px rgba(0,0,0,0.5);
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
    art = rmtp.get("R", 0) + rmtp.get("M", 0) + rmtp.get("P", 0)
    _lg = liga_from_rmp(r, art)
    if _lg:
        return _lg
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
    if any(t in work_lower for t in ["heliograv", "photograv", "fotograv"]): return "Heliogravüre"
    if "cyanotyp" in work_lower: return "Cyanotypie"
    if "monotyp" in work_lower: return "Monotypie"
    if "aquatint" in work_lower: return "Aquatinta"
    if any(t in work_lower for t in ["lithograph", "litho", "farblitho", "algraphie", "algrafie"]): return "Lithographie"
    if any(t in work_lower for t in ["siebdruck", "serigraph"]): return "Siebdruck"
    if any(t in work_lower for t in ["radierung", "kaltnadel", "strichätz", "strichaetz", "weichgrund", "ätzung", "aetzung"]): return "Radierung"
    if any(t in work_lower for t in ["fotografie", "photographie", "photograph", "foto", "photo", "inkjet", "c-print", "ph a.d.n", "fotogram", "s/w", "polaroid"]): return "Fotografie"
    if "holzschnitt" in work_lower: return "Holzschnitt"
    if any(t in work_lower for t in ["holzdruck", "holz-", "linol"]): return "Holz-/Linoldruck"
    if any(t in work_lower for t in ["hochdruck", "reliefdruck", "reliefdr", "relief"]): return "Hochdruck"
    if "prägedr" in work_lower or "praegedr" in work_lower: return "Prägedruck"
    if "multiple" in work_lower: return "Multiple"
    if any(t in work_lower for t in ["offset", "digitaler", "digital"]): return "Offsetdruck"
    if any(t in work_lower for t in ["bleistiftzeichnung", "kohlezeichnung", "tuschzeichnung", "federzeichnung"]): return "Zeichnung"
    return "Sonstige"

_KNOWN_TECH_LABELS = {"Mezzotinto","Schadographie","Heliogravüre","Cyanotypie","Monotypie","Aquatinta",
                      "Lithographie","Siebdruck","Radierung","Fotografie","Holzschnitt","Holz-/Linoldruck",
                      "Linolschnitt","Hochdruck","Prägedruck","Multiple","Offsetdruck","Zeichnung","Digitaldruck"}

def work_technique(w):
    """Technik primär aus dem Werktitel; nur wenn dort nichts erkennbar ist,
    Rückfall auf das gespeicherte technik-Feld. Kann bestehende Zuordnungen nie verschlechtern."""
    t = extract_technique(w.get("work", "") or "")
    if t != "Sonstige":
        return t
    stored = (w.get("technik") or "").strip()
    if stored:
        if stored in _KNOWN_TECH_LABELS:
            return stored
        t2 = extract_technique(stored)
        if t2 != "Sonstige":
            return t2
    return "Sonstige"

def blatt_typ(edition, work=""):
    """Griffelkunst-Blatt-Typ aus dem Editionscode: Wahlblatt (A/B/C), Projektblatt (P), Einzelblatt (E), Mappe, Sonderedition."""
    ed = (edition or "").strip()
    if "mappe" in (work or "").lower() or "mappe" in ed.lower():
        return "Mappe"
    if re.match(r'^P\s*\d', ed):
        return "Projektblatt"
    if re.match(r'^E[\s\d]', ed):
        return "Einzelblatt"
    if re.match(r'^\d', ed):
        return "Wahlblatt"
    return "Sonderedition"

BLATTTYP_INFO = {
    "Wahlblatt": "Aus der vierteljährlichen Wahl (Reihen A/B/C). Kern des Griffelkunst-Programms — gewählt wird nach Anfangsbuchstabe des Nachnamens: A-He aus Reihe A, Hi-Q aus B, R-Z aus C.",
    "Projektblatt": "Aus der Projekt-Reihe (Code P…). Kann ohne Tauschgebühr aus beiden Wahlen gewählt werden.",
    "Einzelblatt": "Separate Sonderedition (Code E…) mit eigenem Preis — nur zusätzlich zu den Reihen A/B/C erwerbbar, nicht anstelle eines Wahlblattes.",
    "Mappe": "Zusammengehörige Serie in einer Sammelmappe.",
    "Sonderedition": "Sonstige Editionen/Sonderformate außerhalb des regulären Wahl-Schemas.",
}

# Alle einzigartigen Techniken in der Sammlung
ALL_TECHNIQUES_IN_COLLECTION = set(work_technique(w) for w in collection if work_technique(w) != "Sonstige")
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
    "Hochdruck": "Hochdruckverfahren (Oberbegriff): Die druckenden Teile liegen erhöht, die Farbe wird von der erhabenen Fläche aufs Papier übertragen. Dazu zählen Holz- und Linolschnitt, aber auch freie Verfahren wie bei Karimah Ashadu (Icons/Machine Boys).",
    "Prägedruck": "Blindprägung/Prägedruck: Ein Motiv wird ohne oder mit wenig Farbe reliefartig ins Papier gepresst — der Reiz liegt im Licht-Schatten-Spiel der Prägung.",
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
st.markdown('<div class="app-header"><h1>Trüffelkunst</h1><div class="subtitle">Sammlung Bodman</div></div>', unsafe_allow_html=True)

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
spitze_count = len(set(w["artist"] for w in collection if w.get("isSpitze")))

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
technique_count = len(set(work_technique(w) for w in collection if work_technique(w) != "Sonstige"))

# ─── Druckwerkstätten ───
_WERKSTATT_ALIAS = {
    "foto company altona": "Foto Company Altona, Hamburg",
    "foto company altona hamburg": "Foto Company Altona, Hamburg",
    "fotocompany altona": "Foto Company Altona, Hamburg",
    "piglab hamburg": "PigLab, Hamburg", "pig lab hamburg": "PigLab, Hamburg",
    "piglab": "PigLab, Hamburg", "pig lab": "PigLab, Hamburg",
    "kunst und radierwerkstatt w jesse berlin": "Kunst- und Radierwerkstatt Jesse, Berlin",
    "kunst und radierwerkstatt willi jesse berlin": "Kunst- und Radierwerkstatt Jesse, Berlin",
    "stephan rosentreter leipzig": "Stephan Rosentreter, Leipzig",
    "stefan rosentreter leipzig": "Stephan Rosentreter, Leipzig",
    "stephan rosentreter lithographisches atelier leipzig": "Stephan Rosentreter, Leipzig",
    "thomas franke stein werk leipzig": "Thomas Franke – stein_werk, Leipzig",
    "stein werk thomas franke leipzig": "Thomas Franke – stein_werk, Leipzig",
    "martin samuel berlin": "1×2 Siebdruck (Martin Samuel), Berlin",
    "1×2 siebdruck martin samuel berlin": "1×2 Siebdruck (Martin Samuel), Berlin",
    "1x2 siebdruck martin samuel berlin": "1×2 Siebdruck (Martin Samuel), Berlin",
    "martin samuel 1x2 siebdruck berlin": "1×2 Siebdruck (Martin Samuel), Berlin",
    "siebdruckwerkstatt ahrens munchen": "Siebdruckwerkstatt Ahrens",
    "siebdruckwerkstatt ahrens ottobrunn": "Siebdruckwerkstatt Ahrens",
    "fritz margull berlin": "Fritz Margull, Berlin", "fritze margull berlin": "Fritz Margull, Berlin",
    "handdruck loeding sturm hamburg": "Handdruck Loeding & Sturm, Hamburg",
    "ellen sturm loeding hamburg": "Handdruck Loeding & Sturm, Hamburg",
    "ellen sturm loeding carlos leon hamburg": "Handdruck Loeding & Sturm, Hamburg",
    "peter loeding und ellen sturm hamburg": "Handdruck Loeding & Sturm, Hamburg",
}
def canon_drucker(d):
    """Werkstatt-Name vereinheitlichen + bekannte Schreibvarianten zusammenführen."""
    if not d: return ""
    d = re.sub(r"\([^)]*\)", "", d)
    d = d.split(";")[0]
    d = d.replace("-", " ").replace("_", " ")
    d = re.sub(r"\s+", " ", d).strip(" ,;")
    _k = re.sub(r"[.,&]", " ", d.lower()); _k = re.sub(r"\s+", " ", _k).strip()
    return _WERKSTATT_ALIAS.get(_k, d)

# ─── Kurzprofile bekannter Werkstätten (verifizierte Charakterisierung) ───
WERKSTATT_NOTE = {
    "Tabor Presse, Berlin": "Renommierte Berliner Lithografie-Werkstatt; realisiert originale Steindrucke für zahlreiche zeitgenössische Künstlerinnen und Künstler.",
    "Steindruckerei Wolfensberger, Zürich": "Traditionsreiche Schweizer Steindruckerei, spezialisiert auf künstlerische Lithografie.",
    "Handdruck Loeding & Sturm, Hamburg": "Hamburger Handdruck-Werkstatt (Ellen Sturm-Loeding / Peter Loeding), eng mit der Griffelkunst verbunden — Holzdruck, Lithografie, Radierung.",
    "Atelier für Druckgrafik, Wedel": "Druckwerkstatt bei Hamburg mit Schwerpunkt Hoch- und Tiefdruck (Holz-/Hochdruck, Radierung).",
    "Kunst- und Radierwerkstatt Jesse, Berlin": "Berliner Tiefdruck-Werkstatt, spezialisiert auf Radierung, Aquatinta und Heliogravüre.",
    "Felix Bauer, Köln": "Kölner Lithograf; Steindruck-Editionen für viele Griffelkunst-Künstler.",
    "Recom Art, Berlin": "Berliner Spezialbetrieb für hochwertige Fine-Art-Fotoabzüge (u. a. Barytpapier).",
    "Saal Presse, Bergsdorf": "Druckwerkstatt mit Schwerpunkt Holz- und Steindruck.",
    "Merkur Druck, Norderstedt": "Druckerei bei Hamburg; häufig für Offset-Editionen und Mappen.",
    "1×2 Siebdruck (Martin Samuel), Berlin": "Berliner Siebdruck-Atelier für künstlerische Editionen.",
    "Gundolf Roy, Zülpich": "Siebdruck-Werkstatt in Zülpich.",
    "Atelier Margotow, Wahlershausen": "Fotolabor für Barytabzüge; druckt Nachlass-Fotoeditionen (u. a. Moholy-Nagy, Chargesheimer).",
}

_werkstatt_groups = {}
for w in collection:
    _cd = canon_drucker(w.get("drucker", ""))
    if _cd:
        _werkstatt_groups.setdefault(_cd, []).append(w)
druckwerkstatt_count = len(_werkstatt_groups)

if "view" not in st.session_state:
    st.session_state.view = "künstler"
if "selected_artist" not in st.session_state:
    st.session_state.selected_artist = None
if "selected_technique" not in st.session_state:
    st.session_state.selected_technique = None
if "selected_blatttyp" not in st.session_state:
    st.session_state.selected_blatttyp = None
    st.session_state.selected_werkstatt = None
if "selected_werkstatt" not in st.session_state:
    st.session_state.selected_werkstatt = None

SCORE_VIEWS = {"künstler", "werke", "spitze", "liga1", "liga2", "liga3", "bluechip", "meisterschueler"}

def set_view(v):
    st.session_state.view = v
    st.session_state.selected_artist = None
    st.session_state.selected_technique = None
    st.session_state.selected_blatttyp = None
    st.session_state["_scroll_to_content"] = True

# ── Navigation ausblenden wenn Künstler-Detail oder Technik-Detail offen ──
_show_nav = (st.session_state.selected_artist is None and st.session_state.get("selected_technique") is None and st.session_state.get("selected_blatttyp") is None and st.session_state.get("selected_werkstatt") is None)

if _show_nav:
    # ── Kachel-Styling: Gruppen-Labels + leichtere Sekundär-/Liga-Kacheln ──
    st.markdown("""<style>
    .nav-group-label{font-size:0.62rem;letter-spacing:0.09em;text-transform:uppercase;color:#B0A692;margin:0.6rem 0 0.15rem 3px;font-weight:600;}
    .st-key-btn_techniken button,.st-key-btn_bluechip button,.st-key-btn_meister button,
    .st-key-btn_blatttyp button,.st-key-btn_druckwerkstatt button,.st-key-btn_extern button,
    .st-key-btn_liga1 button,.st-key-btn_liga2 button,.st-key-btn_liga3 button{
      background:#FAF8F4 !important;border:1px solid #ECE7DE !important;}
    .st-key-btn_techniken button p,.st-key-btn_bluechip button p,.st-key-btn_meister button p,
    .st-key-btn_blatttyp button p,.st-key-btn_druckwerkstatt button p,.st-key-btn_extern button p,
    .st-key-btn_liga1 button p,.st-key-btn_liga2 button p,.st-key-btn_liga3 button p{
      font-size:0.8rem !important;color:#6B6255 !important;}
    .st-key-btn_spitze button{background:#F3ECD9 !important;border:1px solid #D9C27A !important;}
    .st-key-btn_spitze button p{color:#8A6D22 !important;}
    </style>""", unsafe_allow_html=True)

    # ── Ebene 1: Haupt-Ansichten ──
    _rowA = st.columns(2)
    with _rowA[0]:
        if st.button(f"**{unique_artists}**\n\nKÜNSTLER", use_container_width=True, key="btn_kuenstler"):
            set_view("künstler")
    with _rowA[1]:
        if st.button(f"**{len(collection)}**\n\nWERKE", use_container_width=True, key="btn_werke"):
            set_view("werke")

    # ── Auslese: Spitze der Sammlung (Reputation ≥ Rang 17) ──
    st.markdown('<div class="nav-group-label">Auslese</div>', unsafe_allow_html=True)
    if st.button(f"**{stats['spitze']}**\n\nSPITZE", use_container_width=True, key="btn_spitze"):
        set_view("spitze")

    # ── Liga (gebündelt) ──
    st.markdown('<div class="nav-group-label">Liga · nach Rang</div>', unsafe_allow_html=True)
    _rowL = st.columns(3)
    with _rowL[0]:
        if st.button(f"**{stats['liga1']}**\n\nLIGA 1", use_container_width=True, key="btn_liga1"):
            set_view("liga1")
    with _rowL[1]:
        if st.button(f"**{stats['liga2']}**\n\nLIGA 2", use_container_width=True, key="btn_liga2"):
            set_view("liga2")
    with _rowL[2]:
        if st.button(f"**{stats['liga3']}**\n\nLIGA 3", use_container_width=True, key="btn_liga3"):
            set_view("liga3")

    # ── Ebene 2: Sichten & Filter ──
    st.markdown('<div class="nav-group-label">Sichten &amp; Filter</div>', unsafe_allow_html=True)
    _rowB = st.columns(3)
    with _rowB[0]:
        if st.button(f"**{technique_count}**\n\nTECHNIK", use_container_width=True, key="btn_techniken"):
            set_view("techniken")
    with _rowB[1]:
        if st.button(f"**{blue_chip_count}**\n\nBLUE CHIP", use_container_width=True, key="btn_bluechip"):
            set_view("bluechip")
    with _rowB[2]:
        if st.button(f"**{meisterschueler_count}**\n\nMEISTER\u00adSCHÜLER", use_container_width=True, key="btn_meister"):
            set_view("meisterschueler")
    _rowC = st.columns(3)
    with _rowC[0]:
        if st.button(f"**{len(set(blatt_typ(w['edition'], w['work']) for w in collection))}**\n\nBLATT-TYP", use_container_width=True, key="btn_blatttyp"):
            set_view("blatttyp")
    with _rowC[1]:
        if st.button(f"**{druckwerkstatt_count}**\n\nDRUCK\u00adWERKSTÄTTEN", use_container_width=True, key="btn_druckwerkstatt"):
            set_view("druckwerkstaetten")
    with _rowC[2]:
        if st.button(f"**{len(EXTERNAL_WORKS)}**\n\nWEITERE WERKE", use_container_width=True, key="btn_extern"):
            set_view("extern")

    # ── Aktive Kachel hellgrün hervorheben ──
    _view_key = {"künstler": "btn_kuenstler", "werke": "btn_werke", "techniken": "btn_techniken",
                 "spitze": "btn_spitze", "bluechip": "btn_bluechip", "meisterschueler": "btn_meister", "liga1": "btn_liga1",
                 "liga2": "btn_liga2", "liga3": "btn_liga3",
                 "blatttyp": "btn_blatttyp", "extern": "btn_extern",
                 "druckwerkstaetten": "btn_druckwerkstatt"}
    _active_key = _view_key.get(st.session_state.view)
    if _active_key:
        st.markdown(
            f"<style>.st-key-{_active_key} button {{ background:#E3F1E0 !important; "
            f"border:1px solid #8FB98A !important; color:#1B3A2A !important; box-shadow:none !important; }} "
            f".st-key-{_active_key} button p {{ color:#1B3A2A !important; font-weight:700 !important; }}</style>",
            unsafe_allow_html=True
        )
    st.markdown('<div style="border-bottom: 1px solid #E0DDD8; margin-bottom: 0.8rem;"></div>', unsafe_allow_html=True)

    # Suchfeld nur in den Bewertungs-/Listen-Ansichten
    if st.session_state.view in SCORE_VIEWS:
        search = st.text_input("🔍 Suche", placeholder="Künstler, Werk, Edition…", label_visibility="collapsed")
    else:
        search = ""

    # Score-Legende nur in den Bewertungs-/Listen-Ansichten
    if st.session_state.view in SCORE_VIEWS:
        st.markdown(
            '<div style="text-align:center;margin:-0.3rem 0 0.35rem;font-family:Cormorant Garamond,Georgia,serif;color:#3F382E;letter-spacing:0.02em;">'
            '<div style="display:flex;gap:1.1rem;justify-content:center;align-items:center;flex-wrap:wrap;font-size:0.86rem;font-weight:600;">'
            '<span><span style="color:#C44B3F;">R</span> Reputation</span>'
            '<span><span style="color:#6B7DB3;">M</span> Momentum</span>'
            '<span><span style="color:#5A9E5A;">T</span> Druckwert</span>'
            '<span><span style="color:#C4993D;">P</span> Potenzial</span>'
            '<span style="font-weight:400;color:#8A8277;">Künstler-Liga = R+M+P (max 15) · Blatt-Wert = +T (max 20)</span>'
            '</div></div>',
            unsafe_allow_html=True
        )
        with st.expander("Was bedeuten R · M · T · P — und die Liga-Stufen?", expanded=False):
            st.markdown(
                '<div style="font-size:0.8rem;color:#4F473B;line-height:1.7;">'
                '<div><span style="display:inline-block;width:1.15rem;font-weight:700;color:#C44B3F;">R</span><b>Reputation</b> — Galerien · Museen · Kunstgeschichte</div>'
                '<div><span style="display:inline-block;width:1.15rem;font-weight:700;color:#6B7DB3;">M</span><b>Momentum</b> — Aktualität: Museums-Solo · Biennale · Preis · Galeriewechsel · Auktionstrend (jüngste Jahre stärker; auch posthum)</div>'
                '<div><span style="display:inline-block;width:1.15rem;font-weight:700;color:#5A9E5A;">T</span><b>Druckwert</b> — pro Blatt: Unikat (5) → Offset (1); zählt nur zum Blatt-Wert</div>'
                '<div><span style="display:inline-block;width:1.15rem;font-weight:700;color:#C4993D;">P</span><b>Potenzial</b> — Wertsteigerungschance: Karrierestand · Marktdynamik · Editionsseltenheit</div>'
                '<div style="margin-top:0.55rem;padding-top:0.45rem;border-top:1px solid #E8E4DC;">'
                '<b>Liga</b> (nach R+M+P): '
                '<span style="color:#C44B3F;font-weight:700;">1</span> R≥4 &amp; ≥10 &nbsp;·&nbsp; '
                '<span style="color:#6B7DB3;font-weight:700;">2</span> ≥9 oder R≥4 &nbsp;·&nbsp; '
                '<span style="color:#5A9E5A;font-weight:700;">3</span> ≥5 &nbsp;·&nbsp; '
                '<span style="color:#C4993D;font-weight:700;">4</span> Rest</div>'
                '</div>',
                unsafe_allow_html=True
            )
else:
    # Detail-Ansicht: Navigation ausgeblendet, nur search-Variable initialisieren
    search = ""

# ── Anker + einmaliger Auto-Scroll zum Inhalt nach Kachel-Klick ──
if _show_nav:
    st.markdown('<div class="gk-content-top" style="scroll-margin-top:6px;height:0;"></div>', unsafe_allow_html=True)
    if st.session_state.pop("_scroll_to_content", False):
        components.html("""
        <script>
        (function(){
          function go(){
            try{
              var docs=[];
              try{docs.push(window.parent.document);}catch(e){}
              try{if(window.top && window.top!==window.parent){docs.push(window.top.document);}}catch(e){}
              for(var i=0;i<docs.length;i++){
                var d=docs[i];
                var el=d.querySelector('.gk-content-top');
                if(el){
                  var w=d.defaultView||window;
                  var y=el.getBoundingClientRect().top + (w.pageYOffset||d.documentElement.scrollTop||0) - 6;
                  try{ w.scrollTo(0, y); }catch(e){}
                  try{ d.documentElement.scrollTop=y; }catch(e){}
                  try{ if(d.body) d.body.scrollTop=y; }catch(e){}
                  var sels=['section.main','[data-testid="stAppViewContainer"]','[data-testid="stMainBlockContainer"]','.main','.block-container'];
                  for(var s=0;s<sels.length;s++){ var c=d.querySelector(sels[s]); if(c){ try{ c.scrollTop = (el.getBoundingClientRect().top - c.getBoundingClientRect().top) + c.scrollTop - 6; }catch(e){} } }
                  try{ el.scrollIntoView({block:'start'}); }catch(e){}
                  return true;
                }
              }
            }catch(e){}
            return false;
          }
          go(); [50,150,300,500,800,1200,1800].forEach(function(ms){ setTimeout(go, ms); });
        })();
        </script>
        """, height=0)

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
        if work_technique(work) not in selected_techniques:
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



# ─── Querverbindungen zwischen Künstlern (Stufe 1: aus Daten abgeleitet) ───
_MOVEMENTS = [
    ("Junge Wilde / Mülheimer Freiheit", ["junge wilde", "mülheimer freiheit"]),
    ("Neue Leipziger Schule", ["neue leipziger schule", "leipziger schule"]),
    ("Clara Mosch", ["clara mosch", "clara-mosch"]),
    ("Becher-Schule", ["becher-schule", "becher-klasse", "becher schule"]),
    ("Fluxus", ["fluxus"]),
    ("Neue Sachlichkeit", ["neue sachlichkeit"]),
    ("Bauhaus", ["bauhaus"]),
    ("Moskauer Konzeptualismus", ["moskauer konzeptual"]),
    ("DDR-Avantgarde", ["ddr-avantgarde", "ddr-kunst", "clara mosch"]),
    ("Hamburger Sezession", ["hamburger sezession"]),
    ("Gruppe Normal", ["gruppe normal", "normal group"]),
    ("Neues Sehen", ["neues sehen"]),
]

def _artist_text(info):
    return ((info.get("significance","") or "") + " " + (info.get("potential","") or ""))

def _extract_teachers(info):
    text = _artist_text(info)
    low = text.lower()
    teachers = set()
    if "beuys-schüler" in low or "beuys-klasse" in low or "beuys-umfeld" in low:
        teachers.add("Joseph Beuys")
    for m in re.finditer(r"Meistersch[üu]ler(?:in)?\s+(?:von\s+|bei\s+|unter\s+)?([A-ZÄÖÜ][\wäöüß.\-]+(?:\s+[A-ZÄÖÜ][\wäöüß.\-]+){1,2})", text):
        teachers.add(m.group(1).strip(" .,|"))
    for m in re.finditer(r"Sch[üu]ler(?:in)?\s+(?:von|bei|unter)\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s+[A-ZÄÖÜ][\wäöüß.\-]+){0,2})", text):
        teachers.add(m.group(1).strip(" .,|"))
    return teachers

_art_galleries = {}
_art_movements = {}
_art_teachers = {}
_CANON_GALLERIES = [
    "Gagosian", "Hauser & Wirth", "Pace Gallery", "David Zwirner", "Marian Goodman",
    "Sprüth Magers", "Lisson", "Thaddaeus Ropac", "Gladstone", "White Cube",
    "neugerriemschneider", "Esther Schipper", "Galerie Buchholz", "Matthew Marks",
    "Paula Cooper", "Max Hetzler", "König Galerie", "Perrotin", "Petzel", "Eigen+Art",
    "Tanya Bonakdar", "Sadie Coles", "Konrad Fischer", "Karsten Greve", "Templon",
    "Almine Rech", "Peter Kilchmann", "Capitain", "Nagel Draxler", "Barbara Wien",
    "Meyer Riegger", "Contemporary Fine Arts", "Kleindienst", "LEVY", "Whitestone",
    "COSAR", "Loock", "Klemm", "Anton Kern", "Kicken", "Miles McEnery", "Galleria Continua",
    "Campoli Presti", "MASSIMODECARLO", "Nächst St. Stephan", "Sies + Höke", "Ruediger Schoettle",
    "Rüdiger Schöttle", "Produzentengalerie", "Jo van de Loo", "Guido Baudach",
]
for _cn, _ci in artists_data.items():
    _clow = _artist_text(_ci).lower()
    _art_galleries[_cn] = set(_gn for _gn in _CANON_GALLERIES if _gn.lower() in _clow)
    _art_movements[_cn] = set(lbl for lbl, kws in _MOVEMENTS if any(k in _clow for k in kws))
    _art_teachers[_cn] = _extract_teachers(_ci)

_artists_with_works = set(w["artist"] for w in collection)

_MANUAL_CONN_MAP = {}
for _mc in (data.get("connections") or []):
    _ma, _mb, _mt, _mn = _mc.get("a"), _mc.get("b"), _mc.get("type"), _mc.get("note", "")
    if _ma and _mb:
        _MANUAL_CONN_MAP.setdefault(_ma, []).append((_mb, _mt, _mn))
        _MANUAL_CONN_MAP.setdefault(_mb, []).append((_ma, _mt, _mn))

def derive_connections(name):
    conns = {"Lehrer–Schüler": set(), "Gleiche Schule / Bewegung": {}, "Gemeinsame Galerie": {}, "Gleicher Lehrer": {}}
    my_gal = _art_galleries.get(name, set())
    my_mov = _art_movements.get(name, set())
    my_teach = _art_teachers.get(name, set())
    for other in _artists_with_works:
        if other == name:
            continue
        sm = my_mov & _art_movements.get(other, set())
        if sm:
            conns["Gleiche Schule / Bewegung"][other] = ", ".join(sorted(sm))
        sg = my_gal & _art_galleries.get(other, set())
        if sg:
            conns["Gemeinsame Galerie"][other] = ", ".join(sorted(sg))
        st_ = my_teach & _art_teachers.get(other, set())
        if st_:
            conns["Gleicher Lehrer"][other] = ", ".join(sorted(st_))
    for t in my_teach:
        if t in _artists_with_works:
            conns["Lehrer–Schüler"].add((t, "Lehrer·in von " + name))
    for other in _artists_with_works:
        if name in _art_teachers.get(other, set()):
            conns["Lehrer–Schüler"].add((other, "Schüler·in"))
    conns["Paar"] = {}; conns["Kollaboration"] = {}; conns["Gemeinsame Ausstellung"] = {}
    _tm = {"Paar": "Paar", "Kollaboration": "Kollaboration", "Gruppenausstellung": "Gemeinsame Ausstellung"}
    for _o, _t, _note in _MANUAL_CONN_MAP.get(name, []):
        conns[_tm.get(_t, "Gemeinsame Ausstellung")][_o] = _note
    return conns


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
        r, m, p = rmtp.get("R",0), rmtp.get("M",0), rmtp.get("P",0)
        total = r + m + p
        parts.append(f'''<div class="rmtp-bar">
            <span class="rmtp-score-total">{total}/15</span>
            <span class="rmtp-pill rmtp-pill-r"><span class="rmtp-label">R</span> {r}</span>
            <span class="rmtp-pill rmtp-pill-m"><span class="rmtp-label">M</span> {m}</span>
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
        technique = work_technique(w)
        # Support multiple images per work (image_urls array)
        img_urls = w.get("image_urls", [])
        if not img_urls and w.get("image_url"):
            img_urls = [w["image_url"]]
        img_html = ""
        if img_urls:
            img_parts = []
            for iu in img_urls:
                onerror = "this.style.display='none'"
                img_parts.append(f'<a href="{iu}" target="_blank" rel="noopener" title="Größer anzeigen"><img src="{iu}" style="max-width: 260px; max-height: 200px; border: 1px solid #E8E5E0; border-radius: 2px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);cursor:zoom-in;" loading="lazy" onerror="{onerror}"></a>')
            img_html = f'<div style="margin: 0.5rem 0; display: flex; flex-wrap: wrap; gap: 8px;">{"".join(img_parts)}</div>'
        _dw = technique_value(w["work"]); _bval = artist_total(info) + _dw
        _meta_bits = []
        if w.get("blattgroesse"): _meta_bits.append(f'&#128208; {w["blattgroesse"]}')
        if w.get("drucker"): _meta_bits.append(f'&#128424; {w["drucker"]}')
        if w.get("image_unverified"):
            _meta_bits.append(f'<span style="color:#C4632B;font-weight:600;">&#9888; Sekundärmarkt{(" · " + w["image_note"]) if w.get("image_note") else ""} — bitte prüfen</span>')
        _meta_html = f'<div style="font-size:0.66rem;color:#8A8277;margin-top:3px;">{" &middot; ".join(_meta_bits)}</div>' if _meta_bits else ''
        parts.append(f'<div style="padding: 0.6rem 0; border-bottom: 1px solid #F5F4F0;">{img_html}<div style="display: flex; justify-content: space-between;"><div><span style="font-style: italic; color: #555; font-size: 0.85rem;">{w["work"]}</span> <span class="card-edition" style="margin-left: 8px;">{w["edition"]}</span> <span style="font-size: 0.65rem; color: #aaa; margin-left: 6px;">{technique}</span>{_meta_html}</div><div style="text-align: right; white-space: nowrap;"><span class="card-date">{w["date"]}</span><div style="font-size:0.6rem;color:#B98;">Druckwert {_dw}/5 · Blatt {_bval}/20</div></div></div></div>')
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
    score_str = f" ({total}/15)" if total > 0 else ""
    liga_str = f" · {liga}" if liga else ""
    return f"{bc}{artist_name}{liga_str}{score_str}"


# ─── Render work cards in columns ───
def render_work_cards(works, card_key_prefix="card"):
    card_cols = st.columns(2)
    for j, w in enumerate(works):
        liga_class = get_liga_class(w["liga"])
        bc_dot = "● " if w["isBlueChip"] else ""
        liga_badge = ""
        if w["liga"]:
            liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
        rmtp_badge = ""
        artist_info = artists_data.get(w["artist"], {})
        rmtp = artist_info.get("rmtp", {})
        if rmtp:
            total = rmtp.get("total", 0)
            color = "#C44B3F" if total >= 15 else "#6B7DB3" if total >= 12 else "#999"
            rmtp_badge = f'<span style="float:right;font-size:0.75rem;font-weight:700;color:{color};">{total}/15</span>'
        with card_cols[j % 2]:
            st.markdown(f'<div class="work-card liga-border-{liga_class}"><div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
            if st.button(f"{bc_dot}{w['artist']}", key=f"{card_key_prefix}_{j}", use_container_width=True):
                st.session_state.selected_artist = w["artist"]
                st.rerun()


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
elif view == "spitze":
    view_filtered = [w for w in filtered if w.get("isSpitze")]
    view_label = "Spitze"
elif view == "bluechip":
    view_filtered = [w for w in filtered if w["isBlueChip"]]
    view_label = "Blue Chip"
elif view == "meisterschueler":
    view_filtered = [w for w in filtered if is_meisterschueler(w["artist"])]
    view_label = "Meisterschüler"
elif view == "druckwerkstaetten":
    view_filtered = filtered
    view_label = "Druckwerkstätten"
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
        function doScroll() {
            // Alle Ebenen durchgehen: eigenes Fenster, parent, top
            var targets = [window];
            try { targets.push(window.parent); } catch(e) {}
            try { if (window.top !== window.parent) targets.push(window.top); } catch(e) {}

            for (var t = 0; t < targets.length; t++) {
                try {
                    var w = targets[t];
                    w.scrollTo({top: 0, left: 0, behavior: 'instant'});
                    var d = w.document;
                    if (d) {
                        d.documentElement.scrollTop = 0;
                        d.body.scrollTop = 0;
                        // Streamlit-Container
                        var sels = ['section.main', '[data-testid="stAppViewContainer"]',
                                    '[data-testid="stMainBlockContainer"]', '.main', '.block-container'];
                        for (var i = 0; i < sels.length; i++) {
                            var el = d.querySelector(sels[i]);
                            if (el) { el.scrollTop = 0; el.scrollTo && el.scrollTo(0,0); }
                        }
                    }
                } catch(e) {}
            }
        }
        // Mehrfach feuern: sofort + verzögert (DOM rendert asynchron)
        doScroll();
        setTimeout(doScroll, 50);
        setTimeout(doScroll, 200);
        setTimeout(doScroll, 500);
        setTimeout(doScroll, 1000);

        // Browser-History: Zurück-Button/Swipe am Handy
        try {
            var top = window.top || window.parent;
            if (!top._trueffelHistorySet) {
                top.history.pushState({view: 'detail'}, '', '');
                top.addEventListener('popstate', function(e) {
                    try {
                        var btns = top.document.querySelectorAll('button');
                        for (var i = 0; i < btns.length; i++) {
                            if (btns[i].textContent.indexOf('Zurück') !== -1) {
                                btns[i].click();
                                break;
                            }
                        }
                    } catch(e) {}
                });
                top._trueffelHistorySet = true;
            }
        } catch(e) {}
    </script>
    """, height=0)
    if st.button("← Zurück zur Galerie", key="btn_back", use_container_width=True):
        st.session_state.selected_artist = None
        st.rerun()
    show_artist_detail(selected)
    # ── Querverbindungen ──
    _conns = derive_connections(selected)
    _dict_cats = [
        ("💞 Paar", "Paar"),
        ("🤝 Kollaboration", "Kollaboration"),
        ("🖼️ Gemeinsame Ausstellung", "Gemeinsame Ausstellung"),
        ("🎭 Gleiche Schule / Bewegung", "Gleiche Schule / Bewegung"),
        ("🏛️ Gemeinsame Galerie", "Gemeinsame Galerie"),
        ("🎓 Gleicher Lehrer", "Gleicher Lehrer"),
    ]
    _any = bool(_conns["Lehrer–Schüler"]) or any(_conns.get(_k) for _, _k in _dict_cats)
    if _any:
        st.markdown('<div style="font-family:Cormorant Garamond,serif;font-size:1.1rem;color:#1B3A2A;font-weight:700;margin:1.2rem 0 0.3rem;">Querverbindungen</div><div style="font-size:0.72rem;color:#998E7D;margin-bottom:0.5rem;">recherchierte (Paar · Kollaboration · Ausstellung) und aus den Daten abgeleitete (Schule · Galerie · Lehrer) Verbindungen — klickbar</div>', unsafe_allow_html=True)
        for _other, _role in sorted(_conns["Lehrer–Schüler"]):
            if st.button(f"🎓 {_role}: {_other}", key=f"conn_ls_{_other}", use_container_width=True):
                st.session_state.selected_artist = _other; st.rerun()
        for _title, _key in _dict_cats:
            _items = sorted(_conns.get(_key, {}).items())
            if _items:
                st.markdown(f'<div style="font-size:0.72rem;color:#888;margin:0.6rem 0 0.15rem;font-weight:600;">{_title}</div>', unsafe_allow_html=True)
                for _other, _reason in _items[:12]:
                    if st.button(f"{_other}  ·  {_reason}", key=f"conn_{_key}_{_other}", use_container_width=True):
                        st.session_state.selected_artist = _other; st.rerun()
                if len(_items) > 12:
                    st.markdown(f'<div style="font-size:0.68rem;color:#bbb;margin-bottom:0.2rem;">… und {len(_items)-12} weitere</div>', unsafe_allow_html=True)
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
        bc_dot = "● " if w["isBlueChip"] else ""
        liga_badge = ""
        if w["liga"]:
            liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
        technique = work_technique(w)
        img_url = w.get("image_url", "")
        img_html = ""
        if img_url:
            img_html = f'<div style="margin:0.4rem 0;"><a href="{img_url}" target="_blank" rel="noopener" title="Größer anzeigen"><img src="{img_url}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;cursor:zoom-in;" loading="lazy" onerror="this.style.display=\'none\'"></a></div>'
        with card_cols[j % 3]:
            _binfo = artists_data.get(w["artist"], {}); _dw = technique_value(w["work"])
            _bval = _binfo.get("rmtp",{}).get("total",0) + _dw
            _blatt_html = f'<div style="font-size:0.6rem;color:#B98;margin-top:3px;">Druckwert {_dw}/5 · Blatt {_bval}/20</div>' if _binfo.get("rmtp") else ""
            if st.button(f"{bc_dot}{w['artist']}", key=f"werke_artist_{j}", use_container_width=True):
                st.session_state.selected_artist = w["artist"]
                st.rerun()
            st.markdown(f'<div class="work-card liga-border-{liga_class}" style="margin-top:-0.3rem;">{img_html}<div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span><span style="font-size: 0.65rem; color: #aaa; margin-left: 6px;">{technique}</span></div><div><span class="card-date">{w["date"]}</span></div></div>{_blatt_html}</div>', unsafe_allow_html=True)
elif view == "techniken":
    # ── Techniken-Ansicht: Kacheln → Klick → Werke ──
    from collections import defaultdict
    tech_groups = defaultdict(list)
    for w in view_filtered:
        tech = work_technique(w)
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
            bc_dot = "● " if w["isBlueChip"] else ""
            liga_badge = ""
            if w["liga"]:
                liga_badge = f'<span class="liga-badge liga-badge-{liga_class}">{w["liga"]}</span>'
            img_url = w.get("image_url", "")
            img_html = ""
            if img_url:
                img_html = f'<div style="margin:0.4rem 0;"><a href="{img_url}" target="_blank" rel="noopener" title="Größer anzeigen"><img src="{img_url}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;cursor:zoom-in;" loading="lazy" onerror="this.style.display=\'none\'"></a></div>'
            with card_cols[j % 3]:
                st.markdown(f'<div class="work-card liga-border-{liga_class}">{img_html}<div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
                if st.button(f"{bc_dot}{w['artist']}", key=f"tech_artist_{j}", use_container_width=True):
                    st.session_state.selected_artist = w["artist"]
                    st.rerun()
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
elif view == "extern":
    st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem; letter-spacing: 0.03em;">{len(EXTERNAL_WORKS)} Werk(e) — Sammlung außerhalb der Hamburger Griffelkunst</div>', unsafe_allow_html=True)
    ext_cols = st.columns(3)
    for j, w in enumerate(EXTERNAL_WORKS):
        img_html = ""
        if w.get("image_url"):
            img_html = f'<div style="margin:0.4rem 0;"><a href="{w["image_url"]}" target="_blank" rel="noopener" title="Größer anzeigen"><img src="{w["image_url"]}" style="width:100%;max-height:240px;object-fit:contain;border-radius:2px;background:#F8F7F4;cursor:zoom-in;" loading="lazy"></a></div>'
        meta = []
        if w.get("technique"): meta.append(w["technique"])
        if w.get("edition"): meta.append("Auflage " + w["edition"])
        if w.get("size"): meta.append(w["size"])
        meta_line = " · ".join(meta)
        foot = []
        if w.get("gallery"): foot.append(w["gallery"])
        if w.get("price"): foot.append(w["price"])
        foot_line = " · ".join(foot)
        year_str = (" (" + w["year"] + ")") if w.get("year") else ""
        _info = artists_data.get(w["artist"], {})
        _liga = _info.get("liga", "")
        _total = _info.get("rmtp", {}).get("total", 0)
        _dw = technique_value(w.get("technique","") or w.get("work",""))
        _bval = _total + _dw
        if _liga or _total:
            _lc = get_liga_class(_liga)
            _lb = f'<span class="liga-badge liga-badge-{_lc}">{_liga}</span>' if _liga else ""
            _sc = f'<span style="font-family:Cormorant Garamond,serif;font-weight:700;font-size:0.8rem;color:#1B3A2A;margin-left:6px;">Blatt {_bval}/20</span>' if _total else ""
            score_html = f'<div style="margin:6px 0 2px;">{_lb}{_sc}<div style="font-size:0.6rem;color:#B98;margin-top:1px;">Künstler {_total}/15 · Druckwert {_dw}/5</div></div>'
        else:
            score_html = '<div style="font-size:0.65rem;color:#bbb;margin:6px 0 2px;font-style:italic;">noch nicht bewertet</div>'
        with ext_cols[j % 3]:
            st.markdown(
                f'<div class="work-card">{img_html}'
                f'<div class="card-work" style="font-style:italic;">„{w["work"]}“{year_str}</div>'
                f'<div style="font-weight:600;color:#1B3A2A;margin:2px 0;">{w["artist"]}</div>'
                f'{score_html}'
                f'<div style="font-size:0.7rem;color:#888;margin-top:2px;">{meta_line}</div>'
                f'<div style="font-size:0.68rem;color:#aaa;margin-top:4px;">{foot_line}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
elif view == "druckwerkstaetten":
    _sel = st.session_state.get("selected_werkstatt")
    if _sel and _sel in _werkstatt_groups:
        _ws_works = _werkstatt_groups[_sel]
        if st.button("← Zurück zu den Werkstätten", key="btn_back_ws"):
            st.session_state.selected_werkstatt = None; st.rerun()
        st.markdown(f'<div style="font-family: Cormorant Garamond, Georgia, serif; font-size: 1.4rem; color: #1B3A2A; margin-bottom: 0.3rem;">{_sel}</div>', unsafe_allow_html=True)
        _ptech = Counter(((w.get("technik") or "").split("(")[0].strip()) for w in _ws_works if w.get("technik"))
        _pt = ", ".join(t for t, _ in _ptech.most_common(2) if t)
        _pa = sorted(set(w["artist"] for w in _ws_works))
        _pnote = WERKSTATT_NOTE.get(_sel, "")
        _pfact = (f"Schwerpunkt {_pt}. " if _pt else "") + f"In der Sammlung mit {len(_ws_works)} {'Blatt' if len(_ws_works)==1 else 'Blättern'} von {', '.join(_pa)}."
        _profile = ((_pnote + " ") if _pnote else "") + _pfact
        st.markdown(f'<div style="font-size:0.82rem;color:#6B6255;line-height:1.6;margin-bottom:1rem;padding:0.7rem 1rem;background:#F5F3EE;border-left:3px solid #B8964E;border-radius:0 3px 3px 0;">{_profile}</div>', unsafe_allow_html=True)
        _wc = st.columns(3)
        for j, w in enumerate(_ws_works):
            lc = get_liga_class(w["liga"]); dot = "● " if w["isBlueChip"] else ""
            iu = w.get("image_url", "")
            ih = f'<div style="margin:0.4rem 0;"><img src="{iu}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;" loading="lazy" onerror="this.style.display=&quot;none&quot;"></div>' if iu else ""
            with _wc[j % 3]:
                if st.button(f"{dot}{w['artist']}", key=f"ws_artist_{j}", use_container_width=True):
                    st.session_state.selected_artist = w["artist"]; st.rerun()
                st.markdown(f'<div class="work-card liga-border-{lc}" style="margin-top:-0.3rem;">{ih}<div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
    else:
        _ws_sorted = sorted(_werkstatt_groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        _n_bl = sum(len(v) for v in _werkstatt_groups.values())
        st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 0.6rem; letter-spacing: 0.03em;">{len(_ws_sorted)} Druckwerkstätten · {_n_bl} zugeordnete Blätter</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.75rem;color:#6B6255;background:#F5F3EE;border-left:3px solid #B8964E;padding:0.6rem 0.9rem;border-radius:0 3px 3px 0;margin-bottom:1rem;line-height:1.5;">Druckgraphik lebt vom Handwerk der Werkstätten. Hier die Ateliers und Drucker·innen, welche die Blätter der Sammlung realisiert haben — nach Anzahl geordnet.</div>', unsafe_allow_html=True)
        _wcols = st.columns(3)
        for idx, (ws, wks) in enumerate(_ws_sorted):
            with _wcols[idx % 3]:
                _s = ""
                for tw in wks:
                    if tw.get("image_url"): _s = tw["image_url"]; break
                if _s:
                    st.markdown(f'<div style="width:100%;height:110px;overflow:hidden;border-radius:3px 3px 0 0;background:#F5F3EE;border:1px solid #E8E5E0;border-bottom:none;"><img src="{_s}" style="width:100%;height:110px;object-fit:contain;padding:4px;" loading="lazy" onerror="this.parentElement.style.display=&quot;none&quot;"></div>', unsafe_allow_html=True)
                if st.button(f"{ws} ({len(wks)})", key=f"ws_{idx}", use_container_width=True):
                    st.session_state.selected_werkstatt = ws; st.rerun()
elif view == "blatttyp":
    from collections import defaultdict
    _bt_groups = defaultdict(list)
    for w in view_filtered:
        _bt_groups[blatt_typ(w["edition"], w["work"])].append(w)
    _bt_order = ["Wahlblatt", "Projektblatt", "Einzelblatt", "Mappe", "Sonderedition"]
    _selbt = st.session_state.get("selected_blatttyp")
    if _selbt and _selbt in _bt_groups:
        _bt_works = _bt_groups[_selbt]
        if st.button("← Zurück zu Blatt-Typen", key="btn_back_bt"):
            st.session_state.selected_blatttyp = None; st.rerun()
        st.markdown(f'<div style="font-family: Cormorant Garamond, Georgia, serif; font-size: 1.4rem; color: #1B3A2A; margin-bottom: 0.3rem;">{_selbt}</div>', unsafe_allow_html=True)
        _d = BLATTTYP_INFO.get(_selbt, "")
        if _d:
            st.markdown(f'<div style="font-size: 0.82rem; color: #6B6255; line-height: 1.6; margin-bottom: 0.8rem; padding: 0.7rem 1rem; background: #F5F3EE; border-left: 3px solid #B8964E; border-radius: 0 3px 3px 0;">{_d}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem;">{len(_bt_works)} Werke</div>', unsafe_allow_html=True)
        _bc = st.columns(3)
        for j, w in enumerate(_bt_works):
            lc = get_liga_class(w["liga"]); dot = "● " if w["isBlueChip"] else ""
            iu = w.get("image_url", "")
            ih = f'<div style="margin:0.4rem 0;"><img src="{iu}" style="width:100%;max-height:160px;object-fit:contain;border-radius:2px;background:#F8F7F4;" loading="lazy" onerror="this.style.display=\'none\'"></div>' if iu else ""
            with _bc[j % 3]:
                st.markdown(f'<div class="work-card liga-border-{lc}">{ih}<div class="card-work">{w["work"]}</div><div class="card-details"><div><span class="card-edition">{w["edition"]}</span><span style="font-size:0.65rem;color:#aaa;margin-left:6px;">{work_technique(w)}</span></div><div><span class="card-date">{w["date"]}</span></div></div></div>', unsafe_allow_html=True)
                if st.button(f"{dot}{w['artist']}", key=f"bt_artist_{j}", use_container_width=True):
                    st.session_state.selected_artist = w["artist"]; st.rerun()
    else:
        st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 0.6rem; letter-spacing: 0.03em;">Blatt-Typen · {len(view_filtered)} Werke</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.75rem;color:#6B6255;background:#F5F3EE;border-left:3px solid #B8964E;padding:0.6rem 0.9rem;border-radius:0 3px 3px 0;margin-bottom:1rem;line-height:1.5;">Alle Blätter sind <b>originale Druckgraphik</b>, vom Künstler handsigniert (Griffelkunst-Blätter sind signiert, aber <b>nicht</b> nummeriert). Unterschieden wird nach Herkunft im Griffelkunst-Programm:</div>', unsafe_allow_html=True)
        _present = [(t, _bt_groups[t]) for t in _bt_order if t in _bt_groups]
        _cols = st.columns(len(_present) if _present else 1)
        for idx, (t, ws) in enumerate(_present):
            with _cols[idx]:
                _s = ""
                for tw in ws:
                    if tw.get("image_url"): _s = tw["image_url"]; break
                if _s:
                    st.markdown(f'<div style="width:100%;height:120px;overflow:hidden;border-radius:3px 3px 0 0;background:#F5F3EE;border:1px solid #E8E5E0;border-bottom:none;"><img src="{_s}" style="width:100%;height:120px;object-fit:contain;padding:4px;" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></div>', unsafe_allow_html=True)
                if st.button(f"{t} ({len(ws)})", key=f"bt_{t}", use_container_width=True):
                    st.session_state.selected_blatttyp = t; st.rerun()
else:
    # ── Künstler·innen-Galerie: Portrait-Tiles im Grid ──
    filter_hint = f" — {view_label}" if view_label else ""
    _ranked = view in ("spitze", "liga1", "liga2", "liga3", "bluechip", "meisterschueler")
    _sort_hint = "nach Rang · Reputation ×2 · beste zuerst" if _ranked else "alphabetisch nach Nachname"
    st.markdown(f'<div style="font-size: 0.8rem; color: #8A8A8A; margin-bottom: 1rem; letter-spacing: 0.03em;">{len(artist_groups)} Künstler·innen · {len(view_filtered)} Werke{filter_hint} — {_sort_hint}</div>', unsafe_allow_html=True)

    # Render grid — Streamlit columns with portrait tiles
    # 4 Spalten: bricht auf Mobile sauber auf 2×2 um (kein leeres Feld)
    COLS_PER_ROW = 4
    artist_list = list(artist_groups.items())
    if _ranked:
        artist_list.sort(key=lambda kv: rang_sortkey(artists_data.get(kv[0], {})), reverse=True)
    for row_start in range(0, len(artist_list), COLS_PER_ROW):
        row_items = artist_list[row_start:row_start + COLS_PER_ROW]
        # Nur so viele Spalten wie Einträge → keine leeren Spalten am Ende
        cols = st.columns(len(row_items))
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
            score_html = f'<span style="font-family:Cormorant Garamond,serif;font-weight:700;font-size:0.8rem;color:#1B3A2A;">{total}/15</span>' if total > 0 else ""
            works_label = "Werk" if len(works) == 1 else "Werke"

            # Portrait für Tile; Fallback: erstes Werkbild des Künstlers
            img_src = info.get("portrait_url", "")
            _workimg = ""
            for _w in works:
                if _w.get("image_url"):
                    _workimg = _w["image_url"]; break
            if not img_src:
                img_src = _workimg
            _fb = _workimg if (_workimg and _workimg != img_src) else ""

            with cols[idx]:
                # ── Portrait-Bild (oben) ──
                initial = artist_name[0] if artist_name else "?"
                _click_js = 'onclick="var el=this.closest(&#x27;[data-testid=stColumn]&#x27;);if(el){var btn=el.querySelector(&#x27;button&#x27;);if(btn)btn.click();}"'
                if img_src:
                    onerror_attr = 'if(this.dataset.fb&&this.src!=this.dataset.fb){this.src=this.dataset.fb;}else{this.style.display=&quot;none&quot;;this.nextElementSibling.style.display=&quot;flex&quot;;}'
                    _fb_attr = f' data-fb=&quot;{_fb}&quot;' if _fb else ''
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:4/3;overflow:hidden;border-radius:3px 3px 0 0;background:#EDEAE5;position:relative;cursor:pointer;" {_click_js}>'
                        f'<img src="{img_src}"{_fb_attr} style="width:100%;height:100%;object-fit:contain;pointer-events:none;" loading="lazy" onerror="{onerror_attr}">'
                        f'<div style="display:none;width:100%;height:100%;align-items:center;justify-content:center;position:absolute;top:0;left:0;background:#EDEAE5;color:#C0B8A8;font-size:2.5rem;font-family:Cormorant Garamond,Georgia,serif;">{initial}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="width:100%;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;background:#EDEAE5;color:#C0B8A8;font-size:2.5rem;font-family:Cormorant Garamond,Georgia,serif;border-radius:3px 3px 0 0;cursor:pointer;" {_click_js}>{initial}</div>',
                        unsafe_allow_html=True
                    )
                # ── Name as clickable button ──
                if st.button(f"{bc_dot}{artist_name}", key=f"tile_{artist_name}", use_container_width=True):
                    st.session_state.selected_artist = artist_name
                    st.rerun()
                # ── Meisterschüler·in von … (nur in der Meisterschüler-Ansicht) ──
                if view == "meisterschueler":
                    _tset = _art_teachers.get(artist_name, set())
                    if _tset:
                        _tlabel = " · ".join(sorted(_tset))
                        st.markdown(
                            f'<div style="font-size:0.66rem;color:#6B7DB3;font-style:italic;'
                            f'margin:-0.15rem 0 0.35rem;padding:0 2px;line-height:1.3;">'
                            f'Meisterschüler·in von {_tlabel}</div>',
                            unsafe_allow_html=True
                        )
                # ── Meta line: Liga + Score | Werke ──
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin:-0.3rem 0 1rem;padding:0 2px;">'
                    f'<div>{liga_badge_html} {score_html}</div>'
                    f'<div style="font-size:0.68rem;color:#aaa;">{len(works)} {works_label}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ─── Footer ───
st.markdown("---")
APP_BUILD = "2026-08-07h"
st.markdown(f'<div style="text-align: center; padding: 1rem 0 2rem; color: #B8964E; font-size: 0.75rem; letter-spacing: 0.08em; font-family: Cormorant Garamond, Georgia, serif;">Trüffelkunst · Sammlung Bodman<br><span style="font-size:0.62rem;color:#cfae7a;letter-spacing:0.04em;">Build {APP_BUILD}</span></div>', unsafe_allow_html=True)
