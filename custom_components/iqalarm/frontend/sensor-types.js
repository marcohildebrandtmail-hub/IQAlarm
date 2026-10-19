/* Input interpretation is independent of display names and custom symbols. */
export const SENSOR_TYPES={
  entry_contact:"Öffnungskontakt · Tür / Fenster / Tor",
  lock_contact:"Türschloss / Riegel",
  window_handle:"Fenstergriff · Information",
  interior_motion:"Bewegungsmelder",
  motion_change:"Bewegung bei Zustandswechsel (15 s)",
  interior_mmwave:"Präsenz / mmWave",
  perimeter_camera:"Außenkamera · Person",
  perimeter_sensor:"Vorfeld-Sensor",
  vibration_glass:"Glas / Vibration",
  panic:"Panik",
  smoke:"Rauch / Gefahr",
};
export function sensorType(sensor) {
  return sensor.activation_mode==="change"?"motion_change":sensor.sensor_kind==="window_handle"?"window_handle":sensor.role;
}
export function setSensorType(config,id,value) {
  if(!value)return;
  const sensor=config.sensors[id];
  if(!sensor||!Object.hasOwn(SENSOR_TYPES,value))throw Error("Unbekannte Sensorart.");
  if(sensorType(sensor)===value)return;
  const room=sensor.room_id||sensor.front_of?.[0]||null;
  const role=value==="motion_change"?"interior_motion":value==="window_handle"?"lock_contact":value;
  Object.assign(sensor,{role,activation_mode:value==="motion_change"?"change":"state",sensor_kind:value==="window_handle"?"window_handle":role==="lock_contact"?"door_lock":"generic"});
  if(!role.startsWith("perimeter")){sensor.front_of=[];sensor.room_id=room;}
  if(!["entry_contact","lock_contact","vibration_glass"].includes(role))sensor.entry_delay=false;
  if(value==="motion_change"){sensor.immediate=false;sensor.debounce_ms=0;}
}
export function sensorTypeField(sensor,escape) {
  if(sensor.window_id)return "";
  const selected=sensorType(sensor);
  return `<label class="field" style="margin-top:14px">Art<select name="sensor_type" aria-label="Art">${Object.entries(SENSOR_TYPES).map(([value,label])=>`<option value="${value}"${value===selected?" selected":""}>${escape(label)}</option>`).join("")}</select><small>Bei „Bewegung bei Zustandswechsel“ zählt Auf → Zu ebenso wie Zu → Auf. Jeder Wechsel startet die 15 Sekunden neu; dauerhaft offen zählt dabei nicht als Öffnungswarnung.</small></label>`;
}
