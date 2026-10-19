# IQAlarm

**Erst verstehen, dann auslösen.** IQAlarm ist eine lokale Home-Assistant-Integration mit räumlicher Sensor-Korrelation, Prell-Schutz und eigenem deutschen Seitenpanel. Das Panel wird direkt als ES-Modul ausgeliefert. Auf dem Home-Assistant-System sind weder Node.js noch ein Frontend-Build nötig.

## Eigene Symbole

Unter **Kameras & Sensoren** einen Eintrag anklicken und **Symbol anpassen** öffnen. Gängige Symbole (Fenster, Tür, Schublade, Kühlschrank, Bewegung und weitere) sind direkt auswählbar. Eine eigene `mdi:…`-Kennung zeigt sofort eine Vorschau. **Automatisch** stellt das bisherige Symbol wieder her. Speichern, Raumwechsel und Sortieren übernehmen die Auswahl. Zusammengeführte Fenster haben ein eigenes Symbol; ihre Eingangssensoren bleiben erhalten. Das Raumsymbol lässt sich über das Symbol im Gruppenkopf oder unter **Räume & Grundriss → Raum bearbeiten** ändern. Die Auswahl gilt auch im Live-Status und ändert keine Alarmrollen oder Regeln.

## Frei konfigurierbare Alarmstufen

Die folgenden sechs Stufen sind die Startvorgaben ab 2.5.0. Unter **Level-Konfiguration** lassen sich weiterhin 1–32 Stufen mit eigenen Namen und Farben festlegen. Die Reihenfolge bestimmt die Zahl im Kreis; die Bezeichnung steht darüber. Jede Stufe enthält ihre frei konfigurierbaren Sensorregeln. Profile wählen die verwendeten Regeln und haben eigene Aktionen je Level. Aktionen verweisen auf feste Stufenkennungen. Bestehende eigene Stufen und Zuordnungen bleiben bei einem Update erhalten.

| Stufe | Bedeutung | Standardlogik |
| --- | --- | --- |
| 0 | Deaktiviert | Anlage ausgeschaltet; die optionale Live-Beobachtung läuft ohne Geräteaktionen weiter |
| 1 | Sicher | Aktives Profil ohne aktuelles Sicherheitssignal |
| 2 | Bewegung Außen | Person-/Perimeter-Erkennung; Gedächtnis standardmäßig 180 s |
| 3 | Erste Sensorauslösung / Fehlerfall | Einzelkontakt, Prellen oder fehlende Sensorverbindung; keine Einbruchsbestätigung |
| 4 | Bewegung Innen | Unbestätigte Innenbewegung, sofern das Profil sie auswertet |
| 5 | ALARM!!! | Unabhängige, zeitlich und räumlich passende Quellen oder ausdrücklich freigegebener Override |

Innenbewegung allein erzeugt auch auf Stufe 4 keinen Vollalarm. Im Nachtprofil bleibt sie ohne vorherige passende Öffnung ohne Eskalation. Stufe 5 benötigt eine Bestätigung; erst dort sind standardmäßig Sirenen und kritische Pushs freigegeben. Ein allein prellender Sensor kann diese Stufe nicht erreichen.

Der **Normalzustand bei aktivem Profil** ist separat wählbar (standardmäßig Stufe 1). Beim Rückfall werden eigene Alarmausgänge abgeschaltet. Stufe 0 und der aktive Normalzustand bleiben lautlos. Auslöser auf Stufe 0 sind deaktiviert. Alte Vier-Stufen-Konfigurationen behalten ihren bisherigen Normalzustand und ihre Aktionskennungen.

### Freie Auslöser und Bestätigung ab 2.6.0

Unter **Level-Konfiguration → Stufe → Regel hinzufügen** wählst du konkrete, zuvor zugewiesene Sensoren oder ganze Sensorgruppen. Eine Bedingung legt die Meldungsart und die Mindestzahl unabhängiger Quellen fest. Mehrere Bedingungen gelten gemeinsam; optional müssen sie in der angegebenen Reihenfolge eintreffen. Das Bestätigungsfenster gilt ab der ersten frischen Meldung. Eine zusätzliche Verzögerung nach erfüllter Regel ist separat einstellbar, bei Bedarf nur für Sensoren mit erlaubter Eingangsverzögerung.

Beispiel: Eine Kamera meldet eine Person und hebt auf die Vorfeld-Stufe. Eine weitere Regel verlangt innerhalb von 30 Sekunden zwei unabhängige Quellen aus der Auswahl „Personenkamera Terrasse, Personenkamera Einfahrt, Außenbewegungsmelder“. Beide müssen zu einem gemeinsamen Raum/Vorfeld oder einem ausdrücklich freigegebenen gerichteten Weg gehören. Erst diese erfüllte Regel hebt auf ihre gewählte Zielstufe. Zweimal dieselbe Kamera zählt weiterhin einmal; dauerhaft aktive oder beim Start bereits aktive Zustände erzeugen keine künstliche zweite Bestätigung.

Die höchste erfüllte Regel bestimmt die Stufe. „Sicher“ ergibt sich bei aktivem Profil automatisch, wenn keine höhere Regel erfüllt ist. Ein gehaltener bestätigter Alarm bleibt bis zum Entschärfen aktiv; eine höhere bestätigte Stufe kann ihn überlagern. Informationssignale der Fenstergriffe, ausgefallene und quarantänisierte Quellen bestätigen keinen Einbruch. Ein reines Schlossentriegeln mit Innenbewegung ersetzt keine physische Öffnung. Einzelsignale können eine bestätigungspflichtige Stufe nur über einen ausdrücklich freigegebenen Gefahrensensor erreichen.

### Bereits offene Fenster beim Scharfschalten ab 2.11.0

Beim Scharfschalten markiert IQAlarm bereits offene oder gekippte, überwachte Fenster automatisch als **Ignoriert**. Dafür gibt es keine zusätzliche Einstelloption und keine Bestätigungsabfrage. Die Ausnahme gilt für die gesamte Scharfschaltung: Schließen, erneutes Öffnen und Neustarts heben sie nicht auf. Erst beim Ausschalten wird sie verworfen. Beim nächsten Einschalten entscheidet wieder die dann vorhandene Fensterstellung.

Ignorierte Fenster liefern keine Öffnungswarnung, Prell-Auslösung, Alarmbestätigung oder Bestätigungsgrade. Der tatsächliche Zustand bleibt für die technische Fensteransicht erhalten. In der Übersicht steht **Ignoriert**; das Überwachungsrisiko zählt automatisch einen Punkt je Fenster, zusammen mit Roboter-Ausnahmen höchstens 3/3. Kameras, Bewegungsmelder und andere Kontakte werden weiter ausgewertet. Fenster, die beim Scharfschalten geschlossen waren, bleiben normal überwacht. Bei ausgeschalteter Anlage zeigen die Raumkarten keine redundante Alarmstufen-Plakette; die Sensorzustände bleiben sichtbar.

Die Erkennung nutzt zusammengeführte IQAlarm-Fenster und die Home-Assistant-Geräteklasse **window**, einschließlich einer im Entitätsregister gewählten Zuordnung. Der Name ändert diese Einordnung nicht: Eine als Fenster zugeordnete Terrassentür gilt als Fenster. Ein einzelner Kontakt mit Geräteklasse **door** wird als Tür behandelt. Türschlösser, unbekannte und ausgefallene Fenster werden nicht als bereits offene Fenster angenommen. Die vorhandene Scharfschaltprüfung für Türen/Tore und fehlende Verbindungen bleibt bestehen.

### Roboter-Ausnahmen ab 2.10.0

Unter **Level-Konfiguration → LVL 1 · Sicher → Roboter hinzufügen** lassen sich pro Gerät bis zu drei Aktivitätsentitäten mit ihren aktiven Zuständen eintragen. Eine aktive Entität genügt (ODER); mehrere Meldungen desselben Roboters zählen einmal. Optional kann der Zustand aus einem Attribut gelesen werden. Als Bereich wählst du einzelne Räume oder eine Etage mit gespeicherten Raumflächen.

Während der Aktivität ignoriert IQAlarm dort Innenbewegungs- und Präsenzmelder. Fenster, Türkontakte und Kameras bleiben in der Auswertung. Die Rohzustände der Bewegungsmelder bleiben sichtbar, erzeugen aber keine Alarmevidenz, Bestätigung oder rote Bewegungsanzeige. Beim Ende der Aktivität muss ein noch aktiver Melder erst Ruhe melden, bevor eine neue Bewegung wieder zählen kann. Dieser Nachlauf bleibt auch nach einem Neustart erhalten. Ein bereits gehaltener echter Alarm wird durch eine Roboterfahrt nicht aufgehoben.

Pro Roboter sind **1 bis 3 Risikopunkte** einstellbar. Das **Überwachungsrisiko** steigt nur für im aktuellen Profil tatsächlich ausgenommene Melder und insgesamt höchstens auf 3/3. Im Normalzustand zeigt der innere Ring diesen Wert; LVL 1 bleibt bestehen. Bei höheren Alarmstufen zeigt er weiterhin den echten Bestätigungsgrad. Das Überwachungsrisiko ist keine Einbruchsbestätigung und erfüllt keine Alarmvoraussetzung. Bei ausgeschalteter Anlage bleiben die Risikokarte und der Risikoring ausgeblendet.

Fehlende oder nicht verfügbare Aktivitätsquellen werden als Störung angezeigt und öffnen keine neue Ausnahme. Fällt die Verbindung während einer Fahrt aus, bleiben noch aktive Melder bis zu ihrer nächsten Ruhemeldung im Nachlauf. Roboter-Statusentitäten dürfen keine IQAlarm-Ausgaben oder zugleich verwendete Alarmeingänge sein. Anlegen, Ändern und Entfernen erfolgen bei entschärfter Anlage.

### Raumgrafik, Originalbild und Türen ab 2.9.0

Die fertige Vorschau und der Live-Grundriss richten Bildausschnitt und Seitenverhältnis an den erzeugten Raumflächen aus. Leere Ränder des hochgeladenen Bildes fallen weg. Raumgeometrie und gespeicherte Beschriftungspositionen behalten ihre Koordinaten; auch Beschriftungen am Rand werden berücksichtigt.

Unter **Räume & Grundriss → Fertige Raum-Grafik ansehen** lässt sich mit **Originalbild einblenden** die Zeichenvorlage von 0 bis 100 Prozent Deckkraft unterlegen. **Bildanzeige speichern** speichert diese Einstellung je Etage. Die Live-Seite zeigt das gespeicherte Ergebnis ohne Regler oder Speichern-Button. Standard ist 0 Prozent. Bild, Raumflächen und Sensorzuordnungen werden dabei nicht verändert.

Unter **Räume & Grundriss → Grundriss-Assistent → Türen / Raumverbindungen** kannst du zwei Räume nacheinander im Grundriss markieren oder über „Von Raum / Zu Raum“ verbinden. Markierst du dieselben verbundenen Räume erneut, entfernst du die Verbindung; dafür gibt es außerdem einen Entfernen-Button. Maus, Touch und Tastatur werden unterstützt. Die Linien und Türmarkierungen erscheinen nur in der Bearbeitungsansicht.

Eine ausdrücklich eingetragene Tür oder ein offener Durchgang verbindet die beiden Räume direkt für passende Alarmbestätigungen. Ein Öffnungssignal in A und Bewegung in B dürfen räumlich zusammenpassen, wenn A ↔ B eingetragen wurde. A ↔ B ↔ C erlaubt keine Bestätigung zwischen A und C. Sensorrollen, Zeitfenster, unabhängige Quellen, konfigurierte Vorfeldbestätigung und Prell-Schutz gelten weiterhin. Berührende Polygone und alte allgemeine Nachbarschaftsangaben erzeugen keine Türfreigabe. Vorhandene gerichtete Bestätigungswege bleiben erhalten.

### Live-Anzeige und Bestätigungsgrade ab 2.8.0

Das Cockpit zeigt zwei Ringe: außen die Alarmstufe im Verhältnis zur höchsten konfigurierten Stufe, innen den **Bestätigungsgrad** der aktuell angezeigten Stufe. Im Grundriss bleiben ruhige Räume nur mit ihrem Namen sichtbar; „Ruhig“, Sensoranzahl und „Bestätigte Korrelation“ entfallen dort. Aktivitätsfarben blenden innerhalb von 1,5 Sekunden zur Normalfarbe zurück. Bewegungstext und Farbziel nutzen weiterhin dieselbe 15-Sekunden-Nachlaufzeit; bei reduzierter Bewegungseinstellung entfallen Animationen.

In **Level-Konfiguration → Regel bearbeiten → Bestätigungsgrad & Gedächtnis** lassen sich Anzahl der Grade, unabhängige Meldungen je Grad und eine eigene Ruhezeit pro Rückstufung einstellen. Beispiel: drei Grade mit Schwellen 1, 2 und 3 sowie je 60 Sekunden Ruhezeit. Eine zweite unabhängige Quelle erhöht 1/3 auf 2/3; nach 60 Sekunden ohne neue Meldung fällt der Grad auf 1/3, nach weiteren 60 Sekunden auf 0. Verarbeitete alte Meldungen steigen beim nächsten Timerlauf nicht wieder auf. Neue gültige Meldungen starten die Ruhezeit neu; dasselbe physische Gerät zählt weiterhin nur einmal. Das Bestätigungsfenster begrenzt zusätzlich das Alter der Einzelmeldungen. Bereits vorhandene Regeln behalten ihr bisheriges Verhalten, bis die schrittweise Rückstufung eingeschaltet wird.

**Bestätigung merken** ist ein eigener Timer: Eine vollständig erreichte Bestätigung bleibt bis zu ihrem Ablauf für verknüpfte Folgeregeln nutzbar, auch wenn der sichtbare Grad inzwischen sinkt. Ein neuer Tür-/Fensterkontakt muss weiterhin zeitlich nach der Bestätigung und räumlich passend eintreffen.

Unter **Profile & System → Aktionen je Alarmstufe → Aktion hinzufügen/bearbeiten → Ausführen bei** stehen **Beim Erreichen des Levels** und **Bei vollständiger Bestätigung** getrennt zur Auswahl. So kann beispielsweise erst 3/3 eine Nachricht auslösen, ausschließlich im ausgewählten Alarmmodus. Ohne zugeordnete Aktion bleibt die vollständige Bestätigung ohne Geräteaktion. Neustart und normale Timerläufe spielen die Benachrichtigung nicht erneut ab. Die entfernten allgemeinen Checkboxen werden beim Bearbeiten von Namen und Farben nicht versehentlich zurückgesetzt; bestehende Sicherheitsgrenzen bleiben erhalten.

### Bestätigungsgrad und Vorfeldgedächtnis ab 2.7.0

Die größere Quellenauswahl zeigt hinter gewählten Sensorgruppen die konkreten Entitäten mit Anzeigename, Entitäts-ID, Raum und Livezustand. Aktive Quellen sind hervorgehoben; isolierte, nicht erreichbare oder durch die Raumbegrenzung ausgeschlossene Quellen werden erläutert.

**Auslösen ab** legt fest, wie viele unabhängige Quellen eine Stufe starten. Mit **Bestätigungsgrad für diese Regel verwenden** erhält sie ein eigenes **Bestätigungsziel** und die Dauer **Bestätigung merken (Minuten)**. Beispiel: LVL 2 beginnt bei einer Quelle, zeigt danach 1/3, 2/3 und schließlich 3/3. Erst 3/3 speichert die räumlich und zeitlich zusammenhängende Bestätigung. Wiederholungen derselben Kamera und Entitäten desselben Geräts zählen einmal. Drei Außenquellen allein lösen keinen Einbruchsalarm aus.

Für den Vollalarm eine Regel mit den Tür-/Fensterkontakten anlegen und bei **Gespeicherte Bestätigung voraussetzen** die Vorfeldregel wählen. Erst ein **neues Öffnungssignal nach der Bestätigung**, innerhalb ihrer Speicherzeit und im passenden Raum/Vorfeld oder ausdrücklich erlaubten Weg, erreicht die Zielstufe. Die Vorfeldregel wird den gewählten Alarmmodi ebenfalls zugeordnet. Wenn ausschließlich dieser Bestätigungsweg gewünscht ist, im Profil nur die entsprechenden Alarmregeln verwenden: weitere Regeln derselben Zielstufe bleiben alternative Auslösewege.

Das Cockpit zeigt den Bestätigungsgrad und den Ablaufzeitpunkt. Der Speicher verlängert sich nicht durch Timerläufe. Profilwechsel/Entschärfen löschen ihn; Neustarts erhalten nur gültige Beweise mit unverändertem Ablauf und unveränderter räumlicher/physischer Zuordnung. Eine bereits ausgelöste gehaltene Alarmstufe bleibt entsprechend ihrer Halteregel bestehen.

### Aktionen je Level und Alarmmodus

Unter **Profile & System** wählst du oben den Alarmmodus und seine Levelregeln. Ganz unten stehen **Aktionen je Alarmstufe** für genau diesen Modus. Dort lassen sich Push, Licht, Sirenen, Kameraaufnahmen, Rollos und weitere Aktionen anlegen, bearbeiten, entfernen und pro Stufe trocken testen. Der zusätzliche Schalter für einen realen Test führt Geräteaktionen aus. Auch der aktive Normalzustand kann eigene lautlose Aktionen erhalten.

Aktionen anderer Modi bleiben getrennt. Beim Duplizieren eines Profils werden seine Aktionen kopiert; spätere Änderungen an der Kopie verändern das Original nicht. Eine aus älteren Versionen gemeinsam verwendete Aktion wird beim Bearbeiten für den gewählten Modus abgetrennt. Für Kameraaktionen verwendet das Ziel `trigger_camera` die tatsächlich zur Auslösekette gehörenden Kameras.

Die alten zusätzlichen Sensorfilter, Kombinationsschalter und Zuordnungstabellen entfallen in der neuen Profiloberfläche. Bestehende Konfigurationen werden einmalig in gleichwertige Regeln und Aktionszuordnungen überführt. Räumliche Wege, ausgewählte Sensoren, Zeitfenster und die Nacht-Freigabe erst nach Öffnung bleiben dabei erhalten. Eine zuvor ausdrücklich leere Sensorauswahl bleibt leer und schaltet keine fremden Regeln frei. Die ursprüngliche Konfiguration wird vor der Speicher-Migration privat unter `.storage/iqalarm.configuration.before_level_rules` gesichert.

### Sensoren bearbeiten, sortieren und löschen

Unter **Kameras & Sensoren** öffnet ein Klick auf einen Eintrag den Sensor-Dialog. Dort lassen sich Anzeigename und Raum ändern, die Position mit **Nach oben / Nach unten** verschieben und der Sensor nach Rückfrage aus IQAlarm löschen. Am Desktop lassen sich Einträge auch innerhalb ihrer Gruppe oder in einen anderen Raum ziehen. Die Reihenfolge wird pro Raum gespeichert und auch im Live-Cockpit angezeigt. Ein zusammengeführtes Fenster bleibt ein Eintrag; seine Quellen bleiben darunter gruppiert.

**Sensor löschen** entfernt IQAlarm-Zuordnungen und bereinigt Profil- und Sortierverweise. Bei einem zusammengeführten Fenster werden auch dessen zugehörige IQAlarm-Eingangszuordnungen entfernt; mit einem anderen Fenster gemeinsam verwendete Quellen bleiben erhalten. Die ursprünglichen Home-Assistant-Entitäten werden nicht gelöscht. **Fenster entfernen** in der technischen Fensterliste löst weiterhin nur die Zusammenführung auf.

### MACO-/Kontakt-Prellen

Öffnungs-, Riegel- und Vibrationssensoren werden standardmäßig ab drei echten Zustandswechseln innerhalb von 15 Sekunden isoliert, wenn keine unabhängige Bestätigung vorliegt. `on → off → on` bei anfänglichem `off` sind drei Wechsel. Wiederholte identische Werte, `unknown` und `unavailable` zählen nicht als Wechsel.

Ein isolierter Sensor liefert keine Einbruchsbestätigung mehr. Die Quarantäne bleibt bis zum Entschärfen oder einer bewussten Freigabe erhalten, auch nach einem Neustart. Sie wird im Cockpit angezeigt und kann eigene lautlose Diagnoseaktionen auslösen. Ein zuvor unabhängig bestätigter Vollalarm wird durch spätere Kontaktwechsel nicht gelöscht.

Die optionale Mindest-Aktivzeit filtert kurze Impulse, während die Prell-Erkennung weiterhin die ungefilterten Wechsel beobachtet. Werte pro Sensor überschreiben die Vorgabe der Rolle; `0` verwendet die Rollenvorgabe.

### Räumliche Bestätigung ab 2.4.0

- **Person vor dem passenden Eingang:** Nur die Rolle `perimeter_camera` bestätigt eine Person. Die Kamera muss dem betroffenen Raum oder dessen Vorfeld zugeordnet sein und vor der Öffnung ausgelöst haben. Eine nicht zugeordnete Kamera und generische Außenbewegung bleiben Vorfeldanzeigen.
- **Öffnung und neue Innenbewegung:** Ein echter Öffnungskontakt und Bewegung im selben Raum bestätigen sich innerhalb des Zeitfensters. Im Nachtprofil muss die Bewegung nach der Öffnung beginnen. Eine Entriegelung am Türschloss ersetzt keinen Öffnungskontakt.
- **Gezielt erlaubte Wege:** Unter **Profile & System → Profil bearbeiten → Ausdrückliche Bestätigungswege** lässt sich etwa Wohnzimmer → Flur erlauben. Der Weg gilt nur in dieser Richtung und direkt; allgemeine Nachbarschaft, Hausfreigabe oder mehrere Zwischenräume reichen nicht.
- **Zwei Kontakte / zwei Bewegungsmelder:** Diese Regeln sind zunächst ausgeschaltet. Nach ausdrücklicher Aktivierung gelten ebenfalls derselbe Raum oder ein erlaubter Bestätigungsweg. Fenster in Raum Z und Bewegung in einem unverbundenen Raum A bestätigen keinen Einbruch.
- **Physische Unabhängigkeit:** Entitäten eines registrierten HA-Geräts erhalten automatisch dieselbe Signalquellenkennung. Ein zusammengeführtes Fenster und seine Rohsignale zählen einmal. Eine bewusst eigene Kennung kann getrennte Hardware beschreiben; sie muss der tatsächlichen Installation entsprechen.

Das Logbuch erklärt passende Auslöseketten und abgelehnte räumliche Kombinationen. Ein allein prellendes MACO-Schloss erzeugt weiterhin höchstens Verdacht beziehungsweise eine Diagnose. Ein bereits bestätigter Alarm kann auf eine höhere eigene Stufe eskalieren, auch wenn die bisherige Stufe gehalten wird.

**Migration:** Vorhandene Räume, Profile, Aktionen, PIN, Fenster, Grundrisse und Quarantäne bleiben erhalten. Bisherige implizite globale Kamera- oder Nachbarschaftsbestätigungen werden durch die obigen Regeln ersetzt. Bereits gespeicherte Bestätigungen werden beim Laden erneut geprüft. Erlaubte Wege und Personenzuordnungen müssen anhand der tatsächlichen Installation kontrolliert werden; IQAlarm erfindet keine räumlichen Verbindungen.

## Unabhängige IQAlarm-Profile

Profile haben freie Namen und definieren die gesamte Steuerung. Es gibt **keine Zuordnung zu HA-Modi**. Zuhause, Nacht, Abwesend und Urlaub sind bearbeitbare und löschbare Startvorgaben; selbst ihre Kennungen bestimmen keine Regeln.

Jedes Profil wählt seine verwendeten Levelregeln, erlaubt oder unterdrückt Geräteaktionen und kann eine eigene Scharfschaltverzögerung sowie Anwesenheitssimulation verwenden. Sensoren, räumliche Bedingungen und Bestätigungsfenster stehen ausschließlich an der Levelregel. Die Aktionen jedes Modus werden im selben Profil ganz unten gepflegt.

Das Nachtprofil verwendet standardmäßig keine eigenständige Innenbewegungsregel. Bewegung ist weiterhin auf dem Grundriss sichtbar. Für einen Alarm müssen etwa zuerst ein Öffnungssignal und anschließend eine neue passende Bewegung auftreten. Bereits aktive Präsenz liefert keine neue Bestätigung. Ein Profil ohne verwendbare Sensoren lässt sich nicht scharfschalten. Schutzprofile müssen vor einem Wechsel mit der optionalen PIN deaktiviert werden.

Die Grundrissdarstellung wird unter **Räume & Grundriss → Darstellung im Live-Grundriss** eingestellt. Scharfschaltprüfung und Diagnose stehen unter den erweiterten Systemeinstellungen. Die Anwesenheitssimulation wird pro Profil eingeschaltet und verwendet die darunter ausgewählten Lichter und Abendzeiten.

### Live-Beobachtung und Grundriss

**Aus · Live** deaktiviert Alarmreaktionen. Ein wählbares Hintergrundprofil wertet weiterhin Signale und Korrelation aus und zeigt die erreichte Stufe. Das automatisch angelegte Profil „Live-Beobachtung“ schaltet keine Geräte, sendet keine Pushs, speichert keine Kameraaufnahmen und simuliert keine Anwesenheit. Bestätigungen laufen hier wieder aus. Weitere Beobachtungsprofile können eigene Sensoren und Regeln verwenden. Ohne Hintergrundprofil bleiben die Rohzustände sichtbar.

Unter **Räume & Grundriss → Grundriss hochladen** direkt eine PNG-/JPG-Datei auswählen und der Etage einen Namen geben (maximal 10 MB, 8192 Pixel pro Seite, 32 Megapixel). Bild und Etage werden zusammen gespeichert; ein fehlgeschlagener Upload hinterlässt keinen leeren Eintrag. Vorhandene Etagen haben einen sichtbaren Button **Bild ersetzen**.

Der Assistent schlägt anschließend lokal Raumflächen vor. Es werden keine Bilder an einen externen Dienst übertragen. Einen Vorschlag auswählen, einen vorhandenen IQAlarm-Raum zuordnen und den Umriss prüfen. Eckpunkte lassen sich mit Maus oder Finger verschieben sowie per Pfeiltasten korrigieren und mit Entf entfernen. **Neu zeichnen** erlaubt eine vollständig eigene Fläche, etwa für offene Wohn-/Küchenbereiche oder die Terrasse. Die Erkennung stellt den Lückenausgleich automatisch ein. Zusätzliche Einstellungen liegen unter **Erweiterte Erkennung**. Bei farbigen Bauplänen verwendet sie die strukturelle Wandfarbe und angeschlossene Linien, damit Möbel und Terrassenschraffuren nicht als Räume behandelt werden. Möbel, Beschriftungen und offene Übergänge können unpassende Flächen ergeben; Raumtypen und Namen werden nicht automatisch erkannt. Erst **Bereich speichern** übernimmt die Zuordnung.

**Vorhandene Home-Assistant-Bereiche direkt auswählen.** Sowohl die Raumauswahl im Grundriss als auch der Speicherdialog zeigen vorhandene IQAlarm-Räume und noch nicht verknüpfte HA-Bereiche. Ein separater Import ist nicht erforderlich. Erst beim Speichern werden der ausgewählte Bereich und die bearbeitete Fläche gemeinsam übernommen. Bereits verknüpfte Bereiche erscheinen nur einmal; bestehende Raum-, Sensor- und Profilzuordnungen bleiben erhalten.

**Entwürfe gehen bei der Raumauswahl nicht verloren.** Der Raum wird der bearbeiteten Fläche zugeordnet, ohne ihre Eckpunkte zu ersetzen. Fehlt beim Speichern noch ein Raum, öffnet sich die Zuordnung direkt im Speicherdialog; dort kann auch ein neuer Raum angelegt werden. Rückgängig/Wiederholen sowie Strg+Z / Strg+Umschalt+Z im Grundriss stellen Bearbeitungsschritte wieder her. Der Entwurf und seine Historie werden je Benutzer, Etage und Bild im lokalen Browser gesichert und nach Neuladen wieder angeboten. Diese Sicherung ist lokal; sie verändert die in HA gespeicherten Flächen erst beim ausdrücklichen Speichern. Bei gesperrtem oder vollem Browserspeicher weist der Editor darauf hin. Außenbereiche werden ebenso als Raum markiert. Die bestehenden Sensorzuordnungen liefern automatisch Fenster-/Türstatus, Bewegung, Personen und Quarantäne. Markierungen bleiben bei Größenänderungen proportional erhalten. Der Live-Grundriss zeigt auch Signale, die ein Profil nur anzeigt. Ein Klick auf den Raum öffnet Sensorstatus und gegebenenfalls die verknüpfte HA-Kamera.

Grundrissbilder werden als bereinigte PNG-Dateien privat unter `.iqalarm_floorplans` gespeichert. Abrufe und Uploads benötigen einen HA-Administrator. Bilder und Markierungen bleiben bei Neustarts und HACS-Updates erhalten.

Die Bewegungsanzeige im Live-Grundriss verwendet einen gemeinsamen 15-Sekunden-Nachlauf für Text und rote Raumfarbe. Solange ein Melder aktiv ist, bleiben beide sichtbar. Nach seiner Ruhemeldung enden sie gemeinsam nach 15 Sekunden; eine erneute Bewegung startet den Nachlauf neu. Das längere Korrelationsfenster beeinflusst diese Anzeige nicht. Bestätigte Alarme behalten ihre eigene rote Darstellung samt ausdrücklicher Beschriftung.

In der schnellen Raum-Zuweisung öffnet ein Klick **Sensor-Einstellungen**. Dort lassen sich Anzeigename, Symbol und bei einzelnen Sensoren die **Art** ändern. **Speichern** übernimmt die Einstellungen ohne Raumwechsel; die Raumauswahl speichert sie zusammen mit dem Zielraum. Sortieren erhält die Auswahl ebenfalls. Zusammengeführte Fenster behalten ihre Fenster-Auswertung. Die ursprünglichen HA-Entitätskennungen bleiben erhalten.

Mit **Art → Bewegung bei Zustandswechsel (15 s)** lässt sich beispielsweise ein Innentürkontakt als Bewegungsmelder verwenden. Sowohl Zu → Auf als auch Auf → Zu starten eine 15-sekündige Aktivität; jeder weitere echte Wechsel startet die Zeit neu. Ein dauerhaft offener Kontakt ist dabei keine Öffnungswarnung. Gleiche Meldungen, Startzustände und die Rückkehr nach einem Verbindungsfehler erzeugen keine Bewegung. Fehlende Verbindung bleibt eine Störung. Die neue Art gilt auch für Sensorgruppen, Raumkorrelationen und Roboter-Ausnahmen. Die angezeigte Aktivität endet ohne zusätzliche visuelle Nachlaufzeit.

### Profilsymbole

Unter **Profile & System** hat jedes Profil ein eigenes, frei wählbares Symbol. Die Vorgaben sind Haus (Zuhause), Mond (Nacht), Haus mit Ausgang (Abwesend), Palme (Urlaub) und Personengruppe (Besuch). Der Aus-Schalter verwendet das Power-Symbol. Die Auswahl enthält eine grafische Vorschau und erlaubt zusätzliche MDI-Kennungen wie `mdi:dog`. Eigene Symbole und die Profilreihenfolge bleiben beim Bearbeiten, Duplizieren und nach Neustarts erhalten. Symbole ändern keine Alarmregeln.

### Einfache HA-Anbindung

`binary_sensor.iqalarm_aktiv` meldet ausschließlich **an / aus** für erlaubte Alarmreaktionen. Profilname und Alarmstufe sind eigene Sensorinformationen. Die HA-Alarmkarte erhält einen generischen Scharf-Knopf (`armed_away` als technischer HA-Zustand); dieser aktiviert das zuletzt verwendete Schutzprofil. Es ist keine Profilzuordnung erforderlich. Ein bestätigter Alarm meldet weiterhin `triggered`, Ein-/Ausgangsverzögerungen `pending` / `arming`. Beobachtung bleibt für die HA-Alarmkarte `disarmed`, auch wenn die Live-Bewertung hoch ist.

Die Migration übernimmt vorhandene Profile, Auswahl, Regeln, Aktionen, PIN und Quarantäne. Frühere HA-Basismodi werden einmalig in explizite Profilregeln übersetzt und anschließend nicht mehr ausgewertet.

## Fenster-Assistent und Schlösser

Unter **Kameras & Sensoren → Türen, Fenster & Schlösser (Außenhaut) → Fenster einrichten** werden ein Fensterkontakt, bis zu zwei Griffsignale, die optionale Schlossentität und eine Verbindungsüberwachung zu einem Fenster zusammengeführt. Ein einfacher Kontakt benötigt nur die Schritte geschlossen/offen. Mit Griffsignalen führt der Assistent durch geschlossen, entriegelt aber geschlossen, offen, Griff in Kippstellung bei geschlossenem Fenster und gekippt geöffnet. Nicht unterscheidbare Stellungen lassen sich nicht doppelt einlernen; nicht unterstützte Schritte können übersprungen werden. Die abschließende Live-Vorschau zeigt die erkannten Stellungen und Eingangssignale. Erst **Fenster speichern** übernimmt die Konfiguration.

Fensterzeilen zeigen **Fensterzustand | Schlosszustand**, beispielsweise **Geschlossen | Entriegelt** oder **Gekippt | Verriegelt**. Ohne zugeordnetes Schloss steht rechts „Nicht zugeordnet“; unbekannte und ausgefallene Meldungen bleiben ausdrücklich erkennbar. Zusätzliche als Fenstergriff konfigurierte Geräteinformationen (zum Beispiel Aktor-Meldungen) werden über das HA-Geräteregister dem eindeutigen Fenster im selben Raum untergeordnet. Bei mehreren möglichen Fenstern bleibt die Zuordnung offen. Zusatzinformationen sind keine Pflichtsignale der Kalibrierung und keine Alarmeingänge.

Alle Quellen stehen eingerückt unter dem Fenster; sie erscheinen nicht zusätzlich verstreut in der Außenhautliste oder als neue Vorschläge im Entitätskatalog. Die Integration erzeugt einen HA-Sensor für die Fensterstellung und einen Öffnungs-Binary-Sensor. Zuordnungen und eindeutige Entity-IDs bleiben bei Neustarts erhalten. Beim Entfernen der Zusammenführung werden die IQAlarm-Ausgabesensoren entfernt; die ursprünglichen HA-Entitäten bleiben bestehen.

**Fehler sind keine Fensterstellung.** Bei einem ausgefallenen benötigten Eingang oder einer ausgefallenen Verbindungsüberwachung steht im Panel „Keine Verbindung“ und der Stellungssensor wird nicht verfügbar. Unbekannte Signalkombinationen werden als „Stellung nicht eindeutig“ angezeigt. Eine ausdrücklich dokumentierte Codierung `unknown` kann für Griffsignale nur mit separater Verbindungsüberwachung aktiviert werden. `unavailable` ist immer ein Fehler. Ein weiterhin verfügbarer physischer Fensterkontakt wird trotz eines ausgefallenen Griffs unabhängig für die Alarmbewertung ausgewertet. Kurze Zwischenmeldungen werden vor der Erkennung stabilisiert. Ein erreichbarer, vorübergehend mehrdeutiger Griffzustand verschluckt keine anschließende echte Öffnung. Nach einem tatsächlichen Verbindungsausfall wird dagegen keine Öffnungsflanke erfunden. Textkontakte unterstützen getrennte Listen für geöffnet und geschlossen. Widersprüchliche oder unvollständige Kalibrierungen werden vor dem Speichern abgelehnt. Schutzparameter des vorhandenen Kontakts werden übernommen und können im Assistenten angepasst werden.

**Fenstergriff und Türschloss sind eigene Gerätearten.** Fenstergriffe liefern reine Informationen: Sie ändern keine Alarmstufe, bestätigen keinen Einbruch, verhindern keine Scharfschaltung und werden durch normales Ver-/Entriegeln nicht in Prell-Quarantäne gesetzt. Bei ausgeschalteter Anlage erscheinen Entriegelungshinweise nicht in der Übersicht; bei eingeschalteter Anlage werden sie kompakt als **Potenziell unsicher** dargestellt. In den Sensordetails bleiben sie sichtbar. Eindeutig als Fenstergriff benannte Bestandsentitäten werden bei der Migration so eingeordnet; die Geräteart kann manuell angepasst werden. Bestehende falsche Griff-Quarantäne und darauf beruhende Bestätigungen werden beim Laden verworfen. Türschlösser behalten ihre profilabhängige Verdachts- und Prellbewertung. Eine vorherige passende Personenerkennung kann bestätigen; Entriegelung plus Innenbewegung allein genügt nicht.

Ein zusammengeführtes Fenster zählt als **eine physische Alarmquelle**. Seine Griffsignale und sein Kontakt können sich niemals gegenseitig einen Einbruch bestätigen. Profile mit expliziter Sensorauswahl berücksichtigen auch die ausgewählten Stellungseingänge eines zusammengeführten Fensters. Information, Warnung, Alarm und Störung werden unabhängig von den eigenen Alarmstufen ausgewiesen; **Isoliert** bezeichnet einen bewusst deaktivierten Eintrag, **Prell-Quarantäne** einen technischen Ausschluss.

## Installation und Einrichtung

Unterstützt: **Home Assistant ab 2025.12.0**, geprüft mit 2025.12.5 und 2026.10.2.

1. In HACS unter **Benutzerdefinierte Repositorys** die URL `https://github.com/marcohildebrandtmail-hub/IQAlarm` als Typ **Integration** hinzufügen und IQAlarm herunterladen. Alternativ `custom_components/iqalarm` vollständig nach `/config/custom_components/iqalarm` kopieren.
2. Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → IQAlarm** einrichten. Optional eine 4–12-stellige PIN zum Entschärfen vergeben.
4. Im Seitenmenü **IQAlarm** öffnen. Das Konfigurationspanel ist Administratoren vorbehalten.
5. Räume aus HA importieren oder anlegen und Sensoren sowie Personenkameras zuweisen. Der Import übernimmt zunächst nur die Räume; Sensorrollen werden bewusst zugeordnet.
6. Unter **Profile & System** Zeiten und Regeln kontrollieren. Erlaubte Bestätigungswege ausdrücklich auswählen. Standardmäßig verhindern offene Kontakte und nicht verfügbare Sensoren das Scharfschalten; Fenstergriff-Informationen blockieren nicht.
7. Unter **Level-Konfiguration** die eigenen Dienste und Geräte zuweisen. Es werden keine Sirenen oder Benachrichtigungsziele automatisch ausgewählt.
8. Trockenläufe ausführen und anschließend mit bewusst gewähltem realem Aktionstest die eigenen Geräte prüfen.

Die gesamte Alarmkonfiguration erfolgt im Panel. Es sind keine HA-Automatisierungen und keine YAML-Regeln erforderlich. Änderungen an Räumen, Sensoren, Profilen und Aktionen sind im unscharfen Zustand möglich. Gleichzeitige Änderungen aus mehreren Browserfenstern werden über Konfigurationsrevisionen geschützt.

Alarm und Anwesenheitssimulation führen getrennte Besitzzeiten für übernommene Lichter. Das Beenden der Simulation schaltet kein noch für einen Alarm benötigtes Licht aus. Eine inzwischen deaktivierte Anlage startet keine neue Simulationsaktion.

Die Präsenzsimulation ist zusätzlich als native Schalter-Entität verfügbar und benötigt zusätzlich die Freigabe des aktiven Schutzprofils. Sie verwendet lokale HA-Zeit, schaltet zufällig ausgewählte ausgeschaltete Lichter zwischen den gewählten Stunden ein und übernimmt keine bereits eingeschalteten Lichter.

### Kamera-Erkennung und Dateien

Bevorzugt wird die Personen-Erkennungsentität der Kamera, beispielsweise ein `binary_sensor` von Frigate, Reolink oder UniFi. Dazu kann eine `camera.*` für Bilder und Aufzeichnungen verknüpft werden.

Direkte `camera.*`-/`image_processing.*`-Auslöser benötigen ein explizites Erkennungsattribut und passende aktive Werte. `streaming` oder `idle` werden nicht als Personenerkennung interpretiert. Der Import erkennt boolesche Personenattribute (`true`) und numerische Personenzähler (Schwelle größer null). Ohne geeignetes Erkennungsattribut verlangt er eine manuelle Zuordnung. Numerische Schwellen und aktive Textwerte lassen sich im Sensorformular einstellen.

Snapshots werden über `camera.snapshot`, Aufzeichnungen über `camera.record` ausgeführt. IQAlarm gibt ausschließlich sein eigenes Verzeichnis `/config/.iqalarm_media` für diese Dateizugriffe frei. Die Kamera muss den jeweiligen Dienst unterstützen; Aufzeichnungen benötigen eine stream-fähige Kamera. Automatische Snapshots sind eingeschaltet, automatische Aufzeichnung ist optional.

Dateien liegen außerhalb des öffentlichen `/local`-Bereichs und werden standardmäßig nach sieben Tagen gelöscht. Der Bildabruf verlangt HA-Authentifizierung; zusätzlich werden Administratorrechte oder Leserechte für die Kamera geprüft. Mobile Push-Anhänge benötigen eine entsprechend eingerichtete Companion-App und eine erreichbare HA-URL.

### Aktionen und Tests

- Lautlose Stufen und Diagnose: normale Pushs, Licht, Rollos, Snapshots und Aufzeichnungen (nur bei freigegebenen Profilreaktionen).
- Bestätigte, akustisch freigegebene Stufen: zusätzlich Sirenen, Schalter, Skripte, TTS und kritische Mobile-App-Pushs.
- Freie Schalter-/Skript-/Sprachaktionen sind unteren Stufen nicht erlaubt, weil damit eine Innensirene indirekt ausgelöst werden könnte.
- Kritische Pushs/Bilder brauchen einen passenden `notify.mobile_app_*`-Dienst. Generische `notify.*`-Entitäten unterstützen gewöhnliche Textnachrichten über `notify.send_message`.
- Vorlagen unterstützen `{{room}}`, `{{sensor}}`, `{{level}}`, `{{reason}}`, `{{chain}}`, `{{mode}}` und den Profilnamen `{{profile}}`. Andere Jinja-Ausdrücke werden nicht ausgeführt.
- IQAlarm schaltet selbst eingeschaltete Sirenen, Schalter, Skripte und Lichter nach der konfigurierten Dauer, beim tatsächlichen Rückfall auf Stufe 0 oder beim Entschärfen aus. Ein ausdrücklich ausgeführter Gerätetest behält seine eigene Dauer. Bereits eingeschaltete Geräte werden nicht zum späteren Abschalten übernommen. Rollos werden geöffnet und bleiben offen.
- Aktionsfehler erscheinen im Logbuch. Ein fehlerhafter Kameraabruf unterdrückt die Textbenachrichtigung nicht. Langsame Push-/Kameradienste blockieren die Sireneneskalation nicht.
- Ein Trockenlauf verändert keine Alarmstufe und schaltet keine Geräte. Nur der ausdrücklich aktivierte reale Test führt Aktionen aus.

PINs werden ausschließlich gesalzen und gehasht gespeichert. Wiederholt falsche Versuche werden begrenzt. Konfiguration, Quarantäne, aktive Timer, Auslösekette und bis zu 500 Ereignisse liegen im privaten HA-Store `.storage/iqalarm.configuration`; das Panel zeigt die letzten 50 Ereignisse.

Nach einem Neustart wird der gewählte Modus einschließlich Quarantäne und bestätigtem Alarm wiederhergestellt. Pushs, Skripte und Sprachmeldungen werden nicht erneut abgespielt. Während des Herunterfahrens werden von IQAlarm übernommene Ausgänge ausgeschaltet. Bei weiterhin gültigem bestätigtem Alarm werden ausschließlich eigene Sirenen, Lichter und Schalter bis zum ursprünglichen Ablaufzeitpunkt wieder eingeschaltet; fehlgeschlagene Wiederaufnahmen werden begrenzt erneut versucht. Ein während des Neustarts abgelaufener bestätigter Eingangstimer eskaliert nach dem Laden.

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

WebSocket-Befehle: `iqalarm/get`, `iqalarm/subscribe`, `iqalarm/catalog`, `iqalarm/config/save`, `iqalarm/crud`, `iqalarm/import_areas`, `iqalarm/set_mode`, `iqalarm/arm_profile`, `iqalarm/clear_quarantine`, `iqalarm/test_level`, `iqalarm/floorplan/analyze`, `iqalarm/window/preview`, `iqalarm/window/capture`. CRUD unterstützt Räume, Sensoren, Aktionen, Profile, Grundrisse, Fenster und Levelregeln. Stufen werden mit der gesamten Konfiguration gespeichert. Neue Etage mit Bild: POST `/api/iqalarm/floorplans/upload?name=Etagenname`. Die Flächenanalyse ist schreibgeschützt. Geschützte Bild-API: GET/POST `/api/iqalarm/floorplans/{id}/image`; Upload mit aktuellem `X-IQAlarm-Revision`-Header. Alle Befehle verlangen einen Administrator. CRUD und Konfigurationsänderungen verlangen die aktuelle `revision`.

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
