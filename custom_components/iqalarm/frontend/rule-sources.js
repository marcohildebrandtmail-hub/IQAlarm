import {sensorSymbol, symbolHTML} from "./display-icons.js?v=2.12.4";

const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const SOURCE_ROLES={perimeter_camera:"Personenerkennung außen",perimeter_sensor:"Bewegungsmelder außen",entry_contact:"Öffnungskontakte",lock_contact:"Türschlösser",vibration_glass:"Glas / Vibration",interior_motion:"Bewegung innen",interior_mmwave:"Präsenz innen",panic:"Panik",smoke:"Rauch / Gefahr"};
export const RULE_SOURCES_CSS=`
dialog.rule-editor{width:min(1120px,calc(100vw - 28px));max-width:min(1120px,calc(100vw - 28px))}
.rule-sources-grid{display:grid;grid-template-columns:minmax(260px,.85fr) minmax(0,1.15fr);gap:20px;margin-top:14px;align-items:start}
.rule-sources-grid>*{min-width:0}
.rule-source-select{height:360px!important;min-height:300px;font-size:15px;padding:10px!important}
.rule-source-select option{padding:8px 10px;line-height:1.5}
.rule-source-select optgroup{padding:6px 0;font-size:13px}
.rule-source-preview{border:1px solid var(--iq-border);border-radius:10px;background:var(--primary-background-color,#f3f6fa);min-height:360px;padding:14px}
.rule-source-preview h4{font-size:15px;margin:0 0 8px}
.rule-source-summary{font-size:13px;margin-bottom:12px;color:var(--iq-muted)}
.rule-source-members{max-height:410px;overflow:auto;overscroll-behavior:contain;padding-right:3px}
.rule-source-member{padding:12px;border:1px solid var(--iq-border);border-radius:9px;background:var(--iq-surface);margin-top:8px;overflow-wrap:anywhere}
.rule-source-member.is-active{border-color:var(--iq-green);background:color-mix(in srgb,var(--iq-green) 10%,var(--iq-surface))}
.rule-source-member.is-fault{border-color:var(--iq-amber)}
.rule-source-member.is-excluded{opacity:.7}
.rule-source-title{display:flex;align-items:flex-start;gap:9px;font-size:14px;font-weight:650}
.rule-source-title ha-icon{flex-shrink:0;--mdc-icon-size:21px}
.rule-source-member code{display:block;margin:6px 0;font-size:12px;overflow-wrap:anywhere;white-space:normal}
.rule-source-meta{font-size:12px;color:var(--iq-muted);line-height:1.5}
.rule-source-state{display:inline-block;font-size:12px;font-weight:700;padding:4px 8px;border-radius:6px;background:var(--primary-background-color,#f3f6fa);margin-top:8px}
.is-active .rule-source-state{color:var(--iq-green)}
.is-fault .rule-source-state{color:var(--iq-amber)}
@media(max-width:760px){.rule-sources-grid{grid-template-columns:minmax(0,1fr);gap:14px}.rule-source-select{height:310px!important;min-height:260px}.rule-source-preview{min-height:0}.rule-source-members{max-height:340px}}
`;

export function sourceMembers(panel,condition,roomIds=null) {
  const records=panel._allSensorRecords(),visible=new Set(panel._displaySensors().map(s=>s.entity_id));
  const ids=new Set(condition.sensor_ids);
  for(const sensor of Object.values(records))if(visible.has(sensor.entity_id)&&condition.roles.includes(sensor.role))ids.add(sensor.entity_id);
  return [...ids].map(id=>{
    const sensor=records[id],spaces=sensor?.front_of?.length?sensor.front_of:sensor?.room_id?[sensor.room_id]:[];
    const groups=condition.roles.filter(role=>role===sensor?.role).map(role=>SOURCE_ROLES[role]||role);
    const via=[...groups.map(name=>`Gruppe: ${name}`),...(condition.sensor_ids.includes(id)?["Einzeln ausgewählt"]:[])];
    const ignored=panel.data.status.ignored_windows?.includes(id);
    const reason=ignored?"Für diese Scharfschaltung ignoriert":!sensor?"Entität nicht mehr zugeordnet":!visible.has(id)?"Eingang eines zusammengeführten Fensters":sensor.enabled===false?"Sensor isoliert":sensor.sensor_kind==="window_handle"?"Nur Information · keine Alarmquelle":roomIds?.length&&!spaces.some(room=>roomIds.includes(room))?"Außerhalb der Raumbegrenzung dieser Regel":"";
    const raw=panel._connected===false?null:panel.data.status.raw?.[id];
    const quarantined=Boolean(panel.data.status.quarantine?.[id]);
    let state=panel._connected===false?"Live-Verbindung unterbrochen":raw==null?"Keine Verbindung":
      sensor?.window_id&&panel._windowLabel?panel._windowLabel(sensor.window_id):
      sensor?.role==="perimeter_camera"?(raw?"Person erkannt":"Keine Person"):
      sensor?.role?.startsWith("interior")?(raw?"Bewegung / Präsenz":"Ruhig"):
      sensor?.role==="lock_contact"?(raw?"Entriegelt":"Verriegelt"):
      sensor?.role==="entry_contact"?(raw?"Offen":"Geschlossen"):(raw?"Aktiv":"Inaktiv");
    if(ignored)state="Ignoriert";
    else if(quarantined)state+=" · Prell-Quarantäne";
    return {id,sensor,name:sensor?.name||id,rooms:spaces.map(room=>panel.data.config.rooms[room]?.name||room),via,reason,state,active:!ignored&&raw===true,fault:!ignored&&(raw==null||quarantined)};
  }).sort((a,b)=>Number(Boolean(a.reason))-Number(Boolean(b.reason))||Number(b.active)-Number(a.active)||a.name.localeCompare(b.name,"de"));
}

export function renderSourceMembers(panel,condition,roomIds=null) {
  const members=sourceMembers(panel,condition,roomIds),active=members.filter(m=>m.active&&!m.reason).length;
  return `<h4>Entitäten hinter dieser Auswahl</h4><div class="rule-source-summary" role="status">${members.length} Entitäten · ${active} aktuell aktiv</div><div class="rule-source-members">${members.map(m=>`<article class="rule-source-member ${m.reason?"is-excluded":m.fault?"is-fault":m.active?"is-active":""}" data-rule-source-id="${esc(m.id)}"><div class="rule-source-title">${symbolHTML(sensorSymbol(m.sensor))}<span>${esc(m.name)}</span></div><code>${esc(m.id)}</code><div class="rule-source-meta">${esc(m.rooms.join(", ")||"Ohne Raumzuordnung")}<br>${esc(m.via.join(" · "))}</div><span class="rule-source-state">${esc(m.state)}</span>${m.reason?`<p class="rule-source-meta" style="margin-top:8px">${esc(m.reason)}</p>`:""}</article>`).join("")||'<p>Noch keine Quelle gewählt. Links eine Gruppe oder einzelne Entitäten auswählen.</p>'}</div><p class="muted" style="font-size:12px;margin-top:12px">Gruppen umfassen die zugewiesenen Sensoren ihrer Rolle, auch künftig hinzugefügte. Die Regel prüft zusätzlich Quellenzahl, Zeitfenster und Raumbezug.</p>`;
}

export function updateRuleSources(panel) {
  const form=panel.shadowRoot?.querySelector('#editor[open] #editor-form[data-type="level-rule"]');
  if(!form)return;
  const roomIds=[...form.querySelectorAll('[name="rule_rooms"] option:checked')].map(o=>o.value);
  for(const row of form.querySelectorAll("[data-rule-condition]")) {
    const values=[...row.querySelector('select[multiple]').selectedOptions].map(o=>o.value);
    const condition={sensor_ids:values.filter(v=>!v.startsWith("role:")),roles:values.filter(v=>v.startsWith("role:")).map(v=>v.slice(5))};
    const host=row.querySelector("[data-rule-source-preview]"),html=renderSourceMembers(panel,condition,roomIds);
    if(host._iqSourceHTML!==html){host.innerHTML=html;host._iqSourceHTML=html;}
  }
}

export function bindRuleSources(panel) {
  const form=panel.shadowRoot.querySelector('#editor-form[data-type="level-rule"]');
  form.addEventListener("change",()=>updateRuleSources(panel));
  updateRuleSources(panel);
}
