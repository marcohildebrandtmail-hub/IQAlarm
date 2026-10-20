import test from "node:test";
import assert from "node:assert/strict";
import {liveTriggers,triggerRows} from "../../custom_components/iqalarm/frontend/live-view.js";

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
