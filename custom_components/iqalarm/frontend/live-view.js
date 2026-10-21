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
.status-rings .promotion-ring{stroke:var(--iq-red);stroke-linecap:butt;transition:stroke-dashoffset 1s linear}
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
function motionConfirmation(reports,connections) {
  const rooms=new Map();
  for(const report of reports){
    if(report.role!=="perimeter_sensor"||!report.room_id)continue;
    if(!rooms.has(report.room_id))rooms.set(report.room_id,new Map());
    const source=report.source_id||report.entity_id,previous=rooms.get(report.room_id).get(source);
    const expiry=report.expires_at??Infinity,oldExpiry=previous?.expires_at??Infinity;
    if(!previous||expiry>oldExpiry||(expiry===oldExpiry&&(report.timestamp||0)>(previous.timestamp||0)))rooms.get(report.room_id).set(source,report);
  }
  const neighbors=new Map([...rooms.keys()].map(room=>[room,new Set()]));
  for(const [a,b] of connections)if(a!==b&&rooms.has(a)&&rooms.has(b)){
    neighbors.get(a).add(b);neighbors.get(b).add(a);
  }
  const sources=(...ids)=>{
    const combined=new Map();
    for(const room of ids)for(const [source,report] of rooms.get(room))combined.set(source,report);
    return [...combined.values()].slice(0,3);
  };
  let best=[];
  for(const a of [...rooms.keys()].sort()){
    let candidate=sources(a);
    if(candidate.length===3)return candidate;
    if(candidate.length>best.length)best=candidate;
    for(const b of [...neighbors.get(a)].filter(room=>room>a).sort()){
      candidate=sources(a,b);
      if(candidate.length===3)return candidate;
      if(candidate.length>best.length)best=candidate;
      for(const c of [...neighbors.get(a)].filter(room=>room>b&&neighbors.get(b).has(room)).sort()){
        candidate=sources(a,b,c);
        if(candidate.length===3)return candidate;
      }
    }
  }
  return best.length>=2?best:[];
}

export function projectPersonProgress(progress,now,connections=[]) {
  return (progress||[]).flatMap(item=>{
    if(!item.person_reports)return [item];
    const reports=item.person_reports.filter(report=>report.expires_at==null||report.expires_at>now);
    const motionReports=(item.motion_reports||[]).filter(report=>report.expires_at==null||report.expires_at>now);
    const motion=motionConfirmation(motionReports,connections);
    const cameraGrade=(item.thresholds||[1,2,3]).filter(threshold=>reports.length>=threshold).length;
    const motionGrade=Math.max(0,motion.length-1),current=Math.min(3,cameraGrade+motionGrade);
    if(!current)return [];
    const deadlines=[...reports,...motion].map(report=>report.expires_at).filter(Number.isFinite);
    return [{...item,current,complete:current===item.target,person_reports:reports,motion_reports:motionReports,
      camera_grade:cameraGrade,motion_grade:motionGrade,
      next_decay:deadlines.length?Math.min(...deadlines):null,
      sources:[...reports,...motion].map(({expires_at,...source})=>source)}];
  });
}
export function alarmProgress(data,now) {
  const a=data.status.alarm;
  if(!a||a.escalated||data.status.stage_id!==a.stage_id||!data.status.active||!(a.duration>0))return null;
  return Math.max(0,Math.min(1,1-(a.deadline-now)/a.duration));
}
export function ringValues(data,now=Date.now()/1000) {
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
  const elapsed=alarmProgress(data,now);
  if(elapsed!==null)grade={kind:"escalation",current:elapsed,target:1};
  return {level:Math.max(0,Math.min(1,status.level/Math.max(1,data.config.stages.length-1))),grade,confirmation:grade?Math.max(0,Math.min(1,grade.current/grade.target)):0};
}
export function startupProgress(data,now) {
  const s=data.status;
  if(!s.active||!s.profile_id||!Number.isFinite(s.arming_until))return null;
  const start=s.arming_started_at??(s.arming_until-(data.config.settings?.startup_delay_seconds??60));
  return s.arming_until>start?Math.max(0,Math.min(1,(now-start)/(s.arming_until-start))):null;
}
export function promotionProgress(data,now) {
  const startup=startupProgress(data,now);if(startup!==null)return startup;
  const alarm=alarmProgress(data,now);if(alarm!==null)return alarm;
  const status=data.status,settings=data.config.automatic_detection;
  if(!settings||status.active===false||status.mode==='inactive'||status.profile_id===null||status.stage_id!==settings.stage_id||!(settings.promote_seconds>0))return null;
  const deadlines=(status.rule_progress||[]).filter(item=>item.stage_id===settings.stage_id&&item.current===3&&item.target===3&&item.detected_at==null&&Number.isFinite(item.next_level_at)).map(item=>item.next_level_at);
  if(!deadlines.length)return null;
  const end=Math.min(...deadlines);
  return Math.max(0,Math.min(1,1-(end-now)/settings.promote_seconds));
}
export function statusRings(data,now=Date.now()/1000) {
  const isInactive = data.status.active === false || data.status.mode === "inactive" || data.status.profile_id === null;
  const {level,grade,confirmation}=ringValues(data,now),outer=2*Math.PI*61,inner=2*Math.PI*46;
  const label=grade?.kind==="coverage"?"Überwachungsrisiko":"Bestätigungsgrad";
  const stageName = isInactive ? (data.config.stages[0]?.name || "Deaktiviert") : data.status.stage_name;
  const levelNum = isInactive ? 0 : data.status.level;
  const startup=startupProgress(data,now);
  const remaining=startup!==null?Math.max(0,Math.ceil(data.status.arming_until-now)):null;
  const timer=startup!==null?`Start in ${String(Math.floor(remaining/60)).padStart(2,"0")}:${String(remaining%60).padStart(2,"0")}`:grade?.kind==="escalation"?`LVL 5 in ${String(Math.floor(Math.max(0,Math.ceil(data.status.alarm.deadline-now))/60)).padStart(2,"0")}:${String(Math.max(0,Math.ceil(data.status.alarm.deadline-now))%60).padStart(2,"0")}`:null;
  const promotion=promotionProgress(data,now);
  const overlay=promotion===null?'':`<circle class="promotion-ring" data-promotion-ring cx="72" cy="72" r="61" stroke-width="8" stroke-dasharray="${outer}" stroke-dashoffset="${outer*(1-promotion)}"/>`;
  return `<div class="level-display" data-live-key="status-rings"><div class="level-caption">${esc(stageName)}</div><svg class="status-rings" viewBox="0 0 144 144" role="img" aria-label="Alarmstufe ${levelNum}${timer?`, ${timer}`:grade?`, ${label} ${grade.current} von ${grade.target}`:""}"><circle class="ring-track" cx="72" cy="72" r="61" stroke-width="8"/><circle data-level-ring cx="72" cy="72" r="61" stroke="var(--level-color)" stroke-width="8" stroke-dasharray="${outer}" stroke-dashoffset="${outer*(1-level)}"/><circle class="ring-track" cx="72" cy="72" r="46" stroke-width="6"/><circle ${grade?.kind==="coverage"?"data-risk-ring":"data-confirmation-ring"} cx="72" cy="72" r="46" stroke="${grade?.kind==="coverage"?"var(--iq-amber)":"var(--iq-accent)"}" stroke-width="6" stroke-dasharray="${inner}" stroke-dashoffset="${inner*(1-confirmation)}"/>${overlay}<text x="72" y="72">${levelNum}</text></svg>${grade||timer?`<small class="grade-caption">${timer||`${label} ${grade.current}/${grade.target}`}</small>`:""}</div>`;
}
