import {test,expect} from "@playwright/test";

async function ws(page,type,data={}){return page.evaluate(({type,data})=>window.iqTest.request({type:`iqalarm/${type}`,...data}),{type,data});}
async function save(page,config){const current=await ws(page,"get");return ws(page,"config/save",{config,revision:current.config.revision});}
async function state(page,id,value){
  await page.locator("iqalarm-panel").evaluate(async(el,{id,value})=>{
    const response=await el.hass.fetchWithAuth(`/api/states/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:value})});
    if(!response.ok)throw Error("Disposable state setup failed");
  },{id,value});
}
test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  let current=await ws(page,"get");
  if(current.status.active)current=await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  await page.evaluate(config=>window.managementOriginal=config,current.config);
});
test.afterEach(async({page})=>{
  const original=await page.evaluate(()=>window.managementOriginal);
  if(original){const current=await ws(page,"get");if(current.status.active)await ws(page,"set_mode",{mode:"inactive",code:"2468"});await save(page,original);}
});

test("sensor settings retain contact-as-motion interpretation when sorting, moving and reloading",async({page})=>{
  const id="binary_sensor.inner_door_activity",other="binary_sensor.inner_door_other";
  for(const key of [id,other])await state(page,key,"off");
  const data=await ws(page,"get");
  data.config.rooms.activity_room={id:"activity_room",name:"Innentür-Test"};
  data.config.rooms.activity_target={id:"activity_target",name:"Innentür-Ziel"};
  for(const [index,key]of [id,other].entries())data.config.sensors[key]={entity_id:key,role:"entry_contact",room_id:"activity_room",name:`Innentür ${index+1}`};
  data.config.settings.sensor_order.activity_room=[id,other];
  await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.locator(`[data-sensor-id="${id}"]`).first().click();
  const dialog=page.getByRole("dialog");
  await expect(dialog.getByRole("heading",{name:"Sensor-Einstellungen",exact:true})).toBeVisible();
  await dialog.getByLabel("Art",{exact:true}).selectOption("motion_change");
  await dialog.getByLabel("Anzeigename",{exact:true}).fill("Innentür als Bewegung");
  await dialog.getByRole("button",{name:"Nach unten",exact:true}).click();
  await expect(dialog.getByLabel("Art",{exact:true})).toHaveValue("motion_change");
  await expect(dialog.getByLabel("Anzeigename",{exact:true})).toHaveValue("Innentür als Bewegung");
  await dialog.getByRole("button",{name:"Innentür-Ziel",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  let saved=(await ws(page,"get")).config.sensors[id];
  expect(saved.role).toBe("interior_motion");expect(saved.activation_mode).toBe("change");expect(saved.room_id).toBe("activity_target");
  await page.reload();await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.locator(`[data-sensor-id="${id}"]`).first().click();
  await expect(dialog.getByLabel("Art",{exact:true})).toHaveValue("motion_change");
  await dialog.getByLabel("Art",{exact:true}).selectOption("entry_contact");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  saved=(await ws(page,"get")).config.sensors[id];
  expect(saved.role).toBe("entry_contact");expect(saved.activation_mode).toBe("state");expect(saved.entity_id).toBe(id);
});

test("room entries reorder by drag and mobile buttons, persist, and delete without deleting HA",async({page})=>{
  const ids=["binary_sensor.order_a","binary_sensor.order_b","binary_sensor.order_c"];
  for(const id of ids)await state(page,id,"off");
  const data=await ws(page,"get");
  data.config.rooms.order_room={id:"order_room",name:"Sortierung"};
  for(const [index,id]of ids.entries())data.config.sensors[id]={entity_id:id,role:"interior_motion",room_id:"order_room",name:`Sortier-Sensor ${index+1}`};
  data.config.profiles.order_profile={...data.config.profiles.armed_night,name:"Sortierprofil",sensor_ids:ids};
  await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  const card=page.locator('[data-drop-room-id="order_room"]');
  const names=card.locator(".sensor-name");
  await expect(names).toHaveText(["Sortier-Sensor 1","Sortier-Sensor 2","Sortier-Sensor 3"]);
  await card.locator(`[data-sensor-id="${ids[2]}"]`).first().dragTo(card.locator(`[data-sensor-id="${ids[0]}"]`).first(),{targetPosition:{x:20,y:2}});
  await expect(names).toHaveText(["Sortier-Sensor 3","Sortier-Sensor 1","Sortier-Sensor 2"]);
  await page.reload();await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await expect(names).toHaveText(["Sortier-Sensor 3","Sortier-Sensor 1","Sortier-Sensor 2"]);
  await page.setViewportSize({width:390,height:844});
  await card.locator(`[data-sensor-id="${ids[1]}"]`).first().click();
  await page.getByRole("dialog").getByRole("button",{name:"Nach oben",exact:true}).click();
  await expect(page.getByRole("dialog").getByText("Reihenfolge: 2 / 3")).toBeVisible();
  await page.getByRole("dialog").getByRole("button",{name:"Abbrechen",exact:true}).click();
  await expect(names).toHaveText(["Sortier-Sensor 3","Sortier-Sensor 2","Sortier-Sensor 1"]);
  await page.getByRole("tab",{name:"Live-Status"}).click();
  const live=page.locator("article.card").filter({has:page.getByRole("heading",{name:"Sortierung",exact:true})});
  await expect(live.locator(".sensor-name")).toHaveText(["Sortier-Sensor 3","Sortier-Sensor 2","Sortier-Sensor 1"]);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await card.locator(`[data-sensor-id="${ids[1]}"]`).first().click();
  const dialog=page.getByRole("dialog");
  const overflow=await dialog.evaluate(el=>el.scrollWidth>el.clientWidth+1);
  expect(overflow).toBe(false);
  await dialog.getByRole("button",{name:"Sensor löschen",exact:true}).click();
  await dialog.getByRole("button",{name:"Sensor löschen",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await expect(names).toHaveText(["Sortier-Sensor 3","Sortier-Sensor 1"]);
  const saved=await ws(page,"get");
  expect(saved.config.sensors[ids[1]]).toBeUndefined();
  expect(saved.config.settings.sensor_order.order_room).toEqual([ids[2],ids[0]]);
  expect(saved.config.profiles.order_profile.sensor_ids).toEqual([ids[0],ids[2]]);
  expect(await page.locator("iqalarm-panel").evaluate(async(el,id)=>(await el.hass.fetchWithAuth(`/api/states/${id}`)).status,ids[1])).toBe(200);
});

test("deleting a final window removes its IQAlarm source assignments and profile/order references",async({page})=>{
  const contact="binary_sensor.delete_window_frame",lock="lock.delete_window_handle",virtual="binary_sensor.iqalarm_window_delete_window";
  await state(page,contact,"off");await state(page,lock,"locked");
  const data=await ws(page,"get");
  data.config.rooms.delete_room={id:"delete_room",name:"Löschtest"};
  data.config.sensors[contact]={entity_id:contact,role:"entry_contact",room_id:"delete_room"};
  data.config.sensors[lock]={entity_id:lock,role:"lock_contact",sensor_kind:"window_handle",room_id:"delete_room"};
  data.config.windows.delete_window={id:"delete_window",name:"Löschfenster",room_id:"delete_room",contact_entity_id:contact,lock_entity_id:lock,mappings:[{state:"closed",values:{[contact]:"off"}},{state:"open",values:{[contact]:"on"}}]};
  data.config.profiles.delete_profile={...data.config.profiles.armed_night,name:"Löschprofil",sensor_ids:[virtual,contact,lock]};
  data.config.settings.sensor_order.delete_room=[virtual];
  await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.locator('[data-drop-room-id="delete_room"] .sensor-moveable').click();
  await page.getByRole("dialog").getByRole("button",{name:"Sensor löschen",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Sensor löschen",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await ws(page,"get");
  expect(saved.config.windows.delete_window).toBeUndefined();
  expect(saved.config.sensors[contact]).toBeUndefined();expect(saved.config.sensors[lock]).toBeUndefined();
  expect(saved.config.profiles.delete_profile.sensor_ids).toEqual([]);
  expect(saved.config.settings.sensor_order.delete_room).toEqual([]);
});
