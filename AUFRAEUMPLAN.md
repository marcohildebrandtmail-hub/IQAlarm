# Aufräumen der IQAlarm-App · 13 freigegebene Punkte

Stand: 21. Oktober 2026. Umsetzung für Version 2.15.0, noch nicht auf der
produktiven HA-Instanz installiert. Punkt 6 wurde mit konkretem Vorschlag separat
freigegeben. Weitere Änderungen an „Profile & System“ bleiben für später offen.

| Nr. | Freigegebene Änderung | Stand |
| --- | --- | --- |
| 1 | Fenstergriff-Information unter die Live-Grundriss-Karte verschieben | umgesetzt |
| 2 | Grundriss-Kopfzeile samt Auswahl/Bedienung als Fußzeile im selben Kasten | umgesetzt |
| 3 | Startverzögerung unter LVL 1, Standard 60 Sekunden, vorhandener roter Ring | umgesetzt |
| 4 | Statistikzeile ganz nach unten | umgesetzt |
| 5 | Separate Raumkacheln unter „Räume & Grundriss“ entfernen, Räume behalten | umgesetzt |
| 6 | Grundriss-Assistent: globale Werkzeuge einmal oben, Raum-/Zeichenwerkzeuge einmal bei der Zeichnung, doppelte Hinweistasten entfernen | umgesetzt nach Freigabe |
| 7 | Fünf Anzeige-/Animationsschalter entfernen; bisherige Werte behalten | umgesetzt |
| 8 | Nachlaufzeit „Kürzlich“ unter „Kameras & Sensoren“ | umgesetzt |
| 9 | Präsenz/mmWave, Glas/Vibration, Panik und Rauch/Gefahr aus der Sensorartauswahl entfernen | umgesetzt; gespeicherte ältere Rollen bleiben für Importkompatibilität lesbar |
| 10 | Lichtschalter als unabhängige Innenquelle; nach Punkt 11 als Bewegung bei Betätigung/Zustandswechsel | korrigiert: echte Tastenereignisse, physischer Binäreingang oder MQTT-Geräteaktion; keine Lampen-/Relaiszustände |
| 11 | Listen: Kameras, Bewegung außen, Bewegung innen, Kontakte, Kontakt-/Lichtschalter als Bewegungstrigger | umgesetzt; Schlösser/Fensterinformationen bei Kontakten |
| 12 | Je Level „Was soll passieren?“; optionale Aktionen beim Level bzw. 1/3, 2/3, 3/3 bei Leveln mit Bestätigungsgrad | umgesetzt; bestehende Freigaben/Alarmmodi bleiben wirksam |
| 13 | Aktionskonfiguration aus „Profile & System“ entfernen | umgesetzt; dortige übrige Einstellungen bleiben bestehen |

Sensormeldungen bei ausgeschalteter Anlage führen keine Alarmaktionen aus.
Neu beauftragt: Explizite LVL-0-Aktionen laufen einmal beim Deaktivieren, nachdem
die alten Alarm-Ausgänge beendet sind. Beispiel: ein grünes Licht für die
eingestellte Dauer. Die Profilzuordnung bezieht sich auf das vorher aktive Profil.
LVL-1-Aktionen beim Aktivieren können während der Startverzögerung das Haus
vorbereiten; nur die Sensorbewertung wartet. Ein zweiter Start derselben
Aktivierungsaktionen am Ende der Verzögerung findet nicht statt.
Die 60-Sekunden-Verzögerung ist eine neue globale Vorgabe und wird nicht mit
alten Ausgangszeiten einzelner Profile addiert. Frühere Sensor-Testfälle setzen
diese neue Wartezeit explizit auf null, damit weiterhin dieselbe Meldefolge geprüft
wird; eigene neue Tests prüfen die reale Voreinstellung, Timer und Wiederanlauf.

## Neue Liste: Profile & System (21.10.2026)

Zunächst sammeln; noch nicht umgesetzt.

1. Den Schalter „Automatische Erkennung in diesem Alarmmodus“ entfernen.
   Die automatische Erkennung bleibt fest aktiviert und ist pro Alarmmodus
   nicht mehr abschaltbar. Bei der Umsetzung auch bisher gespeicherte
   ausgeschaltete Werte berücksichtigen, damit kein unsichtbar deaktivierter
   Zustand zurückbleibt. Der Hauptschalter für Alarmreaktionen bleibt davon
   unberührt.

2. Den Schalter „Öffnungs-, Schloss- und Vibrationssensoren berücksichtigen“
   entfernen. Zugeordnete und freigegebene Sensoren dieser Arten werden fest
   berücksichtigt. Bei der Umsetzung bisher ausgeschaltete Profilwerte
   übernehmen bzw. auf aktiv setzen, damit keine unsichtbare Sperre bestehen
   bleibt. Individuelle Sensorfreigaben bleiben erhalten.

3. Die Auswahl „Innenbewegung auswerten“ entfernen und fest „Immer“ verwenden.
   Bei der Umsetzung bestehende Profilwerte „Ignorieren“ bzw. „Erst nach
   Öffnung“ entsprechend umstellen, damit keine unsichtbare Einschränkung
   zurückbleibt. Individuelle Sensorfreigaben und Roboter-Ausnahmen bleiben
   erhalten.

4. „Räume und Sensoren begrenzen“ dauerhaft offen anzeigen und die
   Klappfunktion entfernen. Die vorhandenen Einstellungen bleiben erhalten.

5. Den gesamten Bereich „Verwendete Levelregeln“ einschließlich Erklärung
   und Auswahl je Level entfernen. Die gemeinsam festgelegte Alarmkette gilt
   fest; Profile dürfen sie nicht durch eine Regelauswahl einschränken oder
   verändern. Bei der Umsetzung bestehende profilbezogene Regelfilter
   entsprechend bereinigen, ohne alte Regeln als neue Alternative zur
   festgelegten Alarmkette zu reaktivieren.

6. Den gesamten Kasten „System“ entfernen, einschließlich Live-Status-Schalter,
   „Scharfschaltprüfung & Diagnose“, „Kamera-Aufbewahrung & Entprellzeiten“
   und „System speichern“. Umfang ausdrücklich bestätigt. Zusätzlich
   Kamerabild-Aufnahme und -Speicherung entfernen: IQAlarm soll keine Bilder
   von Kameras erstellen oder speichern. Das Entfernen der Einstellungen
   bedeutet nicht, die bestehenden Schutzprüfungen oder das Entprellverhalten
   abzuschalten.

## Native HA-Profile (21.10.2026)

Direkt beauftragt und lokal umgesetzt, noch nicht installiert:

- Standardprofile in Reihenfolge Nacht, Abwesend, Urlaub, Besuch samt passenden
  Symbolen. Vorhandene eigene Profile und Einstellungen bleiben bestehen.
- Native HA-Tasten: Zuhause → Besuch, Nacht → Nacht, Abwesend → Abwesend,
  Urlaub → Urlaub. Zustand und Bedienung verwenden dieselbe feste Zuordnung.
- „Benutzerdefiniert“ aktiviert genau das unter „Profile & System → Home
  Assistant“ ausgewählte Zusatzprofil; keine Auswahl bedeutet keinen Ersatz.
- Zuordnungen werden über Profil-IDs gespeichert und bleiben beim Umbenennen,
  Sortieren und Neustart erhalten. Entfernte Profile verlieren ihre Verknüpfung.
- Die sechs oben gesammelten Aufräumpunkte bleiben separat vorgemerkt.

## Prüfung

Nachtrag Dashboard-Karte (21.10.2026): Kompakte, ausdrücklich ohne Bedientasten
beauftragte IQAlarm-Karte mit dem bestehenden Ring, Profilstatus, Bestätigungsgrad
und Timern. Geteilte Darstellungsfunktionen mit dem Panel; bei Verbindungsverlust
keine veraltete Sicherheitsanzeige. Automatisch als HA-Frontend-Modul registriert.
Nur lokal vorbereitet; kein produktives Dashboard geändert und nicht installiert.
721 Python-Tests, 138 Frontend-Funktionstests und 60 lokale Browserfälle
bestanden (11 Kartenfälle sowie 49 bestehende Live-/Aufräumfälle). Geprüft sind
helle/dunkle und schmale Darstellung, Timer mit Serverzeit, Wiederverbindung,
fehlende Berechtigung, begrenzte Wiederholversuche und sauberes Abmelden.
Lokale Vorschau geprüft; Installationspaket 2.15.0 aktualisiert.

Nachtrag native HA-Profile (21.10.2026): 721 Python-Tests, 132 Frontend-
Funktionstests und 29 lokale Browserfälle bestanden. Geprüft sind exakte
Profilauswahl aller fünf nativen Befehle, Statusmeldungen, Umbenennen/Sortieren,
gespeicherte Zuordnungen, entfernte/deaktivierte Ziele, Scharfschaltblocker,
Profilwechsel und PIN-Prüfung. Der Zusatzprofil-Selektor ist auf Desktop und
Handy geprüft. Kein HA-Live-Schalten und keine Installation.

Nachtrag Deaktivierungsaktionen (21.10.2026): 705 Python-Tests, 131 Frontend-
Funktionstests und 27 lokale Browserfälle bestanden. Geprüft sind einmalige
Ausführung, Farbe und Dauer, Herkunftsprofil, Reihenfolge nach Alarm-Abschaltung,
unveränderte Meldungen bei Aus, Beobachtungsablauf und schnelles Wiedereinschalten.
Der neue LVL-0-Editor ist auf Desktop und Handy geprüft. Keine produktive
Lichtschaltung, keine SMS und keine Installation für diesen Test.

Nachtrag einfacher Hinzufügen-Dialog (21.10.2026): vier sichtbare Felder für
HA-Sensor, IQAlarm-Name, Behandlung und Raum/Außenbereich. Technische Werte werden
aus HA übernommen bzw. mit den bestehenden Standards gesetzt. Kategorien bleiben
voreingestellt; bekannte Gerätebereiche werden als Raum vorgeschlagen.
698 Python-Tests, 131 Frontend-Funktionstests und 25 lokale Browserfälle bestanden.
Darunter Eingabe und Speicherung für alle fünf Kategorien auf Desktop/Handy und
die drei physischen Schalterquellen. Noch keine Installation.

Nachtrag Raumwechsel (21.10.2026): Sensoreinstellungen einschließlich alter
Sensorarten werden vollständig beibehalten; nur eine ausdrücklich ausgewählte
andere Art wird umgestellt. 126 Frontend-Funktionstests und 23 lokale Browserfälle
bestanden, einschließlich 16 Fälle zum Speichern/Verschieben/Sortieren und zum
Sensor-Editor mit den vier alten Sensorarten. Noch keine Installation.

Nachtrag Lichtschalter-Korrektur (21.10.2026): 698 Python-Tests, 115
Frontend-Funktionstests und 27 gezielt ausgeführte Browserfälle bestanden.
Dabei wurden alle drei genannten Eingangsformen über die vorhandene
Sensorauswahl gespeichert; Ausgangszustände stehen dort nicht als Eingänge.
Die nachfolgende Liste dokumentiert den ursprünglichen Aufräumstand.

- 682 Python-Tests bestanden, darunter Startverzögerung, Neustart/Abbruch,
  Lichtschalter, Grad-Aktionen und deren Profil-/Startverzögerungsgrenzen.
- 114 Frontend-Funktionstests bestanden.
- 40 eigenständige Browserfälle für Desktop und Handy bestanden.
- Ruff und JavaScript-Syntaxprüfung bestanden.
- Drei weitere bestehende Browserfälle mit lokalem HA-Core-Testserver waren
  nicht ausführbar, weil auf 127.0.0.1:18123 kein HA-Testserver lief. Sie werden
  nicht als bestanden gezählt. Die produktive HA-Instanz wurde dafür nicht benutzt.
- Ansichten anhand lokal gerenderter Browserbilder geprüft; kein HA-Live-Test,
  keine SMS, kein Neustart und keine Änderung der produktiven Konfiguration.
