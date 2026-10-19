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
.plan-wrap polygon,.plan-wrap .room-badge,.plan-wrap .room-corner{transition:fill 1.5s ease,stroke 1.5s ease,fill-opacity 1.5s ease,stroke-opacity 1.5s ease}
@media(prefers-reduced-motion:reduce){.status-rings circle{transition:none!important}.plan-wrap .anim-pulse,.plan-wrap .anim-pulse .room-badge{animation:none!important}.plan-wrap polygon,.plan-wrap .room-badge,.plan-wrap .room-corner{transition:fill 1.5s ease,stroke 1.5s ease,fill-opacity 1.5s ease,stroke-opacity 1.5s ease!important}}
`;
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
