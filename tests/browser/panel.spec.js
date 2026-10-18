import { test, expect } from "@playwright/test";
import fs from "node:fs";

test.beforeEach(async ({page}) => {
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
});

test("desktop cockpit and real room/sensor/action/profile CRUD", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.getByRole("heading", {name: "Dein Haus im Überblick"})).toBeVisible();
  await expect(page.getByText("Signale verstehen. Ereignisse bestätigen. Gezielt reagieren.")).toHaveCount(0);
  await expect(page.getByRole("button", {name: "Live-Beobachtung"})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "Nacht", exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Räume & Grundriss"}).click();
  await page.getByRole("button", {name: "Raum anlegen"}).click();
  await page.getByLabel("Raumname", {exact: true}).fill("Browser Büro");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Browser Büro", exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Kameras & Sensoren"}).click();
  await expect(page.getByRole("heading", {name: /Kameras & Außensensoren/})).toBeVisible();
  await page.getByRole("button", {name: "binary_sensor.window bearbeiten", exact: true}).click();
  await page.getByLabel("Anzeigename", {exact: true}).fill("Browser Fenster");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Browser Fenster", {exact: true}).first()).toBeVisible();
  await page.getByRole("tab", {name: "Profile & System"}).click();
  await page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true}).fill("58");
  await page.getByRole("button", {name: "Profil speichern"}).click();
  await expect(page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true})).toHaveValue("58");
  await page.getByRole("tab", {name: "Level-Konfiguration"}).click();
  await page.getByRole("button", {name: "Aktion hinzufügen"}).click();
  await page.getByLabel(/^Ziel \/ Dienst/).fill("notify.test_phone");
  await page.getByLabel(/^Nachricht/).fill("Browser-Test {{room}} {{sensor}}");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Browser-Test {{room}} {{sensor}}", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Stufe 1 trocken testen", exact: true}).click();
  await expect(page.getByText("Trockenlauf abgeschlossen. Keine Geräte wurden geschaltet.")).toBeVisible();
  await page.getByRole("tab", {name: "Live-Status"}).click();
  await page.getByRole("button", {name: "Nacht", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht", exact: true})).toBeVisible();
  await expect(page.getByText("Alarmreaktionen aktiv", {exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Räume & Grundriss"}).click();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeDisabled();
  await page.getByRole("tab", {name: "Live-Status"}).click();
  await page.getByRole("button", {name: "Aus", exact: true}).click();
  await page.getByLabel("PIN", {exact: true}).fill("2468");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Anlage aus", exact: true})).toBeVisible();
  expect(errors).toEqual([]);
  fs.mkdirSync("test-results", {recursive: true});
  await page.screenshot({path: "test-results/cockpit-desktop.png", fullPage: true});
});

test("mobile dark theme, accessible tabs, topology and form validation", async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => document.body.classList.add("dark"));
  await expect(page.getByRole("heading", {name: "Dein Haus im Überblick"})).toBeVisible();
  const overflow = await page.locator("iqalarm-panel").evaluate(el => {
    const shell = el.shadowRoot.querySelector(".shell");
    return shell.scrollWidth > shell.clientWidth;
  });
  expect(overflow).toBe(false);
  await page.getByRole("tab", {name: "Räume & Grundriss"}).click();
  await page.getByRole("button", {name: "Raum anlegen"}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", {name: "Abbrechen", exact: true}).click();
  await page.getByRole("tab", {name: "Live-Status"}).click();
  await page.screenshot({path: "test-results/cockpit-mobile-dark.png", fullPage: true});
});

test("all tabs render and untrusted labels stay text", async ({page}) => {
  for (const name of ["Räume & Grundriss", "Kameras & Sensoren", "Level-Konfiguration", "Profile & System", "Live-Status"]) {
    await page.getByRole("tab", {name, exact: true}).click();
    await expect(page.locator("iqalarm-panel").locator("main")).toBeVisible();
  }
  await page.evaluate(async () => {
    const data = await window.iqTest.request({type: "iqalarm/get"});
    await window.iqTest.request({type: "iqalarm/crud", collection: "rooms", operation: "save", revision: data.config.revision, item: {id: "escaped", name: '<img src=x onerror="window.__injected=true">'}});
  });
  await expect(page.getByRole("heading", {name: '<img src=x onerror="window.__injected=true">', exact: true})).toBeVisible();
  expect(await page.evaluate(() => window.__injected)).toBeUndefined();
});

test("lost websocket is visible and configuration becomes read-only", async ({page}) => {
  await page.getByRole("tab", {name: "Räume & Grundriss"}).click();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeEnabled();
  await page.evaluate(() => window.iqTest.disconnect());
  await expect(page.getByText("Verbindung unterbrochen", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeDisabled();
});

test("custom profiles can be created, sorted, scoped, copied, armed and deleted in the panel", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.getByRole("tab", {name: "Profile & System"}).click();
  await page.getByRole("button", {name: "Profil anlegen", exact: true}).click();
  await page.getByRole("dialog").getByLabel("Profilname", {exact: true}).fill("Nacht mit Gästen");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht mit Gästen"})).toBeVisible();
  await expect(page.locator("#rules-form").getByLabel(/^Basis und HA-Modus/)).toHaveCount(0);
  await page.getByRole("button", {name: "Profil nach links verschieben", exact: true}).click();
  const reordered = await page.evaluate(() => window.iqTest.request({type: "iqalarm/get"}));
  expect(Object.values(reordered.config.profiles).at(-2).name).toBe("Nacht mit Gästen");
  await page.getByLabel("Alarmreaktionen und Geräteaktionen erlauben",{exact:true}).check();
  await page.getByLabel("Alle Räume einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Räume auswählen", {exact: false}).selectOption({label: "Wohnzimmer"});
  await page.getByLabel("Alle Sensoren einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Sensoren auswählen", {exact: false}).selectOption("binary_sensor.window");
  await page.getByLabel("Alle Aktionen einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true}).fill("39");
  await page.getByRole("button", {name: "Profil speichern", exact: true}).click();
  await expect(page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true})).toHaveValue("39");
  await page.screenshot({path: "test-results/profiles-desktop.png", fullPage: true});
  await page.reload();
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  await page.getByRole("tab", {name: "Profile & System"}).click();
  await page.getByRole("button", {name: "Nacht mit Gästen", exact: true}).click();
  await expect(page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true})).toHaveValue("39");
  await expect(page.getByLabel("Alle Räume einbeziehen", {exact: true})).not.toBeChecked();
  await page.getByRole("button", {name: "Duplizieren", exact: true}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht mit Gästen Kopie"})).toBeVisible();
  await expect(page.getByLabel("Korrelationsfenster (Sekunden)", {exact: true})).toHaveValue("39");
  await page.getByRole("button", {name: "Löschen", exact: true}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("button", {name: "Nacht mit Gästen Kopie", exact: true})).toHaveCount(0);
  await page.getByRole("tab", {name: "Live-Status"}).click();
  await page.getByRole("button", {name: "Nacht mit Gästen", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht mit Gästen", exact: true})).toBeVisible();
  await expect(page.getByText("1 Sensoren ausgewertet · Home Assistant: An", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Nacht", exact: true})).toBeDisabled();
  const state = await page.evaluate(() => window.iqTest.request({type: "iqalarm/get"}));
  expect(state.status.mode).toBe("active");
  expect(state.status.profile_name).toBe("Nacht mit Gästen");
  await page.getByRole("button", {name: "Aus", exact: true}).click();
  await page.getByLabel("PIN", {exact: true}).fill("2468");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Anlage aus", exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Profile & System"}).click();
  await page.getByRole("button", {name: "Nacht mit Gästen", exact: true}).click();
  await page.getByRole("button", {name: "Löschen", exact: true}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("button", {name: "Nacht mit Gästen", exact: true})).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("custom profile names stay text on mobile and in the rule editor", async ({page}) => {
  const name = '<img src=x onerror="window.__profileInjected=true">';
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(async profileName => {
    document.body.classList.add("dark");
    const data = await window.iqTest.request({type: "iqalarm/get"});
    await window.iqTest.request({type: "iqalarm/crud", collection: "profiles", operation: "save", revision: data.config.revision, item: {id: "panel_escaped", name: profileName, motion_mode: "after_contact", action_ids: []}});
  }, name);
  await expect(page.getByRole("button", {name, exact: true})).toBeVisible();
  await page.getByRole("button", {name, exact: true}).click();
  await expect(page.getByRole("heading", {name, exact: true})).toBeVisible();
  const overflow = await page.locator("iqalarm-panel").evaluate(el => {
    const shell = el.shadowRoot.querySelector(".shell");
    return shell.scrollWidth > shell.clientWidth;
  });
  expect(overflow).toBe(false);
  expect(await page.evaluate(() => window.__profileInjected)).toBeUndefined();
  await page.screenshot({path: "test-results/profiles-mobile-dark.png", fullPage: true});
  await page.getByRole("tab", {name: "Profile & System"}).click();
  await page.getByRole("button", {name, exact: true}).click();
  await expect(page.locator('#rules-form input[name="profile_name"]')).toHaveValue(name);
  expect(await page.evaluate(() => window.__profileInjected)).toBeUndefined();
  await page.evaluate(async () => {
    await window.iqTest.request({type: "iqalarm/set_mode", mode: "disarmed", code: "2468"});
    const data = await window.iqTest.request({type: "iqalarm/get"});
    await window.iqTest.request({type: "iqalarm/crud", collection: "profiles", operation: "delete", revision: data.config.revision, key: "panel_escaped"});
  });
});

test("custom stage count, labels and rule targets are saved without HA mapping", async ({page}) => {
  await page.evaluate(() => { delete Crypto.prototype.randomUUID; });
  await page.getByRole("tab",{name:"Level-Konfiguration"}).click();
  const rows = page.locator("[data-stage-row]");
  const original = await rows.count();
  await page.locator("#stages-form").getByRole("button",{name:"Stufe hinzufügen",exact:true}).click();
  await expect(rows).toHaveCount(original+1);
  await rows.last().locator('[name="stage_name"]').fill("Alarm nach Maß");
  await rows.last().getByLabel("Bestätigung erforderlich",{exact:true}).check();
  await rows.last().getByLabel("Akustische / freie Aktionen erlauben",{exact:true}).check();
  await page.getByRole("button",{name:"Alarmstufen speichern",exact:true}).click();
  await page.getByRole("button",{name:new RegExp("Alarm nach Maß$")}).click();
  await expect(page.getByRole("heading",{name:`LVL ${original} · Alarm nach Maß`,exact:true})).toBeVisible();
  await page.getByRole("tab",{name:"Profile & System"}).click();
  await expect(page.locator('[name="target_contact_motion"] option').filter({hasText:"Alarm nach Maß"})).toHaveCount(1);
  await page.locator('[name="target_contact_motion"]').selectOption({label:`${original} · Alarm nach Maß`});
  await page.getByRole("button",{name:"Profil speichern",exact:true}).click();
  const state = await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  expect(state.config.stages.at(-1).name).toBe("Alarm nach Maß");
  expect(state.config.profiles.armed_night.stage_targets.contact_motion).toBe(state.config.stages.at(-1).id);
  expect(state.config.profiles.armed_night.base_mode).toBeUndefined();
  // Restore the mapping before removing the added stage.
  await page.evaluate(async () => {
    const data=await window.iqTest.request({type:"iqalarm/get"});
    data.config.profiles.armed_night.stage_targets.contact_motion="3";
    data.config.stages.pop();
    await window.iqTest.request({type:"iqalarm/config/save",config:data.config,revision:data.config.revision});
  });
});

test("floorplan upload, room polygon, live state and keyboard room details", async ({page}) => {
  const errors=[]; page.on("pageerror",error => errors.push(error.message));
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.getByRole("button",{name:"Grundriss anlegen",exact:true}).click();
  await page.getByLabel("Etage / Name",{exact:true}).fill("Test-Erdgeschoss");
  await page.getByRole("button",{name:"Speichern",exact:true}).click();
  const png=await page.evaluate(() => {const canvas=document.createElement("canvas");canvas.width=600;canvas.height=400;const ctx=canvas.getContext("2d");ctx.fillStyle="#eef1f4";ctx.fillRect(0,0,600,400);ctx.strokeStyle="#334455";ctx.lineWidth=6;ctx.strokeRect(35,35,530,330);ctx.strokeRect(35,35,300,330);return canvas.toDataURL("image/png").split(",")[1];});
  await page.locator("#plan-upload").setInputFiles({name:"test-grundriss.png",mimeType:"image/png",buffer:Buffer.from(png,"base64")});
  await expect(page.locator("#floorplan")).toBeVisible();
  await page.locator("#zone-room").selectOption("living");
  await page.getByRole("button",{name:"Neu zeichnen",exact:true}).click();
  const svg=page.locator("#floorplan"); const rect=await svg.boundingBox();
  for (const [x,y] of [[.1,.1],[.5,.1],[.5,.8],[.1,.8]]) await svg.click({position:{x:x*rect.width,y:y*rect.height}});
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await expect(page.locator('#floorplan [data-room="living"]:not([data-label-room])')).toHaveCount(1);
  const savedPlan=await page.locator("iqalarm-panel").evaluate(el=>el.plan);
  const liveRoom=page.locator(`#floorplan-${savedPlan} [data-room="living"]:not([data-label-room])`);
  await page.getByRole("tab",{name:"Live-Status"}).click();
  await expect(liveRoom).toBeVisible();
  // Real HA state endpoint, through the admin test session.
  await page.locator("iqalarm-panel").evaluate(async el => {
    const response=await el.hass.fetchWithAuth("/api/states/binary_sensor.window",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:"on"})});
    if (!response.ok) throw new Error("State update failed");
  });
  await expect(liveRoom).toHaveAttribute("aria-label",/Fenster offen/);
  await liveRoom.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("heading",{name:"Wohnzimmer",exact:true})).toHaveCount(2);
  await page.getByRole("button",{name:"Schließen",exact:true}).click();
  await page.screenshot({path:"test-results/floorplan-live.png",fullPage:true});
  await page.reload();
  await expect(liveRoom).toBeVisible();
  await page.locator("iqalarm-panel").evaluate(async el => {await el.hass.fetchWithAuth("/api/states/binary_sensor.window",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:"off"})});});
  expect(errors).toEqual([]);
});

test("profile icons can be chosen, persisted and displayed without changing rules", async ({page}) => {
  await expect(page.getByRole("button",{name:"Nacht",exact:true}).locator("ha-icon")).toHaveAttribute("icon","mdi:weather-night");
  await expect(page.getByRole("button",{name:"Zuhause",exact:true}).locator("ha-icon")).toHaveAttribute("icon","mdi:home-outline");
  await page.getByRole("tab",{name:"Profile & System"}).click();
  await page.getByRole("button",{name:"Nacht",exact:true}).click();
  const before=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  await page.locator("#rules-form").getByRole("button",{name:"Symbol Besuch",exact:true}).click();
  await expect(page.getByLabel("Profilsymbol",{exact:true})).toHaveValue("mdi:account-group-outline");
  await page.getByRole("button",{name:"Profil speichern",exact:true}).click();
  await page.reload();
  await expect(page.getByRole("button",{name:"Nacht",exact:true}).locator("ha-icon")).toHaveAttribute("icon","mdi:account-group-outline");
  const after=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  expect(after.config.profiles.armed_night.motion_mode).toBe(before.config.profiles.armed_night.motion_mode);
  expect(after.config.profiles.armed_night.stage_targets).toEqual(before.config.profiles.armed_night.stage_targets);
  await page.getByRole("tab",{name:"Profile & System"}).click();
  await page.getByLabel("Profilsymbol",{exact:true}).fill("mdi:cat");
  await expect(page.locator("[data-icon-preview]")).toHaveAttribute("icon","mdi:cat");
  await page.getByRole("button",{name:"Profil speichern",exact:true}).click();
  await page.getByRole("tab",{name:"Live-Status"}).click();
  await expect(page.getByRole("button",{name:"Nacht",exact:true}).locator("ha-icon")).toHaveAttribute("icon","mdi:cat");
  await page.evaluate(async () => {
    const data=await window.iqTest.request({type:"iqalarm/get"});
    data.config.profiles.armed_night.icon="mdi:weather-night";
    await window.iqTest.request({type:"iqalarm/config/save",config:data.config,revision:data.config.revision});
  });
});

test("direct upload opens file picker and room proposals remain editable until saved", async ({page}) => {
  const errors=[];page.on("pageerror",error => errors.push(error.message));
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  const existing=await page.getByRole("button",{name:"Weitere Etage hochladen",exact:true}).count();
  await page.getByRole("button",{name:existing ? "Weitere Etage hochladen" : "Grundriss hochladen",exact:true}).click();
  await expect(page.getByRole("dialog").getByRole("heading",{name:"Grundriss hochladen",exact:true})).toBeVisible();
  await page.getByLabel("Etage / Name",{exact:true}).fill("Assistent-Etage");
  const before=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  await page.locator('input[name="image"]').setInputFiles({name:"kaputt.png",mimeType:"image/png",buffer:Buffer.from("broken image")});
  await page.getByRole("button",{name:"Hochladen",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("Ungültiges");
  const failed=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  expect(failed.config.revision).toBe(before.config.revision);
  expect(Object.keys(failed.config.floorplans)).toHaveLength(Object.keys(before.config.floorplans).length);
  const png=await page.evaluate(() => {const canvas=document.createElement("canvas");canvas.width=500;canvas.height=300;const ctx=canvas.getContext("2d");ctx.fillStyle="white";ctx.fillRect(0,0,500,300);ctx.strokeStyle="black";ctx.lineWidth=6;ctx.strokeRect(30,30,440,240);ctx.beginPath();ctx.moveTo(250,30);ctx.lineTo(250,270);ctx.stroke();return canvas.toDataURL("image/png").split(",")[1];});
  const chooserPromise=page.waitForEvent("filechooser");
  await page.locator('input[name="image"]').click();
  const chooser=await chooserPromise;
  await chooser.setFiles({name:"grundriss.png",mimeType:"image/png",buffer:Buffer.from(png,"base64")});
  await page.getByRole("button",{name:"Hochladen",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("#floorplan")).toBeVisible();
  await expect(page.getByText("2 Flächen vorgeschlagen",{exact:true})).toBeVisible();
  const proposals=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  const plan=Object.values(proposals.config.floorplans).find(item => item.name === "Assistent-Etage");
  expect(plan.zones).toEqual({});
  await page.locator("#plan-candidate").selectOption("1");
  await page.locator("#zone-room").selectOption("living");
  const handle=page.locator('[data-draft-vertex="0"]');
  await expect(handle).toBeVisible();
  await handle.scrollIntoViewIfNeeded();
  const beforeDrag=await handle.getAttribute("cx");
  const bounds=await handle.boundingBox();
  await page.mouse.move(bounds.x+bounds.width/2,bounds.y+bounds.height/2);
  await page.mouse.down();await page.mouse.move(bounds.x+bounds.width/2+12,bounds.y+bounds.height/2+10,{steps:4});await page.mouse.up();
  expect(await handle.getAttribute("cx")).not.toBe(beforeDrag);
  await handle.focus();
  const keyboardBefore=Number(await handle.getAttribute("cx"));
  await page.keyboard.press("ArrowRight");
  expect(Number(await handle.getAttribute("cx"))).toBeGreaterThan(keyboardBefore);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  const saved=await page.evaluate(() => window.iqTest.request({type:"iqalarm/get"}));
  expect(saved.config.floorplans[plan.id].zones.living.length).toBeGreaterThanOrEqual(3);
  await page.screenshot({path:"test-results/floorplan-assistant.png",fullPage:true});
  await page.reload();
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator("#plan-select").selectOption(plan.id);
  await expect(page.locator('#floorplan [data-room="living"]:not([data-label-room])')).toBeVisible();
  await expect(page.getByRole("button",{name:"Bild ersetzen",exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

async function prepareDraftPlan(page, id) {
  await page.evaluate(async id => {
    const data=await window.iqTest.request({type:"iqalarm/get"});
    const source=Object.values(data.config.floorplans).find(plan=>plan.image);
    if (!source) throw new Error("Fixture image is missing");
    data.config.rooms.draft_hall={id:"draft_hall",name:"Entwurf Flur",adjacent:[],area_id:null,home_enabled:false};
    data.config.floorplans[id]={...structuredClone(source),id,name:`Entwurf ${id}`,zones:{living:[[.1,.1],[.45,.1],[.45,.9],[.1,.9]],draft_hall:[[.55,.1],[.9,.1],[.9,.9],[.55,.9]]}};
    await window.iqTest.request({type:"iqalarm/config/save",config:data.config,revision:data.config.revision});
  },id);
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await page.locator("#plan-select").selectOption(id);
  await expect(page.locator("#floorplan")).toBeVisible();
}

test("saving an unassigned edited area and selecting an existing room never resets points", async ({page})=>{
  await prepareDraftPlan(page,"draft_loss");
  await page.getByRole("button",{name:"Neu zeichnen",exact:true}).click();
  const svg=page.locator("#floorplan"), bounds=await svg.boundingBox();
  for(const [x,y] of [[.15,.15],[.4,.15],[.4,.8],[.15,.8]]) await svg.click({position:{x:x*bounds.width,y:y*bounds.height}});
  const handle=page.locator('[data-draft-vertex="1"]');await handle.focus();await page.keyboard.press("ArrowRight");
  await page.locator('[data-draft-vertex="2"]').focus();await page.keyboard.press("Delete");
  const edited=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  expect(edited).toHaveLength(3);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await expect(page.getByRole("dialog").getByRole("heading",{name:"Fläche einem Raum zuordnen"})).toBeVisible();
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Abbrechen",exact:true}).click();
  await page.locator("#zone-room").selectOption("living");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(saved.config.floorplans.draft_loss.zones.living).toEqual(edited);
  expect(saved.config.floorplans.draft_loss.zones.draft_hall).toEqual([[.55,.1],[.9,.1],[.9,.9],[.55,.9]]);
});

test("room reassignment, another floor, analysis and reload retain unsaved edits with undo",async({page})=>{
  await prepareDraftPlan(page,"draft_reload");
  await page.locator("#zone-room").selectOption("living");
  const original=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  await page.locator('[data-draft-vertex="0"]').focus();await page.keyboard.press("ArrowRight");
  const edited=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  expect(edited).not.toEqual(original);
  await page.locator("#zone-room").selectOption("draft_hall");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Rückgängig",exact:true}).click();
  await expect(page.locator("#zone-room")).toHaveValue("living");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Rückgängig",exact:true}).click();
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(original);
  await page.getByRole("button",{name:"Wiederholen",exact:true}).click();
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Flächen erkennen",exact:true}).click();
  await expect(page.getByText(/Flächen vorgeschlagen/)).toBeVisible();
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  const other=await page.locator("#plan-select option").first().getAttribute("value");
  await page.locator("#plan-select").selectOption(other);
  await page.locator("#plan-select").selectOption("draft_reload");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.reload();
  await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await expect(page.locator("#plan-select")).toHaveValue("draft_reload");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await expect(page.locator("#draft-status")).toContainText("im Browser gesichert");
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(saved.config.floorplans.draft_reload.zones.living).toEqual(edited);
  await page.screenshot({path:"test-results/floorplan-restored-draft.png",fullPage:true});
});

test("save dialog assigns an existing room directly without discarding edited proposal",async({page})=>{
  await prepareDraftPlan(page,"draft_dialog");
  await page.getByRole("button",{name:"Flächen erkennen",exact:true}).click();
  await page.locator("#plan-candidate").selectOption("1");
  await page.locator('[data-draft-vertex="0"]').focus();await page.keyboard.press("ArrowRight");
  const edited=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  await page.locator("#plan-candidate").selectOption("1");
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Vorhandener Raum",{exact:true}).selectOption("living");
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(saved.config.floorplans.draft_dialog.zones.living).toEqual(edited);
});

test("save dialog creates a room and stores its corrected area together",async({page})=>{
  await page.evaluate(() => { delete Crypto.prototype.randomUUID; });
  await prepareDraftPlan(page,"draft_new_room");
  await page.getByRole("button",{name:"Neu zeichnen",exact:true}).click();
  const svg=page.locator("#floorplan"),bounds=await svg.boundingBox();
  for(const [x,y] of [[.16,.16],[.39,.16],[.39,.7],[.16,.7]]) await svg.click({position:{x:x*bounds.width,y:y*bounds.height}});
  const points=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Oder neuen Raum anlegen",{exact:true}).fill("Neuer Grundrissraum");
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  const room=Object.values(saved.config.rooms).find(room=>room.name === "Neuer Grundrissraum");
  expect(room).toBeDefined();
  expect(saved.config.floorplans.draft_new_room.zones[room.id]).toEqual(points);
  expect(saved.config.floorplans.draft_new_room.zones.living).toEqual([[.1,.1],[.45,.1],[.45,.9],[.1,.9]]);
});

test("assignment dialog lists fresh HA areas and atomically links only the selected area",async({page})=>{
  await prepareDraftPlan(page,"ha_area_dialog");
  const area=await page.evaluate(()=>window.iqTest.request({type:"config/area_registry/create",name:"Browser HA Esszimmer"}));
  await page.getByRole("button",{name:"Neu zeichnen",exact:true}).click();
  const svg=page.locator("#floorplan"),bounds=await svg.boundingBox();
  for(const [x,y] of [[.2,.2],[.4,.2],[.4,.7],[.2,.7]]) await svg.click({position:{x:x*bounds.width,y:y*bounds.height}});
  await page.locator('[data-draft-vertex="1"]').focus();await page.keyboard.press("ArrowRight");
  const points=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  const before=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  const choice=page.getByRole("dialog").getByLabel("Vorhandener Raum",{exact:true});
  await expect(choice.locator('optgroup[label="Home-Assistant-Bereiche"] option')).toContainText([area.name]);
  await choice.selectOption({label:area.name});
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(points);
  const uncommitted=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(uncommitted.config).toEqual(before.config);
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  const linked=Object.values(saved.config.rooms).filter(room=>room.area_id === area.area_id);
  expect(linked).toHaveLength(1);expect(linked[0].name).toBe(area.name);
  expect(Object.keys(saved.config.rooms)).toHaveLength(Object.keys(before.config.rooms).length+1);
  expect(saved.config.floorplans.ha_area_dialog.zones[linked[0].id]).toEqual(points);
  expect(saved.config.sensors).toEqual(before.config.sensors);
  await expect(page.locator("#zone-room option").filter({hasText:area.name})).toHaveCount(1);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  const repeated=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(Object.values(repeated.config.rooms).filter(room=>room.area_id === area.area_id)).toHaveLength(1);
});

test("HA area selection in the editor survives reload and preserves corrected points",async({page})=>{
  const area=await page.evaluate(()=>window.iqTest.request({type:"config/area_registry/create",name:"Browser HA Hauswirtschaft"}));
  await page.reload();
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  await prepareDraftPlan(page,"ha_area_reload");
  await page.getByRole("button",{name:"Flächen erkennen",exact:true}).click();
  await page.locator("#plan-candidate").selectOption("1");
  await page.locator('[data-draft-vertex="0"]').focus();await page.keyboard.press("ArrowRight");
  const edited=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  await page.locator("#zone-room").selectOption({label:area.name});
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.reload();await page.getByRole("tab",{name:"Räume & Grundriss"}).click();
  await expect(page.locator("#zone-room")).toHaveValue(`ha-area:${area.area_id}`);
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(edited);
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await expect(page.locator("#draft-status")).toHaveText("Bereich gespeichert");
  const saved=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  const room=Object.values(saved.config.rooms).find(room=>room.area_id === area.area_id);
  expect(saved.config.floorplans.ha_area_reload.zones[room.id]).toEqual(edited);
});

test("an HA area removed while the dialog is open leaves the entire draft intact",async({page})=>{
  await prepareDraftPlan(page,"ha_area_removed");
  const area=await page.evaluate(()=>window.iqTest.request({type:"config/area_registry/create",name:"Browser HA Entfernt"}));
  await page.getByRole("button",{name:"Flächen erkennen",exact:true}).click();
  await page.locator("#plan-candidate").selectOption("1");
  const points=await page.locator("iqalarm-panel").evaluate(el=>structuredClone(el.points));
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Vorhandener Raum",{exact:true}).selectOption({label:area.name});
  await page.evaluate(area_id=>window.iqTest.request({type:"config/area_registry/delete",area_id}),area.area_id);
  const before=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  await page.getByRole("dialog").getByRole("button",{name:"Speichern",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("wurde entfernt");
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await page.locator("iqalarm-panel").evaluate(el=>el.points)).toEqual(points);
  const after=await page.evaluate(()=>window.iqTest.request({type:"iqalarm/get"}));
  expect(after.config).toEqual(before.config);
});
