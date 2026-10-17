# IQAlarm · Prüfstand vom 17. Oktober 2026

## Erfolgreich geprüft

- **108 pytest-Tests** für Korrelationslogik, Nachtbetrieb, eigene Profile, Konfigurationsgrenzen, Archivierung, Repository-Metadaten und Deployment-Rollback.
- Alle fünf geforderten Pflichtszenarien: MACO-Prellen, einzelnes Fenster, Fenster + Bewegung nach zwölf Sekunden, nächtlicher Toilettengang und Vorfeld + Fenster nach vierzig Sekunden.
- Zusätzliche Fälle: unabhängige Signalquellen, unpassende Kamera-Zuordnung, Nachbarräume, ausgeschaltete Regeln, veraltete Ereignisse, Debounce, Ausfälle/Wiederkehr, Scharf-/Eingangs-/Ausgangszeiten, Quarantänefreigabe und Neustart-Wiederherstellung.
- Eigene Profile: unverwechselbare Profil-ID bei gleichem HA-Modus, Raum-/Sensorfilter vor Scharfschaltprüfung und Korrelation, getrennte Timer, leere Auswahlen, Migration aus Version 1.0 sowie Wiederherstellung und Schutz vor Profilwechseln im scharfen Zustand.
- **96 % Zeilenabdeckung der eigenständigen Korrelations-Engine** durch die pytest-Suite. Diese Zahl beschreibt ausschließlich die Engine; die HA-Anbindung wird zusätzlich durch den realen Core-Prüfer geprüft.
- **Home Assistant 2025.12.5 und 2026.10.2**, jeweils im offiziellen Linux-Container: Config Flow, PIN-Hash, Einzelinstanz, Panel, native Entitäten, dynamische Räume, Dienste, persistenter Zustand und vollständiges Entladen/Neuladen.
- Echte authentifizierte HTTP-/WebSocket-Verbindungen: Status, Katalog, CRUD, Area-Import, Trockenlauf, Subscription und Rechtebegrenzung. Live-Abonnements überleben einen Integrations-Reload.
- Alle neun Aktionsarten gegen ausführbare Testdienste im echten HA-Service-Registry: Push, Sirene, Schalter, Skript, Licht, Rollos, Snapshot, Aufzeichnung und TTS.
- Kamerafehler unterdrücken den Text-Push nicht. Langsame Verdachts-Pushs blockieren den bestätigten Sirenenalarm nicht. Selbst übernommene Ausgänge werden bei Entschärfung oder Timerende abgeschaltet.
- Private Kameradateien, Kameraleserechte und PIN-Versuchslimit.
- **Vier Chromium-Browserprüfungen** gegen den echten Test-Core: CRUD über die deutsche Oberfläche, Profilwechsel/PIN, mobile Darstellung und Dark Theme, Formulare, Text-Escaping und sichtbarer Verbindungsverlust mit Schreibsperre.
- Python-Syntax, Ruff-Lint, Ruff-Format und JavaScript-Syntaxprüfung erfolgreich.
- ZIP-Reproduzierbarkeit, vollständiges ES-Modul im Archiv, Backup und Rollback des Installationsskripts geprüft.

Die Tests verwenden eigene Sensorzustände und ausführbare Testdienste im wegwerfbaren Core. Physische Sensoren, Kamera-Codecs, Companion-App-Zustellung und die tatsächliche Hausinstallation werden erst auf der Zielinstanz überprüft.

## Veröffentlichungsstatus

Das Zielrepository ist [marcohildebrandtmail-hub/IQAlarm](https://github.com/marcohildebrandtmail-hub/IQAlarm). Dokumentation, Issue-Tracker und Codeowner sind gebunden. **Der vollständige lokale hassfest-Lauf besteht mit null ungültigen Integrationen.** Ein zusätzlicher Regressionstest prüft die von hassfest verlangte Reihenfolge der Manifest-Schlüssel beim Binden einer Repository-URL.

Die GitHub-Workflows prüfen HACS, hassfest, Python, Browser und beide HA-Versionen. Der aktuelle Remote-Status ist unter [Actions](https://github.com/marcohildebrandtmail-hub/IQAlarm/actions) einsehbar. Eine Aufnahme in den öffentlichen Standardkatalog und ein Brand-Eintrag sind nicht vorgenommen worden.

Version 1.0 wurde auf der persönlichen Home-Assistant-Instanz über HACS installiert und nach Neustart im unscharfen Zustand geprüft. Der Prüfstand für spätere Updates ist über die jeweiligen GitHub-Actions-Läufe nachvollziehbar. Es werden keine Zugangsdaten im Repository gespeichert.

## Reproduzieren

Die ausführbaren Befehle stehen in README.md. Die Prüfer befinden sich in `tests/`, `scripts/verify_ha.py` und `tests/browser/`. Das Installationsarchiv und seine Prüfsummen entstehen mit `python scripts/package_release.py` unter `dist/`.
