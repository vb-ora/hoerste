// Synth-Klang: Dreieck + Tiefpass + Hüllkurve.

import { holeKontext, masterAusgang, midiZuHz } from "./engine.js";

const ANSCHLAG = 0.012; // s
const ABKLINGEN = 0.25; // s bis zum Haltepegel
const HALTEPEGEL = 0.55;
const AUSKLANG = 0.25; // s

function stimme(ctx, ziel, midi, start, dauer, pegel) {
  const hz = midiZuHz(midi);
  const osz = ctx.createOscillator();
  osz.type = "triangle";
  osz.frequency.value = hz;

  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = Math.min(12000, 1800 + hz * 3);
  filter.Q.value = 0.7;

  const huelle = ctx.createGain();
  const g = huelle.gain;
  g.setValueAtTime(0, start);
  g.linearRampToValueAtTime(pegel, start + ANSCHLAG);
  g.setTargetAtTime(pegel * HALTEPEGEL, start + ANSCHLAG, ABKLINGEN / 3);
  const ende = start + Math.max(dauer, ANSCHLAG + 0.05);
  g.setTargetAtTime(0, ende, AUSKLANG / 4);

  osz.connect(filter).connect(huelle).connect(ziel);
  osz.start(start);
  osz.stop(ende + AUSKLANG * 2);
}

// Spielt einen oder mehrere Töne gleichzeitig.
export async function spieleTon(midis, dauer = 1.0) {
  const ctx = await holeKontext();
  const liste = Array.isArray(midis) ? midis : [midis];
  const pegel = 0.5 / Math.sqrt(liste.length);
  const start = ctx.currentTime + 0.005;
  for (const m of liste) stimme(ctx, masterAusgang(), m, start, dauer, pegel);
}

// Spielt Töne nacheinander.
export async function spieleFolge(midis, dauer = 0.5, abstand = 0.55) {
  const ctx = await holeKontext();
  const start = ctx.currentTime + 0.005;
  midis.forEach((m, i) => stimme(ctx, masterAusgang(), m, start + i * abstand, dauer, 0.5));
}
