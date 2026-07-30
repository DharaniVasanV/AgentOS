document.addEventListener('DOMContentLoaded', () => {
  let allEvents = [];
  let currentDate = new Date();
  let selectedDate = new Date();

  // Initialize
  fetchStatus();
  fetchEvents();

  // Event Listeners
  document.getElementById('syncBtn').addEventListener('click', runSync);
  document.getElementById('clearAllBtn').addEventListener('click', clearAllEvents);
  document.getElementById('geminiScheduleForm').addEventListener('submit', handleGeminiSchedule);
  document.getElementById('prevMonth').addEventListener('click', () => changeMonth(-1));
  document.getElementById('nextMonth').addEventListener('click', () => changeMonth(1));
  document.getElementById('closeModal').addEventListener('click', closeModal);

  async function handleGeminiSchedule(e) {
    e.preventDefault();
    const btn = document.getElementById('scheduleBtn');
    const statusText = document.getElementById('geminiFormStatus');
    const originalHtml = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Creating Event...';
    statusText.style.display = 'none';

    const payload = {
      title: document.getElementById('eventTitleInput').value.trim(),
      start_datetime: document.getElementById('eventDateTimeInput').value,
      event_type: document.getElementById('eventTypeSelect').value,
      location: document.getElementById('eventLocationInput').value.trim(),
      description: document.getElementById('eventDescriptionInput').value.trim(),
      user_id: 'user_1',
      source_type: 'manual'
    };

    try {
      const res = await fetch('/api/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const newEvent = await res.json();

      statusText.textContent = `✅ Event "${newEvent.title}" Created Successfully!`;
      statusText.style.display = 'inline';

      document.getElementById('geminiScheduleForm').reset();

      await fetchStatus();
      await fetchEvents();
    } catch (err) {
      alert('Failed to create event: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      setTimeout(() => {
        statusText.style.display = 'none';
      }, 5000);
    }
  }

  async function clearAllEvents() {
    if (confirm('Are you sure you want to clear all calendar events? This will remove mock and scheduled events.')) {
      try {
        const res = await fetch('/api/calendar/clear-all', { method: 'DELETE' });
        const data = await res.json();
        alert(`Cleared ${data.deleted_count || 0} events.`);
        await fetchStatus();
        await fetchEvents();
      } catch (err) {
        alert('Failed to clear events: ' + err.message);
      }
    }
  }


  // Tab Filtering
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      filterUpcomingEvents(e.target.dataset.filter);
    });
  });

  async function fetchStatus() {
    try {
      const res = await fetch('/api/calendar/status');
      const data = await res.json();
      
      const statusDot = document.getElementById('googleStatusDot');
      const statusText = document.getElementById('googleStatusText');
      const googleConnectBtn = document.getElementById('googleConnectBtn');

      if (data.google_connected) {
        statusDot.className = 'status-dot connected';
        statusText.textContent = `Google Sync Active (${data.google_account_email || 'Connected'})`;
        googleConnectBtn.style.display = 'none';
      } else {
        statusDot.className = 'status-dot disconnected';
        statusText.textContent = 'Google Calendar Disconnected (Mock Local Mode)';
        googleConnectBtn.style.display = 'inline-flex';
      }

      document.getElementById('valToday').textContent = data.today_events_count || 0;
      document.getElementById('valDeadlines').textContent = data.upcoming_deadlines_count || 0;
      document.getElementById('valTotal').textContent = data.active_events || 0;
    } catch (err) {
      console.error('Error fetching status:', err);
    }
  }

  async function fetchEvents() {
    try {
      const res = await fetch('/api/calendar/events');
      allEvents = await res.json();
      
      renderTodayEvents();
      renderUpcomingDeadlines();
      renderCalendar();
      filterUpcomingEvents('ALL');
    } catch (err) {
      console.error('Error fetching events:', err);
    }
  }

  async function runSync() {
    const btn = document.getElementById('syncBtn');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Syncing...';
    btn.disabled = true;

    try {
      const res = await fetch('/api/calendar/sync', { method: 'POST' });
      const summary = await res.json();
      
      alert(`Sync Completed!\nCreated: ${summary.created_count}\nUpdated: ${summary.updated_count}\nUnchanged: ${summary.unchanged_count}\nSkipped (No date): ${summary.skipped_invalid_date}`);
      
      await fetchStatus();
      await fetchEvents();
    } catch (err) {
      alert('Sync failed: ' + err.message);
    } finally {
      btn.innerHTML = originalHtml;
      btn.disabled = false;
    }
  }

  function getLocalTodayStr() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }

  function renderTodayEvents() {
    const container = document.getElementById('todayEventsList');
    const todayStr = getLocalTodayStr();

    const todayEvts = allEvents.filter(e => {
      const startStr = e.start_datetime ? String(e.start_datetime) : '';
      const deadStr = e.deadline ? String(e.deadline) : '';
      return (startStr.includes(todayStr) || deadStr.includes(todayStr)) && e.status === 'ACTIVE';
    });

    if (todayEvts.length === 0) {
      container.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--text-muted);">No events scheduled for today.</td></tr>';
      return;
    }

    container.innerHTML = todayEvts.map(e => `
      <tr class="event-row" onclick="openEventModal('${e.id}')">
        <td>${formatTime(e.start_datetime || e.deadline)}</td>
        <td style="font-weight: 600;">${e.title}</td>
        <td><span class="type-pill">${e.event_type}</span></td>
      </tr>
    `).join('');
  }

  function renderUpcomingDeadlines() {
    const container = document.getElementById('upcomingDeadlinesList');
    const now = new Date();

    const deadlines = allEvents
      .filter(e => e.deadline && new Date(e.deadline) >= now && e.status === 'ACTIVE')
      .sort((a, b) => new Date(a.deadline) - new Date(b.deadline))
      .slice(0, 5);

    if (deadlines.length === 0) {
      container.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--text-muted);">No upcoming deadlines found.</td></tr>';
      return;
    }

    container.innerHTML = deadlines.map(e => {
      const daysLeft = Math.ceil((new Date(e.deadline) - now) / (1000 * 60 * 60 * 24));
      return `
        <tr class="event-row" onclick="openEventModal('${e.id}')">
          <td>${formatDate(e.deadline)}</td>
          <td style="font-weight: 600;">${e.title}</td>
          <td>${daysLeft === 0 ? 'Due Today' : daysLeft + ' days left'}</td>
        </tr>
      `;
    }).join('');
  }

  function filterUpcomingEvents(filter) {
    const container = document.getElementById('upcomingEventsList');
    let filtered = allEvents.filter(e => e.status === 'ACTIVE');

    if (filter !== 'ALL') {
      if (filter === 'MEETING') filtered = filtered.filter(e => e.event_type === 'MEETING');
      else if (filter === 'TASK') filtered = filtered.filter(e => e.event_type === 'TASK_DEADLINE');
      else if (filter === 'HACKATHON') filtered = filtered.filter(e => e.event_type === 'HACKATHON');
      else if (filter === 'INTERNSHIP') filtered = filtered.filter(e => e.event_type === 'INTERNSHIP');
      else if (filter === 'CERTIFICATION') filtered = filtered.filter(e => e.event_type === 'CERTIFICATION');
    }

    if (filtered.length === 0) {
      container.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">No matching events found.</td></tr>';
      return;
    }

    container.innerHTML = filtered.map(e => `
      <tr class="event-row" onclick="openEventModal('${e.id}')">
        <td style="font-weight: 600;">${e.title}</td>
        <td><span class="type-pill">${e.event_type}</span></td>
        <td>${formatDate(e.start_datetime || e.deadline)}</td>
        <td>
          ${e.google_event_link ? `<a href="${e.google_event_link}" target="_blank" onclick="event.stopPropagation();" style="color: var(--accent-cyan);">Google Cal ↗</a>` : 'Local Sync'}
        </td>
      </tr>
    `).join('');
  }

  function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    document.getElementById('currentMonthYear').textContent = new Date(year, month).toLocaleDateString('default', { month: 'long', year: 'numeric' });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    const calendarGrid = document.getElementById('calendarGrid');
    
    // Clear days
    const dayCells = calendarGrid.querySelectorAll('.calendar-day-cell');
    dayCells.forEach(cell => cell.remove());

    const todayStr = new Date().toISOString().split('T')[0];

    // Padding cells
    for (let i = 0; i < firstDay; i++) {
      const cell = document.createElement('div');
      cell.className = 'calendar-day-cell other-month';
      calendarGrid.appendChild(cell);
    }

    // Month days
    for (let day = 1; day <= daysInMonth; day++) {
      const cellDateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const cell = document.createElement('div');
      cell.className = 'calendar-day-cell';
      if (cellDateStr === todayStr) cell.classList.add('today');

      cell.textContent = day;

      // Has event?
      const hasEvent = allEvents.some(e => {
        const start = e.start_datetime ? e.start_datetime.split('T')[0] : '';
        const dead = e.deadline ? e.deadline.split('T')[0] : '';
        return (start === cellDateStr || dead === cellDateStr) && e.status === 'ACTIVE';
      });

      if (hasEvent) {
        const dot = document.createElement('div');
        dot.className = 'event-dot';
        cell.appendChild(dot);
      }

      cell.addEventListener('click', () => {
        document.querySelectorAll('.calendar-day-cell').forEach(c => c.classList.remove('selected'));
        cell.classList.add('selected');
        filterEventsByDate(cellDateStr);
      });

      calendarGrid.appendChild(cell);
    }
  }

  function filterEventsByDate(dateStr) {
    const dateEvts = allEvents.filter(e => {
      const start = e.start_datetime ? e.start_datetime.split('T')[0] : '';
      const dead = e.deadline ? e.deadline.split('T')[0] : '';
      return (start === dateStr || dead === dateStr) && e.status === 'ACTIVE';
    });

    const container = document.getElementById('upcomingEventsList');
    if (dateEvts.length === 0) {
      container.innerHTML = `<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">No events found for ${dateStr}</td></tr>`;
      return;
    }

    container.innerHTML = dateEvts.map(e => `
      <tr class="event-row" onclick="openEventModal('${e.id}')">
        <td style="font-weight: 600;">${e.title}</td>
        <td><span class="type-pill">${e.event_type}</span></td>
        <td>${formatDate(e.start_datetime || e.deadline)}</td>
        <td>${e.sync_status}</td>
      </tr>
    `).join('');
  }

  function changeMonth(delta) {
    currentDate.setMonth(currentDate.getMonth() + delta);
    renderCalendar();
  }

  window.openEventModal = function(id) {
    const evt = allEvents.find(e => e.id === id);
    if (!evt) return;

    document.getElementById('modalTitle').textContent = evt.title;
    document.getElementById('modalType').textContent = evt.event_type;
    document.getElementById('modalSource').textContent = `${evt.source_type} (${evt.source_id || 'manual'})`;
    document.getElementById('modalDate').textContent = formatDate(evt.start_datetime || evt.deadline);
    document.getElementById('modalDeadline').textContent = evt.deadline ? formatDate(evt.deadline) : 'None';
    document.getElementById('modalDesc').textContent = evt.description || 'No description provided.';
    document.getElementById('modalLocation').textContent = evt.location || 'N/A';

    const gLinkBtn = document.getElementById('modalGoogleLink');
    if (evt.google_event_link) {
      gLinkBtn.href = evt.google_event_link;
      gLinkBtn.style.display = 'inline-flex';
    } else {
      gLinkBtn.style.display = 'none';
    }

    const cancelBtn = document.getElementById('modalCancelBtn');
    cancelBtn.onclick = async () => {
      if (confirm('Are you sure you want to cancel this event?')) {
        await fetch(`/api/calendar/events/${evt.id}`, { method: 'DELETE' });
        closeModal();
        await fetchEvents();
      }
    };

    document.getElementById('eventModal').classList.add('active');
  };

  function closeModal() {
    document.getElementById('eventModal').classList.remove('active');
  }

  function formatDate(dtStr) {
    if (!dtStr) return 'N/A';
    const d = new Date(dtStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function formatTime(dtStr) {
    if (!dtStr) return 'All Day';
    const d = new Date(dtStr);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }
});
