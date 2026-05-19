const statusEl = document.getElementById("status");

const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onopen = () => {
  statusEl.textContent = "Connected";
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  document.getElementById("angle").textContent = data.angle_deg.toFixed(2);
  document.getElementById("gyro").textContent = data.gyro_dps.toFixed(2);
  document.getElementById("left").textContent = data.motor_left;
  document.getElementById("right").textContent = data.motor_right;
  document.getElementById("battery").textContent = data.battery_v.toFixed(2);
  document.getElementById("mode").textContent = data.mode;
};

ws.onclose = () => {
  statusEl.textContent = "Disconnected";
};