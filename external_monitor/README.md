# IQAlarm – externer Überwachungsdienst

Der Dienst läuft unabhängig von Home Assistant in einem unprivilegierten LXC.
Abgelaufene Alarme werden dauerhaft in `escalations` erfasst. Der optionale
TeamMessage-Worker kann danach eine SMS an ausdrücklich zugeordnete Empfänger
senden. Ohne aktivierte SMS-Konfiguration bleibt `action_state=unconfigured`.

## Ablauf und Speicherung

- Pro Installation: zufällige 128-Bit-System-ID und separater geheimer 256-Bit-Zugang.
  Nur die ID wird angezeigt; der Zugang bleibt im privaten HA-Speicher.
- Registrierung mit belegter ID und anderem Zugang: HTTP 409. HA erzeugt eine
  neue Identität und versucht erneut. Verlorene Registrierungsantworten sind
  mit derselben Identität wiederholbar.
- Aktivierung/Deaktivierung erfolgt authentifiziert je System. Standard ist Aus.
- Die frei eingebbare Benutzerbezeichnung aus dem LVL-4-Formular wird
  authentifiziert je System gespeichert. Standard: „deinem Freund“.
- Bis zu drei internationale Telefonnummern werden aus demselben Formular
  authentifiziert je System übernommen. Formatierungszeichen werden entfernt,
  `00` als internationale Vorwahl wird zu `+`, doppelte Nummern zählen einmal.
- Ab LVL 4 meldet HA Alarm-ID und verbleibende Eskalationszeit. Der Dienst legt
  eine eigene Frist an; wiederholte Meldungen derselben Alarm-ID verlängern sie nicht.
- Manuelles Ausschalten sendet eine authentifizierte Aufhebung derselben Alarm-ID.
  Auch eine vor der Startmeldung eintreffende Aufhebung verhindert deren Wiederbelebung.
- Offlinegehen, HA-Neustart oder Deaktivierung des Dienstes löschen keine bereits
  laufende Frist. Überfällige Alarme werden beim Dienststart nachgeholt.
- Eine nach Eskalation eintreffende Aufhebung wird als solche protokolliert; das
  schon erzeugte Eskalationsereignis wird nicht rückwirkend gelöscht.

SQLite mit WAL und synchronen Commits speichert Systeme, Alarme und
Eskalationsereignisse. HA speichert Identität und noch nicht bestätigte Meldungen
vor dem Versand. Geheimnisse kommen weder in Konfigurationsexporte noch in die
WebSocket-Anzeige oder HTTP-Zugriffslogs.

## Betrieb

`server.py` benötigt nur Python 3.11 oder neuer. `iqalarm-monitor.service` läuft
als eigener Benutzer; Daten liegen in `/var/lib/iqalarm-monitor/`, TLS-Zertifikat
und privater Schlüssel in `/etc/iqalarm-monitor/`. Dienst und LXC starten automatisch.
Der ausgelieferte Dienst funktioniert ohne verschachtelte Mount-Namespaces in
unprivilegierten Proxmox-Containern.

Die erste Installation ist über das bestehende WireGuard-Netz erreichbar. Der
Host-Forwarder `forward.py` transportiert TLS unverändert und ermittelt bei jeder
Verbindung die aktuelle DHCP-Adresse des Containers. Die Proxmox-Verwaltung und
ihre Zugangsdaten werden der Alarmanlage nicht zugänglich gemacht.

Für weitere Installationen muss der Betreiber die HTTPS-Dienstadresse unter
`external_monitoring.url` bereitstellen. Bei privatem Zertifikat wird dessen
SHA-256-Fingerabdruck unter `certificate_sha256` hinterlegt; ohne Pin gilt die
normale CA-Prüfung. Für Nutzer außerhalb des VPN ist ein eigener öffentlich
 erreichbarer HTTPS-Endpunkt mit passendem Zertifikat erforderlich. Vor einer
öffentlichen Freigabe sind zusätzlich Lastbegrenzung, Einladungsregistrierung,
Überwachung und der Notfallzugang zur direkten Quittierung auszugestalten.

LXC samt Datenbank und Zertifikat regelmäßig sichern. HA-Backups behalten
absichtlich ihre Identität; ein parallel betriebenes geklontes System benötigt
neue Zugangsdaten und eine neue ID. Zertifikate müssen vor ihrem Ablauf erneuert
und bei Pinning die neuen Fingerabdrücke verteilt werden.

## Schnittstelle

- `GET /health`: Funktionsstatus ohne Kundendaten.
- `POST /v1/systems`: Registrierung `{id, secret}`; zunächst deaktiviert.
- `PUT /v1/systems/<id>/enabled`: `{enabled: true|false, user_label: ..., phone_numbers: [...]}`;
  ohne `user_label` bleibt die bestehende Bezeichnung erhalten.
  Ohne `phone_numbers` bleiben die bisherigen Empfänger erhalten; ein explizites
  leeres Array entfernt sämtliche SMS-Empfänger für dieses System.
- `POST /v1/systems/<id>/alarms/<alarm-id>`: `{operation: start, remaining_seconds: ..., duration_seconds: ...}`
  oder `{operation: cancel}`.
- `GET /v1/systems/<id>/alarms/<alarm-id>`: authentifizierter Alarmstatus.

Alle Aufrufe außer Registrierung und Health erfordern `Authorization: Bearer ...`.
Der Dienst speichert nur den SHA-256-Hash des zufälligen Geheimnisses. Die
Registrierung ist derzeit für das VPN vorgesehen und zusätzlich mengenbegrenzt.

Die externe Frist beginnt mit dem ersten angenommenen Bericht über die verbleibende
Zeit; Transportlaufzeit kann einen kleinen Versatz zum lokalen Ablauf erzeugen.
Schutz gegen einen späteren HA-Ausfall besteht erst nach bestätigtem Empfang.
Eine wegen Netzausfalls nicht übertragene lokale Aufhebung kann extern nicht
rechtzeitig wirken.

`duration_seconds` speichert die beim Alarm geltende vollständige Eskalationsdauer
unabhängig von der Restfrist. Eine verspätet übertragene Meldung mit noch zwei
Minuten Restzeit kann deshalb weiterhin korrekt „Seit 5 Minuten“ nennen.
Ältere Clients ohne dieses optionale Feld verwenden für den SMS-Text ihre bei
Empfang gemeldete Restfrist; deren Ablauf bleibt unverändert.

## TeamMessage-SMS

`teammessage.py` und `sms_worker.py` werden neben `server.py` installiert;
`iqalarm-sms.service` betreibt den Versand getrennt vom Watchdog. Eine langsame
Anbieterantwort blockiert dadurch weder dessen Fristen noch Quittierungen.
Home Assistant muss dafür nicht aktualisiert oder neu gestartet werden.

Die Betreiberdatei `/etc/iqalarm-monitor/teammessage.json` basiert auf
`teammessage.example.json`. Eigentümer ist `root:iqalarm-monitor`, Rechte `0640`;
das übergeordnete Verzeichnis hat `0750`. Token und optionale Keywords gehören
ausschließlich in diese geschützte Datei, niemals ins Repository. Der Worker
liest Änderungen ohne Neustart ein.

- Standard: `enabled=false`, `test_mode=true`. Ein aktivierter Worker verlangt
  zusätzlich `active_from` als Unix-Zeitpunkt der Freigabe. Alarme, die bereits
  davor angelegt wurden, lösen keinen nachträglichen SMS-Versand aus.
- Unter `systems` werden Team-ID, Listen-ID `tl` oder Teamlisten-E-Mail,
  gegebenenfalls registrierte Absender-E-Mail und Keyword sowie internationale
  Empfängernummern jeder System-ID ausdrücklich zugeordnet. Andere Systeme
  verwenden diese Empfänger nicht. `from_mobile` legt die SMS-Absenderkennung fest.
  Sobald das System Telefonnummern aus der HA-Oberfläche übermittelt hat, haben
  diese Vorrang vor der alten Betreiberliste. Eine leere UI-Liste fällt nicht
  auf eine versteckte frühere Rufnummer zurück. Die Betreiberzuordnung der
  System-ID zum TeamMessage-Konto bleibt Voraussetzung für den Versand.
- Auf der TeamMessage-Seite muss der HTTP2SMS-Zugriff für die Liste aktiviert sein.
  Die geschlossene Gruppe und ihre Sendeberechtigungen können bestehen bleiben.
- `test_mode=true` sendet `test=1`: TeamMessage validiert ohne SMS-Versand.
  Für echte Alarmnachrichten ist `test_mode=false` erforderlich. Vor der Freigabe
  `active_from` auf den aktuellen Zeitpunkt setzen.
- Der Worker reagiert ausschließlich auf abgelaufene, nicht quittierte Alarme.
  Eine Quittierung vor der Versandübernahme verhindert die SMS. Hat der
  Anbieteraufruf bereits begonnen, kann eine spätere Quittierung ihn nicht
  zuverlässig zurückrufen. Das Abschalten der Überwachung löscht eine zuvor
  angenommene Alarmfrist weiterhin nicht.

`sms_jobs` speichert die Versandübernahme vor dem Anbieteraufruf. Pro Alarm
entsteht höchstens ein Auftrag für die zugeordneten Empfänger. Nach erfolgreicher
Annahme lautet der Status `accepted`, nicht „zugestellt“; Testaufrufe ergeben
`validated`. Eindeutige Ablehnungen werden `rejected`. Nur dokumentierte
HTTP-429-Ablehnungen werden mit Wartezeit wiederholt, höchstens drei Versuche.
Bei verlorener Antwort oder Prozessabbruch während des Aufrufs gilt `uncertain`;
ohne Anbieter-Idempotenz wird nicht automatisch erneut gesendet. Solche Fälle
und Zustellprobleme muss der Betreiber im Anbieterprotokoll prüfen. Es gibt noch
keine automatische Zustellkontrolle oder weitere Eskalationsaktion.

Die Gegenstelle ist fest auf die offizielle HTTPS-API eingestellt. Normale
Zertifikatsprüfung bleibt aktiv; Weiterleitungen werden nicht verfolgt.
Protokolle enthalten keine Token, Rufnummern oder Anbieterantworttexte.

Der SMS-Text verwendet die Benutzerbezeichnung und die ursprüngliche Alarmdauer:
„IQAlarm - ALARM LVL05! Die Alarmanlage von deinem Freund hat einen Einbruchsalarm
gemeldet. Seit 5 Minuten keine Entwarnung. Bitte sofort Anrufen und prüfen!“
Der Worker übermittelt UTF-8-JSON mit `ucs2=0`. Der ursprüngliche typografische
Gedankenstrich wird im SMS-Text als normaler Bindestrich ausgegeben; deutsche
Umlaute bleiben erhalten. Der ausdrücklich eingeschaltete UCS2-Modus führte
im ersten echten Handytest zu unlesbaren Zeichen und wird nicht mehr erzwungen.
Je nach Textlänge kann der Anbieter die Nachricht in mehrere SMS-Teile aufteilen.

Anbieterdokumentation: <https://www.teammessage.de/de/dokumentation/api/>

### Prüfung am 20.10.2026

34 automatisierte Tests für Watchdog und SMS-Anbindung sowie die statischen
Python-Prüfungen waren erfolgreich. Im installierten Container wurden Fristablauf,
Quittierung, Wiederholungen und Neustart zunächst mit einer isolierten Datenbank
geprüft. Danach durchlief eine eigene Diagnose-ID den echten HTTPS-Watchdog und
den laufenden SMS-Worker: eine unquittierte Zwei-Sekunden-Frist erzeugte genau
einen vom Anbieter validierten Testauftrag; die quittierte Frist erzeugte keinen.
Ein Worker-Neustart führte zu keiner Wiederholung.

Die anfänglichen Anbieterprüfungen liefen mit `test=1`. HA-Sensoren wurden für diese
Prüfungen nicht verändert. Die SMS-Aktion ist für die ausdrücklich zugeordnete
Installation vorbereitet; die externe Überwachung in HA blieb ausgeschaltet.

Beim anschließenden ausdrücklich beauftragten echten Versand am 20.10. um
22:00 Uhr kam die SMS mit Absender „IQAlarm“ an. Der Inhalt war mit `ucs2=1`
unlesbar, obwohl der Anbieter Annahme und Zustellung bestätigte. Das Protokoll
enthielt keinen Nachrichtentext, der zur Kontrolle hätte verglichen werden
können. Daraus folgt: Ein erfolgreicher Prüfaufruf oder Zustellbericht bestätigt
nicht die lesbare Darstellung. Die Korrektur auf den normalen SMS-Modus und
UTF-8-JSON muss zusätzlich durch einen neuen Handytest bestätigt werden.
Die Korrektur wurde im Container installiert; 40 Watchdog-/SMS-Tests bestanden.
Ein Prüfaufruf mit `test=1` und `ucs2=0` gab den vollständigen 157-Zeichen-Text
einschließlich Umlaut unverändert zurück. Dabei wurde keine weitere SMS versendet.
Nach erneuter ausdrücklicher Freigabe wurde eine weitere echte SMS mit `ucs2=0`
und „TEST LVL05“ im Text vom Anbieter angenommen. Dieser Testtext umfasst
156 Zeichen. Der Nutzer bestätigte anschließend am 20.10.2026, dass der Text
vollständig und lesbar auf dem Handy angekommen ist. Damit ist die Korrektur
für diesen echten Versand bestätigt; der normale SMS-Modus bleibt installiert.
