/**
 * Live Real-Time Bus Tracker Controller
 */

let map = null;
let busMarker = null;
let routeLine = null;
let stopMarkers = [];
let tripId = null;
let ws = null;

async function initLiveTracker() {
  const urlParams = new URLSearchParams(window.location.search);
  tripId = urlParams.get('trip_id');

  if (!tripId) {
    document.getElementById('tracking-card').innerHTML = `
      <div class="empty-state">
        <h4>No Trip Specified</h4>
        <p>Please provide a valid trip ID to track (e.g. <code>?trip_id=1</code>).</p>
        <a href="/pages/passenger.html" class="btn btn-primary btn-sm">Go to Passenger Portal</a>
      </div>
    `;
    return;
  }

  // Initialize Leaflet map
  map = L.map('live-map').setView([15.65, 73.80], 10);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Fetch initial trip and route snapshot
  await fetchLiveSnapshot();

  // Connect WebSocket for streaming updates
  connectTrackingWebSocket();

  // Refresh snapshot periodically (fallback every 10s)
  setInterval(fetchLiveSnapshot, 10000);
}

async function fetchLiveSnapshot() {
  try {
    const data = await apiRequest(`/tracking/live/${tripId}`);
    updateTrackerUI(data);
  } catch (err) {
    console.warn('Error fetching live snapshot:', err);
  }
}

function updateTrackerUI(data) {
  document.getElementById('trip-title').innerText = `${data.bus_name} (${data.registration_number})`;
  document.getElementById('route-name').innerText = data.route_name;
  document.getElementById('driver-name').innerText = data.driver_name || 'Assigned Driver';
  
  const statusBadge = document.getElementById('status-badge');
  statusBadge.className = `badge ${data.status === 'LIVE' ? 'badge-live' : (data.status === 'DELAYED' ? 'badge-delayed' : 'badge-unavailable')}`;
  statusBadge.innerText = data.status;

  document.getElementById('speed-display').innerText = `${Math.round(data.speed_kmh || 0)} km/h`;
  document.getElementById('next-stop-display').innerText = data.next_stop_name || 'Approaching Next Station';
  
  const lastUpdatedText = data.seconds_since_update !== null 
    ? `${data.seconds_since_update}s ago` 
    : 'Waiting for signal';
  document.getElementById('last-ping-display').innerText = lastUpdatedText;

  // Render Route and Stops on Map
  if (data.stops && data.stops.length > 0 && !routeLine) {
    const latLngs = data.stops.map(s => [s.latitude, s.longitude]);
    routeLine = L.polyline(latLngs, { color: '#3b82f6', weight: 5, opacity: 0.8 }).addTo(map);

    // Stop markers
    data.stops.forEach(s => {
      const marker = L.circleMarker([s.latitude, s.longitude], {
        radius: 7,
        fillColor: s.is_passed ? '#64748b' : '#10b981',
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(map).bindPopup(`<strong>#${s.stop_sequence}: ${s.name}</strong><br>${s.city}`);
      stopMarkers.push(marker);
    });

    map.fitBounds(routeLine.getBounds(), { padding: [50, 50] });
  }

  // Update Bus Marker Position
  if (data.current_latitude && data.current_longitude) {
    const busPos = [data.current_latitude, data.current_longitude];
    
    // Custom bus icon
    const busIcon = L.divIcon({
      html: `
        <div style="background:#2563eb;color:#fff;width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 15px #3b82f6;border:2px solid #fff;font-size:18px;">
          🚌
        </div>
      `,
      className: 'live-bus-marker',
      iconSize: [34, 34],
      iconAnchor: [17, 17]
    });

    if (!busMarker) {
      busMarker = L.marker(busPos, { icon: busIcon }).addTo(map);
    } else {
      busMarker.setLatLng(busPos);
    }

    busMarker.bindPopup(`
      <strong>${data.bus_name} (${data.registration_number})</strong><br>
      Status: ${data.status}<br>
      Speed: ${data.speed_kmh} km/h<br>
      Updated: ${lastUpdatedText}
    `);
  }
}

function connectTrackingWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/v1/tracking/ws/live/${tripId}`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'GPS_UPDATE' && payload.trip_id == tripId) {
          // Immediately update bus position
          if (busMarker && payload.latitude && payload.longitude) {
            busMarker.setLatLng([payload.latitude, payload.longitude]);
          }
          document.getElementById('speed-display').innerText = `${Math.round(payload.speed_kmh || 0)} km/h`;
          document.getElementById('last-ping-display').innerText = 'Just now';
          
          const statusBadge = document.getElementById('status-badge');
          statusBadge.className = 'badge badge-live';
          statusBadge.innerText = 'LIVE';
        }
      } catch (err) {
        console.warn('WS message parse error:', err);
      }
    };

    ws.onclose = () => {
      // Reconnect after 5s
      setTimeout(connectTrackingWebSocket, 5000);
    };

  } catch (err) {
    console.warn('WebSocket connection not supported or failed:', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initLiveTracker();
});
