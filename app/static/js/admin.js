const statusEl = document.getElementById('status');
      const errorEl = document.getElementById('error');
      const databaseSearch = document.getElementById('databaseSearch');
      const databaseSearchBtn = document.getElementById('databaseSearchBtn');
      const databaseTableBody = document.getElementById('databaseTableBody');
      const databasePagination = document.getElementById('databasePagination');
      const databaseDetail = document.getElementById('databaseDetail');
      const targetInfoModal = document.getElementById('targetInfoModal');
      const targetModalClose = document.getElementById('targetModalClose');
      const DATABASE_PAGE_SIZE = 10;
      let databasePage = 1;
      let databaseCatalog = [];

      function showStatus(message) {
        statusEl.textContent = message;
        errorEl.textContent = '';
      }

      function showError(message) {
        errorEl.textContent = message;
        statusEl.textContent = '';
      }

      function parseJsonField(id, fallback) {
        try {
          const value = document.getElementById(id).value.trim();
          if (!value) return fallback;
          return JSON.parse(value);
        } catch (error) {
          throw new Error(`Invalid JSON in ${id}`);
        }
      }

      function parseListField(value) {
        return value.split(',').map(item => item.trim()).filter(Boolean);
      }

      function getPickerValue(fieldId) {
        const select = document.getElementById(`${fieldId}_select`);
        const input = document.getElementById(fieldId);
        const selectedValue = select ? select.value : '';
        if (selectedValue && selectedValue !== '__custom__') {
          return selectedValue.trim();
        }
        return input ? input.value.trim() : '';
      }

      function populatePicker(fieldId, values) {
        const select = document.getElementById(`${fieldId}_select`);
        const input = document.getElementById(fieldId);
        if (!select || !input) return;

        const uniqueValues = [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
        const options = ['<option value="">Select existing</option>'];
        uniqueValues.forEach(value => {
          options.push(`<option value="${value}">${value}</option>`);
        });
        options.push('<option value="__custom__">Add new…</option>');
        select.innerHTML = options.join('');
        select.value = '';
        input.value = input.value || '';
      }

      function bindPicker(fieldId) {
        const select = document.getElementById(`${fieldId}_select`);
        const input = document.getElementById(fieldId);
        if (!select || !input) return;

        select.addEventListener('change', () => {
          if (select.value === '__custom__') {
            input.focus();
            input.value = '';
            return;
          }
          input.value = select.value;
        });
      }

      function syncPickerValue(fieldId, value) {
        const select = document.getElementById(`${fieldId}_select`);
        const input = document.getElementById(fieldId);
        if (!select || !input) return;

        const normalizedValue = value || '';
        if (normalizedValue && [...select.options].some(option => option.value === normalizedValue)) {
          select.value = normalizedValue;
          input.value = '';
        } else {
          select.value = '__custom__';
          input.value = normalizedValue;
        }
      }

      function serializeForm() {
        const compound = {
          key: document.getElementById('key').value.trim(),
          name: document.getElementById('name').value.trim(),
          canonical_name: document.getElementById('canonical_name').value.trim(),
          synonyms: parseListField(document.getElementById('synonyms').value),
          drug_class: getPickerValue('drug_class'),
          compound_class: getPickerValue('compound_class'),
          route_of_administration: getPickerValue('route_of_administration'),
          formulation: getPickerValue('formulation'),
          mechanism: document.getElementById('mechanism').value.trim(),
          receptor_targets: parseJsonField('receptor_targets', []),
          categories: parseListField(document.getElementById('categories').value),
          indications: parseListField(document.getElementById('indications').value),
          dosing: parseJsonField('dosing', {}),
          reason: document.getElementById('reason').value.trim(),
          citation: document.getElementById('citation').value.trim(),
          contraindications: parseJsonField('contraindications', []),
          side_effects: parseJsonField('side_effects', []),
          interactions: parseJsonField('interactions', []),
          warnings: parseJsonField('warnings', []),
          half_life: document.getElementById('half_life').value.trim(),
          oral_bioavailability: document.getElementById('oral_bioavailability').value.trim(),
          metabolism: document.getElementById('metabolism').value.trim(),
          clearance: document.getElementById('clearance').value.trim(),
          primary_effects: parseJsonField('primary_effects', []),
          evidence_level: document.getElementById('evidence_level').value,
          risk_band: document.getElementById('risk_band').value,
          graph_tags: parseListField(document.getElementById('graph_tags').value),
          metadata: {
            route: getPickerValue('route_of_administration'),
            formulation: getPickerValue('formulation'),
            half_life: document.getElementById('half_life').value.trim(),
            oral_bioavailability: document.getElementById('oral_bioavailability').value.trim(),
            metabolism: document.getElementById('metabolism').value.trim(),
            clearance: document.getElementById('clearance').value.trim(),
          }
        };

        if (!compound.key) {
          throw new Error('Key is required.');
        }

        return compound;
      }

      function fillForm(compound) {
        document.getElementById('key').value = compound.key || '';
        document.getElementById('name').value = compound.name || '';
        document.getElementById('canonical_name').value = compound.canonical_name || '';
        document.getElementById('synonyms').value = sanitizeFieldList(compound.synonyms).join(', ');
        syncPickerValue('drug_class', compound.drug_class || '');
        syncPickerValue('compound_class', compound.compound_class || '');
        syncPickerValue('route_of_administration', compound.route_of_administration || '');
        syncPickerValue('formulation', compound.formulation || '');
        document.getElementById('mechanism').value = compound.mechanism || '';
        document.getElementById('receptor_targets').value = JSON.stringify(compound.receptor_targets || [], null, 2);
        document.getElementById('categories').value = sanitizeFieldList(compound.categories).join(', ');
        document.getElementById('indications').value = sanitizeFieldList(compound.indications).join(', ');
        document.getElementById('dosing').value = JSON.stringify(compound.dosing || {}, null, 2);
        document.getElementById('reason').value = compound.reason || '';
        document.getElementById('citation').value = compound.citation || '';
        document.getElementById('contraindications').value = JSON.stringify(compound.contraindications || [], null, 2);
        document.getElementById('side_effects').value = JSON.stringify(sanitizeFieldList(compound.side_effects), null, 2);
        document.getElementById('interactions').value = JSON.stringify(sanitizeFieldList(compound.interactions), null, 2);
        document.getElementById('warnings').value = JSON.stringify(sanitizeFieldList(compound.warnings), null, 2);
        document.getElementById('half_life').value = compound.half_life || '';
        document.getElementById('oral_bioavailability').value = compound.oral_bioavailability || '';
        document.getElementById('metabolism').value = compound.metabolism || '';
        document.getElementById('clearance').value = compound.clearance || '';
        document.getElementById('primary_effects').value = JSON.stringify(sanitizeFieldList(compound.primary_effects), null, 2);
        document.getElementById('evidence_level').value = compound.evidence_level || 'moderate';
        document.getElementById('risk_band').value = compound.risk_band || 'low';
        document.getElementById('graph_tags').value = sanitizeFieldList(compound.graph_tags).join(', ');
      }

      function sanitizeFieldList(value) {
        const values = Array.isArray(value) ? value : [value];
        return [...new Set(values
          .map(item => String(item ?? '').trim())
          .filter(item => item && !/^(none|null|n\/a|na|unknown|not available|not applicable|--|-)$/.test(item.toLowerCase()))
        )];
      }

      function sanitizeTargetList(value) {
        if (!Array.isArray(value)) return [];
        return value
          .filter(Boolean)
          .map(target => {
            if (typeof target === 'string') {
              return { target: target, action: '', family: '', target_id: '' };
            }
            if (typeof target === 'object') {
              return {
                target: target.target || target.name || target.label || target.target_name || '',
                action: target.action || '',
                family: target.family || '',
                target_id: target.target_id || target.id || '',
              };
            }
            return null;
          })
          .filter(target => target && (target.target || target.target_id));
      }

      function escapeHtml(value) {
        return String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/\"/g, '&quot;')
          .replace(/'/g, '&#039;');
      }

      function renderDatabasePagination(totalMatches) {
        const totalPages = Math.max(1, Math.ceil(totalMatches / DATABASE_PAGE_SIZE));
        if (databasePage > totalPages) {
          databasePage = totalPages;
        }

        const start = totalMatches === 0 ? 0 : (databasePage - 1) * DATABASE_PAGE_SIZE + 1;
        const end = Math.min(databasePage * DATABASE_PAGE_SIZE, totalMatches);

        databasePagination.innerHTML = `
          <span>Showing ${start}-${end} of ${totalMatches}</span>
          <div class="db-pagination-buttons">
            <button type="button" ${databasePage <= 1 ? 'disabled' : ''} data-page="prev">Previous</button>
            <button type="button" ${databasePage >= totalPages ? 'disabled' : ''} data-page="next">Next</button>
          </div>
        `;

        const prevButton = databasePagination.querySelector('[data-page="prev"]');
        const nextButton = databasePagination.querySelector('[data-page="next"]');
        prevButton?.addEventListener('click', () => {
          if (databasePage > 1) {
            databasePage -= 1;
            refreshDatabasePage();
          }
        });
        nextButton?.addEventListener('click', () => {
          if (databasePage < totalPages) {
            databasePage += 1;
            refreshDatabasePage();
          }
        });
      }

      async function refreshDatabasePage() {
        const query = (databaseSearch?.value || '').trim();
        const params = new URLSearchParams({
          limit: String(DATABASE_PAGE_SIZE),
          offset: String((databasePage - 1) * DATABASE_PAGE_SIZE),
        });
        if (query) {
          params.set('search', query);
        }

        const response = await fetch(`/catalog?${params.toString()}`);
        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : payload.items || [];
        const total = Array.isArray(payload) ? payload.length : payload.total || 0;

        databaseCatalog = items;
        renderDatabaseTable(items, total);
      }

      function renderTargetModal(target) {
        const payload = target || {};
        const rows = [
          { label: 'Target', value: payload.target || payload.name || '—' },
          { label: 'Action', value: payload.action || '—' },
          { label: 'Family', value: payload.family || '—' },
          { label: 'Target ID', value: payload.target_id || payload.id || '—' },
        ];

        document.getElementById('targetModalTitle').textContent = payload.target || payload.name || 'Target details';
        document.getElementById('targetModalContent').innerHTML = rows.map(row => `
          <div class="target-modal-row">
            <strong>${escapeHtml(row.label)}</strong>
            <div>${escapeHtml(row.value)}</div>
          </div>
        `).join('');

        targetInfoModal.classList.remove('hidden');
      }

      function closeTargetModal() {
        targetInfoModal.classList.add('hidden');
      }

      function renderCompoundDetail(item) {
        if (!item) {
          databaseDetail.classList.add('hidden');
          databaseDetail.innerHTML = '';
          return;
        }

        const targets = sanitizeTargetList(item.receptor_targets || []);
        const details = [
          { label: 'Key', value: item.key || '—' },
          { label: 'Name', value: item.name || '—' },
          { label: 'Class', value: item.drug_class || item.compound_class || '—' },
          { label: 'Route', value: item.route_of_administration || '—' },
          { label: 'Mechanism', value: item.mechanism || '—' },
          { label: 'Targets', value: targets.length ? `<div class="target-links">${targets.map(target => `<button type="button" class="target-link" data-target="${encodeURIComponent(JSON.stringify(target))}">${escapeHtml(target.target || target.target_id || 'Target')}</button>`).join('')}</div>` : '—' },
          { label: 'Indications', value: sanitizeFieldList(item.indications).join(', ') || '—' },
          { label: 'Warnings', value: sanitizeFieldList(item.warnings).join(', ') || '—' },
          { label: 'Side effects', value: sanitizeFieldList(item.side_effects).join(', ') || '—' },
          { label: 'Interactions', value: sanitizeFieldList(item.interactions).join(', ') || '—' },
        ];

        databaseDetail.classList.remove('hidden');
        databaseDetail.innerHTML = `
          <div class="detail-header">
            <h4>${escapeHtml(item.name || item.key || 'Compound details')}</h4>
            <button type="button" class="secondary" data-detail-close="true">Close</button>
          </div>
          <div class="detail-grid">
            ${details.map(detail => `
              <div class="detail-box" tabindex="0" role="button" aria-label="Toggle ${escapeHtml(detail.label)} details">
                <label>${escapeHtml(detail.label)}</label>
                <div>${detail.label === 'Targets' ? detail.value : escapeHtml(detail.value)}</div>
              </div>
            `).join('')}
          </div>
        `;

        const targetButtons = databaseDetail.querySelectorAll('.target-link');
        targetButtons.forEach(button => {
          button.addEventListener('click', () => {
            const target = JSON.parse(decodeURIComponent(button.dataset.target));
            renderTargetModal(target);
          });
        });

        const detailBoxes = databaseDetail.querySelectorAll('.detail-box');
        detailBoxes.forEach(box => {
          box.addEventListener('click', () => box.classList.toggle('expanded'));
          box.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              box.classList.toggle('expanded');
            }
          });
        });

        const closeBtn = databaseDetail.querySelector('[data-detail-close="true"]');
        closeBtn?.addEventListener('click', () => renderCompoundDetail(null));
      }

      function renderDatabaseTable(items, totalMatches = items.length) {
        databaseTableBody.innerHTML = items.map(item => {
          const cleanIndications = sanitizeFieldList(item.indications).slice(0, 3);
          const indications = cleanIndications.length ? cleanIndications.join(', ') : '—';
          const mechanism = item.mechanism ? escapeHtml(item.mechanism) : '—';
          return `
            <tr data-key="${escapeHtml(item.key || '')}">
              <td><span class="pill">${escapeHtml(item.key || '—')}</span></td>
              <td>${escapeHtml(item.name || item.key || 'Unknown')}</td>
              <td>${escapeHtml(item.drug_class || item.compound_class || '—')}</td>
              <td>${escapeHtml(item.route_of_administration || '—')}</td>
              <td>${mechanism}</td>
              <td>${escapeHtml(indications)}</td>
            </tr>
          `;
        }).join('') || '<tr><td colspan="6">No compounds match the current search.</td></tr>';

        databaseTableBody.querySelectorAll('tr[data-key]').forEach(row => {
          row.addEventListener('click', () => {
            const key = row.getAttribute('data-key');
            const selected = items.find(item => String(item.key) === key);
            if (selected) {
              const targetUrl = `/compound/${encodeURIComponent(selected.key || selected.name || '')}`;
              window.location.href = targetUrl;
            }
          });
        });

        renderDatabasePagination(totalMatches);
      }

      async function loadCatalog() {
        databasePage = 1;
        await refreshDatabasePage();

        const response = await fetch('/catalog?limit=10&offset=0');
        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : payload.items || [];
        refreshPickerOptions(items);
      }

      async function saveCompound() {
        try {
          const payload = serializeForm();
          const response = await fetch('/catalog', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          const result = await response.json();
          if (!response.ok) {
            throw new Error(result.detail || 'Could not save compound.');
          }

          showStatus(`Saved ${payload.name}.`);
          await loadCatalog();
          fillForm(result);
        } catch (error) {
          showError(error.message);
        }
      }

      async function deleteCompound() {
        const key = document.getElementById('key').value.trim();
        if (!key) {
          showError('Select or enter a compound key to delete.');
          return;
        }

        try {
          const response = await fetch(`/catalog/${encodeURIComponent(key)}`, {
            method: 'DELETE'
          });
          const result = await response.json();
          if (!response.ok) {
            throw new Error(result.detail || 'Delete failed.');
          }
          showStatus(`Deleted ${key}.`);
          resetForm();
          await loadCatalog();
        } catch (error) {
          showError(error.message);
        }
      }

      function resetForm() {
        document.getElementById('key').value = '';
        document.getElementById('name').value = '';
        document.getElementById('canonical_name').value = '';
        document.getElementById('synonyms').value = '';
        document.getElementById('drug_class').value = '';
        document.getElementById('compound_class').value = '';
        document.getElementById('route_of_administration').value = '';
        document.getElementById('formulation').value = '';
        document.getElementById('mechanism').value = '';
        document.getElementById('receptor_targets').value = '[]';
        document.getElementById('categories').value = '';
        document.getElementById('indications').value = '';
        document.getElementById('dosing').value = '{\n  "unit": "mg/day",\n  "basis": "fixed",\n  "mg_per_kg": {\n    "threshold": 0,\n    "common": 2000,\n    "heavy": 3000\n  }\n}';
        document.getElementById('reason').value = '';
        document.getElementById('citation').value = '';
        document.getElementById('contraindications').value = '[]';
        document.getElementById('side_effects').value = '[]';
        document.getElementById('interactions').value = '[]';
        document.getElementById('warnings').value = '[]';
        document.getElementById('half_life').value = '';
        document.getElementById('oral_bioavailability').value = '';
        document.getElementById('metabolism').value = '';
        document.getElementById('clearance').value = '';
        document.getElementById('primary_effects').value = '[]';
        document.getElementById('evidence_level').value = 'moderate';
        document.getElementById('risk_band').value = 'low';
        document.getElementById('graph_tags').value = '';
        document.getElementById('drug_class_select').value = '';
        document.getElementById('compound_class_select').value = '';
        document.getElementById('route_of_administration_select').value = '';
        document.getElementById('formulation_select').value = '';
      }

      function refreshPickerOptions(catalog) {
        const fieldMap = {
          drug_class: 'drug_class',
          compound_class: 'compound_class',
          route_of_administration: 'route_of_administration',
          formulation: 'formulation',
        };

        const collectedValues = {};
        Object.keys(fieldMap).forEach(key => {
          collectedValues[key] = [];
        });

        catalog.forEach(item => {
          Object.entries(fieldMap).forEach(([key, fieldName]) => {
            if (item[fieldName]) {
              collectedValues[key].push(item[fieldName]);
            }
          });
        });

        Object.entries(fieldMap).forEach(([key]) => populatePicker(key, collectedValues[key]));
      }

      ['drug_class', 'compound_class', 'route_of_administration', 'formulation'].forEach(bindPicker);

      document.getElementById('saveBtn').addEventListener('click', saveCompound);
      document.getElementById('newBtn').addEventListener('click', resetForm);
      document.getElementById('deleteBtn').addEventListener('click', deleteCompound);
      targetModalClose?.addEventListener('click', closeTargetModal);
      targetInfoModal?.addEventListener('click', (event) => {
        if (event.target === targetInfoModal) {
          closeTargetModal();
        }
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          closeTargetModal();
        }
      });

      databaseSearchBtn.addEventListener('click', () => {
        databasePage = 1;
        refreshDatabasePage();
      });
      databaseSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          databasePage = 1;
          refreshDatabasePage();
        }
      });

      // Mobile menu toggle handling
      const adminMobileMenuBtn = document.getElementById('mobile-menu-toggle');
      const adminNavLinks = document.getElementById('nav-links');
      if (adminMobileMenuBtn && adminNavLinks) {
        adminMobileMenuBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          adminNavLinks.classList.toggle('open');
        });

        document.addEventListener('click', (e) => {
          if (!adminNavLinks.contains(e.target) && !adminMobileMenuBtn.contains(e.target)) {
            adminNavLinks.classList.remove('open');
          }
        });
      }

      // WebSockets & Async Ingestion Job Queue Manager
      const btnSubmitAsyncJob = document.getElementById('btnSubmitAsyncJob');
      const asyncBatchInput = document.getElementById('asyncBatchInput');
      const wsConnectionStatus = document.getElementById('wsConnectionStatus');
      const asyncJobProgressWrap = document.getElementById('asyncJobProgressWrap');
      const asyncJobStep = document.getElementById('asyncJobStep');
      const asyncJobPct = document.getElementById('asyncJobPct');
      const asyncJobProgressBar = document.getElementById('asyncJobProgressBar');
      const asyncJobLogs = document.getElementById('asyncJobLogs');

      let socket = null;

      function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/enrichment`;

        try {
          socket = new WebSocket(wsUrl);

          socket.onopen = () => {
            if (wsConnectionStatus) {
              wsConnectionStatus.textContent = 'Connected (Live Stream)';
              wsConnectionStatus.style.color = 'var(--success)';
            }
          };

          socket.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.event === 'job_progress' || data.event === 'job_started' || data.event === 'job_completed') {
                if (asyncJobProgressWrap) asyncJobProgressWrap.style.display = 'block';
                if (asyncJobStep) asyncJobStep.textContent = data.current_step || 'Processing...';
                if (asyncJobPct) asyncJobPct.textContent = `${Math.round(data.progress_pct || 0)}%`;
                if (asyncJobProgressBar) asyncJobProgressBar.style.width = `${data.progress_pct || 0}%`;

                if (data.latest_log && asyncJobLogs) {
                  const logLine = document.createElement('div');
                  logLine.textContent = `[${data.latest_log.timestamp ? data.latest_log.timestamp.substring(11, 19) : ''}] ${data.latest_log.message}`;
                  asyncJobLogs.appendChild(logLine);
                  asyncJobLogs.scrollTop = asyncJobLogs.scrollHeight;
                }

                if (data.event === 'job_completed') {
                  loadCatalog();
                }
              }
            } catch (err) {}
          };

          socket.onclose = () => {
            if (wsConnectionStatus) {
              wsConnectionStatus.textContent = 'Disconnected';
              wsConnectionStatus.style.color = 'var(--muted)';
            }
            setTimeout(connectWebSocket, 3000);
          };
        } catch (e) {
          console.warn('WebSocket connection error:', e);
        }
      }

      if (btnSubmitAsyncJob && asyncBatchInput) {
        btnSubmitAsyncJob.addEventListener('click', async () => {
          const raw = asyncBatchInput.value.trim();
          if (!raw) return;

          const compounds = raw.split(',').map(c => c.trim()).filter(Boolean);
          if (!compounds.length) return;

          btnSubmitAsyncJob.disabled = true;
          btnSubmitAsyncJob.textContent = 'Submitting...';

          try {
            const resp = await fetch('/api/enrichment/jobs', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ compounds: compounds, auto_save_catalog: true })
            });

            const data = await resp.json();
            if (resp.ok) {
              if (asyncJobProgressWrap) asyncJobProgressWrap.style.display = 'block';
              if (asyncJobLogs) asyncJobLogs.innerHTML = `<div>[Job ${data.job_id}] Queued ${compounds.length} compound(s)...</div>`;
              showStatus(`Async enrichment job ${data.job_id} submitted successfully.`);
            } else {
              showError(data.detail || 'Failed to submit async job.');
            }
          } catch (err) {
            showError('Error submitting async job: ' + err.message);
          } finally {
            btnSubmitAsyncJob.disabled = false;
            btnSubmitAsyncJob.textContent = 'Run Async Job';
          }
        });
      }

      connectWebSocket();

      loadCatalog();