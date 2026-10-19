/* Explicit physical room connections; geometry never invents an alarm path. */
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export function roomConnections(config) {
  return (config.room_connections||[]).filter(pair=>pair.length===2&&pair[0]!==pair[1]&&pair.every(id=>config.rooms[id]));
}

export function setRoomConnection(config,a,b,connected) {
  if(a===b||!config.rooms[a]||!config.rooms[b])throw Error("Bitte zwei verschiedene vorhandene Räume wählen.");
  const result=structuredClone(config);
  result.room_connections=roomConnections(result).filter(pair=>!(pair.includes(a)&&pair.includes(b)));
  if(connected)result.room_connections.push([a,b].sort());
  return result;
}

export function imageControls(plan,value) {
  if(!plan.image)return "";
  return `<div class="plan-image-controls" data-image-controls="${esc(plan.id)}"><label class="field">Originalbild einblenden · <output data-image-percent>${Math.round(value*100)} %</output><input type="range" min="0" max="100" step="1" value="${Math.round(value*100)}" data-image-opacity="${esc(plan.id)}" aria-label="Originalbild einblenden ${esc(plan.name)}"></label><button type="button" class="small" data-command="plan-image-save" data-id="${esc(plan.id)}" data-config>Bildanzeige speichern</button></div>`;
}

export function connectionEditor(panel,plan) {
  const rooms=panel.data.config.rooms,ids=Object.keys(plan.zones).filter(id=>rooms[id]);
  const links=roomConnections(panel.data.config).filter(pair=>pair.some(id=>ids.includes(id)));
  const choices=Object.values(rooms).map(room=>`<option value="${esc(room.id)}">${esc(room.name)}</option>`).join("");
  return `<details class="plan-connections"${panel._doorMode?" open":""}><summary>Türen / Raumverbindungen · ${links.length}</summary><p>Markiere direkte Türen oder offene Durchgänge. Verbundene Räume können sich bei passenden Sensorereignissen gegenseitig bestätigen. Eine Kette über weitere Räume zählt nicht als direkte Verbindung. Die Linien erscheinen nur hier im Editor.</p><div class="row" style="margin-top:12px"><button type="button" class="${panel._doorMode?"primary":""}" data-command="door-mode" aria-pressed="${Boolean(panel._doorMode)}" data-config>${panel._doorMode?"Markieren beenden":"Im Grundriss markieren"}</button>${panel._doorMode?`<strong role="status">${panel._doorFrom?`${esc(rooms[panel._doorFrom]?.name)} gewählt – zweiten Raum anklicken`:"Ersten und danach zweiten Raum anklicken"}</strong>`:""}</div><div class="form-grid" style="margin-top:14px"><label class="field">Von Raum<select id="door-from" data-config><option value="">Raum auswählen</option>${choices}</select></label><label class="field">Zu Raum<select id="door-to" data-config><option value="">Raum auswählen</option>${choices}</select></label></div><button type="button" class="small" data-command="door-add" style="margin-top:12px" data-config>Tür / Durchgang verbinden</button><div class="checks" style="margin-top:14px">${links.map(([a,b])=>`<div class="row between"><span>${esc(rooms[a].name)} ↔ ${esc(rooms[b].name)}</span><button type="button" class="small danger" data-command="door-remove" data-from="${esc(a)}" data-to="${esc(b)}" aria-label="Verbindung ${esc(rooms[a].name)} – ${esc(rooms[b].name)} entfernen" data-config>Entfernen</button></div>`).join("")||"<p>Noch keine Raumverbindungen eingetragen.</p>"}</div><p>Weitere Bedingungen der Levelregel, Zeitfenster und Prell-Schutz gelten weiterhin. Es werden keine Türen aus berührenden Raumflächen oder alten Nachbarschaftsangaben erraten.</p></details>`;
}

export const TOPOLOGY_CSS=`
.plan-image-controls{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:14px}
.plan-image-controls label{flex:1;min-width:180px}.plan-image-controls input[type=range]{padding:0;accent-color:var(--iq-accent)}
.plan-connections{margin-top:18px;padding:14px;border:1px solid var(--iq-border);border-radius:12px}
.plan-connections summary{cursor:pointer;font-weight:650}
.plan-wrap .door-mark{pointer-events:none}.plan-wrap .door-selected .room-badge{stroke:#fbbf24;stroke-width:4}
`;
