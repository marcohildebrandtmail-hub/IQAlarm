import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";

// Serve only the panel modules. These display tests never connect to Home Assistant.
test.beforeEach(async({page})=>{
  await page.route("http://127.0.0.1/room-badge-test",route=>route.fulfill({
    contentType:"text/html; charset=utf-8",
    body:'<script type="module" src="/iqalarm-static/iqalarm-panel.js"></script><body style="margin:0"><iqalarm-panel></iqalarm-panel></body>',
  }));
  await page.route("http://127.0.0.1/iqalarm-static/**",async route=>{
    const name=new URL(route.request().url()).pathname.split("/").pop();
    if(!/^[a-z-]+\.js$/.test(name))return route.abort();
    await route.fulfill({contentType:"application/javascript; charset=utf-8",body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.clock.install({time:new Date("2026-10-19T10:00:00Z")});
  await page.goto("http://127.0.0.1/room-badge-test");
  await page.waitForFunction(()=>customElements.get("iqalarm-panel"));
});

for(const width of [1440,390])test(`room badge and sensor row expire together without a new message at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.locator("iqalarm-panel").evaluate(panel=>{
    panel.data={
      config:{secure_stage_id:"secure",stages:[{id:"off",name:"Aus"},{id:"secure",name:"Sicher",color:"#60b720"},{id:"outside",name:"Bewegung Außen",color:"#00c000"}],
        rooms:{roof:{id:"roof",name:"Garagendach"}},windows:{},settings:{recent_seconds:30},
        sensors:{"binary_sensor.motion":{entity_id:"binary_sensor.motion",name:"Bewegung",role:"perimeter_sensor",room_id:"roof",enabled:true}},
        level_rules:{perimeter:{window_seconds:180}}},
      status:{active:true,raw:{"binary_sensor.motion":true},last_active:{"binary_sensor.motion":Date.now()/1000},quarantine:{},
        monitored_sensors:["binary_sensor.motion"],rooms:{roof:{level:2,confirmed:false}}},
    };
    panel.tab=0;
    panel.shadowRoot.getElementById("main").innerHTML=panel._roomLive(panel.data.config.rooms.roof);
  });
  const state=page.locator('[data-sensor-state-id="binary_sensor.motion"]'),badge=page.locator('[data-room-badge="roof"]');
  await expect(state).toHaveText("Aktiv");
  await expect(badge).toHaveText("Bewegung Außen");
  await page.clock.fastForward(181000);
  await expect(state).toHaveText("Aktiv");
  await expect(badge).toHaveText("Bewegung Außen");

  await page.locator("iqalarm-panel").evaluate(panel=>{
    panel.data.status.raw["binary_sensor.motion"]=false;
    panel.data.status.last_active["binary_sensor.motion"]=Date.now()/1000;
    panel._updateSensorStatuses();
  });
  await page.clock.fastForward(29000);
  await expect(state).toHaveText("Kürzlich");
  await expect(badge).toHaveText("Bewegung Außen");
  await page.clock.fastForward(2000);
  await expect(state).toHaveText("Ruhig");
  await expect(badge).toHaveText("Sicher");
  expect(await page.locator("iqalarm-panel").evaluate(panel=>({
    roomLevel:panel.data.status.rooms.roof.level,
    window:panel.data.config.level_rules.perimeter.window_seconds,
    color:panel.shadowRoot.querySelector('[data-live-key="room-roof"]').style.getPropertyValue("--level-color"),
  }))).toEqual({roomLevel:2,window:180,color:"#60b720"});
  expect(errors).toEqual([]);
});

for(const width of [1440,390])test(`two rooms show overlapping activity and expire independently at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.locator("iqalarm-panel").evaluate(panel=>{
    panel.data={
      config:{secure_stage_id:"secure",stages:[{id:"off",name:"Aus"},{id:"secure",name:"Sicher"},{id:"outside",name:"Bewegung Außen"}],
        rooms:{roof:{id:"roof",name:"Garagendach"},garden:{id:"garden",name:"Garten Büroseite"}},windows:{},settings:{recent_seconds:30},
        sensors:{
          "binary_sensor.roof_motion":{entity_id:"binary_sensor.roof_motion",name:"Bewegung",role:"perimeter_sensor",room_id:"roof",enabled:true},
          "binary_sensor.garden_motion":{entity_id:"binary_sensor.garden_motion",name:"Bewegung Lagerplatz",role:"perimeter_sensor",room_id:"garden",enabled:true},
        }},
      status:{active:true,raw:{"binary_sensor.roof_motion":false,"binary_sensor.garden_motion":false},
        last_active:{"binary_sensor.roof_motion":Date.now()/1000,"binary_sensor.garden_motion":Date.now()/1000-15},quarantine:{},
        monitored_sensors:["binary_sensor.roof_motion","binary_sensor.garden_motion"],rooms:{roof:{level:2,confirmed:false},garden:{level:2,confirmed:false}}},
    };
    panel.tab=0;
    panel.shadowRoot.getElementById("main").innerHTML=Object.values(panel.data.config.rooms).map(room=>panel._roomLive(room)).join("");
  });
  const roof=page.locator('[data-live-key="room-roof"]'),garden=page.locator('[data-live-key="room-garden"]');
  for(const room of [roof,garden]){
    await expect(room.locator(".sensor-state")).toHaveText("Kürzlich");
    await expect(room.locator("[data-room-badge]")).toHaveText("Bewegung Außen");
  }
  await page.clock.fastForward(16000);
  await expect(garden.locator(".sensor-state")).toHaveText("Ruhig");
  await expect(garden.locator("[data-room-badge]")).toHaveText("Sicher");
  await expect(roof.locator(".sensor-state")).toHaveText("Kürzlich");
  await expect(roof.locator("[data-room-badge]")).toHaveText("Bewegung Außen");
  await page.clock.fastForward(15000);
  await expect(roof.locator(".sensor-state")).toHaveText("Ruhig");
  await expect(roof.locator("[data-room-badge]")).toHaveText("Sicher");
  expect(errors).toEqual([]);
});
