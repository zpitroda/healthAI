// State
        let ws = null;
        let autoScroll = true;

        const defaultPayloads = {
            collision: JSON.stringify({
                eval_type: "collision",
                stack: [
                    { compound_key: "telmisartan", dose_mg: 40, route: "oral", frequency: "daily" },
                    { compound_key: "enzalutamide", dose_mg: 160, route: "oral", frequency: "daily" }
                ]
            }, null, 2),
            pkpd: JSON.stringify({
                eval_type: "pkpd",
                compound_key: "telmisartan",
                dose_mg: 40,
                duration_h: 24
            }, null, 2),
            catalog: JSON.stringify({
                eval_type: "catalog",
                query: "caffeine"
            }, null, 2),
            graph: JSON.stringify({
                eval_type: "graph",
                cypher: "MATCH (c:Compound)-[r]->(t:Target) RETURN c.name, type(r), t.name LIMIT 10"
            }, null, 2),
            snippet: JSON.stringify({
                eval_type: "snippet",
                code: "cat = CatalogService()\nkeys = cat.list_all_keys()\nprint('Total catalog keys:', len(keys))\nresult = {'total_compounds': len(keys)}"
            }, null, 2)
        };

        // DOM elements
        const wsStatus = document.getElementById('ws-status');
        const wsStatusText = document.getElementById('ws-status-text');
        const logContainer = document.getElementById('log-container');
        const loggerSelect = document.getElementById('logger-select');
        const evalTypeSelect = document.getElementById('eval-type-select');
        const evalInputCode = document.getElementById('eval-input-code');
        const evalResultOutput = document.getElementById('eval-result-output');

        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
        });

        // System Diagnostics
        async function fetchDiagnostics() {
            try {
                const res = await fetch('/api/debug/system');
                const data = await res.json();
                document.getElementById('sys-ram').textContent = data.memory?.rss_mb ? `${data.memory.rss_mb} MB` : 'N/A';
                document.getElementById('sys-sqlite').textContent = `${data.sqlite_status} (${data.sqlite_compounds_count} items)`;
                document.getElementById('sys-neo4j').textContent = data.neo4j_status;
                document.getElementById('sys-log-count').textContent = data.total_logs_in_buffer;
            } catch (e) {
                console.error("Failed to fetch diagnostics", e);
            }
        }

        // Fetch Loggers List
        async function fetchLoggers() {
            try {
                const res = await fetch('/api/debug/loggers');
                const data = await res.json();
                loggerSelect.innerHTML = '';
                data.loggers.forEach(l => {
                    const opt = document.createElement('option');
                    opt.value = l.name;
                    opt.textContent = `${l.name} [${l.level}]`;
                    loggerSelect.appendChild(opt);
                });
            } catch (e) {
                console.error("Failed to fetch loggers", e);
            }
        }

        // Apply Log Level
        document.getElementById('btn-apply-level').addEventListener('click', async () => {
            const logger_name = loggerSelect.value;
            const level_name = document.getElementById('logger-level-select').value;
            try {
                const res = await fetch('/api/debug/log-level', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ logger_name, level_name })
                });
                const data = await res.json();
                alert(data.message || 'Level updated');
                fetchLoggers();
            } catch (e) {
                alert('Failed to set level: ' + e);
            }
        });

        // Render Log Entry
        function renderLogEntry(entry) {
            const row = document.createElement('div');
            row.className = 'log-row';

            const timeSpan = document.createElement('span');
            timeSpan.className = 'log-time';
            timeSpan.textContent = entry.timestamp.split('T')[1]?.split('.')[0] || entry.timestamp;

            const levelSpan = document.createElement('span');
            levelSpan.className = `log-level ${entry.level}`;
            levelSpan.textContent = entry.level;

            const loggerSpan = document.createElement('span');
            loggerSpan.className = 'log-logger';
            loggerSpan.textContent = `[${entry.logger_name}]`;

            const msgSpan = document.createElement('span');
            msgSpan.className = 'log-msg';
            msgSpan.textContent = entry.message;

            row.appendChild(timeSpan);
            row.appendChild(levelSpan);
            row.appendChild(loggerSpan);
            row.appendChild(msgSpan);

            if (entry.exc_info) {
                const traceDiv = document.createElement('div');
                traceDiv.className = 'log-trace';
                traceDiv.textContent = entry.exc_info;
                row.appendChild(traceDiv);
            }

            logContainer.appendChild(row);
            if (autoScroll) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }

        // Connect WebSocket
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/debug/ws/logs`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                wsStatus.className = 'status-badge';
                wsStatusText.textContent = 'Live Streaming';
                logContainer.innerHTML = '';
            };

            ws.onmessage = (event) => {
                const payload = JSON.parse(event.data);
                if (payload.type === 'snapshot') {
                    logContainer.innerHTML = '';
                    payload.data.forEach(renderLogEntry);
                } else if (payload.type === 'log') {
                    renderLogEntry(payload.data);
                }
            };

            ws.onclose = () => {
                wsStatus.className = 'status-badge disconnected';
                wsStatusText.textContent = 'Disconnected (Reconnecting...)';
                setTimeout(connectWebSocket, 3000);
            };

            ws.onerror = (err) => {
                console.error("WS error", err);
            };
        }

        // Fetch logs via REST fallback / refresh
        async function fetchLogsREST() {
            const min_level = document.getElementById('filter-level').value;
            const q = document.getElementById('filter-search').value;
            const url = new URL('/api/debug/logs', window.location.origin);
            if (min_level) url.searchParams.append('min_level', min_level);
            if (q) url.searchParams.append('q', q);

            try {
                const res = await fetch(url);
                const data = await res.json();
                logContainer.innerHTML = '';
                data.logs.forEach(renderLogEntry);
            } catch (e) {
                console.error("Error fetching logs REST", e);
            }
        }

        document.getElementById('btn-refresh-logs').addEventListener('click', fetchLogsREST);
        document.getElementById('btn-clear-logs').addEventListener('click', async () => {
            if (confirm("Clear in-memory log buffer?")) {
                await fetch('/api/debug/logs', { method: 'DELETE' });
                logContainer.innerHTML = '';
                fetchDiagnostics();
            }
        });

        // Eval Sandbox Setup
        evalTypeSelect.addEventListener('change', () => {
            const val = evalTypeSelect.value;
            evalInputCode.value = defaultPayloads[val] || '';
        });
        evalInputCode.value = defaultPayloads.collision;

        document.getElementById('btn-run-eval').addEventListener('click', async () => {
            evalResultOutput.textContent = 'Executing...';
            try {
                const payload = JSON.parse(evalInputCode.value);
                const start = performance.now();
                const res = await fetch('/api/debug/eval', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                const elapsed = Math.round(performance.now() - start);
                evalResultOutput.textContent = `// Execution completed in ${elapsed}ms\n\n` + JSON.stringify(data, null, 2);
            } catch (e) {
                evalResultOutput.textContent = `// Error executing payload:\n${e.message || e}`;
            }
        });

        // Mobile menu toggle
        const debugMobileMenuBtn = document.getElementById('mobile-menu-toggle');
        const debugNavLinks = document.getElementById('nav-links');
        if (debugMobileMenuBtn && debugNavLinks) {
            debugMobileMenuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                debugNavLinks.classList.toggle('open');
            });
            document.addEventListener('click', (e) => {
                if (!debugNavLinks.contains(e.target) && !debugMobileMenuBtn.contains(e.target)) {
                    debugNavLinks.classList.remove('open');
                }
            });
        }

        // Initial launch
        fetchDiagnostics();
        fetchLoggers();
        connectWebSocket();
        setInterval(fetchDiagnostics, 10000);