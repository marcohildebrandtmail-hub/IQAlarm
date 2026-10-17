# IQAlarm

**Erst verstehen, dann auslösen.** IQAlarm ist eine lokale Home-Assistant-Integration mit räumlicher Sensor-Korrelation, Prell-Schutz und eigenem deutschen Seitenpanel. Das Panel wird direkt als ES-Modul ausgeliefert. Auf dem Home-Assistant-System sind weder Node.js noch ein Frontend-Build nötig.

## Frei konfigurierbare Alarmstufen

Die folgenden vier Stufen sind Startvorgaben. Unter **Profile & System → Alarmstufen** lassen sich 1–32 Stufen mit eigenen Namen und Farben festlegen. Die Reihenfolge bestimmt die Zahl im Kreis; die Bezeichnung steht darüber. Jedes Profil ordnet die Ereignisarten seinen Stufen zu. Aktionen verweisen auf feste Stufenkennungen, sodass Umbenennungen keine Zuordnungen lösen. Vor dem Entfernen einer verwendeten Stufe müssen Regeln und Aktionen umgestellt werden.

| Stufe | Bedeutung | Standardlogik |
| --- | --- | --- |
| 0 | Sicher | Keine frischen Sicherheitssignale |
| 1 | Vorfeld | Person-/Perimeter-Erkennung; Gedächtnis standardmäßig 180 s |
| 2 | Verdacht | Einzelkontakt oder unbestätigte Bewegung; Korrelation standardmäßig 60 s |
| 3 | Bestätigter Alarm | Zwei unabhängige, zeitlich und räumlich passende Quellen oder ausdrücklich freigegebener Override |

Bestätigte Stufen können bis zum Ausschalten gehalten werden. Unbestätigte Ereignisse laufen nach ihrem Zeitfenster aus. Sirenen, freie Schalter-/Skriptaktionen, TTS und kritische Pushs sind nur bei Bestätigung und ausdrücklich freigegebener Stufe erlaubt. Stufe 0 ist immer der lautlose Normalzustand. Prellen und Einzelsignale dürfen keiner bestätigungspflichtigen Stufe zugeordnet werden.

### MACO-/Kontakt-Prellen

Öffnungs-, Riegel- und Vibrationssensoren werden standardmäßig ab drei echten Zustandswechseln innerhalb von 15 Sekunden isoliert, wenn keine unabhängige Bestätigung vorliegt. `on → off → on` bei anfänglichem `off` sind drei Wechsel. Wiederholte identische Werte, `unknown` und `unavailable` zählen nicht als Wechsel.

Ein isolierter Sensor liefert keine Einbruchsbestätigung mehr. Die Quarantäne bleibt bis zum Entschärfen oder einer bewussten Freigabe erhalten, auch nach einem Neustart. Sie wird im Cockpit angezeigt und kann eigene lautlose Diagnoseaktionen auslösen. Ein zuvor unabhängig bestätigter Vollalarm wird durch spätere Kontaktwechsel nicht gelöscht.

Die optionale Mindest-Aktivzeit filtert kurze Impulse, während die Prell-Erkennung weiterhin die ungefilterten Wechsel beobachtet. Werte pro Sensor überschreiben die Vorgabe der Rolle; `0` verwendet die Rollenvorgabe.

### Räumliche Bestätigung

- Vorfeld + Öffnung: nur vor dem zugeordneten Raum; ein globales Vorfeld gilt für das gesamte Haus.
- Öffnung + Innenraum: im selben Raum oder optional in einem direkt angrenzenden Raum. Eine Verbindung gilt in beide Richtungen, ohne transitive Weitergabe über mehrere Räume.
- Zwei Öffnungssensoren: im gesamten Haus innerhalb des Korrelationsfensters.
- Zwei Innenraumsensoren: bei aktivierter Profilregel innerhalb des Korrelationsfensters.
- Mehrere Entitäten desselben physischen Sensors müssen dieselbe **Signalquellenkennung** erhalten. Eine Quelle kann sich niemals selbst bestätigen.

Kamera und Öffnung werden auch in umgekehrter Reihenfolge berücksichtigt, solange beide Ereignisse noch in ihrem jeweiligen Zeitfenster liegen.

## Unabhängige IQAlarm-Profile

Profile haben freie Namen und definieren die gesamte Steuerung. Es gibt **keine Zuordnung zu HA-Modi**. Zuhause, Nacht, Abwesend und Urlaub sind bearbeitbare und löschbare Startvorgaben; selbst ihre Kennungen bestimmen keine Regeln.

Jedes Profil legt unabhängig fest:

- Räume und Sensoren (gemeinsame Schnittmenge), erlaubte Aktionen und eigene Timer.
- Vorfeld und Kontakte auswerten oder nur live anzeigen.
- Bewegung immer, erst nach Öffnung oder nur live anzeigen. Eine Bewegungsfreigabe kann auf betroffene Räume oder das Haus begrenzt werden; die räumliche Bestätigung bleibt erforderlich.
- Welche Kombinationen bestätigen und auf welche eigene Alarmstufe sie führen.
- Ob Reaktionen und Anwesenheitssimulation erlaubt sind.

Bei „erst nach Öffnung“ zählt eine frühere Bewegung nicht rückwirkend. Bereits aktive Präsenz erzeugt keine künstliche Bestätigung; erst eine neue Signalflanke nach dem Kontakt zählt. Eingangstimer gelten nur für dafür freigegebene Kontakte und beginnen nach Bestätigung. Weitere Signale verlängern den Timer nicht. Aktive Schutzprofile müssen vor einem Wechsel mit der optionalen PIN deaktiviert werden.

„Alle“ umfasst auch neue Einträge. Eine explizit leere Auswahl umfasst nichts; ein Schutzprofil mit leerem Sensorumfang lässt sich nicht aktivieren. Eine leere Aktionsauswahl schließt konfigurierte Aktionen aus. Automatische Kamerafunktionen benötigen zusätzlich globale Freigabe und ein Profil mit erlaubten Reaktionen.

### Live-Beobachtung und Grundriss

**Aus · Live** deaktiviert Alarmreaktionen. Ein wählbares Hintergrundprofil wertet weiterhin Signale und Korrelation aus und zeigt die erreichte Stufe. Das automatisch angelegte Profil „Live-Beobachtung“ schaltet keine Geräte, sendet keine Pushs, speichert keine Kameraaufnahmen und simuliert keine Anwesenheit. Bestätigungen laufen hier wieder aus. Weitere Beobachtungsprofile können eigene Sensoren und Regeln verwenden. Ohne Hintergrundprofil bleiben die Rohzustände sichtbar.

Unter **Räume & Grundriss → Grundriss hochladen** direkt eine PNG-/JPG-Datei auswählen und der Etage einen Namen geben (maximal 10 MB, 8192 Pixel pro Seite, 32 Megapixel). Bild und Etage werden zusammen gespeichert; ein fehlgeschlagener Upload hinterlässt keinen leeren Eintrag. Vorhandene Etagen haben einen sichtbaren Button **Bild ersetzen**.

Der Assistent schlägt anschließend lokal Raumflächen vor. Es werden keine Bilder an einen externen Dienst übertragen. Einen Vorschlag auswählen, einen vorhandenen IQAlarm-Raum zuordnen und den Umriss prüfen. Eckpunkte lassen sich mit Maus oder Finger verschieben sowie per Pfeiltasten korrigieren und mit Entf entfernen. **Neu zeichnen** erlaubt eine vollständig eigene Fläche, etwa für offene Wohn-/Küchenbereiche oder die Terrasse. Die Erkennung stellt den Lückenausgleich automatisch ein. Zusätzliche Einstellungen liegen unter **Erweiterte Erkennung**. Bei farbigen Bauplänen verwendet sie die strukturelle Wandfarbe und angeschlossene Linien, damit Möbel und Terrassenschraffuren nicht als Räume behandelt werden. Möbel, Beschriftungen und offene Übergänge können unpassende Flächen ergeben; Raumtypen und Namen werden nicht automatisch erkannt. Erst **Bereich speichern** übernimmt die Zuordnung.

**Vorhandene Home-Assistant-Bereiche direkt auswählen.** Sowohl die Raumauswahl im Grundriss als auch der Speicherdialog zeigen vorhandene IQAlarm-Räume und noch nicht verknüpfte HA-Bereiche. Ein separater Import ist nicht erforderlich. Erst beim Speichern werden der ausgewählte Bereich und die bearbeitete Fläche gemeinsam übernommen. Bereits verknüpfte Bereiche erscheinen nur einmal; bestehende Raum-, Sensor- und Profilzuordnungen bleiben erhalten.

**Entwürfe gehen bei der Raumauswahl nicht verloren.** Der Raum wird der bearbeiteten Fläche zugeordnet, ohne ihre Eckpunkte zu ersetzen. Fehlt beim Speichern noch ein Raum, öffnet sich die Zuordnung direkt im Speicherdialog; dort kann auch ein neuer Raum angelegt werden. Rückgängig/Wiederholen sowie Strg+Z / Strg+Umschalt+Z im Grundriss stellen Bearbeitungsschritte wieder her. Der Entwurf und seine Historie werden je Benutzer, Etage und Bild im lokalen Browser gesichert und nach Neuladen wieder angeboten. Diese Sicherung ist lokal; sie verändert die in HA gespeicherten Flächen erst beim ausdrücklichen Speichern. Bei gesperrtem oder vollem Browserspeicher weist der Editor darauf hin. Außenbereiche werden ebenso als Raum markiert. Die bestehenden Sensorzuordnungen liefern automatisch Fenster-/Türstatus, Bewegung, Personen und Quarantäne. Markierungen bleiben bei Größenänderungen proportional erhalten. Der Live-Grundriss zeigt auch Signale, die ein Profil nur anzeigt. Ein Klick auf den Raum öffnet Sensorstatus und gegebenenfalls die verknüpfte HA-Kamera.

Grundrissbilder werden als bereinigte PNG-Dateien privat unter `.iqalarm_floorplans` gespeichert. Abrufe und Uploads benötigen einen HA-Administrator. Bilder und Markierungen bleiben bei Neustarts und HACS-Updates erhalten.

### Profilsymbole

Unter **Profile & System** hat jedes Profil ein eigenes, frei wählbares Symbol. Die Vorgaben sind Haus (Zuhause), Mond (Nacht), Haus mit Ausgang (Abwesend), Palme (Urlaub) und Personengruppe (Besuch). Der Aus-Schalter verwendet das Power-Symbol. Die Auswahl enthält eine grafische Vorschau und erlaubt zusätzliche MDI-Kennungen wie `mdi:dog`. Eigene Symbole und die Profilreihenfolge bleiben beim Bearbeiten, Duplizieren und nach Neustarts erhalten. Symbole ändern keine Alarmregeln.

### Einfache HA-Anbindung

`binary_sensor.iqalarm_aktiv` meldet ausschließlich **an / aus** für erlaubte Alarmreaktionen. Profilname und Alarmstufe sind eigene Sensorinformationen. Die HA-Alarmkarte erhält einen generischen Scharf-Knopf (`armed_away` als technischer HA-Zustand); dieser aktiviert das zuletzt verwendete Schutzprofil. Es ist keine Profilzuordnung erforderlich. Ein bestätigter Alarm meldet weiterhin `triggered`, Ein-/Ausgangsverzögerungen `pending` / `arming`. Beobachtung bleibt für die HA-Alarmkarte `disarmed`, auch wenn die Live-Bewertung hoch ist.

Die Migration übernimmt vorhandene Profile, Auswahl, Regeln, Aktionen, PIN und Quarantäne. Frühere HA-Basismodi werden einmalig in explizite Profilregeln übersetzt und anschließend nicht mehr ausgewertet.

## Installation und Einrichtung

Unterstützt: **Home Assistant ab 2025.12.0**, geprüft mit 2025.12.5 und 2026.10.2.

1. In HACS unter **Benutzerdefinierte Repositorys** die URL `https://github.com/marcohildebrandtmail-hub/IQAlarm` als Typ **Integration** hinzufügen und IQAlarm herunterladen. Alternativ `custom_components/iqalarm` vollständig nach `/config/custom_components/iqalarm` kopieren.
2. Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → IQAlarm** einrichten. Optional eine 4–12-stellige PIN zum Entschärfen vergeben.
4. Im Seitenmenü **IQAlarm** öffnen. Das Konfigurationspanel ist Administratoren vorbehalten.
5. Räume aus HA importieren oder anlegen, Nachbarräume verknüpfen und Sensoren zuweisen. Der Import übernimmt zunächst nur die Räume; Sensorrollen werden bewusst zugeordnet.
6. Unter **Profile & System** Zeiten und Regeln kontrollieren. Standardmäßig verhindern offene Kontakte und nicht verfügbare Sensoren das Scharfschalten.
7. Unter **Level-Konfiguration** die eigenen Dienste und Geräte zuweisen. Es werden keine Sirenen oder Benachrichtigungsziele automatisch ausgewählt.
8. Trockenläufe ausführen und anschließend mit bewusst gewähltem realem Aktionstest die eigenen Geräte prüfen.

Die gesamte Alarmkonfiguration erfolgt im Panel. Es sind keine HA-Automatisierungen und keine YAML-Regeln erforderlich. Änderungen an Räumen, Sensoren, Profilen und Aktionen sind im unscharfen Zustand möglich. Gleichzeitige Änderungen aus mehreren Browserfenstern werden über Konfigurationsrevisionen geschützt.

Die Präsenzsimulation ist zusätzlich als native Schalter-Entität verfügbar und benötigt zusätzlich die Freigabe des aktiven Schutzprofils. Sie verwendet lokale HA-Zeit, schaltet zufällig ausgewählte ausgeschaltete Lichter zwischen den gewählten Stunden ein und übernimmt keine bereits eingeschalteten Lichter.

### Kamera-Erkennung und Dateien

Bevorzugt wird die Personen-Erkennungsentität der Kamera, beispielsweise ein `binary_sensor` von Frigate, Reolink oder UniFi. Dazu kann eine `camera.*` für Bilder und Aufzeichnungen verknüpft werden.

Direkte `camera.*`-/`image_processing.*`-Auslöser benötigen ein explizites Erkennungsattribut und passende aktive Werte. `streaming` oder `idle` werden nicht als Personenerkennung interpretiert. Boolesche Attribute verwenden `true`/`false`; Zählattribute benötigen explizit angegebene Werte.

Snapshots werden über `camera.snapshot`, Aufzeichnungen über `camera.record` ausgeführt. IQAlarm gibt ausschließlich sein eigenes Verzeichnis `/config/.iqalarm_media` für diese Dateizugriffe frei. Die Kamera muss den jeweiligen Dienst unterstützen; Aufzeichnungen benötigen eine stream-fähige Kamera. Automatische Snapshots sind eingeschaltet, automatische Aufzeichnung ist optional.

Dateien liegen außerhalb des öffentlichen `/local`-Bereichs und werden standardmäßig nach sieben Tagen gelöscht. Der Bildabruf verlangt HA-Authentifizierung; zusätzlich werden Administratorrechte oder Leserechte für die Kamera geprüft. Mobile Push-Anhänge benötigen eine entsprechend eingerichtete Companion-App und eine erreichbare HA-URL.

### Aktionen und Tests

- Lautlose Stufen und Diagnose: normale Pushs, Licht, Rollos, Snapshots und Aufzeichnungen (nur bei freigegebenen Profilreaktionen).
- Bestätigte, akustisch freigegebene Stufen: zusätzlich Sirenen, Schalter, Skripte, TTS und kritische Mobile-App-Pushs.
- Freie Schalter-/Skript-/Sprachaktionen sind unteren Stufen nicht erlaubt, weil damit eine Innensirene indirekt ausgelöst werden könnte.
- Kritische Pushs/Bilder brauchen einen passenden `notify.mobile_app_*`-Dienst. Generische `notify.*`-Entitäten unterstützen gewöhnliche Textnachrichten über `notify.send_message`.
- Vorlagen unterstützen `{{room}}`, `{{sensor}}`, `{{level}}`, `{{reason}}`, `{{chain}}`, `{{mode}}` und den Profilnamen `{{profile}}`. Andere Jinja-Ausdrücke werden nicht ausgeführt.
- IQAlarm schaltet selbst eingeschaltete Sirenen, Schalter, Skripte und Lichter nach der konfigurierten Dauer oder beim Entschärfen aus. Bereits eingeschaltete Geräte werden nicht zum späteren Abschalten übernommen. Rollos werden geöffnet und bleiben offen.
- Aktionsfehler erscheinen im Logbuch. Ein fehlerhafter Kameraabruf unterdrückt die Textbenachrichtigung nicht. Langsame Push-/Kameradienste blockieren die Sireneneskalation nicht.
- Ein Trockenlauf verändert keine Alarmstufe und schaltet keine Geräte. Nur der ausdrücklich aktivierte reale Test führt Aktionen aus.

PINs werden ausschließlich gesalzen und gehasht gespeichert. Wiederholt falsche Versuche werden begrenzt. Konfiguration, Quarantäne, aktive Timer, Auslösekette und bis zu 500 Ereignisse liegen im privaten HA-Store `.storage/iqalarm.configuration`; das Panel zeigt die letzten 50 Ereignisse.

Nach einem Neustart wird der gewählte Modus einschließlich Quarantäne und bestätigtem Alarm wiederhergestellt. Bereits gespeicherte Alarmaktionen werden nicht erneut abgespielt. Während des Herunterfahrens werden von IQAlarm übernommene Ausgänge ausgeschaltet. Ein während des Neustarts abgelaufener bestätigter Eingangstimer eskaliert nach dem Laden.

**Override, Rauch und Panik:** Diese ausdrücklich gewählten Sensoren dürfen bei scharfer Anlage alleine die im Profil zugeordnete bestätigte Stufe auslösen. Beim Override wird die normale Wartezeit auf einen zweiten Sensor bewusst aufgehoben. Rauch/Panik werden hier nur innerhalb des scharfen Alarmprofils verarbeitet; bestehende eigenständige Rauchmelderfunktionen bleiben erforderlich.

## Native Schnittstellen

| Schnittstelle | Funktion |
| --- | --- |
| `alarm_control_panel.iqalarm` | Generisches Scharf/Unscharf und tatsächlicher Alarm |
| `binary_sensor.iqalarm_aktiv` | Reaktionen an / aus |
| Diagnose-Sensoren | Alarmstufe samt Bezeichnung, aktuelles Profil, Anzahl isolierter Sensoren, letztes Ereignis |
| Binary-Sensoren je Raum | Raumproblem, Vorfeld aktiv, Verdacht aktiv |
| Simulationsschalter | Anwesenheitssimulation aktivieren/deaktivieren |
| `iqalarm.set_mode` | Modus setzen, optional `code` zum Entschärfen |
| `iqalarm.arm_profile` | Eigenes Profil über `profile_id` scharfschalten |
| `iqalarm.clear_quarantine` | Einzelnen oder alle Sensoren freigeben |
| `iqalarm.trigger_test_level` | Eigene Stufen-ID oder `diagnostic`, `dry_run` standardmäßig `true`, optional `profile_id` |
| `iqalarm_event` | Strukturierte Ereignisse mit Zeit, Modus, Profil, Entscheidung und Auslösekette |

WebSocket-Befehle: `iqalarm/get`, `iqalarm/subscribe`, `iqalarm/catalog`, `iqalarm/config/save`, `iqalarm/crud`, `iqalarm/import_areas`, `iqalarm/set_mode`, `iqalarm/arm_profile`, `iqalarm/clear_quarantine`, `iqalarm/test_level`, `iqalarm/floorplan/analyze`. CRUD unterstützt Räume, Sensoren, Aktionen, Profile und Grundrisse. Stufen werden mit der gesamten Konfiguration gespeichert. Neue Etage mit Bild: POST `/api/iqalarm/floorplans/upload?name=Etagenname`. Die Flächenanalyse ist schreibgeschützt. Geschützte Bild-API: GET/POST `/api/iqalarm/floorplans/{id}/image`; Upload mit aktuellem `X-IQAlarm-Revision`-Header. Alle Befehle verlangen einen Administrator. CRUD und Konfigurationsänderungen verlangen die aktuelle `revision`.

## Entwicklung und Verifikation

```powershell
python -m pip install pytest pytest-cov ruff PyYAML voluptuous Pillow
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
node --check custom_components/iqalarm/frontend/iqalarm-panel.js
node --test tests/frontend/*.test.mjs
```

Die Engine-Tests verwenden kontrollierte Zeit und keine laufende HA-Instanz. Der Integrationsprüfer startet dagegen den echten HA Core im offiziellen Container, richtet IQAlarm über den Config Flow ein und prüft Entitäten, Ereignisse, Services, WebSockets, Berechtigungen und Reloads:

```powershell
$repo = (Get-Location).Path
docker run --rm --entrypoint python --mount "type=bind,source=$repo,target=/work" -w /work ghcr.io/home-assistant/home-assistant:2026.10.2 scripts/verify_ha.py
```

Browserprüfungen verwenden ebenfalls diesen echten HA-Server. Die dabei angelegten Entitäten und Dienste sind ausschließlich Testdaten im wegwerfbaren Container:

```powershell
npm ci
npx playwright install chromium
docker run --rm -d --name iqalarm-browser --entrypoint python -p 127.0.0.1:18123:18123 --mount "type=bind,source=$repo,target=/work" -w /work ghcr.io/home-assistant/home-assistant:2026.10.2 scripts/verify_ha.py --serve
python scripts/wait_for_ha.py
npm test
docker stop iqalarm-browser
```

Der Test-Harness stellt ausschließlich im Testcontainer eine kurzlebige Testsitzung bereit und muss an `127.0.0.1` gebunden bleiben. Er ist kein Bestandteil der installierten Integration.

## Veröffentlichung und Deployment

Das Zielrepository ist [marcohildebrandtmail-hub/IQAlarm](https://github.com/marcohildebrandtmail-hub/IQAlarm). Dokumentationslink, Issue-Tracker und Codeowner sind darauf eingestellt. `scripts/bind_repository.py` aktualisiert diese Metadaten bei einem späteren Repository-Wechsel. Die [GitHub-Workflows](https://github.com/marcohildebrandtmail-hub/IQAlarm/actions) prüfen Python, Browser, beide HA-Versionen, hassfest und HACS. Für den öffentlichen HACS-Standardkatalog ist zusätzlich ein separater Brand-Eintrag nötig; das Repository kann unabhängig davon als benutzerdefinierte HACS-Quelle verwendet werden.

`python scripts/package_release.py` erzeugt ein reproduzierbares ZIP unter `dist/` sowie eine SHA-256-Dateiliste. `scripts/deploy.py` installiert in einen ausdrücklich angegebenen lokalen oder per SSH erreichbaren HA-Konfigurationsordner. Es legt vor einem Update eine Sicherung unter `.iqalarm-backups` an und ersetzt die Integration atomar. Bei Fehlern wird zurückgerollt. SSH nutzt vorhandene Anmeldung und benötigt auf dem Ziel `python3`.

Das Deployment-Skript prüft vor Schreibzugriffen, dass das Ziel ein HA-Konfigurationsordner ist. Falls die `ha`-CLI vorhanden ist, folgt `ha core check`; `--restart` startet nach erfolgreicher Prüfung neu. Bei einem Netzlaufwerk ohne entfernte CLI werden Neustart und Startprotokoll anschließend über die konkrete HA-Instanz geprüft.

## Quellen der HA-Anbindung

[Alarm-Control-Panel-Entität](https://developers.home-assistant.io/docs/core/entity/alarm-control-panel/), [eigene Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/), [WebSocket-Erweiterungen](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/), [HACS-Integrationsanforderungen](https://www.hacs.dev/docs/publish/integration/).

Lizenz: MIT, siehe [LICENSE](LICENSE).
