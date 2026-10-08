"use strict";
import {createEvidenceInspector} from "/review_evidence.js";
(() => {
  const byId = (id) => document.getElementById(id);
  const labels = {open: "Open", in_progress: "In progress", reviewed: "Reviewed"};
  const fields = ["review_status", "reviewer", "note"];
  let worksheet = null;
  let current = [];
  let selectedId = null;
  let busy = false;
  let lastDownloaded = null;
  const drafts = new Map();
  const evidence = createEvidenceInspector();

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function values(row) {
    return drafts.get(row.row_id) || row;
  }
  function edited(row) {
    const draft = drafts.get(row.row_id);
    return Boolean(draft && fields.some((key) => draft[key] !== row[key]));
  }
  function changes() {
    return current.filter(edited).map((row) => ({row_id: row.row_id, ...drafts.get(row.row_id)}));
  }
  function fingerprint() {
    return JSON.stringify(changes());
  }
  function incomplete() {
    return current.filter((row) => {
      const value = values(row);
      return value.review_status.trim() !== "open" &&
        (!value.reviewer.trim() || !value.note.trim());
    });
  }
  function matches(row) {
    const value = values(row);
    const status = byId("status-filter").value;
    const query = byId("search").value.trim().toLocaleLowerCase();
    const text = [row.property, row.utility, row.account_no, row.finding_key,
      row.kind, row.code, row.detail, value.reviewer, value.note].join("\n").toLocaleLowerCase();
    return (!status || value.review_status.trim() === status) && (!query || text.includes(query));
  }
  function addFacts(list, entries) {
    list.replaceChildren();
    for (const [label, value] of entries) {
      list.append(element("dt", label), element("dd", String(value)));
    }
  }
  function updateCounts() {
    const counts = {open: 0, in_progress: 0, reviewed: 0};
    current.forEach((row) => { counts[values(row).review_status.trim()] += 1; });
    byId("counts").replaceChildren();
    for (const [label, count] of [["Current findings", current.length],
      ["Open", counts.open], ["In progress", counts.in_progress], ["Reviewed", counts.reviewed]]) {
      const card = element("div", undefined, "count");
      card.append(element("strong", String(count)), element("span", label));
      byId("counts").append(card);
    }
    const count = changes().length;
    byId("change-count").textContent = count ?
      count + (count === 1 ? " row edited in this page." : " rows edited in this page.") : "No in-page changes.";
    const invalid = incomplete();
    byId("validation").hidden = invalid.length === 0;
    byId("validation-text").textContent = invalid.length +
      (invalid.length === 1 ? " finding needs both a reviewer and a note." : " findings need both a reviewer and a note.");
    const row = current.find((item) => item.row_id === selectedId);
    byId("reset-row").disabled = busy || !row || !edited(row);
  }
  function renderList() {
    const visible = current.filter(matches);
    const list = byId("findings");
    list.replaceChildren();
    byId("match-count").textContent = visible.length + " of " + current.length + " current findings shown";
    for (const row of visible) {
      const value = values(row);
      const button = element("button", undefined, "finding");
      button.type = "button";
      button.dataset.rowId = row.row_id;
      button.setAttribute("aria-pressed", String(row.row_id === selectedId));
      button.append(element("strong", row.account_no + " · " + row.finding_key));
      button.append(element("small", row.property + " · " + row.utility));
      button.append(element("small", row.code));
      const badge = element("span", labels[value.review_status.trim()], "badge");
      badge.dataset.status = value.review_status.trim();
      button.append(badge);
      if (edited(row)) button.append(element("small", "Edited in this page"));
      button.disabled = busy;
      button.addEventListener("click", () => select(row.row_id, true));
      list.append(button);
    }
    if (!visible.length) {
      list.append(element("p", current.length ? "No matching findings. Clear the filters to see all records." :
        "No current findings in this worksheet.", "empty"));
    }
    const row = current.find((item) => item.row_id === selectedId);
    byId("selected-outside").hidden = !row || matches(row);
  }
  function select(id, focus = false) {
    const row = current.find((item) => item.row_id === id);
    if (!row) return;
    selectedId = id;
    evidence.select(row, worksheet);
    byId("empty-editor").hidden = true;
    byId("selected").hidden = false;
    byId("selected-property").textContent = row.property || "Recorded finding";
    byId("selected-title").textContent = row.code;
    addFacts(byId("selected-identity"), [
      ["Account", row.account_no], ["Bill / period", row.finding_key], ["Utility", row.utility],
      ["Kind", row.kind], ["Data mode", row.data_mode], ["Report date", row.as_of], ["Review window starts", row.eval_from],
    ]);
    byId("selected-detail").textContent = row.detail;
    addFacts(byId("selected-evidence"), [
      ["Source rows", row.evidence], ["Finding ID", row.finding_id],
      ["Evidence version", row.evidence_version], ["Row ID", row.row_id],
      ["Protected record", row.record_sha256],
    ]);
    const value = values(row);
    byId("review-status").value = value.review_status.trim();
    byId("reviewer").value = value.reviewer;
    byId("note").value = value.note;
    renderList();
    updateCounts();
    if (focus) {
      byId("reviewer").focus();
      byId("selected-title").scrollIntoView({block: "nearest"});
    }
  }
  function renderHistory() {
    const history = worksheet.rows.filter((row) => row.row_state !== "current");
    byId("history-title").textContent = "Historical findings · " + history.length;
    const list = byId("history-list");
    for (const row of history) {
      const article = element("article", undefined, "history-row");
      article.dataset.rowId = row.row_id;
      article.append(element("strong", row.row_state + " · " + row.account_no + " · " + row.finding_key + " · " + row.code));
      article.append(element("p", row.detail));
      article.append(element("p", labels[row.review_status.trim()] + " · " + (row.reviewer || "No reviewer")));
      article.append(element("p", row.note || "No note recorded."));
      const evidence = element("details");
      evidence.append(element("summary", "Historical evidence and identity"));
      const facts = element("dl", undefined, "identity evidence-values");
      addFacts(facts, [["Property", row.property], ["Utility", row.utility], ["Kind", row.kind],
        ["Data mode", row.data_mode], ["Report date", row.as_of],
        ["Review window starts", row.eval_from], ["Source rows", row.evidence],
        ["Finding ID", row.finding_id], ["Evidence version", row.evidence_version],
        ["Row ID", row.row_id], ["Protected record", row.record_sha256]]);
      evidence.append(facts);
      article.append(evidence);
      list.append(article);
    }
    if (!history.length) list.append(element("p", "No historical findings in this saved worksheet.", "muted"));
  }
  function updateField(key, value) {
    const row = current.find((item) => item.row_id === selectedId);
    if (!row || busy) return;
    const draft = {...Object.fromEntries(fields.map((field) => [field, values(row)[field]])), [key]: value};
    drafts.set(row.row_id, draft);
    byId("download-error").hidden = true;
    byId("download-status").textContent = "";
    renderList();
    updateCounts();
  }
  function setBusy(value) {
    busy = value;
    evidence.setBusy(value);
    byId("download").disabled = value;
    byId("annotation-fields").disabled = value;
    for (const id of ["search", "status-filter", "clear-filters", "show-invalid"]) byId(id).disabled = value;
    renderList();
    updateCounts();
  }

  byId("search").addEventListener("input", renderList);
  byId("status-filter").addEventListener("change", renderList);
  byId("clear-filters").addEventListener("click", () => {
    byId("search").value = "";
    byId("status-filter").value = "";
    renderList();
    byId("search").focus();
  });
  byId("review-status").addEventListener("change", (event) => updateField("review_status", event.target.value));
  byId("reviewer").addEventListener("input", (event) => updateField("reviewer", event.target.value));
  byId("note").addEventListener("input", (event) => updateField("note", event.target.value));
  byId("reset-row").addEventListener("click", () => {
    drafts.delete(selectedId);
    byId("download-status").textContent = "";
    byId("download-error").hidden = true;
    select(selectedId);
  });
  byId("show-invalid").addEventListener("click", () => {
    const row = incomplete()[0];
    if (row) select(row.row_id, true);
  });
  byId("download").addEventListener("click", async () => {
    if (!worksheet || busy) return;
    const invalid = incomplete();
    if (invalid.length) {
      select(invalid[0].row_id, true);
      byId("download-status").textContent = "Complete the highlighted review before downloading.";
      return;
    }
    setBusy(true);
    byId("download-error").hidden = true;
    byId("download-status").textContent = "Validating the complete worksheet…";
    const submitted = fingerprint();
    try {
      const response = await fetch("/api/download", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Review-Token": worksheet.token},
        body: JSON.stringify({snapshot: worksheet.snapshot, changes: changes()}),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Download refused.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = element("a");
      link.href = url;
      link.download = "utility-review-edited.csv";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      lastDownloaded = submitted;
      byId("download-status").textContent =
        "Download requested. Keep the CSV file before closing; the selected worksheet remains unchanged.";
    } catch (error) {
      byId("download-status").textContent = "";
      byId("download-error").textContent = error.message + " Your edits are still in this page.";
      byId("download-error").hidden = false;
    } finally {
      setBusy(false);
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (changes().length && fingerprint() !== lastDownloaded) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  fetch("/api/worksheet").then(async (response) => {
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Cannot open the selected worksheet.");
    worksheet = result;
    current = worksheet.rows.filter((row) => row.row_state === "current");
    const mode = worksheet.metadata.data_mode === "synthetic" ? "Synthetic data" : "Recorded CSV export";
    byId("source").textContent = worksheet.filename + " · " + mode +
      " · Report as of " + worksheet.metadata.as_of;
    byId("desk").hidden = false;
    renderHistory();
    renderList();
    updateCounts();
    if (current.length) select(current[0].row_id);
  }).catch((error) => {
    byId("source").textContent = "Worksheet unavailable";
    byId("load-error").textContent = error.message;
    byId("load-error").hidden = false;
  });
})();
