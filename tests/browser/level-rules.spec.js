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
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="4"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  await page.getByLabel("Regelname",{exact:true}).fill("Zwei Außenquellen");
  await page.getByLabel("Sensoren für Bedingung 1",{exact:true}).selectOption([ids.person,ids.person2,ids.outside]);
  await page.getByLabel("Auslösen ab (unabhängige Quellen)",{exact:true}).fill("2");
  await page.getByLabel("Bestätigungsfenster (Sekunden)",{exact:true}).fill("30");
  await page.getByRole("button",{name:"Weitere Bedingung",exact:true}).click();
  await expect(page.getByLabel("Regelname",{exact:true})).toHaveValue("Zwei Außenquellen");
  await expect(page.getByLabel("Sensoren für Bedingung 1",{exact:true})).toHaveValues([ids.person,ids.person2,ids.outside]);
  await page.locator('[data-rule-condition="1"]').getByRole("button",{name:"Entfernen",exact:true}).click();
  await page.getByRole("listbox",{name:"In diesen Alarmmodi verwenden",exact:true}).selectOption("qa_night");
  await page.screenshot({path:"test-results/free-level-rule-editor.png",fullPage:true});
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await ws(page,"get"),rule=Object.values(saved.config.rules).find(r=>r.name==="Zwei Außenquellen");
  expect(rule.conditions[0].count).toBe(2);expect(rule.window_seconds).toBe(30);
  expect(saved.config.profiles.qa_night.rule_ids).toContain(rule.id);expect(saved.config.profiles.qa_away.rule_ids).not.toContain(rule.id);
  await page.reload();await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="4"]').click();
  await expect(page.getByRole("heading",{name:"Zwei Außenquellen",exact:true})).toBeVisible();
  await page.screenshot({path:"test-results/free-level-rules.png",fullPage:true});
  await ws(page,"set_mode",{mode:"qa_night"});await state(page,ids.person,"on");
  await expect.poll(async()=>(await ws(page,"get")).status.level).toBe(2);
  await state(page,ids.outside,"on");
  await expect.poll(async()=>(await ws(page,"get")).status.level).toBe(4);
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
  await page.setViewportSize({width:390,height:844});await card.scrollIntoViewIfNeeded();await page.screenshot({path:"test-results/profile-level-actions-mobile.png",fullPage:true});
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

test("large source editor reveals live group members and preserves edits on state changes",async({page})=>{
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();
  await page.locator('[data-stage="2"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  const dialog=page.getByRole("dialog"),preview=dialog.locator("[data-rule-source-preview]");
  await dialog.getByLabel("Regelname",{exact:true}).fill("Gruppentest ungespeichert");
  const sources=dialog.getByLabel("Sensoren für Bedingung 1",{exact:true});
  await sources.selectOption(["role:perimeter_camera"]);
  const member=preview.locator(`[data-rule-source-id="${ids.person}"]`);
  await expect(member).toContainText("Regeltest person");
  await expect(member.locator("code")).toHaveText(ids.person);
  await expect(member).toContainText("Wohnzimmer");
  await expect(member.locator(".rule-source-state")).toHaveText("Keine Person");
  await expect(preview.locator(`[data-rule-source-id="${ids.frame}"]`)).toHaveCount(0);
  await state(page,ids.person,"on");
  await expect(member.locator(".rule-source-state")).toHaveText("Person erkannt");
  await expect(member).toHaveClass(/is-active/);
  await expect(dialog.getByLabel("Regelname",{exact:true})).toHaveValue("Gruppentest ungespeichert");
  await state(page,ids.person,"off");
  await expect(member.locator(".rule-source-state")).toHaveText("Keine Person");
  await sources.selectOption(["role:perimeter_camera","role:perimeter_sensor"]);
  await expect(preview.locator(`[data-rule-source-id="${ids.outside}"]`)).toBeVisible();
  expect(await sources.evaluate(el=>el.clientHeight)).toBeGreaterThanOrEqual(300);
  expect(await dialog.evaluate(el=>el.clientWidth)).toBeGreaterThan(900);
  await page.screenshot({path:"test-results/rule-source-groups-desktop.png"});
  await page.setViewportSize({width:390,height:844});
  await member.scrollIntoViewIfNeeded();
  expect(await dialog.evaluate(el=>el.scrollWidth>el.clientWidth+1)).toBe(false);
  await page.screenshot({path:"test-results/rule-source-groups-mobile.png"});
  await dialog.getByRole("button",{name:"Abbrechen",exact:true}).click();
});

test("confirmation grade remembers three sources and requires a later opening",async({page})=>{
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();
  await page.locator('[data-stage="2"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Regelname",{exact:true}).fill("Vorfeldgrad 3");
  await dialog.getByLabel("Sensoren für Bedingung 1",{exact:true}).selectOption([ids.person,ids.person2,ids.outside]);
  await dialog.getByLabel("Bestätigungsgrad für diese Regel verwenden",{exact:true}).check();
  await dialog.getByLabel("Anzahl Bestätigungsgrade",{exact:true}).fill("3");
  await dialog.getByLabel("Bestätigung merken (Minuten)",{exact:true}).fill("3");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  let data=await ws(page,"get");
  const parent=Object.values(data.config.rules).find(r=>r.name==="Vorfeldgrad 3");
  expect(parent.confirmation_target).toBe(3);expect(parent.confirmation_memory_seconds).toBe(180);
  expect(parent.confirmation_thresholds).toEqual([1,2,3]);expect(parent.confirmation_decay_seconds).toEqual([60,60,60]);
  await page.locator('[data-stage="5"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  await dialog.getByLabel("Regelname",{exact:true}).fill("Nur nach bestätigtem Vorfeld");
  await dialog.getByLabel("Sensoren für Bedingung 1",{exact:true}).selectOption([ids.frame]);
  await dialog.getByLabel("Gespeicherte Bestätigung voraussetzen",{exact:true}).selectOption(parent.id);
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  data=await ws(page,"get");
  const child=Object.values(data.config.rules).find(r=>r.name==="Nur nach bestätigtem Vorfeld");
  expect(child.prerequisite_rule_id).toBe(parent.id);
  data.config.profiles.qa_night.rule_ids=[parent.id,child.id];
  await save(page,data.config);
  await ws(page,"set_mode",{mode:"qa_night"});
  for(const [index,id]of [ids.person,ids.person2,ids.outside].entries()){
    await state(page,id,"on");
    await expect.poll(async()=>(await ws(page,"get")).status.rule_progress.find(p=>p.rule_id===parent.id)?.current).toBe(index+1);
    const status=(await ws(page,"get")).status;
    expect(status.level).toBe(2);expect(status.confirmed).toBe(false);
  }
  for(const id of [ids.person,ids.person2,ids.outside])await state(page,id,"off");
  await page.getByRole("tab",{name:"Live-Status"}).click();
  const grade=page.locator(`[data-rule-grade="${parent.id}"]`);
  await expect(page.locator(".status-rings")).toHaveAttribute("aria-label",/Bestätigungsgrad 3 von 3/);
  await expect(grade).toContainText("Bestätigung gespeichert bis");
  await grade.scrollIntoViewIfNeeded();
  await page.screenshot({path:"test-results/confirmation-grade-live.png"});
  await state(page,ids.frame,"on");
  await expect.poll(async()=>(await ws(page,"get")).status.level).toBe(5);
  expect((await ws(page,"get")).status.confirmed).toBe(true);
});


test("grade thresholds and decay settings survive condition edits and reload",async({page})=>{
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="2"]').click();
  await page.getByRole("button",{name:"Regel hinzufügen",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Regelname",{exact:true}).fill("Gestufte Bestätigung");
  await dialog.getByLabel("Sensoren für Bedingung 1",{exact:true}).selectOption([ids.person,ids.person2,ids.outside]);
  await dialog.getByLabel("Bestätigungsgrad für diese Regel verwenden",{exact:true}).check();
  await dialog.getByLabel("Anzahl Bestätigungsgrade",{exact:true}).fill("2");
  await dialog.getByLabel("Unabhängige Meldungen für 2/2",{exact:true}).fill("3");
  await dialog.getByLabel("Rückstufung von 1/2 nach Ruhe (Sekunden)",{exact:true}).fill("90");
  await dialog.getByLabel("Rückstufung von 2/2 nach Ruhe (Sekunden)",{exact:true}).fill("45");
  await dialog.getByRole("button",{name:"Weitere Bedingung",exact:true}).click();
  await expect(dialog.getByLabel("Unabhängige Meldungen für 2/2",{exact:true})).toHaveValue("3");
  await dialog.locator('[data-rule-condition="1"]').getByRole("button",{name:"Entfernen",exact:true}).click();
  await expect(dialog.getByLabel("Rückstufung von 1/2 nach Ruhe (Sekunden)",{exact:true})).toHaveValue("90");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();await expect(dialog).not.toBeVisible();
  let rule=Object.values((await ws(page,"get")).config.rules).find(r=>r.name==="Gestufte Bestätigung");
  expect(rule.confirmation_thresholds).toEqual([1,3]);expect(rule.confirmation_decay_seconds).toEqual([90,45]);
  await page.reload();await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="2"]').click();
  await page.getByRole("button",{name:"Gestufte Bestätigung bearbeiten",exact:true}).click();
  await expect(dialog.getByLabel("Unabhängige Meldungen für 2/2",{exact:true})).toHaveValue("3");
  await expect(dialog.getByLabel("Rückstufung von 2/2 nach Ruhe (Sekunden)",{exact:true})).toHaveValue("45");
  await page.setViewportSize({width:390,height:844});
  expect(await dialog.evaluate(el=>el.scrollWidth>el.clientWidth+1)).toBe(false);
  await page.screenshot({path:"test-results/grade-decay-mobile.png"});
  await dialog.getByRole("button",{name:"Abbrechen",exact:true}).click();
});

test("level appearance edits retain security properties without the removed controls",async({page})=>{
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();await page.locator('[data-stage="5"]').click();
  const form=page.locator("#stage-single-form");
  await expect(form.locator('input[type="checkbox"]')).toHaveCount(0);
  await form.getByLabel("Bezeichnung",{exact:true}).fill("Vollalarm");
  await form.getByRole("button",{name:"Level speichern",exact:true}).click();
  const stage=(await ws(page,"get")).config.stages.find(s=>s.id==="5");
  expect(stage.name).toBe("Vollalarm");expect(stage.requires_confirmation).toBe(true);expect(stage.allow_loud).toBe(true);expect(stage.latch).toBe(true);
});

test("a profile action can wait for full confirmation independently from level entry",async({page})=>{
  await page.getByRole("tab",{name:"Profile & System"}).click();
  await page.getByRole("button",{name:"Regeln Nacht",exact:true}).click();
  const card=page.locator('[data-profile-action-stage="2"]');
  await card.getByRole("button",{name:"Aktion hinzufügen",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Ausführen bei",{exact:true}).selectOption("rule_confirmed");
  await dialog.getByLabel(/^Ziel \/ Dienst/).fill("notify.test_phone");
  await dialog.getByLabel(/^Nachricht/).fill("Erst bei voller Bestätigung");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();await expect(dialog).not.toBeVisible();
  await expect(card.getByText("Bei vollständiger Bestätigung",{exact:true})).toBeVisible();
  const action=Object.values((await ws(page,"get")).config.actions).find(a=>a.message==="Erst bei voller Bestätigung");
  expect(action.trigger).toBe("rule_confirmed");expect(action.profile_ids).toEqual(["qa_night"]);
  await page.getByRole("button",{name:"Regeln Abwesend",exact:true}).click();
  await expect(card.getByText("Erst bei voller Bestätigung",{exact:true})).toHaveCount(0);
});


test("outdoor motion and person detection show their own source type on the floorplan",async({page})=>{
  const data=await ws(page,"get");
  data.config.floorplans.source_labels={id:"source_labels",name:"Vorfeldanzeige",width:1000,height:600,zones:{living:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}};
  await save(page,data.config);
  const label=page.locator('#floorplan-source_labels g[data-label-room="living"]');
  await state(page,ids.outside,"on");
  await expect(label).toContainText("Bewegung erkannt");
  await expect(label).not.toContainText("Kamera aktiv");
  await expect(label).not.toContainText("Person");
  await state(page,ids.person,"on");
  await expect(label).toContainText("Person");
  await expect(label).toContainText("Bewegung erkannt");
  await state(page,ids.outside,"off");
  await expect(label).not.toContainText("Bewegung erkannt");
  await expect(label).toContainText("Person");
});

for(const reducedMotion of ["no-preference","reduce"]){
test(`live colors fade when confirmation details disappear with reduced motion ${reducedMotion}`,async({page})=>{
  await page.emulateMedia({reducedMotion});
  const panel=page.locator("iqalarm-panel");
  // Exercise the real dashboard renderer with a private in-browser snapshot.
  // No configured sensor, output, clock or HA entity is changed by this display check.
  await panel.evaluate(el=>{
    el.__liveOriginal=el.data;el.data=structuredClone(el.data);
    el.data.config.floorplans={fade:{id:"fade",name:"Anzeigeprüfung",width:1000,height:600,image:null,zones:{living:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]}}};
    el.data.status.active=false;el.data.status.rooms.living.confirmed=false;
    el.data.config.settings.floorplan_disarmed_motion=true;
    el.data.status.raw["binary_sensor.level_motion"]=true;
    el.data.status.rooms.living.motion=["binary_sensor.level_motion"];
    el.data.status.last_active["binary_sensor.level_motion"]=Date.now()/1000;
    el.data.status.rule_progress=[{rule_id:"display-fade",name:"Anzeigeprüfung",stage_id:el.data.status.stage_id,current:1,target:3,sources:[]}];
    el._render();
  });
  const room=panel.locator('g[data-room="living"]:not([data-label-room])').first();
  const fill=room.locator('polygon').nth(1);
  await expect(fill).toHaveAttribute("fill","#ef4444");
  await expect(panel.locator('g[data-room="living"][data-label-room]').first()).toContainText("Bewegung");
  await page.waitForTimeout(1700);
  await panel.evaluate(el=>{
    el.__fadePolygon=el.shadowRoot.querySelector('g[data-room="living"]:not([data-label-room]) polygon:nth-of-type(2)');
    el.__ringNode=el.shadowRoot.querySelector('[data-level-ring]');
    el.data.status.raw["binary_sensor.level_motion"]=false;
    el.data.status.rooms.living.motion=[];
    el.data.status.last_active["binary_sensor.level_motion"]=Date.now()/1000-16;
    el.data.status.rule_progress=[];
    el._render();
  });
  await expect(fill).toHaveAttribute("fill","#14b8a6");
  expect(await panel.evaluate(el=>el.__fadePolygon===el.shadowRoot.querySelector('g[data-room="living"]:not([data-label-room]) polygon:nth-of-type(2)'))).toBe(true);
  expect(await panel.evaluate(el=>el.__ringNode===el.shadowRoot.querySelector('[data-level-ring]'))).toBe(true);
  await page.waitForTimeout(300);
  const intermediate=await fill.evaluate(el=>getComputedStyle(el).fill);
  expect(intermediate).not.toBe("rgb(20, 184, 166)");expect(intermediate).not.toBe("rgb(239, 68, 68)");
  const label=panel.locator('g[data-room="living"][data-label-room]').first();
  await expect(label).not.toContainText("Ruhig");await expect(label).not.toContainText("Sensor");await expect(label).not.toContainText("Bestätigte Korrelation");
  await expect(label).toContainText("Wohnzimmer");await expect(label).not.toContainText("Bewegung");
  await expect.poll(()=>fill.evaluate(el=>getComputedStyle(el).fill)).toBe("rgb(20, 184, 166)");
  await page.screenshot({path:"test-results/quiet-floorplan-two-rings.png",fullPage:true});
  await panel.evaluate(el=>{el.data=el.__liveOriginal;delete el.__liveOriginal;delete el.__fadePolygon;delete el.__ringNode;el._render();});
});
}


test("live confirmation decays and is published without further sensor events",async({page})=>{
  const data=await ws(page,"get");
  data.config.rules.timer_grade={id:"timer_grade",name:"Live-Rückstufung",stage_id:"2",conditions:[{sensor_ids:[ids.person,ids.person2,ids.outside],roles:[],event:"active",count:1}],window_seconds:60,confirmation_target:3,confirmation_thresholds:[1,2,3],confirmation_decay_seconds:[2,2,2],confirmation_memory_seconds:30};
  data.config.profiles.qa_night.rule_ids=["timer_grade"];
  await save(page,data.config);await ws(page,"set_mode",{mode:"qa_night"});
  for(const id of [ids.person,ids.person2,ids.outside])await state(page,id,"on");
  const grade=page.locator('[data-rule-grade="timer_grade"]');
  await expect(page.locator(".status-rings")).toHaveAttribute("aria-label",/Bestätigungsgrad 3 von 3/);
  await expect(page.locator('.status-rings')).toHaveAttribute('aria-label','Alarmstufe 2, Bestätigungsgrad 3 von 3');
  await expect(page.locator('[data-confirmation-ring]')).toHaveAttribute('stroke-dashoffset','0');
  // From here no HA state, profile, configuration or browser clock is changed.
  for(const current of [2,1,0]){
    await expect(grade).toBeVisible();
    await expect(page.locator('.status-rings')).toHaveAttribute('aria-label',`Alarmstufe 2, Bestätigungsgrad ${current} von 3`);
  }
  await expect(grade).toContainText("Bestätigung gespeichert bis");
  const current=await ws(page,"get");
  expect(current.status.rule_progress[0].remembered).toBe(true);
  expect(current.status.confirmed).toBe(false);
});
