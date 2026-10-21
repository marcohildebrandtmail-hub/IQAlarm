/* Directed links between an outdoor area and its indoor rooms. */
import {roomVisualCenter} from "./floorplan-rooms.js?v=2.15.0";
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export function setOutsideInside(config,outside,inside) {
  if(!config.rooms[outside])throw Error("Bitte einen vorhandenen Außenbereich wählen.");
  if(inside.some(id=>id===outside||!config.rooms[id]))throw Error("Außenbereich und Innenraum müssen verschieden und vorhanden sein.");
  const result=structuredClone(config);
  result.outside_inside_links=(result.outside_inside_links||[]).filter(pair=>pair[0]!==outside);
  result.outside_inside_links.push(...[...new Set(inside)].map(id=>[outside,id]));
  return result;
}

export function insideRoomChoices(config,outside) {
  if(!config.rooms[outside])return '<p>Wähle zuerst einen Außenbereich.</p>';
  const selected=new Set((config.outside_inside_links||[]).filter(pair=>pair[0]===outside).map(pair=>pair[1]));
  return Object.values(config.rooms).filter(room=>room.id!==outside).map(room=>`<label class="check"><input type="checkbox" name="inside_rooms" value="${esc(room.id)}"${selected.has(room.id)?" checked":""}><span>${esc(room.name)}</span></label>`).join("");
}

export function renderOutsideInside(panel) {
  const c=panel.data.config,selected=c.rooms[panel._outsideArea]?panel._outsideArea:"";
  const links=(c.outside_inside_links||[]).filter(pair=>pair.every(id=>c.rooms[id]));
  return `<section class="card" style="margin-top:18px" data-outside-inside><h2>Außen → Innen</h2><p>Welche Innenräume gehören zu welchem Außenbereich? Die Zuordnung gilt für die Kameras und Außensensoren dieses Bereichs, zum Beispiel Terrasse → Wohnzimmer und Küche.</p><form id="outside-inside-form"><fieldset data-config><label class="field" style="margin-top:14px">Außenbereich<select id="outside-area" name="outside_room" aria-label="Außenbereich" required><option value="">Außenbereich auswählen</option>${Object.values(c.rooms).map(room=>`<option value="${esc(room.id)}"${room.id===selected?" selected":""}>${esc(room.name)}</option>`).join("")}</select></label><h3 style="margin-top:16px">Zugehörige Innenräume</h3><div class="checks" data-inside-rooms style="margin-top:12px">${insideRoomChoices(c,selected)}</div><div class="save-row"><button type="submit" class="primary">Zuordnung speichern</button></div></fieldset></form><details style="margin-top:16px"><summary>Gespeicherte Zuordnungen · ${links.length}</summary><div class="checks" style="margin-top:12px">${links.map(([a,b])=>`<div class="row between"><span style="min-width:0;overflow-wrap:anywhere">${esc(c.rooms[a].name)} → ${esc(c.rooms[b].name)}</span><button type="button" class="small danger" data-command="outside-inside-remove" data-from="${esc(a)}" data-to="${esc(b)}" aria-label="Zuordnung ${esc(c.rooms[a].name)} → ${esc(c.rooms[b].name)} löschen" data-config>Löschen</button></div>`).join("")||"<p>Noch keine Außen-/Innen-Zuordnungen eingetragen.</p>"}</div></details><p>Zuordnungen lassen sich direkt in der Liste löschen oder über die Auswahl ändern. Tatsächliche Türen und Durchgänge werden weiterhin unter „Türen / Raumverbindungen“ im Grundriss-Editor eingestellt.</p></section>`;
}

export function outsideInsideControls(panel) {
  const source=panel.data.config.rooms[panel._outsideArea];
  return `<div class="row" style="margin-top:14px"><button type="button" class="${panel._outsideInsideMode?"primary":""}" data-command="outside-inside-mode" aria-pressed="${Boolean(panel._outsideInsideMode)}" data-config>${panel._outsideInsideMode?"Außen-/Innen-Markieren beenden":"Außen → Innen markieren"}</button>${panel._outsideInsideMode?`<span role="status">${source?`${esc(source.name)} gewählt – zugehörige Innenräume anklicken. Erneuter Klick entfernt die Zuordnung.`:"Zuerst den Außenbereich anklicken, danach die zugehörigen Innenräume."}</span>`:""}</div>`;
}

export function outsideInsideSVG(config,plan,zones) {
  const links=(config.outside_inside_links||[]).filter(pair=>pair.every(id=>zones[id]));
  if(!links.length)return "";
  const marker=`outside-arrow-${plan.id}`;
  return `<g class="outside-inside-marks" style="pointer-events:none"><defs><marker id="${esc(marker)}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#38bdf8"/></marker></defs>${links.map(([a,b])=>{
    const first=plan.labels?.[a]||roomVisualCenter(zones[a]),second=plan.labels?.[b]||roomVisualCenter(zones[b]);
    return `<line data-outside-inside-link="${esc(a)}:${esc(b)}" x1="${first[0]*plan.width}" y1="${first[1]*plan.height}" x2="${second[0]*plan.width}" y2="${second[1]*plan.height}" stroke="#38bdf8" stroke-width="3" marker-end="url(#${esc(marker)})" vector-effect="non-scaling-stroke"/>`;
  }).join("")}</g>`;
}
