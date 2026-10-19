import test from "node:test";
import assert from "node:assert/strict";
import {ringValues,statusRings} from "../../custom_components/iqalarm/frontend/live-view.js";
const data={config:{stages:Array(6).fill({})},status:{level:2,stage_id:"outside",stage_name:"Bewegung Außen",rule_progress:[]}};
test("level and confirmation rings have independent normalized progress",()=>{
  for(const n of [1,2,3]){
    const state=structuredClone(data);state.status.rule_progress=[{stage_id:"outside",current:n,target:3}];
    const values=ringValues(state);assert.equal(values.level,2/5);assert.equal(values.confirmation,n/3);
    const html=statusRings(state);assert.match(html,/data-level-ring/);assert.match(html,/data-confirmation-ring/);assert.match(html,new RegExp(`Bestätigungsgrad ${n} von 3`));
  }
});
test("inactive baseline and stages without a grade never invent confirmation",()=>{
  const state=structuredClone(data);state.status.level=0;
  assert.equal(ringValues(state).level,0);assert.equal(ringValues(state).confirmation,0);
  assert.doesNotMatch(statusRings(state),/class="grade-caption"/);
});
test("a different level's complete rule does not fill the current inner ring",()=>{
  const state=structuredClone(data);state.status.rule_progress=[{stage_id:"other",current:3,target:3},{stage_id:"outside",current:1,target:3}];
  assert.equal(ringValues(state).confirmation,1/3);
});
test("secure baseline shows coverage risk without inventing an intrusion confirmation",()=>{
  const state=structuredClone(data);
  Object.assign(state.config,{secure_stage_id:"secure",robots:{vacuum:{enabled:true}}});
  Object.assign(state.status,{level:1,stage_id:"secure",profile_id:"night",coverage:{current:2,target:3}});
  const values=ringValues(state),html=statusRings(state);
  assert.equal(values.level,1/5);assert.equal(values.grade.kind,"coverage");assert.equal(values.confirmation,2/3);
  assert.match(html,/data-risk-ring/);assert.match(html,/Überwachungsrisiko 2 von 3/);
  assert.doesNotMatch(html,/data-confirmation-ring|Bestätigungsgrad/);
});
test("higher levels keep their actual confirmation grade even with reduced coverage",()=>{
  const state=structuredClone(data);
  Object.assign(state.config,{secure_stage_id:"secure",robots:{vacuum:{enabled:true}}});
  Object.assign(state.status,{profile_id:"night",coverage:{current:3,target:3},rule_progress:[{stage_id:"outside",current:1,target:3}]});
  assert.equal(ringValues(state).confirmation,1/3);
  assert.match(statusRings(state),/Bestätigungsgrad 1 von 3/);assert.doesNotMatch(statusRings(state),/data-risk-ring/);
});
test("disarmed or disabled exceptions do not add a coverage ring",()=>{
  const state=structuredClone(data);
  Object.assign(state.config,{secure_stage_id:"secure",robots:{vacuum:{enabled:true}}});
  Object.assign(state.status,{level:0,stage_id:"secure",profile_id:null,coverage:{current:3,target:3}});
  assert.equal(ringValues(state).grade,null);
  state.status.profile_id="night";state.config.robots.vacuum.enabled=false;
  assert.equal(ringValues(state).grade,null);
});
test("automatically ignored windows show risk on the baseline without any robot configuration",()=>{
  const state=structuredClone(data);
  Object.assign(state.config,{secure_stage_id:"secure",robots:{}});
  Object.assign(state.status,{level:1,stage_id:"secure",profile_id:"night",ignored_windows:["window"],coverage:{current:1,target:3}});
  assert.equal(ringValues(state).grade.kind,"coverage");
  assert.match(statusRings(state),/Überwachungsrisiko 1 von 3/);assert.doesNotMatch(statusRings(state),/Bestätigungsgrad/);
});
