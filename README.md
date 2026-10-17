# IQAlarm

**Erst verstehen, dann auslösen.** IQAlarm ist eine lokale Home-Assistant-Integration mit räumlicher Sensor-Korrelation, Prell-Schutz und eigenem deutschen Seitenpanel. Das Panel wird direkt als ES-Modul ausgeliefert. Auf dem Home-Assistant-System sind weder Node.js noch ein Frontend-Build nötig.

## Alarmstufen

| Stufe | Bedeutung | Standardlogik |
| --- | --- | --- |
| 0 | Sicher | Keine frischen Sicherheitssignale |
| 1 | Vorfeld | Person-/Perimeter-Erkennung; Gedächtnis standardmäßig 180 s |
| 2 | Verdacht | Einzelkontakt oder unbestätigte Bewegung; Korrelation standardmäßig 60 s |
| 3 | Bestätigter Alarm | Zwei unabhängige, zeitlich und räumlich passende Quellen oder ausdrücklich freigegebener Override |

Ein bestätigter Alarm bleibt bis zum Entschärfen bestehen. Unbestätigte Ereignisse laufen automatisch aus. Die native Entität `alarm_control_panel.iqalarm` meldet bei Stufe 1/2 weiterhin den gewählten Scharf-Modus; ausschließlich Stufe 3 meldet `triggered`. Eine aktive Eingangsverzögerung meldet `pending`.

### MACO-/Kontakt-Prellen

Öffnungs-, Riegel- und Vibrationssensoren werden standardmäßig ab drei echten Zustandswechseln innerhalb von 15 Sekunden isoliert, wenn keine unabhängige Bestätigung vorliegt. `on → off → on` bei anfänglichem `off` sind drei Wechsel. Wiederholte identische Werte, `unknown` und `unavailable` zählen nicht als Wechsel.

Ein isolierter Sensor liefert keine Einbruchsbestätigung mehr. Die Quarantäne bleibt bis zum Entschärfen oder einer bewussten Freigabe erhalten, auch nach einem Neustart. Sie wird im Cockpit angezeigt und kann eigene lautlose Diagnoseaktionen auslösen. Ein zuvor unabhängig bestätigter Vollalarm wird durch spätere Kontaktwechsel nicht gelöscht.

Die optionale Mindest-Aktivzeit filtert kurze Impulse, während die Prell-Erkennung weiterhin die ungefilterten Wechsel beobachtet. Werte pro Sensor überschreiben die Vorgabe der Rolle; `0` verwendet die Rollenvorgabe.

### Räumliche Bestätigung

- Vorfeld + Öffnung: nur vor dem zugeordneten Raum; ein globales Vorfeld gilt für das gesamte Haus.
- Öffnung + Innenraum: im selben Raum oder optional in einem direkt angrenzenden Raum. Eine Verbindung gilt in beide Richtungen, ohne transitive Weitergabe über mehrere Räume.
- Zwei Öffnungssensoren: im gesamten Haus innerhalb des Korrelationsfensters.
- Zwei Innenraumsensoren: im Abwesend-/Urlaubsprofil innerhalb des Korrelationsfensters.
- Mehrere Entitäten desselben physischen Sensors müssen dieselbe **Signalquellenkennung** erhalten. Eine Quelle kann sich niemals selbst bestätigen.

Kamera und Öffnung werden auch in umgekehrter Reihenfolge berücksichtigt, solange beide Ereignisse noch in ihrem jeweiligen Zeitfenster liegen.

## Profile

| Modus | Verhalten |
| --- | --- |
| Unscharf | Optional weiterhin Prell-Diagnose; keine Einbruchsalarmierung |
| Zuhause | Vorfeld und zusätzlich ausdrücklich freigegebene Räume, etwa Keller oder Nebengebäude |
| Nacht | Vorfeld und Außenhaut aktiv. Bewegung wird erst nach frischem Öffnungssignal ausgewertet |
| Abwesend | Alle zugeordneten Sensoren; zwei unabhängige Innenraumsensoren können bestätigen |
| Urlaub | Wie Abwesend; standardmäßig 45 s Korrelation und 5 s Eingangsverzögerung; optionale Lichtsimulation |

Im Nachtprofil wird eine Bewegung **vor** dem Öffnungssignal nicht nachträglich zur Bestätigung. Eine bereits aktive Präsenz wird ebenfalls nicht künstlich als neue Bewegung gewertet. Erst eine neue Signalflanke nach dem Kontakt zählt. Die Nacht-Aktivierung kann für betroffene Räume oder das ganze Haus gewählt werden; die räumliche Bestätigungsregel bleibt erhalten.

Eingangsverzögerung gilt ausschließlich für ausdrücklich markierte Öffnungssensoren und beginnt nach deren Bestätigung. Weitere Signale verlängern die laufende Frist nicht. Ausgangsverzögerung unterdrückt Einbruchssignale während des Verlassens; danach werden noch offene Kontakte erneut geprüft. Vor einem Profilwechsel muss entschärft werden.

## Installation und Einrichtung

Unterstützt: **Home Assistant ab 2025.12.0**, geprüft mit 2025.12.5 und 2026.10.2.

1. In HACS unter **Benutzerdefinierte Repositorys** die URL `https://github.com/marcohildebrandtmail-hub/IQAlarm` als Typ **Integration** hinzufügen und IQAlarm herunterladen. Alternativ `custom_components/iqalarm` vollständig nach `/config/custom_components/iqalarm` kopieren.
2. Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → IQAlarm** einrichten. Optional eine 4–12-stellige PIN zum Entschärfen vergeben.
4. Im Seitenmenü **IQAlarm** öffnen. Das Konfigurationspanel ist Administratoren vorbehalten.
5. Räume aus HA importieren oder anlegen, Nachbarräume verknüpfen und Sensoren zuweisen. Der Import übernimmt zunächst nur die Räume; Sensorrollen werden bewusst zugeordnet.
6. Unter **Alarmstufen & Regeln** Zeiten und Regeln kontrollieren. Standardmäßig verhindern offene Kontakte und nicht verfügbare Sensoren das Scharfschalten.
7. Unter **Aktionen & Push** die eigenen Dienste und Geräte zuweisen. Es werden keine Sirenen oder Benachrichtigungsziele automatisch ausgewählt.
8. Trockenläufe ausführen und anschließend mit bewusst gewähltem realem Aktionstest die eigenen Geräte prüfen.

Die gesamte Alarmkonfiguration erfolgt im Panel. Es sind keine HA-Automatisierungen und keine YAML-Regeln erforderlich. Änderungen an Räumen, Sensoren, Profilen und Aktionen sind im unscharfen Zustand möglich. Gleichzeitige Änderungen aus mehreren Browserfenstern werden über Konfigurationsrevisionen geschützt.

Die Präsenzsimulation ist zusätzlich als native Schalter-Entität verfügbar und kann auch im Urlaubsmodus umgeschaltet werden. Sie verwendet lokale HA-Zeit, schaltet zufällig ausgewählte ausgeschaltete Lichter zwischen den gewählten Stunden ein und übernimmt keine bereits eingeschalteten Lichter.

### Kamera-Erkennung und Dateien

Bevorzugt wird die Personen-Erkennungsentität der Kamera, beispielsweise ein `binary_sensor` von Frigate, Reolink oder UniFi. Dazu kann eine `camera.*` für Bilder und Aufzeichnungen verknüpft werden.

Direkte `camera.*`-/`image_processing.*`-Auslöser benötigen ein explizites Erkennungsattribut und passende aktive Werte. `streaming` oder `idle` werden nicht als Personenerkennung interpretiert. Boolesche Attribute verwenden `true`/`false`; Zählattribute benötigen explizit angegebene Werte.

Snapshots werden über `camera.snapshot`, Aufzeichnungen über `camera.record` ausgeführt. IQAlarm gibt ausschließlich sein eigenes Verzeichnis `/config/.iqalarm_media` für diese Dateizugriffe frei. Die Kamera muss den jeweiligen Dienst unterstützen; Aufzeichnungen benötigen eine stream-fähige Kamera. Automatische Snapshots sind eingeschaltet, automatische Aufzeichnung ist optional.

Dateien liegen außerhalb des öffentlichen `/local`-Bereichs und werden standardmäßig nach sieben Tagen gelöscht. Der Bildabruf verlangt HA-Authentifizierung; zusätzlich werden Administratorrechte oder Leserechte für die Kamera geprüft. Mobile Push-Anhänge benötigen eine entsprechend eingerichtete Companion-App und eine erreichbare HA-URL.

### Aktionen und Tests

- Stufe 1, Stufe 2 und Diagnose: normale Pushs, Licht, Rollos, Snapshots und Aufzeichnungen.
- Stufe 3: zusätzlich Sirenen, Schalter, Skripte, TTS und kritische Mobile-App-Pushs.
- Freie Schalter-/Skript-/Sprachaktionen sind unteren Stufen nicht erlaubt, weil damit eine Innensirene indirekt ausgelöst werden könnte.
- Kritische Pushs/Bilder brauchen einen passenden `notify.mobile_app_*`-Dienst. Generische `notify.*`-Entitäten unterstützen gewöhnliche Textnachrichten über `notify.send_message`.
- Vorlagen unterstützen `{{room}}`, `{{sensor}}`, `{{level}}`, `{{reason}}`, `{{chain}}` und `{{mode}}`. Andere Jinja-Ausdrücke werden nicht ausgeführt.
- IQAlarm schaltet selbst eingeschaltete Sirenen, Schalter, Skripte und Lichter nach der konfigurierten Dauer oder beim Entschärfen aus. Bereits eingeschaltete Geräte werden nicht zum späteren Abschalten übernommen. Rollos werden geöffnet und bleiben offen.
- Aktionsfehler erscheinen im Logbuch. Ein fehlerhafter Kameraabruf unterdrückt die Textbenachrichtigung nicht. Langsame Push-/Kameradienste blockieren die Sireneneskalation nicht.
- Ein Trockenlauf verändert keine Alarmstufe und schaltet keine Geräte. Nur der ausdrücklich aktivierte reale Test führt Aktionen aus.

PINs werden ausschließlich gesalzen und gehasht gespeichert. Wiederholt falsche Versuche werden begrenzt. Konfiguration, Quarantäne, aktive Timer, Auslösekette und bis zu 500 Ereignisse liegen im privaten HA-Store `.storage/iqalarm.configuration`; das Panel zeigt die letzten 50 Ereignisse.

Nach einem Neustart wird der gewählte Modus einschließlich Quarantäne und bestätigtem Alarm wiederhergestellt. Bereits gespeicherte Alarmaktionen werden nicht erneut abgespielt. Während des Herunterfahrens werden von IQAlarm übernommene Ausgänge ausgeschaltet. Ein während des Neustarts abgelaufener bestätigter Eingangstimer eskaliert nach dem Laden.

**Override, Rauch und Panik:** Diese ausdrücklich gewählten Sensoren dürfen bei scharfer Anlage alleine Stufe 3 auslösen. Beim Override wird die normale Wartezeit auf einen zweiten Sensor bewusst aufgehoben. Rauch/Panik werden hier nur innerhalb des scharfen Alarmprofils verarbeitet; bestehende eigenständige Rauchmelderfunktionen bleiben erforderlich.

## Native Schnittstellen

| Schnittstelle | Funktion |
| --- | --- |
| `alarm_control_panel.iqalarm` | Unscharf, Zuhause, Nacht, Abwesend, Urlaub |
| Diagnose-Sensoren | Alarmstufe, Anzahl isolierter Sensoren, letztes Ereignis |
| Binary-Sensoren je Raum | Raumproblem, Vorfeld aktiv, Verdacht aktiv |
| Simulationsschalter | Anwesenheitssimulation aktivieren/deaktivieren |
| `iqalarm.set_mode` | Modus setzen, optional `code` zum Entschärfen |
| `iqalarm.clear_quarantine` | Einzelnen oder alle Sensoren freigeben |
| `iqalarm.trigger_test_level` | Stufe `1`, `2`, `3` oder `diagnostic`, `dry_run` standardmäßig `true` |
| `iqalarm_event` | Strukturierte Ereignisse mit Zeit, Modus, Entscheidung und Auslösekette |

WebSocket-Befehle: `iqalarm/get`, `iqalarm/subscribe`, `iqalarm/catalog`, `iqalarm/config/save`, `iqalarm/crud`, `iqalarm/import_areas`, `iqalarm/set_mode`, `iqalarm/clear_quarantine`, `iqalarm/test_level`. Alle verlangen einen Administrator. CRUD und Konfigurationsänderungen verlangen die aktuelle `revision`.

## Entwicklung und Verifikation

```powershell
python -m pip install pytest pytest-cov ruff PyYAML voluptuous
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
node --check custom_components/iqalarm/frontend/iqalarm-panel.js
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
