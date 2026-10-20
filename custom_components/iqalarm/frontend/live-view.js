/* Keep live SVG nodes attached so CSS transitions can interpolate their colors. */
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function key(node) {
  if(node.nodeType!==1)return "";
  for(const name of ["id","data-live-key","data-plan-id","data-room","data-rule-grade","data-sensor-state-id"]){
    if(node.hasAttribute(name))return `${node.nodeName}:${name}:${node.getAttribute(name)}:${node.hasAttribute("data-label-room")}`;
  }
  return "";
}
function compatible(a,b){return a&&a.nodeType===b.nodeType&&a.nodeName===b.nodeName;}
export function patchNode(current,next) {
  if(current.nodeType!==1){if(current.nodeValue!==next.nodeValue)current.nodeValue=next.nodeValue;return;}
  for(const attr of [...current.attributes]){
    if(attr.name==="open"&&current.localName==="details")continue;
    if(!next.hasAttribute(attr.name))current.removeAttribute(attr.name);
  }
  for(const attr of next.attributes)if(current.getAttribute(attr.name)!==attr.value)current.setAttribute(attr.name,attr.value);
  patchChildren(current,next);
}
function patchChildren(current,next) {
  const old=[...current.childNodes],used=new Set(),keys=new Map(old.filter(n=>key(n)).map(n=>[key(n),n]));
  // Remove disappearing keyed cards before aligning siblings. Moving the live
  // floorplan in front of a card that is about to disappear cancels SVG fades.
  const wanted=new Set([...next.childNodes].map(key).filter(Boolean));
  for(const node of old)if(key(node)&&!wanted.has(key(node)))node.remove();
  let position=current.firstChild;
  for(const node of [...next.childNodes]){
    const id=key(node);
    let target=id?keys.get(id):old.find(n=>!used.has(n)&&!key(n)&&compatible(n,node));
    if(!compatible(target,node))target=null;
    if(target){used.add(target);if(target!==position)current.insertBefore(target,position);patchNode(target,node);}
    else{target=node.cloneNode(true);current.insertBefore(target,position);}
    position=target.nextSibling;
  }
  for(const node of old)if(!used.has(node))node.remove();
}
export function patchHTML(host,html) {
  const buffer=document.createElement("template");buffer.innerHTML=html;patchChildren(host,buffer.content);
}
export const LIVE_VIEW_CSS=`
.status-rings{display:block;width:144px;height:144px;overflow:visible}
.status-rings circle{fill:none;transform:rotate(-90deg);transform-origin:72px 72px;stroke-linecap:round;transition:stroke-dashoffset .7s ease,stroke .9s ease}
.status-rings .ring-track{stroke:var(--iq-border);stroke-linecap:butt}
.status-rings text{fill:var(--level-color);font:750 36px system-ui;text-anchor:middle;dominant-baseline:central}
.grade-caption{font-size:12px;color:var(--iq-muted)}
.confirmation-context{margin-top:8px;min-width:0;overflow-wrap:anywhere}
.confirmation-context p{margin:2px 0 0;font-size:12px;line-height:1.4}
.hero .hero-copy{flex:1}
.hero-coverage{flex:0 1 280px;min-width:0;max-width:100%;margin-left:auto;align-self:flex-start;font-size:12px}
.hero-coverage>.row{align-items:flex-start;gap:8px;flex-direction:column}
.hero .hero-coverage .pill{display:inline-flex;margin-left:0;align-self:auto}
@media(max-width:700px){.hero-coverage{flex-basis:100%;margin-left:0}}
.live-floorplan-title,.live-floorplan-controls{flex:0 0 auto;max-width:100%}
.live-trigger-list{flex:1 1 180px;min-width:0;display:grid;gap:3px}
.live-trigger-list[hidden]{display:none}
.live-trigger-item{display:flex;justify-content:center;gap:6px;min-width:0;font-size:12px;line-height:1.35}
.live-trigger-name{min-width:0;overflow-wrap:anywhere}
.live-trigger-timer{flex:none;white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--iq-muted)}
@media(max-width:700px){.live-trigger-list{order:3;flex-basis:100%}.live-trigger-item{justify-content:flex-start}}
.plan-wrap polygon,.plan-wrap .room-badge,.plan-wrap .room-corner{transition:fill var(--room-fade-duration,1.5s) ease,stroke var(--room-fade-duration,1.5s) ease,fill-opacity var(--room-fade-duration,1.5s) ease,stroke-opacity var(--room-fade-duration,1.5s) ease}
@media(prefers-reduced-motion:reduce){.status-rings circle{transition:none!important}.plan-wrap .anim-pulse,.plan-wrap .anim-pulse .room-badge{animation:none!important}.plan-wrap polygon,.plan-wrap .room-badge,.plan-wrap .room-corner{transition:fill var(--room-fade-duration,1.5s) ease,stroke var(--room-fade-duration,1.5s) ease,fill-opacity var(--room-fade-duration,1.5s) ease,stroke-opacity var(--room-fade-duration,1.5s) ease!important}}
`;

export function liveTriggers(data,now) {
  const status=data.status;
  if(!status.active)return [];
  const entries=new Map();
  for(const [room,details] of Object.entries(status.rooms||{}))for(const item of details.recognitions||[]){
    if(["unavailable","flapping"].includes(item.event))continue;
    if(item.expires_at!=null&&(!Number.isFinite(item.expires_at)||item.expires_at<=now))continue;
    for(const source of item.sources||[]){
      const id=source.entity_id;
      if(!id||status.raw?.[id]==null||status.quarantine?.[id]||status.ignored_windows?.includes(id)||status.robot_paused_sensors?.includes(id))continue;
      const identity=item.report_id||id;
      const previous=entries.get(identity),timestamp=Number.isFinite(source.timestamp)?source.timestamp:0;
      const expires=previous?(previous.expires_at==null||item.expires_at==null?null:Math.max(previous.expires_at,item.expires_at)):item.expires_at??null;
      const current={key:identity,entity_id:id,timestamp,expires_at:expires,
        name:source.name||data.config.sensors?.[id]?.name||id,
        room:data.config.rooms?.[source.room_id||room]?.name||""};
      entries.set(identity,previous&&previous.timestamp>timestamp?{...previous,expires_at:expires}:current);
    }
  }
  return [...entries.values()].sort((a,b)=>b.timestamp-a.timestamp||a.entity_id.localeCompare(b.entity_id)).slice(0,3);
}

export function triggerRows(data,now) {
  return liveTriggers(data,now).map(item=>{
    const seconds=item.expires_at==null?null:Math.max(0,Math.ceil(item.expires_at-now));
    const timer=seconds==null?(data.status.raw[item.entity_id]===true?"Aktiv":"Bis Ausschalten"):
      `noch ${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;
    return `<div class="live-trigger-item" role="listitem" data-live-key="live-trigger:${esc(item.key)}" data-live-trigger="${esc(item.entity_id)}"><span class="live-trigger-name">${esc([item.room,item.name].filter(Boolean).join(" · "))}</span><span class="live-trigger-timer">${esc(timer)}</span></div>`;
  }).join("");
}
export function projectPersonProgress(progress,now) {
  return (progress||[]).flatMap(item=>{
    if(!item.person_reports)return [item];
    const reports=item.person_reports.filter(report=>report.expires_at==null||report.expires_at>now);
    const current=(item.thresholds||[1,2,3]).filter(threshold=>reports.length>=threshold).length;
    if(!current)return [];
    const deadlines=reports.map(report=>report.expires_at).filter(Number.isFinite);
    return [{...item,current,complete:current===item.target,person_reports:reports,
      next_decay:deadlines.length?Math.min(...deadlines):null,
      sources:reports.map(({expires_at,...source})=>source)}];
  });
}
export function ringValues(data) {
  const status=data.status;
  const isInactive = status.active === false || status.mode === "inactive" || status.profile_id === null;
  if(isInactive){
    return {level:0,grade:null,confirmation:0};
  }
  const entries=(status.rule_progress||[]).filter(p=>p.stage_id===status.stage_id&&p.target>0);
  let grade=entries.reduce((best,item)=>!best||item.current/item.target>best.current/best.target?item:best,null);
  if(status.profile_id&&status.stage_id===data.config.secure_stage_id&&(Object.values(data.config.robots||{}).some(robot=>robot.enabled)||status.ignored_windows?.length)){
    const coverage=status.coverage||{current:0,target:3};grade={...coverage,kind:"coverage"};
  }
  return {level:Math.max(0,Math.min(1,status.level/Math.max(1,data.config.stages.length-1))),grade,confirmation:grade?Math.max(0,Math.min(1,grade.current/grade.target)):0};
}
export function statusRings(data) {
  const isInactive = data.status.active === false || data.status.mode === "inactive" || data.status.profile_id === null;
  const {level,grade,confirmation}=ringValues(data),outer=2*Math.PI*61,inner=2*Math.PI*46;
  const label=grade?.kind==="coverage"?"Überwachungsrisiko":"Bestätigungsgrad";
  const stageName = isInactive ? (data.config.stages[0]?.name || "Deaktiviert") : data.status.stage_name;
  const levelNum = isInactive ? 0 : data.status.level;
  return `<div class="level-display" data-live-key="status-rings"><div class="level-caption">${esc(stageName)}</div><svg class="status-rings" viewBox="0 0 144 144" role="img" aria-label="Alarmstufe ${levelNum}${grade?`, ${label} ${grade.current} von ${grade.target}`:""}"><circle class="ring-track" cx="72" cy="72" r="61" stroke-width="8"/><circle data-level-ring cx="72" cy="72" r="61" stroke="var(--level-color)" stroke-width="8" stroke-dasharray="${outer}" stroke-dashoffset="${outer*(1-level)}"/><circle class="ring-track" cx="72" cy="72" r="46" stroke-width="6"/><circle ${grade?.kind==="coverage"?"data-risk-ring":"data-confirmation-ring"} cx="72" cy="72" r="46" stroke="${grade?.kind==="coverage"?"var(--iq-amber)":"var(--iq-accent)"}" stroke-width="6" stroke-dasharray="${inner}" stroke-dashoffset="${inner*(1-confirmation)}"/><text x="72" y="72">${levelNum}</text></svg>${grade?`<small class="grade-caption">${label} ${grade.current}/${grade.target}</small>`:""}</div>`;
}
