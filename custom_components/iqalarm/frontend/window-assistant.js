import {randomId} from "./floorplan-rooms.js?v=2.3.0";
/* Directly executable window setup wizard. All recognition is verified by HA. */
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const labels = {closed:"Geschlossen",unlatched:"Geschlossen · entriegelt",open:"Offen",tilt_ready:"Geschlossen · Griff in Kippstellung",tilted:"Gekippt geöffnet"};
const instructions = {
  closed:"Fenster vollständig schließen und verriegeln.",
  unlatched:"Jetzt entriegeln, das Fenster aber geschlossen lassen.",
  open:"Jetzt das Fenster öffnen.",
  tilt_ready:"Fenster wieder geschlossen halten und den Griff in Kippstellung bringen.",
  tilted:"Jetzt das Fenster gekippt öffnen.",
};
const CSS = `:host{display:block;font:inherit;color:var(--primary-text-color,#182b42)}*{box-sizing:border-box}p{font-size:13px;line-height:1.6;color:var(--secondary-text-color,#64758b)}h3{margin:0 0 12px;font-size:18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.wide{grid-column:1/-1}label{display:grid;gap:7px;font-size:12px;font-weight:600}input,select,button{font:inherit;color:inherit}input,select{min-height:42px;padding:10px;border:1px solid var(--divider-color,#dce3ec);border-radius:8px;background:var(--card-background-color,#fff);width:100%;min-width:0}button{min-height:42px;padding:10px 14px;border:1px solid var(--divider-color,#dce3ec);border-radius:9px;background:var(--card-background-color,#fff);cursor:pointer}.primary{background:var(--primary-color,#087e9b);color:var(--text-primary-color,#fff);border-color:transparent}button:disabled{opacity:.5;cursor:not-allowed}input:focus-visible,select:focus-visible,button:focus-visible{outline:3px solid var(--primary-color,#087e9b);outline-offset:2px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.end{justify-content:flex-end}.foot{margin-top:22px;padding-top:16px;border-top:1px solid var(--divider-color,#dce3ec)}.preview{margin:18px 0;padding:15px;border:1px solid var(--divider-color,#dce3ec);border-radius:10px;background:var(--primary-background-color,#f3f6fa)}.signal{padding:9px 0;border-bottom:1px solid var(--divider-color,#dce3ec);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;font-size:12px}.signal code{display:block;overflow-wrap:anywhere;font-size:10px;color:var(--secondary-text-color,#64758b)}.fault,.error{color:var(--error-color,#bd3349)}.error:empty{display:none}.error{font-size:13px;line-height:1.6;white-space:pre-wrap;margin-top:12px}.step{font-size:12px;color:var(--secondary-text-color,#64758b);margin-bottom:12px}.check{display:flex;align-items:flex-start;gap:10px;font-weight:400;line-height:1.5}.check input{width:18px;min-height:18px;flex-shrink:0}small{font-size:11px;line-height:1.5;font-weight:400;color:var(--secondary-text-color,#64758b)}details{margin-top:18px}summary{cursor:pointer;font-size:13px;margin-bottom:12px}.learned{display:flex;gap:7px;flex-wrap:wrap;font-size:11px;margin:14px 0}.learned span{padding:5px 8px;border:1px solid var(--divider-color,#dce3ec);border-radius:6px}[hidden]{display:none!important}@media(max-width:600px){.grid{grid-template-columns:1fr}.foot button{flex:1}}`;

class WindowAssistant extends HTMLElement {
  constructor() {
    super();this.attachShadow({mode:"open"});this.phase="sources";this.index=0;this.busy=false;this.polling=false;this.stopped=false;
    this.shadowRoot.addEventListener("click", event => {const action=event.target.closest("button")?.dataset.act;if(action)this.act(action);});
    this.shadowRoot.addEventListener("submit", event=>{event.preventDefault();event.stopPropagation();if(this.phase==="sources")this.act("next");});
    this.shadowRoot.addEventListener("change", event => {
      if(event.target.name==="lock_entity_id") {
        const guard=this.shadowRoot.querySelector('[name="availability_entity_id"]');
        if(guard&&!guard.value)guard.value=event.target.value;
      }
    });
  }
  setup({hass,catalog,rooms,windows,initial,onSave,onCancel}) {
    this.hass=hass;this.catalog=catalog;this.rooms=rooms;this.windows=windows;this.onSave=onSave;this.onCancel=onCancel;
    this.window=structuredClone(initial||{id:randomId(),name:"",room_id:"",contact_entity_id:null,handle_entity_ids:[],lock_entity_id:null,availability_entity_id:null,availability_states:[],allow_unknown_inputs:[],mappings:[],settle_seconds:1,enabled:true,entry_delay:false,contact_open_states:["on"]});
    this.render();
  }
  disconnectedCallback(){this.stop();}
  stop(){this.stopped=true;clearTimeout(this.timer);}
  sourceOptions(value, domains, blank="Nicht vorhanden") {
    const claimed=new Set(Object.values(this.windows).filter(w=>w.id!==this.window.id).flatMap(w=>[w.contact_entity_id,...w.handle_entity_ids].filter(Boolean)));
    return `<option value="">${esc(blank)}</option>`+this.catalog.entities.filter(e=>domains.includes(e.entity_id.split(".")[0])&&!claimed.has(e.entity_id)&&!e.entity_id.startsWith("sensor.iqalarm")&&!e.entity_id.startsWith("binary_sensor.iqalarm")).sort((a,b)=>a.name.localeCompare(b.name,"de")).map(e=>`<option value="${esc(e.entity_id)}"${e.entity_id===value?" selected":""}>${esc(e.name)} · ${esc(e.entity_id)}</option>`).join("");
  }
  field(name,label,value,domains){return `<label>${label}<select name="${name}" aria-label="${label}">${this.sourceOptions(value,domains)}</select></label>`;}
  render(){
    if(!this.window)return;
    const w=this.window;
    let body;
    if(this.phase==="sources"){
      body=`<p>Ein Fenster, ein Gesamtstatus. Wähle einen einzelnen Kontakt oder kombiniere ihn mit bis zu zwei Griffsignalen. Das Schloss meldet Verriegelung und gegebenenfalls die Verbindung.</p><form id="sources"><div class="grid"><label>Fenstername<input name="name" aria-label="Fenstername" required maxlength="100" value="${esc(w.name)}" placeholder="z. B. Wohnzimmer rechts"></label><label>Raum<select name="room_id" aria-label="Raum" required><option value="">Raum auswählen</option>${Object.values(this.rooms).map(r=>`<option value="${esc(r.id)}"${r.id===w.room_id?" selected":""}>${esc(r.name)}</option>`).join("")}</select></label>${this.field("contact_entity_id","Fensterkontakt",w.contact_entity_id,["binary_sensor","sensor"])}${this.field("lock_entity_id","Fenstergriff – Schloss",w.lock_entity_id,["lock"])}${this.field("handle_1","Griffsignal 1",w.handle_entity_ids[0],["binary_sensor","sensor"])}${this.field("handle_2","Griffsignal 2",w.handle_entity_ids[1],["binary_sensor","sensor"])}${this.field("availability_entity_id","Verbindungsüberwachung",w.availability_entity_id,["lock","binary_sensor","sensor"])}</div><details><summary>Weitere Einstellungen</summary><div class="grid"><label>Stabilisierungszeit (Sekunden)<input name="settle_seconds" aria-label="Stabilisierungszeit (Sekunden)" type="number" min="0.2" max="10" step="0.1" value="${w.settle_seconds}" required></label><label>Verbindung bei diesen Werten<input name="availability_states" aria-label="Verbindung bei diesen Werten" value="${esc(w.availability_states.join(", "))}" placeholder="Leer: jeder gültige Zustand"><small>Bei einem Online-Binary-Sensor beispielsweise on.</small></label><label class="check"><input type="checkbox" name="invert"${w.contact_open_states.includes("off")?" checked":""}>Fensterkontakt invertieren (off bedeutet geöffnet)</label><label class="check"><input type="checkbox" name="entry_delay"${w.entry_delay?" checked":""}>Eingangsverzögerung erlauben</label><label class="check wide"><input type="checkbox" name="allow_unknown"${w.allow_unknown_inputs.length?" checked":""}>Griffsignal unknown ausdrücklich als Stellungscode zulassen<small>Nur für Geräte, die diesen Code tatsächlich für eine Stellung verwenden. Eine separate, gültige Verbindungsüberwachung ist erforderlich. unavailable ist immer ein Fehler.</small></label><label class="check"><input type="checkbox" name="enabled"${w.enabled?" checked":""}>Fenster überwachen</label></div></details></form><div class="row end foot"><button type="button" data-act="cancel">Abbrechen</button><button type="button" class="primary" data-act="next">Weiter: Fensterstellungen</button></div>`;
    }else{
      const verify=this.phase==="verify",state=this.steps[this.index];
      body=`<div class="step">${verify?"Abschluss · Live-Test":`Stellung ${this.index+1} von ${this.steps.length}`}</div><h3>${verify?"Erkennung prüfen":esc(instructions[state])}</h3><p>${verify?"Bewege das Fenster und prüfe die Anzeige. Zum Abschluss wieder schließen und verriegeln. Fehlende Verbindungen werden ausdrücklich angezeigt.":"Warte auf stabile Meldungen und übernimm dann den Zustand. Nicht unterstützte Stellungen kannst du überspringen."}</p><div class="learned">${w.mappings.map(rule=>`<span>${esc(labels[rule.state])} ✓</span>`).join("")}</div><div id="preview" class="preview" aria-live="polite">Signale werden gelesen …</div><div class="row foot"><button type="button" data-act="sources">Sensorzuordnung</button>${verify?'<button type="button" data-act="relearn">Neu einlernen</button>':`<button type="button" data-act="prev"${this.index===0?" disabled":""}>Zurück</button><button type="button" data-act="skip">Schritt überspringen</button>`}<button type="button" data-act="cancel">Abbrechen</button><button type="button" class="primary" data-act="${verify?"save":"capture"}"${!verify?" disabled":""}>${verify?"Fenster speichern":"Zustand übernehmen"}</button></div>`;
    }
    this.shadowRoot.innerHTML=`<style>${CSS}</style>${body}<div id="error" class="error" role="alert"></div>`;
    if(this.phase!=="sources")this.poll();
  }
  error(message){this.shadowRoot.getElementById("error").textContent=message||"";}
  readSources(){
    const form=this.shadowRoot.getElementById("sources");if(!form.reportValidity())return false;
    const data=new FormData(form),get=key=>String(data.get(key)||"");
    const handles=[get("handle_1"),get("handle_2")].filter(Boolean),contact=get("contact_entity_id")||null,lock=get("lock_entity_id")||null,guard=get("availability_entity_id")||lock;
    if(!contact&&!handles.length)throw new Error("Bitte mindestens einen Fensterkontakt oder ein Griffsignal auswählen.");
    if(new Set([contact,...handles].filter(Boolean)).size!==[contact,...handles].filter(Boolean).length)throw new Error("Jedes Stellungssignal darf nur einmal zugeordnet werden.");
    if(data.has("allow_unknown")&&!guard)throw new Error("unknown als Stellungscode benötigt eine separate Verbindungsüberwachung.");
    const before=JSON.stringify([this.window.contact_entity_id,this.window.handle_entity_ids,this.window.allow_unknown_inputs,this.window.contact_open_states]);
    Object.assign(this.window,{name:get("name").trim(),room_id:get("room_id"),contact_entity_id:contact,handle_entity_ids:handles,lock_entity_id:lock,availability_entity_id:guard,availability_states:get("availability_states").split(",").map(x=>x.trim()).filter(Boolean),allow_unknown_inputs:data.has("allow_unknown")?handles:[],settle_seconds:Number(get("settle_seconds")),enabled:data.has("enabled"),entry_delay:data.has("entry_delay"),contact_open_states:data.has("invert")?["off"]:["on"]});
    const after=JSON.stringify([contact,handles,this.window.allow_unknown_inputs,this.window.contact_open_states]);
    if(before!==after)this.window.mappings=[];
    this.steps=handles.length?Object.keys(labels):["closed","open"];
    return true;
  }
  async call(type,args={}){return this.hass.callWS({type:`iqalarm/window/${type}`,window:this.window,...args});}
  async poll(){
    clearTimeout(this.timer);if(this.stopped||this.phase==="sources"||this.polling)return;
    this.polling=true;
    try{
      const preview=await this.call("preview");
      if(this.stopped||this.phase==="sources")return;
      this.preview=preview;
      const target=this.shadowRoot.getElementById("preview");
      if(target)target.innerHTML=`<strong class="${preview.available?"":"fault"}">${esc(preview.label)}</strong><p>${!preview.stable?"Meldungen ändern sich noch …":preview.available?"Signale stabil":"Benötigtes Signal fehlt"}${this.window.lock_entity_id?` · Schloss: ${preview.locked===true?"verriegelt":preview.locked===false?"entriegelt":"nicht verfügbar"}`:""}</p>${Object.entries(preview.inputs).map(([id,value])=>`<div class="signal"><div>${esc(this.catalog.entities.find(e=>e.entity_id===id)?.name||id)}<code>${esc(id)}</code></div><span class="${preview.faults.includes(id)?"fault":""}">${esc(value)}</span></div>`).join("")}`;
      const capture=this.shadowRoot.querySelector('[data-act="capture"]');if(capture)capture.disabled=this.busy||!preview.can_capture;
    }catch(err){this.error(`Signale konnten nicht gelesen werden: ${err.message||err}`);const button=this.shadowRoot.querySelector('[data-act="capture"]');if(button)button.disabled=true;}
    finally{this.polling=false;if(!this.stopped&&this.phase!=="sources")this.timer=setTimeout(()=>this.poll(),750);}
  }
  async act(action){
    if(this.busy)return;this.error("");
    try{
      if(action==="cancel"){this.stop();this.onCancel();return;}
      if(action==="next"){
        if(!this.readSources())return;
        await this.call("preview");
        this.phase=this.window.mappings.length?"verify":"learn";this.index=0;this.render();return;
      }
      if(action==="sources"){clearTimeout(this.timer);this.phase="sources";this.render();return;}
      if(action==="relearn"){this.window.mappings=[];this.index=0;this.phase="learn";this.render();return;}
      if(action==="prev"){this.index=Math.max(0,this.index-1);this.render();return;}
      if(action==="capture"){
        this.busy=true;
        const button=this.shadowRoot.querySelector('[data-act="capture"]');if(button)button.disabled=true;
        const result=await this.call("capture",{state:this.steps[this.index]});
        this.window.mappings=this.window.mappings.filter(rule=>rule.state!==result.mapping.state).concat(result.mapping);
      }
      if(action==="capture"||action==="skip"){
        if(action==="skip")this.window.mappings=this.window.mappings.filter(rule=>rule.state!==this.steps[this.index]);
        this.index++;if(this.index>=this.steps.length)this.phase="verify";this.render();return;
      }
      if(action==="save"){
        if(!["closed","open"].every(state=>this.window.mappings.some(rule=>rule.state===state)))throw new Error("Bitte mindestens Geschlossen und Offen einlernen. Über „Neu einlernen“ kannst du die Schritte wiederholen.");
        this.busy=true;const button=this.shadowRoot.querySelector('[data-act="save"]');button.disabled=true;
        await this.onSave(structuredClone(this.window));this.stop();
      }
    }catch(err){this.error(err.message||String(err));}
    finally{this.busy=false;const save=this.shadowRoot.querySelector('[data-act="save"]');if(save)save.disabled=false;const capture=this.shadowRoot.querySelector('[data-act="capture"]');if(capture)capture.disabled=!this.preview?.can_capture;}
  }
}
if(!customElements.get("iqalarm-window-assistant"))customElements.define("iqalarm-window-assistant",WindowAssistant);
