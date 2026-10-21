import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";

test.beforeEach(async({page})=>{
  await page.route("http://127.0.0.1/area-test",route=>route.fulfill({contentType:"text/html; charset=utf-8",body:'<script type="module" src="/iqalarm-static/iqalarm-panel.js"></script><iqalarm-panel></iqalarm-panel>'}));
  await page.route("http://127.0.0.1/iqalarm-static/**",async route=>{
    const name=new URL(route.request().url()).pathname.split("/").pop();
    if(!/^[a-z-]+\.js$/.test(name))return route.abort();
    await route.fulfill({contentType:"application/javascript; charset=utf-8",body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto("http://127.0.0.1/area-test");
  await page.waitForFunction(()=>customElements.get("iqalarm-panel"));
  await page.locator("iqalarm-panel").evaluate(panel=>{
    const rooms=Object.fromEntries(Object.entries({garden:"Garten Büroseite",office:"Büro",front:"Vorgarten",hall:"Flur UG",wardrobe:"Garderobe",wc:"WC",yard:"Garagenhof",utility:"HWR"}).map(([id,name])=>[id,{id,name,adjacent:[]}]))
    const sensor={entity_id:"binary_sensor.person",role:"perimeter_camera",name:"Person",room_id:"garden",front_of:["garden"],enabled:true};
    panel.catalog={entities:[],areas:[]};panel._connected=true;panel.tab=1;panel.plan="eg";panel.graphicPreview=false;
    panel.data={config:{revision:1,secure_stage_id:"secure",stages:[{id:"off",name:"Aus",color:"#ffffff"},{id:"secure",name:"Sicher",color:"#00ff00"}],rooms,sensors:{[sensor.entity_id]:sensor},windows:{},robots:{},actions:{},rules:null,
      profiles:{away:{name:"Abwesend",rule_ids:[],reactions_enabled:true}},room_connections:[["hall","office"]],outside_inside_links:[],
      floorplans:{eg:{id:"eg",name:"Erdgeschoss",width:1000,height:1000,image:"fixture",zones:{garden:[[.05,.65],[.3,.65],[.3,.95],[.05,.95]],office:[[.05,.35],[.3,.35],[.3,.6],[.05,.6]],front:[[.35,.65],[.65,.65],[.65,.95],[.35,.95]],hall:[[.35,.35],[.5,.35],[.5,.6],[.35,.6]],wardrobe:[[.35,.15],[.5,.15],[.5,.3],[.35,.3]],wc:[[.55,.35],[.65,.35],[.65,.6],[.55,.6]],yard:[[.7,.65],[.95,.65],[.95,.95],[.7,.95]],utility:[[.7,.35],[.95,.35],[.95,.6],[.7,.6]]},labels:{}}},
      settings:{debounce_by_role:{},simulation_lights:[],room_order:Object.keys(rooms)}},information:[],windows:{},window_details:{},status:{active:false,mode:"inactive",level:0,rooms:{},raw:{},last_active:{},rule_progress:[],monitored_sensors:[],quarantine:{}}};
    panel.__calls=[];panel._call=async(type,args)=>{if(type!=="config/save")throw Error(`Unexpected ${type}`);panel.__calls.push(structuredClone(args));return {...panel.data,config:{...args.config,revision:args.revision+1}};};
    panel.imageURLs.set("eg",{image:"fixture",url:"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"});
    panel._render();
  });
});

for(const width of [1440,390])test(`area mapping saves multiple indoor rooms, reloads and removes links at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  const form=page.locator('#outside-inside-form');
  await form.getByLabel('Außenbereich',{exact:true}).selectOption('front');
  for(const room of ['Flur UG','Garderobe','WC'])await form.getByLabel(room,{exact:true}).check();
  await form.getByRole('button',{name:'Zuordnung speichern',exact:true}).click();
  let data=await page.locator('iqalarm-panel').evaluate(p=>p.data.config);
  expect(data.outside_inside_links).toEqual([['front','hall'],['front','wardrobe'],['front','wc']]);
  expect(data.room_connections).toEqual([['hall','office']]);
  expect(data.sensors['binary_sensor.person'].front_of).toEqual(['garden']);
  await form.getByLabel('Außenbereich',{exact:true}).selectOption('garden');
  await form.getByLabel('Büro',{exact:true}).check();await form.getByRole('button',{name:'Zuordnung speichern',exact:true}).click();
  await form.getByLabel('Außenbereich',{exact:true}).selectOption('front');
  await expect(form.getByLabel('WC',{exact:true})).toBeChecked();
  await form.getByLabel('WC',{exact:true}).uncheck();await form.getByRole('button',{name:'Zuordnung speichern',exact:true}).click();
  data=await page.locator('iqalarm-panel').evaluate(p=>p.data.config);
  expect(data.outside_inside_links).toEqual([['garden','office'],['front','hall'],['front','wardrobe']]);
  await page.locator('iqalarm-panel').evaluate(p=>p._render());
  await expect(form.getByLabel('Flur UG',{exact:true})).toBeChecked();
  await expect(form.getByLabel('WC',{exact:true})).not.toBeChecked();
  const savedList=page.locator('[data-outside-inside] details');
  await savedList.locator('summary').click();
  await savedList.getByRole('button',{name:'Zuordnung Vorgarten → Garderobe löschen',exact:true}).click();
  await expect(savedList).toHaveAttribute('open','');
  data=await page.locator('iqalarm-panel').evaluate(p=>p.data.config);
  expect(data.outside_inside_links).toEqual([['garden','office'],['front','hall']]);
  expect(data.room_connections).toEqual([['hall','office']]);
  await expect(form.getByLabel('Garderobe',{exact:true})).not.toBeChecked();
  await expect(page.locator('[data-outside-inside-link="front:wardrobe"]')).toHaveCount(0);
  await expect(savedList.getByRole('button',{name:'Zuordnung Garten Büroseite → Büro löschen',exact:true})).toBeVisible();
  expect(await form.evaluate(f=>f.scrollWidth>f.clientWidth)).toBe(false);
  await page.locator('iqalarm-panel').evaluate(p=>{p.data.status.active=true;p._updateLock();});
  await expect(form.getByRole('button',{name:'Zuordnung speichern',exact:true})).toBeDisabled();
  await expect(form.getByLabel('Außenbereich',{exact:true})).toBeDisabled();
  await expect(savedList.getByRole('button',{name:'Zuordnung Garten Büroseite → Büro löschen',exact:true})).toBeDisabled();
});

for(const width of [1440,390])test(`draw example area links without changing real doors or showing links in live view at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  await page.getByRole('button',{name:'Außen → Innen markieren',exact:true}).click();
  const label=id=>page.locator(`#floorplan .room-label-group[data-room="${id}"]`);
  await page.getByLabel('Außenbereich',{exact:true}).selectOption('garden');
  await expect(label('garden')).toHaveClass(/door-selected/);
  await page.getByLabel('Außenbereich',{exact:true}).selectOption('');
  await label('garden').click();await label('office').click();
  await expect(page.locator('[data-outside-inside-link="garden:office"]')).toHaveCount(1);
  await label('garden').click();await label('front').click();
  for(const id of ['hall','wardrobe','wc'])await label(id).click();
  await label('front').click();await label('yard').click();
  await label('utility').focus();await label('utility').press('Enter');
  let config=await page.locator('iqalarm-panel').evaluate(p=>p.data.config);
  expect(config.outside_inside_links).toEqual([['garden','office'],['front','hall'],['front','wardrobe'],['front','wc'],['yard','utility']]);
  expect(config.room_connections).toEqual([['hall','office']]);
  await label('utility').click();
  await expect(page.locator('[data-outside-inside-link="yard:utility"]')).toHaveCount(0);
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.points.length)).toBe(0);
  await page.getByRole('button',{name:'Außen-/Innen-Markieren beenden',exact:true}).click();
  await page.getByRole('button',{name:'Fertige Raum-Grafik ansehen',exact:true}).first().click();
  await expect(page.locator('[data-outside-inside-link]')).toHaveCount(0);
  await page.getByRole('tab',{name:'Live-Status',exact:true}).click();
  await expect(page.locator('[data-outside-inside-link]')).toHaveCount(0);
});
