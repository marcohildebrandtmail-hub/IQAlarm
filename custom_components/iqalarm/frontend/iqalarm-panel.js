import {DraftJournal} from "./floorplan-drafts.js?v=2.2.11";
import {alignPlanZones, buildGraphicZones, graphicViewBox, hasRoomReference, mergePolygons, orthogonalizePolygon, randomId, resolveRoom, roomGroups, roomVisualCenter} from "./floorplan-rooms.js?v=2.2.11";
/* IQAlarm 2.2.11 · native ES module · no CDN, framework or build required. */
const RULES = {perimeter: "Vorfeld-Erkennung", single: "Unbestätigter Einzelsensor", flapping: "Sensor-Prellen", perimeter_contact: "Vorfeld + Öffnung", contact_motion: "Öffnung + Bewegung", multi_contact: "Zwei Öffnungssensoren", multi_motion: "Zwei Bewegungsmelder", immediate: "Freigegebene Einzelauslösung / Gefahr"};
const PROFILE_ICONS = {"mdi:home-outline":"Zuhause", "mdi:weather-night":"Nacht", "mdi:home-export-outline":"Abwesend", "mdi:palm-tree":"Urlaub", "mdi:account-group-outline":"Besuch", "mdi:garage-variant":"Garage", "mdi:shield-check-outline":"Schutz", "mdi:eye-outline":"Beobachtung", "mdi:dog":"Haustiere", "mdi:briefcase-outline":"Arbeit", "mdi:bed-outline":"Schlafzimmer", "mdi:lock-outline":"Schloss", "mdi:home-floor-0":"Erdgeschoss", "mdi:home-floor-1":"Obergeschoss", "mdi:home-floor-b":"Keller", "mdi:tree-outline":"Garten"};
const ROLES = {perimeter_camera: "Außenkamera / Person", perimeter_sensor: "Vorfeld-Sensor", entry_contact: "Tür / Fenster", lock_contact: "Schloss / Riegel", vibration_glass: "Glas / Vibration", interior_motion: "Bewegung innen", interior_mmwave: "Präsenz / mmWave", panic: "Panik", smoke: "Rauch / Gefahr"};
const KINDS = {notify: "Push-Benachrichtigung", siren: "Sirene", switch: "Schalter", script: "Skript", light: "Licht", cover: "Rollos öffnen", snapshot: "Kamera-Snapshot", record: "Kamera-Aufzeichnung", tts: "Sprachausgabe"};
const TABS = [
  ["view-dashboard-outline", "Live-Status"],
  ["floor-plan", "Räume & Grundriss"],
  ["cctv", "Kameras & Sensoren"],
  ["layers-triple-outline", "Level-Konfiguration"],
  ["shield-account-outline", "Profile & System"],
  ["history", "Logbuch"],
];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const icon = (name) => `<ha-icon icon="mdi:${esc(name)}" aria-hidden="true"></ha-icon>`;
const checked = (value) => value ? " checked" : "";
const selected = (a, b) => a === b ? " selected" : "";
const options = (items, value = "", blank = "") => `${blank ? `<option value="">${esc(blank)}</option>` : ""}${Object.entries(items).map(([id, label]) => `<option value="${esc(id)}"${selected(id, value)}>${esc(label)}</option>`).join("")}`;
const date = (epoch) => new Date(epoch * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"});

const CSS = `
:host{display:block;height:100%;color:var(--primary-text-color,#182b42);background:var(--primary-background-color,#f3f6fa);font-family:var(--paper-font-body1_-_font-family,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif);--iq-accent:var(--primary-color,#087e9b);--iq-muted:var(--secondary-text-color,#64758b);--iq-border:var(--divider-color,#dce3ec);--iq-surface:var(--card-background-color,#fff);--iq-green:#16816a;--iq-amber:#b87808;--iq-red:#d34454;--iq-blue:#2986bb}
*{box-sizing:border-box}button,input,select,textarea{font:inherit}button{cursor:pointer;overflow-wrap:anywhere;max-width:100%}button:disabled{cursor:not-allowed;opacity:.5}ha-icon{--mdc-icon-size:21px;vertical-align:middle}button ha-icon{pointer-events:none}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid var(--iq-accent);outline-offset:3px}button{border:1px solid var(--iq-border);background:var(--iq-surface);color:inherit;border-radius:10px;padding:10px 15px;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;transition:background .15s}button:hover{background:color-mix(in srgb,var(--iq-accent) 8%,var(--iq-surface))}button.primary{background:var(--iq-accent);color:var(--text-primary-color,#fff);border-color:var(--iq-accent)}button.danger{color:var(--iq-red)}button.small{padding:6px 10px;min-height:36px;font-size:13px}.icon-button{padding:8px;border:0;background:transparent;min-width:40px}.shell{height:100%;overflow:auto}.top{position:sticky;top:0;z-index:3;background:var(--iq-surface);border-bottom:1px solid var(--iq-border)}.brand-row{max-width:1440px;margin:auto;padding:18px 30px 14px;display:flex;align-items:center;gap:13px}.brandmark{width:43px;height:47px;background:linear-gradient(145deg,#13b8b0,#076c93);clip-path:polygon(50% 0,93% 16%,88% 64%,74% 84%,50% 100%,26% 84%,12% 64%,7% 16%);display:grid;place-items:center;color:white;font-size:18px;font-weight:800;letter-spacing:-1px}.brand-title{font-size:23px;font-weight:760;letter-spacing:-.7px}.eyebrow{color:var(--iq-muted);font-size:11px;font-weight:650;letter-spacing:1.4px;text-transform:uppercase}.brand-copy{display:grid;gap:2px}.connection{margin-left:auto;display:flex;align-items:center;gap:8px;color:var(--iq-muted);font-size:12px}.dot{width:8px;height:8px;background:var(--iq-green);border-radius:50%;display:inline-block}.dot.off{background:var(--iq-red)}nav{display:flex;gap:8px;max-width:1440px;margin:auto;padding:0 30px;overflow:auto}nav button{border:none;border-bottom:3px solid transparent;border-radius:0;padding:15px 13px;background:transparent;white-space:nowrap;color:var(--iq-muted);font-weight:600;font-size:13px}nav button.active{color:var(--iq-accent);border-bottom-color:var(--iq-accent)}main{max-width:1440px;padding:30px;margin:auto}.page-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px;flex-wrap:wrap}h1{font-size:25px;font-weight:720;letter-spacing:-.7px;margin:0 0 5px}h2{font-size:17px;margin:0 0 10px;letter-spacing:-.2px}h3{font-size:15px;margin:0}p{margin:6px 0 0;line-height:1.6;color:var(--iq-muted);font-size:13px}.muted{color:var(--iq-muted)}.card{background:var(--iq-surface);border:1px solid var(--iq-border);border-radius:16px;padding:23px;min-width:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}.grid.two{grid-template-columns:1.2fr 1fr}.hero{display:flex;align-items:center;gap:28px;background:linear-gradient(120deg,color-mix(in srgb,var(--iq-accent) 7%,var(--iq-surface)),var(--iq-surface));padding:29px;margin-bottom:18px}.level-ring{width:110px;height:110px;flex-shrink:0;border:7px solid color-mix(in srgb,var(--level-color) 20%,transparent);border-top-color:var(--level-color);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;color:var(--level-color)}.level-ring strong{font-size:36px;line-height:1.1}.level-ring span{font-size:10px;font-weight:700;letter-spacing:1px}.hero-copy{min-width:0;overflow-wrap:anywhere}.hero h2{font-size:29px;margin:0 0 4px}.hero .pill{margin-left:auto;align-self:flex-start}.pill{display:inline-flex;align-items:center;gap:6px;border-radius:7px;padding:5px 8px;font-size:11px;font-weight:650;background:color-mix(in srgb,var(--level-color,var(--iq-accent)) 10%,var(--iq-surface));color:var(--level-color,var(--iq-accent));white-space:nowrap}.mode-buttons{display:flex;flex-wrap:wrap;gap:9px;margin-top:20px}.mode-buttons button.active{background:color-mix(in srgb,var(--iq-accent) 12%,var(--iq-surface));border-color:var(--iq-accent);color:var(--iq-accent)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:18px 0 28px}.metric{display:flex;align-items:center;gap:13px;padding:19px}.metric>ha-icon{--mdc-icon-size:25px;color:var(--iq-accent);padding:12px;width:49px;height:49px;background:color-mix(in srgb,var(--iq-accent) 8%,var(--iq-surface));border-radius:12px}.metric strong{display:block;font-size:23px;line-height:1.1}.metric span{font-size:11px;color:var(--iq-muted)}.section-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:26px 0 14px;flex-wrap:wrap}.room-head{display:flex;align-items:center;gap:10px;margin-bottom:16px}.room-head h3{min-width:0;flex:1;overflow-wrap:anywhere}.room-head .pill{margin-left:auto}.sensor-line{display:flex;align-items:center;gap:9px;padding:9px 0;border-top:1px solid var(--iq-border);font-size:12px}.sensor-line .sensor-name{flex:1;overflow-wrap:anywhere}.sensor-line ha-icon{color:var(--iq-muted);--mdc-icon-size:18px}.sensor-state{font-size:11px;color:var(--iq-muted)}.sensor-state.on{color:var(--iq-amber)}.banner{border:1px solid color-mix(in srgb,var(--iq-amber) 40%,var(--iq-border));background:color-mix(in srgb,var(--iq-amber) 7%,var(--iq-surface));padding:18px;border-radius:13px;margin:15px 0;display:flex;gap:13px;align-items:center}.banner ha-icon{color:var(--iq-amber)}.banner>div{flex:1;min-width:0}.banner strong{font-size:13px}.banner p{font-size:12px}.event{display:grid;grid-template-columns:110px 30px minmax(0,1fr);gap:12px;border-top:1px solid var(--iq-border);padding:14px 0;font-size:12px;align-items:start}.event>div{min-width:0;overflow-wrap:anywhere}.event time{color:var(--iq-muted);font-variant-numeric:tabular-nums}.event p{font-size:11px;word-break:break-word}.event-level{display:grid;place-items:center;border-radius:6px;width:25px;height:25px;background:color-mix(in srgb,var(--level-color) 12%,var(--iq-surface));color:var(--level-color);font-weight:700}.empty{padding:34px 20px;text-align:center;border:1px dashed var(--iq-border);border-radius:13px;color:var(--iq-muted)}.empty ha-icon{--mdc-icon-size:30px;margin-bottom:12px}.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.row.between{justify-content:space-between}.row.end{justify-content:flex-end}.spacer{flex:1}.topology{display:flex;align-items:center;justify-content:center;gap:6px;margin:17px 0;font-size:11px;color:var(--iq-muted);background:var(--primary-background-color,#f3f6fa);padding:14px 4px;border-radius:10px}.topology span{text-align:center}.topology strong{display:block;color:var(--primary-text-color);font-size:18px;margin-bottom:4px}.chips{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.chips button.active{background:var(--iq-accent);color:var(--text-primary-color,#fff);border-color:var(--iq-accent)}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:var(--iq-muted);font-size:10px;text-transform:uppercase;letter-spacing:.7px;white-space:nowrap}td,th{padding:13px 9px;border-bottom:1px solid var(--iq-border)}td code{font-size:10px;color:var(--iq-muted);display:block;margin-top:4px}.search{min-width:220px;width:min(100%,390px)}.catalog{max-height:380px;overflow:auto}.catalog-row{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--iq-border);font-size:12px}.catalog-row code{font-size:10px;display:block;margin-top:4px;color:var(--iq-muted);overflow-wrap:anywhere}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.form-grid .wide{grid-column:1/-1}label.field{display:flex;flex-direction:column;gap:7px;font-size:12px;font-weight:600;min-width:0}label small{color:var(--iq-muted);font-size:11px;font-weight:400;line-height:1.5}input:not([type=checkbox]),select,textarea{border:1px solid var(--iq-border);border-radius:8px;background:var(--iq-surface);color:inherit;padding:11px 12px;min-width:0;width:100%;min-height:41px}select[multiple]{height:115px}textarea{min-height:80px;resize:vertical}input[type=checkbox]{accent-color:var(--iq-accent);width:17px;height:17px;flex-shrink:0}.check{display:flex;align-items:flex-start;gap:9px;font-size:12px;line-height:1.6;cursor:pointer}.checks{display:grid;gap:13px}.help{border-left:3px solid var(--iq-accent);padding:10px 14px;background:color-mix(in srgb,var(--iq-accent) 5%,var(--iq-surface));font-size:12px;line-height:1.6;margin:16px 0;color:var(--iq-muted)}fieldset{border:0;padding:0;margin:0;min-width:0}fieldset:disabled{opacity:.6}.save-row{display:flex;gap:12px;align-items:center;margin-top:23px}.action-card{display:flex;align-items:center;gap:14px;margin:12px 0;padding:18px;border:1px solid var(--iq-border);border-radius:12px}.action-card>ha-icon{color:var(--iq-accent)}.action-card .description{flex:1;min-width:0;overflow-wrap:anywhere}.action-card p{font-size:11px}dialog{background:var(--iq-surface);color:inherit;border:1px solid var(--iq-border);border-radius:17px;padding:0;max-width:min(740px,calc(100vw - 28px));width:740px;max-height:90vh;box-shadow:0 20px 80px #0005}dialog::backdrop{background:#101c3080;backdrop-filter:blur(3px)}.dialog-head{padding:22px 25px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--iq-border);position:sticky;top:0;background:var(--iq-surface);z-index:2}.dialog-body{padding:23px 25px}.dialog-foot{padding:17px 25px;border-top:1px solid var(--iq-border);display:flex;justify-content:flex-end;gap:10px;position:sticky;bottom:0;background:var(--iq-surface)}dialog[open]{display:flex;flex-direction:column}dialog form{overflow:auto}#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:14px 22px;background:var(--primary-text-color,#182b42);color:var(--iq-surface);border-radius:10px;box-shadow:0 4px 24px #0003;z-index:20;max-width:90vw;font-size:13px}#toast.error{background:var(--iq-red);color:white}#toast:empty{display:none}.loading{padding:70px;text-align:center;color:var(--iq-muted)}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;padding:16px;background:var(--primary-background-color);border-radius:10px}.armed-note{margin-bottom:18px}.footer-note{margin-top:30px;color:var(--iq-muted);font-size:11px;text-align:center}[hidden]{display:none!important}.countdown{font-size:13px;font-weight:650;color:var(--iq-amber);margin-top:10px}
@media(max-width:1000px){.grid.two{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}nav{gap:0;padding:0 12px}nav button{padding:14px 11px}nav button ha-icon{display:none}}
@media(max-width:600px){main{padding:18px 14px}.brand-row{padding:12px 14px;gap:9px}.brand-title{font-size:21px}.connection span:not(.dot){display:none}.eyebrow{font-size:9px;letter-spacing:1px}.hero{padding:22px 18px;gap:17px;flex-wrap:wrap}.hero-copy{min-width:0;overflow-wrap:anywhere}.hero h2{font-size:23px}.level-ring{width:80px;height:80px;border-width:5px}.level-ring strong{font-size:28px}.hero .pill{display:none}.hero-copy{flex:1;min-width:150px}.mode-buttons{width:100%;gap:7px}.mode-buttons button{flex:1;min-width:90px;padding:9px;font-size:12px}.card{padding:18px}.metrics{gap:10px}.metric{padding:14px 11px;gap:8px}.metric>ha-icon{display:none}.metric strong{font-size:21px}.form-grid{grid-template-columns:1fr}.event{grid-template-columns:76px 24px minmax(0,1fr);gap:8px}.event>div{min-width:0;overflow-wrap:anywhere}.event time{font-size:10px}.banner{flex-wrap:wrap}.banner button{margin-left:33px}.dialog-body{padding:18px}.dialog-head,.dialog-foot{padding:16px 18px}h1{font-size:22px}.page-head>button{width:100%}}
.level-display{display:flex;flex-direction:column;align-items:center;gap:10px;max-width:170px;text-align:center}.level-caption{font-weight:700;font-size:13px;color:var(--level-color);overflow-wrap:anywhere}.plan-wrap{position:relative;width:100%;background:var(--primary-background-color,#f3f6fa);border-radius:14px;overflow:hidden;margin-top:16px}.plan-wrap.graphic-mode{background:radial-gradient(circle at 50% 30%,#132846 0%,#08111f 100%);border:1px solid #1e3a5f;box-shadow:inset 0 0 42px #0009}.plan-wrap.template-mode{background:#0b1526;border:1px solid #1e3a5f}.plan-wrap.template-mode image{opacity:.38;filter:grayscale(.35) contrast(1.08)}.plan-wrap svg{display:block;width:100%;height:100%}.plan-wrap polygon{cursor:pointer;stroke-width:2}.plan-wrap .draft{pointer-events:none;fill:#2986bb40;stroke:#38bdf8;stroke-dasharray:6 4}.plan-wrap text{pointer-events:none;paint-order:stroke;stroke:var(--iq-surface);stroke-width:3px;stroke-linejoin:round;fill:var(--primary-text-color,#122);font-weight:650}.plan-wrap g[data-room]{cursor:pointer}.plan-wrap g[data-room]:focus-visible{outline:none}.plan-wrap g[data-room]:focus-visible .room-badge{stroke:#38bdf8;stroke-width:2.6}.plan-wrap g[data-room] text{stroke:#07101d;stroke-width:3.5px;fill:#f8fafc;font-weight:720;letter-spacing:.2px}.plan-wrap g[data-room] .room-sub{fill:#cbd5e1;font-weight:600}.plan-wrap .room-corner,.plan-wrap .room-glow,.plan-wrap .room-inner,.plan-wrap .room-link{pointer-events:none}.plan-wrap .room-label-group{cursor:grab;touch-action:none;pointer-events:all;user-select:none}.plan-wrap .room-label-group:hover .room-badge{stroke:#38bdf8;stroke-width:2.4;filter:drop-shadow(0 0 8px #38bdf8aa)}.plan-wrap .room-label-group.dragging{cursor:grabbing;opacity:.88}.plan-wrap .room-label-group:focus-visible{outline:none}.plan-wrap .room-label-group:focus-visible .room-badge{stroke:#38bdf8;stroke-width:2.6}.plan-wrap .room-label-group *{pointer-events:none}.stage-row{padding:16px 0;border-bottom:1px solid var(--iq-border)}.stage-row .form-grid{grid-template-columns:80px minmax(0,1fr)}.rule-box{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border:1px solid var(--iq-border);border-radius:10px;background:var(--primary-background-color,#f3f6fa)}
.icon-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:7px;margin-top:12px}.icon-options button{font-size:11px;justify-content:flex-start}.icon-options button.active{border-color:var(--iq-accent);background:color-mix(in srgb,var(--iq-accent) 12%,var(--iq-surface))}.plan-steps{display:flex;gap:20px;flex-wrap:wrap;padding:0;margin:20px 0;list-style:none;counter-reset:step}.plan-steps li{font-size:12px;color:var(--iq-muted);display:flex;align-items:center;gap:8px}.plan-steps li::before{counter-increment:step;content:counter(step);border:1px solid var(--iq-accent);border-radius:50%;width:24px;height:24px;display:grid;place-items:center;color:var(--iq-accent);flex-shrink:0}.plan-assistant{padding:16px;border:1px solid var(--iq-border);border-radius:12px;background:var(--primary-background-color,#f3f6fa)}.assistant-step{margin-top:14px;padding:15px 16px;border:2px solid var(--iq-accent);border-radius:12px;background:color-mix(in srgb,var(--iq-accent) 7%,var(--iq-surface))}.assistant-step.saved{border-color:var(--iq-green);background:color-mix(in srgb,var(--iq-green) 8%,var(--iq-surface))}.plan-wrap .plan-proposal{fill:#33a7c028;stroke:#38bdf8;stroke-dasharray:7 5;vector-effect:non-scaling-stroke}.plan-wrap .plan-proposal.chosen{fill:#33a7c055;stroke-width:3}.draft-points circle{fill:var(--iq-surface);stroke:#087e9b;stroke-width:2;cursor:grab;touch-action:none;vector-effect:non-scaling-stroke}.draft-points circle:focus{fill:#50c6d1;outline:none;stroke-width:4}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
`;

class IQAlarmPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.tab = 0; this.profile = "armed_night"; this.stage = "1"; this.catalogFilter = "all"; this.catalog = {entities: [], notify_services: [], areas: []};
    this.plan = null; this.points = []; this.planAnalysis = null; this.selectedCandidate = ""; this.analysisGap = null; this.manualDrawing = false; this.graphicPreview = false; this.imageURLs = new Map(); this.imageLoading = new Set(); this.data = null; this._connected = false; this._subscribing = false; this._requestBusy = false; this._unsubscribe = null; this._reconnectTimer = null;
    this._saveDraftOnLeave = () => this._storeDraft();
    this._onWindowKey = e => this._windowKey(e);
    this._onDisconnect = () => this._connection(false);
    this._onReady = () => { if (!this._unsubscribe) this._connect(); };
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="shell"><header class="top"><div class="brand-row"><button class="icon-button" data-command="menu" aria-label="Seitenmenü öffnen">${icon("menu")}</button><div class="brandmark">IQ</div><div class="brand-copy"><div class="brand-title">IQAlarm</div><div class="eyebrow">Intelligenz vor dem Alarm</div></div><div class="connection" role="status"><span class="dot off"></span><span id="connection-text">Verbinde …</span></div></div><nav aria-label="IQAlarm Bereiche" role="tablist"></nav></header><main id="main"><div class="loading">IQAlarm wird verbunden …</div></main><div class="footer-note">IQAlarm · Lokal. Räumlich. Korrelierend.</div></div><dialog id="editor" aria-labelledby="dialog-title"></dialog><div id="toast" role="status" aria-live="polite"></div>`;
    this.shadowRoot.addEventListener("click", e => this._click(e));
    this.shadowRoot.addEventListener("click", e => this._planClick(e));
    this.shadowRoot.addEventListener("keydown", e => { const zone=e.target.closest("[data-room]"); if (zone && ["Enter"," "].includes(e.key)) {e.preventDefault(); this._liveDialog(zone.dataset.room);} });
    this.shadowRoot.addEventListener("pointerdown", e => this._vertexDown(e));
    this.shadowRoot.addEventListener("pointermove", e => this._vertexMove(e));
    this.shadowRoot.addEventListener("pointerup", e => this._vertexEnd(e));
    this.shadowRoot.addEventListener("pointercancel", e => this._vertexEnd(e));
    this.shadowRoot.addEventListener("keydown", e => this._vertexKey(e));
    this.shadowRoot.addEventListener("submit", e => this._submit(e));
    this.shadowRoot.addEventListener("input", e => { if (e.target.id === "sensor-search") this._renderCatalog(e.target.value); if (e.target.name === "profile_icon") this._updateIconPreview(e.target.form); });
    this.shadowRoot.addEventListener("change", e => {
      if (e.target.name === "kind") this._actionVisibility(e.target.value);
      if (e.target.id === "plan-select") { this._selectPlan(e.target.value); this._render(); }
      if (e.target.id === "zone-room") this._assignDraftRoom(e.target.value);
      if (e.target.id === "plan-candidate") { if (e.target.value) this._chooseCandidate(e.target.value); else this._deselectZone(); }
      if (e.target.id === "plan-merge" && e.target.value) this._mergeCandidate(e.target.value);
      if (e.target.id === "analysis-gap") this.analysisGap = e.target.value === "auto" ? null : Number(e.target.value);
      if (e.target.id === "plan-upload") this._uploadPlan(e.target.files[0], e.target.dataset.plan);
      if (e.target.hasAttribute("data-scope")) this._scopeVisibility(e.target.form);
    });
    this.shadowRoot.querySelector("nav").addEventListener("keydown", e => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      const total = TABS.length;
      e.preventDefault(); this.tab = e.key === "Home" ? 0 : e.key === "End" ? total - 1 : (this.tab + (e.key === "ArrowRight" ? 1 : total - 1)) % total;
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
  connectedCallback() { window.addEventListener("pagehide", this._saveDraftOnLeave); window.addEventListener("keydown", this._onWindowKey); this._listenConnection(); if (this._hass) this._connect(); }
  disconnectedCallback() { this._storeDraft(); clearTimeout(this._draftPersistTimer); window.removeEventListener("pagehide", this._saveDraftOnLeave); window.removeEventListener("keydown", this._onWindowKey); this._unlistenConnection(); this._connected = false; this._connectAttempt = (this._connectAttempt || 0) + 1; this._unsubscribe?.(); this._unsubscribe = null; clearTimeout(this._reconnectTimer); clearTimeout(this._toastTimer); for (const item of this.imageURLs.values()) URL.revokeObjectURL(item.url); this.imageURLs.clear(); }

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
        if (first || this.tab === 0 || this.tab === 5) this._render();
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
  _floorplanRoomsOptions(value = "") {
    return `<option value="">Raum auswählen</option>` + roomGroups(this.data.config.rooms, this.catalog.areas).map(group => `<optgroup label="${esc(group.name)}">${group.items.map(room => `<option value="${esc(room.id)}"${selected(room.id,value)}>${esc(room.name)}</option>`).join("")}</optgroup>`).join("");
  }
  _entities(domain) { return this.catalog.entities.filter(e => domain.includes(e.entity_id.split(".")[0])); }
  _entityOptions(domains, value = "", blank = "Keine") { return options(Object.fromEntries(this._entities(domains).map(e => [e.entity_id, `${e.name} · ${e.entity_id}`])), value, blank); }
  _empty(title, detail, symbol = "shield-search") { return `<div class="empty">${icon(symbol)}<h3>${esc(title)}</h3><p>${esc(detail)}</p></div>`; }
  _head(title, subtitle = "", button = "") { return `<div class="page-head"><div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${button}</div>`; }
  _checkbox(name, label, value) { return `<label class="check"><input type="checkbox" name="${esc(name)}"${checked(value)}><span>${label}</span></label>`; }
  _number(name, label, value, min, max, hint = "") { return `<label class="field">${label}<input type="number" name="${name}" value="${esc(value)}" min="${min}" max="${max}" required>${hint ? `<small>${hint}</small>` : ""}</label>`; }

  _render() {
    this.shadowRoot.querySelector("nav").innerHTML = TABS.map(([symbol, title], i) => `<button role="tab" id="tab-${i}" aria-selected="${i === this.tab}" aria-controls="main" tabindex="${i === this.tab ? 0 : -1}" data-tab="${i}" class="${i === this.tab ? "active" : ""}">${icon(symbol)}${title}</button>`).join("");
    if (!this.data) return;
    if (!Object.hasOwn(this.data.config.profiles, this.profile)) this.profile = Object.keys(this.data.config.profiles)[0];
    if (this.stage !== "diagnostic" && !this.data.config.stages.some(s => s.id === this.stage)) this.stage = this.data.config.stages[1]?.id || this.data.config.stages[0].id;
    this._viewRevision = this.data.config.revision;
    this.shadowRoot.getElementById("main").innerHTML = [() => this._dashboard(), () => this._rooms(), () => this._sensors(), () => this._levels(), () => this._rules(), () => this._logbook()][this.tab]();
    this.shadowRoot.getElementById("main").setAttribute("role", "tabpanel");
    this.shadowRoot.getElementById("main").setAttribute("aria-labelledby", `tab-${this.tab}`);
    this._updateLock();
    if (this.tab === 4) this._scopeVisibility(this.shadowRoot.getElementById("rules-form"));
    if (this.tab === 2) this._renderCatalog(this.shadowRoot.getElementById("sensor-search")?.value || "");
    const live = this.shadowRoot.getElementById("live-room-status");
    if (live && this.liveRoom && this.data.config.rooms[this.liveRoom]) live.innerHTML = this._roomLive(this.data.config.rooms[this.liveRoom]);
  }

  _updateLock() {
    const armed = this.data.status.active;
    this.shadowRoot.querySelectorAll("[data-config]").forEach(e => {e.disabled = armed || this._requestBusy || !this._connected || (e.dataset.command === "floorplan-analyze" && this._analysisBusy) || (e.dataset.command === "draft-undo" && !this._draftJournal?.history.length) || (e.dataset.command === "draft-redo" && !this._draftJournal?.future.length);});
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
    const profileButtons = `<button data-command="mode" data-mode="inactive" class="${!s.profile_id ? "active" : ""}">${icon("power")}Aus</button>` + Object.entries(c.profiles).map(([id, p]) => `<button data-command="profile-arm" data-id="${esc(id)}" class="${s.profile_id === id ? "active" : ""}">${this._profileSymbol(p)}${esc(p.name)}</button>`).join("");
    return this._head("Dein Haus im Überblick") + quarantine +
      `<section class="card hero" style="--level-color:${this._color(s.level)}"><div class="level-display"><div class="level-caption">${esc(s.stage_name)}</div><div class="level-ring" aria-label="${esc(s.stage_name)}: ${s.level}"><strong>${s.level}</strong></div></div><div class="hero-copy"><h2>${s.profile_name ? esc(s.profile_name) : "Anlage aus"}</h2><p>${s.active ? "Alarmreaktionen aktiv" : "Live-Status aktiv · keine Geräteaktionen"}</p><p>${s.monitored_sensors.length} Sensoren ausgewertet · Home Assistant: ${s.active ? "An" : "Aus"}</p>${s.pending_until ? `<div class="countdown">Eingangsverzögerung bis ${date(s.pending_until)}</div>` : s.arming_until ? `<div class="countdown">Scharf ab ${date(s.arming_until)}</div>` : ""}<div class="mode-buttons">${profileButtons}</div></div></section>` + this._floorplan(false) +
      `<div class="metrics">${[["floor-plan", rooms.length, "Räume verbunden"], ["shield-check-outline", !s.active ? sensors.length : s.monitored_sensors.length, !s.active ? "Sensoren eingerichtet" : "Sensoren im Profil"], ["window-open-variant", open, "Kontakte geöffnet"], ["connection", Object.keys(s.quarantine).length + offline, "Störungen / isoliert"]].map(([symbol, n, title]) => `<div class="card metric">${icon(symbol)}<div><strong>${n}</strong><span>${title}</span></div></div>`).join("")}</div>` +
      `<div class="section-title"><h2>Räume & Sicherheitsstatus</h2><button class="small" data-tab="1">Räume verwalten ${icon("arrow-right")}</button></div><div class="grid">${rooms.length ? rooms.map(r => this._roomLive(r)).join("") : this._empty("Hier beginnt dein Schutzkonzept", "Lege Räume an oder importiere deine Home-Assistant-Bereiche.", "floor-plan")}</div>`;
  }

  _logbook() {
    const s = this.data.status;
    return this._head("Ereignis-Logbuch", "Chronologische Historie der Alarmereignisse, Stufenschaltungen und Sensorauswertungen.") +
      `<section class="card"><div class="row between" style="margin-bottom:14px"><h2>Ereignisse <span class="muted" style="font-size:12px">· ${s.events.length}</span></h2><span class="muted" style="font-size:12px">Letzte ${s.events.length} Einträge</span></div>${s.events.length ? s.events.map(e => `<div class="event" style="--level-color:${this._color(e.level)}"><time>${date(e.timestamp)}</time><span class="event-level">${e.level}</span><div><strong>${esc(e.reason)}</strong>${e.chain?.length ? `<p>${e.chain.map(x => `${esc(x.name)} [${date(x.timestamp)}]`).join(" → ")}</p>` : ""}<p>${esc(e.profile_name || e.mode)} · ${esc(e.kind)}</p></div></div>`).join("") : this._empty("Alles ruhig", "Sicherheitsereignisse und Korrelationsentscheidungen erscheinen hier.", "history")}</section>`;
  }

  _roomLive(room) {
    const state = this.data.status.rooms[room.id] || {level: 0}, sensors = Object.values(this.data.config.sensors).filter(s => s.room_id === room.id || s.front_of.includes(room.id));
    return `<article class="card" style="--level-color:${this._color(state.level)}"><div class="room-head">${icon("floor-plan")}<h3>${esc(room.name)}</h3><span class="pill">${esc(this.data.config.stages[state.level]?.name || "Sicher")}</span></div>${sensors.length ? sensors.map(s => { const raw = this.data.status.raw[s.entity_id], isolated = this.data.status.quarantine[s.entity_id]; return `<div class="sensor-line">${icon(s.role.startsWith("perimeter") ? "cctv" : s.role.startsWith("interior") ? "motion-sensor" : "window-closed-variant")}<span class="sensor-name">${esc(s.name || s.entity_id)}</span><span class="sensor-state ${raw === true ? "on" : ""}">${!s.enabled ? "Deaktiviert" : isolated ? "Isoliert" : raw == null ? "Nicht verfügbar" : raw ? "Aktiv" : "Ruhig"}${!this.data.status.monitored_sensors.includes(s.entity_id) ? " · nur Anzeige" : ""}</span></div>`; }).join("") : `<p>Noch keine Sensoren zugeordnet.</p>`}</article>`;
  }

  _lockNote() { return `<div class="help armed-note" hidden>Zum Ändern der Konfiguration zuerst entschärfen. Quarantäne und Aktionstests bleiben bedienbar.</div>`; }
  _rooms() {
    return this._head("Räume & Grundriss", "Verbinde Vorfeld, Außenhaut und Innenraum zu einem räumlichen Schutzkonzept.", `<div class="row"><button data-command="import" data-config>${icon("import")}HA-Bereiche importieren</button><button class="primary" data-command="room-new" data-config>${icon("plus")}Raum anlegen</button></div>`) + this._lockNote() +
      `<div class="grid">${Object.values(this.data.config.rooms).map(r => {
        const sensors = Object.values(this.data.config.sensors), count = prefix => sensors.filter(s => (s.room_id === r.id || s.front_of.includes(r.id)) && prefix.some(p => s.role.startsWith(p))).length;
        return `<article class="card"><div class="row between"><h2>${esc(r.name)}</h2><div><button class="icon-button" aria-label="${esc(r.name)} bearbeiten" data-command="room-edit" data-id="${r.id}" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" aria-label="${esc(r.name)} löschen" data-command="room-delete" data-id="${r.id}" data-config>${icon("delete-outline")}</button></div></div><div class="topology"><span><strong>${count(["perimeter"])}</strong>${icon("cctv")} Vorfeld</span>${icon("arrow-right")}<span><strong>${count(["entry", "lock", "vibration"])}</strong>Außenhaut</span>${icon("arrow-right")}<span><strong>${count(["interior"])}</strong>Innenraum</span></div><p>Überwachung nach gewähltem IQAlarm-Profil</p><p>Angrenzend: ${r.adjacent.length ? r.adjacent.map(id => esc(this.data.config.rooms[id]?.name)).join(", ") : "Keine Räume verknüpft"}</p><button class="small" style="margin-top:16px" data-tab="2">Sensoren zuweisen ${icon("arrow-right")}</button></article>`;
      }).join("") || this._empty("Deine Räume fehlen noch", "Importiere HA-Bereiche oder lege den ersten Raum an.", "floor-plan")}</div><div class="help">Eine Raumverbindung gilt in beiden Richtungen und genau einen Schritt weit. Vorfeld ohne Raumzuordnung überwacht das gesamte Haus.</div>` + this._floorplan(true);
  }

  _sensorTable(items, emptyTitle, emptyDetail, emptyIcon = "access-point") {
    if (!items.length) return this._empty(emptyTitle, emptyDetail, emptyIcon);
    return `<div class="table-scroll"><table><thead><tr><th>Sensor</th><th>Rolle / Bereich</th><th>Schutz / Details</th><th>Status</th><th>Bearbeiten</th></tr></thead><tbody>${items.map(s => {
      const area = s.role.startsWith("perimeter") ? (s.front_of.length ? `Vor: ${s.front_of.map(id => this.data.config.rooms[id]?.name || id).join(", ")}` : (this.data.config.rooms[s.room_id]?.name || "Gesamtes Umfeld (global)")) : (this.data.config.rooms[s.room_id]?.name || "Kein Raum");
      const detail = s.role.startsWith("perimeter") ? `${s.camera_entity_id ? `Kamera: ${s.camera_entity_id}` : "Direktsensor"}<code>Entprellen: ${s.debounce_ms || this.data.config.settings.debounce_by_role[s.role] || 0} ms</code>` : `${s.flap_enabled && ["entry_contact", "lock_contact", "vibration_glass"].includes(s.role) ? `${s.flap_threshold} Wechsel / ${s.flap_window} s` : "Direkt"}<code>Entprellen: ${s.debounce_ms || this.data.config.settings.debounce_by_role[s.role] || 0} ms</code>`;
      return `<tr><td><strong>${esc(s.name || s.entity_id)}</strong><code>${esc(s.entity_id)}</code></td><td>${esc(ROLES[s.role])}<code>${esc(area)}</code></td><td>${detail}</td><td>${!s.enabled ? "Deaktiviert" : this.data.status.quarantine[s.entity_id] ? "Isoliert" : this.data.status.raw[s.entity_id] == null ? "Nicht verfügbar" : this.data.status.raw[s.entity_id] ? "Aktiv" : "Ruhig"}${s.immediate ? " · Override" : ""}</td><td><button class="icon-button" aria-label="${esc(s.name || s.entity_id)} bearbeiten" data-command="sensor-edit" data-id="${esc(s.entity_id)}" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" aria-label="Sensor entfernen" data-command="sensor-delete" data-id="${esc(s.entity_id)}" data-config>${icon("delete-outline")}</button></td></tr>`;
    }).join("")}</tbody></table></div>`;
  }

  _sensors() {
    const sensors = Object.values(this.data.config.sensors);
    const perimeter = sensors.filter(s => s.role.startsWith("perimeter"));
    const contacts = sensors.filter(s => ["entry_contact", "lock_contact", "vibration_glass"].includes(s.role));
    const interior = sensors.filter(s => ["interior_motion", "interior_mmwave", "panic", "smoke"].includes(s.role));
    return this._head("Kameras & Sensoren", "Umfeldüberwachung (Kameras & Außensensoren), Tür-/Fensterkontakte und Innenraummelder klar getrennt verwalten.", `<div class="row"><button data-command="filter-perimeter" class="small">${icon("cctv")}Kameras & Außensensoren wählen</button><button data-command="refresh" class="small">${icon("refresh")}Entitäten aktualisieren</button></div>`) + this._lockNote() +
      `<section class="card" style="margin-bottom:18px"><div class="row between"><div><h2>${icon("cctv")} Kameras & Außensensoren (Umfeldüberwachung) <span class="muted">· ${perimeter.length}</span></h2><p>Kameras mit Personen-/Objekterkennung und Bewegungsmelder im Außenbereich für die Vorfeld-Überwachung.</p></div></div><div style="margin-top:14px">${this._sensorTable(perimeter, "Noch keine Kameras oder Außensensoren", "Wähle unten im Katalog eine Kamera, Personenerkennung oder einen Außen-Bewegungsmelder mit „Als Kamera / Außen“ aus.", "cctv")}</div></section>` +
      `<section class="card" style="margin-bottom:18px"><h2>${icon("window-closed-variant")} Türen, Fenster & Schlösser (Außenhaut) <span class="muted">· ${contacts.length}</span></h2><div style="margin-top:14px">${this._sensorTable(contacts, "Noch keine Tür-/Fensterkontakte", "Weise unten Öffnungs-, Riegel- oder Glasbruchsensoren einem Raum zu.", "window-closed-variant")}</div></section>` +
      `<section class="card" style="margin-bottom:18px"><h2>${icon("motion-sensor")} Innenraum- & Gefahrenmelder <span class="muted">· ${interior.length}</span></h2><div style="margin-top:14px">${this._sensorTable(interior, "Noch keine Innenraummelder", "Weise unten Bewegungsmelder, Präsenzmelder oder Rauch-/Panikmelder zu.", "motion-sensor")}</div></section>` +
      `<div class="section-title"><div><h2>Verfügbare Home-Assistant-Entitäten</h2><div class="chips" style="margin-top:10px">${[["all", "Alle"], ["perimeter", "Kameras & Außen"], ["contact", "Türen & Fenster"], ["interior", "Innenraum"]].map(([id, label]) => `<button type="button" class="small ${this.catalogFilter === id ? "active" : ""}" data-catalog-filter="${id}">${label}</button>`).join("")}</div></div><input class="search" id="sensor-search" type="search" aria-label="Sensoren suchen" placeholder="Kamera, Bewegung oder Entitäts-ID suchen …"></div><section class="card catalog" id="catalog"></section><div class="help">Kamera-Streaming ist keine Personenerkennung. Verwende bevorzugt den Personen-Binary-Sensor deiner Kamera (z. B. Reolink / Frigate / UniFi Person) oder einen Außen-Bewegungsmelder. Direkte camera-/image_processing-Entitäten brauchen ein explizites Erkennungsattribut.</div>`;
  }

  _renderCatalog(query) {
    const target = this.shadowRoot.getElementById("catalog"); if (!target) return;
    const needle = query.toLocaleLowerCase("de");
    const entities = this._entities(["binary_sensor", "lock", "camera", "image_processing"]).filter(e => {
      if (this.data.config.sensors[e.entity_id]) return false;
      const text = `${e.name} ${e.entity_id}`.toLocaleLowerCase("de");
      if (!text.includes(needle)) return false;
      if (this.catalogFilter === "perimeter") return e.entity_id.startsWith("camera.") || e.entity_id.startsWith("image_processing.") || /person|outdoor|außen|aussen|garten|terrasse|einfahrt|kamera|vorfeld|hof|carport|motion|bewegung/.test(text);
      if (this.catalogFilter === "contact") return e.entity_id.startsWith("lock.") || /window|fenster|door|tür|tuer|kontakt|contact|riegel|maco|vibration|glas/.test(text);
      if (this.catalogFilter === "interior") return /motion|bewegung|presence|präsenz|mmwave|pir|rauch|smoke|panic|panik/.test(text);
      return true;
    });
    target.innerHTML = entities.slice(0, 150).map(e => `<div class="catalog-row"><div><strong>${esc(e.name)}</strong><code>${esc(e.entity_id)} · ${esc(e.state)}</code></div><div class="row"><button class="small" data-command="sensor-new-perimeter" data-id="${esc(e.entity_id)}" data-config>${icon("cctv")}Als Kamera / Außen</button><button class="small primary" data-command="sensor-new" data-id="${esc(e.entity_id)}" data-config>${icon("plus")}Zuweisen</button></div></div>`).join("") || this._empty("Keine passenden Entitäten", "Filter oder Suche anpassen oder Entitäten aktualisieren.", "magnify");
    if (entities.length > 150) target.innerHTML += `<p>150 von ${entities.length} Treffern. Suche eingrenzen.</p>`;
    this._updateLock();
  }

  _levels() {
    const c = this.data.config, isDiag = this.stage === "diagnostic";
    const stageIndex = c.stages.findIndex(s => s.id === this.stage);
    const currentStage = c.stages[stageIndex] || c.stages[0];
    const p = c.profiles[this.profile] || Object.values(c.profiles)[0];
    const actions = Object.values(c.actions).filter(a => a.level === this.stage);
    const levelChips = [
      ...c.stages.map((stage, idx) => `<button data-stage="${esc(stage.id)}" class="${this.stage === stage.id ? "active" : ""}"><span class="dot" style="background:${esc(stage.color)}"></span>LVL ${idx} · ${esc(stage.name)}</button>`),
      `<button data-stage="diagnostic" class="${isDiag ? "active" : ""}">${icon("connection")}Diagnose · Sensor-Prellen</button>`,
    ].join("");
    const stageConfigCard = isDiag ? "" : `<form id="stage-single-form" class="card" style="margin-bottom:18px"><fieldset data-config><div class="row between"><h2>LVL ${stageIndex} · ${esc(currentStage.name)}</h2><span class="pill" style="--level-color:${esc(currentStage.color)}">Level ${stageIndex}</span></div><div class="form-grid" style="margin-top:16px"><label class="field">Farbe<input name="stage_color" type="color" value="${esc(currentStage.color)}"></label><label class="field">Bezeichnung<input name="stage_name" required maxlength="100" value="${esc(currentStage.name)}"></label></div>${stageIndex > 0 ? `<div class="row" style="margin-top:14px">${this._checkbox("stage_confirmed", "Bestätigung erforderlich", currentStage.requires_confirmation)}${this._checkbox("stage_loud", "Akustische / freie Aktionen erlauben", currentStage.allow_loud)}${this._checkbox("stage_latch", "Bis zum Ausschalten halten", currentStage.latch)}</div><h3 style="margin-top:22px">Auslöser für LVL ${stageIndex} (alle Profile)</h3><p>Wähle aus, welche Ereignisse auf dieses Level schalten sollen:</p><div class="form-grid" style="margin-top:12px">${Object.entries(RULES).filter(([key]) => !["perimeter", "single", "flapping"].includes(key) || !currentStage.requires_confirmation).map(([key, label]) => {
      const targetId = p?.stage_targets?.[key], targetIdx = c.stages.findIndex(s => s.id === targetId), targetStage = c.stages[targetIdx];
      return `<div class="rule-box">${this._checkbox(`rule_${key}`, esc(label), targetId === currentStage.id)}<span class="muted" style="font-size:11px">Aktuell: LVL ${targetIdx >= 0 ? targetIdx : "?"} (${esc(targetStage?.name || targetId)})</span></div>`;
    }).join("")}</div>` : `<p style="margin-top:12px">Normalzustand (Sicher): immer lautlos, ohne Bestätigung und Halten. Beim Rückfall auf LVL 0 werden eingeschaltete Alarmausgänge automatisch abgeschaltet.</p>`}<div class="save-row"><button class="primary" type="submit">${icon("content-save-outline")}Level speichern</button></div></fieldset></form>`;
    const actionsCard = !isDiag && stageIndex === 0 ? "" : `<section class="card"><div><div class="row between"><h2>Aktionen & Push · ${isDiag ? "Diagnose (Sensor-Prellen)" : `LVL ${stageIndex} · ${esc(currentStage.name)}`}</h2><button class="primary" data-command="action-new" data-config>${icon("plus")}Aktion hinzufügen</button></div><p>${!isDiag && currentStage.allow_loud ? "Bestätigte Ereignisse dürfen Sirenen, kritische Pushs und Fluchtweg-Aktionen ausführen." : "Lautlose Reaktionen: Push, Licht, Rollos und Kamera. Akustische und freie Aktionen benötigen eine bestätigte, ausdrücklich freigegebene Stufe."}</p></div>${actions.length ? actions.map(a => `<div class="action-card">${icon(a.kind === "notify" ? "bell-outline" : a.kind === "light" ? "lightbulb-outline" : a.kind === "siren" ? "alarm-light-outline" : "play-box-outline")}<div class="description"><h3>${esc(KINDS[a.kind])}${a.enabled ? "" : " · deaktiviert"}</h3><p>${esc(a.target)}${a.critical ? " · Kritischer Alarm" : ""} · ${a.duration} s</p>${a.kind === "notify" ? `<p>${esc(a.message)}</p>` : ""}</div><button class="icon-button" data-command="action-edit" data-id="${esc(a.id)}" aria-label="Aktion bearbeiten" data-config>${icon("pencil-outline")}</button><button class="icon-button danger" data-command="action-delete" data-id="${esc(a.id)}" aria-label="Aktion löschen" data-config>${icon("delete-outline")}</button></div>`).join("") : `<div style="margin-top:20px">${this._empty("Noch keine Aktionen in dieser Stufe", "Füge eine Push-Benachrichtigung oder eine passende Geräteaktion hinzu.", "bell-plus-outline")}</div>`}</section><section class="card" style="margin-top:18px"><h2>Abläufe prüfen</h2><p>Ein Trockenlauf zeigt den Aktionsplan und verändert keine Alarmstufe. Ein realer Test führt die konfigurierten Geräteaktionen aus.</p><label class="field" style="margin-top:16px">Aktionen dieses Profils testen<select id="test-profile">${options(Object.fromEntries(Object.entries(c.profiles).map(([id, prof]) => [id, prof.name])), this.profile, "Alle Aktionen / aktuelles Profil")}</select></label><div class="row" style="margin-top:18px"><button data-command="test" class="primary">${icon("test-tube")}Stufe ${esc(this.stage)} trocken testen</button><label class="check"><input type="checkbox" id="real-test"><span>Aktionen tatsächlich ausführen${!isDiag && currentStage.allow_loud ? " (inklusive Sirenen!)" : ""}</span></label></div><div id="test-plan" aria-live="polite"></div></section><div class="help">Nachrichtenvariablen: <code>{{room}}</code>, <code>{{sensor}}</code>, <code>{{level}}</code>, <code>{{reason}}</code>, <code>{{chain}}</code>, <code>{{mode}}</code>, <code>{{profile}}</code>. Kritische Pushs erfordern die Freigabe in der Companion-App und im Betriebssystem.</div>`;
    return this._head("Level-Konfiguration", "Jedes Level (LVL 0, LVL 1, LVL 2 …) an einem Ort konfigurieren: Bezeichnung, Auslöser und Aktionen.", `<div class="row"><button type="button" data-command="stage-add" class="primary" data-config>${icon("plus")}Stufe hinzufügen</button></div>`) + this._lockNote() +
      `<div class="chips" style="margin-bottom:22px">${levelChips}</div>` + stageConfigCard + actionsCard + this._stagesEditor();
  }

  _rules() {
    const c = this.data.config, keys = Object.keys(c.profiles), idx = keys.indexOf(this.profile), p = c.profiles[this.profile], s = c.settings;
    const names = collection => Object.fromEntries(Object.entries(collection).map(([id, item]) => [id, item.name || item.entity_id || `${KINDS[item.kind]} · ${item.target} · ${item.level}`]));
    return this._head("Profile & System", "Profile bestimmen die gesamte Steuerung. Namen, Reihenfolge und Regeln sind frei wählbar.", `<button class="primary" data-command="profile-new" data-config>${icon("plus")}Profil anlegen</button>`) + this._lockNote() +
      `<div class="row between" style="margin-bottom:20px"><div class="chips">${Object.entries(c.profiles).map(([id,item]) => `<button data-profile="${esc(id)}" class="${id === this.profile ? "active" : ""}">${this._profileSymbol(item)}${esc(item.name)}</button>`).join("")}</div><div class="row"><button type="button" class="small" data-command="profile-move" data-dir="-1" aria-label="Profil nach links verschieben" ${idx <= 0 ? "disabled" : ""} data-config>${icon("arrow-left")}Nach links</button><button type="button" class="small" data-command="profile-move" data-dir="1" aria-label="Profil nach rechts verschieben" ${idx < 0 || idx >= keys.length - 1 ? "disabled" : ""} data-config>Nach rechts${icon("arrow-right")}</button></div></div><div class="grid two"><form id="rules-form" class="card"><fieldset data-config><div class="row between"><h2>${esc(p.name)}</h2><div class="row"><button type="button" class="small" data-command="profile-copy">Duplizieren</button><button type="button" class="small danger" data-command="profile-delete" data-id="${esc(this.profile)}">Löschen</button></div></div><div class="form-grid" style="margin-top:20px"><label class="field wide">Profilname<input name="profile_name" value="${esc(p.name)}" required maxlength="100"></label>${this._profileIconField(p.icon)}<div class="wide checks">${this._checkbox("reactions_enabled", "Alarmreaktionen und Geräteaktionen erlauben", p.reactions_enabled)}${this._checkbox("perimeter_enabled", "Vorfeld auswerten", p.perimeter_enabled)}${this._checkbox("contacts_enabled", "Öffnungs- und Schlosssensoren auswerten", p.contacts_enabled)}${this._checkbox("simulation_enabled", "Anwesenheitssimulation in diesem Profil erlauben", p.simulation_enabled)}</div><label class="field">Bewegung auswerten<select name="motion_mode">${options({always:"Immer",after_contact:"Erst nach einem Öffnungssignal",ignore:"Nur live anzeigen"},p.motion_mode)}</select></label><label class="field">Freigabe nach Öffnung<select name="motion_scope">${options({room:"Raum und freigegebene Nachbarräume",house:"Gesamtes Haus"},p.motion_scope)}</select></label>${this._profileScope("room_ids", "Räume", p.room_ids, names(c.rooms))}${this._profileScope("sensor_ids", "Sensoren", p.sensor_ids, names(c.sensors))}${this._profileScope("action_ids", "Aktionen", p.action_ids, names(c.actions))}${this._number("perimeter_seconds","Vorfeld-Gedächtnis (Sekunden)",p.perimeter_seconds,1,3600)}${this._number("correlation_seconds","Korrelationsfenster (Sekunden)",p.correlation_seconds,1,3600)}${this._number("entry_seconds","Eingangsverzögerung (Sekunden)",p.entry_seconds,0,600)}${this._number("exit_seconds","Ausgangsverzögerung (Sekunden)",p.exit_seconds,0,600)}</div><div class="checks" style="margin-top:24px">${["perimeter_contact","contact_motion","multi_contact","multi_motion"].map(key => this._checkbox(key,RULES[key],p[key])).join("")}${this._checkbox("adjacent_rooms","Angrenzende Räume für Öffnung + Bewegung einbeziehen",p.adjacent_rooms)}</div><h3 style="margin-top:24px">Ereignis → Alarmstufe</h3><div class="form-grid" style="margin-top:16px">${Object.entries(RULES).map(([key,name]) => `<label class="field">${esc(name)}<select name="target_${key}">${options(Object.fromEntries(c.stages.filter(stage => !["perimeter","single","flapping"].includes(key) || !stage.requires_confirmation).map(stage => [stage.id,`${c.stages.indexOf(stage)} · ${stage.name}`])),p.stage_targets[key])}</select></label>`).join("")}</div><div class="save-row"><button class="primary" type="submit">Profil speichern</button></div></fieldset></form>` +
      `<form id="settings-form" class="card"><fieldset data-config><h2>System & Anwesenheitssimulation</h2><div class="checks" style="margin:20px 0">${this._checkbox("live_evaluation", "Live-Status-Auswertung auch im ausgeschalteten Zustand mitlaufen lassen", s.observation_profile_id != null)}${this._checkbox("diagnose_disarmed", "Prell-Diagnose auch im unscharfen Zustand", s.diagnose_disarmed)}${this._checkbox("block_open_on_arm", "Scharfschalten bei geöffneten Kontakten verhindern", s.block_open_on_arm)}${this._checkbox("block_unavailable_on_arm", "Scharfschalten bei nicht verfügbaren Sensoren verhindern", s.block_unavailable_on_arm)}${this._checkbox("auto_camera_snapshot", "Bei Vorfeld automatisch verknüpfte Kamera fotografieren", s.auto_camera_snapshot)}${this._checkbox("auto_camera_record", "Bei Vorfeld zusätzlich 30 Sekunden Kamera aufnehmen", s.auto_camera_record)}${this._checkbox("simulation_enabled", "Anwesenheitssimulation global freigeben (zusätzlich pro Profil)", s.simulation_enabled)}</div><div class="form-grid">${this._number("simulation_start", "Lichtsimulation ab (Stunde)", s.simulation_start, 0, 23)}${this._number("simulation_end", "Lichtsimulation bis (Stunde)", s.simulation_end, 1, 24)}<label class="field wide">Simulationslichter<select name="simulation_lights" multiple>${this._entities(["light"]).map(e => `<option value="${esc(e.entity_id)}"${s.simulation_lights.includes(e.entity_id) ? " selected" : ""}>${esc(e.name)}</option>`).join("")}</select><small>Mehrfachauswahl mit Strg / ⌘. Bereits eingeschaltete Lichter werden nicht übernommen.</small></label>${this._number("retention_days", "Kameradateien aufbewahren (Tage)", s.retention_days, 1, 90)}</div><details style="margin-top:20px"><summary>Standard-Entprellzeiten nach Rolle</summary><div class="form-grid" style="margin-top:14px">${Object.entries(ROLES).map(([key, name]) => this._number(`debounce_${key}`, `${name} (ms)`, s.debounce_by_role[key] || 0, 0, 60000)).join("")}</div></details><div class="help">Kameradateien bleiben im geschützten IQAlarm-Verzeichnis. Aufzeichnungen benötigen eine Kamera mit stream-Unterstützung. Die Alarmkonfiguration erfolgt vollständig hier.</div><div class="save-row"><button type="submit" class="primary">${icon("content-save-outline")}System speichern</button></div></fieldset></form></div>`;
  }

  _stagesEditor() {
    return `<form id="stages-form" class="card" style="margin-top:22px"><fieldset data-config><div class="row between"><h2>Alle Alarmstufen im Überblick · ${this.data.config.stages.length}</h2><div class="row"><button type="button" data-command="stage-remove">Letzte entfernen</button><button type="button" data-command="stage-add">Stufe hinzufügen</button></div></div><p>Namen und Anzahl frei festlegen (1–32). Die Reihenfolge bestimmt die angezeigte Zahl. Bestehende Regeln und Aktionen verweisen auf die feste Kennung. Vor dem Entfernen ihre Zuordnungen ändern.</p><div id="stage-rows">${this.data.config.stages.map((stage,index) => this._stageRow(stage,index)).join("")}</div><div class="save-row"><button class="primary" type="submit">Alarmstufen speichern</button></div></fieldset></form>`;
  }
  _stageRow(stage,index) {
    return `<div class="stage-row" data-stage-row="${esc(stage.id)}"><strong>LVL ${index}</strong><div class="form-grid" style="margin-top:12px"><label class="field">Farbe<input name="stage_color" type="color" value="${esc(stage.color)}"></label><label class="field">Bezeichnung<input name="stage_name" required maxlength="100" value="${esc(stage.name)}"></label></div><div class="row" style="margin-top:12px">${this._checkbox("stage_confirmed","Bestätigung erforderlich",stage.requires_confirmation)}${this._checkbox("stage_loud","Akustische / freie Aktionen erlauben",stage.allow_loud)}${this._checkbox("stage_latch","Bis zum Ausschalten halten",stage.latch)}</div>${index === 0 ? '<p>Normalzustand: immer lautlos, ohne Bestätigung und Halten.</p>' : ''}</div>`;
  }
  _changeStageRows(add) {
    const rows = this.shadowRoot.getElementById("stage-rows"), count = rows.children.length;
    if (add && count < 32) rows.insertAdjacentHTML("beforeend",this._stageRow({id:randomId(),name:`Stufe ${count}`,color:"#2986bb",requires_confirmation:false,allow_loud:false,latch:false},count));
    else if (!add && count > 1) rows.lastElementChild.remove();
  }
  _profileSymbol(profile) {
    const value = profile.icon || (profile.reactions_enabled ? "mdi:shield-check-outline" : "mdi:eye-outline");
    return `<ha-icon icon="${esc(value)}" aria-hidden="true"></ha-icon>`;
  }
  _profileIconField(value) {
    return `<div class="wide icon-picker"><label class="field">Profilsymbol<input name="profile_icon" aria-label="Profilsymbol" value="${esc(value || "")}" placeholder="Automatisch nach Profilname" maxlength="84" pattern="mdi:[a-z0-9][a-z0-9-]{0,79}" list="profile-icon-list"><small>Symbol auswählen oder eine eigene MDI-Kennung eingeben. Leer: passend zum Profilnamen.</small></label><datalist id="profile-icon-list">${Object.entries(PROFILE_ICONS).map(([id,label]) => `<option value="${id}">${esc(label)}</option>`).join("")}</datalist><div class="icon-options" role="group" aria-label="Profilsymbole">${Object.entries(PROFILE_ICONS).map(([id,label]) => `<button type="button" class="small ${value === id ? "active" : ""}" data-command="profile-icon" data-id="${id}" aria-label="Symbol ${esc(label)}" title="${esc(label)}" aria-pressed="${value === id}">${this._profileSymbol({icon:id})}<span>${esc(label)}</span></button>`).join("")}</div><div class="row" style="margin-top:10px"><ha-icon data-icon-preview icon="${esc(value || "mdi:shield-check-outline")}"></ha-icon><small>Vorschau des gewählten Symbols</small></div></div>`;
  }
  _updateIconPreview(form) {
    const value = form.elements.profile_icon.value.trim();
    if (value && !/^mdi:[a-z0-9][a-z0-9-]{0,79}$/.test(value)) return;
    form.querySelector("[data-icon-preview]")?.setAttribute("icon", value || "mdi:shield-check-outline");
    form.querySelectorAll('[data-command="profile-icon"]').forEach(button => { const active=button.dataset.id === value; button.classList.toggle("active",active); button.setAttribute("aria-pressed",String(active)); });
  }
  _floorplan(edit) {
    const plans = Object.values(this.data.config.floorplans);
    if (!plans.some(plan => plan.id === this.plan)) {
      let preferred; try {preferred=window.localStorage.getItem(this._lastPlanKey());} catch {preferred=null;}
      this._selectPlan(plans.find(plan => plan.id === preferred)?.id || plans[0]?.id || null);
    }
    const rawPlan = this.data.config.floorplans[this.plan];
    const plan = rawPlan || (!edit && Object.keys(this.data.config.rooms).length ? {id: "virtual", name: "Raum-Grafik", width: 1000, height: 560, image: null, zones: {}} : null);
    if (!plan) return edit ? `<section class="card floorplan-intro" style="margin:20px 0"><h2>Dein Haus als Live-Grundriss</h2><p>Lade deinen bestehenden Grundriss als PNG oder JPG hoch. Der Assistent schlägt Raumflächen vor. Du prüfst die Flächen und verbindest sie mit deinen Räumen und Sensoren.</p><ol class="plan-steps"><li>Bild hochladen</li><li>Flächen prüfen & Räume zuordnen</li><li>Live-Status sehen</li></ol><div class="row"><button class="primary" data-command="floorplan-upload" data-config>${icon("upload")}Grundriss hochladen</button><button data-command="floorplan-new" data-config>Grundriss anlegen</button></div></section>` : "";
    if (rawPlan) {
      if (this.planAnalysis && (this.planAnalysis.plan_id !== plan.id || this.planAnalysis.image !== plan.image)) { this.planAnalysis = null; this.selectedCandidate = ""; }
      this._activatePlanDraft(plan);
      const cached = this.imageURLs.get(plan.id);
      if (plan.image && cached?.image !== plan.image) this._loadPlan(plan);
    }
    const cached = rawPlan ? this.imageURLs.get(plan.id) : null;
    const image = cached?.image === plan.image ? cached.url : "";
    const width = plan.width || 1000, height = plan.height || 600;
    const candidates = this.planAnalysis?.candidates || [];
    const mergeTargets = this.points.length >= 3 ? candidates.filter(item => item.id !== this.selectedCandidate) : [];
    const assignedAnywhere = new Set(plans.flatMap(p => Object.keys(p.zones || {})));
    const unmappedRooms = Object.fromEntries(Object.entries(this.data.config.rooms).filter(([id]) => !assignedAnywhere.has(id)));
    const isGraphic = !edit || !!this.graphicPreview;
    const renderZones = isGraphic ? buildGraphicZones(plan.zones, unmappedRooms) : plan.zones;
    const {viewBox, scale} = isGraphic ? graphicViewBox(renderZones, width, height) : {viewBox: `0 0 ${width} ${height}`, scale: 1};
    const showSvg = isGraphic ? (Boolean(plan.image || image) || Object.keys(renderZones).length > 0) : Boolean(image);
    const hasSelection = Boolean(this.points.length || this.selectedCandidate || this.zoneRoom);
    const defs = `<defs><pattern id="iq-grid-minor" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M 24 0 L 0 0 0 24" fill="none" stroke="#38bdf8" stroke-opacity=".07" stroke-width="1" vector-effect="non-scaling-stroke"/></pattern><pattern id="iq-grid-major" width="120" height="120" patternUnits="userSpaceOnUse"><rect width="120" height="120" fill="url(#iq-grid-minor)"/><path d="M 120 0 L 0 0 0 120" fill="none" stroke="#38bdf8" stroke-opacity=".15" stroke-width="1" vector-effect="non-scaling-stroke"/></pattern><linearGradient id="iq-room-fill-ok" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#14b8a6" stop-opacity=".32"/><stop offset="100%" stop-color="#0ea5e9" stop-opacity=".16"/></linearGradient><linearGradient id="iq-room-fill-warn" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f59e0b" stop-opacity=".38"/><stop offset="100%" stop-color="#ea580c" stop-opacity=".2"/></linearGradient><linearGradient id="iq-room-fill-alert" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ef4444" stop-opacity=".42"/><stop offset="100%" stop-color="#b91c1c" stop-opacity=".24"/></linearGradient></defs>`;
    const editToolbar = edit ? `<div class="row" style="margin-top:14px">${rawPlan ? `<button class="${plan.image ? "" : "primary"}" data-command="floorplan-pick" data-config>${icon("upload")}${plan.image ? "Bild ersetzen" : "Grundriss hochladen"}</button><input type="file" id="plan-upload" data-plan="${esc(plan.id)}" accept="image/png,image/jpeg" hidden data-config>` : ""}<button data-command="floorplan-upload" data-config>${rawPlan ? "Weitere Etage hochladen" : "Grundriss hochladen"}</button><button type="button" class="${this.graphicPreview ? "primary" : ""}" data-command="toggle-graphic-preview">${icon(this.graphicPreview ? "image-edit-outline" : "vector-polygon")}${this.graphicPreview ? "Vorlagenbild einblenden" : "Fertige Raum-Grafik ansehen"}</button><button type="button" data-command="floorplan-orthogonalize" data-config title="Richtet alle Linien im 90°-Winkel aus und schließt Wandkanten sauber an">${icon("ruler-square")}90° Begradigen</button><button type="button" data-command="labels-reset" data-config title="Setzt alle manuell verschobenen Beschriftungen wieder auf die automatische Raummitte zurück">${icon("format-title")}Beschriftungen zentrieren</button><button data-command="floorplan-edit" data-id="${esc(plan.id)}" data-config>Umbenennen</button>${rawPlan ? `<button type="button" data-command="floorplan-reset" data-id="${esc(plan.id)}" data-config>${icon("refresh")}Von vorne anfangen</button><button type="button" class="danger" data-command="floorplan-delete" data-id="${esc(plan.id)}" data-config>${icon("delete-outline")}Grundriss löschen</button>` : ""}</div>` : "";
    const assistantBody = edit && image ? `<ol class="plan-steps"><li>Bild hochgeladen</li><li>Raumflächen prüfen und zuordnen</li><li>Bereich speichern</li></ol><div class="plan-assistant"><div class="row"><button class="primary" data-command="floorplan-analyze" data-config ${this._analysisBusy ? "disabled" : ""}>${icon("floor-plan")}${this._analysisBusy ? "Flächen werden gesucht …" : "Flächen erkennen"}</button>${candidates.length ? `<button type="button" data-command="candidate-next" data-config>${icon("arrow-right")}Nächste Fläche (${candidates.length} offen)</button><button type="button" data-command="candidates-clear" data-config>${icon("eye-off-outline")}Restliche Vorschläge ausblenden</button>` : ""}${hasSelection ? `<button type="button" data-command="zone-deselect" data-config>${icon("close")}Auswahl aufheben</button>` : ""}<details><summary>Erweiterte Erkennung</summary><label class="field" style="margin-top:12px">Wandlücken schließen<select id="analysis-gap" data-config>${options({auto:"Automatisch",0:"Aus",8:"Kleine Lücken",18:"Mittlere Lücken",28:"Größere Lücken",40:"Große Lücken"},this.analysisGap == null ? "auto" : String(this.analysisGap))}</select><small>Automatisch passt die Bildauswertung an den Grundriss an. Diese Einstellung misst keine Türbreite.</small></label></details></div><p>Dein hochgeladenes Bild dient nur als Zeichenvorlage. Im Live-Status (und über „Fertige Raum-Grafik ansehen“) wird daraus automatisch eine saubere Smart-Home-Raumgrafik ohne das Originalbild erzeugt.</p>${this.planAnalysis ? `<p role="status"><strong>${candidates.length ? `${candidates.length} Flächen vorgeschlagen` : "Keine geschlossenen Raumflächen gefunden"}</strong>${candidates.length ? " · Im Bild anklicken, mit Shift + Klick verbinden oder mit Entf löschen." : " · Türöffnungs-Ausgleich ändern oder Eckpunkte selbst setzen."}</p>` : ""}${candidates.length ? `<div class="row" style="margin-top:14px"><label class="field">Flächenvorschlag<select id="plan-candidate">${options(Object.fromEntries(candidates.map(item => [item.id,`Fläche ${item.id} · ${Math.round(item.area*1000)/10} % des Bildes`])),this.selectedCandidate,"Vorschlag auswählen")}</select></label>${mergeTargets.length ? `<label class="field">Mit Fläche verbinden<select id="plan-merge">${options(Object.fromEntries(mergeTargets.map(item => [item.id,`Fläche ${item.id} hinzufügen`])),"","Fläche zum Verbinden wählen")}</select></label>` : ""}${this.selectedCandidate ? `<button type="button" class="danger" data-command="candidate-delete" data-config>Vorschlag ${esc(this.selectedCandidate)} entfernen</button>` : ""}</div>` : ""}${this._assistantStepHTML(plan,candidates)}</div><div class="row" style="margin-top:14px"><label class="field">Raum / Außenbereich<select id="zone-room" data-config>${this._floorplanRoomsOptions(this.zoneRoom)}</select></label><button data-command="room-new" data-config>${icon("plus")}Raum anlegen</button>${this.zoneRoom && this.data.config.rooms[this.zoneRoom] ? `<button type="button" data-command="room-edit" data-id="${esc(this.zoneRoom)}" data-config>${icon("pencil-outline")}Raum umbenennen</button>` : ""}<button data-command="zone-deselect" data-config ${!hasSelection ? "disabled" : ""}>${icon("close")}Auswahl aufheben</button><button type="button" data-command="floorplan-orthogonalize" data-config title="Richtet alle Linien im 90°-Winkel aus und schließt Wandkanten sauber an">${icon("ruler-square")}90° Begradigen</button><button data-command="zone-clear" data-config>Neu zeichnen</button><button data-command="zone-undo" data-config>Letzter Punkt zurück</button><button data-command="draft-undo" data-config ${!this._draftJournal?.history.length ? "disabled" : ""}>Rückgängig</button><button data-command="draft-redo" data-config ${!this._draftJournal?.future.length ? "disabled" : ""}>Wiederholen</button><button class="primary" data-command="zone-save" data-config>Bereich speichern</button><button data-command="zone-delete" data-config>Bereich entfernen</button></div><p id="draft-status" role="status">${this._draftJournal?.dirty ? (this._draftJournal.available ? "Ungespeicherter Entwurf · im Browser gesichert" : "Ungespeicherter Entwurf · Browser-Sicherung nicht verfügbar") : this.zoneRoom && plan.zones[this.zoneRoom] ? "Bereich gespeichert" : "Raumauswahl ordnet die aktuelle Fläche zu und behält alle Eckpunkte."}</p><p>Vorschlag anklicken (Shift + Klick verbindet zwei Vorschläge, Entf entfernt einen Vorschlag, Esc hebt die Auswahl auf) oder Eckpunkte im Bild setzen. Eckpunkte mit Maus oder Finger verschieben; mit Pfeiltasten fein korrigieren, mit Entf löschen. <strong>Tipp:</strong> Alle Raum-Beschriftungen können direkt mit der Maus oder dem Finger an jede beliebige Position verschoben werden. Erst „Bereich speichern“ übernimmt die Zuordnung.</p>` : edit ? '<p style="margin-top:14px">Wähle zuerst dein Grundrissbild über den Hochladen-Button aus.</p>' : "";
    const svgBody = showSvg ? `<div class="plan-wrap ${isGraphic ? "graphic-mode" : "template-mode"}" style="aspect-ratio:${width}/${height}"><svg id="floorplan" role="img" aria-label="${esc(plan.name)}" data-edit="${edit && !this.graphicPreview}" viewBox="${viewBox}">${defs}${isGraphic ? `<rect x="0" y="0" width="${width}" height="${height}" fill="url(#iq-grid-major)"/>` : `<image href="${esc(image)}" width="${width}" height="${height}"/>`}${this._zoneLinksSVG(plan,renderZones)}${Object.entries(renderZones).map(([room,points]) => this._zoneSVG(plan,room,points,isGraphic,scale)).join("")}${edit && !this.graphicPreview && !this.manualDrawing ? candidates.map(item => `<g data-candidate="${esc(item.id)}" role="button" tabindex="0" aria-label="Fläche ${esc(item.id)} auswählen"><polygon class="plan-proposal ${this.selectedCandidate === item.id ? "chosen" : ""}" points="${(this.selectedCandidate === item.id && this.points.length ? this.points : item.points).map(([x,y]) => `${x*width},${y*height}`).join(" ")}"/><text x="${item.center[0]*width}" y="${item.center[1]*height}" text-anchor="middle" font-size="${Math.max(width,height)*.024}">${esc(item.id)}</text></g>`).join("") : ""}<polygon class="draft" points="${edit && !this.graphicPreview ? this.points.map(([x,y]) => `${x*width},${y*height}`).join(" ") : ""}"/><g class="draft-points">${edit && !this.graphicPreview ? this._draftHandles(plan) : ""}</g><g class="room-labels-layer">${Object.entries(renderZones).map(([room,points]) => this._zoneLabelSVG(plan,room,points,isGraphic,scale)).join("")}</g></svg></div>` : (edit ? `<div class="empty" style="margin-top:16px">${plan.image ? "Bild wird geladen …" : "PNG / JPG auswählen · maximal 10 MB"}</div>` : "");
    return `<section class="card" style="margin:20px 0"><div class="row between"><div class="row"><h2>${edit ? "Grundriss-Assistent" : "Live-Grundriss"}</h2>${!edit || this.graphicPreview ? `<span class="pill">${icon("vector-polygon")}Raum-Grafik · ${Object.keys(renderZones).length} ${Object.keys(renderZones).length === 1 ? "Raum" : "Räume"}</span>` : ""}</div>${plans.length ? `<label class="field">Etage<select id="plan-select">${options(Object.fromEntries(plans.map(p => [p.id,p.name])),plan.id)}</select></label>` : ""}</div>${editToolbar}${assistantBody}${svgBody}</section>`;
  }
  _unassignedRoomChoices(plan) {
    const used = new Set(Object.keys(plan?.zones || {}));
    return roomGroups(this.data.config.rooms,this.catalog.areas).flatMap(g => g.items).filter(item => !used.has(item.id) && !/^(alles|alt|fenstergriffe|weihnachten|unterwegs|homeassistant)$/i.test(item.name.trim()));
  }
  _assistantStepHTML(plan, candidates) {
    const choices = this._unassignedRoomChoices(plan);
    if (this.points.length < 3 && (this.manualDrawing || (this.zoneRoom && !plan.zones[this.zoneRoom]))) {
      const target = this.zoneRoom ? (this.data.config.rooms[this.zoneRoom]?.name || choices.find(c => c.id === this.zoneRoom)?.name || "") : "";
      return `<div class="assistant-step"><div class="row between"><strong>${icon("vector-polygon")} Zeichenmodus${target ? ` für „${esc(target)}“` : ""}: Klicke die Ecken der Fläche ins Bild (${this.points.length}/3 Punkte)</strong><button type="button" class="small" data-command="zone-deselect" data-config>${icon("close")}Abbrechen / Auswahl aufheben</button></div><p style="margin:6px 0 0">Ab 3 Punkten kannst du ${target ? "mit „Bereich speichern“ übernehmen" : "den Raum zuordnen"}. Bestehende Räume und Vorschläge bleiben unverändert.</p></div>`;
    }
    if (this.points.length >= 3 && (!this.zoneRoom || !plan.zones[this.zoneRoom] || this._draftJournal?.dirty)) {
      const currentLabel = this.zoneRoom ? (choices.find(c => c.id === this.zoneRoom)?.name || this.data.config.rooms[this.zoneRoom]?.name || this.zoneRoom) : "";
      return `<div class="assistant-step"><div class="row between"><strong>${icon("cursor-default-click-outline")} ${this.selectedCandidate ? `Fläche ${esc(this.selectedCandidate)} ist ausgewählt` : "Aktuelle Fläche ist markiert"} — Welcher Raum ist das?</strong><div class="row">${currentLabel ? `<span class="pill">Gewählt: ${esc(currentLabel)}</span>` : `<span class="pill" style="--level-color:var(--iq-amber)">Bitte Raum wählen</span>`}<button type="button" class="small" data-command="zone-deselect" data-config>${icon("close")}Auswahl aufheben</button>${this.selectedCandidate ? `<button type="button" class="small danger" data-command="candidate-delete" data-config>${icon("delete-outline")}Keine Raumfläche (verwerfen)</button>` : ""}</div></div><p style="margin:6px 0 10px">Mit 1 Klick dem passenden Raum zuordnen und speichern (oder oben auf „Auswahl aufheben“ klicken, um frei z. B. für Terrasse / Garagenhof zu zeichnen):</p><div class="chips">${choices.slice(0,18).map(item => `<button type="button" class="small ${this.zoneRoom === item.id ? "primary" : ""}" data-command="quick-save-zone" data-id="${esc(item.id)}" data-config>${icon("check")}Als „${esc(item.name)}“ speichern</button>`).join("")}<button type="button" class="small primary" data-command="zone-save-new" data-config>${icon("plus")}Neuen Raumnamen eingeben …</button></div></div>`;
    }
    if (this.zoneRoom && plan.zones[this.zoneRoom] && !this._draftJournal?.dirty) {
      return `<div class="assistant-step saved"><div class="row between"><strong>${icon("check-circle-outline")} Raum „${esc(this.data.config.rooms[this.zoneRoom]?.name || this.zoneRoom)}“ ist ausgewählt (gespeichert)</strong><div class="row"><button type="button" class="small" data-command="zone-deselect" data-config>${icon("close")}Auswahl aufheben</button>${candidates.length ? `<button type="button" class="small primary" data-command="candidate-next" data-config>${icon("arrow-right")}Nächste Fläche (${candidates.length} offen)</button>` : ""}<button type="button" class="small" data-command="floorplan-orthogonalize" data-config title="Richtet alle Linien im 90°-Winkel aus und schließt Wandkanten sauber an">${icon("ruler-square")}90° Begradigen</button><button type="button" class="small" data-command="toggle-graphic-preview">${icon("vector-polygon")}Fertige Raum-Grafik ansehen</button></div></div></div>`;
    }
    if (candidates.length) {
      return `<div class="assistant-step"><div class="row between"><strong>${icon("hand-pointing-right")} Keine Fläche markiert — Nächste Fläche wählen oder Außenbereich anlegen</strong><div class="row"><button type="button" class="small" data-command="zone-clear" data-config>${icon("vector-polygon")}Frei im Bild zeichnen (z. B. Terrasse / Hof)</button><button type="button" class="small" data-command="room-new" data-config>${icon("plus")}Raum / Außenbereich anlegen</button><button type="button" class="small" data-command="candidates-clear" data-config>${icon("eye-off-outline")}Vorschläge ausblenden</button></div></div><div class="chips" style="margin-top:10px">${candidates.map(item => `<button type="button" class="small" data-command="candidate-pick" data-id="${esc(item.id)}" data-config>Fläche ${esc(item.id)} (${Math.round(item.area*1000)/10} %)</button>`).join("")}</div></div>`;
    }
    return `<div class="assistant-step"><div class="row between"><strong>${icon("check-circle-outline")} Keine Fläche markiert — Weitere Bereiche (z. B. Terrasse, Garagenhof) hinzufügen</strong><div class="row"><button type="button" class="small primary" data-command="zone-clear" data-config>${icon("vector-polygon")}Frei im Bild zeichnen</button><button type="button" class="small" data-command="floorplan-orthogonalize" data-config title="Richtet alle Linien im 90°-Winkel aus und schließt Wandkanten sauber an">${icon("ruler-square")}90° Begradigen</button><button type="button" class="small" data-command="room-new" data-config>${icon("plus")}Raum / Außenbereich ohne Zeichnung anlegen</button><button type="button" class="small" data-command="toggle-graphic-preview">${icon("vector-polygon")}Fertige Raum-Grafik ansehen</button></div></div></div>`;
  }

  _draftSnapshot() { return {points:structuredClone(this.points),roomId:this.zoneRoom || null,candidateId:this.selectedCandidate || "",manual:!!this.manualDrawing}; }
  _applyDraft(state) { this.points=structuredClone(state.points); this.zoneRoom=state.roomId; this.selectedCandidate=state.candidateId; this.manualDrawing=state.manual; }
  _lastPlanKey() { return `iqalarm:last-plan:${location.origin}:${this._hass?.user?.id || "local"}`; }
  _activatePlanDraft(plan) {
    try {window.localStorage.setItem(this._lastPlanKey(),plan.id);} catch {this._draftStorageUnavailable=true;}
    const key=`iqalarm:draft:v1:${location.origin}:${this._hass?.user?.id || "local"}:${plan.id}:${plan.image || "empty"}`;
    if (this._draftKey === key) return;
    this._storeDraft(); this._draftKey=key;
    let storage; try {storage=window.localStorage;} catch {storage=null;}
    this._draftJournal=new DraftJournal(key,storage);
    this._applyDraft(this._draftJournal.state);
    if (this.zoneRoom && !hasRoomReference(this.data.config.rooms,this.catalog.areas,this.zoneRoom)) this.zoneRoom=null;
    if (!this._draftJournal.dirty && this.zoneRoom) {
      this.points=structuredClone(plan.zones[this.zoneRoom] || []);
      this._draftJournal.markSaved(this._draftSnapshot());
    }
  }
  _selectPlan(id) {
    this._storeDraft(); this._draftJournal=null; this._draftKey=null;
    this.plan=id; this.points=[]; this.zoneRoom=null; this.selectedCandidate=""; this.manualDrawing=false; this.planAnalysis=null;
  }
  _storeDraft(persist = true) {
    if (!this._draftJournal) return;
    this._draftJournal.update(this._draftSnapshot(),persist);
    clearTimeout(this._draftPersistTimer);
    if (!persist) this._draftPersistTimer=setTimeout(() => this._draftJournal?.flush(),250);
    const status=this.shadowRoot.getElementById("draft-status");
    if (status) status.textContent=this._draftJournal.dirty ? (this._draftJournal.available ? "Ungespeicherter Entwurf · im Browser gesichert" : "Ungespeicherter Entwurf · Browser-Sicherung nicht verfügbar") : "Bereich gespeichert";
    if (this.data) this._updateLock();
  }
  _recordDraft() { this._draftJournal?.checkpoint(this._draftSnapshot()); }
  _undoDraft(redo = false) {
    const state=redo ? this._draftJournal?.redo() : this._draftJournal?.undo();
    if (state) {this._applyDraft(state); this._render();}
  }
  _assignDraftRoom(id) {
    this._recordDraft(); this.zoneRoom=id || null;
    // Assigning a room never replaces geometry the user has already edited.
    if ((!this.points.length || (!this._draftJournal?.dirty && !this.selectedCandidate)) && id) {
      this.points=structuredClone(this.data.config.floorplans[this.plan]?.zones[id] || []);
    } else if (!id && !this._draftJournal?.dirty && !this.selectedCandidate) {
      this.points=[];
    }
    if (id && !this.points.length && !this.data.config.floorplans[this.plan]?.zones[id]) { this.selectedCandidate=""; this.manualDrawing=true; }
    this._storeDraft(); this._render();
  }
  _deselectZone() {
    this._recordDraft();
    this.points=[]; this.selectedCandidate=""; this.zoneRoom=null; this.manualDrawing=false;
    this._storeDraft(); this._render();
  }
  async _zoneAssignmentDialog() {
    this._storeDraft();
    this.catalog=await this._call("catalog");
    this._dialog("Fläche einem Raum zuordnen",`<p>Deine ${this.points.length} Eckpunkte bleiben erhalten. Wähle einen IQAlarm-Raum oder einen vorhandenen Home-Assistant-Bereich.</p><label class="field" style="margin-top:18px">Vorhandener Raum<select name="zone_room" aria-label="Vorhandener Raum">${this._floorplanRoomsOptions(this.zoneRoom)}</select><small>Home-Assistant-Bereiche werden beim Speichern mit IQAlarm verknüpft.</small></label><label class="field" style="margin-top:18px">Oder neuen Raum anlegen<input name="zone_new_room" aria-label="Oder neuen Raum anlegen" maxlength="100" placeholder="z. B. Wohnzimmer"></label>`,"zone-assignment");
  }
  async _saveDraftZone(roomId, newName = "", revision = this._viewRevision) {
    if (this.points.length < 3) throw new Error("Mindestens drei Eckpunkte markieren");
    if (roomId?.startsWith("ha-area:")) this.catalog=await this._call("catalog");
    const config=structuredClone(this.data.config);
    const {id,room}=resolveRoom(config.rooms,this.catalog.areas,roomId,newName,randomId);
    if (room) config.rooms[id]=room;
    config.floorplans[this.plan].zones[id]=structuredClone(this.points);
    const savedCandidate = this.selectedCandidate;
    this.data=await this._call("config/save",{config,revision}); this.zoneRoom=id;
    if (savedCandidate && this.planAnalysis?.candidates) {
      this.planAnalysis.candidates = this.planAnalysis.candidates.filter(item => item.id !== savedCandidate);
      this.selectedCandidate = "";
    }
    this._draftJournal?.markSaved(this._draftSnapshot()); this._render(); this._toast("Bereich gespeichert");
  }
  async _quickSaveZone(roomId) {
    await this._saveDraftZone(roomId);
    this.points=[]; this.zoneRoom=null; this.selectedCandidate=""; this.manualDrawing=false;
    this._draftJournal?.markSaved(this._draftSnapshot()); this._render();
    this._toast("Raum gespeichert · Auswahl freigegeben");
  }
  _draftHandles(plan) {
    return this.points.map(([x,y],index) => `<circle data-draft-vertex="${index}" cx="${x*plan.width}" cy="${y*plan.height}" r="${Math.max(plan.width,plan.height)*.007}" role="button" tabindex="0" aria-label="Eckpunkt ${index+1} verschieben"/>`).join("");
  }
  _uploadDialog() {
    this._dialog("Grundriss hochladen", `<p>Dein Bild wird als Grundriss-Hintergrund übernommen. Danach schlägt der Assistent Raumflächen vor.</p><label class="field" style="margin-top:18px">Etage / Name<input name="name" maxlength="100" required value="" placeholder="z. B. Erdgeschoss"></label><label class="field" style="margin-top:18px">Grundrissbild auswählen<input type="file" name="image" required accept="image/png,image/jpeg"><small>PNG oder JPG · maximal 10 MB · bis 8192 Pixel pro Seite.</small></label>`,"floorplan-upload");
    this.shadowRoot.querySelector('#editor [type="submit"]').textContent="Hochladen";
  }
  async _analyzePlan() {
    if (this._analysisBusy) return;
    const plan = this.data.config.floorplans[this.plan]; if (!plan?.image) return;
    this._analysisBusy = true; this._render();
    try {
      const result = await this._call("floorplan/analyze",{plan_id:plan.id,gap:this.analysisGap});
      if (this.plan === plan.id && this.data.config.floorplans[plan.id]?.image === result.image) { this.planAnalysis=result; }
    } catch(err) { this._toast(err.message || "Flächenanalyse fehlgeschlagen",true); }
    finally { this._analysisBusy=false; if (this.isConnected && this.tab === 1) this._render(); }
  }
  _chooseCandidate(id, focusSvg = false) {
    const candidate=this.planAnalysis?.candidates.find(item => item.id === id);
    if (!candidate) return;
    if (this.selectedCandidate !== id || !this.points.length) {
      this._recordDraft(); this.selectedCandidate=candidate.id;
      this.points=structuredClone(candidate.points); this.manualDrawing=false;
      this.zoneRoom=null;
      this._storeDraft(); this._render();
    }
    if (focusSvg) this.shadowRoot.querySelector(`[data-candidate="${CSS.escape(id)}"]`)?.focus({preventScroll:true});
  }
  _nextCandidate() {
    const list = this.planAnalysis?.candidates || [];
    if (!list.length) return;
    const idx = list.findIndex(item => item.id === this.selectedCandidate);
    const next = list[(idx + 1) % list.length];
    this._chooseCandidate(next.id, true);
  }
  _selectSavedRoomZone(id) {
    const saved = this.data.config.floorplans[this.plan]?.zones[id];
    if (!saved) return;
    if (this.zoneRoom === id && !this.selectedCandidate && !this._draftJournal?.dirty) { this._deselectZone(); return; }
    this._recordDraft(); this.selectedCandidate=""; this.manualDrawing=false; this.zoneRoom=id;
    this.points=structuredClone(saved); this._storeDraft(); this._render();
  }
  _deleteCandidate(id = this.selectedCandidate) {
    if (!id || !this.planAnalysis?.candidates) return;
    const idx = this.planAnalysis.candidates.findIndex(item => item.id === id);
    if (idx < 0) return;
    this._recordDraft();
    this.planAnalysis.candidates.splice(idx, 1);
    if (this.selectedCandidate === id) { this.selectedCandidate = ""; this.points = []; }
    this._storeDraft(); this._render();
    this._toast(`Flächenvorschlag ${id} entfernt`);
  }
  _mergeCandidate(id) {
    const other = this.planAnalysis?.candidates.find(item => item.id === id);
    if (!other || this.points.length < 3) return;
    this._recordDraft();
    this.points = mergePolygons(this.points, other.points);
    this.planAnalysis.candidates = this.planAnalysis.candidates.filter(item => item.id !== id);
    const active = this.planAnalysis.candidates.find(item => item.id === this.selectedCandidate);
    if (active) active.points = structuredClone(this.points);
    this.manualDrawing = false;
    this._storeDraft(); this._render();
    this._toast(`Fläche ${id} mit aktueller Fläche verbunden`);
  }
  _zoneLinksSVG(plan, zones) {
    const seen = new Set(), lines = [];
    for (const [roomId, points] of Object.entries(zones)) {
      const room = this.data.config.rooms[roomId]; if (!room?.adjacent?.length) continue;
      const c1 = plan.labels?.[roomId] || roomVisualCenter(points);
      for (const adjId of room.adjacent) {
        const key = [roomId, adjId].sort().join(":");
        if (!zones[adjId] || seen.has(key)) continue;
        seen.add(key);
        const c2 = plan.labels?.[adjId] || roomVisualCenter(zones[adjId]);
        lines.push(`<line class="room-link" x1="${Math.round(c1[0]*plan.width)}" y1="${Math.round(c1[1]*plan.height)}" x2="${Math.round(c2[0]*plan.width)}" y2="${Math.round(c2[1]*plan.height)}" stroke="#38bdf8" stroke-opacity=".45" stroke-width="2" stroke-dasharray="6 5" vector-effect="non-scaling-stroke"/>`);
      }
    }
    return lines.join("");
  }
  _zoneSVG(plan,room,points,graphic = false,scale = 1) {
    const status = this.data.status.rooms[room] || {}, roomName = this.data.config.rooms[room]?.name || room;
    const tags = [status.open?.length ? "Fenster / Tür offen" : "",status.motion?.length ? "Bewegung" : "",status.persons?.length ? "Person draußen" : "",status.quarantined?.length ? "Sensor isoliert" : ""].filter(Boolean);
    const activeAlert = tags.length > 0 || (status.level || 0) > 0;
    const color = tags.length ? (status.confirmed ? "#ef4444" : "#f59e0b") : (status.level ? this._color(status.level) : "#14b8a6");
    const fillId = tags.length ? (status.confirmed ? "alert" : "warn") : "ok";
    const base = Math.max(plan.width,plan.height)*scale;
    const ptsAttr = points.map(([x,y]) => `${Math.round(x*plan.width*10)/10},${Math.round(y*plan.height*10)/10}`).join(" ");
    const corners = graphic ? points.map(([x,y]) => `<circle class="room-corner" cx="${Math.round(x*plan.width*10)/10}" cy="${Math.round(y*plan.height*10)/10}" r="${Math.max(2.2,base*.0035)}" fill="${color}" fill-opacity=".85"/>`).join("") : "";
    return `<g data-room="${esc(room)}" role="button" tabindex="0" aria-label="${esc(roomName+': '+(tags.join(', ') || 'Ruhig'))}"><polygon class="room-glow" points="${ptsAttr}" fill="${color}" fill-opacity="${activeAlert ? ".26" : ".14"}" stroke="${color}" stroke-width="${activeAlert ? 8 : 5}" stroke-opacity=".28" stroke-linejoin="round" vector-effect="non-scaling-stroke"/><polygon points="${ptsAttr}" fill="url(#iq-room-fill-${fillId})" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/><polygon class="room-inner" points="${ptsAttr}" fill="none" stroke="#e2f1ff" stroke-opacity=".32" stroke-width="1" stroke-dasharray="5 4" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>${corners}</g>`;
  }
  _zoneLabelSVG(plan,room,points,graphic = false,scale = 1) {
    const status = this.data.status.rooms[room] || {}, roomName = this.data.config.rooms[room]?.name || room;
    const tags = [status.open?.length ? "Fenster / Tür offen" : "",status.motion?.length ? "Bewegung" : "",status.persons?.length ? "Person draußen" : "",status.quarantined?.length ? "Sensor isoliert" : ""].filter(Boolean);
    const center = plan.labels?.[room] || roomVisualCenter(points);
    const cx = Math.round(center[0]*plan.width*10)/10, cy = Math.round(center[1]*plan.height*10)/10;
    const color = tags.length ? (status.confirmed ? "#ef4444" : "#f59e0b") : (status.level ? this._color(status.level) : "#14b8a6");
    const sensorCount = Object.values(this.data.config.sensors).filter(s => s.room_id === room || s.front_of?.includes(room)).length;
    const subText = tags.join(" · ") || (graphic && sensorCount ? `Ruhig · ${sensorCount} ${sensorCount === 1 ? "Sensor" : "Sensoren"}` : "Ruhig");
    const base = Math.max(plan.width,plan.height)*scale;
    const fontSize = Math.max(11,Math.min(22,base*.021));
    const subSize = Math.max(9,fontSize*.76);
    const badgeW = Math.max(fontSize*6.2,Math.max(roomName.length*fontSize*.62,subText.length*subSize*.54)+fontSize*1.9);
    const badgeH = fontSize*2.55;
    return `<g class="room-label-group" data-label-room="${esc(room)}" data-room="${esc(room)}" data-cx="${cx}" data-cy="${cy}" tabindex="0" role="button" aria-label="Beschriftung ${esc(roomName)} verschieben"><rect class="room-badge" x="${Math.round((cx-badgeW/2)*10)/10}" y="${Math.round((cy-badgeH/2)*10)/10}" width="${Math.round(badgeW)}" height="${Math.round(badgeH)}" rx="${Math.round(badgeH*.32)}" fill="#091322e0" stroke="${color}" stroke-width="1.5" vector-effect="non-scaling-stroke"/><text x="${cx}" y="${Math.round((cy-badgeH*.1)*10)/10}" text-anchor="middle" font-size="${Math.round(fontSize*10)/10}">${esc(roomName)}<tspan x="${cx}" dy="1.35em" font-size="${Math.round(subSize*10)/10}" class="room-sub">${esc(subText)}</tspan></text></g>`;
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
  async _sendPlanImage(file, planId, name, revision) {
    if (file.size > 10*1024*1024) throw new Error("Bild maximal 10 MB");
    if (!file.size) throw new Error("Die ausgewählte Datei ist leer");
    const path = planId ? `/api/iqalarm/floorplans/${encodeURIComponent(planId)}/image` : `/api/iqalarm/floorplans/upload?name=${encodeURIComponent(name)}`;
    const response = await this._hass.fetchWithAuth(path,{method:"POST",headers:{"X-IQAlarm-Revision":String(revision),"Content-Type":file.type || "application/octet-stream"},body:file});
    let data; try { data = await response.json(); } catch { throw new Error(`Upload fehlgeschlagen (${response.status}). Bitte Verbindung und Dateigröße prüfen.`); }
    if (!response.ok) throw new Error(data.message || `Upload fehlgeschlagen (${response.status})`);
    this._storeDraft(); this._draftJournal=null; this._draftKey=null; this.data=data; this.plan=data.uploaded_plan_id || planId; this.points=[]; this.zoneRoom=null; this.planAnalysis=null; this.selectedCandidate=""; this.tab=1; this._render();
    this._toast("Grundriss hochgeladen. Raumflächen werden gesucht …");
    await this._analyzePlan();
  }
  async _uploadPlan(file, planId) {
    if (!file || this._requestBusy) return;
    this._requestBusy=true; this._updateLock();
    try { await this._sendPlanImage(file,planId,"",this._viewRevision); }
    catch(err) { this._toast(err.message,true); }
    finally { this._requestBusy=false; this._updateLock(); const input=this.shadowRoot.getElementById("plan-upload"); if (input) input.value=""; }
  }
  _planPosition(event, svg) {
    const plan = this.data?.config.floorplans[this.plan];
    const ctm = svg.getScreenCTM?.();
    if (ctm && plan?.width && plan?.height) {
      const pt = svg.createSVGPoint();
      pt.x = event.clientX; pt.y = event.clientY;
      const loc = pt.matrixTransform(ctm.inverse());
      return [Math.max(0, Math.min(1, loc.x / plan.width)), Math.max(0, Math.min(1, loc.y / plan.height))];
    }
    const rect = svg.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))];
  }
  _planClick(event) {
    const svg=event.target.closest("#floorplan"); if (!svg) return;
    if (this._ignorePlanClick) { this._ignorePlanClick=false; return; }
    if (svg.dataset.edit === "true") {
      if (this.data.status.active || this._requestBusy || event.target.closest("[data-draft-vertex]")) return;
      const candidate=event.target.closest("[data-candidate]");
      if (candidate) {
        if (event.shiftKey && this.points.length >= 3 && candidate.dataset.candidate !== this.selectedCandidate) this._mergeCandidate(candidate.dataset.candidate);
        else this._chooseCandidate(candidate.dataset.candidate, true);
        return;
      }
      const room=event.target.closest("[data-room]");
      if (room && !this.manualDrawing) {this._selectSavedRoomZone(room.dataset.room); return;}
      if (this.points.length >= 64) { this._toast("Maximal 64 Eckpunkte pro Raum"); return; }
      this._recordDraft(); this.points.push(this._planPosition(event,svg));
      if (this.points.length === 3) { this._storeDraft(); this._render(); } else this._refreshDraft();
    } else { const zone=event.target.closest("[data-room]"); if (zone) this._liveDialog(zone.dataset.room); }
  }
  _refreshDraft(persist = true) {
    this._storeDraft(persist);
    const plan=this.data.config.floorplans[this.plan]; if (!plan) return;
    const svg=this.shadowRoot.getElementById("floorplan"); if (!svg) return;
    svg.querySelector(".draft")?.setAttribute("points",this.points.map(([x,y]) => `${x*plan.width},${y*plan.height}`).join(" "));
    const handles=svg.querySelector(".draft-points");
    if (!handles) return;
    if (handles.children.length !== this.points.length) handles.innerHTML=this._draftHandles(plan);
    else [...handles.children].forEach((circle,index) => {circle.setAttribute("cx",this.points[index][0]*plan.width); circle.setAttribute("cy",this.points[index][1]*plan.height);});
  }
  _vertexDown(event) {
    const labelGroup = event.target.closest("[data-label-room]");
    if (labelGroup && !this.data.status.active && !this._requestBusy) {
      const svg = labelGroup.closest("svg");
      const room = labelGroup.dataset.labelRoom;
      const plan = this.data.config.floorplans[this.plan];
      if (svg && plan) {
        event.preventDefault();
        labelGroup.classList.add("dragging");
        this._dragLabel = {
          room,
          labelGroup,
          svg,
          plan,
          pointer: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          origCx: Number(labelGroup.dataset.cx),
          origCy: Number(labelGroup.dataset.cy),
          moved: false,
        };
        svg.setPointerCapture(event.pointerId);
        labelGroup.focus();
        return;
      }
    }
    const handle=event.target.closest("[data-draft-vertex]"); if (!handle || this.data.status.active || this._requestBusy) return;
    event.preventDefault(); this._recordDraft();
    const svg=handle.closest("svg");
    this._dragVertex={index:Number(handle.dataset.draftVertex),svg,pointer:event.pointerId};
    svg.setPointerCapture(event.pointerId); handle.focus();
  }
  _vertexMove(event) {
    const dragL = this._dragLabel;
    if (dragL && dragL.pointer === event.pointerId) {
      event.preventDefault();
      const dx = event.clientX - dragL.startX;
      const dy = event.clientY - dragL.startY;
      if (!dragL.moved && Math.hypot(dx, dy) > 3) {
        dragL.moved = true;
      }
      if (dragL.moved) {
        const pos = this._planPosition(event, dragL.svg);
        const targetX = pos[0] * dragL.plan.width;
        const targetY = pos[1] * dragL.plan.height;
        const shiftX = Math.round((targetX - dragL.origCx) * 10) / 10;
        const shiftY = Math.round((targetY - dragL.origCy) * 10) / 10;
        dragL.labelGroup.setAttribute("transform", `translate(${shiftX},${shiftY})`);
      }
      return;
    }
    const drag=this._dragVertex; if (!drag || drag.pointer !== event.pointerId) return;
    event.preventDefault(); this.points[drag.index]=this._planPosition(event,drag.svg); this._refreshDraft(false);
  }
  async _vertexEnd(event) {
    const dragL = this._dragLabel;
    if (dragL && dragL.pointer === event.pointerId) {
      if (dragL.svg.hasPointerCapture(event.pointerId)) dragL.svg.releasePointerCapture(event.pointerId);
      dragL.labelGroup.classList.remove("dragging");
      this._dragLabel = null;
      if (dragL.moved) {
        this._ignorePlanClick = true;
        const pos = this._planPosition(event, dragL.svg);
        const finalPos = [Math.max(0.01, Math.min(0.99, Math.round(pos[0] * 10000) / 10000)), Math.max(0.01, Math.min(0.99, Math.round(pos[1] * 10000) / 10000))];
        await this._saveLabelPosition(dragL.plan.id, dragL.room, finalPos);
      }
      return;
    }
    const drag=this._dragVertex; if (!drag || drag.pointer !== event.pointerId) return;
    if (drag.svg.hasPointerCapture(event.pointerId)) drag.svg.releasePointerCapture(event.pointerId);
    this._dragVertex=null; this._ignorePlanClick=true; this._storeDraft();
  }
  async _saveLabelPosition(planId, roomId, pos) {
    const plan = this.data.config.floorplans[planId];
    if (!plan) return;
    const item = structuredClone(plan);
    if (!item.labels) item.labels = {};
    item.labels[roomId] = pos;
    try {
      this.data = await this._call("crud", {collection: "floorplans", operation: "save", item, revision: this._viewRevision});
      const roomName = this.data.config.rooms[roomId]?.name || roomId;
      this._toast(`Beschriftung für „${roomName}“ platziert`);
      this._render();
    } catch (err) {
      this._toast(`Konnte Beschriftung nicht speichern: ${err.message || err}`, true);
      this._render();
    }
  }
  async _vertexKey(event) {
    if ((event.ctrlKey || event.metaKey) && ["z","y"].includes(event.key.toLowerCase()) && event.target.closest("#floorplan")) {
      event.preventDefault(); this._undoDraft(event.key.toLowerCase() === "y" || event.shiftKey); return;
    }
    const labelGroup = event.target.closest("[data-label-room]");
    if (labelGroup && !this.data.status.active && !this._requestBusy) {
      const roomId = labelGroup.dataset.labelRoom;
      const plan = this.data.config.floorplans[this.plan];
      if (plan && ["Delete", "Backspace"].includes(event.key)) {
        event.preventDefault();
        if (plan.labels?.[roomId]) {
          const item = structuredClone(plan);
          delete item.labels[roomId];
          this.data = await this._call("crud", {collection: "floorplans", operation: "save", item, revision: this._viewRevision});
          const roomName = this.data.config.rooms[roomId]?.name || roomId;
          this._toast(`Beschriftung für „${roomName}“ auf Raummitte zurückgesetzt`);
          this._render();
        }
        return;
      }
      if (plan && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        const cur = plan.labels?.[roomId] || roomVisualCenter(plan.zones[roomId] || []);
        const delta = event.shiftKey ? 0.002 : 0.01;
        const change = {ArrowLeft: [-delta, 0], ArrowRight: [delta, 0], ArrowUp: [0, -delta], ArrowDown: [0, delta]}[event.key];
        const finalPos = [Math.max(0.01, Math.min(0.99, Math.round((cur[0] + change[0]) * 10000) / 10000)), Math.max(0.01, Math.min(0.99, Math.round((cur[1] + change[1]) * 10000) / 10000))];
        await this._saveLabelPosition(plan.id, roomId, finalPos);
        return;
      }
    }
    const candidate=event.target.closest("[data-candidate]");
    if (candidate && ["Enter"," "].includes(event.key)) {event.preventDefault(); this._chooseCandidate(candidate.dataset.candidate, true); return;}
    if (candidate && ["Delete","Backspace"].includes(event.key) && !this.data.status.active && !this._requestBusy) {event.preventDefault(); this._deleteCandidate(candidate.dataset.candidate); return;}
    const handle=event.target.closest("[data-draft-vertex]"); if (!handle || this.data.status.active || this._requestBusy) return;
    const index=Number(handle.dataset.draftVertex), delta=event.shiftKey ? .01 : .002;
    const change={ArrowLeft:[-delta,0],ArrowRight:[delta,0],ArrowUp:[0,-delta],ArrowDown:[0,delta]}[event.key];
    if (change) {event.preventDefault(); this._recordDraft(); this.points[index]=this.points[index].map((value,i) => Math.max(0,Math.min(1,value+change[i]))); this._refreshDraft();}
    else if (["Delete","Backspace"].includes(event.key)) {event.preventDefault(); this._recordDraft(); this.points.splice(index,1); this._refreshDraft();}
  }
  _windowKey(event) {
    if (event.defaultPrevented || this.tab !== 1 || this.data?.status.active || this._requestBusy || this.shadowRoot.getElementById("editor")?.open) return;
    const active = this.shadowRoot.activeElement || document.activeElement;
    if (active && (["INPUT","TEXTAREA","SELECT"].includes(active.tagName) || active.hasAttribute?.("data-draft-vertex") || active.hasAttribute?.("data-label-room"))) return;
    if (event.key === "Escape" && (this.points.length || this.selectedCandidate || this.zoneRoom)) {
      event.preventDefault(); this._deselectZone(); return;
    }
    if (!this.selectedCandidate || !["Delete","Backspace"].includes(event.key)) return;
    event.preventDefault();
    this._deleteCandidate(this.selectedCandidate);
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
    const canAttach = !id && this.tab === 1 && this.points.length >= 3 && !this.zoneRoom;
    this._dialog(id ? "Raum bearbeiten" : "Raum / Außenbereich anlegen", `<div class="form-grid"><label class="field wide">Raumname<input name="name" value="${esc(r.name)}" required maxlength="100" autofocus placeholder="z. B. Terrasse, Garagenhof"></label>${canAttach ? `<div class="wide">${this._checkbox("attach_zone", `Aktuell markierte Fläche${this.selectedCandidate ? ` (Fläche ${esc(this.selectedCandidate)})` : ""} diesem Raum zuordnen`, false)}<small>Ohne Haken wird nur der Raum angelegt – du zeichnest die Fläche danach frei im Bild.</small></div>` : ""}<div class="wide checks"><h3>Direkt angrenzende Räume</h3>${Object.values(this.data.config.rooms).filter(x => x.id !== id).map(x => this._checkbox(`adj_${x.id}`, esc(x.name), r.adjacent.includes(x.id))).join("") || `<p>Noch keine weiteren Räume vorhanden.</p>`}</div></div>`, "room", id);
  }

  _profileDialog(copy = false) {
    const current = this.data.config.profiles[this.profile];
    this._profileTemplate = copy ? this.profile : null;
    this._dialog(copy ? "Profil duplizieren" : "Profil anlegen", `<label class="field">Profilname<input name="name" value="${copy ? esc(current.name.slice(0,85)+" Kopie") : ""}" required maxlength="100" autofocus></label>${this._profileIconField(copy ? current.icon : null)}<p style="margin-top:18px">${copy ? "Sensoren, Aktionen und Regeln werden kopiert." : "Lege anschließend Räume, Sensoren, Regeln und Reaktionen für dieses Profil fest."}</p>`, "profile");
  }

  _sensorDialog(id, forcePerimeter = false) {
    const old = this.data.config.sensors[id], e = this.catalog.entities.find(x => x.entity_id === id);
    const defaultRole = forcePerimeter ? (id.startsWith("camera.") || id.startsWith("image_processing.") || /person|kamera|camera/i.test(`${e?.name || ""} ${id}`) ? "perimeter_camera" : "perimeter_sensor") : (id.startsWith("camera.") ? "perimeter_camera" : id.startsWith("lock.") ? "lock_contact" : "entry_contact");
    const s = old || {entity_id: id, name: e?.name || id, role: defaultRole, front_of: [], enabled: true, flap_enabled: true, flap_threshold: 3, flap_window: 15, debounce_ms: 0, active_states: id.startsWith("lock.") ? ["unlocked", "open"] : ["on"]};
    this._dialog(old ? "Sensor bearbeiten" : (forcePerimeter ? "Kamera / Außensensor zuweisen" : "Sensor zuweisen"), `<div class="form-grid"><label class="field wide">Entität<input value="${esc(id)}" readonly></label><label class="field wide">Anzeigename<input name="name" value="${esc(s.name)}" required maxlength="200"></label><label class="field">Sicherheitsrolle<select name="role">${options(ROLES, s.role)}</select></label><label class="field">Raum<select name="room_id">${this._roomsOptions(s.room_id, "Kein Raum / globales Vorfeld")}</select></label><label class="field wide">Vorfeld vor diesen Räumen<select name="front_of" multiple>${Object.values(this.data.config.rooms).map(r => `<option value="${r.id}"${s.front_of.includes(r.id) ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select><small>Nur für Kameras & Außensensoren (Vorfeld). Keine Auswahl bedeutet gesamtes Grundstück (global), falls auch kein Raum gewählt ist.</small></label><label class="field wide">Unabhängige Signalquelle<input name="source_id" value="${esc(s.source_id || "")}" maxlength="200" placeholder="Standard: Entitäts-ID"><small>Mehrere Entitäten desselben physischen Sensors müssen dieselbe Quellenkennung haben. Sie dürfen sich nicht gegenseitig bestätigen.</small></label><div class="wide checks">${this._checkbox("enabled", "Sensor aktivieren", s.enabled)}${this._checkbox("flap_enabled", "Anti-Flapping für Öffnungs-/Schlosssensoren aktivieren", s.flap_enabled)}</div>${this._number("flap_threshold", "Quarantäne ab N Zustandswechseln", s.flap_threshold, 3, 100)}${this._number("flap_window", "Innerhalb von W Sekunden", s.flap_window, 1, 300)}${this._number("debounce_ms", "Mindest-Aktivzeit (Millisekunden)", s.debounce_ms, 0, 60000, "0 verwendet den Standard der Sensorrolle.")}<label class="field">Verknüpfte Kamera<select name="camera_entity_id">${this._entityOptions(["camera"], s.camera_entity_id)}</select></label><label class="field">Erkennungsattribut (optional)<input name="attribute" value="${esc(s.attribute || "")}" maxlength="100" placeholder="z. B. person_detected"><small>Für camera/image_processing erforderlich.</small></label><label class="field">Aktive Werte, durch Komma getrennt<input name="active_states" value="${esc(s.active_states.join(", "))}" required maxlength="500"><small>Boolesche Attribute: true / false; Zählwerte explizit angeben.</small></label><div class="wide checks">${this._checkbox("entry_delay", "Eingangsverzögerung für diesen Öffnungssensor erlauben", s.entry_delay)}${this._checkbox("immediate", "Darf alleine die zugeordnete bestätigte Stufe auslösen (Override)", s.immediate)}</div><div class="help wide">Override, Rauch und Panik lösen bei scharfer Anlage alleine aus. Für diese Sensoren ersetzt die Entprellzeit die Wartezeit auf eine Bestätigung.</div></div>`, "sensor", id);
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
    if (button.dataset.catalogFilter) { this.catalogFilter = button.dataset.catalogFilter; this._render(); return; }
    const command = button.dataset.command, id = button.dataset.id;
    try {
      if (command === "menu") this.dispatchEvent(new CustomEvent("hass-toggle-menu", {bubbles: true, composed: true}));
      else if (command === "close") { this.liveRoom = null; this.shadowRoot.getElementById("editor").close(); }
      else if (command === "room-new" || command === "room-edit") this._roomDialog(id);
      else if (command === "sensor-new" || command === "sensor-edit") this._sensorDialog(id, false);
      else if (command === "sensor-new-perimeter") this._sensorDialog(id, true);
      else if (command === "filter-perimeter") { this.catalogFilter = "perimeter"; this._render(); this.shadowRoot.getElementById("sensor-search")?.scrollIntoView({behavior: "smooth"}); }
      else if (command === "action-new" || command === "action-edit") this._actionDialog(id);
      else if (command === "profile-icon") { const form = button.closest("form"); form.elements.profile_icon.value = id; this._updateIconPreview(form); }
      else if (command === "floorplan-upload") this._uploadDialog();
      else if (command === "floorplan-pick") this.shadowRoot.getElementById("plan-upload").click();
      else if (command === "floorplan-analyze") await this._analyzePlan();
      else if (command === "floorplan-editor") { this.tab = 1; this._render(); }
      else if (command === "toggle-graphic-preview") { this.graphicPreview = !this.graphicPreview; this._render(); }
      else if (command === "floorplan-new" || command === "floorplan-edit") this._dialog(id ? "Grundriss bearbeiten" : "Grundriss anlegen", `<label class="field">Etage / Name<input name="name" maxlength="100" required value="${esc(this.data.config.floorplans[id]?.name || "")}"></label>`, "floorplan", id);
      else if (command === "zone-save") {
        if (this.points.length < 3) throw new Error("Mindestens drei Eckpunkte markieren");
        if (!this.zoneRoom) await this._zoneAssignmentDialog();
        else await this._saveDraftZone(this.zoneRoom);
      }
      else if (command === "zone-delete") {
        if (!this.zoneRoom) {
          if (this.points.length || this.selectedCandidate) { this._deselectZone(); return; }
          throw new Error("Bitte den Raum des gespeicherten Bereichs auswählen");
        }
        const item=structuredClone(this.data.config.floorplans[this.plan]);
        if (item.zones[this.zoneRoom]) {
          delete item.zones[this.zoneRoom];
          if (item.labels) delete item.labels[this.zoneRoom];
          this.data=await this._call("crud",{collection:"floorplans",operation:"save",item,revision:this._viewRevision});
        }
        this._recordDraft(); this.points=[]; this.selectedCandidate=""; this._storeDraft(); this._draftJournal?.markSaved(this._draftSnapshot()); this._render();
      }
      else if (command === "zone-deselect") this._deselectZone();
      else if (command === "labels-reset") {
        const plan = this.data.config.floorplans[this.plan];
        if (!plan) return;
        const item = structuredClone(plan);
        item.labels = {};
        this.data = await this._call("crud", {collection: "floorplans", operation: "save", item, revision: this._viewRevision});
        this._toast("Alle Beschriftungen auf Raummitte zentriert");
        this._render();
      }
      else if (command === "floorplan-orthogonalize") {
        const plan = this.data.config.floorplans[this.plan];
        if (!plan) return;
        this._recordDraft();
        const zones = plan.zones || {};
        const hasZones = Object.keys(zones).length > 0;
        const hasDraftPoints = Array.isArray(this.points) && this.points.length >= 3;
        if (!hasZones && !hasDraftPoints) throw new Error("Keine Raumflächen zum Begradigen vorhanden");
        let updatedZones = zones;
        if (hasZones) {
          updatedZones = alignPlanZones(zones);
          const item = structuredClone(plan);
          item.zones = updatedZones;
          this.data = await this._call("crud", {collection: "floorplans", operation: "save", item, revision: this._viewRevision});
        }
        if (this.zoneRoom && updatedZones[this.zoneRoom]) {
          this.points = structuredClone(updatedZones[this.zoneRoom]);
        } else if (hasDraftPoints) {
          this.points = orthogonalizePolygon(this.points);
        }
        this._storeDraft();
        this._draftJournal?.markSaved(this._draftSnapshot());
        this._render();
        this._toast("Alle Räume im 90°-Winkel begradigt und ausgerichtet");
      }
      else if (command === "candidates-clear") {
        this._recordDraft();
        if (this.planAnalysis) this.planAnalysis.candidates = [];
        if (this.selectedCandidate) { this.selectedCandidate = ""; this.points = []; }
        this._storeDraft(); this._render();
        this._toast("Restliche Flächenvorschläge ausgeblendet");
      }
      else if (command === "candidate-pick") this._chooseCandidate(id, true);
      else if (command === "candidate-next") this._nextCandidate();
      else if (command === "quick-save-zone") await this._quickSaveZone(id);
      else if (command === "zone-save-new") await this._zoneAssignmentDialog();
      else if (command === "candidate-delete") this._deleteCandidate();
      else if (command === "draft-undo" || command === "draft-redo") this._undoDraft(command === "draft-redo");
      else if (command === "zone-undo") { this._recordDraft(); this.points.pop(); this._refreshDraft(); }
      else if (command === "zone-clear") {
        this._recordDraft();
        if (this.zoneRoom && this.data.config.floorplans[this.plan]?.zones[this.zoneRoom]) this.zoneRoom = null;
        this.points = []; this.selectedCandidate = ""; this.manualDrawing = true; this.graphicPreview = false; this._storeDraft(); this._render();
      }
      else if (command === "stage-add" || command === "stage-remove") this._changeStageRows(command === "stage-add");
      else if (command === "profile-move") {
        const dir = Number(button.dataset.dir), entries = Object.entries(this.data.config.profiles), idx = entries.findIndex(([k]) => k === this.profile), target = idx + dir;
        if (idx < 0 || target < 0 || target >= entries.length) return;
        [entries[idx], entries[target]] = [entries[target], entries[idx]];
        const config = structuredClone(this.data.config);
        config.profiles = Object.fromEntries(entries);
        this.data = await this._call("config/save", {config, revision: this._viewRevision});
        this._render(); this._toast("Profil-Reihenfolge gespeichert");
      }
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
      else if (command === "floorplan-reset") {
        const planName = this.data.config.floorplans[id]?.name || "Grundriss";
        this._dialog("Von vorne anfangen", `<p>Alle gespeicherten Raumflächen im Grundriss „${esc(planName)}“ werden gelöscht. Dein hochgeladenes Grundrissbild bleibt erhalten, sodass du sofort neu starten kannst.</p><div style="margin-top:14px">${this._checkbox("also_delete_rooms", "Auch angelegte IQAlarm-Räume zurücksetzen (Home-Assistant-Bereiche bleiben erhalten)", true)}</div>`, "floorplan-reset", id);
        this.shadowRoot.querySelector('#editor [type="submit"]').textContent = "Jetzt zurücksetzen";
      }
      else if (command === "floorplan-delete") {
        const planName = this.data.config.floorplans[id]?.name || "Grundriss";
        this._dialog("Grundriss komplett löschen", `<p>Der Grundriss „${esc(planName)}“ samt Vorlagenbild und Raumflächen wird entfernt.</p><div style="margin-top:14px">${this._checkbox("also_delete_rooms", "Auch angelegte IQAlarm-Räume zurücksetzen (Home-Assistant-Bereiche bleiben erhalten)", true)}</div>`, "delete-floorplans", id);
        this.shadowRoot.querySelector('#editor [type="submit"]').textContent = "Grundriss löschen";
      }
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

  _pruneRooms(config, ids) {
    for (const rid of ids) delete config.rooms[rid];
    for (const r of Object.values(config.rooms)) r.adjacent = (r.adjacent || []).filter(a => config.rooms[a]);
    for (const s of Object.values(config.sensors)) {
      if (s.room_id && !config.rooms[s.room_id]) s.room_id = null;
      s.front_of = (s.front_of || []).filter(r => config.rooms[r]);
    }
    for (const p of Object.values(config.profiles)) {
      if (Array.isArray(p.room_ids)) p.room_ids = p.room_ids.filter(r => config.rooms[r]);
    }
    for (const fp of Object.values(config.floorplans)) {
      for (const rid of Object.keys(fp.zones || {})) if (!config.rooms[rid]) delete fp.zones[rid];
      for (const rid of Object.keys(fp.labels || {})) if (!config.rooms[rid]) delete fp.labels[rid];
    }
  }

  async _submit(event) {
    event.preventDefault(); if (this._requestBusy) return;
    const form = event.target, fields = new FormData(form), get = k => String(fields.get(k) || ""), num = k => Number(fields.get(k)), bool = k => fields.has(k);
    const button = form.querySelector('[type="submit"]');
    this._requestBusy = true; if (button) button.disabled = true;
    try {
      if (form.id === "stage-single-form") {
        const config = structuredClone(this.data.config);
        const idx = config.stages.findIndex(s => s.id === this.stage);
        if (idx >= 0) {
          config.stages[idx] = {
            id: this.stage,
            name: get("stage_name").trim(),
            color: get("stage_color"),
            requires_confirmation: idx > 0 && bool("stage_confirmed"),
            allow_loud: idx > 0 && bool("stage_loud"),
            latch: idx > 0 && bool("stage_latch"),
          };
          if (idx > 0) {
            for (const key of Object.keys(RULES)) {
              if (bool(`rule_${key}`)) {
                for (const prof of Object.values(config.profiles)) prof.stage_targets[key] = this.stage;
              }
            }
          }
          this.data = await this._call("config/save", {config, revision: this._viewRevision});
        }
      } else if (form.id === "stages-form") {
        const config = structuredClone(this.data.config);
        config.stages = [...form.querySelectorAll("[data-stage-row]")].map((row,index) => ({id:row.dataset.stageRow,name:row.querySelector('[name="stage_name"]').value.trim(),color:row.querySelector('[name="stage_color"]').value,requires_confirmation:index > 0 && row.querySelector('[name="stage_confirmed"]').checked,allow_loud:index > 0 && row.querySelector('[name="stage_loud"]').checked,latch:index > 0 && row.querySelector('[name="stage_latch"]').checked}));
        this.data = await this._call("config/save",{config,revision:this._viewRevision});
      } else if (form.id === "rules-form" || form.id === "settings-form") {
        const config = structuredClone(this.data.config);
        if (form.id === "rules-form") {
          const p = config.profiles[this.profile];
          p.name = get("profile_name").trim(); p.icon = get("profile_icon").trim() || null;
          p.motion_mode = get("motion_mode"); p.motion_scope = get("motion_scope");
          p.stage_targets = Object.fromEntries(Object.keys(RULES).map(key => [key,get(`target_${key}`)]));
          ["room_ids", "sensor_ids", "action_ids"].forEach(key => p[key] = bool(`all_${key}`) ? null : fields.getAll(key));
          ["perimeter_seconds", "correlation_seconds", "entry_seconds", "exit_seconds"].forEach(k => p[k] = num(k));
          ["perimeter_contact", "contact_motion", "multi_contact", "multi_motion", "adjacent_rooms", "reactions_enabled", "perimeter_enabled", "contacts_enabled", "simulation_enabled"].forEach(k => p[k] = bool(k));
        } else {
          const s = config.settings;
          s.observation_profile_id = bool("live_evaluation") ? "live" : null;
          ["diagnose_disarmed", "block_open_on_arm", "block_unavailable_on_arm", "auto_camera_snapshot", "auto_camera_record", "simulation_enabled"].forEach(k => s[k] = bool(k));
          ["retention_days", "simulation_start", "simulation_end"].forEach(k => s[k] = num(k));
          s.simulation_lights = fields.getAll("simulation_lights");
          s.debounce_by_role = Object.fromEntries(Object.keys(ROLES).map(k => [k, num(`debounce_${k}`)]));
        }
        this.data = await this._call("config/save", {config, revision: this._viewRevision});
      } else if (form.id === "editor-form") {
        const type = form.dataset.type, id = form.dataset.id;
        if (type === "zone-assignment") {
          await this._saveDraftZone(get("zone_room"), get("zone_new_room").trim(), this._dialogRevision);
        }
        else if (type === "floorplan-reset") {
          const config = structuredClone(this.data.config);
          const plan = config.floorplans[id];
          if (plan) {
            const roomIds = Object.keys(config.floorplans).length <= 1 ? Object.keys(config.rooms) : Object.keys(plan.zones || {});
            plan.zones = {};
            plan.labels = {};
            if (bool("also_delete_rooms") && roomIds.length) this._pruneRooms(config, roomIds);
            this.data = await this._call("config/save", {config, revision: this._dialogRevision});
          }
          this.points = []; this.zoneRoom = null; this.selectedCandidate = ""; this.manualDrawing = false; this.graphicPreview = false; this.tab = 1;
          this._draftJournal?.markSaved(this._draftSnapshot());
          this.shadowRoot.getElementById("editor").close();
          this._render();
          await this._analyzePlan();
          this._toast("Grundriss zurückgesetzt · Du kannst jetzt von vorne beginnen");
          return;
        }
        else if (type === "floorplan-upload") {
          const file = form.elements.image.files[0];
          if (!file) throw new Error("Bitte ein PNG- oder JPG-Bild auswählen");
          if (button) button.textContent = "Wird hochgeladen …";
          await this._sendPlanImage(file, null, get("name").trim(), this._dialogRevision);
        }
        else if (type === "disarm") this.data = await this._call("set_mode", {mode: "disarmed", code: get("code")});
        else if (type.startsWith("delete-")) {
          const col = type.slice(7);
          const zoneRooms = col === "floorplans" ? (Object.keys(this.data.config.floorplans).length <= 1 ? Object.keys(this.data.config.rooms) : Object.keys(this.data.config.floorplans[id]?.zones || {})) : [];
          this.data = await this._call("crud", {collection: col, operation: "delete", key: id, revision: this._dialogRevision});
          if (col === "floorplans") {
            if (bool("also_delete_rooms") && zoneRooms.length) {
              const config = structuredClone(this.data.config);
              this._pruneRooms(config, zoneRooms);
              this.data = await this._call("config/save", {config, revision: this.data.config.revision});
            }
            this._selectPlan(Object.keys(this.data.config.floorplans)[0] || null);
            this.graphicPreview = false;
          }
        }
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
            item = this._profileTemplate ? structuredClone(this.data.config.profiles[this._profileTemplate]) : {reactions_enabled:true, action_ids:null, motion_mode:"always"};
            item.name = get("name").trim(); item.icon = get("profile_icon").trim() || null;
          } else if (type === "floorplan") { collection = "floorplans"; item = {...(this.data.config.floorplans[id] || {}), name:get("name")}; if (id) item.id = id; } else throw new Error("Unbekanntes Formular");
          const knownRooms = new Set(Object.keys(this.data.config.rooms));
          this.data = await this._call("crud", {collection, operation: "save", item, revision: this._dialogRevision});
          if (type === "room" && !id) {
            const newRoomId = Object.keys(this.data.config.rooms).find(key => !knownRooms.has(key));
            if (newRoomId && this.tab === 1) {
              if (bool("attach_zone") && this.plan && this.data.config.floorplans[this.plan] && this.points.length >= 3) {
                const planItem = structuredClone(this.data.config.floorplans[this.plan]);
                planItem.zones[newRoomId] = structuredClone(this.points);
                const savedCandidate = this.selectedCandidate;
                this.data = await this._call("crud", {collection: "floorplans", operation: "save", item: planItem, revision: this.data.config.revision});
                if (savedCandidate && this.planAnalysis?.candidates) this.planAnalysis.candidates = this.planAnalysis.candidates.filter(c => c.id !== savedCandidate);
                this.points = []; this.selectedCandidate = ""; this.zoneRoom = null; this.manualDrawing = false;
              } else {
                // Clean start: nothing pre-selected, draw the new room's area freely in the image.
                this.points = []; this.selectedCandidate = ""; this.zoneRoom = newRoomId; this.manualDrawing = true; this.graphicPreview = false;
              }
              this._draftJournal?.markSaved(this._draftSnapshot());
            }
          }
          if (type === "profile") this.profile = Object.keys(this.data.config.profiles).find(key => this.data.config.profiles[key].name === item.name);
        }
        this.shadowRoot.getElementById("editor").close();
      }
      this._storeDraft(); this._render(); this._toast("Gespeichert");
    } catch (err) {this._toast(err.message || String(err), true);}
    finally {this._requestBusy = false; if (button?.isConnected) {button.disabled = false; if (form.dataset.type === "floorplan-upload") button.textContent="Hochladen";} this._updateLock();}
  }
}

if (!customElements.get("iqalarm-panel")) customElements.define("iqalarm-panel", IQAlarmPanel);
