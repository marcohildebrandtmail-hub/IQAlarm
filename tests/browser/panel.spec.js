import { test, expect } from "@playwright/test";
import fs from "node:fs";

test.beforeEach(async ({page}) => {
  await page.goto("/iqalarm-test");
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
});

test("desktop cockpit and real room/sensor/action/profile CRUD", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.getByRole("heading", {name: "Dein Haus im Blick"})).toBeVisible();
  await expect(page.getByRole("button", {name: "Nacht", exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Räume & Topologie"}).click();
  await page.getByRole("button", {name: "Raum anlegen"}).click();
  await page.getByLabel("Raumname", {exact: true}).fill("Browser Büro");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Browser Büro", exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Sensoren & Prell-Schutz"}).click();
  await page.getByRole("button", {name: "binary_sensor.window bearbeiten", exact: true}).click();
  await page.getByLabel("Anzeigename", {exact: true}).fill("Browser Fenster");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Browser Fenster", {exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Alarmstufen & Regeln"}).click();
  await page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true}).fill("58");
  await page.getByRole("button", {name: "Profil speichern"}).click();
  await expect(page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true})).toHaveValue("58");
  await page.getByRole("tab", {name: "Aktionen & Push"}).click();
  await page.getByRole("button", {name: "Aktion hinzufügen"}).click();
  await page.getByLabel(/^Ziel \/ Dienst/).fill("notify.test_phone");
  await page.getByLabel(/^Nachricht/).fill("Browser-Test {{room}} {{sensor}}");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Browser-Test {{room}} {{sensor}}", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Stufe 1 trocken testen", exact: true}).click();
  await expect(page.getByText("Trockenlauf abgeschlossen. Keine Geräte wurden geschaltet.")).toBeVisible();
  await page.getByRole("tab", {name: "Live-Cockpit"}).click();
  await page.getByRole("button", {name: "Nacht", exact: true}).click();
  await expect(page.getByText("Nacht · Überwachung aktiv", {exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Räume & Topologie"}).click();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeDisabled();
  await page.getByRole("tab", {name: "Live-Cockpit"}).click();
  await page.getByRole("button", {name: "Unscharf", exact: true}).click();
  await page.getByLabel("PIN", {exact: true}).fill("2468");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Unscharf · Diagnose", {exact: true})).toBeVisible();
  expect(errors).toEqual([]);
  fs.mkdirSync("test-results", {recursive: true});
  await page.screenshot({path: "test-results/cockpit-desktop.png", fullPage: true});
});

test("mobile dark theme, accessible tabs, topology and form validation", async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => document.body.classList.add("dark"));
  await expect(page.getByRole("heading", {name: "Dein Haus im Blick"})).toBeVisible();
  const overflow = await page.locator("iqalarm-panel").evaluate(el => {
    const shell = el.shadowRoot.querySelector(".shell");
    return shell.scrollWidth > shell.clientWidth;
  });
  expect(overflow).toBe(false);
  await page.getByRole("tab", {name: "Räume & Topologie"}).click();
  await page.getByRole("button", {name: "Raum anlegen"}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", {name: "Abbrechen", exact: true}).click();
  await page.getByRole("tab", {name: "Live-Cockpit"}).click();
  await page.screenshot({path: "test-results/cockpit-mobile-dark.png", fullPage: true});
});

test("all tabs render and untrusted labels stay text", async ({page}) => {
  for (const name of ["Räume & Topologie", "Sensoren & Prell-Schutz", "Alarmstufen & Regeln", "Aktionen & Push", "Live-Cockpit"]) {
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
  await page.getByRole("tab", {name: "Räume & Topologie"}).click();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeEnabled();
  await page.evaluate(() => window.iqTest.disconnect());
  await expect(page.getByText("Verbindung unterbrochen", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Raum anlegen"})).toBeDisabled();
});

test("custom profiles can be created, scoped, copied, armed and deleted in the panel", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.getByRole("tab", {name: "Alarmstufen & Regeln"}).click();
  await page.getByRole("button", {name: "Profil anlegen", exact: true}).click();
  await page.getByRole("dialog").getByLabel("Profilname", {exact: true}).fill("Nacht mit Gästen");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht mit Gästen · Korrelations-Matrix"})).toBeVisible();
  await expect(page.locator("#rules-form").getByLabel(/^Basis und HA-Modus/)).toBeEnabled();
  await page.getByLabel("Alle Räume einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Räume auswählen", {exact: false}).selectOption({label: "Wohnzimmer"});
  await page.getByLabel("Alle Sensoren einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Sensoren auswählen", {exact: false}).selectOption("binary_sensor.window");
  await page.getByLabel("Alle Aktionen einbeziehen", {exact: true}).uncheck();
  await page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true}).fill("39");
  await page.getByRole("button", {name: "Profil speichern", exact: true}).click();
  await expect(page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true})).toHaveValue("39");
  await page.screenshot({path: "test-results/profiles-desktop.png", fullPage: true});
  await page.reload();
  await expect(page.getByText("Live verbunden · lokal")).toBeVisible();
  await page.getByRole("tab", {name: "Alarmstufen & Regeln"}).click();
  await page.getByRole("button", {name: "Nacht mit Gästen", exact: true}).click();
  await expect(page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true})).toHaveValue("39");
  await expect(page.getByLabel("Alle Räume einbeziehen", {exact: true})).not.toBeChecked();
  await page.getByRole("button", {name: "Duplizieren", exact: true}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Nacht mit Gästen Kopie · Korrelations-Matrix"})).toBeVisible();
  await expect(page.getByLabel("Korrelation T_corr (Sekunden)", {exact: true})).toHaveValue("39");
  await page.getByRole("button", {name: "Löschen", exact: true}).click();
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByRole("button", {name: "Nacht mit Gästen Kopie", exact: true})).toHaveCount(0);
  await page.getByRole("tab", {name: "Live-Cockpit"}).click();
  await page.getByRole("button", {name: "Nacht mit Gästen", exact: true}).click();
  await expect(page.getByText("Nacht mit Gästen · Überwachung aktiv", {exact: true})).toBeVisible();
  await expect(page.getByText("Home Assistant: Nacht · 1 Sensor im Profil", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Nacht", exact: true})).toBeDisabled();
  const state = await page.evaluate(() => window.iqTest.request({type: "iqalarm/get"}));
  expect(state.status.mode).toBe("armed_night");
  expect(state.status.profile_name).toBe("Nacht mit Gästen");
  await page.getByRole("button", {name: "Unscharf", exact: true}).click();
  await page.getByLabel("PIN", {exact: true}).fill("2468");
  await page.getByRole("button", {name: "Speichern", exact: true}).click();
  await expect(page.getByText("Unscharf · Diagnose", {exact: true})).toBeVisible();
  await page.getByRole("tab", {name: "Alarmstufen & Regeln"}).click();
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
    await window.iqTest.request({type: "iqalarm/crud", collection: "profiles", operation: "save", revision: data.config.revision, item: {id: "panel_escaped", name: profileName, base_mode: "armed_night", action_ids: []}});
  }, name);
  await expect(page.getByRole("button", {name, exact: true})).toBeVisible();
  await page.getByRole("button", {name, exact: true}).click();
  await expect(page.getByText(`${name} · Überwachung aktiv`, {exact: true})).toBeVisible();
  const overflow = await page.locator("iqalarm-panel").evaluate(el => {
    const shell = el.shadowRoot.querySelector(".shell");
    return shell.scrollWidth > shell.clientWidth;
  });
  expect(overflow).toBe(false);
  expect(await page.evaluate(() => window.__profileInjected)).toBeUndefined();
  await page.screenshot({path: "test-results/profiles-mobile-dark.png", fullPage: true});
  await page.getByRole("tab", {name: "Alarmstufen & Regeln"}).click();
  await page.getByRole("button", {name, exact: true}).click();
  await expect(page.locator('#rules-form input[name="profile_name"]')).toHaveValue(name);
  expect(await page.evaluate(() => window.__profileInjected)).toBeUndefined();
  await page.evaluate(async () => {
    await window.iqTest.request({type: "iqalarm/set_mode", mode: "disarmed", code: "2468"});
    const data = await window.iqTest.request({type: "iqalarm/get"});
    await window.iqTest.request({type: "iqalarm/crud", collection: "profiles", operation: "delete", revision: data.config.revision, key: "panel_escaped"});
  });
});
