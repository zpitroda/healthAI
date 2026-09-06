      let _evaluateSeq = 0;
      let _evaluateAbortController = null;

      // EVALUATE STACK WITH BACKEND
      async function evaluateStack() {
        const currentSeq = ++_evaluateSeq;

        if (_evaluateAbortController) {
          try { _evaluateAbortController.abort(); } catch (e) {}
          _evaluateAbortController = null;
        }

        if (!state.stack.length) {
          updateDashboardEmpty();
          const loader = document.getElementById('global-loading-bar');
          if (loader) loader.classList.remove('active');
          const evalIndicator = document.getElementById('stack-eval-indicator');
          if (evalIndicator) evalIndicator.style.display = 'none';
          return;
        }
        
        const loader = document.getElementById('global-loading-bar');
        if (loader) loader.classList.add('active');
        const evalIndicator = document.getElementById('stack-eval-indicator');
        if (evalIndicator) evalIndicator.style.display = 'inline-flex';

        _evaluateAbortController = new AbortController();
        const signal = _evaluateAbortController.signal;

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
            signal,
          });
          if (currentSeq !== _evaluateSeq) return;
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
          }
          const data = await res.json();
          if (currentSeq !== _evaluateSeq) return;
          state.analysis = data;

          if (data.compounds && Array.isArray(data.compounds)) {
            let updatedStack = false;
            data.compounds.forEach(c => {
              if (c.key) {
                _clientCatalogCache[c.key] = c;
                if (c.key.includes('_')) _clientCatalogCache[c.key.replace(/_/g, '-')] = c;
              }
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
                if (c.key && item.key !== c.key && matchCompoundItem([item], c.key)) {
                  item.key = c.key;
                  updatedStack = true;
                }
              }
            });
            if (updatedStack) {
              if (stackCountBadge) {
                if (window._pendingLoadingCompounds && window._pendingLoadingCompounds.size > 0) {
                  stackCountBadge.textContent = `${state.stack.length} items (${window._pendingLoadingCompounds.size} loading)`;
                } else {
                  stackCountBadge.textContent = `${state.stack.length} items`;
                }
              }
              if (statCompounds) statCompounds.textContent = state.stack.length;
              renderStackList();
            }
          }
          renderDashboard(data);
          syncCopilotStackTags();
          if (typeof syncGraphData === 'function') {
            syncGraphData(state.activeTab === 'graph-tab');
          }
        } catch (err) {
          if (err && err.name === 'AbortError') return;
          if (currentSeq !== _evaluateSeq) return;
          console.error('Evaluation error:', err);
          showToast(`Evaluation error: ${err.message || 'Check inputs'}`, 'alert-triangle');
        } finally {
          if (currentSeq === _evaluateSeq) {
            const loader = document.getElementById('global-loading-bar');
            if (loader) loader.classList.remove('active');
            const evalIndicator = document.getElementById('stack-eval-indicator');
            if (evalIndicator) evalIndicator.style.display = 'none';
          }
        }
      }

      function updateDashboardEmpty() {
        state.analysis = null;
        const evalIndicator = document.getElementById('stack-eval-indicator');
        if (evalIndicator) evalIndicator.style.display = 'none';
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
        
        const matrixBadge = document.getElementById('tab-matrix-badge');
        const conflictsBadge = document.getElementById('tab-conflicts-badge');
        if (matrixBadge) matrixBadge.style.display = 'none';
        if (conflictsBadge) conflictsBadge.style.display = 'none';

        const balanceWrap = document.getElementById('balance-dashboard-wrap');
        if (balanceWrap) {
          balanceWrap.innerHTML = '<div class="stack-empty-card">Add compounds to evaluate full-stack physiological axes, dose counterbalances, and net biological equilibrium.</div>';
        }
        if (typeof syncGraphData === 'function') {
          syncGraphData(state.activeTab === 'graph-tab');
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
            matrixBadge.style.display = 'inline-flex';
            matrixBadge.style.alignItems = 'center';
            matrixBadge.style.gap = '3px';
            matrixBadge.innerHTML = `${data.conflict_count || 0}${iconSvg('zap', { class: 'icon-xs' })} ${data.synergy_count || 0}${iconSvg('sparkles', { class: 'icon-xs' })}`;
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
        
        const isOutOfRangeOrTail = (a) => {
          if (a.priority_tier <= 2 || !a.in_safe_range) return true;
          if (a.has_tail_alert || a.tail_elevation_risk || a.tail_suppression_risk) return true;
          const dist = a.distribution || {};
          const p5 = parseFloat(dist.p5);
          const p95 = parseFloat(dist.p95);
          const safeLower = parseFloat(a.safe_lower);
          const safeUpper = parseFloat(a.safe_upper);
          if (!isNaN(p95) && !isNaN(safeUpper) && p95 > safeUpper) return true;
          if (!isNaN(p5) && !isNaN(safeLower) && p5 < safeLower) return true;
          return false;
        };

        const outOfRangeCount = axes.filter(isOutOfRangeOrTail).length;
        const mitigatedCount = axes.filter(a => a.priority_tier === 3).length;
        const activeShiftCount = axes.filter(a => a.priority_tier === 4).length;
        const baselineCount = axes.filter(a => a.priority_tier === 5).length;

        let filteredAxes = axes.filter(a => {
          if (currentFilter === 'out-of-range') return isOutOfRangeOrTail(a);
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
          const height = 100;
          const baselineY = 74;
          const peakY = 16;
          const chartHeight = baselineY - peakY;

          const toX = (v) => Math.max(6, Math.min(width - 6, ((v - xMin) / rangeX) * width));

          const stepCount = 60;
          const points = [];

                if (safeEst > 0 && safeP5 > 0) {
            // Exact Log-Normal Probability Density Function normalized to chart height
            const muLog = Math.log(Math.max(0.0001, safeP50));
            const sigmaLog = Math.max(0.01, (Math.log(Math.max(0.0001, safeP95)) - Math.log(Math.max(0.0001, safeP5))) / 3.29);
            const xMode = Math.exp(muLog - sigmaLog * sigmaLog);
            const modeDensity = (1 / (Math.max(0.0001, xMode) * sigmaLog)) * Math.exp(-0.5 * sigmaLog * sigmaLog);

            let maxFoundDensity = modeDensity;
            const tempPoints = [];
            for (let i = 0; i <= stepCount; i++) {
              const vx = xMin + (i / stepCount) * rangeX;
              if (vx <= 0) {
                tempPoints.push({ vx, rawDensity: 0 });
                continue;
              }
              const z = (Math.log(vx) - muLog) / sigmaLog;
              const rawDensity = (1 / (vx * sigmaLog)) * Math.exp(-0.5 * z * z);
              if (rawDensity > maxFoundDensity) maxFoundDensity = rawDensity;
              tempPoints.push({ vx, rawDensity });
            }

            const peakNorm = Math.max(0.000001, maxFoundDensity);
            for (const pt of tempPoints) {
              const normDensity = Math.max(0, Math.min(1.0, pt.rawDensity / peakNorm));
              const px = toX(pt.vx);
              const py = baselineY - (normDensity * chartHeight);
              points.push({ x: px, y: py, val: pt.vx });
            }
          } else {
            // Gaussian bell curve fallback for zero-centered or negative deltas
            const mu = safeP50;
            const sigma = Math.max(0.001, (safeP95 - safeP5) / 3.29);
            for (let i = 0; i <= stepCount; i++) {
              const vx = xMin + (i / stepCount) * rangeX;
              const z = (vx - mu) / sigma;
              const density = Math.exp(-0.5 * z * z);
              const px = toX(vx);
              const py = baselineY - (density * chartHeight);
              points.push({ x: px, y: py, val: vx });
            }
          }

          const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

          const safeLeftX = toX(safeLower);
          const safeRightX = toX(safeUpper);
          const safeWidthX = Math.max(2, safeRightX - safeLeftX);

          const p5X = toX(safeP5);
          const p95X = toX(safeP95);
          const p50X = toX(safeP50);
          const basePointX = toX(safeBase);

          // Anti-collision label staggered Y positions
          const isBaseNearP5 = Math.abs(basePointX - p5X) < 28;
          const isBaseNearP95 = Math.abs(basePointX - p95X) < 28;
          const baseLabelY = (isBaseNearP5 || isBaseNearP95) ? baselineY + 22 : baselineY + 12;
          const p5LabelY = baselineY + 12;
          const p95LabelY = baselineY + 12;

          const curveAreaD = pathD + ` L ${points[points.length - 1].x.toFixed(1)} ${baselineY} L ${points[0].x.toFixed(1)} ${baselineY} Z`;

          let beginnerSummaryText = '';
          let beginnerBadgeClass = 'safe';
          if (safeEst > safeUpper) {
            if (axis.status === 'OPTIMIZED_ANABOLIC') {
              beginnerSummaryText = `${iconSvg('zap', { class: 'icon-xs' })} <strong>Supraphysiological Target:</strong> Expected median at ${safeEst} ${unit} exceeds baseline physiological range [${safeLower}–${safeUpper} ${unit}], targeted for anabolic/therapeutic response. 90% prediction band: ${safeP5}–${safeP95} ${unit}.`;
              beginnerBadgeClass = 'info';
            } else {
              beginnerSummaryText = `${iconSvg('alert-triangle', { class: 'icon-xs' })} <strong>Clinical Elevation:</strong> Expected median (${safeEst} ${unit}) exceeds safe target limit (${safeUpper} ${unit}). 90% prediction band: ${safeP5}–${safeP95} ${unit}.`;
              beginnerBadgeClass = 'warning';
            }
          } else if (safeEst < safeLower) {
            beginnerSummaryText = `${iconSvg('alert-triangle', { class: 'icon-xs' })} <strong>Clinical Suppression:</strong> Expected median (${safeEst} ${unit}) drops below safe lower threshold (${safeLower} ${unit}). 90% prediction band: ${safeP5}–${safeP95} ${unit}.`;
            beginnerBadgeClass = 'warning';
          } else if (safeP95 > safeUpper) {
            beginnerSummaryText = `${iconSvg('alert-triangle', { class: 'icon-xs' })} <strong>Tail Elevation Risk:</strong> Median (${safeEst} ${unit}) is within limits, but inter-individual variance indicates upper 95th percentile (${safeP95} ${unit}) crosses safety limit (${safeUpper} ${unit}).`;
            beginnerBadgeClass = 'warning';
          } else if (safeP5 < safeLower) {
            beginnerSummaryText = `${iconSvg('alert-triangle', { class: 'icon-xs' })} <strong>Tail Suppression Risk:</strong> Median (${safeEst} ${unit}) is within limits, but inter-individual variance indicates lower 5th percentile (${safeP5} ${unit}) drops below physiological floor (${safeLower} ${unit}).`;
            beginnerBadgeClass = 'warning';
          } else {
            beginnerSummaryText = `${iconSvg('check', { class: 'icon-xs' })} <strong>Safe Target Zone:</strong> 90% of projected outcomes (${safeP5}–${safeP95} ${unit}) remain within healthy limits [${safeLower}–${safeUpper} ${unit}]. Expected median: ${safeEst} ${unit}.`;
            beginnerBadgeClass = 'safe';
          }

          const precisionBadge = axis.is_lab_calibrated
            ? `<span style="font-size: 0.62rem; color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 1px 6px; border-radius: 4px; font-weight: 700; display: inline-flex; align-items: center; gap: 3px;">${iconSvg('check', { class: 'icon-xs' })} Lab-Calibrated Precision</span>`
            : `<span style="font-size: 0.62rem; color: #94a3b8; background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.14); padding: 1px 6px; border-radius: 4px; font-weight: 600;" title="Population prior estimate. Add lab bloodwork to personalize precision.">○ Population Prior</span>`;

          const chartId = `dist-chart-${cardIdx}-${Math.floor(Math.random() * 10000)}`;

          return `
            <div class="dist-chart-wrapper" style="background: rgba(5, 11, 24, 0.7); border: 1px solid rgba(0, 242, 254, 0.18); border-radius: 10px; padding: 12px; margin: 10px 0;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 4px;">
                <span style="font-size: 0.74rem; font-weight: 700; color: #00f2fe; display: flex; align-items: center; gap: 6px;">
                  <span>${iconSvg('trending-up', { class: 'icon-xs icon-cyan' })} Projected Outcome Probability Distribution</span>
                  ${precisionBadge}
                </span>
                <button 
                  type="button" 
                  class="power-user-toggle-btn"
                  onclick="const el=document.getElementById('${chartId}-stats'); el.style.display=(el.style.display==='none'||!el.style.display)?'block':'none';"
                  style="background: rgba(0, 242, 254, 0.12); border: 1px solid rgba(0, 242, 254, 0.35); color: #00f2fe; font-size: 0.68rem; font-weight: 700; padding: 3px 9px; border-radius: 5px; cursor: pointer; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 4px;"
                >
                  ${isPower ? 'Hide Stats' : `<span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('bar-chart-2', { class: 'icon-xs' })} Power Stats</span>`}
                </button>
              </div>

              <div style="font-size: 0.75rem; line-height: 1.4; color: ${beginnerBadgeClass === 'warning' ? '#f87171' : (beginnerBadgeClass === 'safe' ? '#34d399' : (beginnerBadgeClass === 'info' ? '#38bdf8' : '#94a3b8'))}; background: ${beginnerBadgeClass === 'warning' ? 'rgba(239,68,68,0.12)' : (beginnerBadgeClass === 'safe' ? 'rgba(16,185,129,0.12)' : (beginnerBadgeClass === 'info' ? 'rgba(56,189,248,0.12)' : 'rgba(148,163,184,0.12)'))}; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid ${beginnerBadgeClass === 'warning' ? 'rgba(239,68,68,0.3)' : (beginnerBadgeClass === 'safe' ? 'rgba(16,185,129,0.3)' : (beginnerBadgeClass === 'info' ? 'rgba(56,189,248,0.3)' : 'rgba(148,163,184,0.3)'))}; font-weight: 600; display: flex; align-items: center; gap: 6px;">
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
                  
                  <!-- Safe range boundary numbers on top of dashed lines -->
                  <text x="${safeLeftX.toFixed(1)}" y="${peakY - 3}" fill="#10b981" font-size="6.8" font-weight="700" text-anchor="middle" opacity="0.9">${safeLower}</text>
                  <text x="${safeRightX.toFixed(1)}" y="${peakY - 3}" fill="#10b981" font-size="6.8" font-weight="700" text-anchor="middle" opacity="0.9">${safeUpper}</text>
                  <text x="${((safeLeftX + safeRightX) / 2).toFixed(1)}" y="${peakY + 11}" fill="#34d399" font-size="6.8" font-weight="800" text-anchor="middle" letter-spacing="0.05em" opacity="0.75">TARGET ZONE</text>

                  <path d="${curveAreaD}" fill="url(#${chartId}-curve-grad)" />
                  <path d="${pathD}" fill="none" stroke="#00f2fe" stroke-width="2.4" stroke-linecap="round" />

                  <!-- Baseline point and label with collision avoidance -->
                  <line x1="${basePointX.toFixed(1)}" y1="${peakY + 4}" x2="${basePointX.toFixed(1)}" y2="${baselineY}" stroke="#94a3b8" stroke-dasharray="2,2" stroke-width="1.2" />
                  <circle cx="${basePointX.toFixed(1)}" cy="${baselineY}" r="2.8" fill="#94a3b8" />
                  <text x="${basePointX.toFixed(1)}" y="${baseLabelY}" fill="#94a3b8" font-size="7.2" font-weight="600" text-anchor="middle">Base: ${safeBase}</text>

                  <!-- Estimate peak point and label -->
                  <line x1="${p50X.toFixed(1)}" y1="${peakY}" x2="${p50X.toFixed(1)}" y2="${baselineY}" stroke="${statusColor}" stroke-width="2" />
                  <circle cx="${p50X.toFixed(1)}" cy="${peakY + 3}" r="4" fill="${statusColor}" stroke="#0b1324" stroke-width="1.5" />
                  <text x="${p50X.toFixed(1)}" y="${peakY - 4}" fill="${statusColor}" font-size="8.5" font-weight="800" text-anchor="middle">Est: ${safeEst} ${unit}</text>

                  <!-- p5 and p95 percentile indicators -->
                  <line x1="${p5X.toFixed(1)}" y1="${baselineY - 8}" x2="${p5X.toFixed(1)}" y2="${baselineY}" stroke="#00f2fe" stroke-width="1.5" />
                  <text x="${p5X.toFixed(1)}" y="${p5LabelY}" fill="#00f2fe" font-size="7.2" font-weight="700" text-anchor="middle">p5: ${safeP5}</text>

                  <line x1="${p95X.toFixed(1)}" y1="${baselineY - 8}" x2="${p95X.toFixed(1)}" y2="${baselineY}" stroke="#00f2fe" stroke-width="1.5" />
                  <text x="${p95X.toFixed(1)}" y="${p95LabelY}" fill="#00f2fe" font-size="7.2" font-weight="700" text-anchor="middle">p95: ${safeP95}</text>
                </svg>
              </div>

              <div id="${chartId}-stats" style="display: ${isPower ? 'block' : 'none'}; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <div style="font-size: 0.7rem; font-weight: 800; text-transform: uppercase; color: #00f2fe; margin-bottom: 6px; letter-spacing: 0.04em; display: flex; align-items: center; justify-content: space-between;">
                  <span style="display: inline-flex; align-items: center; gap: 4px;">${iconSvg('bar-chart-2', { class: 'icon-xs' })} Log-Normal Inter-Individual Variance Model (90% Prediction Interval)</span>
                  <span style="font-size: 0.62rem; color: var(--text-muted); font-weight: 600;">CV: ${(safeStdDev / (safeMean || 1) * 100).toFixed(1)}%</span>
                </div>
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

                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary); background: rgba(255,255,255,0.03); padding: 5px 8px; border-radius: 5px; flex-wrap: wrap; gap: 4px;">
                  <span>Expected Mean (&mu;): <strong>${safeMean} ${unit}</strong></span>
                  <span>Median: <strong>${safeP50} ${unit}</strong></span>
                  <span>Std Dev (&sigma;): <strong>${safeStdDev.toFixed(2)} ${unit}</strong></span>
                  <span>90% Prediction Band: <strong>${Math.abs(safeP95 - safeP5).toFixed(1)} ${unit}</strong></span>
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
            let tierTagHtml = `<span class="axis-tier-tag tier-baseline" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs' })} Stable Baseline</span>`;

            if (tier === 1) {
              cardTierClass = 'card-tier-critical';
              tierTagHtml = `<span class="axis-tier-tag tier-critical" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('alert-triangle', { class: 'icon-xs' })} Critical Strain</span>`;
            } else if (tier === 2) {
              cardTierClass = 'card-tier-warning';
              tierTagHtml = `<span class="axis-tier-tag tier-warning" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('zap', { class: 'icon-xs' })} Moderate Alert</span>`;
            } else if (tier === 3) {
              cardTierClass = 'card-tier-mitigated';
              tierTagHtml = `<span class="axis-tier-tag tier-mitigated" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('shield-check', { class: 'icon-xs' })} Counterbalanced</span>`;
            } else if (tier === 4) {
              cardTierClass = 'card-tier-active';
              tierTagHtml = `<span class="axis-tier-tag tier-active" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('bar-chart-2', { class: 'icon-xs' })} Active Shift (${axis.percent_shift ? `${axis.percent_shift}%` : 'Shifted'})</span>`;
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
                      p5–p95: ${escapeHtml(p5p95Str)}
                    </span>
                    <div class="axis-val-delta" style="color: ${(axis.estimated_value || 0) >= (axis.baseline || 0) ? '#f87171' : '#34d399'}; margin-top:2px;">
                      Net: ${escapeHtml(axis.net_delta_str || '')}
                    </div>
                  </div>
                </div>

                ${axis.target_tissue || (axis.biometric_modifiers_applied && axis.biometric_modifiers_applied.length) ? `
                  <div style="display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0;">
                    ${axis.target_tissue ? `<span style="font-size: 0.72rem; color: #a7f3d0; background: rgba(16, 185, 129, 0.12); padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.25); display:inline-flex; align-items:center; gap:3px;">${iconSvg('target', { class: 'icon-xs' })} Target: <strong>${escapeHtml(axis.target_tissue)}</strong></span>` : ''}
                    ${(axis.biometric_modifiers_applied || []).map(m => `<span style="font-size: 0.7rem; color: #fde047; background: rgba(245, 158, 11, 0.15); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.3); display:inline-flex; align-items:center; gap:3px;">${iconSvg('sliders', { class: 'icon-xs' })} ${escapeHtml(m)}</span>`).join('')}
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
                  <span style="display:inline-flex; align-items:center; gap:6px;">${iconSvg('shield-check', { class: 'icon-sm icon-emerald' })} Active Stack Mitigations & Counterbalances</span>
                  <span class="panel-title-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">${mitigations.length} Active</span>
                </span>
              </div>
              ${mitigations.map(m => `
                <div class="mitigation-card">
                  <div class="mitigation-card-header">
                    <span class="mitigation-title" style="display:inline-flex; align-items:center; gap:5px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} ${escapeHtml(m.title)}</span>
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
                  <span style="display:inline-flex; align-items:center; gap:6px;">${iconSvg('alert-triangle', { class: 'icon-sm icon-rose' })} Uncompensated Axis Deviations</span>
                  <span class="panel-title-badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171;">${uncompensated.length} Warning</span>
                </span>
              </div>
              ${uncompensated.map(u => `
                <div class="uncompensated-card">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 800; font-size: 0.96rem; color: #f87171; display:inline-flex; align-items:center; gap:5px;">${iconSvg('alert-triangle', { class: 'icon-xs icon-rose' })} ${escapeHtml(u.title)}</span>
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
                  ${iconSvg('clock', { class: 'icon-sm icon-cyan' })} Equilibrium Timeline Horizon
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
                  <button class="axis-filter-btn filter-critical ${currentFilter === 'out-of-range' ? 'active' : ''}" onclick="setAxesFilter('out-of-range')" style="display:inline-flex; align-items:center; gap:4px;">
                    ${iconSvg('alert-triangle', { class: 'icon-xs' })} Out of Range / Tail Alerts (${outOfRangeCount})
                  </button>
                ` : ''}
                ${mitigatedCount > 0 ? `
                  <button class="axis-filter-btn filter-mitigated ${currentFilter === 'counterbalanced' ? 'active' : ''}" onclick="setAxesFilter('counterbalanced')" style="display:inline-flex; align-items:center; gap:4px;">
                    ${iconSvg('shield-check', { class: 'icon-xs' })} Counterbalanced (${mitigatedCount})
                  </button>
                ` : ''}
                ${activeShiftCount > 0 ? `
                  <button class="axis-filter-btn ${currentFilter === 'active-shifts' ? 'active' : ''}" onclick="setAxesFilter('active-shifts')" style="display:inline-flex; align-items:center; gap:4px;">
                    ${iconSvg('bar-chart-2', { class: 'icon-xs' })} Active Shifts (${activeShiftCount})
                  </button>
                ` : ''}
                <button class="axis-filter-btn ${currentFilter === 'baseline' ? 'active' : ''}" onclick="setAxesFilter('baseline')" style="display:inline-flex; align-items:center; gap:4px;">
                  ${iconSvg('check', { class: 'icon-xs' })} Baseline (${baselineCount})
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
            let icon = iconSvg('check', { class: 'icon-xs' });
            let label = 'Neutral';

            if (cell.is_self) {
              cellClass = 'cell-self';
              icon = iconSvg('circle-dot', { class: 'icon-xs' });
              label = 'Self';
            } else if (cell.is_mitigated_by_stack) {
              cellClass = 'cell-mitigated';
              icon = iconSvg('shield-check', { class: 'icon-xs' });
              label = 'Mitigated';
            } else if (cell.severity === 'SYNERGISTIC') {
              cellClass = 'cell-synergy';
              icon = iconSvg('sparkles', { class: 'icon-xs' });
              label = 'Synergy';
            } else if (cell.severity === 'HIGH_RISK' || cell.severity === 'SEVERE_CONTRAINDICATION') {
              cellClass = 'cell-high';
              icon = iconSvg('alert-triangle', { class: 'icon-xs' });
              label = cell.ddi_auc_ratio ? `+${Math.round((cell.ddi_auc_ratio - 1) * 100)}% AUC` : 'High Risk';
            } else if (cell.severity === 'MODERATE_RISK') {
              cellClass = 'cell-moderate';
              icon = iconSvg('zap', { class: 'icon-xs' });
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
                ${item.is_mitigated_by_stack ? `<span class="panel-title-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; display:inline-flex; align-items:center; gap:4px;">${iconSvg('shield-check', { class: 'icon-xs' })} Mitigated by Stack</span>` : ''}
                <span class="panel-title-badge">${escapeHtml(item.cat)}</span>
              </div>
            </div>
            <p class="conflict-card-desc">${escapeHtml(item.description)}</p>
            ${item.mitigation_summary ? `<div style="padding: 8px 12px; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); font-size: 0.82rem; color: #34d399; margin-top: 4px;"><strong>Stack Mitigation:</strong> ${escapeHtml(item.mitigation_summary)}</div>` : ''}
            ${item.ddi_auc_ratio && isPower ? `<div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#00f2fe; margin-top:4px; background:rgba(0,0,0,0.3); padding:4px 8px; border-radius:4px; display:flex; align-items:center; gap:5px;">${iconSvg('bar-chart-2', { class: 'icon-xs' })} Power Metric • Estimated DDI Exposure Multiplier: ${item.ddi_auc_ratio}x AUC (+${Math.round((item.ddi_auc_ratio - 1) * 100)}% surge)</div>` : ''}
            ${item.clinical_recommendation ? `<div class="conflict-card-rec"><strong>Recommendation:</strong> ${escapeHtml(item.clinical_recommendation)}</div>` : ''}
            <div style="margin-top: 8px; display: flex; justify-content: flex-end;">
              <button type="button" class="btn-secondary" onclick="switchToGraphTab('${escapeHtml(item.source_key || item.comp1 || '')}')" style="font-size: 0.74rem; padding: 4px 10px; color: var(--accent-cyan); border-color: rgba(0, 242, 254, 0.35); background: rgba(0, 242, 254, 0.08); font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;">
                <span>${iconSvg('network', { class: 'icon-xs' })} Trace Pathway in Knowledge Graph</span> ➔
              </button>
            </div>
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

        window._currentInspectorPair = {
          source_key: cell.source_key || (state.analysis.compounds?.[i]?.key) || '',
          target_key: cell.target_key || (state.analysis.compounds?.[j]?.key) || '',
          source_name: srcName,
          target_name: tgtName,
        };

        document.getElementById('modal-pair-title').textContent = `${srcName} ⟷ ${tgtName}`;
        document.getElementById('modal-pair-subtitle').textContent = cell.title || 'Pharmacology Collision';
        document.getElementById('modal-description').textContent = cell.description || 'No specific conflict documented.';
        document.getElementById('modal-recommendation').textContent = cell.clinical_recommendation || 'Standard clinical monitoring recommended.';

        const badge = document.getElementById('modal-severity-badge');
        let bandClass = 'band-minimal';
        let badgeHtml = cell.severity ? cell.severity.replace('_', ' ') : 'Neutral';
        
        if (cell.is_mitigated_by_stack) {
          bandClass = 'band-minimal';
          badgeHtml = `${iconSvg('shield-check', { class: 'icon-xs' })} Mitigated by Full Stack`;
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
        badge.innerHTML = badgeHtml;

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
            citeHtml += `<div style="font-size:0.75rem; color:#38bdf8; padding:4px 8px; background:rgba(56,189,248,0.08); border-radius:4px; border:1px solid rgba(56,189,248,0.2); display:flex; align-items:center; gap:5px;">${iconSvg('building-2', { class: 'icon-xs' })} <strong>Regulatory:</strong> ${escapeHtml(fdaRef)}</div>`;
          }
          if (pmids.length > 0) {
            citeHtml += `
              <div style="font-size:0.72rem; color:var(--text-secondary); display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('book-open', { class: 'icon-xs' })} <strong>PubMed Studies:</strong></span>
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

        const modalTraceBtn = document.getElementById('modal-trace-graph-btn');
        if (modalTraceBtn) {
          modalTraceBtn.onclick = () => {
            inspectorModal.classList.remove('open');
            const pair = window._currentInspectorPair;
            if (pair && pair.source_key) {
              switchToGraphTab(pair.source_key, [pair.source_key, pair.target_key].filter(Boolean));
            } else {
              switchToGraphTab();
            }
          };
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
          if (tabId === 'graph-tab') {
            if (typeof initOrRenderEmbeddedGraph === 'function') {
              initOrRenderEmbeddedGraph();
            }
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

        let normTiming = (timing || 'morning').toLowerCase();
        if (normTiming.includes('bed') || normTiming.includes('night')) normTiming = 'before bed';
        else if (normTiming.includes('eve') || normTiming.includes('dinner')) normTiming = 'evening';
        else if (normTiming.includes('mid') || normTiming.includes('noon') || normTiming.includes('afternoon') || normTiming.includes('lunch')) normTiming = 'midday';
        else if (normTiming.includes('pre-workout') || normTiming.includes('preworkout')) normTiming = 'pre-workout';
        else if (normTiming !== 'morning' && normTiming !== 'midday' && normTiming !== 'pre-workout' && normTiming !== 'evening' && normTiming !== 'before bed') normTiming = 'morning';

        return {
          key,
          name,
          drug_class: drugClass,
          dose,
          unit,
          timing: normTiming,
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

      // Global Window Exports
      window.evaluateStack = evaluateStack;
      window.updateDashboardEmpty = updateDashboardEmpty;
      window.renderDashboard = renderDashboard;
      window.renderFullStackBalance = renderFullStackBalance;
      window.renderMatrixTable = renderMatrixTable;
      window.renderBreakdowns = renderBreakdowns;

      // ==========================================================================
