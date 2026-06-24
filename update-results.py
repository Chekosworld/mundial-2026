#!/usr/bin/env python3
"""
Auto-update de resultados del Mundial 2026 para el dashboard de Aitopia.

Fuente: TheSportsDB (API gratis, sin key/registro) — liga 4429 = FIFA World Cup 2026.
Lee el JSON existente, jala los partidos terminados de una ventana de días,
los acumula (merge por equipo+fecha) y reescribe mundial-resultados.json.

El dashboard hace merge por (a, b, fecha-MX) sobre sus datos embebidos, así que
los nombres de equipo van en ESPAÑOL exactos y la fecha en hora del centro de México.

Sin dependencias externas (solo stdlib) → corre tal cual en GitHub Actions.

Env:
  BACKFILL=1    → jala desde el inicio del torneo (2026-06-11) hasta hoy.
  WINDOW_DAYS=N → ventana hacia atrás desde hoy (default 4). Ignorado si BACKFILL=1.
"""
import json, os, sys, urllib.request, datetime

API = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={d}&s=Soccer"
LEAGUE_ID = "4429"          # FIFA World Cup 2026 (verificado vía lookupleague)
TOURNAMENT_START = datetime.date(2026, 6, 11)
MX_OFFSET = datetime.timedelta(hours=-6)   # CDMX = UTC-6 fijo (sin horario de verano)
FINISHED = {"FT", "AET", "PEN", "Match Finished"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mundial-resultados.json")

# TheSportsDB (EN) -> nombres EXACTOS que usa el dashboard (ES). Incluye alias.
ES = {
    "Algeria": "Argelia", "Argentina": "Argentina", "Australia": "Australia",
    "Austria": "Austria", "Belgium": "Bélgica", "Bosnia and Herzegovina": "Bosnia",
    "Bosnia-Herzegovina": "Bosnia", "Bosnia": "Bosnia", "Brazil": "Brasil",
    "Canada": "Canadá", "Cape Verde": "Cabo Verde", "Cabo Verde": "Cabo Verde",
    "Colombia": "Colombia", "Croatia": "Croacia", "Curaçao": "Curazao",
    "Curacao": "Curazao", "Czech Republic": "Rep. Checa", "Czechia": "Rep. Checa",
    "DR Congo": "RD Congo", "Congo DR": "RD Congo", "Ecuador": "Ecuador",
    "Egypt": "Egipto", "England": "Inglaterra", "France": "Francia",
    "Germany": "Alemania", "Ghana": "Ghana", "Haiti": "Haití", "Iran": "Irán",
    "IR Iran": "Irán", "Ivory Coast": "Costa de Marfil", "Cote d'Ivoire": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil", "Japan": "Japón", "Jordan": "Jordania",
    "Mexico": "México", "Morocco": "Marruecos", "Netherlands": "Países Bajos",
    "New Zealand": "Nueva Zelanda", "Norway": "Noruega", "Panama": "Panamá",
    "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Qatar",
    "Saudi Arabia": "Arabia Saudita", "Scotland": "Escocia", "Senegal": "Senegal",
    "South Africa": "Sudáfrica", "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur", "Spain": "España", "Switzerland": "Suiza",
    "Tunisia": "Túnez", "Turkey": "Turquía", "Türkiye": "Turquía",
    "USA": "Estados Unidos", "United States": "Estados Unidos", "Uruguay": "Uruguay",
    "Uzbekistan": "Uzbekistán",
}

def tr(name):
    if name in ES:
        return ES[name]
    print(f"  [WARN] equipo sin mapeo ES: {name!r} (se usa tal cual)", file=sys.stderr)
    return name

def mx_date(ev):
    ts = ev.get("strTimestamp")
    try:
        if ts:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", ""))  # UTC naive
            d = (dt + MX_OFFSET).date()
            return [d.year, d.month, d.day]
    except Exception:
        pass
    de = ev.get("dateEvent")  # fallback: fecha tal cual
    y, m, dd = (int(x) for x in de.split("-"))
    return [y, m, dd]

def fetch_day(d):
    try:
        with urllib.request.urlopen(API.format(d=d.isoformat()), timeout=25) as r:
            data = json.load(r)
        return [e for e in (data.get("events") or []) if e.get("idLeague") == LEAGUE_ID]
    except Exception as ex:
        print(f"  [WARN] fetch {d} falló: {ex}", file=sys.stderr)
        return []

def main():
    today = (datetime.datetime.now(datetime.timezone.utc) + MX_OFFSET).date()
    if os.environ.get("BACKFILL") == "1":
        start = TOURNAMENT_START
    else:
        start = today - datetime.timedelta(days=int(os.environ.get("WINDOW_DAYS", "4")))
    start = max(start, TOURNAMENT_START)

    # JSON existente -> dict acumulado por (a,b,fecha)
    acc = {}
    if os.path.exists(OUT):
        try:
            cur = json.load(open(OUT, encoding="utf-8"))
            for mt in cur.get("matches", []):
                acc[(mt["a"], mt["b"], tuple(mt["d"]))] = mt
        except Exception as ex:
            print(f"[WARN] no pude leer {OUT}: {ex}", file=sys.stderr)

    added = 0
    day = start
    while day <= today:
        for ev in fetch_day(day):
            st = (ev.get("strStatus") or "").strip()
            hs, as_ = ev.get("intHomeScore"), ev.get("intAwayScore")
            if st not in FINISHED or hs is None or as_ is None:
                continue
            a, b = tr(ev.get("strHomeTeam")), tr(ev.get("strAwayTeam"))
            d = mx_date(ev)
            key = (a, b, tuple(d))
            mt = {"d": d, "a": a, "b": b, "s": f"{hs}-{as_}"}
            if acc.get(key) != mt:
                acc[key] = mt
                added += 1
        day += datetime.timedelta(days=1)

    matches = sorted(acc.values(), key=lambda m: (m["d"], m["a"]))
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "matches": matches}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"OK · {len(matches)} partidos en JSON · {added} nuevos/cambiados (ventana {start}..{today})")

if __name__ == "__main__":
    main()
