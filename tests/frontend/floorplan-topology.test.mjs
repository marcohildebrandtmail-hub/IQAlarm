import test from "node:test";
import assert from "node:assert/strict";
import {graphicViewBox} from "../../custom_components/iqalarm/frontend/floorplan-rooms.js";
import {setRoomConnection,roomConnections,imageControls} from "../../custom_components/iqalarm/frontend/floorplan-topology.js";

test("the graphic follows room bounds rather than image size and centers each side equally",()=>{
  const zones={one:[[.55,.4],[.9,.4],[.9,.65],[.55,.65]]},before=structuredClone(zones);
  const box=graphicViewBox(zones,1800,1000);
  assert.equal(box.x>800,true);assert.equal(box.y>300,true);
  assert.equal(box.width<800,true);assert.equal(box.height<400,true);
  assert.ok(Math.abs((990-box.x)-(box.x+box.width-1620))<.001);
  assert.ok(Math.abs((400-box.y)-(box.y+box.height-650))<.001);
  assert.deepEqual(zones,before);
});
test("room edges at the original image boundary still have a symmetric outer margin",()=>{
  const box=graphicViewBox({edge:[[0,0],[.2,0],[.2,.8],[0,.8]]},1000,1000);
  assert.ok(box.x<0&&box.y<0);
  assert.equal(box.width/box.height<.4,true);
});
test("long or repositioned captions remain inside the cropped viewport",()=>{
  const zones={garden:[[.1,.2],[.2,.2],[.2,.8],[.1,.8]]};
  const box=graphicViewBox(zones,1000,1000,{garden:[.01,.5]},{garden:["Garten an der sehr langen Büroseite","Bewegung"]});
  assert.ok(box.x<0);assert.ok(box.x+box.width>200);
  assert.ok(box.y<200&&box.y+box.height>800);
});
test("an explicit physical door is symmetric and independent from old neighborhood metadata",()=>{
  const config={rooms:{a:{id:"a",adjacent:["c"]},b:{id:"b",adjacent:[]},c:{id:"c",adjacent:[]}},room_connections:[],rules:{keep:{paths:[]}}};
  const connected=setRoomConnection(config,"b","a",true);
  assert.deepEqual(roomConnections(connected),[["a","b"]]);
  assert.deepEqual(setRoomConnection(connected,"a","b",true).room_connections,[["a","b"]]);
  assert.deepEqual(setRoomConnection(connected,"b","a",false).room_connections,[]);
  assert.deepEqual(config.room_connections,[]);assert.deepEqual(connected.rules,config.rules);
  assert.deepEqual(connected.rooms.a.adjacent,["c"]);
  assert.throws(()=>setRoomConnection(config,"a","a",true));
  assert.throws(()=>setRoomConnection(config,"a","missing",true));
});
test("opacity controls start hidden for old plans and cannot inject markup through a name",()=>{
  assert.equal(imageControls({id:"one",name:"Empty"},0),"");
  const html=imageControls({id:"one",image:"image.png",name:'<img onerror="bad">'},.25);
  assert.match(html,/value="25"/);assert.doesNotMatch(html,/<img /);
});
