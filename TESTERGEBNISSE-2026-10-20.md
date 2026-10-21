# Live-Testbericht · 20. Oktober 2026

**21 unterschiedliche Funktionsszenarien geprüft: 20 erreichen das vereinbarte Verhalten, eine fachliche Lücke bleibt offen.** Dies ist keine uneingeschränkte Abnahme aller Messbedingungen: Die Kamerazustände ließen sich über HA nicht durchgängig exakt zwei Sekunden halten.

## Ergebnis je Fall

Die Zahlen sind Bestätigungsgrade (jeweils von 3), keine Alarmstufen. Bei LVL 0 und dem ignorierten Fenster ist kein Erkennungsgrad aktiv. Die vollständigen erwarteten und gemessenen Stufen stehen im lokalen JSON-Protokoll.

| Fall | Sollgrade | Beobachtete Grade | Ergebnis |
| --- | --- | --- | --- |
| A-Bewegung-zwei-Kameras | 0 → 1 → 2 | 0 → 1 → 2 | Funktions-Soll erreicht |
| B-Bewegung-drei-Kameras | 0 → 1 → 2 → 3 | 0 → 1 → 2 → 3 | Funktions-Soll erreicht |
| C-Zwei-verbundene-Aussenmelder | 0 → 1 | 0 → 1 | Funktions-Soll erreicht |
| D-Drei-Aussenmelder-Kamera | 0 → 1 → 2 → 3 | 0 → 1 → 2 → 3 | Funktions-Soll erreicht |
| E-Bewegung-und-Kameras-addieren | 0 → 1 → 2 → 3 | 0 → 1 → 2 → 3 | Funktions-Soll erreicht |
| F-Unverbundene-Aussenmelder | 0 → 0 | 0 → 0 | Funktions-Soll erreicht |
| G-Derselbe-Aussenmelder | 0 → 0 | 0 → 0 | Funktions-Soll erreicht |
| LVL0-Aus | 0 | 0 | Funktions-Soll erreicht |
| Ignoriertes-Fenster | 0 | 0 | Funktions-Soll erreicht |
| L3-Einzelmelder | 1 | 1 | Funktions-Soll erreicht |
| L3-Gleicher-Raum | 1 → 2 | 1 → 2 | Funktions-Soll erreicht |
| L3-Unverbundene-Einzelmelder | 1 → 1 | 1 → 1 | Funktions-Soll erreicht |
| L3-Derselbe-Innenmelder | 1 → 1 | 1 → 1 | Funktions-Soll erreicht |
| L3-Zwei-getrennte-bestaetigte-Paare | 1 → 2 → 2 → 3 | 1 → 2 → 2 → 2 | **Abweichung** |
| L4-Innen-30-Sekunden | 1 → 2 → 3 | 1 → 2 → 3 | Funktions-Soll erreicht |
| L4-Vierter-Innensensor-entfernt | 1 → 2 → 3 → 3 | 1 → 2 → 3 → 3 | Funktions-Soll erreicht |
| Haustuer-MACO-Kontakt-Bewegung | 1 → 2 → 3 | 1 → 2 → 3 | Funktions-Soll erreicht |
| L4-Aussen-passende-neue-Oeffnung | 1 → 2 → 3 → 3 | 1 → 2 → 3 → 3 | Funktions-Soll erreicht; Impulszeit eingeschränkt |
| L4-Gegenfall-falscher-Innenraum | 1 → 2 → 3 → 3 | 1 → 2 → 3 → 3 | Funktions-Soll erreicht |
| L4-Gegenfall-nur-zwei-Aussenpunkte | 1 → 2 → 2 | 1 → 2 → 2 | Funktions-Soll erreicht |
| L4-Gegenfall-Oeffnung-vor-Aussen3 | 0 → 1 → 2 → 3 | 0 → 1 → 2 → 3 | Funktions-Soll erreicht |

## Abweichung im ursprünglichen Lauf

Flur UG/Büro und Elternbad/Dusche bildeten zwei getrennte bestätigte Paare. Vereinbart ist gemeinsam 3/3; tatsächlich blieben es 2/3. Deshalb entstand in diesem Fall auch kein 30-Sekunden-Übergang zu LVL 4. Diese bekannte fehlende Zusammenführung wurde erneut bestätigt und nicht als Erfolg umgedeutet.

## Gefunden, korrigiert und erneut geprüft

Nach dem vollständigen Rücklauf einer Flur-Einzelmeldung zählte ein erstmals besuchter Büro-Raum die alte Flur-Meldung erneut. Dadurch entstanden 2/3 statt 1/3 und anschließend 3/3 statt 2/3 mit unberechtigtem LVL 4. Die Folge wurde gestoppt; alle Auslösungen waren bereits beendet.

Die Backend-Korrektur übernimmt in einen erstmals ausgewerteten Raum nur neue oder noch gültige Nachbarbelege und merkt sich abgebaute Meldungen als verbraucht. Der Fehler wurde lokal reproduziert, mit fünf Regressionen abgesichert, installiert und per Prüfsumme auf HA verifiziert. Danach ergab dieselbe Live-Folge korrekt Flur 1/3 → vollständiger Rücklauf → Büro 1/3 → 2/3; kein falsches LVL 4. 581 Python-Tests bestanden. Für diese Korrektur wurde keine UI geändert.

## Stufenwechsel und sichtbare Anzeige

| Prüfung | Ergebnis |
| --- | --- |
| Innen-3/3 ohne weiteren Trigger | LVL 4 nach der 30-Sekunden-Frist; rote Überlagerung des vorhandenen äußeren Rings beobachtet |
| Weiterer unabhängiger Sensor im entfernten Elternbad | Sofort LVL 4 vor Ablauf der Frist |
| MACO → Haustürkontakt → Flurbewegung | 1/3 → 2/3 → 3/3, danach der reguläre Timerweg zu LVL 4 |
| Außen-3/3 → neue Fitnessraum-Öffnung | Sofort LVL 4 über die gespeicherte Zuordnung Garagendach → Fitnessraum |
| Außen-3/3 → nicht zugeordnete Öffnung | Nur LVL 3 mit einem Innenhinweis |
| Außen-2/3 → passende neue Öffnung | Kein direkter LVL-4-Sprung |
| Öffnung zuerst, Außen-3/3 erst danach | Keine rückwirkende Bestätigung |
| Höhere Stufen | Höchste beobachtete Stufe 4, niemals LVL 5; kein Daueralarm |

Die Entity-ID des nicht zugeordneten Fensterkontakts enthält „Schlafzimmer“, die tatsächliche IQAlarm-Zuordnung ist **Ankleide**. Der Fall prüft weiterhin denselben vorab festgelegten Gegenbeweis: keine Bereichszuordnung vom beitragenden Garagendach.

Es wurden Kreis, rote Überlagerung, Auslöserliste, Countdowns und Kartenbeschriftungen im vorhandenen Chrome beobachtet; keine Screenshots. Die Browserbeobachtung erfolgte in Blöcken mit etwa 0,5 Sekunden Abständen. 3.562 DOM-Beobachtungen sind gespeichert. Zwischen den Blöcken bestehen Lücken; nicht jeder Zwischenzustand ist lückenlos visuell dokumentiert. Die Backendmessung lief während der Fälle fortlaufend.

## Zeitmessung und Grenzen

| Fall | Erster Backend-Messpunkt mit LVL 4 | Erster Browser-Messpunkt mit LVL 4 |
| --- | --- | --- |
| L4-Innen-30-Sekunden | 30.367 s nach 3/3 | 30.541 s nach 3/3 |
| Haustuer-MACO-Kontakt-Bewegung | 30.331 s nach 3/3 | 30.405 s nach 3/3 |

Das sind erste Beobachtungspunkte, keine Behauptung einer auf Millisekunden bekannten physischen Schaltlatenz. HA-/Browser-Uhrversatz wurde berücksichtigt. Bei den direkten Wegen wurde LVL 4 im ersten Messpunkt rund 0,22–0,23 Sekunden nach dem neuen Trigger festgestellt.

Die gespeicherten Außenfristen entsprachen jeweils Aus-Zeitpunkt + 60 Sekunden. Bei den verglichenen Meldungen lag die Differenz zum HA-Zustandszeitstempel zwischen rund 0,09 und 0,65 Millisekunden. Spätere Meldungen verlängerten frühere Kamera-Timer nicht.

Das Ausblenden wurde beispielsweise am Garagenhof belegt: 1,72 Sekunden vor Ablauf noch rgb(245,158,11), danach Zwischenfarben rgb(180,166,56), rgb(53,180,143), rgb(21,184,165), nach Ablauf die normale Farbe rgb(20,184,166) ohne Bewegungsbeschriftung. Ein harter Farbwechsel lag in diesem beobachteten Ablauf nicht vor.

Zielzeit der Impulse war zwei Sekunden, mit zehn Sekunden Pause nach Aus. Die erste Zeitsteuerung begann zu früh vor der tatsächlichen HA-An-Meldung. Ein Innenimpuls dauerte dadurch 1,584 Sekunden; dieser Fall wurde mit an der HA-Zeit verankerter Steuerung erfolgreich wiederholt (2,019 / 2,037 / 2,042 Sekunden).

Bei einer Kamera fiel der HA-Zustand vorzeitig zurück: zunächst 0,817 Sekunden, bei der Wiederholung 1,374 Sekunden. Ein Kontakt-Aus-Befehl wurde in der Wiederholung erst nach 2,381 Sekunden als Zustandsänderung sichtbar. Damit ist der direkte Außen-/Innen-Übergang funktional bestätigt, **die exakte Zwei-Sekunden-Impulslänge auf dieser Kamera aber nicht abgesichert**. Die Rohzeiten bleiben erhalten. Es wurde kein zusätzliches An-Signal erzeugt, um den Zustand künstlich zu halten und dabei zusätzliche Personenpunkte zu erzeugen.

Die genaue endgültige Nachlaufgestaltung von LVL 4 war noch nicht vereinbart. Ihr beobachteter Rücklauf ist protokolliert, wird jedoch nicht als bereits abgestimmte Produktvorgabe dargestellt.

## Abschlusszustand

- Abwesend, aktiv, LVL 1; keine Erkennungen oder Rest-Countdowns.
- Alle zuvor ausgeschalteten Testquellen wieder Aus. Das vorher bereits offene Fenster Flur OG weiterhin An und ignoriert.
- Keine Quarantäne und keine fremden Quellen während der ausgewerteten Fälle.
- Konfigurationsrevision unverändert 410, alle Sensorfreigaben und neun Bereichszuordnungen erhalten. LVL 4 freigegeben, LVL 5 gesperrt.
- Beide Roboter wurden für diese Prüfung nicht verändert.
- Zwischen den Fällen natürlicher Rücklauf. Ein Entschärfen/Neustart erfolgte ausdrücklich für die Backend-Korrektur; dies ersetzt nicht den dokumentierten fehlgeschlagenen Erstlauf.

## Lokale Messbelege

- `.ha-test/acceptance-20261020T140833Z.json` und `.jsonl`: erster Lauf, Außenfälle A–G, Nachweis des Wiederverwendungsfehlers.
- `.ha-test/acceptance-20261020T142732Z.json` und `.jsonl`: verbleibende 14 Fälle nach der Korrektur.
- `.ha-test/acceptance-20261020T145728Z.json` und `.jsonl`: zwei Wiederholungen zur Impulszeitprüfung.
- `.ha-test/acceptance-browser-20261020T140833Z.json`: getrennte Browserbeobachtungen.
- `.ha-test/acceptance-analysis-20261020.json`: Zusammenführung auf 21 unterschiedliche Fälle; spätere Wiederholungen ersetzen das jeweilige Funktionsresultat, ohne ursprüngliche Rohwerte zu löschen.
- `.ha-test/acceptance-final-state.json`: abschließender Anlagen- und Quellenzustand.
- `.ha-test/acceptance-fade-example.json`: Farbzwischenwerte vor Ablauf.
- `.ha-test/acceptance-replay-abort-state.json` und `acceptance-abort-note.json`: Fehlerzustand und Abbruchbegründung.

Die Außenfälle A–G wurden vor der ausschließlich die Innen-Auswertung betreffenden Korrektur erfolgreich geprüft. Die Innen- und Übergangsfälle wurden danach durchgeführt beziehungsweise wiederholt. Die bereits erfolgreichen Außenläufe wurden nicht allein für einen weiteren Prüfzyklus erneut abgespielt.


## Nachprüfung nach dem Fix der getrennten bestätigten Bereiche

Die obige Abweichung wurde anschließend auf Nutzerauftrag im Backend korrigiert.
Zwei getrennte, jeweils gültig bestätigte Innenbereiche ergeben gemeinsam 3/3.
Ein Paar plus entfernter Einzelmelder bleibt bei 2/3. Gemeinsame Räume oder
physische Quellen dürfen keine doppelte Bestätigung erzeugen. Die bestehende
30-Sekunden-Eskalation sowie der zusätzliche unabhängige Innensensor gelten auch
für diese gemeinsame Bestätigung; Wiederholungen beteiligter Quellen starten den
Timer nicht neu. Es wurden keine Frontend-Dateien oder Einstellungen geändert.

**Lokale Prüfung:** 596 Python-Tests bestanden, darunter 15 zusätzliche
Regressionsfälle für die Zusammenführung und ihre Grenzen: Zwischenstufen,
weitere unabhängige Quelle, Wiederholung, Überschneidung, gleiche Gerätekennung,
Ablauf vor Fristende, verspäteter Tick, erhöhte Schwelle, Neustart mit ursprünglicher
Frist, deaktivierte/nicht verfügbare/ausgeschlossene Quellen, geänderte Verbindung,
Entschärfen und LVL-4-Sperre. Ruff und Formatprüfung bestanden.

**Installiert und live geprüft:** Beide Backend-Dateien wurden auf HA per SHA-256
mit dem lokalen Stand verglichen. Nach dem Neustart wurde die Verfügbarkeit aller
vorher verfügbaren Sensoren abgewartet. Die gespeicherte Konfiguration blieb
vollständig gleich, einschließlich Revision 410 und neun Bereichszuordnungen.

| Live-Folge | Soll | Beobachtet in Backend und vorhandenem Kreis |
| --- | --- | --- |
| Flur UG → Büro → Elternbad → Dusche | 1/3 → 2/3 → 2/3 → 3/3 | entspricht dem Soll |
| Gemeinsame 3/3 ohne neue Meldung | nach 30 Sekunden LVL 4 | erster Backend-Messpunkt nach 30,114 s; LVL 4 auch im Browser beobachtet |
| Natürlicher Rücklauf | LVL 1 ohne Restmeldungen | erreicht; alle vier Quellen wieder Aus |

Die rote Überlagerung des bestehenden Rings wurde bei 3/3 beobachtet. Die
Browsermessung lief in getrennten Blöcken; der erste sichtbare LVL-4-Messpunkt
liegt nach dem Backend-Messpunkt und belegt keine exakte Browser-Schaltlatenz.
Die Impulse mit zwei Sekunden Zielzeit dauerten gemessen 2,040 / 2,032 / 2,038 /
2,028 Sekunden. Keine fremden Erkennungen, keine Quarantäne und kein LVL 5.
Die anderen 20 Fälle wurden für diesen gezielten Fix nicht vollständig neu live
gespielt; ihre früheren Ergebnisse und Rohbelege bleiben erhalten.

Abschluss: Abwesend aktiv, LVL 1, keine Rest-Countdowns; das bereits offene und
ignorierte Flur-OG-Fenster behielt seinen Ausgangszustand. LVL 5 bleibt gesperrt.
Die zuvor offene Paar-Zusammenführung ist damit behoben und live nachgeprüft.

Lokale Nachweise:

- `.ha-test/acceptance-20261020T172123Z.json` und `.jsonl`: vorab festgelegter Sollablauf und laufende Backendmessung.
- `.ha-test/distributed-fix-browser-20261020.json`: Browserbeobachtungen dieser Nachprüfung.
- `.ha-test/distributed-before-fix.json` und `distributed-fix-final-state.json`: Konfigurationsvergleich und Abschlusszustand.


## Erneuter Gesamtlauf, auf Nutzerwunsch beendet

Nach dem Fix beauftragte der Nutzer nochmals die dokumentierten Fälle. Der Lauf
begann mit Abwesend/LVL 1 ohne Restmeldungen bei unveränderter Revision 410.
Er wurde auf ausdrücklichen Nutzerwunsch während des 15. Falls beendet, weil die
Bewohner zurückkehrten. Es wurden keine weiteren Impulse ausgelöst; alle
simulierten Impulse waren zum Abbruch bereits beendet. Keine Installation,
Konfigurationsänderung oder UI-Änderung in diesem Lauf.

**14 Fälle vollständig funktional abgeschlossen, jeweils ohne Sollabweichung:**
Ausgeschaltete Anlage, ignoriertes Fenster, Außenfälle A bis G, Innen-Einzelmelder,
zwei Quellen im selben Raum, unverbundene Innen-Einzelmelder, Wiederholung
desselben Innenmelders und zwei getrennte bestätigte Innenpaare.
Der natürliche Rücklauf wurde jeweils bis zum nächsten sauberen Ausgangszustand
abgewartet. Die Außenfälle zeigten weiterhin höchstens LVL 2, auch bei 3/3.
Unverbundene Außenmelder und Wiederholungen erzeugten keine Zusatzpunkte.

Der korrigierte Paar-Fall ergab erneut **1/3 → 2/3 → 2/3 → 3/3**, anschließend
LVL 4. Der erste Backend-Messpunkt mit LVL 4 lag 30,377 Sekunden nach Beginn von
3/3, der erste Browser-Messpunkt nach 30,435 Sekunden. Danach natürlicher Rücklauf
bis LVL 1. Die alte abgelaufene Flur-Meldung wurde im nachfolgenden Büro-Fall
nicht erneut gezählt: Büro hinten/vorne ergaben korrekt 1/3 → 2/3.

**15. Fall nur teilweise geprüft:** Drei verbundene Innenquellen erreichten
1/3 → 2/3 → 3/3, danach LVL 4 nach 30 Sekunden. Der vollständige Rücklauf wurde
wegen des Abbruchs nicht mehr abgeschlossen. Gegen Ende kam zusätzlich eine
echte Außenbewegung am Garagenhof hinzu; dieser Fall gilt daher nicht als
vollständig eindeutig abgenommen. Die echte Bewegung wurde nicht zurückgesetzt.

**In diesem erneuten Lauf nicht begonnen:** zusätzlicher entfernter Innensensor
nach 3/3, MACO/Haustür/Flur-Folge und alle vier Außen-/Innen-Fälle einschließlich
der drei Gegenfälle. Frühere Nachweise bleiben bestehen, ersetzen aber keine
Wiederholung dieser sechs Fälle in diesem Lauf. Höchste gemessene Stufe war 4;
LVL 5 blieb gesperrt.

**Messgrenzen:** 2.076 Browser-DOM-Messpunkte in getrennten Blöcken; keine
Screenshots. Die Aus-Phase des ersten Falls wurde nicht erneut vollständig im
Browser beobachtet und ist hier durch Backendmessung belegt. Kameraimpulse
wurden mehrfach von der Integration vorzeitig beendet (unter anderem 1,705 /
1,084 / 0,952 Sekunden statt zwei Sekunden Zielzeit). Ein Innenimpuls dauerte
2,681 Sekunden. Die Funktionszählung passte dennoch; die genaue Zwei-Sekunden-
Impulsdauer ist damit keine bestandene Gesamtprüfung. Es wurde keine zusätzliche
An-Meldung gesendet, um eine künstliche Dauer zu erzwingen.

**Zustand beim Stopp:** Anlage weiterhin Abwesend/aktiv, LVL 3 mit Restmeldungen;
Garagenhof-Bewegungsmelder inzwischen An, alle anderen zuvor ausgeschalteten
verwendeten Quellen Aus. Das bereits offene ignorierte Flur-OG-Fenster blieb An.
Die Konfiguration war vollständig unverändert. Die Anlage wurde durch das
Beenden des Testprogramms nicht entschärft.

Nachweise: `.ha-test/acceptance-20261020T172837Z.json` und `.jsonl`,
`.ha-test/retest-browser-20261020T172837Z.json`, `retest-analysis-20261020.json`,
`retest-timer-check-20261020.json` und `retest-stop-20261020.json`.

## 2.14.0: dauerhafter Alarm, Zeit-Eskalation und externer Dienst

Auf Nutzerauftrag umgesetzt und installiert: LVL 4 ist ein bestätigter, bis zum
manuellen Ausschalten bestehender Alarm. Standardfrist bis LVL 5: 300 Sekunden.
Keine neuen Sensorbedingungen in LVL 4/5; Wiederholungen und Ruhe der Sensoren
setzen die Frist nicht zurück. Die vorhandenen Ringe zeigen in LVL 4 Zeitfortschritt,
rote Überlagerung und Restzeit bis LVL 5. Die zuvor gewählten Namen und Farben
bleiben erhalten. Die neue Konfiguration wurde bei ausgeschalteter Anlage aktiviert.

Auf dem tatsächlich externen Proxmox wurde der unprivilegierte LXC 119
`iqalarm-monitor` mit eigenem Dienst und dauerhafter SQLite-Datenbank eingerichtet.
System-ID und separater geheimer Zugang sind je Installation getrennt; der Zugang
wird nicht in der Anzeige oder im Konfigurationsexport ausgegeben. ID-Kollisionen
führen zu einer neuen Identität. Der externe Dienst ist per TLS mit Zertifikat-Pin
über das bestehende WireGuard-Netz angebunden. Der notwendige Rückweg zur konkreten
HA-VM wurde ergänzt; ein öffentlicher Internetzugang wurde nicht eingerichtet.

Geprüft:

- 610 Python-Tests, 112 Frontend-Tests und 11 gezielte Browserfälle bestanden.
- Engine: LVL 4 bleibt trotz ruhiger/weiterer Quellen bestehen; LVL 5 nach Frist;
  manuelles Aus beendet den Alarm; Neustart hält Alarm-ID und ursprüngliche Frist.
- Externer Dienst im tatsächlichen LXC: doppelte Startmeldung verlängert nicht;
  Aufhebung vor Frist bleibt aufgehoben; nicht aufgehobener Alarm wird auch nach
  Dienstneustart eskaliert. Noch keine externen Folgeaktionen konfiguriert.
- HA meldete die tatsächliche System-ID erfolgreich an und deaktivierte sie danach
  wieder. Die Deaktivierung wurde zusätzlich in der externen Datenbank bestätigt.
- Neue Alarme, Aufhebungen und Konfigurationswechsel unterbrechen die normale
  Wiederholpause unmittelbar. Eine zusätzliche Regression sichert dies ab.
- Browser: LVL 4 zeigt fünf Minuten, System-ID und ausgeschalteten Schalter;
  LVL 5 zeigt keine Sensorregeln. Die Ansicht wurde anschließend auf LVL 4 gelassen.
- Zehn betroffene installierte HA-Dateien stimmen per SHA-256 mit dem lokalen
  Stand überein. Release-Paket: `dist/iqalarm-2.14.0.zip`.

Es wurden keine neuen HA-Sensorimpulse ausgelöst und niemand benachrichtigt.
Die tatsächliche LVL-4-/LVL-5-Eskalation im bewohnten Haus wurde nicht live
provoziert. Der Ablauf ist durch Engine-/Browserprüfungen und getrennte reale
Dienstprüfungen abgesichert, nicht durch einen neuen vollständigen Haus-Live-Test.

Abschluss: Anlage weiterhin Aus/LVL 0, externe Überwachung sowohl lokal als auch
extern deaktiviert, keine unbestätigten Übertragungen, Frist 300 Sekunden,
Konfigurationsrevision 416. Sensorfreigaben, Räume, neun Außen-/Innen-Zuordnungen,
Profile und bestehende Aktionen wurden erhalten. Die frühere Testgrenze wurde
für den ausdrücklich beauftragten LVL-5-Timer aufgehoben.

Private lokale Belege: `.ha-test/external-monitor-deployment.json`,
`external-monitor-service-test.json`, `external-monitor-activation-test.json`,
`external-monitor-hashes.json`, `before-external-monitor.json` und
`external-monitor-configured.json`. Dienstbeschreibung: `external_monitor/README.md`.
