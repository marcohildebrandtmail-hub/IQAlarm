import {test,expect} from "@playwright/test";

async function ws(page,type,args={}){return page.evaluate(({type,args})=>window.iqTest.request({type:`iqalarm/${type}`,...args}),{type,args});}
async function save(page,config){const current=await ws(page,"get");return ws(page,"config/save",{config,revision:current.config.revision});}
async function state(page,id,value){return page.locator("iqalarm-panel").evaluate(async(el,{id,value})=>{const r=await el.hass.fetchWithAuth(`/api/states/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:value})});if(!r.ok)throw Error("Cannot set disposable state");},{id,value});}
const originals=new WeakMap(),planIds=new WeakMap();
const ids={contact:"binary_sensor.geometry_contact",b:"binary_sensor.geometry_motion_b",c:"binary_sensor.geometry_motion_c"};

test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  let data=await ws(page,"get");if(data.status.active)data=await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  originals.set(page,structuredClone(data.config));
  for(const id of Object.values(ids))await state(page,id,"off");
  data.config.rooms={a:{id:"a",name:"Küche",adjacent:[]},b:{id:"b",name:"Wohnzimmer",adjacent:[]},c:{id:"c",name:"Büro",adjacent:[]}};
  data.config.sensors={};data.config.windows={};data.config.floorplans={};data.config.room_connections=[];data.config.actions={};
  data.config.secure_stage_id=data.config.stages[0].id;
  data.config.sensors[ids.contact]={entity_id:ids.contact,role:"entry_contact",room_id:"a"};
  for(const room of ["b","c"])data.config.sensors[ids[room]]={entity_id:ids[room],role:"interior_motion",room_id:room};
  data.config.rules={door_pair:{id:"door_pair",name:"Öffnung und passende Bewegung",stage_id:data.config.stages.at(-1).id,conditions:[{sensor_ids:[ids.contact],roles:[],count:1,event:"active"},{sensor_ids:[ids.b,ids.c],roles:[],count:1,event:"active"}],window_seconds:60}};
  data.config.profiles={qa_door:{name:"Türtest",rule_ids:["door_pair"],reactions_enabled:true,exit_seconds:0,sensor_ids:Object.values(ids)}};
  data.config.settings.observation_profile_id="live";
  await save(page,data.config);
  const upload=await page.locator("iqalarm-panel").evaluate(async el=>{
    const canvas=document.createElement("canvas");canvas.width=1800;canvas.height=1000;
    const ctx=canvas.getContext("2d");ctx.fillStyle="#ffffff";ctx.fillRect(0,0,1800,1000);ctx.strokeStyle="#456789";ctx.lineWidth=8;ctx.strokeRect(990,450,630,250);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
    const response=await el.hass.fetchWithAuth('/api/iqalarm/floorplans/upload?name=QA%20Grundriss',{method:"POST",headers:{"Content-Type":"image/png","X-IQAlarm-Revision":String(el.data.config.revision)},body:blob});
    if(!response.ok)throw Error("Disposable image upload failed");return response.json();
  });
  const id=upload.uploaded_plan_id;planIds.set(page,id);
  const current=await ws(page,"get");current.config.floorplans[id].zones={a:[[.55,.45],[.66,.45],[.66,.7],[.55,.7]],b:[[.67,.45],[.78,.45],[.78,.7],[.67,.7]],c:[[.79,.45],[.9,.45],[.9,.7],[.79,.7]]};
  await save(page,current.config);await page.reload();await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  await expect(page.locator(`[data-plan-underlay="${id}"]`)).toHaveAttribute("href",/^blob:/);
});
test.afterEach(async({page})=>{
  const original=originals.get(page);if(!original)return;
  const data=await ws(page,"get");if(data.status.active)await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  await save(page,original);
});

test("cropped preview and live frame follow room geometry on desktop and mobile",async({page})=>{
  const id=planIds.get(page),svg=page.locator(`#floorplan-${id}`);
  await expect(svg).toBeVisible();
  const viewBox=await svg.getAttribute("viewBox");
  const bounds=await svg.evaluate(el=>{const box=el.viewBox.baseVal,rect=el.getBoundingClientRect();return{x:box.x,y:box.y,w:box.width,h:box.height,ratio:rect.width/rect.height};});
  expect(bounds.x).toBeGreaterThan(800);expect(bounds.y).toBeGreaterThan(300);
  expect(bounds.w).toBeLessThan(800);expect(bounds.h).toBeLessThan(400);
  expect(bounds.ratio).toBeCloseTo(bounds.w/bounds.h,2);
  const geometry=structuredClone((await ws(page,"get")).config.floorplans[id].zones);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator('[data-command="toggle-graphic-preview"]').first().click();
  await expect(page.locator("#floorplan")).toHaveAttribute("viewBox",viewBox);
  await page.setViewportSize({width:390,height:844});await page.locator("#floorplan").scrollIntoViewIfNeeded();
  const clipped=await page.locator("#floorplan").evaluate(el=>{const frame=el.getBoundingClientRect();return [...el.querySelectorAll('.room-label-group')].some(label=>{const b=label.getBoundingClientRect();return b.left<frame.left-1||b.right>frame.right+1||b.top<frame.top-1||b.bottom>frame.bottom+1;});});
  expect(clipped).toBe(false);
  expect((await ws(page,"get")).config.floorplans[id].zones).toEqual(geometry);
  await page.screenshot({path:"test-results/cropped-floorplan-mobile.png",fullPage:true});
});

test("opacity is configured only in room settings and the live page displays the saved result",async({page})=>{
  const id=planIds.get(page),slider=page.getByRole("slider",{name:"Originalbild einblenden QA Grundriss"});
  const before=(await ws(page,"get")).config.floorplans[id];
  await expect(slider).toHaveCount(0);
  await expect(page.getByRole("button",{name:"Bildanzeige speichern",exact:true})).toHaveCount(0);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator('[data-command="toggle-graphic-preview"]').first().click();
  await expect(slider).toHaveValue("0");
  await slider.evaluate(el=>{el.value="25";el.dispatchEvent(new Event("input",{bubbles:true}));});
  await expect(page.locator("#floorplan [data-plan-underlay]")).toHaveCSS("opacity","0.25");
  await page.getByRole("button",{name:"Bildanzeige speichern",exact:true}).click();
  await expect.poll(async()=>(await ws(page,"get")).config.floorplans[id].image_opacity).toBe(.25);
  await page.reload();
  await expect(page.locator(`#floorplan-${id} [data-plan-underlay]`)).toHaveCSS("opacity","0.25");
  await expect(slider).toHaveCount(0);
  await expect(page.getByRole("button",{name:"Bildanzeige speichern",exact:true})).toHaveCount(0);
  const saved=(await ws(page,"get")).config.floorplans[id];
  expect(saved.image).toBe(before.image);expect(saved.zones).toEqual(before.zones);expect(saved.labels).toEqual(before.labels);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator('[data-command="toggle-graphic-preview"]').first().click();
  await expect(slider).toHaveValue("25");
});

test("explicit doors allow direct corroboration but never a second-hop room and stay hidden live",async({page})=>{
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator('.plan-connections summary').click();
  await page.getByRole("button",{name:"Im Grundriss markieren",exact:true}).click();
  for(const [index,pair] of [["a","b"],["b","c"]].entries()){
    const first=page.locator(`#floorplan [data-label-room="${pair[0]}"]`);await first.focus();await page.keyboard.press("Enter");
    await expect(first).toHaveClass(/door-selected/);
    await page.locator(`#floorplan [data-label-room="${pair[1]}"]`).focus();await page.keyboard.press("Enter");
    await expect.poll(async()=>(await ws(page,"get")).config.room_connections.length).toBe(index+1);
  }
  await expect.poll(async()=>(await ws(page,"get")).config.room_connections.length).toBe(2);
  await expect(page.locator('#floorplan [data-door-link]')).toHaveCount(2);
  await page.getByRole("button",{name:"Markieren beenden",exact:true}).click();
  await page.locator('[data-command="toggle-graphic-preview"]').first().click();
  await expect(page.locator('#floorplan [data-door-link]')).toHaveCount(0);
  await page.getByRole("tab",{name:"Live-Status"}).click();
  await expect(page.locator('[data-door-link]')).toHaveCount(0);
  await ws(page,"set_mode",{mode:"qa_door"});
  await state(page,ids.contact,"on");await state(page,ids.c,"on");
  expect((await ws(page,"get")).status.confirmed).toBe(false);
  await state(page,ids.b,"on");await expect.poll(async()=>(await ws(page,"get")).status.confirmed).toBe(true);
  await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  await page.reload();await page.getByRole("tab",{name:"Räume & Grundriss"}).click();await page.locator('.plan-connections summary').click();
  await page.getByRole("button",{name:/Verbindung Küche – Wohnzimmer entfernen/}).click();
  await expect.poll(async()=>(await ws(page,"get")).config.room_connections.length).toBe(1);
});
