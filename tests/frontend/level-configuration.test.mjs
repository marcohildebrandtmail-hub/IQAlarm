import test from "node:test";
import assert from "node:assert/strict";
import {actionsForProfile,ruleSummary} from "../../custom_components/iqalarm/frontend/level-configuration.js";

test("profile stage lists contain only the selected mode's own or explicitly shared actions",()=>{
  const config={actions:{n:{id:"n",level:"2",profile_ids:["night"]},a:{id:"a",level:"2",profile_ids:["away"]},shared:{id:"shared",level:"2",profile_ids:["night","away"]},other:{id:"other",level:"3",profile_ids:["night"]},unused:{id:"unused",level:"2",profile_ids:[]}}};
  assert.deepEqual(actionsForProfile(config,"night","2").map(a=>a.id),["n","shared"]);
  assert.deepEqual(actionsForProfile(config,"away","2").map(a=>a.id),["a","shared"]);
});
test("rule explanations preserve source requirements, temporal order and actual timing",()=>{
  const panel={_sensorRecord(id){return {name:id==="binary_sensor.person"?"Terrasse Person":"Fenster"};}};
  const rule={conditions:[{sensor_ids:["binary_sensor.person"],roles:[],count:1,event:"active"},{sensor_ids:["binary_sensor.frame"],roles:[],count:1,event:"active"}],ordered:true,window_seconds:30,delay_seconds:5};
  const explanation=ruleSummary(panel,rule);
  assert.match(explanation,/Terrasse Person/);assert.match(explanation,/→/);assert.match(explanation,/30 s/);assert.match(explanation,/Verzögerung 5 s/);
});
