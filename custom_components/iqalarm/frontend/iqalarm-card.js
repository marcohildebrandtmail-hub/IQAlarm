/* Read-only Lovelace card. Rendering and timer projection are shared with IQAlarm. */
import {LIVE_VIEW_CSS,patchHTML,recognitionDisplayData,statusRings} from "./live-view.js?v=2.15.2";

const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const css=`
:host{display:block;--iq-border:var(--divider-color,#d6dce0);--iq-muted:var(--secondary-text-color,#667580);--iq-accent:var(--primary-color,#5a9ac6);--iq-amber:#b78412;--iq-red:#d32f2f;color:var(--primary-text-color,#172a34)}
ha-card{height:100%;box-sizing:border-box;overflow:hidden}
.content{display:flex;flex-direction:column;align-items:center;justify-content:center;box-sizing:border-box;min-height:220px;padding:18px 12px;text-align:center;gap:8px}
.level-display{display:flex;flex-direction:column;align-items:center;gap:6px;width:144px;max-width:100%}
.status-rings{max-width:100%;height:auto;aspect-ratio:1}
.level-caption{font-size:12px;font-weight:700;color:var(--level-color);overflow-wrap:anywhere}
.profile{font-size:15px;font-weight:600;margin:0;max-width:100%;overflow-wrap:anywhere}
.entry,.message{font-size:12px;color:var(--iq-muted);margin:0;overflow-wrap:anywhere}
.grade-caption{max-width:100%;overflow-wrap:anywhere}
`;

export function cardMarkup(data,now) {
  const display=recognitionDisplayData(data,now),s=display.status;
  const active=Boolean(s.active&&s.profile_id);
  const stage=display.config.stages[active?s.level:0];
  const color=/^#[a-f\d]{6}$/i.test(stage?.color)?stage.color:"var(--primary-color)";
  const remaining=active&&Number.isFinite(s.pending_until)?Math.max(0,Math.ceil(s.pending_until-now)):null;
  const entry=remaining===null?"":`<p class="entry">Eingangsverzögerung ${String(Math.floor(remaining/60)).padStart(2,"0")}:${String(remaining%60).padStart(2,"0")}</p>`;
  return `<div class="content" style="--level-color:${color}">${statusRings(display,now)}<p class="profile">${esc(active?s.profile_name||"IQAlarm":"Anlage aus")}</p>${entry}</div>`;
}

export class IQAlarmCard extends HTMLElement {
  constructor() {
    super();this.attachShadow({mode:"open"});
    this.shadowRoot.innerHTML=`<style>${LIVE_VIEW_CSS}${css}</style><ha-card><div id="status"></div></ha-card>`;
    this._generation=0;this._retryDelay=1000;this._live=false;
    this._onDisconnect=()=>{this._live=false;this._message="Verbindung unterbrochen";this._render();};
    this._onReady=()=>{this._resetSubscription();this._connect();};
  }
  static getStubConfig(){return {};}
  static get cardType(){return "custom:iqalarm-card";}
  static getConfigForm(){return {schema:[]};}
  getCardSize(){return 5;}
  getGridOptions(){return {columns:6,rows:"auto",min_columns:3};}
  setConfig(config) {
    if(!config||config.type!==this.constructor.cardType)throw new Error(`Kartentyp muss ${this.constructor.cardType} sein`);
    this._config={...config};this._render();this._connect();
  }
  set hass(value) {
    if(this._hass?.connection!==value?.connection){this._resetSubscription();this._unlisten();}
    this._hass=value;
    if(this.isConnected){this._listen();this._connect();}
  }
  get hass(){return this._hass;}
  connectedCallback() {
    this._listen();this._connect();
    clearInterval(this._timer);this._timer=setInterval(()=>this._render(),1000);
  }
  disconnectedCallback() {
    clearInterval(this._timer);this._timer=null;
    this._resetSubscription();this._unlisten();
  }
  _listen() {
    const connection=this._hass?.connection;
    if(!connection||this._connection===connection)return;
    this._connection=connection;
    connection.addEventListener?.("disconnected",this._onDisconnect);
    connection.addEventListener?.("ready",this._onReady);
  }
  _unlisten() {
    this._connection?.removeEventListener?.("disconnected",this._onDisconnect);
    this._connection?.removeEventListener?.("ready",this._onReady);
    this._connection=null;
  }
  _resetSubscription() {
    this._generation++;this._connecting=false;this._live=false;this._denied=false;
    clearTimeout(this._retry);this._retry=null;
    const unsubscribe=this._unsubscribe;this._unsubscribe=null;
    if(unsubscribe)Promise.resolve().then(unsubscribe).catch(()=>{});
    this._render();
  }
  _retryConnect() {
    clearTimeout(this._retry);
    if(!this.isConnected)return;
    this._retry=setTimeout(()=>{this._retry=null;this._connect();},this._retryDelay);
    this._retryDelay=Math.min(30000,this._retryDelay*2);
  }
  async _connect() {
    if(!this.isConnected||!this._config||!this._hass?.connection||this._connecting||this._unsubscribe||this._retry||this._denied)return;
    const generation=++this._generation;this._connecting=true;
    try {
      const unsubscribe=await this._hass.connection.subscribeMessage(data=>{
        if(!this.isConnected||generation!==this._generation)return;
        if(data.available===false){this._live=false;this._message="IQAlarm nicht verfügbar";this._render();return;}
        if(!data.status||!data.config?.stages)return;
        this._data=data;this._live=true;this._retryDelay=1000;
        this._serverTime=Number.isFinite(data.status.server_time)?data.status.server_time:Date.now()/1000;
        this._receivedAt=performance.now()/1000;this._render();
      },{type:"iqalarm/subscribe"});
      if(!this.isConnected||generation!==this._generation){await unsubscribe();return;}
      this._unsubscribe=unsubscribe;
    } catch(error) {
      if(generation!==this._generation||!this.isConnected)return;
      this._live=false;
      const denied=["unauthorized","unauthorized_user"].includes(error?.code);
      this._denied=denied;
      this._message=denied?"Keine Berechtigung für IQAlarm":"IQAlarm nicht verfügbar";
      this._render();if(!denied)this._retryConnect();
    } finally {if(generation===this._generation)this._connecting=false;}
  }
  _render() {
    const host=this.shadowRoot?.getElementById("status");if(!host)return;
    if(this._live&&this._data){
      patchHTML(host,cardMarkup(this._data,this._serverTime+performance.now()/1000-this._receivedAt));
    }else patchHTML(host,`<div class="content"><p class="message" role="status">${esc(this._message||"Verbinde mit IQAlarm …")}</p></div>`);
  }
}

const floorplanCss=`
:host{display:block;color:var(--primary-text-color,#172a34);--iq-surface:var(--card-background-color,#fff);--iq-border:var(--divider-color,#d6dce0);--iq-muted:var(--secondary-text-color,#667580)}
ha-card{box-sizing:border-box;overflow:hidden}
.floorplans{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px;padding:16px}
.floorplan{min-width:0}.floorplan-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
h3{margin:0;font-size:15px;overflow-wrap:anywhere}.room-count{font-size:11px;color:var(--iq-muted);white-space:nowrap}
.plan-wrap{margin-top:10px}.plan-wrap.graphic-mode g[data-room],.plan-wrap.graphic-mode .room-label-group .room-badge{cursor:default;touch-action:auto}
.plan-wrap.graphic-mode g[data-room]{pointer-events:none}
.plan-wrap.graphic-mode .room-label-group:hover .room-badge{filter:none}
.message{padding:20px;text-align:center;color:var(--iq-muted);font-size:13px}
`;

export function selectedFloorplans(data,selection="") {
  const plans=Object.values(data.config.floorplans||{});
  if(!plans.length){
    if(selection&&selection!=="all")throw Error("Die ausgewählte Etage wurde nicht gefunden.");
    return Object.keys(data.config.rooms||{}).length?[{id:"virtual",name:"Raum-Grafik",width:1000,height:560,image:null,zones:{}}]:[];
  }
  if(!selection||selection==="all")return plans;
  const byId=plans.find(plan=>plan.id===selection);if(byId)return [byId];
  const byName=plans.filter(plan=>plan.name===selection);
  if(byName.length!==1)throw Error(byName.length?"Etagenname nicht eindeutig; bitte die Etagen-ID verwenden.":"Die ausgewählte Etage wurde nicht gefunden.");
  return byName;
}

export class IQAlarmFloorplanCard extends IQAlarmCard {
  constructor() {
    super();this._images=new Map();this._imageRequests=new Map();this._imageFailures=new Set();this._imageGeneration=0;
    this.shadowRoot.querySelector("style").textContent=floorplanCss;
  }
  static get cardType(){return "custom:iqalarm-floorplan-card";}
  static getConfigForm(){return {schema:[{name:"floorplan",label:"Etage (Name oder ID; leer: alle)",selector:{text:{}}}]};}
  getCardSize(){return 8;}
  getGridOptions(){return {columns:12,rows:"auto",min_columns:6};}
  setConfig(config) {
    if(config?.floorplan!==undefined&&(typeof config.floorplan!=="string"||config.floorplan.length>100))throw Error("Etage als Name oder ID angeben.");
    super.setConfig(config);
  }
  _clearImages() {
    this._imageGeneration++;
    for(const request of this._imageRequests?.values()||[])request.controller.abort();
    for(const cached of this._images?.values()||[])URL.revokeObjectURL(cached.url);
    this._imageRequests?.clear();this._images?.clear();this._imageFailures?.clear();
  }
  _resetSubscription() {this._clearImages();super._resetSubscription();}
  _syncImages(plans) {
    const wanted=new Map(plans.filter(plan=>plan.image).map(plan=>[plan.id,plan.image]));
    for(const [id,cached] of this._images)if(wanted.get(id)!==cached.image){URL.revokeObjectURL(cached.url);this._images.delete(id);}
    for(const [id,request] of this._imageRequests)if(wanted.get(id)!==request.image){request.controller.abort();this._imageRequests.delete(id);}
    for(const plan of plans){
      const key=`${plan.id}/${plan.image}`;
      if(!plan.image||this._images.get(plan.id)?.image===plan.image||this._imageRequests.has(plan.id)||this._imageFailures.has(key)||!this._hass?.fetchWithAuth)continue;
      const request={image:plan.image,controller:new AbortController()},generation=this._imageGeneration;
      this._imageRequests.set(plan.id,request);
      Promise.resolve().then(async()=>{
        const response=await this._hass.fetchWithAuth(`/api/iqalarm/floorplans/${encodeURIComponent(plan.id)}/image`,{signal:request.controller.signal});
        if(!response.ok)throw Error("Grundrissbild nicht verfügbar");
        const blob=await response.blob();
        if(!this.isConnected||!this._live||generation!==this._imageGeneration||this._imageRequests.get(plan.id)!==request)return;
        this._images.set(plan.id,{image:plan.image,url:URL.createObjectURL(blob)});
      }).catch(error=>{if(error?.name!=="AbortError"&&generation===this._imageGeneration)this._imageFailures.add(key);})
        .finally(()=>{if(this._imageRequests.get(plan.id)===request)this._imageRequests.delete(plan.id);if(this.isConnected&&generation===this._imageGeneration)this._render();});
    }
  }
  _render() {
    const host=this.shadowRoot?.getElementById("status");if(!host)return;
    if(!this._live||!this._data){patchHTML(host,`<p class="message" role="status">${esc(this._message||"Verbinde mit IQAlarm …")}</p>`);return;}
    if(!this._floorplanRenderer){
      if(!this._rendererPromise&&!this._rendererFailed){
        this._rendererPromise=import("./iqalarm-panel.js?v=2.15.2").then(module=>{
          this._floorplanRenderer=module;this.shadowRoot.querySelector("style").textContent=LIVE_VIEW_CSS+module.FLOORPLAN_VIEW_CSS+floorplanCss;
          if(this.isConnected)this._render();
        }).catch(()=>{this._rendererFailed=true;if(this.isConnected)this._render();});
      }
      patchHTML(host,`<p class="message" role="status">${this._rendererFailed?"Grundriss konnte nicht geladen werden.":"Grundriss wird geladen …"}</p>`);return;
    }
    let plans;
    try{plans=selectedFloorplans(this._data,this._config?.floorplan);}catch(error){this._syncImages([]);patchHTML(host,`<p class="message" role="status">${esc(error.message)}</p>`);return;}
    if(!plans.length){this._syncImages([]);patchHTML(host,'<p class="message" role="status">Kein Grundriss eingerichtet.</p>');return;}
    this._syncImages(plans);
    const now=this._serverTime+performance.now()/1000-this._receivedAt;
    patchHTML(host,`<div class="floorplans">${plans.map((plan,index)=>{
      const view=this._floorplanRenderer.renderLiveFloorplan(this._data,plan,{now,images:this._images,first:index===0});
      return `<section class="floorplan" data-live-key="floor-${esc(plan.id)}"><div class="floorplan-head"><h3>${esc(plan.name)}</h3><span class="room-count">${view.roomCount} ${view.roomCount===1?"Raum":"Räume"}</span></div>${view.svg}</section>`;
    }).join("")}</div>`);
  }
}

if(!customElements.get("iqalarm-card"))customElements.define("iqalarm-card",IQAlarmCard);
if(!customElements.get("iqalarm-floorplan-card"))customElements.define("iqalarm-floorplan-card",IQAlarmFloorplanCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="iqalarm-card"))window.customCards.push({
  type:"iqalarm-card",name:"IQAlarm",description:"Kompakter Live-Status mit IQAlarm-Ring, Bestätigungsgrad und Timern.",preview:true,
  documentationURL:"https://github.com/marcohildebrandtmail-hub/IQAlarm#iqalarm-dashboard-karte",
});
if(!window.customCards.some(card=>card.type==="iqalarm-floorplan-card"))window.customCards.push({
  type:"iqalarm-floorplan-card",name:"IQAlarm Grundriss",description:"Live-Grundriss mit Raumfarben und Statusanzeigen; alle oder eine ausgewählte Etage.",preview:true,
  documentationURL:"https://github.com/marcohildebrandtmail-hub/IQAlarm#iqalarm-grundriss-dashboard-karte",
});
