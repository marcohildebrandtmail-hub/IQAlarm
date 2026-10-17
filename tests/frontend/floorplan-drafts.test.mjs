import assert from "node:assert/strict";
import test from "node:test";
import {DraftJournal, emptyDraft} from "../../custom_components/iqalarm/frontend/floorplan-drafts.js";

function storage() {
  const entries=new Map();
  return {getItem:key=>entries.get(key) ?? null,setItem:(key,value)=>entries.set(key,value)};
}
const polygon=()=>({points:[[.1,.1],[.8,.1],[.8,.8],[.1,.8]],roomId:null,candidateId:"1",manual:false});

test("corrected geometry and undo history survive a browser-storage roundtrip",()=>{
  const saved=storage(), first=new DraftJournal("plan/image",saved), state=polygon();
  first.checkpoint(first.state);first.update(state);
  first.checkpoint(first.state);state.points[0][0]=.2;first.update(state);
  const restored=new DraftJournal("plan/image",saved);
  assert.deepEqual(restored.state,state);assert.equal(restored.dirty,true);assert.equal(restored.restored,true);
  assert.equal(restored.undo().points[0][0],.1);
  assert.equal(restored.redo().points[0][0],.2);
});

test("assigning a room preserves every corrected point and can be undone",()=>{
  const journal=new DraftJournal("plan",storage()), state=polygon();
  state.points.splice(1,1);journal.update(state);journal.checkpoint(journal.state);
  const assigned={...state,roomId:"living"};journal.update(assigned);
  assert.deepEqual(journal.state.points,state.points);
  assert.deepEqual(journal.undo(),state);
  assert.deepEqual(journal.redo(),assigned);
});

test("saved state remains recoverable and undo creates an unsaved revision",()=>{
  const journal=new DraftJournal("plan",storage());journal.update(polygon());
  journal.markSaved(journal.state);assert.equal(journal.dirty,false);
  journal.checkpoint(journal.state);const changed=polygon();changed.points[0][0]=.3;journal.update(changed);
  journal.markSaved(journal.state);assert.equal(journal.dirty,false);
  journal.undo();assert.equal(journal.dirty,true);assert.equal(journal.state.points[0][0],.1);
});

test("new image and other plan do not consume another plan's draft",()=>{
  const saved=storage(), a=new DraftJournal("user/eg/image1",saved);a.update(polygon());
  const b=new DraftJournal("user/og/image1",saved), replaced=new DraftJournal("user/eg/image2",saved);
  assert.deepEqual(b.state,emptyDraft());assert.deepEqual(replaced.state,emptyDraft());
  assert.deepEqual(new DraftJournal("user/eg/image1",saved).state,polygon());
});

test("geometry is copied rather than shared with callers",()=>{
  const journal=new DraftJournal("plan",storage()), state=polygon();journal.update(state);
  state.points[0][0]=.9;assert.equal(journal.state.points[0][0],.1);
});

test("failed browser persistence still preserves edits and undo in memory",()=>{
  const failed={getItem:()=>null,setItem:()=>{throw new Error("storage full");}};
  const journal=new DraftJournal("plan",failed);journal.checkpoint(journal.state);journal.update(polygon());
  assert.equal(journal.available,false);assert.deepEqual(journal.state,polygon());
  assert.deepEqual(journal.undo(),emptyDraft());assert.deepEqual(journal.redo(),polygon());
});

test("bounded history keeps the most recent edits",()=>{
  const journal=new DraftJournal("plan",storage());
  for(let i=0;i<80;i++){journal.checkpoint(journal.state);const state=polygon();state.points[0][0]=i/100;journal.update(state);}
  assert.equal(journal.history.length,40);
  for(let i=0;i<40;i++) assert.ok(journal.undo());
  assert.equal(journal.undo(),null);assert.equal(journal.future.length,40);
});

test("corrupt stored geometry is ignored without executing its content",()=>{
  for(const raw of ["invalid json",JSON.stringify({version:1,state:{...polygon(),points:[[NaN,0]]},baseline:emptyDraft()}),JSON.stringify({version:1,state:{...polygon(),points:[[2,0]]},baseline:emptyDraft()})]){
    const journal=new DraftJournal("plan",{getItem:()=>raw,setItem:()=>{}});
    assert.deepEqual(journal.state,emptyDraft());
  }
});

test("non-finite coordinates cannot enter an editable draft",()=>{
  const journal=new DraftJournal("plan",storage());
  for(const value of [NaN,Infinity,-.1,1.1]){
    assert.throws(()=>journal.update({...polygon(),points:[[value,0]]}),/Ungültiger/);
  }
});
