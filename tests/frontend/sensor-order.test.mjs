import test from "node:test";
import assert from "node:assert/strict";

let Panel;
globalThis.HTMLElement = class {};
globalThis.customElements = {get(){return undefined;},define(name,value){if(name==="iqalarm-panel")Panel=value;}};
await import("../../custom_components/iqalarm/frontend/iqalarm-panel.js");

function setup() {
  const panel=Object.create(Panel.prototype);
  panel.data={config:{settings:{sensor_order:{k:["binary_sensor.iqalarm_window_w","binary_sensor.b"]}},sensors:{
    "binary_sensor.a":{entity_id:"binary_sensor.a",room_id:"k",front_of:[]},
    "binary_sensor.b":{entity_id:"binary_sensor.b",room_id:"k",front_of:[]},
    "binary_sensor.other":{entity_id:"binary_sensor.other",room_id:"r",front_of:[]},
    "binary_sensor.shared":{entity_id:"binary_sensor.shared",room_id:null,front_of:["k","r"]},
  },windows:{w:{id:"w",room_id:"k",enabled:true,handle_entity_ids:[]}}}};
  return panel;
}
test("saved room order mixes composite windows and raw sensors, appending new entries",()=>{
  const panel=setup();
  assert.deepEqual(panel._orderedSensors("k").map(s=>s.entity_id),["binary_sensor.iqalarm_window_w","binary_sensor.b","binary_sensor.a","binary_sensor.shared"]);
  assert.deepEqual(panel._orderedSensors("r").map(s=>s.entity_id),["binary_sensor.other","binary_sensor.shared"]);
});
test("placing a sensor before or after another preserves every other group",()=>{
  const panel=setup(),config=structuredClone(panel.data.config);
  config.settings.sensor_order.r=["binary_sensor.shared","binary_sensor.other"];
  panel._placeSensor(config,"binary_sensor.a","k","binary_sensor.iqalarm_window_w");
  assert.deepEqual(config.settings.sensor_order.k,["binary_sensor.a","binary_sensor.iqalarm_window_w","binary_sensor.b","binary_sensor.shared"]);
  assert.deepEqual(config.settings.sensor_order.r,["binary_sensor.shared","binary_sensor.other"]);
  panel.data.config=config;
  panel._placeSensor(config,"binary_sensor.a","k","binary_sensor.b",true);
  assert.deepEqual(config.settings.sensor_order.k,["binary_sensor.iqalarm_window_w","binary_sensor.b","binary_sensor.a","binary_sensor.shared"]);
});
test("choosing the current room retains order and every perimeter association",async()=>{
  const panel=setup();
  panel.data.status={active:false};
  panel.data.config.sensors["binary_sensor.shared"].role="perimeter_camera";
  const before=structuredClone(panel.data.config);
  panel.shadowRoot={getElementById(){return {close(){}};}};
  panel._toast=()=>{};panel._render=()=>{};
  panel._call=async(type,{config})=>({config,status:{active:false}});
  await panel._moveSensor("binary_sensor.shared","k");
  assert.deepEqual(panel.data.config,before);
});
test("room selection saves the new activity interpretation together with the sensor settings",async()=>{
  const panel=setup();panel.data.status={active:false};
  Object.assign(panel.data.config.sensors["binary_sensor.b"],{role:"entry_contact",sensor_kind:"generic",entry_delay:true});
  panel.shadowRoot={getElementById(){return {close(){}};}};
  panel._toast=()=>{};panel._render=()=>{};
  panel._call=async(type,{config})=>({config,status:{active:false}});
  await panel._moveSensor("binary_sensor.b","r","Innentür",1,null,false,"mdi:door-closed","motion_change");
  const saved=panel.data.config.sensors["binary_sensor.b"];
  assert.equal(saved.room_id,"r");assert.equal(saved.name,"Innentür");assert.equal(saved.role,"interior_motion");
  assert.equal(saved.activation_mode,"change");assert.equal(saved.entry_delay,false);assert.equal(saved.icon,"mdi:door-closed");
});
