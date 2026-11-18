import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test.beforeEach(async({page})=>{
  await page.clock.install({time:new Date('2026-10-21T12:00:00Z')});
  await page.route('http://127.0.0.1/floorplan-card',r=>r.fulfill({contentType:'text/html',body:'<script type="module" src="/modules/iqalarm-card.js"></script><div id="container" style="width:700px"><iqalarm-floorplan-card></iqalarm-floorplan-card></div>'}));
  await page.route('http://127.0.0.1/modules/**',async r=>{
    const name=new URL(r.request().url()).pathname.split('/').pop();
    if(!/^[a-z-]+\.js$/.test(name))return r.abort();
    await r.fulfill({contentType:'application/javascript',body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto('http://127.0.0.1/floorplan-card');
  await page.waitForFunction(()=>customElements.get('iqalarm-floorplan-card'));
  await page.locator('iqalarm-floorplan-card').evaluate(card=>{
    const now=Date.now()/1000;
    const sensor=(id,room,role,extra={})=>({entity_id:id,name:id,room_id:room,role,enabled:true,...extra});
    const sensors=[sensor('binary_sensor.motion','wc','interior_motion'),sensor('event.button','wc','interior_motion',{sensor_kind:'light_switch',activation_mode:'press'}),sensor('binary_sensor.window','bed','entry_contact',{name:'Fenster'})];
    window.data={config:{secure_stage_id:'1',stages:[{id:'0',name:'Aus'},{id:'1',name:'Sicher'},{id:'2',name:'Umfeld'},{id:'3',name:'Verdacht'},{id:'4',name:'Alarm'}],settings:{},profiles:{},windows:{},rooms:{wc:{id:'wc',name:'WC'},bed:{id:'bed',name:'Schlafzimmer'}},
      sensors:Object.fromEntries(sensors.map(s=>[s.entity_id,s])),floorplans:{eg:{id:'eg',name:'Erdgeschoss',width:1000,height:600,image:'eg.png',image_opacity:.25,zones:{wc:[[.1,.1],[.8,.1],[.8,.9],[.1,.9]]}},og:{id:'og',name:'Obergeschoss',width:1000,height:600,image:null,zones:{bed:[[.2,.2],[.8,.2],[.8,.8],[.2,.8]]}}}},
      information:[],windows:{},window_details:{},status:{server_time:now,active:false,level:0,stage_id:'0',profile_id:null,raw:Object.fromEntries(sensors.map(s=>[s.entity_id,true])),last_active:{'binary_sensor.motion':now},quarantine:{},
        rooms:{wc:{motion:['binary_sensor.motion','event.button'],open:[],persons:[],quarantined:[]},bed:{motion:[],open:['binary_sensor.window'],persons:[],quarantined:[]}}}};
    window.requests=[];window.imageRequests=[];window.unsubscribed=0;window.target=new EventTarget();
    window.connection={addEventListener:(...a)=>window.target.addEventListener(...a),removeEventListener:(...a)=>window.target.removeEventListener(...a),subscribeMessage:async(callback,msg)=>{window.requests.push(msg);window.receive=callback;callback(structuredClone(window.data));return ()=>{window.unsubscribed++;};}};
    window.revoked=[];const revoke=URL.revokeObjectURL;URL.revokeObjectURL=url=>{window.revoked.push(url);revoke(url);};
    card.setConfig({type:'custom:iqalarm-floorplan-card'});
    card.hass={connection:window.connection,fetchWithAuth:async(url,options)=>{window.imageRequests.push(url);return new Response(new Blob(['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600"><rect width="1000" height="600" fill="gray"/></svg>'],{type:'image/svg+xml'}));},callService:()=>{throw Error('Unexpected write');},callWS:()=>{throw Error('Unexpected API call');}};
  });
  await expect(page.locator('iqalarm-floorplan-card').locator('.floorplan')).toHaveCount(2);
});

for(const width of [320,1000])for(const dark of [false,true])test(`live floorplan is read-only and fits ${width}px in ${dark?'dark':'light'} theme`,async({page})=>{
  await page.evaluate(({width,dark})=>{
    document.getElementById('container').style.width=width+'px';
    document.body.style.background=dark?'#111':'#fff';
    document.body.style.setProperty('--primary-text-color',dark?'#eee':'#172a34');
  },{width,dark});
  const card=page.locator('iqalarm-floorplan-card');
  await expect(card.locator('h3')).toHaveText(['Erdgeschoss','Obergeschoss']);
  await expect(card.locator('[data-label-room="wc"] tspan')).toHaveText(['Bewegung','Interaktion']);
  await expect(card.locator('[data-label-room="bed"]')).toContainText('Fenster offen');
  await expect(card.locator('button,input,select,[role="button"],[tabindex]')).toHaveCount(0);
  await expect(card.locator('image')).toHaveAttribute('href',/^blob:/);
  expect(await card.evaluate(c=>c.scrollWidth<=c.getBoundingClientRect().width+1)).toBe(true);
  expect(await page.evaluate(()=>window.requests)).toEqual([{type:'iqalarm/subscribe'}]);
  expect(await page.evaluate(()=>window.imageRequests)).toEqual(['/api/iqalarm/floorplans/eg/image']);
  if(width===320&&dark)await card.screenshot({path:'.ha-test/iqalarm-floorplan-card-mobile.png'});
});

test('a floor can be selected by name or ID and missing floors never silently show another',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await card.evaluate(c=>c.setConfig({type:'custom:iqalarm-floorplan-card',floorplan:'Obergeschoss'}));
  await expect(card.locator('h3')).toHaveText('Obergeschoss');await expect(card.locator('[data-label-room="wc"]')).toHaveCount(0);
  await card.evaluate(c=>c.setConfig({type:'custom:iqalarm-floorplan-card',floorplan:'eg'}));
  await expect(card.locator('h3')).toHaveText('Erdgeschoss');
  await card.evaluate(c=>c.setConfig({type:'custom:iqalarm-floorplan-card',floorplan:'missing'}));
  await expect(card).toContainText('Etage wurde nicht gefunden');await expect(card.locator('svg')).toHaveCount(0);
  expect(await page.evaluate(()=>window.requests.length)).toBe(1);
});

test('visual editor selects one floor independently per card and preserves other settings',async({page})=>{
  await page.evaluate(()=>{
    const Card=customElements.get('iqalarm-floorplan-card');
    window.changes=[];
    for(const [index,floorplan] of ['Obergeschoss','eg'].entries()){
      const editor=Card.getConfigElement();editor.id=`editor${index}`;
      editor.setConfig({type:'custom:iqalarm-floorplan-card',floorplan,grid_options:{columns:6}});
      editor.addEventListener('config-changed',event=>window.changes.push({index,config:event.detail.config}));
      editor.hass={connection:window.target,callWS:async()=>structuredClone(window.data)};
      document.body.append(editor);
    }
  });
  const first=page.locator('#editor0').getByLabel('Grundriss'),second=page.locator('#editor1').getByLabel('Grundriss');
  await expect(first.locator('option')).toHaveText(['Alle Grundrisse','Erdgeschoss','Obergeschoss']);
  await expect(first).toHaveValue('og');await expect(second).toHaveValue('eg');
  expect(await page.evaluate(()=>window.changes)).toEqual([]);
  await first.selectOption('eg');await expect(second).toHaveValue('eg');
  expect((await page.evaluate(()=>window.changes))[0]).toEqual({index:0,config:{type:'custom:iqalarm-floorplan-card',floorplan:'eg',grid_options:{columns:6}}});
  await second.selectOption('all');
  expect((await page.evaluate(()=>window.changes))[1].config).toEqual({type:'custom:iqalarm-floorplan-card',grid_options:{columns:6}});
  await first.selectOption('og');await expect(second).toHaveValue('all');
});

test('server-clock activity expires in place without any backend update',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await page.evaluate(()=>{
    window.oldSvg=document.querySelector('iqalarm-floorplan-card').shadowRoot.querySelector('svg');
    window.oldLabel=document.querySelector('iqalarm-floorplan-card').shadowRoot.querySelector('[data-label-room="wc"]');
    const d=structuredClone(window.data);d.status.server_time+=3600;d.status.last_active['binary_sensor.motion']=d.status.server_time;
    d.status.raw['binary_sensor.motion']=false;d.status.raw['event.button']=false;d.status.rooms.wc.motion=[];window.receive(d);
  });
  await expect(card.locator('[data-label-room="wc"]')).toContainText('Bewegung');
  await expect(card.locator('[data-label-room="wc"]')).not.toContainText('Interaktion');
  await page.clock.fastForward(16000);
  await expect(card.locator('[data-label-room="wc"] tspan')).toHaveCount(0);
  await expect(card.locator('[data-label-room="wc"] rect')).toHaveAttribute('stroke','#14b8a6');
  expect(await card.evaluate(c=>c.shadowRoot.querySelector('svg')===window.oldSvg&&c.shadowRoot.querySelector('[data-label-room="wc"]')===window.oldLabel)).toBe(true);
});

test('armed recognition uses the same source labels, expiry and alarm persistence',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await page.evaluate(()=>{
    const d=structuredClone(window.data),now=d.status.server_time;
    Object.assign(d.status,{active:true,profile_id:'away',level:3,stage_id:'3'});
    d.status.rooms.wc.recognitions=[{level:3,stage_id:'3',expires_at:now+10,confirmed:false,event:'active',sources:[{entity_id:'event.button',role:'interior_motion'}]}];
    window.receive(d);
  });
  await expect(card.locator('[data-label-room="wc"] tspan')).toHaveText('Interaktion');
  await page.clock.fastForward(11000);await expect(card.locator('[data-label-room="wc"] tspan')).toHaveCount(0);
  await page.evaluate(()=>{const d=structuredClone(window.data);Object.assign(d.status,{active:true,profile_id:'away'});d.status.rooms.wc.confirmed=true;window.receive(d);});
  await expect(card.locator('[data-label-room="wc"]')).toContainText('Bestätigter Alarm');
});

test('disconnect hides stale rooms, ready resubscribes and removal releases images and timers',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await expect(card.locator('image')).toHaveAttribute('href',/^blob:/);
  await page.evaluate(()=>window.target.dispatchEvent(new Event('disconnected')));
  await expect(card).toContainText('Verbindung unterbrochen');await expect(card.locator('svg')).toHaveCount(0);
  await page.evaluate(()=>window.target.dispatchEvent(new Event('ready')));
  await expect(card.locator('svg')).toHaveCount(2);
  expect(await page.evaluate(()=>window.requests.length)).toBe(2);
  await card.evaluate(c=>{window.oldCard=c;c.remove();});
  await expect.poll(()=>page.evaluate(()=>window.unsubscribed)).toBe(2);
  expect(await page.evaluate(()=>window.revoked.length)).toBeGreaterThan(0);
  await page.evaluate(()=>window.receive(window.data));await page.clock.fastForward(60000);
  expect(await page.evaluate(()=>window.oldCard.shadowRoot.querySelector('svg'))).toBe(null);
});

test('an empty or unavailable configuration never fabricates a secure floorplan',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await page.evaluate(()=>{const d=structuredClone(window.data);d.config.floorplans={};d.config.rooms={};window.receive(d);});
  await expect(card).toContainText('Kein Grundriss eingerichtet');await expect(card.locator('svg')).toHaveCount(0);
  await page.evaluate(()=>window.receive({available:false}));await expect(card).toContainText('IQAlarm nicht verfügbar');
  await card.evaluate(c=>{c.hass={connection:{subscribeMessage:async()=>{throw {code:'unauthorized'};}}};});
  await expect(card).toContainText('Keine Berechtigung');await expect(card.locator('svg')).toHaveCount(0);
});

test('removal aborts a pending image and ignores its late response without leaking a blob',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await expect(card.locator('image')).toHaveAttribute('href',/^blob:/);
  await card.evaluate(c=>{
    window.created=0;const create=URL.createObjectURL;URL.createObjectURL=blob=>{window.created++;return create(blob);};
    c.hass={...c.hass,fetchWithAuth:async(url,options)=>{window.imageSignal=options.signal;return new Promise(resolve=>{window.finishImage=()=>resolve(new Response(new Blob(['image'])));});}};
    const d=structuredClone(window.data);d.config.floorplans.eg.image='later.png';window.receive(d);
  });
  await expect.poll(()=>page.evaluate(()=>Boolean(window.finishImage))).toBe(true);
  await card.evaluate(c=>c.remove());
  expect(await page.evaluate(()=>window.imageSignal.aborted)).toBe(true);
  await page.evaluate(()=>window.finishImage());await page.clock.fastForward(1000);
  expect(await page.evaluate(()=>window.created)).toBe(0);
});

test('failed background images do not create a retry storm or hide the room geometry',async({page})=>{
  const card=page.locator('iqalarm-floorplan-card');
  await card.evaluate(c=>{
    window.failures=0;c.hass={...c.hass,fetchWithAuth:async()=>{window.failures++;return new Response('',{status:404});}};
    const d=structuredClone(window.data);d.config.floorplans.eg.image='missing.png';window.receive(d);
  });
  await expect.poll(()=>page.evaluate(()=>window.failures)).toBe(1);
  await page.clock.fastForward(60000);
  expect(await page.evaluate(()=>window.failures)).toBe(1);
  await expect(card.locator('[data-label-room="wc"]')).toContainText('Interaktion');
});
