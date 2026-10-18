import {test,expect} from "@playwright/test";

test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
});

async function signals(page,values){
  await page.locator("iqalarm-panel").evaluate(async(el,values)=>{
    for(const [entity_id,state]of Object.entries(values)){
      const response=await el.hass.fetchWithAuth(`/api/states/${entity_id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state,attributes:{friendly_name:entity_id}})});
      if(!response.ok)throw new Error(`State setup failed: ${entity_id}`);
    }
  },values);
  // The configured 0.2 s stabilization must elapse before capturing real HA states.
  await page.waitForTimeout(250);
}

async function openWizard(page,prefix,complex=true){
  const ids={contact:`binary_sensor.${prefix}_frame`,a:`binary_sensor.${prefix}_grip_a`,b:`binary_sensor.${prefix}_grip_b`,lock:`lock.${prefix}_handle`};
  await signals(page,{[ids.contact]:"off",[ids.a]:"off",[ids.b]:"off",[ids.lock]:"locked"});
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.getByRole("button",{name:"Fenster einrichten",exact:true}).click();
  const wizard=page.locator("iqalarm-window-assistant");
  await wizard.getByLabel("Fenstername",{exact:true}).fill(prefix);
  await wizard.getByLabel("Raum",{exact:true}).selectOption("living");
  await wizard.getByLabel("Fensterkontakt",{exact:true}).selectOption(ids.contact);
  if(complex){
    await wizard.getByLabel("Fenstergriff – Schloss",{exact:true}).selectOption(ids.lock);
    await wizard.getByLabel("Griffsignal 1",{exact:true}).selectOption(ids.a);
    await wizard.getByLabel("Griffsignal 2",{exact:true}).selectOption(ids.b);
  }
  await wizard.getByText("Weitere Einstellungen",{exact:true}).click();
  await wizard.getByLabel("Stabilisierungszeit (Sekunden)",{exact:true}).fill("0.2");
  await wizard.getByRole("button",{name:"Weiter: Fensterstellungen",exact:true}).click();
  await expect(wizard.getByRole("heading",{name:"Fenster vollständig schließen und verriegeln.",exact:true})).toBeVisible();
  return {wizard,ids};
}

test("guided window setup learns five positions and nests original entities without duplicates",async({page})=>{
  const errors=[];page.on("pageerror",err=>errors.push(err.message));
  const {wizard,ids}=await openWizard(page,"browser_composite");
  const before=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  for(const [frame,a,b]of [["off","off","off"],["off","on","on"],["on","on","on"],["off","on","off"],["on","on","off"]]){
    await signals(page,{[ids.contact]:frame,[ids.a]:a,[ids.b]:b});
    const capture=wizard.getByRole("button",{name:"Zustand übernehmen",exact:true});
    await expect(capture).toBeEnabled();await capture.click();
  }
  await expect(wizard.getByRole("heading",{name:"Erkennung prüfen",exact:true})).toBeVisible();
  const uncommitted=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(uncommitted.config.revision).toBe(before.config.revision);
  await signals(page,{[ids.contact]:"off",[ids.a]:"off",[ids.b]:"off",[ids.lock]:"locked"});
  await expect(wizard.locator("#preview strong")).toHaveText("Geschlossen");
  await wizard.getByRole("button",{name:"Fenster speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  const window=Object.values(saved.config.windows).find(w=>w.name==="browser_composite");
  expect(window.mappings).toHaveLength(5);
  const parent=page.locator(`[data-window-id="${window.id}"]`);
  await expect(parent.locator(".window-inputs .sensor-line")).toHaveCount(4);
  await expect(page.locator("#catalog")).not.toContainText(ids.contact);
  for(const id of Object.values(ids))await expect(page.locator(".table-scroll td code").filter({hasText:id})).toHaveCount(0);
  let derivedId;
  await expect.poll(async()=>{
    const states=await page.evaluate(()=>window.iqTest.request({type:"get_states"}));
    const derived=states.find(s=>s.attributes?.inputs?.[ids.contact]!==undefined&&s.entity_id.startsWith("sensor."));
    derivedId=derived?.entity_id;return derived?.state;
  }).toBe("closed");
  await signals(page,{[ids.lock]:"unavailable"});
  await expect(parent.locator("[data-window-status]")).toHaveText("Keine Verbindung");
  await expect(parent.locator(`[data-source-state="${ids.lock}"]`)).toContainText("Keine Verbindung");
  const states=await page.evaluate(()=>window.iqTest.request({type:"get_states"}));
  const derived=states.find(s=>s.entity_id===derivedId);
  expect(derived.state).toBe("unavailable");
  await signals(page,{[ids.lock]:"locked"});
  await page.reload();await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await expect(page.locator(`[data-window-id="${window.id}"] [data-window-status]`)).toHaveText("Geschlossen");
  await page.setViewportSize({width:390,height:844});
  await page.locator(`[data-window-id="${window.id}"]`).getByRole("button",{name:"Bearbeiten",exact:true}).click();
  await expect(page.locator("iqalarm-window-assistant").getByLabel("Fenstername",{exact:true})).toHaveValue("browser_composite");
  const overflow=await page.locator("iqalarm-window-assistant").evaluate(el=>el.scrollWidth>el.clientWidth);
  expect(overflow).toBe(false);expect(errors).toEqual([]);
});

test("wizard detects duplicate signals and never learns a lost connection as tilted",async({page})=>{
  const {wizard,ids}=await openWizard(page,"browser_guard");
  const capture=()=>wizard.getByRole("button",{name:"Zustand übernehmen",exact:true});
  await expect(capture()).toBeEnabled();await capture().click();
  await expect(capture()).toBeEnabled();await capture().click();
  await expect(wizard.getByRole("alert")).toContainText("nicht unterschieden");
  await expect(wizard.getByRole("heading",{name:"Jetzt entriegeln, das Fenster aber geschlossen lassen.",exact:true})).toBeVisible();
  await signals(page,{[ids.lock]:"unavailable"});
  await expect(wizard.locator("#preview strong")).toHaveText("Keine Verbindung");
  await expect(capture()).toBeDisabled();
  await wizard.getByRole("button",{name:"Abbrechen",exact:true}).click();
  const data=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(Object.values(data.config.windows).some(w=>w.name==="browser_guard")).toBe(false);
});

test("simple contact setup works without grip signals and publishes a real HA sensor",async({page})=>{
  const {wizard,ids}=await openWizard(page,"browser_simple",false);
  await expect(wizard.getByRole("button",{name:"Zustand übernehmen",exact:true})).toBeEnabled();
  await wizard.getByRole("button",{name:"Zustand übernehmen",exact:true}).click();
  await signals(page,{[ids.contact]:"on"});
  await expect(wizard.getByRole("button",{name:"Zustand übernehmen",exact:true})).toBeEnabled();
  await wizard.getByRole("button",{name:"Zustand übernehmen",exact:true}).click();
  await wizard.getByRole("button",{name:"Fenster speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const data=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  const window=Object.values(data.config.windows).find(w=>w.name==="browser_simple");
  expect(window.handle_entity_ids).toEqual([]);
  await expect(page.locator(`[data-window-id="${window.id}"] .window-inputs .sensor-line`)).toHaveCount(1);
  await expect.poll(async()=>{
    const states=await page.evaluate(()=>window.iqTest.request({type:"get_states"}));
    return states.some(s=>s.attributes?.inputs?.[ids.contact]==="on"&&s.state==="open");
  }).toBe(true);
});

test("unlocked window handles are shown on rooms but informational banner is armed-only",async({page})=>{
  await signals(page,{"lock.fenstergriff_browser":"unlocked"});
  await page.evaluate(async()=>{
    const data=await window.iqTest.request({type:"iqalarm/get"});
    data.config.sensors["lock.fenstergriff_browser"]={entity_id:"lock.fenstergriff_browser",name:"Fenstergriff Browser",role:"lock_contact",room_id:"living"};
    data.config.settings.block_open_on_arm=false;data.config.settings.block_unavailable_on_arm=false;
    data.config.profiles.window_info={...data.config.profiles.armed_night,name:"Fensterinfo-Test",sensor_ids:["lock.fenstergriff_browser"],exit_seconds:0};
    await window.iqTest.request({type:"iqalarm/config/save",config:data.config,revision:data.config.revision});
  });
  await page.reload();
  await expect(page.locator('[data-category="information"]')).toHaveCount(0);
  await expect(page.locator('[data-category="information"]').getByText("Fenstergriff Browser",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Fensterinfo-Test",exact:true}).click();
  await expect(page.locator('[data-category="information"]')).toContainText("Potenziell unsicher");
  const data=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(data.status.level).toBe(0);expect(data.status.quarantine).toEqual({});
  await page.getByRole("button",{name:"Aus",exact:true}).click();
  await page.getByLabel("PIN",{exact:true}).fill("2468");await page.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.locator('[data-category="information"]')).toHaveCount(0);
});
