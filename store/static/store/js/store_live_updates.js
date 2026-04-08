(function () {
  if (window.__storeLiveUpdatesInit) return;
  window.__storeLiveUpdatesInit = true;

  function getRoot() {
    return document.querySelector("[data-live-root]");
  }

  function getTopics() {
    var root = getRoot();
    if (!root) return [];
    var raw = root.getAttribute("data-live-topics");
    if (!raw) return [];
    return raw.split(",").map(function (value) {
      return value.trim();
    }).filter(Boolean);
  }

  function shouldRefreshFor(messageTopics) {
    var topics = getTopics();
    if (!topics.length) return false;
    if (!Array.isArray(messageTopics)) return true;
    if (!messageTopics.length) return true;
    return messageTopics.some(function (topic) {
      return topics.indexOf(topic) !== -1;
    });
  }

  function shouldSkipRefresh() {
    var tag = "";
    if (document.activeElement) tag = document.activeElement.tagName;
    return ["INPUT", "TEXTAREA", "SELECT"].indexOf(tag) !== -1;
  }

  async function refreshRoot() {
    var currentRoot = getRoot();
    if (!currentRoot) return;
    if (shouldSkipRefresh()) return;

    try {
      var response = await fetch(window.location.href, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Cache-Control": "no-cache"
        },
        credentials: "same-origin"
      });
      if (!response.ok) return;

      var html = await response.text();
      var parser = new DOMParser();
      var doc = parser.parseFromString(html, "text/html");
      var incomingRoot = doc.querySelector("[data-live-root]");
      var mountedRoot = getRoot();
      if (!incomingRoot) return;
      if (!mountedRoot) return;

      var rootName = incomingRoot.getAttribute("data-live-root");
      if (!rootName) rootName = "";
      mountedRoot.replaceWith(incomingRoot);
      document.dispatchEvent(new CustomEvent("store:live-updated", {
        detail: { root: rootName }
      }));
    } catch (error) {
      console.error("Live update refresh failed.", error);
    }
  }

  var refreshTimer = null;
  function queueRefresh() {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(function () {
      refreshRoot();
    }, 250);
  }

  function connect() {
    if (!getRoot()) return;
    var protocol = "ws";
    if (window.location.protocol === "https:") protocol = "wss";
    var socket = new WebSocket(protocol + "://" + window.location.host + "/ws/live/");

    socket.addEventListener("message", function (event) {
      try {
        var rawPayload = event.data;
        if (!rawPayload) rawPayload = "{}";
        var payload = JSON.parse(rawPayload);
        if (!shouldRefreshFor(payload.topics)) return;
        queueRefresh();
      } catch (error) {
        console.error("Live update payload error.", error);
      }
    });

    socket.addEventListener("close", function () {
      window.setTimeout(connect, 1500);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", connect, { once: true });
  } else {
    connect();
  }
}());
