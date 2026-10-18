# IQAlarm · Prüfstand vom 18. Oktober 2026

## Prüfumfang (Version 2.5.0)

- **260 pytest-Tests** für Korrelationslogik, Nachtbetrieb, eigene Profile, Konfigurationsgrenzen, Archivierung, Repository-Metadaten und Deployment-Rollback.
- Alle fünf geforderten Pflichtszenarien: MACO-Prellen, einzelnes Fenster, Fenster + Bewegung nach zwölf Sekunden, nächtlicher Toilettengang und Vorfeld + Fenster nach vierzig Sekunden.
- Neue Sicherheitsregressionen: gerichtete Bestätigungswege, unzugeordnete Kameras, reine Außenbewegung, Schlossentriegelung ohne Öffnung, höherer Alarm trotz gehaltener Stufe und abgelehnte unabhängige Räume. Mehrfachkontakt-/Bewegungsregeln verlangen ausdrückliche Freigabe und räumliche Beziehung.
- Echter Core: langsamer Lichtdienst blockiert keine andere Sirene; langsames Abschalten blockiert keinen Eingangstimer; eigene Alarm-Ausgänge werden nach Reload bis zum ursprünglichen Ablauf wieder aufgenommen.
- Browserregressionen für tatsächliche Importwerte, Abwahl einer Regel, Live-Sensortabelle, atomare Grundrisslöschung, bearbeitete Geometrie und Textkontakte im Fenster-Assistenten.
- Zusätzliche Fälle: unabhängige Signalquellen, unpassende Kamera-Zuordnung, Nachbarräume, ausgeschaltete Regeln, veraltete Ereignisse, Debounce, Ausfälle/Wiederkehr, Scharf-/Eingangs-/Ausgangszeiten, Quarantänefreigabe und Neustart-Wiederherstellung.
- Eigene Profile: unabhängige Profilregeln ohne HA-Modus-Zuordnung, Raum-/Sensorfilter vor Scharfschaltprüfung und Korrelation, getrennte Timer, leere Auswahlen, Migration aus Version 1.0 sowie Wiederherstellung und Schutz vor Profilwechseln im scharfen Zustand.
- **Home Assistant 2025.12.5 und 2026.10.2**, jeweils im offiziellen Linux-Container: Config Flow, PIN-Hash, Einzelinstanz, Panel, native Entitäten, dynamische Räume, Dienste, persistenter Zustand und vollständiges Entladen/Neuladen.
- Echte authentifizierte HTTP-/WebSocket-Verbindungen: Status, Katalog, CRUD, Area-Import, Trockenlauf, Subscription und Rechtebegrenzung. Live-Abonnements überleben einen Integrations-Reload.
- Alle neun Aktionsarten gegen ausführbare Testdienste im echten HA-Service-Registry: Push, Sirene, Schalter, Skript, Licht, Rollos, Snapshot, Aufzeichnung und TTS.
- Kamerafehler unterdrücken den Text-Push nicht. Langsame Verdachts-Pushs blockieren den bestätigten Sirenenalarm nicht. Selbst übernommene Ausgänge werden bei Entschärfung oder Timerende abgeschaltet.
- Private Kameradateien, Kameraleserechte und PIN-Versuchslimit.
- **32 Chromium-Browserprüfungen** gegen den echten Test-Core: CRUD über die deutsche Oberfläche, eigene Profile mit Auswahl und Duplizieren, Profilwechsel/PIN, mobile Darstellung und Dark Theme, Formulare, Text-Escaping und sichtbarer Verbindungsverlust mit Schreibsperre.
- Beobachtung trotz bestätigter Korrelation ohne Geräte, Push, Kamera und Simulation; eigene Stufen mit echten Aktionszuordnungen; generische HA-An/Aus-Anbindung.
- Private PNG-/JPG-Grundrisse: Authentifizierung, Adminrechte, ungültige Bilder, Revisionen, Raumgeometrie, Upload und Neustart.
- Grafische Profilsymbole, freie MDI-Kennung, Speicherung und unveränderte Profilregeln. Direkter Datei-Dialog, ungültiger Upload ohne leere Etage, lokale Flächenvorschläge, korrigierbare Eckpunkte und bewusstes Übernehmen der Raumzuordnung.
- **40 JavaScript-Tests** für lokale Entwurfssicherung, Rückgängig/Wiederholen, Bild-/Benutzertrennung, beschädigte Daten und Speicherausfälle. Browserregressionen bilden den Ablauf „korrigieren → Speichern ohne Raum → Raum auswählen“ ab und prüfen exakte Erhaltung der Eckpunkte, erneute Analyse, Etagenwechsel und Neuladen.
- Direkte Auswahl vorhandener Home-Assistant-Bereiche im Editor und Speicherdialog: aktuelle Liste, Verknüpfung erst beim Speichern, keine doppelten importierten Bereiche, unveränderte Eckpunkte nach Neuladen und vollständiger Entwurfserhalt bei zwischenzeitlich gelöschten HA-Bereichen.
- Strukturierte Erkennung trennt generische farbige Wände von Möbeln und Schraffuren. Der persönliche EG-Grundriss wurde ausschließlich lokal im echten Editor geprüft und wird nicht mit dem Repository oder öffentlichen Testartefakten veröffentlicht.
- Fenster-Assistent: Einlernen der fünf Stellungen, einfache Kontakte, stabile Signale, fehlende Verbindung, explizite unknown-Codes mit separatem Guard, nicht unterscheidbare Kombinationen, ein physisches Fenster als eine Alarmquelle und weiter funktionierender Kontakt bei ausgefallenem Griff. Neue HA-Sensoren werden authentifiziert erzeugt, über Reload geprüft und beim Entfernen der Zuordnung entfernt.
- Fenstergriffe: neutrale Auswertung in allen Profilen, kein Einfluss auf Scharfschaltung/Alarmstufen/Prell-Quarantäne; ausgeblendet in ausgeschalteter Übersicht und „Potenziell unsicher“ bei aktiven Alarmreaktionen. Türschlösser bleiben separat bewertet; Entriegelung und Innenbewegung ersetzen keine physische Öffnung.
- Python-Syntax, Ruff-Lint, Ruff-Format und JavaScript-Syntaxprüfung.
- ZIP-Reproduzierbarkeit, vollständiges ES-Modul im Archiv, Backup und Rollback des Installationsskripts geprüft.

Die vollständige Zuordnung der 16 Auditbefunde und bewusst beibehaltene Grenzen stehen in [AUDIT-RESOLUTION.md](AUDIT-RESOLUTION.md).

Die Tests verwenden eigene Sensorzustände und ausführbare Testdienste im wegwerfbaren Core. Physische Sensoren, Kamera-Codecs, Companion-App-Zustellung und die tatsächliche Hausinstallation werden erst auf der Zielinstanz überprüft.

Die gemeinsame Bewegungsanzeige und rote Raumfarbe laufen nach der Ruhemeldung 15 Sekunden nach und enden zusammen, unabhängig vom Korrelationsfenster. Grenzfälle an der 15-Sekunden-Grenze, aktive/erneute Bewegung, ausgefallene/ausgeblendete Melder und bestätigte Alarme werden geprüft. Eine Browserregression prüft den Ablauf ohne weitere Sensorereignisse.

Fensterübersicht: getrennte Fenster- und Schlosszustände mit gemeinsamem Textformat, Live-Aktualisierung und eindeutige Zuordnung zusätzlicher informativer Aktor-Entitäten anhand echter HA-Geräte. Mehrdeutige, raumfremde und fehlende Zuordnungen bleiben ausgeschlossen. Zusatzinformationen werden nicht zu Pflichtsignalen oder Alarmquellen.

Zusätzliche Prüfungen ab 2.5.0: sechs Standardstufen mit eigenständigem aktiven Normalzustand, lautloser Innenbewegung und ausschließlich bestätigtem Vollalarm; Sirenenabschaltung beim Rückfall auf Stufe 1; Erhalt bestehender Stufenkennungen und Aktionsverweise. Sensorreihenfolgen werden pro Raum gespeichert, beim Verschieben/Löschen bereinigt und im Cockpit wiederverwendet. Browserregressionen prüfen Drag-and-drop, mobile Sortierpfeile, Neuladen, Löschen normaler Sensoren sowie zusammengeführter Fenster samt IQAlarm-Eingangszuordnungen und Profilverweisen. Die HA-Ursprungsentitäten bleiben dabei erhalten.

## Veröffentlichungsstatus

Das Zielrepository ist [marcohildebrandtmail-hub/IQAlarm](https://github.com/marcohildebrandtmail-hub/IQAlarm). Dokumentation, Issue-Tracker und Codeowner sind gebunden. **Der vollständige lokale hassfest-Lauf besteht mit null ungültigen Integrationen.** Ein zusätzlicher Regressionstest prüft die von hassfest verlangte Reihenfolge der Manifest-Schlüssel beim Binden einer Repository-URL.

Die GitHub-Workflows prüfen HACS, hassfest, Python, Browser und beide HA-Versionen. Der aktuelle Remote-Status ist unter [Actions](https://github.com/marcohildebrandtmail-hub/IQAlarm/actions) einsehbar. Eine Aufnahme in den öffentlichen Standardkatalog und ein Brand-Eintrag sind nicht vorgenommen worden.

Version 1.0 wurde auf der persönlichen Home-Assistant-Instanz über HACS installiert und nach Neustart im unscharfen Zustand geprüft. Der Prüfstand für spätere Updates ist über die jeweiligen GitHub-Actions-Läufe nachvollziehbar. Es werden keine Zugangsdaten im Repository gespeichert.

## Reproduzieren

Die ausführbaren Befehle stehen in README.md. Die Prüfer befinden sich in `tests/`, `scripts/verify_ha.py` und `tests/browser/`. Das Installationsarchiv und seine Prüfsummen entstehen mit `python scripts/package_release.py` unter `dist/`.
