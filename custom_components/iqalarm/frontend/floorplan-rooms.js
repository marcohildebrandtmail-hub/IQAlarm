/* Home Assistant areas are linked only when the user saves a floorplan area. */
const AREA_PREFIX = "ha-area:";
export const areaReference = id => `${AREA_PREFIX}${id}`;

export function roomGroups(rooms, areas) {
  const configured = Object.values(rooms);
  const linked = new Set(configured.map(room => room.area_id).filter(Boolean));
  const sort = items => items.sort((a, b) => a.name.localeCompare(b.name, "de"));
  return [
    {name: "IQAlarm-Räume", items: sort(configured.map(room => ({id: room.id, name: room.name})))},
    {name: "Home-Assistant-Bereiche", items: sort(areas.filter(area => !linked.has(area.id)).map(area => ({id: areaReference(area.id), name: area.name})))},
  ].filter(group => group.items.length);
}

export function hasRoomReference(rooms, areas, reference) {
  return Object.hasOwn(rooms, reference) || areas.some(area => areaReference(area.id) === reference);
}

export function resolveRoom(rooms, areas, reference, newName, createId) {
  const name = newName.trim();
  if (reference && name) throw new Error("Bitte einen vorhandenen Raum wählen oder einen neuen benennen");
  if (!reference && !name) throw new Error("Bitte einen Raum auswählen oder einen Namen eingeben. Dein Entwurf bleibt erhalten.");
  if (reference && Object.hasOwn(rooms, reference)) return {id: reference, room: null};
  const area = reference ? areas.find(item => areaReference(item.id) === reference) : null;
  if (reference && !area) throw new Error("Der gewählte Raum oder Home-Assistant-Bereich wurde entfernt. Dein Entwurf bleibt erhalten.");
  const existing = area && Object.values(rooms).find(room => room.area_id === area.id);
  if (existing) return {id: existing.id, room: null};
  const id = createId();
  return {id, room: {id, name: area ? area.name : name, area_id: area?.id || null, adjacent: [], home_enabled: false}};
}
