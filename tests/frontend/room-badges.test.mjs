import test from "node:test";
import assert from "node:assert/strict";

let Panel;
globalThis.HTMLElement = class {};
globalThis.customElements = {get(){return undefined;},define(name,value){if(name==="iqalarm-panel")Panel=value;}};
await import("../../custom_components/iqalarm/frontend/iqalarm-panel.js");

function setup() {
  const panel=Object.create(Panel.prototype);
  panel.data={
    config:{
      secure_stage_id:"secure",stages:[{id:"off"},{id:"secure",name:"Sicher"},{id:"outside",name:"Bewegung Außen"}],
      rooms:{roof:{id:"roof",name:"Garagendach"}},windows:{},settings:{recent_seconds:30},
      sensors:{"binary_sensor.motion":{entity_id:"binary_sensor.motion",name:"Bewegung",role:"perimeter_sensor",room_id:"roof",enabled:true}},
      level_rules:{perimeter:{window_seconds:180}},
    },
    status:{active:true,raw:{"binary_sensor.motion":false},last_active:{"binary_sensor.motion":100},quarantine:{},
      monitored_sensors:["binary_sensor.motion"],rooms:{roof:{level:2,confirmed:false}}},
  };
  return panel;
}

test("room activity expires at exactly the same time as its last recent sensor",()=>{
  const panel=setup(),sensor=panel.data.config.sensors["binary_sensor.motion"];
  const original=structuredClone(panel.data);
  for(const now of [100,129.999,130]){
    assert.equal(panel._sensorLabel(sensor,true,now),"Kürzlich");
    assert.equal(panel._roomBadgeLevel("roof",undefined,now),2);
  }
  for(const now of [130.001,180,280]){
    assert.equal(panel._sensorLabel(sensor,true,now),"Ruhig");
    assert.equal(panel._roomBadgeLevel("roof",undefined,now),1);
  }
  assert.deepEqual(panel.data,original,"display expiry must not clear engine evidence or change rule timing");
});

test("an active sensor keeps the badge regardless of its activation age",()=>{
  const panel=setup(),sensor=panel.data.config.sensors["binary_sensor.motion"];
  panel.data.status.raw[sensor.entity_id]=true;
  assert.equal(panel._sensorLabel(sensor,true,400),"Aktiv");
  assert.equal(panel._roomBadgeLevel("roof",undefined,400),2);
});

test("another recent sensor in the same room keeps the badge until it too expires",()=>{
  const panel=setup(),id="binary_sensor.person";
  panel.data.config.sensors[id]={entity_id:id,role:"perimeter_camera",room_id:"roof",enabled:true};
  panel.data.status.monitored_sensors.push(id);
  panel.data.status.raw[id]=false;
  panel.data.status.last_active[id]=125;
  assert.equal(panel._roomBadgeLevel("roof",undefined,140),2);
  assert.equal(panel._roomBadgeLevel("roof",undefined,156),1);
});

test("ignored, paused, isolated and unmonitored sensors cannot retain a room activity badge",()=>{
  for(const exclude of [
    panel=>{panel.data.status.ignored_windows=["binary_sensor.motion"];},
    panel=>{panel.data.status.robot_paused_sensors=["binary_sensor.motion"];},
    panel=>{panel.data.config.sensors["binary_sensor.motion"].enabled=false;},
    panel=>{panel.data.status.monitored_sensors=[];},
  ]){
    const panel=setup();
    panel.data.status.raw["binary_sensor.motion"]=true;
    exclude(panel);
    assert.equal(panel._roomBadgeLevel("roof",undefined,105),1);
  }
});

test("a finished contact-as-motion pulse gets no extra recent period",()=>{
  const panel=setup(),sensor=panel.data.config.sensors["binary_sensor.motion"];
  sensor.activation_mode="change";
  assert.equal(panel._sensorLabel(sensor,true,101),"Ruhig");
  assert.equal(panel._roomBadgeLevel("roof",undefined,101),1);
  panel.data.status.raw[sensor.entity_id]=true;
  assert.equal(panel._sensorLabel(sensor,true,101),"Aktiv");
  assert.equal(panel._roomBadgeLevel("roof",undefined,101),2);
});

test("current sensor faults and confirmed alarms are not hidden by quiet sensor expiry",()=>{
  for(const raw of [null,false]){
    const panel=setup();
    panel.data.status.raw["binary_sensor.motion"]=raw;
    if(raw===false)panel.data.status.quarantine["binary_sensor.motion"]={};
    assert.match(panel._sensorLabel(panel.data.config.sensors["binary_sensor.motion"],true,400),/Störung/);
    assert.equal(panel._roomBadgeLevel("roof",undefined,400),2);
  }
  const panel=setup();
  panel.data.status.rooms.roof.confirmed=true;
  assert.equal(panel._roomBadgeLevel("roof",undefined,400),2);
});

test("room fallback follows the configured secure stage rather than a fixed number",()=>{
  const panel=setup();
  panel.data.config.stages.splice(1,0,{id:"custom"});
  panel.data.status.rooms.roof.level=3;
  assert.equal(panel._roomBadgeLevel("roof",undefined,400),2);
});
