import {test,expect} from "@playwright/test";

async function ws(page,type,data={}){return page.evaluate(({type,data})=>window.iqTest.request({type:`iqalarm/${type}`,...data}),{type,data});}
async function save(page,config){const current=await ws(page,"get");return ws(page,"config/save",{config,revision:current.config.revision});}
async function state(page,id,value){
  await page.locator("iqalarm-panel").evaluate(async(el,{id,value})=>{
    const response=await el.hass.fetchWithAuth(`/api/states/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:value})});
    if(!response.ok)throw Error("Disposable state setup failed");
  },{id,value});
}
const originals=new WeakMap();
const ids={person:"binary_sensor.level_person",person2:"binary_sensor.level_person2",outside:"binary_sensor.level_outside",frame:"binary_sensor.level_frame",motion:"binary_sensor.level_motion"};

test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  let data=await ws(page,"get");if(data.status.active)data=await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  originals.set(page,structuredClone(data.config));
  for(const id of Object.values(ids))await state(page,id,"off");
  data.config.stages=[
    {id:"0",name:"Deaktiviert",color:"#ffffff"},{id:"1",name:"Sicher",color:"#64bc29"},
    {id:"2",name:"Bewegung Außen",color:"#08ba1d"},{id:"3",name:"Erste Sensorauslösung / Fehlerfall",color:"#cad345"},
    {id:"4",name:"Bewegung Innen",color:"#bc2929"},{id:"5",name:"ALARM!!!",color:"#8000ff",requires_confirmation:true,allow_loud:true,latch:true},
  ];data.config.secure_stage_id="1";data.config.actions={};delete data.config.rules;
  for(const [key,role]of Object.entries({person:"perimeter_camera",person2:"perimeter_camera",outside:"perimeter_sensor",frame:"entry_contact",motion:"interior_motion"}))data.config.sensors[ids[key]]={entity_id:ids[key],name:`Regeltest ${key}`,role,room_id:"living",front_of:role.startsWith("perimeter")?["living"]:[]};
  const targets={perimeter:"2",single:"3",motion:"4",fault:"3",flapping:"3",perimeter_contact:"5",contact_motion:"5",multi_contact:"5",multi_motion:"5",immediate:"5"};
  data.config.profiles={qa_night:{name:"Regeln Nacht",motion_mode:"after_contact",stage_targets:targets,sensor_ids:Object.values(ids),entry_seconds:0},qa_away:{name:"Regeln Abwesend",motion_mode:"always",stage_targets:targets,sensor_ids:Object.values(ids),entry_seconds:0}};
  await save(page,data.config);await page.reload();await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
});
test.afterEach(async({page})=>{
  const original=originals.get(page);
  if(original){const current=await ws(page,"get");if(current.status.active)await ws(page,"set_mode",{mode:"inactive",code:"2468"});await save(page,original);}
});

test("free level conditions select entities, source count, timing and profiles, then evaluate",async({page})=>{
  await page.getByRole("tab",{name:"Profile & System"}).click();
  await expect(page.getByRole("heading",{name:"Verwendete Levelregeln"})).toBeVisible();
  await expect(page.getByLabel("Vorfeld auswerten",{exact:true})).toHaveCount(0);
  await expect(page.getByLabel("Alle Sensoren einbeziehen",{exact:true})).toHaveCount(0);
  await expect(page.getByLabel("Korrelationsfenster (Sekunden)",{exact:true})).toHaveCount(0);
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="3"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  await page.getByLabel("Regelname",{exact:true}).fill("Zwei Außenquellen");
  await page.getByLabel("Sensoren für Bedingung 1",{exact:true}).selectOption([ids.person,ids.person2,ids.outside]);
  await page.getByLabel("Unabhängige Quellen erforderlich",{exact:true}).fill("2");
  await page.getByLabel("Bestätigungsfenster (Sekunden)",{exact:true}).fill("30");
  await page.getByRole("button",{name:"Weitere Bedingung",exact:true}).click();
  await expect(page.getByLabel("Regelname",{exact:true})).toHaveValue("Zwei Außenquellen");
  await expect(page.getByLabel("Sensoren für Bedingung 1",{exact:true})).toHaveValues([ids.person,ids.person2,ids.outside]);
  await page.locator('[data-rule-condition="1"]').getByRole("button",{name:"Entfernen",exact:true}).click();
  await page.getByLabel("In diesen Alarmmodi verwenden",{exact:true}).selectOption("qa_night");
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await ws(page,"get"),rule=Object.values(saved.config.rules).find(r=>r.name==="Zwei Außenquellen");
  expect(rule.conditions[0].count).toBe(2);expect(rule.window_seconds).toBe(30);
  expect(saved.config.profiles.qa_night.rule_ids).toContain(rule.id);expect(saved.config.profiles.qa_away.rule_ids).not.toContain(rule.id);
  await page.reload();await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="3"]').click();
  await expect(page.getByRole("heading",{name:"Zwei Außenquellen",exact:true})).toBeVisible();
  await page.screenshot({path:"test-results/free-level-rules.png",fullPage:true});
  await ws(page,"set_mode",{mode:"qa_night"});await state(page,ids.person,"on");
  await expect.poll(async()=>(await ws(page,"get")).status.level).toBe(2);
  await state(page,ids.outside,"on");
  await expect.poll(async()=>(await ws(page,"get")).status.level).toBe(3);
  expect((await ws(page,"get")).status.confirmed).toBe(false);
});

test("profile level actions and dry runs are isolated, persist and duplicate independently",async({page})=>{
  await page.getByRole("tab",{name:"Profile & System"}).click();
  const card=page.locator('[data-profile-action-stage="2"]');
  async function add(message){
    await card.getByRole("button",{name:"Aktion hinzufügen",exact:true}).click();
    await page.getByLabel(/^Ziel \/ Dienst/).fill("notify.test_phone");await page.getByLabel(/^Nachricht/).fill(message);
    await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();await expect(page.getByRole("dialog")).not.toBeVisible();
  }
  await add("Nur nachts");
  await page.getByRole("button",{name:"Regeln Abwesend",exact:true}).click();await expect(card.getByText("Nur nachts",{exact:true})).toHaveCount(0);
  await add("Nur abwesend");
  await card.getByRole("button",{name:"Stufe trocken testen",exact:true}).click();
  await expect(card.locator("[data-level-test-plan]")).toContainText("Trockenlauf abgeschlossen");
  let data=await ws(page,"get");const night=Object.values(data.config.actions).find(a=>a.message==="Nur nachts"),away=Object.values(data.config.actions).find(a=>a.message==="Nur abwesend");
  expect(night.profile_ids).toEqual(["qa_night"]);expect(away.profile_ids).toEqual(["qa_away"]);
  let plan=await ws(page,"test_level",{level:"2",profile_id:"qa_away",dry_run:true});expect(plan.actions.map(a=>a.id)).toContain(away.id);expect(plan.actions.map(a=>a.id)).not.toContain(night.id);
  await page.getByRole("button",{name:"Duplizieren",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Profilname",{exact:true}).fill("Kopie Regeln");
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  data=await ws(page,"get");const copy=Object.entries(data.config.profiles).find(([,p])=>p.name==="Kopie Regeln")[0];
  const copyAction=Object.values(data.config.actions).find(a=>a.message==="Nur abwesend"&&a.profile_ids.includes(copy));
  expect(copyAction.id).not.toBe(away.id);
  await card.locator(".action-card").filter({hasText:"Nur abwesend"}).getByRole("button",{name:"Aktion bearbeiten",exact:true}).click();
  await page.getByLabel(/^Nachricht/).fill("Nur Kopie");await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await page.getByRole("button",{name:"Regeln Abwesend",exact:true}).click();await expect(card.getByText("Nur abwesend",{exact:true})).toBeVisible();await expect(card.getByText("Nur Kopie",{exact:true})).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:"test-results/profile-level-actions-mobile.png",fullPage:true});
  await page.reload();await page.getByRole("tab",{name:"Profile & System"}).click();await page.getByRole("button",{name:"Regeln Nacht",exact:true}).click();await expect(card.getByText("Nur nachts",{exact:true})).toBeVisible();
});

test("deleting an explicitly selected source disables incomplete rules without deleting HA",async({page})=>{
  let data=await ws(page,"get");
  data.config.rules.explicit={id:"explicit",name:"Explizite Kamera",stage_id:"2",conditions:[{sensor_ids:[ids.person],roles:[],event:"active",count:1}],window_seconds:30};
  data.config.profiles.qa_night.rule_ids.push("explicit");await save(page,data.config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.locator(`[data-sensor-id="${ids.person}"]`).first().click();
  await page.getByRole("dialog").getByRole("button",{name:"Sensor löschen",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Sensor löschen",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  data=await ws(page,"get");expect(data.config.rules.explicit.enabled).toBe(false);expect(data.config.rules.explicit.conditions[0].sensor_ids).toEqual([]);
});
