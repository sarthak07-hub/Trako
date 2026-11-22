/**
 * Passenger Dashboard Controller
 */

let currentUser = null;
let currentTripId = null;
let currentLayoutData = null;
let selectedSeatId = null;
let selectedSeatNumber = null;

// Tab Switcher
function switchDashboardTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.dashboard-tab-content').forEach(c => c.style.display = 'none');

  const btn = document.getElementById(`btn-tab-${tabId}`);
  const content = document.getElementById(`tab-${tabId}`);
  if (btn) btn.classList.add('active');
  if (content) content.style.display = 'block';

  if (tabId === 'bookings') {
    loadMyBookings();
  }
}

// ----------------- BUS SEARCH & AVAILABILITY -----------------

async function handleBusSearch(e) {
  if (e) e.preventDefault();
  const origin = document.getElementById('search-origin').value.trim();
  const dest = document.getElementById('search-dest').value.trim();
  const date = document.getElementById('search-date').value;

  if (!origin || !dest || !date) {
    showToast('Please specify origin, destination, and travel date', 'error');
    return;
  }

  const container = document.getElementById('search-results-container');
  container.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Searching available buses...</div></div>';

  try {
    const results = await apiRequest(`/passenger/search?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}&travel_date=${encodeURIComponent(date)}`);

    if (!results || results.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          <h4>No Buses Found for this Segment</h4>
          <p>No active scheduled services match "${origin}" to "${dest}" on ${date}. Try another date or nearby stops.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="margin-bottom:1rem;color:var(--text-secondary);font-size:0.9rem;">
        Found <strong>${results.length}</strong> available service(s) for ${origin} &rarr; ${dest}
      </div>
      <div style="display:flex;flex-direction:column;gap:1.25rem;">
        ${results.map(trip => `
          <div class="card card-glass" style="display:flex;flex-direction:column;gap:1rem;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.75rem;">
              <div>
                <span class="badge ${trip.status === 'IN_TRANSIT' ? 'badge-live' : 'badge-primary'}">${trip.status}</span>
                <span style="font-weight:700;font-size:1.15rem;margin-left:0.5rem;">${trip.bus_name}</span>
                <span style="color:var(--text-muted);font-size:0.85rem;margin-left:0.5rem;">(${trip.registration_number}) &bull; ${trip.bus_type}</span>
              </div>
              <div style="text-align:right;">
                <span style="font-size:1.5rem;font-weight:800;color:var(--success);">₹${trip.fare}</span>
                <div style="font-size:0.75rem;color:var(--text-muted);">per passenger (segment fare)</div>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:1rem;background:var(--bg-input);border-radius:var(--radius-md);gap:1rem;">
              <div>
                <div style="font-size:1.25rem;font-weight:800;">${trip.departure_time}</div>
                <div style="font-size:0.9rem;color:var(--text-secondary);">${trip.origin_stop_name}</div>
              </div>
              <div style="text-align:center;color:var(--text-muted);font-size:0.8rem;">
                <div>⏱️ ~${trip.duration_minutes} mins</div>
                <div style="border-top:2px dashed var(--border-color);width:80px;margin:0.25rem auto;"></div>
                <div>Direct Segment</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:1.25rem;font-weight:800;">${trip.arrival_time}</div>
                <div style="font-size:0.9rem;color:var(--text-secondary);">${trip.destination_stop_name}</div>
              </div>
            </div>

            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.75rem;">
              <div style="font-size:0.875rem;">
                <span style="color:var(--success);font-weight:700;">${trip.available_seats} seats free</span>
                <span style="color:var(--text-muted);"> of ${trip.total_seats} total on this segment</span>
              </div>
              <div style="display:flex;gap:0.75rem;">
                ${trip.status === 'IN_TRANSIT' ? `
                  <a href="/pages/live-track.html?trip_id=${trip.trip_id}" class="btn btn-outline btn-sm">
                    🛰️ Live Radar
                  </a>
                ` : ''}
                <button onclick="openSeatLayoutModal(${trip.trip_id}, ${trip.boarding_stop_id}, ${trip.destination_stop_id})" class="btn btn-primary btn-sm">
                  Select Seats &rarr;
                </button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state" style="color:var(--danger);">
        <h4>Error loading bus services</h4>
        <p>${err.message}</p>
      </div>
    `;
  }
}

// ----------------- INTERACTIVE SEAT SELECTION -----------------

async function openSeatLayoutModal(tripId, boardStopId, destStopId) {
  currentTripId = tripId;
  selectedSeatId = null;
  selectedSeatNumber = null;

  const modal = document.getElementById('seat-modal');
  const body = document.getElementById('seat-modal-body');
  modal.classList.add('active');
  body.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Rendering interactive cabin layout...</div></div>';

  try {
    const layout = await apiRequest(`/passenger/trips/${tripId}/seat-layout?boarding_stop_id=${boardStopId}&destination_stop_id=${destStopId}`);
    currentLayoutData = layout;

    // Group seats into rows
    const rowsMap = {};
    layout.seats.forEach(seat => {
      if (!rowsMap[seat.row_num]) rowsMap[seat.row_num] = [];
      rowsMap[seat.row_num].push(seat);
    });

    const is2x2 = layout.layout_type === '2+2';

    body.innerHTML = `
      <div style="margin-bottom:1.25rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h4 style="font-size:1.15rem;font-weight:800;">${layout.bus_name}</h4>
            <div style="color:var(--text-secondary);font-size:0.85rem;">${layout.registration_number} &bull; ${layout.bus_type}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:1.4rem;font-weight:800;color:var(--success);">₹${layout.fare}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${layout.boarding_stop_name} &rarr; ${layout.destination_stop_name}</div>
          </div>
        </div>
      </div>

      <!-- Bus Cabin Graphic -->
      <div class="bus-cabin-container">
        <div class="bus-front-indicator">
          <span>FRONT &bull; DRIVER CABIN</span>
          <svg class="steering-wheel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 2a10 10 0 0 0 0 20M12 12l8 4M12 12l-8 4M12 12V2"></path>
          </svg>
        </div>

        <div class="seats-grid-2x2">
          ${Object.keys(rowsMap).sort((a,b) => a-b).map(rowNum => {
            const rowSeats = rowsMap[rowNum];
            // Sort by col_num
            rowSeats.sort((a,b) => a.col_num - b.col_num);

            const leftPair = rowSeats.filter(s => s.col_num <= (is2x2 ? 2 : 2));
            const rightPair = rowSeats.filter(s => s.col_num > (is2x2 ? 2 : 2));

            return `
              <div class="seat-row">
                <div class="seat-pair">
                  ${leftPair.map(s => renderSeatElement(s)).join('')}
                </div>
                <div class="aisle-space">Row ${rowNum}</div>
                <div class="seat-pair">
                  ${rightPair.map(s => renderSeatElement(s)).join('')}
                </div>
              </div>
            `;
          }).join('')}
        </div>

        <div class="seat-legend">
          <div class="legend-item">
            <div class="legend-color" style="background:#064e3b;border:1px solid #059669;"></div>
            <span>Available</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background:#1e293b;border:1px solid #334155;"></div>
            <span>Occupied</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background:#2563eb;border:1px solid #60a5fa;"></div>
            <span>Selected</span>
          </div>
        </div>
      </div>

      <!-- Booking Confirmation Form -->
      <form id="seat-confirm-form" onsubmit="handleConfirmBooking(event)" style="margin-top:1.5rem;background:var(--bg-secondary);padding:1.25rem;border-radius:var(--radius-lg);border:1px solid var(--border-color);">
        <h5 style="font-size:1rem;font-weight:700;margin-bottom:1rem;">Passenger Details</h5>
        
        <div class="grid grid-2" style="gap:1rem;">
          <div class="form-group" style="margin-bottom:0.75rem;">
            <label class="form-label">Full Name</label>
            <input type="text" id="pass-name" class="form-input" value="${currentUser ? currentUser.full_name : ''}" required>
          </div>
          <div class="form-group" style="margin-bottom:0.75rem;">
            <label class="form-label">Phone Number</label>
            <input type="tel" id="pass-phone" class="form-input" placeholder="+91 98200 00000" required>
          </div>
        </div>

        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border-color);">
          <div>
            <div style="font-size:0.85rem;color:var(--text-secondary);">Selected Seat:</div>
            <strong id="selected-seat-display" style="font-size:1.1rem;color:var(--primary);">None selected</strong>
          </div>
          <button type="submit" id="book-btn" class="btn btn-primary btn-lg" disabled>
            <span>Confirm & Generate Ticket</span>
          </button>
        </div>
      </form>
    `;

  } catch (err) {
    body.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

function renderSeatElement(seat) {
  if (!seat.is_available) {
    const reason = seat.current_occupant_segment ? `title="${seat.current_occupant_segment}"` : 'title="Occupied for this segment"';
    return `<div class="bus-seat occupied" ${reason}>${seat.seat_number}</div>`;
  }
  return `
    <div class="bus-seat available" id="seat-box-${seat.seat_id}" onclick="selectSeat(${seat.seat_id}, '${seat.seat_number}')" title="Seat ${seat.seat_number} (${seat.seat_type})">
      ${seat.seat_number}
    </div>
  `;
}

function selectSeat(seatId, seatNumber) {
  // Deselect previous
  document.querySelectorAll('.bus-seat.selected').forEach(el => {
    el.classList.remove('selected');
    el.classList.add('available');
  });

  selectedSeatId = seatId;
  selectedSeatNumber = seatNumber;

  const target = document.getElementById(`seat-box-${seatId}`);
  if (target) {
    target.classList.remove('available');
    target.classList.add('selected');
  }

  document.getElementById('selected-seat-display').innerText = `Seat ${seatNumber} (₹${currentLayoutData.fare})`;
  document.getElementById('book-btn').disabled = false;
}

async function handleConfirmBooking(e) {
  e.preventDefault();
  if (!selectedSeatId || !currentTripId || !currentLayoutData) {
    showToast('Please select an available seat first', 'error');
    return;
  }

  const passenger_name = document.getElementById('pass-name').value.trim();
  const passenger_phone = document.getElementById('pass-phone').value.trim();
  const btn = document.getElementById('book-btn');

  btn.disabled = true;
  btn.innerText = 'Reserving Seat & Generating Ticket...';

  try {
    const booking = await apiRequest('/passenger/book', {
      method: 'POST',
      body: JSON.stringify({
        trip_id: currentTripId,
        seat_id: selectedSeatId,
        boarding_stop_id: currentLayoutData.boarding_stop_id,
        destination_stop_id: currentLayoutData.destination_stop_id,
        passenger_name,
        passenger_phone,
        booking_source: 'WEB'
      })
    });

    closeModal('seat-modal');
    showToast('Booking Confirmed! Digital ticket generated.', 'success');
    openTicketModal(booking.booking_reference);

  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerText = 'Confirm & Generate Ticket';
  }
}

// ----------------- DIGITAL TICKET MODAL -----------------

async function openTicketModal(bookingRef) {
  const modal = document.getElementById('ticket-modal');
  const body = document.getElementById('ticket-modal-body');
  modal.classList.add('active');
  body.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Fetching digital ticket...</div></div>';

  try {
    const ticket = await apiRequest(`/passenger/tickets/${bookingRef}`);

    const depDate = new Date(ticket.departure_datetime).toLocaleString();

    body.innerHTML = `
      <div class="ticket-pass">
        <div class="ticket-header">
          <div class="ticket-brand">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="15" rx="3"></rect><circle cx="7" cy="19" r="2"></circle><circle cx="17" cy="19" r="2"></circle></svg>
            <span>TRAKO DIGITAL TICKET</span>
          </div>
          <span class="badge ${ticket.status === 'BOARDED' ? 'badge-live' : 'badge-primary'}">${ticket.status}</span>
        </div>

        <div class="ticket-body">
          <div class="ticket-route-display">
            <div>
              <div class="ticket-stop-title">${ticket.boarding_stop_name.split('(')[0]}</div>
              <div class="ticket-stop-sub">Boarding Stop</div>
            </div>
            <div style="color:var(--primary);font-size:1.5rem;">&rarr;</div>
            <div>
              <div class="ticket-stop-title">${ticket.destination_stop_name.split('(')[0]}</div>
              <div class="ticket-stop-sub">Destination Stop</div>
            </div>
          </div>

          <div class="ticket-divider-line"></div>

          <div class="ticket-meta-grid">
            <div class="ticket-meta-item">
              <div class="label">Passenger</div>
              <div class="val">${ticket.passenger_name}</div>
            </div>
            <div class="ticket-meta-item">
              <div class="label">Seat Number</div>
              <div class="val" style="color:#60a5fa;font-size:1.25rem;">${ticket.seat_number}</div>
            </div>
            <div class="ticket-meta-item">
              <div class="label">Fare Amount</div>
              <div class="val" style="color:var(--success);">₹${ticket.fare_amount}</div>
            </div>
            <div class="ticket-meta-item">
              <div class="label">Bus / Reg</div>
              <div class="val">${ticket.bus_name} (${ticket.registration_number})</div>
            </div>
            <div class="ticket-meta-item">
              <div class="label">Departure</div>
              <div class="val" style="font-size:0.85rem;">${depDate}</div>
            </div>
            <div class="ticket-meta-item">
              <div class="label">Booking Ref</div>
              <div class="val" style="font-family:monospace;font-size:0.9rem;">${ticket.booking_reference}</div>
            </div>
          </div>

          <!-- Digital Ticket QR for Conductor Verification -->
          <div class="ticket-qr-container">
            <img src="${ticket.qr_data}" alt="Digital Ticket QR">
            <div class="ticket-qr-caption">SCAN FOR CONDUCTOR VERIFICATION</div>
          </div>

          ${ticket.is_verified ? `
            <div style="margin-top:1rem;text-align:center;color:var(--success);font-weight:700;font-size:0.85rem;">
              ✓ Ticket Verified & Passenger Boarded (${new Date(ticket.verified_at).toLocaleTimeString()})
            </div>
          ` : `
            <div style="margin-top:1rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">
              Present this QR to the conductor when boarding at your stop.
            </div>
          `}
        </div>
      </div>

      <div style="display:flex;justify-content:center;gap:1rem;margin-top:1.5rem;">
        <button onclick="window.print()" class="btn btn-secondary btn-sm">🖨️ Print / Save PDF</button>
        <button onclick="closeModal('ticket-modal')" class="btn btn-primary btn-sm">Done</button>
      </div>
    `;

  } catch (err) {
    body.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

// ----------------- BOOKINGS TAB -----------------

async function loadMyBookings() {
  const container = document.getElementById('my-bookings-list');
  container.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="badge badge-primary">Loading bookings...</div></div>';

  try {
    const bookings = await apiRequest('/passenger/bookings');
    if (!bookings || bookings.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <h4>No Bookings Yet</h4>
          <p>You haven't reserved any bus journeys. Use the search tab to book your first smart bus segment!</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:1.25rem;">
        ${bookings.map(b => `
          <div class="card card-glass" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;">
            <div>
              <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.35rem;">
                <span class="badge ${b.status === 'BOARDED' ? 'badge-live' : (b.status === 'CANCELLED' ? 'badge-unavailable' : 'badge-primary')}">${b.status}</span>
                <span style="font-family:monospace;font-weight:700;color:#60a5fa;">${b.booking_reference}</span>
                <span style="color:var(--text-muted);font-size:0.8rem;">&bull; Booked on ${new Date(b.booked_at).toLocaleDateString()}</span>
              </div>
              <div style="font-size:1.15rem;font-weight:800;color:var(--text-primary);">
                ${b.boarding_stop.split('(')[0]} &rarr; ${b.destination_stop.split('(')[0]}
              </div>
              <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:0.2rem;">
                ${b.bus_name} (${b.registration_number}) &bull; <strong>Seat ${b.seat_number}</strong> &bull; Fare: ₹${b.fare_amount}
              </div>
            </div>

            <div style="display:flex;gap:0.75rem;align-items:center;">
              <a href="/pages/live-track.html?trip_id=${b.trip_id}" class="btn btn-outline btn-sm">
                🛰️ Live Track
              </a>
              <button onclick="openTicketModal('${b.booking_reference}')" class="btn btn-secondary btn-sm">
                🎫 View Ticket Pass
              </button>
              ${b.status === 'CONFIRMED' ? `
                <button onclick="cancelBooking('${b.booking_reference}')" class="btn btn-danger btn-sm">
                  Cancel
                </button>
              ` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="color:var(--danger);">${err.message}</div>`;
  }
}

async function cancelBooking(bookingRef) {
  if (!confirm(`Are you sure you want to cancel booking ${bookingRef}? This will immediately release the seat segment.`)) {
    return;
  }

  try {
    await apiRequest(`/passenger/bookings/${bookingRef}/cancel`, { method: 'POST' });
    showToast('Booking cancelled. Seat segment freed.', 'success');
    loadMyBookings();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// Initialize Page
document.addEventListener('DOMContentLoaded', async () => {
  currentUser = requireAuth(['PASSENGER']);
  if (!currentUser) return;

  const nameEl = document.getElementById('user-display-name');
  if (nameEl) nameEl.innerText = currentUser.full_name;

  // Set default travel date
  const dateInput = document.getElementById('search-date');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
    dateInput.min = today;
  }

  // Check URL query parameters (if coming from landing page quick search)
  const urlParams = new URLSearchParams(window.location.search);
  const originParam = urlParams.get('origin');
  const destParam = urlParams.get('dest');
  const dateParam = urlParams.get('date');

  if (originParam && destParam) {
    document.getElementById('search-origin').value = originParam;
    document.getElementById('search-dest').value = destParam;
    if (dateParam) document.getElementById('search-date').value = dateParam;
    handleBusSearch();
  }
});
