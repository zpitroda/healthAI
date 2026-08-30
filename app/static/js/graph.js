const graphContainer = document.getElementById('graph-canvas');
      const statusEl = document.getElementById('status');
      const nodePanel = document.getElementById('nodePanel');
      const nodePanelContainer = document.getElementById('nodePanelContainer');
      const searchInput = document.getElementById('searchInput');
      const layoutSelect = document.getElementById('layoutSelect');
      const typeFiltersWrap = document.getElementById('typeFilters');
      const legendEl = document.getElementById('legend');
      const stackPillsList = document.getElementById('stackPillsList');
      const stackSearchInput = document.getElementById('stackSearchInput');
      const stackSearchDropdown = document.getElementById('stackSearchDropdown');
      const cascadeChipsList = document.getElementById('cascadeChipsList');
      const inspectorCloseBtn = document.getElementById('inspectorCloseBtn');
      const graphTooltip = document.getElementById('graphTooltip');
      const tooltipTitle = document.getElementById('tooltipTitle');
      const tooltipSub = document.getElementById('tooltipSub');
      const tooltipBadge = document.getElementById('tooltipBadge');
      const btnSimulate = document.getElementById('btnSimulate');
      const btnTracePath = document.getElementById('btnTracePath');
      const btnExport = document.getElementById('btnExport');

      const nodeColors = {
        compound: '#00f2fe',
        receptor: '#ff4b72',
        enzyme: '#f59e0b',
        transporter: '#fb923c',
        ion_channel: '#ef4444',
        signaling_pathway: '#a855f7',
        physiology: '#38bdf8',
        biomarker: '#10b981',
        phenotype: '#f43f5e',
        reaction: '#f97316',
        carrier_protein: '#14b8a6',
        target: '#ff4b72',
        default: '#94a3b8'
      };

      const tierNames = {
        0: 'Compound / Ligand',
        1: 'Molecular Target',
        2: 'Signaling Cascade',
        3: 'Organ Physiology',
        4: 'Clinical Biomarker',
        5: 'Clinical Outcome'
      };

      const state = {
        baseData: { nodes: [], edges: [], cascade_simulation: {}, combined_effects: {} },
        data: { nodes: [], edges: [], cascade_simulation: {}, combined_effects: {} },
        filtered: { nodes: [], edges: [] },
        filterMode: 'all',
        typeFilter: new Set(),
        search: '',
        selectedNode: null,
        selectedTab: 'overview',
        pathfindingMode: false,
        pathSourceNode: null,
        simulating: false,
        cy: null,
        stack: [],
        timeline: 'steady_state',
        loadRequestId: 0,
        localDoseMultipliers: {}, // targetId -> { compId: multiplier }
      };

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
          '1_day': 'Immediate acute response: autonomic tone, heart rate, acute blood pressure reactivity, and immediate peak biophase saturation.',
          '3_days': 'Early adaptation: autonomic steady state, renal electrolyte reabsorption shifts, and acute-phase inflammatory markers.',
          '1_week': 'Sub-acute tone: initial receptor downregulation/upregulation, transaminase elevations, and early glycemic adaptations.',
          '2_weeks': 'Endocrine equilibrium: HPTA axis feedback suppression, steady transaminase enzyme response, and initial lipid receptor modulation.',
          '1_month': 'Hepatic lipid remodeling (4 weeks): LDL-C / HDL-C remodeling, SHBG adaptation, and standard 4-week clinical bloodwork milestone.',
          '2_months': 'Reticulocyte maturation (8 weeks): Cumulative bone marrow erythropoietic stimulation and hematological adaptation.',
          '3_months': 'Full ~120-day erythrocyte turnover (12 weeks): Full steady-state HbA1c, hematocrit, and long-term multi-organ equilibrium.',
          'steady_state': 'Theoretical long-term asymptotic steady-state biological equilibrium (100% full saturation & turnover).',
        };
        return map[tl] || map['steady_state'];
      }

      window.setGraphTimeline = function(tl) {
        state.timeline = tl || 'steady_state';
        const select = document.getElementById('cascadeTimelineSelect');
        if (select && select.value !== state.timeline) select.value = state.timeline;
        loadGraphData();
      };

      function colorForNode(nodeType) {
        return nodeColors[nodeType] || nodeColors.default;
      }

      function getNodeLabel(node) {
        return node.label || node.id;
      }

      function buildTypeFilters() {
        const typeSet = new Set(state.data.nodes.map(node => node.node_type).filter(Boolean));
        if (!typeSet.size) {
          state.typeFilter = new Set(['compound', 'receptor']);
        } else {
          state.typeFilter = new Set(typeSet);
        }

        typeFiltersWrap.innerHTML = '';
        
        // "ALL" Toggle
        const allBtn = document.createElement('button');
        allBtn.className = 'filter-pill active';
        allBtn.textContent = 'All Tiers';
        allBtn.addEventListener('click', () => {
          if (state.typeFilter.size === typeSet.size) {
            state.typeFilter.clear();
            allBtn.classList.remove('active');
            typeFiltersWrap.querySelectorAll('.filter-pill[data-type]').forEach(b => b.classList.remove('active'));
          } else {
            state.typeFilter = new Set(typeSet);
            allBtn.classList.add('active');
            typeFiltersWrap.querySelectorAll('.filter-pill[data-type]').forEach(b => b.classList.add('active'));
          }
          render();
        });
        typeFiltersWrap.appendChild(allBtn);

        Array.from(typeSet).sort().forEach(type => {
          const button = document.createElement('button');
          button.className = 'filter-pill active';
          button.dataset.type = type;
          button.innerHTML = `<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${colorForNode(type)};"></span>${type.replace('_', ' ')}`;
          button.addEventListener('click', () => {
            if (state.typeFilter.has(type)) {
              state.typeFilter.delete(type);
              button.classList.remove('active');
            } else {
              state.typeFilter.add(type);
              button.classList.add('active');
            }
            allBtn.classList.toggle('active', state.typeFilter.size === typeSet.size);
            render();
          });
          typeFiltersWrap.appendChild(button);
        });

        legendEl.innerHTML = '';
        Array.from(typeSet).sort().forEach(type => {
          const chip = document.createElement('div');
          chip.className = 'legend-item';
          chip.innerHTML = `<span class="legend-dot" style="background:${colorForNode(type)};color:${colorForNode(type)};"></span>${type.replace('_', ' ')}`;
          legendEl.appendChild(chip);
        });
      }

      function computeAdjacent(nodeId) {
        const incoming = [];
        const outgoing = [];
        for (const edge of state.data.edges) {
          if (edge.target === nodeId) incoming.push(edge);
          if (edge.source === nodeId) outgoing.push(edge);
        }
        return { incoming, outgoing };
      }

      function resolveSelectedNode() {
        const candidates = [];
        if (Array.isArray(state.data && state.data.nodes)) candidates.push(...state.data.nodes);
        if (Array.isArray(state.filtered && state.filtered.nodes)) candidates.push(...state.filtered.nodes);
        if (Array.isArray(state.baseData && state.baseData.nodes)) candidates.push(...state.baseData.nodes);

        const seen = new Set();
        const unique = [];
        for (const node of candidates) {
          if (!node || !node.id || seen.has(node.id)) continue;
          seen.add(node.id);
          unique.push(node);
        }

        if (!state.selectedNode) return null;
        return unique.find(node => node.id === state.selectedNode) || {
          id: state.selectedNode,
          label: state.selectedNode,
          node_type: 'selected',
        };
      }


      // MULTI-COMPOUND RECEPTOR VISUALIZER WIDGET
      function renderCombinedReceptorWidget(node, combined) {
        if (!combined || !combined.compounds || !combined.compounds.length) return '';

        const dynamicCombined = combined;
        const net = dynamicCombined.net_activation_score;
        const netPct = dynamicCombined.net_activation_pct;
        const satPct = dynamicCombined.receptor_saturation_pct !== undefined ? dynamicCombined.receptor_saturation_pct : 0;
        const reservePct = dynamicCombined.unoccupied_reserve_pct !== undefined ? dynamicCombined.unoccupied_reserve_pct : 100;
        
        // Dial needle: 0% at left (-100% blockade), 50% at center (0% basal), 100% at right (+100% agonism)
        const needlePos = Math.min(96, Math.max(4, 50 + (net * 50)));

        const isPositive = net > 0.05;
        const isNegative = net < -0.05;
        const netColor = isPositive ? '#00f2fe' : (isNegative ? '#ff4b72' : '#c084fc');
        const stateClass = isPositive ? 'state-agonism' : (isNegative ? 'state-antagonism' : 'state-balanced');

        const compoundRows = dynamicCombined.compounds.map((c, idx) => {
          let pillClass = 'pill-modulator';
          if (c.is_agonist) pillClass = 'pill-agonist';
          else if (c.is_antagonist) pillClass = 'pill-antagonist';
          else if (c.is_pam) pillClass = 'pill-pam';
          else if (c.is_nam) pillClass = 'pill-nam';

          const barColor = c.intrinsic_efficacy > 0 ? '#00f2fe' : (c.intrinsic_efficacy < 0 ? '#ff4b72' : '#f59e0b');
          const concStr = c.c_free_nm ? `C<sub>free</sub>: <strong>${c.c_free_nm.toFixed(3)} nM</strong>` : '';
          const affinityStr = c.affinity_ki ? `K<sub>i</sub>: <strong>${c.affinity_ki} nM</strong>` : (c.inhibition_ic50 ? `IC<sub>50</sub>: <strong>${c.inhibition_ic50} nM</strong>` : '');

          return `
            <div class="compound-card">
              <div class="compound-row-top">
                <span class="compound-row-title" style="cursor:pointer;" onclick="focusAndSelectNode('${c.compound_id}')" title="Click to view & adjust global dose">
                  <span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:${barColor}; box-shadow:0 0 6px ${barColor};"></span>
                  ${c.compound_label}
                  <span style="font-size:0.64rem; color:#38bdf8; font-family:'JetBrains Mono',monospace; margin-left:4px; font-weight:700;">(${c.dose_display || 'Standard Dose'})</span>
                </span>
                <span class="compound-action-pill ${pillClass}">${c.action.split(' ')[0]}</span>
              </div>

              <div style="display:flex; justify-content:space-between; font-size:0.68rem; color:var(--text-muted); margin-top:2px;">
                <span>Efficacy: <strong style="color:${barColor};">${c.individual_effect_pct > 0 ? '+' : ''}${c.individual_effect_pct}%</strong></span>
                <span>${[concStr, affinityStr].filter(Boolean).join(' • ') || `Potency: ${c.potency_weight.toFixed(1)}`}</span>
              </div>

              <div class="occupancy-bar-wrap" style="margin-top:4px;">
                <span style="color:var(--text-secondary); min-width:86px;">Receptor Sat:</span>
                <div class="occupancy-track">
                  <div class="occupancy-fill" style="width:${c.absolute_saturation_pct}%; background:${barColor};"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace; font-weight:700; color:var(--text-primary); min-width:44px; text-align:right;">${c.absolute_saturation_pct}%</span>
              </div>

              <div class="occupancy-bar-wrap" style="font-size:0.64rem; opacity:0.8;">
                <span style="color:var(--text-muted); min-width:86px;">Bound Share:</span>
                <div class="occupancy-track" style="height:4px;">
                  <div class="occupancy-fill" style="width:${c.fractional_occupancy_pct}%; background:rgba(255,255,255,0.3);"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace; color:var(--text-muted); min-width:44px; text-align:right;">${c.fractional_occupancy_pct}%</span>
              </div>
            </div>
          `;
        }).join('');

        return `
          <div class="convergence-card">
            <div class="convergence-header">
              <span class="convergence-tag">
                ⚔️ Receptor Saturation & PD • ${dynamicCombined.ligand_count} Compound${dynamicCombined.ligand_count > 1 ? 's' : ''}
              </span>
              <span class="receptor-state-badge ${stateClass}">
                ${dynamicCombined.receptor_state}
              </span>
            </div>

            <!-- TOTAL RECEPTOR POOL SATURATION BAR -->
            <div class="saturation-pool-wrap">
              <div style="display:flex; justify-content:space-between; font-size:0.66rem; text-transform:uppercase; letter-spacing:0.04em;">
                <span style="color:var(--text-secondary);">Receptor Pool Saturation</span>
                <span style="font-family:'JetBrains Mono',monospace; font-weight:700; color:#38bdf8;">${satPct}% Bound • ${reservePct}% Reserve</span>
              </div>
              <div class="saturation-pool-bar">
                <div class="saturation-pool-fill" style="width:${satPct}%; background:linear-gradient(90deg, #38bdf8, #c084fc);"></div>
              </div>
            </div>

            <!-- BIDIRECTIONAL ACTIVATION GAUGE -->
            <div class="gauge-container">
              <div class="gauge-title-row">
                <span style="color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; font-size:0.66rem;">Net Biological Activation</span>
                <span class="gauge-value-readout" style="color:${netColor};">
                  ${netPct > 0 ? '+' : ''}${netPct}%
                </span>
              </div>

              <div class="gauge-track-wrap">
                <div class="gauge-center-notch" title="0% Basal Tone"></div>
                <div class="gauge-marker" style="left:${needlePos}%; border-color:${netColor}; box-shadow:0 0 12px ${netColor};"></div>
              </div>

              <div class="gauge-labels">
                <span style="color:#ff4b72;">-100% Blockade</span>
                <span style="color:var(--text-muted); text-align:center;">0% Basal Tone</span>
                <span style="color:#00f2fe; text-align:right;">+100% Agonism</span>
              </div>
            </div>

            <!-- PER-COMPOUND BREAKDOWN -->
            <div class="compound-influence-list">
              ${compoundRows}
            </div>

            <!-- MECHANISM SUMMARY -->
            <div class="mechanism-summary-card">
              <div style="font-weight:700; color:#38bdf8; margin-bottom:3px; display:flex; align-items:center; gap:4px;">
                🔬 Pharmacodynamic Convergence
              </div>
              ${dynamicCombined.pharmacological_summary}
            </div>
          </div>
        `;
      }

      function renderNodePanel() {
        if (!state.selectedNode) {
          nodePanel.innerHTML = `
            <div>
              <div class="node-hero-title">Select a node</div>
              <p style="color:var(--text-muted); font-size:0.8rem; margin-top:6px;">
                Click any molecular node or edge to inspect binding properties, intracellular pathways, and clinical biomarkers.
              </p>
            </div>
          `;
          return;
        }

        const node = resolveSelectedNode();
        if (!node) return;

        const { incoming, outgoing } = computeAdjacent(node.id);
        const nodeColor = colorForNode(node.node_type);

        const incomingTexts = incoming.length
          ? incoming.map(edge => `
              <div class="neighbor-pill" onclick="focusAndSelectNode('${edge.source}')">
                <strong>${edge.type || 'MODULATES'}</strong>
                <span style="color:var(--text-secondary); font-size:0.72rem;">from ${edge.source} ${edge.affinity_ki ? `(Ki: ${edge.affinity_ki} nM)` : ''}</span>
              </div>
            `).join('')
          : '<div style="color:var(--text-muted); font-size:0.75rem;">No upstream cascade inputs.</div>';

        const outgoingTexts = outgoing.length
          ? outgoing.map(edge => `
              <div class="neighbor-pill" onclick="focusAndSelectNode('${edge.target}')">
                <strong>${edge.type || 'MODULATES'}</strong>
                <span style="color:var(--text-secondary); font-size:0.72rem;">to ${edge.target} ${edge.is_bridge ? '⚡ Cross-Talk Bridge' : ''}</span>
              </div>
            `).join('')
          : '<div style="color:var(--text-muted); font-size:0.75rem;">No downstream targets.</div>';

        // Check if node has combined effect
        const comb = (state.data.combined_effects && state.data.combined_effects[node.id]) || node.combined_effect;
        const combinedWidgetHtml = comb ? renderCombinedReceptorWidget(node, comb) : '';

        // If node is a compound, provide global dose regimen controller
        let compoundGlobalDoseCard = '';
        let compoundConvergingTargetsHtml = '';
        if (node.node_type === 'compound') {
          const stackItem = state.stack.find(s => {
            const p = parseStackKey(s);
            return p.key.toLowerCase() === node.id.toLowerCase() || (node.label && p.key.toLowerCase() === node.label.toLowerCase());
          });
          const parsedDose = stackItem ? parseStackKey(stackItem) : parseStackKey(node.id);

          compoundGlobalDoseCard = `
            <div class="global-dose-card">
              <div style="font-size:0.68rem; text-transform:uppercase; font-weight:700; color:#38bdf8; letter-spacing:0.04em; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <span>💊 Global Regimen & Dose</span>
                <span style="font-family:'JetBrains Mono',monospace; color:var(--text-muted); font-size:0.62rem;">Applies network-wide</span>
              </div>
              <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                <span style="font-size:0.75rem; color:var(--text-secondary); font-weight:600;">Administered Dose:</span>
                <div style="display:flex; align-items:center; gap:6px;">
                  <input 
                    type="number" 
                    class="dose-number-input" 
                    id="compound_dose_val_${node.id}"
                    step="any"
                    min="0"
                    value="${parsedDose.val}"
                    onchange="handleGlobalDoseUpdate('${node.id}', this.value, document.getElementById('compound_dose_unit_${node.id}').value)"
                  />
                  <select 
                    id="compound_dose_unit_${node.id}" 
                    class="dose-unit-select"
                    onchange="handleGlobalDoseUpdate('${node.id}', document.getElementById('compound_dose_val_${node.id}').value, this.value)"
                  >
                    <option value="mg" ${parsedDose.unit === 'mg' ? 'selected' : ''}>mg</option>
                    <option value="μg" ${parsedDose.unit === 'μg' || parsedDose.unit === 'ug' || parsedDose.unit === 'mcg' ? 'selected' : ''}>μg</option>
                    <option value="g" ${parsedDose.unit === 'g' ? 'selected' : ''}>g</option>
                    <option value="IU" ${parsedDose.unit === 'IU' ? 'selected' : ''}>IU</option>
                  </select>
                </div>
              </div>
              <div style="margin-top:6px; font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between;">
                <span>Assigned Regimen:</span>
                <strong style="color:#00f2fe; font-family:'JetBrains Mono',monospace;">${parsedDose.display}</strong>
              </div>
            </div>
          `;

          const targets = outgoing.map(e => {
            const targetNode = (state.data.nodes || []).find(n => n.id === e.target);
            const targetComb = (state.data.combined_effects && state.data.combined_effects[e.target]) || (targetNode && targetNode.combined_effect);
            return { edge: e, targetNode, targetComb };
          }).filter(t => t.targetComb && t.targetComb.has_multiple_ligands);

          if (targets.length) {
            compoundConvergingTargetsHtml = `
              <div class="convergence-card" style="margin-top:4px;">
                <div class="convergence-header">
                  <span class="convergence-tag">⚔️ Converging Target Receptors</span>
                </div>
                <div style="display:flex; flex-direction:column; gap:5px;">
                  ${targets.map(t => {
                    const tc = t.targetComb;
                    const netColor = tc.net_activation_score > 0.05 ? '#00f2fe' : (tc.net_activation_score < -0.05 ? '#ff4b72' : '#c084fc');
                    return `
                      <div class="neighbor-pill" onclick="focusAndSelectNode('${t.edge.target}')">
                        <strong>${t.edge.target}</strong>
                        <span style="color:${netColor}; font-size:0.72rem; font-weight:700;">
                          Net Activation: ${tc.net_activation_pct > 0 ? '+' : ''}${tc.net_activation_pct}% (${tc.receptor_state})
                        </span>
                      </div>
                    `;
                  }).join('')}
                </div>
              </div>
            `;
          }
        }

        if (state.selectedTab === 'overview') {
          const metaRows = [];
          if (node.smiles) metaRows.push(`<div style="grid-column: span 2; background:rgba(0,0,0,0.35); padding:6px 8px; border-radius:6px; font-family:'JetBrains Mono',monospace; font-size:0.68rem; word-break:break-all; border:1px solid rgba(255,255,255,0.06);"><div style="color:var(--text-muted); margin-bottom:2px; font-size:0.62rem;">SMILES</div>${node.smiles}</div>`);
          if (node.logP !== undefined && node.logP !== null) metaRows.push(`<div class="metric-card"><div class="metric-label">LogP Lipophilicity</div><div class="metric-value">${node.logP}</div></div>`);
          if (node.molecular_weight) metaRows.push(`<div class="metric-card"><div class="metric-label">Molecular Weight</div><div class="metric-value">${node.molecular_weight} g/mol</div></div>`);
          if (node.unit) metaRows.push(`<div class="metric-card"><div class="metric-label">Lab Unit</div><div class="metric-value">${node.unit}</div></div>`);
          if (node.biomarker_panel) metaRows.push(`<div class="metric-card"><div class="metric-label">Biomarker Panel</div><div class="metric-value">${node.biomarker_panel}</div></div>`);
          if (node.organ_system) metaRows.push(`<div class="metric-card"><div class="metric-label">Organ System</div><div class="metric-value">${node.organ_system}</div></div>`);
          if (node.pathway_database) metaRows.push(`<div class="metric-card"><div class="metric-label">Pathway DB</div><div class="metric-value">${node.pathway_database}</div></div>`);

          nodePanel.innerHTML = `
            <div>
              <div class="node-hero-title">${getNodeLabel(node)}</div>
              <div class="node-badge-row">
                <span class="node-badge" style="border-color:${nodeColor}; color:${nodeColor}; background:rgba(0, 242, 254, 0.08); font-weight:700;">
                  ${(node.node_type || 'node').toUpperCase()}
                </span>
                <span class="node-badge" style="color:#38bdf8;">Tier ${node.tier !== undefined ? node.tier : 1}: ${node.tier_name || 'Target'}</span>
                <span class="node-badge" style="font-family:'JetBrains Mono',monospace;">${node.id}</span>
              </div>
            </div>

            ${compoundGlobalDoseCard}
            ${combinedWidgetHtml}
            ${compoundConvergingTargetsHtml}

            ${metaRows.length ? `<div class="metrics-grid">${metaRows.join('')}</div>` : ''}

            <div class="metrics-grid">
              <div class="metric-card">
                <div class="metric-label">Inputs / Upstream</div>
                <div class="metric-value" style="color:#38bdf8;">${incoming.length}</div>
              </div>
              <div class="metric-card">
                <div class="metric-label">Downstream Targets</div>
                <div class="metric-value" style="color:#00f2fe;">${outgoing.length}</div>
              </div>
            </div>

            <div>
              <div class="neighbor-group-title">Upstream Regulators & Inputs</div>
              <div class="neighbor-pill-list">${incomingTexts}</div>
            </div>

            <div>
              <div class="neighbor-group-title">Downstream Signaling & Targets</div>
              <div class="neighbor-pill-list">${outgoingTexts}</div>
            </div>
          `;
        } else if (state.selectedTab === 'pharmacodynamics') {
          nodePanel.innerHTML = `
            <div>
              <div class="node-hero-title">${getNodeLabel(node)}</div>
              <p style="color:var(--text-secondary); font-size:0.75rem; margin-top:4px;">Direct molecular binding kinetics & multi-compound receptor cross-talk.</p>
            </div>
            ${compoundGlobalDoseCard}
            ${combinedWidgetHtml}
            ${compoundConvergingTargetsHtml}
            <div>
              <div class="neighbor-group-title">Upstream Ligand Binding</div>
              <div class="neighbor-pill-list">${incomingTexts}</div>
            </div>
            <div>
              <div class="neighbor-group-title">Target Effector Actions</div>
              <div class="neighbor-pill-list">${outgoingTexts}</div>
            </div>
          `;
        } else if (state.selectedTab === 'cascade') {
          const cascade = (state.data && state.data.cascade_simulation) ? state.data.cascade_simulation : null;
          
          let biomarkersHtml = '<p style="color:var(--text-muted); font-size:0.75rem;">No active clinical biomarker shifts mapped.</p>';
          if (cascade && cascade.biomarker_shifts && cascade.biomarker_shifts.length) {
            biomarkersHtml = cascade.biomarker_shifts.map(b => {
              const isUp = b.direction === 'INCREASE';
              const isDown = b.direction === 'DECREASE';
              const cls = isUp ? 'shift-up' : (isDown ? 'shift-down' : 'shift-neutral');
              const arrow = b.arrow || (isUp ? '↑' : (isDown ? '↓' : '→'));
              const inSafe = b.in_safe_range !== false;
              const rangePill = inSafe 
                ? '<span class="range-status-pill range-safe">IN RANGE</span>' 
                : '<span class="range-status-pill range-alert">OUT OF RANGE</span>';
              
              const contribPills = (b.compound_contributions || []).map(c => {
                return `<span class="contrib-chip"><strong>${c.compound_label}:</strong> ${c.formatted_delta}</span>`;
              }).join('');

              const dist = b.distribution || {};
              const p5p95Str = b.p5_p95_range_str || (dist.p5 !== undefined ? `${dist.p5} - ${dist.p95} ${b.unit}` : '');

              return `
                <div class="biomarker-card" id="cascade-item-${b.biomarker_id}">
                  <div class="biomarker-header-row">
                    <div class="biomarker-title" onclick="focusAndSelectNode('${b.biomarker_id}')" style="cursor:pointer;" title="Click to inspect node on graph">
                      <span>${arrow}</span>
                      <span>${b.label || b.name}</span>
                    </div>
                    <div class="biomarker-value-display ${cls}">
                      ${b.formatted_change || b.direction}
                    </div>
                  </div>
                  <div class="biomarker-meta-row">
                    <span>Baseline: <strong>${b.baseline_value} ${b.unit}</strong> → Projected: <strong>${b.estimated_value} ${b.unit}</strong></span>
                    ${rangePill}
                  </div>
                  ${p5p95Str ? `
                  <div class="biomarker-meta-row" style="margin-top:-2px;">
                    <span style="color:#00f2fe; font-family:'JetBrains Mono',monospace; font-size:0.68rem;" title="90% Population Percentile Distribution Curve (p5 to p95)">
                      📊 p5–p95 Curve: <strong>${p5p95Str}</strong>
                    </span>
                    <span>Net Shift: <strong>${b.net_shift > 0 ? '+' : ''}${b.net_shift}</strong></span>
                  </div>
                  ` : `
                  <div class="biomarker-meta-row" style="margin-top:-2px;">
                    <span>Safe Reference: <strong>${b.safe_range} ${b.unit}</strong></span>
                    <span>Net Shift: <strong>${b.net_shift > 0 ? '+' : ''}${b.net_shift}</strong></span>
                  </div>
                  `}
                  <div class="biomarker-meta-row" style="margin-top:1px; font-size:0.65rem; color:#38bdf8; border-top:1px dashed rgba(255,255,255,0.06); padding-top:2px;" title="${b.time_course_description || ''}">
                    <span>⏱️ Steady-State: <strong>~${b.time_to_steady_state_weeks || 1} wks</strong> (t½: ${b.half_time_days || 3}d)</span>
                    <span style="text-transform:capitalize; color:var(--text-muted);">${(b.kinetic_profile || '').replace(/_/g, ' ')}</span>
                  </div>
                  ${contribPills ? `<div class="contrib-chips-list">${contribPills}</div>` : ''}
                </div>
              `;
            }).join('');
          }

          let phenosHtml = '<p style="color:var(--text-muted); font-size:0.75rem;">No clinical phenotype outcomes forecasted.</p>';
          if (cascade && cascade.phenotypes && cascade.phenotypes.length) {
            phenosHtml = cascade.phenotypes.map(p => {
              const isSuppressed = (p.net_score || 0) < -0.03;
              const isHigh = p.risk_status === 'HIGH_RISK';
              const isMod = p.risk_status === 'MODERATE_RISK';
              const tagCls = isSuppressed ? 'risk-suppressed' : (isHigh ? 'risk-high' : (isMod ? 'risk-moderate' : 'risk-neutral'));
              const icon = isSuppressed ? '🛡️' : (p.severity === 'high' || p.severity === 'critical' ? '⚠️' : '🎯');
              const pDistStr = p.p5_p95_range_str || '';
              
              const contribPills = (p.compound_contributions || []).map(c => {
                return `<span class="contrib-chip"><strong>${c.compound_label}:</strong> ${c.formatted_risk}</span>`;
              }).join('');

              return `
                <div class="phenotype-forecast-card" id="cascade-item-${p.phenotype_id}">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:6px;">
                    <div style="font-weight:700; font-size:0.78rem; color:var(--text-primary); cursor:pointer;" onclick="focusAndSelectNode('${p.phenotype_id}')" title="Click to inspect node on graph">
                      ${icon} ${p.label || p.name}
                    </div>
                    <span class="pheno-risk-tag ${tagCls}">${p.risk_badge || p.risk_status || 'OUTCOME'}</span>
                  </div>
                  <div style="display:flex; justify-content:space-between; font-size:0.70rem; color:var(--text-secondary); font-family:'JetBrains Mono', monospace;">
                    <span>Est. Risk Shift: <strong style="color:var(--text-primary);">${p.formatted_risk || `${p.risk_delta_pct}%`}</strong></span>
                    <span style="text-transform:capitalize;">Severity: <strong>${p.severity || 'Moderate'}</strong></span>
                  </div>
                  ${pDistStr ? `
                  <div style="font-size:0.66rem; color:#00f2fe; font-family:'JetBrains Mono', monospace; margin-top:2px;" title="90% Inter-individual Risk Shift Distribution (p5 to p95)">
                    📊 p5–p95 Risk Band: <strong>${pDistStr}</strong>
                  </div>
                  ` : ''}
                  ${p.description ? `<p style="font-size:0.68rem; color:var(--text-muted); margin:0;">${p.description}</p>` : ''}
                  ${contribPills ? `<div class="contrib-chips-list">${contribPills}</div>` : ''}
                </div>
              `;
            }).join('');
          }

          let pathwaysHtml = '<p style="color:var(--text-muted); font-size:0.75rem;">No active intracellular pathways.</p>';
          if (cascade && cascade.activated_pathways && cascade.activated_pathways.length) {
            pathwaysHtml = cascade.activated_pathways.map(pw => {
              const isUp = pw.status === 'UPREGULATED';
              const isDown = pw.status === 'DOWNREGULATED';
              return `
                <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 9px; background:rgba(13,20,38,0.75); border:1px solid rgba(255,255,255,0.06); border-radius:6px; font-size:0.72rem; cursor:pointer;" onclick="focusAndSelectNode('${pw.pathway_id}')" title="Click to focus pathway node">
                  <span style="font-weight:600; color:var(--text-primary);">⚡ ${pw.label || pw.name}</span>
                  <span class="compound-action-pill ${isUp ? 'pill-agonist' : (isDown ? 'pill-antagonist' : 'pill-modulator')}">${pw.status || 'ACTIVE'}</span>
                </div>
              `;
            }).join('');
          }

          nodePanel.innerHTML = `
            <div>
              <div class="node-hero-title">Cascade Forecast & Biomarker Estimation</div>
              <p style="color:var(--text-secondary); font-size:0.75rem; margin-top:4px;">Multi-tier signal propagation from active stack through intracellular pathways to clinical outcomes.</p>
            </div>
            <div style="background:rgba(12,24,38,0.85); border:1px solid rgba(0,242,254,0.25); border-radius:8px; padding:10px 12px; display:flex; flex-direction:column; gap:6px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.75rem; font-weight:700; color:#38bdf8; display:flex; align-items:center; gap:4px;">⏱️ Timeline Horizon:</span>
                <select 
                  class="chip-unit-select" 
                  style="background:rgba(0,0,0,0.4); border:1px solid rgba(0,242,254,0.3); color:#00f2fe; font-weight:700; padding:2px 8px; border-radius:6px; font-size:0.72rem;"
                  onchange="setGraphTimeline(this.value)"
                >
                  <option value="1_day" ${state.timeline === '1_day' ? 'selected' : ''}>1 Day (Acute)</option>
                  <option value="3_days" ${state.timeline === '3_days' ? 'selected' : ''}>3 Days (Early)</option>
                  <option value="1_week" ${state.timeline === '1_week' ? 'selected' : ''}>1 Week (Sub-acute)</option>
                  <option value="2_weeks" ${state.timeline === '2_weeks' ? 'selected' : ''}>2 Weeks (Endocrine)</option>
                  <option value="1_month" ${state.timeline === '1_month' ? 'selected' : ''}>1 Month (Lipids)</option>
                  <option value="2_months" ${state.timeline === '2_months' ? 'selected' : ''}>2 Months (Reticulocyte)</option>
                  <option value="3_months" ${state.timeline === '3_months' ? 'selected' : ''}>3 Months (HbA1c & RBC)</option>
                  <option value="steady_state" ${state.timeline === 'steady_state' || !state.timeline ? 'selected' : ''}>Steady State (Full)</option>
                </select>
              </div>
              <div style="font-size:0.68rem; color:var(--text-secondary); line-height:1.35;">
                ${getTimelineDescription(state.timeline)}
              </div>
            </div>
            ${compoundGlobalDoseCard}
            ${combinedWidgetHtml}
            <div class="cascade-dashboard">
              <div>
                <div class="cascade-section-title">
                  <span>🩸 Quantitative Biomarker Predictions</span>
                  <span style="font-size:0.65rem; color:var(--text-muted); font-weight:normal;">Baseline vs Projected</span>
                </div>
                <div style="display:flex; flex-direction:column; gap:7px; margin-top:6px;">
                  ${biomarkersHtml}
                </div>
              </div>

              <div>
                <div class="cascade-section-title">
                  <span>🎯 Clinical Outcome & Risk Forecast</span>
                  <span style="font-size:0.65rem; color:var(--text-muted); font-weight:normal;">Safety Endpoints</span>
                </div>
                <div style="display:flex; flex-direction:column; gap:7px; margin-top:6px;">
                  ${phenosHtml}
                </div>
              </div>

              <div>
                <div class="cascade-section-title">
                  <span>⚡ Intracellular Signaling Pathways</span>
                  <span style="font-size:0.65rem; color:var(--text-muted); font-weight:normal;">Reactome/KEGG</span>
                </div>
                <div style="display:flex; flex-direction:column; gap:5px; margin-top:6px;">
                  ${pathwaysHtml}
                </div>
              </div>
            </div>
          `;
        } else if (state.selectedTab === 'evidence') {
          // EVIDENCE & CITATIONS TAB
          const entityId = node.id.toLowerCase();
          nodePanel.innerHTML = `
            <div>
              <div class="node-hero-title">${node.label} Evidence Dossier</div>
              <p style="color:var(--text-secondary); font-size:0.75rem; margin-top:4px;">Peer-reviewed literature, landmark clinical trials, and discovery timeline.</p>
            </div>
            <div id="graphEvidenceContent" style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">
              <div style="font-size:0.75rem; color:var(--text-muted);">Fetching authoritative citation network...</div>
            </div>
          `;

          fetch(`/catalog/${encodeURIComponent(entityId)}/evidence-dossier`)
            .then(res => res.json())
            .then(dossier => {
              const el = document.getElementById('graphEvidenceContent');
              if (!el) return;
              const cites = dossier.citations || [];
              const trials = dossier.clinical_trials || [];
              const timeline = dossier.chronological_timeline || [];
              const conflicts = dossier.conflicts || [];

              let outHtml = '';
              if (conflicts.length > 0) {
                outHtml += `<div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:10px;">
                  <div style="font-size:0.78rem; font-weight:800; color:#fbbf24;">⚠️ Active Scientific Controversies</div>`;
                conflicts.forEach(cf => {
                  outHtml += `
                    <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:6px; line-height:1.35;">
                      <strong>${cf.topic || 'Pharmacological Debate'}</strong> (Consensus: ${Math.round((cf.consensus_score||0.6)*100)}%)
                      <div style="color:var(--text-muted); font-size:0.68rem; margin-top:2px;">${cf.divergence_rationale || ''}</div>
                    </div>
                  `;
                });
                outHtml += `</div>`;
              }

              if (timeline.length > 0) {
                outHtml += `<div>
                  <div style="font-size:0.75rem; font-weight:700; color:#38bdf8; margin-bottom:6px;">⏳ Discovery Milestones</div>
                  <div style="display:flex; flex-direction:column; gap:6px;">`;
                timeline.forEach(m => {
                  outHtml += `
                    <div style="font-size:0.72rem; padding:6px 8px; background:rgba(8,13,25,0.7); border:1px solid var(--border-subtle); border-radius:6px;">
                      <span style="color:#00f2fe; font-weight:700; font-family:'JetBrains Mono';">${m.year || 'Discovery'}:</span>
                      <span style="color:var(--text-secondary); margin-left:4px;">${m.title || m.milestone}</span>
                      ${m.pmid ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/" target="_blank" rel="noopener" style="color:#38bdf8; font-size:0.65rem; margin-left:4px;">[PMID: ${m.pmid}]</a>` : ''}
                    </div>
                  `;
                });
                outHtml += `</div></div>`;
              }

              if (cites.length > 0 || trials.length > 0) {
                outHtml += `<div>
                  <div style="font-size:0.75rem; font-weight:700; color:#10b981; margin-bottom:6px;">🔬 Peer-Reviewed Grounding (${cites.length + trials.length} Studies)</div>
                  <div style="display:flex; flex-direction:column; gap:6px;">`;
                cites.slice(0, 5).forEach(c => {
                  outHtml += `
                    <div style="font-size:0.72rem; padding:8px 10px; background:rgba(8,13,25,0.7); border:1px solid var(--border-subtle); border-radius:6px;">
                      <div style="font-weight:700; color:#ffffff;">${c.title}</div>
                      <div style="font-size:0.65rem; color:var(--text-muted); margin-top:2px;">${c.journal || 'Journal'} (${c.pub_year || 'N/A'}) &bull; ${c.evidence_tier || 'Study'}</div>
                      ${c.key_findings ? `<div style="font-size:0.68rem; color:#94a3b8; margin-top:3px;">💡 ${c.key_findings}</div>` : ''}
                      ${c.pmid ? `<div style="margin-top:4px;"><a href="https://pubmed.ncbi.nlm.nih.gov/${c.pmid}/" target="_blank" rel="noopener" style="color:#38bdf8; font-size:0.68rem; text-decoration:none;">PubMed: ${c.pmid} ↗</a></div>` : ''}
                    </div>
                  `;
                });
                outHtml += `</div></div>`;
              }

              el.innerHTML = outHtml || `<div style="font-size:0.75rem; color:var(--text-muted);">No direct literature citations found.</div>`;
            })
            .catch(() => {
              const el = document.getElementById('graphEvidenceContent');
              if (el) el.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted);">Live literature lookup active via PubMed API.</div>`;
            });
        }
      }

      function renderEdgeInspector(edgeData) {
        if (!edgeData) return;
        const nodePanel = document.getElementById('nodePanel');
        const nodePanelContainer = document.getElementById('nodePanelContainer');
        const inspectorHeaderTitle = document.getElementById('inspectorHeaderTitle');

        if (inspectorHeaderTitle) inspectorHeaderTitle.textContent = '⚡ Interaction Provenance';
        if (nodePanelContainer) nodePanelContainer.classList.remove('hidden');

        const src = edgeData.source;
        const tgt = edgeData.target;
        const eType = edgeData.type || edgeData.edge_type || 'MODULATES';
        const ki = edgeData.affinity_ki ? `<div><strong>Ki (Affinity):</strong> ${edgeData.affinity_ki} nM</div>` : '';
        const ic50 = edgeData.inhibition_ic50 ? `<div><strong>IC50:</strong> ${edgeData.inhibition_ic50} nM</div>` : '';
        const discYear = edgeData.discovery_year ? `<div><strong>Discovery Year:</strong> ${edgeData.discovery_year}</div>` : '';
        const consensus = edgeData.consensus_score !== undefined ? Math.round(Number(edgeData.consensus_score) * 100) : 100;
        const pmids = edgeData.pmids || [];
        const isConflict = edgeData.conflict_flag || consensus < 85;

        let pmidHtml = '';
        if (pmids.length > 0) {
          pmidHtml = `
            <div style="margin-top:8px;">
              <span style="font-size:0.72rem; font-weight:700; color:#38bdf8;">Supporting Citations:</span>
              <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;">
                ${pmids.map(p => `<a href="https://pubmed.ncbi.nlm.nih.gov/${p}/" target="_blank" rel="noopener" style="font-size:0.68rem; padding:2px 6px; background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.3); border-radius:4px; color:#38bdf8; text-decoration:none;">PMID: ${p} ↗</a>`).join('')}
              </div>
            </div>
          `;
        }

        let conflictHtml = '';
        if (isConflict) {
          conflictHtml = `
            <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:10px; margin-top:8px;">
              <div style="font-size:0.75rem; font-weight:800; color:#fbbf24;">⚠️ Disputed Relationship (Consensus: ${consensus}%)</div>
              <div style="font-size:0.70rem; color:var(--text-secondary); margin-top:4px;">
                ${edgeData.divergence_rationale || 'Published assays report variance across high-dose in vitro models vs human clinical trials.'}
              </div>
            </div>
          `;
        }

        nodePanel.innerHTML = `
          <div>
            <div style="font-size:0.68rem; text-transform:uppercase; font-weight:800; color:#38bdf8; letter-spacing:0.5px;">Biological Interaction</div>
            <div class="node-hero-title" style="font-size:1.1rem; margin-top:2px;">${src} ➔ ${tgt}</div>
            <div style="display:inline-block; margin-top:6px; padding:2px 8px; border-radius:4px; font-size:0.72rem; font-weight:700; background:rgba(0,242,254,0.12); color:#00f2fe; border:1px solid rgba(0,242,254,0.3);">${eType}</div>
          </div>

          <div style="background:rgba(8,13,25,0.8); border:1px solid var(--border-subtle); border-radius:8px; padding:10px; margin-top:10px; font-size:0.74rem; color:var(--text-secondary); display:flex; flex-direction:column; gap:4px;">
            ${ki}
            ${ic50}
            ${discYear}
            <div><strong>Consensus Agreement:</strong> ${consensus}%</div>
            <div><strong>Vector Magnitude:</strong> ${edgeData.vector_magnitude || 1.0}</div>
          </div>

          ${conflictHtml}
          ${pmidHtml}
        `;
      }

      // INSPECTOR TAB SWITCHING
      document.querySelectorAll('.inspector-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          document.querySelectorAll('.inspector-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          state.selectedTab = tab.dataset.tab;
          const inspectorHeaderTitle = document.getElementById('inspectorHeaderTitle');
          if (inspectorHeaderTitle) inspectorHeaderTitle.textContent = '🧬 Node Inspector';
          renderNodePanel();
        });
      });

      window.openCascadeInspector = (targetId) => {
        state.selectedTab = 'cascade';
        document.querySelectorAll('.inspector-tab').forEach(t => {
          if (t.dataset.tab === 'cascade') t.classList.add('active');
          else t.classList.remove('active');
        });
        nodePanelContainer.classList.remove('hidden');
        renderNodePanel();
        fitGraph();
        if (targetId) {
          setTimeout(() => {
            const el = document.getElementById(`cascade-item-${targetId}`);
            if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              el.style.borderColor = '#00f2fe';
              el.style.boxShadow = '0 0 12px rgba(0, 242, 254, 0.4)';
              setTimeout(() => {
                el.style.borderColor = '';
                el.style.boxShadow = '';
              }, 1600);
            }
          }, 50);
        }
      };

      window.focusAndSelectNode = (nodeId) => {
        if (!state.cy) return;
        let targetEle = state.cy.getElementById(nodeId);
        if (!targetEle.length) {
          targetEle = state.cy.nodes().filter(n => {
            const nid = n.id().toLowerCase();
            const nlabel = (n.data('label') || '').toLowerCase();
            const query = nodeId.toLowerCase();
            return nid === query || nlabel === query;
          });
        }
        if (targetEle && targetEle.length) {
          state.selectedNode = nodeId;
          nodePanelContainer.classList.remove('hidden');
          state.cy.elements().removeClass('highlighted');
          targetEle.addClass('highlighted');
          renderNodePanel();
          fitGraph();
          state.cy.animate({
            center: { eles: targetEle },
            zoom: Math.min(state.cy.maxZoom(), Math.max(1.3, state.cy.zoom())),
            duration: 350
          });
        }
      };

      function renderCascadeStrip(cascade) {
        if (!cascade) {
          cascadeChipsList.innerHTML = '<span class="cascade-badge">No cascade simulation data.</span>';
          return;
        }

        const chips = [];

        (cascade.biomarker_shifts || []).forEach(shift => {
          const name = shift.label || shift.name || shift.biomarker_id || 'Biomarker';
          const isUp = shift.direction === 'INCREASE';
          const isDown = shift.direction === 'DECREASE';
          const arrow = shift.arrow || (isUp ? '↑' : (isDown ? '↓' : '→'));
          const badgeClass = isUp ? 'shift-up' : (isDown ? 'shift-down' : 'shift-neutral');
          const valText = shift.formatted_change ? shift.formatted_change : (shift.direction || 'MODULATED');
          const estSub = shift.estimated_value ? `<span class="badge-sub">(${shift.estimated_value} ${shift.unit})</span>` : '';
          chips.push(`
            <span class="cascade-badge ${badgeClass}" onclick="openCascadeInspector('${shift.biomarker_id}')" title="${name}: ${shift.formatted_display || shift.direction} (Click to inspect detailed forecast)">
              ${arrow} ${name}: <strong>${valText}</strong> ${estSub}
            </span>
          `);
        });

        (cascade.activated_pathways || []).forEach(p => {
          const name = p.label || p.name || p.pathway_id || 'Pathway';
          chips.push(`
            <span class="cascade-badge pathway" onclick="openCascadeInspector('${p.pathway_id}')" title="${name} (${p.status || ''})">
              ⚡ ${name}: <strong>${p.status || 'ACTIVE'}</strong>
            </span>
          `);
        });

        (cascade.phenotypes || []).forEach(pheno => {
          const name = pheno.label || pheno.name || pheno.phenotype_id || 'Phenotype';
          const isSuppressed = (pheno.net_score || 0) < -0.03;
          const isSevere = pheno.severity === 'high' || pheno.severity === 'critical';
          const icon = isSuppressed ? '🛡️' : (isSevere ? '⚠️' : '🎯');
          const riskStyle = isSuppressed 
            ? 'border-color:rgba(16,185,129,0.45); color:#6ee7b7; background:rgba(16,185,129,0.08);' 
            : 'border-color:rgba(244,63,94,0.45); color:#fda4af; background:rgba(244,63,94,0.08);';
          const riskVal = pheno.formatted_risk || `${pheno.risk_delta_pct || 0}%`;
          chips.push(`
            <span class="cascade-badge" style="${riskStyle}" onclick="openCascadeInspector('${pheno.phenotype_id}')" title="${name}: ${pheno.formatted_risk || ''} (Click to inspect forecast)">
              ${icon} ${name}: <strong>${riskVal}</strong>
            </span>
          `);
        });

        cascadeChipsList.innerHTML = chips.length ? chips.join('') : '<span class="cascade-badge">Clean physiological basal state</span>';
      }

      function filterGraph() {
        const search = state.search.trim().toLowerCase();
        const mode = state.filterMode || 'all';
        const nodeIdsInScope = new Set();

        state.filtered.nodes = state.data.nodes.filter(node => {
          if (mode !== 'all') {
            if (mode === 'convergence') {
              const isConvergingTarget = Boolean(
                node.has_multiple_ligands || 
                (node.combined_effect && node.combined_effect.has_multiple_ligands)
              );
              if (isConvergingTarget) return true;

              if (node.node_type === 'compound') {
                const targetsConverging = state.data.edges.some(e => {
                  if (e.source !== node.id) return false;
                  const tNode = state.data.nodes.find(n => n.id === e.target);
                  return Boolean(tNode && (tNode.has_multiple_ligands || (tNode.combined_effect && tNode.combined_effect.has_multiple_ligands)));
                });
                if (targetsConverging) return true;
              }
              return false;
            } else if (mode === 'pd') {
              const isPD = node.node_type === 'compound' || node.pk_pd_class === 'PD' || ['receptor', 'signaling_pathway', 'physiology', 'biomarker', 'phenotype', 'ion_channel', 'target'].includes(node.node_type);
              if (!isPD) return false;
            } else if (mode === 'pk') {
              const isPK = node.node_type === 'compound' || node.pk_pd_class === 'PK' || ['enzyme', 'transporter', 'carrier_protein'].includes(node.node_type);
              if (!isPK) return false;
            } else if (mode === 'outcomes') {
              const isOutcomes = node.node_type === 'compound' || ['biomarker', 'phenotype', 'physiology', 'lab', 'outcome', 'toxicity', 'benefit'].includes(node.node_type);
              if (!isOutcomes) return false;
            }
          }

          if (!state.typeFilter.has(node.node_type)) return false;
          if (search) {
            const label = getNodeLabel(node).toLowerCase();
            const id = (node.id || '').toLowerCase();
            return label.includes(search) || id.includes(search);
          }
          return true;
        });

        state.filtered.nodes.forEach(node => nodeIdsInScope.add(node.id));
        state.filtered.edges = state.data.edges.filter(edge => nodeIdsInScope.has(edge.source) && nodeIdsInScope.has(edge.target));
      }

      // HIGH-DPI CRISP CYTOSCAPE INITIALIZATION
      function ensureCytoscape() {
        if (!window.cytoscape) {
          statusEl.textContent = 'Graph library failed to load.';
          return null;
        }

        if (state.cy) {
          state.cy.resize();
          return state.cy;
        }

        // Force 2x+ pixelRatio so canvas backing store rasterizes text with crisp subpixels
        const dpr = Math.max(window.devicePixelRatio || 1, 2);

        state.cy = window.cytoscape({
          container: graphContainer,
          pixelRatio: dpr,
          textureOnViewport: false,
          motionBlur: false,
          hideEdgesOnViewport: false,
          style: [
            {
              selector: 'node',
              style: {
                'background-color': ele => colorForNode(ele.data('node_type')),
                'label': ele => ele.data('label') || ele.data('id'),
                'font-family': 'Plus Jakarta Sans, -apple-system, sans-serif',
                'font-size': '11px',
                'font-weight': '700',
                'text-wrap': 'wrap',
                'text-max-width': '120px',
                'color': '#f8fafc',
                'text-background-opacity': 0.88,
                'text-background-color': '#070d19',
                'text-background-padding': '3px 5px',
                'text-background-shape': 'roundrectangle',
                'text-border-width': 1,
                'text-border-color': ele => colorForNode(ele.data('node_type')),
                'text-border-opacity': 0.6,
                'text-margin-y': 6,
                'text-valign': 'bottom',
                'text-halign': 'center',
                'border-width': 2.5,
                'border-color': ele => ele.data('node_type') === 'compound' ? '#ffffff' : 'rgba(255,255,255,0.7)',
                'width': ele => ele.data('node_type') === 'compound' ? 46 : (ele.data('node_type') === 'biomarker' ? 32 : 36),
                'height': ele => ele.data('node_type') === 'compound' ? 46 : (ele.data('node_type') === 'biomarker' ? 32 : 36),
                'shape': ele => {
                  const type = ele.data('node_type');
                  if (type === 'compound') return 'ellipse';
                  if (type === 'signaling_pathway') return 'diamond';
                  if (type === 'biomarker') return 'round-rectangle';
                  if (type === 'phenotype') return 'hexagon';
                  if (type === 'physiology') return 'round-rectangle';
                  return 'ellipse';
                },
                'min-zoomed-font-size': 5,
              }
            },
            {
              selector: 'node[?has_multiple_ligands]',
              style: {
                'border-width': 4.0,
                'border-color': ele => {
                  const net = ele.data('net_activation_score') !== undefined ? ele.data('net_activation_score') : 0;
                  if (net > 0.15) return '#00f2fe';
                  if (net < -0.15) return '#ff4b72';
                  return '#c084fc';
                },
              }
            },
            {
              selector: 'edge',
              style: {
                'curve-style': 'bezier',
                'target-arrow-shape': 'triangle',
                'arrow-scale': 1.1,
                'line-color': edge => {
                  const dir = edge.data('direction_class');
                  const isBridge = edge.data('is_bridge');
                  if (isBridge) return '#c084fc';
                  if (dir === 'negative') return '#ff4b72';
                  if (dir === 'allosteric') return '#f59e0b';
                  return '#00f2fe';
                },
                'target-arrow-color': edge => {
                  const dir = edge.data('direction_class');
                  const isBridge = edge.data('is_bridge');
                  if (isBridge) return '#c084fc';
                  if (dir === 'negative') return '#ff4b72';
                  if (dir === 'allosteric') return '#f59e0b';
                  return '#00f2fe';
                },
                'line-style': edge => {
                  const dir = edge.data('direction_class');
                  const isBridge = edge.data('is_bridge');
                  if (isBridge) return 'dotted';
                  if (dir === 'negative') return 'dashed';
                  return 'solid';
                },
                'width': edge => edge.data('is_bridge') ? 2.8 : 2.0,
                'label': 'data(type)',
                'font-family': 'JetBrains Mono, monospace',
                'font-size': '8.5px',
                'font-weight': '600',
                'color': '#cbd5e1',
                'text-background-opacity': 0.85,
                'text-background-color': '#060a14',
                'text-background-padding': '2px 4px',
                'text-background-shape': 'roundrectangle',
                'text-border-width': 0.8,
                'text-border-color': 'rgba(255,255,255,0.15)',
                'text-border-opacity': 0.8,
                'opacity': 0.82,
                'text-rotation': 'autorotate',
                'min-zoomed-font-size': 7,
              }
            },
            {
              selector: 'node:selected',
              style: {
                'border-width': 4,
                'border-color': '#ffffff',
              }
            },
            {
              selector: '.highlighted',
              style: {
                'border-width': 4,
                'border-color': '#00f2fe',
              }
            },
            {
              selector: '.path-highlight',
              style: {
                'line-color': '#c084fc',
                'target-arrow-color': '#c084fc',
                'width': 4.5,
                'opacity': 1.0,
              }
            },
            {
              selector: '.faded',
              style: {
                'opacity': 0.15,
              }
            }
          ],
          zoomingEnabled: true,
          userZoomingEnabled: true,
          panningEnabled: true,
          userPanningEnabled: true,
          minZoom: 0.15,
          maxZoom: 3.5,
          wheelSensitivity: 0.14,
          padding: 40,
        });

        // Hover Spotlight & Tooltip
        state.cy.on('mouseover', 'node', event => {
          const selNode = event.target;
          const neighborhood = selNode.neighborhood().add(selNode);
          state.cy.elements().addClass('faded');
          neighborhood.removeClass('faded');

          const renderedPos = selNode.renderedPosition();
          const nodeData = selNode.data();

          tooltipTitle.textContent = nodeData.label || nodeData.id;
          tooltipSub.textContent = `Type: ${(nodeData.node_type || 'Node').toUpperCase()}`;
          const col = colorForNode(nodeData.node_type);
          
          let badgesHtml = `<span class="tooltip-badge" style="background:${col}22; color:${col}; border:1px solid ${col}66;">Tier ${nodeData.tier !== undefined ? nodeData.tier : 1}: ${nodeData.tier_name || 'Entity'}</span>`;
          if (nodeData.combined_effect && nodeData.combined_effect.has_multiple_ligands) {
            const comb = nodeData.combined_effect;
            const net = comb.net_activation_pct;
            const netCol = net > 0 ? '#00f2fe' : (net < 0 ? '#ff4b72' : '#c084fc');
            badgesHtml += `<span class="tooltip-badge" style="background:${netCol}22; color:${netCol}; border:1px solid ${netCol}66; margin-left:4px;">⚔️ ${comb.ligand_count} Ligands • Net: ${net > 0 ? '+' : ''}${net}%</span>`;
          }
          tooltipBadge.innerHTML = badgesHtml;

          graphTooltip.style.left = `${renderedPos.x}px`;
          graphTooltip.style.top = `${renderedPos.y}px`;
          graphTooltip.style.display = 'block';
        });

        state.cy.on('mouseout', 'node', () => {
          state.cy.elements().removeClass('faded');
          graphTooltip.style.display = 'none';
        });

        state.cy.on('tap', 'node', event => {
          const nodeId = event.target.id();
          
          if (state.pathfindingMode) {
            if (!state.pathSourceNode) {
              state.pathSourceNode = nodeId;
              event.target.addClass('highlighted');
              statusEl.textContent = `Path source selected: ${nodeId}. Now click destination node...`;
              return;
            } else {
              const destNode = nodeId;
              tracePathBetween(state.pathSourceNode, destNode);
              state.pathSourceNode = null;
              state.pathfindingMode = false;
              btnTracePath.classList.remove('active');
              return;
            }
          }

          state.selectedNode = nodeId;
          const inspectorHeaderTitle = document.getElementById('inspectorHeaderTitle');
          if (inspectorHeaderTitle) inspectorHeaderTitle.textContent = '🧬 Node Inspector';
          renderNodePanel();
        });

        // EDGE PROVENANCE & CITATION TAP HANDLER
        state.cy.on('tap', 'edge', event => {
          const edgeData = event.target.data();
          renderEdgeInspector(edgeData);
        });

        state.cy.on('tap', event => {
          if (event.target === state.cy) {
            state.selectedNode = null;
            renderNodePanel();
            state.cy.elements().removeClass('path-highlight');
          }
        });

        // TEMPORAL SCRUBBER LISTENER
        const temporalSlider = document.getElementById('temporalYearSlider');
        const temporalDisplay = document.getElementById('temporalYearDisplay');
        if (temporalSlider && temporalDisplay) {
          temporalSlider.addEventListener('input', (e) => {
            const yr = parseInt(e.target.value, 10);
            temporalDisplay.textContent = yr;
            if (state.cy) {
              state.cy.batch(() => {
                state.cy.edges().forEach(edge => {
                  const dYr = edge.data('discovery_year');
                  if (dYr && Number(dYr) > yr) {
                    edge.style('opacity', 0.08);
                  } else {
                    edge.style('opacity', 1.0);
                  }
                });
              });
            }
          });
        }

        // CONTROVERSY RADAR HIGHLIGHT TOGGLE
        const btnControversies = document.getElementById('btnToggleControversies');
        if (btnControversies) {
          btnControversies.addEventListener('click', () => {
            btnControversies.classList.toggle('active');
            const isActive = btnControversies.classList.contains('active');
            if (state.cy) {
              state.cy.batch(() => {
                state.cy.edges().forEach(edge => {
                  const isDisputed = edge.data('conflict_flag') || (edge.data('consensus_score') !== undefined && Number(edge.data('consensus_score')) < 0.85);
                  if (isActive) {
                    if (isDisputed) {
                      edge.style('line-color', '#fbbf24');
                      edge.style('width', 4);
                      edge.style('opacity', 1.0);
                    } else {
                      edge.style('opacity', 0.15);
                    }
                  } else {
                    edge.removeStyle('line-color');
                    edge.removeStyle('width');
                    edge.removeStyle('opacity');
                  }
                });
              });
            }
          });
        }

        window.addEventListener('resize', () => {
          if (state.cy) {
            state.cy.resize();
          }
        });

        return state.cy;
      }

      function fitGraph(cy) {
        const cyt = cy || state.cy;
        if (!cyt) return;
        cyt.resize();
        const isDrawerOpen = nodePanelContainer && !nodePanelContainer.classList.contains('hidden');
        const isWide = window.innerWidth > 900;
        const padRight = (isDrawerOpen && isWide) ? 410 : 50;
        cyt.fit(undefined, { top: 50, bottom: 50, left: 50, right: padRight });
        cyt.center();
      }

      // CUSTOM MULTI-TIER CASCADE FLOW LAYOUT
      function applyTierFlowLayout(cy) {
        cy.resize();
        const nodes = cy.nodes();
        if (!nodes.length) return;

        // Group nodes by biological tier index
        const tiers = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [] };
        
        nodes.forEach(node => {
          const tier = node.data('tier') !== undefined ? node.data('tier') : 1;
          const bucket = Math.min(5, Math.max(0, tier));
          tiers[bucket].push(node);
        });

        const columnWidth = 230;
        const startX = 60;
        const centerY = 350;

        cy.batch(() => {
          for (let t = 0; t <= 5; t++) {
            const group = tiers[t];
            if (!group || !group.length) continue;
            
            const colX = startX + (t * columnWidth);
            const totalInCol = group.length;
            const spacingY = Math.min(95, Math.max(55, 600 / Math.max(totalInCol, 1)));
            const colHeight = (totalInCol - 1) * spacingY;
            const topY = centerY - (colHeight / 2);

            group.forEach((node, idx) => {
              const jitterX = (idx % 2 === 1) ? 14 : -14;
              node.position({
                x: colX + jitterX,
                y: topY + (idx * spacingY)
              });
            });
          }
        });

        fitGraph(cy);
      }

      function render() {
        filterGraph();
        const cy = ensureCytoscape();
        if (!cy) return;

        cy.resize();

        const seenNodeIds = new Set();
        const cleanNodes = [];
        for (const node of state.filtered.nodes) {
          if (!node || !node.id || seenNodeIds.has(node.id)) continue;
          seenNodeIds.add(node.id);
          const comb = (state.data.combined_effects && state.data.combined_effects[node.id]) || node.combined_effect;
          cleanNodes.push({
            data: {
              id: node.id,
              label: getNodeLabel(node),
              node_type: node.node_type || 'default',
              tier: node.tier !== undefined ? node.tier : 1,
              tier_name: node.tier_name || 'Target',
              degree: node.degree || 0,
              combined_effect: comb,
              has_multiple_ligands: Boolean(comb && comb.has_multiple_ligands),
              net_activation_score: comb ? comb.net_activation_score : 0,
              net_activation_pct: comb ? comb.net_activation_pct : 0,
            },
          });
        }

        const seenEdgeIds = new Set();
        const cleanEdges = [];
        for (const edge of state.filtered.edges) {
          if (!edge || !edge.source || !edge.target) continue;
          if (!seenNodeIds.has(edge.source) || !seenNodeIds.has(edge.target)) continue;
          const edgeId = `${edge.source}->${edge.target}`;
          if (seenEdgeIds.has(edgeId)) continue;
          seenEdgeIds.add(edgeId);
          cleanEdges.push({
            data: {
              id: edgeId,
              source: edge.source,
              target: edge.target,
              type: edge.type || 'MODULATES',
              direction_class: edge.direction_class || 'positive',
              is_bridge: Boolean(edge.is_bridge),
            },
          });
        }

        cy.elements().remove();
        cy.add({ nodes: cleanNodes, edges: cleanEdges });

        const layoutName = layoutSelect ? (layoutSelect.value || 'tier_flow') : 'tier_flow';

        if (layoutName === 'tier_flow') {
          applyTierFlowLayout(cy);
        } else {
          const layoutOptions = {
            name: layoutName,
            padding: 45,
            animate: true,
            animationDuration: 350,
            nodeDimensionsIncludeLabels: true,
          };

          if (layoutName === 'breadthfirst') {
            layoutOptions.directed = true;
            layoutOptions.spacingFactor = 1.4;
          } else if (layoutName === 'cose') {
            layoutOptions.nodeRepulsion = 4500;
            layoutOptions.idealEdgeLength = 90;
            layoutOptions.edgeElasticity = 100;
          } else if (layoutName === 'concentric') {
            layoutOptions.concentric = ele => 6 - (ele.data('tier') || 1);
            layoutOptions.levelWidth = () => 1;
          }

          const layout = cy.layout(layoutOptions);
          layout.run();
          cy.resize();
          cy.fit(undefined, 45);
        }

        const totalCount = cleanNodes.length;
        statusEl.textContent = totalCount === 0
          ? 'No nodes match the selected filters.'
          : `${totalCount} visible nodes • ${cleanEdges.length} connections • ${layoutName.toUpperCase()} layout`;

        renderNodePanel();
      }

      // DYNAMIC CASCADE SIGNAL PROPAGATION SIMULATOR
      function simulateCascadeSignal() {
        if (!state.cy || state.simulating) return;
        state.simulating = true;
        btnSimulate.classList.add('active');
        btnSimulate.textContent = '🌊 Propagating Signal…';

        const cy = state.cy;
        const tiers = [0, 1, 2, 3, 4, 5];

        let step = 0;
        cy.elements().removeClass('highlighted').addClass('faded');

        const interval = setInterval(() => {
          if (step > 5) {
            clearInterval(interval);
            setTimeout(() => {
              cy.elements().removeClass('faded').removeClass('highlighted');
              state.simulating = false;
              btnSimulate.classList.remove('active');
              btnSimulate.textContent = '⚡ Simulate Signal';
              statusEl.textContent = 'Signal cascade simulation complete.';
            }, 600);
            return;
          }

          const currentNodes = cy.nodes().filter(n => (n.data('tier') || 0) === step);
          const currentEdges = cy.edges().filter(e => {
            const srcTier = e.source().data('tier') || 0;
            return srcTier === step - 1 || srcTier === step;
          });

          currentNodes.removeClass('faded').addClass('highlighted');
          currentEdges.removeClass('faded').addClass('highlighted');

          statusEl.textContent = `Propagating signal wave through Tier ${step}: ${tierNames[step] || 'Cascade'}`;
          step++;
        }, 400);
      }

      btnSimulate.addEventListener('click', simulateCascadeSignal);

      // PATHFINDING & CROSS-TALK FINDER
      function tracePathBetween(sourceId, targetId) {
        statusEl.textContent = `Finding biological path from ${sourceId} to ${targetId}…`;
        
        fetch(`/graph-path?source=${encodeURIComponent(sourceId)}&target=${encodeURIComponent(targetId)}&stack=${encodeURIComponent(state.stack.join(','))}`)
          .then(res => res.json())
          .then(data => {
            if (!data.path || !data.path.length) {
              statusEl.textContent = `No connecting biological cascade between ${sourceId} and ${targetId}.`;
              return;
            }

            const cy = state.cy;
            cy.elements().addClass('faded').removeClass('path-highlight');

            const pathEles = [];
            for (let i = 0; i < data.path.length; i++) {
              const n = cy.getElementById(data.path[i]);
              if (n.length) pathEles.push(n);
              if (i < data.path.length - 1) {
                const s = data.path[i];
                const t = data.path[i + 1];
                const e = cy.edges(`[source="${s}"][target="${t}"], [source="${t}"][target="${s}"]`);
                if (e.length) pathEles.push(e);
              }
            }

            pathEles.forEach(ele => ele.removeClass('faded').addClass('path-highlight'));

            statusEl.textContent = `Path found (${data.length} steps): ${data.path.join(' → ')}`;
          })
          .catch(err => {
            console.error(err);
            statusEl.textContent = 'Path lookup error.';
          });
      }

      btnTracePath.addEventListener('click', () => {
        state.pathfindingMode = !state.pathfindingMode;
        state.pathSourceNode = null;
        btnTracePath.classList.toggle('active', state.pathfindingMode);
        if (state.pathfindingMode) {
          statusEl.textContent = 'Path Mode active: Click starting node in the graph…';
        } else {
          statusEl.textContent = 'Path Mode cancelled.';
          if (state.cy) state.cy.elements().removeClass('path-highlight');
        }
      });

      // EXPORT HIGH-RES PNG
      btnExport.addEventListener('click', () => {
        if (!state.cy) return;
        const png = state.cy.png({
          bg: '#050811',
          full: true,
          scale: 2.5
        });
        const link = document.createElement('a');
        link.download = `healthai-knowledge-graph-${state.stack.join('-') || 'network'}.png`;
        link.href = png;
        link.click();
      });

      function roundTo(num, decimals) {
        const factor = Math.pow(10, decimals);
        return Math.round(num * factor) / factor;
      }

      function parseStackKey(item) {
        if (!item) return { raw: '', key: '', val: 10, unit: 'mg', frequency: 'daily', display: '10 mg', effDisplay: '' };
        const parts = String(item).split(':');
        const key = parts[0].trim();
        let val = 10;
        let unit = 'mg';
        let freq = 'daily';

        if (parts.length >= 3) {
          freq = parts[2].trim();
        }

        if (parts.length >= 2) {
          const spec = parts[1].trim();
          const match = spec.match(/^([\d.]+)\s*([a-zA-Zμ]+)(?:_([a-zA-Z0-9_]+))?$/);
          if (match) {
            val = parseFloat(match[1]) || 1.0;
            unit = match[2];
            if (unit === 'ug' || unit === 'mcg') unit = 'μg';
            if (match[3] && parts.length < 3) freq = match[3];
          } else {
            val = parseFloat(spec) || 10;
          }
        } else {
          const node = (state.data && state.data.nodes || []).find(n => 
            n.id.toLowerCase() === key.toLowerCase() || 
            (n.label && n.label.toLowerCase() === key.toLowerCase())
          );
          let doseMg = (node && node.dose_mg !== undefined) ? node.dose_mg : null;
          if (doseMg === null) {
            const kl = key.toLowerCase();
            if (kl.includes('clenbuterol')) doseMg = 0.04;
            else if (kl.includes('nebivolol')) doseMg = 5.0;
            else if (kl.includes('caffeine')) doseMg = 200.0;
            else if (kl.includes('theanine')) doseMg = 200.0;
            else if (kl.includes('creatine')) doseMg = 5000.0;
            else doseMg = 10.0;
          }
          val = doseMg >= 1.0 ? roundTo(doseMg, 2) : roundTo(doseMg * 1000.0, 2);
          unit = doseMg >= 1.0 ? 'mg' : 'μg';
        }

        const mult = getFrequencyMultiplierClient(freq);
        const effVal = val * mult;
        const effDisplay = mult !== 1.0 
          ? `≈ ${effVal >= 1.0 ? effVal.toFixed(effVal >= 10 ? 1 : 2) : (effVal * 1000).toFixed(1)} ${effVal >= 1.0 ? unit : (unit === 'mg' ? 'μg' : unit)}/d`
          : '';

        return { raw: item, key, val, unit, frequency: freq, display: `${val} ${unit}`, effDisplay };
      }

      const compoundNameCache = {
        'chembl49080': 'Clenbuterol',
        'chembl434394': 'Nebivolol',
        'chembl27': 'Propranolol',
        'chembl18': 'Metoprolol',
        'chembl25': 'Atenolol',
        'chembl39': 'Clonidine',
        'chembl714': 'Albuterol',
        'chembl723': 'Telmisartan',
        'chembl1201127': 'Eplerenone',
        'chembl1415': 'Spironolactone',
        'chembl12': 'Diazepam',
        'chembl779': 'Tadalafil',
        'chembl192': 'Sildenafil',
      };

      function resolveCompoundDisplayName(key) {
        if (!key) return '';
        const lowerKey = key.trim().toLowerCase();
        
        // 1. Direct cache lookup
        if (compoundNameCache[lowerKey]) {
          return compoundNameCache[lowerKey];
        }

        // 2. Check current graph data nodes
        if (state.data && Array.isArray(state.data.nodes)) {
          const match = state.data.nodes.find(n => {
            if (!n) return false;
            const nid = String(n.id || '').toLowerCase();
            const nkey = String((n.data && (n.data.key || n.data.canonical_key || n.data.inchikey)) || '').toLowerCase();
            return nid === lowerKey || nkey === lowerKey;
          });
          if (match && match.label && !/^chembl\d+$/i.test(match.label)) {
            compoundNameCache[lowerKey] = match.label;
            return match.label;
          }
        }

        // 3. Check localStorage saved stack
        try {
          const saved = localStorage.getItem('healthai_stack');
          if (saved) {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed)) {
              const item = parsed.find(it => it && (String(it.key || '').toLowerCase() === lowerKey || String(it.name || '').toLowerCase() === lowerKey));
              if (item && item.name && !/^chembl\d+$/i.test(item.name)) {
                compoundNameCache[lowerKey] = item.name;
                return item.name;
              }
            }
          }
        } catch (e) {}

        // 4. If key is a ChEMBL ID, fetch and populate asynchronously
        if (/^chembl\d+$/i.test(lowerKey)) {
          fetch(`/api/compounds/${encodeURIComponent(lowerKey)}`)
            .then(res => res.ok ? res.json() : null)
            .then(c => {
              if (c && c.name && !/^chembl\d+$/i.test(c.name)) {
                compoundNameCache[lowerKey] = c.name;
                renderStackBadges();
              }
            })
            .catch(() => {});
        }

        // 5. Clean standard keys (e.g. "l_theanine" -> "L Theanine")
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      }

      window.focusAndSelectNode = (nodeId) => {
        if (!nodeId) return;
        state.selectedNode = nodeId;
        nodePanelContainer.classList.remove('hidden');
        renderNodePanel();
        if (state.cy) {
          let ele = state.cy.getElementById(nodeId);
          if (!ele.length) {
            ele = state.cy.nodes().filter(n => {
              const nid = n.id().toLowerCase();
              const nlabel = (n.data('label') || '').toLowerCase();
              const query = nodeId.toLowerCase();
              return nid === query || nlabel === query;
            });
          }
          if (ele.length) {
            const targetNode = ele.length > 0 && ele[0] ? ele[0] : ele;
            state.cy.animate({
              center: { eles: targetNode },
              zoom: 1.35,
              duration: 300
            });
            state.cy.elements().removeClass('faded');
            targetNode.neighborhood().add(targetNode).removeClass('faded');
            targetNode.select();
          }
        }
      };

      window.handleGlobalDoseUpdate = (key, val, unit, freq) => {
        const parsedVal = parseFloat(val);
        if (isNaN(parsedVal) || parsedVal <= 0) return;
        const cleanUnit = unit || 'mg';
        const cleanFreq = freq || 'daily';

        const idx = state.stack.findIndex(s => {
          const p = parseStackKey(s);
          return p.key.toLowerCase() === key.toLowerCase();
        });

        const formatted = `${key}:${parsedVal}${cleanUnit}:${cleanFreq}`;
        if (idx >= 0) {
          state.stack[idx] = formatted;
        } else {
          state.stack.push(formatted);
        }

        syncStackState();
        loadGraphData();
      };

      function renderStackBadges() {
        if (!state.stack.length) {
          stackPillsList.innerHTML = '<span style="color:var(--text-muted); font-size:0.75rem;">Empty stack. Search below or add compounds to explore cascade interactions.</span>';
          return;
        }

        stackPillsList.innerHTML = state.stack.map(item => {
          const p = parseStackKey(item);
          const name = resolveCompoundDisplayName(p.key);
          return `
            <span class="compound-chip">
              <span class="chip-name" onclick="focusAndSelectNode('${p.key}')" title="Click to view & inspect compound">${name}</span>
              <input 
                type="number" 
                class="chip-dose-input" 
                step="any"
                min="0"
                value="${p.val}" 
                onchange="handleGlobalDoseUpdate('${p.key}', this.value, this.nextElementSibling.value, this.nextElementSibling.nextElementSibling.value)"
                onkeydown="if(event.key==='Enter'){event.preventDefault(); this.blur(); handleGlobalDoseUpdate('${p.key}', this.value, this.nextElementSibling.value, this.nextElementSibling.nextElementSibling.value);}"
                title="Change administered dose"
              />
              <select 
                class="chip-unit-select" 
                onchange="handleGlobalDoseUpdate('${p.key}', this.previousElementSibling.value, this.value, this.nextElementSibling.value)"
                title="Change dose unit"
              >
                <option value="mg" ${p.unit === 'mg' ? 'selected' : ''}>mg</option>
                <option value="μg" ${p.unit === 'μg' || p.unit === 'ug' || p.unit === 'mcg' ? 'selected' : ''}>μg</option>
                <option value="g" ${p.unit === 'g' ? 'selected' : ''}>g</option>
                <option value="IU" ${p.unit === 'IU' ? 'selected' : ''}>IU</option>
              </select>
              <select 
                class="chip-unit-select" 
                style="width: 58px; font-weight:700;"
                onchange="handleGlobalDoseUpdate('${p.key}', this.previousElementSibling.previousElementSibling.value, this.previousElementSibling.value, this.value)"
                title="Dosing frequency"
              >
                <option value="daily" ${p.frequency === 'daily' ? 'selected' : ''}>QD</option>
                <option value="twice_daily" ${p.frequency === 'twice_daily' ? 'selected' : ''}>BID</option>
                <option value="three_times_daily" ${p.frequency === 'three_times_daily' ? 'selected' : ''}>TID</option>
                <option value="every_other_day" ${p.frequency === 'every_other_day' ? 'selected' : ''}>QOD</option>
                <option value="twice_weekly" ${p.frequency === 'twice_weekly' ? 'selected' : ''}>2x/w</option>
                <option value="weekly" ${p.frequency === 'weekly' ? 'selected' : ''}>QW</option>
                <option value="biweekly" ${p.frequency === 'biweekly' ? 'selected' : ''}>Q2W</option>
                <option value="monthly" ${p.frequency === 'monthly' ? 'selected' : ''}>QM</option>
                <option value="as_needed" ${p.frequency === 'as_needed' ? 'selected' : ''}>PRN</option>
              </select>
              ${p.effDisplay ? `<span style="font-size:0.65rem; color:#38bdf8; font-family:'JetBrains Mono',monospace; padding:0 2px;" title="Continuous daily rate">${p.effDisplay}</span>` : ''}
              <button type="button" class="chip-del" onclick="removeCompoundFromGraph('${item}')" title="Remove from graph">&times;</button>
            </span>
          `;
        }).join('');
      }

      window.removeCompoundFromGraph = (item) => {
        const p = parseStackKey(item);
        state.stack = state.stack.filter(s => {
          const sp = parseStackKey(s);
          return sp.key.toLowerCase() !== p.key.toLowerCase();
        });
        syncStackState();
        loadGraphData();
      };

      function addCompoundToGraph(key) {
        if (!key) return;
        const exists = state.stack.some(s => parseStackKey(s).key.toLowerCase() === key.toLowerCase());
        if (exists) return;
        state.stack.push(key);
        syncStackState();
        loadGraphData();
      }

      function syncStackState() {
        renderStackBadges();
        try {
          const structured = state.stack.map(item => {
            const p = parseStackKey(item);
            const name = resolveCompoundDisplayName(p.key);
            return {
              key: p.key,
              name: name,
              dose: p.val,
              unit: p.unit,
              timing: 'morning',
              frequency: p.frequency || 'daily'
            };
          });
          localStorage.setItem('healthai_stack', JSON.stringify(structured));
          window.dispatchEvent(new CustomEvent('healthai:stack-updated'));
        } catch (e) {
          console.warn('localStorage sync error', e);
        }
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('stack', state.stack.join(','));
        newUrl.searchParams.set('timeline', state.timeline || 'steady_state');
        window.history.replaceState({}, '', newUrl);
      }

      // Real-time synchronization with SafetyLab dashboard across tabs & windows
      window.addEventListener('storage', (e) => {
        if (e.key === 'healthai_stack' && e.newValue) {
          try {
            const parsed = JSON.parse(e.newValue);
            if (Array.isArray(parsed)) {
              const newStack = parsed.map(item => {
                if (typeof item === 'string') return item;
                if (item && (item.key || item.name)) {
                  const k = item.key || item.name;
                  if (item.name && !/^chembl\d+$/i.test(item.name)) {
                    compoundNameCache[String(k).toLowerCase()] = item.name;
                  }
                  if (item.dose !== undefined && item.dose !== null && !isNaN(parseFloat(item.dose))) {
                    const u = (item.unit || 'mg').replace('μg', 'ug');
                    return `${k}:${item.dose}${u}`;
                  }
                  return k;
                }
                return '';
              }).filter(Boolean);
              if (newStack.join(',') !== state.stack.join(',')) {
                state.stack = newStack;
                renderStackBadges();
                loadGraphData();
              }
            }
          } catch (err) {
            console.warn('Storage sync error', err);
          }
        }
      });

      // STACK SEARCH AUTOCOMPLETE (Instant cache + 100ms fast typeahead)
      let searchTimeout = null;
      const _graphSearchQueryCache = {};
      stackSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchTimeout);
        if (!query) {
          stackSearchDropdown.style.display = 'none';
          return;
        }

        const normQ = query.toLowerCase();
        if (_graphSearchQueryCache[normQ]) {
          renderGraphSearchDropdown(_graphSearchQueryCache[normQ]);
          return;
        }

        searchTimeout = setTimeout(() => {
          fetch(`/api/compounds/search?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(items => {
              _graphSearchQueryCache[normQ] = items;
              if (stackSearchInput.value.trim().toLowerCase() === normQ) {
                renderGraphSearchDropdown(items);
              }
            })
            .catch(err => console.error(err));
        }, 100);
      });

      function renderGraphSearchDropdown(items) {
        if (!items || !items.length) {
          stackSearchDropdown.innerHTML = '<div style="padding:8px 11px;color:var(--text-muted);font-size:0.75rem;">No match found</div>';
          stackSearchDropdown.style.display = 'block';
          return;
        }

        stackSearchDropdown.innerHTML = items.map(c => `
          <div class="autocomplete-row" data-key="${c.key}" data-name="${c.name || ''}">
            <span>${c.name}</span>
            <span style="color:#00f2fe;font-size:0.72rem;font-weight:700;">+ Add</span>
          </div>
        `).join('');

        stackSearchDropdown.style.display = 'block';

        stackSearchDropdown.querySelectorAll('.autocomplete-row').forEach(el => {
          el.addEventListener('click', () => {
            if (el.dataset.key && el.dataset.name) {
              compoundNameCache[el.dataset.key.toLowerCase()] = el.dataset.name;
            }
            addCompoundToGraph(el.dataset.key);
            stackSearchInput.value = '';
            stackSearchDropdown.style.display = 'none';
          });
        });
      }

      document.addEventListener('click', (e) => {
        if (!stackSearchInput.contains(e.target) && !stackSearchDropdown.contains(e.target)) {
          stackSearchDropdown.style.display = 'none';
        }
      });

      function applyZoom(delta) {
        if (!state.cy) return;
        const current = state.cy.zoom();
        state.cy.zoom({ level: Math.min(3.5, Math.max(0.15, current + delta)), renderedPosition: { x: state.cy.width() / 2, y: state.cy.height() / 2 } });
      }

      graphContainer.addEventListener('wheel', event => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? -0.12 : 0.12;
        applyZoom(delta);
      }, { passive: false });

      const domainFilterBtns = document.querySelectorAll('#domainFilters .filter-btn');
      domainFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          domainFilterBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          state.filterMode = btn.dataset.filter || 'all';
          render();
        });
      });

      searchInput.addEventListener('input', event => {
        state.search = event.target.value;
        render();

        if (state.cy && state.search.trim()) {
          const match = state.cy.nodes().filter(n => (n.data('label') || '').toLowerCase().includes(state.search.toLowerCase()));
          if (match.length) {
            state.cy.animate({
              center: { eles: match[0] },
              zoom: 1.4,
              duration: 300
            });
          }
        }
      });

      layoutSelect.addEventListener('change', () => render());
      document.getElementById('zoomIn').addEventListener('click', () => applyZoom(0.25));
      document.getElementById('zoomOut').addEventListener('click', () => applyZoom(-0.25));
      document.getElementById('resetView').addEventListener('click', () => {
        fitGraph();
      });

      document.getElementById('togglePanel').addEventListener('click', () => {
        nodePanelContainer.classList.toggle('hidden');
        fitGraph();
      });

      inspectorCloseBtn.addEventListener('click', () => {
        nodePanelContainer.classList.add('hidden');
        fitGraph();
      });

      function loadGraphData() {
        const urlParams = new URLSearchParams(window.location.search);
        let stackFromUrl = [];
        const rawStackParams = urlParams.getAll('stack').filter(Boolean);
        for (const item of rawStackParams) {
          item.split(',').forEach(part => {
            const cleaned = part.trim();
            if (cleaned && !stackFromUrl.includes(cleaned)) stackFromUrl.push(cleaned);
          });
        }

        const saved = localStorage.getItem('healthai_stack');
        let stack = stackFromUrl.length ? stackFromUrl : [];

        const tlFromUrl = urlParams.get('timeline');
        if (tlFromUrl) {
          state.timeline = tlFromUrl;
          const select = document.getElementById('cascadeTimelineSelect');
          if (select) select.value = tlFromUrl;
        }

        if (!stack.length && saved) {
          try {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed)) {
              stack = parsed
                .map(item => {
                  if (typeof item === 'string') return item;
                  if (item && (item.key || item.name)) {
                    const k = item.key || item.name;
                    if (item.name && !/^chembl\d+$/i.test(item.name)) {
                      compoundNameCache[String(k).toLowerCase()] = item.name;
                    }
                    const freq = item.frequency || 'daily';
                    if (item.dose !== undefined && item.dose !== null && !isNaN(parseFloat(item.dose))) {
                      const u = (item.unit || 'mg').replace('μg', 'ug');
                      return `${k}:${item.dose}${u}:${freq}`;
                    }
                    return `${k}:10mg:${freq}`;
                  }
                  return '';
                })
                .filter(Boolean);
            }
          } catch (error) {
            console.warn('Failed to parse saved stack', error);
          }
        }

        if (!stack.length) {
          stack = ['caffeine:200mg:daily', 'creatine:5g:daily', 'theanine:200mg:daily'];
        }

        state.stack = Array.from(new Set(stack));
        renderStackBadges();

        const requestId = ++state.loadRequestId;
        const params = new URLSearchParams();
        state.stack.forEach(item => params.append('stack', item));
        params.set('depth', '5');
        params.set('timeline', state.timeline || 'steady_state');

        fetch(`/graph-data?${params.toString()}`, { cache: 'no-store' })
          .then(response => response.json())
          .then(data => {
            if (requestId !== state.loadRequestId) return;

            state.baseData = data;
            state.data = data;
            if (data.nodes && data.nodes.length) {
              state.selectedNode = data.nodes[0].id;
              data.nodes.forEach(n => {
                if (n && n.id && n.label && !/^chembl\d+$/i.test(n.label)) {
                  compoundNameCache[n.id.toLowerCase()] = n.label;
                  if (n.data && n.data.canonical_key) {
                    compoundNameCache[n.data.canonical_key.toLowerCase()] = n.label;
                  }
                }
              });
              renderStackBadges();
            } else {
              state.selectedNode = null;
            }

            renderCascadeStrip(data.cascade_simulation);
            buildTypeFilters();
            render();
          })
          .catch(error => {
            if (requestId !== state.loadRequestId) return;
            console.error('Failed to load graph data', error);
            statusEl.textContent = 'Graph data unavailable';
          });
      }

      // Mobile menu toggle handling
      const graphMobileMenuBtn = document.getElementById('mobile-menu-toggle');
      const graphNavLinks = document.getElementById('nav-links');
      if (graphMobileMenuBtn && graphNavLinks) {
        graphMobileMenuBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          graphNavLinks.classList.toggle('open');
        });

        document.addEventListener('click', (e) => {
          if (!graphNavLinks.contains(e.target) && !graphMobileMenuBtn.contains(e.target)) {
            graphNavLinks.classList.remove('open');
          }
        });
      }

      window.addEventListener('storage', (event) => {
        if (event.key === 'healthai_stack') {
          loadGraphData();
        }
      });

      loadGraphData();