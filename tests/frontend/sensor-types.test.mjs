import test from "node:test";
import assert from "node:assert/strict";
import {sensorType,setSensorType,sensorTypeField,sensorTypeChoices,SENSOR_TYPES,sensorListGroup,isSensorInput} from "../../custom_components/iqalarm/frontend/sensor-types.js";

function config() {
  return {sensors:{door:{entity_id:"binary_sensor.door",name:"Innentür",role:"entry_contact",sensor_kind:"generic",room_id:"sophie",source_id:"device:door",active_states:["on"],front_of:[],entry_delay:true,immediate:true,debounce_ms:500,icon:"mdi:door-closed"}}};
}
test("inner-door motion conversion keeps identity, source, room and symbol",()=>{
  const c=config();setSensorType(c,"door","motion_change");const s=c.sensors.door;
  assert.equal(s.role,"interior_motion");assert.equal(s.activation_mode,"change");assert.equal(s.sensor_kind,"generic");
  assert.equal(s.room_id,"sophie");assert.equal(s.source_id,"device:door");assert.equal(s.icon,"mdi:door-closed");
  assert.equal(s.immediate,false);assert.equal(s.entry_delay,false);assert.equal(s.debounce_ms,0);
  assert.equal(sensorType(s),"motion_change");
});
test("returning to a contact restores state evaluation without changing its HA input",()=>{
  const c=config();setSensorType(c,"door","motion_change");setSensorType(c,"door","entry_contact");
  assert.equal(c.sensors.door.activation_mode,"state");assert.equal(sensorType(c.sensors.door),"entry_contact");
  assert.equal(c.sensors.door.entity_id,"binary_sensor.door");assert.deepEqual(c.sensors.door.active_states,["on"]);
});
test("an unchanged type and composite window retain their existing interpretation",()=>{
  const c=config(),before=structuredClone(c);setSensorType(c,"door","entry_contact");assert.deepEqual(c,before);
  assert.equal(sensorTypeField({window_id:"w"},String),"");
  assert.throws(()=>setSensorType(c,"door","nonexistent"),/Sensorart/);
});
test("the current pulse interpretation is selected in the settings field",()=>{
  const c=config();setSensorType(c,"door","motion_change");
  const html=sensorTypeField(c.sensors.door,String);
  assert.match(html,/name="sensor_type" aria-label="Art"/);assert.match(html,/value="motion_change" selected/);
  assert.match(html,/15 Sekunden/);
});

test("light switches use edge motion and stay in the trigger list",()=>{
  const c=config();setSensorType(c,"door","light_switch");
  assert.equal(c.sensors.door.role,"interior_motion");assert.equal(c.sensors.door.activation_mode,"change");
  assert.equal(sensorType(c.sensors.door),"light_switch");assert.equal(sensorListGroup(c.sensors.door),"trigger");
  assert.equal(sensorListGroup({role:"interior_motion",activation_mode:"state"}),"inside");
  assert.equal(sensorListGroup({role:"perimeter_sensor"}),"outside");
  assert.equal(sensorListGroup({role:"perimeter_camera"}),"camera");
  for(const kind of ["interior_mmwave","vibration_glass","panic","smoke"])assert.equal(SENSOR_TYPES[kind],undefined);
});

test("event switches use press events while lamp and relay outputs cannot become inputs",()=>{
  const c=config();c.sensors.door.entity_id="event.hue_wall_switch_module_14_button_1";
  setSensorType(c,"door","light_switch");
  assert.equal(c.sensors.door.activation_mode,"press");
  assert.equal(sensorListGroup(c.sensors.door),"trigger");
  assert.throws(()=>setSensorType(c,"door","motion_change"),/Tastenereignisse/);
  for(const domain of ["light","switch"]){
    const a=config();a.sensors.door.entity_id=`${domain}.flur`;
    assert.throws(()=>setSensorType(a,"door","light_switch"),/physischen Eingang/);
    assert.equal(isSensorInput(a.sensors.door),false);
  }
  assert.equal(isSensorInput(c.sensors.door),true);
  assert.equal(isSensorInput({entity_id:"event.repairs",setup_required:true}),false);
  assert.equal(isSensorInput({entity_id:"binary_sensor.licht_flur_og_input_0_input"}),true);
});

for(const role of ["interior_mmwave","vibration_glass","panic","smoke"])test(`saved legacy type ${role} survives unchanged assignment but allows explicit conversion`,()=>{
  const c=config();c.sensors.door.role=role;
  const before=structuredClone(c);
  assert.match(sensorTypeField(c.sensors.door,String),new RegExp(`value="${role}" selected`));
  setSensorType(c,"door",role);
  assert.deepEqual(c,before);
  assert.equal(SENSOR_TYPES[role],undefined);
  assert.equal(sensorTypeChoices("entry_contact")[role],undefined);
  assert.throws(()=>setSensorType(config(),"door",role),/Sensorart/);
  setSensorType(c,"door","interior_motion");
  assert.equal(c.sensors.door.role,"interior_motion");
  assert.equal(c.sensors.door.source_id,before.sensors.door.source_id);
  assert.deepEqual(c.sensors.door.active_states,before.sensors.door.active_states);
});
