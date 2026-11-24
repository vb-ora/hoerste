// Formulare mit data-api="/api/..." werden per fetch mit X-Hoerste-Kennung gesendet.
// Antwort mit "weiter" → Seitenwechsel, mit "meldung" → Text im Formular.

import { sende } from "./api.js";

function zeige(form, text, fehler) {
  const feld = form.querySelector(".meldung");
  if (!feld) return;
  feld.textContent = text;
  feld.classList.toggle("fehler", fehler);
  feld.classList.toggle("ok", !fehler);
  feld.hidden = !text;
}

function daten(form) {
  const zahlen = (form.dataset.zahlen || "").split(",").filter(Boolean);
  const ergebnis = {};
  for (const [name, wert] of new FormData(form)) {
    if (name.startsWith("_")) continue;
    ergebnis[name] = zahlen.includes(name) ? Number(wert) : wert;
  }
  return ergebnis;
}

for (const form of document.querySelectorAll("form[data-api]")) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const knopf = form.querySelector("button[type=submit]");
    if (knopf) knopf.disabled = true;
    zeige(form, "", false);
    try {
      const antwort = await sende(form.dataset.api, daten(form));
      if (antwort.weiter) {
        window.location.assign(antwort.weiter);
        return;
      }
      if ("leeren" in form.dataset) form.reset();
      zeige(form, antwort.meldung || "Gespeichert.", false);
    } catch (err) {
      zeige(form, err.message, true);
    } finally {
      if (knopf) knopf.disabled = false;
    }
  });
}

for (const knopf of document.querySelectorAll("[data-abmelden]")) {
  knopf.addEventListener("click", async () => {
    try {
      await sende("/api/logout");
    } finally {
      window.location.assign("/login");
    }
  });
}
