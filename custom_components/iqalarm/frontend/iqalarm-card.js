/* Read-only Lovelace card. Rendering and timer projection are shared with IQAlarm. */
import {LIVE_VIEW_CSS,patchHTML,recognitionDisplayData,statusRings} from "./live-view.js?v=2.15.0";

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
  static getConfigForm(){return {schema:[]};}
  getCardSize(){return 5;}
  getGridOptions(){return {columns:6,rows:"auto",min_columns:3};}
  setConfig(config) {
    if(!config||config.type!=="custom:iqalarm-card")throw new Error("Kartentyp muss custom:iqalarm-card sein");
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

if(!customElements.get("iqalarm-card"))customElements.define("iqalarm-card",IQAlarmCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="iqalarm-card"))window.customCards.push({
  type:"iqalarm-card",name:"IQAlarm",description:"Kompakter Live-Status mit IQAlarm-Ring, Bestätigungsgrad und Timern.",preview:true,
  documentationURL:"https://github.com/marcohildebrandtmail-hub/IQAlarm#iqalarm-dashboard-karte",
});
