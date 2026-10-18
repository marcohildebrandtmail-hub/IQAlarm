import {test,expect} from "@playwright/test";

const originals=new WeakMap();
async function ws(page,type,data={}){return page.evaluate(({type,data})=>window.iqTest.request({type:`iqalarm/${type}`,...data}),{type,data});}
async function save(page,config){const current=await ws(page,"get");return ws(page,"config/save",{config,revision:current.config.revision});}
test.beforeEach(async({page})=>{
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  let current=await ws(page,"get");
  if(current.status.active)current=await ws(page,"set_mode",{mode:"inactive",code:"2468"});
  originals.set(page,current.config);
});
test.afterEach(async({page})=>{if(originals.has(page))await save(page,originals.get(page));});

test("sensor, composite window and room icons persist in assignment and live views, with mobile reset",async({page})=>{
  const current=await ws(page,"get"),config=current.config;
  config.rooms.symbol_room={id:"symbol_room",name:"Symbolküche"};
  config.sensors["binary_sensor.symbol_fridge"]={entity_id:"binary_sensor.symbol_fridge",name:"Kühlschrank",role:"interior_motion",room_id:"symbol_room"};
  config.windows.symbol_window={id:"symbol_window",name:"Symbolfenster",room_id:"symbol_room",contact_entity_id:"binary_sensor.symbol_frame",mappings:[{state:"closed",values:{"binary_sensor.symbol_frame":"off"}},{state:"open",values:{"binary_sensor.symbol_frame":"on"}}]};
  await save(page,config);
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  const card=page.locator('[data-drop-room-id="symbol_room"]');
  const fridge=card.locator('[data-sensor-id="binary_sensor.symbol_fridge"]').first();
  const window=card.locator('[data-sensor-id="binary_sensor.iqalarm_window_symbol_window"]').first();
  const dialog=page.getByRole("dialog");
  await fridge.click();
  await dialog.getByText("Symbol anpassen",{exact:true}).click();
  await dialog.getByRole("button",{name:"Kühlschrank",exact:true}).click();
  await expect(dialog.locator("[data-display-icon-preview]")).toHaveAttribute("icon","mdi:fridge-outline");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(fridge.locator(".sensor-line-title ha-icon")).toHaveAttribute("icon","mdi:fridge-outline");

  // The full sensor editor must preserve the override too.
  await page.getByRole("button",{name:"Kühlschrank bearbeiten",exact:true}).click();
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(fridge.locator(".sensor-line-title ha-icon")).toHaveAttribute("icon","mdi:fridge-outline");
  await window.click();
  await dialog.getByText("Symbol anpassen",{exact:true}).click();
  await dialog.getByRole("textbox",{name:"Symbol",exact:true}).fill("mdi:door-sliding");
  await expect(dialog.locator("[data-display-icon-preview]")).toHaveAttribute("icon","mdi:door-sliding");
  await dialog.getByRole("button",{name:"Nach oben",exact:true}).click();
  await dialog.getByRole("button",{name:"Abbrechen",exact:true}).click();
  await expect(window.locator(".sensor-line-title ha-icon")).toHaveAttribute("icon","mdi:door-sliding");
  await card.getByRole("button",{name:"Symbolküche bearbeiten",exact:true}).click();
  await dialog.getByText("Symbol anpassen",{exact:true}).click();
  await dialog.getByRole("button",{name:"Küche",exact:true}).click();
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await page.reload();
  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await expect(card.locator(".room-head-title ha-icon").first()).toHaveAttribute("icon","mdi:stove");
  await expect(window.locator(".sensor-line-title ha-icon")).toHaveAttribute("icon","mdi:door-sliding");
  await page.getByRole("tab",{name:"Live-Status"}).click();
  const live=page.locator("article.card").filter({has:page.getByRole("heading",{name:"Symbolküche",exact:true})});
  await expect(live.locator(".room-head ha-icon")).toHaveAttribute("icon","mdi:stove");
  await expect(live.locator(".sensor-line-title ha-icon")).toHaveCount(2);
  await expect(live.locator(".sensor-line-title ha-icon").nth(0)).toHaveAttribute("icon","mdi:door-sliding");
  await expect(live.locator(".sensor-line-title ha-icon").nth(1)).toHaveAttribute("icon","mdi:fridge-outline");
  const saved=await ws(page,"get");
  expect(saved.config.sensors["binary_sensor.symbol_fridge"].role).toBe("interior_motion");
  expect(saved.config.windows.symbol_window.icon).toBe("mdi:door-sliding");

  await page.getByRole("tab",{name:"Kameras & Sensoren"}).click();
  await page.setViewportSize({width:390,height:844});
  await fridge.click();
  await dialog.getByText("Symbol anpassen",{exact:true}).click();
  expect(await dialog.evaluate(el=>el.scrollWidth>el.clientWidth+1)).toBe(false);
  await dialog.screenshot({path:"test-results/display-symbol-picker-mobile.png"});
  await dialog.getByRole("button",{name:"Automatisch",exact:true}).click();
  await expect(dialog.locator("[data-display-icon-preview]")).toHaveAttribute("icon","mdi:motion-sensor");
  await dialog.getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(fridge.locator(".sensor-line-title ha-icon")).toHaveAttribute("icon","mdi:motion-sensor");
});
