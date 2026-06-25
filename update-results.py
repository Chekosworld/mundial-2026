#!/usr/bin/env python3
"""
Auto-update de resultados del Mundial 2026 para el dashboard de Aitopia.

Fuente: football-data.org (free tier "Tier One") — competition WC = FIFA World Cup 2026.
Cobertura completa (104 partidos). 1 request por corrida (límite free 10/min).

Lee TODOS los partidos, filtra los terminados, mapea nombres a ESPAÑOL exactos
(los que usa el dashboard) y fecha en hora del centro de México, y reescribe
mundial-resultados.json. El dashboard hace merge por (a, b, fecha-MX).

Sin dependencias externas (solo stdlib) → corre tal cual en GitHub Actions.

Env:
  FOOTBALL_DATA_TOKEN  (requerido) — token de football-data.org.
"""
import json, os, sys, urllib.request, datetime

URL = "https://api.football-data.org/v4/competitions/WC/matches"
MX_OFFSET = datetime.timedelta(hours=-6)   # CDMX = UTC-6 fijo (sin horario de verano)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mundial-resultados.json")

# football-data.org (EN) -> nombres EXACTOS que usa el dashboard (ES).
ES = {
    "Algeria": "Argelia", "Argentina": "Argentina", "Australia": "Australia",
    "Austria": "Austria", "Belgium": "Bélgica", "Bosnia-Herzegovina": "Bosnia",
    "Brazil": "Brasil", "Canada": "Canadá", "Cape Verde Islands": "Cabo Verde",
    "Cape Verde": "Cabo Verde", "Colombia": "Colombia", "Congo DR": "RD Congo",
    "DR Congo": "RD Congo", "Croatia": "Croacia", "Curaçao": "Curazao",
    "Czechia": "Rep. Checa", "Czech Republic": "Rep. Checa", "Ecuador": "Ecuador",
    "Egypt": "Egipto", "England": "Inglaterra", "France": "Francia",
    "Germany": "Alemania", "Ghana": "Ghana", "Haiti": "Haití", "Iran": "Irán",
    "Iraq": "Irak", "Ivory Coast": "Costa de Marfil", "Japan": "Japón",
    "Jordan": "Jordania", "Mexico": "México", "Morocco": "Marruecos",
    "Netherlands": "Países Bajos", "New Zealand": "Nueva Zelanda", "Norway": "Noruega",
    "Panama": "Panamá", "Paraguay": "Paraguay", "Portugal": "Portugal",
    "Qatar": "Qatar", "Saudi Arabia": "Arabia Saudita", "Scotland": "Escocia",
    "Senegal": "Senegal", "South Africa": "Sudáfrica", "South Korea": "Corea del Sur",
    "Spain": "España", "Sweden": "Suecia", "Switzerland": "Suiza", "Tunisia": "Túnez",
    "Turkey": "Turquía", "United States": "Estados Unidos", "Uruguay": "Uruguay",
    "Uzbekistan": "Uzbekistán",
}

def tr(name):
    if name in ES:
        return ES[name]
    print(f"  [WARN] equipo sin mapeo ES: {name!r} (se usa tal cual)", file=sys.stderr)
    return name

def mx_date(utc_iso):
    dt = datetime.datetime.fromisoformat(utc_iso.replace("Z", ""))  # UTC naive
    d = (dt + MX_OFFSET).date()
    return [d.year, d.month, d.day]

def main():
    today = (datetime.datetime.now(datetime.timezone.utc) + MX_OFFSET).date()
    if today >= datetime.date(2026, 7, 20):   # día después de la final → auto-apagado
        print("Mundial terminado; sin actualización.")
        return

    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        print("[ERROR] falta FOOTBALL_DATA_TOKEN", file=sys.stderr)
        sys.exit(1)

    req = urllib.request.Request(URL, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errorCode" in data:
        print(f"[ERROR] API: {data.get('message')}", file=sys.stderr)
        sys.exit(1)

    matches = []
    for fx in data.get("matches", []):
        if fx.get("status") != "FINISHED":
            continue
        ft = (fx.get("score") or {}).get("fullTime") or {}
        h, a = ft.get("home"), ft.get("away")
        if h is None or a is None:
            continue
        matches.append({
            "d": mx_date(fx["utcDate"]),
            "a": tr(fx.get("homeTeam", {}).get("name")),
            "b": tr(fx.get("awayTeam", {}).get("name")),
            "s": f"{h}-{a}",
        })
    matches.sort(key=lambda m: (m["d"], m["a"]))

    out = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "matches": matches}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"OK · {len(matches)} partidos terminados en JSON (de {len(data.get('matches', []))} totales)")

if __name__ == "__main__":
    main()
