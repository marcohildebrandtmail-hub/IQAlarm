import test from "node:test";
import assert from "node:assert/strict";
import {sensorType,setSensorType,sensorTypeField} from "../../custom_components/iqalarm/frontend/sensor-types.js";

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
