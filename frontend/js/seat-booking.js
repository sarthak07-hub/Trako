/**
 * Physical Seat QR Code Booking Workflow Controller
 */

let busData = null;
let seatData = null;
let availableTrips = [];
let selectedTrip = null;

async function initSeatBooking() {
  const urlParams = new URLSearchParams(window.location.search);
  const busId = urlParams.get('bus_id') || 1; // default to demo bus 1 if not passed
  const seatNum = urlParams.get('seat') || '1A';

  const container = document.getElementById('seat-qr-workflow-container');
  container.innerHTML = '<div style="text-align:center;padding:3rem;"><div class="badge badge-primary">Identifying bus and physical seat...</div></div>';

  try {
    const data = await apiRequest(`/qr/bus-seat-info?bus_id=${busId}&seat_number=${encodeURIComponent(seatNum)}`);
    busData = data.bus;
    seatData = data.seat;
    availableTrips = data.available_trips;

    renderWorkflowStep1();
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state" style="color:var(--danger);">
        <h4>Bus Seat QR Code Not Recognized</h4>
        <p>${err.message}</p>
        <a href="/pages/passenger.html" class="btn btn-primary btn-sm" style="margin-top:1rem;">Go to Passenger Portal</a>
      </div>
    `;
  }
}

function renderWorkflowStep1() {
  const container = document.getElementById('seat-qr-workflow-container');

  container.innerHTML = `
    <!-- Step 1: Physical Seat Identification Card -->
    <div class="card card-glass" style="margin-bottom:1.5rem;border-color:rgba(59,130,246,0.4);">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;">
        <div>
          <span class="badge badge-live">Physical Seat Verified</span>
          <h2 style="font-size:1.6rem;font-weight:800;margin-top:0.35rem;">
            Seat ${seatData.seat_number} &bull; ${busData.bus_name}
          </h2>
          <div style="color:var(--text-secondary);font-size:0.9rem;">
            Bus Reg: <code style="color:#60a5fa;">${busData.registration_number}</code> &bull; Type: ${busData.bus_type} &bull; ${seatData.seat_type} (${seatData.deck} Deck)
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:2.5rem;">💺</div>
        </div>
      </div>
    </div>

    <!-- Step 2: Trip & Segment Selection Form -->
    <div class="card card-glass" style="padding:2rem;">
      <h3 style="font-size:1.25rem;font-weight:700;margin-bottom:1.25rem;">Select Active Trip & Travel Stops</h3>

      ${availableTrips.length === 0 ? `
        <div class="empty-state">
          <h4>No Upcoming Trips for this Bus</h4>
          <p>This bus currently has no scheduled journeys today. Please consult the conductor.</p>
        </div>
      ` : `
        <form onsubmit="handleConfirmQrBooking(event)">
          <div class="form-group">
            <label class="form-label">Available Trip</label>
            <select id="select-trip" class="form-select" onchange="onTripChange()" required>
              ${availableTrips.map(t => `
                <option value="${t.trip_id}">
                  ${t.trip_code} &bull; ${t.route_name} (Dep: ${new Date(t.departure_datetime).toLocaleTimeString()}) - ${t.status}
                </option>
              `).join('')}
            </select>
          </div>

          <div class="grid grid-2" style="gap:1rem;">
            <div class="form-group">
              <label class="form-label">Boarding Stop</label>
              <select id="select-board-stop" class="form-select" onchange="updateSegmentFare()" required></select>
            </div>
            <div class="form-group">
              <label class="form-label">Destination Stop</label>
              <select id="select-dest-stop" class="form-select" onchange="updateSegmentFare()" required></select>
            </div>
          </div>

          <!-- Segment Availability & Price Live Calculator -->
          <div style="background:var(--bg-secondary);padding:1.25rem;border-radius:var(--radius-md);margin-bottom:1.5rem;display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;">Calculated Segment Fare</div>
              <div id="segment-fare-display" style="font-size:1.75rem;font-weight:800;color:var(--success);">₹--</div>
            </div>
            <div id="segment-availability-status" style="text-align:right;">
              <span class="badge badge-primary">Checking availability...</span>
            </div>
          </div>

          <h4 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Passenger Details</h4>
          <div class="grid grid-2" style="gap:1rem;">
            <div class="form-group">
              <label class="form-label">Passenger Name</label>
              <input type="text" id="qr-pass-name" class="form-input" placeholder="Your Name" required>
            </div>
            <div class="form-group">
              <label class="form-label">Phone Number</label>
              <input type="tel" id="qr-pass-phone" class="form-input" placeholder="+91 98200 00000" required>
            </div>
          </div>

          <button type="submit" id="qr-confirm-btn" class="btn btn-primary btn-full btn-lg" style="margin-top:1rem;">
            <span>Instant Book Seat & Generate Digital Ticket</span>
          </button>
        </form>
      `}
    </div>

    <!-- Ticket Modal Placeholder -->
    <div id="qr-ticket-modal" class="modal-overlay">
      <div class="modal-content" style="max-width:560px;background:var(--bg-secondary);">
        <div class="modal-header">
          <h3 class="modal-title">Your Confirmed Ticket</h3>
          <button class="modal-close" onclick="closeModal('qr-ticket-modal')">&times;</button>
        </div>
        <div id="qr-ticket-modal-body"></div>
      </div>
    </div>
  `;

  if (availableTrips.length > 0) {
    onTripChange();
  }
}

function onTripChange() {
  const tripSelect = document.getElementById('select-trip');
  const tripId = parseInt(tripSelect.value, 10);
  selectedTrip = availableTrips.find(t => t.trip_id === tripId);
  if (!selectedTrip) return;

  const boardSelect = document.getElementById('select-board-stop');
  const destSelect = document.getElementById('select-dest-stop');

  boardSelect.innerHTML = selectedTrip.stops.slice(0, -1).map(s => `
    <option value="${s.stop_id}" data-seq="${s.sequence}">${s.name} (${s.city})</option>
  `).join('');

  destSelect.innerHTML = selectedTrip.stops.slice(1).map(s => `
    <option value="${s.stop_id}" data-seq="${s.sequence}">${s.name} (${s.city})</option>
  `).join('');

  // Default destination to last stop
  destSelect.selectedIndex = destSelect.options.length - 1;

  updateSegmentFare();
}

async function updateSegmentFare() {
  const boardSelect = document.getElementById('select-board-stop');
  const destSelect = document.getElementById('select-dest-stop');
  if (!boardSelect || !destSelect || !selectedTrip) return;

  const boardOption = boardSelect.options[boardSelect.selectedIndex];
  const destOption = destSelect.options[destSelect.selectedIndex];

  if (!boardOption || !destOption) return;

  const boardSeq = parseInt(boardOption.getAttribute('data-seq'), 10);
  const destSeq = parseInt(destOption.getAttribute('data-seq'), 10);

  const statusBadge = document.getElementById('segment-availability-status');
  const fareDisplay = document.getElementById('segment-fare-display');
  const confirmBtn = document.getElementById('qr-confirm-btn');

  if (boardSeq >= destSeq) {
    statusBadge.innerHTML = '<span class="badge badge-delayed">Boarding must be before destination</span>';
    confirmBtn.disabled = true;
    fareDisplay.innerText = '₹--';
    return;
  }

  // Calculate fare
  const totalStops = Math.max(selectedTrip.stops.length - 1, 1);
  const fare = Math.round(((destSeq - boardSeq) / totalStops) * selectedTrip.base_fare);
  fareDisplay.innerText = `₹${fare}`;

  // Check segment availability on backend
  try {
    const layout = await apiRequest(`/passenger/trips/${selectedTrip.trip_id}/seat-layout?boarding_stop_id=${boardSelect.value}&destination_stop_id=${destSelect.value}`);
    const currentSeatAvailability = layout.seats.find(s => s.seat_number === seatData.seat_number);

    if (currentSeatAvailability && currentSeatAvailability.is_available) {
      statusBadge.innerHTML = '<span class="badge badge-live">Seat Free for this Segment</span>';
      confirmBtn.disabled = false;
    } else {
      const reason = currentSeatAvailability ? currentSeatAvailability.current_occupant_segment : 'Occupied';
      statusBadge.innerHTML = `<span class="badge badge-delayed" title="${reason}">Seat Occupied on this Segment</span>`;
      confirmBtn.disabled = true;
    }
  } catch (err) {
    statusBadge.innerHTML = `<span class="badge badge-delayed">${err.message}</span>`;
    confirmBtn.disabled = true;
  }
}

async function handleConfirmQrBooking(e) {
  e.preventDefault();
  const boardStopId = parseInt(document.getElementById('select-board-stop').value, 10);
  const destStopId = parseInt(document.getElementById('select-dest-stop').value, 10);
  const passenger_name = document.getElementById('qr-pass-name').value.trim();
  const passenger_phone = document.getElementById('qr-pass-phone').value.trim();
  const btn = document.getElementById('qr-confirm-btn');

  btn.disabled = true;
  btn.innerText = 'Processing Booking...';

  try {
    const booking = await apiRequest('/passenger/book', {
      method: 'POST',
      body: JSON.stringify({
        trip_id: selectedTrip.trip_id,
        seat_id: seatData.id,
        boarding_stop_id: boardStopId,
        destination_stop_id: destStopId,
        passenger_name,
        passenger_phone,
        booking_source: 'SEAT_QR'
      })
    });

    showToast('Seat booked successfully from physical QR!', 'success');
    showConfirmedTicketModal(booking);

  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerText = 'Instant Book Seat & Generate Digital Ticket';
  }
}

function showConfirmedTicketModal(b) {
  const modal = document.getElementById('qr-ticket-modal');
  const body = document.getElementById('qr-ticket-modal-body');
  modal.classList.add('active');

  body.innerHTML = `
    <div class="ticket-pass" style="box-shadow:none;">
      <div class="ticket-header">
        <div class="ticket-brand">TRAKO DIGITAL PASS</div>
        <span class="badge badge-live">CONFIRMED</span>
      </div>
      <div class="ticket-body">
        <div class="ticket-route-display">
          <div>
            <div class="ticket-stop-title">${b.boarding_stop_name.split('(')[0]}</div>
            <div class="ticket-stop-sub">Boarding</div>
          </div>
          <div style="color:var(--primary);font-size:1.5rem;">&rarr;</div>
          <div>
            <div class="ticket-stop-title">${b.destination_stop_name.split('(')[0]}</div>
            <div class="ticket-stop-sub">Destination</div>
          </div>
        </div>

        <div class="ticket-divider-line"></div>

        <div class="ticket-meta-grid">
          <div class="ticket-meta-item">
            <div class="label">Passenger</div>
            <div class="val">${b.passenger_name}</div>
          </div>
          <div class="ticket-meta-item">
            <div class="label">Seat Number</div>
            <div class="val" style="color:#60a5fa;font-size:1.25rem;">${b.seat_number}</div>
          </div>
          <div class="ticket-meta-item">
            <div class="label">Fare Amount</div>
            <div class="val" style="color:var(--success);">₹${b.fare_amount}</div>
          </div>
        </div>

        <div class="ticket-qr-container">
          <img src="${b.qr_data}" alt="Digital Ticket QR">
          <div class="ticket-qr-caption">FOR CONDUCTOR VERIFICATION</div>
        </div>
      </div>
    </div>

    <div style="display:flex;justify-content:center;gap:1rem;margin-top:1.5rem;">
      <a href="/pages/passenger.html" class="btn btn-primary btn-sm">Go to Dashboard</a>
      <button onclick="window.print()" class="btn btn-secondary btn-sm">Print Ticket</button>
    </div>
  `;
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

document.addEventListener('DOMContentLoaded', () => {
  initSeatBooking();
});
