"use strict";

const byId = (id) => document.getElementById(id);
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function facts(list, entries) {
  list.replaceChildren();
  for (const [name, value] of entries) {
    list.append(element("dt", name), element("dd", String(value)));
  }
}

/** A read-only view of one native response; never reads or writes annotations. */
export function createEvidenceInspector() {
  let selection = null;
  let generation = 0;
  let pending = false;
  let blocked = false;
  let responseBytes = null;
  let controller = null;
  const inspect = byId("inspect-evidence");
  const download = byId("download-evidence");

  function controls() {
    inspect.disabled = blocked || pending || !selection?.worksheet.source_evidence;
    download.disabled = blocked || pending || responseBytes === null;
  }
  function clear() {
    responseBytes = null;
    byId("source-record-result").hidden = true;
    byId("source-record-list").replaceChildren();
    byId("source-record-status").textContent = "";
    byId("source-record-error").hidden = true;
  }
  function selected(row, worksheet) {
    // Re-rendering the same selected row (for example resetting its note) does
    // not discard a checked result. Moving to another row always does.
    const key = worksheet.snapshot + ":" + row.row_id;
    if (selection?.key === key) return;
    controller?.abort();
    controller = null;
    generation += 1;
    pending = false;
    selection = {key, row, worksheet};
    clear();
    byId("source-record-help").textContent = worksheet.source_evidence ?
      "Inspect the actual CSV records for this saved finding using the connected export and report." :
      "To inspect records, restart this desk with the matching --data export and --report summary.json.";
    controls();
  }

  function render(document) {
    const finding = document.finding;
    byId("source-record-summary").textContent = document.records.length +
      (document.records.length === 1 ? " cited record" : " cited records") +
      " · " + finding.account_no + " · " + finding.finding_key + " · " + finding.code;
    const list = byId("source-record-list");
    list.replaceChildren();
    for (const record of document.records) {
      const article = element("article", undefined, "source-record");
      article.dataset.pointer = record.pointer;
      article.append(element("h4", record.pointer));
      article.append(element("p", "CSV record ending on physical line " + record.record_end_line, "muted"));
      const values = element("dl", undefined, "identity source-record-fields");
      facts(values, record.columns.map(column => [column, record.fields[column]]));
      article.append(values);
      list.append(article);
    }
    facts(byId("source-record-provenance"), [
      ["Report date", document.review.as_of], ["Review window starts", document.review.eval_from],
      ["Data mode", document.review.data_mode], ["Finding ID", finding.finding_id],
      ["Evidence version", finding.evidence_version],
      ["Report SHA-256", document.source.report.sha256],
      ["Checker SHA-256", document.source.engine_sha256],
      ...document.source.inputs.map(input => [
        input.file, input.present ? input.bytes + " bytes · SHA-256 " + input.sha256 : "Not present",
      ]),
    ]);
    byId("source-record-result").hidden = false;
  }

  inspect.addEventListener("click", async () => {
    if (inspect.disabled || !selection) return;
    const admitted = selection;
    const requestGeneration = ++generation;
    controller?.abort();
    controller = new AbortController();
    pending = true;
    clear();
    byId("source-record-status").textContent = "Checking the connected source records…";
    controls();
    try {
      const response = await fetch("/api/evidence", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Review-Token": admitted.worksheet.token},
        body: JSON.stringify({snapshot: admitted.worksheet.snapshot, row_id: admitted.row.row_id}),
        signal: controller.signal,
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "Source inspection was refused.");
      }
      const bytes = await response.arrayBuffer();
      const document = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(bytes));
      if (generation !== requestGeneration || selection?.key !== admitted.key) return;
      render(document);
      responseBytes = bytes;
      byId("source-record-status").textContent =
        "Source records matched this saved finding. These are the checked snapshot; inspect again to recheck.";
    } catch (error) {
      if (generation !== requestGeneration || selection?.key !== admitted.key) return;
      byId("source-record-status").textContent = "";
      byId("source-record-error").textContent = error.message + " Your in-page notes are unchanged.";
      byId("source-record-error").hidden = false;
    } finally {
      if (generation === requestGeneration) {
        pending = false;
        controller = null;
        controls();
      }
    }
  });

  download.addEventListener("click", () => {
    if (download.disabled || responseBytes === null) return;
    const blob = new Blob([responseBytes], {type: "application/json;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = element("a");
    link.href = url;
    link.download = "utility-source-evidence.json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  });

  controls();
  return {
    select: selected,
    setBusy(value) { blocked = value; controls(); },
  };
}
