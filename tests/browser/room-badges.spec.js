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

for(const width of [1440,390])test(`armed recognition fades to turquoise at the same deadline as its level at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.clock.resume();
  await page.locator('iqalarm-panel').evaluate(panel=>{
    const plan={id:'eg',name:'Erdgeschoss',width:400,height:300,image:null,zones:{hall:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
    const now=Date.now()/1000;
    panel.tab=0;panel._connected=true;panel.catalog={entities:[],areas:[]};
    panel.data={config:{secure_stage_id:'secure',stages:[{id:'off',name:'Aus',color:'#ffffff'},{id:'secure',name:'Sicher',color:'#60b720'},{id:'outside',name:'Bewegung Außen',color:'#0000ff'}],
      profiles:{},robots:{},actions:{},rules:{},rooms:{hall:{id:'hall',name:'Garagenhof'}},windows:{},floorplans:{eg:plan},settings:{recent_seconds:30,floorplan_armed_animation:false},
      sensors:{'binary_sensor.motion':{entity_id:'binary_sensor.motion',name:'Bewegung',room_id:'hall',role:'perimeter_sensor',enabled:true}}},information:[],windows:{},window_details:{},
      status:{active:true,profile_id:'away',profile_name:'Abwesend',level:2,stage_id:'outside',stage_name:'Bewegung Außen',raw:{'binary_sensor.motion':false},last_active:{'binary_sensor.motion':now-100},quarantine:{},
        monitored_sensors:['binary_sensor.motion'],rule_progress:[],rooms:{hall:{level:2,confirmed:false,motion:[],open:[],persons:[],quarantined:[],
          recognitions:[{stage_id:'outside',level:2,confirmed:false,event:'active',expires_at:now+4,sources:[{entity_id:'binary_sensor.motion',role:'perimeter_sensor'}]}]}}}};
    panel._render();
    panel.__heldShape=panel.shadowRoot.querySelector('g[data-room="hall"]:not([data-label-room]) polygon:nth-of-type(2)');
  });
  const shape=page.locator('g[data-room="hall"]:not([data-label-room]) polygon').nth(1),label=page.locator('[data-label-room="hall"]'),ring=page.locator('.status-rings');
  await expect(label).toContainText('Bewegung erkannt');
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 2');
  await expect(shape).toHaveCSS('fill','rgb(245, 158, 11)');
  await expect.poll(()=>shape.evaluate(node=>getComputedStyle(node).fill),{timeout:3500,intervals:[60]}).not.toBe('rgb(245, 158, 11)');
  expect(await shape.evaluate(node=>getComputedStyle(node).fill)).not.toBe('rgb(20, 184, 166)');
  await expect(label).toContainText('Bewegung erkannt');
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 2');
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 1',{timeout:2200});
  await expect(label).not.toContainText('Bewegung erkannt');
  await expect(shape).toHaveCSS('fill','rgb(20, 184, 166)');
  expect(await page.locator('iqalarm-panel').evaluate(panel=>panel.__heldShape===panel.shadowRoot.querySelector('g[data-room="hall"]:not([data-label-room]) polygon:nth-of-type(2)'))).toBe(true);
});

for(const width of [1440,390])test(`disarmed correlation cannot retain a red floorplan after motion expires at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.locator("iqalarm-panel").evaluate(panel=>{
    const plan={id:"eg",name:"Erdgeschoss",width:400,height:300,image:null,zones:{hall:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
    panel.tab=0;
    panel.data={
      config:{rooms:{hall:{id:"hall",name:"Flur UG"}},windows:{},floorplans:{eg:plan},settings:{floorplan_disarmed_motion:true},
        sensors:{"binary_sensor.motion":{entity_id:"binary_sensor.motion",room_id:"hall",role:"interior_motion",enabled:true}}},
      information:[],
      status:{active:false,raw:{"binary_sensor.motion":false},last_active:{"binary_sensor.motion":Date.now()/1000},quarantine:{},
        rooms:{hall:{level:5,confirmed:true,motion:[],open:[],persons:[],quarantined:[]}}},
    };
    panel.shadowRoot.getElementById("main").innerHTML=panel._renderPlanSvg(plan,true,false,true).svg;
  });
  const room=page.locator('g[data-room="hall"]:not([data-label-room]) polygon').nth(1);
  const label=page.locator('[data-label-room="hall"]');
  await expect(room).toHaveAttribute("fill","#ef4444");
  await expect(label).toContainText("Bewegung");
  await page.clock.fastForward(16000);
  await expect(label).not.toContainText("Bewegung");
  await expect(label).not.toContainText("Bestätigter Alarm");
  await expect(room).toHaveAttribute("fill","#14b8a6");
  // Actual armed confirmations still retain their explicit red alarm display.
  await page.locator("iqalarm-panel").evaluate(panel=>{panel.data.status.active=true;panel._refreshFloorplanStatuses();});
  await expect(room).toHaveAttribute("fill","#ef4444");
  await expect(label).toContainText("Bestätigter Alarm");
});

for(const width of [1440,390])for(const route of ["render","timer"])test(`motion stays continuous with HA clock ahead on ${route} at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.locator("iqalarm-panel").evaluate(panel=>{
    const plan={id:"eg",name:"Erdgeschoss",width:400,height:300,image:null,zones:{hall:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
    const now=Date.now()/1000;
    panel.tab=0;panel._connected=true;panel.catalog={entities:[],areas:[]};
    panel.data={
      config:{secure_stage_id:"secure",stages:[{id:"off",name:"Aus"},{id:"secure",name:"Sicher"}],
        profiles:{},robots:{},actions:{},rules:{},rooms:{hall:{id:"hall",name:"Flur UG"}},windows:{},floorplans:{eg:plan},settings:{recent_seconds:30,floorplan_disarmed_motion:true},
        sensors:{"binary_sensor.motion":{entity_id:"binary_sensor.motion",name:"Bewegung Flur",room_id:"hall",role:"interior_motion",enabled:true}}},
      information:[],windows:{},window_details:{},
      status:{server_time:now+.075,active:false,profile_id:null,level:0,stage_id:"off",stage_name:"Aus",raw:{"binary_sensor.motion":true},last_active:{"binary_sensor.motion":now+.08},quarantine:{},
        monitored_sensors:["binary_sensor.motion"],rooms:{hall:{level:0,confirmed:false,motion:["binary_sensor.motion"],open:[],persons:[],quarantined:[]}}},
    };
    panel._render();
    panel.__clockShape=panel.shadowRoot.querySelector('g[data-room="hall"]:not([data-label-room]) polygon:nth-of-type(2)');
  });
  await page.clock.fastForward(2000);
  const immediate=await page.locator("iqalarm-panel").evaluate((panel,route)=>{
    const now=Date.now()/1000,previous=panel.data.status;
    panel.data={...panel.data,status:{...previous,server_time:now+.075,raw:{"binary_sensor.motion":false},last_active:{"binary_sensor.motion":now+.08},
      rooms:{hall:{...previous.rooms.hall,motion:[]}}}};
    if(route==="render")panel._render();else{panel._updateSensorStatuses();panel._refreshFloorplanStatuses();}
    return {sensor:panel.shadowRoot.querySelector('[data-sensor-state-id="binary_sensor.motion"]').textContent,
      text:panel.shadowRoot.querySelector('[data-label-room="hall"]').textContent,
      color:panel.__clockShape.getAttribute("fill"),connected:panel.__clockShape.isConnected};
  },route);
  expect(immediate).toEqual({sensor:"Kürzlich",text:"Flur UGBewegung",color:"#ef4444",connected:true});
  const state=page.locator('[data-sensor-state-id="binary_sensor.motion"]'),label=page.locator('[data-label-room="hall"]');
  for(const step of [100,900,13000]){
    await page.clock.fastForward(step);
    await expect(state).toHaveText("Kürzlich");
    await expect(label).toContainText("Bewegung");
  }
  await page.clock.fastForward(2000);
  await expect(label).not.toContainText("Bewegung");
  await expect(page.locator('g[data-room="hall"]:not([data-label-room]) polygon').nth(1)).toHaveAttribute("fill","#14b8a6");
  await page.clock.fastForward(15000);
  await expect(state).toHaveText("Ruhig");
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
