// Industrial SCADA HMI Live Client Script

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const clockEl = document.getElementById("clock-display");
  const modbusLed = document.getElementById("modbus-led");
  const modbusStatusText = document.getElementById("modbus-status-text");
  const fpsBadge = document.getElementById("fps-badge");
  const latencyBadge = document.getElementById("latency-badge");

  const totalEl = document.getElementById("metric-total");
  const passedEl = document.getElementById("metric-passed");
  const defectEl = document.getElementById("metric-defect");
  const rateEl = document.getElementById("metric-rate");
  const progressFill = document.getElementById("defect-progress");

  const rejectorLamp = document.getElementById("rejector-lamp");
  const conveyorLamp = document.getElementById("conveyor-lamp");
  const towerRed = document.getElementById("tower-red");
  const towerGreen = document.getElementById("tower-green");
  const logTbody = document.getElementById("log-tbody");

  const btnReject = document.getElementById("btn-test-reject");
  const btnToggleConveyor = document.getElementById("btn-toggle-conveyor");

  // Clock
  setInterval(() => {
    const d = new Date();
    clockEl.innerText = d.toTimeString().split(" ")[0] + "." + Math.floor(d.getMilliseconds() / 100);
  }, 100);

  // Button Listeners
  btnReject.addEventListener("click", async () => {
    try {
      await fetch("/api/modbus/reject", { method: "POST" });
    } catch (e) {
      console.error(e);
    }
  });

  btnToggleConveyor.addEventListener("click", async () => {
    try {
      await fetch("/api/modbus/toggle_conveyor", { method: "POST" });
    } catch (e) {
      console.error(e);
    }
  });

  // WebSocket Telemetry Client
  function connectWebSocket() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/telemetry`);

    ws.onopen = () => {
      modbusLed.classList.remove("offline");
      modbusStatusText.innerText = "MODBUS PLC: CONNECTED (PORT 5020)";
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        updateUI(data);
      } catch (err) {
        console.error("Telemetry parse error", err);
      }
    };

    ws.onclose = () => {
      modbusLed.classList.add("offline");
      modbusStatusText.innerText = "MODBUS PLC: RECONNECTING...";
      setTimeout(connectWebSocket, 1500);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function updateUI(data) {
    // Metrics
    totalEl.innerText = data.total_inspected || 0;
    passedEl.innerText = data.total_passed || 0;
    defectEl.innerText = data.total_defect || 0;
    rateEl.innerText = (data.defect_rate_pct || 0).toFixed(1) + "%";
    progressFill.style.width = Math.min(100, (data.defect_rate_pct || 0) * 2.5) + "%";

    // FPS & Latency
    fpsBadge.innerText = (data.fps || 0).toFixed(1) + " FPS";
    latencyBadge.innerText = (data.latency_ms || 0).toFixed(1) + " ms";

    // PLC Registers & Actuator Status
    if (data.plc_registers) {
      const plc = data.plc_registers;

      // Rejector Solenoid Lamp
      if (plc.rejector_active) {
        rejectorLamp.classList.add("active-red");
      } else {
        rejectorLamp.classList.remove("active-red");
      }

      // Conveyor Lamp
      if (plc.conveyor_running) {
        conveyorLamp.classList.add("active-green");
      } else {
        conveyorLamp.classList.remove("active-green");
      }

      // Tower Lamp
      if (plc.beacon_red) {
        towerRed.classList.add("active");
      } else {
        towerRed.classList.remove("active");
      }

      if (plc.beacon_green) {
        towerGreen.classList.add("active");
      } else {
        towerGreen.classList.remove("active");
      }
    }

    // Event Log Table
    if (data.events && data.events.length > 0) {
      logTbody.innerHTML = data.events.map((ev) => {
        const badgeClass = ev.result === "PASS" ? "tag-pass" : "tag-reject";
        return `
          <tr>
            <td>#${ev.id}</td>
            <td>${ev.timestamp}</td>
            <td><span class="${badgeClass}">${ev.result}</span></td>
            <td>${ev.defect_label}</td>
            <td>${Math.round(ev.confidence * 100)}%</td>
            <td>${ev.latency_ms.toFixed(1)} ms</td>
          </tr>
        `;
      }).join("");
    }
  }

  connectWebSocket();
});
