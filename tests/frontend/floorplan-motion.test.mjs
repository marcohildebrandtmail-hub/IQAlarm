import test from "node:test";
import assert from "node:assert/strict";

let Panel;
globalThis.HTMLElement = class {};
globalThis.customElements = {
  get() { return undefined; },
  define(name, value) { if (name === "iqalarm-panel") Panel = value; },
};
await import("../../custom_components/iqalarm/frontend/iqalarm-panel.js");

function setup({raw = false, last = 100, confirmed = false, visible = true, active = false} = {}) {
  const panel = Object.create(Panel.prototype);
  panel.data = {
    config: {
      rooms: {tv: {id: "tv", name: "Wohnzimmer TV"}}, windows: {},
      sensors: {"binary_sensor.motion": {entity_id: "binary_sensor.motion", role: "interior_motion", room_id: "tv"}},
      settings: {floorplan_disarmed_motion: visible},
    },
    information: [],
    status: {active, raw: {"binary_sensor.motion": raw}, last_active: {"binary_sensor.motion": last},
      rooms: {tv: {level: 2, confirmed, motion: raw === true ? ["binary_sensor.motion"] : [], open: [], persons: [], quarantined: []}}},
  };
  return panel;
}
const plan = {width: 100, height: 100, zones: {tv: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]}};

function display(panel, now) {
  const shared = panel._roomPresentation("tv", now);
  return {
    color: shared.color,
    shape: panel._zoneSVG(plan, "tv", plan.zones.tv, true, 1, shared),
    label: panel._zoneLabelSVG(plan, "tv", plan.zones.tv, true, 1, shared),
  };
}

for (const [now, motion] of [[100, true], [114.999, true], [115, false], [160, false]]) {
  test(`motion text and red room agree at ${now - 100} seconds despite level 2`, () => {
    const result = display(setup(), now);
    assert.equal(result.color, motion ? "#ef4444" : "#14b8a6");
    assert.equal(result.label.includes("Bewegung"), motion);
    assert.equal(result.label.includes("Ruhig"), false);
    assert.match(result.label, /Wohnzimmer TV/);
    assert.doesNotMatch(result.label, /Sensoren?/);
    assert.equal(result.shape.includes('fill="#ef4444"'), motion);
  });
}
test("still active motion remains visible after 15 seconds", () => {
  assert.equal(display(setup({raw: true}), 200).color, "#ef4444");
});
test("a completed contact pulse has no second visual hold interval",()=>{
  const panel=setup({raw:false,last:110});
  panel.data.config.sensors["binary_sensor.motion"].activation_mode="change";
  const result=display(panel,111);
  assert.equal(result.color,"#14b8a6");assert.doesNotMatch(result.label,/Bewegung/);
});
test("a new motion restarts the shared interval", () => {
  const panel = setup();
  assert.equal(display(panel, 115).color, "#14b8a6");
  panel.data.status.last_active["binary_sensor.motion"] = 116;
  assert.equal(display(panel, 130).color, "#ef4444");
  assert.equal(display(panel, 131).color, "#14b8a6");
});
test("unavailable or hidden motion does not retain a red room", () => {
  for (const panel of [setup({raw: null}), setup({visible: false})]) {
    const result = display(panel, 105);
    assert.equal(result.color, "#14b8a6");
    assert.equal(result.label.includes("Bewegung"), false);
  }
});
test("a confirmed alarm stays red with an explicit label after motion expires", () => {
  const result = display(setup({confirmed: true, active: true}), 200);
  assert.equal(result.color, "#ef4444");
  assert.match(result.label, /Bestätigter Alarm/);
  assert.equal(result.label.includes("Ruhig"), false);
});

test("observation hides the correlation caption while showing actual activity", () => {
  const result=display(setup({confirmed:true}),105);
  assert.doesNotMatch(result.label,/Bestätigte Korrelation/);
  assert.match(result.label,/Bewegung/);
});

function perimeter(camera, motion) {
  const panel=setup({last:0});
  panel.data.config.sensors["binary_sensor.person"]={entity_id:"binary_sensor.person",name:"Person",role:"perimeter_camera",front_of:["tv"]};
  panel.data.config.sensors["binary_sensor.outside_motion"]={entity_id:"binary_sensor.outside_motion",name:"Außenbewegung",role:"perimeter_sensor",room_id:"tv",camera_entity_id:"camera.roof"};
  Object.assign(panel.data.status.raw,{"binary_sensor.person":camera,"binary_sensor.outside_motion":motion});
  panel.data.status.rooms.tv.persons=["binary_sensor.person","binary_sensor.outside_motion"];
  return panel;
}

test("outdoor motion is never presented as a camera even with a linked camera",()=>{
  const result=display(perimeter(false,true),200);
  assert.match(result.label,/Bewegung erkannt/);
  assert.doesNotMatch(result.label,/Kamera aktiv|Person/);
  assert.equal(result.color,"#f59e0b");
});

test("camera detection and outdoor motion remain separate simultaneous reports",()=>{
  const result=display(perimeter(true,true),200);
  assert.match(result.label,/Person/);assert.match(result.label,/Bewegung erkannt/);
});

test("a person detection does not invent a motion sensor report",()=>{
  const result=display(perimeter(true,false),200);
  assert.match(result.label,/Person/);assert.doesNotMatch(result.label,/Bewegung erkannt/);
});

test("stale or unavailable perimeter states and isolated sensors do not appear active",()=>{
  const panel=perimeter(null,false);
  assert.equal(display(panel,200).color,"#14b8a6");
  panel.data.status.raw["binary_sensor.outside_motion"]=true;
  panel.data.config.sensors["binary_sensor.outside_motion"].enabled=false;
  assert.equal(display(panel,200).color,"#14b8a6");
});

test("outdoor display settings remain independent of interior motion",()=>{
  const panel=perimeter(false,true);
  panel.data.config.settings.floorplan_disarmed_motion=false;
  assert.match(display(panel,200).label,/Bewegung erkannt/);
  panel.data.config.settings.floorplan_disarmed_cameras=false;
  assert.doesNotMatch(display(panel,200).label,/Bewegung erkannt/);
  assert.equal(display(panel,200).color,"#14b8a6");
});
