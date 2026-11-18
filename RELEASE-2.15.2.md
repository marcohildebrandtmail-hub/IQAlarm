# IQAlarm 2.15.2

Dieser Release enthält die Scharfschaltkorrektur und die automatische Migration
aus 2.15.1 zusammen mit den bereits eingesetzten weiteren Korrekturen:

- Gleichzeitige Speicheranforderungen werden zusammengefasst. Wichtige
  Schalt- und Aktionszustände warten auf ihre bestätigte Speicherung.
- Kontaktwechsel bei ausgeschalteter Anlage erzeugen keine Prell-Quarantäne.
  Die Darstellung laufender Bewegung verwendet den passenden Meldezeitpunkt.
- Die eigenständige Grundriss-Karte und die vorhandenen kompakten
  Sensorbeschriftungen bleiben enthalten.
- Profilfreigaben und bestehende Einstellungen bleiben beim Speichern erhalten.

Nicht verfügbare Sensoren blockieren standardmäßig nicht die Scharfschaltung.
Beim ersten Laden einer älteren Konfiguration wird die bisherige
Verfügbarkeitssperre einmalig deaktiviert. Andere Melder bleiben wirksam;
zurückkehrende Sensoren werden wieder ausgewertet. Die Prüfung offener
Türen/Tore bleibt bestehen. Eine danach bewusst aktivierte strenge
Verfügbarkeitssperre bleibt über Neustarts erhalten.

Nach der Installation Home Assistant neu starten. Eigene Hausautomationen
werden durch das Installationspaket nicht verändert.
