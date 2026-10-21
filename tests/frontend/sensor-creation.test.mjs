import test from "node:test";
import assert from "node:assert/strict";
import {createSensor,suggestedSensorType} from "../../custom_components/iqalarm/frontend/sensor-types.js";

const source={entity_id:"binary_sensor.door",name:"Haustür",role:"entry_contact",active_states:["on"],source_id:"device:door"};
const fields={name:" Meine Tür ",type:"entry_contact",roomId:"hall"};

test("a simple assignment keeps the real signal format and physical identity with automatic protection defaults",()=>{
  const raw={...source,active_states:["open","tilted"],attribute:"opening",active_above:2};
  const before=structuredClone(raw),saved=createSensor(raw,fields);
  assert.equal(saved.name,"Meine Tür");assert.equal(saved.room_id,"hall");assert.equal(saved.source_id,"device:door");
  assert.deepEqual(saved.active_states,["open","tilted"]);assert.equal(saved.attribute,"opening");assert.equal(saved.active_above,2);
  assert.equal(saved.enabled,true);assert.equal(saved.flap_enabled,true);assert.equal(saved.flap_threshold,3);assert.equal(saved.flap_window,15);
  assert.equal(saved.debounce_ms,0);assert.equal(saved.entry_delay,false);assert.equal(saved.immediate,false);
  assert.deepEqual(raw,before);saved.active_states.push("other");assert.deepEqual(raw,before);
});

test("the selected interpretation controls contacts, lock contacts, information and motion pulses",()=>{
  for(const [type,role,kind,mode] of [
    ["entry_contact","entry_contact","generic","state"],
    ["lock_contact","lock_contact","door_lock","state"],
    ["window_handle","lock_contact","window_handle","state"],
    ["interior_motion","interior_motion","generic","state"],
    ["motion_change","interior_motion","generic","change"],
    ["light_switch","interior_motion","light_switch","change"],
    ["perimeter_camera","perimeter_camera","generic","state"],
    ["perimeter_sensor","perimeter_sensor","generic","state"],
  ]){
    const saved=createSensor(source,{...fields,type});
    assert.equal(saved.role,role);assert.equal(saved.sensor_kind,kind);assert.equal(saved.activation_mode,mode);
  }
  assert.throws(()=>createSensor(source,{...fields,roomId:""}),/Raum/);
  assert.equal(createSensor(source,{...fields,type:"perimeter_sensor",roomId:""}).room_id,null);
});

test("button sources retain their real event values and MQTT device trigger automatically",()=>{
  const trigger={platform:"device",domain:"mqtt",device_id:"bd3c8cf65bec9038a01fe8a92b811feb",type:"action",subtype:"single_left"};
  const event={...source,entity_id:"event.button",sensor_kind:"light_switch",activation_mode:"press",active_states:["single_left"],device_trigger:trigger};
  const saved=createSensor(event,{...fields,type:"light_switch"});
  assert.equal(saved.activation_mode,"press");assert.deepEqual(saved.active_states,["single_left"]);assert.deepEqual(saved.device_trigger,trigger);
  assert.notEqual(saved.device_trigger,trigger);
  assert.equal(suggestedSensorType(event,"inside"),"light_switch");
  assert.throws(()=>createSensor(event,fields),/Tastenereignisse/);
  assert.throws(()=>createSensor({...source,entity_id:"light.lamp"},fields),/Home Assistant/);
});

test("verified camera attributes work without technical form fields; streaming alone cannot be mistaken for a person",()=>{
  const camera={...source,entity_id:"camera.door",attribute:"person_count",active_above:0};
  const saved=createSensor(camera,{...fields,type:"perimeter_camera"});
  assert.equal(saved.attribute,"person_count");assert.equal(saved.active_above,0);assert.equal(saved.camera_entity_id,"camera.door");
  assert.throws(()=>createSensor({...camera,attribute:null},fields),/Personen-Sensor/);
  assert.throws(()=>createSensor({...camera,setup_required:true},fields),/Personen-Sensor/);
  assert.throws(()=>createSensor(undefined,fields),/auswählen/);
});

test("category defaults and device information propose the intended treatment",()=>{
  for(const [group,type] of [["camera","perimeter_camera"],["outside","perimeter_sensor"],["inside","interior_motion"],["contact","entry_contact"],["trigger","motion_change"]])assert.equal(suggestedSensorType(source,group),type);
  assert.equal(suggestedSensorType({...source,entity_id:"lock.door",role:"lock_contact"},"contact"),"lock_contact");
  assert.equal(suggestedSensorType({...source,name:"Fenstergriff"},"contact"),"window_handle");
  assert.equal(suggestedSensorType({...source,role:"interior_mmwave"}),"interior_motion");
  assert.equal(suggestedSensorType({...source,role:"perimeter_camera"}),"perimeter_camera");
  assert.equal(suggestedSensorType({...source,role:"perimeter_sensor"}),"perimeter_sensor");
});
