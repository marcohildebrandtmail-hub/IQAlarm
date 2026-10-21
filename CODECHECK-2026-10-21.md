# Codeprüfung vom 21.10.2026

Geprüft wurde der lokale Arbeitsstand 2.15.0 einschließlich der vorhandenen,
noch nicht eingecheckten Änderungen. Dies ist keine Aussage darüber, welcher
Stand aktuell auf Home Assistant installiert ist. Keine produktiven Sensoren,
Geräte, SMS oder Dienste wurden ausgelöst. Der Anwendungscode wurde bei dieser
Prüfung nicht geändert.

## Bestätigte Befunde

Nachtrag zur Nutzerklärung: Befund 1 ist im lokalen Arbeitsstand korrigiert.
Als Lichtschalter zählen jetzt Tastenereignisse, physische Binäreingänge und
MQTT-Geräteaktionen. Lampen-/Relaiszustände sind als Eingangsquelle gesperrt;
alte solche Zuordnungen werden deaktiviert. Ausgangsaktionen bleiben erhalten.
Die unten beschriebene Reproduktion dokumentiert den Stand vor der Korrektur.
Nachtrag zur Raumzuordnung: Auch Befund 4 ist lokal korrigiert und getestet.
Bestehende Sensorarten und Einstellungen bleiben bei einem Raumwechsel erhalten.
Noch keine Installation dieser Korrekturen.

### 1. P1 – Eigene Lichtaktionen werden als Einbruchsbelege gezählt

**Bedingung:** Eine `light.*`-Entität ist als Lichtschalter/Bewegungstrigger
konfiguriert und wird zugleich durch eine IQAlarm-Aktion geschaltet.

`runtime.py`, `_state_changed`, Zeilen 222–246, gibt auch diese Zustandsänderungen
unterschiedslos an die Korrelationsauswertung weiter. Die neue Eingangsart und
die Ausgangsaktionen dürfen dieselbe Entität verwenden; die Validierung lässt
diese Kombination zu.

**Lokal reproduziert:** Ein echter Bewegungsmelder im Flur führt zu LVL 3,
1/3. Zwei konfigurierte Lichtaktionen dieser Stufe schalten zwei ebenfalls als
Bewegungstrigger überwachte Lichter im selben Raum ein. Der Bestätigungsgrad
steigt dadurch auf 3/3. Nach 31 simulierten Sekunden steht LVL 4 an – ohne
weitere menschliche Aktivität. Die normale Startverzögerung von 60 Sekunden war
vorher bereits abgelaufen.

Auch eine einzelne eigene Anwesenheitssimulations-Aktion wird als Innenbewegung
gezählt. Die vollständige Eskalation wurde mit den Levelaktionen reproduziert,
nicht durch künstliches Beschleunigen des normalen Simulationsintervalls.

**Korrekturrichtung:** Eigene Ausgangsschaltungen dürfen keine unabhängigen
Einbruchsbelege erzeugen. Dabei echte Betätigungen weiterhin erfassen; keine
pauschale dauerhafte Deaktivierung der Quelle.

### 2. Neubewertet – Startverzögerung 0 wartet bei bestehender Bewegung auf Ruhe

**Bedingung:** Ein Innenbewegungsmelder meldet bereits vor der Aktivierung
Bewegung; die unter LVL 1 angebotene Startverzögerung ist auf 0 gesetzt.

`correlation_engine.py`, `set_profile`, legt nur für eine positive Verzögerung
einen Timer an. Bestehende aktive Quellen werden beim Ablauf dieses Timers in
`tick` ausgewertet. Bei 0 Sekunden findet diese Auswertung nicht statt.

**Lokal reproduziert:** Derselbe aktive Melder bleibt mit Verzögerung 0 bei
LVL 1, ohne Alarmevidenz. Mit Verzögerung 1 steht nach Ablauf LVL 3, 1/3 an.
Bei 0 ist erst ein neuer Aus-/Ein-Wechsel des Melders erforderlich. Bei einer
positiven Startverzögerung werden weiterhin aktive Quellen am Ende bewertet.

**Nutzerentscheidung vom 21.10.2026:** Bei 0 Sekunden soll bereits bestehende
Bewegung zunächst nicht zählen. Nach dem ersten Ruhigwerden zählt die nächste
Bewegung wieder regulär. Das zuvor als Fehler bewertete Ergebnis ist damit für
diesen Fall ausdrücklich gewünscht. Die frühere Empfehlung, sofort LVL 3
auszulösen, ist aufgehoben. Die Sollregel und der erwartete Ablauf stehen in
[SIMULATIONSTESTS.md](SIMULATIONSTESTS.md). Eine ausdrückliche Absicherung dieser
Regel durch Tests steht noch aus; hier wurden nur die Vorgaben dokumentiert.

### 3. P2 – Neustart spielt LVL-4-/LVL-5-Aktionen erneut ab

**Bedingung:** Home Assistant startet während eines bereits bestehenden
Alarms neu.

`correlation_engine.py`, `_restore_rules`, Zeilen 2505–2509, findet für den
separat gespeicherten Alarm keine passende gewöhnliche Sensorregel und setzt
die Stufe zunächst auf den Grundzustand zurück. Der anschließende Timerlauf
stellt denselben Alarm wieder her, erzeugt dabei aber ein neues
`confirmation_changed`-Ereignis. `runtime.flush` und der Aktionsverteiler
behandeln dieses als erneuten Eintritt in die Alarmstufe.

**Lokal reproduziert:** LVL 4 → Speichern → Wiederherstellen vor derselben
Eskalationsfrist erzeugt ein neues bestätigtes LVL-4-Ereignis. Dasselbe passiert
bei einem bereits erreichten LVL 5. Ein mit Testdiensten angeschlossener
Benachrichtigungszähler steigt beim Neustart von 1 auf 2.

Damit können Pushs, Skripte oder Sprachmeldungen erneut ausgeführt und
Ausgangslaufzeiten verlängert werden. Die Alarm-ID und die externe Frist
bleiben dabei erhalten; ein doppelter externer SMS-Versand wurde hiermit nicht
nachgewiesen und ist nicht die Aussage dieses Befunds.

**Korrekturrichtung:** Bestehenden Alarm ohne erneutes Eintrittsereignis
wiederherstellen. Ein tatsächlich während der Ausfallzeit erstmals fälliger
Übergang von LVL 4 auf LVL 5 muss weiterhin ausgeführt werden.

### 4. Lokal korrigiert – Alte Sensorarten ändern sich beim gewöhnlichen Speichern

**Nutzerentscheidung und Korrektur vom 21.10.2026:** Ein Raumwechsel nimmt alle
Sensoreinstellungen mit. Die vorhandenen Auswahlfelder behalten deshalb auch
einen gespeicherten alten Typ als aktuellen Wert. Andere alte Typen werden nicht
wieder als neue Optionen angeboten. Unveränderte Typen werden beim Speichern
nicht konvertiert; eine bewusst ausgewählte neue Art bleibt möglich. Dies gilt
für die Raumzuordnung, deren Speichern/Sortieren und den Sensor-Editor.

Geprüft mit vollständigem Vorher-/Nachher-Vergleich der Sensordatensätze:
126 Frontend-Funktionstests und 23 lokale Browserfälle bestanden, darunter
16 Fälle für die vier alten Arten und die vier Speicherwege. Keine HA-Live-
Änderung oder Installation. Die folgende Beschreibung dokumentiert den Fehler
vor dieser Korrektur.

**Bedingung:** Eine vorhandene Konfiguration enthält noch einen Sensor der
entfernten Auswahlkategorien, beispielsweise `interior_mmwave`.

`frontend/sensor-types.js`, `sensorTypeField`, Zeilen 27–30, erzeugt für diesen
gespeicherten Wert keine ausgewählte Option. Der Browser wählt automatisch den
ersten Eintrag `entry_contact`. `_moveSensor` in `frontend/iqalarm-panel.js`,
Zeile 691, übernimmt diesen Wert beim Speichern der Zuordnung.

**In lokalem Chromium reproduziert:** Vorhandener Präsenzsensor
`interior_mmwave` → Formular ohne Änderung der Sensorart öffnen → ausgewählter
Formularwert `entry_contact` → Speichern konvertiert den Sensor zum
Öffnungskontakt. Dadurch ändern sich unter anderem die fachliche Auswertung
und die geltenden Ausnahmen.

**Korrekturrichtung:** Bestehende Typen beim unveränderten Speichern erhalten
oder eine ausdrücklich festgelegte Migration durchführen. Eine eventuell
zusätzliche UI-Darstellung dafür zuvor mit Marco abstimmen.

## Prüfungen und Grenzen

- 682 vorhandene Python-Tests bestanden.
- 114 vorhandene Frontend-Tests bestanden.
- Ruff-Prüfung bestanden; Formatprüfung für 87 Dateien bestanden.
- `git diff --check` ohne Whitespace-Fehler; Git meldet bestehende
  CRLF/LF-Konvertierungshinweise.
- Zusätzliche lokale Reproduktionen mit dem unveränderten Engine- und
  Runtime-Code sowie den vorhandenen HA-Testadaptern; keine echten HA-Aufrufe.
- Die Sensorart-Auswahl wurde zusätzlich mit lokalem Headless Chromium geprüft.
- Kein vollständiger neuer Browser-Testlauf, keine Live-Simulation,
  keine Installation und keine SMS-Zustellprüfung in diesem Codecheck.

Die damaligen grünen Tests deckten die vier beschriebenen Randfälle nicht ab.
Aktueller Nachtragsstand: Befunde 1 und 4 lokal korrigiert und getestet; Fall 2
durch die Nutzerentscheidung als gewünschte Startregel festgelegt, gezielte
Testabsicherung noch offen. Zu Fall 3 wünscht der Nutzer die Wiederholung der
Alarmaktionen beim HA-Neustart; in diesem Schritt keine Änderung daran.
