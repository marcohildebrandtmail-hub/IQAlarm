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

for(const width of [1440,390])test(`coverage details sit inside the status field instead of a separate card at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.tab=0;panel._connected=true;panel.catalog={entities:[],areas:[]};
    panel.data={config:{secure_stage_id:'secure',stages:[{id:'off',name:'Aus',color:'#fff'},{id:'secure',name:'Sicher',color:'#60b720'},{id:'outside',name:'Bewegung Außen',color:'#0000ff'}],
      profiles:Object.fromEntries(['Zuhause','Nacht','Abwesend','Urlaub','Besuch'].map((name,index)=>[`mode${index}`,{name}])),robots:{},actions:{},rules:{},rooms:{},windows:{},floorplans:{},settings:{},sensors:{}},
      information:[],windows:{},window_details:{},status:{active:true,profile_id:'mode2',profile_name:'Abwesend',level:2,stage_id:'outside',stage_name:'Bewegung Außen',raw:{},last_active:{},quarantine:{},ignored_windows:['window'],monitored_sensors:[],rooms:{},rule_progress:[],
        coverage:{current:1,target:3,robots:[],ignored_windows:[{entity_id:'window',name:'Küchenfenster'}]}}};
    panel._render();
  });
  const coverage=page.locator('[data-live-key="robot-coverage"]');
  await expect(page.locator('.hero [data-live-key="robot-coverage"]')).toHaveCount(1);
  await expect(page.locator('#main > [data-live-key="robot-coverage"]')).toHaveCount(0);
  await expect(coverage.locator('.pill')).toBeVisible();
  await expect(coverage).toContainText('Überwachung reduziert');
  const bounds=await coverage.evaluate(node=>{
    const rect=node.getBoundingClientRect(),copy=node.parentElement.querySelector('.hero-copy').getBoundingClientRect(),hero=node.parentElement.getBoundingClientRect();
    return {inside:rect.left>=hero.left&&rect.right<=hero.right&&rect.top>=hero.top&&rect.bottom<=hero.bottom,rightOfCopy:rect.left>=copy.right,overflow:node.getRootNode().host.shadowRoot.querySelector('.shell').scrollWidth>innerWidth};
  });
  expect(bounds.inside).toBe(true);expect(bounds.overflow).toBe(false);
  if(width===1440)expect(bounds.rightOfCopy).toBe(true);
  await coverage.getByText('1 Fenster ignoriert',{exact:true}).click();
  await expect(coverage.getByText('Küchenfenster',{exact:true})).toBeVisible();
  await page.locator('iqalarm-panel').evaluate(panel=>panel._render());
  await expect(coverage.locator('details')).toHaveAttribute('open','');
});

for(const width of [1440,390])test(`person timers and shared grade expire together without a backend refresh at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.locator('iqalarm-panel').evaluate(panel=>{
    const now=Date.now()/1000;
    const reports=[{entity_id:'binary_sensor.office_person',name:'Person Büro',room_id:'office',role:'perimeter_camera',timestamp:now-12,expires_at:now+50},
      {entity_id:'binary_sensor.terrace_person',name:'Person Garten',room_id:'terrace',role:'perimeter_camera',timestamp:now-2,expires_at:now+60}];
    const sensors=Object.fromEntries(reports.map(({expires_at,...source})=>[source.entity_id,{...source,enabled:true}]));
    const rooms=Object.fromEntries(reports.map(report=>[report.room_id,{level:2,confirmed:false,motion:[],open:[],persons:[],quarantined:[],recognitions:[{
      stage_id:'outside',level:2,confirmed:false,event:'active',report_id:`${report.entity_id}:${report.timestamp}`,expires_at:report.expires_at,sources:[report]}]}]));
    panel.tab=0;panel._connected=true;panel.catalog={entities:[],areas:[]};
    panel.data={config:{secure_stage_id:'secure',stages:[{id:'off',name:'Aus',color:'#ffffff'},{id:'secure',name:'Sicher',color:'#60b720'},{id:'outside',name:'Bewegung Außen',color:'#0000ff'}],
      profiles:{},robots:{},actions:{},rules:{},rooms:{office:{id:'office',name:'Garten Büroseite'},terrace:{id:'terrace',name:'Terrasse'}},windows:{},floorplans:{},settings:{floorplan_armed_animation:false},sensors},
      information:[],windows:{},window_details:{},status:{active:true,profile_id:'away',profile_name:'Abwesend',level:2,stage_id:'outside',stage_name:'Bewegung Außen',raw:Object.fromEntries(reports.map(r=>[r.entity_id,false])),last_active:{},quarantine:{},monitored_sensors:Object.keys(sensors),rooms,
      rule_progress:[{rule_id:'person:global',name:'Personenerkennung außen',stage_id:'outside',room_id:null,current:2,target:3,thresholds:[1,2,3],person_reports:reports,sources:reports}]}};
    panel._render();
  });
  const ring=page.locator('.status-rings'),list=page.getByRole('list',{name:'Aktuelle Auslöser',exact:true});
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 2, Bestätigungsgrad 2 von 3');
  await expect(list.getByRole('listitem')).toHaveCount(2);
  await expect(list.locator('.live-trigger-timer')).toHaveText(['noch 01:00','noch 00:50']);
  await page.clock.fastForward(50000);
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 2, Bestätigungsgrad 1 von 3');
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(list).toContainText('Terrasse · Person Garten');
  await expect(list.locator('.live-trigger-timer')).toHaveText('noch 00:10');
  await page.clock.fastForward(10000);
  await expect(ring).toHaveAttribute('aria-label','Alarmstufe 1');
  await expect(list).toBeHidden();
});

for(const width of [1440,390])test(`floorplan header shows three latest triggers with a live countdown at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.locator('iqalarm-panel').evaluate(panel=>{
    const plan={id:'eg',name:'Erdgeschoss',width:400,height:300,image:null,zones:{yard:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
    const now=Date.now()/1000;
    const sensors={},raw={},recognitions=[];
    for(const [index,name] of ['Alte Bewegung','Person Haustür','Bewegung Garagenhof','Person Büroseite'].entries()){
      const id=`binary_sensor.trigger_${index}`;
      sensors[id]={entity_id:id,name,room_id:'yard',role:index%2?'perimeter_camera':'perimeter_sensor',enabled:true};raw[id]=false;
      recognitions.push({stage_id:'outside',level:2,confirmed:false,event:'active',expires_at:now+102,sources:[{entity_id:id,name,role:sensors[id].role,room_id:'yard',timestamp:now-10+index}]});
    }
    panel.tab=0;panel._connected=true;panel.catalog={entities:[],areas:[]};
    panel.data={config:{secure_stage_id:'secure',stages:[{id:'off',name:'Aus',color:'#ffffff'},{id:'secure',name:'Sicher',color:'#60b720'},{id:'outside',name:'Bewegung Außen',color:'#0000ff'}],
      profiles:{},robots:{},actions:{},rules:{},rooms:{yard:{id:'yard',name:'Garagenhof'}},windows:{},floorplans:{eg:plan},settings:{recent_seconds:30,floorplan_armed_animation:false},sensors},
      information:[],windows:{},window_details:{},status:{active:true,profile_id:'away',profile_name:'Abwesend',level:2,stage_id:'outside',stage_name:'Bewegung Außen',raw,last_active:{},quarantine:{},
        monitored_sensors:Object.keys(sensors),rule_progress:[],rooms:{yard:{level:2,confirmed:false,motion:[],open:[],persons:[],quarantined:[],recognitions}}}};
    panel._render();
  });
  const list=page.getByRole('list',{name:'Aktuelle Auslöser',exact:true});
  await expect(list.getByRole('listitem')).toHaveCount(3);
  await expect(list.locator('.live-trigger-name')).toHaveText(['Garagenhof · Person Büroseite','Garagenhof · Bewegung Garagenhof','Garagenhof · Person Haustür']);
  await expect(list.locator('.live-trigger-timer').first()).toHaveText('noch 01:42');
  const layout=await list.evaluate(node=>({inHeader:node.parentElement.classList.contains('live-floorplan-header'),overflows:node.getRootNode().host.shadowRoot.querySelector('.shell').scrollWidth>innerWidth}));
  expect(layout).toEqual({inHeader:true,overflows:false});
  await page.clock.fastForward(1000);
  await expect(list.locator('.live-trigger-timer').first()).toHaveText('noch 01:41');
  await page.clock.fastForward(101000);
  await expect(list).toBeHidden();
  await expect(list.getByRole('listitem')).toHaveCount(0);
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
