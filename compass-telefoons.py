#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Compass telefoonexport: alle telefoons van een Compass-company met status naar CSV.

GEBRUIK
=======
Vereist: uv (https://docs.astral.sh/uv/). Installeren:
  curl -LsSf https://astral.sh/uv/install.sh | sh

Draaien:
  export COMPASS_API_USERNAME='jouw-compass-gebruikersnaam'
  export COMPASS_API_PASSWORD='jouw-compass-wachtwoord'
  uv run compass-telefoons.py                    # schrijft compass-telefoons.csv
  uv run compass-telefoons.py speakup-tel.csv    # eigen bestandsnaam
  # of: chmod +x compass-telefoons.py && ./compass-telefoons.py

Let op: `uvx` is voor tools uit een package; een los script draai je met `uv run`.
Zonder uv werkt ook gewoon: python3 compass-telefoons.py (Python >= 3.9).

- De company is automatisch die van het account waarmee je inlogt.
- Duur: ongeveer 1 minuut voor ~220 telefoons (3 calls per telefoon, 8 tegelijk).
- Uitvoer: CSV met ; als scheidingsteken en UTF-8 BOM, opent direct in Nederlandse Excel.
- Zet het wachtwoord liever niet in je shell-history: gebruik bv. `read -s COMPASS_API_PASSWORD; export COMPASS_API_PASSWORD`.

KOLOMMEN
========
  naam, id, model, mac           basisgegevens van de telefoon
  eigenaar                        het bedrijf of de gebruiker die eigenaar is
  ingelogd                        gebruiker die nu op dit toestel is ingelogd
  online, versleuteld             of het toestel nu geregistreerd is, en of dat via TLS/SRTP gaat
  publiek_ip, prive_ip            adres waarvandaan het toestel registreert
  user_agent                      app of firmware (bv. Mobile-On-PBX, snom715/10.1.x)
  sip_gebruiker                   SIP-gebruiker van de actieve registratie
  registratie_verloopt            wanneer de huidige registratie verloopt (lokale tijd)
  sip_accounts                    SIP-accounts als gebruiker@domein (ZONDER wachtwoord)
  mogelijkheden                   call control die via de API kan (answer, hold, unhold)

GEBRUIKTE API'S
===============
Compass REST API v3, basis-URL https://rest.pbx.speakup-telecom.com
Documentatie: https://rest.pbx.speakup-telecom.com/schema/#/  (OpenAPI: /api-docs/v3)

Authenticatie: HTTP Basic met je Compass-gebruikersnaam en wachtwoord (OIDC kan ook, niet gebruikt).
Verplichte header: Accept: application/vnd.iperity.compass.v3+json
  (met application/json krijg je 406 Not Acceptable)

  GET /user                         303-redirect naar /user/{id} van de ingelogde gebruiker
                                    (er is geen /user/me)
  GET /user/{id}/company            303-redirect naar /company/{companyId}
  GET /company/{id}                 bedrijfsgegevens (naam)
  GET /company/{id}/phones          lijst van alle telefoons (resourceId, name, model, macAddress, owner)
  GET /company/{id}/users           gebruikers, incl. loggedInPhoneIds (wie waar is ingelogd)
  GET /phoneModel/{id}              naam van het model (bv. D715, SIP Softphone)
  GET /phone/{id}/phoneStatus       online, encrypted, publicIP, privateIP, userAgent, user, expires
  GET /phone/{id}/sipAccounts       SIP-accounts (username, domain, secret)
  GET /phone/{id}/capabilities      mogelijke call-control-acties
  Eén telefoon los opvragen kan met GET /phone/{id} (operationId get_4 in de docs).

BEVEILIGING
===========
/phone/{id}/sipAccounts geeft het SIP-wachtwoord (secret) in leesbare tekst terug.
Dit script schrijft dat veld bewust NIET weg. Deel de CSV dus gerust, maar deel je
API-inloggegevens niet: daarmee kan iemand wel de SIP-wachtwoorden opvragen.

FOUTMELDINGEN
=============
  "Zet eerst COMPASS_API_USERNAME en COMPASS_API_PASSWORD"  omgevingsvariabelen ontbreken
  "Inloggen mislukt (401)"                                  verkeerde gebruikersnaam of wachtwoord
  Lege kolommen bij een telefoon                            die call faalde of gaf geen data (geen rechten)
"""
import base64, csv, datetime, json, os, sys, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://rest.pbx.speakup-telecom.com"
ACCEPT = "application/vnd.iperity.compass.v3+json"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def auth_header():
    user, pw = os.environ.get("COMPASS_API_USERNAME"), os.environ.get("COMPASS_API_PASSWORD")
    if not user or not pw:
        sys.exit("Zet eerst COMPASS_API_USERNAME en COMPASS_API_PASSWORD.")
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


AUTH = auth_header()


def request(path, follow=True):
    req = urllib.request.Request(BASE + path, headers={"Authorization": AUTH, "Accept": ACCEPT})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    return opener.open(req, timeout=30)


def get(path):
    try:
        with request(path) as r:
            return json.load(r)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def redirect_id(path):
    """GET /user en /user/{id}/company antwoorden met 303 naar /<type>/<id>."""
    try:
        request(path, follow=False)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303) and e.headers.get("Location"):
            return int(e.headers["Location"].rstrip("/").rsplit("/", 1)[1])
        if e.code == 401:
            sys.exit("Inloggen mislukt (401): controleer gebruikersnaam en wachtwoord.")
        raise
    sys.exit(f"Geen redirect op {path}")


def fmt_expires(value):
    if not value:
        return ""
    seconds = value / 1000 if value > 1e11 else value
    return datetime.datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "compass-telefoons.csv"
    user_id = redirect_id("/user")
    company_id = redirect_id(f"/user/{user_id}/company")
    company = get(f"/company/{company_id}") or {}
    phones = get(f"/company/{company_id}/phones") or []
    users = get(f"/company/{company_id}/users") or []
    print(f"{company.get('name', company_id)}: {len(phones)} telefoons, {len(users)} gebruikers")

    user_names = {u["entityId"]: u["name"] for u in users}
    logged_in = {pid: u["name"] for u in users for pid in (u.get("loggedInPhoneIds") or [])}
    models = {m: (get(m.replace(BASE, "")) or {}).get("name", m.rsplit("/", 1)[1])
              for m in {p["model"] for p in phones if p.get("model")}}

    def row(p):
        pid = p["resourceId"]
        status = get(f"/phone/{pid}/phoneStatus") or {}
        accounts = get(f"/phone/{pid}/sipAccounts") or []
        caps = get(f"/phone/{pid}/capabilities") or []
        owner = p.get("owner")
        return {
            "naam": p.get("name", ""),
            "id": pid,
            "model": models.get(p.get("model"), ""),
            "mac": ":".join(f"{b:02X}" for b in p.get("macAddress") or []),
            "eigenaar": f"{company.get('name', 'bedrijf')} (bedrijf)" if owner == company_id else user_names.get(owner, owner),
            "ingelogd": logged_in.get(pid, p.get("loggedInUser") or ""),
            "online": "ja" if status.get("online") else "nee",
            "versleuteld": "ja" if status.get("encrypted") else "nee",
            "publiek_ip": status.get("publicIP", ""),
            "prive_ip": status.get("privateIP", ""),
            "user_agent": status.get("userAgent", ""),
            "sip_gebruiker": status.get("user", ""),
            "registratie_verloopt": fmt_expires(status.get("expires")),
            "sip_accounts": " ".join(f"{a['username']}@{a['domain']}" for a in accounts),
            "mogelijkheden": ", ".join(c["value"] for c in caps),
        }

    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(row, phones))
    rows.sort(key=lambda r: (r["online"] != "ja", str(r["naam"]).lower()))

    # utf-8-sig + ; zodat Excel (NL) het direct goed opent
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["naam"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{sum(r['online'] == 'ja' for r in rows)} online. Geschreven naar {out}")


if __name__ == "__main__":
    main()
