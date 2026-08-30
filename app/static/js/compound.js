const compoundKey = decodeURIComponent(window.location.pathname.split('/').filter(Boolean).slice(-1)[0] || '');
      const compoundLoading = document.getElementById('compoundLoading');
      const compoundError = document.getElementById('compoundError');
      const compoundContent = document.getElementById('compoundContent');
      const targetInfoModal = document.getElementById('targetInfoModal');
      const targetModalClose = document.getElementById('targetModalClose');
      const layoutSelect = document.getElementById('layoutSelect');
      const btnSimulateFlow = document.getElementById('btnSimulateFlow');
      const openInGraphBtn = document.getElementById('openInGraphBtn');
      const quickCard = document.getElementById('quickCard');
      const quickCardTitle = document.getElementById('quickCardTitle');
      const quickCardSub = document.getElementById('quickCardSub');
      const quickCardDetailBtn = document.getElementById('quickCardDetailBtn');
      const filterBtns = document.querySelectorAll('.filter-btn');

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

      const state = {
        compound: null,
        rawNodes: [],
        rawEdges: [],
        filterMode: 'all',
        cy: null,
        selectedNode: null,
        simulating: false,
      };

      function colorForNode(nodeType) {
        return nodeColors[nodeType] || nodeColors.default;
      }

      function asList(value) {
        if (Array.isArray(value)) return value.filter(item => item !== null && item !== undefined && item !== '');
        if (typeof value === 'string') {
          return value.split(',').map(item => item.trim()).filter(Boolean);
        }
        return [];
      }

      function safeText(value) {
        return value === null || value === undefined || value === 'None' ? '—' : String(value);
      }

      function renderCompound(compound) {
        state.compound = compound;
        document.getElementById('topbarTitle').textContent = compound.name || compound.key || 'Compound Intelligence';
        document.getElementById('compoundName').textContent = compound.name || compound.key || 'Compound';
        document.getElementById('compoundSubtitle').textContent = compound.canonical_name || compound.name || 'No canonical name recorded';
        document.getElementById('compoundRisk').textContent = compound.risk_band || 'LOW';

        const riskBox = document.querySelector('.risk-badge-box');
        const rb = (compound.risk_band || '').toUpperCase();
        if (rb.includes('SEVERE') || rb.includes('HIGH') || rb.includes('CRITICAL')) {
          riskBox.style.borderColor = 'rgba(255, 75, 114, 0.45)';
          riskBox.style.background = 'rgba(255, 75, 114, 0.1)';
          riskBox.querySelector('strong').style.color = '#ff4b72';
        } else if (rb.includes('MODERATE') || rb.includes('ELEVATED')) {
          riskBox.style.borderColor = 'rgba(245, 158, 11, 0.45)';
          riskBox.style.background = 'rgba(245, 158, 11, 0.1)';
          riskBox.querySelector('strong').style.color = '#f59e0b';
        } else {
          riskBox.style.borderColor = 'rgba(16, 185, 129, 0.45)';
          riskBox.style.background = 'rgba(16, 185, 129, 0.1)';
          riskBox.querySelector('strong').style.color = '#10b981';
        }

        const tags = [];
        if (compound.drug_class) tags.push(compound.drug_class);
        if (compound.compound_class) tags.push(compound.compound_class);
        if (compound.route_of_administration) tags.push(compound.route_of_administration);
        if (compound.evidence_level) tags.push(`Evidence: ${compound.evidence_level}`);

        document.getElementById('compoundTags').innerHTML = tags.length
          ? tags.map(tag => `<span class="pill">${tag}</span>`).join('')
          : '<span class="pill">Unclassified Molecule</span>';

        document.getElementById('compoundMechanism').textContent = compound.mechanism || 'No pharmacodynamic mechanism recorded.';

        // PK & ADMET Grid
        const pkRows = [
          ['Elimination Half-Life (t½)', compound.t_half_numeric ? `${compound.t_half_numeric} h (numeric)` : (compound.half_life || '—')],
          ['Oral Bioavailability (F)', compound.bioavailability_f !== null && compound.bioavailability_f !== undefined ? `${Math.round(compound.bioavailability_f * 100)}% (F=${compound.bioavailability_f})` : (compound.oral_bioavailability ? `${compound.oral_bioavailability}%` : '—')],
          ['Volume of Distribution (Vd)', compound.volume_of_distribution_l_kg ? `${compound.volume_of_distribution_l_kg} L/kg` : (compound.volume_of_distribution || '—')],
          ['Systemic Clearance (CL)', compound.clearance_l_h_kg ? `${compound.clearance_l_h_kg} L/h/kg` : (compound.clearance || '—')],
          ['Absorption Rate (ka)', compound.absorption_rate_ka ? `${compound.absorption_rate_ka} h⁻¹` : '—'],
          ['Plasma Protein Binding', compound.protein_binding_pct ? `${compound.protein_binding_pct}% (fu=${compound.fraction_unbound !== null && compound.fraction_unbound !== undefined ? compound.fraction_unbound : '—'})` : (compound.protein_binding ? `${compound.protein_binding}%` : '—')],
          ['Biopharmaceutics (BCS)', compound.bcs_class || 'Class II / Unclassified'],
          ['Therapeutic Precision', compound.therapeutic_index ? `TI: ${compound.therapeutic_index}x (MEC: ${compound.mec_ng_ml || '—'} ng/mL, MTC: ${compound.mtc_ng_ml || '—'} ng/mL)` : (compound.is_narrow_therapeutic_index ? '⚠️ Narrow Therapeutic Index (NTI)' : 'Standard Margin')],
        ];
        document.getElementById('pkOverviewGrid').innerHTML = pkRows.map(([lbl, val]) => `
          <div class="info-box" style="${lbl.includes('Precision') && val.includes('Narrow') ? 'border-color:var(--warning);background:rgba(245,158,11,0.08);' : ''}">
            <label>${lbl}</label>
            <div class="value">${safeText(val)}</div>
          </div>
        `).join('');

        // Populate Dosing Default into Simulator
        if (compound.dosing && compound.dosing.common) {
          document.getElementById('simDose').value = compound.dosing.common;
        }

        // CYP & Transporter Grid
        const formatObj = (obj) => {
          if (!obj || typeof obj !== 'object') return 'None recorded';
          const parts = [];
          if (obj.substrates && obj.substrates.length) parts.push(`Substrates: ${obj.substrates.join(', ')}`);
          if (obj.inhibitors && obj.inhibitors.length) parts.push(`Inhibits: ${obj.inhibitors.join(', ')}`);
          if (obj.inducers && obj.inducers.length) parts.push(`Induces: ${obj.inducers.join(', ')}`);
          return parts.length ? parts.join(' • ') : 'None active';
        };

        const cypRows = [
          ['CYP450 Metabolism', formatObj(compound.cyp_enzymes)],
          ['Membrane Transporters', formatObj(compound.transporters)],
          ['Phase II Conjugation', formatObj(compound.phase2_enzymes)],
        ];
        document.getElementById('cypTransporterGrid').innerHTML = cypRows.map(([lbl, val]) => `
          <div class="info-box" style="grid-column: span 1;">
            <label>${lbl}</label>
            <div class="value">${safeText(val)}</div>
          </div>
        `).join('');

        // Physicochemical Grid
        const chemRows = [
          ['Canonical InChIKey', compound.inchikey || '—'],
          ['LogP (Lipophilicity)', compound.logp !== null && compound.logp !== undefined ? compound.logp : '—'],
          ['Polar Surface (TPSA)', compound.tpsa !== null && compound.tpsa !== undefined ? `${compound.tpsa} Å²` : '—'],
          ['Molecular Weight', compound.molecular_weight !== null && compound.molecular_weight !== undefined ? `${compound.molecular_weight} g/mol` : '—'],
          ['Biological Pathways', (compound.pathway_details && compound.pathway_details.length) ? compound.pathway_details.map(p => p.name || p.id).join(', ') : '—'],
          ['Canonical SMILES', compound.smiles || '—'],
        ];
        document.getElementById('physicochemicalGrid').innerHTML = chemRows.map(([lbl, val]) => `
          <div class="info-box" style="${lbl.includes('SMILES') || lbl.includes('Pathways') ? 'grid-column: 1 / -1;' : ''}">
            <label>${lbl}</label>
            <div class="value" style="${lbl.includes('SMILES') || lbl.includes('InChI') ? 'font-family:\'JetBrains Mono\',monospace; font-size:0.75rem;' : ''}">
              ${safeText(val)}
            </div>
          </div>
        `).join('');

        // Run Initial PK/PD Simulation
        runPKPDSimulation();

        // Target Pills
        renderTargetPills(compound);
        renderList('compoundIndications', compound.indications);
        renderList('compoundWarnings', compound.warnings);
        renderList('compoundSideEffects', compound.side_effects);
        renderList('compoundInteractions', compound.interactions);

        // Deep-link to Knowledge Graph
        openInGraphBtn.href = `/graph?stack=${encodeURIComponent(compound.key || compound.name)}&focus=${encodeURIComponent(compound.key || compound.name)}`;

        compoundContent.style.display = 'block';
      }

      function renderTargetPills(compound) {
        const targetField = document.getElementById('compoundTargets');
        const targets = Array.isArray(compound.receptor_targets) ? compound.receptor_targets : [];

        if (!targets.length) {
          targetField.innerHTML = '<span class="pill">No primary targets recorded</span>';
          return;
        }

        targetField.innerHTML = targets.map((target, index) => {
          const label = typeof target === 'string' ? target : (target.name || target.gene || target.target || `Target ${index + 1}`);
          const action = typeof target === 'object' && target.action ? ` (${target.action})` : '';
          return `<button type="button" class="target-link" data-target-index="${index}">${label}${action}</button>`;
        }).join('');

        targetField.querySelectorAll('.target-link').forEach((button) => {
          button.addEventListener('click', () => {
            const index = Number(button.dataset.targetIndex || 0);
            const target = targets[index];
            openTargetModal(target);
          });
        });
      }

      function renderList(targetId, items) {
        const list = document.getElementById(targetId);
        const values = asList(items);
        if (!values.length) {
          list.innerHTML = '<li>None recorded.</li>';
          return;
        }
        list.innerHTML = values.map(value => `<li>${safeText(typeof value === 'string' ? value : JSON.stringify(value, null, 2))}</li>`).join('');
      }

      function openTargetModal(target) {
        const modalTitle = document.getElementById('targetModalTitle');
        const modalContent = document.getElementById('targetModalContent');

        if (!target) {
          targetInfoModal.classList.add('hidden');
          return;
        }

        const detail = typeof target === 'string' ? { name: target } : target;
        const rows = [
          ['Name', detail.name || detail.target || detail.label || 'Molecular Target'],
          ['Category / Class', detail.category || detail.type || detail.target_type || detail.receptor_family || detail.enzyme_family || '—'],
          ['Pharmacological Action', detail.action || detail.mechanism || '—'],
          ['Binding Affinity (Ki)', detail.affinity_ki ? `${detail.affinity_ki} nM` : '—'],
          ['Inhibitory Potency (IC50)', detail.inhibition_ic50 ? `${detail.inhibition_ic50} nM` : '—'],
          ['Organ System / Panel', detail.organ_system || detail.biomarker_panel || '—'],
          ['Biological Summary', detail.notes || detail.summary || detail.description || '—'],
        ];

        modalTitle.textContent = detail.name || detail.target || detail.label || 'Target Details';
        modalContent.innerHTML = rows.map(([label, value]) => `
          <div class="target-modal-row">
            <strong>${label}</strong>
            <div style="font-size:0.82rem; line-height:1.4; color:var(--text-primary);">${safeText(value)}</div>
          </div>
        `).join('');

        targetInfoModal.classList.remove('hidden');
      }

      targetModalClose.addEventListener('click', () => targetInfoModal.classList.add('hidden'));
      targetInfoModal.addEventListener('click', (event) => {
        if (event.target === targetInfoModal) targetInfoModal.classList.add('hidden');
      });

      // ==========================================================================
      // CYTOSCAPE HIGH-DPI PK/PD GRAPH RENDERING
      // ==========================================================================
      function filterGraphElements() {
        const mode = state.filterMode;
        if (mode === 'all') {
          return { nodes: state.rawNodes, edges: state.rawEdges };
        }

        let filteredNodes = [];
        if (mode === 'pd') {
          filteredNodes = state.rawNodes.filter(n => n.node_type === 'compound' || n.pk_pd_class === 'PD' || n.node_type === 'receptor' || n.node_type === 'signaling_pathway' || n.node_type === 'physiology' || n.node_type === 'biomarker' || n.node_type === 'phenotype');
        } else if (mode === 'pk') {
          filteredNodes = state.rawNodes.filter(n => n.node_type === 'compound' || n.pk_pd_class === 'PK' || n.node_type === 'enzyme' || n.node_type === 'transporter');
        } else if (mode === 'outcomes') {
          filteredNodes = state.rawNodes.filter(n => n.node_type === 'compound' || n.node_type === 'biomarker' || n.node_type === 'phenotype' || n.node_type === 'physiology');
        }

        const validIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges = state.rawEdges.filter(e => validIds.has(e.source) && validIds.has(e.target));

        return { nodes: filteredNodes, edges: filteredEdges };
      }

      function ensureCytoscape() {
        const container = document.getElementById('compoundGraph');
        if (!container || !window.cytoscape) return null;
        if (state.cy) return state.cy;

        const dpr = Math.max(window.devicePixelRatio || 1, 2);

        state.cy = window.cytoscape({
          container,
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
                'text-max-width': '110px',
                'color': '#f8fafc',
                
                // Crisp Badge Box Styling
                'text-background-opacity': 0.88,
                'text-background-color': '#070d19',
                'text-background-padding': '3px 5px',
                'text-background-shape': 'roundrectangle',
                'text-border-width': 1,
                'text-border-color': ele => colorForNode(ele.data('node_type')),
                'text-border-opacity': 0.6,
                'text-margin-y': 5,
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
                  if (type === 'biomarker' || type === 'physiology') return 'round-rectangle';
                  if (type === 'phenotype') return 'hexagon';
                  if (type === 'transporter') return 'round-tag';
                  return 'ellipse';
                },
                'shadow-blur': 14,
                'shadow-color': ele => colorForNode(ele.data('node_type')),
                'shadow-opacity': 0.45,
                'min-zoomed-font-size': 5,
                'transition-property': 'background-color, border-color, shadow-blur, opacity',
                'transition-duration': '0.2s',
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
                  if (dir === 'metabolic') return '#fb923c';
                  return '#00f2fe';
                },
                'target-arrow-color': edge => {
                  const dir = edge.data('direction_class');
                  const isBridge = edge.data('is_bridge');
                  if (isBridge) return '#c084fc';
                  if (dir === 'negative') return '#ff4b72';
                  if (dir === 'allosteric') return '#f59e0b';
                  if (dir === 'metabolic') return '#fb923c';
                  return '#00f2fe';
                },
                'line-style': edge => {
                  const dir = edge.data('direction_class');
                  if (dir === 'negative') return 'dashed';
                  if (edge.data('is_bridge')) return 'dotted';
                  return 'solid';
                },
                'width': 2.0,
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
                'text-rotation': 'autorotate',
                'min-zoomed-font-size': 7,
              }
            },
            {
              selector: 'node:selected, .highlighted',
              style: {
                'border-width': 4,
                'border-color': '#00f2fe',
                'shadow-blur': 25,
                'shadow-color': '#00f2fe',
                'shadow-opacity': 0.9,
              }
            },
            {
              selector: '.faded',
              style: {
                'opacity': 0.14,
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
          padding: 35,
        });

        // Hover effect
        state.cy.on('mouseover', 'node', event => {
          const selNode = event.target;
          const neighborhood = selNode.neighborhood().add(selNode);
          state.cy.elements().addClass('faded');
          neighborhood.removeClass('faded');
        });

        state.cy.on('mouseout', 'node', () => {
          state.cy.elements().removeClass('faded');
        });

        // Tap node to show quick card
        state.cy.on('tap', 'node', event => {
          const nodeId = event.target.id();
          const nodeData = event.target.data();
          state.selectedNode = nodeData;

          quickCardTitle.innerHTML = `<span style="color:${colorForNode(nodeData.node_type)};">●</span> ${nodeData.label || nodeId}`;
          quickCardSub.textContent = `Tier ${nodeData.tier !== undefined ? nodeData.tier : 1}: ${nodeData.tier_name || 'Target'} • ${(nodeData.node_type || 'Node').toUpperCase()} ${nodeData.pk_pd_class ? `[${nodeData.pk_pd_class}]` : ''}`;
          quickCard.classList.remove('hidden');
        });

        state.cy.on('tap', event => {
          if (event.target === state.cy) {
            state.selectedNode = null;
            quickCard.classList.add('hidden');
          }
        });

        return state.cy;
      }

      quickCardDetailBtn.addEventListener('click', () => {
        if (state.selectedNode) {
          openTargetModal(state.selectedNode);
        }
      });

      // CASCADE TIER FLOW LAYOUT
      function applyTierFlowLayout(cy) {
        const nodes = cy.nodes();
        if (!nodes.length) return;

        const tiers = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [] };
        nodes.forEach(node => {
          const tier = node.data('tier') !== undefined ? node.data('tier') : 1;
          const bucket = Math.min(5, Math.max(0, tier));
          tiers[bucket].push(node);
        });

        const columnWidth = 190;
        const startX = 40;
        const centerY = 260;

        cy.batch(() => {
          for (let t = 0; t <= 5; t++) {
            const group = tiers[t];
            if (!group || !group.length) continue;

            const colX = startX + (t * columnWidth);
            const totalInCol = group.length;
            const spacingY = Math.min(85, Math.max(50, 480 / Math.max(totalInCol, 1)));
            const colHeight = (totalInCol - 1) * spacingY;
            const topY = centerY - (colHeight / 2);

            group.forEach((node, idx) => {
              const jitterX = (idx % 2 === 1) ? 10 : -10;
              node.position({
                x: colX + jitterX,
                y: topY + (idx * spacingY)
              });
            });
          }
        });

        cy.fit(undefined, 35);
      }

      function renderGraph() {
        const cy = ensureCytoscape();
        if (!cy) return;

        const { nodes, edges } = filterGraphElements();

        cy.elements().remove();
        cy.add({
          nodes: nodes.map(n => ({
            data: {
              id: n.id,
              label: n.label || n.id,
              node_type: n.node_type || 'default',
              tier: n.tier,
              tier_name: n.tier_name,
              pk_pd_class: n.pk_pd_class,
              category: n.category,
              affinity_ki: n.affinity_ki,
              inhibition_ic50: n.inhibition_ic50,
              organ_system: n.organ_system,
              biomarker_panel: n.biomarker_panel,
            }
          })),
          edges: edges.map(e => ({
            data: {
              id: `${e.source}->${e.target}`,
              source: e.source,
              target: e.target,
              type: e.type || 'MODULATES',
              direction_class: e.direction_class || 'positive',
              is_bridge: e.is_bridge,
            }
          }))
        });

        const layoutName = layoutSelect.value || 'tier_flow';

        if (layoutName === 'tier_flow') {
          applyTierFlowLayout(cy);
        } else {
          const layoutOptions = {
            name: layoutName,
            padding: 35,
            animate: true,
            animationDuration: 300,
            nodeDimensionsIncludeLabels: true,
          };

          if (layoutName === 'concentric') {
            layoutOptions.concentric = ele => 6 - (ele.data('tier') || 1);
            layoutOptions.levelWidth = () => 1;
          } else if (layoutName === 'cose') {
            layoutOptions.nodeRepulsion = 3800;
            layoutOptions.idealEdgeLength = 80;
          } else if (layoutName === 'breadthfirst') {
            layoutOptions.directed = true;
            layoutOptions.spacingFactor = 1.3;
          }

          const layout = cy.layout(layoutOptions);
          layout.run();
          cy.fit(undefined, 35);
        }

        document.getElementById('graphSummary').textContent = `${nodes.length} connected entities • ${edges.length} interactions • ${layoutName.toUpperCase()}`;
      }

      // SIMULATE CASCADE SIGNAL FLOW
      btnSimulateFlow.addEventListener('click', () => {
        if (!state.cy || state.simulating) return;
        state.simulating = true;
        btnSimulateFlow.classList.add('active');
        btnSimulateFlow.textContent = '🌊 Propagating…';

        const cy = state.cy;
        let step = 0;
        cy.elements().removeClass('highlighted').addClass('faded');

        const interval = setInterval(() => {
          if (step > 5) {
            clearInterval(interval);
            setTimeout(() => {
              cy.elements().removeClass('faded').removeClass('highlighted');
              state.simulating = false;
              btnSimulateFlow.classList.remove('active');
              btnSimulateFlow.textContent = '⚡ Simulate Flow';
            }, 500);
            return;
          }

          const currentNodes = cy.nodes().filter(n => (n.data('tier') || 0) === step);
          const currentEdges = cy.edges().filter(e => (e.source().data('tier') || 0) === step - 1 || (e.source().data('tier') || 0) === step);

          currentNodes.removeClass('faded').addClass('highlighted');
          currentEdges.removeClass('faded').addClass('highlighted');
          step++;
        }, 350);
      });

      // FILTER BUTTONS
      filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          filterBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          state.filterMode = btn.dataset.filter;
          renderGraph();
        });
      });

      layoutSelect.addEventListener('change', () => renderGraph());
      document.getElementById('zoomIn').addEventListener('click', () => {
        if (!state.cy) return;
        state.cy.zoom(state.cy.zoom() + 0.25);
      });
      document.getElementById('zoomOut').addEventListener('click', () => {
        if (!state.cy) return;
        state.cy.zoom(state.cy.zoom() - 0.25);
      });
      document.getElementById('fitView').addEventListener('click', () => {
        if (state.cy) {
          state.cy.fit(undefined, 35);
          state.cy.center();
        }
      });

      function loadGraph(compound) {
        const key = compound.key || compound.name;
        if (!key) {
          document.getElementById('graphSummary').textContent = 'No graph data available.';
          return;
        }

        fetch(`/graph-data?stack=${encodeURIComponent(key)}&depth=5`, { cache: 'no-store' })
          .then((response) => response.json())
          .then((data) => {
            state.rawNodes = Array.isArray(data.nodes) ? data.nodes : [];
            state.rawEdges = Array.isArray(data.edges) ? data.edges : [];
            renderGraph();
          })
          .catch((error) => {
            console.error('Graph load error', error);
            document.getElementById('graphSummary').textContent = 'Unable to render graph for this compound.';
          });
      }

      // ==========================================
      // PK/PD CONTINUOUS SIMULATION ENGINE (CANVAS)
      // ==========================================
      let pkpdSimData = null;

      function runPKPDSimulation() {
        if (!state.compound) return;
        const dose = parseFloat(document.getElementById('simDose').value) || 100;
        const tau = parseFloat(document.getElementById('simTau').value) || 24;
        const route = document.getElementById('simRoute').value || 'oral';
        const regimen = document.getElementById('simRegimen').value || 'steady_state';
        const curveType = document.getElementById('simCurveType').value || 'pk';

        document.getElementById('simModeTag').textContent = regimen === 'steady_state' ? 'Bateman Steady-State' : 'Single-Dose Oral Curve';

        const payload = {
          compound_key: state.compound.key || compoundKey,
          dose_mg: dose,
          dosing_interval_h: tau,
          simulation_duration_h: tau * 2,
          route: route,
          steady_state: regimen === 'steady_state',
          body_weight_kg: 70.0,
          egfr_ml_min: 90.0
        };

        fetch('/api/pkpd/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
          pkpdSimData = data;
          renderSimStats(data);
          drawPKPDChart(data, curveType);
        })
        .catch(err => console.error('PK/PD simulation failure', err));
      }

      function renderSimStats(data) {
        const routeF = data.route_pk_details ? `${Math.round(data.route_pk_details.bioavailability_f * 100)}%` : '100%';
        const bypassPct = data.first_pass_bypass_pct !== undefined ? `${data.first_pass_bypass_pct}%` : '100%';
        const stats = [
          ['Cmax (Peak)', `${data.c_max_ng_ml || 0} ng/mL`],
          ['Tmax', `${data.t_max_h || 0} h`],
          ['Cmin (Trough)', `${data.c_min_trough_ng_ml || 0} ng/mL`],
          ['AUC (0-τ)', `${data.auc_0_tau_ng_h_ml || 0} ng·h/mL`],
          ['Route F', routeF],
          ['Portal Bypass', bypassPct],
          ['Effective t½', `${data.elimination_half_life_effective_h || 0} h`],
          ['In Window %', `${data.time_in_therapeutic_window_pct || 100}%`],
        ];

        document.getElementById('simStatsGrid').innerHTML = stats.map(([l, v]) => `
          <div class="info-box" style="padding:6px 8px; border-radius:6px; background:rgba(10,16,31,0.6);">
            <label style="font-size:0.65rem; color:var(--text-muted);">${l}</label>
            <div class="value" style="font-size:0.82rem; font-family:'JetBrains Mono'; color:#00f2fe;">${v}</div>
          </div>
        `).join('');

        const winStatus = document.getElementById('simWindowStatus');
        const winPct = data.time_in_therapeutic_window_pct !== undefined ? data.time_in_therapeutic_window_pct : 100;
        winStatus.textContent = `In Window: ${winPct}% (${(data.metabolites || []).length} active metabolites)`;
        winStatus.style.color = winPct > 80 ? 'var(--success)' : (winPct > 40 ? 'var(--warning)' : 'var(--danger)');
      }

      function drawPKPDChart(data, curveType) {
        const canvas = document.getElementById('pkpdCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const pad = { top: 18, right: 24, bottom: 28, left: 52 };
        const plotW = w - pad.left - pad.right;
        const plotH = h - pad.top - pad.bottom;

        ctx.clearRect(0, 0, w, h);

        const points = data.time_series || [];
        if (!points.length) {
          ctx.fillStyle = '#64748b';
          ctx.font = '12px Plus Jakarta Sans';
          ctx.fillText('No simulation curve points available.', w / 2 - 80, h / 2);
          return;
        }

        const maxT = points[points.length - 1].time_h || 24;
        let maxVal = 1;

        if (curveType === 'pd') {
          maxVal = 100;
        } else {
          const maxC = Math.max(...points.map(p => Math.max(p.c_plasma_ng_ml || 0, p.c_metabolite_ng_ml || 0)), data.mtc_threshold_ng_ml || 0);
          maxVal = maxC > 0 ? maxC * 1.15 : 10;
        }

        // Draw grid lines
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        for (let i = 0; i <= 4; i++) {
          const y = pad.top + (plotH * (i / 4));
          ctx.beginPath();
          ctx.moveTo(pad.left, y);
          ctx.lineTo(w - pad.right, y);
          ctx.stroke();

          const valLabel = curveType === 'pd' ? `${100 - i * 25}%` : `${Math.round(maxVal * (1 - i / 4))}`;
          ctx.fillStyle = '#64748b';
          ctx.font = '10px JetBrains Mono';
          ctx.textAlign = 'right';
          ctx.fillText(valLabel, pad.left - 6, y + 3);
        }

        for (let i = 0; i <= 6; i++) {
          const x = pad.left + (plotW * (i / 6));
          ctx.beginPath();
          ctx.moveTo(x, pad.top);
          ctx.lineTo(x, h - pad.bottom);
          ctx.stroke();

          const tLabel = `${Math.round(maxT * (i / 6))}h`;
          ctx.fillStyle = '#64748b';
          ctx.font = '10px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.fillText(tLabel, x, h - pad.bottom + 14);
        }

        // Draw MEC and MTC Thresholds for PK mode
        if (curveType === 'pk') {
          if (data.mtc_threshold_ng_ml && data.mtc_threshold_ng_ml < maxVal) {
            const mtcY = pad.top + plotH * (1 - data.mtc_threshold_ng_ml / maxVal);
            ctx.strokeStyle = '#ff4b72';
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(pad.left, mtcY);
            ctx.lineTo(w - pad.right, mtcY);
            ctx.stroke();
            ctx.fillStyle = '#ff4b72';
            ctx.font = '9px JetBrains Mono';
            ctx.textAlign = 'right';
            ctx.fillText(`MTC (${data.mtc_threshold_ng_ml})`, w - pad.right, mtcY - 3);
          }

          if (data.mec_threshold_ng_ml && data.mec_threshold_ng_ml < maxVal) {
            const mecY = pad.top + plotH * (1 - data.mec_threshold_ng_ml / maxVal);
            ctx.strokeStyle = '#f59e0b';
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(pad.left, mecY);
            ctx.lineTo(w - pad.right, mecY);
            ctx.stroke();
            ctx.fillStyle = '#f59e0b';
            ctx.font = '9px JetBrains Mono';
            ctx.textAlign = 'right';
            ctx.fillText(`MEC (${data.mec_threshold_ng_ml})`, w - pad.right, mecY - 3);
          }
        }

        ctx.setLineDash([]);

        // Draw Area Fill for Plasma C(t)
        const getX = t => pad.left + (t / maxT) * plotW;
        const getY = v => pad.top + plotH * (1 - v / maxVal);

        const plasmaGrad = ctx.createLinearGradient(0, pad.top, 0, h - pad.bottom);
        plasmaGrad.addColorStop(0, 'rgba(0, 242, 254, 0.28)');
        plasmaGrad.addColorStop(1, 'rgba(0, 242, 254, 0.01)');

        ctx.beginPath();
        ctx.moveTo(getX(points[0].time_h), getY(0));
        points.forEach(p => {
          const val = curveType === 'pd' ? p.effect_pct : p.c_plasma_ng_ml;
          ctx.lineTo(getX(p.time_h), getY(Math.max(0, val)));
        });
        ctx.lineTo(getX(points[points.length - 1].time_h), getY(0));
        ctx.fillStyle = plasmaGrad;
        ctx.fill();

        // Draw Main Curve Stroke
        ctx.beginPath();
        ctx.strokeStyle = curveType === 'pd' ? '#c084fc' : '#00f2fe';
        ctx.lineWidth = 2.5;
        points.forEach((p, idx) => {
          const val = curveType === 'pd' ? p.effect_pct : p.c_plasma_ng_ml;
          const px = getX(p.time_h);
          const py = getY(Math.max(0, val));
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();

        // Draw Free Unbound Curve if in PK mode
        if (curveType === 'pk') {
          ctx.beginPath();
          ctx.strokeStyle = '#10b981';
          ctx.lineWidth = 1.5;
          points.forEach((p, idx) => {
            const px = getX(p.time_h);
            const py = getY(Math.max(0, p.c_free_ng_ml));
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.stroke();

          // Draw Metabolite Curve if present
          if (points.some(p => p.c_metabolite_ng_ml && p.c_metabolite_ng_ml > 0)) {
            ctx.beginPath();
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 1.8;
            ctx.setLineDash([3, 3]);
            points.forEach((p, idx) => {
              const px = getX(p.time_h);
              const py = getY(Math.max(0, p.c_metabolite_ng_ml || 0));
              if (idx === 0) ctx.moveTo(px, py);
              else ctx.lineTo(px, py);
            });
            ctx.stroke();
            ctx.setLineDash([]);
          }
        }
      }

      // Simulator event listeners
      ['simDose', 'simTau', 'simRoute', 'simRegimen', 'simCurveType'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          el.addEventListener('input', runPKPDSimulation);
          el.addEventListener('change', runPKPDSimulation);
        }
      });

      // Deep Enrich Button Listener
      const btnDeepEnrich = document.getElementById('btnDeepEnrich');
      if (btnDeepEnrich) {
        btnDeepEnrich.addEventListener('click', () => {
          btnDeepEnrich.textContent = '⏳ Enriching PubChem/ChEMBL/Reactome…';
          btnDeepEnrich.style.opacity = '0.7';

          fetch(`/api/compounds/${encodeURIComponent(compoundKey)}/enrich-full`, { method: 'POST' })
            .then(res => res.json())
            .then(updated => {
              btnDeepEnrich.textContent = '✅ Enriched & Saved';
              btnDeepEnrich.style.opacity = '1';
              renderCompound(updated);
              setTimeout(() => {
                btnDeepEnrich.textContent = '⚡ Full PK/PD Enrich';
              }, 2500);
            })
            .catch(err => {
              console.error('Enrichment failed', err);
              btnDeepEnrich.textContent = '❌ Enrichment Error';
              setTimeout(() => {
                btnDeepEnrich.textContent = '⚡ Full PK/PD Enrich';
                btnDeepEnrich.style.opacity = '1';
              }, 2500);
            });
        });
      }

      // Mobile menu toggle handling
      const compoundMobileMenuBtn = document.getElementById('mobile-menu-toggle');
      const compoundNavLinks = document.getElementById('nav-links');
      if (compoundMobileMenuBtn && compoundNavLinks) {
        compoundMobileMenuBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          compoundNavLinks.classList.toggle('open');
        });

        document.addEventListener('click', (e) => {
          if (!compoundNavLinks.contains(e.target) && !compoundMobileMenuBtn.contains(e.target)) {
            compoundNavLinks.classList.remove('open');
          }
        });
      }

      // EVIDENCE & CITATION DOSSIER RENDERER
      function loadEvidenceDossier(cKey) {
        const studiesGrid = document.getElementById('landmarkStudiesGrid');
        const timelineTrack = document.getElementById('timelineTrack');
        const controversiesGrid = document.getElementById('controversiesGrid');
        const evidenceCountTag = document.getElementById('evidenceCountTag');

        fetch(`/catalog/${encodeURIComponent(cKey)}/evidence-dossier`)
          .then(res => res.json())
          .then(dossier => {
            const citations = dossier.citations || [];
            const trials = dossier.clinical_trials || [];
            const timeline = dossier.chronological_timeline || [];
            const conflicts = dossier.conflicts || [];

            if (evidenceCountTag) {
              evidenceCountTag.textContent = `${citations.length + trials.length} Verified Evidence Records`;
            }

            // 1. Render Landmark Studies & Trials
            if (studiesGrid) {
              if (citations.length === 0 && trials.length === 0) {
                studiesGrid.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted);">No direct landmark citations cataloged yet. Live literature extraction active.</div>`;
              } else {
                let html = '';
                citations.forEach(c => {
                  const tier = c.evidence_tier || 'Clinical Study';
                  const tierClass = tier.toLowerCase().includes('rct') ? 'rct' : (tier.toLowerCase().includes('meta') ? 'meta' : '');
                  const pmid = c.pmid ? `<a class="study-link" href="https://pubmed.ncbi.nlm.nih.gov/${c.pmid}/" target="_blank" rel="noopener">PMID: ${c.pmid} ↗</a>` : '';
                  const doi = c.doi ? `<a class="study-link" href="https://doi.org/${c.doi}" target="_blank" rel="noopener">DOI ↗</a>` : '';
                  const n = c.sample_size ? `<span>Sample N = ${c.sample_size.toLocaleString()}</span>` : '';
                  const auth = Array.isArray(c.authors) ? c.authors.slice(0, 3).join(', ') : (c.authors || '');

                  html += `
                    <div class="study-card">
                      <div class="study-header">
                        <div class="study-title">${c.title || 'Biomedical Investigation'}</div>
                        <span class="study-badge ${tierClass}">${tier}</span>
                      </div>
                      <div class="study-meta">
                        <span>📖 ${c.journal || 'Peer-Reviewed Journal'} (${c.pub_year || 'N/A'})</span>
                        ${auth ? `<span>👥 ${auth}</span>` : ''}
                        ${n}
                      </div>
                      ${c.key_findings ? `<div class="study-finding">💡 ${c.key_findings}</div>` : ''}
                      <div class="study-links">
                        ${pmid}
                        ${doi}
                      </div>
                    </div>
                  `;
                });

                trials.forEach(t => {
                  html += `
                    <div class="study-card" style="border-left: 3px solid #38bdf8;">
                      <div class="study-header">
                        <div class="study-title">${t.title}</div>
                        <span class="study-badge rct">${t.phase || 'Clinical Trial'} [${t.status || 'COMPLETED'}]</span>
                      </div>
                      <div class="study-meta">
                        <span>🏛️ ${t.sponsor || 'Clinical Investigation'}</span>
                        ${t.enrollment ? `<span>👥 Enrollment N = ${t.enrollment.toLocaleString()}</span>` : ''}
                        ${t.completion_year ? `<span>📅 Year: ${t.completion_year}</span>` : ''}
                      </div>
                      <div class="study-links">
                        <a class="study-link" href="https://clinicaltrials.gov/study/${t.nct_id}" target="_blank" rel="noopener">ClinicalTrials.gov: ${t.nct_id} ↗</a>
                      </div>
                    </div>
                  `;
                });
                studiesGrid.innerHTML = html;
              }
            }

            // 2. Render Chronological Timeline
            if (timelineTrack) {
              if (timeline.length === 0) {
                timelineTrack.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted);">No timeline milestones mapped.</div>`;
              } else {
                let tHtml = '';
                timeline.forEach(m => {
                  tHtml += `
                    <div class="timeline-item">
                      <div class="timeline-node-dot"></div>
                      <div class="timeline-year">${m.year || 'Discovery'} &bull; ${m.tier || 'Milestone'}</div>
                      <div class="timeline-text"><strong>${m.title || m.milestone}</strong></div>
                      ${m.pmid ? `<div style="margin-top:3px;"><a class="study-link" href="https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/" target="_blank" rel="noopener" style="font-size:0.65rem;">PMID: ${m.pmid} ↗</a></div>` : ''}
                    </div>
                  `;
                });
                timelineTrack.innerHTML = tHtml;
              }
            }

            // 3. Render Controversies Radar
            if (controversiesGrid) {
              if (conflicts.length === 0) {
                controversiesGrid.innerHTML = `
                  <div style="font-size:0.8rem; color:var(--success); display:flex; align-items:center; gap:6px;">
                    <span>✅</span> High scientific consensus observed across published assays & human clinical trials.
                  </div>
                `;
              } else {
                let cHtml = '';
                conflicts.forEach(cf => {
                  const sc = Math.round((cf.consensus_score || 0.6) * 100);
                  cHtml += `
                    <div class="controversy-card">
                      <div class="controversy-title">
                        <span>⚡ ${cf.topic || 'Pharmacological Debate'}</span>
                        <span style="font-size:0.7rem; font-weight:600; color:var(--text-muted); margin-left:auto;">Consensus: ${sc}%</span>
                      </div>
                      <div class="consensus-bar-wrap">
                        <div class="consensus-bar-fill" style="width: ${sc}%;"></div>
                      </div>
                      <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:6px;">
                        <div>🟢 <strong>Supported Observation</strong>: ${cf.positive_claim || 'Documented efficacy.'}</div>
                        <div style="margin-top:4px;">🔴 <strong>Opposing / Limiting Finding</strong>: ${cf.opposing_claim || 'Context-dependent attenuation.'}</div>
                      </div>
                      ${cf.divergence_rationale ? `<div style="font-size:0.72rem; color:#f59e0b; margin-top:6px; font-style:italic;">🔍 Rationale: ${cf.divergence_rationale}</div>` : ''}
                    </div>
                  `;
                });
                controversiesGrid.innerHTML = cHtml;
              }
            }
          })
          .catch(err => {
            console.debug('Failed to load evidence dossier', err);
          });
      }

      // INITIAL FETCH
      fetch(`/catalog/${encodeURIComponent(compoundKey)}`)
        .then((response) => {
          if (!response.ok) throw new Error('Compound not found');
          return response.json();
        })
        .then((compound) => {
          compoundLoading.style.display = 'none';
          renderCompound(compound);
          loadGraph(compound);
          loadEvidenceDossier(compoundKey);
        })
        .catch((error) => {
          compoundLoading.style.display = 'none';
          compoundError.style.display = 'block';
          compoundError.textContent = 'Unable to load this compound. Please return to the catalog and select a valid entry.';
          console.error('Failed to fetch compound details', error);
        });