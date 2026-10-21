import test from "node:test";
import assert from "node:assert/strict";
globalThis.HTMLElement=class {};
globalThis.window={};
globalThis.customElements={get:()=>false,define(){}};
const {cardMarkup}=await import("../../custom_components/iqalarm/frontend/iqalarm-card.js");
const {recognitionDisplayData}=await import("../../custom_components/iqalarm/frontend/live-view.js");

function data(){return {config:{secure_stage_id:"1",settings:{startup_delay_seconds:60},robots:{},stages:["Deaktiviert","Sicher","Umfeld","Verdacht","Alarm","Alarmstufe 2"].map((name,i)=>({id:String(i),name,color:"#081dba"})),automatic_detection:{stage_id:"3",promote_seconds:30}},status:{active:true,mode:"active",profile_id:"away",profile_name:"Abwesend",level:2,stage_id:"2",stage_name:"Umfeld",rule_progress:[{stage_id:"2",current:2,target:3}],rooms:{}}};}

test("card uses the real stage and grade without controls or script markup",()=>{
  const d=data();d.status.profile_name='<img src=x onerror="bad()">';
  const html=cardMarkup(d,100);
  assert.match(html,/Bestätigungsgrad 2\/3/);assert.match(html,/&lt;img/);
  assert.doesNotMatch(html,/<img|<button|<input|<select|<script/);
  assert.equal(window.customCards[0].type,"iqalarm-card");
});
test("disarmed card never shows an old alarm or internal observation grade",()=>{
  const d=data();Object.assign(d.status,{active:false,mode:"inactive",level:5,stage_name:"Alarm",profile_id:null});
  const html=cardMarkup(d,100);
  assert.match(html,/Deaktiviert/);assert.match(html,/>0<\/text>/);
  assert.doesNotMatch(html,/Bestätigungsgrad|>Abwesend</);
});
test("shared timer projection expires reports and returns to the real secure baseline",()=>{
  const d=data(),reports=[{role:"perimeter_camera",entity_id:"binary_sensor.person",timestamp:90,expires_at:110}];
  d.status.rule_progress=[{stage_id:"2",current:1,target:3,person_reports:reports}];
  d.status.rooms={garden:{recognitions:[{level:2,expires_at:110}]}};
  assert.match(cardMarkup(d,109),/Bestätigungsgrad 1\/3/);
  const after=recognitionDisplayData(d,110);
  assert.equal(after.status.level,1);assert.equal(after.status.stage_name,"Sicher");
  assert.equal(after.status.rule_progress.length,0);
  assert.equal(d.status.level,2);assert.equal(d.status.rule_progress.length,1);
});
test("confirmed alarms survive expired room evidence and await backend changes",()=>{
  const d=data();Object.assign(d.status,{level:4,stage_id:"4",stage_name:"Alarm",confirmed:true,rooms:{hall:{recognitions:[{level:4,expires_at:99}]}}});
  assert.equal(recognitionDisplayData(d,100).status.level,4);
});
test("startup, promotion and escalation use the shared red overlay",()=>{
  const d=data();Object.assign(d.status,{level:1,stage_id:"1",stage_name:"Sicher",arming_started_at:100,arming_until:160});
  assert.match(cardMarkup(d,130),/Start in 00:30/);assert.match(cardMarkup(d,130),/data-promotion-ring/);
  Object.assign(d.status,{level:3,stage_id:"3",stage_name:"Verdacht",arming_until:null,rule_progress:[{stage_id:"3",current:3,target:3,next_level_at:160}]});
  assert.match(cardMarkup(d,145),/data-promotion-ring/);
  Object.assign(d.status,{level:4,stage_id:"4",stage_name:"Alarm",alarm:{stage_id:"4",deadline:400,duration:300}});
  assert.match(cardMarkup(d,100),/LVL 5 in 05:00/);
  assert.match(cardMarkup(d,250),/LVL 5 in 02:30/);
  assert.match(cardMarkup(d,401),/>4<\/text>/); // no invented level 5 without backend confirmation
});
test("invalid colors cannot inject attributes and entry delay counts down",()=>{
  const d=data();d.config.stages[2].color='red" onclick="bad()';d.status.pending_until=145;
  const html=cardMarkup(d,100);
  assert.match(html,/Eingangsverzögerung 00:45/);assert.doesNotMatch(html,/onclick/);
});
