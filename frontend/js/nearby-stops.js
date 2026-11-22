/**
 * Nearby Bus Stand Finder Controller
 */

let map = null;
let userMarker = null;
let stopMarkers = [];
let userLat = 15.4989; // Default Panaji, Goa
let userLng = 73.8278;

async function initNearbyStops() {
  map = L.map('nearby-map').setView([userLat, userLng], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Attempt browser geolocation
  requestUserLocation();
}

function requestUserLocation() {
  const statusEl = document.getElementById('location-status');
  statusEl.innerText = 'Detecting current GPS coordinates...';

  if (!navigator.geolocation) {
    statusEl.innerText = 'Geolocation not supported. Showing central Goa stations.';
    fetchAndRenderStops(userLat, userLng);
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      userLat = pos.coords.latitude;
      userLng = pos.coords.longitude;
      statusEl.innerText = `Detected Location (${userLat.toFixed(4)}, ${userLng.toFixed(4)})`;
      renderUserLocationPin();
      fetchAndRenderStops(userLat, userLng);
    },
    (err) => {
      console.warn('Geolocation denied or timed out:', err);
      statusEl.innerHTML = `
        <span style="color:var(--warning);">Location permission denied or unavailable.</span> Showing stations around Panaji Central.
      `;
      renderUserLocationPin();
      fetchAndRenderStops(userLat, userLng);
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}

function renderUserLocationPin() {
  if (userMarker) userMarker.remove();

  const userIcon = L.divIcon({
    html: `
      <div style="background:#ef4444;color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 12px #ef4444;border:2px solid #fff;font-size:14px;">
        📍
      </div>
    `,
    className: 'user-pin-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });

  userMarker = L.marker([userLat, userLng], { icon: userIcon }).addTo(map).bindPopup('<strong>Your Location</strong>');
  map.setView([userLat, userLng], 12);
}

async function fetchAndRenderStops(lat, lng) {
  const container = document.getElementById('stops-cards-list');
  container.innerHTML = '<div style="text-align:center;padding:2rem;">Calculating proximity to registered bus stations...</div>';

  try {
    const stops = await apiRequest(`/tracking/nearby-stops?lat=${lat}&lng=${lng}&radius_km=75`);

    // Clear old stop markers
    stopMarkers.forEach(m => m.remove());
    stopMarkers = [];

    if (!stops || stops.length === 0) {
      container.innerHTML = '<div class="empty-state">No bus stations found within 75 km of this location.</div>';
      return;
    }

    container.innerHTML = stops.map((s, idx) => `
      <div class="card" style="padding:1.25rem;margin-bottom:1rem;background:var(--bg-secondary);cursor:pointer;border-left:4px solid ${idx === 0 ? 'var(--success)' : 'var(--border-color)'};" onclick="focusOnStop(${s.latitude}, ${s.longitude}, '${s.name}')">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:0.35rem;">
          <h4 style="font-size:1.05rem;font-weight:700;">${s.name}</h4>
          <span class="badge ${idx === 0 ? 'badge-live' : 'badge-primary'}">${s.distance_km} km away</span>
        </div>
        <div style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.75rem;">
          ${s.city}, ${s.state} &bull; ${s.landmark || 'Bus Stop'}
        </div>
        <div style="display:flex;gap:0.75rem;">
          <a href="https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}" target="_blank" class="btn btn-outline btn-sm" onclick="event.stopPropagation()">
            🗺️ Directions
          </a>
          <button onclick="bookFromThisStop(${s.id}, '${s.city}'); event.stopPropagation();" class="btn btn-primary btn-sm">
            Book From Here &rarr;
          </button>
        </div>
      </div>
    `).join('');

    // Add pins to map
    stops.forEach(s => {
      const marker = L.marker([s.latitude, s.longitude]).addTo(map).bindPopup(`
        <strong>${s.name}</strong><br>
        ${s.city}, ${s.state}<br>
        Distance: ${s.distance_km} km<br>
        <a href="https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}" target="_blank" style="color:#60a5fa;">Get Directions &rarr;</a>
      `);
      stopMarkers.push(marker);
    });

  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

function focusOnStop(lat, lng, name) {
  map.setView([lat, lng], 14);
}

function bookFromThisStop(stopId, cityName) {
  window.location.href = `/pages/passenger.html?origin=${encodeURIComponent(cityName)}&dest=Ratnagiri`;
}

document.addEventListener('DOMContentLoaded', () => {
  initNearbyStops();
});
