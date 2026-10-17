import test from "node:test";
import assert from "node:assert/strict";
import {areaReference, buildGraphicZones, graphicViewBox, hasRoomReference, mergePolygons, randomId, resolveRoom, roomGroups, roomVisualCenter} from "../../custom_components/iqalarm/frontend/floorplan-rooms.js";
import {DraftJournal} from "../../custom_components/iqalarm/frontend/floorplan-drafts.js";

const areas = [{id: "kitchen", name: "Küche"}, {id: "living", name: "Wohnzimmer"}];
const makeId = () => "new_room";

test("Home Assistant areas appear without a separate IQAlarm import", () => {
  assert.deepEqual(roomGroups({}, areas), [{name: "Home-Assistant-Bereiche", items: [
    {id: areaReference("kitchen"), name: "Küche"}, {id: areaReference("living"), name: "Wohnzimmer"},
  ]}]);
});

test("linked areas appear only once and preserve existing room names", () => {
  const rooms = {lounge: {id: "lounge", name: "Mein Wohnzimmer", area_id: "living"}};
  const groups = roomGroups(rooms, areas);
  assert.deepEqual(groups[0].items, [{id: "lounge", name: "Mein Wohnzimmer"}]);
  assert.deepEqual(groups[1].items, [{id: areaReference("kitchen"), name: "Küche"}]);
  assert.equal(hasRoomReference(rooms, areas, "lounge"), true);
  assert.equal(hasRoomReference(rooms, areas, areaReference("kitchen")), true);
  assert.equal(hasRoomReference(rooms, areas, areaReference("removed")), false);
});

test("saving an area prepares only that linked room without mutating the configuration", () => {
  const rooms = {};
  assert.deepEqual(resolveRoom(rooms, areas, areaReference("kitchen"), "", makeId), {
    id: "new_room", room: {id: "new_room", name: "Küche", area_id: "kitchen", adjacent: [], home_enabled: false},
  });
  assert.deepEqual(rooms, {});
});

test("randomId and resolveRoom work on HTTP origins where crypto.randomUUID is unavailable", () => {
  const httpCrypto = {
    getRandomValues(bytes) {
      for (let i = 0; i < bytes.length; i += 1) bytes[i] = i + 1;
      return bytes;
    },
  };
  const generated = randomId(httpCrypto);
  assert.match(generated, /^[0-9a-f]{32}$/);
  assert.match(randomId({}), /^[0-9a-f]{32}$/);
  const created = resolveRoom({}, areas, areaReference("kitchen"), "", () => randomId(httpCrypto));
  assert.equal(created.id, generated);
  assert.equal(created.room.name, "Küche");
});

test("mergePolygons combines two wall-separated proposals into a single outer room polygon", () => {
  const topRoom = [[0.72, 0.36], [0.89, 0.36], [0.89, 0.51], [0.72, 0.51]];
  const bottomRoom = [[0.72, 0.53], [0.89, 0.53], [0.89, 0.85], [0.72, 0.85]];
  assert.deepEqual(mergePolygons(topRoom, bottomRoom), [
    [0.72, 0.36], [0.89, 0.36], [0.89, 0.85], [0.72, 0.85],
  ]);
});

test("roomVisualCenter, buildGraphicZones and graphicViewBox generate clean room graphics", () => {
  const lShape = [[0.1, 0.1], [0.6, 0.1], [0.6, 0.35], [0.35, 0.35], [0.35, 0.8], [0.1, 0.8]];
  const center = roomVisualCenter(lShape);
  assert.equal(center[0] > 0.1 && center[0] < 0.35, true);
  assert.equal(center[1] > 0.1 && center[1] < 0.8, true);

  const zones = buildGraphicZones({living: lShape}, {
    living: {id: "living", name: "Wohnzimmer"},
    office: {id: "office", name: "Büro"},
  });
  assert.deepEqual(zones.living, lShape);
  assert.equal(zones.office.length, 4);

  const box = graphicViewBox(zones, 1000, 800);
  assert.match(box.viewBox, /^\d+ \d+ \d+ \d+$/);
  assert.equal(box.scale >= 0.35 && box.scale <= 1, true);
});

test("another client importing the same area does not create a duplicate", () => {
  const room = {id: "existing", name: "Meine Küche", area_id: "kitchen", adjacent: ["hall"]};
  assert.deepEqual(resolveRoom({existing: room}, areas, areaReference("kitchen"), "", () => {throw new Error("No new ID expected");}), {id: "existing", room: null});
  assert.deepEqual(room.adjacent, ["hall"]);
});

test("identical room names do not silently link different rooms", () => {
  const rooms = {manual: {id: "manual", name: "Küche", area_id: null}};
  assert.equal(roomGroups(rooms, areas).flatMap(group => group.items).length, 3);
  assert.equal(resolveRoom(rooms, areas, areaReference("kitchen"), "", makeId).room.area_id, "kitchen");
});

test("missing, conflicting and removed choices fail without creating a room", () => {
  for (const [reference, name] of [["", ""], [areaReference("kitchen"), "Neuer Raum"], [areaReference("removed"), ""], ["removed", ""]]) {
    assert.throws(() => resolveRoom({}, areas, reference, name, () => {throw new Error("Unexpected creation");}), /Bitte|entfernt/);
  }
  assert.equal(resolveRoom({}, areas, "", "  Neuer Raum  ", makeId).room.name, "Neuer Raum");
});

test("a selected HA area and every edited point survive draft restoration and undo", () => {
  let raw;
  const journal = new DraftJournal("test", {getItem: () => raw, setItem: (_, value) => {raw = value;}});
  const initial = {points: [[.1,.2],[.7,.2],[.5,.8]], roomId: null, candidateId: "2", manual: false};
  journal.update(initial); journal.checkpoint(initial);
  journal.update({...initial, roomId: areaReference("kitchen")});
  const restored = new DraftJournal("test", {getItem: () => raw, setItem: (_, value) => {raw = value;}});
  assert.equal(restored.state.roomId, areaReference("kitchen"));
  assert.deepEqual(restored.state.points, initial.points);
  assert.deepEqual(restored.undo(), initial);
  assert.equal(restored.redo().roomId, areaReference("kitchen"));
});
