# Vereinbarte Live-Simulationen

Stand: 20. Oktober 2026. Referenz: die gemeinsam durchgeführten und vom Nutzer
bestätigten Außenmeldungs-Tests mit dem Verhalten von Version 2.13.3.

Ergänzung vom selben Tag: Der Nutzer hat zusätzlich die unten beschriebene
Bewegungsbestätigung und das Addieren von Bewegungs- und Kameraanteil freigegeben.
Die Dateien dieser Erweiterung wurden auf der Zielinstanz am 20. Oktober 2026
über Prüfsummen verifiziert: beide Backend-Dateien und die drei betroffenen
Frontend-Dateien stimmen exakt mit dem lokalen Stand überein. Die gemeldete
Versionsnummer ist dabei weiterhin 2.13.3; sie allein belegt den Dateistand nicht.
Die neue Erhöhung für zwei direkt verbundene Bewegungsmelder wurde mit Variante C
positiv live geprüft; Einzelheiten stehen im Prüfprotokoll weiter unten.
Die ursprünglichen Abläufe A/B mit nur einem Bewegungsmelder bleiben unverändert
gültig. Auch der gemischte Ablauf E wurde inzwischen positiv live geprüft;
Ablauf D mit drei Bewegungsmeldern ist noch nicht live abgenommen.

Diese Datei beschreibt das erwartete Verhalten **vor** einem Test. Sie ist die
Vorgabe für spätere Simulationen, auch mit anderen geeigneten Sensoren. Ein
beobachtetes Ergebnis oder die aktuelle Implementierung darf die Erwartung nicht
nachträglich ersetzen. Abweichungen werden als Abweichungen protokolliert.

## Geltungsbereich und feste Vorgaben

### Vereinbarte Startregel bei 0 Sekunden (21.10.2026)

Bei **Startverzögerung 0 Sekunden** zählt eine beim Aktivieren bereits bestehende
Bewegungsmeldung zunächst nicht als neuer Alarmbeleg. Der betroffene Melder muss
erst wieder **ruhig** werden. Die **nächste neue Bewegung** wird anschließend
regulär nach den Level- und Raumregeln bewertet. Dies gilt je Melder; andere
bereite Melder bleiben normal auswertbar. Es ist keine dauerhafte Ausnahme wie
bei einem für die Scharfschaltung ignorierten offenen Fenster.

Sollfall ohne weitere Belege: Innenmelder bereits aktiv → Anlage mit 0 Sekunden
aktivieren → LVL 1 und kein Innenbeleg; Melder wird ruhig → weiterhin LVL 1;
erneute Bewegung → LVL 3 mit 1/3. Dauerhaft aktive Bewegung aus der Zeit vor dem
Einschalten darf allein keinen Grad aufbauen. Für eine positive Startverzögerung
(Standard 60 Sekunden) bleibt die bisherige Auswertung am Ende der Wartezeit
bestehen. Diese Festlegung betrifft Bewegungsmelder, nicht neue Tastenereignisse
oder die eigenständige Fensterregel.

Status: ausdrücklich vom Nutzer als Regel bestätigt und dokumentiert. In diesem
Schritt keine Codeänderung, Installation oder neue Live-Prüfung vorgenommen.

### Weitere feste Vorgaben

- **Deaktivierungsaktionen (beauftragt am 21.10.2026):** Unter LVL 0 dürfen
  ausdrücklich konfigurierte Aktionen einmal beim Wechsel von einer aktiven
  Anlage zu Aus laufen, beispielsweise grünes Licht für die eingestellte Dauer.
  Die ausgewählten Alarmmodi beziehen sich auf das vorher aktive Profil. Zuerst
  müssen alte Alarm-Ausgänge beendet werden. Weitere Sensormeldungen oder deren
  Ablauf bei Aus sowie erneutes Ausschalten starten die Aktion nicht nochmals.
  Ein schnelles Wiedereinschalten verwirft noch nicht ausgeführte alte
  Deaktivierungsaktionen. Statusbeobachtung allein erzeugt weiterhin keine
  Geräteaktionen. Diese Vorgaben sind lokal geprüft, noch kein HA-Live-Test.

- **Raumwechsel (bestätigt am 21.10.2026):** Alle Einstellungen des Sensors werden
  mitgenommen. Außer der beauftragten Raumzuordnung bzw. Reihenfolge bleibt der
  Sensordatensatz unverändert. Dies umfasst auch gespeicherte ältere Sensorarten,
  aktive Werte, Entprell-/Prellzeiten, Quellenkennung, Aktivierung und
  Kameraverknüpfung. Eine andere Sensorart wird nur bei ausdrücklicher Auswahl
  übernommen. Das reine Speichern oder Sortieren darf sie ebenfalls nicht ändern.

- Geprüft wird die scharfgeschaltete Anlage, im Referenzlauf im Profil
  **Abwesend**, ausgehend von **LVL 1 · Sicher**.
- Ein einzelner **Bewegungsmelder außen** löst **LVL 2 · Bewegung Außen** aus,
  erhöht aber den Bestätigungsgrad nicht.
- Zwei unabhängige Außenbewegungsmelder im selben oder direkt verbundenen Bereich
  ergeben einen **Bewegungsanteil von 1/3**, drei ergeben **2/3**. Auch mehr Melder
  erreichen ohne Kamera höchstens 2/3. Wiederholungen desselben Melders und mehrere
  Entitäten desselben physischen Geräts zählen hierfür einmal.
- Die beteiligten Bereiche müssen direkt zueinander passen. Eine Kette A–B–C
  ersetzt keine direkte Verbindung A–C. Die Teilgrade voneinander unabhängiger
  Bewegungsgruppen werden nicht addiert; es zählt die stärkste passende Gruppe.
  Fehlende Raumzuordnung, berührende Polygone und alte Nachbarschaftsangaben
  erzeugen keine Verbindung.
- Jede neue gültige **Personenmeldung einer Außenkamera** zählt bei den hier
  verwendeten Schwellen **1, 2, 3** einen Punkt. Zwei noch gültige Personenmeldungen
  ergeben einen Kameraanteil von 2/3, drei einen Kameraanteil von 3/3.
- Bewegungs- und Kameraanteil werden bis höchstens 3/3 **addiert**. Zwei passende
  Bewegungsmelder plus eine Personenmeldung ergeben 2/3; eine zweite Personenmeldung
  vervollständigt 3/3. Drei passende Bewegungsmelder plus eine Personenmeldung
  ergeben bereits 3/3. Bei eigenen Kameraschwellen gelten diese weiterhin für den
  Kameraanteil; die zwei beziehungsweise drei Bewegungsmelder liefern 1/3 bzw. 2/3.
- Dieser LVL-2-Personenzähler gilt gemeinsam über die einbezogenen Außenbereiche.
  Die Kameras müssen dafür weder denselben Raum noch eine Türverbindung haben.
  Daraus folgt keine Freigabe für räumliche Innenraum- oder Vollalarmbestätigungen.
- **3/3 ist der vollständige Bestätigungsgrad von LVL 2**, kein automatischer
  Sprung zu LVL 3, LVL 4 oder LVL 5. Reine Außenbewegung ergibt auch bei mehreren
  Meldungen niemals eine vollständige 3/3-Bestätigung.
- Die gemeinsame Meldegültigkeit beträgt in diesen Tests **60 Sekunden nach dem
  Ende der jeweiligen Meldung**. Solange die Quelle tatsächlich aktiv ist, steht
  sie auf **Aktiv**; der Nachlauf beginnt mit ihrer Aus-Meldung.
- Jede Meldung besitzt ihre eigene Ablaufzeit. Eine spätere Kamera verlängert
  nicht den Timer einer früheren Kamera. Gleiche Gültigkeit bedeutet deshalb
  nicht identische Restzeit bei zeitversetzten Meldungen.
- Bestätigungsgrad, LVL-2-Meldegültigkeit, Kartenmarkierung und Countdown verwenden
  dieselbe Ablaufzeit. Der alte separate 180-Sekunden-Nachlauf darf hier nicht
  weiterlaufen, wenn die betreffende Meldung bereits abgelaufen ist.
- Höhere Stufen LVL 4 und LVL 5 sind für die laufende Erprobung weiterhin gesperrt.
  Diese Datei erteilt keine Freigabe, sie zu aktivieren.

Die Sollwerte gelten für diese Testkonfiguration. Weichen Schwellen, Zeit,
Profilzuordnung oder Sensorrollen ab, muss das **vor dem Auslösen** dokumentiert
werden. Bestehende Einstellungen nicht stillschweigend an den Test anpassen.

## Sensorzuordnung

| Kürzel | Rolle im Test | Erfolgreich verwendete Quelle |
| --- | --- | --- |
| M | einzelner Bewegungsmelder außen, allein ohne Bestätigungsgrad | Bewegung Garagenhof |
| P1 | Kamera mit Personenmeldung | Person Büro, Garten Büroseite |
| P2 | Kamera mit Personenmeldung | Person Garten, Terrasse |
| P3 | Kamera mit Personenmeldung | Person, Garagendach |

Konkrete HA-Entitäten stehen ausschließlich in der lokalen, ignorierten Datei
`.ha-test/live-simulation-reference.json`. Die Zuordnung vor jedem Lauf anhand
der aktuellen HA-/IQAlarm-Konfiguration überprüfen. Keine Entitäts-ID aus einem
Namen erraten. Bei der Terrasse ist im Referenzlauf **Person Garten** gemeint.

Andere Sensoren dürfen diese Kürzel ersetzen, wenn sie dieselbe Funktion haben,
im Testprofil überwacht werden, verfügbar und nicht isoliert sind. Für P1 bis P3
im Referenzablauf drei getrennte Kameras mit echter **Personenerkennung** wählen.
Kamerabetrieb, allgemeine Bewegung und Fahrzeugerkennung sind kein Ersatz dafür.
Debounce, Auslöseverzögerungen und zusätzliche Regelbedingungen vorab prüfen:
Die Zwei-Sekunden-Meldung muss unter den festgelegten Testbedingungen gültig sein.
Abweichende Bedingungen erfordern vor dem Start eine dokumentierte Testvorgabe;
sie rechtfertigen keine nachträgliche Änderung des Soll-Ergebnisses.

## Vorbereitung eines eindeutigen Laufs

1. Aktuellen Anlagenzustand, Profil, wirksame Schwellen und Meldegültigkeit lesen.
   Die Anlage muss für den Lauf scharf sein; etwaige Scharfschaltverzögerung
   vollständig abwarten.
2. Ausgangszustand prüfen: LVL 1, kein laufender Personen-Bestätigungsgrad, keine
   alten relevanten Meldungen oder Countdowns. Alle ausgewählten Testquellen
   müssen auf Aus stehen. Eine bereits aktive Quelle nicht als neue Testmeldung
   ausgeben.
3. Echte Innenbewegung darf den isolierten LVL-2-Test nicht überlagern. Für die
   Referenzläufe wurden mit ausdrücklicher Zustimmung **20 Innenbewegungssensoren**
   vorübergehend aus IQAlarm genommen, darunter Dusche, Elternbad und die als
   Bewegung eingestufte Innentür Sophie. Kameras und Außenbewegungsmelder blieben
   aktiv. Die im Vorgarten als Bewegung eingestuften Brief-/Paketkasten-Kontakte
   gehörten nicht zu diesen 20 Innenquellen.
4. Vor einem weiteren Lauf prüfen, ob eine Test-Ausnahme noch besteht und für
   diesen Lauf benötigt wird; den tatsächlichen Zustand protokollieren. Neue
   Ausnahmen oder eine Wiederherstellung nur im abgestimmten Umfang durchführen.
   Konfiguration lässt sich nur bei ausgeschalteter Anlage ändern. Vorherige
   Werte sichern; später nur die tatsächlich geänderten Werte zurücksetzen, nicht
   eine komplette alte Konfiguration über inzwischen erfolgte Änderungen schreiben.
5. Ein einmaliges Zurücksetzen einer HA-Quelle auf Aus löscht keine gespeicherte
   Erkennung. Neue echte Bewegung kann sofort wieder LVL 3 auslösen. Kontakte mit
   **Bewegung bei Zustandswechsel** reagieren sogar auf das Zurücksetzen selbst.
   Deshalb nicht durch wiederholte Aus-Meldungen einen scheinbar sauberen Lauf
   erzeugen. Bei Überlagerung den Lauf als nicht eindeutig markieren.

**Innenmelder-Ausnahme beendet:** Am 20. Oktober 2026 wurden auf Nutzerauftrag
alle 20 vorübergehend ausgeschlossenen Innenmelder wieder auf ihre ursprüngliche
Freigabe gesetzt. Anschließend waren keine Sensorzuordnungen mehr deaktiviert.
Raumverbindungen, übrige Einstellungen und die Sperre für LVL 4/5 blieben erhalten.
Die Anlage war dabei bereits Aus und blieb Aus. Die Wiederherstellung wurde durch
erneutes Lesen der gespeicherten Konfiguration geprüft. Lokaler Nachweis:
`.ha-test/restored-indoor-motion-test-20261020T121505Z.json`.

Bei einer künftig erneut vereinbarten Innenmelder-Ausnahme deren ursprüngliche
Werte unter `.ha-test/active-indoor-motion-test.json` sichern. Eine solche Ausnahme
ist eine Testvorbereitung, keine dauerhaft vereinbarte Überwachungseinstellung.
Nach Abschluss der vereinbarten Testphase die ursprünglichen Werte im vereinbarten
Umfang wiederherstellen und den Erfolg prüfen. Bereits erteilte Freigaben gelten
weiter; noch bestehende Ausnahmen ausdrücklich festhalten. Für die nun geplanten
weiteren Leveltests sind die Innenmelder wieder freigegeben.

## Durchführung und Zeitmessung

- Je Quelle genau **einen An-Impuls mit Zielzeit 2 Sekunden**, danach wieder Aus.
  Die bestehenden HA-Attribute erhalten. Das Aus-Signal auch bei einem Fehler
  zuverlässig ausführen und den Endzustand überprüfen.
- Zwischen dem **Ende** eines Impulses und dem Beginn des nächsten **10 Sekunden**
  warten. Die Sollstarts liegen somit bei t = 0, 12, 24 und gegebenenfalls 36.
- Tatsächliche An-/Aus-Zeitstempel und Impulsdauer messen. HTTP-Laufzeit und
  Beobachtungsintervall machen die gemessenen Zeiten geringfügig ungenau. Nicht
  behaupten, exakt 2,000 Sekunden gemessen zu haben, wenn es etwa 2,024 waren.
- Für jede Quelle die verbindliche Ablaufzeit festhalten:
  **Zeitpunkt der Aus-Meldung + 60 Sekunden**.
- Backendstatus und sichtbare Oberfläche getrennt prüfen. Ein Backendwert allein
  beweist nicht, dass Kreis, Karte und Countdown richtig dargestellt wurden.
- Für Messungen HA-Serverzeit, Uhrversatz des Browsers und Zeitauflösung beachten.
  Berechneten Ablauf und ersten tatsächlich beobachteten Rückfall getrennt
  protokollieren. Keine nicht vereinbarte Toleranz erfinden, um Fehler zu bestehen.
- Der Nutzer schaut im vorhandenen Browser mit. Keine Screenshots anfertigen und
  keine eigenständigen UI-Änderungen vornehmen. Ein Neuladen ersetzt keinen Reset
  der Erkennung.

## Ablauf A: Außenbewegung und zwei Kameras

| Sollzeit ab erstem An-Signal | Eingabe / Ablauf | Erwartetes LVL | Personen-Bestätigungsgrad |
| --- | --- | --- | --- |
| vor t = 0 | sauberer Ausgangszustand | 1 | 0/3 |
| t = 0 bis 2 | M an, danach aus | 2 | 0/3 |
| t = 12 bis 14 | P1 an, danach aus | 2 | 1/3 |
| t = 24 bis 26 | P2 an, danach aus | 2 | 2/3 |
| t = 62 | M läuft aus | 2 | weiterhin 2/3 |
| t = 74 | P1 läuft aus | 2 | 1/3 |
| t = 86 | P2 als letzte Meldung läuft aus | 1 | 0/3 |

Die Zeiten der Rückfälle beziehen sich auf die Soll-Impulsenden. Beim echten Lauf
werden sie aus den tatsächlich gemessenen Aus-Zeitpunkten berechnet.

## Ablauf B: Außenbewegung und drei Kameras

| Sollzeit ab erstem An-Signal | Eingabe / Ablauf | Erwartetes LVL | Personen-Bestätigungsgrad |
| --- | --- | --- | --- |
| vor t = 0 | sauberer Ausgangszustand | 1 | 0/3 |
| t = 0 bis 2 | M an, danach aus | 2 | 0/3 |
| t = 12 bis 14 | P1 an, danach aus | 2 | 1/3 |
| t = 24 bis 26 | P2 an, danach aus | 2 | 2/3 |
| t = 36 bis 38 | P3 an, danach aus | 2 | 3/3 |
| t = 62 | M läuft aus | 2 | weiterhin 3/3 |
| t = 74 | P1 läuft aus | 2 | 2/3 |
| t = 86 | P2 läuft aus | 2 | 1/3 |
| t = 98 | P3 als letzte Meldung läuft aus | 1 | 0/3 |

Ein Vorfeld-Bewegungsmelder zählt auch in dieser Viererfolge **nicht** als vierte
Person oder als zusätzliche Stufe. Der innere Bestätigungskreis ist bei 3/3 voll,
die Zahl im äußeren Stufenring bleibt 2.

## Neue Abläufe mit Bewegungsbestätigung

Diese Sollwerte wurden vor den neuen Implementierungsprüfungen festgelegt. Sie
sind noch keine Behauptung über einen erfolgreichen Live-Lauf der Erweiterung.
M1/M2/M3 sind unterschiedliche physische Außenbewegungsmelder in passenden,
direkt zueinander verbundenen Bereichen oder im selben Bereich. P1/P2 bleiben
Kamera-Personenmeldungen. Pulse, Pausen und Einzelgültigkeit bleiben gleich.

| Variante | Reihenfolge der Impulse | Erwarteter Grad nach jedem Impuls |
| --- | --- | --- |
| C | M1 → M2 | 0/3 → 1/3 |
| D | M1 → M2 → M3 → P1 | 0/3 → 1/3 → 2/3 → 3/3 |
| E | M1 → M2 → P1 → P2 | 0/3 → 1/3 → 2/3 → 3/3 |
| F | zwei Melder aus nicht verbundenen Bereichen | 0/3 → 0/3 |
| G | derselbe Bewegungsmelder mehrfach | stets 0/3 |

LVL bleibt in allen Varianten während einer gültigen Außenmeldung 2.

**Rücklauf C:** M1 endet bei t = 2 und läuft bei t = 62 aus. Dann ist nur M2 gültig:
kein Bewegungsgrad mehr, aber weiter LVL 2. Bei t = 74 läuft M2 aus: LVL 1.

**Rücklauf D:** M1 läuft bei t = 62 aus: zwei Bewegungsmelder plus eine Kamera
ergeben 2/3. M2 läuft bei t = 74 aus: eine Bewegung plus eine Kamera ergeben 1/3.
M3 läuft bei t = 86 aus: der Kameraanteil bleibt 1/3. Bei t = 98 läuft P1 aus:
LVL 1 und kein Bestätigungsgrad.

**Rücklauf E:** M1 läuft bei t = 62 aus: der Bewegungsanteil entfällt, zwei Kameras
ergeben weiter 2/3. M2 läuft bei t = 74 aus: weiter 2/3. Bei t = 86 läuft P1 aus:
1/3. Bei t = 98 läuft P2 aus: LVL 1 und kein Bestätigungsgrad.

Zusätzlich prüfen: Läuft die einzige Personenmeldung bei noch drei gültigen
Bewegungsmeldern aus, fällt 3/3 sofort auf 2/3. Ein nicht mehr gültiger, nicht
verfügbarer oder isolierter Melder darf keine Bewegungsbestätigung erhalten.
Die kamerabasierten Abläufe A/B müssen weiterhin dieselben Ergebnisse liefern.

## Erwartete sichtbare Anzeige

- Jeder betroffene Außenbereich kann gleichzeitig markiert sein. Eine neue Kamera
  entfernt nicht die noch gültige Erkennung eines anderen Bereichs.
- Garagenhof-Bewegung heißt auf der Karte **Bewegung erkannt**, nicht Kamera aktiv.
  Personenmeldungen werden als Personenerkennung angezeigt.
- Im scharfen Zustand bleibt die Kartenmarkierung während der gültigen Erkennung
  bestehen. Die Farbe blendet zum Ende weich zurück; der bisher verwendete Verlauf
  beginnt ungefähr **1,5 Sekunden vor dem Ablauf**, damit nach Ablauf keine alte
  Farbe weiter stehen bleibt. Kein harter Wechsel von Aktivfarbe zu Normalfarbe.
- Im Kopf von **Live-Grundriss** stehen höchstens die **drei neuesten noch gültigen
  direkten Auslöser**, jeweils mit Quelle und Restzeit. Eine noch aktive Quelle
  zeigt Aktiv. Sobald P3 in Ablauf B erscheint, darf M aus dieser Liste fallen;
  seine eigene noch gültige Kartenmarkierung bleibt bis zu seinem Ablauf bestehen.
- Der Countdown einer Kamera und ihr Beitrag zum Bestätigungsgrad enden zusammen.
  Es darf keine abgelaufene Kamera mehr zum Grad beitragen oder ohne sichtbare
  Meldung weiterzählen. Unterschiede der Restzeiten entsprechen den verschiedenen
  Meldezeitpunkten, nicht unterschiedlichen Gewichten der Kameras.
- Nach der letzten Außenmeldung sind die Karten wieder neutral, die Auslöserliste
  leer und die Anlage auf LVL 1. Das ist weiterhin **scharfgeschaltet**, nicht Aus.
- Der innere Ring kann bei LVL 1 anschließend wieder das **Überwachungsrisiko**
  zeigen, etwa wegen ignorierter Fenster. Dieser Wert ist ausdrücklich kein
  verbleibender Personen-Bestätigungsgrad und muss nicht 0/3 sein.
- Keine zusätzlichen Fortschrittsbalken oder Test-Hinweiskarten zwischen den
  vorhandenen Bereichen einfügen; siehe [AGENTS.md](AGENTS.md).

## Abgenommen, übertragbar und noch offen

**Am 20. Oktober 2026 live abgenommen:** Ablauf A mit Garagenhof, Büroseite und
Terrasse sowie Ablauf B zusätzlich mit Person Garagendach. Die gemessenen Impulse
lagen ungefähr zwischen 2,000 und 2,024 Sekunden. Alle Quellen bekamen jeweils
60 Sekunden Gültigkeit nach Aus. Die erwarteten Grade wurden erreicht und liefen
wieder zurück; beim Abschluss standen alle Testquellen auf Aus und die Anlage
auf LVL 1. Es gab in diesen beiden eindeutigen Läufen keine überlagernde Erkennung.

Die lokalen Backendprotokolle heißen `.ha-test/camera-sequence-latest.json` und
`.ha-test/camera-sequence-4-latest.json`. Sie sind Messbelege und keine Ersatzvorgabe.
Die Kreis- und Kartenanzeige wurde zusätzlich gemeinsam im Browser geprüft.

**Zusätzlich am selben Tag live geprüft: Variante F.** Bewegung Lagerplatz
(Garten Büroseite) und Bewegung Garagenhof wurden erneut mit etwa zwei Sekunden
Impuls und zehn Sekunden Pause ausgelöst. Die Bereiche waren nur über den
Vorgarten, nicht direkt verbunden. Erwartung vor dem Lauf: LVL 2 ohne
Bestätigungsgrad. Das wurde im Backend und im Browser beobachtet; nach jeweils
60 Sekunden Nachlauf endeten die Meldungen, zuletzt Rückfall auf LVL 1 und beide
Quellen wieder Aus. Lokaler Messbeleg:
`.ha-test/motion-unconnected-20261020T111235Z.json`. Dieser Negativfall ersetzt
keinen positiven Live-Test der neuen Bewegungsbestätigung.

**Zusätzlich am selben Tag positiv live geprüft: Variante C.** Bewegung Garagenhof
und danach Bewegung Garagendach wurden mit etwa zwei Sekunden Impuls und zehn
Sekunden Pause ausgelöst. Ihre direkte Raumverbindung war vor dem Lauf geprüft.
Nach dem ersten Melder stand LVL 2 ohne Grad; nach dem zweiten LVL 2 mit 1/3.
Backend meldete dabei Bewegungsanteil 1, Kameraanteil 0; der innere Kreis zeigte
ebenfalls 1/3. Mit Ablauf der ersten Meldung entfiel der Grad bei weiter LVL 2.
Mit Ablauf der zweiten Meldung folgte LVL 1; beide Testquellen standen wieder Aus.
Lokaler Messbeleg: `.ha-test/motion-connected-20261020T111618Z.json`.
Erst nach Abschluss dieses Laufs erschien eine zusätzliche Meldung von Bewegung
Lagerplatz. Sie gehört nicht zur vorgegebenen Testfolge und darf nicht als deren
fortgesetzte oder fehlerhafte Erkennung ausgegeben werden.

**Zusätzlich am selben Tag positiv live geprüft: Variante E.** Nach sauberem
Ausgangszustand folgten Bewegung Garagenhof, Bewegung Garagendach, Person Büroseite
und Person Garten an der Terrasse, jeweils ungefähr zwei Sekunden aktiv und
zehn Sekunden Pause nach Aus. Die Reihenfolge erreichte im Backend und im
sichtbaren Kreis LVL 2 ohne Grad, dann 1/3, 2/3 und 3/3. Bei 3/3 meldete das
Backend Bewegungsanteil 1 und Kameraanteil 2. Beim Ablauf der ersten Bewegung
entfiel der Bewegungsanteil: weiter 2/3 durch die beiden Kameras. Beim Ablauf
der zweiten Bewegung blieb 2/3 bestehen, danach folgten 1/3 und schließlich
LVL 1 ohne laufende Meldungen. Alle vier Testquellen standen wieder Aus.
Es gab während dieses Laufs keine überlagernden Quellen. Lokaler Messbeleg:
`.ha-test/motion-camera-mixed-20261020T111922Z.json`.

**Für andere Sensoren übertragbar:** dieselben Abläufe A/B mit anderen überwachten
Außenbewegungsmeldern beziehungsweise anderen Personenmeldungen geeigneter Kameras.
Vor dem Start die Zuordnung M/P1/P2/P3 dokumentieren; Sollgrade und Lebensdauer
bleiben bei derselben Testkonfiguration unverändert.

**Bereits vereinbart, aber durch diese beiden Live-Läufe nicht eigens abgenommen:**
eine neue echte Aus-/An-Personenmeldung derselben Kamera zählt erneut; bloßes
Abfragen oder Wiederholen eines unverändert aktiven Zustands zählt nicht neu.
Ein späterer Wiederholungstest braucht einen eigenen vorher festgelegten Ablauf
mit den tatsächlichen Ablaufzeiten beider Meldungen.

**Hier nicht definiert:** über die nachfolgend vereinbarten LVL-3-Fälle hinausgehende
Auslösefolgen in Innenräumen, LVL-3-Eskalation,
Verwendung einer vollständigen LVL-2-Bestätigung für Folgeregeln, LVL 4, LVL 5,
Sirenen und Benachrichtigungsaktionen. Dafür keine Sollwerte aus dem aktuellen
Programm ableiten oder frei ergänzen. Vor einem solchen Test mit dem Nutzer
festlegen, was wann passieren soll.

## LVL 3: erster Einzelmelder-Test

Am 20. Oktober 2026 hat der Nutzer als ersten Schritt Bewegung im Flur UG
angefordert. Vor dem Impuls wurde die Erwartung festgehalten: LVL 3 mit 1/3,
Bewegungsanzeige im Flur UG und anschließend Rücklauf ohne weitere Meldungen.
Vorbereitung: Alle Innenmelder waren wieder freigegeben, beide Saugroboter auf
Nutzerauftrag pausiert. Ausgangszustand war Abwesend, LVL 1, ohne Erkennungen.

Der Impuls hatte zwei Sekunden Zielzeit; tatsächlich wurden **2,156326 Sekunden**
gemessen. Backend und sichtbarer Kreis erreichten LVL 3 mit 1/3. Die Karte zeigte
im Flur UG Bewegung, die Auslöserliste den passenden Countdown. Nach Ablauf
verschwanden Bewegungsbeschriftung und Countdown bei derselben Browserbeobachtung,
und der Kreis wechselte zu LVL 1. Dort erschien wieder Überwachungsrisiko 1/3;
das war kein verbleibender Erkennungsgrad. Der Sensor stand abschließend Aus.
Während des Laufs gab es keine überlagernden Erkennungen.

**Zeitmessung, noch keine abgenommene LVL-3-Zeitvorgabe:** Die Erkennung erhielt
ihre Ablaufzeit 60 Sekunden nach dem An-Signal, nicht nach dem Aus-Signal.
Dieses Verhalten wurde beobachtet und darf nicht als bereits vereinbarter Sollwert
ausgegeben werden. Der genaue Farbverlauf beim Ausblenden wurde in diesem Lauf
nicht vermessen. Weitere Innenraumfolgen und Eskalationen bleiben gesondert
festzulegen; LVL 4/5 bleiben gesperrt.

Lokaler Messbeleg: `.ha-test/level3-flur-ug-20261020T122858Z.json`, einschließlich
Browserbeobachtungen und tatsächlicher Impulszeiten.

## Vereinbarte LVL-3-Sollfälle und vollständiger Simulationslauf

Nach dem Einzelmelder-Test bestätigte der Nutzer 1/3 als ersten Hinweis ohne
bestätigte Erkennung. Anschließend wurden diese Erwartungen gemeinsam festgelegt;
der Nutzer beauftragte danach deren Simulation, um passende und fehlende Logik
zu unterscheiden. Die Erwartungen stehen vor den Läufen fest:

| Fall | Meldungen noch innerhalb ihres Zeitfensters | Erwartete Grade nach jedem Impuls |
| --- | --- | --- |
| L3-verbunden | Flur UG Flur → Büro hinten → Flur UG Treppe, drei unabhängige Geräte im selben/direkt verbundenen Bereich | 1/3 → 2/3 → 3/3 |
| L3-zwei-Bereiche | Flur UG Flur → Büro hinten → Elternbad Raum → Dusche; Flur UG/Büro und Elternbad/Dusche sind getrennte verbundene Paare | 1/3 → 2/3 → 2/3 → 3/3 |
| L3-gleicher-Raum | Büro hinten → Büro vorne, zwei unabhängige Geräte | 1/3 → 2/3 |
| L3-unverbunden | Flur UG Flur → Elternbad Raum, keine direkte Verbindung | 1/3 → 1/3 |
| L3-Wiederholung | Flur UG Flur zweimal, zwei echte An-/Aus-Impulse desselben Geräts | 1/3 → 1/3 |

Die Zwischenstufe im Fall L3-zwei-Bereiche prüft ausdrücklich zwei zusammenhängende
Melder plus einen entfernten Einzelmelder: Der Einzelmelder vervollständigt keine
3/3. Erst die unabhängige Bestätigung auch im zweiten Bereich ergibt gemeinsam
3/3. Das ist ein verdächtiges Muster, kein Beweis für zwei Personen.

LVL bleibt während gültiger Innenmeldungen 3, auch bei 3/3; LVL 4/5 bleiben
gesperrt. Nach vollständigem Rücklauf wird ohne andere Erkennungen LVL 1 erwartet.
Jede Quelle hat zwei Sekunden Zielzeit und anschließend zehn Sekunden Abstand
zum nächsten Impuls. Der nächste Fall beginnt erst nach sauberem Rücklauf.
Attribute erhalten, alle ausgelösten Quellen abschließend Aus prüfen.

Die Konfiguration hat quiet_seconds=60. Exakte LVL-3-Timersemantik (An- oder
Aus-Zeitpunkt, Einzelablauf oder schrittweiser Abbau) ist noch nicht eigens
abgenommen und wird als Messung dokumentiert. Erwartete Grade werden unabhängig
von der aktuellen Implementierung geprüft. Backend und bestehende Browseranzeige
werden getrennt beobachtet; echte überlagernde Ereignisse machen einen Lauf nicht
eindeutig. Keine Produkt-, Konfigurations- oder UI-Änderungen für diese Simulation.

### Ergebnis des vollständigen LVL-3-Laufs vom 20. Oktober 2026

| Prüfung | Soll | Tatsächlich in Backend und Browser | Ergebnis |
| --- | --- | --- | --- |
| Ein unabhängiger Innenmelder | 1/3 | 1/3 | passt |
| Zwei unabhängige Melder in direkt verbundenen Räumen | 2/3 | 2/3 | passt |
| Drei unabhängige Melder im selben/direkt verbundenen Bereich | 3/3 | 3/3 | passt |
| Zwei verbundene Melder plus ein entfernter Einzelmelder | 2/3 | 2/3 | passt |
| Zwei getrennte verbundene Paare | 3/3 | **2/3** | **Abweichung: gemeinsame Bewertung fehlt** |
| Zwei unabhängige Melder im selben Raum | 2/3 | 2/3 | passt |
| Zwei unverbundene Einzelmelder | 1/3 | 1/3 | passt |
| Derselbe Melder zweimal | 1/3 | 1/3 | passt; zweiter Impuls erneuert Ruhezeit |

**Fehlende Funktion:** Flur UG/Büro erreichten gemeinsam 2/3. Elternbad allein
erhöhte diesen Grad korrekt nicht. Nach zusätzlicher Dusche hatten auch
Elternbad/Dusche 2/3, aber der globale Grad blieb bei 2/3. Erwartet war 3/3 wegen
zweier getrennter, jeweils unabhängig bestätigter Bereiche. Das ist keine reine
Darstellungsabweichung: Backend und sichtbarer Kreis blieben beide bei 2/3.
Alle vier Räume zeigten gleichzeitig Bewegung auf der Karte.

**Gemessener Rücklauf:** Nach dem letzten passenden An-Signal sank der Grad je
ruhiger Minute um einen Schritt. Die Dreierfolge fiel nach ungefähr 60 Sekunden
auf 2/3, nach 120 Sekunden auf 1/3 und nach 180 Sekunden auf LVL 1. Die Zweierfälle
benötigten ungefähr 120 Sekunden, Einzelmelder 60 Sekunden. Die Restzeiten in der
Auslöserliste zeigten dabei den verbleibenden gemeinsamen Nachlauf der jeweiligen
Raumgruppe, nicht die LVL-2-Einzelgültigkeit. Diese LVL-3-Timersemantik ist eine
Messung; die genaue gewünschte Zeitvorgabe bleibt gesondert abzustimmen.

Der Farbverlauf wurde zusätzlich anhand berechneter SVG-Füllfarben beobachtet:
vor dem letzten Ablauf Zwischenfarben, dann die normale türkisfarbene Füllung.
Beim beobachteten Endablauf verschwanden Bewegungsbeschriftung und Countdown
zusammen mit dem Rückfall des Kreises auf LVL 1. Der Browser wurde in Blöcken
beobachtet; eine exakte Zeitgleichheit aller Zwischenwechsel im Subsekundenbereich
ist damit nicht belegt. Bei LVL 1 erschien wieder das Überwachungsrisiko 1/3,
kein verbleibender Erkennungsgrad.

Alle Fälle begannen erst nach natürlichem, sauberem Rücklauf. Während der
eigentlichen Testfolgen und ihres Rücklaufs gab es keine fremden Erkennungen.
Die Impulse dauerten gemessen zwischen 1,987239 und 2,021764 Sekunden. Alle sechs
verwendeten Quellen standen abschließend Aus; Anlage weiterhin Abwesend/LVL 1,
alle Sensorzuordnungen freigegeben, LVL 4/5 gesperrt. Die gespeicherte Konfiguration
blieb unverändert. Die Roboter wurden nicht wieder gestartet.

Lokale Nachweise:

- `.ha-test/level3-matrix-20261020T124239Z.json`: Rohmessungen und vorab festgelegter Plan.
- `.ha-test/level3-matrix-20261020T124239Z-analysis.json`: Soll-/Ist-Vergleich,
  vollständiger natürlicher Rücklauf und gesonderte Browserbeobachtungen.

Methodischer Hinweis zum Rohprotokoll: Die automatischen `case_done`-Zwischenwerte
wurden bereits 65 Sekunden nach dem letzten Aus-Signal geschrieben. Das war bei
mehrstufigem Rücklauf noch kein endgültiger Abschluss. Die anschließende Wartephase
vor dem nächsten Impuls erfasste den restlichen Rücklauf. Deren alte Meldungen
sind im Rohfeld `unexpected` dem nächsten Fall zugeordnet, aber keine fremden
Ereignisse dieses Falls. Die Auswertung trennt deshalb die tatsächlichen Testfenster
und ordnet alle Quellen erneut dem zugehörigen Fall zu. Kein Zurücksetzen oder
Scharfschaltwechsel wurde verwendet, um einen Ausgangszustand zu erzwingen.

## Haustür: MACO-Schloss, Aqara-Kontakt und Innenbewegung

Der Nutzer beauftragte nach dem Bewegungsmelder-Lauf genau diese Folge:
MACO Haustürschloss → Kontaktsensor Haustür → Bewegung Flur UG. Alle drei
konfigurierten Quellen gehören zum Flur UG und haben unterschiedliche physische
Gerätekennungen. Jeweils zwei Sekunden Zielzeit und zehn Sekunden Pause nach Aus.
LVL 4/5 bleiben gesperrt, keine Konfigurationsänderung und kein Schalten des echten
Schlosses: Es werden ausschließlich die drei Sensorzustände simuliert.

Vor dem Lauf festgelegte Unterscheidung: Ein einzelner Türkontakt ist ein erster
Hinweis (1/3), zwei unabhängige tatsächliche Öffnungsbelege ergeben 2/3, ein dritter
passender unabhängiger Beleg 3/3. Reines Entriegeln ist kein zusätzlicher
Öffnungsbeleg. Der konkrete MACO ist in HA ein binärer Sensor mit device_class=lock
und in IQAlarm lock_contact/door_lock; ein eigener Öffnungszustand liegt an dieser
Quelle nicht vor. Daraus leitete der Assistent vor dem Lauf die strengere
Testannahme **kein Bestätigungspunkt → 1/3 → 2/3** ab und erläuterte sie gegenüber
dem Nutzer. Diese Annahme war keine ausdrücklich bestätigte Nutzervorgabe:
„Kein zusätzlicher Öffnungsbeleg“ legt nicht automatisch fest, dass ein
Schlosszustand überhaupt keinen Hinweis-Punkt erhalten darf.

Zu prüfen ist, ob der MACO bereits als bloßer Schlosszustand unterschieden wird
oder noch einen zusätzlichen Bestätigungspunkt erzeugt. Ein beobachtetes
1/3 → 2/3 → 3/3 widerspricht der strengeren Testannahme, belegt aber für sich
keinen bestätigten Produktfehler. Es zeigt die bestehende Zählung von drei
unabhängigen Geräten und beweist keine zweimal unabhängig erfasste Türöffnung.
Der Nutzer hat anschließend ausdrücklich bestätigt: Der MACO zählt wie ein
Bewegungsmelder als eigene Sensorquelle einen Hinweis-Punkt. Damit ist die
verbindliche Erwartung für diese konkrete Folge **1/3 → 2/3 → 3/3**. Die strengere
frühere Testannahme ist verworfen; die Rohmessung und ihre vorherige Erwartung
bleiben zur Nachvollziehbarkeit erhalten.

### Gemessenes Ergebnis der Haustür-Folge

Der vollständige Live-Lauf ergab MACO allein 1/3, nach zusätzlichem Aqara-Kontakt
2/3, nach Bewegung Flur UG 3/3. In allen Schritten blieb die Anlage auf LVL 3;
LVL 4/5 waren gesperrt. Damit funktioniert die Zählung dreier unabhängiger Geräte.
Die strengere Annahme kein Punkt → 1/3 → 2/3 wurde nicht erreicht; sie war jedoch
nicht als Nutzervorgabe bestätigt. Die zunächst berichtete „fehlende
Unterscheidung“ war deshalb eine zu strenge Bewertung des Assistenten und ist
hiermit korrigiert. Ein Punkt bedeutet erster Hinweis, keinen Vollalarm.

**Nachträgliche ausdrückliche Bestätigung der Vorgabe durch den Nutzer:**
„ja es ist eine zählung genau wie der bewegungsmelder ect“. Die gemessene Folge
1/3 → 2/3 → 3/3 entspricht damit der bestätigten Anforderung und ist für diese
Zählung bestanden. Jede unabhängige physische Quelle zählt einmal; mehrere
Entitäten desselben Geräts werden dadurch nicht zu mehreren Quellen. Es besteht
für diese Haustür-Zählung kein Änderungsbedarf. Die separate Abweichung bei zwei
getrennten bestätigten Melderpaaren bleibt offen.

Im Browser wurden nach dem Kontakt 2/3 und nach Bewegung 3/3 beobachtet. Die Karte
zeigte dabei „Öffnung erkannt: Schlossbetätigung“ und anschließend zusätzlich
Bewegung. Die Einordnung des Schlosszustands unter Öffnung ist ebenfalls erfasst;
an der Oberfläche wurde nichts geändert. Die MACO-Alleinphase 1/3 wurde im Backend
gemessen; die Browserbeobachtung begann erst nach dem Kontakt.

Danach erfolgte natürlicher Rücklauf 3/3 → 2/3 → 1/3 → LVL 1 ohne fremde Quellen.
Die gespeicherten Belege entfielen in der Reihenfolge MACO, Aqara-Kontakt, Bewegung.
Die gemessenen Impulse dauerten 1,989149 / 2,000565 / 2,027310 Sekunden.
Abschließend alle drei Quellen Aus, Anlage weiterhin Abwesend/LVL 1,
Konfigurationsrevision unverändert, LVL 4/5 gesperrt. Keine echten Schlossbefehle,
keine Installation und kein Neustart.

Lokaler Nachweis: `.ha-test/level3-haustuer-20261020T130050Z.json`, einschließlich
vorher festgelegtem Soll, Rohmessungen, Browserbeobachtungen und Endprüfung.

## Außen-/Innen-Zuordnung als Vorbereitung des weiteren Übergangs

Der Nutzer besprach folgenden späteren Ablauf: noch gültige LVL-2-Bestätigung 3/3
plus neue passende, überwachte und nicht ignorierte Fenster-/Türmeldung soll direkt
zu LVL 4 führen können. Hierfür fordert er eine räumliche Außen-/Innen-Zuordnung.
Er korrigierte ausdrücklich: **nicht je Kamera, sondern Außenraum zu Innenraum**.
Sein Bild zeigt als Beispiele Garten Büroseite → Büro, Vorgarten → Flur UG,
Garderobe und WC sowie Garagenhof → HWR.

Die lokal ergänzte Einstellung speichert diese gerichteten Bereichszuordnungen
unter `outside_inside_links`. Ein Außenraum kann mehrere Innenräume haben.
Auswahl über Räume & Grundriss → Außen → Innen oder durch Markieren der Flächen
im Grundriss-Assistenten. Die Zuordnung gilt als räumlicher Kontext für die
Kameras und Sensoren des Außenbereichs, nicht als zusätzliche physische Quelle.
Sie verändert keine Sensorrollen, Vorfeldzuordnungen, Profilfreigaben oder echten
Türen/Durchgänge (`room_connections`). Verbindungslinien erscheinen nur im Editor,
nicht in Vorschau oder Live-Anzeige. Die Beispielzuordnungen wurden in lokalen
Browserfixtures geprüft, nicht in die laufende HA-Konfiguration geschrieben.

Die ursprüngliche UI-/Konfigurationsarbeit bereitete nur die Zuordnung vor;
der direkte Übergang war zu diesem Zeitpunkt noch nicht implementiert.

### Vereinbarter Übergang von Außen-3/3 zu LVL 4

Nach dem Einrichten der neun Zuordnungen beauftragte der Nutzer den Übergang
und die Freigabe von LVL 4 für diesen Test. LVL 5 bleibt gesperrt. Der bestehende
Testhinweis in der Level-Konfiguration darf entsprechend angepasst werden;
zusätzliche UI-Elemente sind nicht beauftragt.

**Ergebnis des vollständigen Folgelaufs:** Siehe
[TESTERGEBNISSE-2026-10-20.md](TESTERGEBNISSE-2026-10-20.md).
21 unterschiedliche Funktionsfälle wurden geprüft: 20 erreichen das vereinbarte
Verhalten. Offen bleibt 2/3 statt 3/3 bei zwei getrennten bestätigten Paaren.
Der zusätzlich entdeckte Fehler wiederverwendeter abgelaufener Nachbarmeldungen
wurde korrigiert, installiert und durch dieselbe Live-Folge nachgeprüft.
Beide Innen-Eskalationen und der direkte Außen-/Innen-Übergang sind funktional
beobachtet; die Gegenfälle bleiben ohne unzulässige Eskalation. Die exakte
Zwei-Sekunden-Dauer war bei einer Kamera trotz Wiederholung nicht stabil
herstellbar und ist im Bericht als Einschränkung, nicht als bestandene Zeitprüfung
gekennzeichnet. Abschluss: Abwesend, LVL 1, keine Restmeldungen, Revision 410
unverändert, keine Test-Ausnahme aktiv, vorher off-Quellen wieder off. Das
bereits offene und ignorierte Fenster Flur OG bleibt in seinem Ausgangszustand.

Verbindliches Soll für den Übergang:

- Der Außen-Bestätigungsgrad muss **bereits vor** der neuen Kontaktmeldung noch
  gültige 3/3 erreicht haben. Eine vorherige Kontaktmeldung wird nicht rückwirkend
  durch spätere Kamerameldungen bestätigt.
- Mindestens ein tatsächlich zur 3/3-Bestätigung beitragender Außenbereich muss
  dem Innenraum direkt unter `outside_inside_links` zugeordnet sein. Eine bloß
  gleichzeitig laufende Einzel-PIR-Meldung ohne Bestätigungsanteil reicht nicht.
- Eine neue, überwachte Kontaktmeldung dieses Innenraums führt direkt zu LVL 4.
  Ein MACO-Schlosskontakt zählt dabei wie die andere unabhängige Kontaktquelle;
  reine Innenbewegung allein löst diesen besonderen Übergang nicht aus.
- Ignorierte, gesperrte, nicht verfügbare oder im Profil ausgeschlossene Quellen
  und derselbe physische Sensor als Außen- und Innenbeleg reichen nicht.
- Nur 2/3, bereits abgelaufene Außen-3/3, ein nicht passender Innenraum oder eine
  fehlende Bereichszuordnung führen nicht über diesen Weg zu LVL 4.
- Kein Übergang zu LVL 5, keine Vollalarm-Bestätigung und kein gespeicherter
  Daueralarm. Der nachträglich beauftragte Innenweg ist unten gesondert beschrieben.

Für diesen ersten LVL-4-Test wurde gegenüber dem Nutzer die vorhandene
LVL-3-Ruhezeit als vorläufiger Nachlauf benannt: aktuell 60 Sekunden ab der neuen
Kontaktmeldung. Unverändert aktive Zustände verlängern diesen Nachlauf nicht.
Ein später abfallender Außengrad entkräftet den bereits gültig entstandenen
Nachweis nicht sofort. Nach Ablauf fällt die Anzeige auf die noch gültige andere
Erkennung zurück. Das endgültige Verhalten von LVL 4 wird erst anschließend
gestaltet; dies ist keine bereits abgestimmte endgültige LVL-4-Zeitregel.

Vorgesehener erster Live-Fall: Garagendach → Fitnessraum. Drei getrennte
Personenmeldungen von `binary_sensor.garagen_dach_person` ergeben mit den
Standardschwellen 1/3 → 2/3 → 3/3 bei LVL 2. Danach neue Öffnung von
`binary_sensor.fenstersens_fitnessraum_contact` → LVL 4, niemals LVL 5.
Jeweils zwei Sekunden Zielzeit, zehn Sekunden Pause nach Aus. Vorher saubere
Ausgangslage und nicht ignorierten Kontakt prüfen. Gegenfälle separat mit
sauberem Ausgangszustand prüfen. Live-Ergebnisse sind noch **ungeprüft**.

### Nachtrag: Innen-3/3 erreicht LVL 4 nach 30 Sekunden oder weiterer Quelle

Der Nutzer ergänzt ausdrücklich einen zweiten Weg ohne vorherige Außenaktion:
Bleibt der gültige Innen-Nachweis bei 3/3, erfolgt nach **30 Sekunden ab dem
erstmaligen Erreichen von 3/3** der Übergang zu LVL 4. Ein weiterer unabhängiger
Innensensor nach Erreichen von 3/3 löst LVL 4 früher aus, ausdrücklich auch in
einem entfernten Raum. Begründung des Nutzers: Vier unabhängige Sensorquellen
sind bereits viele Meldungen. Wiederholungen der
bisherigen Quellen zählen dafür nicht als weiterer Sensor und starten die
30 Sekunden nicht neu. Fällt der gültige Nachweis vorher unter 3/3, entfällt
die alte Frist. Ein erneut gültiges 3/3 erhält seinen eigenen Beginn.

Die ausdrücklich gewünschte UI-Ergänzung ist eine rote Überlagerung des
vorhandenen äußeren Rings, die über diese 30 Sekunden vollläuft. Der bestehende
innere Bestätigungsring bleibt bei 3/3 voll. Für Darstellung und Auswertung gilt
derselbe Backend-Ablaufzeitpunkt einschließlich HA-/Browser-Zeitversatz. Kein
zusätzlicher Balken und keine zusätzliche Statuskarte.

Der schnellere Außen-/Innen-Weg bleibt erhalten. LVL 5 bleibt gesperrt. Die
gespeicherte Testgrenze bleibt deshalb bei LVL 4, der Testmodus bleibt an und
`promote_seconds` wird auf 30 gesetzt. Live-Ergebnisse dieses neuen Innenwegs
sind noch **ungeprüft**.

Installationsstand am 20.10.2026: Die Backend- und Frontend-Dateien wurden
direkt synchronisiert, HA wurde neu gestartet und die installierten Dateien
per SHA-256 mit dem lokalen Stand verglichen. Konfigurationsrevision 410:
`test_mode=true`, Testgrenze auf der vorhandenen LVL-4-Kennung,
`promote_seconds=30`, alle neun Außen-/Innen-Zuordnungen erhalten. Es wurden
ausschließlich Testgrenze und Verweildauer geändert. Nach vollständiger Rückkehr
aller zuvor verfügbaren Sensoren wurde Abwesend wiederhergestellt: LVL 1,
keine Störung, weiterhin nur das bereits offene Fenster Flur OG ignoriert.
Der vorhandene Testhinweis wurde in Chrome geprüft und zur Live-Anzeige
zurückgewechselt. Für diese Installation wurden noch keine Sensorimpulse
ausgelöst. 576 Python-Tests, 111 Frontend-Tests und 34 gezielte Browserfälle
bestanden; dazu gehört die Ringfüllung mit HA-Zeitversatz auf Desktop und Mobil.

## Ergebnis eines künftigen Laufs festhalten

### Lauf vom 20.10.2026: Wiederverwendung abgelaufener Nachbarmeldungen

Im vollständigen Folgelauf waren die Außenfälle A bis G erfolgreich. Nach dem
Innen-Einzelmelder Flur UG wurde dessen natürlicher Rücklauf bis LVL 1 abgewartet.
Der danach erstmals besuchte Büro-Raum zählte die alte Flur-Meldung trotzdem
erneut: Büro hinten ergab 2/3 statt 1/3, Büro vorne anschließend 3/3 statt 2/3.
Dadurch trat nach 30 Sekunden ein unberechtigtes LVL 4 ein. Die ursprüngliche
Sollvorgabe wurde nicht angepasst. Die Testfolge wurde vor weiteren Fällen
gestoppt; alle ausgewählten Testquellen standen bereits Aus.

Nachweise: `.ha-test/acceptance-20261020T140833Z.json` und gleichnamige JSONL-Datei,
`.ha-test/acceptance-replay-abort-state.json`, `.ha-test/acceptance-abort-note.json`.
Der ursprüngliche Runner meldete im LVL-0-Fall zusätzlich eine Testwarnung beim
absichtlichen Wieder-Scharfschalten auf LVL 1. Das war eine zu enge Obergrenze
des Messprogramms für die Wiederherstellungsphase, keine unerlaubte Eskalation:
während der ausgeschalteten Phase blieb die Anlage korrekt auf LVL 0.
Dieser Fall wird mit getrennter Bewertung der Wiederherstellung erneut geprüft.

Die Backend-Korrektur lässt einen erstmals besuchten Raum nur neue Meldungen
und noch gültige Belege bereits laufender Raumgruppen übernehmen. Bereits
verarbeitete, abgebaute Meldungen werden auch dort als verbraucht markiert.
Der Fehler wurde zuvor lokal reproduziert; danach bestanden die Regression
und Prüfungen für teilweise abgebaute, weiterhin gültige Nachbargrade.
Keine UI-Änderung. Die nachfolgenden Live-Prüfungen sind hiervon getrennt zu
protokollieren; eine lokal bestandene Regression ist noch keine Live-Abnahme.

Vor dem ersten Impuls Szenario A bis G, Sensortausch, Sollwerte und Anfangszustand
aufschreiben. Danach je Schritt Eingabe, gemessene Impulsdauer, Ablaufzeit,
beobachtetes LVL/Grad, Kartenanzeige und Countdown festhalten. Rohprotokolle mit
Datum unter `.ha-test/` speichern; keine Zugangsdaten oder privaten HA-Daten ins
Repository übernehmen.

Ein Lauf ist **bestanden**, wenn die vereinbarten Schritte einschließlich Rücklauf
und sichtbarer Anzeige geprüft wurden. Eine echte Überlagerung macht den
betroffenen Lauf **nicht eindeutig**; ein widersprechendes Verhalten ist eine
**Abweichung**. Eine nicht beobachtete Teilprüfung bleibt **ungeprüft**. Diese Fälle
nicht als Erfolg umdeuten. Zum Schluss alle Testquellen auf Aus prüfen und offen
gebliebene Test-Ausnahmen beziehungsweise Wiederherstellungen benennen.
## Nachprüfung: zwei getrennte bestätigte Innenbereiche

Der Nutzer beauftragte nach dem vollständigen Lauf die Korrektur der noch offenen
Zusammenführung. Verbindlicher Nachtest mit unveränderten Raumverbindungen:
Flur UG Flur → Büro hinten → Elternbad Raum → Dusche. Erwartet werden
**1/3 → 2/3 → 2/3 → 3/3**, jeweils LVL 3. Ein entfernter Einzelmelder genügt
also weiterhin nicht. Jede Quelle hat zwei Sekunden Zielzeit, danach zehn
Sekunden Pause bis zur nächsten Quelle. Die vier Quellen müssen von unabhängigen
physischen Geräten stammen; überlappende Belege zählen nicht doppelt.

Ab dem vierten Impuls gilt die bereits beauftragte Eskalation: Liegt die gemeinsame
3/3-Bestätigung ununterbrochen 30 Sekunden vor, folgt LVL 4. Ein weiterer neuer,
unabhängiger Innensensor darf vorher sofort LVL 4 auslösen, auch entfernt.
Wiederholungen der vier bereits beteiligten Geräte ersetzen diesen Zusatzbeleg
nicht und starten die 30 Sekunden nicht neu. Verliert ein Bereich seine gültige
Bestätigung vor Fristende, reicht er nicht mehr für den Timerweg.
LVL 5 bleibt gesperrt. Nach dem Lauf wird der natürliche Rücklauf bis LVL 1
abgewartet; alle vorher ausgeschalteten Quellen müssen wieder Aus sein.

Die Nachprüfung nutzt bestehende Anzeigen und Einstellungen. Für diesen Fix
werden keine neuen UI-Elemente oder Konfigurationsmöglichkeiten ergänzt.


**Ergebnis der gezielten Nachprüfung:** Nach Installation des Backend-Fixes wurde
obenstehende Vier-Melder-Folge am 20. Oktober 2026 erneut live durchgeführt.
Backend und bestehender Kreis zeigten 1/3 → 2/3 → 2/3 → 3/3; anschließend LVL 4
nach der 30-Sekunden-Frist. Natürlicher Rücklauf bis LVL 1, alle vier Quellen
wieder Aus, keine fremde Meldung, Konfiguration einschließlich Revision 410
unverändert, LVL 5 weiterhin gesperrt. Der historische fehlgeschlagene Lauf bleibt
oben dokumentiert. Einzelheiten und Rohbelege stehen unter „Nachprüfung nach dem
Fix der getrennten bestätigten Bereiche“ in TESTERGEBNISSE-2026-10-20.md.

## Neue Vorgabe ab 2.14.0: Alarm bleibt bestehen, LVL 5 nach Zeit

Auf ausdrücklichen Nutzerauftrag ersetzt der neue Alarmablauf nach Einrichtung
von `alarm_escalation` den bisherigen vorläufigen LVL-4-Nachlauf. Ab LVL 4 wird
nicht mehr auf natürliche Rückkehr zu LVL 1 gewartet: Der bestätigte Alarm bleibt
bestehen, bis die Anlage manuell ausgeschaltet wird. Ohne Ausschalten folgt
standardmäßig 300 Sekunden nach dem ersten LVL-4-Erreichen LVL 5. Weitere
Sensoren starten diese Frist nicht neu; ruhige, nicht verfügbare oder abgelaufene
ursprüngliche Quellen löschen sie nicht. LVL 5 besitzt keine Sensorregeln.
Der Timer und die Alarm-ID müssen einen HA-Neustart unverändert überstehen.

Bei LVL 4 füllt sich der vorhandene innere Ring über diese Zeit. Die rote
Überlagerung des äußeren Rings läuft ebenfalls mit. Statt x/3 wird die Restzeit
bis LVL 5 gezeigt. Keine zusätzliche Statuskarte oder weiterer Balken.

Externe Überwachung ist standardmäßig Aus. Bei Aktivierung wird die System-ID
mit eigenem geheimem Zugang extern registriert/aktiviert. Ein LVL-4-Alarm erhält
eine eigene Alarm-ID. Dessen erste extern bestätigte Frist darf durch doppelte
Startmeldungen nicht verlängert werden. Eine passende manuelle Aufhebung beendet
sie; bloßer Verbindungsverlust nicht. Nach Serverneustart muss eine überfällige
nicht aufgehobene Frist genau ein Eskalationsereignis erzeugen. Andere IDs dürfen
den Alarm weder lesen noch quittieren. Folgeaktionen sind zunächst unkonfiguriert.

Für den Aufbau wurden keine weiteren HA-Sensorimpulse ausgeführt. Die neue
Timerlogik wurde mit kontrollierter Zeit im Engine-Test und mit isolierten
Diagnose-IDs im tatsächlichen externen LXC geprüft. Ein späterer Live-Test der
Anlage benötigt einen eigenen angekündigten Ablauf mit manuellem Ausschalten;
der alte Runner mit natürlichem LVL-4-Rücklauf passt für diesen neuen Ablauf nicht.


## Live-Nachprüfung am 21.10.2026: bis LVL 5, externe Überwachung aus

Nutzerauftrag: vollständiger Live-Ablauf bis LVL 5 bei durchgehend erreichbarem
Home Assistant; ausdrücklich ohne externe Überwachung und ohne Abrisssimulation.
Vorab angekündigtes Soll: Garagenhof-Bewegung → LVL 2 ohne Bestätigungsgrad,
Person Büro → 1/3, Person Terrasse → 2/3, Person Garagendach → 3/3;
neuer Fitnessraumkontakt mit vorhandener Zuordnung Garagendach → Fitnessraum
löst direkt LVL 4 aus. Danach unveränderte 300 Sekunden bis LVL 5, anschließend Aus.

Backend-Ergebnis: alle genannten Level und Grade erfüllt. Alarm-ID und Deadline
blieben unverändert. LVL 5 wurde erstmals nach 301.551 Sekunden beobachtet
(Abfrageintervall etwa zwei Sekunden; keine Behauptung über den exakten
Umschaltzeitpunkt). Die konfigurierte Frist betrug genau 300 Sekunden.
Anschließend manuell über den normalen Ausschaltbefehl deaktiviert: LVL 0,
kein gespeicherter Alarm, alle fünf Testquellen wieder off. Konfiguration gegenüber
dem Beginn unverändert. Externe Überwachung durchgehend aus, keine ausstehenden
externen Meldungen und keine SMS beauftragt oder versendet.

Dieser Lauf prüft den direkten Außen-/Innen-Weg und den lokalen Fünf-Minuten-Timer.
Er ersetzt weder einen separaten LVL-3-Innenlauf noch eine Prüfung externer
SMS-Zustellung oder einen Ausfalltest. Die sichtbare Oberfläche wurde in diesem
Lauf nicht unabhängig automatisiert geprüft; Backendwerte sind kein visueller
Nachweis der Ringanimation. Private Messdaten: `.ha-test/full-chain-20261021.json`.


## Neue Vorgabe am 21.10.2026: Außen-3/3 gibt einen Innen-Zusatzpunkt

Auf Nutzerauftrag gilt bei weiterhin gültigem Außen-Bestätigungsgrad 3/3:
Die Innenbewertung erhält genau einen zusätzlichen Bestätigungspunkt, auch
wenn der Innenraum keinem beitragenden Außenbereich zugeordnet ist. Der Bonus
allein erzeugt keine Innenmeldung und kein LVL 3. Bei Standardschwelle 1 gilt:

| Innenmeldungen bei Außen-3/3 | Erwartung |
| --- | --- |
| Keine Innenmeldung | Weiter LVL 2, außen 3/3 |
| Ein unabhängiger Innensensor | LVL 3, innen 2/3 |
| Zweiter passender unabhängiger Innensensor im selben/direkt verbundenen Bereich | LVL 3, innen 3/3 |
| Zwei unverbundene Einzelmelder | Jeweils innen 2/3, keine gemeinsame 3/3-Bestätigung |
| 30 Sekunden durchgehend innen 3/3 | LVL 4 |
| Nach innen 3/3 ein weiterer unabhängiger Innensensor, auch entfernt | Sofort LVL 4 |

Der direkte Weg Außen-3/3 plus neuer zugeordneter Innenkontakt bleibt unverändert
LVL 4. Ohne Außen-3/3 gilt die bisherige Innenkette einschließlich der getrennten
bestätigten Paare. Wiederholungen desselben Innenmelders erhöhen den Grad nicht.
Derselbe physische Sensor darf nicht als Außenbeleg und Innen-Zusatzpunkt zählen.
Eigene Empfindlichkeitsschwellen bleiben wirksam; der Außenanteil erhöht den
bereits vorhandenen Innen-Basisgrad um höchstens eins, maximal auf 3/3.

Läuft Außen-3/3 vor Ende der 30 Sekunden ab oder wird sein Beleg ungültig,
entfällt der Zusatzpunkt und eine davon abhängige Eskalationsfrist wird verworfen.
Erreicht die Außenbestätigung erst später 3/3, beginnt die Innen-3/3-Frist frühestens
dann; keine rückwirkende Anrechnung der Zeit. Ein bereits bestätigter und
gehaltener LVL-4-Alarm wird durch das spätere Auslaufen des Bonus nicht aufgehoben.

Prüfstand: lokal durch Engine-Tests geprüft; noch keine Installation und kein
HA-Live-Lauf dieser Erweiterung. Keine UI-Texte, Bedienelemente oder Einstellungen
wurden für die neue Bewertung ergänzt oder geändert.


## Live-Nachprüfung am 21.10.2026: LVL 2 mit Cooldown und Innenfälle A/B/C

Alle vier vorab angekündigten Funktionsfälle wurden auf Nutzerauftrag mit dem
installierten Außenbonus geprüft. SHA-256 von automatic_detection.py und
correlation_engine.py auf der HA-Instanz stimmten vor dem Lauf mit dem lokalen
Stand überein. Externe Überwachung blieb deaktiviert; keine Konfigurationsänderung.

| Fall | Soll | Beobachtet | Ergebnis |
| --- | --- | --- | --- |
| LVL 2: Garagenhof, Person Büro, Terrasse, Garagendach | 0/3 → 1/3 → 2/3 → 3/3, danach 2/3 → 1/3 → LVL 1 | genau diese Folge | Funktions-Soll erreicht |
| A: ohne Außenbestätigung, Flur UG → Büro → Flur UG/Treppe | innen 1/3 → 2/3 → 3/3; nach 30 Sekunden LVL 4 | genau diese Folge | Funktions-Soll erreicht |
| B: dreimal Person Garagendach, dann dieselbe Innenfolge ohne passende Außen-/Innen-Zuordnung | innen 2/3 → 3/3 → durch dritten Innenmelder sofort LVL 4 | genau diese Folge | Funktions-Soll erreicht |
| C: dreimal Person Garagendach, dann Fenster Fitnessraum | direkter Übergang Außen-3/3 → LVL 4 | genau dieser Übergang | Funktions-Soll erreicht |

B prüft ausdrücklich den Zusatzsensorweg nach Innen-3/3, nicht zusätzlich dessen
30-Sekunden-Weg. Flur UG/Büro sind untereinander verbunden, aber nicht als
Innenziel des beitragenden Garagendachs zugeordnet. In C ist die Zuordnung
Garagendach → Fitnessraum vorhanden. Nach jedem bestätigten Alarm wurde regulär
ausgeschaltet und vor dem nächsten Fall sauber scharfgeschaltet. LVL 5 wurde
für diese Fälle nicht abgewartet.

A: gespeicherter Alarmbeginn lag 30.090 Sekunden nach Innen-3/3. Die 17 Impulse mit Zielzeit zwei Sekunden dauerten gemessen 0.241 bis 2.023 Sekunden.
Bei LVL 2 wurden die Rückfälle gegenüber den zuvor publizierten Backend-Ablaufzeiten beobachtet:

| Neuer Grad | Erste Beobachtung minus publizierte Ablaufzeit |
| --- | --- |
| 2/3 | +0.441 Sekunden |
| 1/3 | +0.301 Sekunden |
| 0/3 | +0.165 Sekunden |

Diese Messung beschreibt Backendstatus bei regelmäßigen Abfragen; sie belegt
keinen exakten Browser-Umschaltzeitpunkt und keine visuelle Ring-/Fade-Animation.
Es wurde keine zusätzliche Toleranzgrenze erfunden. Abschluss: Abwesend, LVL 1,
kein Innen- oder Außen-Bestätigungsgrad, alle acht Testquellen wieder off,
Konfiguration einschließlich Revision unverändert, externe Überwachung aus.
Private Rohdaten: `.ha-test/abc-live-20261021.json` und `.jsonl`.

**Einschränkung der Impulsdauer:** Beim LVL-2-Lauf endete Person Büro nach
1,404 Sekunden; im C-Lauf endete die zweite Garagendach-Personenmeldung nach
0,241 Sekunden. HA meldete die Zustandsänderung vor dem geplanten Aus-Befehl.
Die genaue Ursache wurde nicht bestimmt. Deshalb sind diese beiden Impulse
kein bestandener Nachweis einer vollständigen Zwei-Sekunden-Dauer. Die
angekündigten Funktions-Sollwerte der Level/Grade wurden trotzdem beobachtet;
Funktionsresultat und Dauerprüfung werden ausdrücklich getrennt bewertet.

## Lichtschalter: vereinbarte Eingänge, noch kein Live-Nachweis (21.10.2026)

Der Nutzer meint erkannte Tastendrücke bzw. den physischen Schaltereingang,
keine geschalteten Lampen oder Relais. Seine Beispiele:

- `event.hue_wall_switch_module_14_button_1`: neues `initial_press`.
- `binary_sensor.licht_flur_og_input_0_input`: Wechsel des physischen Eingangs.
- MQTT-Gerät `bd3c8cf65bec9038a01fe8a92b811feb`, Aktion `single_left`.

Sollwerte für einen später ausdrücklich beauftragten Test: Nach Ablauf der
Startverzögerung, ohne weitere Belege, erzeugt eine solche Betätigung innen
LVL 3 mit 1/3. Der Eingangsimpuls läuft 15 Sekunden; Bestätigungsgrad und
Kartenanzeige folgen anschließend den vorhandenen Bewertungs-/Cooldownregeln.
Wiederholungen oder mehrere Tasten desselben Geräts ergeben keine zusätzlichen
unabhängigen Quellen. Hue-Release-/Repeat-Ereignisse und ein beim Start bereits
gespeicherter Ereigniszeitstempel sind keine neuen Tastendrücke. Ein bereits
eingeschalteter physischer Eingang erzeugt erst beim nächsten Wechsel einen Impuls.
Änderungen an `light.*` oder `switch.*` erhöhen den Grad nicht.

Diese Fälle sind lokal mit nachgebildeten HA-Ereignissen geprüft. Kein
Tastendruck und keine Ausgangsschaltung wurden hierfür produktiv ausgelöst.
