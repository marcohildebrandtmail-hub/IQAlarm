import test from "node:test";
import assert from "node:assert/strict";
import {iconField, roomSymbol, sensorSymbol, symbolHTML} from "../../custom_components/iqalarm/frontend/display-icons.js";

let Panel;
globalThis.HTMLElement = class {};
globalThis.customElements = {get(){return undefined;},define(name,value){if(name === "iqalarm-panel")Panel=value;}};
await import("../../custom_components/iqalarm/frontend/iqalarm-panel.js");

test("per-object symbols override role defaults and unsafe values never become markup",()=>{
  assert.equal(sensorSymbol({role:"interior_motion",icon:"mdi:fridge-outline"}),"mdi:fridge-outline");
  assert.equal(sensorSymbol({role:"interior_motion",icon:null}),"mdi:motion-sensor");
  assert.equal(sensorSymbol({role:"lock_contact"}),"mdi:lock");
  assert.equal(roomSymbol({icon:"mdi:stove"}),"mdi:stove");
  assert.equal(roomSymbol(),"mdi:floor-plan");
  assert.doesNotMatch(symbolHTML('mdi:x" onload="bad'),/onload/);
  assert.doesNotMatch(iconField('<script>',"mdi:floor-plan"),/<script>/);
});

test("changing and resetting a composite window symbol affects no raw source or alarm metadata",()=>{
  const panel=Object.create(Panel.prototype);
  panel.data={config:{sensors:{"binary_sensor.frame":{entity_id:"binary_sensor.frame",role:"entry_contact",room_id:"r"}},windows:{w:{id:"w",room_id:"r",name:"Fenster",enabled:true,entry_delay:true}}}};
  const config=structuredClone(panel.data.config);
  panel._setDisplayIcon(config,"binary_sensor.iqalarm_window_w"," mdi:door-closed ");
  assert.deepEqual(config.windows.w,{...panel.data.config.windows.w,icon:"mdi:door-closed"});
  assert.deepEqual(config.sensors,panel.data.config.sensors);
  panel.data.config=config;
  assert.equal(panel._sensorRecord("binary_sensor.iqalarm_window_w").icon,"mdi:door-closed");
  panel._setDisplayIcon(config,"binary_sensor.iqalarm_window_w","");
  assert.equal(config.windows.w.icon,null);
  assert.throws(()=>panel._setDisplayIcon(config,"binary_sensor.frame","bad"),/MDI/);
});
