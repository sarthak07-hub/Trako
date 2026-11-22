/**
 * Bus Operator Dashboard Controller
 */

let operatorUser = null;
let fleetMap = null;
let fleetMarkers = {};
let allStopsCache = [];

function switchOperatorTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.operator-tab-content').forEach(c => c.style.display = 'none');

  const btn = document.getElementById(`btn-tab-${tabId}`);
  const content = document.getElementById(`tab-${tabId}`);
  if (btn) btn.classList.add('active');
  if (content) content.style.display = 'block';

  if (tabId === 'overview') loadOverviewStats();
  else if (tabId === 'buses') loadBuses();
  else if (tabId === 'routes') loadRoutes();
  else if (tabId === 'trips') loadTrips();
  else if (tabId === 'bookings') loadBookings();
  else if (tabId === 'radar') initFleetRadar();
}

// ----------------- OVERVIEW STATS -----------------

async function loadOverviewStats() {
  try {
    const stats = await apiRequest('/operator/stats');
    document.getElementById('stat-buses').innerText = stats.total_buses;
    document.getElementById('stat-routes').innerText = stats.total_routes;
    document.getElementById('stat-today-trips').innerText = stats.today_trips;
    document.getElementById('stat-in-transit').innerText = stats.active_in_transit;
    document.getElementById('stat-bookings').innerText = stats.total_bookings;
    document.getElementById('stat-revenue').innerText = `₹${stats.total_revenue}`;
  } catch (err) {
    console.error('Error loading stats:', err);
  }
}

// ----------------- BUSES & SEAT QR GENERATOR -----------------

async function loadBuses() {
  const container = document.getElementById('buses-table-body');
  container.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading fleet...</td></tr>';

  try {
    const buses = await apiRequest('/operator/buses');
    if (!buses || buses.length === 0) {
      container.innerHTML = '<tr><td colspan="7" class="empty-state">No buses found. Add your first bus above.</td></tr>';
      return;
    }

    container.innerHTML = buses.map(b => `
      <tr>
        <td><strong>${b.bus_name}</strong></td>
        <td><code style="color:#60a5fa;">${b.registration_number}</code></td>
        <td>${b.bus_type}</td>
        <td>${b.seating_capacity} seats</td>
        <td>${b.layout_type}</td>
        <td><span class="badge ${b.is_active ? 'badge-live' : 'badge-unavailable'}">${b.is_active ? 'Active' : 'Inactive'}</span></td>
        <td style="display:flex;gap:0.5rem;">
          <button onclick="viewBusSeatsAndQR(${b.id})" class="btn btn-primary btn-sm">
            🔲 Seat QRs
          </button>
          <button onclick="deactivateBus(${b.id})" class="btn btn-danger btn-sm">
            Deactivate
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color:var(--danger);text-align:center;">${err.message}</td></tr>`;
  }
}

async function handleAddBus(e) {
  e.preventDefault();
  const registration_number = document.getElementById('bus-reg').value.trim();
  const bus_name = document.getElementById('bus-name').value.trim();
  const bus_type = document.getElementById('bus-type').value;
  const seating_capacity = parseInt(document.getElementById('bus-capacity').value, 10);
  const layout_type = document.getElementById('bus-layout').value;

  try {
    await apiRequest('/operator/buses', {
      method: 'POST',
      body: JSON.stringify({ registration_number, bus_name, bus_type, seating_capacity, layout_type })
    });
    showToast('Bus registered with seats initialized!', 'success');
    closeModal('add-bus-modal');
    loadBuses();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function viewBusSeatsAndQR(busId) {
  const modal = document.getElementById('bus-qr-modal');
  const body = document.getElementById('bus-qr-modal-body');
  modal.classList.add('active');
  body.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Generating physical seat QR codes...</div></div>';

  try {
    const data = await apiRequest(`/operator/buses/${busId}/seats`);

    body.innerHTML = `
      <div style="margin-bottom:1.5rem;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <h4 style="font-size:1.2rem;font-weight:800;">${data.bus_name} (${data.registration_number})</h4>
          <p style="color:var(--text-secondary);font-size:0.85rem;">Print and paste these QR codes on physical seats for walk-in passenger bookings.</p>
        </div>
        <button onclick="window.print()" class="btn btn-secondary btn-sm">🖨️ Print All QRs</button>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:1rem;max-height:60vh;overflow-y:auto;padding-right:0.5rem;">
        ${data.seats.map(s => `
          <div class="card" style="text-align:center;padding:1rem;background:var(--bg-secondary);">
            <div style="font-weight:800;font-size:1.15rem;color:var(--primary);margin-bottom:0.25rem;">
              Seat ${s.seat_number}
            </div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.75rem;">${s.seat_type} (${s.deck})</div>
            <div style="background:#ffffff;padding:0.5rem;border-radius:var(--radius-sm);display:inline-block;">
              <img src="${s.qr_code_image}" style="width:120px;height:120px;display:block;" alt="Seat QR">
            </div>
            <div style="margin-top:0.5rem;">
              <a href="${s.booking_url}" target="_blank" style="font-size:0.75rem;color:#60a5fa;">Test URL &rarr;</a>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

async function deactivateBus(busId) {
  if (!confirm('Are you sure you want to deactivate this bus?')) return;
  try {
    await apiRequest(`/operator/buses/${busId}`, { method: 'DELETE' });
    showToast('Bus deactivated', 'info');
    loadBuses();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ----------------- ROUTES & STOPS -----------------

async function loadRoutes() {
  const container = document.getElementById('routes-list-container');
  container.innerHTML = '<div style="text-align:center;padding:2rem;">Loading routes...</div>';

  try {
    const routes = await apiRequest('/operator/routes');
    if (!routes || routes.length === 0) {
      container.innerHTML = '<div class="empty-state">No routes created yet. Add a route above.</div>';
      return;
    }

    container.innerHTML = routes.map(r => `
      <div class="card card-glass" style="margin-bottom:1.25rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;margin-bottom:1rem;">
          <div>
            <span class="badge badge-primary">${r.route_code}</span>
            <strong style="font-size:1.15rem;margin-left:0.5rem;">${r.name}</strong>
          </div>
          <div style="font-size:0.85rem;color:var(--text-secondary);">
            Total Distance: <strong>${r.total_distance_km} km</strong> &bull; Est. Duration: <strong>${r.estimated_duration_minutes} mins</strong>
          </div>
        </div>

        <!-- Ordered Stops Sequence Display -->
        <div style="background:var(--bg-input);border-radius:var(--radius-md);padding:1rem;">
          <div style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:0.75rem;">
            Ordered Route Segments (${r.stops.length} stops)
          </div>
          <div style="display:flex;align-items:center;gap:0.5rem;overflow-x:auto;padding-bottom:0.5rem;">
            ${r.stops.map((s, idx) => `
              <div style="display:flex;align-items:center;gap:0.5rem;flex-shrink:0;">
                <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-sm);padding:0.4rem 0.75rem;font-size:0.85rem;">
                  <span style="color:var(--primary);font-weight:700;">#${s.sequence}</span>
                  <strong>${s.name}</strong> (${s.city})
                  <div style="font-size:0.75rem;color:var(--text-muted);">₹${s.fare} fare &bull; ${s.distance_km} km</div>
                </div>
                ${idx < r.stops.length - 1 ? '<span style="color:var(--text-muted);">&rarr;</span>' : ''}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

// ----------------- TRIPS & SCHEDULER -----------------

async function loadTrips() {
  const container = document.getElementById('trips-table-body');
  container.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading scheduled trips...</td></tr>';

  try {
    const trips = await apiRequest('/operator/trips');
    if (!trips || trips.length === 0) {
      container.innerHTML = '<tr><td colspan="7" class="empty-state">No dated trips found. Schedule a trip above.</td></tr>';
      return;
    }

    container.innerHTML = trips.map(t => `
      <tr>
        <td><strong>${t.trip_code}</strong></td>
        <td>${t.route_name}</td>
        <td>${t.bus_name} (<code style="color:#60a5fa;">${t.registration_number}</code>)</td>
        <td>${new Date(t.departure_datetime).toLocaleString()}</td>
        <td>
          <div style="font-size:0.85rem;">Driver: <strong>${t.driver_name}</strong></div>
          <div style="font-size:0.8rem;color:var(--text-muted);">Conductor: ${t.conductor_name}</div>
        </td>
        <td>
          <span class="badge ${t.status === 'IN_TRANSIT' ? 'badge-live' : (t.status === 'COMPLETED' ? 'badge-unavailable' : 'badge-primary')}">
            ${t.status}
          </span>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem;">${t.booked_seats_count} bookings</div>
        </td>
        <td>
          <a href="/pages/live-track.html?trip_id=${t.id}" target="_blank" class="btn btn-outline btn-sm">
            Live Radar
          </a>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color:var(--danger);text-align:center;">${err.message}</td></tr>`;
  }
}

async function openAddTripModal() {
  const modal = document.getElementById('add-trip-modal');
  modal.classList.add('active');

  // Populate routes, buses, and crew dropdowns
  const [routes, buses, crew] = await Promise.all([
    apiRequest('/operator/routes'),
    apiRequest('/operator/buses'),
    apiRequest('/operator/crew')
  ]);

  const routeSelect = document.getElementById('trip-route');
  routeSelect.innerHTML = routes.map(r => `<option value="${r.id}">${r.name} (${r.route_code})</option>`).join('');

  const busSelect = document.getElementById('trip-bus');
  busSelect.innerHTML = buses.map(b => `<option value="${b.id}">${b.bus_name} (${b.registration_number}) - ${b.seating_capacity} seats</option>`).join('');

  const driverSelect = document.getElementById('trip-driver');
  driverSelect.innerHTML = crew.drivers.map(d => `<option value="${d.id}">${d.name} (${d.phone})</option>`).join('');

  const conductorSelect = document.getElementById('trip-conductor');
  conductorSelect.innerHTML = crew.conductors.map(c => `<option value="${c.id}">${c.name} (${c.phone})</option>`).join('');

  const dateInput = document.getElementById('trip-date');
  dateInput.value = new Date().toISOString().split('T')[0];
}

async function handleCreateTrip(e) {
  e.preventDefault();
  const route_id = parseInt(document.getElementById('trip-route').value, 10);
  const bus_id = parseInt(document.getElementById('trip-bus').value, 10);
  const driver_id = parseInt(document.getElementById('trip-driver').value, 10);
  const conductor_id = parseInt(document.getElementById('trip-conductor').value, 10);
  const trip_date = document.getElementById('trip-date').value;
  const time = document.getElementById('trip-time').value;
  const base_fare = parseFloat(document.getElementById('trip-fare').value);

  const departure_datetime = `${trip_date}T${time}:00`;
  const arrival = new Date(new Date(departure_datetime).getTime() + 5 * 3600000).toISOString();

  try {
    await apiRequest('/operator/trips', {
      method: 'POST',
      body: JSON.stringify({
        route_id, bus_id, driver_id, conductor_id, trip_date,
        departure_datetime, expected_arrival_datetime: arrival, base_fare
      })
    });
    showToast('Trip scheduled successfully!', 'success');
    closeModal('add-trip-modal');
    loadTrips();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ----------------- OPERATOR BOOKINGS -----------------

async function loadBookings() {
  const container = document.getElementById('operator-bookings-table');
  container.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading passenger bookings...</td></tr>';

  try {
    const bookings = await apiRequest('/operator/bookings');
    if (!bookings || bookings.length === 0) {
      container.innerHTML = '<tr><td colspan="7" class="empty-state">No passenger reservations found yet.</td></tr>';
      return;
    }

    container.innerHTML = bookings.map(b => `
      <tr>
        <td><strong style="color:#60a5fa;">${b.booking_reference}</strong></td>
        <td>${b.trip_code}</td>
        <td>
          <strong>${b.passenger_name}</strong>
          <div style="font-size:0.75rem;color:var(--text-muted);">${b.passenger_phone}</div>
        </td>
        <td>Seat <strong>${b.seat_number}</strong></td>
        <td>${b.boarding_stop} &rarr; ${b.destination_stop}</td>
        <td>₹${b.fare_amount}</td>
        <td><span class="badge ${b.status === 'BOARDED' ? 'badge-live' : (b.status === 'CANCELLED' ? 'badge-unavailable' : 'badge-primary')}">${b.status}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color:var(--danger);">${err.message}</td></tr>`;
  }
}

// ----------------- FLEET RADAR MAP -----------------

async function initFleetRadar() {
  const mapElement = document.getElementById('fleet-map');
  if (!mapElement) return;

  if (!fleetMap) {
    // Default center at Panaji, Goa
    fleetMap = L.map('fleet-map').setView([15.65, 73.80], 9);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(fleetMap);
  }

  // Fetch live fleet coordinates
  try {
    const fleet = await apiRequest('/operator/fleet-radar');
    const listContainer = document.getElementById('fleet-cards-list');

    // Clear old markers
    Object.values(fleetMarkers).forEach(m => m.remove());
    fleetMarkers = {};

    if (!fleet || fleet.length === 0) {
      listContainer.innerHTML = '<div class="empty-state">No buses currently active in transit.</div>';
      return;
    }

    listContainer.innerHTML = fleet.map(f => `
      <div class="card" style="padding:1rem;margin-bottom:0.75rem;background:var(--bg-secondary);">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong>${f.bus_name} (${f.registration_number})</strong>
          <span class="badge ${f.gps_status === 'LIVE' ? 'badge-live' : 'badge-unavailable'}">${f.gps_status}</span>
        </div>
        <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:0.25rem;">
          Route: ${f.route_name} &bull; Driver: ${f.driver_name}
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.25rem;">
          Speed: ${f.speed_kmh} km/h &bull; Last update: ${f.seconds_since_update !== null ? `${f.seconds_since_update}s ago` : 'N/A'}
        </div>
      </div>
    `).join('');

    fleet.forEach(f => {
      if (f.latitude && f.longitude) {
        const marker = L.marker([f.latitude, f.longitude])
          .addTo(fleetMap)
          .bindPopup(`
            <strong>${f.bus_name}</strong><br>
            Reg: ${f.registration_number}<br>
            Status: ${f.gps_status}<br>
            Speed: ${f.speed_kmh} km/h
          `);
        fleetMarkers[f.trip_id] = marker;
      }
    });

  } catch (err) {
    console.error('Error loading fleet radar:', err);
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

document.addEventListener('DOMContentLoaded', () => {
  operatorUser = requireAuth(['OPERATOR']);
  if (!operatorUser) return;

  const nameEl = document.getElementById('operator-name');
  if (nameEl) nameEl.innerText = operatorUser.full_name;

  loadOverviewStats();
});
