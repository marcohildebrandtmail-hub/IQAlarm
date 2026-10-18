import test from "node:test";
import assert from "node:assert/strict";
import {sourceMembers,renderSourceMembers} from "../../custom_components/iqalarm/frontend/rule-sources.js";

function setup() {
  const sensors={
    "binary_sensor.person":{entity_id:"binary_sensor.person",name:"Terrasse <Person>",role:"perimeter_camera",front_of:["living"],enabled:true},
    "binary_sensor.person2":{entity_id:"binary_sensor.person2",name:"Einfahrt",role:"perimeter_camera",front_of:["hall"],enabled:false},
    "binary_sensor.frame":{entity_id:"binary_sensor.frame",name:"Fensterkontakt",role:"entry_contact",room_id:"living"},
    "lock.handle":{entity_id:"lock.handle",role:"lock_contact",sensor_kind:"window_handle",room_id:"living"},
    "binary_sensor.window":{entity_id:"binary_sensor.window",role:"entry_contact",room_id:"living",window_id:"w"},
  };
  return {_connected:true,data:{config:{rooms:{living:{name:"Wohnzimmer"},hall:{name:"Flur"}}},status:{raw:{"binary_sensor.person":true,"binary_sensor.person2":false,"binary_sensor.window":null},quarantine:{}}},_allSensorRecords:()=>sensors,_displaySensors:()=>Object.values(sensors).filter(s=>s.entity_id!=="binary_sensor.frame")};
}
test("role groups resolve actual entities, deduplicate explicit choices and explain exclusions",()=>{
  const panel=setup(),condition={roles:["perimeter_camera","entry_contact","lock_contact"],sensor_ids:["binary_sensor.person"]};
  const members=sourceMembers(panel,condition,["living"]);
  assert.equal(members.filter(m=>m.id==="binary_sensor.person").length,1);
  assert.equal(members.find(m=>m.id==="binary_sensor.person").state,"Person erkannt");
  assert.equal(members.find(m=>m.id==="binary_sensor.person2").reason,"Sensor isoliert");
  assert.equal(members.find(m=>m.id==="lock.handle").reason,"Nur Information · keine Alarmquelle");
  assert.equal(members.find(m=>m.id==="binary_sensor.window").state,"Keine Verbindung");
  assert.equal(members.some(m=>m.id==="binary_sensor.frame"),false);
  assert.equal(sourceMembers(panel,{roles:["perimeter_camera"],sensor_ids:[]},["hall"]).find(m=>m.id==="binary_sensor.person").reason,"Außerhalb der Raumbegrenzung dieser Regel");
  assert.match(renderSourceMembers(panel,condition),/Terrasse &lt;Person&gt;/);
  assert.match(renderSourceMembers(panel,condition),/binary_sensor.person/);
});
test("connection loss clears active indicators and missing explicit entities remain visible",()=>{
  const panel=setup();panel._connected=false;
  const members=sourceMembers(panel,{roles:["perimeter_camera"],sensor_ids:["binary_sensor.missing"]});
  assert.equal(members.some(m=>m.active),false);
  assert.equal(members.every(m=>m.state==="Live-Verbindung unterbrochen"),true);
  assert.equal(members.find(m=>m.id==="binary_sensor.missing").reason,"Entität nicht mehr zugeordnet");
});
