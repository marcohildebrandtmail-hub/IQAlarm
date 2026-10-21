/* Input interpretation is independent of display names and custom symbols. */
export const SENSOR_TYPES={
  entry_contact:"Öffnungskontakt · Tür / Fenster / Tor",
  lock_contact:"Türschloss / Riegel",
  window_handle:"Fenstergriff · Information",
  interior_motion:"Bewegungsmelder innen",
  light_switch:"Lichtschalter · Bewegung bei Betätigung (15 s)",
  motion_change:"Bewegung bei Zustandswechsel (15 s)",
  perimeter_camera:"Außenkamera · Person",
  perimeter_sensor:"Bewegungsmelder außen",
};
const LEGACY_SENSOR_TYPES={interior_mmwave:"Präsenz / mmWave",vibration_glass:"Glas / Vibration",panic:"Panik",smoke:"Rauch / Gefahr"};
export function sensorTypeChoices(current,choices=SENSOR_TYPES) {
  // Keep only this sensor's saved legacy value; do not offer retired types for new assignments.
  return !current||Object.hasOwn(choices,current)?choices:{[current]:LEGACY_SENSOR_TYPES[current]||current,...choices};
}
export function sensorType(sensor) {
  return sensor.sensor_kind==="light_switch"?"light_switch":sensor.activation_mode==="change"?"motion_change":sensor.sensor_kind==="window_handle"?"window_handle":sensor.role;
}
export function setSensorType(config,id,value) {
  if(!value)return;
  const sensor=config.sensors[id];
  if(!sensor)throw Error("Unbekannte Sensorart.");
  if(sensorType(sensor)===value)return;
  if(!Object.hasOwn(SENSOR_TYPES,value))throw Error("Unbekannte Sensorart.");
  if(value==="light_switch"&&!/^(event|binary_sensor)\./.test(sensor.entity_id))throw Error("Lichtschalter benötigt ein Tastenereignis oder einen physischen Eingang.");
  if(sensor.entity_id.startsWith("event.")&&value!=="light_switch")throw Error("Tastenereignisse benötigen die Geräteart Lichtschalter.");
  const room=sensor.room_id||sensor.front_of?.[0]||null;
  const role=["motion_change","light_switch"].includes(value)?"interior_motion":value==="window_handle"?"lock_contact":value;
  Object.assign(sensor,{role,activation_mode:value==="light_switch"&&sensor.entity_id.startsWith("event.")?"press":["motion_change","light_switch"].includes(value)?"change":"state",sensor_kind:value==="light_switch"?"light_switch":value==="window_handle"?"window_handle":role==="lock_contact"?"door_lock":"generic"});
  if(!role.startsWith("perimeter")){sensor.front_of=[];sensor.room_id=room;}
  if(!["entry_contact","lock_contact","vibration_glass"].includes(role))sensor.entry_delay=false;
  if(["motion_change","light_switch"].includes(value)){sensor.immediate=false;sensor.debounce_ms=0;}
}

export function isSensorInput(entity) {
  const domain=entity.entity_id.split(".")[0];
  return domain==="event"?entity.sensor_kind==="light_switch"&&!entity.setup_required:["binary_sensor","lock","camera","image_processing","sensor","input_boolean","input_select","select","cover"].includes(domain);
}

export function suggestedSensorType(source,group=null,perimeter=false) {
  if(source?.sensor_kind==="light_switch"||source?.entity_id?.startsWith("event."))return "light_switch";
  if(group==="trigger")return "motion_change";
  const id=source?.entity_id||"",name=`${source?.name||""} ${id}`;
  if((!group||group==="contact")&&/fenstergriff|window.?handle/i.test(name))return "window_handle";
  if((!group||group==="contact")&&(id.startsWith("lock.")||source?.role==="lock_contact"))return "lock_contact";
  const preset={camera:"perimeter_camera",outside:"perimeter_sensor",inside:"interior_motion",contact:"entry_contact"}[group];
  if(preset)return preset;
  if(id.startsWith("camera.")||id.startsWith("image_processing.")||source?.role==="perimeter_camera"||/person|kamera|camera/i.test(name))return "perimeter_camera";
  if(perimeter)return "perimeter_sensor";
  if(source?.role==="interior_mmwave")return "interior_motion";
  return Object.hasOwn(SENSOR_TYPES,source?.role)?source.role:/motion|bewegung|presence|präsenz|pir/i.test(name)?"interior_motion":"entry_contact";
}

export function createSensor(source,{name,type,roomId}) {
  if(!source||!isSensorInput(source))throw Error("Bitte einen vorhandenen Sensor aus Home Assistant auswählen.");
  if(source.setup_required)throw Error(source.entity_id.startsWith("camera.")||source.entity_id.startsWith("image_processing.")?"Bitte den zugehörigen Personen-Sensor der Kamera auswählen.":"Dieses Signal kann noch nicht automatisch ausgewertet werden. Bitte einen passenden Sensor auswählen.");
  const id=source.entity_id;
  const sensor={entity_id:id,name:name.trim()||source.name||id,role:"entry_contact",sensor_kind:"generic",activation_mode:"state",room_id:roomId||null,front_of:[],source_id:source.source_id||id,enabled:true,flap_enabled:true,flap_threshold:3,flap_window:15,debounce_ms:0,entry_delay:false,immediate:false,attribute:source.attribute||null,active_above:source.active_above??null,active_states:structuredClone(source.active_states||["on"]),camera_entity_id:null,icon:null,device_trigger:null};
  setSensorType({sensors:{[id]:sensor}},id,type);
  if(!sensor.role.startsWith("perimeter")&&!sensor.room_id)throw Error("Bitte einen Raum für den Sensor auswählen.");
  if(source.device_trigger){
    if(sensor.activation_mode!=="press")throw Error("Tastenereignisse benötigen die Geräteart Lichtschalter.");
    sensor.device_trigger=structuredClone(source.device_trigger);
  }
  if(/^(camera|image_processing)\./.test(id)){
    if(!sensor.attribute)throw Error("Bitte den zugehörigen Personen-Sensor der Kamera auswählen.");
    if(sensor.role==="perimeter_camera")sensor.camera_entity_id=id;
  }
  return sensor;
}
export function sensorTypeField(sensor,escape) {
  if(sensor.window_id)return "";
  const selected=sensorType(sensor);
  return `<label class="field" style="margin-top:14px">Art<select name="sensor_type" aria-label="Art">${Object.entries(sensorTypeChoices(selected)).map(([value,label])=>`<option value="${escape(value)}"${value===selected?" selected":""}>${escape(label)}</option>`).join("")}</select><small>Bei „Bewegung bei Zustandswechsel“ zählt Auf → Zu ebenso wie Zu → Auf. Jeder Wechsel startet die 15 Sekunden neu; dauerhaft offen zählt dabei nicht als Öffnungswarnung.</small></label>`;
}

export function sensorListGroup(sensor) {
  if(sensor.role==="perimeter_camera")return "camera";
  if(sensor.role==="perimeter_sensor")return "outside";
  if(sensor.activation_mode==="change"||sensor.sensor_kind==="light_switch")return "trigger";
  if(["entry_contact","lock_contact"].includes(sensor.role)||sensor.window_id||sensor.sensor_kind==="window_handle")return "contact";
  return "inside";
}
