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
