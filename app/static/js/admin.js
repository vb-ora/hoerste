// Verwaltung: Einladungen und Konten.

import { sende } from "./api.js";

const $ = (id) => document.getElementById(id);

function zeigeLink(titel, text, link) {
  $("link-titel").textContent = titel;
  $("link-text").textContent = text;
  $("link-feld").value = link;
  $("link-karte").hidden = false;
  $("link-karte").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("link-kopieren").addEventListener("click", async () => {
  const feld = $("link-feld");
  try {
    await navigator.clipboard.writeText(feld.value);
  } catch (_) {
    feld.select();
    document.execCommand("copy");
  }
  $("link-kopieren").textContent = "Kopiert";
  setTimeout(() => ($("link-kopieren").textContent = "Kopieren"), 1500);
});

function fehler(knopf, text) {
  const feld = knopf.closest(".karte").querySelector(".meldung");
  if (feld) {
    feld.textContent = text;
    feld.classList.add("fehler");
    feld.hidden = false;
  } else {
    alert(text);
  }
}

document.addEventListener("click", async (e) => {
  const knopf = e.target.closest("[data-aktion]");
  if (!knopf) return;
  const id = knopf.dataset.id;
  knopf.disabled = true;
  try {
    switch (knopf.dataset.aktion) {
      case "einladen": {
        const a = await sende("/api/admin/einladungen");
        zeigeLink("Neuer Einladungslink", `Gültig für ${a.tage} Tage, einmal nutzbar.`, a.link);
        return;
      }
      case "passwort": {
        const a = await sende(`/api/admin/nutzer/${id}/passwort-link`);
        zeigeLink(`Passwort-Link für ${a.name}`,
          `Gültig für ${a.stunden} Stunden. Damit setzt ${a.name} selbst ein neues Passwort.`, a.link);
        return;
      }
      case "zurueckziehen":
        await sende(`/api/admin/einladungen/${id}/zurueckziehen`);
        break;
      case "deaktivieren":
        if (!confirm(`${knopf.dataset.name} deaktivieren? Das Konto wird sofort abgemeldet.`)) return;
        await sende(`/api/admin/nutzer/${id}/aktiv`, { aktiv: false });
        break;
      case "aktivieren":
        await sende(`/api/admin/nutzer/${id}/aktiv`, { aktiv: true });
        break;
      case "rolle":
        await sende(`/api/admin/nutzer/${id}/rolle`, { rolle: knopf.dataset.rolle });
        break;
    }
    window.location.reload();
  } catch (err) {
    fehler(knopf, err.message);
  } finally {
    knopf.disabled = false;
  }
});
