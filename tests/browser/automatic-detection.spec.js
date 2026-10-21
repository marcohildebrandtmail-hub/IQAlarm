import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";

test.beforeEach(async({page})=>{
  await page.clock.install({time:new Date('2026-10-20T12:00:00Z')});
  await page.route("http://127.0.0.1/automatic-test",route=>route.fulfill({contentType:"text/html; charset=utf-8",body:'<script type="module" src="/iqalarm-static/iqalarm-panel.js"></script><body><iqalarm-panel></iqalarm-panel></body>'}));
  await page.route("http://127.0.0.1/iqalarm-static/**",async route=>{
    const name=new URL(route.request().url()).pathname.split("/").pop();
    if(!/^[a-z-]+\.js$/.test(name))return route.abort();
    await route.fulfill({contentType:"application/javascript; charset=utf-8",body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto("http://127.0.0.1/automatic-test");
  await page.waitForFunction(()=>customElements.get("iqalarm-panel"));
  await page.locator("iqalarm-panel").evaluate(panel=>{
    panel.catalog={entities:[],areas:[]};panel._connected=true;panel.tab=3;panel.stage="sensor_stage";panel.profile="away";
    panel.data={config:{revision:1,secure_stage_id:"secure",stages:[
      {id:"off",name:"Aus",color:"#ffffff"},{id:"secure",name:"Sicher",color:"#00ff00"},{id:"outside",name:"Außen",color:"#0000ff"},
      {id:"sensor_stage",name:"Sensorauslösung",color:"#dddd00"},{id:"detected_stage",name:"Auslösung",color:"#ff0000"},{id:"alarm",name:"Alarm",color:"#ff00ff"},
    ],rooms:{kitchen:{id:"kitchen",name:"Küche"}},windows:{},floorplans:{},room_connections:[],robots:{},automatic_detection:null,
    sensors:{"binary_sensor.motion":{entity_id:"binary_sensor.motion",name:"Bewegung Küche",room_id:"kitchen",role:"interior_motion",enabled:true}},
    rules:{motion:{id:"motion",name:"Alter Bewegungsauslöser",stage_id:"detected_stage",conditions:[],enabled:true}},actions:{},
    profiles:{away:{name:"Abwesend",rule_ids:["motion"],automatic_detection:true,contacts_enabled:true,motion_mode:"always",reactions_enabled:true,simulation_enabled:false,exit_seconds:0,room_ids:null,sensor_ids:null}},
    settings:{debounce_by_role:{},simulation_lights:[],simulation_start:18,simulation_end:23,retention_days:7}},
    status:{active:false,rooms:{},raw:{},last_active:{},monitored_sensors:[],quarantine:{}},information:[]};
    panel._call=async(type,args)=>{
      if(type!=="config/save")throw Error(`Unexpected request ${type}`);
      panel.__savedConfig=structuredClone(args.config);
      return {...panel.data,config:{...args.config,revision:args.revision+1}};
    };
    panel._render();
  });
});

for(const width of [1440,390])test(`person report thresholds and decay save separately from outdoor motion at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  await page.locator('[data-stage="outside"]').first().click();
  const form=page.locator('#person-detection-form');
  for(const n of [1,2,3])await expect(form.locator(`[name="person_threshold_${n}"]`)).toHaveValue(String(n));
  await expect(form.locator('[name="person_quiet"]')).toHaveValue('60');
  await expect(form).toContainText('Ein Außenbewegungsmelder startet LVL 2 ohne Bestätigung.');
  await expect(form).toContainText('Bewegungs- und Kameraanteil werden zusammengezählt.');
  for(const n of [1,2,3])await form.locator(`[name="person_threshold_${n}"]`).fill(String(n*2));
  await form.locator('[name="person_quiet"]').fill('90');
  await form.getByRole('button',{name:'Personenerkennung speichern',exact:true}).click();
  const saved=await page.locator('iqalarm-panel').evaluate(panel=>panel.__savedConfig);
  expect(saved.person_detection).toEqual({stage_id:'outside',thresholds:[2,4,6],quiet_seconds:90});
  expect(saved.automatic_detection).toBeNull();
  expect(saved.profiles.away.rule_ids).toEqual(['motion']);
  expect(saved.actions).toEqual({});
  expect(await page.locator('iqalarm-panel').evaluate(panel=>panel.shadowRoot.querySelector('.shell').scrollWidth>panel.shadowRoot.querySelector('.shell').clientWidth)).toBe(false);
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.data.config.rules.perimeter={id:'perimeter',name:'Außenmeldung',stage_id:'outside',enabled:true,window_seconds:180,delay_seconds:0,entry_only:false,ordered:false,room_ids:null,paths:[],confirmation_target:null,prerequisite_rule_id:null,
      conditions:[{sensor_ids:[],roles:['perimeter_camera','perimeter_sensor'],event:'active',count:1,max_age_seconds:10}]};
    panel._render();
  });
  await page.getByRole('button',{name:'Außenmeldung bearbeiten',exact:true}).click();
  const editor=page.locator('#editor-form');
  await expect(editor.locator('[name="rule_window"]')).toHaveValue('90');
  await expect(editor.locator('[name="rule_window"]')).toHaveAttribute('readonly','');
  await expect(editor.locator('[name="age_0"]')).toHaveCount(0);
  await expect(editor.locator('[name="rule_grade_enabled"]')).toHaveCount(0);
  await expect(editor.locator('[name="count_0"]')).toHaveAttribute('readonly','');
  await editor.getByRole('button',{name:'Speichern',exact:true}).click();
  const coupled=await page.locator('iqalarm-panel').evaluate(panel=>panel.__savedConfig.rules.perimeter);
  expect(coupled.window_seconds).toBe(90);
  expect(coupled.conditions[0].max_age_seconds).toBeNull();
});

test('outdoor-indoor test ceiling preserves LVL 4 permission when automatic settings save',async({page})=>{
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.data.config.automatic_detection={stage_id:'sensor_stage',next_stage_id:'detected_stage',threshold:1,quiet_seconds:60,promote_seconds:60,test_mode:true,test_stage_id:'detected_stage'};
    panel._render();
  });
  const form=page.locator('#automatic-detection-form');
  await expect(form.locator('[data-test-mode]')).toHaveText('LVL 4 für den Außen-/Innen-Test freigegeben, LVL 5 bleibt gesperrt.');
  await form.getByRole('button',{name:'Automatik speichern',exact:true}).click();
  const saved=await page.locator('iqalarm-panel').evaluate(panel=>panel.__savedConfig.automatic_detection);
  expect(saved.test_mode).toBe(true);
  expect(saved.test_stage_id).toBe('detected_stage');
  await page.locator('[data-stage="detected_stage"]').first().click();
  await expect(page.locator('[data-stage-blocked]')).toHaveCount(0);
  await page.locator('[data-stage="alarm"]').first().click();
  await expect(page.locator('[data-stage-blocked]')).toHaveCount(0);
  await expect(page.locator('[data-stage="alarm"]').first()).toContainText('deaktiviert');
});

test('LVL 2 person reports charge the existing inner ring without a second bar',async({page})=>{
  for(const current of [0,1,2,3,2,1,0]){
    await page.locator('iqalarm-panel').evaluate((panel,current)=>{
      panel.tab=0;
      panel.data={...panel.data,status:{...panel.data.status,active:true,mode:'active',profile_id:'away',profile_name:'Abwesend',stage_id:'outside',level:2,stage_name:'Außen',rule_progress:current?[{rule_id:'person:kitchen',name:'Personenerkennung außen',stage_id:'outside',room_id:'kitchen',current,target:3,sources:[{entity_id:'binary_sensor.person',name:'Person Haustür'}]}]:[]}};
      panel._render();
    },current);
    const ring=page.locator('[data-confirmation-ring]');
    const offset=Number(await ring.getAttribute('stroke-dashoffset'));
    const circumference=Number(await ring.getAttribute('stroke-dasharray'));
    expect(offset).toBeCloseTo(circumference*(1-current/3),5);
    await expect(page.locator('progress')).toHaveCount(0);
    await expect(page.locator('[data-live-key="confirmation-grades"]')).toHaveCount(0);
  }
});

for(const width of [1440,390])test(`indoor full grade fills a red overlay in thirty seconds using the HA clock at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.tab=0;
    const now=Date.now()/1000+120;
    panel.data={...panel.data,config:{...panel.data.config,automatic_detection:{stage_id:'sensor_stage',next_stage_id:'detected_stage',threshold:1,quiet_seconds:60,promote_seconds:30,test_mode:true,test_stage_id:'detected_stage'}},
      status:{...panel.data.status,server_time:now,active:true,profile_id:'away',profile_name:'Abwesend',level:3,stage_id:'sensor_stage',stage_name:'Sensorauslösung',monitored_sensors:[],
      rule_progress:[{rule_id:'automatic_level3:kitchen',stage_id:'sensor_stage',room_id:'kitchen',current:3,target:3,next_level_at:now+30,sources:[]}]}};
    panel._render();
  });
  const overlay=page.locator('[data-promotion-ring]');
  const circumference=Number(await overlay.getAttribute('stroke-dasharray'));
  await expect(overlay).toHaveAttribute('r','61');
  expect(Number(await overlay.getAttribute('stroke-dashoffset'))/circumference).toBeCloseTo(1,2);
  await expect(page.locator('[data-confirmation-ring]')).toHaveAttribute('stroke-dashoffset','0');
  await page.clock.runFor(15000);
  expect(Number(await overlay.getAttribute('stroke-dashoffset'))/circumference).toBeCloseTo(.5,2);
  expect(await overlay.evaluate(e=>getComputedStyle(e).stroke)).toBe('rgb(211, 68, 84)');
  expect(await overlay.evaluate(e=>getComputedStyle(e).transitionTimingFunction)).toBe('linear');
  await page.clock.runFor(15000);
  expect(Number(await overlay.getAttribute('stroke-dashoffset'))).toBeCloseTo(0,2);
  await expect(page.locator('progress')).toHaveCount(0);
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.data.status={...panel.data.status,level:4,stage_id:'detected_stage',stage_name:'Auslösung'};
    panel._refreshRecognitionDisplay();
  });
  await expect(overlay).toHaveCount(0);
});

for(const width of [1440,390])test(`automatic LVL 3 settings save with stable stage IDs and separate mode scope at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  const errors=[];page.on("pageerror",error=>errors.push(error.message));
  const form=page.locator("#automatic-detection-form");
  await expect(form.getByRole("heading",{name:"Automatische Erkennung · Bestätigungsgrad"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Regel hinzufügen",exact:true})).toHaveCount(0);
  await form.getByLabel("Bestätigungsschwelle",{exact:true}).focus();
  await page.keyboard.press("ArrowRight");
  await expect(form.locator("[data-automatic-threshold-label]")).toContainText("1/3 ab 2 · 2/3 ab 3 · 3/3 ab 4");
  await form.getByLabel("Ohne neue Meldung einen Grad zurück nach (Sekunden)",{exact:true}).fill("90");
  await expect(form.locator("[data-test-mode]")).toContainText("LVL 4 und LVL 5 sind deaktiviert");
  await expect(form.locator('[name="automatic_promote"]')).toHaveCount(0);
  await form.getByRole("button",{name:"Automatik aktivieren",exact:true}).click();
  expect(await page.locator("iqalarm-panel").evaluate(panel=>panel.__savedConfig.automatic_detection)).toEqual({stage_id:"sensor_stage",next_stage_id:"detected_stage",threshold:2,quiet_seconds:90,promote_seconds:30,test_mode:true});
  await expect(form.getByRole("button",{name:"Automatik speichern",exact:true})).toBeVisible();
  await form.getByText("Sensoren und direkte Raumverbindungen ansehen",{exact:true}).click();
  await expect(form.getByText("binary_sensor.motion",{exact:true})).toBeVisible();
  await expect(form.locator("[data-automatic-required]")).toHaveText("4");
  await page.screenshot({path:`test-results/automatic-detection-${width}.png`,fullPage:true});

  for(const [id,rank] of [["detected_stage",4],["alarm",5]]){
    await page.locator(`[data-stage="${id}"]`).first().click();
    await expect(page.locator("[data-stage-blocked]")).toHaveCount(0);
    await expect(page.locator("#alarm-escalation-form")).toHaveCount(rank===4?1:0);
    await expect(page.getByRole("button",{name:"Regel hinzufügen",exact:true})).toHaveCount(0);
    await expect(page.locator(`[data-stage="${id}"]`).first()).toContainText(`LVL ${rank}`);
    await expect(page.locator(`[data-stage="${id}"]`).first()).toContainText("deaktiviert");
  }
  await page.getByRole("tab",{name:"Profile & System",exact:true}).click();
  await expect(page.locator("#profile-actions")).toHaveCount(0);
  const profile=page.locator("#profile-levels-form");
  await expect(profile.getByRole("heading",{name:"Sensorfreigaben für automatische Erkennung",exact:true})).toBeVisible();
  await expect(profile.locator('[name="use_rule_motion"]')).toHaveCount(0);
  await profile.getByLabel("Innenbewegung auswerten",{exact:true}).selectOption("ignore");
  await profile.getByRole("button",{name:"Profil speichern",exact:true}).click();
  const saved=await page.locator("iqalarm-panel").evaluate(panel=>panel.__savedConfig);
  expect(saved.profiles.away.motion_mode).toBe("ignore");
  expect(saved.profiles.away.automatic_detection).toBe(true);
  expect(saved.profiles.away.rule_ids).toEqual(["motion"]);
  expect(saved.actions).toEqual({});
  expect(await page.locator("iqalarm-panel").evaluate(panel=>panel.shadowRoot.querySelector(".shell").scrollWidth>panel.shadowRoot.querySelector(".shell").clientWidth)).toBe(false);
  expect(errors).toEqual([]);
});

for(const width of [1440,390])test(`confirmation uses the ring and compact source text inside the hero at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  await page.locator("iqalarm-panel").evaluate(panel=>{
    panel.tab=0;
    panel.data.status={...panel.data.status,active:true,profile_id:"away",profile_name:"Abwesend",level:3,stage_id:"sensor_stage",stage_name:"Sensorauslösung",
      raw:{"binary_sensor.motion":false},monitored_sensors:["binary_sensor.motion"],
      rooms:{kitchen:{level:3,confirmed:false,motion:[],open:[],persons:[],quarantined:[]}},
      rule_progress:[{rule_id:"automatic_level3:kitchen",room_id:"kitchen",name:"Automatische Erkennung · Küche",stage_id:"sensor_stage",current:1,target:3,
        sources:[{entity_id:"binary_sensor.motion",name:"Bewegung Küche"}]}]};
    panel._render();
  });
  const hero=page.locator(".hero"),context=hero.locator(".confirmation-context");
  await expect(hero.locator(".status-rings")).toHaveAttribute("aria-label","Alarmstufe 3, Bestätigungsgrad 1 von 3");
  await expect(context).toHaveText("Küche: Bewegung Küche");
  await expect(page.locator("progress")).toHaveCount(0);
  await expect(page.locator('[data-live-key="confirmation-grades"]')).toHaveCount(0);
  expect(await context.evaluate(element=>element.getBoundingClientRect().height)).toBeLessThan(40);
  expect(await page.locator("iqalarm-panel").evaluate(panel=>panel.shadowRoot.querySelector(".shell").scrollWidth>panel.shadowRoot.querySelector(".shell").clientWidth)).toBe(false);
});

for(const width of [1440,390])test(`LVL 4 saves escalation time and SMS user label; LVL 5 has no sensor rules at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:920});
  await page.locator('iqalarm-panel').evaluate(panel=>{
    panel.data.external_monitor={id:'a'.repeat(32),enabled:false,status:'disabled'};
    panel._render();
  });
  await page.locator('[data-stage="detected_stage"]').first().click();
  const form=page.locator('#alarm-escalation-form');
  await expect(form.locator('[name="escalation_minutes"]')).toHaveValue('5');
  await expect(form.locator('[name="external_monitoring"]')).not.toBeChecked();
  await expect(form.getByLabel('Benutzerbezeichnung',{exact:true})).toHaveValue('deinem Freund');
  await expect(form.getByText('Der Schutz greift erst, sobald der externe Dienst die Alarmmeldung empfangen und bestätigt hat.',{exact:true})).toBeVisible();
  await expect(form.locator('input[type="tel"]')).toHaveCount(3);
  for(const n of [1,2,3])await expect(form.getByLabel(`Telefonnummer ${n}`,{exact:true})).toHaveValue('');
  await expect(form.locator('[data-monitor-id]')).toHaveText('a'.repeat(32));
  await expect(page.getByRole('button',{name:'Regel hinzufügen',exact:true})).toHaveCount(0);
  await form.locator('[name="escalation_minutes"]').fill('7');
  await form.getByLabel('Benutzerbezeichnung',{exact:true}).fill('Nachbar <West & Süd>');
  const numbers=['+4915111111111','+4916111111111','+4917111111111'];
  for(const n of [1,2,3])await form.getByLabel(`Telefonnummer ${n}`,{exact:true}).fill(numbers[n-1]);
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.__savedConfig.alarm_escalation.delay_seconds)).toBe(420);
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.__savedConfig.external_monitoring.user_label)).toBe('Nachbar <West & Süd>');
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.__savedConfig.external_monitoring.phone_numbers)).toEqual(numbers);
  await expect(form.getByLabel('Benutzerbezeichnung',{exact:true})).toHaveValue('Nachbar <West & Süd>');
  await form.getByLabel('Benutzerbezeichnung',{exact:true}).fill('');
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.__savedConfig.external_monitoring.user_label)).toBe('deinem Freund');
  expect(await page.locator('iqalarm-panel').evaluate(p=>p.__savedConfig.external_monitoring.enabled)).toBe(false);
  await page.screenshot({path:`test-results/sms-user-label-${width}.png`,fullPage:true});
  await page.locator('[data-stage="alarm"]').first().click();
  await expect(page.getByRole('button',{name:'Regel hinzufügen',exact:true})).toHaveCount(0);
  await expect(page.locator('#alarm-escalation-form')).toHaveCount(0);
});
