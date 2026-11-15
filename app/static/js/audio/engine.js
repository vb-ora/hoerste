// Gemeinsamer AudioContext für Klang und Mikrofon.
// Darf nur aus einer Nutzergeste heraus erzeugt oder fortgesetzt werden (iOS).

let kontext = null;
let master = null;
let lautstaerke = 0.6;

export function kontextVorhanden() {
  return kontext;
}

export async function holeKontext() {
  if (!kontext) {
    const AC = window.AudioContext || window.webkitAudioContext;
    kontext = new AC({ latencyHint: "interactive" });
    master = kontext.createGain();
    master.gain.value = lautstaerke;
    master.connect(kontext.destination);
  }
  if (kontext.state !== "running") {
    await kontext.resume();
  }
  return kontext;
}

export function masterAusgang() {
  return master;
}

export function setzeLautstaerke(wert) {
  lautstaerke = wert;
  if (master) {
    master.gain.setTargetAtTime(wert, kontext.currentTime, 0.02);
  }
}

// iOS 17+: Audio-Sitzung steuern (Stummschalter, Lautsprecher bei Mikrofon).
export function setzeAudioSitzung(typ) {
  if (navigator.audioSession) {
    try {
      navigator.audioSession.type = typ;
    } catch (_) {
      // nicht unterstützt
    }
  }
}

export function midiZuHz(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}
