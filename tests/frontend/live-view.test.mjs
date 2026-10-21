import test from "node:test";
import assert from "node:assert/strict";
import {ringValues,statusRings,promotionProgress} from "../../custom_components/iqalarm/frontend/live-view.js";
const data={config:{stages:Array(6).fill({})},status:{level:2,stage_id:"outside",stage_name:"Bewegung Außen",rule_progress:[]}};
test('red overlay follows the authoritative thirty-second deadline on the existing outer ring',()=>{
  const state=structuredClone(data);
  state.config.automatic_detection={stage_id:'inside',promote_seconds:30};
  Object.assign(state.status,{active:true,level:3,stage_id:'inside',rule_progress:[{stage_id:'inside',current:3,target:3,next_level_at:130}]});
  for(const [now,expected] of [[100,0],[107.5,.25],[115,.5],[129,29/30],[130,1]])assert.equal(promotionProgress(state,now),expected);
  const html=statusRings(state,115);
  assert.match(html,/class="promotion-ring" data-promotion-ring/);
  assert.match(html,/data-promotion-ring[^>]*r="61"/);
  assert.doesNotMatch(html,/<progress/);
  state.status.rule_progress[0].next_level_at=null;
  assert.equal(promotionProgress(state,115),null);
  assert.doesNotMatch(statusRings(state,115),/data-promotion-ring/);
  state.status.rule_progress[0].next_level_at=130;
  state.status.active=false;
  assert.equal(promotionProgress(state,115),null);
  state.status.active=true;state.status.stage_id='four';
  assert.equal(promotionProgress(state,115),null);
});
test('simultaneous full indoor areas animate toward the earliest real promotion',()=>{
  const state=structuredClone(data);
  state.config.automatic_detection={stage_id:'inside',promote_seconds:30};
  Object.assign(state.status,{active:true,level:3,stage_id:'inside',rule_progress:[{stage_id:'inside',current:3,target:3,next_level_at:150},{stage_id:'inside',current:3,target:3,next_level_at:130}]});
  assert.equal(promotionProgress(state,115),.5);
});
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
test("disarmed inactive status strictly enforces level 0 and empty rings",()=>{
  const state=structuredClone(data);
  state.status.level=3;
  state.status.active=false;
  state.status.mode="inactive";
  state.status.rule_progress=[{stage_id:"outside",current:2,target:3}];
  const values=ringValues(state);
  assert.equal(values.level,0);
  assert.equal(values.confirmation,0);
  assert.equal(values.grade,null);
  const html=statusRings(state);
  assert.match(html,/<text x="72" y="72">0<\/text>/);
  assert.match(html,/Deaktiviert/);
  assert.doesNotMatch(html,/Bestätigungsgrad/);
  assert.doesNotMatch(html,/grade-caption/);
});

test('LVL 4 uses the existing rings for escalation time instead of x/3',()=>{
  const state=structuredClone(data);
  Object.assign(state.status,{active:true,profile_id:'away',level:4,stage_id:'alarm',stage_name:'Alarm',alarm:{stage_id:'alarm',started_at:100,deadline:400,duration:300,escalated:false}});
  const html=statusRings(state,250);
  assert.match(html,/LVL 5 in 02:30/);
  assert.match(html,/data-promotion-ring/);
  assert.doesNotMatch(html,/Bestätigungsgrad|<progress/);
  assert.equal(promotionProgress(state,250),.5);
  state.status.alarm.escalated=true;
  assert.equal(promotionProgress(state,401),null);
});

test("startup delay fills only the existing red ring and shows the remaining time",()=>{
  const d={config:{settings:{startup_delay_seconds:60},stages:[{name:"Aus"},{name:"Sicher"}]},status:{active:true,profile_id:"away",mode:"active",stage_id:"1",stage_name:"Sicher",level:1,arming_started_at:100,arming_until:160,rule_progress:[]}};
  const html=statusRings(d,130);
  assert.match(html,/data-promotion-ring/);assert.match(html,/Start in 00:30/);
  assert.doesNotMatch(html,/<progress|class="card"/);
  assert.equal(promotionProgress(d,100),0);assert.equal(promotionProgress(d,130),.5);assert.equal(promotionProgress(d,160),1);
  d.status.active=false;assert.equal(promotionProgress(d,130),null);
});
