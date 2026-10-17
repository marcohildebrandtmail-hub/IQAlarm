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
  await expect(page.getByText("Browser Fenster", {exact: true})).toBeVisible();
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
  await expect(page.getByRole("heading",{name:new RegExp("Alarm nach Maß$")})).toBeVisible();
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
  const svg=page.locator("#floorplan"); const rect=await svg.boundingBox();
  for (const [x,y] of [[.1,.1],[.5,.1],[.5,.8],[.1,.8]]) await svg.click({position:{x:x*rect.width,y:y*rect.height}});
  await page.getByRole("button",{name:"Bereich speichern",exact:true}).click();
  await expect(page.locator('#floorplan [data-room="living"]')).toHaveCount(1);
  await page.getByRole("tab",{name:"Live-Status"}).click();
  await expect(page.locator('#floorplan [data-room="living"]')).toBeVisible();
  // Real HA state endpoint, through the admin test session.
  await page.locator("iqalarm-panel").evaluate(async el => {
    const response=await el.hass.fetchWithAuth("/api/states/binary_sensor.window",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:"on"})});
    if (!response.ok) throw new Error("State update failed");
  });
  await expect(page.locator('#floorplan [data-room="living"]')).toHaveAttribute("aria-label",/Fenster \/ Tür offen/);
  await page.locator('#floorplan [data-room="living"]').focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("heading",{name:"Wohnzimmer",exact:true})).toHaveCount(2);
  await page.getByRole("button",{name:"Schließen",exact:true}).click();
  await page.screenshot({path:"test-results/floorplan-live.png",fullPage:true});
  await page.reload();
  await expect(page.locator('#floorplan [data-room="living"]')).toBeVisible();
  await page.locator("iqalarm-panel").evaluate(async el => {await el.hass.fetchWithAuth("/api/states/binary_sensor.window",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:"off"})});});
  expect(errors).toEqual([]);
});
