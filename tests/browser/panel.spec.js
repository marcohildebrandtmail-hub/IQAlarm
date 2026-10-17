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
