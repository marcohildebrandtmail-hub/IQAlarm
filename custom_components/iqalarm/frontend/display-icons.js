/* Presentation choices never change sensor roles or alarm conditions. */
export const MDI_ICON = /^mdi:[a-z0-9][a-z0-9-]{0,79}$/;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SENSOR_ICONS = {
  "mdi:motion-sensor":"Bewegung", "mdi:account-eye-outline":"Präsenz",
  "mdi:window-closed-variant":"Fenster", "mdi:door-closed":"Tür",
  "mdi:lock-outline":"Schloss", "mdi:fridge-outline":"Kühlschrank",
  "mdi:archive-outline":"Schublade", "mdi:wardrobe-outline":"Schrank",
  "mdi:garage-variant":"Garagentor", "mdi:cctv":"Kamera",
  "mdi:walk":"Außenbewegung", "mdi:smoke-detector-variant":"Rauchmelder",
  "mdi:gesture-tap-button":"Taster",
};
const ROOM_ICONS = {
  "mdi:floor-plan":"Grundriss", "mdi:sofa-outline":"Wohnzimmer",
  "mdi:television":"Fernsehzimmer", "mdi:stove":"Küche",
  "mdi:bed-outline":"Schlafzimmer", "mdi:desk":"Büro",
  "mdi:shower":"Bad", "mdi:toilet":"WC", "mdi:stairs":"Flur / Treppe",
  "mdi:garage-variant":"Garage", "mdi:washing-machine":"Hauswirtschaft",
  "mdi:flower-outline":"Terrasse", "mdi:tree-outline":"Garten",
};
export function sensorSymbol(sensor = {}) {
  if (MDI_ICON.test(sensor.icon || "")) return sensor.icon;
  if(sensor.sensor_kind==="light_switch")return "mdi:light-switch";
  const role = sensor.role || "";
  return `mdi:${role.startsWith("perimeter") ? "cctv" : role.startsWith("interior") ? "motion-sensor" : sensor.sensor_kind === "door_lock" || role === "lock_contact" ? "lock" : role === "smoke" ? "smoke-detector-variant" : role === "panic" ? "gesture-tap-button" : "window-closed-variant"}`;
}
export function roomSymbol(room = {}) {
  return MDI_ICON.test(room.icon || "") ? room.icon : "mdi:floor-plan";
}
export function symbolHTML(value) {
  return `<ha-icon icon="${esc(MDI_ICON.test(value || "") ? value : "mdi:help-circle-outline")}" aria-hidden="true"></ha-icon>`;
}
export function iconField(value, fallback, kind = "sensor") {
  const choices = kind === "room" ? ROOM_ICONS : SENSOR_ICONS;
  const current = MDI_ICON.test(value || "") ? value : "";
  return `<details class="wide display-icon-picker" data-display-icon data-fallback="${esc(fallback)}"><summary>${symbolHTML(current || fallback)} Symbol anpassen</summary><label class="field" style="margin-top:12px">Symbol<input name="display_icon" aria-label="Symbol" value="${esc(current)}" placeholder="Automatisch" maxlength="84" pattern="mdi:[a-z0-9][a-z0-9-]{0,79}"><small>Symbol auswählen oder eine eigene MDI-Kennung eingeben, z. B. mdi:fridge-outline. Leer: automatisch. Die Alarmrolle bleibt erhalten.</small></label><div class="icon-options" role="group" aria-label="Symbole" style="margin-top:12px"><button type="button" class="small" data-display-icon-choice="" aria-pressed="${!current}">${symbolHTML(fallback)}<span>Automatisch</span></button>${Object.entries(choices).map(([id,label]) => `<button type="button" class="small" data-display-icon-choice="${id}" aria-pressed="${current === id}">${symbolHTML(id)}<span>${esc(label)}</span></button>`).join("")}</div><div class="row" style="margin-top:12px"><ha-icon data-display-icon-preview icon="${esc(current || fallback)}"></ha-icon><small>Vorschau des gewählten Symbols</small></div></details>`;
}
export function bindIconFields(container) {
  for (const picker of container.querySelectorAll("[data-display-icon]")) {
    const input = picker.querySelector('input[name="display_icon"]');
    const update = () => {
      const value = input.value.trim();
      const icon = MDI_ICON.test(value) ? value : picker.dataset.fallback;
      picker.querySelector("[data-display-icon-preview]").setAttribute("icon", icon);
      picker.querySelector("summary ha-icon").setAttribute("icon", icon);
      for (const button of picker.querySelectorAll("[data-display-icon-choice]")) {
        const active = button.dataset.displayIconChoice === value;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      }
    };
    input.addEventListener("input", update);
    input.addEventListener("change", update);
    picker.addEventListener("click", event => {
      const button = event.target.closest("[data-display-icon-choice]");
      if (!button) return;
      input.value = button.dataset.displayIconChoice;
      update();
    });
    update();
  }
}
