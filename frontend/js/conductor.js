/**
 * Conductor Dashboard & Ticket Verification Controller
 */

let conductorUser = null;
let assignedTrips = [];
let currentTripId = null;
let html5QrScanner = null;

async function loadConductorTrips() {
  try {
    assignedTrips = await apiRequest('/conductor/assigned-trips');
    const select = document.getElementById('conductor-trip-select');
    if (!assignedTrips || assignedTrips.length === 0) {
      select.innerHTML = '<option value="">No trips assigned</option>';
      document.getElementById('manifest-container').innerHTML = '<div class="empty-state">No trips assigned to your conductor account.</div>';
      return;
    }

    select.innerHTML = assignedTrips.map(t => `
      <option value="${t.id}">
        ${t.trip_code} &bull; ${t.route_name} (${t.bus_name}) - ${t.status}
      </option>
    `).join('');

    currentTripId = assignedTrips[0].id;
    loadManifest(currentTripId);

  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function onTripSelected() {
  currentTripId = parseInt(document.getElementById('conductor-trip-select').value, 10);
  if (currentTripId) {
    loadManifest(currentTripId);
  }
}

async function loadManifest(tripId) {
  const container = document.getElementById('manifest-table-body');
  container.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading manifest...</td></tr>';

  try {
    const manifest = await apiRequest(`/conductor/trips/${tripId}/manifest`);
    
    // Calculate stats
    const total = manifest.length;
    const boarded = manifest.filter(p => p.status === 'BOARDED').length;
    const noShows = manifest.filter(p => p.status === 'NO_SHOW').length;
    const pending = total - boarded - noShows;
    const potentialNoShows = manifest.filter(p => p.is_potential_no_show).length;

    document.getElementById('stat-total-passengers').innerText = total;
    document.getElementById('stat-boarded').innerText = boarded;
    document.getElementById('stat-pending').innerText = pending;
    document.getElementById('stat-no-shows').innerText = potentialNoShows;

    if (!manifest || manifest.length === 0) {
      container.innerHTML = '<tr><td colspan="7" class="empty-state">No passenger bookings on this trip yet.</td></tr>';
      return;
    }

    container.innerHTML = manifest.map(p => {
      let statusBadge = '<span class="badge badge-primary">CONFIRMED</span>';
      if (p.status === 'BOARDED') statusBadge = '<span class="badge badge-live">BOARDED</span>';
      else if (p.status === 'NO_SHOW') statusBadge = '<span class="badge badge-unavailable">NO SHOW</span>';
      else if (p.is_potential_no_show) statusBadge = '<span class="badge badge-delayed">POTENTIAL NO-SHOW</span>';

      return `
        <tr style="${p.is_potential_no_show ? 'background:rgba(245, 158, 11, 0.08);' : ''}">
          <td>
            <strong style="color:var(--primary);font-size:1.15rem;">Seat ${p.seat_number}</strong>
          </td>
          <td>
            <strong>${p.passenger_name}</strong>
            <div style="font-size:0.75rem;color:var(--text-muted);">${p.passenger_phone}</div>
          </td>
          <td>
            <code style="color:#60a5fa;">${p.booking_reference}</code>
            <div style="font-size:0.75rem;color:var(--text-muted);">${p.ticket_token}</div>
          </td>
          <td>
            <div>${p.boarding_stop_name.split('(')[0]} &rarr; ${p.destination_stop_name.split('(')[0]}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">Seq #${p.boarding_sequence} to #${p.destination_sequence}</div>
          </td>
          <td>${statusBadge}</td>
          <td>
            <div style="display:flex;gap:0.5rem;">
              ${p.status !== 'BOARDED' ? `
                <button onclick="quickBoardPassenger(${p.booking_id})" class="btn btn-success btn-sm">
                  ✓ Board
                </button>
              ` : `
                <span style="color:var(--success);font-size:0.85rem;font-weight:600;">✓ Checked in</span>
              `}
              ${p.is_potential_no_show && p.status !== 'NO_SHOW' ? `
                <button onclick="quickDeclareNoShow(${p.booking_id}, '${p.passenger_name}', '${p.seat_number}')" class="btn btn-danger btn-sm">
                  Release Seat
                </button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" style="color:var(--danger);">${err.message}</td></tr>`;
  }
}

// ----------------- TICKET VERIFICATION (QR & MANUAL) -----------------

async function verifyTicketToken(tokenOrRef) {
  if (!tokenOrRef) return;

  try {
    const res = await apiRequest('/conductor/verify-ticket', {
      method: 'POST',
      body: JSON.stringify({
        ticket_token_or_ref: tokenOrRef.trim(),
        trip_id: currentTripId
      })
    });

    displayVerificationResult(res);

  } catch (err) {
    showToast(err.message, 'error');
  }
}

function displayVerificationResult(res) {
  const modal = document.getElementById('verify-result-modal');
  const body = document.getElementById('verify-result-modal-body');
  modal.classList.add('active');

  if (!res.valid) {
    body.innerHTML = `
      <div style="text-align:center;padding:1.5rem;">
        <div style="font-size:3rem;margin-bottom:1rem;">❌</div>
        <h3 style="color:var(--danger);font-size:1.35rem;font-weight:800;margin-bottom:0.5rem;">
          INVALID TICKET: ${res.status_code}
        </h3>
        <p style="color:var(--text-secondary);margin-bottom:1.5rem;">${res.message}</p>
        <button onclick="closeModal('verify-result-modal')" class="btn btn-secondary btn-full">Close</button>
      </div>
    `;
    return;
  }

  const isAlreadyBoarded = (res.status_code === 'ALREADY_BOARDED');

  body.innerHTML = `
    <div style="padding:1rem;">
      <div style="text-align:center;margin-bottom:1.5rem;">
        <div style="font-size:3rem;margin-bottom:0.5rem;">${isAlreadyBoarded ? '⚠️' : '✅'}</div>
        <h3 style="color:${isAlreadyBoarded ? 'var(--warning)' : 'var(--success)'};font-size:1.35rem;font-weight:800;">
          ${res.message}
        </h3>
      </div>

      <div class="card" style="background:var(--bg-secondary);padding:1.25rem;margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.75rem;">
          <span style="color:var(--text-muted);font-size:0.85rem;">PASSENGER</span>
          <strong>${res.passenger_name} (${res.passenger_phone})</strong>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:0.75rem;">
          <span style="color:var(--text-muted);font-size:0.85rem;">ASSIGNED SEAT</span>
          <strong style="color:var(--primary);font-size:1.25rem;">Seat ${res.seat_number}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:0.75rem;">
          <span style="color:var(--text-muted);font-size:0.85rem;">JOURNEY SEGMENT</span>
          <span>${res.boarding_stop.split('(')[0]} &rarr; ${res.destination_stop.split('(')[0]}</span>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span style="color:var(--text-muted);font-size:0.85rem;">BOOKING REF</span>
          <code style="color:#60a5fa;">${res.booking_reference}</code>
        </div>
      </div>

      <div style="display:flex;gap:1rem;">
        ${!isAlreadyBoarded ? `
          <button onclick="quickBoardPassenger(${res.booking_id}); closeModal('verify-result-modal');" class="btn btn-success btn-full btn-lg">
            ✓ Confirm Passenger Boarding
          </button>
        ` : `
          <button onclick="closeModal('verify-result-modal')" class="btn btn-secondary btn-full">
            Passenger Already Boarded
          </button>
        `}
      </div>
    </div>
  `;
}

async function quickBoardPassenger(bookingId) {
  try {
    const res = await apiRequest('/conductor/confirm-boarding', {
      method: 'POST',
      body: JSON.stringify({ booking_id: bookingId, action: 'BOARDED' })
    });
    showToast(res.message, 'success');
    loadManifest(currentTripId);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function quickDeclareNoShow(bookingId, passengerName, seatNumber) {
  if (!confirm(`Confirm NO-SHOW for ${passengerName} on Seat ${seatNumber}?\n\nThis will permanently release the seat segment for other passengers.`)) {
    return;
  }

  try {
    const res = await apiRequest('/conductor/declare-no-show', {
      method: 'POST',
      body: JSON.stringify({ booking_id: bookingId, action: 'NO_SHOW_SEAT_RELEASED' })
    });
    showToast(res.message, 'warning');
    loadManifest(currentTripId);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ----------------- CAMERA QR SCANNER -----------------

function initCameraScanner() {
  const qrRegion = document.getElementById('qr-reader');
  if (!qrRegion) return;

  if (typeof Html5QrcodeScanner === 'undefined') {
    showToast('Camera scanner library loading... Use manual input below if camera is unavailable.', 'info');
    return;
  }

  if (!html5QrScanner) {
    html5QrScanner = new Html5QrcodeScanner(
      "qr-reader",
      { fps: 10, qrbox: { width: 250, height: 250 } },
      false
    );

    html5QrScanner.render((decodedText) => {
      showToast(`Scanned QR: ${decodedText}`, 'info');
      verifyTicketToken(decodedText);
    }, (error) => {
      // ignore frame scan misses
    });
  }
}

function handleManualVerify(e) {
  e.preventDefault();
  const code = document.getElementById('manual-ticket-input').value.trim();
  if (code) {
    verifyTicketToken(code);
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

document.addEventListener('DOMContentLoaded', () => {
  conductorUser = requireAuth(['CONDUCTOR']);
  if (!conductorUser) return;

  const nameEl = document.getElementById('conductor-name');
  if (nameEl) nameEl.innerText = conductorUser.full_name;

  loadConductorTrips();
});
