/**
 * HealthAI Public Launch Disclaimer & Safety System
 * Handles first-time user acknowledgement, persistent footer banners, and multi-tab medical/legal modals.
 */

(function () {
  const DISCLAIMER_STORAGE_KEY = 'healthai_disclaimer_accepted_v1';

  const DISCLAIMER_MODAL_HTML = `
  <div id="disclaimer-modal">
    <div class="modal-dialog">
      <div class="disclaimer-modal-header">
        <div class="disclaimer-modal-title">
          <span style="display:inline-flex; align-items:center; gap:6px;"><i data-lucide="shield-alert" class="icon-sm icon-amber"></i> Medical, Scientific & Legal Disclaimers</span>
        </div>
        <button type="button" class="disclaimer-modal-close-btn" id="disclaimer-modal-close-btn" aria-label="Close disclaimer modal">&times;</button>
      </div>

      <div class="disclaimer-modal-tabs">
        <button type="button" class="disclaimer-tab-btn active" data-tab="medical"><i data-lucide="shield-check" class="icon-xs icon-cyan"></i> Medical & Clinical Safety</button>
        <button type="button" class="disclaimer-tab-btn" data-tab="computational"><i data-lucide="cpu" class="icon-xs icon-teal"></i> AI & Computational Scope</button>
        <button type="button" class="disclaimer-tab-btn" data-tab="terms"><i data-lucide="file-text" class="icon-xs icon-blue"></i> Terms of Use & Liability</button>
        <button type="button" class="disclaimer-tab-btn" data-tab="emergency"><i data-lucide="alert-triangle" class="icon-xs icon-rose"></i> Emergency & Crisis Care</button>
      </div>

      <div class="disclaimer-tab-content active" id="disclaimer-tab-medical">
        <h4>1. Not Medical or Prescriptive Advice</h4>
        <p><strong>HealthAI is an advanced computational pharmacology research, continuous biophysical simulation, and biological network mapping workbench.</strong> It is designed solely to assist researchers, students, clinicians, and informed health professionals in modeling molecular mechanisms, pharmacokinetic principles, and receptor binding interactions.</p>
        
        <h4>2. No Doctor-Patient Relationship</h4>
        <p>Use of this application, its simulated dosage schedules, collision matrices, or AI Clinical Copilot outputs does <strong>NOT</strong> establish a physician-patient, pharmacist-patient, or healthcare provider relationship. HealthAI is NOT a licensed medical device and does NOT diagnose conditions, recommend individualized medical treatments, or prescribe pharmaceuticals.</p>

        <h4>3. Mandatory Healthcare Provider Supervision</h4>
        <p>Always consult a licensed medical doctor, board-certified clinical pharmacologist, or appropriate healthcare provider before initiating, modifying, combining, or discontinuing any pharmaceutical medication, hormone replacement protocol, bioactive peptide, or dietary supplement.</p>
      </div>

      <div class="disclaimer-tab-content" id="disclaimer-tab-computational">
        <h4>1. Computational Modeling & ODE Simulation Scope</h4>
        <p>All pharmacokinetic and pharmacodynamic projections—including 2-compartment open models, Rodgers-Rowland tissue partition coefficients ($K_p$), elimination half-lives, and receptor occupancy ($RO\%$) curves—are <em>in silico</em> mathematical approximations derived from published literature and population averages.</p>

        <h4>2. Individual Biological Variability</h4>
        <p>Real-world human biology exhibits substantial non-linear variability based on unmeasured genetics, epigenetic modifications, renal/hepatic perfusion, gastrointestinal absorption, microbial metabolism, and transient physiological states. Simulations may not reflect your exact in vivo response.</p>

        <h4>3. AI Copilot Grounding & Model Hallucination Safeguards</h4>
        <p>While the AI Copilot reasons over deterministic databases (PubChem, ChEMBL, Reactome, CPIC, PubMed) and causal knowledge graphs, generative AI responses may occasionally misinterpret nuance. Always verify critical drug interaction claims with primary medical literature and validated reference compendia.</p>
      </div>

      <div class="disclaimer-tab-content" id="disclaimer-tab-terms">
        <h4>1. Educational & Research Purpose Only</h4>
        <p>HealthAI is provided under the MIT License for educational, scientific evaluation, and pharmacological research purposes. By accessing or using this software, you expressly acknowledge and agree that you assume full responsibility for your health decisions and independent research.</p>

        <h4>2. Limitation of Liability & "As Is" Warranty</h4>
        <p>THIS SOFTWARE AND ALL ASSOCIATED CALCULATIONS, PREDICTIONS, AND AI INFERENCES ARE PROVIDED "AS IS" AND "AS AVAILABLE", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. IN NO EVENT SHALL THE AUTHORS, DEVELOPERS, OR CONTRIBUTORS BE LIABLE FOR ANY CLAIM, DAMAGES, ADVERSE EVENT, OR OTHER LIABILITY ARISING FROM THE USE OR MISUSE OF THIS SOFTWARE.</p>
      </div>

      <div class="disclaimer-tab-content" id="disclaimer-tab-emergency">
        <h4 style="display:inline-flex; align-items:center; gap:6px;"><i data-lucide="alert-octagon" class="icon-sm icon-rose"></i> Medical Emergency Notice</h4>
        <p>If you or someone you know is experiencing acute adverse symptoms, suspected overdose, severe allergic reactions, chest pain, shortness of breath, serotonin toxicity symptoms, or any other life-threatening medical emergency:</p>
        
        <div class="disclaimer-emergency-highlight">
          <strong>IMMEDIATELY CALL EMERGENCY SERVICES (911 in the US/Canada, 999 in the UK, 112 in the EU) OR GO TO THE NEAREST HOSPITAL EMERGENCY DEPARTMENT.</strong>
        </div>

        <h4 style="margin-top: 14px;">Poison Control & Crisis Hotlines:</h4>
        <ul>
          <li><strong>US Poison Control Center:</strong> <a href="tel:18002221222" style="color:var(--accent-cyan);">1-800-222-1222</a> (Free, confidential 24/7 expert medical advice)</li>
          <li><strong>UK NHS Non-Emergency:</strong> <a href="tel:111" style="color:var(--accent-cyan);">111</a> / <strong>Emergency:</strong> 999</li>
          <li><strong>Canada Poison Centres:</strong> <a href="tel:18447647661" style="color:var(--accent-cyan);">1-844-POISON-X (1-844-764-7661)</a></li>
          <li><strong>European Emergency Helpline:</strong> <a href="tel:112" style="color:var(--accent-cyan);">112</a></li>
        </ul>
      </div>

      <div class="disclaimer-modal-footer">
        <label class="disclaimer-ack-checkbox-wrap" id="disclaimer-checkbox-label">
          <input type="checkbox" id="disclaimer-ack-checkbox" checked />
          <span>I have read, understand, and agree to these terms & medical disclosures</span>
        </label>
        <button type="button" class="btn-accept-disclaimer" id="btn-accept-disclaimer">
          I Understand & Accept
        </button>
      </div>
    </div>
  </div>
  `;

  const GLOBAL_FOOTER_HTML = `
  <footer class="global-disclaimer-footer" id="global-disclaimer-footer">
    <div class="global-disclaimer-footer-inner">
      <div class="disclaimer-badge-row">
        <div class="disclaimer-badge-title">
          <span class="disclaimer-pill">Scientific Research Notice</span>
          <span>HealthAI Computational Pharmacology & Network Biology Platform</span>
        </div>
        <div class="disclaimer-nav-links">
          <button type="button" class="disclaimer-link-btn" onclick="HealthAIDisclaimer.open('medical')" style="display:inline-flex; align-items:center; gap:4px;"><i data-lucide="shield-check" class="icon-xs icon-cyan"></i> Medical Disclaimer</button>
          <button type="button" class="disclaimer-link-btn" onclick="HealthAIDisclaimer.open('computational')" style="display:inline-flex; align-items:center; gap:4px;"><i data-lucide="cpu" class="icon-xs icon-teal"></i> AI & ODE Scope</button>
          <button type="button" class="disclaimer-link-btn" onclick="HealthAIDisclaimer.open('terms')" style="display:inline-flex; align-items:center; gap:4px;"><i data-lucide="file-text" class="icon-xs"></i> Terms of Use</button>
          <button type="button" class="disclaimer-link-btn" onclick="HealthAIDisclaimer.open('emergency')" style="color: #fca5a5; display:inline-flex; align-items:center; gap:4px;"><i data-lucide="alert-triangle" class="icon-xs icon-rose"></i> Emergency Care</button>
          <a href="/docs" target="_blank" style="display:inline-flex; align-items:center; gap:4px;"><i data-lucide="book-open" class="icon-xs"></i> <span>API Docs</span> <i data-lucide="external-link" class="icon-xs"></i></a>
        </div>
      </div>
      <div class="disclaimer-text-block">
        <strong>IMPORTANT MEDICAL NOTICE:</strong> HealthAI is an experimental computational simulation, biophysical PBPK modeling, and educational network analysis workbench. It does <strong>NOT</strong> constitute medical advice, clinical diagnosis, or prescriptive therapeutic regimens. Drug interaction simulations and AI Copilot responses must be interpreted with professional clinical judgement and verified with licensed healthcare providers prior to protocol administration.
      </div>
    </div>
  </footer>
  `;

  function initDisclaimerModal() {
    if (!document.getElementById('disclaimer-modal')) {
      const container = document.createElement('div');
      container.innerHTML = DISCLAIMER_MODAL_HTML;
      document.body.appendChild(container.firstElementChild);
      if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
      }
    }

    const modal = document.getElementById('disclaimer-modal');
    const closeBtn = document.getElementById('disclaimer-modal-close-btn');
    const acceptBtn = document.getElementById('btn-accept-disclaimer');
    const tabs = modal.querySelectorAll('.disclaimer-tab-btn');

    // Tab switching
    tabs.forEach(btn => {
      btn.addEventListener('click', () => {
        const tabId = btn.getAttribute('data-tab');
        switchTab(tabId);
      });
    });

    // Close button
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        modal.classList.remove('open');
      });
    }

    // Backdrop click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('open');
      }
    });

    // Accept button
    if (acceptBtn) {
      acceptBtn.addEventListener('click', () => {
        try {
          localStorage.setItem(DISCLAIMER_STORAGE_KEY, new Date().toISOString());
        } catch (e) {
          console.warn('LocalStorage unavailable for disclaimer acceptance:', e);
        }
        modal.classList.remove('open');
      });
    }
  }

  function switchTab(tabId) {
    const modal = document.getElementById('disclaimer-modal');
    if (!modal) return;

    modal.querySelectorAll('.disclaimer-tab-btn').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
    });

    modal.querySelectorAll('.disclaimer-tab-content').forEach(c => {
      c.classList.toggle('active', c.id === `disclaimer-tab-${tabId}`);
    });
  }

  function initGlobalFooter() {
    if (!document.getElementById('global-disclaimer-footer')) {
      const wrapper = document.querySelector('.app-wrapper') || document.querySelector('.container') || document.querySelector('.app-shell') || document.body;
      const footerContainer = document.createElement('div');
      footerContainer.innerHTML = GLOBAL_FOOTER_HTML;
      wrapper.appendChild(footerContainer.firstElementChild);
      if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
      }
    }
  }

  function checkFirstVisitAcknowledgement() {
    try {
      const accepted = localStorage.getItem(DISCLAIMER_STORAGE_KEY);
      if (!accepted) {
        // Open modal automatically on first visit
        setTimeout(() => {
          HealthAIDisclaimer.open('medical');
        }, 500);
      }
    } catch (e) {
      console.warn('LocalStorage check failed:', e);
    }
  }

  // Public API
  window.HealthAIDisclaimer = {
    open: function (initialTab = 'medical') {
      const modal = document.getElementById('disclaimer-modal');
      if (modal) {
        switchTab(initialTab);
        modal.classList.add('open');
      }
    },
    close: function () {
      const modal = document.getElementById('disclaimer-modal');
      if (modal) {
        modal.classList.remove('open');
      }
    },
    isAccepted: function () {
      try {
        return Boolean(localStorage.getItem(DISCLAIMER_STORAGE_KEY));
      } catch (e) {
        return false;
      }
    }
  };

  // Auto-init on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initDisclaimerModal();
      initGlobalFooter();
      checkFirstVisitAcknowledgement();
    });
  } else {
    initDisclaimerModal();
    initGlobalFooter();
    checkFirstVisitAcknowledgement();
  }
})();
