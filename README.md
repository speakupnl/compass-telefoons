# Compass telefoonexport

Alle telefoons van een Compass-company met status naar CSV.

## Gebruik

Vereist: [uv](https://docs.astral.sh/uv/). Installeren:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Draaien:

```bash
export COMPASS_API_USERNAME='jouw-compass-gebruikersnaam'
export COMPASS_API_PASSWORD='jouw-compass-wachtwoord'
uv run compass-telefoons.py                    # schrijft compass-telefoons.csv
uv run compass-telefoons.py speakup-tel.csv    # eigen bestandsnaam
# of: chmod +x compass-telefoons.py && ./compass-telefoons.py
```

Let op: `uvx` is voor tools uit een package; een los script draai je met `uv run`.
Zonder uv werkt ook gewoon: `python3 compass-telefoons.py` (Python >= 3.9).

- De company is automatisch die van het account waarmee je inlogt.
- Duur: ongeveer 1 minuut voor ~220 telefoons (3 calls per telefoon, 8 tegelijk).
- Uitvoer: CSV met ; als scheidingsteken en UTF-8 BOM, opent direct in Nederlandse Excel.
- Zet het wachtwoord liever niet in je shell-history: gebruik bv. `read -s COMPASS_API_PASSWORD; export COMPASS_API_PASSWORD`.

## Kolommen

```text
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
```

## Gebruikte API's

```text
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
```

## Beveiliging

/phone/{id}/sipAccounts geeft het SIP-wachtwoord (secret) in leesbare tekst terug.
Dit script schrijft dat veld bewust NIET weg. Deel de CSV dus gerust, maar deel je
API-inloggegevens niet: daarmee kan iemand wel de SIP-wachtwoorden opvragen.

## Foutmeldingen

```text
"Zet eerst COMPASS_API_USERNAME en COMPASS_API_PASSWORD"  omgevingsvariabelen ontbreken
"Inloggen mislukt (401)"                                  verkeerde gebruikersnaam of wachtwoord
Lege kolommen bij een telefoon                            die call faalde of gaf geen data (geen rechten)
```
