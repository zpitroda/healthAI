const state = {
        stack: [],
        biomarkers: {
          sex: null,
          age: null,
          weight_kg: null,
          height_cm: null,
          body_fat_pct: null,
          blood_pressure: null,
          egfr: null,
          sleep_hours: null,
          alt_u_l: null,
          hematocrit_pct: null,
        },
        analysis: null,
        activeTab: 'balance-tab',
        timeline: 'steady_state',
        axesFilter: 'all',
        axesSort: 'priority',
        experienceMode: 'standard',
      };

      const BIO_FIELDS = [
        { key: 'sex', type: 'string' },
        { key: 'age', type: 'int', default: 30 },
        { key: 'weight', type: 'float', default: 75 },
        { key: 'height', type: 'float', default: 175 },
        { key: 'bodyfat', type: 'float', default: 15 },
        { key: 'bp', type: 'float', default: 120 },
        { key: 'egfr', type: 'float', default: 95 },
        { key: 'alt', type: 'float', default: 25 },
        { key: 'sleep', type: 'float', default: 7.5 },
        { key: 'hematocrit', type: 'float', default: 46 }
      ];

      function getBiometricsPayload() {
        const bioAge = document.getElementById('bio-age')?.value;
        const bioWeight = document.getElementById('bio-weight')?.value;
        const bioEgfr = document.getElementById('bio-egfr')?.value;
        const bioAlt = document.getElementById('bio-alt')?.value;
        const bioBp = document.getElementById('bio-bp')?.value;
        const bioBodyfat = document.getElementById('bio-bodyfat')?.value;
        const bioSex = document.getElementById('bio-sex')?.value;
        const bioHeight = document.getElementById('bio-height')?.value;
        const bioSleep = document.getElementById('bio-sleep')?.value;
        const bioHematocrit = document.getElementById('bio-hematocrit')?.value;

        const biometrics = {};
        if (bioAge && !isNaN(Number(bioAge))) biometrics.age = Number(bioAge);
        if (bioWeight && !isNaN(Number(bioWeight))) biometrics.weight_kg = Number(bioWeight);
        if (bioEgfr && !isNaN(Number(bioEgfr))) biometrics.egfr = Number(bioEgfr);
        if (bioAlt && !isNaN(Number(bioAlt))) biometrics.alt_u_l = Number(bioAlt);
        if (bioBp && !isNaN(Number(bioBp))) biometrics.blood_pressure = Number(bioBp);
        if (bioBodyfat && !isNaN(Number(bioBodyfat))) biometrics.body_fat_pct = Number(bioBodyfat);
        if (bioSex) biometrics.sex = bioSex;
        if (bioHeight && !isNaN(Number(bioHeight))) biometrics.height_cm = Number(bioHeight);
        if (bioSleep && !isNaN(Number(bioSleep))) biometrics.sleep_hours = Number(bioSleep);
        if (bioHematocrit && !isNaN(Number(bioHematocrit))) biometrics.hematocrit_pct = Number(bioHematocrit);

        return biometrics;
      }

      function syncAllBiometrics(sourcePrefix = 'bio', shouldEvaluate = true) {
        BIO_FIELDS.forEach(f => {
          const srcEl = document.getElementById(`${sourcePrefix}-${f.key}`);
          if (!srcEl) return;
          const val = srcEl.value;

          // Sync into state.biomarkers
          if (f.key === 'sex') state.biomarkers.sex = val || null;
          else if (f.key === 'age') state.biomarkers.age = parseInt(val) || null;
          else if (f.key === 'weight') state.biomarkers.weight_kg = parseFloat(val) || null;
          else if (f.key === 'height') state.biomarkers.height_cm = parseFloat(val) || null;
          else if (f.key === 'bodyfat') state.biomarkers.body_fat_pct = parseFloat(val) || null;
          else if (f.key === 'bp') state.biomarkers.blood_pressure = parseFloat(val) || (val === '' ? null : 120);
          else if (f.key === 'egfr') state.biomarkers.egfr = parseFloat(val) || (val === '' ? null : 95);
          else if (f.key === 'alt') state.biomarkers.alt_u_l = parseFloat(val) || (val === '' ? null : 25);
          else if (f.key === 'sleep') state.biomarkers.sleep_hours = parseFloat(val) || (val === '' ? null : 7.5);
          else if (f.key === 'hematocrit') state.biomarkers.hematocrit_pct = parseFloat(val) || (val === '' ? null : 46);

          // Sync other two input sets
          ['bio', 'builder-bio', 'copilot-bio'].forEach(prefix => {
            if (prefix === sourcePrefix) return;
            const targetEl = document.getElementById(`${prefix}-${f.key}`);
            if (targetEl && targetEl.value !== val) {
              targetEl.value = val;
            }
          });
        });

        updateBiometricsPreviews();

        if (shouldEvaluate && typeof debouncedEvaluate === 'function') {
          debouncedEvaluate();
        }
      }

      function updateBiometricsPreviews() {
        const bio = getBiometricsPayload();
        const customItems = [];
        if (bio.sex) customItems.push(`Sex: ${bio.sex.charAt(0).toUpperCase() + bio.sex.slice(1)}`);
        if (bio.age !== undefined) customItems.push(`Age: ${bio.age}y`);
        if (bio.weight_kg !== undefined) customItems.push(`Weight: ${bio.weight_kg}kg`);
        if (bio.height_cm !== undefined) customItems.push(`Height: ${bio.height_cm}cm`);
        if (bio.body_fat_pct !== undefined) customItems.push(`BF: ${bio.body_fat_pct}%`);
        if (bio.blood_pressure !== undefined) customItems.push(`BP: ${bio.blood_pressure} mmHg`);
        if (bio.egfr !== undefined) customItems.push(`eGFR: ${bio.egfr}`);
        if (bio.alt_u_l !== undefined) customItems.push(`ALT: ${bio.alt_u_l} U/L`);
        if (bio.sleep_hours !== undefined) customItems.push(`Sleep: ${bio.sleep_hours}h`);
        if (bio.hematocrit_pct !== undefined) customItems.push(`HCT: ${bio.hematocrit_pct}%`);

        // AI Stack Builder Modal Summary
        const builderSummary = document.getElementById('builder-bio-summary');
        if (builderSummary) {
          if (customItems.length) {
            builderSummary.innerHTML = `<span style="color: var(--accent-cyan); font-weight: 700;">Personalized Profile:</span> ${customItems.map(item => `<span class="bio-chip">${escapeHtml(item)}</span>`).join(' ')} <span style="color: var(--text-muted); font-size: 0.72rem;">(Auto-scales PK & Dosing)</span>`;
          } else {
            builderSummary.innerHTML = `<span style="color: var(--text-secondary); font-style: italic;">Standard reference baseline active (75 kg, 30y, BP 120, eGFR 95, ALT 25). Click <strong>"Edit Metrics"</strong> above to personalize dosing & organ shields.</span>`;
          }
        }

        // Copilot Drawer Summary
        const copilotSummary = document.getElementById('copilot-bio-summary');
        if (copilotSummary) {
          if (customItems.length) {
            copilotSummary.innerHTML = `<span style="color: var(--accent-cyan); font-weight: 700;">👤 Profile:</span> ${customItems.slice(0, 4).map(item => `<span class="bio-chip-sm">${escapeHtml(item)}</span>`).join(' ')}${customItems.length > 4 ? ` <span style="color: var(--text-muted); font-size: 0.68rem;">+${customItems.length - 4} more</span>` : ''}`;
          } else {
            copilotSummary.innerHTML = `<span style="color: var(--text-muted);">👤 Profile: Reference Baseline (75kg, 30y)</span>`;
          }
        }

        // Sidebar Live Sync Badge
        const syncBadge = document.getElementById('biometric-sync-badge');
        if (syncBadge) {
          if (customItems.length) {
            syncBadge.textContent = `${customItems.length} Custom Metrics`;
            syncBadge.style.color = 'var(--accent-teal)';
            syncBadge.style.borderColor = 'rgba(16, 185, 129, 0.35)';
            syncBadge.style.background = 'rgba(16, 185, 129, 0.12)';
          } else {
            syncBadge.textContent = 'Reference Profile';
            syncBadge.style.color = 'var(--accent-cyan)';
            syncBadge.style.borderColor = 'rgba(0, 242, 254, 0.25)';
            syncBadge.style.background = 'rgba(0, 242, 254, 0.12)';
          }
        }
      }

      // 6 SCIENTIFICALLY GROUNDED & POWERFUL PRESET PROTOCOLS
      const PRESET_STACKS = {
        focus: [
          { key: 'caffeine', name: 'Caffeine', drug_class: 'Adenosine Receptor Antagonist', dose: 150, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'bacopa', name: 'Bacopa Monnieri', drug_class: 'Herbal Adaptogen / Nootropic', dose: 300, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'l_carnitine', name: 'L-Carnitine (ALCAR)', drug_class: 'Mitochondrial Biomolecule', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        cardio_shield: [
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'citrus_bergamot', name: 'Citrus Bergamot', drug_class: 'Cardiometabolic Flavonoid', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'coq10', name: 'Coenzyme Q10', drug_class: 'Mitochondrial Antioxidant', dose: 100, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'tadalafil', name: 'Tadalafil', drug_class: 'PDE5 Inhibitor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        trt_balance: [
          { key: 'testosterone_enanthate', name: 'Testosterone Enanthate', drug_class: 'Anabolic-Androgenic Steroid', dose: 100, unit: 'mg', frequency: 'weekly', timing: 'morning', route: 'intramuscular' },
          { key: 'anastrozole', name: 'Anastrozole', drug_class: 'Aromatase Inhibitor', dose: 0.25, unit: 'mg', frequency: 'twice_weekly', timing: 'morning', route: 'oral' },
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'tudca', name: 'TUDCA', drug_class: 'Hydrophilic Bile Acid', dose: 250, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        thermogenic_shield: [
          { key: 'clenbuterol', name: 'Clenbuterol', drug_class: 'Beta-2 Adrenergic Agonist', dose: 40, unit: 'μg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nebivolol', name: 'Nebivolol', drug_class: 'Cardioselective Beta-1 Blocker & NO Donor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'taurine', name: 'Taurine', drug_class: 'Osmolytic Amino Acid', dose: 2, unit: 'g', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        bioenhancement: [
          { key: 'curcumin', name: 'Curcumin', drug_class: 'Polyphenolic Anti-inflammatory', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'piperine', name: 'Piperine', drug_class: 'Bioavailability Enhancer', dose: 10, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nac', name: 'N-Acetyl Cysteine', drug_class: 'Glutathione Precursor', dose: 600, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        sleep_recovery: [
          { key: 'magnesium', name: 'Magnesium Glycinate', drug_class: 'Mineral / NMDA Modulator', dose: 400, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'melatonin', name: 'Melatonin', drug_class: 'Pineal Neurohormone', dose: 1, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'tart_cherry', name: 'Tart Cherry Extract', drug_class: 'Phytochemical Antioxidant', dose: 500, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' }
        ]
      };

      const _clientCatalogCache = {};
      const _searchQueryCache = {};

      function toggleBiomarkerDrawer() {
        const drawer = document.getElementById('biomarker-drawer');
        const icon = document.getElementById('biomarker-toggle-icon');
        if (!drawer) return;
        const isHidden = drawer.style.display === 'none';
        drawer.style.display = isHidden ? 'block' : 'none';
        if (icon) icon.textContent = isHidden ? '▲' : '▼';
      }
      window.toggleBiomarkerDrawer = toggleBiomarkerDrawer;

      function showToast(message, icon = '✓') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = 'toast-message';
        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(-10px)';
          toast.style.transition = 'all 0.3s ease';
          setTimeout(() => toast.remove(), 300);
        }, 3000);
      }

      function setExperienceMode(mode) {
        state.experienceMode = mode;
        const stdBtn = document.getElementById('mode-std-btn');
        const pwrBtn = document.getElementById('mode-power-btn');
        if (mode === 'power') {
          stdBtn.classList.remove('active');
          pwrBtn.classList.add('active');
          showToast('Power-User Mode: Pharmacokinetic constants & variance enabled', '🔬');
        } else {
          pwrBtn.classList.remove('active');
          stdBtn.classList.add('active');
          showToast('Standard Mode: Plain-English clinical explanations', '🩺');
        }
        if (state.analysis) {
          renderFullStackBalance(state.analysis);
          renderBreakdowns(state.analysis);
        }
      }
      window.setExperienceMode = setExperienceMode;

      async function loadPreset(presetKey) {
        const preset = PRESET_STACKS[presetKey];
        if (!preset) return;
        const menu = document.getElementById('preset-menu');
        if (menu) menu.classList.remove('open');

        // Immediately render cards into DOM with 0ms delay!
        state.stack = preset.map(item => ({
          key: item.key,
          name: item.name || item.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          drug_class: item.drug_class || 'Compound',
          mechanism: item.mechanism || '',
          dose: item.dose,
          unit: item.unit,
          frequency: item.frequency,
          timing: item.timing,
          route: item.route || 'oral',
        }));

        state.stack.forEach(c => {
          _clientCatalogCache[c.key] = c;
          if (c.key.includes('_')) _clientCatalogCache[c.key.replace(/_/g, '-')] = c;
        });

        showToast(`Loaded ${presetKey.replace(/_/g, ' ').toUpperCase()} Protocol`, '⚡');
        syncAndEvaluateStack();

        // Background hydration for full pharmacology metadata
        const missingKeys = preset.filter(p => !_clientCatalogCache[p.key]?.mechanism).map(p => p.key);
        if (missingKeys.length) {
          try {
            const batchRes = await fetch('/api/compounds/batch', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ keys: missingKeys })
            });
            if (batchRes.ok) {
              const data = await batchRes.json();
              Object.entries(data).forEach(([k, comp]) => {
                _clientCatalogCache[k] = comp;
                const match = matchCompoundItem(state.stack, k);
                if (match && comp.name) {
                  match.name = comp.name;
                  if (comp.drug_class) match.drug_class = comp.drug_class;
                  if (comp.mechanism) match.mechanism = comp.mechanism;
                }
              });
              renderStackList();
            }
          } catch (e) { /* ignore background fetch */ }
        }
      }
      window.loadPreset = loadPreset;

      function switchQuickCat(cat, btn) {
        document.querySelectorAll('.quick-cat-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.quick-tag').forEach(tag => {
          if (cat === 'all' || tag.dataset.cat === cat) {
            tag.style.display = 'inline-block';
          } else {
            tag.style.display = 'none';
          }
        });
      }
      window.switchQuickCat = switchQuickCat;

      function getFrequencyMultiplierClient(freq) {
        const f = (freq || '').toLowerCase().replace(/[^a-z0-9]/g, '_');
        if (f.includes('bid') || (f.includes('twice') && !f.includes('week'))) return 2.0;
        if (f.includes('tid') || f.includes('three')) return 3.0;
        if (f.includes('qid') || f.includes('four')) return 4.0;
        if (f.includes('qod') || f.includes('other')) return 0.5;
        if (f.includes('biw') || (f.includes('twice') && f.includes('week'))) return 2.0 / 7.0;
        if (f.includes('qw') || (f.includes('week') && !f.includes('2') && !f.includes('bi'))) return 1.0 / 7.0;
        if (f.includes('q2w') || f.includes('2_week') || f.includes('biweek')) return 1.0 / 14.0;
        if (f.includes('qm') || f.includes('month')) return 1.0 / 30.0;
        if (f.includes('prn') || f.includes('needed')) return 0.5;
        return 1.0;
      }

      function getTimelineDescription(tl) {
        const map = {
          '1_day': 'Immediate acute response: autonomic tone, heart rate, acute blood pressure reactivity, and peak biophase saturation.',
          '3_days': 'Early adaptation: autonomic steady state, renal electrolyte reabsorption shifts, and acute-phase markers.',
          '1_week': 'Sub-acute tone: initial receptor downregulation/upregulation, transaminase elevations, and early glycemic adjustments.',
          '2_weeks': 'Endocrine equilibrium: HPTA axis feedback suppression, steady transaminase response, and lipid receptor modulation.',
          '1_month': 'Hepatic lipid remodeling (4 weeks): LDL-C / HDL-C shifts, SHBG adaptation, and clinical bloodwork milestone.',
          '2_months': 'Reticulocyte maturation (8 weeks): Cumulative bone marrow erythropoietic stimulation.',
          '3_months': 'Full ~120-day erythrocyte turnover (12 weeks): Full steady-state HbA1c, hematocrit, and long-term equilibrium.',
          'steady_state': 'Theoretical long-term asymptotic steady-state biological equilibrium (100% saturation & turnover).',
        };
        return map[tl] || map['steady_state'];
      }

      function getTimelineNarrativePill(tl) {
        const map = {
          '1_day': 'Day 1 • Acute Autonomic',
          '3_days': 'Day 3 • Early Adaptation',
          '1_week': 'Week 1 • Sub-acute Tone',
          '2_weeks': 'Week 2 • Endocrine Equilibrium',
          '1_month': 'Week 4 • Lipid Remodeling',
          '2_months': 'Week 8 • Reticulocyte Response',
          '3_months': 'Week 12 • RBC Turnover',
          'steady_state': 'Steady State • Full Equilibrium',
        };
        return map[tl] || map['steady_state'];
      }

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

      // DEBOUNCED SEARCH (Instant cache + 100ms fast typeahead)
      let searchTimeout = null;
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchTimeout);
        if (!query) {
          searchDropdown.style.display = 'none';
          return;
        }

        const normQ = query.toLowerCase();
        if (_searchQueryCache[normQ]) {
          renderSearchDropdown(_searchQueryCache[normQ]);
          return;
        }

        searchTimeout = setTimeout(() => {
          fetch(`/api/compounds/search?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
              _searchQueryCache[normQ] = data;
              if (Array.isArray(data)) {
                data.forEach(item => {
                  if (item && item.key) {
                    _clientCatalogCache[item.key] = item;
                    if (item.key.includes('_')) _clientCatalogCache[item.key.replace(/_/g, '-')] = item;
                  }
                });
              }
              if (searchInput.value.trim().toLowerCase() === normQ) {
                renderSearchDropdown(data);
              }
            })
            .catch(err => console.error(err));
        }, 100);
      });

      function renderSearchDropdown(items) {
        if (!items || !items.length) {
          searchDropdown.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 0.84rem;">No compounds found.</div>';
          searchDropdown.style.display = 'block';
          return;
        }

        searchDropdown.innerHTML = items.map(c => `
          <div class="search-item" data-key="${c.key}">
            <div class="search-item-info">
              <span class="search-item-name">${c.name}</span>
              <span class="search-item-class">${c.drug_class || 'Compound'}</span>
            </div>
            <span class="search-item-add-btn">+ Add</span>
          </div>
        `).join('');

        searchDropdown.style.display = 'block';

        searchDropdown.querySelectorAll('.search-item').forEach(el => {
          el.addEventListener('click', () => {
            const key = el.dataset.key;
            addCompoundKey(key);
            searchInput.value = '';
            searchDropdown.style.display = 'none';
          });
        });
      }

      document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
          searchDropdown.style.display = 'none';
        }
      });

      // QUICK ADD TAGS
      document.querySelectorAll('.quick-tag').forEach(btn => {
        btn.addEventListener('click', () => {
          const key = btn.dataset.key;
          addCompoundKey(key);
        });
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

      function addCompoundKey(key) {
        if (!key) return;
        const cleanKey = String(key).trim().toLowerCase().split(':')[0];
        if (!cleanKey || matchCompoundItem(state.stack, cleanKey)) return;

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
          showToast(`Added ${cached.name || cleanKey}`, '✓');
          syncAndEvaluateStack();
          return;
        }

        fetch(`/catalog/${encodeURIComponent(cleanKey)}`)
          .then(res => {
            if (!res.ok) throw new Error('Compound not found');
            return res.json();
          })
          .then(compound => {
            _clientCatalogCache[cleanKey] = compound;
            if (compound.key) _clientCatalogCache[compound.key] = compound;
            const fallback = getDefaultDoseFallback(compound.key || cleanKey);
            const defDose = compound.default_dose || {};
            const doseVal = defDose.dose_val !== undefined ? defDose.dose_val : (compound.dose !== undefined ? compound.dose : fallback.dose);
            const doseUnit = defDose.dose_unit || compound.unit || fallback.unit;
            const routeVal = compound.route || compound.default_route || fallback.route || 'oral';

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
            showToast(`Added ${compound.name || cleanKey}`, '✓');
            syncAndEvaluateStack();
          })
          .catch(() => {
            const fallback = getDefaultDoseFallback(cleanKey);
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
            showToast(`Added ${cleanKey}`, '✓');
            syncAndEvaluateStack();
          });
      }

      function removeCompoundKey(key) {
        if (!key) return;
        const item = matchCompoundItem(state.stack, key);
        if (item) {
          state.stack = state.stack.filter(c => c !== item);
          showToast(`Removed ${item.name}`, '✕');
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
        if (stackCountBadge) stackCountBadge.textContent = `${state.stack.length} items`;
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

        if (!state.stack.length) {
          if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';
          if (stackItemsWrap) {
            stackItemsWrap.innerHTML = '';
            stackItemsWrap.appendChild(emptyPlaceholder);
          }
          return;
        }

        if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
        if (!stackItemsWrap) return;

        stackItemsWrap.innerHTML = state.stack.map(c => {
          const unit = c.unit || 'mg';
          const freq = c.frequency || 'daily';
          const route = c.route || 'oral';
          const mult = getFrequencyMultiplierClient(freq);
          const effDaily = c.dose * mult;
          const effDisplay = mult !== 1.0 
            ? `≈ ${effDaily >= 1.0 ? effDaily.toFixed(effDaily >= 10 ? 1 : 2) : (effDaily * 1000).toFixed(1)} ${effDaily >= 1.0 ? unit : (unit === 'mg' ? 'μg' : unit)}/day`
            : '';

          return `
            <div class="stack-item-card" data-key="${escapeHtml(c.key)}">
              <div class="stack-item-top">
                <div class="stack-item-name-group">
                  <span class="stack-item-name">${escapeHtml(c.name)}</span>
                  <span class="stack-item-class">${escapeHtml(c.drug_class || 'Compound')}</span>
                </div>
                <div class="stack-item-actions">
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
                  <select class="control-select stack-timing-select" onchange="updateTiming('${escapeHtml(c.key)}', this.value)" title="Dosing timing">
                    <option value="morning" ${c.timing === 'morning' ? 'selected' : ''}>Morning</option>
                    <option value="pre-workout" ${c.timing === 'pre-workout' ? 'selected' : ''}>Pre-Workout</option>
                    <option value="evening" ${c.timing === 'evening' ? 'selected' : ''}>Evening</option>
                    <option value="before bed" ${c.timing === 'before bed' ? 'selected' : ''}>Before Bed</option>
                  </select>
                </div>
                <div class="stack-item-row stack-item-route-row">
                  <select 
                    class="control-select stack-route-select" 
                    onchange="updateRoute('${escapeHtml(c.key)}', this.value)" 
                    title="Route of administration"
                  >
                    <option value="oral" ${route === 'oral' ? 'selected' : ''}>💊 Oral (PO)</option>
                    <option value="sublingual" ${route === 'sublingual' ? 'selected' : ''}>💧 Sublingual (SL)</option>
                    <option value="subcutaneous" ${route === 'subcutaneous' ? 'selected' : ''}>💉 Subcutaneous (SC)</option>
                    <option value="intramuscular" ${route === 'intramuscular' ? 'selected' : ''}>💉 Intramuscular (IM)</option>
                    <option value="transdermal" ${route === 'transdermal' ? 'selected' : ''}>🧴 Transdermal (TD)</option>
                    <option value="intravenous" ${route === 'intravenous' ? 'selected' : ''}>🩸 Intravenous (IV)</option>
                    <option value="inhalation" ${route === 'inhalation' ? 'selected' : ''}>💨 Inhalation (IN)</option>
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
      window.evaluateStack = evaluateStack;

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

      document.getElementById('clear-stack-btn').addEventListener('click', () => {
        state.stack = [];
        renderStackList();
        evaluateStack();
        showToast('Stack cleared', '🗑️');
      });

      document.getElementById('export-json-btn').addEventListener('click', () => {
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
        showToast('Audit JSON downloaded', '📥');
      });

      // EVALUATE STACK WITH BACKEND
      async function evaluateStack() {
        if (!state.stack.length) {
          updateDashboardEmpty();
          return;
        }

        const payload = {
          stack: state.stack.map(c => ({
            key: c.key,
            name: c.name,
            dose: c.dose,
            unit: c.unit || 'mg',
            timing: c.timing || 'morning',
            frequency: c.frequency || 'daily',
            route: c.route || 'oral',
          })),
          sex: state.biomarkers.sex,
          age: state.biomarkers.age,
          weight_kg: state.biomarkers.weight_kg,
          height_cm: state.biomarkers.height_cm,
          body_fat_pct: state.biomarkers.body_fat_pct,
          blood_pressure: state.biomarkers.blood_pressure,
          sleep_hours: state.biomarkers.sleep_hours,
          timeline: state.timeline || 'steady_state',
          labs: {
            alt_u_l: state.biomarkers.alt_u_l,
            hematocrit_pct: state.biomarkers.hematocrit_pct,
            blood_pressure: state.biomarkers.blood_pressure,
            egfr: state.biomarkers.egfr,
          },
        };

        try {
          const res = await fetch('/api/interactions/matrix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
          }
          const data = await res.json();
          state.analysis = data;

          if (data.compounds && Array.isArray(data.compounds)) {
            let updatedStack = false;
            data.compounds.forEach(c => {
              const item = matchCompoundItem(state.stack, c.key || c.canonical_name || c.name);
              if (item) {
                if (c.name && (!item.name || item.name === item.key)) {
                  item.name = c.name;
                  updatedStack = true;
                }
                if (c.drug_class && (item.drug_class === 'Compound' || !item.drug_class)) {
                  item.drug_class = c.drug_class;
                  updatedStack = true;
                }
              }
            });
            if (updatedStack) {
              if (stackCountBadge) stackCountBadge.textContent = `${state.stack.length} items`;
              if (statCompounds) statCompounds.textContent = state.stack.length;
            }
          }
          renderDashboard(data);
          syncCopilotStackTags();
        } catch (err) {
          console.error('Evaluation error:', err);
          showToast(`Evaluation error: ${err.message || 'Check inputs'}`, '⚠️');
        }
      }

      function updateDashboardEmpty() {
        if (riskScoreVal) riskScoreVal.textContent = '0';
        if (gaugeCircle) {
          gaugeCircle.style.strokeDashoffset = 377;
          gaugeCircle.style.stroke = 'var(--severity-synergy)';
        }
        if (riskBandBadge) riskBandBadge.className = 'risk-band-pill band-minimal';
        if (riskBandText) riskBandText.textContent = 'Minimal Risk';
        if (statConflicts) statConflicts.textContent = '0';
        if (statSynergies) statSynergies.textContent = '0';
        if (statOrganLoad) statOrganLoad.textContent = 'None';
        if (summaryNarrative) summaryNarrative.textContent = 'Add compounds from the search catalog or pick an example stack to evaluate real-time pharmacodynamic collisions, CYP450 enzyme overlaps, and cumulative safety scores.';
        if (matrixContainer) matrixContainer.innerHTML = '<div class="stack-empty-card" style="padding: 60px 20px;">Add 2 or more compounds to populate the pairwise N×N collision matrix.</div>';
        if (breakdownsContainer) breakdownsContainer.innerHTML = '<div class="stack-empty-card">No active conflicts or synergies recorded.</div>';
        
        const balanceWrap = document.getElementById('balance-dashboard-wrap');
        if (balanceWrap) {
          balanceWrap.innerHTML = '<div class="stack-empty-card">Add compounds to evaluate full-stack physiological axes, dose counterbalances, and net biological equilibrium.</div>';
        }
      }

      function renderDashboard(data) {
        if (!data) return;
        const score = data.cumulative_risk_score || 0;
        if (riskScoreVal) riskScoreVal.textContent = score;

        const offset = 377 - (377 * (score / 100));
        if (gaugeCircle) gaugeCircle.style.strokeDashoffset = offset;

        const band = data.risk_band || 'MINIMAL';
        if (riskBandText) riskBandText.textContent = `${band} Risk`;

        let bandClass = 'band-minimal';
        let strokeColor = 'var(--severity-synergy)';
        if (band === 'LOW') { bandClass = 'band-low'; strokeColor = '#34d399'; }
        else if (band === 'MODERATE') { bandClass = 'band-moderate'; strokeColor = 'var(--severity-moderate)'; }
        else if (band === 'ELEVATED') { bandClass = 'band-elevated'; strokeColor = '#f87171'; }
        else if (band === 'SEVERE') { bandClass = 'band-severe'; strokeColor = 'var(--severity-high)'; }

        if (riskBandBadge) riskBandBadge.className = `risk-band-pill ${bandClass}`;
        if (gaugeCircle) gaugeCircle.style.stroke = strokeColor;

        if (statConflicts) statConflicts.textContent = data.conflict_count || 0;
        if (statSynergies) statSynergies.textContent = data.synergy_count || 0;

        const hep = data.breakdown?.organ_burdens?.hepatic?.level || 'None';
        if (statOrganLoad) statOrganLoad.textContent = hep !== 'None' ? `${hep} Hepatic` : 'Normal';

        if (summaryNarrative) summaryNarrative.textContent = data.summary || 'Pharmacological evaluation complete.';

        // Update tab badges
        const matrixBadge = document.getElementById('tab-matrix-badge');
        const conflictsBadge = document.getElementById('tab-conflicts-badge');
        if (matrixBadge) {
          if ((data.conflict_count || 0) > 0 || (data.synergy_count || 0) > 0) {
            matrixBadge.style.display = 'inline-block';
            matrixBadge.textContent = `${data.conflict_count || 0}⚡ ${data.synergy_count || 0}✨`;
          } else {
            matrixBadge.style.display = 'none';
          }
        }
        if (conflictsBadge) {
          if ((data.conflict_count || 0) > 0) {
            conflictsBadge.style.display = 'inline-block';
            conflictsBadge.textContent = data.conflict_count;
          } else {
            conflictsBadge.style.display = 'none';
          }
        }

        renderMatrixTable(data);
        renderFullStackBalance(data);
        renderBreakdowns(data);
      }

      function renderFullStackBalance(data) {
        const wrap = document.getElementById('balance-dashboard-wrap');
        if (!wrap) return;

        const b = data.full_stack_balance;
        if (!b || !data.compounds || !data.compounds.length) {
          wrap.innerHTML = '<div class="stack-empty-card">Add compounds to evaluate full-stack physiological axes, dose counterbalances, and net biological equilibrium.</div>';
          return;
        }

        const isPower = state.experienceMode === 'power';
        const healthIndex = b.health_index || 85;
        const statusLabel = b.status_label || 'Normal Physiological Baseline';
        const mitigations = b.active_mitigations || [];
        const uncompensated = b.uncompensated_risks || [];
        const axes = b.axes || [];

        let heroBadgeColor = '#10b981';
        if (b.status === 'UNCOMPENSATED_STRAIN') heroBadgeColor = '#ef4444';
        else if (b.status === 'MODERATE_DEVIATION') heroBadgeColor = '#f59e0b';
        else if (b.status === 'COUNTERBALANCED') heroBadgeColor = '#3b82f6';

        const currentFilter = state.axesFilter || 'all';
        const currentSort = state.axesSort || 'priority';

        const totalCount = axes.length;
        const criticalCount = axes.filter(a => a.priority_tier === 1).length;
        const warningCount = axes.filter(a => a.priority_tier === 2).length;
        const outOfRangeCount = criticalCount + warningCount;
        const mitigatedCount = axes.filter(a => a.priority_tier === 3).length;
        const activeShiftCount = axes.filter(a => a.priority_tier === 4).length;
        const baselineCount = axes.filter(a => a.priority_tier === 5).length;

        let filteredAxes = axes.filter(a => {
          if (currentFilter === 'out-of-range') return a.priority_tier <= 2 || !a.in_safe_range;
          if (currentFilter === 'counterbalanced') return a.priority_tier === 3 || (a.status && String(a.status).includes('BALANCED'));
          if (currentFilter === 'active-shifts') return a.priority_tier <= 4 && ((a.compounds_breakdown && a.compounds_breakdown.length > 0) || Math.abs((a.estimated_value || 0) - (a.baseline || 0)) > 0.001);
          if (currentFilter === 'baseline') return a.priority_tier === 5;
          return true;
        });

        filteredAxes.sort((a, b) => {
          const nameA = String(a.name || '');
          const nameB = String(b.name || '');
          if (currentSort === 'shift') {
            return (b.percent_shift || 0) - (a.percent_shift || 0) || nameA.localeCompare(nameB);
          }
          if (currentSort === 'name') {
            return nameA.localeCompare(nameB);
          }
          if (currentSort === 'status') {
            return (a.priority_tier || 5) - (b.priority_tier || 5) || nameA.localeCompare(nameB);
          }
          return (a.priority_tier || 5) - (b.priority_tier || 5) || (b.percent_shift || 0) - (a.percent_shift || 0) || nameA.localeCompare(nameB);
        });

        function renderDistributionGraphSVG(axis, cardIdx) {
          const rawBase = parseFloat(axis.baseline);
          const safeBase = isNaN(rawBase) ? 0 : rawBase;
          const rawEst = parseFloat(axis.estimated_value);
          const safeEst = isNaN(rawEst) ? safeBase : rawEst;
          
          const dist = axis.distribution || {};
          const p5 = parseFloat(dist.p5 !== undefined ? dist.p5 : safeEst * 0.85);
          const p25 = parseFloat(dist.p25 !== undefined ? dist.p25 : safeEst * 0.93);
          const p50 = parseFloat(dist.p50 !== undefined ? dist.p50 : safeEst);
          const p75 = parseFloat(dist.p75 !== undefined ? dist.p75 : safeEst * 1.07);
          const p95 = parseFloat(dist.p95 !== undefined ? dist.p95 : safeEst * 1.15);
          const mean = parseFloat(dist.mean !== undefined ? dist.mean : safeEst);
          const stdDev = parseFloat(dist.std_dev !== undefined ? dist.std_dev : Math.max(0.1, (p95 - p5) / 3.29));

          const safeP5 = isNaN(p5) ? safeEst * 0.85 : p5;
          const safeP25 = isNaN(p25) ? (safeP5 + safeEst) / 2 : p25;
          const safeP50 = isNaN(p50) ? safeEst : p50;
          const safeP75 = isNaN(p75) ? (safeEst + safeEst * 1.15) / 2 : p75;
          const safeP95 = isNaN(p95) ? safeEst * 1.15 : p95;
          const safeMean = isNaN(mean) ? safeEst : mean;
          const safeStdDev = isNaN(stdDev) ? Math.max(0.1, Math.abs(safeP95 - safeP5) / 3.29) : stdDev;

          const rawSLower = axis.safe_lower !== undefined ? parseFloat(axis.safe_lower) : (safeBase * 0.8);
          const safeLower = isNaN(rawSLower) ? safeBase * 0.8 : rawSLower;
          const rawSUpper = axis.safe_upper !== undefined ? parseFloat(axis.safe_upper) : (safeBase * 1.2);
          const safeUpper = isNaN(rawSUpper) ? safeBase * 1.2 : rawSUpper;

          const unit = escapeHtml(axis.unit || '');
          const statusColor = axis.status_color || '#34d399';

          const minVal = Math.min(safeLower, safeBase, safeEst, safeP5);
          const maxVal = Math.max(safeUpper, safeBase, safeEst, safeP95);
          const padding = Math.max((maxVal - minVal) * 0.18, Math.max(safeEst, safeBase) * 0.1, 1.0);
          const xMin = Math.max(0, minVal - padding);
          const xMax = maxVal + padding;
          const rangeX = (xMax - xMin) || 1.0;

          const width = 340;
          const height = 95;
          const baselineY = 78;
          const peakY = 16;
          const chartHeight = baselineY - peakY;

          const toX = (v) => Math.max(6, Math.min(width - 6, ((v - xMin) / rangeX) * width));

          const mu = safeP50;
          const sigma = Math.max(0.001, (safeP95 - safeP5) / 3.29);
          const stepCount = 60;
          const points = [];

          for (let i = 0; i <= stepCount; i++) {
            const vx = xMin + (i / stepCount) * rangeX;
            const z = (vx - mu) / sigma;
            const density = Math.exp(-0.5 * z * z);
            const px = toX(vx);
            const py = baselineY - (density * chartHeight);
            points.push({ x: px, y: py, val: vx });
          }

          const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

          const safeLeftX = toX(safeLower);
          const safeRightX = toX(safeUpper);
          const safeWidthX = Math.max(2, safeRightX - safeLeftX);

          const p5X = toX(safeP5);
          const p95X = toX(safeP95);
          const p50X = toX(safeP50);
          const basePointX = toX(safeBase);

          const curveAreaD = pathD + ` L ${points[points.length - 1].x.toFixed(1)} ${baselineY} L ${points[0].x.toFixed(1)} ${baselineY} Z`;

          let beginnerSummaryText = '';
          let beginnerBadgeClass = 'safe';
          if (safeP95 <= safeUpper && safeP5 >= safeLower) {
            beginnerSummaryText = `✓ Safe Target Zone: 90% of projected outcomes (${safeP5}–${safeP95} ${unit}) remain within healthy limits [${safeLower}–${safeUpper} ${unit}].`;
            beginnerBadgeClass = 'safe';
          } else if (safeEst > safeUpper || safeP95 > safeUpper * 1.15) {
            beginnerSummaryText = `⚠️ Elevation Risk: Projected upper percentile (${safeP95} ${unit}) exceeds safety limit (${safeUpper} ${unit}).`;
            beginnerBadgeClass = 'warning';
          } else if (safeEst < safeLower || safeP5 < safeLower * 0.85) {
            beginnerSummaryText = `⚠️ Suppression Risk: Lower percentile (${safeP5} ${unit}) drops below physiological floor (${safeLower} ${unit}).`;
            beginnerBadgeClass = 'warning';
          } else {
            beginnerSummaryText = `ℹ️ Dynamic Shift: Expected median at ${safeEst} ${unit} (90% distribution between ${safeP5} and ${safeP95} ${unit}).`;
            beginnerBadgeClass = 'info';
          }

          const chartId = `dist-chart-${cardIdx}-${Math.floor(Math.random() * 10000)}`;

          return `
            <div class="dist-chart-wrapper" style="background: rgba(5, 11, 24, 0.7); border: 1px solid rgba(0, 242, 254, 0.18); border-radius: 10px; padding: 12px; margin: 10px 0;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.74rem; font-weight: 700; color: #00f2fe; display: flex; align-items: center; gap: 6px;">
                  <span>📈 Projected Outcome Probability Distribution</span>
                </span>
                <button 
                  type="button" 
                  class="power-user-toggle-btn"
                  onclick="const el=document.getElementById('${chartId}-stats'); el.style.display=(el.style.display==='none'||!el.style.display)?'block':'none';"
                  style="background: rgba(0, 242, 254, 0.12); border: 1px solid rgba(0, 242, 254, 0.35); color: #00f2fe; font-size: 0.68rem; font-weight: 700; padding: 3px 9px; border-radius: 5px; cursor: pointer; transition: all 0.2s ease;"
                >
                  ${isPower ? 'Hide Stats' : '📊 Power Stats'}
                </button>
              </div>

              <div style="font-size: 0.75rem; line-height: 1.4; color: ${beginnerBadgeClass === 'warning' ? '#f87171' : (beginnerBadgeClass === 'safe' ? '#34d399' : '#94a3b8')}; background: ${beginnerBadgeClass === 'warning' ? 'rgba(239,68,68,0.12)' : (beginnerBadgeClass === 'safe' ? 'rgba(16,185,129,0.12)' : 'rgba(148,163,184,0.12)')}; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid ${beginnerBadgeClass === 'warning' ? 'rgba(239,68,68,0.3)' : (beginnerBadgeClass === 'safe' ? 'rgba(16,185,129,0.3)' : 'rgba(148,163,184,0.3)')}; font-weight: 600;">
                ${beginnerSummaryText}
              </div>

              <div style="position: relative; width: 100%;">
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: auto; overflow: visible; display: block;">
                  <defs>
                    <linearGradient id="${chartId}-curve-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#00f2fe" stop-opacity="0.38" />
                      <stop offset="100%" stop-color="#00f2fe" stop-opacity="0.0" />
                    </linearGradient>
                    <linearGradient id="${chartId}-safe-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#10b981" stop-opacity="0.22" />
                      <stop offset="100%" stop-color="#10b981" stop-opacity="0.04" />
                    </linearGradient>
                  </defs>

                  <rect x="${safeLeftX.toFixed(1)}" y="${peakY}" width="${safeWidthX.toFixed(1)}" height="${chartHeight}" fill="url(#${chartId}-safe-grad)" rx="4" />
                  <line x1="${safeLeftX.toFixed(1)}" y1="${peakY}" x2="${safeLeftX.toFixed(1)}" y2="${baselineY}" stroke="#10b981" stroke-dasharray="3,3" stroke-opacity="0.7" stroke-width="1.2" />
                  <line x1="${safeRightX.toFixed(1)}" y1="${peakY}" x2="${safeRightX.toFixed(1)}" y2="${baselineY}" stroke="#10b981" stroke-dasharray="3,3" stroke-opacity="0.7" stroke-width="1.2" />
                  <text x="${((safeLeftX + safeRightX) / 2).toFixed(1)}" y="${peakY + 10}" fill="#34d399" font-size="7.5" font-weight="800" text-anchor="middle" letter-spacing="0.04em">SAFE TARGET ZONE</text>

                  <path d="${curveAreaD}" fill="url(#${chartId}-curve-grad)" />
                  <path d="${pathD}" fill="none" stroke="#00f2fe" stroke-width="2.4" stroke-linecap="round" />

                  <line x1="${basePointX.toFixed(1)}" y1="${peakY + 4}" x2="${basePointX.toFixed(1)}" y2="${baselineY}" stroke="#94a3b8" stroke-dasharray="2,2" stroke-width="1.2" />
                  <circle cx="${basePointX.toFixed(1)}" cy="${baselineY}" r="2.8" fill="#94a3b8" />
                  <text x="${basePointX.toFixed(1)}" y="${baselineY + 12}" fill="#94a3b8" font-size="7.5" font-weight="600" text-anchor="middle">Base: ${safeBase}</text>

                  <line x1="${p50X.toFixed(1)}" y1="${peakY}" x2="${p50X.toFixed(1)}" y2="${baselineY}" stroke="${statusColor}" stroke-width="2" />
                  <circle cx="${p50X.toFixed(1)}" cy="${peakY + 3}" r="4" fill="${statusColor}" stroke="#0b1324" stroke-width="1.5" />
                  <text x="${p50X.toFixed(1)}" y="${peakY - 3}" fill="${statusColor}" font-size="8.5" font-weight="800" text-anchor="middle">Est: ${safeEst} ${unit}</text>

                  <line x1="${p5X.toFixed(1)}" y1="${baselineY - 8}" x2="${p5X.toFixed(1)}" y2="${baselineY}" stroke="#00f2fe" stroke-width="1.5" />
                  <text x="${p5X.toFixed(1)}" y="${baselineY + 12}" fill="#00f2fe" font-size="7.5" font-weight="700" text-anchor="middle">p5: ${safeP5}</text>

                  <line x1="${p95X.toFixed(1)}" y1="${baselineY - 8}" x2="${p95X.toFixed(1)}" y2="${baselineY}" stroke="#00f2fe" stroke-width="1.5" />
                  <text x="${p95X.toFixed(1)}" y="${baselineY + 12}" fill="#00f2fe" font-size="7.5" font-weight="700" text-anchor="middle">p95: ${safeP95}</text>
                </svg>
              </div>

              <div id="${chartId}-stats" style="display: ${isPower ? 'block' : 'none'}; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <div style="font-size: 0.7rem; font-weight: 800; text-transform: uppercase; color: #00f2fe; margin-bottom: 6px; letter-spacing: 0.04em;">📊 Power User Percentile Variance & Normal Distribution</div>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; text-align: center; background: rgba(0, 0, 0, 0.35); padding: 8px; border-radius: 6px; margin-bottom: 6px;">
                  <div>
                    <div style="font-size: 0.62rem; color: var(--text-muted);">p5 (Lower 5%)</div>
                    <div style="font-size: 0.78rem; font-weight: 700; color: #00f2fe; font-family: 'JetBrains Mono', monospace;">${safeP5}</div>
                  </div>
                  <div>
                    <div style="font-size: 0.62rem; color: var(--text-muted);">p25 (25th %)</div>
                    <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${safeP25}</div>
                  </div>
                  <div>
                    <div style="font-size: 0.62rem; color: var(--text-muted);">p50 (Median)</div>
                    <div style="font-size: 0.82rem; font-weight: 800; color: ${statusColor}; font-family: 'JetBrains Mono', monospace;">${safeP50}</div>
                  </div>
                  <div>
                    <div style="font-size: 0.62rem; color: var(--text-muted);">p75 (75th %)</div>
                    <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${safeP75}</div>
                  </div>
                  <div>
                    <div style="font-size: 0.62rem; color: var(--text-muted);">p95 (Upper 95%)</div>
                    <div style="font-size: 0.78rem; font-weight: 700; color: #00f2fe; font-family: 'JetBrains Mono', monospace;">${safeP95}</div>
                  </div>
                </div>

                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary); background: rgba(255,255,255,0.03); padding: 5px 8px; border-radius: 5px;">
                  <span>Mean (&mu;): <strong>${safeMean} ${unit}</strong></span>
                  <span>Std Dev (&sigma;): <strong>${safeStdDev.toFixed(2)} ${unit}</strong></span>
                  <span>90% Span: <strong>${Math.abs(safeP95 - safeP5).toFixed(1)} ${unit}</strong></span>
                </div>
              </div>
            </div>
          `;
        }

        let axesHtml = '';
        if (filteredAxes.length) {
          axesHtml = filteredAxes.map((axis, cardIdx) => {
            const statusColor = axis.status_color || '#34d399';
            const compList = axis.compounds_breakdown || [];
            const tier = axis.priority_tier || 5;

            let cardTierClass = 'card-tier-baseline';
            let tierTagHtml = '<span class="axis-tier-tag tier-baseline">✓ Stable Baseline</span>';

            if (tier === 1) {
              cardTierClass = 'card-tier-critical';
              tierTagHtml = '<span class="axis-tier-tag tier-critical">⚠️ Critical Strain</span>';
            } else if (tier === 2) {
              cardTierClass = 'card-tier-warning';
              tierTagHtml = '<span class="axis-tier-tag tier-warning">⚡ Moderate Alert</span>';
            } else if (tier === 3) {
              cardTierClass = 'card-tier-mitigated';
              tierTagHtml = '<span class="axis-tier-tag tier-mitigated">🛡️ Counterbalanced</span>';
            } else if (tier === 4) {
              cardTierClass = 'card-tier-active';
              tierTagHtml = `<span class="axis-tier-tag tier-active">📊 Active Shift (${axis.percent_shift ? `${axis.percent_shift}%` : 'Shifted'})</span>`;
            }

            const contribRows = compList.map(c => {
              const deltaClass = c.direction === 'UP' ? 'up' : 'down';
              return `
                <div class="axis-contrib-item">
                  <span class="contrib-name">${escapeHtml(c.compound_label || c.compound_id)}</span>
                  <span class="contrib-delta ${deltaClass}">${escapeHtml(c.formatted_delta || '')}</span>
                </div>
              `;
            }).join('');

            const dist = axis.distribution || {};
            const p5 = dist.p5 !== undefined ? dist.p5 : axis.estimated_value;
            const p95 = dist.p95 !== undefined ? dist.p95 : axis.estimated_value;
            const p5p95Str = axis.p5_p95_range_str || `${p5} - ${p95} ${axis.unit || ''}`;

            return `
              <div class="axis-card ${cardTierClass}">
                <div class="axis-card-top">
                  <div class="axis-name-group">
                    <div class="axis-name">
                      <span>${escapeHtml(axis.name || 'Biomarker Axis')}</span>
                    </div>
                    <span class="axis-safe-range">Target Safe Range: ${escapeHtml(axis.safe_range || '')}</span>
                  </div>
                  <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                    ${tierTagHtml}
                    <span class="panel-title-badge" style="background: ${statusColor}22; color: ${statusColor}; border-color: ${statusColor}55;">
                      ${escapeHtml(axis.status_label || '')}
                    </span>
                  </div>
                </div>

                <div class="axis-values-row">
                  <div>
                    <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Baseline → Projected</span>
                    <div class="axis-val-primary" style="color: ${statusColor};">
                      ${axis.baseline} → ${axis.estimated_value} <span style="font-size: 0.85rem; font-weight: 600;">${escapeHtml(axis.unit || '')}</span>
                    </div>
                  </div>
                  <div style="text-align: right;">
                    <span style="font-size: 0.68rem; color: #00f2fe; font-weight: 700; text-transform: uppercase; font-family: 'JetBrains Mono', monospace;" title="90% Population Percentile Distribution Curve (p5 to p95)">
                      📊 p5–p95: ${escapeHtml(p5p95Str)}
                    </span>
                    <div class="axis-val-delta" style="color: ${(axis.estimated_value || 0) >= (axis.baseline || 0) ? '#f87171' : '#34d399'}; margin-top:2px;">
                      Net: ${escapeHtml(axis.net_delta_str || '')}
                    </div>
                  </div>
                </div>

                ${axis.target_tissue || (axis.biometric_modifiers_applied && axis.biometric_modifiers_applied.length) ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0;">
                    ${axis.target_tissue ? `<span style="font-size: 0.72rem; color: #a7f3d0; background: rgba(16, 185, 129, 0.12); padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.25);">🎯 Target: <strong>${escapeHtml(axis.target_tissue)}</strong></span>` : ''}
                    ${(axis.biometric_modifiers_applied || []).map(m => `<span style="font-size: 0.7rem; color: #fde047; background: rgba(245, 158, 11, 0.15); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.3);">⚙️ ${escapeHtml(m)}</span>`).join('')}
                  </div>
                ` : ''}

                <!-- Dynamic Probability Distribution Curve Graph -->
                ${renderDistributionGraphSVG(axis, cardIdx)}

                ${contribRows ? `
                  <div>
                    <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 4px;">Compound Dose Contributions</div>
                    <div class="axis-contrib-list">
                      ${contribRows}
                    </div>
                  </div>
                ` : ''}
              </div>
            `;
          }).join('');
        } else {
          axesHtml = '<div class="stack-empty-card" style="grid-column: 1 / -1;">No physiological axes match the selected filter.</div>';
        }

        let mitigationsHtml = '';
        if (mitigations.length) {
          mitigationsHtml = `
            <div class="mitigations-section">
              <div class="section-heading-row">
                <span class="section-heading-title">
                  <span>🛡️ Active Stack Mitigations & Counterbalances</span>
                  <span class="panel-title-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">${mitigations.length} Active</span>
                </span>
              </div>
              ${mitigations.map(m => `
                <div class="mitigation-card">
                  <div class="mitigation-card-header">
                    <span class="mitigation-title">✓ ${escapeHtml(m.title)}</span>
                    <span style="font-size: 0.75rem; font-weight: 700; color: #00f2fe; font-family: 'JetBrains Mono', monospace;">
                      -${m.risk_reduction_points || 20} Risk Points
                    </span>
                  </div>
                  <p style="font-size: 0.86rem; color: var(--text-secondary); line-height: 1.45; margin: 0;">
                    ${escapeHtml(m.description)}
                  </p>
                  <div style="display: flex; gap: 6px; align-items: center; margin-top: 2px;">
                    <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">Participating:</span>
                    ${(m.participating_compounds || []).map(p => `<span class="modal-chip" style="font-size: 0.72rem; padding: 2px 8px;">${escapeHtml(p)}</span>`).join('')}
                  </div>
                </div>
              `).join('')}
            </div>
          `;
        }

        let uncompensatedHtml = '';
        if (uncompensated.length) {
          uncompensatedHtml = `
            <div class="uncompensated-section">
              <div class="section-heading-row">
                <span class="section-heading-title">
                  <span>⚠️ Uncompensated Axis Deviations</span>
                  <span class="panel-title-badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171;">${uncompensated.length} Warning</span>
                </span>
              </div>
              ${uncompensated.map(u => `
                <div class="uncompensated-card">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 800; font-size: 0.96rem; color: #f87171;">⚠️ ${escapeHtml(u.title)}</span>
                    <span class="panel-title-badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171;">${escapeHtml(u.axis || 'Axis Hazard')}</span>
                  </div>
                  <p style="font-size: 0.86rem; color: var(--text-secondary); line-height: 1.45; margin: 0;">
                    ${escapeHtml(u.description)}
                  </p>
                  ${u.clinical_recommendation ? `
                    <div class="conflict-card-rec" style="color: #fca5a5; background: rgba(0, 0, 0, 0.35);">
                      <strong>Clinical Guidance:</strong> ${escapeHtml(u.clinical_recommendation)}
                    </div>
                  ` : ''}
                </div>
              `).join('')}
            </div>
          `;
        }

        wrap.innerHTML = `
          <div class="balance-hero-banner">
            <div class="balance-hero-left">
              <div class="balance-hero-title">
                <span>Holistic Stack Equilibrium</span>
                <span class="panel-title-badge" style="background: ${heroBadgeColor}22; color: ${heroBadgeColor}; border-color: ${heroBadgeColor}55;">
                  ${escapeHtml(statusLabel)}
                </span>
              </div>
              <p class="balance-hero-desc">
                Evaluates your complete compound regimen as an interconnected physiological network. Determines whether co-administered compounds neutralize monotherapy hazards (e.g. Aromatase Inhibitor + Androgen balancing Estrogen, ARB + Androgen protecting Blood Pressure).
              </p>
            </div>
            <div class="balance-hero-badge-wrap">
              <div class="balance-index-gauge">
                <span class="balance-index-num" style="color: ${heroBadgeColor};">${healthIndex}</span>
                <span class="balance-index-label">Equilibrium Index</span>
              </div>
            </div>
          </div>

          <div class="timeline-controller-card" style="background: rgba(12, 24, 38, 0.85); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 18px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.88rem; font-weight: 800; color: #00f2fe; display: flex; align-items: center; gap: 6px;">
                  ⏱️ Equilibrium Timeline Horizon
                </span>
                <span style="font-size: 0.72rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">
                  Horizon: <strong style="color: #00f2fe;">${escapeHtml(b.timeline_label || 'Steady State (Full Equilibrium)')}</strong>
                </span>
              </div>
              <span style="font-size: 0.72rem; color: var(--text-secondary); background: rgba(0,242,254,0.08); border: 1px solid rgba(0,242,254,0.25); padding: 3px 8px; border-radius: 9999px;">
                ${getTimelineNarrativePill(state.timeline)}
              </span>
            </div>

            <div class="timeline-presets-bar" style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
              ${[
                { key: '1_day', label: '1 Day', sub: 'Acute Autonomic' },
                { key: '3_days', label: '3 Days', sub: 'Early Adapt' },
                { key: '1_week', label: '1 Week', sub: 'Sub-acute Tone' },
                { key: '2_weeks', label: '2 Weeks', sub: 'Endocrine Eq' },
                { key: '1_month', label: '1 Month', sub: 'Lipids (4w)' },
                { key: '2_months', label: '2 Months', sub: 'Reticulocyte (8w)' },
                { key: '3_months', label: '3 Months', sub: 'HbA1c & RBC (12w)' },
                { key: 'steady_state', label: 'Steady State', sub: 'Full Equilibrium' },
              ].map(t => `
                <button 
                  type="button" 
                  class="axis-filter-btn ${state.timeline === t.key ? 'active' : ''}" 
                  style="padding: 5px 10px; font-size: 0.74rem;" 
                  onclick="setStackTimeline('${t.key}')"
                  title="${t.sub}"
                >
                  <span>${t.label}</span>
                  <span style="font-size: 0.64rem; opacity: 0.75; margin-left: 2px;">(${t.sub})</span>
                </button>
              `).join('')}
            </div>

            <div style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.45; padding: 7px 12px; background: rgba(0, 0, 0, 0.3); border-radius: var(--radius-sm); border-left: 3px solid #00f2fe;">
              ${getTimelineDescription(state.timeline)}
            </div>
          </div>

          ${uncompensatedHtml}
          ${mitigationsHtml}

          <div>
            <div class="axes-toolbar-row">
              <div class="axes-filter-chips">
                <button class="axis-filter-btn ${currentFilter === 'all' ? 'active' : ''}" onclick="setAxesFilter('all')">
                  All Axes (${totalCount})
                </button>
                ${outOfRangeCount > 0 ? `
                  <button class="axis-filter-btn filter-critical ${currentFilter === 'out-of-range' ? 'active' : ''}" onclick="setAxesFilter('out-of-range')">
                    ⚠️ Out of Range (${outOfRangeCount})
                  </button>
                ` : ''}
                ${mitigatedCount > 0 ? `
                  <button class="axis-filter-btn filter-mitigated ${currentFilter === 'counterbalanced' ? 'active' : ''}" onclick="setAxesFilter('counterbalanced')">
                    🛡️ Counterbalanced (${mitigatedCount})
                  </button>
                ` : ''}
                ${activeShiftCount > 0 ? `
                  <button class="axis-filter-btn ${currentFilter === 'active-shifts' ? 'active' : ''}" onclick="setAxesFilter('active-shifts')">
                    📊 Active Shifts (${activeShiftCount})
                  </button>
                ` : ''}
                <button class="axis-filter-btn ${currentFilter === 'baseline' ? 'active' : ''}" onclick="setAxesFilter('baseline')">
                  ✓ Baseline (${baselineCount})
                </button>
              </div>

              <div class="axis-sort-wrap">
                <span class="axis-sort-label">Sort:</span>
                <select class="axis-sort-select" onchange="setAxesSort(this.value)">
                  <option value="priority" ${currentSort === 'priority' ? 'selected' : ''}>Clinical Priority (Risk & Deviations First)</option>
                  <option value="shift" ${currentSort === 'shift' ? 'selected' : ''}>Largest % Shift (Highest Impact First)</option>
                  <option value="name" ${currentSort === 'name' ? 'selected' : ''}>Axis Name (A → Z)</option>
                  <option value="status" ${currentSort === 'status' ? 'selected' : ''}>Status (Critical → Safe)</option>
                </select>
              </div>
            </div>

            <div class="axes-cards-grid">
              ${axesHtml}
            </div>
          </div>
        `;
      }

      window.setAxesFilter = function(filterKey) {
        state.axesFilter = filterKey;
        if (state.analysis) {
          renderFullStackBalance(state.analysis);
        }
      };

      window.setAxesSort = function(sortKey) {
        state.axesSort = sortKey;
        if (state.analysis) {
          renderFullStackBalance(state.analysis);
        }
      };

      function renderMatrixTable(data) {
        if (!matrixContainer) return;
        if (!data || !data.matrix || !data.matrix.length) {
          matrixContainer.innerHTML = '<div class="stack-empty-card" style="padding: 60px 20px;">Add 2 or more compounds to populate the pairwise N×N collision matrix.</div>';
          return;
        }

        const compounds = data.compounds || [];
        let html = '<table class="matrix-table"><thead><tr><th></th>';
        compounds.forEach(c => {
          const doseStr = c.dose ? ` (${c.dose}${c.unit || 'mg'})` : '';
          html += `<th>${escapeHtml(c.name || c.key || '')}${escapeHtml(doseStr)}</th>`;
        });
        html += '</tr></thead><tbody>';

        data.matrix.forEach((row, i) => {
          const cRow = compounds[i];
          const doseStr = cRow?.dose ? ` (${cRow.dose}${cRow.unit || 'mg'})` : '';
          html += `<tr><th>${escapeHtml(cRow?.name || '')}${escapeHtml(doseStr)}</th>`;
          row.forEach((cell, j) => {
            let cellClass = 'cell-neutral';
            let icon = '✓';
            let label = 'Neutral';

            if (cell.is_self) {
              cellClass = 'cell-self';
              icon = '●';
              label = 'Self';
            } else if (cell.is_mitigated_by_stack) {
              cellClass = 'cell-mitigated';
              icon = '🛡️';
              label = 'Mitigated';
            } else if (cell.severity === 'SYNERGISTIC') {
              cellClass = 'cell-synergy';
              icon = '✨';
              label = 'Synergy';
            } else if (cell.severity === 'HIGH_RISK' || cell.severity === 'SEVERE_CONTRAINDICATION') {
              cellClass = 'cell-high';
              icon = '⚠️';
              label = cell.ddi_auc_ratio ? `+${Math.round((cell.ddi_auc_ratio - 1) * 100)}% AUC` : 'High Risk';
            } else if (cell.severity === 'MODERATE_RISK') {
              cellClass = 'cell-moderate';
              icon = '⚡';
              label = cell.ddi_auc_ratio ? `+${Math.round((cell.ddi_auc_ratio - 1) * 100)}% AUC` : 'Moderate';
            }

            const srcName = escapeHtml(cell.source_name || compounds[i]?.name || 'Compound A');
            const tgtName = escapeHtml(cell.target_name || compounds[j]?.name || 'Compound B');

            html += `
              <td>
                <div class="matrix-cell ${cellClass}" onclick="openCellInspector(${i}, ${j})" title="Click to view biochemical details for ${srcName} + ${tgtName}">
                  <span class="cell-icon">${icon}</span>
                  <span class="cell-label">${escapeHtml(label)}</span>
                </div>
              </td>
            `;
          });
          html += '</tr>';
        });

        html += '</tbody></table>';
        matrixContainer.innerHTML = html;
      }

      function renderBreakdowns(data) {
        if (!breakdownsContainer) return;
        const b = data.breakdown || {};
        const isPower = state.experienceMode === 'power';
        const allItems = [
          ...(b.cyp_conflicts || []).map(c => ({ ...c, cat: 'CYP450 Metabolism', cardClass: 'card-high' })),
          ...(b.receptor_conflicts || []).map(c => ({ ...c, cat: 'Pharmacodynamic / Receptor', cardClass: 'card-moderate' })),
          ...(b.biomarker_warnings || []).map(c => ({ ...c, cat: 'Biomarker Stress', cardClass: 'card-high' })),
          ...(b.synergistic_benefits || []).map(c => ({ ...c, cat: 'Synergistic Pairing', cardClass: 'card-synergy' })),
        ];

        if (!allItems.length) {
          breakdownsContainer.innerHTML = '<div class="stack-empty-card">Clean profile: No adverse CYP450 conflicts or receptor competitions found.</div>';
          return;
        }

        breakdownsContainer.innerHTML = allItems.map(item => `
          <div class="conflict-card ${item.cardClass}">
            <div class="conflict-card-top">
              <span class="conflict-card-title">${escapeHtml(item.title)}</span>
              <div style="display: flex; gap: 6px; align-items: center;">
                ${item.is_mitigated_by_stack ? '<span class="panel-title-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">🛡️ Mitigated by Stack</span>' : ''}
                <span class="panel-title-badge">${escapeHtml(item.cat)}</span>
              </div>
            </div>
            <p class="conflict-card-desc">${escapeHtml(item.description)}</p>
            ${item.mitigation_summary ? `<div style="padding: 8px 12px; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); font-size: 0.82rem; color: #34d399; margin-top: 4px;"><strong>Stack Mitigation:</strong> ${escapeHtml(item.mitigation_summary)}</div>` : ''}
            ${item.ddi_auc_ratio && isPower ? `<div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#00f2fe; margin-top:4px; background:rgba(0,0,0,0.3); padding:4px 8px; border-radius:4px;">📊 Power Metric • Estimated DDI Exposure Multiplier: ${item.ddi_auc_ratio}x AUC (+${Math.round((item.ddi_auc_ratio - 1) * 100)}% surge)</div>` : ''}
            ${item.clinical_recommendation ? `<div class="conflict-card-rec"><strong>Recommendation:</strong> ${escapeHtml(item.clinical_recommendation)}</div>` : ''}
          </div>
        `).join('');
      }

      // INSPECTOR MODAL
      window.openCellInspector = (i, j) => {
        if (!state.analysis || !state.analysis.matrix) return;
        const cell = state.analysis.matrix[i]?.[j];
        if (!cell) return;

        const srcName = cell.source_name || (state.analysis.compounds?.[i]?.name) || 'Compound A';
        const tgtName = cell.target_name || (state.analysis.compounds?.[j]?.name) || 'Compound B';

        document.getElementById('modal-pair-title').textContent = `${srcName} ⟷ ${tgtName}`;
        document.getElementById('modal-pair-subtitle').textContent = cell.title || 'Pharmacology Collision';
        document.getElementById('modal-description').textContent = cell.description || 'No specific conflict documented.';
        document.getElementById('modal-recommendation').textContent = cell.clinical_recommendation || 'Standard clinical monitoring recommended.';

        const badge = document.getElementById('modal-severity-badge');
        let bandClass = 'band-minimal';
        let badgeText = cell.severity ? cell.severity.replace('_', ' ') : 'Neutral';
        
        if (cell.is_mitigated_by_stack) {
          bandClass = 'band-minimal';
          badgeText = '🛡️ Mitigated by Full Stack';
        } else if (cell.severity === 'SYNERGISTIC') {
          bandClass = 'band-minimal';
        } else if (cell.severity === 'MODERATE_RISK') {
          bandClass = 'band-moderate';
        } else if (cell.severity === 'HIGH_RISK' || cell.severity === 'SEVERE_CONTRAINDICATION') {
          bandClass = 'band-severe';
        } else if (cell.is_self) {
          bandClass = 'band-low';
        }

        badge.className = `risk-band-pill ${bandClass}`;
        badge.textContent = badgeText;

        const targetsWrap = document.getElementById('modal-targets-wrap');
        const targetsSection = document.getElementById('modal-targets-section');
        if (cell.affected_targets && cell.affected_targets.length) {
          targetsSection.style.display = 'block';
          targetsWrap.innerHTML = cell.affected_targets.map(t => `<span class="modal-chip">${escapeHtml(t)}</span>`).join('');
        } else {
          targetsSection.style.display = 'none';
        }

        const citationsWrap = document.getElementById('modal-citations-wrap');
        const evidenceSection = document.getElementById('modal-evidence-section');
        if (citationsWrap) {
          const pmids = cell.pmids || [];
          const cites = cell.citations || [];
          const fdaRef = cell.fda_label_ref || (cell.conflict_types && cell.conflict_types.includes('CYP450') ? 'FDA Guidance on DDI & CYP450 Evaluation' : null);

          let citeHtml = '';
          if (fdaRef) {
            citeHtml += `<div style="font-size:0.75rem; color:#38bdf8; padding:4px 8px; background:rgba(56,189,248,0.08); border-radius:4px; border:1px solid rgba(56,189,248,0.2);">🏛️ <strong>Regulatory:</strong> ${escapeHtml(fdaRef)}</div>`;
          }
          if (pmids.length > 0) {
            citeHtml += `
              <div style="font-size:0.72rem; color:var(--text-secondary); display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span>🔬 <strong>PubMed Studies:</strong></span>
                ${pmids.map(p => `<a href="https://pubmed.ncbi.nlm.nih.gov/${p}/" target="_blank" rel="noopener" style="color:#00f2fe; text-decoration:none; padding:2px 6px; background:rgba(0,242,254,0.1); border-radius:4px; border:1px solid rgba(0,242,254,0.3);">PMID: ${p} ↗</a>`).join('')}
              </div>
            `;
          }
          if (cites.length > 0) {
            citeHtml += cites.slice(0, 2).map(c => `
              <div style="font-size:0.72rem; color:var(--text-secondary); padding:4px 8px; background:rgba(8,13,25,0.6); border-radius:4px; border:1px solid var(--border-subtle);">
                <div style="font-weight:600; color:#fff;">${escapeHtml(c.title || '')}</div>
                <div style="font-size:0.65rem; color:var(--text-muted);">${escapeHtml(c.journal || '')} (${c.pub_year || ''}) &bull; ${escapeHtml(c.evidence_tier || 'Study')}</div>
              </div>
            `).join('');
          }
          if (!citeHtml) {
            const compKeyA = (cell.source_key || '').toLowerCase();
            const compKeyB = (cell.target_key || '').toLowerCase();
            citeHtml = `<div style="font-size:0.72rem; color:var(--text-muted);">Grounded in catalog pharmacological profiles. Search literature for <a href="https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(compKeyA + ' ' + compKeyB)}" target="_blank" rel="noopener" style="color:#38bdf8;">${escapeHtml(cell.source_name || compKeyA)} + ${escapeHtml(cell.target_name || compKeyB)} on PubMed ↗</a></div>`;
          }
          citationsWrap.innerHTML = citeHtml;
        }

        inspectorModal.classList.add('open');
      };

      modalCloseBtn.addEventListener('click', () => inspectorModal.classList.remove('open'));
      inspectorModal.addEventListener('click', (e) => {
        if (e.target === inspectorModal) inspectorModal.classList.remove('open');
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          inspectorModal.classList.remove('open');
          if (guideModal) guideModal.classList.remove('open');
          if (presetMenu) presetMenu.classList.remove('open');
        }
      });

      // TABS SWITCHING
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');

          btn.classList.add('active');
          const tabId = btn.dataset.tab;
          state.activeTab = tabId;
          const targetPane = document.getElementById(tabId);
          if (targetPane) {
            targetPane.style.display = 'block';
          }
        });
      });

      function normalizeStackItem(item) {
        if (!item) return null;
        let key = '';
        let name = '';
        let dose = null;
        let unit = 'mg';
        let timing = 'morning';
        let frequency = 'daily';
        let route = '';
        let drugClass = 'Compound';

        function strClean(s) { return typeof s === 'string' ? s.trim() : ''; }

        if (typeof item === 'string') {
          const parts = item.split(':');
          key = parts[0].trim();
          name = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          if (parts.length > 1) {
            const m = parts[1].trim().match(/^([\d.]+)\s*([a-zA-Zμµ]*)$/);
            if (m) {
              dose = parseFloat(m[1]);
              unit = m[2] || 'mg';
              if (unit === 'ug' || unit === 'mcg') unit = 'μg';
            }
          }
          if (parts.length > 2) frequency = parts[2].trim();
          if (parts.length > 3) route = parts[3].trim().toLowerCase();
        } else if (typeof item === 'object') {
          let rawKey = strClean(item.key || item.name || '');
          if (rawKey.includes(':')) {
            const parts = rawKey.split(':');
            key = parts[0].trim();
            if (parts.length > 1 && (item.dose === undefined || item.dose === null)) {
              const m = parts[1].trim().match(/^([\d.]+)\s*([a-zA-Zμµ]*)$/);
              if (m) {
                dose = parseFloat(m[1]);
                unit = m[2] || 'mg';
              }
            }
            if (parts.length > 2 && !item.frequency) frequency = parts[2].trim();
            if (parts.length > 3 && !item.route) route = parts[3].trim().toLowerCase();
          } else {
            key = rawKey;
          }
          name = item.name || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          drugClass = item.drug_class || 'Compound';
          timing = item.timing || 'morning';
          frequency = item.frequency || frequency || 'daily';
          route = (strClean(item.route || route || '')).toLowerCase();
          if (item.dose !== undefined && item.dose !== null && !isNaN(parseFloat(item.dose))) {
            dose = parseFloat(item.dose);
            unit = item.unit || 'mg';
            if (unit === 'ug' || unit === 'mcg') unit = 'μg';
          }
        }

        key = key.trim().toLowerCase().split(':')[0];
        if (!key) return null;
        const def = getDefaultDoseFallback(key);
        if (dose === null || isNaN(dose) || dose <= 0) {
          dose = def.dose;
          unit = def.unit;
        }
        if (!route) {
          route = def.route || 'oral';
        }

        return {
          key,
          name,
          drug_class: drugClass,
          dose,
          unit,
          timing,
          frequency,
          route,
        };
      }

      // Initial state render with URL params & localStorage restore
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const presetParam = urlParams.get('preset');
        const stackParam = urlParams.get('stack');
        const timelineParam = urlParams.get('timeline');
        if (timelineParam) {
          state.timeline = timelineParam;
        }

        if (presetParam && PRESET_STACKS[presetParam]) {
          loadPreset(presetParam);
        } else if (stackParam) {
          const rawItems = stackParam.split(',').map(s => s.trim()).filter(Boolean);
          if (rawItems.length) {
            state.stack = rawItems.map(normalizeStackItem).filter(Boolean);
          }
        } else {
          const saved = localStorage.getItem('healthai_stack');
          if (saved) {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed) && parsed.length) {
              state.stack = parsed.map(normalizeStackItem).filter(Boolean);
            }
          }
        }
      } catch (e) {
        console.warn('Failed to parse saved stack or URL params on startup', e);
      }

      // Real-time synchronization with Knowledge Graph across tabs & windows
      window.addEventListener('storage', (e) => {
        if (e.key === 'healthai_stack' && e.newValue) {
          try {
            const parsed = JSON.parse(e.newValue);
            if (Array.isArray(parsed)) {
              state.stack = parsed.map(normalizeStackItem).filter(Boolean);
              renderStackList();
              if (state.stack.length) evaluateStack();
              else updateDashboardEmpty();
            }
          } catch (err) {
            console.warn('Storage sync error', err);
          }
        }
      });

      // Mobile menu toggle handling
      const mobileMenuBtn = document.getElementById('mobile-menu-toggle');
      const navLinksMenu = document.getElementById('nav-links');
      if (mobileMenuBtn && navLinksMenu) {
        mobileMenuBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          navLinksMenu.classList.toggle('open');
        });

        document.addEventListener('click', (e) => {
          if (!navLinksMenu.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
            navLinksMenu.classList.remove('open');
          }
        });
      }

      // ==========================================================================
      // FLAGSHIP AI COPILOT CLIENT ENGINE (MULTI-TURN SSE STREAMING & ACTION CARDS)
      // ==========================================================================
      function escapeHtml(str) {
        if (!str && str !== 0) return '';
        return String(str)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#039;');
      }

      function renderInlineMarkdown(str) {
        if (!str) return '';
        return str
          .replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--accent-cyan);">$1</strong>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.35); border-radius: 3px; padding: 1px 5px; font-size: 0.76rem; color: var(--accent-cyan);">$1</code>');
      }

      function renderMarkdownLite(rawText) {
        if (!rawText) return '';

        // 1. Strip raw action_card tags completely from text bubble
        let text = rawText.replace(/<action_card[\s\S]*?(<\/action_card>|$)/gi, '').trim();
        if (!text) return '';

        // 2. Extract and protect code blocks
        const codeBlocks = [];
        text = text.replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (match, lang, code) => {
          const idx = codeBlocks.length;
          codeBlocks.push(`<pre style="background: rgba(0,0,0,0.5); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; overflow-x: auto; font-family: monospace; font-size: 0.8rem; margin: 8px 0;"><code>${escapeHtml(code.trim())}</code></pre>`);
          return `__CODE_BLOCK_${idx}__`;
        });

        // Extract inline code
        const inlineCodes = [];
        text = text.replace(/`([^`]+)`/g, (match, code) => {
          const idx = inlineCodes.length;
          inlineCodes.push(`<code style="background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08); border-radius: 4px; padding: 2px 6px; font-family: monospace; font-size: 0.82rem; color: var(--accent-cyan);">${escapeHtml(code)}</code>`);
          return `__INLINE_CODE_${idx}__`;
        });

        // 3. Convert markdown tables (support any spacing and line breaks)
        text = text.replace(/(?:^|\n)((?:[ \t]*\|[^\n]+\|[ \t]*\r?\n)+)/g, (fullMatch, tableBlock) => {
          const rawLines = tableBlock.trim().split('\n').map(l => l.trim()).filter(Boolean);
          if (rawLines.length < 2) return fullMatch;
          if (!/^[|:\-\s]+$/.test(rawLines[1])) return fullMatch;

          const headers = rawLines[0].split('|').slice(1, -1).map(h => h.trim());
          const rowLines = rawLines.slice(2);

          let tableHtml = '<div style="overflow-x: auto; margin: 10px 0;"><table class="copilot-table" style="width: 100%; border-collapse: collapse; font-size: 0.78rem; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); overflow: hidden; background: rgba(0,0,0,0.2);">';
          tableHtml += '<thead style="background: rgba(0, 242, 254, 0.08); border-bottom: 1px solid var(--border-subtle);"><tr style="text-align: left;">';
          headers.forEach(h => {
            tableHtml += `<th style="padding: 6px 10px; font-weight: 700; color: var(--text-primary); border-right: 1px solid var(--border-subtle);">${escapeHtml(h)}</th>`;
          });
          tableHtml += '</tr></thead><tbody>';

          rowLines.forEach((r, idx) => {
            const cols = r.split('|').slice(1, -1).map(c => c.trim());
            const bg = idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)';
            tableHtml += `<tr style="background: ${bg}; border-bottom: 1px solid rgba(255,255,255,0.04);">`;
            cols.forEach(c => {
              tableHtml += `<td style="padding: 6px 10px; color: var(--text-secondary); border-right: 1px solid rgba(255,255,255,0.04);">${renderInlineMarkdown(escapeHtml(c))}</td>`;
            });
            tableHtml += '</tr>';
          });

          tableHtml += '</tbody></table></div>';
          return tableHtml;
        });

        // 4. Headings
        text = text.replace(/^#### (.*$)/gim, '<h5 style="margin: 10px 0 4px 0; color: var(--accent-cyan); font-size: 0.84rem; font-weight: 700;">$1</h5>');
        text = text.replace(/^### (.*$)/gim, '<h4 style="margin: 12px 0 6px 0; color: #f8fafc; font-size: 0.92rem; font-weight: 800; display: flex; align-items: center; gap: 6px;">$1</h4>');
        text = text.replace(/^## (.*$)/gim, '<h3 style="margin: 14px 0 8px 0; color: var(--accent-cyan); font-size: 1.0rem; font-weight: 800; border-bottom: 1px solid rgba(0,242,254,0.15); padding-bottom: 4px;">$1</h3>');
        text = text.replace(/^# (.*$)/gim, '<h2 style="margin: 16px 0 8px 0; color: #ffffff; font-size: 1.1rem; font-weight: 800;">$1</h2>');

        // 5. Blockquotes / Alerts
        text = text.replace(/^> (.*$)/gim, '<blockquote style="background: rgba(0, 242, 254, 0.05); border-left: 3px solid var(--accent-cyan); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 6px 12px; margin: 8px 0; font-size: 0.82rem; color: var(--text-secondary);">$1</blockquote>');

        // 6. Dividers
        text = text.replace(/^---$/gim, '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 12px 0;">');

        // 7. Bold & Italic
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--accent-cyan); font-weight: 700;">$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em style="color: var(--text-primary);">$1</em>');

        // 7b. Clean inline drafting self-talk & question marks inside/outside citations
        text = text.replace(/\[([A-Za-z0-9\s:§\.\-_]+?)\s*\?\s*(?:Need real|Could use|Need verified|We need|Use known|Not sure|I think|maybe|Need not be|But should|Use FDA).*?\]/gi, '[$1]');
        text = text.replace(/\[([A-Za-z0-9\s:§\.\-_]+?)\s*\?\]/g, '[$1]');
        text = text.replace(/(?:\?\s*)?(?:Need real\?|Could use generic\?|Need verified citations\.?|We need citations\.?|Use known\?|Need avoid false\?|But prompt requires citations\.?|Not sure\.?|Actually IMPROVE-IT.*?I think yes\.?|Need not be perfect\?|But should be plausible\.?|Could use \[.*?\] maybe\.?|for testosterone\?|ChEMBL\d+ is testosterone\?|I think CHEMBL\d+ is testosterone\.?|Anastrozole CHEMBL\?|Maybe CHEMBL\d+\?|Use FDA labels\.?)/gi, '');

        // 8. Medical & Literature Citation Badging (Supports structured author/year, DOIs, ChEMBL, FDA, NCT, CPIC)
        text = text.replace(/\[PMID:\s*(\d+)(?:\s*[-–—:]\s*([^\]]+))?\]/gi, (match, pmid, extra) => {
          const label = extra ? `📄 PMID: ${pmid} (${extra.trim()})` : `📄 PMID: ${pmid}`;
          return `<a href="https://pubmed.ncbi.nlm.nih.gov/${pmid}/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge pmid-badge" title="View study on PubMed (PMID: ${pmid})">${label}</a>`;
        });
        text = text.replace(/\[DOI:\s*([^\s\]]+)\]/gi, '<a href="https://doi.org/$1" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge doi-badge" title="View DOI Publication">🌐 DOI: $1</a>');
        text = text.replace(/\[ChEMBL:\s*([A-Za-z0-9_]+)\]/gi, '<a href="https://www.ebi.ac.uk/chembl/target_report_card/$1/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge chembl-badge" title="View target in ChEMBL database">🔬 ChEMBL: $1</a>');
        text = text.replace(/\[FDA(?:\s+Label)?:\s*([^\]]+)\]/gi, '<span class="copilot-citation-badge fda-badge" title="FDA Structured Product Labeling Standard">🏛️ FDA: $1</span>');
        text = text.replace(/\[NCT:\s*([A-Za-z0-9_]+)\]/gi, '<a href="https://clinicaltrials.gov/study/$1" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge trial-badge" title="View Clinical Trial on ClinicalTrials.gov">🧪 NCT: $1</a>');
        text = text.replace(/\[CPIC(?:\s+Guideline)?:\s*([^\]]+)\]/gi, '<span class="copilot-citation-badge cpic-badge" title="CPIC Clinical Pharmacogenetics Implementation Consortium">🧬 CPIC: $1</span>');

        // 9. Bullet lists
        text = text.replace(/^[ \t]*[-*][ \t]+(.*$)/gim, '<li style="margin-bottom: 4px;">$1</li>');
        text = text.replace(/((?:<li style="margin-bottom: 4px;">.*?<\/li>\s*)+)/g, '<ul style="margin: 6px 0 8px 18px; padding: 0; list-style-type: disc;">$1</ul>');

        // 9. Paragraphs
        const blocks = text.split(/\n{2,}/).map(p => {
          p = p.trim();
          if (!p) return '';
          if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<table') || p.startsWith('<ul') || p.startsWith('<ol') || p.startsWith('<pre') || p.startsWith('<hr') || p.startsWith('<blockquote')) {
            return p;
          }
          return `<p style="margin-bottom: 8px;">${p.replace(/\n/g, '<br>')}</p>`;
        }).filter(Boolean);

        let html = blocks.join('');

        // Restore code blocks and inline code
        inlineCodes.forEach((code, idx) => {
          html = html.replace(`__INLINE_CODE_${idx}__`, code);
        });
        codeBlocks.forEach((block, idx) => {
          html = html.replace(`__CODE_BLOCK_${idx}__`, block);
        });

        return html;
      }

      // ==============================================================================
      // USER API KEY STORAGE & MANAGEMENT (BYOK FOR HOST TOKEN EXHAUSTION)
      // ==============================================================================
      function getUserApiKey() {
        try {
          return (localStorage.getItem('healthai_custom_api_key') || '').trim();
        } catch (e) {
          return '';
        }
      }

      function setUserApiKey(key) {
        try {
          const cleanKey = (key || '').trim();
          if (cleanKey) {
            localStorage.setItem('healthai_custom_api_key', cleanKey);
          } else {
            localStorage.removeItem('healthai_custom_api_key');
          }
          updateApiKeyUiState();
        } catch (e) {
          console.error('Failed to save custom API key:', e);
        }
      }

      function clearUserApiKey() {
        try {
          localStorage.removeItem('healthai_custom_api_key');
          updateApiKeyUiState();
        } catch (e) {}
      }

      function getAiRequestHeaders(extraHeaders = {}) {
        const headers = { 'Content-Type': 'application/json', ...extraHeaders };
        const userKey = getUserApiKey();
        if (userKey) {
          headers['X-User-API-Key'] = userKey;
        }
        return headers;
      }

      function updateApiKeyUiState() {
        const userKey = getUserApiKey();
        const apiKeyBtn = document.getElementById('copilot-api-key-btn');
        const apiKeyBadgeText = document.getElementById('copilot-key-badge-text');
        const currentKeyBadge = document.getElementById('current-key-badge');
        const userKeyInput = document.getElementById('user-api-key-input');
        const statusIndicator = document.getElementById('copilot-status-indicator');

        if (userKey) {
          if (apiKeyBtn) {
            apiKeyBtn.classList.add('copilot-key-btn-active');
            apiKeyBtn.title = 'Custom API Key Active (Click to view or remove)';
          }
          if (apiKeyBadgeText) {
            apiKeyBadgeText.textContent = 'Custom Key';
          }
          if (currentKeyBadge) {
            currentKeyBadge.className = 'key-status-pill custom';
            const masked = userKey.length > 12 ? `${userKey.slice(0, 6)}...${userKey.slice(-4)}` : 'Active';
            currentKeyBadge.textContent = `Custom Key (${masked})`;
          }
          if (statusIndicator) {
            statusIndicator.innerHTML = '<span style="color: var(--accent-teal);">● Custom AI Key Active</span>';
          }
        } else {
          if (apiKeyBtn) {
            apiKeyBtn.classList.remove('copilot-key-btn-active');
            apiKeyBtn.title = 'Configure OpenRouter / OpenAI API Key';
          }
          if (apiKeyBadgeText) {
            apiKeyBadgeText.textContent = 'API Key';
          }
          if (currentKeyBadge) {
            currentKeyBadge.className = 'key-status-pill default';
            currentKeyBadge.textContent = 'Admin Default Key';
          }
          if (statusIndicator) {
            statusIndicator.innerHTML = '<span style="color: var(--accent-teal);">● Local / Cloud Online</span>';
          }
        }
        if (userKeyInput && document.activeElement !== userKeyInput) {
          userKeyInput.value = userKey;
        }
      }

      const copilotState = {
        open: false,
        persona: 'architect',
        protocolGoal: 'auto',
        protocolObjective: '',
        inferredAnalysis: null,
        messages: [],
        isStreaming: false,
        abortController: null,
      };

      const COPILOT_MODE_PROMPTS = {
        architect: [
          'Optimize my circadian dosing schedule for this stack',
          'What synergistic co-factors can enhance this protocol?',
          'How should I adjust dosing based on my body weight and eGFR?',
          'Propose a balanced daily protocol with morning and bedtime allocations'
        ],
        auditor: [
          'Audit my stack for CYP450 enzyme bottlenecks and DDI surges',
          'Are there any renal or hepatic clearance concerns with my biomarkers?',
          'What protective countermeasures should I add to mitigate risks?',
          'Check for receptor overlap or target competition clashes'
        ],
        tutor: [
          'Explain the exact molecular mechanism of action for my stack',
          'How do these compounds interact at the receptor and enzyme level?',
          'Explain the downstream AMPK and mitochondrial signaling pathways',
          'What is the binding affinity and receptor occupancy kinetics here?'
        ],
        labs: [
          'How will this stack impact my lipid profile (ApoB/Triglycerides) and ALT?',
          'My ALT is 45 U/L and eGFR is 85; what adjustments are recommended?',
          'Analyze hormone balance (Testosterone/Estradiol/SHBG) for this protocol',
          'What lab biomarkers should I monitor while on this stack?'
        ]
      };

      const copilotDrawer = document.getElementById('copilot-drawer');
      const copilotBackdrop = document.getElementById('copilot-drawer-backdrop');
      const copilotFloatingTrigger = document.getElementById('floating-copilot-trigger');
      const copilotHeaderBtn = document.getElementById('protocol-copilot-btn');
      const copilotApiKeyBtn = document.getElementById('copilot-api-key-btn');
      const copilotCloseBtn = document.getElementById('copilot-drawer-close');
      const copilotClearBtn = document.getElementById('copilot-clear-chat');
      const copilotChatContainer = document.getElementById('copilot-chat-container');
      const copilotInput = document.getElementById('copilot-chat-input');
      const copilotSendBtn = document.getElementById('copilot-chat-send-btn');
      const copilotModeBar = document.getElementById('copilot-mode-bar');
      const copilotQuickPrompts = document.getElementById('copilot-quick-prompts');
      const copilotStackTags = document.getElementById('copilot-drawer-stack-tags');
      const copilotGoalSelect = document.getElementById('copilot-goal-select');
      const copilotGoalStatusBadge = document.getElementById('copilot-goal-status-badge');
      const copilotToggleNotesBtn = document.getElementById('copilot-toggle-notes-btn');
      const copilotCustomNotesWrap = document.getElementById('copilot-custom-notes-wrap');
      const copilotCustomNotes = document.getElementById('copilot-custom-notes');
      const copilotInferredText = document.getElementById('copilot-inferred-text');

      let _inferTimeout = null;
      async function syncStackPurposeAndGaps() {
        clearTimeout(_inferTimeout);
        _inferTimeout = setTimeout(async () => {
          const compoundKeys = (state.stack || []).map(s => s.key || s.name || s.id).filter(Boolean);
          if (!compoundKeys.length) {
            if (copilotInferredText) copilotInferredText.textContent = 'Add compounds to infer stack purpose';
            return;
          }
          try {
            const biometrics = getBiometricsPayload();
            const res = await fetch('/api/ai/infer-purpose', {
              method: 'POST',
              headers: getAiRequestHeaders(),
              body: JSON.stringify({
                stack: compoundKeys,
                biometrics: biometrics,
                user_goal: copilotState.protocolGoal,
                user_objective: copilotState.protocolObjective,
                user_api_key: getUserApiKey() || undefined,
              })
            });
            if (res.ok) {
              const data = await res.json();
              copilotState.inferredAnalysis = data;
              if (copilotInferredText) {
                const gaps = data.therapeutic_gaps || [];
                const gapText = gaps.length ? ` • ⚠️ ${gaps.length} gaps flagged` : ' • ✓ Balanced';
                copilotInferredText.innerHTML = `<strong>${escapeHtml(data.goal_title)}</strong>${gapText}`;
              }
              if (copilotGoalStatusBadge) {
                copilotGoalStatusBadge.className = `copilot-goal-badge ${data.is_user_selected ? 'user' : 'auto'}`;
                copilotGoalStatusBadge.textContent = data.is_user_selected ? 'User' : 'Auto';
              }
            }
          } catch (e) {
            console.debug('Purpose inference notice', e);
          }
        }, 150);
      }

      if (copilotGoalSelect) {
        copilotGoalSelect.addEventListener('change', (e) => {
          copilotState.protocolGoal = e.target.value;
          if (copilotGoalStatusBadge) {
            const isUser = e.target.value !== 'auto';
            copilotGoalStatusBadge.className = `copilot-goal-badge ${isUser ? 'user' : 'auto'}`;
            copilotGoalStatusBadge.textContent = isUser ? 'User' : 'Auto';
          }
          if (e.target.value === 'custom' && copilotCustomNotesWrap) {
            copilotCustomNotesWrap.style.display = 'block';
            if (copilotCustomNotes) copilotCustomNotes.focus();
          }
          syncStackPurposeAndGaps();
        });
      }

      if (copilotToggleNotesBtn && copilotCustomNotesWrap) {
        copilotToggleNotesBtn.addEventListener('click', () => {
          const isHidden = copilotCustomNotesWrap.style.display === 'none';
          copilotCustomNotesWrap.style.display = isHidden ? 'block' : 'none';
          copilotToggleNotesBtn.style.color = isHidden ? 'var(--accent-cyan)' : 'var(--text-muted)';
          if (isHidden && copilotCustomNotes) copilotCustomNotes.focus();
        });
      }

      if (copilotCustomNotes) {
        copilotCustomNotes.addEventListener('input', (e) => {
          copilotState.protocolObjective = e.target.value;
        });
      }

      function syncCopilotStackTags() {
        if (!copilotStackTags) return;
        const stackList = state.stack || [];
        if (!stackList.length) {
          copilotStackTags.innerHTML = '<span style="color: var(--text-muted); font-size: 0.74rem;">No compounds in stack</span>';
          if (copilotInferredText) copilotInferredText.textContent = 'Add compounds to infer stack purpose';
          return;
        }
        copilotStackTags.innerHTML = stackList.map(c => `
          <span style="display: inline-flex; align-items: center; gap: 4px; background: rgba(0, 242, 254, 0.1); border: 1px solid rgba(0, 242, 254, 0.25); border-radius: 4px; padding: 2px 6px; font-size: 0.72rem; color: var(--accent-cyan); font-weight: 700;">
            ${c.name || c.key} <span style="color: var(--text-muted); font-size: 0.68rem;">${c.dose}${c.unit || 'mg'}</span>
          </span>
        `).join('');
        syncStackPurposeAndGaps();
      }

      function renderQuickPrompts() {
        if (!copilotQuickPrompts) return;
        const prompts = COPILOT_MODE_PROMPTS[copilotState.persona] || COPILOT_MODE_PROMPTS.architect;
        copilotQuickPrompts.innerHTML = prompts.map(p => `
          <button class="quick-prompt-chip" data-prompt="${p.replace(/"/g, '&quot;')}">${p}</button>
        `).join('');

        copilotQuickPrompts.querySelectorAll('.quick-prompt-chip').forEach(chip => {
          chip.addEventListener('click', () => {
            const promptText = chip.getAttribute('data-prompt');
            if (promptText && !copilotState.isStreaming) {
              sendCopilotMessage(promptText, promptText);
            }
          });
        });
      }

      // Drag-to-resize & Expand Mode setup
      const copilotResizeHandle = document.getElementById('copilot-resize-handle');
      const copilotExpandBtn = document.getElementById('copilot-drawer-expand');
      const copilotExpandIcon = document.getElementById('copilot-expand-icon');
      const copilotExpandText = document.getElementById('copilot-expand-text');

      let isResizingCopilot = false;

      // Restore saved custom width if present
      try {
        const savedWidth = localStorage.getItem('healthai_copilot_width');
        if (savedWidth && Number(savedWidth) >= 380) {
          document.documentElement.style.setProperty('--copilot-width', `${Number(savedWidth)}px`);
        }
      } catch (e) {}

      if (copilotResizeHandle && copilotDrawer) {
        const onResizeStart = (e) => {
          isResizingCopilot = true;
          copilotDrawer.classList.add('resizing');
          copilotResizeHandle.classList.add('active');
          document.body.style.cursor = 'ew-resize';
          document.body.style.userSelect = 'none';
        };

        const onResizeMove = (e) => {
          if (!isResizingCopilot) return;
          const clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : null);
          if (clientX === null) return;
          const targetWidth = Math.max(380, Math.min(Math.round(window.innerWidth - clientX), Math.round(window.innerWidth * 0.94)));
          document.documentElement.style.setProperty('--copilot-width', `${targetWidth}px`);
        };

        const onResizeEnd = () => {
          if (!isResizingCopilot) return;
          isResizingCopilot = false;
          copilotDrawer.classList.remove('resizing');
          copilotResizeHandle.classList.remove('active');
          document.body.style.cursor = '';
          document.body.style.userSelect = '';
          try {
            const currentWidth = copilotDrawer.getBoundingClientRect().width;
            if (currentWidth >= 380) {
              localStorage.setItem('healthai_copilot_width', Math.round(currentWidth));
            }
          } catch (e) {}
        };

        copilotResizeHandle.addEventListener('mousedown', onResizeStart);
        window.addEventListener('mousemove', onResizeMove);
        window.addEventListener('mouseup', onResizeEnd);

        copilotResizeHandle.addEventListener('touchstart', onResizeStart, { passive: true });
        window.addEventListener('touchmove', onResizeMove, { passive: true });
        window.addEventListener('touchend', onResizeEnd);
      }

      if (copilotExpandBtn && copilotDrawer) {
        copilotExpandBtn.addEventListener('click', () => {
          const isExpanded = copilotDrawer.classList.toggle('expanded');
          if (copilotExpandIcon) copilotExpandIcon.textContent = isExpanded ? '⤡' : '⤢';
          if (copilotExpandText) copilotExpandText.textContent = isExpanded ? 'Standard' : 'Wide';
          copilotExpandBtn.title = isExpanded ? 'Switch to Standard Width (⤡)' : 'Switch to Wide Width (⤢)';
        });
      }

      function toggleCopilotDrawer(forceOpen) {
        const nextState = typeof forceOpen === 'boolean' ? forceOpen : !copilotState.open;
        copilotState.open = nextState;
        if (copilotDrawer) copilotDrawer.classList.toggle('open', nextState);
        if (copilotBackdrop) copilotBackdrop.classList.toggle('open', nextState);
        if (nextState) {
          syncCopilotStackTags();
          renderQuickPrompts();
          if (copilotInput) copilotInput.focus();
        }
      }

      if (copilotFloatingTrigger) copilotFloatingTrigger.addEventListener('click', () => toggleCopilotDrawer(true));
      if (copilotHeaderBtn) copilotHeaderBtn.addEventListener('click', () => toggleCopilotDrawer(true));
      if (copilotCloseBtn) copilotCloseBtn.addEventListener('click', () => toggleCopilotDrawer(false));
      if (copilotBackdrop) copilotBackdrop.addEventListener('click', () => toggleCopilotDrawer(false));

      // Global keyboard shortcut: Ctrl+K or Cmd+K
      document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
          e.preventDefault();
          toggleCopilotDrawer();
        } else if (e.key === 'Escape' && copilotState.open) {
          toggleCopilotDrawer(false);
        }
      });

      // Persona Tab Switching
      if (copilotModeBar) {
        copilotModeBar.querySelectorAll('.copilot-mode-btn').forEach(btn => {
          btn.addEventListener('click', () => {
            copilotModeBar.querySelectorAll('.copilot-mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            copilotState.persona = btn.getAttribute('data-mode') || 'architect';
            renderQuickPrompts();
            showToast(`Switched Copilot Persona to ${btn.textContent.trim()}`, '🤖');
          });
        });
      }

      // Clear chat
      if (copilotClearBtn) {
        copilotClearBtn.addEventListener('click', async () => {
          if (copilotState.abortController) {
            copilotState.abortController.abort();
            copilotState.abortController = null;
          }
          copilotState.isStreaming = false;
          if (copilotSendBtn) copilotSendBtn.disabled = false;
          copilotState.messages = [];
          copilotState.protocolObjective = '';
          copilotState.inferredAnalysis = null;

          if (copilotCustomNotes) {
            copilotCustomNotes.value = '';
          }
          if (copilotInput) {
            copilotInput.value = '';
            copilotInput.style.height = 'auto';
          }

          if (copilotChatContainer) {
            copilotChatContainer.innerHTML = `
              <div class="chat-msg assistant">
                <div class="chat-msg-header">
                  <span>🤖 HealthAI Copilot</span>
                  <span style="color: var(--accent-teal);">• Reset</span>
                </div>
                <div class="chat-msg-bubble">
                  <p>Conversation history and model context completely reset. Choose an expert persona or ask any question to begin.</p>
                </div>
              </div>
            `;
          }

          // Trigger backend LLM KV cache and slot context wipe
          try {
            await fetch('/api/ai/chat/reset', { method: 'POST' });
          } catch (e) {
            console.debug('Copilot model reset notice:', e);
          }

          showToast('Copilot chat and model context reset', '🗑️');
        });
      }

      function applyCopilotStackDiff(diff) {
        if (!diff) return;
        let modifiedCount = 0;

        // 1. Removals
        if (Array.isArray(diff.removals || diff.remove)) {
          const toRemove = (diff.removals || diff.remove).map(k => String(k).toLowerCase().trim());
          const initialLen = state.stack.length;
          state.stack = state.stack.filter(s => !toRemove.includes(String(s.key || s.name).toLowerCase().trim()));
          if (state.stack.length < initialLen) modifiedCount++;
        }

        // 2. Modifications
        if (Array.isArray(diff.modifications || diff.modify)) {
          (diff.modifications || diff.modify).forEach(m => {
            const key = String(m.key || m.name || '').toLowerCase().trim();
            const existing = state.stack.find(s => String(s.key || s.name).toLowerCase().trim() === key);
            if (existing) {
              if (m.dose !== undefined) existing.dose = m.dose;
              if (m.unit !== undefined) existing.unit = m.unit;
              if (m.timing !== undefined) existing.timing = m.timing;
              modifiedCount++;
            }
          });
        }

        // 3. Additions
        if (Array.isArray(diff.additions || diff.add)) {
          (diff.additions || diff.add).forEach(a => {
            const key = String(a.key || a.name || '').toLowerCase().trim().replace(/ /g, '_');
            const exists = state.stack.some(s => String(s.key || s.name).toLowerCase().trim() === key);
            if (!exists && key) {
              state.stack.push({
                key: key,
                name: a.name || a.key || key,
                dose: a.dose || 100,
                unit: a.unit || 'mg',
                frequency: a.frequency || 'daily',
                timing: a.timing || 'morning',
                route: a.route || 'oral'
              });
              modifiedCount++;
            }
          });
        }

        renderStackList();
        if (state.stack.length) evaluateStack();
        else updateDashboardEmpty();
        syncCopilotStackTags();

        showToast(`✓ Copilot protocol applied: ${modifiedCount} updates made to workbench stack!`, '⚡');
      }
      window.applyCopilotStackDiff = applyCopilotStackDiff;

      function renderQuotaExceededCard(bubbleElement, pendingUserPrompt) {
        if (!bubbleElement) return;
        const currentSavedKey = getUserApiKey();
        bubbleElement.innerHTML = `
          <div class="copilot-quota-card">
            <div class="copilot-quota-header">
              <span>💳</span>
              <span>Admin Token Budget Exhausted</span>
            </div>
            <p class="copilot-quota-desc">
              The live webpage's OpenRouter token quota has run out. You can continue using all HealthAI Copilot features and protocol optimizations uninterrupted by providing your own OpenRouter (or OpenAI) API key below:
            </p>
            <div class="copilot-quota-input-wrap">
              <div class="copilot-quota-field-row">
                <input type="password" class="copilot-quota-input inline-quota-input" placeholder="sk-or-v1-..." value="${escapeHtml(currentSavedKey)}" />
                <button type="button" class="btn-secondary inline-quota-vis-btn" style="padding: 7px 10px; font-size: 0.76rem;" title="Show/Hide Key">👁️</button>
                <button type="button" class="btn-primary inline-quota-save-btn" style="padding: 7px 14px; font-size: 0.76rem; font-weight: 800; white-space: nowrap; background: linear-gradient(135deg, #00f2fe 0%, #4f46e5 100%); border: none; cursor: pointer;">
                  💾 Save & Retry
                </button>
              </div>
              <div class="inline-quota-feedback" style="font-size: 0.72rem; min-height: 16px; line-height: 1.35;"></div>
              <div class="copilot-quota-actions">
                <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">🌐 Get OpenRouter Key (openrouter.ai/keys) ↗</a>
                <span style="color: var(--text-muted);">Stored locally in your browser</span>
              </div>
            </div>
          </div>
        `;

        const inputEl = bubbleElement.querySelector('.inline-quota-input');
        const visBtn = bubbleElement.querySelector('.inline-quota-vis-btn');
        const saveBtn = bubbleElement.querySelector('.inline-quota-save-btn');
        const feedbackEl = bubbleElement.querySelector('.inline-quota-feedback');

        if (visBtn && inputEl) {
          visBtn.addEventListener('click', () => {
            inputEl.type = inputEl.type === 'password' ? 'text' : 'password';
            visBtn.textContent = inputEl.type === 'password' ? '👁️' : '🙈';
          });
        }

        if (saveBtn && inputEl) {
          saveBtn.addEventListener('click', async () => {
            const keyVal = (inputEl.value || '').trim();
            if (!keyVal) {
              if (feedbackEl) feedbackEl.innerHTML = '<span style="color: #f87171;">Please enter a valid API key.</span>';
              return;
            }
            if (feedbackEl) feedbackEl.innerHTML = '<span style="color: var(--accent-cyan);"><span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span> Validating key...</span>';
            saveBtn.disabled = true;

            try {
              const valRes = await fetch('/api/ai/validate-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: keyVal })
              });
              const valData = await valRes.json();
              if (valData.valid) {
                setUserApiKey(keyVal);
                showToast('✓ Custom API key validated & saved!', '🔑');
                if (feedbackEl) feedbackEl.innerHTML = '<span style="color: #34d399;">✓ Key valid! Resuming copilot...</span>';
                setTimeout(() => {
                  const msgEl = bubbleElement.closest('.chat-msg');
                  if (msgEl) msgEl.remove();
                  if (pendingUserPrompt) {
                    if (copilotState.messages.length && copilotState.messages[copilotState.messages.length - 1].role === 'user') {
                      copilotState.messages.pop();
                    }
                    const lastUserBubble = copilotChatContainer ? copilotChatContainer.querySelector('.chat-msg.user:last-of-type') : null;
                    if (lastUserBubble) lastUserBubble.remove();
                    sendCopilotMessage(pendingUserPrompt, pendingUserPrompt);
                  }
                }, 500);
              } else {
                saveBtn.disabled = false;
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color: #f87171;">⚠️ ${escapeHtml(valData.message || 'Key validation failed')}</span>`;
              }
            } catch (err) {
              setUserApiKey(keyVal);
              showToast('Saved custom API key', '🔑');
              setTimeout(() => {
                const msgEl = bubbleElement.closest('.chat-msg');
                if (msgEl) msgEl.remove();
                if (pendingUserPrompt) {
                  if (copilotState.messages.length && copilotState.messages[copilotState.messages.length - 1].role === 'user') {
                    copilotState.messages.pop();
                  }
                  const lastUserBubble = copilotChatContainer ? copilotChatContainer.querySelector('.chat-msg.user:last-of-type') : null;
                  if (lastUserBubble) lastUserBubble.remove();
                  sendCopilotMessage(pendingUserPrompt, pendingUserPrompt);
                }
              }, 500);
            }
          });
        }
      }

      async function sendCopilotMessage(userPromptText, userDisplayHtml) {
        const text = (userPromptText || (copilotInput ? copilotInput.value : '')).trim();
        if (!text) return;

        // If a previous stream is still active, abort it cleanly first
        if (copilotState.isStreaming && copilotState.abortController) {
          copilotState.abortController.abort();
          copilotState.abortController = null;
          copilotState.isStreaming = false;
        }

        if (copilotInput) {
          copilotInput.value = '';
          copilotInput.style.height = 'auto';
        }

        // Add user message to conversation history
        copilotState.messages.push({ role: 'user', content: text });

        // Add user message bubble (displaying clean label rather than internal generation prompt)
        const userMsgEl = document.createElement('div');
        userMsgEl.className = 'chat-msg user';
        userMsgEl.innerHTML = `
          <div class="chat-msg-header">
            <span>You</span>
          </div>
          <div class="chat-msg-bubble">
            ${userDisplayHtml || escapeHtml(text)}
          </div>
        `;
        copilotChatContainer.appendChild(userMsgEl);

        // Add assistant placeholder bubble with expandable thought box
        const assistantMsgEl = document.createElement('div');
        assistantMsgEl.className = 'chat-msg assistant';
        assistantMsgEl.innerHTML = `
          <div class="chat-msg-header">
            <span>🤖 HealthAI ${copilotState.persona.toUpperCase()}</span>
            <span class="copilot-stream-status" style="color: var(--accent-cyan); display: inline-flex; align-items: center; gap: 4px;">
              <span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Initializing...
            </span>
          </div>
          <div class="copilot-thought-box" style="display: none;">
            <div class="copilot-thought-header" onclick="this.parentElement.classList.toggle('collapsed')">
              <div class="copilot-thought-header-left">
                <span class="copilot-thought-icon">🧠</span>
                <span class="copilot-thought-title">Clinical Reasoning & Grounding</span>
                <span class="copilot-thought-badge live"><span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span> Thinking</span>
              </div>
              <div class="copilot-thought-header-right">
                <span class="copilot-thought-meta">0.0s</span>
                <span class="copilot-thought-toggle">▾</span>
              </div>
            </div>
            <div class="copilot-thought-body">
              <div class="copilot-thought-content"></div>
            </div>
          </div>
          <div class="chat-msg-bubble">
            <span style="color: var(--text-muted); font-style: italic;">
              <span class="copilot-pulse-dot" style="width: 6px; height: 6px; display: inline-block; margin-right: 6px;"></span>Grounding against Pharmacokinetics & Biological Network...
            </span>
          </div>
          <div class="action-cards-wrap" style="display: flex; flex-direction: column; gap: 8px;"></div>
        `;
        copilotChatContainer.appendChild(assistantMsgEl);
        copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;

        const bubble = assistantMsgEl.querySelector('.chat-msg-bubble');
        const actionCardsWrap = assistantMsgEl.querySelector('.action-cards-wrap');
        const headerStatus = assistantMsgEl.querySelector('.copilot-stream-status');
        const thoughtBox = assistantMsgEl.querySelector('.copilot-thought-box');
        const thoughtContent = assistantMsgEl.querySelector('.copilot-thought-content');
        const thoughtBody = assistantMsgEl.querySelector('.copilot-thought-body');
        const thoughtBadge = assistantMsgEl.querySelector('.copilot-thought-badge');
        const thoughtMeta = assistantMsgEl.querySelector('.copilot-thought-meta');

        copilotState.isStreaming = true;
        if (copilotSendBtn) copilotSendBtn.disabled = true;

        const compoundKeys = (state.stack || []).map(s => s.key || s.name || s.id).filter(Boolean);
        const biometrics = getBiometricsPayload();

        copilotState.abortController = new AbortController();
        let accumulatedContent = '';
        let accumulatedReasoning = '';
        let lastActionCardPayload = null;
        let reasoningStartTime = Date.now();
        let reasoningCount = 0;
        let reasoningCompleted = false;
        let currentEvent = 'delta';
        let quotaExceededTriggered = false;

        try {
          const response = await fetch('/api/ai/chat/stream', {
            method: 'POST',
            headers: getAiRequestHeaders(),
            body: JSON.stringify({
              messages: copilotState.messages,
              persona: copilotState.persona,
              stack: compoundKeys,
              biometrics: biometrics,
              protocol_goal: copilotState.protocolGoal,
              protocol_objective: copilotState.protocolObjective,
              user_api_key: getUserApiKey() || undefined,
            }),
            signal: copilotState.abortController.signal
          });

          if (response.status === 402) {
            quotaExceededTriggered = true;
            if (headerStatus) {
              headerStatus.innerHTML = '• Token Budget Exhausted';
              headerStatus.style.color = '#fbbf24';
            }
            renderQuotaExceededCard(bubble, text);
            return;
          }

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = (errData.detail || `Server returned ${response.status}`).toLowerCase();
            if (response.status === 402 || errMsg.includes('credit') || errMsg.includes('quota') || errMsg.includes('token budget')) {
              quotaExceededTriggered = true;
              if (headerStatus) {
                headerStatus.innerHTML = '• Token Budget Exhausted';
                headerStatus.style.color = '#fbbf24';
              }
              renderQuotaExceededCard(bubble, text);
              return;
            }
            throw new Error(errData.detail || `Server returned ${response.status}`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          let streamFinished = false;

          while (!streamFinished) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep partial line in buffer

            for (const line of lines) {
              const trimmedLine = line.trim();
              if (trimmedLine === '') {
                currentEvent = 'delta';
                continue;
              }

              if (trimmedLine.startsWith('event:')) {
                currentEvent = trimmedLine.slice(6).trim();
              } else if (trimmedLine.startsWith('data:')) {
                const rawStr = trimmedLine.startsWith('data: ') ? trimmedLine.slice(6) : trimmedLine.slice(5);
                let dataVal;
                try {
                  dataVal = JSON.parse(rawStr);
                } catch (e) {
                  dataVal = rawStr;
                }
                if (dataVal === '[DONE]') {
                  streamFinished = true;
                  break;
                }

                if (currentEvent === 'quota_exceeded') {
                  quotaExceededTriggered = true;
                  if (headerStatus) {
                    headerStatus.innerHTML = '• Token Budget Exhausted';
                    headerStatus.style.color = '#fbbf24';
                  }
                  renderQuotaExceededCard(bubble, text);
                  streamFinished = true;
                  break;
                } else if (currentEvent === 'delta') {
                  if (!reasoningCompleted && accumulatedReasoning) {
                    reasoningCompleted = true;
                    if (thoughtBadge) {
                      const finalElapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
                      thoughtBadge.className = 'copilot-thought-badge';
                      thoughtBadge.innerHTML = `✓ Reasoned in ${finalElapsed}s`;
                    }
                    if (thoughtBox && !thoughtBox.classList.contains('collapsed')) {
                      thoughtBox.classList.add('collapsed');
                    }
                  }

                  accumulatedContent += (typeof dataVal === 'string' ? dataVal : JSON.stringify(dataVal));
                  if (bubble && accumulatedContent.trim()) {
                    bubble.innerHTML = renderMarkdownLite(accumulatedContent);
                  }
                  if (headerStatus) {
                    headerStatus.innerHTML = '<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Formulating protocol...';
                    headerStatus.style.color = 'var(--accent-cyan)';
                  }
                  copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;
                } else if (currentEvent === 'reasoning') {
                  const reasoningText = typeof dataVal === 'string' ? dataVal : JSON.stringify(dataVal);
                  accumulatedReasoning += reasoningText;
                  reasoningCount++;

                  if (thoughtBox) {
                    thoughtBox.style.display = 'block';
                    if (thoughtContent) {
                      thoughtContent.textContent = accumulatedReasoning;
                      if (thoughtBody) thoughtBody.scrollTop = thoughtBody.scrollHeight;
                    }
                    if (thoughtMeta) {
                      const elapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
                      thoughtMeta.textContent = `${elapsed}s`;
                    }
                  }

                  if ((!accumulatedContent || !accumulatedContent.trim()) && headerStatus) {
                    headerStatus.innerHTML = '<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Deep Graph & PK/PD Reasoning...';
                    headerStatus.style.color = 'var(--accent-cyan)';
                  }
                  copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;
                } else if (currentEvent === 'action_card') {
                  try {
                    const cardObj = typeof dataVal === 'string' ? JSON.parse(dataVal) : dataVal;
                    lastActionCardPayload = cardObj.payload || cardObj;
                    renderActionCardInChat(actionCardsWrap, cardObj);
                    copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;
                  } catch (e) {
                    console.debug('Card parse notice', e);
                  }
                } else if (currentEvent === 'error') {
                  console.warn('Copilot streaming notice:', dataVal);
                  const errString = String(dataVal).toLowerCase();
                  if (errString.includes('credit') || errString.includes('quota') || errString.includes('402') || errString.includes('token budget')) {
                    quotaExceededTriggered = true;
                    if (headerStatus) {
                      headerStatus.innerHTML = '• Token Budget Exhausted';
                      headerStatus.style.color = '#fbbf24';
                    }
                    renderQuotaExceededCard(bubble, text);
                    streamFinished = true;
                    break;
                  }
                  if (headerStatus) {
                    headerStatus.innerHTML = '<span class="copilot-pulse-dot" style="background: var(--accent-orange); width: 6px; height: 6px;"></span> Calibrating Grounding...';
                    headerStatus.style.color = 'var(--accent-orange)';
                  }
                }
              }
            }
          }

          try { reader.cancel(); } catch (e) {}

          if (quotaExceededTriggered) {
            return;
          }

          if (!reasoningCompleted && accumulatedReasoning) {
            reasoningCompleted = true;
            if (thoughtBadge) {
              const finalElapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
              thoughtBadge.className = 'copilot-thought-badge';
              thoughtBadge.innerHTML = `✓ Reasoned in ${finalElapsed}s`;
            }
          }

          // Fallback if no content was yielded
          if (!accumulatedContent || !accumulatedContent.trim()) {
            const hasActionCards = actionCardsWrap && actionCardsWrap.children.length > 0;
            if (hasActionCards) {
              accumulatedContent = "### ⚡ Protocol Architecture Formulated\n\nClinical protocol calibrated against patient biometrics and pharmacokinetic clearance. Review the proposed adjustments in the action card below and click to apply them directly to your active workbench stack:";
            } else {
              accumulatedContent = "Clinical protocol analysis completed.";
            }
            if (bubble) bubble.innerHTML = renderMarkdownLite(accumulatedContent);
          }

          // Save completed assistant message to history (including action card payload for cumulative multi-turn tracking)
          const finalMsgContent = (lastActionCardPayload && !accumulatedContent.includes('<action_card'))
            ? `${accumulatedContent}\n\n<action_card type="stack_diff">${JSON.stringify(lastActionCardPayload)}</action_card>`
            : accumulatedContent;
          copilotState.messages.push({ role: 'assistant', content: finalMsgContent });

          // Update header status
          if (headerStatus) {
            headerStatus.innerHTML = '• Ready';
            headerStatus.style.color = 'var(--accent-teal)';
          }

        } catch (err) {
          if (err.name !== 'AbortError') {
            console.error('Copilot Stream Error:', err);
            const errStr = String(err.message || '').toLowerCase();
            if (errStr.includes('quota') || errStr.includes('credit') || errStr.includes('402') || errStr.includes('token budget')) {
              if (headerStatus) {
                headerStatus.innerHTML = '• Token Budget Exhausted';
                headerStatus.style.color = '#fbbf24';
              }
              renderQuotaExceededCard(bubble, text);
              return;
            }
            if (bubble) {
              bubble.innerHTML = `
                <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: var(--radius-sm); padding: 12px;">
                  <strong style="color: #f87171;">⚠️ Copilot Notice:</strong>
                  <p style="margin-top: 4px; font-size: 0.84rem; color: var(--text-secondary);">${err.message || 'Connection lost'}</p>
                  <p style="margin-top: 6px; font-size: 0.76rem; color: var(--text-muted);">Ensure local AI engine (llama-server on port 8080 or Ollama on port 11434) is running, or enter a custom OpenRouter key via the 🔑 API Key button above.</p>
                </div>
              `;
            }
            if (headerStatus) {
              headerStatus.innerHTML = '• Notice';
              headerStatus.style.color = '#f87171';
            }
          }
        } finally {
          copilotState.isStreaming = false;
          if (copilotSendBtn) copilotSendBtn.disabled = false;
          copilotState.abortController = null;
        }
      }

      function renderActionCardInChat(container, cardObj) {
        if (!container || !cardObj) return;
        const payload = cardObj.payload || cardObj;
        const cardType = cardObj.type || payload.action_card;

        if (cardType === 'stack_diff' || payload.add || payload.modify || payload.remove || payload.additions || payload.modifications || payload.removals) {
          const additions = payload.additions || payload.add || [];
          const modifications = payload.modifications || payload.modify || [];
          const removals = payload.removals || payload.remove || [];

          if (!additions.length && !modifications.length && !removals.length) return;

          let rowsHtml = '';
          additions.forEach(a => {
            rowsHtml += `
              <div class="diff-row add">
                <span style="color: var(--accent-teal); font-weight: 800;">+ ADD: ${escapeHtml(a.name || a.key)}</span>
                <span style="color: var(--text-muted); font-size: 0.74rem;">${escapeHtml(a.dose)}${escapeHtml(a.unit || 'mg')} • ${escapeHtml(a.timing || 'morning')}</span>
              </div>
            `;
          });
          modifications.forEach(m => {
            rowsHtml += `
              <div class="diff-row modify">
                <span style="color: #fbbf24; font-weight: 800;">~ TITRATE: ${escapeHtml(m.name || m.key)}</span>
                <span style="color: var(--text-muted); font-size: 0.74rem;">➔ ${escapeHtml(m.dose)}${escapeHtml(m.unit || 'mg')} • ${escapeHtml(m.timing || 'morning')}</span>
              </div>
            `;
          });
          removals.forEach(r => {
            rowsHtml += `
              <div class="diff-row remove">
                <span style="color: #f87171; font-weight: 800;">- REMOVE: ${escapeHtml(r)}</span>
                <span style="color: var(--text-muted); font-size: 0.74rem;">Eliminate conflict</span>
              </div>
            `;
          });

          const diffJsonEscaped = JSON.stringify(payload).replace(/"/g, '&quot;');
          
          // Clear any intermediate partial card so only one consolidated card is displayed
          container.innerHTML = '';

          const cardEl = document.createElement('div');
          cardEl.className = 'action-card-diff';
          cardEl.innerHTML = `
            <div class="action-card-title">
              <span>⚡ AI Proposed Protocol Modifications</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
              ${rowsHtml}
            </div>
            <button class="btn-apply-diff" onclick="applyCopilotStackDiff(${diffJsonEscaped})">
              <span>⚡ Apply Changes to Workbench Stack</span>
            </button>
          `;
          container.appendChild(cardEl);
        }
      }

      // Input event listeners
      if (copilotSendBtn) {
        copilotSendBtn.addEventListener('click', () => sendCopilotMessage());
      }
      if (copilotInput) {
        copilotInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendCopilotMessage();
          }
        });
        copilotInput.addEventListener('input', () => {
          copilotInput.style.height = 'auto';
          copilotInput.style.height = `${Math.min(copilotInput.scrollHeight, 120)}px`;
        });
      }

      // ==========================================================================
      // AI STACK BUILDER & SCRATCH PROTOCOL GENERATOR
      // ==========================================================================
      const aiBuilderModal = document.getElementById('ai-stack-builder-modal');
      const openAiBuilderBtn = document.getElementById('open-ai-stack-builder-btn');
      const emptyStateAiBuilderBtn = document.getElementById('empty-state-ai-builder-btn');
      const aiBuilderCloseBtn = document.getElementById('ai-builder-close-btn');
      const builderCancelBtn = document.getElementById('builder-cancel-btn');
      const builderGenerateBtn = document.getElementById('builder-generate-btn');
      const builderGoalsGrid = document.getElementById('builder-goals-grid');
      const builderBioSummary = document.getElementById('builder-bio-summary');
      const builderRiskPref = document.getElementById('builder-risk-pref');
      const builderStimPref = document.getElementById('builder-stim-pref');
      const builderComplexityPref = document.getElementById('builder-complexity-pref');
      const builderStylePref = document.getElementById('builder-style-pref');
      const builderRoutePref = document.getElementById('builder-route-pref');
      const builderSchedulePref = document.getElementById('builder-schedule-pref');
      const builderOrganPref = document.getElementById('builder-organ-pref');
      const builderBudgetPref = document.getElementById('builder-budget-pref');
      const builderCustomNotes = document.getElementById('builder-custom-notes');

      const builderBioToggleBtn = document.getElementById('builder-bio-toggle-btn');
      const builderBioEditor = document.getElementById('builder-bio-editor');
      const builderBioToggleText = document.getElementById('builder-bio-toggle-text');
      const builderBioToggleIcon = document.getElementById('builder-bio-toggle-icon');
      const copilotBioToggleBtn = document.getElementById('copilot-bio-toggle-btn');
      const copilotBioDrawer = document.getElementById('copilot-bio-drawer');
      const copilotBioToggleIcon = document.getElementById('copilot-bio-toggle-icon');

      if (builderBioToggleBtn && builderBioEditor) {
        builderBioToggleBtn.addEventListener('click', () => {
          const isHidden = builderBioEditor.style.display === 'none';
          builderBioEditor.style.display = isHidden ? 'flex' : 'none';
          if (builderBioToggleText) builderBioToggleText.textContent = isHidden ? 'Hide Metrics' : 'Edit Metrics';
          if (builderBioToggleIcon) builderBioToggleIcon.textContent = isHidden ? '▲' : '✏️';
        });
      }

      if (copilotBioToggleBtn && copilotBioDrawer) {
        copilotBioToggleBtn.addEventListener('click', () => {
          const isHidden = copilotBioDrawer.style.display === 'none';
          copilotBioDrawer.style.display = isHidden ? 'flex' : 'none';
          copilotBioToggleBtn.classList.toggle('active', isHidden);
          if (copilotBioToggleIcon) copilotBioToggleIcon.textContent = isHidden ? '▲' : '✏️';
        });
      }

      function syncBuilderBiometricsPreview() {
        syncAllBiometrics('bio', false);
      }

      function openAiStackBuilderModal() {
        if (!aiBuilderModal) return;
        syncAllBiometrics('bio', false);
        aiBuilderModal.classList.add('open');
      }

      function closeAiStackBuilderModal() {
        if (!aiBuilderModal) return;
        aiBuilderModal.classList.remove('open');
      }

      if (openAiBuilderBtn) {
        openAiBuilderBtn.addEventListener('click', openAiStackBuilderModal);
        openAiBuilderBtn.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openAiStackBuilderModal();
          }
        });
      }
      if (emptyStateAiBuilderBtn) emptyStateAiBuilderBtn.addEventListener('click', openAiStackBuilderModal);
      if (aiBuilderCloseBtn) aiBuilderCloseBtn.addEventListener('click', closeAiStackBuilderModal);
      if (builderCancelBtn) builderCancelBtn.addEventListener('click', closeAiStackBuilderModal);
      if (aiBuilderModal) {
        aiBuilderModal.addEventListener('click', (e) => {
          if (e.target === aiBuilderModal) closeAiStackBuilderModal();
        });
      }

      let selectedBuilderGoal = 'cognitive_focus';

      if (builderGoalsGrid) {
        builderGoalsGrid.querySelectorAll('.builder-goal-card').forEach(card => {
          card.addEventListener('click', () => {
            builderGoalsGrid.querySelectorAll('.builder-goal-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedBuilderGoal = card.getAttribute('data-goal') || 'cognitive_focus';
          });
        });
      }

      const GOAL_TITLES = {
        cognitive_focus: 'Cognitive Focus & Neuroprotection',
        longevity_autophagy: 'Longevity & Cellular Autophagy',
        cardiovascular_lipid: 'Cardiovascular & Lipid Optimization',
        anabolic_physique: 'Physique & Anabolic Hypertrophy',
        sleep_stress_recovery: 'Sleep Architecture & Stress Recovery',
        fat_loss_metabolic: 'Metabolic Output & Fat Loss',
        post_therapy_reset: 'Post-Therapy Restoration (PCT / Reset)',
        custom: 'Custom Clinical Protocol'
      };

      function quickBuildStackFromScratch(goalId) {
        const goal = goalId || 'cognitive_focus';
        const title = GOAL_TITLES[goal] || goal.replace(/_/g, ' ').toUpperCase();
        
        // Open copilot drawer and switch to Architect
        toggleCopilotDrawer(true);
        copilotState.persona = 'architect';
        if (copilotModeBar) {
          copilotModeBar.querySelectorAll('.copilot-mode-btn').forEach(b => {
            b.classList.toggle('active', b.getAttribute('data-mode') === 'architect');
          });
        }
        copilotState.protocolGoal = goal;
        if (copilotGoalSelect) copilotGoalSelect.value = goal;

        const promptText = `🏗️ Build a comprehensive, synergistic ${title} protocol from scratch. Include exact circadian timing allocations, pharmacokinetic rationales, organ protection co-factors, and provide the action card to apply the entire stack.`;
        const displayHtml = `<span>🏗️ <strong>Build ${escapeHtml(title)}</strong> from scratch</span>`;
        sendCopilotMessage(promptText, displayHtml);
        showToast(`AI Architect: Designing ${title} from scratch...`, '✨');
      }
      window.quickBuildStackFromScratch = quickBuildStackFromScratch;

      if (builderGenerateBtn) {
        builderGenerateBtn.addEventListener('click', () => {
          const goal = selectedBuilderGoal || 'cognitive_focus';
          const title = GOAL_TITLES[goal] || 'Clinical Protocol';
          const risk = builderRiskPref ? builderRiskPref.value : '';
          const stim = builderStimPref ? builderStimPref.value : '';
          const complexity = builderComplexityPref ? builderComplexityPref.value : '';
          const style = builderStylePref ? builderStylePref.value : '';
          const route = builderRoutePref ? builderRoutePref.value : '';
          const schedule = builderSchedulePref ? builderSchedulePref.value : '';
          const organ = builderOrganPref ? builderOrganPref.value : '';
          const budget = builderBudgetPref ? builderBudgetPref.value : '';
          const notes = (builderCustomNotes ? builderCustomNotes.value : '').trim();

          closeAiStackBuilderModal();
          toggleCopilotDrawer(true);

          copilotState.persona = 'architect';
          if (copilotModeBar) {
            copilotModeBar.querySelectorAll('.copilot-mode-btn').forEach(b => {
              b.classList.toggle('active', b.getAttribute('data-mode') === 'architect');
            });
          }
          copilotState.protocolGoal = goal;
          if (copilotGoalSelect) copilotGoalSelect.value = goal;
          if (notes) {
            copilotState.protocolObjective = notes;
            if (copilotCustomNotes) copilotCustomNotes.value = notes;
            if (copilotCustomNotesWrap) copilotCustomNotesWrap.style.display = 'block';
          }

          let promptParts = [`🏗️ Please build a personalized ${title} protocol from scratch.`];
          
          let prefItems = [];
          if (risk) prefItems.push(`Risk tolerance = ${risk}`);
          if (stim) prefItems.push(`Stimulant level = ${stim}`);
          if (complexity) prefItems.push(`Complexity = ${complexity}`);
          if (style) prefItems.push(`Substance style = ${style}`);
          if (route) prefItems.push(`Route preference = ${route}`);
          if (schedule) prefItems.push(`Dosing schedule = ${schedule}`);
          if (organ) prefItems.push(`Organ shield priority = ${organ}`);
          if (budget) prefItems.push(`Sourcing/Budget tier = ${budget}`);

          if (prefItems.length > 0) {
            promptParts.push(`Preferences: ${prefItems.join(', ')}.`);
          }
          if (notes) {
            promptParts.push(`Patient specific notes/constraints: "${notes}".`);
          }
          promptParts.push('Provide a structured circadian schedule, molecular pharmacodynamic rationale, and the action card to apply the complete protocol to my workbench stack.');

          let tagPills = [];
          if (risk === 'conservative') {
            tagPills.push(`<span style="background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); border-radius: 4px; padding: 1px 5px; color: var(--accent-teal);">🛡️ Conservative Risk</span>`);
          } else if (risk === 'aggressive') {
            tagPills.push(`<span style="background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3); border-radius: 4px; padding: 1px 5px; color: #f59e0b;">⚡ Aggressive Potency</span>`);
          } else if (risk === 'balanced') {
            tagPills.push(`<span style="background: rgba(0,242,254,0.1); border: 1px solid rgba(0,242,254,0.25); border-radius: 4px; padding: 1px 5px; color: var(--accent-cyan);">🛡️ Balanced Risk</span>`);
          } else if (risk) {
            tagPills.push(`<span style="background: rgba(0,242,254,0.1); border: 1px solid rgba(0,242,254,0.25); border-radius: 4px; padding: 1px 5px; color: var(--accent-cyan);">Risk: ${escapeHtml(risk)}</span>`);
          }

          if (stim) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">Stim: ${escapeHtml(stim)}</span>`);
          if (complexity) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">${escapeHtml(complexity)}</span>`);
          if (style) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">${escapeHtml(style)}</span>`);
          if (route) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">Route: ${escapeHtml(route)}</span>`);
          if (schedule) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">Schedule: ${escapeHtml(schedule)}</span>`);
          if (organ) tagPills.push(`<span style="background: rgba(236,72,153,0.12); border: 1px solid rgba(236,72,153,0.25); border-radius: 4px; padding: 1px 5px; color: #f472b6;">Shield: ${escapeHtml(organ)}</span>`);
          if (budget) tagPills.push(`<span style="background: rgba(255,255,255,0.06); border-radius: 4px; padding: 1px 5px;">Budget: ${escapeHtml(budget)}</span>`);
          if (notes) tagPills.push(`<span style="background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25); border-radius: 4px; padding: 1px 5px; color: var(--accent-teal);">Note: ${escapeHtml(notes)}</span>`);

          const displayHtml = `
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <span>🏗️ <strong>Build ${escapeHtml(title)} Protocol</strong></span>
              ${tagPills.length ? `<div style="display: flex; flex-wrap: wrap; gap: 4px; font-size: 0.72rem; color: var(--text-muted);">${tagPills.join('')}</div>` : ''}
            </div>
          `;

          sendCopilotMessage(promptParts.join(' '), displayHtml);
          showToast(`AI Architect: Generating ${title} protocol...`, '🚀');
        });
      }

      // ==============================================================================
      // API KEY SETTINGS MODAL INTERACTION
      // ==============================================================================
      const apiKeyModal = document.getElementById('api-key-modal');
      const copilotApiKeyBtnEl = document.getElementById('copilot-api-key-btn');
      const apiKeyModalClose = document.getElementById('api-key-modal-close');
      const apiKeyCancelBtn = document.getElementById('api-key-cancel-btn');
      const saveApiKeyBtn = document.getElementById('save-api-key-btn');
      const clearApiKeyBtn = document.getElementById('clear-api-key-btn');
      const testApiKeyBtn = document.getElementById('test-api-key-btn');
      const userApiKeyInput = document.getElementById('user-api-key-input');
      const toggleKeyVisBtn = document.getElementById('toggle-key-visibility-btn');
      const keyValidationFeedback = document.getElementById('key-validation-feedback');

      function openApiKeyModal() {
        if (!apiKeyModal) return;
        if (userApiKeyInput) {
          userApiKeyInput.value = getUserApiKey();
        }
        if (keyValidationFeedback) {
          keyValidationFeedback.innerHTML = '';
        }
        updateApiKeyUiState();
        apiKeyModal.classList.add('open');
        if (userApiKeyInput) userApiKeyInput.focus();
      }

      function closeApiKeyModal() {
        if (!apiKeyModal) return;
        apiKeyModal.classList.remove('open');
      }

      if (copilotApiKeyBtnEl) {
        copilotApiKeyBtnEl.addEventListener('click', openApiKeyModal);
      }
      if (apiKeyModalClose) {
        apiKeyModalClose.addEventListener('click', closeApiKeyModal);
      }
      if (apiKeyCancelBtn) {
        apiKeyCancelBtn.addEventListener('click', closeApiKeyModal);
      }
      if (apiKeyModal) {
        apiKeyModal.addEventListener('click', (e) => {
          if (e.target === apiKeyModal) closeApiKeyModal();
        });
      }

      if (toggleKeyVisBtn && userApiKeyInput) {
        toggleKeyVisBtn.addEventListener('click', () => {
          userApiKeyInput.type = userApiKeyInput.type === 'password' ? 'text' : 'password';
          toggleKeyVisBtn.textContent = userApiKeyInput.type === 'password' ? '👁️' : '🙈';
        });
      }

      if (saveApiKeyBtn && userApiKeyInput) {
        saveApiKeyBtn.addEventListener('click', () => {
          const val = userApiKeyInput.value.trim();
          if (val) {
            setUserApiKey(val);
            showToast('Custom OpenRouter / OpenAI API Key Saved!', '🔑');
            if (keyValidationFeedback) {
              keyValidationFeedback.innerHTML = '<span style="color: #34d399;">✓ Key saved to browser storage. Active for all AI requests.</span>';
            }
            setTimeout(closeApiKeyModal, 450);
          } else {
            clearUserApiKey();
            showToast('Reverted to Admin default API key', 'ℹ️');
            if (keyValidationFeedback) {
              keyValidationFeedback.innerHTML = '<span style="color: var(--text-muted);">Reverted to server default configuration.</span>';
            }
            setTimeout(closeApiKeyModal, 450);
          }
        });
      }

      if (clearApiKeyBtn && userApiKeyInput) {
        clearApiKeyBtn.addEventListener('click', () => {
          clearUserApiKey();
          userApiKeyInput.value = '';
          if (keyValidationFeedback) {
            keyValidationFeedback.innerHTML = '<span style="color: #f87171;">Custom key removed. Reverted to server default.</span>';
          }
          showToast('Custom API key removed', '🗑️');
        });
      }

      if (testApiKeyBtn && userApiKeyInput) {
        testApiKeyBtn.addEventListener('click', async () => {
          const val = userApiKeyInput.value.trim();
          if (!val) {
            if (keyValidationFeedback) {
              keyValidationFeedback.innerHTML = '<span style="color: #f87171;">Please enter an API key to test.</span>';
            }
            return;
          }
          if (keyValidationFeedback) {
            keyValidationFeedback.innerHTML = '<span style="color: var(--accent-cyan);"><span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span> Probing provider endpoint...</span>';
          }
          testApiKeyBtn.disabled = true;

          try {
            const res = await fetch('/api/ai/validate-key', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ api_key: val })
            });
            const data = await res.json();
            if (data.valid) {
              if (keyValidationFeedback) {
                keyValidationFeedback.innerHTML = `<span style="color: #34d399;">✓ ${escapeHtml(data.message || 'Key valid!')} (${escapeHtml(data.provider || 'AI')})</span>`;
              }
            } else {
              if (keyValidationFeedback) {
                keyValidationFeedback.innerHTML = `<span style="color: #f87171;">⚠️ ${escapeHtml(data.message || 'Validation failed')}</span>`;
              }
            }
          } catch (e) {
            if (keyValidationFeedback) {
              keyValidationFeedback.innerHTML = `<span style="color: #f87171;">Network error validating key: ${escapeHtml(e.message)}</span>`;
            }
          } finally {
            testApiKeyBtn.disabled = false;
          }
        });
      }

      updateApiKeyUiState();
      syncAllBiometrics('bio', false);
      renderStackList();
      if (state.stack.length) {
        evaluateStack();
      } else {
        updateDashboardEmpty();
      }