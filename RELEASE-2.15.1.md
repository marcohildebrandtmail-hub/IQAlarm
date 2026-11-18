# IQAlarm 2.15.1

Ein ausgefallener Sensor darf nicht die Scharfschaltung der gesamten Anlage
verhindern. Bisher war die entsprechende Sperre standardmäßig aktiviert:
Ein einziger nicht verfügbarer Melder konnte dadurch beispielsweise eine
automatische nächtliche Scharfschaltung verhindern.

- Neue Installationen schalten trotz nicht verfügbarer Sensoren scharf.
- Beim ersten Laden einer älteren Konfiguration wird die bisherige
  Sensorausfall-Sperre einmalig deaktiviert und die Änderung gespeichert.
  Das Update wirkt damit auch bei bestehenden Installationen.
- Die übrigen Melder bleiben aktiv. Nach Wiederkehr wird ein ausgefallener
  Melder automatisch wieder ausgewertet; er wird nicht dauerhaft ignoriert.
- Die Prüfung offener Türen/Tore bleibt erhalten. Wer nach diesem Update
  bewusst eine strenge Verfügbarkeitssperre einschaltet, behält diese
  Einstellung auch über weitere Neustarts.

Nach der Installation Home Assistant neu starten, damit die Korrektur und
die Migration geladen werden. Eigene Hausautomationen werden durch den
Release nicht umgeschrieben.

Die Tests prüfen Neuinstallationen, bestehende gespeicherte Konfigurationen,
Wiederanlauf, Schutz durch andere Melder und erneutes Laden einer bewusst
aktivierten strengen Einstellung. Der HA-Integrationstest verwendet eine
isolierte Instanz und löst keine Aktionen im echten Haus aus.
