/* Unsaved geometry stays independent of room assignment and server snapshots. */
const copy = value => structuredClone(value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const emptyDraft = () => ({points: [], roomId: null, candidateId: "", manual: false});

function valid(state) {
  return state && Array.isArray(state.points) && state.points.length <= 64 &&
    state.points.every(point => Array.isArray(point) && point.length === 2 && point.every(value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1)) &&
    (state.roomId === null || typeof state.roomId === "string") && typeof state.candidateId === "string" && typeof state.manual === "boolean";
}

export class DraftJournal {
  constructor(key, storage) {
    this.key = key; this.storage = storage; this.state = emptyDraft(); this.baseline = emptyDraft();
    this.history = []; this.future = []; this.available = true; this.restored = false;
    try {
      const raw = storage?.getItem(key);
      if (!raw || raw.length > 750000) return;
      const saved = JSON.parse(raw);
      if (saved.version !== 1 || !valid(saved.state) || !valid(saved.baseline)) return;
      this.state = copy(saved.state); this.baseline = copy(saved.baseline);
      this.history = Array.isArray(saved.history) ? saved.history.filter(valid).slice(-40) : [];
      this.future = Array.isArray(saved.future) ? saved.future.filter(valid).slice(-40) : [];
      this.restored = this.dirty;
    } catch { this.available = false; }
  }
  get dirty() { return !equal(this.state, this.baseline); }
  checkpoint(state) {
    if (!valid(state)) throw new Error("Ungültiger Grundrissentwurf");
    if (!this.history.length || !equal(this.history.at(-1), state)) this.history.push(copy(state));
    this.history = this.history.slice(-40); this.future = [];
  }
  update(state, persist = true) {
    if (!valid(state)) throw new Error("Ungültiger Grundrissentwurf");
    this.state = copy(state);
    if (persist) this.flush();
  }
  flush() {
    try {
      if (!this.storage) { this.available = false; return; }
      this.storage.setItem(this.key, JSON.stringify({version: 1, state: this.state, baseline: this.baseline, history: this.history, future: this.future}));
      this.available = true;
    } catch { this.available = false; }
  }
  undo() {
    if (!this.history.length) return null;
    this.future.push(copy(this.state));
    this.state = this.history.pop(); this.flush(); return copy(this.state);
  }
  redo() {
    if (!this.future.length) return null;
    this.history.push(copy(this.state));
    this.state = this.future.pop(); this.flush(); return copy(this.state);
  }
  markSaved(state) {
    if (!valid(state)) throw new Error("Ungültiger Grundrissentwurf");
    this.state = copy(state); this.baseline = copy(state); this.restored = false; this.flush();
  }
}
