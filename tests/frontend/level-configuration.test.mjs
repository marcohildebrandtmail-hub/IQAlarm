import test from "node:test";
import assert from "node:assert/strict";
import {actionsForProfile,ruleSummary,renderHaProfileSettings} from "../../custom_components/iqalarm/frontend/level-configuration.js";

test("HA custom selector offers additional profiles and keeps stable standard associations",()=>{
  const panel={data:{config:{ha_profile_ids:{armed_home:"guests",armed_night:"night",armed_away:"away",armed_vacation:"trip",armed_custom_bypass:"extra2"},profiles:{guests:{name:"Gästeabend"},night:{name:"Nachtschutz"},away:{name:"Unterwegs"},trip:{name:"Reise"},extra1:{name:"Werkstatt"},extra2:{name:"Garage <EG>"},disabled:{name:"Beobachtung",reactions_enabled:false}}}}};
  const html=renderHaProfileSettings(panel);
  assert.match(html,/value="extra2" selected/);assert.match(html,/Garage &lt;EG&gt;/);
  assert.match(html,/value="extra1"/);assert.match(html,/value="disabled" disabled/);
  assert.doesNotMatch(html,/value="guests"|value="night"|value="away"|value="trip"/);
  assert.match(html,/Kein Zusatzprofil ausgewählt/);
});

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
