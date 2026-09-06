function escapeHtml(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

function renderInlineMarkdown(str) {
  if (!str) return '';
  return str
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--accent-cyan);">$1</strong>')
    .replace(/\*(.*?)\*\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.35); border-radius: 3px; padding: 1px 5px; font-size: 0.76rem; color: var(--accent-cyan);">$1</code>');
}
window.renderInlineMarkdown = renderInlineMarkdown;

function iconSvg(name, options = {}) {
  if (!name) return '';
  if (typeof name === 'string' && name.trim().startsWith('<')) return name;
  const aliasMap = {
    'warning': 'alert-triangle',
    'warn': 'alert-triangle',
    'danger': 'alert-circle',
    'error': 'alert-circle',
    'info': 'info',
    'success': 'check',
    'done': 'check',
    'delete': 'trash-2',
    'remove': 'x',
    'close': 'x',
    'graph': 'network',
    'dna': 'dna',
    'preset': 'zap',
    'copilot': 'sparkles',
    'ai': 'sparkles',
    'user': 'user',
    'profile': 'user',
    'organ': 'shield-check',
    'shield': 'shield-check',
    'flame': 'flame',
    'fire': 'flame',
    'brain': 'brain',
    'heart': 'heart-pulse',
    'cardio': 'heart-pulse',
    'pill': 'pill',
    'sleep': 'moon',
    'moon': 'moon',
    'sun': 'sun',
    'edit': 'pencil',
    'key': 'key',
    'settings': 'sliders',
    'flask': 'flask-conical',
    'science': 'flask-conical',
    'search': 'search',
    'crosshair': 'crosshair',
    'target': 'target',
    'clock': 'clock',
    'repeat': 'repeat',
    'droplet': 'droplet',
    'syringe': 'syringe',
    'microscope': 'microscope',
    'activity': 'activity',
    'layers': 'layers',
    'scale': 'scale',
    'check': 'check',
    'x': 'x'
  };
  const lookupName = aliasMap[name.toLowerCase()] || name.toLowerCase();
  if (window.lucide && window.lucide.icons && window.lucide.icons[lookupName]) {
    const size = options.size || (options.class?.includes('icon-xs') ? 13 : options.class?.includes('icon-sm') ? 16 : options.class?.includes('icon-lg') ? 24 : options.class?.includes('icon-xl') ? 32 : 16);
    return window.lucide.icons[lookupName].toSvg({
      class: `lucide-icon ${options.class || ''}`.trim(),
      width: size,
      height: size,
      'stroke-width': options.strokeWidth || 2,
      ...(options.attrs || {})
    });
  }
  return `<i data-lucide="${lookupName}" class="${options.class || ''}"></i>`;
}
window.iconSvg = iconSvg;

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
          metabolic_rate_kcal: null,
          hrv_rmssd_ms: null,
          free_t3_pg_ml: null,
          free_t4_ng_dl: null,
          fasting_insulin_u_iu_ml: null,
          homa_ir: null,
          shbg_nmol_l: null,
          bdnf_ng_ml: null,
          igf1_ng_ml: null,
          nad_plus_umol_l: null,
          hs_crp_mg_l: null,
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
        { key: 'hematocrit', type: 'float', default: 46 },
        { key: 'bmr', type: 'float', default: 1750 },
        { key: 'hrv', type: 'float', default: 45 },
        { key: 'freet3', type: 'float', default: 3.2 },
        { key: 'freet4', type: 'float', default: 1.3 },
        { key: 'insulin', type: 'float', default: 6 },
        { key: 'homair', type: 'float', default: 1.2 },
        { key: 'shbg', type: 'float', default: 32 },
        { key: 'bdnf', type: 'float', default: 25 },
        { key: 'igf1', type: 'float', default: 190 },
        { key: 'nad', type: 'float', default: 30 },
        { key: 'hscrp', type: 'float', default: 0.8 }
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
        const bioBmr = document.getElementById('bio-bmr')?.value;
        const bioHrv = document.getElementById('bio-hrv')?.value;
        const bioFreeT3 = document.getElementById('bio-freet3')?.value;
        const bioFreeT4 = document.getElementById('bio-freet4')?.value;
        const bioInsulin = document.getElementById('bio-insulin')?.value;
        const bioHomaIr = document.getElementById('bio-homair')?.value;
        const bioShbg = document.getElementById('bio-shbg')?.value;
        const bioBdnf = document.getElementById('bio-bdnf')?.value;
        const bioIgf1 = document.getElementById('bio-igf1')?.value;
        const bioNad = document.getElementById('bio-nad')?.value;
        const bioHsCrp = document.getElementById('bio-hscrp')?.value;

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
        if (bioBmr && !isNaN(Number(bioBmr))) biometrics.metabolic_rate_kcal = Number(bioBmr);
        if (bioHrv && !isNaN(Number(bioHrv))) biometrics.hrv_rmssd_ms = Number(bioHrv);
        if (bioFreeT3 && !isNaN(Number(bioFreeT3))) biometrics.free_t3_pg_ml = Number(bioFreeT3);
        if (bioFreeT4 && !isNaN(Number(bioFreeT4))) biometrics.free_t4_ng_dl = Number(bioFreeT4);
        if (bioInsulin && !isNaN(Number(bioInsulin))) biometrics.fasting_insulin_u_iu_ml = Number(bioInsulin);
        if (bioHomaIr && !isNaN(Number(bioHomaIr))) biometrics.homa_ir = Number(bioHomaIr);
        if (bioShbg && !isNaN(Number(bioShbg))) biometrics.shbg_nmol_l = Number(bioShbg);
        if (bioBdnf && !isNaN(Number(bioBdnf))) biometrics.bdnf_ng_ml = Number(bioBdnf);
        if (bioIgf1 && !isNaN(Number(bioIgf1))) biometrics.igf1_ng_ml = Number(bioIgf1);
        if (bioNad && !isNaN(Number(bioNad))) biometrics.nad_plus_umol_l = Number(bioNad);
        if (bioHsCrp && !isNaN(Number(bioHsCrp))) biometrics.hs_crp_mg_l = Number(bioHsCrp);

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
          else if (f.key === 'bmr') state.biomarkers.metabolic_rate_kcal = parseFloat(val) || null;
          else if (f.key === 'hrv') state.biomarkers.hrv_rmssd_ms = parseFloat(val) || null;
          else if (f.key === 'freet3') state.biomarkers.free_t3_pg_ml = parseFloat(val) || null;
          else if (f.key === 'freet4') state.biomarkers.free_t4_ng_dl = parseFloat(val) || null;
          else if (f.key === 'insulin') state.biomarkers.fasting_insulin_u_iu_ml = parseFloat(val) || null;
          else if (f.key === 'homair') state.biomarkers.homa_ir = parseFloat(val) || null;
          else if (f.key === 'shbg') state.biomarkers.shbg_nmol_l = parseFloat(val) || null;
          else if (f.key === 'bdnf') state.biomarkers.bdnf_ng_ml = parseFloat(val) || null;
          else if (f.key === 'igf1') state.biomarkers.igf1_ng_ml = parseFloat(val) || null;
          else if (f.key === 'nad') state.biomarkers.nad_plus_umol_l = parseFloat(val) || null;
          else if (f.key === 'hscrp') state.biomarkers.hs_crp_mg_l = parseFloat(val) || null;

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
        if (bio.metabolic_rate_kcal !== undefined) customItems.push(`BMR: ${bio.metabolic_rate_kcal}kcal`);
        if (bio.hrv_rmssd_ms !== undefined) customItems.push(`HRV: ${bio.hrv_rmssd_ms}ms`);
        if (bio.free_t3_pg_ml !== undefined) customItems.push(`fT3: ${bio.free_t3_pg_ml}pg`);
        if (bio.shbg_nmol_l !== undefined) customItems.push(`SHBG: ${bio.shbg_nmol_l}nM`);
        if (bio.bdnf_ng_ml !== undefined) customItems.push(`BDNF: ${bio.bdnf_ng_ml}ng`);
        if (bio.hs_crp_mg_l !== undefined) customItems.push(`hs-CRP: ${bio.hs_crp_mg_l}mg`);

        // AI Stack Builder Modal Summary
        const builderSummary = document.getElementById('builder-bio-summary');
        if (builderSummary) {
          if (customItems.length) {
            builderSummary.innerHTML = `<span style="color: var(--accent-cyan); font-weight: 700;">Personalized Profile:</span> ${customItems.map(item => `<span class="bio-chip">${escapeHtml(item)}</span>`).join(' ')} <span style="color: var(--text-muted); font-size: 0.72rem;">(Auto-scales PK & Dosing)</span>`;
          } else {
            builderSummary.innerHTML = `<span style="color: var(--text-secondary); font-style: italic;">No biometrics specified. Click <strong>"Edit Metrics"</strong> above to personalize dosing & organ shields.</span>`;
          }
        }

        // Copilot Drawer Summary
        const copilotSummary = document.getElementById('copilot-bio-summary');
        if (copilotSummary) {
          if (customItems.length) {
            copilotSummary.innerHTML = `<span style="color: var(--accent-cyan); font-weight: 700; display:inline-flex; align-items:center; gap:4px;">${iconSvg('user', { class: 'icon-xs icon-cyan' })} Profile:</span> ${customItems.slice(0, 4).map(item => `<span class="bio-chip-sm">${escapeHtml(item)}</span>`).join(' ')}${customItems.length > 4 ? ` <span style="color: var(--text-muted); font-size: 0.68rem;">+${customItems.length - 4} more</span>` : ''}`;
          } else {
            copilotSummary.innerHTML = `<span style="color: var(--text-muted); display:inline-flex; align-items:center; gap:4px;">${iconSvg('user', { class: 'icon-xs' })} Biometrics Unspecified</span>`;
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
            syncBadge.textContent = 'Biometrics Unspecified';
            syncBadge.style.color = 'var(--accent-cyan)';
            syncBadge.style.borderColor = 'rgba(0, 242, 254, 0.25)';
            syncBadge.style.background = 'rgba(0, 242, 254, 0.12)';
          }
        }
      }

      // SCIENTIFICALLY GROUNDED & POWERFUL PRESET PROTOCOLS
      const PRESET_STACKS = {
        focus: [
          { key: 'modafinil', name: 'Modafinil', drug_class: 'Eugeroic / CNS Stimulant', dose: 100, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'alpha_gpc', name: 'Alpha-GPC', drug_class: 'Cholinergic Precursor', dose: 300, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'caffeine', name: 'Caffeine Anhydrous', drug_class: 'Adenosine Receptor Antagonist', dose: 100, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        cognitive_focus: [
          { key: 'modafinil', name: 'Modafinil', drug_class: 'Eugeroic / CNS Stimulant', dose: 100, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'alpha_gpc', name: 'Alpha-GPC', drug_class: 'Cholinergic Precursor', dose: 300, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'caffeine', name: 'Caffeine Anhydrous', drug_class: 'Adenosine Receptor Antagonist', dose: 100, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        cardio_shield: [
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nebivolol', name: 'Nebivolol', drug_class: 'Cardioselective Beta-1 Blocker & NO Donor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'rosuvastatin', name: 'Rosuvastatin', drug_class: 'HMG-CoA Reductase Inhibitor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'evening', route: 'oral' },
          { key: 'ezetimibe', name: 'Ezetimibe', drug_class: 'Cholesterol Absorption Inhibitor', dose: 10, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        cardiovascular_lipid: [
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nebivolol', name: 'Nebivolol', drug_class: 'Cardioselective Beta-1 Blocker & NO Donor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'rosuvastatin', name: 'Rosuvastatin', drug_class: 'HMG-CoA Reductase Inhibitor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'evening', route: 'oral' },
          { key: 'ezetimibe', name: 'Ezetimibe', drug_class: 'Cholesterol Absorption Inhibitor', dose: 10, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        trt_balance: [
          { key: 'testosterone_cypionate', name: 'Testosterone Cypionate', drug_class: 'Anabolic-Androgenic Steroid', dose: 100, unit: 'mg', frequency: 'weekly', timing: 'morning', route: 'intramuscular' },
          { key: 'hcg', name: 'Human Chorionic Gonadotropin (HCG)', drug_class: 'LH Analog / Glycoprotein', dose: 250, unit: 'IU', frequency: 'twice_weekly', timing: 'morning', route: 'subcutaneous' },
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'anastrozole', name: 'Anastrozole', drug_class: 'Aromatase Inhibitor', dose: 0.25, unit: 'mg', frequency: 'twice_weekly', timing: 'morning', route: 'oral' }
        ],
        anabolic_physique: [
          { key: 'testosterone_cypionate', name: 'Testosterone Cypionate', drug_class: 'Anabolic-Androgenic Steroid', dose: 100, unit: 'mg', frequency: 'weekly', timing: 'morning', route: 'intramuscular' },
          { key: 'hcg', name: 'Human Chorionic Gonadotropin (HCG)', drug_class: 'LH Analog / Glycoprotein', dose: 250, unit: 'IU', frequency: 'twice_weekly', timing: 'morning', route: 'subcutaneous' },
          { key: 'telmisartan', name: 'Telmisartan', drug_class: 'Angiotensin II Receptor Blocker (ARB)', dose: 40, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'anastrozole', name: 'Anastrozole', drug_class: 'Aromatase Inhibitor', dose: 0.25, unit: 'mg', frequency: 'twice_weekly', timing: 'morning', route: 'oral' }
        ],
        thermogenic_shield: [
          { key: 'clenbuterol', name: 'Clenbuterol', drug_class: 'Beta-2 Adrenergic Agonist', dose: 40, unit: 'μg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nebivolol', name: 'Nebivolol', drug_class: 'Cardioselective Beta-1 Blocker & NO Donor', dose: 5, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'taurine', name: 'Taurine', drug_class: 'Osmolytic Amino Acid', dose: 2, unit: 'g', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        fat_loss_metabolic: [
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
          { key: 'apigenin', name: 'Apigenin', drug_class: 'Flavonoid / GABA Modulator', dose: 50, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'melatonin', name: 'Melatonin', drug_class: 'Pineal Neurohormone', dose: 0.3, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' }
        ],
        sleep_stress_recovery: [
          { key: 'magnesium', name: 'Magnesium Glycinate', drug_class: 'Mineral / NMDA Modulator', dose: 400, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'apigenin', name: 'Apigenin', drug_class: 'Flavonoid / GABA Modulator', dose: 50, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'melatonin', name: 'Melatonin', drug_class: 'Pineal Neurohormone', dose: 0.3, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' },
          { key: 'l_theanine', name: 'L-Theanine', drug_class: 'Dietary Supplement / Amino Acid', dose: 200, unit: 'mg', frequency: 'daily', timing: 'before bed', route: 'oral' }
        ],
        gut_microbiome: [
          { key: 'bpc_157', name: 'BPC-157 (Arginine Salt)', drug_class: 'Gastric Peptide', dose: 500, unit: 'μg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'glutamine', name: 'L-Glutamine', drug_class: 'Amino Acid', dose: 5, unit: 'g', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'tributyrin', name: 'Tributyrin', drug_class: 'Postbiotic / SCFA', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        immune_defense: [
          { key: 'vitamin_d3', name: 'Vitamin D3', drug_class: 'Secosteroid Hormone', dose: 5000, unit: 'IU', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'zinc', name: 'Zinc Picolinate', drug_class: 'Trace Mineral', dose: 30, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'vitamin_c', name: 'Vitamin C', drug_class: 'Water-Soluble Antioxidant', dose: 1000, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'nac', name: 'N-Acetyl Cysteine', drug_class: 'Glutathione Precursor', dose: 600, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        longevity_ampk: [
          { key: 'rapamycin', name: 'Rapamycin', drug_class: 'mTOR Inhibitor', dose: 5, unit: 'mg', frequency: 'weekly', timing: 'morning', route: 'oral' },
          { key: 'metformin', name: 'Metformin', drug_class: 'Biguanide / AMPK Activator', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'spermidine', name: 'Spermidine', drug_class: 'Polyamine / Autophagy Inducer', dose: 3, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        longevity_autophagy: [
          { key: 'rapamycin', name: 'Rapamycin', drug_class: 'mTOR Inhibitor', dose: 5, unit: 'mg', frequency: 'weekly', timing: 'morning', route: 'oral' },
          { key: 'metformin', name: 'Metformin', drug_class: 'Biguanide / AMPK Activator', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'spermidine', name: 'Spermidine', drug_class: 'Polyamine / Autophagy Inducer', dose: 3, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        hair_skin_derm: [
          { key: 'finasteride', name: 'Finasteride', drug_class: '5-Alpha Reductase Inhibitor', dose: 1, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'curcumin', name: 'Curcumin', drug_class: 'Polyphenolic Anti-inflammatory', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ],
        post_therapy_reset: [
          { key: 'nac', name: 'N-Acetyl Cysteine', drug_class: 'Glutathione Precursor', dose: 600, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'tudca', name: 'TUDCA', drug_class: 'Hydrophilic Bile Acid', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' },
          { key: 'citrus_bergamot', name: 'Citrus Bergamot', drug_class: 'Cardiovascular Support', dose: 500, unit: 'mg', frequency: 'daily', timing: 'morning', route: 'oral' }
        ]
      };

      const _clientCatalogCache = {};
      const _searchQueryCache = {};
      window._clientCatalogCache = _clientCatalogCache;
      window._searchQueryCache = _searchQueryCache;

      let _catalogSearchIndex = [];
      window._catalogSearchIndex = _catalogSearchIndex;

      async function loadCatalogSearchIndex() {
        try {
          const cached = localStorage.getItem('healthai_search_index_v2');
          if (cached) {
            try {
              const parsed = JSON.parse(cached);
              if (Array.isArray(parsed) && parsed.length > 0) {
                _catalogSearchIndex = parsed;
                window._catalogSearchIndex = parsed;
                parsed.forEach(item => {
                  if (item && item.key) {
                    _clientCatalogCache[item.key] = item;
                    if (item.key.includes('_')) _clientCatalogCache[item.key.replace(/_/g, '-')] = item;
                  }
                });
              }
            } catch (e) {}
          }

          const res = await fetch('/api/compounds/index');
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              _catalogSearchIndex = data;
              window._catalogSearchIndex = data;
              data.forEach(item => {
                if (item && item.key) {
                  _clientCatalogCache[item.key] = item;
                  if (item.key.includes('_')) _clientCatalogCache[item.key.replace(/_/g, '-')] = item;
                }
              });
              try {
                localStorage.setItem('healthai_search_index_v2', JSON.stringify(data));
              } catch (e) {}
            }
          }
        } catch (err) {
          console.debug('Index preload deferred:', err);
        }
      }
      window.loadCatalogSearchIndex = loadCatalogSearchIndex;
      // Start background index load immediately
      loadCatalogSearchIndex();

      function filterLocalCatalogIndex(query, modality = 'all') {
        const index = window._catalogSearchIndex || _catalogSearchIndex;
        if (!index || !index.length) return [];
        const q = String(query || '').toLowerCase().trim();
        if (!q) return [];

        const matches = [];
        for (const c of index) {
          if (modality && modality !== 'all') {
            const mod = String(c.modality || '').toLowerCase();
            const drugClass = String(c.drug_class || '').toLowerCase();
            if (modality === 'peptide' && !(mod === 'peptide' || c.is_peptide || drugClass.includes('peptide') || drugClass.includes('glp-1'))) continue;
            if (modality === 'biologic_antibody' && !(mod === 'biologic_antibody' || c.is_biologic || drugClass.includes('biologic') || drugClass.includes('antibody') || drugClass.includes('mab'))) continue;
            if (modality === 'botanical_natural' && !(mod === 'botanical_natural' || c.is_botanical || drugClass.includes('botanical') || drugClass.includes('herb'))) continue;
            if (modality === 'combination_drug' && !(mod === 'combination_drug' || c.is_combination || drugClass.includes('combination') || drugClass.includes('combo'))) continue;
            if (modality === 'small_molecule' && (c.is_peptide || c.is_biologic || c.is_botanical || c.is_combination || mod !== 'small_molecule')) continue;
          }

          const cName = String(c.name || '').toLowerCase();
          const cKey = String(c.key || '').toLowerCase();
          const cCanon = String(c.canonical_name || '').toLowerCase();
          const syns = Array.isArray(c.synonyms) ? c.synonyms.map(s => String(s).toLowerCase()) : [];

          let score = 0;
          if (cName === q || cKey === q) score = 100;
          else if (syns.includes(q)) score = 90;
          else if (cName.startsWith(q) || cKey.startsWith(q)) score = 80;
          else if (syns.some(s => s.startsWith(q))) score = 70;
          else if (cName.includes(q) || cKey.includes(q) || cCanon.includes(q)) score = 50;
          else if (syns.some(s => s.includes(q))) score = 40;

          if (score > 0) {
            matches.push({ score, item: c });
          }
        }

        matches.sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));
        return matches.map(m => m.item);
      }
      window.filterLocalCatalogIndex = filterLocalCatalogIndex;

      function toggleBiomarkerDrawer() {
        const drawer = document.getElementById('biomarker-drawer');
        const icon = document.getElementById('biomarker-toggle-icon');
        if (!drawer) return;
        const isHidden = drawer.style.display === 'none';
        drawer.style.display = isHidden ? 'block' : 'none';
        if (icon) icon.innerHTML = iconSvg(isHidden ? 'chevron-up' : 'chevron-down', { class: 'icon-xs' });
      }
      window.toggleBiomarkerDrawer = toggleBiomarkerDrawer;

      function showToast(message, icon = 'check') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = 'toast-message';
        const iconHtml = iconSvg(icon, { class: 'icon-sm' });
        toast.innerHTML = `<span class="toast-icon-wrap" style="display:inline-flex; align-items:center;">${iconHtml}</span> <span>${message}</span>`;
        container.appendChild(toast);
        if (window.lucide && window.lucide.createIcons) {
          window.lucide.createIcons({ root: toast });
        }
        setTimeout(() => {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(-10px)';
          toast.style.transition = 'all 0.3s ease';
          setTimeout(() => toast.remove(), 300);
        }, 3000);
      }
      window.showToast = showToast;

      function setExperienceMode(mode) {
        state.experienceMode = mode;
        const stdBtn = document.getElementById('mode-std-btn');
        const pwrBtn = document.getElementById('mode-power-btn');
        if (mode === 'power') {
          stdBtn.classList.remove('active');
          pwrBtn.classList.add('active');
          showToast('Power-User Mode: Pharmacokinetic constants & variance enabled', 'microscope');
        } else {
          pwrBtn.classList.remove('active');
          stdBtn.classList.add('active');
          showToast('Standard Mode: Plain-English clinical explanations', 'activity');
        }
        if (state.analysis) {
          renderFullStackBalance(state.analysis);
          renderBreakdowns(state.analysis);
        }
      }
      window.setExperienceMode = setExperienceMode;

      async function loadPreset(presetKey) {
        const normKey = String(presetKey || '').toLowerCase().trim();
        const preset = PRESET_STACKS[normKey] || PRESET_STACKS[normKey.replace(/_/g, '')] || PRESET_STACKS[normKey.replace(/-/g, '_')];
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

        showToast(`Loaded ${presetKey.replace(/_/g, ' ').toUpperCase()} Protocol`, 'zap');
        if (typeof syncAndEvaluateStack === 'function') {
          syncAndEvaluateStack();
        } else if (typeof renderStackList === 'function') {
          renderStackList();
          if (typeof evaluateStack === 'function') evaluateStack();
        }

        // Background hydration for full pharmacology metadata
        const missingKeys = preset.filter(p => !_clientCatalogCache[p.key]?.mechanism).map(p => p.key);
        if (missingKeys.length) {
          const evalIndicator = document.getElementById('stack-eval-indicator');
          if (evalIndicator) {
            const label = evalIndicator.querySelector('span:last-child');
            if (label) label.textContent = 'Hydrating compound metadata…';
            evalIndicator.style.display = 'inline-flex';
          }
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
                const match = typeof matchCompoundItem === 'function' ? matchCompoundItem(state.stack, k) : null;
                if (match && comp.name) {
                  match.name = comp.name;
                  if (comp.drug_class) match.drug_class = comp.drug_class;
                  if (comp.mechanism) match.mechanism = comp.mechanism;
                }
              });
              if (typeof renderStackList === 'function') renderStackList();
            }
          } catch (e) { /* ignore background fetch */ }
          finally {
            if (evalIndicator) {
              const label = evalIndicator.querySelector('span:last-child');
              if (label) label.textContent = 'Evaluating stack safety…';
              evalIndicator.style.display = 'none';
            }
          }
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
        if (f.includes('tiw') || f.includes('3x_week') || (f.includes('three') && f.includes('week'))) return 3.0 / 7.0;
        if (f.includes('tid') || (f.includes('three') && !f.includes('week'))) return 3.0;
        if (f.includes('qid') || f.includes('four')) return 4.0;
        if (f.includes('qod') || f.includes('eod') || f.includes('other') || f.includes('alternate')) return 0.5;
        if (f.includes('biw') || (f.includes('twice') && f.includes('week')) || f.includes('2x_week')) return 2.0 / 7.0;
        if (f.includes('qw') || (f.includes('week') && !f.includes('2') && !f.includes('bi') && !f.includes('three') && !f.includes('3'))) return 1.0 / 7.0;
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

