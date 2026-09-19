/**
 * MCP Service Resolution Assistant - Frontend Logic
 * Implements real-time chat, MCP tool activity visualizer, provider cards, and booking management.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Base API URL configuration
  const API_BASE = (window.location.protocol === 'file:' || window.location.port === '5500' || window.location.port === '5501')
    ? 'http://127.0.0.1:8000'
    : '';

  // DOM Elements
  const chatForm = document.getElementById('chat-form');
  const userInput = document.getElementById('user-input');
  const sendBtn = document.getElementById('send-btn');
  const chatHistory = document.getElementById('chat-history');
  const quickPrompts = document.getElementById('quick-prompts');
  const activityFeed = document.getElementById('activity-feed');
  const activityCountBadge = document.getElementById('activity-count');
  const activityEmptyState = document.getElementById('activity-empty');
  const clearActivityBtn = document.getElementById('clear-activity-btn');
  const appointmentsList = document.getElementById('appointments-list');
  const appointmentsCountBadge = document.getElementById('appointments-count');
  const refreshAppointmentsBtn = document.getElementById('refresh-appointments-btn');
  const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
  const activitySidebar = document.getElementById('activity-sidebar');

  // Landing Page & Navigation Elements (Canva UI Integration)
  const landingView = document.getElementById('landing-view');
  const assistantView = document.getElementById('assistant-view');
  const heroSearchForm = document.getElementById('hero-search-form');
  const heroSearchInput = document.getElementById('hero-search-input');
  const launchAssistantBtn = document.getElementById('launch-assistant-btn');
  const navHomeBtn = document.getElementById('nav-home-btn');

  // Status Indicators
  const mcpStatus = document.getElementById('mcp-status');
  const llmStatus = document.getElementById('llm-status');
  const dbStatus = document.getElementById('db-status');
  const refreshChatBtn = document.getElementById('refresh-chat-btn');

  // Customer Booking Modal Elements (Feature Requirement #3)
  const customerBookingModal = document.getElementById('customer-booking-modal');
  const customerBookingForm = document.getElementById('customer-booking-form');
  const bookingModalCloseBtn = document.getElementById('booking-modal-close-btn');
  const bookingModalCancelBtn = document.getElementById('booking-modal-cancel-btn');
  const modalSummaryProvider = document.getElementById('modal-summary-provider');
  const modalSummarySlot = document.getElementById('modal-summary-slot');
  const custNameInput = document.getElementById('cust-name-input');
  const custPhoneInput = document.getElementById('cust-phone-input');
  const custEmailInput = document.getElementById('cust-email-input');
  const custAddressInput = document.getElementById('cust-address-input');
  const custProblemInput = document.getElementById('cust-problem-input');
  const bookingModalSubmitBtn = document.getElementById('booking-modal-submit-btn');
  const bookingModalError = document.getElementById('booking-modal-error');
  const modalSlotSelect = document.getElementById('modal-slot-select');
  const modalSlotHint = document.getElementById('modal-slot-hint');
  const modalDateInput = document.getElementById('modal-date-input');

  // Cancellation Reason Modal Elements
  const cancellationModal = document.getElementById('cancellation-modal');
  const cancelModalCloseBtn = document.getElementById('cancel-modal-close-btn');
  const cancelModalBackBtn = document.getElementById('cancel-modal-back-btn');
  const cancelAppointmentForm = document.getElementById('cancel-appointment-form');
  const cancelModalApptRef = document.getElementById('cancel-modal-appt-ref');
  const cancelReasonChips = document.getElementById('cancel-reason-chips');
  const cancelReasonInput = document.getElementById('cancel-reason-input');
  const cancelModalError = document.getElementById('cancel-modal-error');
  const cancelModalConfirmBtn = document.getElementById('cancel-modal-confirm-btn');

  let activeCancelAppointmentId = null;
  let activeCancelTriggerBtn = null;
  const cancellingApptIds = new Set();

  // State
  let conversationId = null;
  let toolActivityTotal = 0;
  let pendingBooking = null;
  let bookedSlotsByProvider = {}; // Map of providerId -> Set of booked normalized time slots
  let isTaskRunning = false; // Flag to prevent concurrent tasks/queries

  // UI state manager ensuring single-task execution
  function setTaskRunningState(running) {
    isTaskRunning = Boolean(running);

    if (userInput) {
      userInput.disabled = isTaskRunning;
      if (isTaskRunning) {
        if (!userInput.getAttribute('data-orig-placeholder')) {
          userInput.setAttribute('data-orig-placeholder', userInput.placeholder || 'Describe your issue or confirm a booking...');
        }
        userInput.placeholder = '⏳ Assistant is processing your request... Please wait until this task completes';
      } else {
        const orig = userInput.getAttribute('data-orig-placeholder');
        if (orig) userInput.placeholder = orig;
      }
      const container = userInput.closest('.input-container');
      if (container) {
        if (isTaskRunning) container.classList.add('disabled');
        else container.classList.remove('disabled');
      }
    }

    if (sendBtn) {
      sendBtn.disabled = isTaskRunning;
      sendBtn.title = isTaskRunning ? 'Task in progress... please wait' : 'Send message';
    }

    if (quickPrompts) {
      if (isTaskRunning) quickPrompts.classList.add('disabled');
      else quickPrompts.classList.remove('disabled');
    }

    document.querySelectorAll('.hero-chip, #hero-search-btn').forEach(el => {
      if (isTaskRunning) {
        el.setAttribute('disabled', 'true');
        el.classList.add('disabled');
      } else {
        el.removeAttribute('disabled');
        el.classList.remove('disabled');
      }
    });
  }

  // Slot Availability Helpers (Real-time booked slot reflection)
  function normalizeSlot(slot) {
    if (!slot) return '';
    const s = String(slot).trim().toUpperCase();
    const map = {
      '10:00 AM': '10:00',
      '10:00': '10:00',
      '10 AM': '10:00',
      '12:00 PM': '12:00',
      '12:00': '12:00',
      '12 PM': '12:00',
      '02:00 PM': '14:00',
      '2:00 PM': '14:00',
      '2 PM': '14:00',
      '14:00': '14:00',
      '04:00 PM': '16:00',
      '4:00 PM': '16:00',
      '4 PM': '16:00',
      '16:00': '16:00',
    };
    return map[s] || s;
  }

  function isSlotBooked(providerId, slot) {
    if (!providerId || !slot) return false;
    const pid = String(providerId);
    const norm = normalizeSlot(slot);
    return Boolean(bookedSlotsByProvider[pid] && bookedSlotsByProvider[pid].has(norm));
  }

  const STANDARD_SLOTS_DEF = [
    { value: '10:00 AM', label: '10:00 AM (Morning)' },
    { value: '12:00 PM', label: '12:00 PM (Noon)' },
    { value: '02:00 PM', label: '02:00 PM (Afternoon)' },
    { value: '04:00 PM', label: '04:00 PM (Late Afternoon)' }
  ];

  function buildSlotOptionsHtml(providerId, providerBookedSlots = [], selectedVal = '') {
    const pid = String(providerId);
    if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();
    if (Array.isArray(providerBookedSlots)) {
      providerBookedSlots.forEach(s => bookedSlotsByProvider[pid].add(normalizeSlot(s)));
    }

    return STANDARD_SLOTS_DEF.map(s => {
      const booked = bookedSlotsByProvider[pid].has(normalizeSlot(s.value));
      const isSelected = selectedVal && normalizeSlot(selectedVal) === normalizeSlot(s.value);
      if (booked) {
        return `<option value="${s.value}" disabled class="slot-booked" style="color: #94a3b8; font-style: italic; background-color: #f8fafc;" ${isSelected ? 'selected' : ''}>${s.value} (Booked • Unavailable)</option>`;
      }
      return `<option value="${s.value}" ${isSelected ? 'selected' : ''}>${s.label}</option>`;
    }).join('');
  }

  function refreshAllProviderCardSlots() {
    const selects = document.querySelectorAll('select[id^="slot-select-"]');
    selects.forEach(sel => {
      const pid = sel.id.replace('slot-select-', '');
      const currentVal = sel.value;
      const options = sel.querySelectorAll('option');
      options.forEach(opt => {
        if (!opt.value) return; // skip placeholder
        const booked = isSlotBooked(pid, opt.value);
        const def = STANDARD_SLOTS_DEF.find(d => normalizeSlot(d.value) === normalizeSlot(opt.value));
        const baseLabel = def ? def.label : opt.value;
        if (booked) {
          opt.disabled = true;
          opt.className = 'slot-booked';
          opt.textContent = `${opt.value} (Booked • Unavailable)`;
          opt.style.color = '#94a3b8';
          opt.style.fontStyle = 'italic';
          opt.style.backgroundColor = '#f8fafc';
          if (currentVal && normalizeSlot(currentVal) === normalizeSlot(opt.value)) {
            sel.value = '';
          }
        } else {
          opt.disabled = false;
          opt.className = '';
          opt.textContent = baseLabel;
          opt.style.color = '#0f172a';
          opt.style.fontStyle = 'normal';
          opt.style.backgroundColor = '#ffffff';
        }
      });
    });
  }

  // View Navigation Helpers
  function showAssistantView() {
    if (landingView) landingView.style.display = 'none';
    if (assistantView) {
      assistantView.style.display = 'flex';
      userInput.focus();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function showLandingView() {
    if (assistantView) assistantView.style.display = 'none';
    if (landingView) {
      landingView.style.display = 'flex';
      if (heroSearchInput) heroSearchInput.focus();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (launchAssistantBtn) {
    launchAssistantBtn.addEventListener('click', showAssistantView);
  }

  if (navHomeBtn) {
    navHomeBtn.addEventListener('click', showLandingView);
  }

  // Handle Hero Search Form Submission from Canva Landing Page
  if (heroSearchForm) {
    heroSearchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      if (isTaskRunning) return;
      const query = heroSearchInput ? heroSearchInput.value.trim() : '';
      if (!query) return;

      // Switch to Assistant Workspace and forward query
      showAssistantView();
      userInput.value = query;
      heroSearchInput.value = '';
      chatForm.dispatchEvent(new Event('submit'));
    });
  }

  // Handle Quick Chips on Canva Landing Page
  document.querySelectorAll('.hero-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      if (isTaskRunning) return;
      const query = chip.getAttribute('data-query');
      if (query) {
        showAssistantView();
        userInput.value = query;
        chatForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  // Initialize
  checkSystemHealth();
  loadAppointments();
  loadCatalog();

  if (refreshChatBtn) {
    refreshChatBtn.addEventListener('click', () => {
      resetWorkspace();
    });
  }

  // --------------------------------------------------------------------------
  // System Health Check
  // --------------------------------------------------------------------------
  async function checkSystemHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        if (mcpStatus) {
          mcpStatus.querySelector('.status-label').textContent = `MCP: ${data.mcp_server || 'Active'}`;
        }
        if (llmStatus) {
          if (data.active_backend === 'groq') {
            llmStatus.querySelector('.status-label').textContent = `Groq: Active (Fallback)`;
            llmStatus.style.borderColor = 'rgba(245, 158, 11, 0.4)';
          } else {
            const fallbackTxt = data.groq_fallback === 'configured' ? ' (Groq Standby)' : '';
            llmStatus.querySelector('.status-label').textContent = `Gemini: Ready${fallbackTxt}`;
          }
        }
        if (dbStatus) {
          dbStatus.querySelector('.status-label').textContent = `SQLite: ${data.providers_loaded} Providers`;
        }
      }
    } catch (err) {
      console.warn('Health check failed:', err);
    }
  }

  // --------------------------------------------------------------------------
  // Chat Submission Handler
  // --------------------------------------------------------------------------
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (isTaskRunning) return;
    const message = userInput.value.trim();
    if (!message) return;

    // Lock UI to prevent concurrent queries/tasks
    setTaskRunningState(true);

    // Append User Message
    appendUserMessage(message);
    userInput.value = '';
    userInput.style.height = 'auto';

    // Show Typing Indicator
    const typingIndicator = showTypingIndicator();

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          conversation_id: conversationId,
        }),
      });

      typingIndicator.remove();

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      conversationId = data.conversation_id;

      // Update LLM status indicator if fallback took effect
      if (llmStatus && data.backend === 'groq') {
        llmStatus.querySelector('.status-label').textContent = 'Groq: Active (Fallback)';
        llmStatus.style.borderColor = 'rgba(245, 158, 11, 0.5)';
      }

      // Render Assistant Response with Receipt support
      appendAssistantMessage(data.response, data.providers, data.receipt);

      // Render Tool Activities (STEP 23)
      if (data.tool_activities && data.tool_activities.length > 0) {
        renderToolActivities(data.tool_activities);
      }

      // Refresh appointments list if booking or cancellation occurred
      if (data.receipt || (data.tool_activities && data.tool_activities.some(a => a.tool === 'schedule_appointment' || a.tool === 'cancel_appointment'))) {
        loadAppointments();
      }

    } catch (err) {
      if (typingIndicator) typingIndicator.remove();
      appendAssistantMessage(
        "I'm sorry, an error occurred while connecting to the assistant. Please ensure the server is running and try again."
      );
      console.error('Chat error:', err);
    } finally {
      // Re-enable input and UI when the task completes
      setTaskRunningState(false);
      userInput.focus();
    }
  });

  // Handle Enter key in textarea (Shift+Enter for newline)
  userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isTaskRunning) return;
      chatForm.dispatchEvent(new Event('submit'));
    }
  });

  // Auto-grow textarea
  userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
  });

  // --------------------------------------------------------------------------
  // Message Rendering
  // --------------------------------------------------------------------------
  function appendUserMessage(text) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user-wrapper';

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    wrapper.innerHTML = `
      <div class="avatar user-avatar">👤</div>
      <div class="message-bubble user-bubble">
        <div class="bubble-header">
          <span class="sender-name">You</span>
          <span class="message-time">${now}</span>
        </div>
        <div class="bubble-content">
          <p>${escapeHtml(text)}</p>
        </div>
      </div>
    `;

    chatHistory.appendChild(wrapper);
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  function appendAssistantMessage(text, providers = [], receipt = null) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper assistant-wrapper';

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const formattedHtml = formatMarkdown(text);

    let providersHtml = '';
    if (providers && providers.length > 0) {
      providersHtml = `
        <div class="providers-grid">
          ${providers.map((p) => {
            const encodedProvider = encodeURIComponent(JSON.stringify(p));
            return `
            <div class="provider-card">
              <div class="provider-card-header">
                <div>
                  <span class="provider-name">${escapeHtml(p.name)}</span>
                  <span class="provider-cat-tag">${escapeHtml(p.category || 'Service')}</span>
                </div>
                <div class="provider-rating-badge">
                  ★ ${p.rating || '4.5'}
                </div>
              </div>

              <div class="provider-details-grid">
                <div class="detail-item">
                  <span class="detail-label">Location:</span>
                  <span class="detail-value">📍 ${escapeHtml(p.location || 'Goa')}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Price Range:</span>
                  <span class="detail-value price-val">${escapeHtml(p.price || `₹${p.price_min || 500}–₹${p.price_max || 1000}`)}</span>
                </div>
                ${p.phone ? `
                <div class="detail-item">
                  <span class="detail-label">Contact:</span>
                  <span class="detail-value">📞 ${escapeHtml(p.phone)}</span>
                </div>` : ''}
                ${p.provider_score ? `
                <div class="detail-item">
                  <span class="detail-label">Strategy Score:</span>
                  <span class="provider-score-badge">⚡ ${p.provider_score}/100</span>
                </div>` : ''}
              </div>

              ${p.description ? `
                <p class="provider-card-desc" title="${escapeHtml(p.description)}">${escapeHtml(p.description)}</p>
              ` : ''}

              <!-- Time Slot Selectbox -->
              <div class="card-slot-box">
                <label class="slot-select-label" for="slot-select-${p.id}">Select Time Slot:</label>
                <div class="slot-select-container">
                  <select id="slot-select-${p.id}" class="time-slot-select" onchange="window.onSlotSelectChange(${p.id}, '${escapeHtml(p.name)}', this.value)">
                    <option value="">-- Choose Time Slot --</option>
                    ${buildSlotOptionsHtml(p.id, p.booked_slots)}
                  </select>
                </div>
              </div>

              <div class="provider-actions">
                <button class="btn-card btn-card-primary" onclick="window.bookProviderWithSlot(${p.id}, '${escapeHtml(p.name)}')">Confirm & Book</button>
                <button class="btn-card btn-card-secondary" onclick="window.viewProviderDetails('${encodedProvider}')">Details</button>
              </div>
            </div>
          `;
          }).join('')}
        </div>
      `;
    }

    // Appointment Confirmation Receipt Card
    let receiptHtml = '';
    if (receipt && receipt.appointment_id) {
      receiptHtml = `
        <div class="receipt-card" id="receipt-card-${receipt.appointment_id}">
          <div class="receipt-card-header">
            <span class="receipt-badge">RECEIPT CONFIRMED</span>
            <span class="receipt-id">#APPT-${escapeHtml(String(receipt.appointment_id))}</span>
          </div>
          <div class="receipt-grid">
            <div class="receipt-row">
              <span class="receipt-label">Customer Name:</span>
              <span class="receipt-val"><strong>${escapeHtml(receipt.customer_name || 'Valued Customer')}</strong> ${receipt.customer_phone ? `<span style="color: #64748b; font-size: 0.85rem;">(${escapeHtml(receipt.customer_phone)})</span>` : ''}</span>
            </div>
            ${receipt.customer_email ? `
            <div class="receipt-row">
              <span class="receipt-label">Customer Email:</span>
              <span class="receipt-val">✉️ ${escapeHtml(receipt.customer_email)}</span>
            </div>` : ''}
            ${receipt.customer_address ? `
            <div class="receipt-row">
              <span class="receipt-label">Service Address:</span>
              <span class="receipt-val">📍 ${escapeHtml(receipt.customer_address)}</span>
            </div>` : ''}
            <div class="receipt-row">
              <span class="receipt-label">Service Provider:</span>
              <span class="receipt-val"><strong>${escapeHtml(receipt.provider || receipt.provider_name || 'Service Partner')}</strong></span>
            </div>
            <div class="receipt-row">
              <span class="receipt-label">Provider's Phone No:</span>
              <span class="receipt-val phone-highlight">📞 ${escapeHtml(receipt.provider_phone || '+91 98765 43210')}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-label">Problem / Issue:</span>
              <span class="receipt-val">${escapeHtml(receipt.problem || receipt.issue || 'Appliance repair')}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-label">Scheduled Date:</span>
              <span class="receipt-val">📅 ${escapeHtml(receipt.date || '2026-09-17')}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-label">Time Slot:</span>
              <span class="receipt-val time-highlight">⏰ ${escapeHtml(receipt.time_slot || receipt.time || '10:00 AM')}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-label">Booking Status:</span>
              <span class="receipt-status-pill confirmed">● Confirmed</span>
            </div>
          </div>

          <!-- Live Chat with Assigned Technician (Visible once accepted) -->
          <div class="customer-job-chat-box" id="customer-chat-box-${receipt.appointment_id}" style="${['accepted', 'en_route', 'arrived', 'in_progress'].includes(receipt.status) ? 'display: flex;' : 'display: none;'}">
            <div class="chat-box-header">
              <span>💬 Direct Chat with Technician (<strong id="chat-tech-name-${receipt.appointment_id}">${escapeHtml(receipt.technician_name || 'Assigned Partner')}</strong>)</span>
              <span style="font-size: 0.72rem; color: #34d399;">● Online</span>
            </div>
            <div class="customer-chat-messages" id="customer-chat-msgs-${receipt.appointment_id}">
              <div class="chat-placeholder">Technician assigned! Send a message below to coordinate directions or landmark.</div>
            </div>
            <form class="customer-chat-form" onsubmit="window.sendCustomerMessage(event, ${receipt.appointment_id}, '${escapeHtml(receipt.customer_name || 'Customer')}')">
              <input type="text" id="customer-chat-input-${receipt.appointment_id}" class="customer-chat-input" placeholder="Type message to technician..." autocomplete="off" required />
              <button type="submit" class="customer-chat-send-btn">Send</button>
            </form>
          </div>

          <div class="receipt-footer">
            <span class="receipt-note">Need to make changes?</span>
            <button class="btn-cancel-receipt" data-cancel-id="${receipt.appointment_id}">✕ Cancel Appointment</button>
          </div>
        </div>
      `;
    }

    // Embed Provider Cards directly inside the combined Recommended Providers & Scheduling section
    let finalContentHtml = formattedHtml;
    if (providersHtml) {
      const headingMatch = finalContentHtml.match(/(<h3 class="md-heading">[^<]*(?:Recommended Providers|Scheduling|Next Step)[^<]*<\/h3>)/i);
      if (headingMatch) {
        const heading = headingMatch[1];
        const headingIdx = finalContentHtml.indexOf(heading);
        const afterHeading = finalContentHtml.substring(headingIdx + heading.length);

        // If there is an introductory recommendation paragraph, insert cards right after it; otherwise right after the heading
        const firstPMatch = afterHeading.match(/^(\s*<p>.*?<\/p>)/is);
        if (firstPMatch) {
          const insertPos = headingIdx + heading.length + firstPMatch[1].length;
          finalContentHtml = finalContentHtml.substring(0, insertPos) + providersHtml + finalContentHtml.substring(insertPos);
        } else {
          const insertPos = headingIdx + heading.length;
          finalContentHtml = finalContentHtml.substring(0, insertPos) + providersHtml + finalContentHtml.substring(insertPos);
        }
      } else {
        finalContentHtml += providersHtml;
      }
    }

    if (receiptHtml) {
      finalContentHtml += receiptHtml;
    }

    // Two-Step Flow: Detect follow-up question asking if user wants nearby verified technicians
    const isFollowUpQuestion = /nearby.*technician|technician.*nearby|inspect and fix this for you|find verified.*|would you like us to provide local service|technician to come/i.test(text);
    if (isFollowUpQuestion && (!providers || providers.length === 0) && !receiptHtml) {
      finalContentHtml += `
        <div class="follow-up-actions-bar">
          <button type="button" class="follow-up-chip follow-up-chip-primary" onclick="window.triggerFollowUpChoice(true)">
            ✓ Yes
          </button>
          <button type="button" class="follow-up-chip follow-up-chip-secondary" onclick="window.triggerFollowUpChoice(false)">
            No
          </button>
        </div>
      `;
    }

    wrapper.innerHTML = `
      <div class="avatar assistant-avatar">🤖</div>
      <div class="message-bubble assistant-bubble">
        <div class="bubble-header">
          <span class="sender-name">Service Assistant</span>
          <span class="message-time">${now}</span>
        </div>
        <div class="bubble-content">
          ${finalContentHtml}
        </div>
      </div>
    `;

    chatHistory.appendChild(wrapper);
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  function showTypingIndicator() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper assistant-wrapper typing-wrapper';
    wrapper.innerHTML = `
      <div class="avatar assistant-avatar">🤖</div>
      <div class="message-bubble assistant-bubble">
        <div class="typing-indicator">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    `;
    chatHistory.appendChild(wrapper);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return wrapper;
  }

  // --------------------------------------------------------------------------
  // Tool Activities Visualizer (STEP 23)
  // --------------------------------------------------------------------------
  function renderToolActivities(activities) {
    if (activityEmptyState) {
      activityEmptyState.style.display = 'none';
    }

    activities.forEach(act => {
      toolActivityTotal++;
      activityCountBadge.textContent = toolActivityTotal;

      const card = document.createElement('div');
      card.className = 'activity-card';

      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      card.innerHTML = `
        <div class="activity-card-header">
          <span class="activity-tool-name">✓ ${escapeHtml(act.tool)}</span>
          <span class="activity-status-tag">${time}</span>
        </div>
        <div class="activity-summary">${escapeHtml(act.summary)}</div>
      `;

      // Prepend so latest tool calls appear on top
      activityFeed.insertBefore(card, activityFeed.firstChild);
    });
  }

  // Clear Activity
  clearActivityBtn.addEventListener('click', () => {
    activityFeed.innerHTML = `
      <div class="empty-state" id="activity-empty">
        <span class="empty-icon">🔌</span>
        <p>Activity cleared. New MCP tool calls will appear here.</p>
      </div>
    `;
    toolActivityTotal = 0;
    activityCountBadge.textContent = '0';
  });

  // --------------------------------------------------------------------------
  // Scheduled Appointments (STEP 21 & STEP 13)
  // --------------------------------------------------------------------------
  async function loadAppointments() {
    try {
      const res = await fetch(`${API_BASE}/appointments?_t=${Date.now()}`);
      if (res.ok) {
        const appts = await res.json();
        appointmentsCountBadge.textContent = appts.length;

        // Update global booked slots state from confirmed appointments
        bookedSlotsByProvider = {};
        appts.forEach(a => {
          if (a.status === 'confirmed' && a.provider_id) {
            const pid = String(a.provider_id);
            if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();
            bookedSlotsByProvider[pid].add(normalizeSlot(a.time_slot || a.time));
          }
        });
        refreshAllProviderCardSlots();
        if (pendingBooking && customerBookingModal && customerBookingModal.classList.contains('open') && typeof updateModalSlotUI === 'function') {
          updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
        }

        if (appts.length === 0) {
          appointmentsList.innerHTML = `
            <div class="empty-state">
              <span class="empty-icon">📅</span>
              <p>No appointments booked yet.</p>
            </div>
          `;
          return;
        }

        appointmentsList.innerHTML = appts.map(a => `
          <div class="appointment-item">
            <div class="appointment-header">
              <span class="appointment-id">#APPT-${a.id}</span>
              <span class="appointment-status ${a.status === 'confirmed' ? 'status-confirmed' : 'status-cancelled'}">
                ${escapeHtml(a.status)}
              </span>
            </div>
            <div class="appointment-provider">${escapeHtml(a.provider_name || 'Service Partner')}</div>
            ${a.provider_phone ? `<div class="appointment-meta"><span>📞 Provider: ${escapeHtml(a.provider_phone)}</span></div>` : ''}
            <div class="appointment-meta">
              <span>📅 ${escapeHtml(a.date)}</span>
              <span>⏰ ${escapeHtml(a.time_slot || a.time || '10:00 AM')}</span>
            </div>
            ${a.problem || a.issue ? `<div class="appointment-meta"><span>🔧 Issue: ${escapeHtml(a.problem || a.issue)}</span></div>` : ''}
            ${a.customer_name ? `<div class="appointment-meta"><span>👤 Customer: <strong>${escapeHtml(a.customer_name)}</strong> ${a.customer_phone ? `<span style="color: #64748b;">(${escapeHtml(a.customer_phone)})</span>` : ''}</span></div>` : ''}
            ${a.customer_address ? `<div class="appointment-meta"><span>📍 ${escapeHtml(a.customer_address)}</span></div>` : ''}
            ${a.status === 'cancelled' && a.cancellation_reason ? `<div class="appointment-meta" style="color: #dc2626; font-size: 0.75rem;"><span>✕ Reason: ${escapeHtml(a.cancellation_reason)}</span></div>` : ''}
            ${a.status === 'confirmed' ? `
              <button class="btn-cancel-appt" data-cancel-id="${a.id}">✕ Cancel Appointment</button>
            ` : ''}
          </div>
        `).join('');
      }
    } catch (err) {
      console.warn('Could not load appointments:', err);
    }
  }

  refreshAppointmentsBtn.addEventListener('click', loadAppointments);

  // --------------------------------------------------------------------------
  // Catalog & Tools Loader (Feature Requirement #1)
  // --------------------------------------------------------------------------
  async function loadCatalog() {
    const catalogPane = document.getElementById('content-catalog');
    if (!catalogPane) return;
    try {
      const res = await fetch(`${API_BASE}/catalog?_t=${Date.now()}`);
      if (res.ok) {
        const data = await res.json();
        const stats = data.stats || {};
        const categories = data.categories || [];
        const tools = data.tools || [];
        const resources = data.resources || [];

        catalogPane.innerHTML = `
          <div class="sidebar-header">
            <h2 class="sidebar-title">MCP Tools & Resources</h2>
            <button class="refresh-btn" id="refresh-catalog-btn" title="Refresh catalog">↻</button>
          </div>
          <div class="catalog-content">
            <!-- Live Metrics Banner -->
            <div class="modal-score-card" style="margin-bottom: 14px;">
              <div class="score-card-title">⚡ Service Network Stats</div>
              <div class="score-breakdown-grid">
                <div class="score-breakdown-item">
                  <div class="score-breakdown-label">Providers</div>
                  <div class="score-breakdown-val">${stats.total_providers || 0}</div>
                </div>
                <div class="score-breakdown-item">
                  <div class="score-breakdown-label">Bookings</div>
                  <div class="score-breakdown-val">${stats.active_bookings || 0}</div>
                </div>
                <div class="score-breakdown-item">
                  <div class="score-breakdown-label">Customers</div>
                  <div class="score-breakdown-val">${stats.total_customers || 0}</div>
                </div>
              </div>
            </div>

            <h3 class="catalog-section-title">Verified Categories in DB</h3>
            <ul class="catalog-list" style="margin-bottom: 14px;">
              ${categories.map(c => `
                <li><code>${escapeHtml(c.category)}</code> <span>${c.count} verified partners</span></li>
              `).join('')}
            </ul>

            <h3 class="catalog-section-title">Registered MCP Tools</h3>
            <ul class="catalog-list" style="margin-bottom: 14px;">
              ${tools.map(t => `
                <li><code>${escapeHtml(t.name)}</code> <span>${escapeHtml(t.desc)}</span></li>
              `).join('')}
            </ul>

            <h3 class="catalog-section-title">Registered MCP Resources</h3>
            <ul class="catalog-list">
              ${resources.map(r => `
                <li><code>${escapeHtml(r.uri)}</code> <span>${escapeHtml(r.desc)}</span></li>
              `).join('')}
            </ul>
          </div>
        `;

        const refreshCatalogBtn = document.getElementById('refresh-catalog-btn');
        if (refreshCatalogBtn) {
          refreshCatalogBtn.addEventListener('click', loadCatalog);
        }
      }
    } catch (err) {
      console.warn('Could not load catalog:', err);
    }
  }

  // --------------------------------------------------------------------------
  // Workspace Refresh / Reset (Feature Requirement #1)
  // --------------------------------------------------------------------------
  function resetWorkspace() {
    // 1. Reset chat history to clean initial greeting
    chatHistory.innerHTML = `
      <div class="message-wrapper assistant-wrapper">
        <div class="avatar assistant-avatar">🤖</div>
        <div class="message-bubble assistant-bubble">
          <div class="bubble-header">
            <span class="sender-name">Service Assistant</span>
            <span class="message-time">Just now</span>
          </div>
          <div class="bubble-content">
            <p>Hello! I am your <strong>MCP Service Resolution Assistant</strong>. What service or repair do you need help with today?</p>
            <p class="bubble-hint">I can diagnose issues, query verified local providers, compare ratings & pricing, check real-time slots, and schedule appointments.</p>
          </div>
        </div>
      </div>
    `;

    // 2. Clear conversation state
    conversationId = null;
    if (userInput) userInput.value = '';

    // 3. Clear MCP tool activity feed and counter
    toolActivityTotal = 0;
    if (activityCountBadge) activityCountBadge.textContent = '0';
    if (activityFeed) {
      activityFeed.innerHTML = `
        <div class="empty-state" id="activity-empty">
          <span class="empty-icon">⚡</span>
          <p>No tool calls executed yet in this session.</p>
        </div>
      `;
    }

    // 4. Reload appointments from SQLite
    loadAppointments();

    // 5. Reload catalog & stats
    loadCatalog();
  }

  // Modal Dialog Elements & Handlers (STEP 22)
  const providerModal = document.getElementById('provider-modal');
  const modalProviderName = document.getElementById('modal-provider-name');
  const modalProviderCategory = document.getElementById('modal-provider-category');
  const modalProviderBody = document.getElementById('modal-provider-body');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalCancelBtn = document.getElementById('modal-cancel-btn');
  const modalCheckSlotsBtn = document.getElementById('modal-check-slots-btn');
  const modalSelectBtn = document.getElementById('modal-select-btn');

  let activeModalProvider = null;

  function closeModal() {
    if (providerModal) {
      providerModal.classList.remove('open');
      providerModal.setAttribute('aria-hidden', 'true');
    }
    activeModalProvider = null;
  }

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', closeModal);
  }

  if (modalCancelBtn) {
    modalCancelBtn.addEventListener('click', closeModal);
  }

  if (providerModal) {
    providerModal.addEventListener('click', (e) => {
      if (e.target === providerModal) closeModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && providerModal && providerModal.classList.contains('open')) {
      closeModal();
    }
  });

  if (modalCheckSlotsBtn) {
    modalCheckSlotsBtn.addEventListener('click', () => {
      if (activeModalProvider) {
        const name = activeModalProvider.name;
        closeModal();
        window.checkSlotsFor(name);
      }
    });
  }

  if (modalSelectBtn) {
    modalSelectBtn.addEventListener('click', () => {
      if (activeModalProvider) {
        const name = activeModalProvider.name;
        closeModal();
        window.selectProvider(name);
      }
    });
  }

  // --------------------------------------------------------------------------
  // Quick Prompt Chips
  // --------------------------------------------------------------------------
  quickPrompts.addEventListener('click', (e) => {
    if (isTaskRunning) return;
    const chip = e.target.closest('.prompt-chip');
    if (!chip) return;
    const prompt = chip.getAttribute('data-prompt');
    if (prompt) {
      userInput.value = prompt;
      chatForm.dispatchEvent(new Event('submit'));
    }
  });

  // --------------------------------------------------------------------------
  // Sidebar Tabs
  // --------------------------------------------------------------------------
  const tabButtons = document.querySelectorAll('.sidebar-tab');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(btn.getAttribute('data-tab'));
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Mobile Sidebar Toggle
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener('click', () => {
      activitySidebar.classList.toggle('open');
    });
  }

  // --------------------------------------------------------------------------
  // Helper Formatters
  // --------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Headings (### and ##)
    html = html.replace(/^###\s+(.*$)/gim, '<h3 class="md-heading">$1</h3>');
    html = html.replace(/^##\s+(.*$)/gim, '<h3 class="md-heading">$1</h3>');

    // Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic (*text*)
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

    // Convert any [Cancel Appointment] or [Cancel Appointment #X] in markdown into real buttons
    html = html.replace(/\[Cancel Appointment(?:\s*#?(\d+))?\]/gi, (match, p1) => {
      const id = p1 || '';
      return `<button class="btn-cancel-receipt cancel-inline-btn" ${id ? `data-cancel-id="${id}"` : ''}>✕ Cancel Appointment${id ? ' #' + id : ''}</button>`;
    });

    // Parse Markdown tables (| Header 1 | Header 2 | ... \n |---|---| ... \n | Val 1 | Val 2 |)
    html = html.replace(/(?:(?:^[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$)){2,})/gim, (tableBlock) => {
      const lines = tableBlock.trim().split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      if (lines.length < 2) return tableBlock;

      let separatorIdx = -1;
      for (let i = 1; i < lines.length; i++) {
        if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[i])) {
          separatorIdx = i;
          break;
        }
      }
      if (separatorIdx === -1) return tableBlock;

      const headerLines = lines.slice(0, separatorIdx);
      const rowLines = lines.slice(separatorIdx + 1);

      const parseCells = (line) => {
        let trimmed = line.replace(/^\|\s*/, '').replace(/\s*\|$/, '');
        return trimmed.split('|').map(c => c.trim());
      };

      let tableHtml = '<div class="table-responsive"><table class="md-table">';
      if (headerLines.length > 0) {
        tableHtml += '<thead>';
        headerLines.forEach(hLine => {
          const cells = parseCells(hLine);
          tableHtml += '<tr>' + cells.map(c => `<th>${c}</th>`).join('') + '</tr>';
        });
        tableHtml += '</thead>';
      }

      if (rowLines.length > 0) {
        tableHtml += '<tbody>';
        rowLines.forEach(rLine => {
          if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(rLine)) return;
          const cells = parseCells(rLine);
          tableHtml += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
        });
        tableHtml += '</tbody>';
      }

      tableHtml += '</table></div>';
      return '\n' + tableHtml + '\n';
    });

    // Numbered lists (1. Item)
    html = html.replace(/^\s*\d+\.\s+(.*)$/gim, '<li class="num-li">$1</li>');

    // Bullet list items (* or - or •)
    html = html.replace(/^\s*[-*•]\s+(.*)$/gim, '<li>$1</li>');

    // Wrap consecutive list items into <ul>
    html = html.replace(/((?:<li(?: class="num-li")?>.*?<\/li>\s*)+)/gis, '<ul>$1</ul>');

    // Strip newlines directly adjacent to list, table, and heading tags
    html = html.replace(/\n\s*<ul>/gis, '<ul>');
    html = html.replace(/<\/ul>\s*\n/gis, '</ul>');
    html = html.replace(/\n\s*<h3/gis, '<h3');
    html = html.replace(/<\/h3>\s*\n/gis, '</h3>');
    html = html.replace(/\n\s*(<div class="table-responsive">)/gis, '$1');
    html = html.replace(/(<\/div>)\s*\n/gis, '$1');

    // Paragraph breaks for double newlines
    html = html.replace(/\n{2,}/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Clean up empty line breaks next to headings, lists, and tables
    html = html.replace(/<br\s*\/?>\s*(<h3|<ul|<div class="table-responsive")/gi, '$1');
    html = html.replace(/(<\/h3>|<\/ul>|<\/div>)\s*<br\s*\/?>/gi, '$1');
    html = html.replace(/<\/li>\s*<br\s*\/?>/gi, '</li>');
    html = html.replace(/(<br\s*\/?>){2,}/gi, '<br>');

    // Clean up empty <p> wrapping around <h3>, <ul>, or <div>
    html = html.replace(/<p>\s*(<h3[^>]*>.*?<\/h3>)\s*<\/p>/gis, '$1');
    html = html.replace(/<p>\s*(<ul[^>]*>.*?<\/ul>)\s*<\/p>/gis, '$1');
    html = html.replace(/<p>\s*(<div class="table-responsive">.*?<\/div>)\s*<\/p>/gis, '$1');
    html = html.replace(/<p>\s*<\/p>/gis, '');

    return `<p>${html}</p>`;
  }

  // --------------------------------------------------------------------------
  // Global Handlers
  // --------------------------------------------------------------------------
  window.viewProviderDetails = function(encodedJson) {
    try {
      const p = JSON.parse(decodeURIComponent(encodedJson));
      activeModalProvider = p;

      modalProviderName.textContent = p.name || 'Provider Details';
      modalProviderCategory.textContent = `${p.category || 'Home Services'} • ★ ${p.rating || '4.5'}`;

      modalProviderBody.innerHTML = `
        <div class="modal-score-card">
          <div class="score-card-title">⚡ MCP Provider Strategy Scoring (STEP 25)</div>
          <div style="font-size: 0.88rem; color: #f8fafc; font-weight: 600;">
            Composite Score: ${p.provider_score || 90}/100
          </div>
          <div class="score-breakdown-grid">
            <div class="score-breakdown-item">
              <div class="score-breakdown-label">Rating (40%)</div>
              <div class="score-breakdown-val">${p.rating_score || 36}/40</div>
            </div>
            <div class="score-breakdown-item">
              <div class="score-breakdown-label">Price (30%)</div>
              <div class="score-breakdown-val">${p.price_score || 25}/30</div>
            </div>
            <div class="score-breakdown-item">
              <div class="score-breakdown-label">Availability (30%)</div>
              <div class="score-breakdown-val">${p.availability_score || 30}/30</div>
            </div>
          </div>
        </div>

        <div class="modal-meta-row">
          <span>Service Category:</span>
          <strong>${escapeHtml(p.category || 'Service')}</strong>
        </div>
        <div class="modal-meta-row">
          <span>Location:</span>
          <strong>📍 ${escapeHtml(p.location || 'Goa')}</strong>
        </div>
        <div class="modal-meta-row">
          <span>Price Estimate:</span>
          <strong style="color: #38bdf8;">${escapeHtml(p.price || `₹${p.price_min || 500}–₹${p.price_max || 1000}`)}</strong>
        </div>
        ${p.phone ? `
        <div class="modal-meta-row">
          <span>Phone:</span>
          <strong>📞 ${escapeHtml(p.phone)}</strong>
        </div>` : ''}
        ${p.description ? `
        <div style="margin-top: 4px;">
          <span style="font-size: 0.78rem; color: var(--text-secondary); text-transform: uppercase;">Overview:</span>
          <p class="modal-description">${escapeHtml(p.description)}</p>
        </div>` : ''}
      `;

      providerModal.classList.add('open');
      providerModal.setAttribute('aria-hidden', 'false');
    } catch (e) {
      console.error('Error opening provider details:', e);
    }
  };

  // --------------------------------------------------------------------------
  // Cancellation Reason Modal & Execution Handlers
  // --------------------------------------------------------------------------
  function closeCancellationModal() {
    if (cancellationModal) {
      cancellationModal.classList.remove('open');
      cancellationModal.setAttribute('aria-hidden', 'true');
    }
    if (cancelReasonInput) cancelReasonInput.value = '';
    if (cancelModalError) {
      cancelModalError.style.display = 'none';
      cancelModalError.textContent = '';
    }
    const chips = cancelReasonChips ? cancelReasonChips.querySelectorAll('.reason-chip') : [];
    chips.forEach(c => c.classList.remove('selected'));
    activeCancelAppointmentId = null;
    activeCancelTriggerBtn = null;
  }

  if (cancelModalCloseBtn) cancelModalCloseBtn.addEventListener('click', closeCancellationModal);
  if (cancelModalBackBtn) cancelModalBackBtn.addEventListener('click', closeCancellationModal);
  if (cancellationModal) {
    cancellationModal.addEventListener('click', (e) => {
      if (e.target === cancellationModal) closeCancellationModal();
    });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && cancellationModal && cancellationModal.classList.contains('open')) {
      closeCancellationModal();
    }
  });

  if (cancelReasonChips) {
    cancelReasonChips.addEventListener('click', (e) => {
      const chip = e.target.closest('.reason-chip');
      if (!chip) return;
      const wasSelected = chip.classList.contains('selected');
      cancelReasonChips.querySelectorAll('.reason-chip').forEach(c => c.classList.remove('selected'));
      if (!wasSelected) {
        chip.classList.add('selected');
        if (cancelReasonInput) cancelReasonInput.value = chip.getAttribute('data-reason') || chip.textContent.trim();
      } else {
        if (cancelReasonInput) cancelReasonInput.value = '';
      }
    });
  }

  window.openCancellationModal = function(appointmentId, triggerBtn = null) {
    let id = parseInt(String(appointmentId).replace(/\D/g, ''), 10);
    if (!id || isNaN(id)) {
      alert('Unable to identify appointment ID to cancel.');
      return;
    }
    activeCancelAppointmentId = id;
    activeCancelTriggerBtn = triggerBtn;

    if (cancelModalApptRef) {
      cancelModalApptRef.textContent = `#APPT-${id}`;
    }
    if (cancelReasonInput) cancelReasonInput.value = '';
    if (cancelModalError) {
      cancelModalError.style.display = 'none';
      cancelModalError.textContent = '';
    }
    if (cancelReasonChips) {
      cancelReasonChips.querySelectorAll('.reason-chip').forEach(c => c.classList.remove('selected'));
    }
    if (cancelModalConfirmBtn) {
      cancelModalConfirmBtn.disabled = false;
      cancelModalConfirmBtn.textContent = '✕ Confirm Cancellation';
    }

    if (cancellationModal) {
      cancellationModal.classList.add('open');
      cancellationModal.setAttribute('aria-hidden', 'false');
      if (cancelReasonInput) setTimeout(() => cancelReasonInput.focus(), 60);
    }
  };

  if (cancelAppointmentForm) {
    cancelAppointmentForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeCancelAppointmentId) return;

      const selectedChip = cancelReasonChips ? cancelReasonChips.querySelector('.reason-chip.selected') : null;
      const chipReason = selectedChip ? selectedChip.getAttribute('data-reason') : '';
      const customReason = cancelReasonInput ? cancelReasonInput.value.trim() : '';
      const finalReason = customReason || chipReason || 'Customer request';

      if (cancelModalConfirmBtn) {
        cancelModalConfirmBtn.disabled = true;
        cancelModalConfirmBtn.textContent = '⏳ Cancelling...';
      }

      const apptId = activeCancelAppointmentId;
      const trigBtn = activeCancelTriggerBtn;

      closeCancellationModal();
      await window.executeAppointmentCancellation(apptId, finalReason, trigBtn);
    });
  }

  window.executeAppointmentCancellation = async function(appointmentId, reason = 'Customer request', triggerBtn = null) {
    const id = parseInt(String(appointmentId).replace(/\D/g, ''), 10);
    if (!id || isNaN(id)) return;

    // Prevent duplicate in-flight cancellation calls (solves double cancellation message)
    if (cancellingApptIds.has(id)) return;
    cancellingApptIds.add(id);

    const allRelatedBtns = document.querySelectorAll(
      `button[data-cancel-id="${id}"], #receipt-card-${id} .btn-cancel-receipt, .appointment-item button[onclick*="${id}"]`
    );

    if (triggerBtn) {
      triggerBtn.disabled = true;
      triggerBtn.innerHTML = '⏳ Cancelling...';
    }
    allRelatedBtns.forEach(b => {
      b.disabled = true;
      b.innerHTML = '⏳ Cancelling...';
    });

    try {
      let res = await fetch(`${API_BASE}/cancel-appointment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ appointment_id: id, reason: reason }),
      });

      if (!res.ok) {
        res = await fetch(`${API_BASE}/appointments/${id}`, { method: 'DELETE' });
      }

      if (res.ok || res.status === 200) {
        // 1. Visually update ANY receipt card for this appointment in chat
        const receiptCard = document.getElementById(`receipt-card-${id}`);
        if (receiptCard) {
          const badge = receiptCard.querySelector('.receipt-badge');
          if (badge) {
            badge.textContent = 'APPOINTMENT CANCELLED';
            badge.style.background = '#dc2626';
          }
          const statusPill = receiptCard.querySelector('.receipt-status-pill');
          if (statusPill) {
            statusPill.className = 'receipt-status-pill cancelled';
            statusPill.textContent = '✕ Cancelled';
          }
          const footer = receiptCard.querySelector('.receipt-footer');
          if (footer) {
            footer.innerHTML = `
              <span class="receipt-note">Booking cancelled</span>
              <span class="cancellation-confirmed-tag" title="Reason: ${escapeHtml(reason)}">✕ Cancelled (${escapeHtml(reason)})</span>
            `;
          }
        }

        // 2. Update any trigger buttons
        allRelatedBtns.forEach(b => {
          b.disabled = true;
          b.classList.add('cancelled');
          b.innerHTML = '✕ Cancelled';
        });

        // 3. Append assistant notification message into chat (only ONCE)
        appendAssistantMessage(
          `**Appointment #${id} has been successfully cancelled.**\n\n*Reason:* ${escapeHtml(reason)}\n\nYour booked slot has been released back into availability. If you would like to book a different time slot or service provider, let me know or pick from the cards above!`
        );

        // 4. Reload appointments sidebar
        loadAppointments();
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`Could not cancel appointment: ${errData.detail || errData.message || 'Server error'}`);
        allRelatedBtns.forEach(b => {
          b.disabled = false;
          b.innerHTML = '✕ Cancel Appointment';
        });
      }
    } catch (err) {
      console.error('Cancel appointment error:', err);
      alert('Failed to connect to the server to cancel the appointment.');
      allRelatedBtns.forEach(b => {
        b.disabled = false;
        b.innerHTML = '✕ Cancel Appointment';
      });
    } finally {
      cancellingApptIds.delete(id);
    }
  };

  window.cancelAppointment = function(appointmentId, triggerBtn = null) {
    window.openCancellationModal(appointmentId, triggerBtn);
  };

  // Event delegation for all cancel appointment buttons (avoids duplicate execution)
  document.addEventListener('click', (e) => {
    const cancelBtn = e.target.closest('.btn-cancel-receipt, .btn-cancel-appt, .cancel-inline-btn, [data-cancel-id]');
    if (!cancelBtn) return;
    if (cancelBtn.closest('#cancellation-modal')) return;
    if (cancelBtn.classList.contains('cancelled') || cancelBtn.disabled) return;
    e.preventDefault();
    e.stopPropagation();

    let id = cancelBtn.getAttribute('data-cancel-id');
    if (!id) {
      const card = cancelBtn.closest('.receipt-card, .appointment-item');
      if (card) {
        const match = (card.id || card.textContent).match(/(?:APPT-|\b)(\d+)\b/i);
        if (match) id = match[1];
      }
    }
    if (id) {
      window.openCancellationModal(id, cancelBtn);
    }
  });

  // --------------------------------------------------------------------------
  // Customer Booking Details Modal & Form Handlers (Feature Requirement #3)
  // --------------------------------------------------------------------------
  function closeBookingModal() {
    if (customerBookingModal) {
      customerBookingModal.classList.remove('open');
      customerBookingModal.setAttribute('aria-hidden', 'true');
    }
    pendingBooking = null;
  }

  if (bookingModalCloseBtn) {
    bookingModalCloseBtn.addEventListener('click', closeBookingModal);
  }

  if (bookingModalCancelBtn) {
    bookingModalCancelBtn.addEventListener('click', closeBookingModal);
  }

  if (customerBookingModal) {
    customerBookingModal.addEventListener('click', (e) => {
      if (e.target === customerBookingModal) closeBookingModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && customerBookingModal && customerBookingModal.classList.contains('open')) {
      closeBookingModal();
    }
  });

  async function syncBookedSlotsForDate(date) {
    if (!date) return;
    try {
      const res = await fetch(`${API_BASE}/booked-slots?date=${encodeURIComponent(date)}&_t=${Date.now()}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.booked_slots) {
          bookedSlotsByProvider = {};
          for (const [pid, slots] of Object.entries(data.booked_slots)) {
            bookedSlotsByProvider[pid] = new Set(slots.map(s => normalizeSlot(s)));
          }
          refreshAllProviderCardSlots();
          if (pendingBooking && customerBookingModal && customerBookingModal.classList.contains('open')) {
            updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
          }
        }
      }
    } catch (e) {
      console.warn('Failed to sync booked slots for date:', e);
    }
  }

  function updateModalSlotUI(providerId, selectedSlot) {
    const pid = String(providerId);
    if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();

    if (modalSlotSelect) {
      modalSlotSelect.innerHTML = STANDARD_SLOTS_DEF.map(s => {
        const booked = isSlotBooked(providerId, s.value);
        const isSelected = normalizeSlot(s.value) === normalizeSlot(selectedSlot);
        if (booked) {
          return `<option value="${s.value}" disabled class="slot-booked" style="color: #94a3b8; font-style: italic; background-color: #f8fafc;" ${isSelected ? 'selected' : ''}>${s.value} (Booked • Unavailable)</option>`;
        }
        return `<option value="${s.value}" ${isSelected ? 'selected' : ''}>${s.label}</option>`;
      }).join('');
    }

    const isCurrentBooked = isSlotBooked(providerId, selectedSlot);
    const dateLabel = (pendingBooking && pendingBooking.date) ? pendingBooking.date : 'Selected Date';
    if (modalSummarySlot) {
      if (isCurrentBooked) {
        modalSummarySlot.textContent = `${selectedSlot} (${dateLabel} • Booked • Unavailable)`;
        modalSummarySlot.className = 'summary-value slot-pill booked';
      } else {
        modalSummarySlot.textContent = `${selectedSlot} (${dateLabel})`;
        modalSummarySlot.className = 'summary-value slot-pill available';
      }
    }

    if (isCurrentBooked) {
      if (bookingModalError) {
        bookingModalError.textContent = `⚠️ The ${selectedSlot} slot is already booked for ${dateLabel}. Please choose an available time slot from the dropdown above.`;
        bookingModalError.style.display = 'flex';
      }
      if (bookingModalSubmitBtn) {
        bookingModalSubmitBtn.disabled = true;
        bookingModalSubmitBtn.textContent = '✕ Slot Already Booked';
      }
      if (modalSlotHint) {
        modalSlotHint.textContent = `⚠️ This slot is already taken on ${dateLabel}. Please choose another available slot above.`;
        modalSlotHint.style.color = '#e11d48';
      }
    } else {
      if (bookingModalError) {
        bookingModalError.textContent = '';
        bookingModalError.style.display = 'none';
      }
      if (bookingModalSubmitBtn) {
        bookingModalSubmitBtn.disabled = false;
        bookingModalSubmitBtn.textContent = '✓ Confirm & Book Service';
      }
      if (modalSlotHint) {
        modalSlotHint.textContent = 'Slot is available! Fill in your details below to confirm.';
        modalSlotHint.style.color = '#15803d';
      }
    }
  }

  if (modalSlotSelect) {
    modalSlotSelect.addEventListener('change', (e) => {
      const newSlot = e.target.value;
      if (!newSlot || !pendingBooking) return;
      pendingBooking.slot = newSlot;
      updateModalSlotUI(pendingBooking.providerId, newSlot);

      // Also synchronize with card select if rendered
      const cardSelect = document.getElementById(`slot-select-${pendingBooking.providerId}`);
      if (cardSelect && !isSlotBooked(pendingBooking.providerId, newSlot)) {
        cardSelect.value = newSlot;
      }
    });
  }

  if (modalDateInput) {
    modalDateInput.addEventListener('change', async (e) => {
      const newDate = e.target.value;
      if (!newDate) return;
      if (pendingBooking) {
        pendingBooking.date = newDate;
      }
      await syncBookedSlotsForDate(newDate);
      if (pendingBooking) {
        updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
      }
    });
  }

  window.openBookingModal = function(providerId, providerName, slot, problem = '', chosenDate = '') {
    const pid = parseInt(providerId, 10);
    
    // Determine default date (tomorrow formatted as YYYY-MM-DD)
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    const todayStr = today.toISOString().split('T')[0];

    const initialDate = chosenDate || tomorrowStr;

    pendingBooking = {
      providerId: pid,
      providerName: providerName,
      slot: slot,
      date: initialDate
    };

    if (modalDateInput) {
      modalDateInput.min = todayStr;
      modalDateInput.value = initialDate;
    }

    if (customerBookingForm) {
      customerBookingForm.dataset.providerId = String(pid);
      customerBookingForm.dataset.providerName = providerName;
    }

    if (modalSummaryProvider) modalSummaryProvider.textContent = providerName;

    // Detect user problem from input or default
    const currentQuery = (userInput && userInput.value) ? userInput.value.trim() : '';
    if (custProblemInput) {
      custProblemInput.value = problem || currentQuery || 'Appliance repair and service';
    }

    // Clear chat input bar
    if (userInput) userInput.value = '';

    // Fetch booked slots for the selected date and refresh UI
    syncBookedSlotsForDate(initialDate);
    updateModalSlotUI(pid, slot);

    const booked = isSlotBooked(pid, slot);
    if (customerBookingModal) {
      customerBookingModal.classList.add('open');
      customerBookingModal.setAttribute('aria-hidden', 'false');
      if (custNameInput && !booked) {
        setTimeout(() => custNameInput.focus(), 60);
      }
    }
  };

  async function submitBookingForm(e) {
    if (e && e.preventDefault) e.preventDefault();

    // Reconstruct pendingBooking from form dataset if needed
    if (!pendingBooking) {
      const formPid = customerBookingForm ? customerBookingForm.dataset.providerId : null;
      const formPname = customerBookingForm ? customerBookingForm.dataset.providerName : null;
      const formSlot = modalSlotSelect ? modalSlotSelect.value : (modalSummarySlot ? modalSummarySlot.textContent : '');
      const formDate = (modalDateInput && modalDateInput.value) ? modalDateInput.value : 'Tomorrow';
      if (formPid && formPname) {
        pendingBooking = {
          providerId: parseInt(formPid, 10),
          providerName: formPname,
          slot: formSlot,
          date: formDate
        };
      }
    }

    if (!pendingBooking) {
      if (bookingModalError) {
        bookingModalError.textContent = '⚠️ Booking session not found. Please choose a provider and slot from the cards.';
        bookingModalError.style.display = 'flex';
      }
      return;
    }

    // Ensure date and slot are synced from modal inputs
    if (modalDateInput && modalDateInput.value) {
      pendingBooking.date = modalDateInput.value;
    }
    if (modalSlotSelect && modalSlotSelect.value) {
      pendingBooking.slot = modalSlotSelect.value;
    }

    // Clear previous error
    if (bookingModalError) {
      bookingModalError.style.display = 'none';
      bookingModalError.textContent = '';
    }

    const name = custNameInput ? custNameInput.value.trim() : '';
    const phone = custPhoneInput ? custPhoneInput.value.trim() : '';
    const email = custEmailInput ? custEmailInput.value.trim() : '';
    const address = custAddressInput ? custAddressInput.value.trim() : '';
    const problem = custProblemInput ? custProblemInput.value.trim() : 'Appliance repair';

    if (!name || !phone) {
      const msg = '⚠️ Please enter both your Full Name and Phone Number to confirm booking.';
      if (bookingModalError) {
        bookingModalError.textContent = msg;
        bookingModalError.style.display = 'flex';
      } else {
        alert(msg);
      }
      if (!name && custNameInput) custNameInput.focus();
      else if (!phone && custPhoneInput) custPhoneInput.focus();
      return;
    }

    if (isSlotBooked(pendingBooking.providerId, pendingBooking.slot)) {
      const msg = `⚠️ The ${pendingBooking.slot} slot for ${pendingBooking.providerName} has already been booked by another customer. Please choose an available slot from the dropdown above.`;
      if (bookingModalError) {
        bookingModalError.textContent = msg;
        bookingModalError.style.display = 'flex';
      } else {
        alert(msg);
      }
      updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
      return;
    }

    if (bookingModalSubmitBtn) {
      bookingModalSubmitBtn.disabled = true;
      bookingModalSubmitBtn.textContent = '⏳ Confirming Booking...';
    }

    try {
      const payload = {
        provider_id: pendingBooking.providerId,
        date: pendingBooking.date || 'Tomorrow',
        time_slot: pendingBooking.slot,
        customer_name: name,
        customer_phone: phone,
        customer_email: email,
        customer_address: address,
        problem: problem,
        service_id: 1
      };

      const res = await fetch(`${API_BASE}/book-appointment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (res.ok && data.success) {
        // 1. Mark slot as booked locally & refresh all card selects
        const pid = String(pendingBooking.providerId);
        if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();
        bookedSlotsByProvider[pid].add(normalizeSlot(payload.time_slot));
        refreshAllProviderCardSlots();

        // 2. Show user booking message in chat
        appendUserMessage(`Please confirm my booking with ${pendingBooking.providerName} for ${pendingBooking.slot} (Customer: ${name}, Phone: ${phone}).`);

        // 3. Add assistant response with confirmation receipt
        const receiptObj = {
          appointment_id: data.appointment_id,
          customer_name: name,
          customer_phone: phone,
          customer_email: email,
          customer_address: address,
          provider: pendingBooking.providerName,
          provider_phone: data.provider_phone || '+91 98221 11223',
          problem: problem,
          date: payload.date,
          time_slot: payload.time_slot,
          status: 'confirmed'
        };

        const assistantText = `### Appointment Confirmed! 🎉\n\nYour service booking with **${pendingBooking.providerName}** has been confirmed for **${payload.date}** at **${payload.time_slot}**.\n\n` +
          `* **Customer:** ${name}\n` +
          `* **Phone:** ${phone}\n` +
          `* **Service Address:** ${address || 'Provided to technician'}\n` +
          `* **Issue:** ${problem}\n\n` +
          `Your customer details and booking have been recorded in the database. The technician will contact you prior to arrival.`;

        appendAssistantMessage(assistantText, [], receiptObj);

        // 4. Log MCP tool activity
        renderToolActivities([{
          tool: 'schedule_appointment',
          summary: `schedule_appointment(provider_id=${pendingBooking.providerId}, slot="${payload.time_slot}", customer="${name}") -> DB Appt #${data.appointment_id}`
        }]);

        // 5. Reload Bookings & Catalog tabs
        loadAppointments();
        loadCatalog();

        // 6. Clear chat text bar & close modal
        if (userInput) userInput.value = '';
        closeBookingModal();
      } else {
        const errMsg = data.detail || data.message || 'Unable to complete appointment';
        if (bookingModalError) {
          bookingModalError.textContent = `⚠️ Booking failed: ${errMsg}`;
          bookingModalError.style.display = 'flex';
        } else {
          alert(`Booking failed: ${errMsg}`);
        }

        // If slot was taken by someone else on the server, update local state
        if (errMsg.toLowerCase().includes('already been booked')) {
          const pid = String(pendingBooking.providerId);
          if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();
          bookedSlotsByProvider[pid].add(normalizeSlot(pendingBooking.slot));
          refreshAllProviderCardSlots();
          updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
        } else if (bookingModalSubmitBtn) {
          bookingModalSubmitBtn.disabled = false;
          bookingModalSubmitBtn.textContent = '✓ Confirm & Book Service';
        }
      }
    } catch (err) {
      console.error('Booking submission error:', err);
      const netErr = 'Network error while booking appointment. Please check if the server is running on port 8000.';
      if (bookingModalError) {
        bookingModalError.textContent = `⚠️ ${netErr}`;
        bookingModalError.style.display = 'flex';
      } else {
        alert(netErr);
      }
      if (bookingModalSubmitBtn) {
        bookingModalSubmitBtn.disabled = false;
        bookingModalSubmitBtn.textContent = '✓ Confirm & Book Service';
      }
    }
  }

  if (customerBookingForm) {
    customerBookingForm.addEventListener('submit', submitBookingForm);
  }

  // Reliable click handler for confirm button
  if (bookingModalSubmitBtn) {
    bookingModalSubmitBtn.addEventListener('click', (e) => {
      e.preventDefault();
      submitBookingForm(e);
    });
  }

  // Real-time synchronization for multi-user booked slot reflection (every 3 seconds)
  async function syncBookedSlotsRealtime() {
    try {
      const res = await fetch(`${API_BASE}/booked-slots?_t=${Date.now()}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.booked_slots) {
          let hasChanges = false;
          for (const [pid, slots] of Object.entries(data.booked_slots)) {
            if (!bookedSlotsByProvider[pid]) bookedSlotsByProvider[pid] = new Set();
            for (const s of slots) {
              const norm = normalizeSlot(s);
              if (!bookedSlotsByProvider[pid].has(norm)) {
                bookedSlotsByProvider[pid].add(norm);
                hasChanges = true;
              }
            }
          }
          if (hasChanges) {
            refreshAllProviderCardSlots();
            if (pendingBooking && customerBookingModal && customerBookingModal.classList.contains('open')) {
              updateModalSlotUI(pendingBooking.providerId, pendingBooking.slot);
            }
          }
        }
      }
    } catch (e) {
      // Silent catch for background poll
    }
  }

  setInterval(syncBookedSlotsRealtime, 3000);

  // --------------------------------------------------------------------------
  // Live WebSocket Synchronization for Customer Tracking Stepper
  // --------------------------------------------------------------------------
  const getCustomerWsUrl = () => {
    const isFile = window.location.protocol === 'file:';
    const isLiveServer = window.location.port === '5500' || window.location.port === '5501';
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = (isFile || isLiveServer) ? '127.0.0.1:8000' : window.location.host;
    return `${wsProto}//${wsHost}/ws/live`;
  };

  let customerWs = null;
  function initCustomerWebSocket() {
    try {
      const wsUrl = getCustomerWsUrl();
      customerWs = new WebSocket(wsUrl);

      customerWs.onopen = () => {
        console.log('Customer WS connected for live tracking:', wsUrl);
      };

      customerWs.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'STATUS_UPDATE' && msg.data) {
            updateCustomerTrackingStepper(msg.data);
            loadAppointments();
          } else if (msg.type === 'NEW_JOB') {
            loadAppointments();
            syncBookedSlotsRealtime();
          } else if (msg.type === 'JOB_CHAT_MESSAGE' && msg.data) {
            handleCustomerIncomingChatMessage(msg.data);
          } else if (msg.type === 'BOOKINGS_CLEARED') {
            bookedSlotsByProvider = {};
            refreshAllProviderCardSlots();
            loadAppointments();
          }
        } catch (e) {
          console.warn('Customer WS message parse error:', e);
        }
      };

      customerWs.onclose = () => {
        setTimeout(initCustomerWebSocket, 4000);
      };
    } catch (err) {
      console.warn('Could not initialize customer WS:', err);
    }
  }

  function updateCustomerTrackingStepper(update) {
    const card = document.getElementById(`receipt-card-${update.appointment_id}`);
    if (!card) return;

    const status = update.status || 'confirmed';
    const eta = document.getElementById(`stepper-eta-${update.appointment_id}`);
    const statusPill = card.querySelector('.receipt-status-pill');

    if (statusPill) {
      statusPill.className = `receipt-status-pill ${status}`;
      const labels = {
        confirmed: 'Confirmed',
        accepted: 'Accepted by Technician',
        en_route: 'Technician En Route',
        arrived: 'Technician Arrived',
        in_progress: 'Repair in Progress',
        completed: 'Completed',
        cancelled: 'Cancelled',
      };
      statusPill.textContent = `● ${labels[status] || status}`;
    }

    if (eta) {
      if (status === 'accepted') eta.textContent = `Assigned: ${update.technician_name || 'Technician'}`;
      else if (status === 'en_route') eta.textContent = `🚗 En Route (${update.eta_minutes || 15}m away)`;
      else if (status === 'arrived') eta.textContent = `📍 Technician is at your door!`;
      else if (status === 'in_progress') eta.textContent = `🛠️ Repair work in progress`;
      else if (status === 'completed') eta.textContent = `✅ Service completed & billed`;
      else if (status === 'cancelled') eta.textContent = `❌ Appointment cancelled`;
    }

    // Step sequence
    const stepKeys = ['confirmed', 'accepted', 'en_route', 'arrived', 'completed'];
    const activeKey = status === 'in_progress' ? 'arrived' : status;
    const activeIdx = stepKeys.indexOf(activeKey);

    stepKeys.forEach((s, idx) => {
      const stepEl = document.getElementById(`step-${s}-${update.appointment_id}`);
      if (stepEl) {
        if (idx <= activeIdx) {
          stepEl.classList.add('active');
          if (idx === activeIdx && status !== 'completed') {
            stepEl.classList.add('current-pulse');
          } else {
            stepEl.classList.remove('current-pulse');
          }
        } else {
          stepEl.classList.remove('active', 'current-pulse');
        }
      }
      if (idx > 0) {
        const line = document.getElementById(`line-${idx}-${update.appointment_id}`);
        if (line) {
          if (idx <= activeIdx) line.classList.add('active');
          else line.classList.remove('active');
        }
      }
    });

    // Unlock and populate Live Chat Box when technician accepts
    const chatBox = document.getElementById(`customer-chat-box-${update.appointment_id}`);
    if (chatBox) {
      if (['accepted', 'en_route', 'arrived', 'in_progress'].includes(status)) {
        chatBox.style.display = 'flex';
        const techNameEl = document.getElementById(`chat-tech-name-${update.appointment_id}`);
        if (techNameEl && update.technician_name) {
          techNameEl.textContent = update.technician_name;
        }
        loadCustomerChatMessages(update.appointment_id);
      }
    }
  }

  // --------------------------------------------------------------------------
  // Customer Direct Chat Box Handlers
  // --------------------------------------------------------------------------
  async function loadCustomerChatMessages(apptId) {
    const container = document.getElementById(`customer-chat-msgs-${apptId}`);
    if (!container) return;

    try {
      const resp = await fetch(`${API_BASE}/api/appointments/${apptId}/messages`);
      if (!resp.ok) return;
      const data = await resp.json();
      const messages = data.messages || [];

      if (messages.length === 0) {
        container.innerHTML = `<div class="chat-placeholder">Technician assigned! You can chat here directly to share directions or gate codes.</div>`;
        return;
      }

      container.innerHTML = messages.map(m => {
        const isCust = m.sender_type === 'customer';
        const time = m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
        return `
          <div class="customer-chat-bubble ${isCust ? 'customer-side' : 'technician-side'}">
            <span style="font-size: 0.7rem; opacity: 0.8; font-weight: 700; display: block; margin-bottom: 2px;">
              ${escapeHtml(m.sender_name)} ${time ? `• ${time}` : ''}
            </span>
            <div>${escapeHtml(m.message)}</div>
          </div>
        `;
      }).join('');

      container.scrollTop = container.scrollHeight;
    } catch (e) {
      console.warn('Could not load chat messages:', e);
    }
  }

  window.sendCustomerMessage = async function(event, apptId, custName) {
    if (event && event.preventDefault) event.preventDefault();
    const input = document.getElementById(`customer-chat-input-${apptId}`);
    if (!input) return;

    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    input.disabled = true;

    try {
      const resp = await fetch(`${API_BASE}/api/appointments/${apptId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender_type: 'customer',
          sender_name: custName || 'Customer',
          message: message
        })
      });

      if (!resp.ok) {
        alert('Failed to send message to technician.');
      } else {
        const newMsg = await resp.json();
        appendCustomerSingleMessage(apptId, newMsg);
      }
    } catch (err) {
      console.error('Error sending customer chat message:', err);
      alert('Network error sending message');
    } finally {
      input.disabled = false;
      input.focus();
    }
  };

  function appendCustomerSingleMessage(apptId, m) {
    const container = document.getElementById(`customer-chat-msgs-${apptId}`);
    if (!container) return;

    const placeholder = container.querySelector('.chat-placeholder');
    if (placeholder) placeholder.remove();

    const isCust = m.sender_type === 'customer';
    const time = m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const bubble = document.createElement('div');
    bubble.className = `customer-chat-bubble ${isCust ? 'customer-side' : 'technician-side'}`;
    bubble.innerHTML = `
      <span style="font-size: 0.7rem; opacity: 0.8; font-weight: 700; display: block; margin-bottom: 2px;">
        ${escapeHtml(m.sender_name)} ${time ? `• ${time}` : ''}
      </span>
      <div>${escapeHtml(m.message)}</div>
    `;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
  }

  function handleCustomerIncomingChatMessage(msgData) {
    const apptId = msgData.appointment_id;
    appendCustomerSingleMessage(apptId, msgData);
  }

  // --------------------------------------------------------------------------
  // Two-Step Flow Follow-Up Quick Trigger
  // --------------------------------------------------------------------------
  window.triggerFollowUpChoice = function(choice) {
    if (isTaskRunning) return;
    if (choice) {
      userInput.value = 'Yes, please find verified nearby service technicians for this issue.';
    } else {
      userInput.value = 'Thank you, I will try the manual checks first.';
    }
    chatForm.dispatchEvent(new Event('submit'));
  };

  // Start customer WS on load
  initCustomerWebSocket();


  window.onSlotSelectChange = function(providerId, providerName, slotValue) {
    if (!slotValue) return;
    if (isSlotBooked(providerId, slotValue)) {
      alert(`The ${slotValue} slot is already booked for ${providerName}. Please select an available slot.`);
      const selectEl = document.getElementById(`slot-select-${providerId}`);
      if (selectEl) selectEl.value = '';
      return;
    }
  };

  window.bookProviderWithSlot = function(providerId, providerName) {
    if (isTaskRunning) {
      alert('Please wait for the current assistant task to complete before booking.');
      return;
    }
    const selectEl = document.getElementById(`slot-select-${providerId}`);
    const selectedSlot = selectEl ? selectEl.value : '';
    if (!selectedSlot) {
      alert(`Please choose an available time slot from the dropdown for ${providerName} first!`);
      if (selectEl) selectEl.focus();
      return;
    }
    if (isSlotBooked(providerId, selectedSlot)) {
      alert(`⚠️ The ${selectedSlot} slot for ${providerName} is already booked by another customer! Please select an available time slot.`);
      if (selectEl) {
        selectEl.value = '';
        selectEl.focus();
      }
      return;
    }
    // Open the Customer Details modal popup (Feature Requirement #3)
    window.openBookingModal(providerId, providerName, selectedSlot);
  };

  window.checkSlotsFor = function(providerName) {
    if (isTaskRunning) return;
    userInput.value = `What time slots are available for ${providerName} tomorrow?`;
    chatForm.dispatchEvent(new Event('submit'));
  };

  window.selectProvider = function(providerName) {
    if (isTaskRunning) return;
    userInput.value = `I would like to select ${providerName}. What slots do they have?`;
    chatForm.dispatchEvent(new Event('submit'));
  };
});
