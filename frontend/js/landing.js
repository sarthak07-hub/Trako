/**
 * Landing Page Controller
 */

function switchRoleTab(role) {
  const tabs = document.querySelectorAll('.role-tab-btn');
  tabs.forEach(btn => btn.classList.remove('active'));

  const activeBtn = Array.from(tabs).find(b => b.textContent.toLowerCase().includes(role.toLowerCase()));
  if (activeBtn) activeBtn.classList.add('active');

  const contentBoxes = ['passenger', 'operator', 'driver', 'conductor'];
  contentBoxes.forEach(r => {
    const box = document.getElementById(`role-${r}`);
    if (box) {
      box.style.display = (r === role) ? 'grid' : 'none';
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  // Set default travel date to today
  const dateInput = document.getElementById('date-input');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
    dateInput.min = today;
  }

  // Load stops for search datalist
  try {
    const stops = await apiRequest('/passenger/stops');
    const datalist = document.getElementById('stops-datalist');
    if (datalist && stops) {
      const cities = [...new Set(stops.map(s => s.city))];
      stops.forEach(s => {
        const opt = document.createElement('option');
        opt.value = `${s.name} (${s.city})`;
        datalist.appendChild(opt);
      });
      cities.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        datalist.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn('Could not pre-load stops datalist:', err);
  }

  // Handle Search Form Submit
  const searchForm = document.getElementById('quick-search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const origin = document.getElementById('origin-input').value.trim();
      const dest = document.getElementById('dest-input').value.trim();
      const date = document.getElementById('date-input').value;

      if (!origin || !dest || !date) {
        showToast('Please specify origin, destination, and travel date', 'error');
        return;
      }

      window.location.href = `/pages/passenger.html?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}&date=${encodeURIComponent(date)}`;
    });
  }
});
