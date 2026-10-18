import {test,expect} from "@playwright/test";

async function ws(page,type,data={}){return page.evaluate(({type,data})=>window.iqTest.request({type:`iqalarm/${type}`,...data}),{type,data});}
async function state(page,id,value,attributes={}){
  await page.locator("iqalarm-panel").evaluate(async(el,{id,value,attributes})=>{
    const response=await el.hass.fetchWithAuth(`/api/states/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:value,attributes})});
    if(!response.ok)throw Error("Cannot set disposable test state");
  },{id,value,attributes});
}
async function save(page,config){const current=await ws(page,"get");return ws(page,"config/save",{config,revision:current.config.revision});}

test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  let current=await ws(page,"get");
  if(current.status.active)current=await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  await page.evaluate(config=>window.safetyOriginal=config,current.config);
});
test.afterEach(async({page})=>{
  const original=await page.evaluate(()=>window.safetyOriginal);
  if(original){const current=await ws(page,"get");if(current.status.active)await ws(page,"set_mode",{mode:"inactive",code:"2468"});await save(page,original);}
});

test("import uses binary lock values and verified boolean camera detection",async({page})=>{
  await state(page,"binary_sensor.safety_deadbolt","off",{friendly_name:"QA Türschloss",device_class:"lock"});
  await state(page,"camera.safety_person","idle",{friendly_name:"QA Personenkamera",person_detected:true});
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.getByRole("button",{name:"Sensoren automatisch erkennen",exact:true}).click();
  await expect(page.locator('[data-candidate-check="binary_sensor.safety_deadbolt"]')).toBeVisible();
  await page.locator("iqalarm-panel").evaluate(el=>el._assistantToggleAll(false));
  for(const id of ["binary_sensor.safety_deadbolt","camera.safety_person"]){
    await page.locator(`[data-room-select="${id}"]`).selectOption("living");
    await page.locator(`[data-candidate-check="${id}"]`).check();
  }
  await page.getByRole("button",{name:"2 Sensoren importieren",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const result=await ws(page,"get");
  expect(result.config.sensors["binary_sensor.safety_deadbolt"].active_states).toEqual(["on"]);
  expect(result.config.sensors["camera.safety_person"].active_states).toEqual(["true"]);
  expect(result.config.sensors["camera.safety_person"].attribute).toBe("person_detected");
});

test("unchecking a level trigger persists its removal",async({page})=>{
  const data=await ws(page,"get"),target=data.config.stages.at(-1).id,baseline=data.config.stages[0].id;
  for(const p of Object.values(data.config.profiles))p.stage_targets.contact_motion=target;
  await save(page,data.config);
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();
  await page.locator(`[data-stage="${target}"]`).click();
  const field=page.locator('#stage-single-form [name="rule_contact_motion"]');
  await expect(field).toBeChecked();await field.uncheck();
  await page.getByRole("button",{name:"Level speichern",exact:true}).click();
  await expect(field).not.toBeChecked();
  const saved=await ws(page,"get");
  expect(Object.values(saved.config.profiles).every(p=>p.stage_targets.contact_motion===baseline)).toBe(true);
});

test("ordinary sensor table updates live without replacing forms",async({page})=>{
  await state(page,"binary_sensor.safety_motion","off",{friendly_name:"QA Status",device_class:"motion"});
  const data=await ws(page,"get");
  data.config.sensors["binary_sensor.safety_motion"]={entity_id:"binary_sensor.safety_motion",role:"interior_motion",room_id:"living",name:"QA Status"};
  await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  const field=page.locator('[data-sensor-status="binary_sensor.safety_motion"]');
  await expect(field).toHaveText("Ruhig");
  await state(page,"binary_sensor.safety_motion","on",{friendly_name:"QA Status",device_class:"motion"});
  await expect(field).toHaveText("Aktiv");
});

test("floorplan and room deletion validates before committing anything",async({page})=>{
  await state(page,"binary_sensor.safety_frame","off");
  const data=await ws(page,"get");
  data.config.rooms.safety_room={id:"safety_room",name:"QA Raum",adjacent:[]};
  data.config.floorplans.safety_plan={id:"safety_plan",name:"QA Grundriss",zones:{safety_room:[[0.1,0.1],[0.4,0.1],[0.4,0.4],[0.1,0.4]]},width:100,height:100};
  data.config.windows.safety_window={id:"safety_window",name:"QA Fenster",room_id:"safety_room",contact_entity_id:"binary_sensor.safety_frame",mappings:[{state:"closed",values:{"binary_sensor.safety_frame":"off"}},{state:"open",values:{"binary_sensor.safety_frame":"on"}}]};
  await save(page,data.config);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator("#plan-select").selectOption("safety_plan");
  await page.getByRole("button",{name:"Grundriss löschen",exact:true}).click();
  await page.getByRole("dialog").getByRole("button",{name:"Grundriss löschen",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("Zuerst zusammengeführte Fenster");
  const saved=await ws(page,"get");expect(saved.config.floorplans.safety_plan).toBeTruthy();expect(saved.config.rooms.safety_room).toBeTruthy();
});

test("orthogonalization saves the edited draft rather than old geometry",async({page})=>{
  const data=await ws(page,"get");
  data.config.floorplans.safety_draft={id:"safety_draft",name:"QA Entwurf",zones:{living:[[0.1,0.1],[0.4,0.1],[0.4,0.4],[0.1,0.4]]},width:100,height:100};
  await save(page,data.config);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator("#plan-select").selectOption("safety_draft");
  await page.locator("iqalarm-panel").evaluate(el=>{el.zoneRoom="living";el.points=[[0.1,0.1],[0.8,0.1],[0.8,0.4],[0.1,0.4]];el._storeDraft();});
  await page.getByRole("button",{name:"90° Begradigen",exact:true}).first().click();
  await expect.poll(async()=>Math.max(...(await ws(page,"get")).config.floorplans.safety_draft.zones.living.map(p=>p[0]))).toBe(0.8);
});

test("window wizard supports explicit enum contact values",async({page})=>{
  await state(page,"sensor.safety_enum_window","closed",{friendly_name:"QA Textkontakt"});
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.getByRole("button",{name:"Fenster einrichten",exact:true}).click();
  const wizard=page.locator("iqalarm-window-assistant");
  await wizard.getByLabel("Fenstername",{exact:true}).fill("QA Textfenster");
  await wizard.getByLabel("Raum",{exact:true}).selectOption("living");
  await wizard.getByLabel("Fensterkontakt",{exact:true}).selectOption("sensor.safety_enum_window");
  await wizard.getByText("Weitere Einstellungen",{exact:true}).click();
  await wizard.getByLabel("Kontakt geöffnet bei",{exact:true}).fill("open, tilted");
  await wizard.getByLabel("Kontakt geschlossen bei",{exact:true}).fill("closed");
  await wizard.getByLabel("Stabilisierungszeit (Sekunden)",{exact:true}).fill("0.2");
  await wizard.getByRole("button",{name:"Weiter: Fensterstellungen",exact:true}).click();
  await expect(wizard.getByRole("button",{name:"Zustand übernehmen",exact:true})).toBeEnabled();
  await wizard.getByRole("button",{name:"Zustand übernehmen",exact:true}).click();
  await state(page,"sensor.safety_enum_window","open",{friendly_name:"QA Textkontakt"});
  await expect(wizard.locator("#preview .signal span")).toHaveText("open");
  await expect(wizard.locator("#preview p")).toHaveText("Signale stabil");
  await expect(wizard.getByRole("button",{name:"Zustand übernehmen",exact:true})).toBeEnabled();
  await wizard.getByRole("button",{name:"Zustand übernehmen",exact:true}).click();
  await wizard.getByRole("button",{name:"Fenster speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await ws(page,"get"),window=Object.values(saved.config.windows).find(w=>w.name==="QA Textfenster");
  expect(saved.status.raw[`binary_sensor.iqalarm_window_${window.id}`]).toBe(true);
});

test("motion label and red room expire together after fifteen seconds without another event",async({page})=>{
  await page.clock.install();
  await state(page,"binary_sensor.qa_floorplan_motion","off");
  const data=await ws(page,"get");
  data.config.rooms.qa_motion={id:"qa_motion",name:"QA Bewegung",adjacent:[]};
  data.config.sensors["binary_sensor.qa_floorplan_motion"]={entity_id:"binary_sensor.qa_floorplan_motion",role:"interior_motion",room_id:"qa_motion"};
  data.config.floorplans.qa_motion={id:"qa_motion",name:"QA Timer",width:100,height:100,zones:{qa_motion:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
  data.config.settings.observation_profile_id="live";
  data.config.settings.floorplan_disarmed_motion=true;
  await save(page,data.config);
  const shape=page.locator('#floorplan-qa_motion g[data-room="qa_motion"]:not([data-label-room]) .room-glow');
  const label=page.locator('#floorplan-qa_motion [data-label-room="qa_motion"] .room-sub');
  await state(page,"binary_sensor.qa_floorplan_motion","on");
  await expect(label).toContainText("Bewegung");
  await expect(shape).toHaveAttribute("fill","#ef4444");
  await state(page,"binary_sensor.qa_floorplan_motion","off");
  await expect.poll(()=>page.locator("iqalarm-panel").evaluate(el=>el.data.status.raw["binary_sensor.qa_floorplan_motion"])).toBe(false);
  await page.clock.fastForward(14000);
  await expect(label).toContainText("Bewegung");
  await expect(shape).toHaveAttribute("fill","#ef4444");
  await page.clock.fastForward(2000);
  await expect(label).toContainText("Ruhig");
  await expect(label).not.toContainText("Bewegung",{ignoreCase:false});
  await expect(shape).toHaveAttribute("fill","#14b8a6");
  const current=await ws(page,"get");
  expect(current.status.rooms.qa_motion.level).toBe(2);
  expect(current.status.rooms.qa_motion.confirmed).toBe(false);
});

test("window and lock states update separately and related actors stay nested",async({page})=>{
  const registry=await page.evaluate(()=>window.iqTest.request({type:"config/entity_registry/list"}));
  const lockRecord=registry.find(e=>e.platform==="iqalarm_test"&&e.unique_id==="test_window_handle");
  expect(lockRecord).toBeTruthy();
  await state(page,lockRecord.entity_id,"locked");
  const catalog=await ws(page,"catalog");
  const actor=catalog.entities.find(e=>e.entity_id.startsWith("binary_sensor.qa_window_actor"));
  const lock=catalog.entities.find(e=>e.entity_id===lockRecord.entity_id);
  expect(actor).toBeTruthy();expect(lock.source_id).toBe(actor.source_id);
  await state(page,"binary_sensor.qa_summary_contact","off");
  await state(page,lock.entity_id,"locked");await state(page,actor.entity_id,"off");
  const data=await ws(page,"get");
  data.config.windows.qa_summary={id:"qa_summary",name:"QA Zusammenfassung",room_id:"living",contact_entity_id:"binary_sensor.qa_summary_contact",lock_entity_id:lock.entity_id,settle_seconds:.2,mappings:[{state:"closed",values:{"binary_sensor.qa_summary_contact":"off"}},{state:"open",values:{"binary_sensor.qa_summary_contact":"on"}}]};
  data.config.sensors[actor.entity_id]={entity_id:actor.entity_id,name:"QA Aktor",role:"lock_contact",sensor_kind:"window_handle",room_id:"living"};
  await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  const parent=page.locator('[data-window-id="qa_summary"]');
  await expect(parent.locator("[data-window-status]")).toHaveText("Geschlossen | Verriegelt");
  await expect(parent.locator(`[data-source-state="${actor.entity_id}"]`)).toHaveCount(1);
  await expect(page.locator(`[data-sensor-state-id="${actor.entity_id}"]`)).toHaveCount(0);
  await state(page,lock.entity_id,"unlocked");
  await expect(parent.locator("[data-window-status]")).toHaveText("Geschlossen | Entriegelt");
  await state(page,actor.entity_id,"unavailable");
  await expect(parent.locator(`[data-source-state="${actor.entity_id}"]`)).toContainText("Keine Verbindung");
  await expect(parent.locator("[data-window-status]")).toHaveText("Geschlossen | Entriegelt");
  await page.getByRole("tab",{name:"Live-Status"}).click();
  await expect(page.locator('[data-sensor-state-id="binary_sensor.iqalarm_window_qa_summary"]')).toContainText("Geschlossen | Entriegelt");
  await expect(page.locator('[data-window-related="qa_summary"]')).toContainText("QA Aktor");
});
