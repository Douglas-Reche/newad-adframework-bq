/**
 * apps_script_trigger.js
 * ----------------------
 * Paste this code in the Cora Google Sheet:
 *   Extensions → Apps Script → paste → Save → set trigger
 *
 * It calls the GitHub Actions workflow_dispatch endpoint whenever
 * the spreadsheet is edited (or on a time-based trigger).
 *
 * SETUP (one-time):
 *   1. In Apps Script, go to Project Settings → Script Properties
 *   2. Add property:  GITHUB_TOKEN  = <your PAT with workflow scope>
 *      (GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained
 *       → select repo "newad-adframework-bq" → permission: Actions: Read & Write)
 *
 * HOW TO SET THE TRIGGER:
 *   Option A — on every edit:
 *     Triggers → + Add Trigger → onSheetEdit, From spreadsheet, On edit
 *
 *   Option B — daily at a fixed time (recommended to avoid spam):
 *     Triggers → + Add Trigger → triggerDailySync, Time-driven, Day timer, 7am-8am
 */

var GITHUB_OWNER    = "Douglas-Reche";
var GITHUB_REPO     = "newad-adframework-bq";
var WORKFLOW_FILE   = "cora_sheets_sync.yml";

function dispatchSync(reason) {
  var token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  if (!token) {
    Logger.log("ERROR: GITHUB_TOKEN not set in Script Properties.");
    return;
  }

  var url = "https://api.github.com/repos/" + GITHUB_OWNER + "/" + GITHUB_REPO +
            "/actions/workflows/" + WORKFLOW_FILE + "/dispatches";

  var payload = JSON.stringify({
    ref: "main",
    inputs: { reason: reason || "Triggered from Google Sheet" }
  });

  var options = {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    payload: payload,
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(url, options);
  Logger.log("GitHub Actions dispatch status: " + response.getResponseCode());
}

// Called on every spreadsheet edit (attach via Triggers UI)
function onSheetEdit(e) {
  // Debounce: only dispatch once per 5 minutes to avoid hammering the API
  var cache = CacheService.getScriptCache();
  if (cache.get("sync_lock")) {
    Logger.log("Sync already queued, skipping.");
    return;
  }
  cache.put("sync_lock", "1", 300); // lock for 5 minutes
  dispatchSync("Sheet edited by " + (e && e.user ? e.user.email : "unknown"));
}

// Called on daily time-based trigger (attach via Triggers UI)
function triggerDailySync() {
  dispatchSync("Scheduled daily sync");
}
