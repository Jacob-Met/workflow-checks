/* Explicit local batch downloads; existing review and per-load handlers remain authoritative. */
(() => {
  "use strict";
  const limit = 100;
  const hex = value => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  window.createFreightBatchHandoff = getReviewState => {
    const chosen = new Map();
    let panel, summary, active = null, message = "Choose the saved reviews to keep together.";
    const same = (a, b) => a?.load_id === b?.load_id &&
      a?.evidence_version === b?.evidence_version && a?.review_version === b?.review_version;
    const current = id => ({
      load_id: id, evidence_version: summary?.evidence_versions?.[id],
      review_version: summary?.review_versions?.[id],
    });
    const dirty = () => {
      const state = getReviewState();
      const note = document.querySelector("#note");
      return !!note && note.value !== (state.summary?.decisions?.[state.selected]?.note || "");
    };
    const blocked = () => getReviewState().busy || dirty();
    const availableRows = () => {
      const rows = Array.isArray(summary?.packets) ? summary.packets : [];
      const counts = new Map();
      rows.forEach(row => counts.set(row.load_id, (counts.get(row.load_id) || 0) + 1));
      return rows.map(row => ({id: row.load_id, valid: typeof row.load_id === "string" &&
        row.load_id.length > 0 && counts.get(row.load_id) === 1 &&
        hex(current(row.load_id).evidence_version) && hex(current(row.load_id).review_version)}));
    };
    const selection = () => availableRows().filter(row => chosen.has(row.id))
      .map(row => ({...chosen.get(row.id)}));
    const updateControls = () => {
      if (!panel) return;
      const busy = blocked();
      panel.querySelector("[data-batch-download]").disabled = !chosen.size || busy || !!active;
      panel.querySelector("[data-batch-cancel]").hidden = !active;
      panel.querySelector("[data-batch-clear]").disabled = !chosen.size;
      const available = availableRows().filter(row => row.valid);
      panel.querySelector("[data-batch-all]").disabled = !available.length || available.length > limit;
      panel.querySelector("[data-batch-count]").textContent = chosen.size + " selected";
      panel.querySelector("[data-batch-status]").textContent = dirty()
        ? "Save or undo the current note edits before downloading saved reviews."
        : getReviewState().busy ? "Wait for the current review or pipeline update to finish." : message;
      panel.querySelectorAll("input[data-batch-load]").forEach(input => {
        input.checked = chosen.has(input.dataset.batchLoad);
      });
    };
    const cancel = text => {
      active?.controller.abort();
      active = null;
      if (text) message = text;
      updateControls();
    };
    const changedSelection = () => cancel("Selection updated. The archive will include only these saved reviews.");

    const download = async () => {
      if (!chosen.size || blocked() || active) { updateControls(); return; }
      const loads = selection();
      const ticket = {controller: new AbortController()};
      active = ticket;
      message = "Preparing the selected saved reviews…";
      updateControls();
      const stillCurrent = () => {
        const now = selection();
        return active === ticket && !ticket.controller.signal.aborted && !blocked() &&
          now.length === loads.length && now.every((row, i) => same(row, loads[i]));
      };
      let objectUrl, link;
      try {
        const response = await fetch("/api/review-batch", {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({loads}), signal: ticket.controller.signal,
        });
        if (!response.ok) {
          const text = await response.text();
          let detail = text;
          try { detail = JSON.parse(text).error || text; } catch (_) {}
          throw new Error(detail || "The selected reviews could not be downloaded.");
        }
        const blob = await response.blob();
        if (!stillCurrent()) return;
        if (response.headers.get("Content-Type")?.split(";")[0] !== "application/zip") {
          throw new Error("The server did not return a batch review archive.");
        }
        const filename = /filename="([A-Za-z0-9_.-]+\.zip)"/.exec(
          response.headers.get("Content-Disposition") || "")?.[1];
        if (!filename) throw new Error("The batch archive has no download filename.");
        objectUrl = URL.createObjectURL(blob);
        link = document.createElement("a");
        link.href = objectUrl;
        link.download = filename;
        document.body.append(link);
        link.click();
        message = "Selected reviews downloaded. Unzip the file and open index.html.";
      } catch (error) {
        if (active === ticket) message = ticket.controller.signal.aborted
          ? "Batch download canceled. Saved reviews are unchanged."
          : error.message + " No batch was downloaded. Reload to inspect the current records before trying again.";
      } finally {
        link?.remove();
        if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        if (active === ticket) {
          active = null;
          updateControls();
        }
      }
    };

    document.addEventListener("input", event => {
      if (event.target.id === "note") {
        cancel(dirty() ? "Save or undo the current note edits before downloading saved reviews."
          : "The archive includes saved reviews only.");
      }
    });
    document.addEventListener("click", event => {
      if (event.target.closest("#run, #gen, button[data-d]")) {
        cancel("Review or pipeline update requested. The selected identities will be checked again.");
      }
    }, true);
    // Bubble after the existing target handler has set reviewBusy or disabled its button.
    document.addEventListener("click", event => {
      if (event.target.closest("#run, #gen, button[data-d]")) updateControls();
    });
    const observer = new MutationObserver(updateControls);
    ["run", "gen"].forEach(id => {
      const button = document.getElementById(id);
      if (button) observer.observe(button, {attributes: true, attributeFilter: ["disabled"]});
    });

    return {
      render(next, host) {
        summary = next;
        const rows = availableRows();
        const currentIds = new Set(rows.filter(row => row.valid).map(row => row.id));
        if ([...chosen].some(([id, old]) => !currentIds.has(id) || !same(old, current(id)))) {
          chosen.clear();
          cancel("Selection cleared because a selected packet or saved review changed. Inspect and select the current records again.");
        }
        if (!document.getElementById("freight-batch-style")) {
          const style = document.createElement("style");
          style.id = "freight-batch-style";
          style.textContent = "#freight-batch-panel{margin:1.2rem 0;padding:1rem;border:1px solid var(--line);background:white;border-radius:8px;min-width:0}" +
            "#freight-batch-panel legend{font-weight:700}#freight-batch-panel .batch-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));gap:.4rem}" +
            "#freight-batch-panel label{display:flex;align-items:flex-start;gap:.5rem;min-height:44px;padding:.55rem;border:1px solid var(--line);border-radius:6px;overflow-wrap:anywhere}" +
            "#freight-batch-panel label span{min-width:0}#freight-batch-panel input{margin:.25rem .15rem 0 0;flex:none}" +
            "#freight-batch-panel .batch-actions{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin:.8rem 0}" +
            "#freight-batch-panel button{min-height:44px;white-space:normal}#freight-batch-panel [role=status]{overflow-wrap:anywhere}";
          document.head.append(style);
        }
        panel = document.createElement("fieldset");
        panel.id = "freight-batch-panel";
        panel.innerHTML = '<legend>Download a group of saved reviews</legend>' +
          '<p>Choose up to 100 displayed loads. The archive keeps each original packet, saved review and history, with an index for the group. Unsaved notes are not included.</p>' +
          '<div class="batch-actions"><button type="button" data-batch-all>Select all available</button>' +
          '<button type="button" data-batch-clear>Clear selection</button><strong data-batch-count></strong></div>' +
          '<div class="batch-options"></div><div class="batch-actions">' +
          '<button type="button" class="pri" data-batch-download>Download selected reviews</button>' +
          '<button type="button" data-batch-cancel hidden>Cancel batch download</button></div>' +
          '<p data-batch-status role="status"></p><small>Draft snapshots only. Nothing is sent, invoiced or paid.</small>';
        const options = panel.querySelector(".batch-options");
        for (const row of rows) {
          const label = document.createElement("label");
          const input = document.createElement("input");
          input.type = "checkbox";
          input.dataset.batchLoad = row.id;
          input.disabled = !row.valid;
          const text = document.createElement("span");
          const review = summary?.decisions?.[row.id];
          const state = !row.valid ? "unavailable or ambiguous"
            : !review ? "not reviewed" : review.review_state === "current"
            ? "current saved review: " + review.decision : review.review_state + " saved review";
          text.textContent = row.id + " — " + state;
          input.addEventListener("change", () => {
            if (input.checked) {
              if (chosen.size >= limit) {
                input.checked = false;
                message = "Choose at most " + limit + " saved reviews.";
                updateControls();
                return;
              }
              chosen.set(row.id, current(row.id));
            } else chosen.delete(row.id);
            changedSelection();
          });
          label.append(input, text);
          options.append(label);
        }
        if (!rows.length) options.textContent = "No generated packets are available.";
        panel.querySelector("[data-batch-all]").onclick = () => {
          chosen.clear();
          rows.filter(row => row.valid).forEach(row => chosen.set(row.id, current(row.id)));
          changedSelection();
        };
        panel.querySelector("[data-batch-clear]").onclick = () => {
          chosen.clear();
          changedSelection();
        };
        panel.querySelector("[data-batch-download]").onclick = download;
        panel.querySelector("[data-batch-cancel]").onclick = () => cancel("Batch download canceled. Saved reviews are unchanged.");
        host.append(panel);
        updateControls();
      },
    };
  };
})();
