// FLAGSHIP AI COPILOT CLIENT ENGINE (MULTI-TURN SSE STREAMING & ACTION CARDS)
// ==========================================================================
var iconSvg = window.iconSvg || function(name, options = {}) {
  if (typeof window.iconSvg === 'function') return window.iconSvg(name, options);
  return `<i data-lucide="${name}" class="${options.class || ''}"></i>`;
};
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
          .replace(/\*(.*?)\*\*/g, '<em>$1</em>')
          .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.35); border-radius: 3px; padding: 1px 5px; font-size: 0.76rem; color: var(--accent-cyan);">$1</code>');
      }

      // ==============================================================================
      // STRUCTURED PROTOCOL PARSER & INTERACTIVE PROTOCOL CANVAS RENDERER
      // ==============================================================================
      function addSingleCompoundToStack(chipOrObj) {
        if (!chipOrObj) return;
        let comp = null;
        if (typeof chipOrObj === 'string') {
          const k = chipOrObj.toLowerCase().trim().replace(/ /g, '_');
          comp = { key: k, name: chipOrObj.replace(/_/g, ' ') };
        } else if (chipOrObj && chipOrObj.nodeType) {
          // DOM element
          try {
            comp = JSON.parse(chipOrObj.getAttribute('data-compound-json'));
          } catch (e) {
            const key = chipOrObj.getAttribute('data-compound-key') || '';
            const name = chipOrObj.querySelector('.copilot-chip-name')?.textContent || key;
            comp = { key, name };
          }
        } else if (typeof chipOrObj === 'object' && chipOrObj !== null) {
          comp = chipOrObj;
        }

        if (!comp) return;

        const rawKey = String(comp.key || comp.name || '').toLowerCase().trim().replace(/ /g, '_');
        if (!rawKey) return;

        const cached = _clientCatalogCache[rawKey] || _clientCatalogCache[rawKey.replace(/_/g, '-')];
        const fallback = getDefaultDoseFallback(rawKey);

        const doseVal = (comp.dose !== undefined && comp.dose !== null && !isNaN(Number(comp.dose)))
          ? Number(comp.dose)
          : (cached && cached.dose !== undefined ? cached.dose : fallback.dose);
        const unitVal = comp.unit || (cached && cached.unit) || fallback.unit || 'mg';
        const freqVal = comp.frequency || (cached && cached.frequency) || 'daily';
        let timingVal = comp.timing;
        if (!timingVal || (timingVal === 'morning' && freqVal !== 'daily')) {
          const normF = String(freqVal).toLowerCase().replace(/ /g, '_');
          if (normF === 'every_other_day' || normF === 'eod') timingVal = 'Every Other Day (EOD)';
          else if (normF === 'three_times_weekly' || normF === '3x_weekly') timingVal = 'Three Times Weekly (Mon / Wed / Fri)';
          else if (normF === 'twice_weekly') timingVal = 'Twice Weekly (Mon / Thu)';
          else if (normF === 'weekly') timingVal = 'Weekly';
          else if (normF === 'biweekly') timingVal = 'Bi-Weekly (Every 2 Weeks)';
          else if (normF === 'as_needed') timingVal = 'As Needed (PRN)';
          else timingVal = timingVal || 'morning';
        }
        const routeVal = comp.route || (cached && (cached.route || cached.default_route)) || fallback.route || 'oral';
        const nameVal = comp.name || (cached && cached.name) || rawKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const drugClassVal = comp.drug_class || comp.target || (cached && cached.drug_class) || 'Compound';

        const existingItem = matchCompoundItem(state.stack, rawKey);

        if (existingItem) {
          existingItem.dose = doseVal;
          existingItem.unit = unitVal;
          existingItem.timing = timingVal;
          existingItem.route = routeVal;
          existingItem.frequency = freqVal;
          showToast(`Updated ${existingItem.name || nameVal} in workbench stack (${doseVal}${unitVal})`, 'zap');
        } else {
          state.stack.push({
            key: rawKey,
            name: nameVal,
            drug_class: drugClassVal,
            dose: doseVal,
            unit: unitVal,
            frequency: freqVal,
            timing: timingVal,
            route: routeVal,
          });
          showToast(`Added ${nameVal} (${doseVal}${unitVal}) to workbench stack!`, 'check');
        }

        renderStackList();
        if (state.stack.length) {
          if (typeof evaluateStack === 'function') evaluateStack();
        } else {
          if (typeof updateDashboardEmpty === 'function') updateDashboardEmpty();
        }
        if (typeof syncCopilotStackTags === 'function') syncCopilotStackTags();

        // Background hydration for compound metadata
        if (!_clientCatalogCache[rawKey]) {
          fetch('/api/compounds/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keys: [rawKey] })
          }).then(res => res.ok ? res.json() : {}).then(data => {
            const enriched = data[rawKey] || Object.values(data)[0];
            if (enriched) {
              _clientCatalogCache[rawKey] = enriched;
              if (enriched.key) _clientCatalogCache[enriched.key] = enriched;
              const match = matchCompoundItem(state.stack, rawKey);
              if (match) {
                if (enriched.name) match.name = enriched.name;
                if (enriched.drug_class) match.drug_class = enriched.drug_class;
                renderStackList();
              }
            }
          }).catch(() => {});
        }

        // Update all matching chips in current protocol cards
        document.querySelectorAll(`.copilot-compound-chip[data-compound-key="${rawKey}"]`).forEach(chip => {
          const actionEl = chip.querySelector('.copilot-chip-action, .copilot-chip-quick-add-btn');
          if (actionEl) {
            actionEl.className = 'copilot-chip-quick-add-btn in-stack';
            actionEl.innerHTML = `<span style="display:inline-flex; align-items:center; gap:3px;">${iconSvg('check', { class: 'icon-xs' })} In Stack</span>`;
          }
        });

        // Update inspector action button if currently open
        document.querySelectorAll('.copilot-compound-inspector').forEach(ins => {
          const btn = ins.querySelector('.btn-inspector-add');
          if (btn) {
            btn.className = 'btn-inspector-add in-stack';
            btn.innerHTML = `<span>${iconSvg('check', { class: 'icon-xs' })} In Workbench Stack (${doseVal}${unitVal})</span>`;
          }
        });
      }
      window.addSingleCompoundToStack = addSingleCompoundToStack;

      function extractFirstBalancedJson(str) {
        if (!str || typeof str !== 'string') return null;
        const start = str.indexOf('{');
        if (start === -1) return null;
        let depth = 0;
        let inString = false;
        let escapeNext = false;
        for (let i = start; i < str.length; i++) {
          const ch = str[i];
          if (escapeNext) {
            escapeNext = false;
          } else if (ch === '\\' && inString) {
            escapeNext = true;
          } else if (ch === '"') {
            inString = !inString;
          } else if (!inString) {
            if (ch === '{') {
              depth++;
            } else if (ch === '}') {
              depth--;
              if (depth === 0) {
                try {
                  return JSON.parse(str.substring(start, i + 1));
                } catch (e) {
                  return null;
                }
              }
            }
          }
        }
        
        // If we reach here, the JSON might be truncated. Try to repair it.
        const candidate = str.substring(start);
        for (let i = candidate.length; i > Math.max(0, candidate.length - 200); i--) {
          const testStr = candidate.substring(0, i);
          let s2 = [];
          let ins2 = false;
          let esc2 = false;
          for (let j = 0; j < testStr.length; j++) {
            const c = testStr[j];
            if (esc2) { esc2 = false; }
            else if (c === '\\') { esc2 = true; }
            else if (c === '"') { ins2 = !ins2; }
            else if (!ins2) {
              if (c === '{' || c === '[') { s2.push(c === '{' ? '}' : ']'); }
              else if (c === '}' || c === ']') {
                if (s2.length && s2[s2.length - 1] === c) { s2.pop(); }
              }
            }
          }
          let tmp = testStr;
          if (ins2) tmp += '"';
          tmp = tmp.replace(/\s+$/, '');
          if (tmp.endsWith(',')) {
            tmp = tmp.substring(0, tmp.length - 1);
          }
          for (let j = s2.length - 1; j >= 0; j--) {
            tmp += s2[j];
          }
          try {
            return JSON.parse(tmp);
          } catch (e) {
            continue;
          }
        }
        
        return null;
      }

      function parseProtocolData(rawMarkdown, actionCardPayload) {
        if (!rawMarkdown && !actionCardPayload) return null;
        
        try {
          let cleanJson = typeof rawMarkdown === 'string' ? rawMarkdown.trim() : rawMarkdown;
          if (typeof cleanJson === 'string') {
            // Strip think blocks and action_card XML tags
            cleanJson = cleanJson.replace(/<think[\s\S]*?(<\/think>|$)/gi, '').trim();
            cleanJson = cleanJson.replace(/<action_card[\s\S]*?(<\/action_card>|$)/gi, '').trim();
            cleanJson = cleanJson.replace(/^```json\s*/i, '').replace(/^```\s*/, '').replace(/```\s*$/i, '').trim();
            
            if (cleanJson.startsWith('"') && cleanJson.endsWith('"')) {
               cleanJson = cleanJson.slice(1, -1).replace(/\\"/g, '"').replace(/\\n/g, '\n');
            }
            if (cleanJson.startsWith("'") && cleanJson.endsWith("'")) {
               cleanJson = cleanJson.slice(1, -1);
            }
          }

          let parsed = null;
          if (typeof cleanJson === 'string') {
            try {
              parsed = JSON.parse(cleanJson);
            } catch (jsonErr) {
              parsed = extractFirstBalancedJson(cleanJson);
            }
          } else {
            parsed = cleanJson;
          }
          
          let data = null;
          if (parsed && Array.isArray(parsed.blocks)) {
            const proposalBlock = parsed.blocks.find(b => b.type === 'protocol_proposal');
            if (proposalBlock && proposalBlock.data) {
              data = proposalBlock.data;
            }
          } else if (parsed && parsed.compounds) {
            data = parsed; // Legacy / Direct format
          } else if (parsed && parsed.data && parsed.data.compounds) {
            data = parsed.data;
          }

          // Fallback to actionCardPayload if no structured data in blocks
          if (!data && actionCardPayload) {
            const rawAdd = actionCardPayload.additions || actionCardPayload.add || actionCardPayload.compounds || [];
            if (Array.isArray(rawAdd) && rawAdd.length) {
              const synthCompounds = rawAdd.map(a => {
                const k = typeof a === 'string' ? a.toLowerCase().trim().replace(/ /g, '_') : String(a.id || a.key || a.chembl_id || a.name || '').toLowerCase().trim().replace(/ /g, '_');
                const catComp = (state.catalog && Array.isArray(state.catalog)) ? state.catalog.find(c => String(c.key || c.id || '').toLowerCase() === k) : null;
                const compName = (typeof a === 'object' && a.name) || (catComp && catComp.name) || k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                let compTarget = (typeof a === 'object' && a.target) || '';
                if (!compTarget || compTarget === 'Molecular Target / Receptor' || compTarget === 'Molecular Target / Pathway') {
                  if (catComp && catComp.receptor_targets && catComp.receptor_targets.length) {
                    const firstTgt = catComp.receptor_targets[0];
                    compTarget = `${firstTgt.target || firstTgt.name} (${firstTgt.action || 'modulator'})`;
                  } else if (catComp && catComp.mechanism) {
                    compTarget = catComp.mechanism;
                  } else if (catComp && catComp.drug_class) {
                    compTarget = catComp.drug_class;
                  } else {
                    compTarget = 'Pharmacological Target';
                  }
                }
                const doseVal = (typeof a === 'object' && a.dose) ? a.dose : ((catComp && catComp.default_dose && catComp.default_dose.dose_mg) ? catComp.default_dose.dose_mg : 100);
                const unitVal = (typeof a === 'object' && a.unit) ? a.unit : ((catComp && catComp.default_dose && catComp.default_dose.unit) ? catComp.default_dose.unit : 'mg');
                const routeVal = (typeof a === 'object' && a.route) ? a.route : ((catComp && catComp.route) ? catComp.route : 'oral');
                const timingVal = (typeof a === 'object' && a.timing) ? a.timing : 'morning';
                let rationaleVal = (typeof a === 'object' && (a.rationale || a.clinical_purpose || a.reason)) ? (a.rationale || a.clinical_purpose || a.reason) : '';
                if (!rationaleVal && catComp) {
                  const mech = catComp.mechanism || '';
                  const targets = (catComp.receptor_targets || []).map(t => typeof t === 'object' ? `${t.target || t.name} (${t.action || 'modulator'})` : String(t)).join(', ');
                  const notes = catComp.clinical_notes || catComp.description || '';
                  const parts = [];
                  if (mech) parts.push(mech.endsWith('.') ? mech : `${mech}.`);
                  if (targets) parts.push(`Primary receptor engagement: ${targets}.`);
                  if (notes) parts.push(notes.endsWith('.') ? notes : `${notes}.`);
                  rationaleVal = parts.join(' ');
                }
                if (!rationaleVal) {
                  rationaleVal = `Bio-individualized protocol addition targeting ${compTarget} with calibrated ${doseVal}${unitVal} administration.`;
                }

                return {
                  id: k,
                  key: k,
                  name: compName,
                  dose: doseVal,
                  unit: unitVal,
                  route: routeVal,
                  frequency: freqVal,
                  timing: timingVal,
                  target: compTarget,
                  rationale: rationaleVal
                };
              });

              let summaryVal = actionCardPayload.summary || actionCardPayload.protocol_summary || actionCardPayload.description || '';
              if (!summaryVal) {
                const goalTitle = actionCardPayload.goal_title || 'Precision Clinical Protocol';
                summaryVal = `Synergistic ${goalTitle} architecture formulated with ${synthCompounds.length} compounds calibrated for bio-availability, targeted receptor kinetics, and organ-protective circadian windows.`;
              }

              data = {
                goal_title: actionCardPayload.goal_title || 'Clinical Protocol Architecture',
                persona: 'ARCHITECT',
                summary: summaryVal,
                compounds: synthCompounds,
                diff: actionCardPayload
              };
            }
          }

          if (data) {
            const compounds = data.compounds || [];
            const diffPayload = data.diff || { additions: [], modifications: [], removals: [], add: [], modify: [], remove: [] };
            
            // Normalize diff payload arrays
            const adds = [].concat(diffPayload.additions || [], diffPayload.add || []).map(a => typeof a === 'string' ? a.toLowerCase().trim().replace(/ /g, '_') : String(a.key || a.name || '').toLowerCase().trim().replace(/ /g, '_'));
            const mods = [].concat(diffPayload.modifications || [], diffPayload.modify || []).map(m => typeof m === 'string' ? m.toLowerCase().trim().replace(/ /g, '_') : String(m.key || m.name || '').toLowerCase().trim().replace(/ /g, '_'));
            const rems = [].concat(diffPayload.removals || [], diffPayload.remove || []).map(r => typeof r === 'string' ? r.toLowerCase().trim().replace(/ /g, '_') : String(r.key || r.name || '').toLowerCase().trim().replace(/ /g, '_'));

            // Assign action property to each compound based on diff payload and current stack
            compounds.forEach(c => {
              const cKey = String(c.key || c.name || '').toLowerCase().trim().replace(/ /g, '_');
              const inWorkbench = state.stack.some(s => String(s.key || s.name || '').toLowerCase().trim().replace(/ /g, '_') === cKey);
              if (mods.includes(cKey)) {
                c.action = 'modify';
              } else if (adds.includes(cKey)) {
                c.action = inWorkbench ? 'retain' : 'add';
              } else if (inWorkbench) {
                c.action = 'retain';
              } else {
                c.action = 'add';
              }
            });

            // Enrich diffPayload.add with full compound metadata
            if (Array.isArray(diffPayload.add)) {
              diffPayload.add = diffPayload.add.map(item => {
                const itemKey = typeof item === 'string' ? item.toLowerCase().trim().replace(/ /g, '_') : String(item.key || item.name || '').toLowerCase().trim().replace(/ /g, '_');
                const matched = compounds.find(c => String(c.key || c.name || '').toLowerCase().trim().replace(/ /g, '_') === itemKey);
                if (matched) {
                  return {
                    key: matched.key,
                    name: matched.name,
                    dose: matched.dose,
                    unit: matched.unit,
                    timing: matched.timing,
                    frequency: matched.frequency,
                    route: matched.route,
                    target: matched.target,
                  };
                }
                return typeof item === 'string' ? { key: item, name: item.replace(/_/g, ' ') } : item;
              });
            }

            return {
              goalTitle: data.goal_title || 'Clinical Protocol Architecture',
              persona: data.persona || 'ARCHITECT',
              execSummary: data.summary || '',
              biometricsStr: 'Reference Baseline',
              compounds: compounds,
              safetyNotes: data.safety_notes || [],
              sources: data.sources || [],
              diffPayload: diffPayload
            };
          }
        } catch (e) {
          console.debug('parseProtocolData error', e);
        }
        
        return null;
      }

      function renderInteractiveProtocolCard(proto) {
        if (!proto) return '';

        const slotGroups = {
          morning: { label: 'Morning', icon: 'sunrise', items: [] },
          midday: { label: 'Midday / Afternoon', icon: 'sun', items: [] },
          evening: { label: 'Evening', icon: 'sunset', items: [] },
          bedtime: { label: 'Bedtime', icon: 'moon', items: [] },
          preworkout: { label: 'Pre-Workout / Targeted', icon: 'zap', items: [] },
          eod: { label: 'Every Other Day (EOD / QOD)', icon: 'repeat', items: [] },
          three_times_weekly: { label: 'Three Times Weekly (Mon / Wed / Fri)', icon: 'calendar', items: [] },
          twice_weekly: { label: 'Twice Weekly Split (Mon / Thu)', icon: 'calendar', items: [] },
          weekly: { label: 'Weekly Protocol (Once Weekly)', icon: 'calendar', items: [] },
          extended: { label: 'Extended Interval / Depot (Bi-Weekly / Monthly)', icon: 'calendar-days', items: [] },
          prn: { label: 'As Needed (PRN / Situational)', icon: 'clock', items: [] }
        };

        proto.compounds.forEach(c => {
          const t = String(c.timing || '').toLowerCase();
          const freq = String(c.frequency || '').toLowerCase().replace(/ /g, '_');
          
          if (freq === 'every_other_day' || freq === 'eod' || freq === 'qod' || t.includes('eod') || t.includes('every other day') || t.includes('qod') || t.includes('alternate day')) {
            slotGroups.eod.items.push(c);
          } else if (freq === 'three_times_weekly' || freq === '3x_weekly' || freq === 'tiw' || t.includes('mon/wed/fri') || t.includes('mon / wed / fri') || t.includes('mwf') || t.includes('3x weekly') || t.includes('three times weekly')) {
            slotGroups.three_times_weekly.items.push(c);
          } else if (freq === 'twice_weekly' || freq === 'biw' || freq === '2x_weekly' || t.includes('mon/thu') || t.includes('mon / thu') || t.includes('twice weekly') || t.includes('biw') || t.includes('split depot')) {
            slotGroups.twice_weekly.items.push(c);
          } else if (freq === 'biweekly' || freq === 'q2w' || freq === 'monthly' || freq === 'qm' || t.includes('biweekly') || t.includes('every 2 weeks') || t.includes('monthly')) {
            slotGroups.extended.items.push(c);
          } else if (freq === 'weekly' || freq === 'qw' || freq === 'once_weekly' || t.includes('weekly') || t.includes('depot')) {
            slotGroups.weekly.items.push(c);
          } else if (freq === 'as_needed' || freq === 'prn' || t.includes('as needed') || t.includes('prn')) {
            slotGroups.prn.items.push(c);
          } else if (t.includes('pre-workout') || t.includes('preworkout')) {
            slotGroups.preworkout.items.push(c);
          } else if (t.includes('mid') || t.includes('noon') || t.includes('afternoon') || t.includes('lunch')) {
            slotGroups.midday.items.push(c);
          } else if (t.includes('bed') || t.includes('night') || t.includes('nocturnal')) {
            slotGroups.bedtime.items.push(c);
          } else if (t.includes('eve') || t.includes('dinner')) {
            slotGroups.evening.items.push(c);
          } else {
            slotGroups.morning.items.push(c);
          }
        });

        let chronoGroupsHtml = '';
        Object.keys(slotGroups).forEach(k => {
          const grp = slotGroups[k];
          if (grp.items.length > 0) {
            let chipsHtml = '';
            grp.items.forEach(c => {
              const cKey = String(c.key || c.name || '').toLowerCase().trim().replace(/ /g, '_');
              const inWorkbench = state.stack.some(s => String(s.key || s.name || '').toLowerCase().trim().replace(/ /g, '_') === cKey);
              const actionCls = inWorkbench ? 'retain in-stack' : (c.action === 'modify' ? 'modify' : 'add');
              const actionLabel = inWorkbench ? 'In Stack' : (c.action === 'modify' ? '~ TITRATE' : '+ ADD');
              const routeLabel = c.route ? (c.route === 'intramuscular' ? 'IM' : (c.route === 'subcutaneous' ? 'SubQ' : String(c.route).toUpperCase())) : 'ORAL';
              
              let scheduleBadge = '';
              const normFreq = String(c.frequency || '').toLowerCase().replace(/ /g, '_');
              if (normFreq === 'every_other_day' || normFreq === 'eod') {
                scheduleBadge = ' • EOD';
              } else if (normFreq === 'three_times_weekly' || normFreq === '3x_weekly') {
                scheduleBadge = ' • 3x/wk';
              } else if (normFreq === 'twice_weekly') {
                scheduleBadge = ' • 2x/wk';
              } else if (normFreq === 'weekly') {
                scheduleBadge = ' • QW';
              } else if (normFreq === 'biweekly') {
                scheduleBadge = ' • Q2W';
              } else if (normFreq === 'monthly') {
                scheduleBadge = ' • Monthly';
              } else if (normFreq === 'as_needed') {
                scheduleBadge = ' • PRN';
              } else if (normFreq === 'twice_daily') {
                scheduleBadge = ' • BID';
              } else if (normFreq === 'three_times_daily') {
                scheduleBadge = ' • TID';
              }

              const compJsonStr = JSON.stringify(c).replace(/"/g, '&quot;');

              chipsHtml += `
                <div class="copilot-compound-chip" data-compound-key="${escapeHtml(c.key)}" data-compound-json="${compJsonStr}" onclick="inspectProtocolCompound(this)">
                  <div class="copilot-chip-top">
                    <span class="copilot-chip-name" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span>
                    <button type="button" class="copilot-chip-quick-add-btn ${actionCls}" onclick="event.stopPropagation(); addSingleCompoundToStack(this.closest('.copilot-compound-chip'))" title="Add ${escapeHtml(c.name)} to Workbench Stack">
                      ${actionLabel}
                    </button>
                  </div>
                  <div class="copilot-chip-bottom">
                    <span class="copilot-chip-dose">${escapeHtml(c.dose)}${escapeHtml(c.unit || 'mg')} ${escapeHtml(routeLabel)}${escapeHtml(scheduleBadge)}</span>
                    <span class="copilot-chip-target" title="${escapeHtml(c.target || '')}">${escapeHtml(c.target || '')}</span>
                    <span class="copilot-chip-inspect-icon" title="Click to inspect pharmacology">${iconSvg('info', { class: 'icon-xs' })}</span>
                  </div>
                </div>
              `;
            });

            chronoGroupsHtml += `
              <div class="copilot-chrono-group">
                <div class="copilot-chrono-header">
                  <span style="display:inline-flex; align-items:center; gap:5px;">${iconSvg(grp.icon, { class: 'icon-xs icon-cyan' })} ${grp.label}</span>
                  <span class="copilot-chrono-slot-badge">${grp.items.length} compound${grp.items.length > 1 ? 's' : ''}</span>
                </div>
                <div class="copilot-chrono-chips-wrap">
                  ${chipsHtml}
                </div>
              </div>
            `;
          }
        });

        let safetyAccordionHtml = '';
        if (proto.safetyNotes && proto.safetyNotes.length) {
          const notesHtml = proto.safetyNotes.map(n => `<li style="margin-bottom: 4px;">${renderInlineMarkdown(escapeHtml(n))}</li>`).join('');
          safetyAccordionHtml = `
            <div class="copilot-accordion">
              <button type="button" class="copilot-accordion-toggle" onclick="this.parentElement.classList.toggle('open')">
                <div class="copilot-accordion-title-wrap">
                  <span>${iconSvg('shield-check', { class: 'icon-xs icon-emerald' })} Clinical Titration & Biomarker Safety Guidance</span>
                  <span class="copilot-accordion-badge">CMP, Lipids & Organ Shield</span>
                </div>
                <span class="copilot-accordion-icon">${iconSvg('chevron-down', { class: 'icon-xs' })}</span>
              </button>
              <div class="copilot-accordion-content">
                <ul style="margin: 0; padding-left: 18px;">
                  ${notesHtml}
                </ul>
              </div>
            </div>
          `;
        }

        let sourcesAccordionHtml = '';
        if (proto.sources && proto.sources.length) {
          let sourcesListHtml = '';
          proto.sources.forEach(s => {
            sourcesListHtml += `<li style="margin-bottom: 5px;"><strong>${renderMarkdownLite(s.badge)}</strong> ${renderInlineMarkdown(escapeHtml(s.description))}</li>`;
          });
          sourcesAccordionHtml = `
            <div class="copilot-accordion">
              <button type="button" class="copilot-accordion-toggle" onclick="this.parentElement.classList.toggle('open')">
                <div class="copilot-accordion-title-wrap">
                  <span>${iconSvg('book-open', { class: 'icon-xs icon-blue' })} Scientific Evidence Base</span>
                  <span class="copilot-accordion-badge">${proto.sources.length} Studies & Registries</span>
                </div>
                <span class="copilot-accordion-icon">${iconSvg('chevron-down', { class: 'icon-xs' })}</span>
              </button>
              <div class="copilot-accordion-content">
                <ul style="margin: 0; padding-left: 18px; list-style-type: disc;">
                  ${sourcesListHtml}
                </ul>
              </div>
            </div>
          `;
        }

        const addCount = (proto.diffPayload.additions || proto.diffPayload.add || []).length;
        const modCount = (proto.diffPayload.modifications || proto.diffPayload.modify || []).length;
        const remCount = (proto.diffPayload.removals || proto.diffPayload.remove || []).length;
        const diffEscaped = JSON.stringify(proto.diffPayload).replace(/"/g, '&quot;');

        return `
          <div class="copilot-protocol-card">
            <!-- HERO -->
            <div class="copilot-protocol-hero">
              <div class="copilot-protocol-hero-left">
                <div class="copilot-protocol-title-row">
                  <span class="copilot-protocol-icon">${iconSvg('zap', { class: 'icon-sm icon-cyan icon-glow-cyan' })}</span>
                  <span class="copilot-protocol-title">${escapeHtml(proto.goalTitle)}</span>
                  <span class="copilot-persona-pill">${escapeHtml(proto.persona)}</span>
                </div>
                <div class="copilot-protocol-meta-row">
                  <span class="copilot-meta-chip bio">${iconSvg('user', { class: 'icon-xs icon-cyan' })} ${escapeHtml(proto.biometricsStr)}</span>
                  <span class="copilot-meta-chip count">${iconSvg('flask-conical', { class: 'icon-xs icon-purple' })} ${proto.compounds.length} Compounds</span>
                  <span class="copilot-meta-chip">${iconSvg('shield-check', { class: 'icon-xs icon-teal' })} Zero bro-science</span>
                </div>
              </div>
            </div>

            <!-- EXECUTIVE ASSESSMENT -->
            ${proto.execSummary ? `<div class="copilot-protocol-exec-summary">${renderInlineMarkdown(escapeHtml(proto.execSummary))}</div>` : ''}

            <!-- CIRCADIAN CHRONO MATRIX -->
            <div class="copilot-chrono-matrix">
              <div class="copilot-chrono-matrix-title">
                <span>${iconSvg('clock', { class: 'icon-xs icon-cyan' })} Circadian Administration Schedule</span>
                <span class="copilot-chrono-hint">Click compound to inspect pharmacology & evidence ↗</span>
              </div>
              ${chronoGroupsHtml}
            </div>

            <!-- SLIDING COMPOUND INSPECTOR PANEL -->
            <div class="copilot-compound-inspector" style="display: none;"></div>

            <!-- COLLAPSIBLE ACCORDIONS -->
            ${safetyAccordionHtml}
            ${sourcesAccordionHtml}

            <!-- ACTIONS BAR -->
            <div class="copilot-protocol-actions">
              <div class="copilot-protocol-diff-summary">
                ${addCount > 0 ? `<span class="copilot-diff-pill add">+${addCount} Add</span>` : ''}
                ${modCount > 0 ? `<span class="copilot-diff-pill mod">~${modCount} Titrate</span>` : ''}
                ${remCount > 0 ? `<span class="copilot-diff-pill rem">-${remCount} Drop</span>` : ''}
              </div>
              <button type="button" class="btn-apply-diff" onclick="applyCopilotStackDiff(${diffEscaped}, this)">
                <span>${iconSvg('zap', { class: 'icon-xs icon-cyan' })} Apply Protocol to Workbench Stack</span>
              </button>
            </div>
          </div>
        `;
      }

      function formatTargetRole(targetStr, comp) {
        if (!targetStr || targetStr === 'Target Receptor / Enzyme' || targetStr === 'Target Pathway / Receptor Ligand' || targetStr === 'Molecular Target / Pathway') {
          if (comp && comp.drug_class) return comp.drug_class;
          return 'Molecular Target / Pathway';
        }
        const s = String(targetStr).trim();
        const lower = s.toLowerCase();
        if (lower.startsWith('⚙️') || lower.startsWith('🚪') || lower.startsWith('🧬') || lower.startsWith('⚡') || lower.startsWith('🎯') || lower.startsWith('🧪')) {
          return s;
        }
        if (lower.includes('substrate') || lower.includes('carns1') || lower.includes('ckm') || lower.includes('phosphagen') || lower.includes('atp-pcr')) {
          if (lower.includes('transporter') || lower.includes('slc')) {
            return `Transporter Substrate: ${s}`;
          }
          return `Enzyme Substrate: ${s}`;
        }
        if (lower.includes('transporter') || lower.includes('dat') || lower.includes('sert') || lower.includes('net') || lower.includes('slc')) {
          return `Transporter: ${s}`;
        }
        if (lower.includes('channel') || lower.includes('ampa') || lower.includes('cav') || lower.includes('nav')) {
          return `Ion Channel: ${s}`;
        }
        if (lower.includes('synthase') || lower.includes('kinase') || lower.includes('enzyme') || lower.includes('cyp') || lower.includes('reductase') || lower.includes('aromatase') || lower.includes('hydroxylase')) {
          return `Enzyme: ${s}`;
        }
        if (lower.includes('receptor') || lower.includes('gpcr') || lower.includes('agonist') || lower.includes('antagonist') || lower.includes('mrgpr')) {
          return `Receptor: ${s}`;
        }
        return `${s}`;
      }

      function inspectProtocolCompound(chipEl) {
        if (!chipEl) return;
        const parentCard = chipEl.closest('.copilot-protocol-card');
        if (!parentCard) return;

        const inspector = parentCard.querySelector('.copilot-compound-inspector');
        if (!inspector) return;

        const isAlreadySelected = chipEl.classList.contains('selected');
        parentCard.querySelectorAll('.copilot-compound-chip').forEach(c => c.classList.remove('selected'));

        if (isAlreadySelected) {
          inspector.style.display = 'none';
          return;
        }

        chipEl.classList.add('selected');

        let comp = null;
        try {
          comp = JSON.parse(chipEl.getAttribute('data-compound-json'));
        } catch (e) {
          comp = { name: chipEl.querySelector('.copilot-chip-name')?.textContent || 'Compound' };
        }

        const routeLabel = comp.route ? (comp.route === 'intramuscular' ? 'Intramuscular' : (comp.route === 'subcutaneous' ? 'Subcutaneous' : String(comp.route).toUpperCase())) : 'Oral';
        const freqLabel = comp.frequency ? String(comp.frequency).replace(/_/g, ' ') : 'daily';
        const timingLabel = (comp.timing || 'morning').toUpperCase();
        const cKey = String(comp.key || comp.name || '').toLowerCase().trim().replace(/ /g, '_');
        const inWorkbench = state.stack.some(s => String(s.key || s.name || '').toLowerCase().trim().replace(/ /g, '_') === cKey);
        const addBtnText = inWorkbench ? `${iconSvg('check', { class: 'icon-xs' })} In Workbench Stack (${comp.dose}${comp.unit || 'mg'})` : `${iconSvg('plus', { class: 'icon-xs' })} Add ${escapeHtml(comp.name)} to Workbench Stack`;
        const addBtnCls = inWorkbench ? 'btn-inspector-add in-stack' : 'btn-inspector-add';

        let citationBadgesHtml = '';
        if (comp.citations && comp.citations.length) {
          citationBadgesHtml = comp.citations.map(c => {
            const citeStr = String(c).trim();
            const pmidM = citeStr.match(/PMID:\s*(\d+)/i);
            if (pmidM) {
              return `<a href="https://pubmed.ncbi.nlm.nih.gov/${pmidM[1]}/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge pmid-badge" title="View study on PubMed (PMID: ${pmidM[1]})">${iconSvg('file-text', { class: 'icon-xs icon-teal' })} PMID: ${pmidM[1]}</a>`;
            }
            const doiM = citeStr.match(/DOI:\s*([^\s\]]+)/i);
            if (doiM) {
              return `<a href="https://doi.org/${doiM[1]}" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge doi-badge" title="View DOI Publication">${iconSvg('globe', { class: 'icon-xs icon-blue' })} DOI: ${doiM[1]}</a>`;
            }
            const chemblM = citeStr.match(/ChEMBL:\s*([A-Za-z0-9_]+)/i);
            if (chemblM) {
              return `<a href="https://www.ebi.ac.uk/chembl/target_report_card/${chemblM[1]}/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge chembl-badge" title="View ChEMBL Target">${iconSvg('microscope', { class: 'icon-xs icon-purple' })} ChEMBL: ${chemblM[1]}</a>`;
            }
            return `<span class="copilot-citation-badge pmid-badge">${escapeHtml(citeStr)}</span>`;
          }).join(' ');
        }

        inspector.innerHTML = `
          <div class="copilot-inspector-header">
            <div class="copilot-inspector-title">
              <span style="display:inline-flex; align-items:center; gap:5px;">${iconSvg('search', { class: 'icon-xs' })} ${escapeHtml(comp.name)}</span>
              <span style="font-size: 0.72rem; color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace;">(${escapeHtml(comp.dose)}${escapeHtml(comp.unit || 'mg')} • ${escapeHtml(routeLabel)})</span>
            </div>
            <button type="button" class="copilot-inspector-close" onclick="closeProtocolInspector(this)" title="Close Inspector" aria-label="Close Inspector">&times;</button>
          </div>
          <div class="copilot-inspector-grid">
            <div class="copilot-inspector-item">
              <span class="copilot-inspector-label" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('target', { class: 'icon-xs' })} Primary Mechanism / Target</span>
              <span class="copilot-inspector-val highlight">${escapeHtml(formatTargetRole(comp.target, comp))}</span>
            </div>
            <div class="copilot-inspector-item">
              <span class="copilot-inspector-label" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('clock', { class: 'icon-xs' })} Timing & Clearance</span>
              <span class="copilot-inspector-val">${escapeHtml(timingLabel)} • ${escapeHtml(freqLabel)} • ${escapeHtml(routeLabel)}</span>
            </div>
          </div>
          <div class="copilot-inspector-item">
            <span class="copilot-inspector-label" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('lightbulb', { class: 'icon-xs' })} Clinical Rationale & Synergy</span>
            <div class="copilot-inspector-rationale">${renderInlineMarkdown(escapeHtml(comp.rationale || 'Calibrated synergistic protocol addition based on patient biometrics.'))}</div>
          </div>
          ${citationBadgesHtml ? `
            <div class="copilot-inspector-item">
              <span class="copilot-inspector-label" style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('book-open', { class: 'icon-xs' })} Verified Citations & Evidence</span>
              <div class="copilot-inspector-citations">${citationBadgesHtml}</div>
            </div>
          ` : ''}
          <div class="copilot-inspector-actions">
            <button type="button" class="${addBtnCls}" onclick="addSingleCompoundToStack(this.closest('.copilot-protocol-card').querySelector('.copilot-compound-chip.selected'))">
              <span>${addBtnText}</span>
            </button>
          </div>
        `;

        inspector.style.display = 'flex';
      }
      window.inspectProtocolCompound = inspectProtocolCompound;

      function closeProtocolInspector(closeBtn) {
        if (!closeBtn) return;
        const inspector = closeBtn.closest('.copilot-compound-inspector');
        if (inspector) inspector.style.display = 'none';
        const parentCard = closeBtn.closest('.copilot-protocol-card');
        if (parentCard) {
          parentCard.querySelectorAll('.copilot-compound-chip').forEach(c => c.classList.remove('selected'));
        }
      }
      window.closeProtocolInspector = closeProtocolInspector;

      function renderMarkdownLite(rawText) {
        if (!rawText) return '';

        // 1. Strip raw action_card, think, and scratchpad tags completely from text bubble
        let text = String(rawText).replace(/<action_card[\s\S]*?(<\/action_card>|$)/gi, '').trim();
        text = text.replace(/<think[\s\S]*?(<\/think>|$)/gi, '').trim();
        text = text.replace(/<scratchpad[\s\S]*?(<\/scratchpad>|$)/gi, '').trim();
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
          const label = extra ? `${iconSvg('file-text', { class: 'icon-xs icon-teal' })} PMID: ${pmid} (${extra.trim()})` : `${iconSvg('file-text', { class: 'icon-xs icon-teal' })} PMID: ${pmid}`;
          return `<a href="https://pubmed.ncbi.nlm.nih.gov/${pmid}/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge pmid-badge" title="View study on PubMed (PMID: ${pmid})">${label}</a>`;
        });
        text = text.replace(/\[DOI:\s*([^\s\]]+)\]/gi, (match, p1) => `<a href="https://doi.org/${p1}" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge doi-badge" title="View DOI Publication">${iconSvg('globe', { class: 'icon-xs icon-blue' })} DOI: ${p1}</a>`);
        text = text.replace(/\[ChEMBL:\s*([A-Za-z0-9_]+)\]/gi, (match, p1) => `<a href="https://www.ebi.ac.uk/chembl/target_report_card/${p1}/" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge chembl-badge" title="View target in ChEMBL database">${iconSvg('microscope', { class: 'icon-xs icon-purple' })} ChEMBL: ${p1}</a>`);
        text = text.replace(/\[FDA(?:\s+Label)?:\s*([^\]]+)\]/gi, (match, p1) => `<span class="copilot-citation-badge fda-badge" title="FDA Structured Product Labeling Standard">${iconSvg('building-2', { class: 'icon-xs icon-cyan' })} FDA: ${p1}</span>`);
        text = text.replace(/\[NCT:\s*([A-Za-z0-9_]+)\]/gi, (match, p1) => `<a href="https://clinicaltrials.gov/study/${p1}" target="_blank" rel="noopener noreferrer" class="copilot-citation-badge trial-badge" title="View Clinical Trial on ClinicalTrials.gov">${iconSvg('flask-conical', { class: 'icon-xs icon-emerald' })} NCT: ${p1}</a>`);
        text = text.replace(/\[CPIC(?:\s+Guideline)?:\s*([^\]]+)\]/gi, (match, p1) => `<span class="copilot-citation-badge cpic-badge" title="CPIC Clinical Pharmacogenetics Implementation Consortium">${iconSvg('dna', { class: 'icon-xs icon-amber' })} CPIC: ${p1}</span>`);

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
            statusIndicator.innerHTML = `<span style="color: var(--accent-teal); display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs icon-teal' })} Custom AI Key Active</span>`;
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
            statusIndicator.innerHTML = `<span style="color: var(--accent-teal); display:inline-flex; align-items:center; gap:4px;">${iconSvg('activity', { class: 'icon-xs icon-teal' })} Local / Cloud Online</span>`;
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
          'Trace multi-tier biological cascades & organ pathways in Knowledge Graph',
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
          'Explain the downstream AMPK and mitochondrial signaling pathways in the Graph',
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
                const gapText = gaps.length ? ` • <span style="color:#f59e0b; display:inline-flex; align-items:center; gap:3px;">${iconSvg('alert-triangle', { class: 'icon-xs icon-amber' })} ${gaps.length} gaps flagged</span>` : ` • <span style="color:#10b981; display:inline-flex; align-items:center; gap:3px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} Balanced</span>`;
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
          if (copilotExpandIcon) copilotExpandIcon.innerHTML = isExpanded ? iconSvg('minimize-2', { class: 'icon-xs' }) : iconSvg('maximize-2', { class: 'icon-xs' });
          if (copilotExpandText) copilotExpandText.textContent = isExpanded ? 'Standard' : 'Wide';
          copilotExpandBtn.title = isExpanded ? 'Switch to Standard Width' : 'Switch to Wide Width';
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
      window.toggleCopilotDrawer = toggleCopilotDrawer;

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
            showToast(`Switched Copilot Persona to ${btn.textContent.trim()}`, 'bot');
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
                  <span style="display:inline-flex; align-items:center; gap:5px;"><i data-lucide="bot" class="icon-xs icon-cyan"></i> HealthAI Copilot</span>
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

          showToast('Copilot chat and model context reset', 'trash-2');
        });
      }

      function applyCopilotStackDiff(diff, btnElement) {
        if (!diff) return;
        let addedCount = 0;
        let modifiedCount = 0;
        let removedCount = 0;

        // 1. Removals
        const rawRemovals = diff.removals || diff.remove || [];
        if (Array.isArray(rawRemovals) && rawRemovals.length) {
          const toRemove = rawRemovals.map(k => {
            if (typeof k === 'string') return k.toLowerCase().trim().replace(/ /g, '_');
            return String(k.key || k.name || '').toLowerCase().trim().replace(/ /g, '_');
          }).filter(Boolean);

          const initialLen = state.stack.length;
          state.stack = state.stack.filter(s => {
            const sKey = String(s.key || s.name || '').toLowerCase().trim().replace(/ /g, '_');
            return !toRemove.includes(sKey);
          });
          removedCount = initialLen - state.stack.length;
        }

        // 2. Modifications
        const rawMods = diff.modifications || diff.modify || [];
        if (Array.isArray(rawMods) && rawMods.length) {
          rawMods.forEach(m => {
            const mKey = String(m.key || m.name || '').toLowerCase().trim().replace(/ /g, '_');
            const existing = state.stack.find(s => String(s.key || s.name || '').toLowerCase().trim().replace(/ /g, '_') === mKey);
            if (existing) {
              if (m.dose !== undefined) existing.dose = Number(m.dose);
              if (m.unit !== undefined) existing.unit = m.unit;
              if (m.timing !== undefined) existing.timing = m.timing;
              if (m.route !== undefined) existing.route = m.route;
              if (m.frequency !== undefined) existing.frequency = m.frequency;
              modifiedCount++;
            }
          });
        }

        // 3. Additions
        const rawAdditions = diff.additions || diff.add || [];
        if (Array.isArray(rawAdditions) && rawAdditions.length) {
          rawAdditions.forEach(a => {
            let key = '';
            let name = '';
            let dose = null;
            let unit = '';
            let timing = 'morning';
            let frequency = 'daily';
            let route = '';
            let drugClass = '';

            if (typeof a === 'string') {
              const parts = a.split(':');
              key = parts[0].toLowerCase().trim().replace(/ /g, '_');
              name = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
              if (parts[1]) {
                const doseMatch = parts[1].match(/^([\d\.]+)\s*([a-zA-Zμµ]*)$/);
                if (doseMatch) {
                  dose = Number(doseMatch[1]);
                  if (doseMatch[2]) unit = doseMatch[2];
                }
              }
              if (parts[2]) frequency = parts[2];
              if (parts[3]) route = parts[3];
              if (parts[4]) timing = parts[4];
            } else if (typeof a === 'object' && a !== null) {
              key = String(a.key || a.name || '').toLowerCase().trim().replace(/ /g, '_');
              name = a.name || a.key || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
              if (a.dose !== undefined && a.dose !== null && !isNaN(Number(a.dose))) dose = Number(a.dose);
              if (a.unit) unit = a.unit;
              if (a.timing) timing = a.timing;
              if (a.frequency) frequency = a.frequency;
              if (a.route) route = a.route;
              if (a.drug_class || a.target) drugClass = a.drug_class || a.target;
            }

            if (!key) return;

            const cached = _clientCatalogCache[key] || _clientCatalogCache[key.replace(/_/g, '-')];
            const fallback = getDefaultDoseFallback(key);

            if (!timing || (timing === 'morning' && frequency && frequency !== 'daily')) {
              const normF = String(frequency).toLowerCase().replace(/ /g, '_');
              if (normF === 'every_other_day' || normF === 'eod') timing = 'Every Other Day (EOD)';
              else if (normF === 'three_times_weekly' || normF === '3x_weekly') timing = 'Three Times Weekly (Mon / Wed / Fri)';
              else if (normF === 'twice_weekly') timing = 'Twice Weekly (Mon / Thu)';
              else if (normF === 'weekly') timing = 'Weekly';
              else if (normF === 'biweekly') timing = 'Bi-Weekly (Every 2 Weeks)';
              else if (normF === 'as_needed') timing = 'As Needed (PRN)';
            }

            const doseVal = (dose !== null && !isNaN(dose)) ? dose : ((cached && cached.dose !== undefined) ? cached.dose : fallback.dose);
            const unitVal = unit || (cached && cached.unit) || fallback.unit || 'mg';
            const routeVal = route || (cached && (cached.route || cached.default_route)) || fallback.route || 'oral';
            const nameVal = (cached && cached.name) || name || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const drugClassVal = drugClass || (cached && cached.drug_class) || 'Compound';

            const existing = matchCompoundItem(state.stack, key);
            if (existing) {
              existing.dose = doseVal;
              existing.unit = unitVal;
              existing.timing = timing;
              existing.route = routeVal;
              existing.frequency = frequency;
              modifiedCount++;
            } else {
              state.stack.push({
                key: key,
                name: nameVal,
                drug_class: drugClassVal,
                dose: doseVal,
                unit: unitVal,
                frequency: frequency,
                timing: timing,
                route: routeVal
              });
              addedCount++;
            }
          });
        }

        renderStackList();
        if (state.stack.length) {
          if (typeof evaluateStack === 'function') evaluateStack();
        } else {
          if (typeof updateDashboardEmpty === 'function') updateDashboardEmpty();
        }
        if (typeof syncCopilotStackTags === 'function') syncCopilotStackTags();

        // Background batch hydration for any newly added compounds
        const missingBatchKeys = state.stack.filter(s => !_clientCatalogCache[s.key]?.mechanism).map(s => s.key);
        if (missingBatchKeys.length) {
          fetch('/api/compounds/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keys: missingBatchKeys })
          }).then(res => res.ok ? res.json() : {}).then(data => {
            let hasUpdate = false;
            Object.entries(data).forEach(([k, comp]) => {
              _clientCatalogCache[k] = comp;
              if (comp.key) _clientCatalogCache[comp.key] = comp;
              const match = matchCompoundItem(state.stack, k);
              if (match) {
                if (comp.name && (!match.name || match.name === match.key)) {
                  match.name = comp.name;
                  hasUpdate = true;
                }
                if (comp.drug_class && (match.drug_class === 'Compound' || !match.drug_class)) {
                  match.drug_class = comp.drug_class;
                  hasUpdate = true;
                }
              }
            });
            if (hasUpdate) renderStackList();
          }).catch(() => {});
        }

        // Update all chips in active protocol cards
        document.querySelectorAll('.copilot-compound-chip').forEach(chip => {
          const actionEl = chip.querySelector('.copilot-chip-action, .copilot-chip-quick-add-btn');
          if (actionEl) {
            actionEl.className = 'copilot-chip-quick-add-btn in-stack';
            actionEl.innerHTML = `<span style="display:inline-flex; align-items:center; gap:3px;">${iconSvg('check', { class: 'icon-xs' })} In Stack</span>`;
          }
        });

        // Visual feedback on the trigger button
        const targetBtn = btnElement || (typeof event !== 'undefined' && event && event.target ? event.target.closest('.btn-apply-diff') : null);
        if (targetBtn) {
          targetBtn.classList.add('applied');
          targetBtn.innerHTML = `<span>${iconSvg('check', { class: 'icon-xs' })} Protocol Applied to Workbench!</span>`;
        }

        showToast(`Protocol Applied: ${addedCount} added, ${modifiedCount} updated, ${removedCount} removed!`, 'check');
      }
      window.applyCopilotStackDiff = applyCopilotStackDiff;

      function renderQuotaExceededCard(bubbleElement, pendingUserPrompt) {
        if (!bubbleElement) return;
        const currentSavedKey = getUserApiKey();
        bubbleElement.innerHTML = `
          <div class="copilot-quota-card">
            <div class="copilot-quota-header">
              <span>${iconSvg('credit-card', { class: 'icon-sm icon-amber' })}</span>
              <span>Admin Token Budget Exhausted</span>
            </div>
            <p class="copilot-quota-desc">
              The live webpage's OpenRouter token quota has run out. You can continue using all HealthAI Copilot features and protocol optimizations uninterrupted by providing your own OpenRouter (or OpenAI) API key below:
            </p>
            <div class="copilot-quota-input-wrap">
              <div class="copilot-quota-field-row">
                <input type="password" class="copilot-quota-input inline-quota-input" placeholder="sk-or-v1-..." value="${escapeHtml(currentSavedKey)}" />
                <button type="button" class="btn-secondary inline-quota-vis-btn" style="padding: 7px 10px; font-size: 0.76rem;" title="Show/Hide Key">${iconSvg('eye', { class: 'icon-xs' })}</button>
                <button type="button" class="btn-primary inline-quota-save-btn" style="padding: 7px 14px; font-size: 0.76rem; font-weight: 800; white-space: nowrap; background: linear-gradient(135deg, #00f2fe 0%, #4f46e5 100%); border: none; cursor: pointer;">
                  ${iconSvg('save', { class: 'icon-xs' })} Save & Retry
                </button>
              </div>
              <div class="inline-quota-feedback" style="font-size: 0.72rem; min-height: 16px; line-height: 1.35;"></div>
              <div class="copilot-quota-actions">
                <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">${iconSvg('external-link', { class: 'icon-xs' })} Get OpenRouter Key (openrouter.ai/keys) ↗</a>
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
            visBtn.innerHTML = inputEl.type === 'password' ? iconSvg('eye', { class: 'icon-xs' }) : iconSvg('eye-off', { class: 'icon-xs' });
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
                showToast('Custom API key validated & saved!', 'check');
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color: #34d399; display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} Key valid! Resuming copilot...</span>`;
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
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color: #f87171; display:inline-flex; align-items:center; gap:4px;">${iconSvg('alert-triangle', { class: 'icon-xs icon-rose' })} ${escapeHtml(valData.message || 'Key validation failed')}</span>`;
              }
            } catch (err) {
              setUserApiKey(keyVal);
              showToast('Saved custom API key', 'key');
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

      function extractCleanResponseContent(rawText, lastActionCardPayload) {
        if (!rawText && !lastActionCardPayload) {
          return { textHeader: 'Clinical protocol analysis completed.', protocol: null, actionCard: null };
        }

        let text = typeof rawText === 'string' ? rawText.trim() : (rawText ? JSON.stringify(rawText) : '');

        // 1. Strip reasoning / scratchpad / think tags
        text = text.replace(/<think[\s\S]*?(<\/think>|$)/gi, '').trim();
        text = text.replace(/<scratchpad[\s\S]*?(<\/scratchpad>|$)/gi, '').trim();

        // 2. Extract action_card tag or text if present
        let actionCardData = lastActionCardPayload;
        const cardMatch = text.match(/<action_card(?:\s+type=[\'"]?([^\'">\s]+)[\'"]?)?\s*>([\s\S]*?)(?:<\/action_card>|$)/i);
        if (cardMatch) {
          try {
            const cardType = cardMatch[1] || 'stack_diff';
            const parsedBody = JSON.parse(cardMatch[2].trim());
            actionCardData = { type: cardType, payload: parsedBody.payload || parsedBody };
          } catch (e) {}
          text = text.replace(/<action_card[\s\S]*?(<\/action_card>|$)/gi, '').trim();
        } else {
          const actionTextMatch = text.match(/ACTION\s+CARD:\s*(\{[\s\S]*?\})(?:\s*|$)/i);
          if (actionTextMatch) {
            try {
              const parsedBody = JSON.parse(actionTextMatch[1].trim());
              actionCardData = { type: parsedBody.type || 'stack_diff', payload: parsedBody.payload || parsedBody };
            } catch (e) {
              const balanced = extractFirstBalancedJson(actionTextMatch[0]);
              if (balanced) {
                actionCardData = { type: balanced.type || 'stack_diff', payload: balanced.payload || balanced };
              }
            }
            text = text.replace(/ACTION\s+CARD:\s*\{[\s\S]*?\}/gi, '').trim();
          }
        }

        // 3. First check if it's a protocol proposal with compounds
        const actionPayload = actionCardData ? (actionCardData.payload || actionCardData) : null;
        const proto = parseProtocolData(text, actionPayload);
        if (proto && proto.compounds && proto.compounds.length > 0) {
          return { textHeader: '', protocol: proto, actionCard: null };
        }

        // 4. If not a protocol proposal, try to parse JSON blocks / structured properties
        let cleanJsonStr = text.replace(/^```json\s*/i, '').replace(/^```\s*/, '').replace(/```\s*$/i, '').trim();
        if (cleanJsonStr.startsWith('"') && cleanJsonStr.endsWith('"')) {
          cleanJsonStr = cleanJsonStr.slice(1, -1).replace(/\\"/g, '"').replace(/\\n/g, '\n');
        }

        let parsed = null;
        try {
          parsed = JSON.parse(cleanJsonStr);
        } catch (e) {
          parsed = extractFirstBalancedJson(cleanJsonStr);
        }

        if (parsed) {
          if (Array.isArray(parsed.blocks)) {
            const textParts = [];
            parsed.blocks.forEach(b => {
              if (b && b.type === 'text' && b.content) {
                textParts.push(b.content);
              } else if (b && typeof b.content === 'string' && b.content) {
                textParts.push(b.content);
              }
            });
            if (textParts.length > 0) {
              return { textHeader: textParts.join('\n\n'), protocol: null, actionCard: actionCardData };
            }
          }
          if (typeof parsed.content === 'string' && parsed.content) {
            return { textHeader: parsed.content, protocol: null, actionCard: actionCardData };
          }
          if (typeof parsed.response === 'string' && parsed.response) {
            return { textHeader: parsed.response, protocol: null, actionCard: actionCardData };
          }
          if (typeof parsed.summary === 'string' && parsed.summary) {
            return { textHeader: parsed.summary, protocol: null, actionCard: actionCardData };
          }
          if (typeof parsed.message === 'string' && parsed.message) {
            return { textHeader: parsed.message, protocol: null, actionCard: actionCardData };
          }
          if (typeof parsed.text === 'string' && parsed.text) {
            return { textHeader: parsed.text, protocol: null, actionCard: actionCardData };
          }
        }

        // 5. Fallback regex extraction if raw JSON structure failed to parse directly
        const trimmed = text.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
          const textMatches = [...text.matchAll(/"(?:type"\s*:\s*"text"\s*,\s*)?content"\s*:\s*"([^]*?)"/g)];
          if (textMatches.length > 0) {
            const extracted = textMatches.map(m => m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')).join('\n\n');
            return { textHeader: extracted, protocol: null, actionCard: actionCardData };
          }
        }

        // 6. Regular markdown/text
        return { textHeader: text, protocol: null, actionCard: actionCardData };
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
            <span style="display:inline-flex; align-items:center; gap:5px;"><i data-lucide="bot" class="icon-xs icon-cyan"></i> HealthAI ${copilotState.persona.toUpperCase()}</span>
            <span class="copilot-stream-status" style="color: var(--accent-cyan); display: inline-flex; align-items: center; gap: 4px;">
              <span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Initializing...
            </span>
          </div>
          <div class="copilot-thought-box" style="display: none;">
            <div class="copilot-thought-header">
              <div class="copilot-thought-header-left">
                <span class="copilot-thought-icon"><i data-lucide="brain" class="icon-xs icon-cyan"></i></span>
                <span class="copilot-thought-title">Clinical Reasoning & Grounding</span>
                <span class="copilot-thought-badge live"><span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span> Thinking</span>
              </div>
              <div class="copilot-thought-header-right">
                <span class="copilot-thought-meta">0.0s</span>
              </div>
            </div>
            <div class="copilot-thought-activity-bar" style="display: none;">
              <div class="copilot-thought-activity-step">
                <span class="copilot-activity-spinner"></span>
                <span class="copilot-activity-text">Deliberating & Traversing Knowledge Graph...</span>
              </div>
              <div class="copilot-completed-tools-list"></div>
            </div>
            <div class="copilot-thought-flow-container">
              <div class="copilot-thought-flow-inner">
                <span class="copilot-thought-flow-text"></span>
                <span class="copilot-thought-flow-cursor"></span>
              </div>
            </div>
          </div>
          <div class="chat-msg-bubble">
            <div class="typing-indicator-wrap">
              <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
              <span style="color: var(--text-muted); font-style: italic; font-size: 0.85rem;">Grounding against Pharmacokinetics...</span>
            </div>
          </div>
          <div class="action-cards-wrap" style="display: flex; flex-direction: column; gap: 8px;"></div>
        `;
        copilotChatContainer.appendChild(assistantMsgEl);
        copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;

        const bubble = assistantMsgEl.querySelector('.chat-msg-bubble');
        const actionCardsWrap = assistantMsgEl.querySelector('.action-cards-wrap');
        const headerStatus = assistantMsgEl.querySelector('.copilot-stream-status');
        const thoughtBox = assistantMsgEl.querySelector('.copilot-thought-box');
        const thoughtBadge = assistantMsgEl.querySelector('.copilot-thought-badge');
        const thoughtMeta = assistantMsgEl.querySelector('.copilot-thought-meta');
        const thoughtFlowText = assistantMsgEl.querySelector('.copilot-thought-flow-text');
        const thoughtActivityBar = assistantMsgEl.querySelector('.copilot-thought-activity-bar');
        const thoughtActivityText = assistantMsgEl.querySelector('.copilot-activity-text');
        const thoughtCompletedTools = assistantMsgEl.querySelector('.copilot-completed-tools-list');

        function formatToolActivity(toolName, args) {
          args = args || {};
          switch (toolName) {
            case 'search_pubmed_titles':
            case 'search_paper_titles':
            case 'search_literature_titles':
            case 'search_pubmed':
            case 'search_biomedical_literature':
            case 'search_pubmed_literature':
            case 'search_literature_for_claim':
            case 'search_evidence_for_claim':
            case 'get_claim_citations':
              return { icon: 'search', title: 'Searching PubMed Literature', label: args.query ? `"${args.query}"` : (args.claim ? `"${args.claim}"` : 'biomedical literature') };
            case 'read_paper_abstract':
            case 'fetch_paper_abstract':
            case 'get_paper_abstract':
            case 'read_study':
            case 'get_citation_details':
            case 'get_citation_metadata':
              return { icon: 'file-text', title: 'Reading Paper Abstract', label: args.pmid ? `PMID: ${args.pmid}` : 'study abstract' };
            case 'read_paper_section':
            case 'fetch_paper_full_text_section':
            case 'read_full_text_section':
              return { icon: 'book-open', title: 'Reading Full Text Section', label: args.section || args.section_requested || (args.pmid ? `PMID: ${args.pmid}` : 'study section') };
            case 'search_within_paper':
            case 'search_in_paper':
            case 'search_paper_passages':
              return { icon: 'file-text', title: 'Searching Within Full Paper', label: args.query ? `"${args.query}"` : (args.pmid ? `PMID: ${args.pmid}` : 'paper text') };
            case 'find_similar_papers':
            case 'find_similar_studies':
            case 'find_similar_citations':
              return { icon: 'layers', title: 'Finding Similar Studies', label: args.pmid ? `PMID: ${args.pmid}` : 'vector graph' };
            case 'search_cached_papers_semantic':
            case 'search_citations_semantic':
              return { icon: 'database', title: 'Semantic Citation Search', label: args.query ? `"${args.query}"` : 'local vector cache' };
            case 'search_clinical_trials':
            case 'search_trials':
              return { icon: 'activity', title: 'Querying Clinical Trials', label: args.query || args.condition || args.intervention || 'ClinicalTrials.gov' };
            case 'get_compound_details':
            case 'get_compound_info':
              return { icon: 'info', title: 'Inspecting Pharmacology', label: args.compound_key || args.name || 'pharmacokinetics' };
            case 'subagent_delegation':
              return { icon: 'bot', title: 'Subagent Data Extraction', label: 'context optimization' };
            case 'simulate_pkpd':
              return { icon: 'sliders', title: 'Simulating PK/PD Kinetics', label: args.compound_key ? `${args.compound_key} (${args.dose_mg || 100}mg)` : 'steady-state model' };
            case 'calculate_individualized_dosing':
              return { icon: 'scale', title: 'Calculating Scaled Dosing', label: args.compound_key || 'clearance' };
            case 'check_cyp450_conflicts':
            case 'analyze_stack_conflicts':
              return { icon: 'zap', title: 'Auditing CYP450 Collisions', label: 'hepatic clearance & DDI' };
            case 'query_pathway_cascade':
            case 'trace_mechanism_pathway':
              return { icon: 'dna', title: 'Tracing Biological Pathway', label: args.target_id || args.source || 'signal cascade' };
            case 'find_candidate_pairings':
            case 'get_evidence_based_recommendations':
              return { icon: 'target', title: 'Discovering Synergies', label: args.goal || 'evidence pairings' };
            case 'evaluate_synergies':
            case 'query_compound_associations':
              return { icon: 'link', title: 'Evaluating Receptor Synergy', label: 'Loewe & Bliss matrices' };
            case 'execute_read_only_cypher':
            case 'query_cypher':
              return { icon: 'network', title: 'Querying Graph Database', label: '3-hop graph traversal' };
            case 'query_graphrag_subgraph':
            case 'hybrid_rag_search':
              return { icon: 'microscope', title: 'Traversing GraphRAG', label: args.query || 'knowledge triples' };
            case 'build_stack_from_scratch':
            case 'propose_stack_from_scratch':
            case 'create_protocol_from_scratch':
              return { icon: 'sparkles', title: 'Architecting Stack Blueprint', label: args.goal ? args.goal.replace(/_/g, ' ') : 'evidence synthesis' };
            case 'simulate_stack_diff':
            case 'propose_stack_diff':
              return { icon: 'git-merge', title: 'Simulating Stack Modifications', label: 'validating interactions' };
            default:
              return { icon: 'wrench', title: `Executing ${toolName.replace(/_/g, ' ')}`, label: '' };
          }
        }

        function updateProtocolLoadingProgress(bubbleEl, stage, detailText) {
          if (!bubbleEl) return;
          const loadingContainer = bubbleEl.querySelector('.copilot-protocol-loading');
          if (!loadingContainer) return;

          // Strictly monotonic stage progression: never step backwards
          if (stage && Number.isInteger(stage) && stage > currentProtocolStage) {
            currentProtocolStage = stage;
          }
          const effectiveStage = currentProtocolStage || 1;

          const step1 = loadingContainer.querySelector('.copilot-loading-step[data-step="1"]');
          const step2 = loadingContainer.querySelector('.copilot-loading-step[data-step="2"]');
          const step3 = loadingContainer.querySelector('.copilot-loading-step[data-step="3"]');
          const subtextEl = loadingContainer.querySelector('.copilot-loading-substatus-text');

          if (effectiveStage === 1) {
            if (step1) {
              step1.className = 'copilot-loading-step active';
              const badge = step1.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '<span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span>';
            }
            if (step2) {
              step2.className = 'copilot-loading-step';
              const badge = step2.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '';
            }
            if (step3) {
              step3.className = 'copilot-loading-step';
              const badge = step3.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '';
            }
          } else if (effectiveStage === 2) {
            if (step1) {
              step1.className = 'copilot-loading-step completed';
              const badge = step1.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
            if (step2) {
              step2.className = 'copilot-loading-step active';
              const badge = step2.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '<span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span>';
            }
            if (step3) {
              step3.className = 'copilot-loading-step';
              const badge = step3.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '';
            }
          } else if (effectiveStage === 3) {
            if (step1) {
              step1.className = 'copilot-loading-step completed';
              const badge = step1.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
            if (step2) {
              step2.className = 'copilot-loading-step completed';
              const badge = step2.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
            if (step3) {
              step3.className = 'copilot-loading-step active';
              const badge = step3.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = '<span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span>';
            }
          } else if (effectiveStage >= 4) {
            if (step1) {
              step1.className = 'copilot-loading-step completed';
              const badge = step1.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
            if (step2) {
              step2.className = 'copilot-loading-step completed';
              const badge = step2.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
            if (step3) {
              step3.className = 'copilot-loading-step completed';
              const badge = step3.querySelector('.copilot-step-badge');
              if (badge) badge.innerHTML = `<span class="copilot-step-check">${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
            }
          }

          if (detailText && subtextEl) {
            subtextEl.textContent = detailText;
          }
        }

        copilotState.isStreaming = true;
        if (copilotSendBtn) copilotSendBtn.disabled = true;

        const rawPromptStr = typeof userPromptText === 'string' ? userPromptText : '';
        const cleanPrompt = rawPromptStr.replace(/^[^\w\s]+/u, '').trim().toLowerCase();
        const displayHtmlStr = typeof userDisplayHtml === 'string' ? userDisplayHtml : '';

        const isExplicitStackBuild = (
          displayHtmlStr.includes('Build') ||
          displayHtmlStr.includes('AI Stack Builder') ||
          displayHtmlStr.includes('Protocol') ||
          cleanPrompt.startsWith('build') ||
          cleanPrompt.startsWith('please build') ||
          cleanPrompt.startsWith('generate') ||
          cleanPrompt.startsWith('create') ||
          cleanPrompt.startsWith('formulate') ||
          cleanPrompt.startsWith('design') ||
          cleanPrompt.includes('from scratch') ||
          cleanPrompt.includes('stack from scratch') ||
          cleanPrompt.includes('protocol from scratch') ||
          rawPromptStr.includes('build_stack_from_scratch')
        );
        const isProtocolMode = isExplicitStackBuild;
        let currentProtocolStage = 1;

        if (isProtocolMode) {
          bubble.innerHTML = `
            <div class="copilot-protocol-loading">
              <div class="copilot-loading-header">
                <span class="copilot-loading-spinner"></span>
                <span>${iconSvg('zap', { class: 'icon-xs icon-cyan' })} Formulating Precision Protocol Architecture...</span>
              </div>
              <div class="copilot-loading-shimmer-bar"></div>
              <div class="copilot-loading-steps">
                <div class="copilot-loading-step active" data-step="1">
                  <span>${iconSvg('dna', { class: 'icon-xs icon-cyan' })}</span> <span>Calibrating receptor kinetics & patient clearance</span>
                  <span class="copilot-step-badge"><span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span></span>
                </div>
                <div class="copilot-loading-step" data-step="2">
                  <span>${iconSvg('clock', { class: 'icon-xs icon-teal' })}</span> <span>Optimizing circadian administration windows</span>
                  <span class="copilot-step-badge"></span>
                </div>
                <div class="copilot-loading-step" data-step="3">
                  <span>${iconSvg('shield-check', { class: 'icon-xs icon-emerald' })}</span> <span>Grounding multi-organ protection & verified evidence</span>
                  <span class="copilot-step-badge"></span>
                </div>
              </div>
              <div class="copilot-loading-substatus">
                <span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span>
                <span class="copilot-loading-substatus-text">Reasoning through biological pathways & molecular targets...</span>
              </div>
            </div>
          `;
        }

        const compoundKeys = (state.stack || []).map(s => s.key || s.name || s.id).filter(Boolean);
        const biometrics = getBiometricsPayload();

        copilotState.abortController = new AbortController();
        let accumulatedContent = '';
        let accumulatedReasoning = '';
        let executedToolCount = 0;
        let lastActionCardPayload = null;
        let reasoningStartTime = Date.now();
        let reasoningCount = 0;
        let reasoningCompleted = false;
        let currentEvent = 'delta';
        let quotaExceededTriggered = false;

        let userHasScrolledUp = false;
        let isAutoScrolling = false;

        const onUserScroll = () => {
          if (!copilotChatContainer || isAutoScrolling) return;
          const distanceFromBottom = copilotChatContainer.scrollHeight - copilotChatContainer.scrollTop - copilotChatContainer.clientHeight;
          if (distanceFromBottom > 40) {
            userHasScrolledUp = true;
          } else {
            userHasScrolledUp = false;
          }
        };

        if (copilotChatContainer) {
          copilotChatContainer.addEventListener('scroll', onUserScroll, { passive: true });
        }

        const thoughtTimerInterval = setInterval(() => {
          if (!reasoningCompleted) {
            if (thoughtMeta) {
              const elapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
              thoughtMeta.textContent = `${elapsed}s`;
            }
            autoScrollChatIfNearBottom();
          }
        }, 100);

        function autoScrollChatIfNearBottom(force = false) {
          if (!copilotChatContainer) return;
          if (userHasScrolledUp && !force) return;
          isAutoScrolling = true;
          copilotChatContainer.scrollTop = copilotChatContainer.scrollHeight;
          setTimeout(() => { isAutoScrolling = false; }, 50);
        }

        try {
          const depthEl = document.getElementById('copilot-research-depth');
          const maxSteps = depthEl ? parseInt(depthEl.value) : 8;
          
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
              max_exploration_steps: maxSteps,
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
                } else if (currentEvent === 'tool_call') {
                  const toolObj = typeof dataVal === 'string' ? JSON.parse(dataVal) : dataVal;
                  const toolInfo = formatToolActivity(toolObj.tool, toolObj.arguments);
                  executedToolCount++;

                  if (thoughtBox) {
                    thoughtBox.style.display = 'block';
                    thoughtBox.classList.remove('reasoning-done');
                  }
                  if (thoughtActivityBar) {
                    thoughtActivityBar.style.display = 'flex';
                  }
                  if (thoughtActivityText) {
                    thoughtActivityText.innerHTML = `${iconSvg(toolInfo.icon, {class: 'icon-xs'})} <span>${escapeHtml(toolInfo.title)}</span> ${toolInfo.label ? `<span style="color: #94a3b8; font-weight: normal;">— ${escapeHtml(toolInfo.label)}</span>` : ''}`;
                  }
                  if (headerStatus) {
                    headerStatus.innerHTML = `<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> ${iconSvg(toolInfo.icon, {class: 'icon-xs'})} ${escapeHtml(toolInfo.title)}...`;
                    headerStatus.style.color = 'var(--accent-cyan)';
                  }
                  if (isProtocolMode) {
                    updateProtocolLoadingProgress(bubble, currentProtocolStage, `Traversing knowledge graph: ${toolInfo.title}...`);
                  }
                  if (window.lucide && window.lucide.createIcons) {
                    window.lucide.createIcons();
                  }
                  autoScrollChatIfNearBottom();
                } else if (currentEvent === 'tool_result') {
                  const resObj = typeof dataVal === 'string' ? JSON.parse(dataVal) : dataVal;
                  const toolInfo = formatToolActivity(resObj.tool, {});

                  if (thoughtCompletedTools) {
                    const cleanLabel = toolInfo.title.replace(/^Searching\s+|^Reading\s+|^Simulating\s+|^Auditing\s+|^Tracing\s+/, '');
                    const chip = document.createElement('span');
                    chip.className = 'copilot-tool-chip success';
                    chip.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg(toolInfo.icon, { class: 'icon-xs' })} <span>${escapeHtml(cleanLabel)}</span> ${iconSvg('check', { class: 'icon-xs icon-emerald' })}</span>`;
                    chip.title = resObj.summary || toolInfo.title;
                    thoughtCompletedTools.appendChild(chip);
                  }
                  if (thoughtActivityText) {
                    thoughtActivityText.innerHTML = `<span style="display:inline-flex; align-items:center; gap:5px;">${iconSvg('dna', { class: 'icon-xs icon-cyan' })} <span>Grounded & Traversing Knowledge Graph...</span></span>`;
                  }
                  if (isProtocolMode) {
                    updateProtocolLoadingProgress(bubble, currentProtocolStage, `Grounded graph observation: ${toolInfo.title}`);
                  }
                  if (window.lucide && window.lucide.createIcons) {
                    window.lucide.createIcons();
                  }
                  autoScrollChatIfNearBottom();
                } else if (currentEvent === 'delta') {
                  const deltaStr = (typeof dataVal === 'string' ? dataVal : JSON.stringify(dataVal));
                  accumulatedContent += deltaStr;

                  if (accumulatedContent.trim()) {
                    if (!reasoningCompleted && accumulatedReasoning) {
                      reasoningCompleted = true;
                      if (thoughtBadge) {
                        const finalElapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
                        const toolSuffix = executedToolCount > 0 ? ` • ${executedToolCount} tool${executedToolCount > 1 ? 's' : ''}` : '';
                        thoughtBadge.className = 'copilot-thought-badge';
                        thoughtBadge.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} Reasoned in ${finalElapsed}s${toolSuffix}</span>`;
                      }
                      if (thoughtBox) {
                        thoughtBox.classList.add('reasoning-done');
                      }
                    }
                  }

                  // For protocol building, update dynamic loading step progression and live status subtext
                  if (isProtocolMode && bubble) {
                    const compCount = (accumulatedContent.match(/"(?:key|name)"\s*:\s*"[^"]+"/g) || []).length;
                    const isStep3 = (
                      accumulatedContent.includes('"safety_notes"') ||
                      accumulatedContent.includes('"sources"') ||
                      accumulatedContent.includes('"citations"') ||
                      accumulatedContent.includes('"diff"') ||
                      accumulatedContent.includes('<action_card') ||
                      accumulatedContent.length > 1800
                    );

                    if (isStep3) {
                      currentProtocolStage = 3;
                      updateProtocolLoadingProgress(bubble, 3, 'Validating organ shielding, evidence citations & diff card...');
                      if (headerStatus) {
                        headerStatus.innerHTML = `<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> <span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('shield-check', { class: 'icon-xs icon-teal' })} Grounding evidence & safety...</span>`;
                        headerStatus.style.color = 'var(--accent-teal)';
                      }
                    } else {
                      currentProtocolStage = 2;
                      const compSuffix = compCount > 0 ? ` (${compCount} compound${compCount > 1 ? 's' : ''} structured)` : '';
                      updateProtocolLoadingProgress(bubble, 2, `Synthesizing compound dosages & circadian schedule${compSuffix}...`);
                      if (headerStatus) {
                        headerStatus.innerHTML = `<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> <span style="display:inline-flex; align-items:center; gap:4px;">${iconSvg('clock', { class: 'icon-xs icon-cyan' })} Circadian schedule${compSuffix}...</span>`;
                        headerStatus.style.color = 'var(--accent-cyan)';
                      }
                    }
                  } else if (headerStatus && !isProtocolMode) {
                    headerStatus.innerHTML = '<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Formulating clinical response...';
                    headerStatus.style.color = 'var(--accent-cyan)';
                  }
                  autoScrollChatIfNearBottom();
                } else if (currentEvent === 'reasoning') {
                  const reasoningText = typeof dataVal === 'string' ? dataVal : JSON.stringify(dataVal);
                  accumulatedReasoning += reasoningText;
                  reasoningCount++;

                  if (thoughtBox) {
                    thoughtBox.style.display = 'block';
                    thoughtBox.classList.remove('reasoning-done');
                    if (thoughtBadge) {
                      thoughtBadge.className = 'copilot-thought-badge live';
                      thoughtBadge.innerHTML = '<span class="copilot-pulse-dot" style="width: 5px; height: 5px;"></span> Thinking';
                    }
                    if (thoughtFlowText) {
                      const cleaned = accumulatedReasoning.replace(/\s+/g, ' ').trim();
                      const words = cleaned.split(' ');
                      const recentWords = words.length > 16 ? '… ' + words.slice(-16).join(' ') : cleaned;
                      thoughtFlowText.textContent = recentWords;
                    }
                    if (thoughtMeta) {
                      const elapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
                      thoughtMeta.textContent = `${elapsed}s`;
                    }
                  }

                  if (isProtocolMode && currentProtocolStage === 1) {
                    updateProtocolLoadingProgress(bubble, 1, 'Reasoning through biological pathways & molecular targets...');
                  }

                  if ((!accumulatedContent || !accumulatedContent.trim()) && headerStatus) {
                    headerStatus.innerHTML = '<span class="copilot-pulse-dot" style="width: 6px; height: 6px;"></span> Deep Graph & PK/PD Reasoning...';
                    headerStatus.style.color = 'var(--accent-cyan)';
                  }
                  autoScrollChatIfNearBottom();
                } else if (currentEvent === 'action_card') {
                  try {
                    const cardObj = typeof dataVal === 'string' ? JSON.parse(dataVal) : dataVal;
                    lastActionCardPayload = cardObj.payload || cardObj;
                    if (isProtocolMode) {
                      currentProtocolStage = 3;
                      updateProtocolLoadingProgress(bubble, 3, 'Calibrated stack diff action card generated');
                    }
                    autoScrollChatIfNearBottom();
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

          if (accumulatedReasoning) {
            reasoningCompleted = true;
            if (thoughtBadge) {
              const finalElapsed = ((Date.now() - reasoningStartTime) / 1000).toFixed(1);
              thoughtBadge.className = 'copilot-thought-badge';
              thoughtBadge.innerHTML = `${iconSvg('check', { class: 'icon-xs icon-emerald' })} Reasoned in ${finalElapsed}s`;
            }
            if (thoughtBox) {
              thoughtBox.classList.add('reasoning-done');
            }
          }

          // Fallback or final render of protocol card / markdown
          if (isProtocolMode && bubble) {
            updateProtocolLoadingProgress(bubble, 4, 'Finalizing precision protocol architecture...');
          }

          if (!accumulatedContent || !accumulatedContent.trim()) {
            const hasActionCards = lastActionCardPayload || (actionCardsWrap && actionCardsWrap.children.length > 0);
            if (hasActionCards) {
              accumulatedContent = "### Protocol Architecture Formulated\n\nClinical protocol calibrated against patient biometrics and pharmacokinetic clearance. Review the proposed adjustments in the protocol canvas below and click to apply them directly to your active workbench stack:";
            } else {
              accumulatedContent = "Clinical protocol analysis completed.";
            }
          }

          // Render final parsed response cleanly without exposing JSON beforehand
          const resObj = extractCleanResponseContent(accumulatedContent, lastActionCardPayload);

          if (bubble) {
            if (resObj.protocol) {
              const headerHtml = resObj.textHeader ? (renderMarkdownLite(resObj.textHeader) + '<br>') : '';
              bubble.innerHTML = headerHtml + renderInteractiveProtocolCard(resObj.protocol);
              if (actionCardsWrap) actionCardsWrap.innerHTML = '';
            } else {
              const contentToRender = resObj.textHeader || accumulatedContent;
              bubble.innerHTML = renderMarkdownLite(contentToRender);
              if (actionCardsWrap) {
                actionCardsWrap.innerHTML = '';
                if (resObj.actionCard) {
                  renderActionCardInChat(actionCardsWrap, resObj.actionCard);
                }
              }
            }
          }

          // Save completed assistant message to history (including action card payload for cumulative multi-turn tracking)
          const finalActionPayload = resObj.actionCard ? (resObj.actionCard.payload || resObj.actionCard) : lastActionCardPayload;
          const finalMsgContent = (finalActionPayload && !accumulatedContent.includes('<action_card'))
            ? `${accumulatedContent}\n\n<action_card type="stack_diff">${JSON.stringify(finalActionPayload)}</action_card>`
            : accumulatedContent;
          copilotState.messages.push({ role: 'assistant', content: finalMsgContent });

          // Update header status
          if (headerStatus) {
            headerStatus.innerHTML = '• Ready';
            headerStatus.style.color = 'var(--accent-teal)';
          }
          autoScrollChatIfNearBottom();

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
                  <strong style="color: #f87171; display:inline-flex; align-items:center; gap:4px;">${iconSvg('alert-triangle', { class: 'icon-xs icon-rose' })} Copilot Notice:</strong>
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
          if (thoughtTimerInterval) clearInterval(thoughtTimerInterval);
          if (copilotChatContainer && typeof onUserScroll === 'function') {
            copilotChatContainer.removeEventListener('scroll', onUserScroll);
          }
          copilotState.isStreaming = false;
          if (copilotSendBtn) copilotSendBtn.disabled = false;
          copilotState.abortController = null;
        }
      }

      function renderActionCardInChat(container, cardObj) {
        if (!container || !cardObj) return;
        const payload = cardObj.payload || cardObj;
        const cardType = cardObj.type || payload.action_card;

        // Check if parent message bubble can be enriched directly into an interactive protocol card
        const assistantMsgEl = container.closest('.chat-msg.assistant');
        const bubbleEl = assistantMsgEl ? assistantMsgEl.querySelector('.chat-msg-bubble') : null;
        if (bubbleEl && bubbleEl.textContent) {
          const protoData = parseProtocolData(bubbleEl.textContent, payload);
          if (protoData && protoData.compounds && protoData.compounds.length > 0) {
            bubbleEl.innerHTML = renderInteractiveProtocolCard(protoData);
            container.innerHTML = '';
            return;
          }
        }

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
              <span>${iconSvg('zap', { class: 'icon-xs icon-cyan' })} AI Proposed Protocol Modifications</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
              ${rowsHtml}
            </div>
            <button class="btn-apply-diff" onclick="applyCopilotStackDiff(${diffJsonEscaped})">
              <span>${iconSvg('zap', { class: 'icon-xs icon-cyan' })} Apply Changes to Workbench Stack</span>
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
          if (builderBioToggleIcon) builderBioToggleIcon.innerHTML = isHidden ? iconSvg('chevron-up', { class: 'icon-xs' }) : iconSvg('pencil', { class: 'icon-xs' });
        });
      }

      if (copilotBioToggleBtn && copilotBioDrawer) {
        copilotBioToggleBtn.addEventListener('click', () => {
          const isHidden = copilotBioDrawer.style.display === 'none';
          copilotBioDrawer.style.display = isHidden ? 'flex' : 'none';
          copilotBioToggleBtn.classList.toggle('active', isHidden);
          if (copilotBioToggleIcon) copilotBioToggleIcon.innerHTML = isHidden ? iconSvg('chevron-up', { class: 'icon-xs' }) : iconSvg('pencil', { class: 'icon-xs' });
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
      window.openAiStackBuilderModal = openAiStackBuilderModal;

      function closeAiStackBuilderModal() {
        if (!aiBuilderModal) return;
        aiBuilderModal.classList.remove('open');
      }
      window.closeAiStackBuilderModal = closeAiStackBuilderModal;

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
        gut_microbiome: 'Gut Microbiome & Intestinal Barrier',
        immune_defense: 'Immune Defense & Cellular Resilience',
        hair_skin_derm: 'Dermatology & Hair Follicle Health',
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

        const promptText = `Build a comprehensive, synergistic ${title} protocol from scratch. Include exact circadian timing allocations, pharmacokinetic rationales, organ protection co-factors, and provide the action card to apply the entire stack.`;
        const displayHtml = `<span style="display:inline-flex; align-items:center; gap:5px;"><i data-lucide="sparkles" class="icon-xs icon-cyan"></i> <span><strong>Build ${escapeHtml(title)}</strong> from scratch</span></span>`;
        sendCopilotMessage(promptText, displayHtml);
        showToast(`AI Architect: Designing ${title} from scratch...`, 'sparkles');
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

          const builderDepthEl = document.getElementById('builder-research-depth');
          const copilotDepthEl = document.getElementById('copilot-research-depth');
          if (builderDepthEl && copilotDepthEl) {
            copilotDepthEl.value = builderDepthEl.value;
            copilotDepthEl.dispatchEvent(new Event('input'));
          }

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

          let promptParts = [`Please build a personalized ${title} protocol from scratch.`];
          
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
          if (builderDepthEl && builderDepthEl.value) {
            let d = parseInt(builderDepthEl.value);
            let dLbl = d <= 4 ? 'Quick' : (d <= 8 ? 'Standard' : (d <= 12 ? 'Deep' : 'Architect'));
            tagPills.push(`<span style="background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.3); border-radius: 4px; padding: 1px 5px; color: #a78bfa;">Depth: ${dLbl} (${d})</span>`);
          }

          const displayHtml = `
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <span style="display:inline-flex; align-items:center; gap:5px;"><i data-lucide="sparkles" class="icon-xs icon-cyan"></i> <strong>Build ${escapeHtml(title)} Protocol</strong></span>
              ${tagPills.length ? `<div style="display: flex; flex-wrap: wrap; gap: 4px; font-size: 0.72rem; color: var(--text-muted);">${tagPills.join('')}</div>` : ''}
            </div>
          `;

          sendCopilotMessage(promptParts.join(' '), displayHtml);
          showToast(`AI Architect: Generating ${title} protocol...`, 'sparkles');
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
          toggleKeyVisBtn.innerHTML = userApiKeyInput.type === 'password' ? iconSvg('eye', { class: 'icon-xs' }) : iconSvg('eye-off', { class: 'icon-xs' });
        });
      }

      if (saveApiKeyBtn && userApiKeyInput) {
        saveApiKeyBtn.addEventListener('click', () => {
          const val = userApiKeyInput.value.trim();
          if (val) {
            setUserApiKey(val);
            showToast('Custom OpenRouter / OpenAI API Key Saved!', 'key');
            if (keyValidationFeedback) {
              keyValidationFeedback.innerHTML = `<span style="color: #34d399; display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} Key saved to browser storage. Active for all AI requests.</span>`;
            }
            setTimeout(closeApiKeyModal, 450);
          } else {
            clearUserApiKey();
            showToast('Reverted to Admin default API key', 'info');
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
          showToast('Custom API key removed', 'trash-2');
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
                keyValidationFeedback.innerHTML = `<span style="color: #34d399; display:inline-flex; align-items:center; gap:4px;">${iconSvg('check', { class: 'icon-xs icon-emerald' })} ${escapeHtml(data.message || 'Key valid!')} (${escapeHtml(data.provider || 'AI')})</span>`;
              }
            } else {
              if (keyValidationFeedback) {
                keyValidationFeedback.innerHTML = `<span style="color: #f87171; display:inline-flex; align-items:center; gap:4px;">${iconSvg('alert-triangle', { class: 'icon-xs icon-rose' })} ${escapeHtml(data.message || 'Validation failed')}</span>`;
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

      // ==========================================================================
      // EMBEDDED BIOLOGICAL KNOWLEDGE GRAPH ENGINE
      // ==========================================================================
      const embeddedNodeColors = {
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

      const embeddedTierNames = {
        0: 'Compound / Ligand',
        1: 'Molecular Target',
        2: 'Signaling Cascade',
        3: 'Organ Physiology',
        4: 'Clinical Biomarker',
        5: 'Clinical Outcome'
      };

      const embeddedGraphState = {
        cy: null,
        data: { nodes: [], edges: [], cascade_simulation: {}, combined_effects: {} },
        selectedNode: null,
        selectedTab: 'overview',
        layout: 'tier_flow',
        timeline: 'steady_state',
        filterConvergence: false,
        searchTerm: '',
        simulating: false,
        isLoading: false,
        loadRequestId: 0,
        initialized: false,
      };

      function colorForEmbeddedNode(nodeType) {
        return embeddedNodeColors[nodeType] || embeddedNodeColors.default;
      }

      function getEmbeddedNodeLabel(node) {
        return node.label || node.id;
      }

      window.switchToGraphTab = function(focusNodeId, pathNodeIds) {
        const tabBtn = document.getElementById('tab-btn-graph') || document.querySelector('[data-tab="graph-tab"]');
        if (tabBtn) {
          tabBtn.click();
        } else {
          document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
          const targetPane = document.getElementById('graph-tab');
          if (targetPane) targetPane.style.display = 'block';
          state.activeTab = 'graph-tab';
        }

        initOrRenderEmbeddedGraph(false, () => {
          if (focusNodeId && embeddedGraphState.cy) {
            focusAndSelectEmbeddedNode(focusNodeId, pathNodeIds);
          }
        });
      };

      const headerGraphBtn = document.getElementById('header-graph-btn');
      if (headerGraphBtn) {
        headerGraphBtn.addEventListener('click', () => window.switchToGraphTab());
      }

      async function syncGraphData(shouldRender = false, callback = null) {
        const reqId = ++embeddedGraphState.loadRequestId;
        const stackSpecs = (state.stack || []).map(c => {
          const u = (c.unit || 'mg').replace('μg', 'ug');
          const freq = c.frequency || 'daily';
          const route = c.route || 'oral';
          return `${encodeURIComponent(c.key)}:${c.dose}${u}:${freq}:${route}`;
        });

        const tabGraphBadge = document.getElementById('tab-graph-badge');
        const statGraphNodes = document.getElementById('stat-graph-nodes');
        const cascadeChipsWrap = document.getElementById('embedded-cascade-chips');

        if (!stackSpecs.length) {
          embeddedGraphState.data = { nodes: [], edges: [], cascade_simulation: {}, combined_effects: {} };
          if (tabGraphBadge) tabGraphBadge.textContent = '0 Nodes';
          if (statGraphNodes) statGraphNodes.textContent = '0 Nodes';
          if (cascadeChipsWrap) {
            cascadeChipsWrap.innerHTML = '<span class="cascade-badge">Add compounds to compute 6-tier biological cascade predictions…</span>';
          }
          if (embeddedGraphState.cy && (state.activeTab === 'graph-tab' || shouldRender)) {
            renderEmbeddedCytoscape();
          }
          if (typeof callback === 'function') callback();
          return;
        }

        const bio = getBiometricsPayload();
        const params = new URLSearchParams();
        params.set('stack', stackSpecs.join(','));
        params.set('timeline', embeddedGraphState.timeline || state.timeline || 'steady_state');
        if (bio.sex) params.set('sex', bio.sex);
        if (bio.age) params.set('age', bio.age);
        if (bio.weight_kg) params.set('weight_kg', bio.weight_kg);
        if (bio.height_cm) params.set('height_cm', bio.height_cm);
        if (bio.body_fat_pct) params.set('body_fat_pct', bio.body_fat_pct);
        if (bio.blood_pressure) params.set('blood_pressure', bio.blood_pressure);
        if (bio.alt_u_l) params.set('alt_u_l', bio.alt_u_l);
        if (bio.egfr) params.set('egfr', bio.egfr);
        if (bio.hematocrit_pct) params.set('hematocrit_pct', bio.hematocrit_pct);

        try {
          const res = await fetch(`/graph-data?${params.toString()}`);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          if (reqId !== embeddedGraphState.loadRequestId) return;
          const data = await res.json();
          embeddedGraphState.data = data;

          const nodeCount = data.nodes ? data.nodes.length : 0;
          const edgeCount = data.edges ? data.edges.length : 0;
          const cascadeCount = data.cascade_simulation ? Object.keys(data.cascade_simulation).length : 0;

          if (tabGraphBadge) tabGraphBadge.textContent = `${nodeCount} Nodes`;
          if (statGraphNodes) statGraphNodes.textContent = `${nodeCount} Nodes • ${cascadeCount} Cascades`;

          renderEmbeddedCascadeChips(data.cascade_simulation);

          if (state.activeTab === 'graph-tab' || shouldRender || embeddedGraphState.initialized) {
            renderEmbeddedCytoscape();
          }

          if (typeof callback === 'function') callback();
        } catch (e) {
          console.debug('Embedded graph fetch notice', e);
          if (typeof callback === 'function') callback();
        }
      }

      function renderEmbeddedCascadeChips(cascadeMap) {
        const wrap = document.getElementById('embedded-cascade-chips');
        if (!wrap) return;
        if (!cascadeMap || !Object.keys(cascadeMap).length) {
          wrap.innerHTML = '<span class="cascade-badge">No active multi-tier cascades detected.</span>';
          return;
        }
        const entries = Object.entries(cascadeMap).slice(0, 10);
        wrap.innerHTML = entries.map(([key, val]) => {
          const sign = val > 0 ? '+' : '';
          const color = val > 0.05 ? '#00f2fe' : (val < -0.05 ? '#ff4b72' : '#94a3b8');
          const pct = Math.round(val * 100);
          return `
            <span class="cascade-badge" style="border-color:${color}; color:${color}; background:rgba(0,0,0,0.4); cursor:pointer;" onclick="focusAndSelectEmbeddedNode('${escapeHtml(key)}')">
              ${escapeHtml(key)}: <strong>${sign}${pct}%</strong>
            </span>
          `;
        }).join('');
      }

      function initOrRenderEmbeddedGraph(forceRefresh = false, callback = null) {
        const container = document.getElementById('embedded-graph-canvas');
        if (!container || !window.cytoscape) return;

        if (!embeddedGraphState.initialized) {
          setupEmbeddedGraphControls();
          embeddedGraphState.initialized = true;
        }

        if (!embeddedGraphState.data.nodes.length || forceRefresh) {
          syncGraphData(true, () => {
            renderEmbeddedCytoscape();
            if (typeof callback === 'function') callback();
          });
        } else {
          renderEmbeddedCytoscape();
          if (typeof callback === 'function') callback();
        }
      }

      function setupEmbeddedGraphControls() {
        const layoutSelect = document.getElementById('embedded-layout-select');
        const timelineSelect = document.getElementById('embedded-timeline-select');
        const searchInput = document.getElementById('embedded-graph-search');
        const btnSimulate = document.getElementById('embedded-btn-simulate');
        const btnConvergence = document.getElementById('embedded-btn-convergence');
        const btnFit = document.getElementById('embedded-btn-fit');
        const btnZoomIn = document.getElementById('embedded-btn-zoomin');
        const btnZoomOut = document.getElementById('embedded-btn-zoomout');
        const btnToggleInspector = document.getElementById('embedded-btn-toggle-inspector');
        const inspectorClose = document.getElementById('embedded-inspector-close-btn');

        if (layoutSelect) {
          layoutSelect.addEventListener('change', (e) => {
            embeddedGraphState.layout = e.target.value;
            renderEmbeddedCytoscape();
          });
        }

        if (timelineSelect) {
          timelineSelect.addEventListener('change', (e) => {
            embeddedGraphState.timeline = e.target.value;
            state.timeline = e.target.value;
            syncGraphData(true);
          });
        }

        if (searchInput) {
          searchInput.addEventListener('input', (e) => {
            embeddedGraphState.searchTerm = e.target.value.toLowerCase().trim();
            applyEmbeddedSearchFilter();
          });
        }

        if (btnSimulate) {
          btnSimulate.addEventListener('click', () => simulateEmbeddedSignal());
        }

        if (btnConvergence) {
          btnConvergence.addEventListener('click', () => {
            embeddedGraphState.filterConvergence = !embeddedGraphState.filterConvergence;
            btnConvergence.classList.toggle('active', embeddedGraphState.filterConvergence);
            renderEmbeddedCytoscape();
          });
        }

        if (btnFit) {
          btnFit.addEventListener('click', () => {
            if (embeddedGraphState.cy) embeddedGraphState.cy.fit(undefined, 30);
          });
        }
        if (btnZoomIn) {
          btnZoomIn.addEventListener('click', () => {
            if (embeddedGraphState.cy) embeddedGraphState.cy.zoom(embeddedGraphState.cy.zoom() * 1.25);
          });
        }
        if (btnZoomOut) {
          btnZoomOut.addEventListener('click', () => {
            if (embeddedGraphState.cy) embeddedGraphState.cy.zoom(embeddedGraphState.cy.zoom() * 0.8);
          });
        }
        if (btnToggleInspector) {
          btnToggleInspector.addEventListener('click', () => {
            const insp = document.getElementById('embedded-node-inspector');
            if (insp) insp.classList.toggle('hidden');
          });
        }
        if (inspectorClose) {
          inspectorClose.addEventListener('click', () => {
            const insp = document.getElementById('embedded-node-inspector');
            if (insp) insp.classList.add('hidden');
          });
        }

        document.querySelectorAll('.embedded-inspector-tab').forEach(tab => {
          tab.addEventListener('click', () => {
            document.querySelectorAll('.embedded-inspector-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            embeddedGraphState.selectedTab = tab.dataset.tab;
            renderEmbeddedNodePanel();
          });
        });
      }

      function renderEmbeddedCytoscape() {
        const container = document.getElementById('embedded-graph-canvas');
        if (!container || !window.cytoscape) return;

        let nodes = embeddedGraphState.data.nodes || [];
        let edges = embeddedGraphState.data.edges || [];

        if (embeddedGraphState.filterConvergence) {
          const targetIds = new Set(
            Object.keys(embeddedGraphState.data.combined_effects || {}).filter(k => {
              const eff = embeddedGraphState.data.combined_effects[k];
              return eff && eff.has_multiple_ligands;
            })
          );
          if (targetIds.size) {
            const visibleNodes = new Set(targetIds);
            edges.forEach(e => {
              if (targetIds.has(e.target)) visibleNodes.add(e.source);
              if (targetIds.has(e.source)) visibleNodes.add(e.target);
            });
            nodes = nodes.filter(n => visibleNodes.has(n.id));
            edges = edges.filter(e => visibleNodes.has(e.source) && visibleNodes.has(e.target));
          }
        }

        const elements = [
          ...nodes.map(n => ({
            data: {
              id: n.id,
              label: getEmbeddedNodeLabel(n),
              node_type: n.node_type || 'default',
              tier: n.tier !== undefined ? n.tier : 1,
              tier_name: n.tier_name || 'Target',
              raw: n,
            }
          })),
          ...edges.map((e, idx) => ({
            data: {
              id: `edge_${idx}_${e.source}_${e.target}`,
              source: e.source,
              target: e.target,
              type: e.type || 'MODULATES',
              effect_direction: e.effect_direction || 'neutral',
              affinity_ki: e.affinity_ki,
              raw: e,
            }
          }))
        ];

        if (embeddedGraphState.cy) {
          embeddedGraphState.cy.destroy();
        }

        embeddedGraphState.cy = cytoscape({
          container: container,
          elements: elements,
          style: [
            {
              selector: 'node',
              style: {
                'label': 'data(label)',
                'color': '#f8fafc',
                'font-size': '10px',
                'font-family': 'Plus Jakarta Sans, sans-serif',
                'font-weight': 700,
                'text-valign': 'bottom',
                'text-margin-y': 4,
                'background-color': ele => colorForEmbeddedNode(ele.data('node_type')),
                'width': ele => ele.data('node_type') === 'compound' ? 34 : 24,
                'height': ele => ele.data('node_type') === 'compound' ? 34 : 24,
                'border-width': 2,
                'border-color': '#050811',
                'shadow-blur': 12,
                'shadow-color': ele => colorForEmbeddedNode(ele.data('node_type')),
                'shadow-opacity': 0.6,
              }
            },
            {
              selector: 'node[node_type = "compound"]',
              style: {
                'shape': 'hexagon',
                'border-color': '#00f2fe',
                'border-width': 2.5,
              }
            },
            {
              selector: 'node[node_type = "receptor"], node[node_type = "target"]',
              style: { 'shape': 'round-rectangle' }
            },
            {
              selector: 'node[node_type = "enzyme"]',
              style: { 'shape': 'diamond' }
            },
            {
              selector: 'node[node_type = "biomarker"]',
              style: { 'shape': 'ellipse' }
            },
            {
              selector: 'node:selected',
              style: {
                'border-color': '#fff',
                'border-width': 3,
                'shadow-blur': 24,
                'shadow-opacity': 1,
              }
            },
            {
              selector: 'edge',
              style: {
                'width': 1.8,
                'line-color': ele => {
                  const dir = ele.data('effect_direction');
                  if (dir === 'positive') return '#10b981';
                  if (dir === 'negative') return '#ef4444';
                  if (dir === 'metabolic') return '#f59e0b';
                  return '#38bdf8';
                },
                'target-arrow-color': ele => {
                  const dir = ele.data('effect_direction');
                  if (dir === 'positive') return '#10b981';
                  if (dir === 'negative') return '#ef4444';
                  if (dir === 'metabolic') return '#f59e0b';
                  return '#38bdf8';
                },
                'target-arrow-shape': ele => {
                  const dir = ele.data('effect_direction');
                  return dir === 'negative' ? 'tee' : 'triangle';
                },
                'curve-style': 'bezier',
                'opacity': 0.75,
              }
            },
            {
              selector: '.edge-highlight',
              style: {
                'width': 3.5,
                'opacity': 1,
                'shadow-blur': 10,
                'shadow-color': '#00f2fe',
              }
            },
            {
              selector: '.dimmed',
              style: {
                'opacity': 0.15,
              }
            }
          ],
          layout: getEmbeddedLayoutOptions(nodes)
        });

        // Event Listeners
        embeddedGraphState.cy.on('tap', 'node', (evt) => {
          const nodeData = evt.target.data('raw');
          embeddedGraphState.selectedNode = nodeData.id;
          const insp = document.getElementById('embedded-node-inspector');
          if (insp) insp.classList.remove('hidden');
          renderEmbeddedNodePanel();
        });

        const tooltip = document.getElementById('embedded-graph-tooltip');
        const tooltipTitle = document.getElementById('embedded-tooltip-title');
        const tooltipSub = document.getElementById('embedded-tooltip-sub');
        const tooltipBadge = document.getElementById('embedded-tooltip-badge');

        embeddedGraphState.cy.on('mouseover', 'node', (evt) => {
          if (!tooltip) return;
          const n = evt.target.data('raw');
          if (!n) return;
          tooltipTitle.textContent = getEmbeddedNodeLabel(n);
          tooltipSub.textContent = `Tier ${n.tier !== undefined ? n.tier : 1}: ${n.tier_name || 'Entity'}`;
          if (tooltipBadge) {
            tooltipBadge.innerHTML = `<span class="risk-band-pill" style="font-size:0.62rem; padding:1px 5px; background:rgba(0,242,254,0.15); color:#00f2fe;">${(n.node_type || 'node').toUpperCase()}</span>`;
          }
          const pos = evt.renderedPosition;
          tooltip.style.left = `${pos.x + 15}px`;
          tooltip.style.top = `${pos.y + 15}px`;
          tooltip.style.display = 'block';
        });

        embeddedGraphState.cy.on('mouseout', 'node', () => {
          if (tooltip) tooltip.style.display = 'none';
        });

        applyEmbeddedSearchFilter();
      }

      function getEmbeddedLayoutOptions(nodes) {
        const layoutType = embeddedGraphState.layout || 'tier_flow';
        if (layoutType === 'tier_flow') {
          const tierBuckets = {};
          nodes.forEach(n => {
            const t = n.tier !== undefined ? n.tier : 1;
            if (!tierBuckets[t]) tierBuckets[t] = [];
            tierBuckets[t].push(n.id);
          });
          return {
            name: 'preset',
            positions: (node) => {
              const raw = node.data('raw') || {};
              const t = raw.tier !== undefined ? raw.tier : 1;
              const bucket = tierBuckets[t] || [node.id()];
              const idx = bucket.indexOf(node.id());
              const total = bucket.length;
              const x = 50 + (t * 180);
              const y = 50 + ((idx - (total - 1) / 2) * 55) + 200;
              return { x, y };
            },
            fit: true,
            padding: 30,
          };
        }
        if (layoutType === 'cose') {
          return { name: 'cose', animate: false, padding: 30 };
        }
        if (layoutType === 'breadthfirst') {
          return { name: 'breadthfirst', directed: true, padding: 30 };
        }
        if (layoutType === 'concentric') {
          return {
            name: 'concentric',
            concentric: ele => 6 - (ele.data('tier') || 1),
            levelWidth: () => 1,
            padding: 30
          };
        }
        return { name: 'circle', padding: 30 };
      }

      function applyEmbeddedSearchFilter() {
        if (!embeddedGraphState.cy) return;
        const term = embeddedGraphState.searchTerm;
        if (!term) {
          embeddedGraphState.cy.elements().removeClass('dimmed');
          return;
        }
        embeddedGraphState.cy.batch(() => {
          embeddedGraphState.cy.elements().addClass('dimmed');
          embeddedGraphState.cy.nodes().forEach(node => {
            const label = (node.data('label') || '').toLowerCase();
            const id = (node.data('id') || '').toLowerCase();
            if (label.includes(term) || id.includes(term)) {
              node.removeClass('dimmed');
              node.neighborhood().removeClass('dimmed');
            }
          });
        });
      }

      function simulateEmbeddedSignal() {
        if (!embeddedGraphState.cy || embeddedGraphState.simulating) return;
        embeddedGraphState.simulating = true;
        const cy = embeddedGraphState.cy;
        const btn = document.getElementById('embedded-btn-simulate');
        if (btn) btn.textContent = '⏳ Simulating...';

        const tiers = [0, 1, 2, 3, 4, 5];
        tiers.forEach((t, idx) => {
          setTimeout(() => {
            cy.batch(() => {
              cy.nodes().forEach(n => {
                if (n.data('tier') === t) {
                  n.flashClass('edge-highlight', 600);
                  n.connectedEdges().flashClass('edge-highlight', 600);
                }
              });
            });
            if (idx === tiers.length - 1) {
              setTimeout(() => {
                embeddedGraphState.simulating = false;
                if (btn) btn.innerHTML = `${iconSvg('zap', { class: 'icon-xs' })} Simulate Signal`;
              }, 650);
            }
          }, idx * 280);
        });
      }

      window.focusAndSelectEmbeddedNode = function(nodeId, pathIds = null) {
        if (!embeddedGraphState.cy) return;
        const cy = embeddedGraphState.cy;
        const target = cy.nodes().filter(n => n.data('id') === nodeId || n.data('label')?.toLowerCase() === nodeId?.toLowerCase());
        if (target.length) {
          cy.elements().removeClass('edge-highlight');
          target.select();
          cy.animate({
            center: { eles: target },
            zoom: 1.4,
            duration: 400
          });
          embeddedGraphState.selectedNode = target.data('id');
          const insp = document.getElementById('embedded-node-inspector');
          if (insp) insp.classList.remove('hidden');
          renderEmbeddedNodePanel();
        }
      };

      function renderEmbeddedNodePanel() {
        const body = document.getElementById('embedded-inspector-body');
        const titleEl = document.getElementById('embedded-inspector-title');
        if (!body) return;

        if (!embeddedGraphState.selectedNode) {
          body.innerHTML = '<div class="stack-empty-card" style="padding:20px;">Click any molecular node or interaction edge in the network to inspect detailed receptor affinities, saturation dials, and cascade predictions.</div>';
          return;
        }

        const nodes = embeddedGraphState.data.nodes || [];
        const edges = embeddedGraphState.data.edges || [];
        const node = nodes.find(n => n.id === embeddedGraphState.selectedNode) || { id: embeddedGraphState.selectedNode, label: embeddedGraphState.selectedNode, node_type: 'target' };

        if (titleEl) titleEl.textContent = `${getEmbeddedNodeLabel(node)}`;

        const incoming = edges.filter(e => e.target === node.id);
        const outgoing = edges.filter(e => e.source === node.id);
        const nodeColor = colorForEmbeddedNode(node.node_type);

        const comb = (embeddedGraphState.data.combined_effects && embeddedGraphState.data.combined_effects[node.id]) || node.combined_effect;

        // Render Combined Receptor PD Visualizer
        let combinedHtml = '';
        if (comb && comb.compounds && comb.compounds.length) {
          const net = comb.net_activation_score || 0;
          const netPct = comb.net_activation_pct !== undefined ? comb.net_activation_pct : Math.round(net * 100);
          const satPct = comb.receptor_saturation_pct !== undefined ? comb.receptor_saturation_pct : 0;
          const reservePct = comb.unoccupied_reserve_pct !== undefined ? comb.unoccupied_reserve_pct : 100;
          const needlePos = Math.min(96, Math.max(4, 50 + (net * 50)));
          const isPositive = net > 0.05;
          const isNegative = net < -0.05;
          const netColor = isPositive ? '#00f2fe' : (isNegative ? '#ff4b72' : '#c084fc');
          const stateClass = isPositive ? 'state-agonism' : (isNegative ? 'state-antagonism' : 'state-balanced');

          const compoundRows = comb.compounds.map(c => {
            const barColor = c.intrinsic_efficacy > 0 ? '#00f2fe' : (c.intrinsic_efficacy < 0 ? '#ff4b72' : '#f59e0b');
            return `
              <div class="compound-card">
                <div class="compound-row-top">
                  <span class="compound-row-title">
                    <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:${barColor};"></span>
                    ${escapeHtml(c.compound_label || c.compound_id)}
                  </span>
                  <span class="compound-action-pill ${c.is_agonist ? 'pill-agonist' : (c.is_antagonist ? 'pill-antagonist' : 'pill-modulator')}">${escapeHtml(c.action || 'Modulates')}</span>
                </div>
                <div class="occupancy-bar-wrap" style="margin-top:4px;">
                  <span style="color:var(--text-muted); min-width:70px;">Sat:</span>
                  <div class="occupancy-track">
                    <div class="occupancy-fill" style="width:${c.absolute_saturation_pct || 0}%; background:${barColor};"></div>
                  </div>
                  <span style="font-family:'JetBrains Mono',monospace; font-weight:700; color:#fff;">${c.absolute_saturation_pct || 0}%</span>
                </div>
              </div>
            `;
          }).join('');

          combinedHtml = `
            <div class="convergence-card">
              <div class="convergence-header">
                <span class="convergence-tag">${iconSvg('activity', { class: 'icon-xs icon-rose' })} Multi-Ligand Receptor PD (${comb.ligand_count || comb.compounds.length} Compounds)</span>
                <span class="receptor-state-badge ${stateClass}">${comb.receptor_state || 'Equilibrium'}</span>
              </div>
              <div class="saturation-pool-wrap">
                <div style="display:flex; justify-content:space-between; font-size:0.65rem; color:var(--text-secondary);">
                  <span>Pool Saturation</span>
                  <span style="color:#38bdf8; font-family:'JetBrains Mono',monospace; font-weight:700;">${satPct}% Bound • ${reservePct}% Reserve</span>
                </div>
                <div class="saturation-pool-bar">
                  <div class="saturation-pool-fill" style="width:${satPct}%; background:linear-gradient(90deg, #38bdf8, #c084fc);"></div>
                </div>
              </div>
              <div class="gauge-container">
                <div class="gauge-title-row">
                  <span style="font-size:0.65rem; color:var(--text-muted);">Net Biological Activation</span>
                  <span class="gauge-value-readout" style="color:${netColor};">${netPct > 0 ? '+' : ''}${netPct}%</span>
                </div>
                <div class="gauge-track-wrap">
                  <div class="gauge-center-notch"></div>
                  <div class="gauge-marker" style="left:${needlePos}%; border-color:${netColor}; box-shadow:0 0 10px ${netColor};"></div>
                </div>
                <div class="gauge-labels">
                  <span style="color:#ff4b72;">-100% Blockade</span>
                  <span>0% Basal</span>
                  <span style="color:#00f2fe;">+100% Agonism</span>
                </div>
              </div>
              <div class="compound-influence-list">${compoundRows}</div>
              ${comb.pharmacological_summary ? `<div class="mechanism-summary-card">${iconSvg('microscope', { class: 'icon-xs icon-teal' })} ${escapeHtml(comb.pharmacological_summary)}</div>` : ''}
            </div>
          `;
        }

        const tab = embeddedGraphState.selectedTab || 'overview';
        if (tab === 'pharmacodynamics') {
          body.innerHTML = `
            <div>
              <div class="node-hero-title">${getEmbeddedNodeLabel(node)}</div>
              <div class="node-badge-row">
                <span class="node-badge" style="border-color:${nodeColor}; color:${nodeColor};">${(node.node_type || 'TARGET').toUpperCase()}</span>
                <span class="node-badge">Tier ${node.tier !== undefined ? node.tier : 1}</span>
              </div>
            </div>
            ${combinedHtml || '<div style="font-size:0.75rem; color:var(--text-muted); padding:10px; background:rgba(0,0,0,0.3); border-radius:6px;">Single-agent ligand target. Add co-binding compounds to evaluate competitive receptor occupancy.</div>'}
            <div>
              <div class="neighbor-group-title">Upstream Ligand Inputs (${incoming.length})</div>
              <div class="neighbor-pill-list">
                ${incoming.map(e => `
                  <div class="neighbor-pill" onclick="focusAndSelectEmbeddedNode('${e.source}')">
                    <strong>${e.type || 'MODULATES'}</strong>
                    <span style="color:var(--text-secondary);">${e.source} ${e.affinity_ki ? `(Ki: ${e.affinity_ki} nM)` : ''}</span>
                  </div>
                `).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">None</span>'}
              </div>
            </div>
          `;
        } else if (tab === 'cascade') {
          body.innerHTML = `
            <div>
              <div class="node-hero-title">${getEmbeddedNodeLabel(node)}</div>
              <p style="font-size:0.75rem; color:var(--text-secondary); margin-top:4px;">Downstream biological signaling pathways & organ outcomes.</p>
            </div>
            <div>
              <div class="neighbor-group-title">Downstream Signaling Cascades (${outgoing.length})</div>
              <div class="neighbor-pill-list">
                ${outgoing.map(e => `
                  <div class="neighbor-pill" onclick="focusAndSelectEmbeddedNode('${e.target}')">
                    <strong>${e.type || 'SIGNALS_TO'}</strong>
                    <span style="color:var(--text-secondary);">${e.target}</span>
                  </div>
                `).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">Terminal node in current cascade depth.</span>'}
              </div>
            </div>
          `;
        } else if (tab === 'evidence') {
          body.innerHTML = `
            <div>
              <div class="node-hero-title">${getEmbeddedNodeLabel(node)}</div>
              <div class="node-badge-row">
                <span class="node-badge" style="color:var(--accent-cyan);">Catalog Grounded</span>
              </div>
            </div>
            <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.45; background:rgba(0,0,0,0.3); padding:10px; border-radius:6px; border:1px solid var(--border-subtle);">
              Biological causal edge verified via IUPHAR receptor kinetics, DrugBank mechanisms, and PubMed peer-reviewed pharmacological citations.
            </div>
            <a href="https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(node.label || node.id)}" target="_blank" rel="noopener" style="font-size:0.76rem; color:var(--accent-cyan); text-decoration:none; font-weight:700; display:inline-flex; align-items:center; gap:4px;">
              <span>Search Literature on PubMed ↗</span>
            </a>
          `;
        } else {
          // Overview
          body.innerHTML = `
            <div>
              <div class="node-hero-title">${getEmbeddedNodeLabel(node)}</div>
              <div class="node-badge-row">
                <span class="node-badge" style="border-color:${nodeColor}; color:${nodeColor};">${(node.node_type || 'TARGET').toUpperCase()}</span>
                <span class="node-badge" style="color:#38bdf8;">Tier ${node.tier !== undefined ? node.tier : 1}: ${node.tier_name || 'Target'}</span>
                <span class="node-badge" style="font-family:'JetBrains Mono',monospace;">${node.id}</span>
              </div>
            </div>
            ${combinedHtml}
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
              <div class="neighbor-group-title">Upstream Connections</div>
              <div class="neighbor-pill-list">
                ${incoming.map(e => `
                  <div class="neighbor-pill" onclick="focusAndSelectEmbeddedNode('${e.source}')">
                    <strong>${e.type || 'MODULATES'}</strong>
                    <span style="color:var(--text-secondary);">${e.source}</span>
                  </div>
                `).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">No upstream cascade inputs.</span>'}
              </div>
            </div>
            <div>
              <div class="neighbor-group-title">Downstream Signaling</div>
              <div class="neighbor-pill-list">
                ${outgoing.map(e => `
                  <div class="neighbor-pill" onclick="focusAndSelectEmbeddedNode('${e.target}')">
                    <strong>${e.type || 'MODULATES'}</strong>
                    <span style="color:var(--text-secondary);">${e.target}</span>
                  </div>
                `).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">No downstream targets.</span>'}
              </div>
            </div>
          `;
        }
      }

      syncAllBiometrics('bio', false);
      renderStackList();
      if (state.stack.length) {
        evaluateStack();
      } else {
        updateDashboardEmpty();
      }
      syncGraphData(false);