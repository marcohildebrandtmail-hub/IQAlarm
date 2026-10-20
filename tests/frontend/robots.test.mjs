import test from "node:test";
import assert from "node:assert/strict";
import {renderCoverage,renderRobotSettings,updateRobotStatuses} from "../../custom_components/iqalarm/frontend/robots.js";
import {renderLevels} from "../../custom_components/iqalarm/frontend/level-configuration.js";

function panel() {
  const robot={id:"bot",name:"Saugroboter <EG>",activities:[{entity_id:"vacuum.robot"}],room_ids:["kitchen"],floorplan_id:null,risk_points:1,enabled:true};
  return {stage:"1",_head:()=>"",_lockNote:()=>"",_stagesEditor:()=>"",data:{config:{robots:{bot:robot},rooms:{kitchen:{id:"kitchen",name:"Küche"}},floorplans:{},stages:[{id:"0",name:"Aus",color:"#fff"},{id:"1",name:"Sicher",color:"#000"},{id:"2",name:"Außen",color:"#000"}],secure_stage_id:"1",rules:{},profiles:{}},status:{profile_id:"night",coverage:{current:1,target:3,robots:[{...robot,active:true,waiting:false,fault:false,paused_sensors:["binary_sensor.motion"]}]}}}};
}
test("robot settings belong to the secure baseline and retain configurable scope and points",()=>{
  const p=panel(),html=renderLevels(p);
  assert.match(html,/Roboter & Überwachungsrisiko/);assert.match(html,/Küche · 1 Aktivitätsentitäten · 1\/3 Risikopunkte/);
  assert.match(html,/data-command="robot-edit"/);assert.match(html,/data-command="robot-delete"/);
  p._number=(name,label,value)=>`<label>${label}<input name="${name}" value="${value}"></label>`;
  p.stage="2";assert.doesNotMatch(renderLevels(p),/robot-new/);
  p.stage="0";assert.doesNotMatch(renderLevels(p),/robot-new/);
});
test("live coverage is informational, escapes names and disappears while disarmed",()=>{
  const p=panel(),html=renderCoverage(p);
  assert.match(html,/Überwachungsrisiko 1\/3/);assert.match(html,/1 Bewegungsmelder ausgenommen/);
  assert.match(html,/Saugroboter &lt;EG&gt;/);assert.doesNotMatch(html,/<EG>|data-rule-grade/);
  p.data.status.profile_id=null;assert.equal(renderCoverage(p),"");
});
test("source connection failures stay visible even while another source activates the robot",()=>{
  const p=panel();p.data.status.coverage.robots[0].fault=true;
  assert.match(renderCoverage(p),/Aktiv · 1 Bewegungsmelder ausgenommen · Störung: Aktivität nicht vollständig verfügbar/);
  assert.match(renderRobotSettings(p),/Störung: Aktivität nicht vollständig verfügbar/);
});
test("idle exceptions disappear from live status and disabled settings do not wait for status",()=>{
  const p=panel(),device=p.data.status.coverage.robots[0];
  device.active=false;device.paused_sensors=[];p.data.status.coverage.current=0;
  assert.equal(renderCoverage(p),"");
  p.data.config.robots.bot.enabled=false;p.data.status.coverage.robots=[];
  assert.match(renderRobotSettings(p),/Ausnahme deaktiviert/);assert.doesNotMatch(renderRobotSettings(p),/Status wird ermittelt/);
});
test("status updates patch labels without replacing an unfinished robot editor",()=>{
  const p=panel(),node={dataset:{robotStatus:"bot"},textContent:""};
  p.shadowRoot={querySelectorAll:()=>[node]};
  updateRobotStatuses(p);assert.match(node.textContent,/Aktiv/);
  p.data.status.coverage.robots[0].active=false;p.data.status.coverage.robots[0].waiting=true;
  updateRobotStatuses(p);assert.match(node.textContent,/Nachlauf/);
});
test("ignored windows reuse the coverage notice without adding configuration controls",()=>{
  const p=panel();p.data.status.coverage.robots=[];
  p.data.status.coverage.ignored_windows=[{entity_id:"window",name:"Küche <Rechts>"}];
  const html=renderCoverage(p);
  assert.match(html,/1 Fenster ignoriert/);assert.match(html,/Küche &lt;Rechts&gt;/);
  assert.match(html,/auch nach dem Schließen/);assert.doesNotMatch(html,/button|input|select/);
  p.data.status.profile_id=null;assert.equal(renderCoverage(p),"");
});
