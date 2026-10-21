import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test.beforeEach(async({page})=>{
  await page.clock.install({time:new Date('2026-10-21T12:00:00Z')});
  await page.route('http://127.0.0.1/card',r=>r.fulfill({contentType:'text/html',body:'<script type="module" src="/modules/iqalarm-card.js"></script><div id="container" style="width:320px"><iqalarm-card></iqalarm-card></div>'}));
  await page.route('http://127.0.0.1/modules/**',async r=>{
    const name=new URL(r.request().url()).pathname.split('/').pop();
    if(!/^[a-z-]+\.js$/.test(name))return r.abort();
    await r.fulfill({contentType:'application/javascript',body:await readFile(new URL(`../../custom_components/iqalarm/frontend/${name}`,import.meta.url))});
  });
  await page.goto('http://127.0.0.1/card');
  await page.waitForFunction(()=>customElements.get('iqalarm-card'));
  await page.locator('iqalarm-card').evaluate(card=>{
    const now=Date.now()/1000;
    window.data={config:{secure_stage_id:'1',settings:{startup_delay_seconds:60},robots:{},stages:['Deaktiviert','Sicher','Umfeld','Verdacht','Alarm','Alarmstufe 2'].map((name,i)=>({id:String(i),name,color:['#000000','#64bc29','#081dba','#cad345','#bc2929','#8000ff'][i]})),automatic_detection:{stage_id:'3',promote_seconds:30}},status:{server_time:now,active:true,mode:'active',profile_id:'away',profile_name:'Abwesend',level:2,stage_id:'2',stage_name:'Umfeld',rule_progress:[{stage_id:'2',current:2,target:3}],rooms:{}}};
    window.requests=[];window.unsubscribed=0;window.target=new EventTarget();
    window.connection={addEventListener:(...args)=>window.target.addEventListener(...args),removeEventListener:(...args)=>window.target.removeEventListener(...args),subscribeMessage:async(callback,msg)=>{window.requests.push(msg);window.receive=callback;callback(structuredClone(window.data));return ()=>{window.unsubscribed++;};}};
    card.setConfig({type:'custom:iqalarm-card'});
    card.hass={connection:window.connection,callWS:()=>{throw Error('Unexpected write/API request');},callService:()=>{throw Error('Unexpected service call');}};
  });
});

for(const width of [150,320])for(const dark of [false,true])test(`compact read-only card fits ${width}px in ${dark?'dark':'light'} theme`,async({page})=>{
  await page.evaluate(({width,dark})=>{
    document.getElementById('container').style.width=width+'px';
    document.body.style.background=dark?'#111':'#fff';
    document.body.style.setProperty('--primary-text-color',dark?'#eee':'#172a34');
    document.body.style.setProperty('--divider-color',dark?'#4a5055':'#d6dce0');
  },{width,dark});
  const card=page.locator('iqalarm-card');
  await expect(card.locator('svg')).toHaveAttribute('aria-label','Alarmstufe 2, Bestätigungsgrad 2 von 3');
  await expect(card).toContainText('Abwesend');
  await expect(card.locator('button,input,select,a')).toHaveCount(0);
  expect(await card.evaluate(c=>{const a=c.getBoundingClientRect(),b=c.shadowRoot.querySelector('svg').getBoundingClientRect();return b.left>=a.left&&b.right<=a.right;})).toBe(true);
  expect(await page.evaluate(()=>window.requests)).toEqual([{type:'iqalarm/subscribe'}]);
});
test('same ring nodes animate countdown using the server clock',async({page})=>{
  await page.evaluate(()=>{
    const d=structuredClone(window.data),now=d.status.server_time+3600;
    Object.assign(d.status,{server_time:now,level:1,stage_id:'1',stage_name:'Sicher',arming_started_at:now,arming_until:now+60});
    window.receive(d);window.svg=document.querySelector('iqalarm-card').shadowRoot.querySelector('svg');
  });
  const card=page.locator('iqalarm-card');
  await expect(card).toContainText('Start in 01:00');
  await page.clock.fastForward(30000);
  await expect(card).toContainText('Start in 00:30');
  expect(await card.locator('[data-promotion-ring]').getAttribute('stroke-dashoffset')).not.toBe('0');
  expect(await card.evaluate(c=>c.shadowRoot.querySelector('svg')===window.svg)).toBe(true);
});
test('LVL 4 countdown waits for confirmed LVL 5 from the backend',async({page})=>{
  await page.evaluate(()=>{
    const d=structuredClone(window.data),now=d.status.server_time;
    Object.assign(d.status,{level:4,stage_id:'4',stage_name:'Alarm',confirmed:true,alarm:{stage_id:'4',deadline:now+300,duration:300}});window.receive(d);
  });
  const card=page.locator('iqalarm-card');await expect(card).toContainText('LVL 5 in 05:00');
  await page.clock.fastForward(150000);await expect(card).toContainText('LVL 5 in 02:30');
  await page.clock.fastForward(151000);await expect(card.locator('svg text')).toHaveText('4');
  await page.evaluate(()=>{Object.assign(window.data.status,{level:5,stage_id:'5',stage_name:'Alarmstufe 2'});window.receive(window.data);});
  await expect(card.locator('svg text')).toHaveText('5');
});
test('disconnect clears stale status and ready resubscribes only once',async({page})=>{
  await page.evaluate(()=>window.target.dispatchEvent(new Event('disconnected')));
  const card=page.locator('iqalarm-card');await expect(card).toContainText('Verbindung unterbrochen');await expect(card.locator('svg')).toHaveCount(0);
  await page.evaluate(()=>window.target.dispatchEvent(new Event('ready')));
  await expect(card.locator('svg')).toHaveCount(1);
  await expect.poll(()=>page.evaluate(()=>window.unsubscribed)).toBe(1);
  expect(await page.evaluate(()=>window.requests.length)).toBe(2);
  await card.evaluate(c=>{for(let i=0;i<10;i++)c.hass={connection:window.connection};});
  expect(await page.evaluate(()=>window.requests.length)).toBe(2);
});
test('removal cleans timers/listeners and rejects late subscription callbacks',async({page})=>{
  await page.locator('iqalarm-card').evaluate(c=>{window.oldCard=c;c.remove();});
  await expect.poll(()=>page.evaluate(()=>window.unsubscribed)).toBe(1);
  await page.evaluate(()=>{window.receive(window.data);window.target.dispatchEvent(new Event('ready'));});
  await page.clock.fastForward(60000);
  expect(await page.evaluate(()=>window.requests.length)).toBe(1);
  expect(await page.evaluate(()=>window.oldCard.shadowRoot.querySelector('svg'))).toBe(null);
});
test('unavailable backend and denied access never show a fake secure level',async({page})=>{
  const card=page.locator('iqalarm-card');
  await page.evaluate(()=>window.receive({available:false}));
  await expect(card).toContainText('IQAlarm nicht verfügbar');await expect(card.locator('svg')).toHaveCount(0);
  await card.evaluate(c=>{c.hass={connection:{subscribeMessage:async()=>{throw {code:'unauthorized'};}}};});
  await expect(card).toContainText('Keine Berechtigung');await expect(card.locator('svg')).toHaveCount(0);
  await page.clock.fastForward(60000);await expect(card).toContainText('Keine Berechtigung');
});
test('HA state updates do not bypass retry backoff or repeat permission failures',async({page})=>{
  const card=page.locator('iqalarm-card');
  await card.evaluate(c=>{
    window.attempts=0;window.failing={subscribeMessage:async()=>{window.attempts++;throw {code:'unknown_command'};}};
    c.hass={connection:window.failing};
  });
  await expect.poll(()=>page.evaluate(()=>window.attempts)).toBe(1);
  await card.evaluate(c=>{for(let i=0;i<20;i++)c.hass={connection:window.failing};});
  expect(await page.evaluate(()=>window.attempts)).toBe(1);
  await page.clock.fastForward(1000);
  await expect.poll(()=>page.evaluate(()=>window.attempts)).toBe(2);
  await card.evaluate(c=>{
    window.denials=0;window.denied={subscribeMessage:async()=>{window.denials++;throw {code:'unauthorized'};}};
    c.hass={connection:window.denied};
  });
  await expect.poll(()=>page.evaluate(()=>window.denials)).toBe(1);
  await card.evaluate(c=>{for(let i=0;i<20;i++)c.hass={connection:window.denied};});
  await page.clock.fastForward(60000);
  expect(await page.evaluate(()=>window.denials)).toBe(1);
});
test('a removed card releases a subscription that finishes late',async({page})=>{
  await page.locator('iqalarm-card').evaluate(c=>{
    window.lateStops=0;
    c.hass={connection:{subscribeMessage:()=>new Promise(resolve=>{window.finishSubscribe=()=>resolve(()=>{window.lateStops++;});})}};
    c.remove();window.finishSubscribe();
  });
  await expect.poll(()=>page.evaluate(()=>window.lateStops)).toBe(1);
});
