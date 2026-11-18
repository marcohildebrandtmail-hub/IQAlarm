import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";

// A disposable browser-only backend. No HA connection or alarm services exist.
test.beforeEach(async({page})=>{
  await page.route("http://127.0.0.1/profile-scope",route=>route.fulfill({contentType:"text/html; charset=utf-8",body:`
    <iqalarm-panel></iqalarm-panel><script type="module">
    import "/modules/iqalarm-panel.js";
    const initial={config:{revision:1,secure_stage_id:"1",stages:["Aus","Sicher","Umfeld","Verdacht","Alarm","Eskalation"].map((name,i)=>({id:String(i),name,color:"#64bc29"})),
      rooms:{eg:{id:"eg",name:"Erdgeschoss"},og:{id:"og",name:"Elternbad OG"}},sensors:{},windows:{},robots:{},rules:{},actions:{},floorplans:{},room_connections:[],
      profiles:{night:{name:"Nacht",room_ids:null,sensor_ids:null,rule_ids:[],motion_mode:"after_contact",automatic_detection:true,contacts_enabled:true,reactions_enabled:true,simulation_enabled:false},away:{name:"Abwesend",room_ids:null,sensor_ids:null,rule_ids:[],motion_mode:"always",reactions_enabled:true}},
      ha_profile_ids:{armed_night:"night",armed_away:"away"},automatic_detection:{stage_id:"3",next_stage_id:"4",threshold:1,quiet_seconds:60,promote_seconds:30,test_mode:false},
      settings:{simulation_lights:[],simulation_start:18,simulation_end:23,retention_days:7,debounce_by_role:{},observation_profile_id:"live"}},status:{active:false,profile_id:null,mode:"inactive",level:0,stage_id:"0",events:[],rooms:{},quarantine:{},rule_progress:[]},information:[]};
    window.server=JSON.parse(localStorage.getItem("profile-server")||"null")||initial;
    const panel=document.querySelector("iqalarm-panel");panel.profile="night";panel.tab=4;window.saves=0;
    panel.hass={callWS:async message=>{
      if(message.type==="iqalarm/catalog")return {entities:[],areas:[],notify_services:[]};
      if(message.type!=="iqalarm/config/save")throw Error("Unexpected test request");
      if(message.revision!==window.server.config.revision)throw Error("Konfiguration wurde in einem anderen Fenster geändert. Bitte neu laden.");
      window.saves++;window.server.config=structuredClone(message.config);window.server.config.revision++;localStorage.setItem("profile-server",JSON.stringify(window.server));
      return structuredClone(window.server);
    },connection:{subscribeMessage:async callback=>{window.deliver=()=>callback(structuredClone(window.server));window.deliver();return ()=>{};}}};
    </script>`}));
  await page.route("http://127.0.0.1/modules/**",async route=>{
    const name=new URL(route.request().url()).pathname.split("/").pop();
    if(!/^[a-z-]+\.js$/.test(name))return route.abort();
    await route.fulfill({contentType:"application/javascript",body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto("http://127.0.0.1/profile-scope");
  await expect(page.getByRole("button",{name:"Profil speichern",exact:true})).toBeVisible();
});

async function updateScope(page,selection=["eg"]){
  await page.evaluate(selection=>{window.server.config.profiles.night.room_ids=selection;window.server.config.revision++;window.deliver();},selection);
}
async function editScope(page){
  await page.getByText("Räume und Sensoren begrenzen",{exact:true}).click();
  await page.getByLabel("Alle Räume einbeziehen",{exact:true}).uncheck();
  await page.locator('select[name="room_ids"]').selectOption("eg");
}

test("an unedited profile immediately shows externally saved room exclusions",async({page})=>{
  await expect(page.locator('[name="all_room_ids"]')).toBeChecked();
  await updateScope(page);
  await expect(page.locator('[name="all_room_ids"]')).not.toBeChecked();
  await expect(page.locator('select[name="room_ids"]')).toHaveValues(["eg"]);
  expect(await page.locator("iqalarm-panel").evaluate(p=>p._viewRevision)).toBe(2);
});

test("live status snapshots preserve unsaved room selection",async({page})=>{
  await editScope(page);
  await page.evaluate(()=>window.deliver());
  await expect(page.locator('[name="all_room_ids"]')).not.toBeChecked();
  await expect(page.locator('select[name="room_ids"]')).toHaveValues(["eg"]);
});

test("external changes preserve edits and stale saves cannot overwrite server scope",async({page})=>{
  await editScope(page);await updateScope(page,[]);
  await expect(page.locator('select[name="room_ids"]')).toHaveValues(["eg"]);
  await page.getByRole("button",{name:"Profil speichern",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("Konfiguration wurde in einem anderen Fenster geändert");
  expect(await page.evaluate(()=>window.saves)).toBe(0);
  expect(await page.evaluate(()=>window.server.config.profiles.night.room_ids)).toEqual([]);
});

test("unsaved simulation fields survive an external profile update",async({page})=>{
  await page.getByLabel("Lichtsimulation ab (Stunde)",{exact:true}).fill("19");
  await updateScope(page);
  await expect(page.getByLabel("Lichtsimulation ab (Stunde)",{exact:true})).toHaveValue("19");
});

test("icon button edits survive an external profile update",async({page})=>{
  await page.getByText("Profilsymbol ändern",{exact:true}).click();
  await page.getByRole("button",{name:"Symbol Garage",exact:true}).click();
  await updateScope(page);
  await expect(page.getByLabel("Profilsymbol",{exact:true})).toHaveValue("mdi:garage-variant");
});

test("saved exclusions survive profile changes, unrelated saves and page reload",async({page})=>{
  await editScope(page);
  await page.getByRole("button",{name:"Profil speichern",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("Gespeichert");
  await page.getByRole("button",{name:"Abwesend",exact:true}).click();
  await page.getByRole("button",{name:"Nacht",exact:true}).click();
  await expect(page.locator('[name="all_room_ids"]')).not.toBeChecked();
  await page.getByRole("button",{name:"System speichern",exact:true}).click();
  await expect(page.locator("#toast")).toContainText("Gespeichert");
  await page.reload();
  await expect(page.locator('[name="all_room_ids"]')).not.toBeChecked();
  await expect(page.locator('select[name="room_ids"]')).toHaveValues(["eg"]);
});
