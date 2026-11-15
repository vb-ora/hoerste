// Testseite /labor: Synth-Ton und Live-Tonhöhenerkennung.

import { holeKontext, kontextVorhanden, setzeLautstaerke, setzeAudioSitzung } from "./audio/engine.js";
import { spieleTon, spieleFolge } from "./audio/synth.js";
import { Tonerkennung } from "./pitch/erkennung.js";

const $ = (id) => document.getElementById(id);

// Vorläufige Anzeige (H-System, Silben). Die richtige notation.js kommt in Etappe 2.
const NAMEN = ["C", "Cis/Des", "D", "Dis/Es", "E", "F", "Fis/Ges", "G", "Gis/As", "A", "Ais/B", "H"];

function hzZuMidi(hz) {
  return 69 + 12 * Math.log2(hz / 440);
}

function notenname(midi) {
  const n = ((midi % 12) + 12) % 12;
  const oktave = Math.floor(midi / 12) - 1;
  return NAMEN[n]
    .split("/")
    .map((t) => t + oktave)
    .join("/");
}

// ---- Diagnose ----
function ms(wert) {
  return wert != null ? (wert * 1000).toFixed(1) + " ms" : "nicht verfügbar";
}

function zeigeDiagnose() {
  $("d-browser").textContent = navigator.userAgent;
  const ctx = kontextVorhanden();
  if (!ctx) return;
  $("d-zustand").textContent = ctx.state;
  $("d-rate").textContent = ctx.sampleRate + " Hz";
  $("d-base").textContent = ms(ctx.baseLatency);
  $("d-output").textContent = ms(ctx.outputLatency);
}
zeigeDiagnose();

// ---- Mikrofon-Anzeige ----
const zeiger = $("cent-zeiger");
const PEGEL_MAX = 0.1;

function zeigeMessung({ hz, klarheit, rms }) {
  $("pegel").style.width = Math.min(100, (rms / PEGEL_MAX) * 100) + "%";
  $("klarheit").textContent = klarheit.toFixed(2);
  if (hz == null) {
    zeiger.classList.remove("sichtbar", "gut", "daneben");
    return;
  }
  const exakt = hzZuMidi(hz);
  const midi = Math.round(exakt);
  const cent = Math.round((exakt - midi) * 100);
  $("note").textContent = notenname(midi);
  $("frequenz").textContent = hz.toFixed(1);
  $("cent").textContent = (cent > 0 ? "+" : "") + cent;
  zeiger.style.left = 50 + cent + "%";
  zeiger.classList.add("sichtbar");
  zeiger.classList.toggle("gut", Math.abs(cent) <= 15);
  zeiger.classList.toggle("daneben", Math.abs(cent) > 15);
}

const erkennung = new Tonerkennung(zeigeMessung);

// ---- Klang ----
$("tasten").addEventListener("pointerdown", async (e) => {
  const t = e.target.closest(".taste");
  if (!t) return;
  t.classList.add("aktiv");
  setTimeout(() => t.classList.remove("aktiv"), 180);
  if (!erkennung.laeuft) setzeAudioSitzung("playback");
  if (t.dataset.midi) await spieleTon(Number(t.dataset.midi), 1.0);
  else if (t.dataset.akkord) await spieleTon(t.dataset.akkord.split(",").map(Number), 1.6);
  else if (t.dataset.folge) await spieleFolge(t.dataset.folge.split(",").map(Number));
  zeigeDiagnose();
});

$("lautstaerke").addEventListener("input", (e) => setzeLautstaerke(Number(e.target.value)));

// ---- Mikrofon ----
function setzeSchwelle(wert) {
  erkennung.schwelleRms = wert;
  $("schwelle-wert").textContent = wert.toFixed(3);
  $("pegel-schwelle").style.left = Math.min(100, (wert / PEGEL_MAX) * 100) + "%";
}
setzeSchwelle(Number($("schwelle").value));
$("schwelle").addEventListener("input", (e) => setzeSchwelle(Number(e.target.value)));

$("mikro-knopf").addEventListener("click", async () => {
  const knopf = $("mikro-knopf");
  const fehler = $("mikro-fehler");
  fehler.hidden = true;

  if (erkennung.laeuft) {
    erkennung.stoppe();
    setzeAudioSitzung("playback");
    knopf.textContent = "Mikrofon an";
    knopf.classList.remove("an");
    zeigeMessung({ hz: null, klarheit: 0, rms: 0 });
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    fehler.textContent = "Kein Mikrofonzugriff möglich. Die Seite braucht HTTPS (oder localhost).";
    fehler.hidden = false;
    return;
  }

  try {
    setzeAudioSitzung("play-and-record");
    await holeKontext();
    const einst = await erkennung.starte();
    knopf.textContent = "Mikrofon aus";
    knopf.classList.add("an");
    const w = (x) => (x === undefined ? "?" : String(x));
    $("d-mikro").textContent =
      "Echo " + w(einst.echoCancellation) +
      ", Rauschen " + w(einst.noiseSuppression) +
      ", Pegelautomatik " + w(einst.autoGainControl) +
      ", Rate " + w(einst.sampleRate);
  } catch (err) {
    fehler.textContent = "Mikrofon konnte nicht gestartet werden: " + (err.message || err.name);
    fehler.hidden = false;
  }
  zeigeDiagnose();
});
