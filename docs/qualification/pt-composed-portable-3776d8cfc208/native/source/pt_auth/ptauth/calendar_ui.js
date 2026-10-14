/* Calendar handoff only. Existing rules and staff-state writers remain authoritative. */
(() => {
  "use strict";
  window.PTWorklistCalendar = {
    create(panel, asof) {
      const summary = panel.querySelector("[data-calendar-summary]");
      const contextText = panel.querySelector("[data-calendar-context]");
      const details = panel.querySelector("[data-calendar-details]");
      const list = panel.querySelector("[data-calendar-list]");
      const button = panel.querySelector("[data-calendar-download]");
      const status = panel.querySelector("[data-calendar-status]");
      let generation = 0, revision = 0, pendingLoad = true;
      let accepted = null, lastRows = [], current = null, request = null, url = null;

      function cancelDownload() {
        revision += 1;
        if (request) request.abort();
        request = null;
        if (url) URL.revokeObjectURL(url);
        url = null;
      }
      function unavailable(message) {
        cancelDownload();
        current = null;
        button.disabled = true;
        button.textContent = "Download calendar (.ics)";
        summary.textContent = "Calendar unavailable";
        contextText.textContent = "";
        list.replaceChildren();
        details.hidden = true;
        status.textContent = message;
      }
      function beginChange(message = "Loading the worklist…") {
        generation += 1;
        pendingLoad = true;
        accepted = null;
        unavailable(message);
        return generation;
      }
      function fail(ticket, message) {
        if (ticket !== generation) return;
        pendingLoad = false;
        accepted = null;
        unavailable(message + " Refresh the worklist before exporting.");
      }
      function dateOK(value) {
        if (typeof value !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)) return false;
        const [year, month, day] = value.split("-").map(Number);
        const days = [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28,
          31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
      }
      function update(source, rows, ticket) {
        unavailable("");
        if (ticket !== undefined) {
          if (ticket !== generation) {
            status.textContent = "An older worklist response arrived. Run worklist again before exporting.";
            return;
          }
          accepted = source;
          pendingLoad = false;
        }
        if (pendingLoad || !source || source !== accepted) {
          status.textContent = "Wait for a current worklist, then review its selection.";
          return;
        }
        lastRows = rows;
        if (asof.value !== source.as_of) {
          status.textContent = "The as-of date has changed. Run worklist to review that date before exporting.";
          return;
        }
        if (source.calendar_error || !/^[a-f0-9]{64}$/.test(source.calendar_snapshot || "")) {
          status.textContent = source.calendar_error || "Run worklist to obtain a validated calendar snapshot.";
          return;
        }
        if (!Array.isArray(rows) || new Set(rows.map(row => row.key)).size !== rows.length ||
            rows.some(row => !source.worklist.includes(row) ||
              (row.submit_by !== null && !dateOK(row.submit_by)) ||
              !["open", "submitted", "approved", "n/a"].includes((source.states[row.key] || {}).state || "open"))) {
          status.textContent = "This selection contains unsupported worklist fields. Refresh before exporting.";
          return;
        }
        const included = [], excluded = [];
        let undated = 0, completed = 0;
        for (const row of rows) {
          const state = (source.states[row.key] || {}).state || "open";
          const reasons = [];
          if (row.submit_by === null) { reasons.push("no recorded submit-by date"); undated += 1; }
          if (["approved", "n/a"].includes(state)) { reasons.push("staff state " + state); completed += 1; }
          if (reasons.length) excluded.push({row, state, reasons});
          else included.push({row, state});
        }
        summary.textContent = included.length + " all-day event(s) · " + excluded.length + " excluded item(s)";
        contextText.textContent = rows.length + " currently filtered item(s); report as of " + source.as_of +
          ". Clinic time zone: " + source.clinic_timezone + ". " + undated + " undated; " + completed +
          " approved/n/a (exclusion reasons can overlap).";
        const lines = included.map(({row, state}) => "Include · " + row.submit_by + " · " + row.patient_id +
          " · " + row.payer_name + " · " + (row.auth_no || "no auth") + " · " + row.clinic + " · " + state);
        lines.push(...excluded.map(({row, reasons}) => "Exclude · " + row.patient_id + " · " +
          (row.auth_no || "no auth") + " · " + reasons.join("; ")));
        for (const text of lines.slice(0, 200)) {
          const li = document.createElement("li");
          li.textContent = text;
          list.append(li);
        }
        if (lines.length > 200) {
          const li = document.createElement("li");
          li.textContent = "First 200 items shown here; the export uses the entire filtered selection.";
          list.append(li);
        }
        details.hidden = lines.length === 0;
        if (!included.length) {
          status.textContent = "No dated open/submitted items in this selection. No calendar will be created.";
          return;
        }
        current = {snapshot: source.calendar_snapshot, keys: rows.map(row => row.key), events: included.length};
        button.disabled = false;
        button.textContent = "Download " + included.length + " event(s) (.ics)";
        status.textContent = "Uses recorded submit-by dates only. Review these items before downloading.";
      }
      function inputChanged() {
        if (pendingLoad) {
          generation += 1;
          pendingLoad = false;
          accepted = null;
          unavailable("The as-of input changed during a refresh. Run worklist again before exporting.");
          return;
        }
        update(accepted, lastRows);
      }
      async function download() {
        if (!current || button.disabled) return;
        cancelDownload();
        const mine = revision, selection = current;
        const controller = new AbortController();
        request = controller;
        button.disabled = true;
        status.textContent = "Checking the reviewed report and staff state…";
        try {
          const response = await fetch("/api/calendar", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({snapshot: selection.snapshot, keys: selection.keys}),
            signal: controller.signal
          });
          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || "Calendar request failed");
          }
          if (!response.headers.get("Content-Type")?.startsWith("text/calendar")) {
            throw new Error("The server did not return a calendar");
          }
          const blob = await response.blob();
          if (mine !== revision || current !== selection || controller.signal.aborted) return;
          url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = "ptauth-submit-by.ics";
          document.body.append(anchor);
          anchor.click();
          anchor.remove();
          const downloadedURL = url;
          setTimeout(() => {
            URL.revokeObjectURL(downloadedURL);
            if (url === downloadedURL) url = null;
          }, 1000);
          status.textContent = "Downloaded " + selection.events +
            " all-day event(s). Review in your calendar app; later downloads do not remove prior imports.";
          button.disabled = false;
        } catch (error) {
          if (mine !== revision || controller.signal.aborted) return;
          unavailable(error.message + " Refresh the worklist before exporting.");
        } finally {
          if (request === controller) request = null;
        }
      }
      button.addEventListener("click", download);
      asof.addEventListener("input", inputChanged);
      return {beginChange, update, fail};
    }
  };
})();
