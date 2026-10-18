import test from "node:test";
import assert from "node:assert/strict";

let Panel;
globalThis.HTMLElement = class {};
globalThis.customElements = {get(){return undefined;},define(name,value){if(name==="iqalarm-panel")Panel=value;}};
await import("../../custom_components/iqalarm/frontend/iqalarm-panel.js");

function setup(reading, lock = "lock.grip") {
  const panel=Object.create(Panel.prototype);
  panel.data={config:{windows:{w:{id:"w",name:"Fenster",room_id:"r",handle_entity_ids:[],lock_entity_id:lock,enabled:true}},sensors:{},settings:{}},windows:{w:reading},status:{active:false}};
  return panel;
}
for(const [position,lock_state,expected] of [
  ["closed","locked","Geschlossen | Verriegelt"],
  ["closed","unlocked","Geschlossen | Entriegelt"],
  ["open","locked","Offen | Verriegelt"],
  ["tilted","unlocked","Gekippt | Entriegelt"],
  ["closed","unknown","Geschlossen | Unbekannt"],
  ["closed","unlocking","Geschlossen | Wird entriegelt"],
])test(expected,()=>{
  const panel=setup({position,lock_state,available:true});
  assert.equal(panel._sensorLabel({window_id:"w",enabled:true},true),expected);
  panel.data.status.active=true;
  assert.equal(panel._windowLabel("w"),expected);
});
test("missing connections and missing locks remain explicit",()=>{
  assert.equal(setup({available:false,lock_state:"unavailable"})._windowLabel("w"),"Keine Verbindung | Keine Verbindung");
  assert.equal(setup({available:true,position:"closed"},null)._windowLabel("w"),"Geschlossen | Nicht zugeordnet");
  assert.equal(setup({available:true,position:"unknown",label:"Stellung nicht eindeutig",lock_state:"locked"})._windowLabel("w"),"Stellung nicht eindeutig | Verriegelt");
});
test("related actor stays under its window and never replaces a required input",()=>{
  const panel=setup({position:"closed",available:true,lock_state:"locked",inputs:{"lock.grip":"locked"}});
  panel.data.config.sensors["binary_sensor.actor"]={entity_id:"binary_sensor.actor",name:"<Aktor>",sensor_kind:"window_handle",role:"lock_contact"};
  panel.data.window_details={w:[{entity_id:"binary_sensor.actor",name:"<Aktor>",state:"unavailable"}]};
  assert.deepEqual(panel._displaySensors().map(s=>s.entity_id),["binary_sensor.iqalarm_window_w"]);
  assert.match(panel._windowRelatedRows("w"),/&lt;Aktor&gt;/);
  assert.match(panel._windowSourceValue("w","binary_sensor.actor"),/Keine Verbindung/);
  assert.equal(panel._windowLabel("w"),"Geschlossen | Verriegelt");
});
