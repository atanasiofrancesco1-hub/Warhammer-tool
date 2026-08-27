#!/usr/bin/env python3
"""
WH40K 11th Edition Scraper for GitHub Actions
==============================================
Scarica TUTTI i datasheet da Wahapedia.ru e genera data.json
con units, rules, compendium e tooltips.

Ottimizzato per girare su GitHub Actions:
- Nessuna cache su disco (parte sempre da zero)
- Output diretto a data.json
- Non genera HTML (index.html è separato e statico)
- User-Agent realistico per evitare blocchi

USO:
  python scraper_ga.py
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERRORE: Installa le dipendenze con:")
    print("  pip install requests beautifulsoup4 lxml")
    sys.exit(1)

# ============================================================
# CONFIGURAZIONE
# ============================================================

BASE_URL = "https://wahapedia.ru/wh40k11ed/factions"
CORE_RULES_URL = "https://wahapedia.ru/wh40k11ed/the-rules/core-rules/"

FACTIONS = [
    ("space-marines",        "Space Marines"),
    ("chaos-space-marines",  "Chaos Space Marines"),
    ("astra-militarum",      "Astra Militarum"),
    ("aeldari",              "Aeldari"),
    ("drukhari",             "Drukhari"),
    ("necrons",              "Necrons"),
    ("t-au-empire",          "T'au Empire"),
    ("tyranids",             "Tyranids"),
    ("orks",                 "Orks"),
    ("death-guard",          "Death Guard"),
    ("thousand-sons",        "Thousand Sons"),
    ("world-eaters",         "World Eaters"),
    ("emperor-s-children",   "Emperor's Children"),
    ("chaos-daemons",        "Chaos Daemons"),
    ("adeptus-mechanicus",   "Adeptus Mechanicus"),
    ("adepta-sororitas",     "Adepta Sororitas"),
    ("adeptus-custodes",     "Adeptus Custodes"),
    ("imperial-knights",     "Imperial Knights"),
    ("chaos-knights",        "Chaos Knights"),
    ("leagues-of-votann",    "Leagues of Votann"),
    ("genestealer-cults",    "Genestealer Cults"),
    ("imperial-agents",      "Imperial Agents"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DELAY = 0.1
OUTPUT_FILE = "data.json"

# ============================================================
# TOOLTIPS incorporati (keyword definitions)
# ============================================================
TOOLTIPS = {
    "ASSAULT": "If a unit that Advanced this turn contains models equipped with Assault weapons, it is still eligible to shoot.",
    "HEAVY": "Add 1 to the hit roll if the attacking unit Remained Stationary this turn.",
    "BLAST": "Add one additional attack die for every 5 models in the target unit (rounding down).",
    "TORRENT": "Each time an attack is made with a Torrent weapon, that attack automatically hits the target.",
    "MELTA": "If the target is within half range, add X to the weapon's Damage characteristic.",
    "HAZARDOUS": "After resolving attacks, make a hazard roll for each Hazardous weapon used. On a 1, the attacking unit suffers mortal wounds.",
    "IGNORES COVER": "The target cannot have the benefit of cover against this attack, including from Stealth.",
    "LETHAL HITS": "On a critical hit (unmodified 6), you can choose to automatically wound the target — no wound roll needed.",
    "DEVASTATING WOUNDS": "On a critical wound (unmodified 6), the attack inflicts mortal wounds equal to the weapon's Damage instead of normal damage.",
    "SUSTAINED HITS": "On a critical hit, score X additional hits on the target.",
    "RAPID FIRE": "Add X to the Attack characteristic when targeting a unit within half range.",
    "TWIN-LINKED": "You can re-roll Hit rolls of 1 (and Wound rolls of 1 for melee).",
    "PISTOL": "Can be fired even while the unit is engaged in melee, but only Pistol weapons can be used.",
    "PRECISION": "The controlling player can allocate attacks to a CHARACTER model in the target unit instead of the closest model.",
    "ANTI": "Wound rolls of Y+ against units with the X keyword are critical wounds.",
    "ONE SHOT": "Can only be used once per battle.",
    "EXTRA ATTACKS": "Adds bonus attacks without requiring the model to select a non-Extra Attacks weapon.",
    "INDIRECT FIRE": "Can target units not visible to the attacking model, but worsens BS by 1 and the target gains cover.",
    "FEEL NO PAIN": "Each time a model would lose a wound, roll one D6: on X+, that wound is not lost.",
    "STEALTH": "If every model in a unit has this ability, the unit has the benefit of cover against ranged attacks.",
    "DEADLY DEMISE": "When a model with this ability is destroyed, roll one D6. On a 6, each unit within 6\" suffers mortal wounds.",
    "FIRING DECK": "When this TRANSPORT shoots, roll dice equal to the number of embarked units' weapons and use those profiles.",
    "LONE OPERATIVE": "Unless part of an attached unit, cannot be targeted unless within 12\" (or X\"). Immune to Indirect Fire.",
    "DEEP STRIKE": "Can be set up in Reinforcements. When arriving, set up more than 9\" from enemy models.",
    "SCOUT": "Can make a move of up to X\" before the first battle round begins.",
    "INFILTRATORS": "Can be set up anywhere on the battlefield more than 9\" from enemy models, instead of in your deployment zone.",
    "FIGHTS FIRST": "This unit fights at the start of the Fight phase, before units without this ability.",
    "LEADER": "Can be attached to a bodyguard unit during Muster Armies, forming an attached unit.",
    "SUPPORT": "Can be attached to a bodyguard unit alongside a Leader, providing additional abilities.",
    "SCOUTS": "Can make a Scout move of up to X\" before the first battle round begins.",
    "OBJECTIVE SECURED": "Controls an objective marker even if outnumbered, as long as within range.",
    "TRANSPORT": "Can carry other units. Capacity and restrictions vary by model.",
    "FLY": "Can move over other models and terrain as if they were not there.",
    "TITANIC": "Models with this keyword use special movement and visibility rules due to their size.",
    "BATTLELINE": "Counts towards Battleline requirements in matched play.",
    "CHARACTER": "Can be targeted by Precision attacks. Can lead bodyguard units.",
    "PSYKER": "Can use psychic abilities.",
}

# ============================================================
# COMPENDIUM — regole sintetiche in italiano
# ============================================================
COMPENDIUM = [
    {"title": "Il Battle Round", "body": "Le partite si svolgono in una serie di Battle Round. Ogni Battle Round e' composto da un turno per ciascun giocatore. Nel proprio turno, un giocatore esegue le fasi nell'ordine: Command, Movement, Shooting, Charge, Fight."},
    {"title": "Fase di Comando (Command Phase)", "body": "All'inizio di questa fase, entrambi i giocatori ottengono 1 Core CP. Poi ogni giocatore esegue i Battle-shock test per le unita' sotto Starting Strength."},
    {"title": "Fase di Movimento (Movement Phase)", "body": "Muovi ogni unita' fino alla sua caratteristica di Movimento (M). Le unita' possono anche Advance (muovere +D6 ma non sparare/chargeare) o Remain Stationary."},
    {"title": "Fase di Tiro (Shooting Phase)", "body": "Seleziona un'unita' visibile e in portata; ognuna delle sue armi da tiro puo' sparare. Sequenza: 1) Hit roll (1D6 vs BS), 2) Wound roll (S vs T), 3) Save roll (modificato da AP), 4) Damage."},
    {"title": "Fase di Carica (Charge Phase)", "body": "Seleziona un'unita' non ingaggiata, dichiara un'unita' nemica visibile come bersaglio. Tira 2D6: se il risultato >= distanza in pollici, l'unita' si muove in engagement."},
    {"title": "Fase di Combattimento (Fight Phase)", "body": "Si combatte in mischia. Prima combattono le unita' con Fights First, poi quelle con Fights Last, poi tutte le altre. Sequenza: pile-in, melee attacks, consolidate."},
    {"title": "Datasheet - Profili", "body": "Ogni unita' ha un datasheet con: Move (M), Toughness (T), Save (SV), Wounds (W), Leadership (LD), Objective Control (OC)."},
    {"title": "Datasheet - Abilita'", "body": "Le unita' hanno abilities proprie e di fazione. Le CORE abilities comuni includono: Leader, Support, Deep Strike, Scout, Infiltrators, Fights First, Lone Operative."},
    {"title": "Datasheet - Keywords", "body": "Le keywords sono etichette che identificano il tipo di unita'. Faction keywords (es. ADEPTUS ASTARTES) non contano per regole di fazione nemiche. Altre keywords (es. INFANTRY, CHARACTER) determinano interazioni con regole."},
    {"title": "Coerenza delle Unita'", "body": "Una unita' con piu' di un modello deve mantenere coerenza: ogni modello deve essere entro 2\" di almeno un altro modello della stessa unita'."},
    {"title": "Engagement Range", "body": "Un modello e' in Engagement Range di un'unita' nemica se e' entro 1\" orizzontalmente e 5\" verticalmente. Le unita' in Engagement Range non possono sparare (tranne Pistols)."},
    {"title": "Hit Roll e Critical Hit", "body": "Tira 1D6 per ogni attacco. Un risultato >= BS/WS e' un hit. Un 6 non modificato e' un Critical Hit (puo' attivare abilities come Lethal Hits)."},
    {"title": "Wound Roll e Critical Wound", "body": "Tira 1D6 e confronta S dell'arma con T del bersaglio. Un 6 non modificato e' un Critical Wound (sempre un wound, puo' attivare Devastating Wounds)."},
    {"title": "Save Roll", "body": "Il bersaglio tira 1D6 per ogni ferita. Risultato >= Save = ferita bloccata. AP dell'arma modifica il save (es. AP -1 riduce il save di 1)."},
    {"title": "Mortal Wounds", "body": "Le Mortal Wounds bypassano i save roll. Vengono inflitte una alla volta. Possono essere assegnate a qualsiasi modello della unita' bersaglio."},
    {"title": "Hazard Rolls", "body": "Dopo aver risolto gli attacchi con armi [HAZARDOUS], tira un D6 per ogni arma hazardous usata. Su un 1, l'unita' che ha sparato subisce mortal wounds."},
    {"title": "Battle-shock", "body": "In Command Phase, per ogni unita' sotto Starting Strength, tira 2D6 e confronta con Leadership (es. sotto il 50% della forza). Se fallito, l'unita' e' Battle-shocked: non puo' controllare obiettivi e usa Stratagemmi solo con CP extra."},
    {"title": "Stratagemmi", "body": "I Stratagemmi sono abilita' speciali che costano Command Points (CP). Ogni giocatore ottiene 1 Core CP per turno. Alcuni Stratagemmi costano piu' CP."},
    {"title": "Terreno - Categorie", "body": "Il terreno si divide in: Exposed (nessun beneficio), Light (cover se parzialmente nascosto), Dense (blocks visibility), Solid (blocks movement), Obstacles (barricades, walls)."},
    {"title": "Terreno - Benefit of Cover", "body": "Un'unita' ha benefit of cover contro un attacco a distanza se ogni modello e': interamente entro un'area di terreno con cover, o parzialmente nascosto da terreno tra il tiratore e il bersaglio."},
    {"title": "Obiettivi", "body": "Gli obiettivi sono marker sul tavolo. Un'unita' controlla un obiettivo se ha piu' modelli entro 3\" del marker rispetto all'avversario. OC (Objective Control) determina il valore di controllo."},
    {"title": "Mostri e Veicoli", "body": "I Mostri e Veicoli usano regole speciali di movimento: possono muovere attraverso terrain non-Solid e ignorano Coerenza. Possono sparare anche in mischia (con armi non-Pistol)."},
    {"title": "Trasporti", "body": "I modelli con keyword TRANSPORT possono trasportare altre unita'. Embarking: un'unita' entro 3\" puo' imbarcarsi nel turno di movimento. Disembarking: puo' sbarcare nel turno successivo entro 3\"."},
    {"title": "Unita' Attaccate (Attached Units)", "body": "Un Leader puo' essere attaccato a un'unita' bodyguard durante Muster Armies. L'unita' combinata conta come una singola unita' per coerenza, morale e obiettivi."},
    {"title": "Riserve Strategiche", "body": "Le unita' possono essere messe in Riserve Strategiche (costa CP). Arrivano dalla Movement Phase del secondo Battle Round. Non possono arrivare nel deployment zone nemico."},
    {"title": "Flying e Surge", "body": "I modelli con FLY possono muovere sopra altri modelli e terrain. Surge Move: alcuni modelli possono muovere una distanza aggiuntiva nel Charge phase."},
    {"title": "Aircraft", "body": "Gli Aircraft hanno regole speciali: devono muoversi di almeno 20\" per turno, non possono stare fermi, e escono dal tavolo se raggiungono il bordo."},
    {"title": "Muster Armies", "body": "Per creare un'armata: 1) Seleziona Army Faction, 2) Seleziona Battle Size (Incursione 1000pt, Strike Force 2000pt, Onslaught 3000pt), 3) Aggiungi unita' fino al limite punti."},
    {"title": "Core Abilities", "body": "Le Core Abilities sono regole comuni a molte unita'. Includono: [EXTRA ATTACKS], Lone Operative, [ONE SHOT], [FEEL NO PAIN], [DEADLY DEMISE], [DEEP STRIKE], [SCOUT]."},
    {"title": "Modificatori alle Caratteristiche", "body": "Le caratteristiche (BS, WS, S, T, AP, D) possono essere modificate da regole. Un modificatore non puo' mai superare +/-1 tranne dove specificato. Mai modificare il risultato di un dice."},
    {"title": "Aura Abilities", "body": "Le Aura abilities sono abilities che si applicano a unita' amiche entro una certa distanza del portatore. Un'unita' puo' beneficiare di ogni tipo di aura una sola volta."},
    {"title": "Faction Abilities", "body": "Ogni fazione ha abilities proprie (es. Oath of Moment per i Space Marines, Reanimation Protocols per i Necrons). Queste sono descritte nel codex o online."},
    {"title": "Wargear Abilities", "body": "Le Wargear Abilities sono abilities associate a equipaggiamenti specifici (Enhancements). Sono indicate nel datasheet o nel codex della fazione."},
    {"title": "Plunging Fire", "body": "I modelli posizionati in alto (su terrain elevato) possono fare Plunging Fire: se sparano a un'unita' piu' in basso, le loro armi guadagnano [LETHAL HITS] per quel attacco."},
    {"title": "Psychic Abilities", "body": "I Psyker possono usare psychic abilities. Witchfire abilities infliggono danni. Hazardous test obbligatorio per ogni psychic ability usata."},
    {"title": "Actions", "body": "Alcune missioni richiedono di compiere Actions. Un'unita' puo' compiere un'Action se e' within range di un obiettivo. Un'unita' che compie un'Action non puo' muovere, sparare o chargeare."},
    {"title": "Duplicated Abilities", "body": "Se un'unita' ha la stessa ability da piu' fonti, si usa solo una volta. I numeri non si sommano: si applica il valore piu' alto."},
]

# ============================================================
# FUNZIONI DI RETE
# ============================================================

def split_weapon_keywords(name):
    """Separa il nome dell'arma dalle sue keyword (es. 'Gauss blaster lethal hits' -> 'Gauss blaster', ['LETHAL HITS'])."""
    remaining = name
    found_keywords = []

    kw_patterns = [
        r'\banti-(?:infantry|mounted|monster|vehicle|psyker|fly)\s+\d+\+',
        r'\bsustained hits\s+\d+',
        r'\brapid fire\s+\d+',
        r'\bmelta\s+\d+',
        r'\blethal hits\b',
        r'\bdevastating wounds\b',
        r'\bignores cover\b',
        r'\bindirect fire\b',
        r'\bextra attacks\b',
        r'\bone shot\b',
        r'\btwin-linked\b',
        r'\bassault\b',
        r'\bheavy\b',
        r'\bblast\b',
        r'\bpistol\b',
        r'\btorrent\b',
        r'\bhazardous\b',
        r'\bprecision\b',
        r'\bbarrage\b',
        r'\blance\b',
    ]

    for pattern in kw_patterns:
        matches = list(re.finditer(pattern, remaining, re.IGNORECASE))
        if matches:
            for m in matches:
                kw = m.group(0).strip()
                found_keywords.append(kw.upper())
            remaining = re.sub(pattern, '', remaining, flags=re.IGNORECASE)

    # Pulisci spazi multipli e virgole
    remaining = re.sub(r'\s+', ' ', remaining).strip().rstrip(',;').strip()
    # Rimuovi duplicati dalle keyword
    seen = set()
    unique_kw = []
    for k in found_keywords:
        if k not in seen:
            seen.add(k)
            unique_kw.append(k)

    return remaining, unique_kw


def fetch_url(url):
    """Scarica una URL senza cache (sempre fresca su GitHub Actions)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        time.sleep(DELAY)
        return r.text
    except Exception as e:
        print(f"  ERRORE download {url}: {e}")
        return None

# ============================================================
# SCRAPING: LISTA DATASHEETS PER FAZIONE
# ============================================================

def get_faction_datasheets(faction_slug, faction_name):
    """Estrae la lista dei datasheet URL dalla pagina principale della fazione."""
    url = f"{BASE_URL}/{faction_slug}/"
    print(f"\n-> Analisi fazione: {faction_name}")
    html = fetch_url(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")

    datasheet_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        pattern = r"/wh40k11ed/factions/" + re.escape(faction_slug) + r"/([A-Za-z0-9_\-]+)"
        m = re.search(pattern, href)
        if m:
            unit_slug = m.group(1)
            skip = {"units", "stratagems", "enhancements", "army-rules",
                    "crusade-rules", "detachments"}
            if unit_slug.lower() in skip:
                continue
            full_url = f"{BASE_URL}/{faction_slug}/{unit_slug}"
            datasheet_urls.add((unit_slug, full_url))

    datasheet_urls = sorted(datasheet_urls, key=lambda x: x[0])
    print(f"  Trovati {len(datasheet_urls)} datasheet")
    return datasheet_urls

# ============================================================
# PARSING DATASHEET
# ============================================================

def parse_datasheet(html_text, faction_name):
    """Parserizza una pagina datasheet di Wahapedia 11th ed."""
    soup = BeautifulSoup(html_text, "lxml")

    unit = {
        "name": "",
        "faction": faction_name,
        "stats": {},
        "ranged": [],
        "melee": [],
        "abilities": [],
        "keywords": [],
        "faction_keywords": [],
        "composition": "",
        "wargear": "",
        "points": {},
        "base": "",
        "image_search": "",
        "faction_logo": "",
    }

    # === NOME UNITA' ===
    h1 = soup.find("h1")
    if h1:
        title_text = h1.get_text(strip=True)
        parts = re.split(r"\s*[\u2013\-]\s*", title_text, maxsplit=1)
        if len(parts) > 1:
            unit["name"] = parts[-1].strip()
        else:
            unit["name"] = parts[0].strip()

    if not unit["name"]:
        title_tag = soup.find("title")
        if title_tag:
            t = title_tag.get_text(strip=True)
            parts = re.split(r"\s*[\u2013\-]\s*", t, maxsplit=1)
            unit["name"] = parts[-1].strip() if parts else t

    # === DIAMETRO BASE ===
    base_match = re.search(r"\u230c(\d+mm)", html_text)
    if base_match:
        unit["base"] = base_match.group(1)

    # === IMAGE SEARCH ===
    if unit["name"]:
        import urllib.parse
        unit["image_search"] = "https://www.google.com/search?tbm=isch&q=" + urllib.parse.quote("Warhammer 40k " + unit["name"] + " 11th edition")

    # === FACTION LOGO ===
    logo = soup.find("img", class_="factionLogo")
    if logo and logo.get("src"):
        unit["faction_logo"] = logo["src"]

    # === STATISTICHE ===
    char_wraps = soup.find_all("div", class_="dsCharWrap")
    for cw in char_wraps:
        name_div = cw.find("div", class_="dsCharName")
        value_div = cw.find("div", class_="dsCharValue")
        if name_div and value_div:
            label = name_div.get_text(strip=True)
            value = value_div.get_text(strip=True)
            if label and value:
                unit["stats"][label] = value

    # === TABELLE ARMI ===
    wtables = soup.find_all("table", class_="wTable")
    current_section = None

    for wt in wtables:
        rows = wt.find_all("tr")
        for row in rows:
            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            if not cells:
                continue

            row_text = " ".join(cells).upper()
            if "RANGED WEAPONS" in row_text:
                current_section = "ranged"
                continue
            elif "MELEE WEAPONS" in row_text:
                current_section = "melee"
                continue

            if len(cells) >= 8 and cells[1]:
                if any(cells[i] for i in range(2, 8)):
                    raw_name = cells[1]
                    clean_name, weapon_kw = split_weapon_keywords(raw_name)
                    weapon = {
                        "name": clean_name,
                        "keywords": weapon_kw,
                        "range": cells[2] if len(cells) > 2 else "",
                        "A": cells[3] if len(cells) > 3 else "",
                        "skill": cells[4] if len(cells) > 4 else "",
                        "S": cells[5] if len(cells) > 5 else "",
                        "AP": cells[6] if len(cells) > 6 else "",
                        "D": cells[7] if len(cells) > 7 else "",
                    }
                    if current_section == "ranged":
                        unit["ranged"].append(weapon)
                    elif current_section == "melee":
                        unit["melee"].append(weapon)

    # === ABILITIES ===
    for div in soup.find_all("div", class_="dsAbility"):
        # Salta dsAbility_noLine (stratagemmi)
        classes = div.get("class", [])
        if "dsAbility_noLine" in classes:
            continue
        # Salta se contiene una tabella (prezzi/costi)
        if div.find("table"):
            continue

        text = div.get_text(" ", strip=True)
        if not text:
            continue

        # Pattern 1: "FACTION: AbilityName" o "CORE: AbilityName"
        if text.startswith("FACTION:") or text.startswith("CORE:") or text.startswith("UNIT:") or text.startswith("WARGEAR:"):
            parts = text.split(":", 1)
            ab_type = parts[0].strip()
            ab_name = parts[1].strip() if len(parts) > 1 else ""
            if ab_name:
                unit["abilities"].append({"name": ab_type, "desc": ab_name})
            continue

        # Pattern 2: "<b>Name:</b> Description"
        b_tag = div.find("b")
        if b_tag:
            b_text = b_tag.get_text(strip=True)
            # La descrizione è tutto il testo dopo il <b>
            full_text = div.get_text(" ", strip=True)
            # Rimuovi il nome del <b> dall'inizio
            if full_text.startswith(b_text):
                desc = full_text[len(b_text):].lstrip(":").strip()
            else:
                desc = full_text

            # Salta sezioni non-ability (composizione, costi, leader)
            skip_prefixes = ["Every model is equipped", "This unit can be led", "This unit can be supported",
                             "YOUR UNIT COSTS", "5-10", "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 ", "10 "]
            if any(b_text.startswith(p) for p in skip_prefixes):
                continue

            # Se il nome finisce con ":", puliscilo
            name = b_text.rstrip(":").strip()
            if name and desc:
                unit["abilities"].append({"name": name, "desc": desc})
            elif name and not desc:
                # Ability con solo nome (es. enhancement list)
                unit["abilities"].append({"name": name, "desc": ""})
            continue

        # Pattern 3: solo testo senza <b> (skiplink, leader, composition, enhancements)
        skip_text = ["This unit can be led", "This unit can be supported", "YOUR UNIT COSTS"]
        if any(text.startswith(s) for s in skip_text):
            continue

    # === KEYWORDS ===
    # Wahapedia usa caratteri cirillici nei nomi delle classi (dsLeftСolKW con С cirillica)
    # Cerchiamo per testo invece che per classe esatta
    left_col = None
    right_col = None
    for div in soup.find_all("div", class_=True):
        classes = " ".join(div.get("class", []))
        if "dsLeft" in classes and "KW" in classes:
            left_col = div
        elif "dsRight" in classes and "KW" in classes:
            right_col = div

    if left_col:
        text = left_col.get_text(" ", strip=True)
        # Rimuovi "KEYWORDS:" se presente
        text = re.sub(r'^KEYWORDS:\s*', '', text, flags=re.IGNORECASE)
        # Split su ; o ,
        kws = [k.strip() for k in re.split(r'[;,]', text) if k.strip()]
        unit["keywords"] = kws

    if right_col:
        text = right_col.get_text(" ", strip=True)
        text = re.sub(r'^FACTION\s*KEYWORDS:\s*', '', text, flags=re.IGNORECASE)
        kws = [k.strip() for k in re.split(r'[;,]', text) if k.strip()]
        unit["faction_keywords"] = kws

    # === PUNTI ===
    for pt in soup.find_all("span", class_="PriceTag"):
        pt_text = pt.get_text(strip=True)
        m = re.match(r"(\d+)\s*models?\s*:?\s*(\d+)", pt_text, re.I)
        if m:
            unit["points"][m.group(1) + " models"] = int(m.group(2))
        else:
            m2 = re.search(r"(\d+)", pt_text)
            if m2:
                unit["points"]["base"] = int(m2.group(1))

    # === COMPOSITION ===
    comp_div = soup.find("div", class_="dsComposition")
    if comp_div:
        unit["composition"] = comp_div.get_text(" ", strip=True)

    # === WARGEAR ===
    wg_div = soup.find("div", class_="dsWargear")
    if wg_div:
        unit["wargear"] = wg_div.get_text(" ", strip=True)

    return unit

# ============================================================
# SCRAPING: CORE RULES
# ============================================================

def scrape_core_rules():
    """Scarica le core rules dell'11th edition."""
    print("\n-> Scaricamento Core Rules...")
    html_text = fetch_url(CORE_RULES_URL)
    if not html_text:
        return []

    soup = BeautifulSoup(html_text, "lxml")

    rules = []
    current_title = None
    current_body = []

    for tag in soup.find_all(["h2", "h3", "p", "div"]):
        text = tag.get_text(strip=True)
        if not text:
            continue
        if tag.name in ("h2", "h3"):
            if current_title and current_body:
                rules.append({
                    "title": current_title,
                    "body": "\n".join(current_body)
                })
            current_title = text
            current_body = []
        elif current_title and len(text) > 30:
            current_body.append(text)

    if current_title and current_body:
        rules.append({
            "title": current_title,
            "body": "\n".join(current_body)
        })

    print(f"  Trovate {len(rules)} regole")
    return rules

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("WH40K 11th Edition Scraper (GitHub Actions)")
    print("Fonte: Wahapedia.ru")
    print("Output: data.json")
    print("=" * 60)

    all_units = []
    total_errors = 0

    # 1. Raccogli tutte le URL dei datasheet di tutte le fazioni
    all_datasheets = []
    for faction_slug, faction_name in FACTIONS:
        datasheets = get_faction_datasheets(faction_slug, faction_name)
        for unit_slug, unit_url in datasheets:
            all_datasheets.append((faction_slug, faction_name, unit_slug, unit_url))

    print(f"\nTotale datasheet da scaricare: {len(all_datasheets)}")

    # 2. Scarica e parserizza in parallelo (8 thread)
    def process_datasheet(item):
        faction_slug, faction_name, unit_slug, unit_url = item
        html_text = fetch_url(unit_url)
        if not html_text:
            return None, f"Download fallito: {unit_slug}"
        try:
            unit = parse_datasheet(html_text, faction_name)
            if unit["name"]:
                return unit, None
            else:
                return None, f"Nome non trovato: {unit_slug}"
        except Exception as e:
            return None, f"Errore parsing {unit_slug}: {e}"

    completed = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_datasheet, item): item for item in all_datasheets}
        for future in as_completed(futures):
            completed += 1
            unit, error = future.result()
            if unit:
                all_units.append(unit)
                if completed % 50 == 0:
                    print(f"  Progresso: {completed}/{len(all_datasheets)} ({len(all_units)} unità valide)")
            else:
                total_errors += 1
                if completed % 100 == 0:
                    print(f"  Progresso: {completed}/{len(all_datasheets)} (errori: {total_errors})")

    print(f"\nDownload completato: {len(all_units)} unità valide, {total_errors} errori")

    # 3. Scarica core rules
    core_rules = scrape_core_rules()
    if not core_rules:
        print("  ATTENZIONE: Core rules non scaricate")
        core_rules = []

    # 4. Genera data.json
    print("\n" + "=" * 60)
    print("Generazione data.json...")
    print(f"  Unita totali: {len(all_units)}")
    print(f"  Core rules: {len(core_rules)}")
    print(f"  Compendium: {len(COMPENDIUM)} voci")
    print(f"  Tooltips: {len(TOOLTIPS)} voci")
    print(f"  Errori: {total_errors}")

    data = {
        "units": all_units,
        "rules": core_rules,
        "compendium": COMPENDIUM,
        "tooltips": TOOLTIPS,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"\n  File generato: {OUTPUT_FILE}")
    print(f"  Dimensione: {file_size:,} byte")
    print(f"  Unita per fazione:")
    faction_names = sorted(set(u["faction"] for u in all_units))
    for f in faction_names:
        count = sum(1 for u in all_units if u["faction"] == f)
        print(f"    {f}: {count}")

    print("\n" + "=" * 60)
    print("COMPLETATO!")
    print("=" * 60)

    # Non uscire con errore anche se ci sono errori di parsing —
    # alcuni datasheet possono fallire ma il data.json è comunque valido


if __name__ == "__main__":
    main()
