import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test.beforeEach(async({page})=>{
  await page.clock.install({time:new Date('2026-10-21T12:00:00Z')});
  await page.route('http://127.0.0.1/cleanup',route=>route.fulfill({contentType:'text/html',body:'<script type="module" src="/modules/iqalarm-panel.js"></script><iqalarm-panel></iqalarm-panel>'}));
  await page.route('http://127.0.0.1/modules/**',async route=>{
    const name=new URL(route.request().url()).pathname.split('/').pop();
    if(!/^[a-z-]+\.js$/.test(name))return route.abort();
    return route.fulfill({contentType:'application/javascript',body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto('http://127.0.0.1/cleanup');
  await page.waitForFunction(()=>customElements.get('iqalarm-panel'));
  await page.locator('iqalarm-panel').evaluate(panel=>{
    const sensor=(entity_id,role,extra={})=>({entity_id,role,room_id:'r',name:entity_id,enabled:true,front_of:[],active_states:['on'],flap_enabled:true,flap_threshold:3,flap_window:15,debounce_ms:0,sensor_kind:'generic',activation_mode:'state',...extra});
    panel.catalog={entities:[],areas:[],notify_services:['notify.phone']};panel._connected=true;
    panel.profile='away';panel.stage='1';panel.tab=0;
    panel.data={config:{revision:1,secure_stage_id:'1',stages:['Deaktiviert','Sicher','Umfeld','Verdacht','Alarm','Alarmstufe 2'].map((name,i)=>({id:String(i),name,color:['#000000','#64bc29','#0000ff','#cad345','#bc2929','#8000ff'][i],allow_loud:i===5})),
      settings:{startup_delay_seconds:60,recent_seconds:30,debounce_by_role:{},retention_days:7,simulation_start:18,simulation_end:23,simulation_lights:[],observation_profile_id:'live',floorplan_disarmed_motion:true,floorplan_disarmed_contacts:true,floorplan_disarmed_cameras:true,floorplan_disarmed_animation:false,floorplan_armed_animation:true},
      rooms:{r:{id:'r',name:'Flur',adjacent:[]}},floorplans:{eg:{id:'eg',name:'Erdgeschoss',width:1000,height:600,image:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png',zones:{r:[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]},labels:{}}},
      profiles:{away:{name:'Abwesend',icon:'mdi:home-export-outline',rule_ids:['motion'],automatic_detection:true,contacts_enabled:true,motion_mode:'always',reactions_enabled:true,simulation_enabled:false,room_ids:null,sensor_ids:null,exit_seconds:0}},
      sensors:{'binary_sensor.camera':sensor('binary_sensor.camera','perimeter_camera'),'binary_sensor.outside':sensor('binary_sensor.outside','perimeter_sensor'),'binary_sensor.inside':sensor('binary_sensor.inside','interior_motion'),'binary_sensor.contact':sensor('binary_sensor.contact','entry_contact'),'binary_sensor.flur_input':sensor('binary_sensor.flur_input','interior_motion',{sensor_kind:'light_switch',activation_mode:'change'})},
      windows:{},robots:{},room_connections:[],outside_inside_links:[],automatic_detection:{stage_id:'3',next_stage_id:'4',threshold:1,quiet_seconds:60,promote_seconds:30,test_mode:false},alarm_escalation:{stage_id:'4',next_stage_id:'5',delay_seconds:300},
      rules:{motion:{id:'motion',name:'Bewegung',stage_id:'3',conditions:[{roles:['interior_motion'],sensor_ids:[],count:1,event:'active'}],enabled:true,window_seconds:60}},actions:{}},
      status:{active:true,profile_id:'away',evaluation_profile_id:'away',profile_name:'Abwesend',mode:'active',level:1,stage_id:'1',stage_name:'Sicher',raw:{},last_active:{},quarantine:{},monitored_sensors:[],rooms:{r:{level:1,recognitions:[],open:[],motion:[],persons:[]}},events:[],rule_progress:[],ignored_windows:[],coverage:{current:0,target:3,robots:[]}},
      information:[{name:'Fenstergriff Flur'}]};
    panel.imageURLs.set("eg",{image:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",url:"data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27/%3E"});
    panel._call=async(type,args)=>{
      if(type!=='config/save')throw Error(`Unexpected request ${type}`);
      panel.__savedConfig=structuredClone(args.config);
      return {...panel.data,config:{...args.config,revision:args.revision+1}};
    };
    panel._render();
  });
});

const mqttDevice='bd3c8cf65bec9038a01fe8a92b811feb';
const mqttSource=`event.iqalarm_button_${createHash('sha256').update(`${mqttDevice}:single_left`).digest('hex').slice(0,24)}`;
for(const width of [1440,390])test(`HA custom profile can be selected, saved and cleared at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const panel=page.locator('iqalarm-panel');
  await panel.evaluate(p=>{
    p.data.status.active=false;p.data.status.mode='inactive';p.data.status.profile_id=null;p.tab=4;
    p.data.config.profiles.guests={...structuredClone(p.data.config.profiles.away),name:'Besuch'};
    p.data.config.profiles.extra1={...structuredClone(p.data.config.profiles.away),name:'Werkstatt'};
    p.data.config.profiles.extra2={...structuredClone(p.data.config.profiles.away),name:'Garage'};
    p.data.config.ha_profile_ids={armed_home:'guests',armed_away:'away'};
    p._render();
  });
  const form=page.locator('#ha-profile-form'),select=form.locator('select');
  expect(await select.locator('option').evaluateAll(nodes=>nodes.map(n=>n.value))).toEqual(['','extra1','extra2']);
  await expect(select).toHaveValue('');
  await select.selectOption('extra2');
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await panel.evaluate(p=>p.__savedConfig.ha_profile_ids)).toEqual({armed_home:'guests',armed_away:'away',armed_custom_bypass:'extra2'});
  await expect(select).toHaveValue('extra2');
  await select.selectOption('');
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await panel.evaluate(p=>p.__savedConfig.ha_profile_ids)).toEqual({armed_home:'guests',armed_away:'away'});
  await expect(select).toHaveValue('');
});
for(const width of [1440,390])test(`LVL 0 offers a green light action on deactivation at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const panel=page.locator('iqalarm-panel');
  await panel.evaluate(p=>{
    p.data.status.active=false;p.data.status.mode='inactive';p.data.status.profile_id=null;p.stage='0';p.tab=3;
    p.catalog.entities=[{entity_id:'light.indicator',name:'Statuslicht'}];p._render();
  });
  const card=page.locator('[data-level-actions="0"]');
  await card.getByRole('button',{name:'Aktion hinzufügen',exact:true}).click();
  const form=page.locator('#editor-form');
  await expect(form.locator('[name="action_trigger"]')).toHaveText('Beim Deaktivieren');
  await form.locator('[name="kind"]').selectOption('light');
  await form.locator('[name="target"]').fill('light.indicator');
  await form.locator('[name="color"]').fill('#00ff00');
  await form.locator('[name="use_color"]').check();
  await form.locator('[name="duration"]').fill('10');
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  const saved=await panel.evaluate(p=>Object.values(p.__savedConfig.actions)[0]);
  expect(saved).toMatchObject({level:'0',kind:'light',target:'light.indicator',color:[0,255,0],duration:10,trigger:'level_entered',profile_ids:['away']});
  await expect(card).toContainText('Beim Deaktivieren');
  await expect(card).not.toContainText('werden keine Aktionen ausgeführt');
});
for(const width of [1440,390])test(`simple sensor creation preserves automatic signal settings for every category at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const panel=page.locator('iqalarm-panel');
  const cases=[
    {group:'camera',type:'perimeter_camera',id:'binary_sensor.new_person',name:'Person Garten',states:['on'],role:'perimeter_camera',mode:'state'},
    {group:'outside',type:'perimeter_sensor',id:'binary_sensor.new_outside',name:'Bewegung Garten',states:['on'],role:'perimeter_sensor',mode:'state'},
    {group:'inside',type:'interior_motion',id:'binary_sensor.new_inside',name:'Bewegung Flur',states:['on'],role:'interior_motion',mode:'state'},
    {group:'contact',type:'lock_contact',id:'lock.new_lock',name:'MACO Haustür',states:['unlocked','open'],role:'lock_contact',mode:'state'},
    {group:'trigger',type:'motion_change',id:'binary_sensor.new_trigger',name:'Innentür',states:['on'],role:'interior_motion',mode:'change'},
  ];
  await panel.evaluate((p,cases)=>{
    p.data.status.active=false;p.data.status.mode='inactive';p.data.status.profile_id=null;p.tab=2;
    p.data.config.rooms.r.area_id='flur';
    p.catalog.entities=cases.map(c=>({entity_id:c.id,name:c.name,role:c.role,active_states:c.states,source_id:`device:${c.group}`,area_id:'flur',attribute:null,active_above:null}));
    p.catalog.entities.push({entity_id:'camera.linked',name:'Kamera',source_id:'device:camera',setup_required:true});
    p._call=async(type,args)=>{
      if(type!=='crud')throw Error(`Unexpected ${type}`);
      p.__savedInput=structuredClone(args.item);p.data.config.sensors[args.item.entity_id]=args.item;return p.data;
    };p._render();
  },cases);
  for(const c of cases){
    await page.locator(`[data-add-sensor-group="${c.group}"]`).click();
    const form=page.locator('#editor-form');
    expect(await form.locator('input,select').evaluateAll(nodes=>nodes.map(n=>n.name))).toEqual(['entity_id','name','sensor_type','room_id']);
    await form.locator('[name="entity_id"]').fill(c.id);
    await expect(form.locator('[name="name"]')).toHaveValue(c.name);
    await expect(form.locator('[name="sensor_type"]')).toHaveValue(c.type);
    await expect(form.locator('[name="room_id"]')).toHaveValue('r');
    await form.locator('[name="name"]').fill(`IQ ${c.name}`);
    await form.getByRole('button',{name:'Speichern',exact:true}).click();
    const saved=await panel.evaluate(p=>p.__savedInput);
    expect(saved).toMatchObject({entity_id:c.id,name:`IQ ${c.name}`,role:c.role,room_id:'r',source_id:`device:${c.group}`,activation_mode:c.mode,active_states:c.states,enabled:true,flap_enabled:true,flap_threshold:3,flap_window:15,debounce_ms:0,entry_delay:false,immediate:false});
    expect(saved.camera_entity_id).toBe(c.group==='camera'?'camera.linked':null);
    await expect(page.locator(`[data-sensor-group="${c.group}"]`).getByText(`IQ ${c.name}`,{exact:true})).toHaveCount(1);
  }
});
for(const role of ['interior_mmwave','vibration_glass','panic','smoke'])for(const operation of ['save','move','sort','editor'])test(`legacy ${role}: ${operation} preserves sensor settings`,async({page})=>{
  const panel=page.locator('iqalarm-panel');
  const before=await panel.evaluate((p,{role,operation})=>{
    p.data.status.active=false;p.data.status.mode='inactive';p.data.status.profile_id=null;
    p.data.config.rooms.target={id:'target',name:'Büro',adjacent:[]};
    const sensor={...structuredClone(p.data.config.sensors['binary_sensor.inside']),entity_id:'binary_sensor.legacy',name:'Bestandssensor',role,icon:'mdi:account-eye-outline',source_id:'device:existing',debounce_ms:1234,flap_enabled:false,flap_threshold:7,flap_window:22,entry_delay:true,immediate:false,active_states:['occupied','present'],attribute:'presence',active_above:2,camera_entity_id:'camera.linked',device_trigger:null};
    p.data.config.sensors[sensor.entity_id]=sensor;
    p.catalog.entities=[{entity_id:'camera.linked',name:'Kamera'}];
    p.tab=2;p._render();
    if(operation==='editor')p._sensorDialog(sensor.entity_id);else p._sensorMoveDialog(sensor.entity_id,'r');
    return structuredClone(sensor);
  },{role,operation});
  const form=page.locator('#editor-form');
  await expect(form.locator(`[name="${operation==='editor'?'role':'sensor_type'}"]`)).toHaveValue(role);
  if(operation==='move')await form.locator('[data-command="move-sensor-target"][data-target-room="target"]').click();
  else if(operation==='sort')await form.locator('[data-command="sensor-order"][data-dir="-1"]').click();
  else {
    if(operation==='editor'){
      await form.locator('[name="room_id"]').selectOption('target');
      await panel.evaluate(p=>{p._call=async(type,args)=>{
        if(type!=='crud')throw Error(`Unexpected ${type}`);
        p.__savedInput=structuredClone(args.item);return p.data;
      };});
    }
    await form.getByRole('button',{name:'Speichern',exact:true}).click();
  }
  const saved=await panel.evaluate((p,operation)=>operation==='editor'?p.__savedInput:p.__savedConfig?.sensors['binary_sensor.legacy'],operation);
  expect(saved).toEqual({...before,room_id:['move','editor'].includes(operation)?'target':'r'});
});
for(const source of [
  {entity_id:'event.hue_wall_switch_module_14_button_1',name:'HWR Taste 1',activation_mode:'press',active_states:['initial_press'],options:['initial_press'],source_id:'device:hue'},
  {entity_id:'binary_sensor.licht_flur_og_input_0_input',name:'Licht Flur OG Input 0 input',activation_mode:'change',active_states:['on'],source_id:'device:shelly'},
  {entity_id:mqttSource,name:'Taster · single_left',activation_mode:'press',active_states:['single_left'],options:['single_left'],source_id:`device:${mqttDevice}`,device_trigger:{platform:'device',domain:'mqtt',device_id:mqttDevice,type:'action',subtype:'single_left'}},
])test(`physical button assignment: ${source.entity_id}`,async({page})=>{
  const panel=page.locator('iqalarm-panel');
  await panel.evaluate((p,source)=>{
    p.data.status.active=false;p.data.status.mode='inactive';p.data.status.profile_id=null;
    p.catalog.entities=[{...source,sensor_kind:'light_switch',setup_required:false},{entity_id:'light.flur',name:'Flur Lampe'},{entity_id:'switch.flur',name:'Flur Relais'}];
    p._call=async(type,args)=>{
      if(type!=='crud')throw Error(`Unexpected request ${type}`);
      p.__savedInput=structuredClone(args.item);
      p.data.config.sensors[args.item.entity_id]=args.item;
      return p.data;
    };
    p._render();p._sensorDialog();
  },source);
  const form=page.locator('#editor-form');
  expect(await form.locator('#ha-entity-catalog option').evaluateAll(nodes=>nodes.map(n=>n.value))).toEqual([source.entity_id]);
  await form.locator('[name="entity_id"]').fill(source.entity_id);
  await expect(form.locator('[name="sensor_type"]')).toHaveValue('light_switch');
  expect(await form.locator('input,select').evaluateAll(nodes=>nodes.map(n=>n.name))).toEqual(['entity_id','name','sensor_type','room_id']);
  await form.locator('[name="room_id"]').selectOption('r');
  await form.getByRole('button',{name:'Speichern',exact:true}).click();
  const saved=await panel.evaluate(p=>p.__savedInput);
  expect(saved).toMatchObject({entity_id:source.entity_id,role:'interior_motion',sensor_kind:'light_switch',activation_mode:source.activation_mode,source_id:source.source_id,active_states:source.active_states,room_id:'r'});
  expect(saved.device_trigger).toEqual(source.device_trigger||null);
});

for(const width of [1440,390])test(`cleanup layout and settings at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const panel=page.locator('iqalarm-panel');
  const order=await panel.evaluate(p=>{
    const root=p.shadowRoot,plan=root.querySelector('[data-live-key="live-floorplans"]');
    return {footer:!!(plan.querySelector('svg').compareDocumentPosition(plan.querySelector('.live-floorplan-header'))&Node.DOCUMENT_POSITION_FOLLOWING),info:!!(plan.compareDocumentPosition(root.querySelector('.information'))&Node.DOCUMENT_POSITION_FOLLOWING),statsLast:root.querySelector('.shell').textContent.lastIndexOf('Störungen / isoliert')>root.querySelector('.shell').textContent.lastIndexOf('Räume & Sicherheitsstatus')};
  });
  expect(order).toEqual({footer:true,info:true,statsLast:true});
  await page.screenshot({path:`test-results/cleanup-dashboard-${width}.png`,fullPage:true});
  await panel.evaluate(p=>{p.data.status.active=false;p.data.status.mode="inactive";p.data.status.profile_id=null;p._render();});
  await page.getByRole('tab',{name:'Räume & Grundriss',exact:true}).click();
  await expect(page.locator('.topology')).toHaveCount(0);
  for(const command of ['floorplan-orthogonalize','toggle-graphic-preview','zone-deselect','label-position-mode']){
    await expect(page.locator(`[data-command="${command}"]`)).toHaveCount(command==='label-position-mode'?0:1);
  }
  await expect(page.locator('[name="floorplan_disarmed_animation"]')).toHaveCount(0);
  await expect(page.locator('[name="recent_seconds"]')).toHaveCount(0);
  await page.screenshot({path:`test-results/cleanup-floorplan-${width}.png`,fullPage:true});
  await page.getByRole('tab',{name:'Kameras & Sensoren',exact:true}).click();
  expect(await page.locator('[data-sensor-group]').evaluateAll(nodes=>nodes.map(n=>n.dataset.sensorGroup))).toEqual(['camera','outside','inside','contact','trigger']);
  await expect(page.locator('[data-sensor-group="trigger"]')).toContainText('binary_sensor.flur_input');
  await page.locator('[data-sensor-group="trigger"] [data-command="sensor-edit"]').click();
  await expect(page.locator('#editor-form [name="sensor_kind"]')).toHaveValue('light_switch');
  expect(await page.locator('#editor-form [name="role"] option').evaluateAll(nodes=>nodes.map(n=>n.value))).toEqual(['perimeter_camera','perimeter_sensor','entry_contact','lock_contact','interior_motion']);
  await page.locator('#editor-form').getByRole('button',{name:'Abbrechen',exact:true}).click();
  await page.locator('[name="recent_seconds"]').fill('45');
  await page.locator('#sensor-display-form').getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await panel.evaluate(p=>p.__savedConfig.settings.recent_seconds)).toBe(45);
  await page.getByRole('tab',{name:'Level-Konfiguration',exact:true}).click();
  await page.locator('[data-stage="1"]').first().click();
  await page.locator('[name="startup_delay_seconds"]').fill('75');
  await page.locator('#startup-delay-form').getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await panel.evaluate(p=>p.__savedConfig.settings.startup_delay_seconds)).toBe(75);
  await page.locator('[data-stage="3"]').first().click();
  await page.locator('[data-level-actions="3"]').getByRole('button',{name:'Aktion hinzufügen',exact:true}).click();
  await page.getByLabel('Ausführen bei',{exact:true}).selectOption('grade_2');
  await page.locator('#editor-form [name="target"]').fill('notify.phone');
  await page.locator('#editor-form').getByRole('button',{name:'Speichern',exact:true}).click();
  const action=await panel.evaluate(p=>Object.values(p.__savedConfig.actions)[0]);
  expect(action.trigger).toBe('grade_2');expect(action.profile_ids).toEqual(['away']);
  await page.screenshot({path:`test-results/cleanup-level-${width}.png`,fullPage:true});
  await page.getByRole('tab',{name:'Profile & System',exact:true}).click();
  await expect(page.locator('#profile-actions')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Aktion hinzufügen',exact:true})).toHaveCount(0);
  expect(await panel.evaluate(p=>p.shadowRoot.querySelector('.shell').scrollWidth>p.shadowRoot.querySelector('.shell').clientWidth)).toBe(false);
  expect(errors).toEqual([]);
});

for(const width of [1440,390])test(`startup clock animates the existing red ring at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.locator('iqalarm-panel').evaluate(p=>{
    const now=Date.now()/1000;p.data.status.arming_started_at=now-30;p.data.status.arming_until=now+30;p._render();
  });
  await expect(page.locator('.grade-caption')).toHaveText('Start in 00:30');
  const circle=page.locator('[data-promotion-ring]');
  expect(Number(await circle.getAttribute('stroke-dashoffset'))/(2*Math.PI*61)).toBeCloseTo(.5,3);
  await page.clock.runFor(10000);
  await expect(page.locator('.grade-caption')).toHaveText('Start in 00:20');
  const remainingFraction=Number(await circle.getAttribute('stroke-dashoffset'))/(2*Math.PI*61);
  // The text uses ceil(seconds); the continuous ring must lie in that same second.
  expect(remainingFraction).toBeGreaterThanOrEqual(19/60);
  expect(remainingFraction).toBeLessThanOrEqual(20/60);
  await expect(page.locator('.hero progress')).toHaveCount(0);
});
