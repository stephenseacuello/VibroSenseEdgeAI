// Shared client: owns the SocketIO connection and small pub/subs for `state` and `alarm`.
// Pages do: `VibroSense.onState(fn)` / `VibroSense.onAlarm(fn)` to subscribe.
(function () {
  const stateListeners = new Set();
  const alarmListeners = new Set();

  const conn      = document.getElementById("conn");
  const connLabel = document.getElementById("conn-label");

  function setConn(state) {
    if (!conn) return;
    conn.classList.remove("connected", "disconnected");
    conn.classList.add(state);
    if (connLabel) {
      connLabel.textContent =
        state === "connected" ? "live" : state === "disconnected" ? "offline" : "connecting…";
    }
  }

  function broadcast(set, payload) {
    for (const fn of set) {
      try { fn(payload); } catch (e) { console.error(e); }
    }
  }

  const socket = io({ transports: ["websocket", "polling"] });

  socket.on("connect",       () => setConn("connected"));
  socket.on("disconnect",    () => setConn("disconnected"));
  socket.on("connect_error", () => setConn("disconnected"));

  socket.on("state", (p) => broadcast(stateListeners, p));
  socket.on("alarm", (p) => broadcast(alarmListeners, p));

  window.VibroSense = {
    socket,
    onState(fn) { stateListeners.add(fn); return () => stateListeners.delete(fn); },
    onAlarm(fn) { alarmListeners.add(fn); return () => alarmListeners.delete(fn); },
  };
})();
