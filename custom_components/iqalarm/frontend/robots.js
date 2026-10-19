/* Robot coverage is informational and never becomes an intrusion confirmation. */
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const defaults=["on","cleaning","returning","mowing","working"];
function stateText(device,enabled=true) {
  if(!enabled)return "Ausnahme deaktiviert";
  if(!device)return "Status wird ermittelt";
  const text=device.active?`Aktiv · ${device.paused_sensors.length} Bewegungsmelder ausgenommen`:device.waiting?"Nachlauf · wartet auf ruhige Bewegungsmelder":"Inaktiv · keine Ausnahme";
  return device.fault?`${text} · Störung: Aktivität nicht vollständig verfügbar`:text;
}

export function renderRobotSettings(panel) {
  const config=panel.data.config;
  return `<section class="card" style="margin-top:18px"><div class="row between"><h2>Roboter & Überwachungsrisiko</h2><button type="button" class="primary" data-command="robot-new" data-config>Roboter hinzufügen</button></div><p>Arbeitet ein Roboter, ignoriert IQAlarm die Bewegungsmelder in seinen Räumen oder seiner Etage. Fenster, Türen und Kameras bleiben aktiv. Das Überwachungsrisiko ist keine Einbruchsbestätigung.</p>${Object.values(config.robots||{}).map(robot=>`<article class="action-card"><div class="description"><h3>${esc(robot.name)}${robot.enabled?"":" · deaktiviert"}</h3><p>${esc(robot.floorplan_id?config.floorplans[robot.floorplan_id]?.name:robot.room_ids.map(id=>config.rooms[id]?.name).join(", "))} · ${robot.activities.length} Aktivitätsentitäten · ${robot.risk_points}/3 Risikopunkte</p><p data-robot-status="${esc(robot.id)}">${esc(stateText(panel.data.status.coverage?.robots.find(item=>item.id===robot.id),robot.enabled))}</p></div><button type="button" class="small" data-command="robot-edit" data-id="${esc(robot.id)}" data-config>Bearbeiten</button><button type="button" class="small danger" data-command="robot-delete" data-id="${esc(robot.id)}" data-config>Entfernen</button></article>`).join("")||"<p>Noch keine Roboter-Ausnahme eingerichtet.</p>"}</section>`;
}

export function openRobotDialog(panel,id) {
  const config=panel.data.config,robot=config.robots?.[id]||{name:"",activities:[],room_ids:[],floorplan_id:null,risk_points:1,enabled:true};
  const activities=Array.from({length:3},(_,i)=>{
    const source=robot.activities[i];
    return `<section class="card" style="margin-top:12px;padding:16px"><h3>Aktivitätsentität ${i+1}${i?" · optional":""}</h3><div class="form-grid" style="margin-top:12px"><label class="field">Entität ${i+1}<input name="robot_entity_${i}" list="robot-entities" value="${esc(source?.entity_id||"")}" ${i?"":"required"} placeholder="vacuum.saugroboter"></label><label class="field">Aktive Zustände ${i+1}<input name="robot_states_${i}" aria-label="Aktive Zustände ${i+1}" value="${esc((source?.active_states||defaults).join(", "))}" placeholder="cleaning, returning"><small>Durch Komma trennen; zum Beispiel on oder cleaning.</small></label></div><details style="margin-top:10px"><summary>Zustand aus einem Attribut lesen</summary><label class="field" style="margin-top:10px">Attribut ${i+1}<input name="robot_attribute_${i}" value="${esc(source?.attribute||"")}" placeholder="Leer: Entitätszustand verwenden"></label></details></section>`;
  }).join("");
  const body=`<label class="field">Robotername<input name="robot_name" value="${esc(robot.name)}" required maxlength="100"></label><p>Bis zu drei Statusentitäten pro Gerät. Eine aktive Meldung genügt (ODER); das Gerät zählt einmal. Wähle Statusentitäten des Roboters und keine Alarmsensoren.</p><datalist id="robot-entities">${panel.catalog.entities.map(item=>`<option value="${esc(item.entity_id)}">${esc(item.name)}</option>`).join("")}</datalist>${activities}<div class="form-grid" style="margin-top:18px"><label class="field">Überwachungsbereich<select name="robot_scope" aria-label="Überwachungsbereich"><option value="rooms"${robot.floorplan_id?"":" selected"}>Ausgewählte Räume</option><option value="floor"${robot.floorplan_id?" selected":""}>Eine Etage</option></select></label><label class="field">Beitrag zum Überwachungsrisiko (von 3)<input name="robot_points" type="number" min="1" max="3" value="${robot.risk_points}" required></label><label class="field wide" data-robot-rooms>Bewegungsmelder in diesen Räumen ignorieren<select name="robot_rooms" aria-label="Bewegungsmelder in diesen Räumen ignorieren" multiple>${Object.values(config.rooms).map(room=>`<option value="${esc(room.id)}"${robot.room_ids.includes(room.id)?" selected":""}>${esc(room.name)}</option>`).join("")}</select></label><label class="field wide" data-robot-floor>Bewegungsmelder auf dieser Etage ignorieren<select name="robot_floor" aria-label="Bewegungsmelder auf dieser Etage ignorieren"><option value="">Etage auswählen</option>${Object.values(config.floorplans).map(plan=>`<option value="${esc(plan.id)}"${robot.floorplan_id===plan.id?" selected":""}>${esc(plan.name)}</option>`).join("")}</select><small>Es zählen die Räume mit gespeicherter Fläche auf dieser Etage.</small></label></div><div style="margin-top:18px">${panel._checkbox("robot_enabled","Roboter-Ausnahme aktivieren",robot.enabled)}</div>`;
  panel._dialog(id?"Roboter bearbeiten":"Roboter einrichten",body,"robot",id);
  const form=panel.shadowRoot.getElementById("editor-form"),refresh=()=>{
    const floor=form.elements.robot_scope.value==="floor";
    form.querySelector("[data-robot-rooms]").hidden=floor;form.elements.robot_rooms.disabled=floor;
    form.querySelector("[data-robot-floor]").hidden=!floor;form.elements.robot_floor.disabled=!floor;form.elements.robot_floor.required=floor;
  };
  form.elements.robot_scope.addEventListener("change",refresh);refresh();
}

export function readRobotForm(form) {
  const fields=new FormData(form),get=key=>String(fields.get(key)||"").trim();
  const activities=Array.from({length:3},(_,i)=>({entity_id:get(`robot_entity_${i}`),active_states:get(`robot_states_${i}`).split(",").map(s=>s.trim()).filter(Boolean),attribute:get(`robot_attribute_${i}`)||null})).filter(source=>source.entity_id);
  return {name:get("robot_name"),activities,room_ids:get("robot_scope")==="floor"?[]:fields.getAll("robot_rooms"),floorplan_id:get("robot_scope")==="floor"?get("robot_floor"):null,risk_points:Number(get("robot_points")),enabled:fields.has("robot_enabled")};
}

export function updateRobotStatuses(panel) {
  for(const node of panel.shadowRoot.querySelectorAll("[data-robot-status]"))node.textContent=stateText(panel.data.status.coverage?.robots.find(item=>item.id===node.dataset.robotStatus),panel.data.config.robots?.[node.dataset.robotStatus]?.enabled);
}

export function renderCoverage(panel) {
  const coverage=panel.data.status.coverage;if(!coverage||!panel.data.status.profile_id)return "";
  const devices=coverage.robots.filter(device=>device.paused_sensors.length||device.fault),windows=coverage.ignored_windows||[];
  if(!devices.length&&!windows.length)return "";
  const windowInfo=windows.length?`<details style="margin-top:10px"><summary>${windows.length} Fenster ignoriert</summary><p>${windows.map(window=>esc(window.name)).join(", ")}</p><p>Beim Scharfschalten bereits offen. Bleibt bis zum Ausschalten ignoriert, auch nach dem Schließen.</p></details>`:"";
  return `<section class="card" data-live-key="robot-coverage" style="margin-bottom:18px"><div class="row between"><strong>Überwachung ${coverage.current?"reduziert":"prüfen"}</strong><span class="pill">Überwachungsrisiko ${coverage.current}/${coverage.target}</span></div>${devices.map(device=>`<p><strong>${esc(device.name)}</strong> · ${esc(stateText(device))}</p>`).join("")}${windowInfo}${devices.length?"<p>Nur die Bewegungsmelder der zugeordneten Räume sind ausgenommen. Eine gespeicherte Einbruchsbestätigung entsteht dadurch nicht.</p>":""}</section>`;
}
