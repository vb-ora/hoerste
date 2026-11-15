// Live-Tonhöhenerkennung im Browser mit pitchy (McLeod-Methode).
// Es wird kein Audio an den Server geschickt.

import { PitchDetector } from "../vendor/pitchy/pitchy.js";
import { holeKontext } from "../audio/engine.js";

const FENSTER = 2048;
const MIN_KLARHEIT = 0.9;
const MIN_HZ = 60;
const MAX_HZ = 1200;
const MEDIAN_LAENGE = 5;

function median(werte) {
  const s = [...werte].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export class Tonerkennung {
  constructor(rueckruf) {
    this.rueckruf = rueckruf; // ({hz, rohHz, klarheit, rms, gueltig, zeit})
    this.schwelleRms = 0.01;
    this.stream = null;
    this.quelle = null;
    this.analyser = null;
    this.puffer = new Float32Array(FENSTER);
    this.detektor = PitchDetector.forFloat32Array(FENSTER);
    this.letzte = [];
    this.laeuft = false;
    this._schritt = this._schritt.bind(this);
  }

  async starte() {
    const ctx = await holeKontext();
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    this.quelle = ctx.createMediaStreamSource(this.stream);
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = FENSTER;
    this.quelle.connect(this.analyser); // nicht an destination: keine Rückkopplung
    this.ctx = ctx;
    this.letzte = [];
    this.laeuft = true;
    requestAnimationFrame(this._schritt);
    const spur = this.stream.getAudioTracks()[0];
    return spur && spur.getSettings ? spur.getSettings() : {};
  }

  stoppe() {
    this.laeuft = false;
    if (this.quelle) this.quelle.disconnect();
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = this.quelle = this.analyser = null;
  }

  _schritt() {
    if (!this.laeuft) return;
    this.analyser.getFloatTimeDomainData(this.puffer);

    let summe = 0;
    for (let i = 0; i < this.puffer.length; i++) summe += this.puffer[i] * this.puffer[i];
    const rms = Math.sqrt(summe / this.puffer.length);

    const [rohHz, klarheit] = this.detektor.findPitch(this.puffer, this.ctx.sampleRate);
    const gueltig =
      rms >= this.schwelleRms && klarheit >= MIN_KLARHEIT && rohHz >= MIN_HZ && rohHz <= MAX_HZ;

    let hz = null;
    if (gueltig) {
      this.letzte.push(rohHz);
      if (this.letzte.length > MEDIAN_LAENGE) this.letzte.shift();
      hz = median(this.letzte);
    } else {
      this.letzte = [];
    }

    this.rueckruf({ hz, rohHz, klarheit, rms, gueltig, zeit: this.ctx.currentTime });
    requestAnimationFrame(this._schritt);
  }
}
