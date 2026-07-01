#!/usr/bin/env python3
"""
Auto-update de resultados del Mundial 2026 para el dashboard de Aitopia.

Fuente: football-data.org (free tier "Tier One") — competition WC = FIFA World Cup 2026.
Cobertura completa (104 partidos). 1 request por corrida (límite free 10/min).

Emite dos bloques:
  - "matches": partidos de FASE DE GRUPOS terminados → {d, a, b, s}. El dashboard
    los mergea por (a, b, fecha-MX) sobre su fixture embebido para pintar marcadores.
  - "bracket": TODOS los partidos de eliminatoria (LAST_32 .. FINAL), jugados o no →
    {stage, d, x, a, b, s, st}. La API rellena los equipos conforme avanzan las rondas
    (source of truth de matchups Y progresión); el dashboard arma el árbol con esto.
    a/b pueden ser null (cruce aún por definir); s null si no ha terminado.

Nombres mapeados a ESPAÑOL exactos (los que usa el dashboard) y fecha/hora en hora
del centro de México (UTC-6 fijo). Sin dependencias externas (solo stdlib) → corre
tal cual en GitHub Actions.

Env:
  FOOTBALL_DATA_TOKEN  (requerido) — token de football-data.org.
"""
import json, os, sys, urllib.request, datetime

URL = "https://api.football-data.org/v4/competitions/WC/matches"
MX_OFFSET = datetime.timedelta(hours=-6)   # CDMX = UTC-6 fijo (sin horario de verano)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mundial-resultados.json")

# Rondas de eliminatoria en orden (stage de football-data → etiqueta ES corta).
KO_STAGES = ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "THIRD_PLACE", "FINAL"]

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
    if not name:
        return None
    if name in ES:
        return ES[name]
    print(f"  [WARN] equipo sin mapeo ES: {name!r} (se usa tal cual)", file=sys.stderr)
    return name

def mx_dt(utc_iso):
    dt = datetime.datetime.fromisoformat(utc_iso.replace("Z", "")) + MX_OFFSET  # UTC naive → CDMX
    return [dt.year, dt.month, dt.day], dt.strftime("%H:%M")

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

    matches, bracket = [], []
    for fx in data.get("matches", []):
        stage = fx.get("stage")
        sc = fx.get("score") or {}
        ft = sc.get("fullTime") or {}
        h, a = ft.get("home"), ft.get("away")
        score = f"{h}-{a}" if (h is not None and a is not None) else None
        ha = tr(fx.get("homeTeam", {}).get("name"))
        aa = tr(fx.get("awayTeam", {}).get("name"))

        if stage == "GROUP_STAGE":
            if fx.get("status") != "FINISHED" or score is None:
                continue
            d, _ = mx_dt(fx["utcDate"])
            matches.append({"d": d, "a": ha, "b": aa, "s": score})
        elif stage in KO_STAGES:
            d, x = mx_dt(fx["utcDate"])
            # ganador autoritativo de la API (los empates en eliminatoria se van a penales)
            win = sc.get("winner")
            w = "a" if win == "HOME_TEAM" else "b" if win == "AWAY_TEAM" else None
            pen = sc.get("penalties") or {}
            ph, pa = pen.get("home"), pen.get("away")
            pens = f"{ph}-{pa}" if (ph is not None and pa is not None) else None
            bracket.append({"stage": stage, "d": d, "x": x, "a": ha, "b": aa,
                            "s": score, "w": w, "p": pens, "st": fx.get("status")})

    matches.sort(key=lambda m: (m["d"], m["a"]))
    bracket.sort(key=lambda m: (KO_STAGES.index(m["stage"]), m["d"], m["x"]))

    out = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "matches": matches, "bracket": bracket}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    done = sum(1 for m in bracket if m["s"])
    print(f"OK · {len(matches)} de grupos terminados + {len(bracket)} de eliminatoria "
          f"({done} jugados) en JSON (de {len(data.get('matches', []))} totales)")

if __name__ == "__main__":
    main()
