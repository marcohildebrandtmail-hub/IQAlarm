import {randomId} from "./floorplan-rooms.js?v=2.4.9";
/* Directly executable window setup wizard. All recognition is verified by HA. */
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const labels = {
  closed: "Geschlossen",
  unlatched: "Geschlossen · entriegelt",
  open: "Offen",
  tilt_ready: "Geschlossen · Griff in Kippstellung",
  tilted: "Gekippt geöffnet",
};

const instructions = {
  closed: "Fenster vollständig schließen und verriegeln.",
  unlatched: "Jetzt entriegeln, das Fenster aber geschlossen lassen.",
  open: "Jetzt das Fenster öffnen.",
  tilt_ready: "Fenster wieder geschlossen halten und den Griff in Kippstellung bringen.",
  tilted: "Jetzt das Fenster gekippt öffnen.",
};

const STEPS_INFO = {
  closed: {
    title: "1. FENSTER VOLLSTÄNDIG SCHLIESSEN",
    action: "Fensterflügel komplett schließen und Griff ganz nach unten drehen",
    detail: "Bringe das Fenster in die Schließstellung (Griff senkrecht nach unten). Der Fensterkontakt muss geschlossen melden.",
    icon: "🪟",
    badge: "Geschlossen",
  },
  unlatched: {
    title: "2. GRIFF IN DREHSTELLUNG (FLÜGEL ANGELEHNT)",
    action: "Griff in Normalstellung drehen, Flügel geschlossen angelehnt lassen",
    detail: "Drehe den Fenstergriff waagerecht, drücke den Fensterflügel aber noch nicht auf. (Kann übersprungen werden).",
    icon: "🔓",
    badge: "Drehstellung",
  },
  open: {
    title: "3. FENSTER GANZ ÖFFNEN",
    action: "Fensterflügel jetzt ganz aufschwenken",
    detail: "Öffne das Fenster vollständig. Der Kontakt meldet offen, der Griffsensor steht auf Drehöffnung.",
    icon: "🪟",
    badge: "Geöffnet",
  },
  tilt_ready: {
    title: "4. GRIFF AUF KIPP DREHEN (FLÜGEL ANGELEHNT)",
    action: "Flügel an den Rahmen anlegen & Griff senkrecht nach oben auf Kipp drehen",
    detail: "Fensterflügel wieder an den Rahmen anlehnen und den Griff senkrecht nach oben auf Kipp drehen. (Kann übersprungen werden).",
    icon: "📐",
    badge: "Kippstellung Griff",
  },
  tilted: {
    title: "5. MACHE JETZT AUF KIPP!",
    action: "Fensterflügel jetzt oben in Kippstellung kippen",
    detail: "Kippe den Flügel oben an. Alle Sensoren erfassen jetzt die stabile Kippstellung.",
    icon: "💨",
    badge: "Gekippt geöffnet",
  },
};

const SIMPLE_STEPS_INFO = {
  closed: {
    title: "1. FENSTER VOLLSTÄNDIG SCHLIESSEN",
    action: "Fensterflügel komplett anlegen und schließen",
    detail: "Bringe das Fenster in den geschlossenen Grundzustand.",
    icon: "🪟",
    badge: "Geschlossen",
  },
  open: {
    title: "2. FENSTER JETZT ÖFFNEN",
    action: "Fensterflügel jetzt öffnen",
    detail: "Öffne das Fenster. Der Kontakt muss offen melden.",
    icon: "🪟",
    badge: "Geöffnet",
  },
};

const CSS = `:host{display:block;font:inherit;color:var(--primary-text-color,#182b42)}
*{box-sizing:border-box}
p{font-size:13px;line-height:1.6;color:var(--secondary-text-color,#64758b);margin:0 0 12px}
h3{margin:0 0 12px;font-size:18px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.wide{grid-column:1/-1}
label{display:grid;gap:7px;font-size:12px;font-weight:600}
input,select,button{font:inherit;color:inherit}
input,select{min-height:42px;padding:10px;border:1px solid var(--divider-color,#dce3ec);border-radius:8px;background:var(--card-background-color,#fff);width:100%;min-width:0}
button{min-height:42px;padding:10px 14px;border:1px solid var(--divider-color,#dce3ec);border-radius:9px;background:var(--card-background-color,#fff);cursor:pointer}
.primary{background:var(--primary-color,#087e9b);color:var(--text-primary-color,#fff);border-color:transparent;font-weight:600}
button:disabled{opacity:.5;cursor:not-allowed}
input:focus-visible,select:focus-visible,button:focus-visible{outline:3px solid var(--primary-color,#087e9b);outline-offset:2px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.end{justify-content:flex-end}
.foot{margin-top:16px;padding-top:14px;border-top:1px solid var(--divider-color,#dce3ec);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.foot-group{display:flex;gap:8px;flex-wrap:wrap;align-items:center}

.btn-automatch{background:#f0fdf4;border:1px solid #86efac;color:#166534;font-weight:600;display:inline-flex;align-items:center;gap:6px;transition:background-color .15s}
.btn-automatch:hover{background:#dcfce7}

.step-card{margin:10px 0 14px;padding:14px;border:2px solid var(--primary-color,#087e9b);border-radius:12px;background:rgba(8,126,155,0.06)}
.step-card.verify-card{border-color:#10b981;background:rgba(16,185,129,0.06)}
.step-badge-row{display:flex;gap:8px;align-items:center;margin-bottom:6px}
.step-num-pill{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;padding:3px 8px;border-radius:9999px;background:var(--primary-color,#087e9b);color:#fff}
.step-num-pill.success{background:#10b981}
.step-phase-tag{font-size:11px;font-weight:600;color:var(--secondary-text-color,#64758b)}
.step-hero{display:flex;align-items:center;gap:12px}
.step-icon{font-size:26px;line-height:1}
.step-hero-text{flex:1;min-width:0}
.step-hero-title{font-size:14px;font-weight:800;letter-spacing:0.5px;color:var(--primary-color,#087e9b)}
.verify-card .step-hero-title{color:#059669}
.step-hero-action{font-size:15px;font-weight:700;color:var(--primary-text-color,#182b42);margin-top:2px}
.step-hero-detail{font-size:12px;line-height:1.4;color:var(--secondary-text-color,#64758b);margin-top:6px}

.preview{margin:12px 0;padding:12px 14px;border:1px solid var(--divider-color,#dce3ec);border-radius:12px;background:var(--primary-background-color,#f8fafc)}
.preview-header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid var(--divider-color,#dce3ec)}
.preview-state{display:flex;align-items:center;gap:8px}
.preview-state strong{font-size:15px;font-weight:700}
.preview-badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.pill-status{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 8px;border-radius:9999px}
.pill-stable{background:#dcfce7;color:#166534;border:1px solid #86efac}
.pill-settling{background:#fef3c7;color:#92400e;border:1px solid #fcd34d}
.pill-fault{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}
.pill-lock{background:#e0f2fe;color:#075985;border:1px solid #7dd3fc}

.signals-list{display:grid;gap:6px}
.signal-card{padding:8px 12px;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e2e8f0);border-radius:8px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;transition:border-color .2s,box-shadow .2s}
.signal-card.just-reacted{border-color:var(--primary-color,#087e9b);box-shadow:0 0 0 2px rgba(8,126,155,0.25)}
.signal-info{display:flex;flex-direction:column;gap:2px;min-width:0}
.signal-role-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.signal-role{display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--secondary-text-color,#64758b);background:var(--primary-background-color,#f1f5f9);padding:2px 6px;border-radius:4px}
.signal-name{font-size:13px;font-weight:600;color:var(--primary-text-color,#182b42);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.signal-entity-id{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:11px;color:var(--secondary-text-color,#64758b);word-break:break-all}
.signal-val-wrap{display:flex;flex-direction:column;align-items:flex-end;gap:4px}
.val-pill{display:inline-block;font-size:12px;font-weight:700;padding:3px 8px;border-radius:6px;text-align:center;min-width:55px}
.val-active{background:#fef3c7;color:#92400e;border:1px solid #fcd34d}
.val-calm{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.val-fault{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}
.badge-reacted{display:inline-block;font-size:10px;font-weight:700;color:#0284c7;background:#e0f2fe;padding:2px 6px;border-radius:4px;white-space:nowrap}

.fault,.error{color:var(--error-color,#bd3349)}
.error:empty{display:none}
.error{font-size:13px;line-height:1.6;white-space:pre-wrap;margin-top:12px}
.step{font-size:12px;color:var(--secondary-text-color,#64758b);margin-bottom:12px}
.check{display:flex;align-items:flex-start;gap:10px;font-weight:400;line-height:1.5}
.check input{width:18px;min-height:18px;flex-shrink:0}
small{font-size:11px;line-height:1.5;font-weight:400;color:var(--secondary-text-color,#64758b)}
details{margin-top:18px}
summary{cursor:pointer;font-size:13px;margin-bottom:12px;font-weight:600}
.learned{display:flex;gap:7px;flex-wrap:wrap;font-size:11px;margin:14px 0}
.learned span{padding:5px 8px;border:1px solid var(--divider-color,#dce3ec);border-radius:6px;background:var(--card-background-color,#fff)}
[hidden]{display:none!important}
@media(max-width:600px){.grid{grid-template-columns:1fr}.foot button{flex:1}.preview-header{flex-direction:column;align-items:flex-start}}`;

class WindowAssistant extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this.phase="sources";
    this.index=0;
    this.busy=false;
    this.polling=false;
    this.stopped=false;
    this._lastValues={};

    this.shadowRoot.addEventListener("click", event => {
      const action = event.target.closest("button")?.dataset.act;
      if (action) this.act(action);
    });

    this.shadowRoot.addEventListener("submit", event => {
      event.preventDefault();
      event.stopPropagation();
      if (this.phase === "sources") this.act("next");
    });

    this.shadowRoot.addEventListener("change", event => {
      if (event.target.name === "room_id") {
        const newRoomId = event.target.value;
        this.window.room_id = newRoomId;
        this._updateDropdowns(newRoomId);
      }
      if (event.target.name === "contact_entity_id") {
        const sensor = this.sensors[event.target.value];
        if (sensor) {
          for (const name of ["entry_delay","immediate","debounce_ms","flap_enabled","flap_window","flap_threshold"]) {
            const field = this.shadowRoot.querySelector(`[name="${name}"]`);
            if (field) {
              if (field.type === "checkbox") field.checked = !sensor[name];
              else field.value = sensor[name];
            }
          }
        }
      }
      if (event.target.name === "availability_entity_id") {
        const source = this.catalog.entities.find(e => e.entity_id === event.target.value);
        const field = this.shadowRoot.querySelector('[name="availability_states"]');
        if (field && !field.value && source?.attributes?.device_class === "connectivity") field.value = "on";
      }
    });
  }

  setup({hass, catalog, rooms, orderedRooms, sensors = {}, windows, initial, onSave, onCancel}) {
    this.hass = hass;
    this.catalog = catalog;
    this.sensors = sensors;
    this.rooms = rooms;
    this.orderedRooms = orderedRooms || Object.values(rooms);
    this.windows = windows;
    this.onSave = onSave;
    this.onCancel = onCancel;
    this.window = structuredClone(initial || {
      id: randomId(),
      name: "",
      room_id: "",
      contact_entity_id: null,
      handle_entity_ids: [],
      lock_entity_id: null,
      availability_entity_id: null,
      availability_states: [],
      allow_unknown_inputs: [],
      mappings: [],
      settle_seconds: 1,
      enabled: true,
      entry_delay: false,
      contact_open_states: ["on"],
      contact_closed_states: ["off"],
      immediate: false,
      debounce_ms: 0,
      flap_enabled: true,
      flap_window: 15,
      flap_threshold: 3
    });
    this.render();
  }

  disconnectedCallback() { this.stop(); }
  stop() { this.stopped = true; clearTimeout(this.timer); }

  isWindowRelevantEntity(e, isLock = false, isAvailability = false) {
    if (this.sensors[e.entity_id]) return true;
    const domain = e.entity_id.split(".")[0];
    if (isLock) {
      return domain === "lock" || /lock|schloss/i.test(e.entity_id) || /lock|schloss/i.test(e.name || "");
    }
    if (!["binary_sensor", "sensor"].includes(domain)) return false;
    const attrs = e.attributes || {};
    if (attrs.unit_of_measurement) return false;
    const badDc = ["energy","power","battery","temperature","humidity","illuminance","timestamp","monetary","frequency","pressure","voltage","current","duration","distance","speed","gas","water","pm25","aqi","carbon_dioxide","carbon_monoxide","signal_strength"];
    if (badDc.includes(attrs.device_class)) return false;

    if (!isAvailability) {
      if (["connectivity", "tamper", "vibration", "problem", "safety", "plug", "moisture", "smoke", "motion", "occupancy"].includes(attrs.device_class)) return false;
      const excludeNonContact = /(connectivity|verbindung|online|ping|ethernet|wifi|wlan|tamper|vibration|erschutterung|manipulation|mopp|wasserkasten|current|voltage|over_current|over_voltage|schlafstatus|fahrzeug|script|thermostat|rollladen)/i;
      if (excludeNonContact.test(e.entity_id) || excludeNonContact.test(e.name || "")) return false;
    }

    const badRegex = /(energy|power|verbrauch|leistung|batterie|battery|temperatur|feuchtigkeit|spannung|strom|zaehler|counter|differenz|ungetrackt|netz|update|signal|rssi|dbm|speed|download|upload|ping|co2|pm25|humidity)/i;
    if (badRegex.test(e.entity_id) || badRegex.test(e.name || "")) return false;

    if (domain === "binary_sensor") {
      const goodDc = isAvailability
        ? ["door","window","opening","garage_door","lock","safety","vibration","tamper","connectivity"]
        : ["door","window","opening","garage_door","lock"];
      if (goodDc.includes(attrs.device_class)) return true;
      const goodRegex = /(fenster|window|kontakt|contact|griff|handle|grip|frame|door|tur|schloss|lock|kipp|tilt)/i;
      return goodRegex.test(e.entity_id) || goodRegex.test(e.name || "");
    }
    const goodRegex = /(fenster|window|kontakt|contact|griff|handle|grip|frame|door|tur|schloss|lock|kipp|tilt)/i;
    return goodRegex.test(e.entity_id) || goodRegex.test(e.name || "");
  }

  sourceOptions(value, domains, blank = "Nicht vorhanden", isLock = false, selectedRoomId = null, isAvailability = false) {
    const roomId = selectedRoomId ?? this.window?.room_id ?? "";
    const claimed = new Set(Object.values(this.windows).filter(w => w.id !== this.window.id).flatMap(w => [w.contact_entity_id, ...w.handle_entity_ids].filter(Boolean)));
    const all = this.catalog.entities.filter(e =>
      domains.includes(e.entity_id.split(".")[0]) &&
      !claimed.has(e.entity_id) &&
      !e.entity_id.startsWith("sensor.iqalarm") &&
      !e.entity_id.startsWith("binary_sensor.iqalarm") &&
      this.isWindowRelevantEntity(e, isLock, isAvailability)
    );

    const roomSensors = [];
    const otherIQSensors = [];
    const haEntities = [];

    const roomObj = this.rooms[roomId] || Object.values(this.rooms).find(r => r.id === roomId);
    const roomName = roomObj?.name || "";

    const seen = new Set();
    for (const e of all) {
      seen.add(e.entity_id);
      const cfgSensor = this.sensors[e.entity_id];
      const displayName = cfgSensor?.name || e.name || e.entity_id;
      const item = {entity_id: e.entity_id, name: displayName};
      if (cfgSensor) {
        if (roomId && cfgSensor.room_id === roomId) {
          roomSensors.push(item);
        } else {
          otherIQSensors.push(item);
        }
      } else {
        haEntities.push(item);
      }
    }

    if (value && !seen.has(value)) {
      const existing = this.catalog.entities.find(e => e.entity_id === value);
      const name = this.sensors[value]?.name || existing?.name || value;
      roomSensors.unshift({entity_id: value, name});
    }

    const sortFn = (a, b) => a.name.localeCompare(b.name, "de");
    roomSensors.sort(sortFn);
    otherIQSensors.sort(sortFn);
    haEntities.sort(sortFn);

    const makeOption = item => `<option value="${esc(item.entity_id)}"${item.entity_id === value ? " selected" : ""}>${esc(item.name)} · ${esc(item.entity_id)}</option>`;

    let html = `<option value="">${esc(blank)}</option>`;
    if (roomSensors.length) {
      html += `<optgroup label="Sensoren in diesem Raum (${esc(roomName)})">${roomSensors.map(makeOption).join("")}</optgroup>`;
    }
    if (otherIQSensors.length) {
      html += `<optgroup label="Weitere IQAlarm-Sensoren">${otherIQSensors.map(makeOption).join("")}</optgroup>`;
    }
    if (haEntities.length) {
      html += `<optgroup label="Weitere passende Home-Assistant-Geräte">${haEntities.map(makeOption).join("")}</optgroup>`;
    }
    return html;
  }

  _updateDropdowns(roomId) {
    const update = (name, domains, isLock, isAvailability = false) => {
      const sel = this.shadowRoot.querySelector(`select[name="${name}"]`);
      if (!sel) return;
      const curVal = sel.value;
      sel.innerHTML = this.sourceOptions(curVal, domains, "Nicht vorhanden", isLock, roomId, isAvailability);
      if (curVal) sel.value = curVal;
    };
    update("contact_entity_id", ["binary_sensor", "sensor"], false, false);
    update("lock_entity_id", ["lock"], true, false);
    update("handle_1", ["binary_sensor", "sensor"], false, false);
    update("handle_2", ["binary_sensor", "sensor"], false, false);
    update("availability_entity_id", ["lock", "binary_sensor", "sensor"], false, true);
  }

  autoMatchRoomSensors() {
    const form = this.shadowRoot.getElementById("sources");
    if (!form) return;
    const roomId = form.room_id.value;
    if (!roomId) {
      this.error("Bitte wähle zuerst einen Raum aus.");
      return;
    }
    const roomSensors = Object.values(this.sensors).filter(s => s.room_id === roomId);
    if (!roomSensors.length) {
      this.error("In diesem Raum sind noch keine IQAlarm-Sensoren hinterlegt.");
      return;
    }

    // Prioritize physical window contacts (name/id with 'kontakt' or 'contact')
    const contact = roomSensors.find(s => /kontakt|contact/i.test(s.entity_id) || /kontakt|contact/i.test(s.name || ""))
      || roomSensors.find(s => {
        const ent = this.catalog.entities.find(e => e.entity_id === s.entity_id);
        const dc = ent?.attributes?.device_class;
        return ["window", "opening"].includes(dc) && !/griff|handle/i.test(s.entity_id) && !/griff|handle/i.test(s.name || "");
      })
      || roomSensors.find(s => {
        const ent = this.catalog.entities.find(e => e.entity_id === s.entity_id);
        return ["window", "door", "opening"].includes(ent?.attributes?.device_class);
      });

    const isContactRight = contact && (/rechts/i.test(contact.name) || /rechts/i.test(contact.entity_id));
    const isContactLeft = contact && (/links/i.test(contact.name) || /links/i.test(contact.entity_id));

    // Match handles (exclude chosen contact, prefer side match)
    const handles = roomSensors.filter(s => {
      if (contact && s.entity_id === contact.entity_id) return false;
      if (s.entity_id.startsWith("lock.")) return false;
      return /griff|handle|kipp|tilt|tur|door|aktor/i.test(s.entity_id) || /griff|handle|kipp|tilt|tur|door|aktor/i.test(s.name || "");
    });

    if (isContactRight) {
      handles.sort((a, b) => (/rechts/i.test(b.name || b.entity_id) ? 1 : 0) - (/rechts/i.test(a.name || a.entity_id) ? 1 : 0));
    } else if (isContactLeft) {
      handles.sort((a, b) => (/links/i.test(b.name || b.entity_id) ? 1 : 0) - (/links/i.test(a.name || a.entity_id) ? 1 : 0));
    }

    // Sort handles: prefer kipp for handle 1 and offen for handle 2
    handles.sort((a, b) => {
      const aKipp = /kipp|tilt/i.test(a.entity_id || a.name) ? 1 : 0;
      const bKipp = /kipp|tilt/i.test(b.entity_id || b.name) ? 1 : 0;
      return bKipp - aKipp;
    });

    if (contact) {
      const field = form.querySelector('[name="contact_entity_id"]');
      if (field) field.value = contact.entity_id;
    }
    if (handles[0]) {
      const field = form.querySelector('[name="handle_1"]');
      if (field) field.value = handles[0].entity_id;
    }
    if (handles[1]) {
      const field = form.querySelector('[name="handle_2"]');
      if (field) field.value = handles[1].entity_id;
    }

    const nameField = form.querySelector('[name="name"]');
    if (nameField && !nameField.value.trim()) {
      const roomName = (this.rooms[roomId] || Object.values(this.rooms).find(r => r.id === roomId))?.name || "Fenster";
      if (isContactRight) {
        nameField.value = `Fenster ${roomName} Rechts`;
      } else if (isContactLeft) {
        nameField.value = `Fenster ${roomName} Links`;
      } else {
        nameField.value = `Fenster ${roomName}`;
      }
    }

    this.error("");
    this._updateDropdowns(roomId);
  }

  field(name, label, value, domains, isLock = false, isAvailability = false) {
    return `<label>${label}<select name="${name}" aria-label="${label}">${this.sourceOptions(value, domains, "Nicht vorhanden", isLock, null, isAvailability)}</select></label>`;
  }

  render() {
    if (!this.window) return;
    const w = this.window;
    let body;
    if (this.phase === "sources") {
      const roomsList = this.orderedRooms || Object.values(this.rooms);
      body = `
        <p>Ein Fenster, ein Gesamtstatus. Wähle Sensoren aus dem Raum oder lass passende Kontakte und Griffe mit einem Klick zuordnen.</p>
        <div class="row" style="margin-bottom:12px;">
          <button type="button" class="btn-automatch" data-act="auto-match">⚡ Sensoren aus Raum automatisch zuordnen</button>
        </div>
        <form id="sources">
          <div class="grid">
            <label>Fenstername
              <input name="name" aria-label="Fenstername" required maxlength="100" value="${esc(w.name)}" placeholder="z. B. Wohnzimmer rechts">
            </label>
            <label>Raum
              <select name="room_id" aria-label="Raum" required>
                <option value="">Raum auswählen</option>
                ${roomsList.map(r => `<option value="${esc(r.id)}"${r.id === w.room_id ? " selected" : ""}>${esc(r.name)}</option>`).join("")}
              </select>
            </label>
            ${this.field("contact_entity_id", "Fensterkontakt", w.contact_entity_id, ["binary_sensor", "sensor"], false)}
            ${this.field("lock_entity_id", "Fenstergriff – Schloss", w.lock_entity_id, ["lock"], true)}
            ${this.field("handle_1", "Griffsignal 1", w.handle_entity_ids[0], ["binary_sensor", "sensor"], false)}
            ${this.field("handle_2", "Griffsignal 2", w.handle_entity_ids[1], ["binary_sensor", "sensor"], false)}
            ${this.field("availability_entity_id", "Verbindungsüberwachung", w.availability_entity_id, ["lock", "binary_sensor", "sensor"], false)}
          </div>
          <details>
            <summary>Weitere Einstellungen</summary>
            <div class="grid">
              <label>Stabilisierungszeit (Sekunden)
                <input name="settle_seconds" aria-label="Stabilisierungszeit (Sekunden)" type="number" min="0.2" max="10" step="0.1" value="${w.settle_seconds}" required>
              </label>
              <label>Verbindung bei diesen Werten
                <input name="availability_states" aria-label="Verbindung bei diesen Werten" value="${esc(w.availability_states.join(", "))}" placeholder="Leer: jeder gültige Zustand">
                <small>Bei einem Online-Binary-Sensor beispielsweise on.</small>
              </label>
              <label>Kontakt geöffnet bei
                <input name="contact_open_states" aria-label="Kontakt geöffnet bei" value="${esc((w.contact_open_states || ["on"]).join(", "))}" required>
                <small>Binär: on. Textsensor z. B. open, tilted.</small>
              </label>
              <label>Kontakt geschlossen bei
                <input name="contact_closed_states" aria-label="Kontakt geschlossen bei" value="${esc((w.contact_closed_states || ["off"]).join(", "))}" required>
                <small>Binär: off. Textsensor z. B. closed.</small>
              </label>
              <label class="check">
                <input type="checkbox" name="invert"${w.contact_open_states.includes("off") ? " checked" : ""}>
                Fensterkontakt invertieren (off bedeutet geöffnet)
              </label>
              <label class="check">
                <input type="checkbox" name="entry_delay"${w.entry_delay ? " checked" : ""}>
                Eingangsverzögerung erlauben
              </label>
              ${[0, 1].map(index => `
                <label class="check wide">
                  <input type="checkbox" name="allow_unknown_${index}" checked>
                  Griffsignal ${index + 1}: unknown als regulären Zustand zulassen
                  <small>Smart-Home-Fenstergriffe senden in Kippstellung häufig den Code unknown. Ist automatisch als gültiges Signal aktiv.</small>
                </label>
              `).join("")}
              <label>Entprellzeit (Millisekunden)
                <input type="number" name="debounce_ms" min="0" max="60000" value="${w.debounce_ms || 0}" required>
              </label>
              <label>Prell-Zeitfenster (Sekunden)
                <input type="number" name="flap_window" min="1" max="300" value="${w.flap_window ?? 15}" required>
              </label>
              <label>Prell-Schwelle (Wechsel)
                <input type="number" name="flap_threshold" min="3" max="100" value="${w.flap_threshold ?? 3}" required>
              </label>
              <label class="check">
                <input type="checkbox" name="flap_enabled"${w.flap_enabled !== false ? " checked" : ""}>
                Prellschutz für die Fensteröffnung
              </label>
              <label class="check">
                <input type="checkbox" name="immediate"${w.immediate ? " checked" : ""}>
                Ausdrücklicher Override: Fenster darf alleine bestätigen
              </label>
              <p class="wide">Beim Auswählen eines bereits zugeordneten Kontakts werden dessen Schutzparameter übernommen. Sie gelten hier für das gesamte Fenster; Griff-Entriegelung bleibt Information.</p>
              <label class="check">
                <input type="checkbox" name="enabled"${w.enabled ? " checked" : ""}>
                Fenster überwachen
              </label>
            </div>
          </details>
        </form>
        <div class="row end foot">
          <button type="button" data-act="cancel">Abbrechen</button>
          <button type="button" class="primary" data-act="next">Weiter: Fensterstellungen</button>
        </div>
      `;
    } else {
      const verify = this.phase === "verify";
      const state = this.steps[this.index];
      const stepInfo = this.steps.length === 2 ? SIMPLE_STEPS_INFO[state] : STEPS_INFO[state];

      body = `
        <div class="step">${verify ? "Abschluss · Live-Test" : `Stellung ${this.index + 1} von ${this.steps.length}`}</div>
        <h3>${verify ? "Erkennung prüfen" : esc(instructions[state])}</h3>
        <div class="step-card${verify ? " verify-card" : ""}">
          <div class="step-badge-row">
            <span class="step-num-pill${verify ? " success" : ""}">${verify ? "Live-Test" : `Schritt ${this.index + 1} von ${this.steps.length}`}</span>
            <span class="step-phase-tag">${verify ? "Funktionstest" : esc(stepInfo?.badge || "")}</span>
          </div>
          <div class="step-hero">
            <span class="step-icon">${verify ? "🎯" : (stepInfo?.icon || "🪟")}</span>
            <div class="step-hero-text">
              <div class="step-hero-title">${verify ? "ERKENNUNG PRÜFEN" : esc(stepInfo?.title || "")}</div>
              <div class="step-hero-action">${verify ? "Bewege das Fenster in beliebige Stellungen" : esc(stepInfo?.action || instructions[state])}</div>
            </div>
          </div>
          <div class="step-hero-detail">${verify ? "Teste Schließen, Entriegeln, Öffnen und Kippen. Die Signale unten zeigen dir live den Zustand jedes Sensors und die erkannte Gesamtstellung." : esc(stepInfo?.detail || "")}</div>
        </div>
        <div class="learned">
          ${w.mappings.map(rule => `<span>${esc(labels[rule.state])} ✓</span>`).join("")}
        </div>
        <div id="preview" class="preview" aria-live="polite">Signale werden gelesen …</div>
        <div class="row foot">
          <div class="foot-group">
            <button type="button" data-act="sources">Sensorzuordnung</button>
            ${verify ? '<button type="button" data-act="relearn">Neu einlernen</button>' : `
              <button type="button" data-act="prev"${this.index === 0 ? " disabled" : ""}>Zurück</button>
              <button type="button" data-act="skip">Schritt überspringen</button>
            `}
          </div>
          <div class="foot-group">
            <button type="button" data-act="cancel">Abbrechen</button>
            <button type="button" class="primary" data-act="${verify ? "save" : "capture"}"${!verify ? " disabled" : ""}>
              ${verify ? "Fenster speichern" : "Zustand übernehmen"}
            </button>
          </div>
        </div>
      `;
    }
    this.shadowRoot.innerHTML = `<style>${CSS}</style>${body}<div id="error" class="error" role="alert"></div>`;
    if (this.phase !== "sources") this.poll();
  }

  error(message) {
    const el = this.shadowRoot.getElementById("error");
    if (el) el.textContent = message || "";
  }

  readSources() {
    const form = this.shadowRoot.getElementById("sources");
    if (!form.reportValidity()) return false;
    const data = new FormData(form), get = key => String(data.get(key) || "");
    const handles = [get("handle_1"), get("handle_2")].filter(Boolean);
    const contact = get("contact_entity_id") || null;
    const lock = get("lock_entity_id") || null;
    const guard = get("availability_entity_id") || null;
    if (!contact && !handles.length) throw new Error("Bitte mindestens einen Fensterkontakt oder ein Griffsignal auswählen.");
    if (new Set([contact, ...handles].filter(Boolean)).size !== [contact, ...handles].filter(Boolean).length) {
      throw new Error("Jedes Stellungssignal darf nur einmal zugeordnet werden.");
    }
    const allowed = handles;
    const before = JSON.stringify([this.window.contact_entity_id, this.window.handle_entity_ids, this.window.allow_unknown_inputs, this.window.contact_open_states, this.window.contact_closed_states]);
    Object.assign(this.window, {
      name: get("name").trim(),
      room_id: get("room_id"),
      contact_entity_id: contact,
      handle_entity_ids: handles,
      lock_entity_id: lock,
      availability_entity_id: guard,
      availability_states: get("availability_states").split(",").map(x => x.trim()).filter(Boolean),
      allow_unknown_inputs: allowed,
      settle_seconds: Number(get("settle_seconds")),
      enabled: data.has("enabled"),
      entry_delay: data.has("entry_delay"),
      contact_open_states: data.has("invert") ? ["off"] : get("contact_open_states").split(",").map(x => x.trim()).filter(Boolean),
      contact_closed_states: data.has("invert") ? ["on"] : get("contact_closed_states").split(",").map(x => x.trim()).filter(Boolean),
      immediate: data.has("immediate"),
      debounce_ms: Number(get("debounce_ms")),
      flap_enabled: data.has("flap_enabled"),
      flap_window: Number(get("flap_window")),
      flap_threshold: Number(get("flap_threshold"))
    });
    const after = JSON.stringify([contact, handles, this.window.allow_unknown_inputs, this.window.contact_open_states, this.window.contact_closed_states]);
    if (before !== after) this.window.mappings = [];
    this.steps = handles.length ? Object.keys(labels) : ["closed", "open"];
    return true;
  }

  async call(type, args = {}) {
    return this.hass.callWS({type: `iqalarm/window/${type}`, window: this.window, ...args});
  }

  async poll() {
    clearTimeout(this.timer);
    if (this.stopped || this.phase === "sources" || this.polling) return;
    this.polling = true;
    try {
      const preview = await this.call("preview");
      if (this.stopped || this.phase === "sources") return;
      this.preview = preview;
      const target = this.shadowRoot.getElementById("preview");
      if (target) {
        const lastValues = this._lastValues || {};
        const newLastValues = {};
        const reacted = new Set();
        for (const [id, value] of Object.entries(preview.inputs)) {
          newLastValues[id] = value;
          if (lastValues[id] !== undefined && lastValues[id] !== value) {
            reacted.add(id);
          }
        }
        this._lastValues = newLastValues;

        const stateClass = preview.available ? "" : "fault";
        const stabilityBadge = !preview.stable
          ? `<span class="pill-status pill-settling">⏳ Signale ändern sich …</span>`
          : preview.available
          ? `<span class="pill-status pill-stable">✅ Signale stabil</span>`
          : `<span class="pill-status pill-fault">⚠️ Signal fehlt</span>`;

        const lockBadge = this.window.lock_entity_id
          ? `<span class="pill-status pill-lock">🔒 Schloss: ${esc(preview.lock_label || "Keine Verbindung")}</span>`
          : "";

        const getRole = id => {
          if (id === this.window.contact_entity_id) return "Fensterkontakt";
          if (id === this.window.lock_entity_id) return "Schloss / Riegel (Optional)";
          if (id === this.window.handle_entity_ids[0]) return "Griffsignal 1";
          if (id === this.window.handle_entity_ids[1]) return "Griffsignal 2";
          if (id === this.window.availability_entity_id) return "Verbindung (Optional)";
          return "Sensor";
        };

        const signalCards = Object.entries(preview.inputs).map(([id, value]) => {
          const cfgSensor = this.sensors[id];
          const catEntity = this.catalog.entities.find(e => e.entity_id === id);
          const name = cfgSensor?.name || catEntity?.name || id;
          const isFault = preview.faults.includes(id);
          const isReacted = reacted.has(id);
          const isCalm = ["off", "closed", "locked"].includes(String(value).toLowerCase());
          const valClass = isFault ? "val-fault" : isCalm ? "val-calm" : "val-active";

          return `
            <div class="signal signal-card${isReacted ? " just-reacted" : ""}">
              <div class="signal-info">
                <div class="signal-role-row">
                  <div class="signal-role">${esc(getRole(id))}</div>
                  ${isReacted ? '<div class="badge-reacted">⚡ Gerade gemeldet!</div>' : ""}
                </div>
                <div class="signal-name" title="${esc(name)}">${esc(name)}</div>
                <code class="signal-entity-id">${esc(id)}</code>
              </div>
              <div class="signal-val-wrap">
                <span class="val-pill ${valClass}">${esc(value)}</span>
              </div>
            </div>
          `;
        }).join("");

        const statusText = !preview.stable
          ? "Meldungen ändern sich noch …"
          : preview.available
          ? "Signale stabil"
          : "Benötigtes Signal fehlt";
        const lockText = this.window.lock_entity_id ? ` · Schloss: ${esc(preview.lock_label || "Keine Verbindung")}` : "";

        target.innerHTML = `
          <div class="preview-header">
            <div class="preview-state">
              <strong class="${stateClass}">${esc(preview.label)}</strong>
            </div>
            <div class="preview-badges">
              ${stabilityBadge}
              ${lockBadge}
            </div>
          </div>
          <p>${statusText}${lockText}</p>
          <div class="signals-list">
            ${signalCards}
          </div>
        `;
      }
      const capture = this.shadowRoot.querySelector('[data-act="capture"]');
      if (capture) capture.disabled = this.busy || !preview.can_capture;
    } catch (err) {
      this.error(`Signale konnten nicht gelesen werden: ${err.message || err}`);
      const button = this.shadowRoot.querySelector('[data-act="capture"]');
      if (button) button.disabled = true;
    } finally {
      this.polling = false;
      if (!this.stopped && this.phase !== "sources") this.timer = setTimeout(() => this.poll(), 750);
    }
  }

  async act(action) {
    if (this.busy) return;
    this.error("");
    try {
      if (action === "cancel") {
        this.stop();
        this.onCancel();
        return;
      }
      if (action === "auto-match") {
        this.autoMatchRoomSensors();
        return;
      }
      if (action === "next") {
        if (!this.readSources()) return;
        await this.call("preview");
        this.phase = this.window.mappings.length ? "verify" : "learn";
        this.index = 0;
        this.render();
        return;
      }
      if (action === "sources") {
        clearTimeout(this.timer);
        this.phase = "sources";
        this.render();
        return;
      }
      if (action === "relearn") {
        this.window.mappings = [];
        this.index = 0;
        this.phase = "learn";
        this.render();
        return;
      }
      if (action === "prev") {
        this.index = Math.max(0, this.index - 1);
        this.render();
        return;
      }
      if (action === "capture") {
        this.busy = true;
        const button = this.shadowRoot.querySelector('[data-act="capture"]');
        if (button) button.disabled = true;
        const result = await this.call("capture", {state: this.steps[this.index]});
        this.window.mappings = this.window.mappings.filter(rule => rule.state !== result.mapping.state).concat(result.mapping);
      }
      if (action === "capture" || action === "skip") {
        if (action === "skip") this.window.mappings = this.window.mappings.filter(rule => rule.state !== this.steps[this.index]);
        this.index++;
        if (this.index >= this.steps.length) this.phase = "verify";
        this.render();
        return;
      }
      if (action === "save") {
        if (!["closed", "open"].every(state => this.window.mappings.some(rule => rule.state === state))) {
          throw new Error("Bitte mindestens Geschlossen und Offen einlernen. Über „Neu einlernen“ kannst du die Schritte wiederholen.");
        }
        this.busy = true;
        const button = this.shadowRoot.querySelector('[data-act="save"]');
        if (button) button.disabled = true;
        await this.onSave(structuredClone(this.window));
        this.stop();
      }
    } catch (err) {
      this.error(err.message || String(err));
    } finally {
      this.busy = false;
      const save = this.shadowRoot.querySelector('[data-act="save"]');
      if (save) save.disabled = false;
      const capture = this.shadowRoot.querySelector('[data-act="capture"]');
      if (capture) capture.disabled = !this.preview?.can_capture;
    }
  }
}

if (!customElements.get("iqalarm-window-assistant")) customElements.define("iqalarm-window-assistant", WindowAssistant);
