/* IQAlarm 2.0.0 · native ES module · no CDN, framework or build required. */
const RULES = {perimeter: "Vorfeld-Erkennung", single: "Unbestätigter Einzelsensor", flapping: "Sensor-Prellen", perimeter_contact: "Vorfeld + Öffnung", contact_motion: "Öffnung + Bewegung", multi_contact: "Zwei Öffnungssensoren", multi_motion: "Zwei Bewegungsmelder", immediate: "Freigegebene Einzelauslösung / Gefahr"};
const ROLES = {perimeter_camera: "Außenkamera / Person", perimeter_sensor: "Vorfeld-Sensor", entry_contact: "Tür / Fenster", lock_contact: "Schloss / Riegel", vibration_glass: "Glas / Vibration", interior_motion: "Bewegung innen", interior_mmwave: "Präsenz / mmWave", panic: "Panik", smoke: "Rauch / Gefahr"};
const KINDS = {notify: "Push-Benachrichtigung", siren: "Sirene", switch: "Schalter", script: "Skript", light: "Licht", cover: "Rollos öffnen", snapshot: "Kamera-Snapshot", record: "Kamera-Aufzeichnung", tts: "Sprachausgabe"};
const TABS = [["view-dashboard-outline", "Live-Cockpit"], ["floor-plan", "Räume & Topologie"], ["access-point", "Sensoren & Prell-Schutz"], ["tune-variant", "Alarmstufen & Regeln"], ["bell-outline", "Aktionen & Push"]];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const icon = (name) => `<ha-icon icon="mdi:${esc(name)}" aria-hidden="true"></ha-icon>`;
const checked = (value) => value ? " checked" : "";
const selected = (a, b) => a === b ? " selected" : "";
const options = (items, value = "", blank = "") => `${blank ? `<option value="">${esc(blank)}</option>` : ""}${Object.entries(items).map(([id, label]) => `<option value="${esc(id)}"${selected(id, value)}>${esc(label)}</option>`).join("")}`;
const date = (epoch) => new Date(epoch * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"});

const CSS = `
:host{display:block;height:100%;color:var(--primary-text-color,#182b42);background:var(--primary-background-color,#f3f6fa);font-family:var(--paper-font-body1_-_font-family,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif);--iq-accent:var(--primary-color,#087e9b);--iq-muted:var(--secondary-text-color,#64758b);--iq-border:var(--divider-color,#dce3ec);--iq-surface:var(--card-background-color,#fff);--iq-green:#16816a;--iq-amber:#b87808;--iq-red:#d34454;--iq-blue:#2986bb}
*{box-sizing:border-box}button,input,select,textarea{font:inherit}button{cursor:pointer;overflow-wrap:anywhere;max-width:100%}button:disabled{cursor:not-allowed;opacity:.5}ha-icon{--mdc-icon-size:21px;vertical-align:middle}button ha-icon{pointer-events:none}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid var(--iq-accent);outline-offset:3px}button{border:1px solid var(--iq-border);background:var(--iq-surface);color:inherit;border-radius:10px;padding:10px 15px;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;transition:background .15s}button:hover{background:color-mix(in srgb,var(--iq-accent) 8%,var(--iq-surface))}button.primary{background:var(--iq-accent);color:var(--text-primary-color,#fff);border-color:var(--iq-accent)}button.danger{color:var(--iq-red)}button.small{padding:6px 10px;min-height:36px;font-size:13px}.icon-button{padding:8px;border:0;background:transparent;min-width:40px}.shell{height:100%;overflow:auto}.top{position:sticky;top:0;z-index:3;background:var(--iq-surface);border-bottom:1px solid var(--iq-border)}.brand-row{max-width:1440px;margin:auto;padding:18px 30px 14px;display:flex;align-items:center;gap:13px}.brandmark{width:43px;height:47px;background:linear-gradient(145deg,#13b8b0,#076c93);clip-path:polygon(50% 0,93% 16%,88% 64%,74% 84%,50% 100%,26% 84%,12% 64%,7% 16%);display:grid;place-items:center;color:white;font-size:18px;font-weight:800;letter-spacing:-1px}.brand-title{font-size:23px;font-weight:760;letter-spacing:-.7px}.eyebrow{color:var(--iq-muted);font-size:11px;font-weight:650;letter-spacing:1.4px;text-transform:uppercase}.brand-copy{display:grid;gap:2px}.connection{margin-left:auto;display:flex;align-items:center;gap:8px;color:var(--iq-muted);font-size:12px}.dot{width:8px;height:8px;background:var(--iq-green);border-radius:50%;display:inline-block}.dot.off{background:var(--iq-red)}nav{display:flex;gap:8px;max-width:1440px;margin:auto;padding:0 30px;overflow:auto}nav button{border:none;border-bottom:3px solid transparent;border-radius:0;padding:15px 13px;background:transparent;white-space:nowrap;color:var(--iq-muted);font-weight:600;font-size:13px}nav button.active{color:var(--iq-accent);border-bottom-color:var(--iq-accent)}main{max-width:1440px;padding:30px;margin:auto}.page-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px;flex-wrap:wrap}h1{font-size:25px;font-weight:720;letter-spacing:-.7px;margin:0 0 5px}h2{font-size:17px;margin:0 0 10px;letter-spacing:-.2px}h3{font-size:15px;margin:0}p{margin:6px 0 0;line-height:1.6;color:var(--iq-muted);font-size:13px}.muted{color:var(--iq-muted)}.card{background:var(--iq-surface);border:1px solid var(--iq-border);border-radius:16px;padding:23px;min-width:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}.grid.two{grid-template-columns:1.2fr 1fr}.hero{display:flex;align-items:center;gap:28px;background:linear-gradient(120deg,color-mix(in srgb,var(--iq-accent) 7%,var(--iq-surface)),var(--iq-surface));padding:29px;margin-bottom:18px}.level-ring{width:110px;height:110px;flex-shrink:0;border:7px solid color-mix(in srgb,var(--level-color) 20%,transparent);border-top-color:var(--level-color);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;color:var(--level-color)}.level-ring strong{font-size:36px;line-height:1.1}.level-ring span{font-size:10px;font-weight:700;letter-spacing:1px}.hero-copy{min-width:0;overflow-wrap:anywhere}.hero h2{font-size:29px;margin:7px 0 4px}.hero .pill{margin-left:auto;align-self:flex-start}.pill{display:inline-flex;align-items:center;gap:6px;border-radius:7px;padding:5px 8px;font-size:11px;font-weight:650;background:color-mix(in srgb,var(--level-color,var(--iq-accent)) 10%,var(--iq-surface));color:var(--level-color,var(--iq-accent));white-space:nowrap}.mode-buttons{display:flex;flex-wrap:wrap;gap:9px;margin-top:20px}.mode-buttons button.active{background:color-mix(in srgb,var(--iq-accent) 12%,var(--iq-surface));border-color:var(--iq-accent);color:var(--iq-accent)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:18px 0 28px}.metric{display:flex;align-items:center;gap:13px;padding:19px}.metric>ha-icon{--mdc-icon-size:25px;color:var(--iq-accent);padding:12px;width:49px;height:49px;background:color-mix(in srgb,var(--iq-accent) 8%,var(--iq-surface));border-radius:12px}.metric strong{display:block;font-size:23px;line-height:1.1}.metric span{font-size:11px;color:var(--iq-muted)}.section-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:26px 0 14px}.room-head{display:flex;align-items:center;gap:10px;margin-bottom:16px}.room-head h3{min-width:0;flex:1;overflow-wrap:anywhere}.room-head .pill{margin-left:auto}.sensor-line{display:flex;align-items:center;gap:9px;padding:9px 0;border-top:1px solid var(--iq-border);font-size:12px}.sensor-line .sensor-name{flex:1;overflow-wrap:anywhere}.sensor-line ha-icon{color:var(--iq-muted);--mdc-icon-size:18px}.sensor-state{font-size:11px;color:var(--iq-muted)}.sensor-state.on{color:var(--iq-amber)}.banner{border:1px solid color-mix(in srgb,var(--iq-amber) 40%,var(--iq-border));background:color-mix(in srgb,var(--iq-amber) 7%,var(--iq-surface));padding:18px;border-radius:13px;margin:15px 0;display:flex;gap:13px;align-items:center}.banner ha-icon{color:var(--iq-amber)}.banner>div{flex:1;min-width:0}.banner strong{font-size:13px}.banner p{font-size:12px}.event{display:grid;grid-template-columns:110px 30px minmax(0,1fr);gap:12px;border-top:1px solid var(--iq-border);padding:14px 0;font-size:12px;align-items:start}.event>div{min-width:0;overflow-wrap:anywhere}.event time{color:var(--iq-muted);font-variant-numeric:tabular-nums}.event p{font-size:11px;word-break:break-word}.event-level{display:grid;place-items:center;border-radius:6px;width:25px;height:25px;background:color-mix(in srgb,var(--level-color) 12%,var(--iq-surface));color:var(--level-color);font-weight:700}.empty{padding:34px 20px;text-align:center;border:1px dashed var(--iq-border);border-radius:13px;color:var(--iq-muted)}.empty ha-icon{--mdc-icon-size:30px;margin-bottom:12px}.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.row.between{justify-content:space-between}.row.end{justify-content:flex-end}.spacer{flex:1}.topology{display:flex;align-items:center;justify-content:center;gap:6px;margin:17px 0;font-size:11px;color:var(--iq-muted);background:var(--primary-background-color,#f3f6fa);padding:14px 4px;border-radius:10px}.topology span{text-align:center}.topology strong{display:block;color:var(--primary-text-color);font-size:18px;margin-bottom:4px}.chips{display:flex;gap:8px;flex-wrap:wrap}.chips button.active{background:var(--iq-accent);color:var(--text-primary-color,#fff);border-color:var(--iq-accent)}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:var(--iq-muted);font-size:10px;text-transform:uppercase;letter-spacing:.7px;white-space:nowrap}td,th{padding:13px 9px;border-bottom:1px solid var(--iq-border)}td code{font-size:10px;color:var(--iq-muted);display:block;margin-top:4px}.search{min-width:220px;width:min(100%,390px)}.catalog{max-height:380px;overflow:auto}.catalog-row{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--iq-border);font-size:12px}.catalog-row code{font-size:10px;display:block;margin-top:4px;color:var(--iq-muted);overflow-wrap:anywhere}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.form-grid .wide{grid-column:1/-1}label.field{display:flex;flex-direction:column;gap:7px;font-size:12px;font-weight:600;min-width:0}label small{color:var(--iq-muted);font-size:11px;font-weight:400;line-height:1.5}input:not([type=checkbox]),select,textarea{border:1px solid var(--iq-border);border-radius:8px;background:var(--iq-surface);color:inherit;padding:11px 12px;min-width:0;width:100%;min-height:41px}select[multiple]{height:115px}textarea{min-height:80px;resize:vertical}input[type=checkbox]{accent-color:var(--iq-accent);width:17px;height:17px;flex-shrink:0}.check{display:flex;align-items:flex-start;gap:9px;font-size:12px;line-height:1.6;cursor:pointer}.checks{display:grid;gap:13px}.help{border-left:3px solid var(--iq-accent);padding:10px 14px;background:color-mix(in srgb,var(--iq-accent) 5%,var(--iq-surface));font-size:12px;line-height:1.6;margin:16px 0;color:var(--iq-muted)}fieldset{border:0;padding:0;margin:0;min-width:0}fieldset:disabled{opacity:.6}.save-row{display:flex;gap:12px;align-items:center;margin-top:23px}.action-card{display:flex;align-items:center;gap:14px;margin:12px 0;padding:18px;border:1px solid var(--iq-border);border-radius:12px}.action-card>ha-icon{color:var(--iq-accent)}.action-card .description{flex:1;min-width:0;overflow-wrap:anywhere}.action-card p{font-size:11px}dialog{background:var(--iq-surface);color:inherit;border:1px solid var(--iq-border);border-radius:17px;padding:0;max-width:min(740px,calc(100vw - 28px));width:740px;max-height:90vh;box-shadow:0 20px 80px #0005}dialog::backdrop{background:#101c3080;backdrop-filter:blur(3px)}.dialog-head{padding:22px 25px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--iq-border);position:sticky;top:0;background:var(--iq-surface);z-index:2}.dialog-body{padding:23px 25px}.dialog-foot{padding:17px 25px;border-top:1px solid var(--iq-border);display:flex;justify-content:flex-end;gap:10px;position:sticky;bottom:0;background:var(--iq-surface)}dialog[open]{display:flex;flex-direction:column}dialog form{overflow:auto}#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:14px 22px;background:var(--primary-text-color,#182b42);color:var(--iq-surface);border-radius:10px;box-shadow:0 4px 24px #0003;z-index:20;max-width:90vw;font-size:13px}#toast.error{background:var(--iq-red);color:white}#toast:empty{display:none}.loading{padding:70px;text-align:center;color:var(--iq-muted)}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;padding:16px;background:var(--primary-background-color);border-radius:10px}.armed-note{margin-bottom:18px}.footer-note{margin-top:30px;color:var(--iq-muted);font-size:11px;text-align:center}[hidden]{display:none!important}.countdown{font-size:13px;font-weight:650;color:var(--iq-amber);margin-top:10px}
@media(max-width:1000px){.grid.two{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}nav{gap:0;padding:0 12px}nav button{padding:14px 11px}nav button ha-icon{display:none}}
@media(max-width:600px){main{padding:18px 14px}.brand-row{padding:12px 14px;gap:9px}.brand-title{font-size:21px}.connection span:not(.dot){display:none}.eyebrow{font-size:9px;letter-spacing:1px}.hero{padding:22px 18px;gap:17px;flex-wrap:wrap}.hero-copy{min-width:0;overflow-wrap:anywhere}.hero h2{font-size:23px}.level-ring{width:80px;height:80px;border-width:5px}.level-ring strong{font-size:28px}.hero .pill{display:none}.hero-copy{flex:1;min-width:150px}.mode-buttons{width:100%;gap:7px}.mode-buttons button{flex:1;min-width:90px;padding:9px;font-size:12px}.card{padding:18px}.metrics{gap:10px}.metric{padding:14px 11px;gap:8px}.metric>ha-icon{display:none}.metric strong{font-size:21px}.form-grid{grid-template-columns:1fr}.event{grid-template-columns:76px 24px minmax(0,1fr);gap:8px}.event>div{min-width:0;overflow-wrap:anywhere}.event time{font-size:10px}.banner{flex-wrap:wrap}.banner button{margin-left:33px}.dialog-body{padding:18px}.dialog-head,.dialog-foot{padding:16px 18px}h1{font-size:22px}.page-head>button{width:100%}}
.level-display{display:flex;flex-direction:column;align-items:center;gap:10px;max-width:170px;text-align:center}.level-caption{font-weight:700;font-size:13px;color:var(--level-color);overflow-wrap:anywhere}.plan-wrap{position:relative;width:100%;background:var(--primary-background-color,#f3f6fa);border-radius:12px;overflow:hidden;margin-top:16px}.plan-wrap svg{display:block;width:100%;height:100%}.plan-wrap polygon{cursor:pointer;stroke-width:2}.plan-wrap .draft{pointer-events:none;fill:#2986bb40;stroke:#2986bb;stroke-dasharray:6 4}.plan-wrap text{pointer-events:none;paint-order:stroke;stroke:var(--iq-surface);stroke-width:3px;stroke-linejoin:round;fill:var(--primary-text-color,#122);font-weight:650}.stage-row{padding:16px 0;border-bottom:1px solid var(--iq-border)}.stage-row .form-grid{grid-template-columns:80px minmax(0,1fr)}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
`;

class IQAlarmPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.tab = 0; this.profile = "armed_night"; this.stage = "1"; this.catalog = {entities: [], notify_services: [], areas: []};
    this.plan = null; this.points = []; this.imageURLs = new Map(); this.imageLoading = new Set(); this.data = null; this._connected = false; this._subscribing = false; this._requestBusy = false; this._unsubscribe = null; this._reconnectTimer = null;
    this._onDisconnect = () => this._connection(false);
    this._onReady = () => { if (!this._unsubscribe) this._connect(); };
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="shell"><header class="top"><div class="brand-row"><button class="icon-button" data-command="menu" aria-label="Seitenmenü öffnen">${icon("menu")}</button><div class="brandmark">IQ</div><div class="brand-copy"><div class="brand-title">IQAlarm</div><div class="eyebrow">Intelligenz vor dem Alarm</div></div><div class="connection" role="status"><span class="dot off"></span><span id="connection-text">Verbinde …</span></div></div><nav aria-label="IQAlarm Bereiche" role="tablist"></nav></header><main id="main"><div class="loading">IQAlarm wird verbunden …</div></main><div class="footer-note">IQAlarm · Lokal. Räumlich. Korrelierend.</div></div><dialog id="editor" aria-labelledby="dialog-title"></dialog><div id="toast" role="status" aria-live="polite"></div>`;
    this.shadowRoot.addEventListener("click", e => this._click(e));
    this.shadowRoot.addEventListener("click", e => this._planClick(e));
    this.shadowRoot.addEventListener("keydown", e => { const zone=e.target.closest("[data-room]"); if (zone && ["Enter"," "].includes(e.key)) {e.preventDefault(); this._liveDialog(zone.dataset.room);} });
    this.shadowRoot.addEventListener("submit", e => this._submit(e));
    this.shadowRoot.addEventListener("input", e => { if (e.target.id === "sensor-search") this._renderCatalog(e.target.value); });
    this.shadowRoot.addEventListener("change", e => {
      if (e.target.name === "kind") this._actionVisibility(e.target.value);
      if (e.target.id === "plan-select") { this.plan = e.target.value; this.points = []; this._render(); }
      if (e.target.id === "zone-room") { this.zoneRoom = e.target.value; this.points = structuredClone(this.data.config.floorplans[this.plan]?.zones[this.zoneRoom] || []); this._render(); }
      if (e.target.id === "plan-upload") this._uploadPlan(e.target.files[0]);
      if (e.target.hasAttribute("data-scope")) this._scopeVisibility(e.target.form);
    });
    this.shadowRoot.querySelector("nav").addEventListener("keydown", e => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault(); this.tab = e.key === "Home" ? 0 : e.key === "End" ? 4 : (this.tab + (e.key === "ArrowRight" ? 1 : 4)) % 5;
      this._render(); this.shadowRoot.querySelector(`nav [data-tab="${this.tab}"]`).focus();
    });
  }

  set hass(value) {
    if (this._hass && this._hass.connection !== value.connection) {
      this._unlistenConnection(); this._unsubscribe?.(); this._unsubscribe = null;
    }
    this._hass = value;
    if (this.isConnected) this._listenConnection();
    if (this.isConnected && !this._unsubscribe && !this._subscribing) this._connect();
  }
  get hass() { return this._hass; }
  connectedCallback() { this._listenConnection(); if (this._hass) this._connect(); }
  disconnectedCallback() { this._unlistenConnection(); this._connected = false; this._connectAttempt = (this._connectAttempt || 0) + 1; this._unsubscribe?.(); this._unsubscribe = null; clearTimeout(this._reconnectTimer); clearTimeout(this._toastTimer); for (const item of this.imageURLs.values()) URL.revokeObjectURL(item.url); this.imageURLs.clear(); }

  _listenConnection() {
    const connection = this._hass?.connection;
    if (!connection || this._listeningConnection === connection) return;
    this._unlistenConnection(); this._listeningConnection = connection;
    connection.addEventListener?.("disconnected", this._onDisconnect);
    connection.addEventListener?.("ready", this._onReady);
  }
  _unlistenConnection() {
    this._listeningConnection?.removeEventListener?.("disconnected", this._onDisconnect);
    this._listeningConnection?.removeEventListener?.("ready", this._onReady);
    this._listeningConnection = null;
  }

  async _connect() {
    if (this._subscribing || !this._hass || !this.isConnected) return;
    const attempt = this._connectAttempt = (this._connectAttempt || 0) + 1;
    this._subscribing = true;
    try {
      this.catalog = await this._hass.callWS({type: "iqalarm/catalog"});
      const unsub = await this._hass.connection.subscribeMessage(data => {
        if (!this.isConnected || attempt !== this._connectAttempt) return;
        if (data.available === false) { this._connection(false); return; }
        const first = !this.data; this.data = data; this._connection(true);
        if (first || this.tab === 0) this._render();
        else this._updateLock();
      }, {type: "iqalarm/subscribe"});
      if (!this.isConnected || attempt !== this._connectAttempt) unsub();
      else this._unsubscribe = unsub;
    } catch (err) {
      this._connection(false); this._toast(`Verbindung fehlgeschlagen: ${err.message || err}`, true);
      this._reconnectTimer = setTimeout(() => this._connect(), 5000);
    } finally { this._subscribing = false; }
  }

  _connection(ok) { this._connected = ok; this.shadowRoot.querySelector(".dot").classList.toggle("off", !ok); this.shadowRoot.getElementById("connection-text").textContent = ok ? "Live verbunden · lokal" : "Verbindung unterbrochen"; if (this.data) this._updateLock(); }
  _toast(message, error = false) { const toast = this.shadowRoot.getElementById("toast"); toast.textContent = message; toast.classList.toggle("error", error); clearTimeout(this._toastTimer); this._toastTimer = setTimeout(() => {toast.textContent = "";}, error ? 10000 : 5000); }
  _color(level) { return this.data?.config.stages[level]?.color || "var(--iq-green)"; }
  _roomsOptions(value, blank = "Raum wählen") { return options(Object.fromEntries(Object.values(this.data.config.rooms).map(r => [r.id, r.name])), value, blank); }
  _entities(domain) { return this.catalog.entities.filter(e => domain.includes(e.entity_id.split(".")[0])); }
  _entityOptions(domains, value = "", blank = "Keine") { return options(Object.fromEntries(this._entities(domains).map(e => [e.entity_id, `${e.name} · ${e.entity_id}`])), value, blank); }
  _empty(title, detail, symbol = "shield-search") { return `<div class="empty">${icon(symbol)}<h3>${esc(title)}</h3><p>${esc(detail)}</p></div>`; }
  _head(title, subtitle, button = "") { return `<div class="page-head"><div><h1>${title}</h1><p>${subtitle}</p></div>${button}</div>`; }
  _checkbox(name, label, value) { return `<label class="check"><input type="checkbox" name="${esc(name)}"${checked(value)}><span>${label}</span></label>`; }
  _number(name, label, value, min, max, hint = "") { return `<label class="field">${label}<input type="number" name="${name}" value="${esc(value)}" min="${min}" max="${max}" required>${hint ? `<small>${hint}</small>` : ""}</label>`; }

  _render() {
    this.shadowRoot.querySelector("nav").innerHTML = TABS.map(([symbol, title], i) => `<button role="tab" id="tab-${i}" aria-selected="${i === this.tab}" aria-controls="main" tabindex="${i === this.tab ? 0 : -1}" data-tab="${i}" class="${i === this.tab ? "active" : ""}">${icon(symbol)}${title}</button>`).join("");
    if (!this.data) return;
    if (!Object.hasOwn(this.data.config.profiles, this.profile)) this.profile = Object.keys(this.data.config.profiles)[0];
    this._viewRevision = this.data.config.revision;
    this.shadowRoot.getElementById("main").innerHTML = [() => this._dashboard(), () => this._rooms(), () => this._sensors(), () => this._rules(), () => this._actions()][this.tab]();
    this.shadowRoot.getElementById("main").setAttribute("role", "tabpanel");
    this.shadowRoot.getElementById("main").setAttribute("aria-labelledby", `tab-${this.tab}`);
    this._updateLock();
    if (this.tab === 3) this._scopeVisibility(this.shadowRoot.getElementById("rules-form"));
    if (this.tab === 2) this._renderCatalog("");
    const live = this.shadowRoot.getElementById("live-room-status");
    if (live && this.liveRoom && this.data.config.rooms[this.liveRoom]) live.innerHTML = this._roomLive(this.data.config.rooms[this.liveRoom]);
  }

  _updateLock() {
    const armed = this.data.status.active;
    this.shadowRoot.querySelectorAll("[data-config]").forEach(e => {e.disabled = armed || this._requestBusy || !this._connected;});
    this.shadowRoot.querySelectorAll(".armed-note").forEach(e => {e.hidden = !armed;});
    this.shadowRoot.querySelectorAll('[data-command="mode"], [data-command="profile-arm"]').forEach(button => {
      const target = button.dataset.id;
      button.disabled = !this._connected || this._requestBusy || (button.dataset.command === "profile-arm" && armed && target !== this.data.status.profile_id);
    });
  }

  _scopeVisibility(form) {
    if (!form) return;
    form.querySelectorAll("[data-scope-list]").forEach(element => {
      element.hidden = form.elements[`all_${element.dataset.scopeList}`].checked;
    });
  }

  _profileScope(name, title, values, items) {
    return `<div class="wide"><h3>${title}</h3><div style="margin-top:10px">${this._checkbox(`all_${name}`, `Alle ${title} einbeziehen`, values == null).replace('type="checkbox"', 'type="checkbox" data-scope')}</div><label class="field" data-scope-list="${name}" style="margin-top:12px">${title} auswählen<select name="${name}" multiple>${Object.entries(items).map(([id, label]) => `<option value="${esc(id)}"${values?.includes(id) ? " selected" : ""}>${esc(label)}</option>`).join("")}</select><small>Eine leere Auswahl schließt alle aus. Mehrfachauswahl mit Strg / ⌘.</small></label></div>`;
  }

  _dashboard() {
    const {status: s, config: c} = this.data, sensors = Object.values(c.sensors).filter(x => x.enabled), rooms = Object.values(c.rooms);
    const quarantine = Object.entries(s.quarantine).map(([id]) => `<div class="banner" role="alert">${icon("connection")}<div><strong>Prell-Schutz aktiv: ${esc(c.sensors[id]?.name || id)}</strong><p>Sensor isoliert. Er liefert keine Einbruchsbestätigung für diese Scharfschalt-Periode.</p></div><button class="small" data-command="clear-quarantine" data-id="${esc(id)}">Quarantäne aufheben</button></div>`).join("");
    const open = sensors.filter(x => ["entry_contact", "lock_contact", "vibration_glass"].includes(x.role) && s.raw[x.entity_id] === true).length;
    const offline = sensors.filter(x => s.raw[x.entity_id] == null).length;
    const profileButtons = `<button data-command="mode" data-mode="inactive" class="${!s.profile_id ? "active" : ""}">${icon("shield-off-outline")}Aus · Live</button>` + Object.entries(c.profiles).map(([id, p]) => `<button data-command="profile-arm" data-id="${esc(id)}" class="${s.profile_id === id ? "active" : ""}">${icon(p.reactions_enabled ? "shield-check-outline" : "eye-outline")}${esc(p.name)}</button>`).join("");
    return this._head("Dein Haus im Blick", "Signale verstehen. Ereignisse bestätigen. Gezielt reagieren.") + quarantine +
      `<section class="card hero" style="--level-color:${this._color(s.level)}"><div class="level-display"><div class="level-caption">${esc(s.stage_name)}</div><div class="level-ring" aria-label="${esc(s.stage_name)}: ${s.level}"><strong>${s.level}</strong></div></div><div class="hero-copy"><div class="eyebrow">${esc(s.profile_name || "Live")} · ${s.active ? "Alarmreaktionen aktiv" : "Beobachtung"}</div><h2>${s.active ? "Schutz aktiv" : "Live-Beobachtung"}</h2><p>${s.active ? "Dieses Profil bestimmt Sensoren, Bestätigung und Geräteaktionen." : "Signale und Korrelation laufen mit. Benachrichtigungen, Aufnahmen und Geräteaktionen bleiben aus."}</p><p>${s.monitored_sensors.length} Sensoren ausgewertet · Home Assistant: ${s.active ? "An" : "Aus"}</p>${s.pending_until ? `<div class="countdown">Eingangsverzögerung bis ${date(s.pending_until)}</div>` : s.arming_until ? `<div class="countdown">Scharf ab ${date(s.arming_until)}</div>` : ""}<div class="mode-buttons">${profileButtons}</div></div></section>` + this._floorplan(false) +
      `<div class="metrics">${[["floor-plan", rooms.length, "Räume verbunden"], ["shield-check-outline", !s.active ? sensors.length : s.monitored_sensors.length, !s.active ? "Sensoren eingerichtet" : "Sensoren im Profil"], ["window-open-variant", open, "Kontakte geöffnet"], ["connection", Object.keys(s.quarantine).length + offline, "Störungen / isoliert"]].map(([symbol, n, title]) => `<div class="card metric">${icon(symbol)}<div><strong>${n}</strong><span>${title}</span></div></div>`).join("")}</div>` +
      `<div class="section-title"><h2>Räume & Sicherheitsstatus</h2><button class="small" data-tab="1">Räume verwalten ${icon("arrow-right")}</button></div><div class="grid">${rooms.length ? rooms.map(r => this._roomLive(r)).join("") : this._empty("Hier beginnt dein Schutzkonzept", "Lege Räume an oder importiere deine Home-Assistant-Bereiche.", "floor-plan")}</div>` +
      `<div class="section-title"><h2>Ereignis-Logbuch</h2><span class="muted" style="font-size:12px">Letzte 50 Ereignisse</span></div><section class="card">${s.events.length ? s.events.map(e => `<div class="event" style="--level-color:${this._color(e.level)}"><time>${date(e.timestamp)}</time><span class="event-level">${e.level}</span><div><strong>${esc(e.reason)}</strong>${e.chain?.length ? `<p>${e.chain.map(x => `${esc(x.name)} [${date(x.timestamp)}]`).join(" → ")}</p>` : ""}<p>${esc(e.profile_name || e.mode)} · ${esc(e.kind)}</p></div></div>`).join("") : this._empty("Alles ruhig", "Sicherheitsereignisse und Korrelationsentscheidungen erscheinen hier.")}</section>`;
  }

  _roomLive(room) {
    const state = this.data.status.rooms[room.id] || {level: 0}, sensors = Object.values(this.data.config.sensors).filter(s => s.room_id === room.id || s.front_of.includes(room.id));
    return `<article class="card" style="--level-color:${this._color(state.level)}"><div class="room-head">${icon("floor-plan")}<h3>${esc(room.name)}</h3><span class="pill">${esc(this.data.config.stages[state.level]?.name || "Sicher")}</span></div>${sensors.length ? sensors.map(s => { const raw = this.data.status.raw[s.entity_id], isolated = this.data.status.quarantine[s.entity_id]; return `<div class="sensor-line">${icon(s.role.startsWith("perimeter") ? "cctv" : s.role.startsWith("interior") ? "motion-sensor" : "window-closed-variant")}<span class="sensor-name">${esc(s.name || s.entity_id)}</span><span class="sensor-state ${raw === true ? "on" : ""}">${!s.enabled ? "Deaktiviert" : isolated ? "Isoliert" : raw == null ? "Nicht verfügbar" : raw ? "Aktiv" : "Ruhig"}${!this.data.status.monitored_sensors.includes(s.entity_id) ? " · nur Anzeige" : ""}</span></div>`; }).join("") : `<p>Noch keine Sensoren zugeordnet.</p>`}</article>`;
  }

  _lockNote() { return `<div class="help armed-note" hidden>Zum Ändern der Konfiguration zuerst entschärfen. Quarantäne und Aktionstests bleiben bedienbar.</div>`; }
  _rooms() {
    return this._head("Räume & Topologie", "Verbinde Vorfeld, Außenhaut und Innenraum zu einem räumlichen Schutzkonzept.", `<div class="row"><button data-command="import" data-config>${icon("import")}HA-Bereiche importieren</button><button class="primary" data-command="room-new" data-config>${icon("plus")}Raum anlegen</button></div>`) + this._lockNote() +
      `<div class="grid">${Object.values(this.data.config.rooms).map(r => {
        const sensors = Object.values(this.data.config.sensors), count = prefix => sensors.filter(s => (s.room_id === r.id || s.front_of.includes(r.id)) && prefix.some(p => s.role.startsWith(p))).length;
        return `<article class="card"><div class="row between"><h2>${esc(r.name)}</h2><div><button class="icon-button" aria-label="${esc(r.name)} bearbeiten" data-command="room-edit" data-id="${r.id}" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" aria-label="${esc(r.name)} löschen" data-command="room-delete" data-id="${r.id}" data-config>${icon("delete-outline")}</button></div></div><div class="topology"><span><strong>${count(["perimeter"])}</strong>${icon("cctv")} Vorfeld</span>${icon("arrow-right")}<span><strong>${count(["entry", "lock", "vibration"])}</strong>Außenhaut</span>${icon("arrow-right")}<span><strong>${count(["interior"])}</strong>Innenraum</span></div><p>Überwachung nach gewähltem IQAlarm-Profil</p><p>Angrenzend: ${r.adjacent.length ? r.adjacent.map(id => esc(this.data.config.rooms[id]?.name)).join(", ") : "Keine Räume verknüpft"}</p><button class="small" style="margin-top:16px" data-tab="2">Sensoren zuweisen ${icon("arrow-right")}</button></article>`;
      }).join("") || this._empty("Deine Räume fehlen noch", "Importiere HA-Bereiche oder lege den ersten Raum an.", "floor-plan")}</div><div class="help">Eine Raumverbindung gilt in beiden Richtungen und genau einen Schritt weit. Vorfeld ohne Raumzuordnung überwacht das gesamte Haus.</div>` + this._floorplan(true);
  }

  _sensors() {
    const sensors = Object.values(this.data.config.sensors);
    return this._head("Sensoren & Prell-Schutz", "Jeder Sensor erhält eine klare Rolle. Ein einzelner Kontakt bleibt zunächst ein Verdacht.", `<button data-command="refresh" class="small">${icon("refresh")}Entitäten aktualisieren</button>`) + this._lockNote() +
      `<section class="card"><h2>Konfigurierte Sensoren <span class="muted">· ${sensors.length}</span></h2>${sensors.length ? `<div class="table-scroll"><table><thead><tr><th>Sensor</th><th>Rolle / Raum</th><th>Prell-Schutz</th><th>Status</th><th>Bearbeiten</th></tr></thead><tbody>${sensors.map(s => `<tr><td><strong>${esc(s.name || s.entity_id)}</strong><code>${esc(s.entity_id)}</code></td><td>${esc(ROLES[s.role])}<code>${esc(this.data.config.rooms[s.room_id]?.name || "Vorfeld / global")}</code></td><td>${s.flap_enabled ? `${s.flap_threshold} Wechsel / ${s.flap_window} s` : "Aus"}<code>Entprellen: ${s.debounce_ms || this.data.config.settings.debounce_by_role[s.role] || 0} ms</code></td><td>${!s.enabled ? "Deaktiviert" : this.data.status.quarantine[s.entity_id] ? "Isoliert" : this.data.status.raw[s.entity_id] == null ? "Nicht verfügbar" : this.data.status.raw[s.entity_id] ? "Aktiv" : "Ruhig"}${s.immediate ? " · Override" : ""}</td><td><button class="icon-button" aria-label="${esc(s.name || s.entity_id)} bearbeiten" data-command="sensor-edit" data-id="${esc(s.entity_id)}" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" aria-label="Sensor entfernen" data-command="sensor-delete" data-id="${esc(s.entity_id)}" data-config>${icon("delete-outline")}</button></td></tr>`).join("")}</tbody></table></div>` : this._empty("Noch keine Sensoren", "Wähle unten eine verfügbare Entität aus.", "access-point")}</section>` +
      `<div class="section-title"><h2>Verfügbare Home-Assistant-Entitäten</h2><input class="search" id="sensor-search" type="search" aria-label="Sensoren suchen" placeholder="Name oder Entitäts-ID suchen …"></div><section class="card catalog" id="catalog"></section><div class="help">Kamera-Streaming ist keine Personenerkennung. Verwende bevorzugt den Personen-Binary-Sensor deiner Kamera. Direkte camera-/image_processing-Entitäten brauchen ein explizites Erkennungsattribut und passende aktive Werte.</div>`;
  }

  _renderCatalog(query) {
    const target = this.shadowRoot.getElementById("catalog"); if (!target) return;
    const needle = query.toLocaleLowerCase("de"), entities = this._entities(["binary_sensor", "lock", "camera", "image_processing"]).filter(e => !this.data.config.sensors[e.entity_id] && `${e.name} ${e.entity_id}`.toLocaleLowerCase("de").includes(needle));
    target.innerHTML = entities.slice(0, 150).map(e => `<div class="catalog-row"><div><strong>${esc(e.name)}</strong><code>${esc(e.entity_id)} · ${esc(e.state)}</code></div><button class="small" data-command="sensor-new" data-id="${esc(e.entity_id)}" data-config>${icon("plus")}Zuweisen</button></div>`).join("") || this._empty("Keine passenden Entitäten", "Suche anpassen oder Entitäten aktualisieren.", "magnify");
    if (entities.length > 150) target.innerHTML += `<p>150 von ${entities.length} Treffern. Suche eingrenzen.</p>`;
    this._updateLock();
  }

  _rules() {
    const c = this.data.config, p = c.profiles[this.profile], s = c.settings;
    const names = collection => Object.fromEntries(Object.entries(collection).map(([id, item]) => [id, item.name || item.entity_id || `${KINDS[item.kind]} · ${item.target} · ${item.level}`]));
    return this._head("Alarmstufen & Regeln", "Profile bestimmen die gesamte Steuerung. Namen und Regeln sind frei wählbar.", `<button class="primary" data-command="profile-new" data-config>${icon("plus")}Profil anlegen</button>`) + this._lockNote() +
      `<div class="chips" style="margin-bottom:20px">${Object.entries(c.profiles).map(([id,item]) => `<button data-profile="${esc(id)}" class="${id === this.profile ? "active" : ""}">${icon(item.reactions_enabled ? "shield-check-outline" : "eye-outline")}${esc(item.name)}</button>`).join("")}</div><div class="grid two"><form id="rules-form" class="card"><fieldset data-config><div class="row between"><h2>${esc(p.name)}</h2><div class="row"><button type="button" class="small" data-command="profile-copy">Duplizieren</button><button type="button" class="small danger" data-command="profile-delete" data-id="${esc(this.profile)}">Löschen</button></div></div><div class="form-grid" style="margin-top:20px"><label class="field wide">Profilname<input name="profile_name" value="${esc(p.name)}" required maxlength="100"></label><div class="wide checks">${this._checkbox("reactions_enabled", "Alarmreaktionen und Geräteaktionen erlauben", p.reactions_enabled)}${this._checkbox("perimeter_enabled", "Vorfeld auswerten", p.perimeter_enabled)}${this._checkbox("contacts_enabled", "Öffnungs- und Schlosssensoren auswerten", p.contacts_enabled)}${this._checkbox("simulation_enabled", "Anwesenheitssimulation in diesem Profil erlauben", p.simulation_enabled)}</div><label class="field">Bewegung auswerten<select name="motion_mode">${options({always:"Immer",after_contact:"Erst nach einem Öffnungssignal",ignore:"Nur live anzeigen"},p.motion_mode)}</select></label><label class="field">Freigabe nach Öffnung<select name="motion_scope">${options({room:"Raum und freigegebene Nachbarräume",house:"Gesamtes Haus"},p.motion_scope)}</select></label>${this._profileScope("room_ids", "Räume", p.room_ids, names(c.rooms))}${this._profileScope("sensor_ids", "Sensoren", p.sensor_ids, names(c.sensors))}${this._profileScope("action_ids", "Aktionen", p.action_ids, names(c.actions))}${this._number("perimeter_seconds","Vorfeld-Gedächtnis (Sekunden)",p.perimeter_seconds,1,3600)}${this._number("correlation_seconds","Korrelationsfenster (Sekunden)",p.correlation_seconds,1,3600)}${this._number("entry_seconds","Eingangsverzögerung (Sekunden)",p.entry_seconds,0,600)}${this._number("exit_seconds","Ausgangsverzögerung (Sekunden)",p.exit_seconds,0,600)}</div><div class="checks" style="margin-top:24px">${["perimeter_contact","contact_motion","multi_contact","multi_motion"].map(key => this._checkbox(key,RULES[key],p[key])).join("")}${this._checkbox("adjacent_rooms","Angrenzende Räume für Öffnung + Bewegung einbeziehen",p.adjacent_rooms)}</div><h3 style="margin-top:24px">Ereignis → Alarmstufe</h3><div class="form-grid" style="margin-top:16px">${Object.entries(RULES).map(([key,name]) => `<label class="field">${esc(name)}<select name="target_${key}">${options(Object.fromEntries(c.stages.filter(stage => !["perimeter","single","flapping"].includes(key) || !stage.requires_confirmation).map(stage => [stage.id,`${c.stages.indexOf(stage)} · ${stage.name}`])),p.stage_targets[key])}</select></label>`).join("")}</div><div class="help">Ohne Alarmreaktionen läuft dieses Profil als Beobachtung. Sensorzustände bleiben immer sichtbar. Bewegungsfreigabe ersetzt keine räumlich passende Einbruchsbestätigung.</div><button class="primary" type="submit">Profil speichern</button></fieldset></form>` +
      `<form id="settings-form" class="card"><fieldset data-config><h2>System & Anwesenheitssimulation</h2><label class="field" style="margin-top:20px">Hintergrundprofil bei Aus<select name="observation_profile_id">${options(Object.fromEntries(Object.entries(c.profiles).filter(([,v]) => !v.reactions_enabled).map(([id,v]) => [id,v.name])), s.observation_profile_id, "Keine Auswertung")}</select></label><div class="checks" style="margin:20px 0">${this._checkbox("diagnose_disarmed", "Prell-Diagnose auch im unscharfen Zustand", s.diagnose_disarmed)}${this._checkbox("block_open_on_arm", "Scharfschalten bei geöffneten Kontakten verhindern", s.block_open_on_arm)}${this._checkbox("block_unavailable_on_arm", "Scharfschalten bei nicht verfügbaren Sensoren verhindern", s.block_unavailable_on_arm)}${this._checkbox("auto_camera_snapshot", "Bei Vorfeld automatisch verknüpfte Kamera fotografieren", s.auto_camera_snapshot)}${this._checkbox("auto_camera_record", "Bei Vorfeld zusätzlich 30 Sekunden Kamera aufnehmen", s.auto_camera_record)}${this._checkbox("simulation_enabled", "Anwesenheitssimulation global freigeben (zusätzlich pro Profil)", s.simulation_enabled)}</div><div class="form-grid">${this._number("simulation_start", "Lichtsimulation ab (Stunde)", s.simulation_start, 0, 23)}${this._number("simulation_end", "Lichtsimulation bis (Stunde)", s.simulation_end, 1, 24)}<label class="field wide">Simulationslichter<select name="simulation_lights" multiple>${this._entities(["light"]).map(e => `<option value="${esc(e.entity_id)}"${s.simulation_lights.includes(e.entity_id) ? " selected" : ""}>${esc(e.name)}</option>`).join("")}</select><small>Mehrfachauswahl mit Strg / ⌘. Bereits eingeschaltete Lichter werden nicht übernommen.</small></label>${this._number("retention_days", "Kameradateien aufbewahren (Tage)", s.retention_days, 1, 90)}</div><details style="margin-top:20px"><summary>Standard-Entprellzeiten nach Rolle</summary><div class="form-grid" style="margin-top:14px">${Object.entries(ROLES).map(([key, name]) => this._number(`debounce_${key}`, `${name} (ms)`, s.debounce_by_role[key] || 0, 0, 60000)).join("")}</div></details><div class="help">Kameradateien bleiben im geschützten IQAlarm-Verzeichnis. Aufzeichnungen benötigen eine Kamera mit stream-Unterstützung. Die Alarmkonfiguration erfolgt vollständig hier.</div><div class="save-row"><button type="submit" class="primary">${icon("content-save-outline")}System speichern</button></div></fieldset></form></div>` + this._stagesEditor();
  }

  _actions() {
    const actions = Object.values(this.data.config.actions).filter(a => a.level === this.stage);
    return this._head("Aktionen & Benachrichtigungen", "Reaktionen direkt konfigurieren – mit nachvollziehbaren Tests.", `<button class="primary" data-command="action-new" data-config>${icon("plus")}Aktion hinzufügen</button>`) + this._lockNote() +
      `<div class="chips" style="margin-bottom:22px">${[...this.data.config.stages.slice(1).map((stage,index) => [stage.id, `${index+1} · ${stage.name}`]), ["diagnostic", "Sensor-Prellen"]].map(([id, name]) => `<button data-stage="${id}" class="${this.stage === id ? "active" : ""}">${id === "diagnostic" ? icon("connection") : `<b>${id}</b>`}${esc(name)}</button>`).join("")}</div><section class="card"><h2>${this.stage === "diagnostic" ? "Diagnose · Sensor-Prellen" : esc(this.data.config.stages.find(stage => stage.id === this.stage)?.name || "Stufe")}</h2><p>${this.data.config.stages.find(stage => stage.id === this.stage)?.allow_loud ? "Bestätigte Ereignisse dürfen Sirenen, kritische Pushs und Fluchtweg-Aktionen ausführen." : "Lautlose Reaktionen: Push, Licht, Rollos und Kamera. Akustische und freie Aktionen benötigen eine bestätigte, ausdrücklich freigegebene Stufe."}</p>${actions.length ? actions.map(a => `<div class="action-card">${icon(a.kind === "notify" ? "bell-outline" : a.kind === "light" ? "lightbulb-outline" : a.kind === "siren" ? "alarm-light-outline" : "play-box-outline")}<div class="description"><h3>${esc(KINDS[a.kind])}${a.enabled ? "" : " · deaktiviert"}</h3><p>${esc(a.target)}${a.critical ? " · Kritischer Alarm" : ""} · ${a.duration} s</p>${a.kind === "notify" ? `<p>${esc(a.message)}</p>` : ""}</div><button class="icon-button" data-command="action-edit" data-id="${esc(a.id)}" aria-label="Aktion bearbeiten" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" data-command="action-delete" data-id="${esc(a.id)}" aria-label="Aktion löschen" data-config>${icon("delete-outline")}</button></div>`).join("") : `<div style="margin-top:20px">${this._empty("Noch keine Aktionen in dieser Stufe", "Füge eine Push-Benachrichtigung oder eine passende Geräteaktion hinzu.", "bell-plus-outline")}</div>`}</section><section class="card" style="margin-top:18px"><h2>Abläufe prüfen</h2><p>Ein Trockenlauf zeigt den Aktionsplan und verändert keine Alarmstufe. Ein realer Test führt die konfigurierten Geräteaktionen aus.</p><label class="field" style="margin-top:16px">Aktionen dieses Profils testen<select id="test-profile">${options(Object.fromEntries(Object.entries(this.data.config.profiles).map(([id, p]) => [id, p.name])), this.profile, "Alle Aktionen / aktuelles Profil")}</select></label><div class="row" style="margin-top:18px"><button data-command="test" class="primary">${icon("test-tube")}Stufe ${esc(this.stage)} trocken testen</button><label class="check"><input type="checkbox" id="real-test"><span>Aktionen tatsächlich ausführen${this.data.config.stages.find(stage => stage.id === this.stage)?.allow_loud ? " (inklusive Sirenen!)" : ""}</span></label></div><div id="test-plan" aria-live="polite"></div></section><div class="help">Nachrichtenvariablen: <code>{{room}}</code>, <code>{{sensor}}</code>, <code>{{level}}</code>, <code>{{reason}}</code>, <code>{{chain}}</code>, <code>{{mode}}</code>, <code>{{profile}}</code>. Kritische Pushs erfordern die Freigabe in der Companion-App und im Betriebssystem.</div>`;
  }

  _stagesEditor() {
    return `<form id="stages-form" class="card" style="margin-top:22px"><fieldset data-config><div class="row between"><h2>Alarmstufen · ${this.data.config.stages.length}</h2><div class="row"><button type="button" data-command="stage-remove">Letzte entfernen</button><button type="button" data-command="stage-add">Stufe hinzufügen</button></div></div><p>Namen und Anzahl frei festlegen (1–32). Die Reihenfolge bestimmt die angezeigte Zahl. Bestehende Regeln und Aktionen verweisen auf die feste Kennung. Vor dem Entfernen ihre Zuordnungen ändern.</p><div id="stage-rows">${this.data.config.stages.map((stage,index) => this._stageRow(stage,index)).join("")}</div><div class="save-row"><button class="primary" type="submit">Alarmstufen speichern</button></div></fieldset></form>`;
  }
  _stageRow(stage,index) {
    return `<div class="stage-row" data-stage-row="${esc(stage.id)}"><strong>Stufe ${index}</strong><div class="form-grid" style="margin-top:12px"><label class="field">Farbe<input name="stage_color" type="color" value="${esc(stage.color)}"></label><label class="field">Bezeichnung<input name="stage_name" required maxlength="100" value="${esc(stage.name)}"></label></div><div class="row" style="margin-top:12px">${this._checkbox("stage_confirmed","Bestätigung erforderlich",stage.requires_confirmation)}${this._checkbox("stage_loud","Akustische / freie Aktionen erlauben",stage.allow_loud)}${this._checkbox("stage_latch","Bis zum Ausschalten halten",stage.latch)}</div>${index === 0 ? '<p>Normalzustand: immer lautlos, ohne Bestätigung und Halten.</p>' : ''}</div>`;
  }
  _changeStageRows(add) {
    const rows = this.shadowRoot.getElementById("stage-rows"), count = rows.children.length;
    if (add && count < 32) rows.insertAdjacentHTML("beforeend",this._stageRow({id:crypto.randomUUID().replaceAll("-",""),name:`Stufe ${count}`,color:"#2986bb",requires_confirmation:false,allow_loud:false,latch:false},count));
    else if (!add && count > 1) rows.lastElementChild.remove();
  }
  _floorplan(edit) {
    const plans = Object.values(this.data.config.floorplans);
    if (!plans.some(plan => plan.id === this.plan)) this.plan = plans[0]?.id || null;
    const plan = this.data.config.floorplans[this.plan];
    if (!plan) return `<section class="card" style="margin:20px 0"><h2>Dein Haus als Live-Grundriss</h2><p>PNG oder JPG pro Etage hochladen und Räume einmal markieren. Fenster, Bewegung und Personen erscheinen aus den vorhandenen Sensorzuordnungen.</p><button style="margin-top:16px" data-command="floorplan-new" data-config>Grundriss anlegen</button></section>`;
    const cached = this.imageURLs.get(plan.id);
    if (plan.image && cached?.image !== plan.image) this._loadPlan(plan);
    const image = cached?.image === plan.image ? cached.url : "";
    const width = plan.width || 1000, height = plan.height || 600;
    return `<section class="card" style="margin:20px 0"><div class="row between"><h2>${edit ? "Grundrisse & Raum-Markierungen" : "Live-Grundriss"}</h2><label class="field">Etage<select id="plan-select">${options(Object.fromEntries(plans.map(p => [p.id,p.name])),plan.id)}</select></label></div>${edit ? `<div class="row" style="margin-top:14px"><button data-command="floorplan-new" data-config>Etage hinzufügen</button><button data-command="floorplan-edit" data-id="${esc(plan.id)}" data-config>Umbenennen</button><button data-command="floorplan-delete" data-id="${esc(plan.id)}" data-config>Löschen</button><label class="field">PNG / JPG hochladen (max. 10 MB)<input type="file" id="plan-upload" accept="image/png,image/jpeg" data-config></label></div><p style="margin-top:14px">Raum auswählen und seine Eckpunkte im Bild anklicken. Auch Außenbereiche lassen sich als Raum markieren. Anschließend „Bereich speichern“.</p><div class="row" style="margin-top:14px"><label class="field">Raum / Außenbereich<select id="zone-room">${this._roomsOptions(this.zoneRoom,"Raum auswählen")}</select></label><button data-command="zone-undo" data-config>Letzter Punkt zurück</button><button data-command="zone-clear" data-config>Neu zeichnen</button><button class="primary" data-command="zone-save" data-config>Bereich speichern</button><button data-command="zone-delete" data-config>Bereich entfernen</button></div>` : `<p>Räume anklicken für Sensorstatus und Kamera. Auch vom Profil ignorierte Signale bleiben sichtbar.</p>`}${image ? `<div class="plan-wrap" style="aspect-ratio:${width}/${height}"><svg id="floorplan" role="img" aria-label="${esc(plan.name)}" data-edit="${edit}" viewBox="0 0 ${width} ${height}"><image href="${esc(image)}" width="${width}" height="${height}"/>${Object.entries(plan.zones).map(([room,points]) => this._zoneSVG(plan,room,points)).join("")}<polygon class="draft" points="${edit ? this.points.map(([x,y]) => `${x*width},${y*height}`).join(" ") : ""}"/></svg></div>` : `<div class="empty" style="margin-top:16px">${plan.image ? "Bild wird geladen …" : "Lade den Grundriss unter Räume & Topologie hoch."}</div>`}</section>`;
  }
  _zoneSVG(plan,room,points) {
    const status = this.data.status.rooms[room] || {}, roomName = this.data.config.rooms[room]?.name || room;
    const tags = [status.open?.length ? "Fenster / Tür offen" : "",status.motion?.length ? "Bewegung" : "",status.persons?.length ? "Person draußen" : "",status.quarantined?.length ? "Sensor isoliert" : ""].filter(Boolean);
    const center = points.reduce(([x,y],point) => [x+point[0]/points.length,y+point[1]/points.length],[0,0]);
    const color = tags.length ? (status.confirmed ? "#d34454" : "#b87808") : this._color(status.level || 0);
    return `<g data-room="${esc(room)}" role="button" tabindex="0" aria-label="${esc(roomName+': '+(tags.join(', ') || 'Ruhig'))}"><polygon points="${points.map(([x,y]) => `${x*plan.width},${y*plan.height}`).join(" ")}" fill="${color}" fill-opacity=".19" stroke="${color}" vector-effect="non-scaling-stroke"/><text x="${center[0]*plan.width}" y="${center[1]*plan.height}" text-anchor="middle" font-size="${Math.max(plan.width,plan.height)*.019}">${esc(roomName)}<tspan x="${center[0]*plan.width}" dy="1.4em" font-size=".8em">${esc(tags.join(' · ') || 'Ruhig')}</tspan></text></g>`;
  }
  async _loadPlan(plan) {
    const key = `${plan.id}/${plan.image}`; if (this.imageLoading.has(key)) return;
    this.imageLoading.add(key);
    try {
      const response = await this._hass.fetchWithAuth(`/api/iqalarm/floorplans/${encodeURIComponent(plan.id)}/image`);
      if (!response.ok) throw new Error(`Grundriss konnte nicht geladen werden (${response.status})`);
      const blob = await response.blob(); if (!this.isConnected) return;
      const previous = this.imageURLs.get(plan.id); if (previous) URL.revokeObjectURL(previous.url);
      this.imageURLs.set(plan.id,{image:plan.image,url:URL.createObjectURL(blob)}); if (this.tab === 0 || this.tab === 1) this._render();
    } catch (err) { this._toast(err.message,true); } finally { this.imageLoading.delete(key); }
  }
  async _uploadPlan(file) {
    if (!file) return;
    try {
      if (file.size > 10*1024*1024) throw new Error("Bild maximal 10 MB");
      const response = await this._hass.fetchWithAuth(`/api/iqalarm/floorplans/${encodeURIComponent(this.plan)}/image`,{method:"POST",headers:{"X-IQAlarm-Revision":String(this._viewRevision),"Content-Type":file.type},body:file});
      const data = await response.json(); if (!response.ok) throw new Error(data.message || "Upload fehlgeschlagen");
      this.data = data; this.points = []; this._render(); this._toast("Grundriss gespeichert");
    } catch(err) { this._toast(err.message,true); }
  }
  _planClick(event) {
    const svg = event.target.closest("#floorplan"); if (!svg) return;
    if (svg.dataset.edit === "true") {
      if (this.data.status.active || !this.zoneRoom || this.points.length >= 64) return;
      const rect = svg.getBoundingClientRect();
      this.points.push([Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))]); this._refreshDraft();
    } else { const zone = event.target.closest("[data-room]"); if (zone) this._liveDialog(zone.dataset.room); }
  }
  _refreshDraft() {
    const plan = this.data.config.floorplans[this.plan];
    this.shadowRoot.querySelector("#floorplan .draft")?.setAttribute("points",this.points.map(([x,y]) => `${x*plan.width},${y*plan.height}`).join(" "));
  }
  _liveDialog(room) {
    const data = this.data.config.rooms[room]; if (!data) return;
    const sensors = Object.values(this.data.config.sensors).filter(s => s.room_id === room || s.front_of.includes(room));
    const cameras = [...new Set(sensors.flatMap(s => [s.camera_entity_id,s.entity_id.startsWith("camera.") ? s.entity_id : null]).filter(Boolean))];
    this.liveRoom = room;
    this._dialog(data.name, `<div id="live-room-status">${this._roomLive(data)}</div>` + cameras.map(id => `<button type="button" style="margin-top:14px" data-command="more-info" data-id="${esc(id)}">${icon("cctv")}${esc(this.catalog.entities.find(e => e.entity_id === id)?.name || id)}</button>`).join(""),"live");
    this.shadowRoot.querySelector('#editor [type="submit"]').hidden = true;
  }

  _dialog(title, body, type, id = "") {
    this._dialogRevision = this.data.config.revision;
    const dialog = this.shadowRoot.getElementById("editor");
    dialog.innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-button" data-command="close" aria-label="Schließen">${icon("close")}</button></div><form id="editor-form" data-type="${type}" data-id="${esc(id)}"><div class="dialog-body">${body}</div><div class="dialog-foot"><button type="button" data-command="close">Abbrechen</button><button type="submit" class="primary">Speichern</button></div></form>`;
    dialog.showModal();
  }

  _roomDialog(id) {
    const r = this.data.config.rooms[id] || {name: "", adjacent: [], home_enabled: false};
    this._dialog(id ? "Raum bearbeiten" : "Raum anlegen", `<div class="form-grid"><label class="field wide">Raumname<input name="name" value="${esc(r.name)}" required maxlength="100" autofocus></label><div class="wide checks"><h3>Direkt angrenzende Räume</h3>${Object.values(this.data.config.rooms).filter(x => x.id !== id).map(x => this._checkbox(`adj_${x.id}`, esc(x.name), r.adjacent.includes(x.id))).join("") || `<p>Noch keine weiteren Räume vorhanden.</p>`}</div></div>`, "room", id);
  }

  _profileDialog(copy = false) {
    const current = this.data.config.profiles[this.profile];
    this._profileTemplate = copy ? this.profile : null;
    this._dialog(copy ? "Profil duplizieren" : "Profil anlegen", `<label class="field">Profilname<input name="name" value="${copy ? esc(current.name.slice(0,85)+" Kopie") : ""}" required maxlength="100" autofocus></label><p style="margin-top:18px">${copy ? "Sensoren, Aktionen und Regeln werden kopiert." : "Das neue Profil beginnt als lautlose Beobachtung. Lege anschließend Sensoren, Regeln und Reaktionen fest."}</p>`, "profile");
  }

  _sensorDialog(id) {
    const old = this.data.config.sensors[id], e = this.catalog.entities.find(x => x.entity_id === id);
    const s = old || {entity_id: id, name: e?.name || id, role: id.startsWith("camera.") ? "perimeter_camera" : id.startsWith("lock.") ? "lock_contact" : "entry_contact", front_of: [], enabled: true, flap_enabled: true, flap_threshold: 3, flap_window: 15, debounce_ms: 0, active_states: id.startsWith("lock.") ? ["unlocked", "open"] : ["on"]};
    this._dialog(old ? "Sensor bearbeiten" : "Sensor zuweisen", `<div class="form-grid"><label class="field wide">Entität<input value="${esc(id)}" readonly></label><label class="field wide">Anzeigename<input name="name" value="${esc(s.name)}" required maxlength="200"></label><label class="field">Sicherheitsrolle<select name="role">${options(ROLES, s.role)}</select></label><label class="field">Raum<select name="room_id">${this._roomsOptions(s.room_id, "Kein Raum / globales Vorfeld")}</select></label><label class="field wide">Vorfeld vor diesen Räumen<select name="front_of" multiple>${Object.values(this.data.config.rooms).map(r => `<option value="${r.id}"${s.front_of.includes(r.id) ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select><small>Nur für Vorfeld-Rollen. Keine Auswahl bedeutet global, falls auch kein Raum gewählt ist.</small></label><label class="field wide">Unabhängige Signalquelle<input name="source_id" value="${esc(s.source_id || "")}" maxlength="200" placeholder="Standard: Entitäts-ID"><small>Mehrere Entitäten desselben physischen Sensors müssen dieselbe Quellenkennung haben. Sie dürfen sich nicht gegenseitig bestätigen.</small></label><div class="wide checks">${this._checkbox("enabled", "Sensor aktivieren", s.enabled)}${this._checkbox("flap_enabled", "Anti-Flapping für Öffnungs-/Schlosssensoren aktivieren", s.flap_enabled)}</div>${this._number("flap_threshold", "Quarantäne ab N Zustandswechseln", s.flap_threshold, 3, 100)}${this._number("flap_window", "Innerhalb von W Sekunden", s.flap_window, 1, 300)}${this._number("debounce_ms", "Mindest-Aktivzeit (Millisekunden)", s.debounce_ms, 0, 60000, "0 verwendet den Standard der Sensorrolle.")}<label class="field">Verknüpfte Kamera<select name="camera_entity_id">${this._entityOptions(["camera"], s.camera_entity_id)}</select></label><label class="field">Erkennungsattribut (optional)<input name="attribute" value="${esc(s.attribute || "")}" maxlength="100" placeholder="z. B. person_detected"><small>Für camera/image_processing erforderlich.</small></label><label class="field">Aktive Werte, durch Komma getrennt<input name="active_states" value="${esc(s.active_states.join(", "))}" required maxlength="500"><small>Boolesche Attribute: true / false; Zählwerte explizit angeben.</small></label><div class="wide checks">${this._checkbox("entry_delay", "Eingangsverzögerung für diesen Öffnungssensor erlauben", s.entry_delay)}${this._checkbox("immediate", "Darf alleine die zugeordnete bestätigte Stufe auslösen (Override)", s.immediate)}</div><div class="help wide">Override, Rauch und Panik lösen bei scharfer Anlage alleine aus. Für diese Sensoren ersetzt die Entprellzeit die Wartezeit auf eine Bestätigung.</div></div>`, "sensor", id);
  }

  _actionDialog(id) {
    const a = this.data.config.actions[id] || {level: this.stage, kind: "notify", target: "", title: "IQAlarm · Stufe {{level}}", message: "{{room}}: {{sensor}} — {{reason}}\n{{chain}}", enabled: true, critical: false, duration: 180, brightness: 100};
    const kinds = Object.fromEntries(Object.entries(KINDS).filter(([kind]) => this.data.config.stages.find(stage => stage.id === a.level)?.allow_loud || !["siren", "switch", "script", "tts"].includes(kind)));
    this._dialog(id ? "Aktion bearbeiten" : "Aktion hinzufügen", `<div class="form-grid"><label class="field">Aktionsart<select name="kind">${options(kinds, a.kind)}</select></label><label class="field">Ziel / Dienst<input name="target" list="action-targets" value="${esc(a.target)}" required><datalist id="action-targets"></datalist><small>Ein konkreter notify-Dienst oder eine Geräte-Entität.</small></label><label class="field wide" data-kinds="notify">Titel<input name="title" value="${esc(a.title)}" maxlength="200"></label><label class="field wide" data-kinds="notify,tts">Nachricht<textarea name="message" maxlength="3000">${esc(a.message)}</textarea><small>{{room}} · {{sensor}} · {{level}} · {{reason}} · {{chain}}</small></label><label class="field wide" data-kinds="notify">Kamera-Snapshot anhängen<select name="camera_entity_id">${this._entityOptions(["camera"], a.camera_entity_id)}</select></label><div class="wide" data-kinds="notify">${this._checkbox("critical", "Kritischer Alarm (nur für bestätigte, akustisch freigegebene Stufen)", a.critical)}</div><label class="field wide" data-kinds="tts">Lautsprecher<select name="media_player">${this._entityOptions(["media_player"], a.media_player)}</select></label><div data-kinds="siren,switch,script,light,record">${this._number("duration", "Automatisch aus nach / Aufnahmedauer (Sekunden)", a.duration, 1, 3600)}</div><div data-kinds="light">${this._number("brightness", "Helligkeit (%)", a.brightness, 1, 100)}</div><label class="field" data-kinds="light">Warnfarbe<input name="color" type="color" value="${a.color ? '#' + a.color.map(n => n.toString(16).padStart(2, '0')).join('') : '#ff3344'}"></label><div data-kinds="light">${this._checkbox("use_color", "Warnfarbe verwenden", !!a.color)}</div><div class="wide">${this._checkbox("enabled", "Aktion aktivieren", a.enabled)}</div></div><div class="help">Selbst eingeschaltete Sirenen, Schalter und Lichter werden zeitgesteuert oder beim Entschärfen ausgeschaltet. Bereits eingeschaltete Geräte werden nicht abgeschaltet. Rollos werden geöffnet und bleiben offen.</div>`, "action", id);
    this._actionVisibility(a.kind);
  }

  _actionVisibility(kind) {
    const dialog = this.shadowRoot.getElementById("editor");
    dialog.querySelectorAll("[data-kinds]").forEach(e => {e.hidden = !e.dataset.kinds.split(",").includes(kind);});
    const targets = kind === "notify" ? [...this.catalog.notify_services, ...this._entities(["notify"]).map(e => e.entity_id)] : this._entities([kind === "snapshot" || kind === "record" ? "camera" : kind]).map(e => e.entity_id);
    dialog.querySelector("#action-targets").innerHTML = [...new Set(targets)].map(id => `<option value="${esc(id)}"></option>`).join("");
  }

  async _call(type, args = {}) {
    if (!this._hass) throw new Error("Home Assistant ist nicht verbunden");
    return await this._hass.callWS({type: `iqalarm/${type}`, ...args});
  }

  async _click(event) {
    const button = event.target.closest("button"); if (!button || button.disabled) return;
    if (button.dataset.tab != null) { this.tab = Number(button.dataset.tab); this._render(); return; }
    if (button.dataset.profile) { this.profile = button.dataset.profile; this._render(); return; }
    if (button.dataset.stage) { this.stage = button.dataset.stage; this._render(); return; }
    const command = button.dataset.command, id = button.dataset.id;
    try {
      if (command === "menu") this.dispatchEvent(new CustomEvent("hass-toggle-menu", {bubbles: true, composed: true}));
      else if (command === "close") { this.liveRoom = null; this.shadowRoot.getElementById("editor").close(); }
      else if (command === "room-new" || command === "room-edit") this._roomDialog(id);
      else if (command === "sensor-new" || command === "sensor-edit") this._sensorDialog(id);
      else if (command === "action-new" || command === "action-edit") this._actionDialog(id);
      else if (command === "floorplan-new" || command === "floorplan-edit") this._dialog(id ? "Grundriss bearbeiten" : "Grundriss anlegen", `<label class="field">Etage / Name<input name="name" maxlength="100" required value="${esc(this.data.config.floorplans[id]?.name || "")}"></label>`, "floorplan", id);
      else if (command === "zone-save" || command === "zone-delete") {
        if (!this.zoneRoom) throw new Error("Bitte einen Raum auswählen");
        const item = structuredClone(this.data.config.floorplans[this.plan]);
        if (command === "zone-save") { if (this.points.length < 3) throw new Error("Mindestens drei Eckpunkte markieren"); item.zones[this.zoneRoom] = this.points; }
        else { delete item.zones[this.zoneRoom]; this.points = []; }
        this.data = await this._call("crud", {collection:"floorplans",operation:"save",item,revision:this._viewRevision}); this._render();
      }
      else if (command === "zone-undo") { this.points.pop(); this._refreshDraft(); }
      else if (command === "zone-clear") { this.points = []; this._refreshDraft(); }
      else if (command === "stage-add" || command === "stage-remove") this._changeStageRows(command === "stage-add");
      else if (command === "room-live") this._liveDialog(id);
      else if (command === "more-info") this.dispatchEvent(new CustomEvent("hass-more-info", {detail:{entityId:id},bubbles:true,composed:true}));
      else if (command === "profile-new" || command === "profile-copy") this._profileDialog(command === "profile-copy");
      else if (command === "profile-arm") {
        button.disabled = true; this.data = await this._call("arm_profile", {profile_id: id}); this._render();
      }
      else if (command === "mode") {
        const mode = button.dataset.mode;
        if (mode === "inactive" && this.data.pin_required) this._dialog("Anlage entschärfen", `<label class="field">PIN<input name="code" type="password" inputmode="numeric" pattern="[0-9]{4,12}" required autocomplete="off" autofocus></label>`, "disarm");
        else {button.disabled = true; this.data = await this._call("set_mode", {mode}); this._render();}
      } else if (command === "clear-quarantine") {this.data = await this._call("clear_quarantine", {entity_id: id}); this._render();}
      else if (command === "refresh") {this.catalog = await this._call("catalog"); this._render(); this._toast("Entitäten aktualisiert");}
      else if (command === "import") {this.data = await this._call("import_areas", {revision: this._viewRevision}); this._render(); this._toast("Home-Assistant-Bereiche importiert");}
      else if (command?.endsWith("-delete")) {
        const collection = {"room-delete": "rooms", "sensor-delete": "sensors", "action-delete": "actions", "profile-delete": "profiles", "floorplan-delete":"floorplans"}[command];
        this._dialog("Eintrag entfernen", `<p>Dieser konfigurierte Eintrag wird aus IQAlarm entfernt. Home-Assistant-Entitäten bleiben erhalten.</p>`, `delete-${collection}`, id);
      } else if (command === "test") {
        button.disabled = true;
        const dry_run = !this.shadowRoot.getElementById("real-test").checked;
        const profile_id = this.shadowRoot.getElementById("test-profile").value || undefined;
        const result = await this._call("test_level", {level: this.stage, dry_run, ...(profile_id ? {profile_id} : {})});
        this.shadowRoot.getElementById("test-plan").innerHTML = `<p>${dry_run ? "Trockenlauf abgeschlossen. Keine Geräte wurden geschaltet." : "Realer Test abgeschlossen. Ausführungsfehler erscheinen im Logbuch."}</p><pre>${esc(JSON.stringify(result.actions, null, 2))}</pre>`;
      }
    } catch (err) { this._toast(err.message || String(err), true); }
    finally { if (button.isConnected) button.disabled = false; this._updateLock(); }
  }

  async _submit(event) {
    event.preventDefault(); if (this._requestBusy) return;
    const form = event.target, fields = new FormData(form), get = k => String(fields.get(k) || ""), num = k => Number(fields.get(k)), bool = k => fields.has(k);
    const button = form.querySelector('[type="submit"]');
    this._requestBusy = true; if (button) button.disabled = true;
    try {
      if (form.id === "stages-form") {
        const config = structuredClone(this.data.config);
        config.stages = [...form.querySelectorAll("[data-stage-row]")].map((row,index) => ({id:row.dataset.stageRow,name:row.querySelector('[name="stage_name"]').value.trim(),color:row.querySelector('[name="stage_color"]').value,requires_confirmation:index > 0 && row.querySelector('[name="stage_confirmed"]').checked,allow_loud:index > 0 && row.querySelector('[name="stage_loud"]').checked,latch:index > 0 && row.querySelector('[name="stage_latch"]').checked}));
        this.data = await this._call("config/save",{config,revision:this._viewRevision});
      } else if (form.id === "rules-form" || form.id === "settings-form") {
        const config = structuredClone(this.data.config);
        if (form.id === "rules-form") {
          const p = config.profiles[this.profile];
          p.name = get("profile_name").trim();
          p.motion_mode = get("motion_mode"); p.motion_scope = get("motion_scope");
          p.stage_targets = Object.fromEntries(Object.keys(RULES).map(key => [key,get(`target_${key}`)]));
          ["room_ids", "sensor_ids", "action_ids"].forEach(key => p[key] = bool(`all_${key}`) ? null : fields.getAll(key));
          ["perimeter_seconds", "correlation_seconds", "entry_seconds", "exit_seconds"].forEach(k => p[k] = num(k));
          ["perimeter_contact", "contact_motion", "multi_contact", "multi_motion", "adjacent_rooms", "reactions_enabled", "perimeter_enabled", "contacts_enabled", "simulation_enabled"].forEach(k => p[k] = bool(k));
        } else {
          const s = config.settings;
          s.observation_profile_id = get("observation_profile_id") || null;
          ["diagnose_disarmed", "block_open_on_arm", "block_unavailable_on_arm", "auto_camera_snapshot", "auto_camera_record", "simulation_enabled"].forEach(k => s[k] = bool(k));
          ["retention_days", "simulation_start", "simulation_end"].forEach(k => s[k] = num(k));
          s.simulation_lights = fields.getAll("simulation_lights");
          s.debounce_by_role = Object.fromEntries(Object.keys(ROLES).map(k => [k, num(`debounce_${k}`)]));
        }
        this.data = await this._call("config/save", {config, revision: this._viewRevision});
      } else if (form.id === "editor-form") {
        const type = form.dataset.type, id = form.dataset.id;
        if (type === "disarm") this.data = await this._call("set_mode", {mode: "disarmed", code: get("code")});
        else if (type.startsWith("delete-")) this.data = await this._call("crud", {collection: type.slice(7), operation: "delete", key: id, revision: this._dialogRevision});
        else {
          let item, collection;
          if (type === "room") {collection = "rooms"; item = {name: get("name"), adjacent: Object.keys(this.data.config.rooms).filter(r => bool(`adj_${r}`)), home_enabled: false, area_id: this.data.config.rooms[id]?.area_id || null}; if (id) item.id = id;}
          else if (type === "sensor") {
            collection = "sensors"; item = {entity_id: id, name: get("name"), role: get("role"), room_id: get("room_id") || null, front_of: fields.getAll("front_of"), source_id: get("source_id"), enabled: bool("enabled"), flap_enabled: bool("flap_enabled"), flap_threshold: num("flap_threshold"), flap_window: num("flap_window"), debounce_ms: num("debounce_ms"), entry_delay: bool("entry_delay"), immediate: bool("immediate"), attribute: get("attribute") || null, active_states: get("active_states").split(",").map(s => s.trim()).filter(Boolean), camera_entity_id: get("camera_entity_id") || null};
          } else if (type === "action") {
            collection = "actions"; const old = this.data.config.actions[id], kind = get("kind");
            item = {level: old?.level || this.stage, kind, target: get("target"), title: get("title"), message: get("message"), duration: num("duration"), brightness: num("brightness"), critical: kind === "notify" && bool("critical"), camera_entity_id: kind === "notify" ? get("camera_entity_id") || null : null, media_player: kind === "tts" ? get("media_player") || null : null, enabled: bool("enabled"), color: kind === "light" && bool("use_color") ? [1, 3, 5].map(i => parseInt(get("color").slice(i, i + 2), 16)) : null}; if (id) item.id = id;
          } else if (type === "profile") {
            collection = "profiles";
            item = this._profileTemplate ? structuredClone(this.data.config.profiles[this._profileTemplate]) : {reactions_enabled:false, action_ids:[], motion_mode:"always"};
            item.name = get("name").trim();
          } else if (type === "floorplan") { collection = "floorplans"; item = {...(this.data.config.floorplans[id] || {}), name:get("name")}; if (id) item.id = id; } else throw new Error("Unbekanntes Formular");
          this.data = await this._call("crud", {collection, operation: "save", item, revision: this._dialogRevision});
          if (type === "profile") this.profile = Object.keys(this.data.config.profiles).find(key => this.data.config.profiles[key].name === item.name);
        }
        this.shadowRoot.getElementById("editor").close();
      }
      this._render(); this._toast("Gespeichert");
    } catch (err) {this._toast(err.message || String(err), true);}
    finally {this._requestBusy = false; if (button?.isConnected) button.disabled = false; this._updateLock();}
  }
}

if (!customElements.get("iqalarm-panel")) customElements.define("iqalarm-panel", IQAlarmPanel);
