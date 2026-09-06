      // DOM ELEMENTS
      const searchInput = document.getElementById('compound-search-input');
      const searchDropdown = document.getElementById('search-dropdown');
      const stackItemsWrap = document.getElementById('stack-items-wrap');
      const emptyPlaceholder = document.getElementById('empty-stack-placeholder');
      const stackCountBadge = document.getElementById('stack-count-badge');
      const matrixContainer = document.getElementById('matrix-table-container');
      const breakdownsContainer = document.getElementById('breakdowns-container');
      
      const riskScoreVal = document.getElementById('risk-score-val');
      const riskBandBadge = document.getElementById('risk-band-badge');
      const riskBandText = document.getElementById('risk-band-text');
      const gaugeCircle = document.getElementById('gauge-circle');
      
      const statCompounds = document.getElementById('stat-compounds-count');
      const statConflicts = document.getElementById('stat-conflicts-count');
      const statSynergies = document.getElementById('stat-synergies-count');
      const statOrganLoad = document.getElementById('stat-organ-load');
      const summaryNarrative = document.getElementById('summary-narrative');

      const inspectorModal = document.getElementById('inspector-modal');
      const modalCloseBtn = document.getElementById('modal-close-btn');

      // PRESET DROPDOWN TOGGLE
      const presetBtn = document.getElementById('preset-menu-btn');
      const presetMenu = document.getElementById('preset-menu');
      if (presetBtn && presetMenu) {
        presetBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          presetMenu.classList.toggle('open');
        });
        document.addEventListener('click', (e) => {
          if (!presetMenu.contains(e.target) && !presetBtn.contains(e.target)) {
            presetMenu.classList.remove('open');
          }
        });
      }

      // GUIDE MODAL
      const guideBtn = document.getElementById('how-it-works-btn');
      const guideModal = document.getElementById('guide-modal');
      const guideCloseBtn = document.getElementById('guide-close-btn');
      if (guideBtn && guideModal) {
        guideBtn.addEventListener('click', () => guideModal.classList.add('open'));
        if (guideCloseBtn) guideCloseBtn.addEventListener('click', () => guideModal.classList.remove('open'));
        guideModal.addEventListener('click', (e) => {
          if (e.target === guideModal) guideModal.classList.remove('open');
        });
      }

      // MODALITY FILTER & DEBOUNCED SEARCH (Instant cache + fast streaming typeahead)
      window.currentSearchModality = 'all';

      window.setSearchModality = function(modality, btn) {
        window.currentSearchModality = modality || 'all';
        const bar = document.getElementById('search-modality-bar');
        if (bar) {
          bar.querySelectorAll('.search-mod-btn').forEach(b => b.classList.remove('active'));
        }
        if (btn) {
          btn.classList.add('active');
        } else if (bar) {
          const target = bar.querySelector(`.search-mod-btn[data-modality="${window.currentSearchModality}"]`);
          if (target) target.classList.add('active');
        }

        const input = document.getElementById('compound-search-input');
        if (input && input.value.trim().length > 0) {
          input.dispatchEvent(new Event('input'));
        }
      };

      function getModalityBadgeHtml(c) {
        if (!c) return '';
        const mod = String(c.modality || '').toLowerCase();
        const drugClass = String(c.drug_class || '').toLowerCase();
        const cName = String(c.name || '').toLowerCase();
        if (mod === 'peptide' || c.is_peptide || drugClass.includes('peptide') || drugClass.includes('glp-1')) {
          return `<span class="search-mod-badge badge-peptide"><i data-lucide="dna" class="icon-xs icon-teal"></i> Peptide</span>`;
        }
        if (mod === 'biologic_antibody' || c.is_biologic || drugClass.includes('biologic') || drugClass.includes('antibody') || drugClass.includes('mab') || cName.endsWith('mab')) {
          return `<span class="search-mod-badge badge-biologic"><i data-lucide="shield" class="icon-xs icon-purple"></i> Biologic</span>`;
        }
        if (mod === 'botanical_natural' || c.is_botanical || drugClass.includes('botanical') || drugClass.includes('herb') || drugClass.includes('phytochemical')) {
          return `<span class="search-mod-badge badge-botanical"><i data-lucide="leaf" class="icon-xs icon-emerald"></i> Botanical</span>`;
        }
        if (mod === 'combination_drug' || c.is_combination || drugClass.includes('combination') || cName.includes('combo')) {
          return `<span class="search-mod-badge badge-combo"><i data-lucide="layers" class="icon-xs icon-amber"></i> Combo</span>`;
        }
        if (mod === 'small_molecule' || (!c.is_peptide && !c.is_biologic && !c.is_botanical && !c.is_combination)) {
          return `<span class="search-mod-badge badge-small-molecule"><i data-lucide="atom" class="icon-xs icon-blue"></i> Small Molecule</span>`;
        }
        return '';
      }

      const searchLoadingSpinner = document.getElementById('search-loading-spinner');
      function setSearchSpinnerVisible(visible) {
        if (searchLoadingSpinner) searchLoadingSpinner.style.display = visible ? 'flex' : 'none';
      }

      let searchTimeout = null;
      let searchAbortController = null;
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchTimeout);
        if (searchAbortController) {
          searchAbortController.abort();
          searchAbortController = null;
        }
        if (!query) {
          setSearchSpinnerVisible(false);
          searchDropdown.style.display = 'none';
          return;
        }

        const normQ = query.toLowerCase();
        const activeModality = window.currentSearchModality || 'all';
        const cacheKey = `${normQ}::${activeModality}`;

        // 1. Instant Cache Check (< 0.01ms)
        if (_searchQueryCache[cacheKey]) {
          setSearchSpinnerVisible(false);
          renderSearchDropdown(_searchQueryCache[cacheKey], true);
          return;
        }

        // 2. Instant Local Catalog Search (< 0.05ms)
        const localMatches = typeof window.filterLocalCatalogIndex === 'function'
          ? window.filterLocalCatalogIndex(query, activeModality)
          : [];

        if (localMatches.length > 0) {
          renderSearchDropdown(localMatches, false);
          const first = localMatches[0];
          const isExact = first && (first.name.toLowerCase() === normQ || first.key.toLowerCase() === normQ);
          // If exact match or 4+ strong local matches, finalize instantly without network delay
          if (isExact || localMatches.length >= 4) {
            setSearchSpinnerVisible(false);
            _searchQueryCache[cacheKey] = localMatches;
            renderSearchDropdown(localMatches, true);
            return;
          }
        } else {
          renderSearchDropdown([], false);
        }

        // 3. Debounced streaming search for external/novel compounds
        searchTimeout = setTimeout(async () => {
          searchAbortController = new AbortController();
          const signal = searchAbortController.signal;

          let accumulatedItems = localMatches.slice();
          let isStreamingDone = false;
          setSearchSpinnerVisible(true);

          try {
            const modalityParam = activeModality !== 'all' ? `&modality=${encodeURIComponent(activeModality)}` : '';
            const response = await fetch(`/api/compounds/search/stream?q=${encodeURIComponent(query)}${modalityParam}`, { signal });
            if (!response.ok || !response.body) {
              throw new Error(`Streaming request failed with status ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEvent = 'message';

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop();

              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) {
                  currentEvent = 'message';
                  continue;
                }
                if (trimmed.startsWith('event:')) {
                  currentEvent = trimmed.slice(6).trim();
                } else if (trimmed.startsWith('data:')) {
                  const dataStr = trimmed.startsWith('data: ') ? trimmed.slice(6) : trimmed.slice(5);
                  let dataVal;
                  try {
                    dataVal = JSON.parse(dataStr);
                  } catch (e) {
                    dataVal = dataStr;
                  }

                  if (currentEvent === 'local') {
                    if (Array.isArray(dataVal) && dataVal.length) {
                      accumulatedItems = dataVal;
                      dataVal.forEach(item => {
                        if (item && item.key) {
                          _clientCatalogCache[item.key] = item;
                          if (item.key.includes('_')) _clientCatalogCache[item.key.replace(/_/g, '-')] = item;
                        }
                      });
                      if (searchInput.value.trim().toLowerCase() === normQ && (window.currentSearchModality || 'all') === activeModality) {
                        renderSearchDropdown(accumulatedItems, false);
                      }
                    }
                  } else if (currentEvent === 'candidates') {
                    if (Array.isArray(dataVal) && dataVal.length) {
                      const seen = new Set(accumulatedItems.map(x => x.key));
                      dataVal.forEach(item => {
                        if (item && item.key && !seen.has(item.key)) {
                          seen.add(item.key);
                          accumulatedItems.push(item);
                          _clientCatalogCache[item.key] = item;
                          if (item.key.includes('_')) _clientCatalogCache[item.key.replace(/_/g, '-')] = item;
                        }
                      });
                      if (searchInput.value.trim().toLowerCase() === normQ && (window.currentSearchModality || 'all') === activeModality) {
                        renderSearchDropdown(accumulatedItems, false);
                      }
                    }
                  } else if (currentEvent === 'done') {
                    isStreamingDone = true;
                    setSearchSpinnerVisible(false);
                    _searchQueryCache[cacheKey] = accumulatedItems;
                    if (searchInput.value.trim().toLowerCase() === normQ && (window.currentSearchModality || 'all') === activeModality) {
                      renderSearchDropdown(accumulatedItems, true);
                    }
                  }
                }
              }
            }

            setSearchSpinnerVisible(false);
            if (!isStreamingDone) {
              _searchQueryCache[cacheKey] = accumulatedItems;
              if (searchInput.value.trim().toLowerCase() === normQ && (window.currentSearchModality || 'all') === activeModality) {
                renderSearchDropdown(accumulatedItems, true);
              }
            }
          } catch (err) {
            setSearchSpinnerVisible(false);
            if (err.name !== 'AbortError') {
              console.error('Search stream error:', err);
              renderSearchDropdown(accumulatedItems, true);
            }
          }
        }, 150);
      });

      function renderSearchDropdown(items, isDone = true) {
        if (!items || !items.length) {
          if (isDone) {
            searchDropdown.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 0.84rem;">No compounds found.</div>';
            searchDropdown.style.display = 'block';
          } else {
            searchDropdown.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 0.84rem; display: flex; align-items: center; gap: 8px;"><div class="copilot-loading-spinner" style="width: 14px; height: 14px; border-width: 2px;"></div>Searching catalog & online registries...</div>';
            searchDropdown.style.display = 'block';
          }
          return;
        }

        const itemsHtml = items.map(c => `
          <div class="search-item" data-key="${escapeHtml(c.key)}">
            <div class="search-item-info">
              <span class="search-item-name">
                ${escapeHtml(c.name)}
                ${getModalityBadgeHtml(c)}
                ${c.is_external ? `<span style="font-size:0.68rem; padding:1px 6px; border-radius:4px; background: rgba(59,130,246,0.15); color: #60a5fa; margin-left: 6px; font-weight: 500;">${escapeHtml(c.source_registry || 'Online Registry')}</span>` : ''}
              </span>
              <span class="search-item-class">${escapeHtml(c.drug_class || 'Compound')}</span>
            </div>
            <span class="search-item-add-btn">${c.is_external ? '+ Enrich & Add' : '+ Add'}</span>
          </div>
        `).join('');

        const spinnerHtml = isDone ? '' : '<div style="padding: 6px 12px; color: var(--text-muted); font-size: 0.74rem; display: flex; align-items: center; gap: 6px; border-top: 1px solid var(--border-subtle, rgba(255,255,255,0.06));"><div class="copilot-loading-spinner" style="width: 11px; height: 11px; border-width: 1.5px;"></div>Searching online registries...</div>';

        searchDropdown.innerHTML = itemsHtml + spinnerHtml;
        searchDropdown.style.display = 'block';
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }

      // GLOBAL DELEGATION FOR QUICK TAGS, SEARCH ITEMS, AND DROPDOWN CLOSE
      document.addEventListener('click', (e) => {
        const quickTag = e.target.closest('.quick-tag');
        if (quickTag && quickTag.dataset.key) {
          e.preventDefault();
          addCompoundKey(quickTag.dataset.key);
          return;
        }
        const searchItem = e.target.closest('.search-item');
        if (searchItem && searchItem.dataset.key) {
          e.preventDefault();
          addCompoundKey(searchItem.dataset.key);
          if (searchInput) searchInput.value = '';
          if (searchDropdown) searchDropdown.style.display = 'none';
          return;
        }
        if (searchInput && searchDropdown && !searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
          searchDropdown.style.display = 'none';
        }
      });

      function getDefaultDoseFallback(key) {
        const k = String(key || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        if (k.includes('clenbuterol')) return { dose: 40, unit: 'μg', route: 'oral' };
        if (k.includes('clonidine')) return { dose: 100, unit: 'μg', route: 'oral' };
        if (k.includes('alprazolam')) return { dose: 0.5, unit: 'mg', route: 'oral' };
        if (k.includes('nebivolol')) return { dose: 5, unit: 'mg', route: 'oral' };
        if (k.includes('caffeine')) return { dose: 150, unit: 'mg', route: 'oral' };
        if (k.includes('theanine')) return { dose: 200, unit: 'mg', route: 'oral' };
        if (k.includes('creatine')) return { dose: 5, unit: 'g', route: 'oral' };
        if (k.includes('citrulline')) return { dose: 6, unit: 'g', route: 'oral' };
        if (k.includes('betaalanine')) return { dose: 3.2, unit: 'g', route: 'oral' };
        if (k.includes('yohimbine')) return { dose: 5, unit: 'mg', route: 'oral' };
        if (k.includes('telmisartan')) return { dose: 40, unit: 'mg', route: 'oral' };
        if (k.includes('curcumin')) return { dose: 500, unit: 'mg', route: 'oral' };
        if (k.includes('nattokinase')) return { dose: 100, unit: 'mg', route: 'oral' };
        if (k.includes('piperine')) return { dose: 10, unit: 'mg', route: 'oral' };
        if (k.includes('bacopa')) return { dose: 300, unit: 'mg', route: 'oral' };
        if (k.includes('lcarnitine') || k.includes('carnitine')) return { dose: 500, unit: 'mg', route: 'oral' };
        if (k.includes('coq10')) return { dose: 100, unit: 'mg', route: 'oral' };
        if (k.includes('citrusbergamot') || k.includes('bergamot')) return { dose: 500, unit: 'mg', route: 'oral' };
        if (k.includes('anastrozole')) return { dose: 0.25, unit: 'mg', route: 'oral' };
        if (k.includes('tudca')) return { dose: 250, unit: 'mg', route: 'oral' };
        if (k.includes('taurine')) return { dose: 2, unit: 'g', route: 'oral' };
        if (k.includes('magnesium')) return { dose: 400, unit: 'mg', route: 'oral' };
        if (k.includes('melatonin')) return { dose: 1, unit: 'mg', route: 'oral' };
        if (k.includes('tartcherry')) return { dose: 500, unit: 'mg', route: 'oral' };
        if (k.includes('metformin')) return { dose: 500, unit: 'mg', route: 'oral' };
        if (k.includes('empagliflozin')) return { dose: 10, unit: 'mg', route: 'oral' };
        if (k.includes('semaglutide') || k.includes('bpc157')) return { dose: 0.25, unit: 'mg', route: 'subcutaneous' };
        if (k.includes('testosterone') || k.includes('nandrolone') || k.includes('trenbolone') || k.includes('boldenone') || k.includes('drostanolone')) return { dose: 100, unit: 'mg', route: 'intramuscular' };
        if (k.includes('tadalafil')) return { dose: 5, unit: 'mg', route: 'oral' };
        if (k.includes('sildenafil')) return { dose: 50, unit: 'mg', route: 'oral' };
        if (k.includes('finasteride')) return { dose: 1, unit: 'mg', route: 'oral' };
        return { dose: 10, unit: 'mg', route: 'oral' };
      }

      function matchCompoundItem(stack, targetKey) {
        if (!stack || !stack.length || !targetKey) return null;
        const normTarget = String(targetKey).trim().toLowerCase().split(':')[0].replace(/[^a-z0-9]/g, '');
        return stack.find(c => {
          const normKey = String(c.key || '').trim().toLowerCase().split(':')[0].replace(/[^a-z0-9]/g, '');
          const normName = String(c.name || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '');
          return normKey === normTarget || normName === normTarget || (normKey && normTarget && (normKey.includes(normTarget) || normTarget.includes(normKey)));
        }) || null;
      }

      const _pendingLoadingCompounds = new Map();
      window._pendingLoadingCompounds = _pendingLoadingCompounds;

      function addCompoundKey(key) {
        if (!key) return;
        const cleanKey = String(key).trim().toLowerCase().split(':')[0];
        if (!cleanKey || matchCompoundItem(state.stack, cleanKey)) return;
        if (_pendingLoadingCompounds.has(cleanKey)) return;

        // Fast path: cached client record
        const cached = _clientCatalogCache[cleanKey] || _clientCatalogCache[cleanKey.replace(/-/g, '_')];
        if (cached) {
          const fallback = getDefaultDoseFallback(cached.key || cleanKey);
          const defDose = cached.default_dose || {};
          const doseVal = defDose.dose_val !== undefined ? defDose.dose_val : (cached.dose !== undefined ? cached.dose : fallback.dose);
          const doseUnit = defDose.dose_unit || cached.unit || fallback.unit;
          const routeVal = cached.route || cached.default_route || fallback.route || 'oral';

          state.stack.push({
            key: cached.key || cleanKey,
            name: cached.name || cleanKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
            drug_class: cached.drug_class || 'Compound',
            mechanism: cached.mechanism || '',
            dose: doseVal,
            unit: doseUnit,
            frequency: 'daily',
            timing: 'morning',
            route: routeVal,
          });
          showToast(`Added ${cached.name || cleanKey}`, 'check');
          syncAndEvaluateStack();
          return;
        }

        const displayLabel = cleanKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const abortController = new AbortController();
        _pendingLoadingCompounds.set(cleanKey, {
          key: cleanKey,
          name: displayLabel,
          abortController,
          startedAt: Date.now()
        });

        setSearchSpinnerVisible(true);
        // Render immediately so user sees the new loading card alongside current stack
        renderStackList();

        fetch(`/catalog/${encodeURIComponent(cleanKey)}`, { signal: abortController.signal })
          .then(res => {
            if (!res.ok) throw new Error('Compound not found');
            return res.json();
          })
          .then(compound => {
            if (!_pendingLoadingCompounds.has(cleanKey)) return;
            _pendingLoadingCompounds.delete(cleanKey);
            if (!_pendingLoadingCompounds.size) setSearchSpinnerVisible(false);

            _clientCatalogCache[cleanKey] = compound;
            if (compound.key) _clientCatalogCache[compound.key] = compound;
            const fallback = getDefaultDoseFallback(compound.key || cleanKey);
            const defDose = compound.default_dose || {};
            const doseVal = defDose.dose_val !== undefined ? defDose.dose_val : (compound.dose !== undefined ? compound.dose : fallback.dose);
            const doseUnit = defDose.dose_unit || compound.unit || fallback.unit;
            const routeVal = compound.route || compound.default_route || fallback.route || 'oral';

            if (!matchCompoundItem(state.stack, compound.key || cleanKey)) {
              state.stack.push({
                key: compound.key || cleanKey,
                name: compound.name || cleanKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                drug_class: compound.drug_class || 'Compound',
                mechanism: compound.mechanism || '',
                dose: doseVal,
                unit: doseUnit,
                frequency: 'daily',
                timing: 'morning',
                route: routeVal,
              });
              showToast(`Added ${compound.name || cleanKey}`, 'check');
            }
            syncAndEvaluateStack();
          })
          .catch((err) => {
            if (err && err.name === 'AbortError') {
              return; // Cancelled intentionally via removeCompoundKey
            }
            if (!_pendingLoadingCompounds.has(cleanKey)) return;
            _pendingLoadingCompounds.delete(cleanKey);
            if (!_pendingLoadingCompounds.size) setSearchSpinnerVisible(false);

            const fallback = getDefaultDoseFallback(cleanKey);
            if (!matchCompoundItem(state.stack, cleanKey)) {
              state.stack.push({
                key: cleanKey,
                name: cleanKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                drug_class: 'Custom Compound',
                dose: fallback.dose,
                unit: fallback.unit,
                frequency: 'daily',
                timing: 'morning',
                route: fallback.route || 'oral',
              });
              showToast(`Added ${cleanKey}`, 'check');
            }
            syncAndEvaluateStack();
          });
      }

      function removeCompoundKey(key) {
        if (!key) return;
        const cleanKey = String(key).trim().toLowerCase().split(':')[0];

        // Check if deleting a currently loading compound
        let matchedPendingKey = null;
        if (_pendingLoadingCompounds.has(cleanKey)) {
          matchedPendingKey = cleanKey;
        } else {
          for (const [pKey, pVal] of _pendingLoadingCompounds.entries()) {
            if (pKey === cleanKey || pVal.name.toLowerCase() === cleanKey || pKey.replace(/[^a-z0-9]/g, '') === cleanKey.replace(/[^a-z0-9]/g, '')) {
              matchedPendingKey = pKey;
              break;
            }
          }
        }

        if (matchedPendingKey) {
          const pending = _pendingLoadingCompounds.get(matchedPendingKey);
          if (pending && pending.abortController) {
            try { pending.abortController.abort(); } catch (e) {}
          }
          _pendingLoadingCompounds.delete(matchedPendingKey);
          if (!_pendingLoadingCompounds.size) setSearchSpinnerVisible(false);
          showToast(`Removed ${pending.name || matchedPendingKey}`, 'x');
          syncAndEvaluateStack();
          return;
        }

        const item = matchCompoundItem(state.stack, key);
        if (item) {
          state.stack = state.stack.filter(c => c !== item);
          showToast(`Removed ${item.name}`, 'x');
          syncAndEvaluateStack();
        }
      }

      let _evalDebounce = null;
      function debouncedEvaluate() {
        clearTimeout(_evalDebounce);
        _evalDebounce = setTimeout(() => evaluateStack(), 180);
      }

      function syncAndEvaluateStack() {
        renderStackList();
        debouncedEvaluate();
      }

      function persistAndEvaluate() {
        try {
          localStorage.setItem('healthai_stack', JSON.stringify(state.stack));
          window.dispatchEvent(new CustomEvent('healthai:stack-updated'));
        } catch (e) { /* ignore */ }

        const keys = state.stack.map(c => {
          const u = (c.unit || 'mg').replace('μg', 'ug');
          const freq = c.frequency || 'daily';
          const route = c.route || 'oral';
          return `${encodeURIComponent(c.key)}:${c.dose}${u}:${freq}:${route}`;
        }).join(',');
        const targetUrl = keys ? `/graph?stack=${keys}&timeline=${state.timeline || 'steady_state'}` : '/graph';
        const graphLink = document.getElementById('nav-graph-link');
        if (graphLink) graphLink.href = targetUrl;
        const openBtn = document.getElementById('open-full-graph-btn');
        if (openBtn) openBtn.href = targetUrl;

        debouncedEvaluate();
      }

      function renderStackList() {
        if (stackCountBadge) {
          if (_pendingLoadingCompounds && _pendingLoadingCompounds.size > 0) {
            stackCountBadge.textContent = `${state.stack.length} items (${_pendingLoadingCompounds.size} loading)`;
          } else {
            stackCountBadge.textContent = `${state.stack.length} items`;
          }
        }
        if (statCompounds) statCompounds.textContent = state.stack.length;

        try {
          localStorage.setItem('healthai_stack', JSON.stringify(state.stack));
          window.dispatchEvent(new CustomEvent('healthai:stack-updated'));
        } catch (e) {
          console.warn('localStorage error', e);
        }

        const keys = state.stack.map(c => {
          const u = (c.unit || 'mg').replace('μg', 'ug');
          const freq = c.frequency || 'daily';
          const route = c.route || 'oral';
          return `${encodeURIComponent(c.key)}:${c.dose}${u}:${freq}:${route}`;
        }).join(',');
        const targetUrl = keys ? `/graph?stack=${keys}&timeline=${state.timeline || 'steady_state'}` : '/graph';
        const graphLink = document.getElementById('nav-graph-link');
        if (graphLink) graphLink.href = targetUrl;
        const openBtn = document.getElementById('open-full-graph-btn');
        if (openBtn) openBtn.href = targetUrl;

        const hasActive = state.stack.length > 0;
        const hasPending = _pendingLoadingCompounds && _pendingLoadingCompounds.size > 0;

        if (!hasActive && !hasPending) {
          if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';
          if (stackItemsWrap) {
            stackItemsWrap.innerHTML = '';
            stackItemsWrap.appendChild(emptyPlaceholder);
          }
          return;
        }

        if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
        if (!stackItemsWrap) return;

        const stackCardsHtml = state.stack.map(c => {
          const unit = c.unit || 'mg';
          const freq = c.frequency || 'daily';
          const route = c.route || 'oral';
          const mult = getFrequencyMultiplierClient(freq);
          const effDaily = c.dose * mult;
          const effDisplay = mult !== 1.0 
            ? `≈ ${effDaily >= 1.0 ? effDaily.toFixed(effDaily >= 10 ? 1 : 2) : (effDaily * 1000).toFixed(1)} ${effDaily >= 1.0 ? unit : (unit === 'mg' ? 'μg' : unit)}/day`
            : '';

          let timing = (c.timing || 'morning').toLowerCase();
          if (timing.includes('bed') || timing.includes('night')) timing = 'before bed';
          else if (timing.includes('eve') || timing.includes('dinner')) timing = 'evening';
          else if (timing.includes('mid') || timing.includes('noon') || timing.includes('afternoon') || timing.includes('lunch')) timing = 'midday';
          else if (timing.includes('pre-workout') || timing.includes('preworkout')) timing = 'pre-workout';
          else if (timing !== 'morning' && timing !== 'midday' && timing !== 'pre-workout' && timing !== 'evening' && timing !== 'before bed') timing = 'morning';

          return `
            <div class="stack-item-card" data-key="${escapeHtml(c.key)}">
              <div class="stack-item-top">
                <div class="stack-item-name-group">
                  <span class="stack-item-name">${escapeHtml(c.name)}</span>
                  <span class="stack-item-class">${escapeHtml(c.drug_class || 'Compound')}</span>
                </div>
                <div class="stack-item-actions">
                  <button type="button" class="stack-item-graph-btn" onclick="switchToGraphTab('${escapeHtml(c.key)}')" title="Inspect in Knowledge Graph" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('network', { class: 'icon-xs' })} Graph</button>
                  <a href="/compound?key=${encodeURIComponent(c.key)}" target="_blank" class="stack-item-link-btn" title="View Deep Pharmacology">↗</a>
                  <button class="stack-item-remove-btn" onclick="removeCompoundKey('${escapeHtml(c.key)}')" title="Remove">&times;</button>
                </div>
              </div>
              <div class="stack-item-controls-wrap">
                <div class="stack-item-row stack-item-dose-row">
                  <div class="stack-item-dose-group">
                    <input 
                      type="number" 
                      class="control-input stack-dose-input" 
                      min="0" 
                      step="any" 
                      value="${c.dose}" 
                      oninput="updateDoseVal('${escapeHtml(c.key)}', this.value)"
                      onchange="updateDoseVal('${escapeHtml(c.key)}', this.value)" 
                      title="Administered dose amount"
                    />
                    <select 
                      class="control-select stack-unit-select" 
                      onchange="updateDoseUnit('${escapeHtml(c.key)}', this.value)"
                      title="Select dose unit"
                    >
                      <option value="mg" ${unit === 'mg' ? 'selected' : ''}>mg</option>
                      <option value="μg" ${unit === 'μg' || unit === 'ug' || unit === 'mcg' ? 'selected' : ''}>μg</option>
                      <option value="g" ${unit === 'g' ? 'selected' : ''}>g</option>
                      <option value="IU" ${unit === 'IU' ? 'selected' : ''}>IU</option>
                    </select>
                  </div>
                  <select class="control-select stack-timing-select" onchange="updateTiming('${escapeHtml(c.key)}', this.value)" title="Time of day">
                    <option value="morning" ${timing === 'morning' ? 'selected' : ''}>Morning</option>
                    <option value="midday" ${timing === 'midday' ? 'selected' : ''}>Midday</option>
                    <option value="pre-workout" ${timing === 'pre-workout' ? 'selected' : ''}>Pre-Workout</option>
                    <option value="evening" ${timing === 'evening' ? 'selected' : ''}>Evening</option>
                    <option value="before bed" ${timing === 'before bed' || timing === 'bedtime' ? 'selected' : ''}>Before Bed</option>
                  </select>
                </div>
                <div class="stack-item-row stack-item-route-row">
                  <select 
                    class="control-select stack-route-select" 
                    onchange="updateRoute('${escapeHtml(c.key)}', this.value)" 
                    title="Route of administration"
                  >
                    <option value="oral" ${route === 'oral' ? 'selected' : ''}>Oral (PO)</option>
                    <option value="sublingual" ${route === 'sublingual' ? 'selected' : ''}>Sublingual (SL)</option>
                    <option value="subcutaneous" ${route === 'subcutaneous' ? 'selected' : ''}>Subcutaneous (SC)</option>
                    <option value="intramuscular" ${route === 'intramuscular' ? 'selected' : ''}>Intramuscular (IM)</option>
                    <option value="transdermal" ${route === 'transdermal' ? 'selected' : ''}>Transdermal (TD)</option>
                    <option value="intravenous" ${route === 'intravenous' ? 'selected' : ''}>Intravenous (IV)</option>
                    <option value="inhalation" ${route === 'inhalation' ? 'selected' : ''}>Inhalation (IN)</option>
                  </select>
                  <select 
                    class="control-select stack-freq-select" 
                    onchange="updateFrequency('${escapeHtml(c.key)}', this.value)" 
                    title="Dosing frequency"
                  >
                    <option value="daily" ${freq === 'daily' ? 'selected' : ''}>Once Daily (QD)</option>
                    <option value="twice_daily" ${freq === 'twice_daily' ? 'selected' : ''}>Twice Daily (BID)</option>
                    <option value="three_times_daily" ${freq === 'three_times_daily' ? 'selected' : ''}>Three Times Daily (TID)</option>
                    <option value="four_times_daily" ${freq === 'four_times_daily' ? 'selected' : ''}>Four Times Daily (QID)</option>
                    <option value="every_other_day" ${freq === 'every_other_day' ? 'selected' : ''}>Every Other Day (QOD)</option>
                    <option value="three_times_weekly" ${freq === 'three_times_weekly' ? 'selected' : ''}>Three Times Weekly (3x/wk)</option>
                    <option value="twice_weekly" ${freq === 'twice_weekly' ? 'selected' : ''}>Twice Weekly (2x/wk)</option>
                    <option value="weekly" ${freq === 'weekly' ? 'selected' : ''}>Once Weekly (QW)</option>
                    <option value="biweekly" ${freq === 'biweekly' ? 'selected' : ''}>Every 2 Weeks (Q2W)</option>
                    <option value="monthly" ${freq === 'monthly' ? 'selected' : ''}>Monthly (QM)</option>
                    <option value="as_needed" ${freq === 'as_needed' ? 'selected' : ''}>As Needed (PRN)</option>
                  </select>
                </div>
                ${effDisplay ? `<div class="stack-item-eff-row"><span class="eff-daily-badge" title="Effective continuous 24h baseline load">${effDisplay}</span></div>` : ''}
              </div>
            </div>
          `;
        }).join('');

        let loadingCardsHtml = '';
        if (hasPending) {
          _pendingLoadingCompounds.forEach((item, pKey) => {
            const loadingCardId = `stack-loading-${pKey.replace(/[^a-z0-9]/g, '-')}`;
            loadingCardsHtml += `
              <div id="${loadingCardId}" class="stack-item-loading-card" data-key="${escapeHtml(pKey)}">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span class="copilot-loading-spinner" style="width: 14px; height: 14px; border-width: 2px;"></span>
                  <div>
                    <div style="font-size: 0.84rem; font-weight: 600; color: #f8fafc;">Loading ${escapeHtml(item.name)}…</div>
                    <div style="font-size: 0.70rem; color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace;">Fetching pharmacology & online registries</div>
                  </div>
                </div>
                <div class="stack-item-actions" style="margin-left: auto;">
                  <button type="button" class="stack-item-remove-btn" onclick="removeCompoundKey('${escapeHtml(pKey)}')" title="Cancel">&times;</button>
                </div>
              </div>
            `;
          });
        }

        stackItemsWrap.innerHTML = stackCardsHtml + loadingCardsHtml;
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }

      window.updateDoseVal = (key, val) => {
        const parsed = parseFloat(val);
        if (isNaN(parsed) || parsed <= 0) return;
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          item.dose = parsed;
          persistAndEvaluate();
          // Update the card's effective daily badge immediately without recreating DOM
          const card = document.querySelector(`.stack-item-card[data-key="${CSS.escape(item.key)}"]`);
          if (card) {
            const mult = getFrequencyMultiplierClient(item.frequency);
            const effDaily = item.dose * mult;
            const effSpan = card.querySelector('.eff-daily-badge');
            if (effSpan && mult !== 1.0) {
              const u = item.unit || 'mg';
              effSpan.textContent = `≈ ${effDaily >= 1.0 ? effDaily.toFixed(effDaily >= 10 ? 1 : 2) : (effDaily * 1000).toFixed(1)} ${effDaily >= 1.0 ? u : (u === 'mg' ? 'μg' : u)}/day`;
            }
          }
        }
      };

      window.updateDoseUnit = (key, unit) => {
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          item.unit = unit || 'mg';
          persistAndEvaluate();
        }
      };

      window.updateTiming = (key, val) => {
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          item.timing = val || 'morning';
          persistAndEvaluate();
        }
      };

      window.updateRoute = (key, val) => {
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          item.route = val || 'oral';
          persistAndEvaluate();
        }
      };

      window.updateFrequency = (key, val) => {
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          item.frequency = val || 'daily';
          persistAndEvaluate();
          renderStackList();
        }
      };

      window.setStackTimeline = (timelineKey) => {
        state.timeline = timelineKey;
        evaluateStack();
      };

      window.removeCompoundKey = removeCompoundKey;
      window.addCompoundKey = addCompoundKey;
      window.syncAndEvaluateStack = syncAndEvaluateStack;
      window.renderStackList = renderStackList;

      // BIOMARKER & DEMOGRAPHICS INPUT LISTENERS (SIDEBAR, BUILDER MODAL, COPILOT DRAWER)
      ['bio', 'builder-bio', 'copilot-bio'].forEach(prefix => {
        BIO_FIELDS.forEach(f => {
          const el = document.getElementById(`${prefix}-${f.key}`);
          if (!el) return;
          const handler = () => {
            syncAllBiometrics(prefix, true);
          };
          el.addEventListener('input', handler);
          el.addEventListener('change', handler);
        });
      });

      const clearStackBtn = document.getElementById('clear-stack-btn');
      if (clearStackBtn) {
        clearStackBtn.addEventListener('click', () => {
          if (_pendingLoadingCompounds && _pendingLoadingCompounds.size > 0) {
            _pendingLoadingCompounds.forEach((item) => {
              if (item && item.abortController) {
                try { item.abortController.abort(); } catch (e) {}
              }
            });
            _pendingLoadingCompounds.clear();
          }
          setSearchSpinnerVisible(false);
          state.stack = [];
          state.analysis = null;
          renderStackList();
          if (typeof evaluateStack === 'function') {
            evaluateStack();
          } else if (typeof updateDashboardEmpty === 'function') {
            updateDashboardEmpty();
          }
          if (typeof syncCopilotStackTags === 'function') {
            syncCopilotStackTags();
          }
          if (typeof syncGraphData === 'function') {
            syncGraphData(false);
          }
          // Reset action buttons across copilot chat cards
          document.querySelectorAll('.copilot-compound-chip').forEach(chip => {
            const actionEl = chip.querySelector('.copilot-chip-action, .copilot-chip-quick-add-btn');
            if (actionEl) {
              actionEl.className = 'copilot-chip-quick-add-btn add';
              actionEl.textContent = '+ ADD';
            }
          });
          document.querySelectorAll('.copilot-compound-inspector').forEach(ins => {
            const btn = ins.querySelector('.btn-inspector-add');
            if (btn) {
              btn.className = 'btn-inspector-add';
              const name = ins.querySelector('.copilot-inspector-title span')?.textContent?.replace('🔍 ', '') || 'Compound';
              btn.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('plus', { class: 'icon-xs' })} Add ${escapeHtml(name)} to Workbench Stack</span>`;
            }
          });
          document.querySelectorAll('.btn-apply-diff').forEach(btn => {
            btn.classList.remove('applied');
            btn.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('zap', { class: 'icon-xs' })} Apply Protocol to Workbench Stack</span>`;
          });
          showToast('Stack cleared', 'trash-2');
        });
      }

      const exportJsonBtn = document.getElementById('export-json-btn');
      if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', () => {
          const payload = {
            timestamp: new Date().toISOString(),
            stack: state.stack,
            biomarkers: state.biomarkers,
            analysis: state.analysis,
          };
          const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `healthai-pharmacology-audit-${Date.now()}.json`;
          a.click();
          showToast('Audit JSON downloaded', 'download');
        });
      }

