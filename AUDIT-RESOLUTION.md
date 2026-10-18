# IQAlarm 2.4.0 – Auditkorrekturen

Der Audit vom 18. Oktober 2026 wurde in folgenden Änderungen umgesetzt. Die Regressionstests gehören zum Repository; private Grundrisse, Zugangsdaten und Audit-Artefakte werden nicht veröffentlicht.

| Befund | Korrektur | Nachweis |
| --- | --- | --- |
| F001 Mehrdeutige Griff-Zwischenstellung verschluckt Öffnung | Erreichbare Mehrdeutigkeit bewahrt die Vergleichsbasis; Transportausfall unterbricht sie | `test_runtime_safety.py` |
| F002 Import verwendet falsche aktive Werte | Binary-Schloss `on`, boolesche Personenattribute `true`, numerische Schwellen; fehlende Erkennung verlangt Einrichtung | Python- und Browserregression |
| F003 Gehaltene Stufe verhindert höhere Eskalation | Höhere Stufen bleiben erreichbar; die gehaltene Mindeststufe bleibt erhalten | `test_spatial_policy.py` |
| F004 Zusammenführung verliert Schutzparameter | Fenster übernehmen und speichern Debounce, Prellschutz, Override und Eingangsverzögerung | `test_runtime_safety.py` |
| F005 Langsames Abschalten blockiert Timer | Wartung und Engine-Takt laufen getrennt | Python- und echter Core-Prüfer |
| F006 Globaler Ausgabelock blockiert Sirene | Locks pro Zielgerät und getrennte Warteschlangen für bestätigte Ereignisse | Python- und echter Core-Prüfer |
| F007 Gleiche Hardware zählt doppelt | Signalquelle aus HA-Geräteregister, auch bei bestehenden Standardkennungen | Import- und Korrelationsregression |
| F008 Simulation startet nach Entschärfung | Generation unmittelbar vor dem Dienstaufruf erneut prüfen | `test_runtime_safety.py` |
| F009 Simulationsende schaltet Alarmlicht aus | Getrennte Besitzzeiten für Simulation und Alarm | `test_runtime_safety.py` |
| F010 Stufe 0 beendet Ausgänge nicht | Tatsächlicher Rückfall beendet eigene Alarmausgänge; Simulation/Test behalten ihren eigenen Ablauf | `test_runtime_safety.py` |
| F011 Abgewählte Regel bleibt aktiv | Abwahl entfernt die Stufenzuordnung in allen betroffenen Profilen | Browserregression |
| F012 Sensortabelle bleibt stehen | Zustandszellen werden aus Live-Ereignissen aktualisiert, Formulare bleiben bestehen | Browserregression |
| F013 Grundriss teilweise gelöscht | Gesamte Raum-/Profilbereinigung vor einem einzigen Konfigurationscommit validieren | Browserregression |
| F014 Widersprüchliche Fensterkalibrierung | Öffnungswerte gegen Stellung prüfen; geschlossen und offen sind beim Speichern Pflicht | `test_runtime_safety.py` |
| F015 Textkontakt nicht einlernbar | Getrennte offene/geschlossene Werte im Assistenten und Backend | Python- und Browserregression |
| F016 Begradigen verwirft bearbeitete Punkte | Aktuellen Entwurf statt der alten gespeicherten Geometrie übernehmen | Browserregression |

## Präzisierte Alarmentscheidung

Die Tests KOR01–KOR14 und zusätzliche Varianten prüfen passende Personenerkennung vor einem zugeordneten Eingang, echte Öffnung mit neuer Innenbewegung, nicht verbundene Räume, ausdrücklich gerichtete Wege, alte Ereignisse, allgemeine Außenbewegung, Schlossentriegelung und physisch identische Quellen. Mehrfachkontakt- und Mehrfachbewegungsregeln sind ausdrücklich wählbar und räumlich begrenzt. Unzugeordnete Kameras bestätigen keinen beliebigen Kontakt.

## Wiederanlauf und Arbeitslast

Eigene Sirenen, Lichter und Schalter werden bei einem weiterhin gültigen bestätigten Alarm nach Reload bis zum ursprünglichen Ablauf wieder aufgenommen. Benachrichtigungen und Skripte werden nicht erneut abgespielt. Zeitkritische bestätigte Aktionen haben eine getrennte begrenzte Warteschlange und Ausführungskapazität. Das Speichern von Laufzeit- und Ausgangszuständen ist zeitlich begrenzt.

## Bewusst beibehaltene Grenzen

- Eine während der Live-Beobachtung entstandene Kontakt-Quarantäne bleibt sichtbar und muss vor einer gewünschten erneuten Nutzung bewusst freigegeben werden. Fenstergriffe sind davon ausgenommen.
- Korrelation erfordert frische Ereignisse innerhalb der Profilzeiten. Ein seit Langem offenes Fenster und eine viel später beginnende Bewegung werden nicht automatisch zum bestätigten Einbruch. Die Offenanzeige und Scharfschaltprüfung bleiben davon unabhängig.
- Zulässige Wege, echte Personenerkennung und Hardware-Unabhängigkeit müssen zur Installation passen. Ein automatischer Import kann diese bauliche Prüfung nicht ersetzen.
- Softwareprüfungen ersetzen keinen kontrollierten Funktionstest der physischen Sirenen, Sensoren, Kameras und Push-Zustellung.
