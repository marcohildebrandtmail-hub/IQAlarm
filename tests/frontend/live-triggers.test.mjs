import test from "node:test";
import assert from "node:assert/strict";
import {liveTriggers,triggerRows,projectPersonProgress} from "../../custom_components/iqalarm/frontend/live-view.js";

function setup() {
  const data={config:{rooms:{yard:{name:"Garagenhof"},office:{name:"Garten Büroseite"}},sensors:{}},status:{active:true,raw:{},rooms:{yard:{recognitions:[]},office:{recognitions:[]}}}};
  const add=(id,timestamp,expires_at=200,room="yard",name=id)=>{
    data.status.raw[id]=false;
    data.status.rooms[room].recognitions.push({event:"active",expires_at,sources:[{entity_id:id,timestamp,room_id:room,name}]});
  };
  return {data,add};
}

test("shows at most three newest direct sources and merges repeated camera proof",()=>{
  const {data,add}=setup();
  for(const [id,time] of [["old",90],["motion",92],["camera",94],["new",96]])add(id,time);
  add("camera",94,220,"office");
  const items=liveTriggers(data,100);
  assert.deepEqual(items.map(item=>item.entity_id),["new","camera","motion"]);
  assert.equal(items[1].expires_at,220);
});

test("countdown uses recognition expiry and disappears exactly at its deadline",()=>{
  const {data,add}=setup();add("binary_sensor.motion",90,202,"yard","Bewegung");
  assert.match(triggerRows(data,100),/Garagenhof · Bewegung/);
  assert.match(triggerRows(data,100),/noch 01:42/);
  assert.match(triggerRows(data,101),/noch 01:41/);
  assert.match(triggerRows(data,201.9),/noch 00:01/);
  assert.equal(triggerRows(data,202),"");
});

test("ongoing activity and held alarms never invent a countdown",()=>{
  const {data,add}=setup();add("person",90,null);
  data.status.raw.person=true;
  assert.match(triggerRows(data,100),/>Aktiv</);
  data.status.raw.person=false;
  assert.match(triggerRows(data,100),/>Bis Ausschalten</);
  assert.doesNotMatch(triggerRows(data,100),/noch /);
});

test("old, unavailable, ignored and technical reports do not occupy direct trigger slots",()=>{
  const {data,add}=setup();
  add("expired",90,99);add("missing",91);add("ignored",92);add("fault",93);
  data.status.raw.missing=null;data.status.ignored_windows=["ignored"];
  data.status.rooms.yard.recognitions.at(-1).event="unavailable";
  assert.deepEqual(liveTriggers(data,100),[]);
  add("new",101);
  data.status.active=false;
  assert.equal(triggerRows(data,102),"");
});

test("source names are escaped and multiple proofs retain their shared longest lifetime",()=>{
  const {data,add}=setup();add("sensor",90,120,"yard",'<img src=x onerror="alert(1)">');
  add("sensor",89,150);
  assert.equal(liveTriggers(data,100)[0].expires_at,150);
  const html=triggerRows(data,100);
  assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);
});

test("every counted person report has the same expiry in the timer and the ring",()=>{
  const {data,add}=setup();
  add("office_person",100,162,"office");add("terrace_person",110,172,"yard");
  const reports=[{entity_id:"office_person",expires_at:162},{entity_id:"terrace_person",expires_at:172}];
  const progress=[{current:2,target:3,thresholds:[1,2,3],person_reports:reports}];
  assert.equal(projectPersonProgress(progress,120)[0].current,2);
  assert.equal(liveTriggers(data,120).length,2);
  assert.equal(projectPersonProgress(progress,162)[0].current,1);
  assert.deepEqual(liveTriggers(data,162).map(item=>item.entity_id),["terrace_person"]);
  assert.deepEqual(projectPersonProgress(progress,172),[]);
  assert.deepEqual(liveTriggers(data,172),[]);
});

test("repeat reports from one camera retain their individual timers",()=>{
  const {data,add}=setup();add("camera",100,162);add("camera",110,172);
  data.status.rooms.yard.recognitions[0].report_id="camera:100";
  data.status.rooms.yard.recognitions[1].report_id="camera:110";
  const entries=liveTriggers(data,120);
  assert.equal(entries.length,2);
  assert.match(triggerRows(data,120),/noch 00:42/);
  assert.match(triggerRows(data,120),/noch 00:52/);
  assert.equal(liveTriggers(data,162).length,1);
});

function motion(id,room="yard",expires_at=200,source_id=id){
  return {entity_id:id,source_id,room_id:room,role:"perimeter_sensor",timestamp:90,expires_at};
}
function outdoorProgress(motions,persons=[],thresholds=[1,2,3]){
  return [{current:0,target:3,thresholds,person_reports:persons,motion_reports:motions}];
}
function outdoorGrade(motions,persons=[],connections=[],now=100){
  return projectPersonProgress(outdoorProgress(motions,persons),now,connections)[0]?.current||0;
}

test("motion counts independent devices once and caps its contribution at two",()=>{
  assert.equal(outdoorGrade([motion("one")]),0);
  assert.equal(outdoorGrade([motion("one"),motion("one")]),0);
  assert.equal(outdoorGrade([motion("one","yard",200,"device"),motion("two","yard",200,"device")]),0);
  assert.equal(outdoorGrade([motion("one"),motion("two")]),1);
  assert.equal(outdoorGrade([motion("one"),motion("two"),motion("three")]),2);
  assert.equal(outdoorGrade([motion("one"),motion("two"),motion("three"),motion("four")]),2);
  assert.equal(outdoorGrade([motion("one",null),motion("two",null)]),0);
});

test("only directly related motion groups contribute, without pooling separate groups",()=>{
  const a=motion("one","a"),b=motion("two","b"),c=motion("three","c");
  assert.equal(outdoorGrade([a,b]),0);
  assert.equal(outdoorGrade([a,b],[],[["a","b"]]),1);
  assert.equal(outdoorGrade([a,c],[],[["a","b"],["b","c"]]),0);
  assert.equal(outdoorGrade([a,b,c],[],[["a","b"],["b","c"]]),1);
  assert.equal(outdoorGrade([a,b,c],[],[["a","b"],["b","c"],["a","c"]]),2);
  assert.equal(outdoorGrade([a,motion("four","a"),c,motion("five","c")]),1);
});

test("two motion detectors replace one camera report and each expires on its own timer",()=>{
  const motions=[motion("one","a",150),motion("two","b",160)],connections=[["a","b"]];
  const persons=[{entity_id:"camera_one",expires_at:170},{entity_id:"camera_two",expires_at:180}];
  const progress=outdoorProgress(motions,persons);
  assert.equal(projectPersonProgress(progress,100,connections)[0].current,3);
  assert.equal(projectPersonProgress(progress,150,connections)[0].current,2);
  assert.equal(projectPersonProgress(progress,160,connections)[0].current,2);
  assert.equal(projectPersonProgress(progress,170,connections)[0].current,1);
  assert.deepEqual(projectPersonProgress(progress,180,connections),[]);
});

test("three motion detectors need one camera and lose full confirmation when it expires",()=>{
  const motions=[motion("one"),motion("two"),motion("three")];
  const progress=outdoorProgress(motions,[{entity_id:"camera",expires_at:150}]);
  assert.equal(projectPersonProgress(progress,100)[0].current,3);
  const partial=projectPersonProgress(progress,150)[0];
  assert.equal(partial.current,2);assert.equal(partial.complete,false);
  assert.deepEqual(partial.person_reports,[]);
  assert.deepEqual(projectPersonProgress(progress,200),[]);
});

test("custom camera thresholds still govern the camera contribution",()=>{
  const motions=[motion("one"),motion("two")];
  const persons=Array.from({length:4},(_,index)=>({entity_id:`camera${index}`,expires_at:null}));
  for(const [count,current] of [[0,1],[1,1],[2,2],[3,2],[4,3]]){
    assert.equal(projectPersonProgress(outdoorProgress(motions,persons.slice(0,count),[2,4,6]),100)[0].current,current);
  }
});

test("repeat motion uses its latest valid timer without creating another source",()=>{
  const reports=[motion("one","yard",170),motion("one","yard",150),motion("two","yard",180)];
  const progress=outdoorProgress(reports);
  assert.equal(projectPersonProgress(progress,100)[0].current,1);
  assert.equal(projectPersonProgress(progress,100)[0].next_decay,170);
  assert.equal(projectPersonProgress(progress,150)[0].current,1);
  assert.deepEqual(projectPersonProgress(progress,170),[]);
});
