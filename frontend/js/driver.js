/**
 * Driver Dashboard & Smartphone GPS Streaming Controller
 */

let driverUser = null;
let assignedTrips = [];
let activeTrip = null;
let gpsWatchId = null;
let simulationInterval = null;
let simulationStep = 0;

async function loadAssignedTrips() {
  const container = document.getElementById('driver-trips-container');
  container.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Loading assigned trips...</div></div>';

  try {
    assignedTrips = await apiRequest('/driver/assigned-trips');
    if (!assignedTrips || assignedTrips.length === 0) {
      container.innerHTML = '<div class="empty-state">No trips currently assigned to your driver ID.</div>';
      return;
    }

    container.innerHTML = assignedTrips.map(t => {
      const isCurrentActive = activeTrip && activeTrip.id === t.id;
      return `
        <div class="card card-glass" style="margin-bottom:1.25rem;border-color:${isCurrentActive ? 'var(--primary)' : 'var(--border-color)'};">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;margin-bottom:1rem;">
            <div>
              <span class="badge ${t.status === 'IN_TRANSIT' ? 'badge-live' : (t.status === 'COMPLETED' ? 'badge-unavailable' : 'badge-primary')}">${t.status}</span>
              <strong style="font-size:1.15rem;margin-left:0.5rem;">${t.route_name}</strong>
              <span style="color:var(--text-muted);font-size:0.85rem;margin-left:0.5rem;">(${t.trip_code})</span>
            </div>
            <div>
              <span style="font-size:0.85rem;color:var(--text-secondary);">Bus: <strong>${t.bus_name} (${t.registration_number})</strong></span>
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;padding:0.75rem 1rem;background:var(--bg-input);border-radius:var(--radius-md);margin-bottom:1rem;">
            <div>
              <div style="font-size:0.8rem;color:var(--text-muted);">Scheduled Departure</div>
              <div style="font-weight:700;">${new Date(t.departure_datetime).toLocaleString()}</div>
            </div>
            <div>
              <div style="font-size:0.8rem;color:var(--text-muted);">Stops on Route</div>
              <div style="font-weight:700;">${t.stops.length} Stops</div>
            </div>
            <div>
              <div style="font-size:0.8rem;color:var(--text-muted);">GPS Status</div>
              <div><span class="badge ${t.gps_status === 'LIVE' ? 'badge-live' : 'badge-unavailable'}">${t.gps_status}</span></div>
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:0.85rem;color:var(--text-secondary);">
              Route Stops: ${t.stops.map(s => s.name.split(' ')[0]).join(' &rarr; ')}
            </div>
            <div style="display:flex;gap:0.75rem;">
              ${t.status !== 'COMPLETED' ? `
                <button onclick="selectTripForDriving(${t.id})" class="btn btn-primary btn-sm">
                  ${isCurrentActive ? '✓ Currently Selected' : 'Select Trip'}
                </button>
              ` : `
                <span class="badge badge-unavailable">Trip Finished</span>
              `}
            </div>
          </div>
        </div>
      `;
    }).join('');

    // If an in-transit trip exists, auto select it
    if (!activeTrip) {
      const inTransit = assignedTrips.find(t => t.status === 'IN_TRANSIT');
      if (inTransit) selectTripForDriving(inTransit.id);
    }

  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

function selectTripForDriving(tripId) {
  activeTrip = assignedTrips.find(t => t.id === tripId);
  if (!activeTrip) return;

  document.getElementById('active-trip-console').style.display = 'block';
  document.getElementById('console-trip-code').innerText = activeTrip.trip_code;
  document.getElementById('console-route-name').innerText = activeTrip.route_name;
  document.getElementById('console-bus-info').innerText = `${activeTrip.bus_name} (${activeTrip.registration_number})`;
  document.getElementById('console-trip-status').innerText = activeTrip.status;

  updateTrackingButtons();
  loadAssignedTrips(); // Refresh highlight
}

function updateTrackingButtons() {
  if (!activeTrip) return;

  const startBtn = document.getElementById('btn-start-trip');
  const endBtn = document.getElementById('btn-end-trip');
  const gpsToggle = document.getElementById('gps-streaming-controls');

  if (activeTrip.status === 'IN_TRANSIT') {
    startBtn.style.display = 'none';
    endBtn.style.display = 'inline-flex';
    gpsToggle.style.display = 'block';
  } else if (activeTrip.status === 'SCHEDULED' || activeTrip.status === 'BOARDING') {
    startBtn.style.display = 'inline-flex';
    endBtn.style.display = 'none';
    gpsToggle.style.display = 'none';
    stopGpsStreaming();
  } else {
    startBtn.style.display = 'none';
    endBtn.style.display = 'none';
    gpsToggle.style.display = 'none';
    stopGpsStreaming();
  }
}

async function handleStartTrip() {
  if (!activeTrip) return;

  try {
    const res = await apiRequest(`/driver/trips/${activeTrip.id}/start`, { method: 'POST' });
    activeTrip.status = res.status;
    showToast('Trip Started! GPS Location sharing authorized.', 'success');
    updateTrackingButtons();
    loadAssignedTrips();
    // Auto-prompt to start smartphone GPS
    startDeviceGps();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleEndTrip() {
  if (!activeTrip) return;
  if (!confirm('Are you sure you want to end this trip? Location sharing will stop.')) return;

  try {
    const res = await apiRequest(`/driver/trips/${activeTrip.id}/end`, { method: 'POST' });
    activeTrip.status = res.status;
    stopGpsStreaming();
    showToast('Trip Completed. Location sharing stopped.', 'info');
    updateTrackingButtons();
    loadAssignedTrips();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ----------------- SMARTPHONE GPS & SIMULATION ENGINE -----------------

function startDeviceGps() {
  if (!activeTrip || activeTrip.status !== 'IN_TRANSIT') {
    showToast('Trip must be active to stream GPS coordinates', 'error');
    return;
  }

  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser', 'error');
    return;
  }

  stopGpsStreaming(); // Reset any existing

  document.getElementById('gps-mode-badge').innerText = 'Device GPS (Active)';
  document.getElementById('gps-mode-badge').className = 'badge badge-live';

  gpsWatchId = navigator.geolocation.watchPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const speed = pos.coords.speed ? (pos.coords.speed * 3.6) : 48.0;
      const heading = pos.coords.heading || 0.0;
      await sendGpsUpdate(lat, lng, speed, heading, 'LIVE');
    },
    (err) => {
      console.warn('Geolocation watch error:', err);
      showToast(`GPS Error: ${err.message}. You can use "Simulate Highway Drive" for testing.`, 'warning');
      document.getElementById('gps-mode-badge').innerText = 'GPS Denied / Error';
      document.getElementById('gps-mode-badge').className = 'badge badge-unavailable';
    },
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 }
  );

  showToast('Device GPS tracking started', 'success');
}

function startSimulationMode() {
  if (!activeTrip || activeTrip.status !== 'IN_TRANSIT') {
    showToast('Trip must be active to stream coordinates', 'error');
    return;
  }

  stopGpsStreaming();

  document.getElementById('gps-mode-badge').innerText = 'Simulated Drive (Active)';
  document.getElementById('gps-mode-badge').className = 'badge badge-live';

  // Realistic coordinates along NH 66 route: Panaji -> Mapusa -> Pernem -> Sawantwadi -> Kankavli -> Ratnagiri
  const routePoints = [
    { lat: 15.4989, lng: 73.8278, speed: 30.0, heading: 10.0 }, // Panaji
    { lat: 15.5340, lng: 73.8200, speed: 52.0, heading: 12.0 },
    { lat: 15.5937, lng: 73.8143, speed: 45.0, heading: 15.0 }, // Mapusa
    { lat: 15.6500, lng: 73.8050, speed: 65.0, heading: 8.0 },
    { lat: 15.7175, lng: 73.7972, speed: 55.0, heading: 14.0 }, // Pernem
    { lat: 15.7830, lng: 73.8120, speed: 60.0, heading: 20.0 },
    { lat: 15.9056, lng: 73.8203, speed: 40.0, heading: 25.0 }, // Sawantwadi
    { lat: 16.0500, lng: 73.7800, speed: 68.0, heading: 350.0 },
    { lat: 16.2657, lng: 73.7089, speed: 50.0, heading: 345.0 }, // Kankavli
    { lat: 16.6000, lng: 73.5000, speed: 70.0, heading: 330.0 },
    { lat: 16.9902, lng: 73.3120, speed: 35.0, heading: 315.0 }  // Ratnagiri
  ];

  simulationStep = 0;

  // Send first coordinate immediately
  const pt = routePoints[simulationStep];
  sendGpsUpdate(pt.lat, pt.lng, pt.speed, pt.heading, 'LIVE');

  simulationInterval = setInterval(() => {
    simulationStep = (simulationStep + 1) % routePoints.length;
    const p = routePoints[simulationStep];
    sendGpsUpdate(p.lat, p.lng, p.speed, p.heading, 'LIVE');
  }, 4000); // update every 4 seconds

  showToast('Highway route simulation activated! Emitting real-time coordinates every 4s.', 'info');
}

function stopGpsStreaming() {
  if (gpsWatchId !== null) {
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
  }
  if (simulationInterval !== null) {
    clearInterval(simulationInterval);
    simulationInterval = null;
  }
  const badge = document.getElementById('gps-mode-badge');
  if (badge) {
    badge.innerText = 'GPS Off';
    badge.className = 'badge badge-unavailable';
  }
}

async function sendGpsUpdate(latitude, longitude, speed_kmh, heading_degrees, status) {
  if (!activeTrip) return;

  try {
    await apiRequest('/driver/location', {
      method: 'POST',
      body: JSON.stringify({
        trip_id: activeTrip.id,
        latitude,
        longitude,
        speed_kmh: Math.round(speed_kmh),
        heading_degrees: Math.round(heading_degrees),
        status
      })
    });

    document.getElementById('last-lat').innerText = latitude.toFixed(4);
    document.getElementById('last-lng').innerText = longitude.toFixed(4);
    document.getElementById('last-speed').innerText = `${Math.round(speed_kmh)} km/h`;
    document.getElementById('last-ping-time').innerText = new Date().toLocaleTimeString();

  } catch (err) {
    console.warn('GPS post failed:', err);
    // If forbidden because trip ended
    if (err.message && err.message.includes('Unauthorized')) {
      stopGpsStreaming();
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  driverUser = requireAuth(['DRIVER']);
  if (!driverUser) return;

  const nameEl = document.getElementById('driver-name');
  if (nameEl) nameEl.innerText = driverUser.full_name;

  loadAssignedTrips();
});
