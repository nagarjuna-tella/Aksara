/**
 * Aksara Studio - Dashboard Application
 * 
 * Zero-dependency, zero-build JavaScript for Aksara Studio dashboard.
 * Uses vanilla JS with modern ES6+ features.
 * 
 * v0.5.11
 */

// =============================================================================
// State
// =============================================================================

const state = {
    handshake: null,
    contextSummary: null,
    runtimeInfo: null,
    routes: [],
    migrations: null,
    currentSection: 'overview',
    isConnected: false,
    diagnosticsInterval: null,
    // v0.5.4: AI Helpers state
    aiContext: null,
    aiSchemas: null,
    aiPrompts: null,
    currentSchemaTab: 'plan',
    // v0.5.10: DB Queries state
    dbQueries: null,
    // v0.5.11: AI Profiles state
    aiProfiles: null,
    aiSecrets: null,
    // v0.5.12: AI Profile Health state
    aiHealth: null,
};

// =============================================================================
// DOM Elements
// =============================================================================

const elements = {
    root: () => document.getElementById('root'),
    loadingState: () => document.getElementById('loading-state'),
    errorState: () => document.getElementById('error-state'),
    errorMessage: () => document.getElementById('error-message'),
    contentArea: () => document.getElementById('content-area'),
    versionBadge: () => document.getElementById('version-badge'),
    connectionStatus: () => document.getElementById('connection-status'),
    themeToggle: () => document.getElementById('theme-toggle'),
    retryButton: () => document.getElementById('retry-button'),
};

// =============================================================================
// API Helpers
// =============================================================================

/**
 * Make a JSON GET request to the backend.
 * @param {string} path - API path (e.g., '/studio/handshake')
 * @returns {Promise<any>} JSON response
 */
async function jsonGet(path) {
    const response = await fetch(path, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
        },
        credentials: 'same-origin',
    });
    
    if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        throw error;
    }
    
    return response.json();
}

// =============================================================================
// Theme Management
// =============================================================================

function initTheme() {
    // Check for saved preference or system preference
    const saved = localStorage.getItem('aksara-studio-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('aksara-studio-theme', next);
}

// =============================================================================
// Connection Status
// =============================================================================

function updateConnectionStatus(status, text) {
    const el = elements.connectionStatus();
    if (!el) return;
    
    el.className = `connection-status ${status}`;
    const textEl = el.querySelector('.status-text');
    if (textEl) textEl.textContent = text;
}

// =============================================================================
// Navigation
// =============================================================================

function initNavigation() {
    // Handle nav item clicks
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            if (section) {
                navigateTo(section);
            }
        });
    });
    
    // Handle browser back/forward
    window.addEventListener('hashchange', () => {
        const hash = window.location.hash;
        const section = hash.replace('#/', '') || 'overview';
        if (section !== state.currentSection) {
            navigateTo(section, false);
        }
    });
}

function navigateTo(section, updateHash = true) {
    state.currentSection = section;
    
    // Update URL hash
    if (updateHash) {
        window.location.hash = `#/${section}`;
    }
    
    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });
    
    // Render the section
    renderSection(section);
}

// =============================================================================
// Section Rendering
// =============================================================================

function renderSection(section) {
    const template = document.getElementById(`template-${section}`);
    const contentArea = elements.contentArea();
    
    if (!template || !contentArea) return;
    
    // Clone template content
    const content = template.content.cloneNode(true);
    
    // Clear and append
    contentArea.innerHTML = '';
    contentArea.appendChild(content);
    
    // Section-specific rendering
    switch (section) {
        case 'overview':
            renderOverview();
            break;
        case 'models':
            renderModels();
            break;
        case 'routes':
            renderRoutes();
            break;
        case 'migrations':
            renderMigrations();
            break;
        case 'diagnostics':
            renderDiagnostics();
            break;
        case 'api':
            // Static content, no additional rendering needed
            break;
        case 'ai-helpers':
            renderAiHelpers();
            break;
        case 'db-queries':
            renderDbQueries();
            break;
        case 'ai-profiles':
            renderAiProfiles();
            break;
    }
}

// =============================================================================
// Overview Section
// =============================================================================

function renderOverview() {
    // Version info from handshake
    if (state.handshake) {
        const project = state.handshake.project || {};
        
        setText('aksara-version', project.aksara_version || '-');
        setText('python-version', project.python_version || '-');
        setText('environment', project.environment || '-');
        
        const debugBadge = document.getElementById('debug-badge');
        if (debugBadge) {
            if (project.debug_mode) {
                debugBadge.textContent = 'DEBUG';
                debugBadge.className = 'status debug';
            } else {
                debugBadge.textContent = 'PRODUCTION';
                debugBadge.className = 'status ok';
            }
        }
        
        // Database status
        const db = state.handshake.database || {};
        const dbStatus = document.getElementById('db-status');
        if (dbStatus) {
            if (db.connected) {
                dbStatus.textContent = 'Connected';
                dbStatus.className = 'status ok';
            } else {
                dbStatus.textContent = 'Disconnected';
                dbStatus.className = 'status error';
            }
        }
        setText('db-pool-size', db.pool_size ?? '-');
        setText('db-pool-available', db.pool_available ?? '-');
    }
    
    // Runtime info for uptime
    if (state.runtimeInfo) {
        setText('uptime', formatUptime(state.runtimeInfo.uptime_seconds));
    }
    
    // Context summary for stats and migrations
    if (state.contextSummary) {
        setText('model-count', state.contextSummary.model_count ?? '-');
        setText('route-count', state.contextSummary.route_count ?? '-');
        setText('viewset-count', state.contextSummary.viewset_count ?? '-');
        setText('ai-tool-count', state.contextSummary.ai_tool_count ?? '-');
        
        // Migration status
        const migStatus = state.contextSummary.migration_status || {};
        setText('migrations-total', migStatus.total ?? '-');
        setText('migrations-applied', migStatus.applied ?? '-');
        
        const pendingEl = document.getElementById('migrations-pending');
        if (pendingEl) {
            const pending = migStatus.pending ?? 0;
            pendingEl.textContent = pending;
            pendingEl.className = pending > 0 ? 'status warning' : 'status ok';
        }
    }
}

// =============================================================================
// Models Section
// =============================================================================

function renderModels() {
    const list = document.getElementById('models-list');
    if (!list) return;
    
    const models = state.contextSummary?.models || [];
    
    if (models.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>No models found</p></div>';
        return;
    }
    
    list.innerHTML = models.map(model => `
        <div class="model-card">
            <div class="model-header">
                <div>
                    <span class="model-name">${escapeHtml(model.name)}</span>
                    <span class="model-table">${escapeHtml(model.table_name)}</span>
                </div>
                <div class="model-meta">
                    <span>${model.field_count} fields</span>
                    ${model.has_relations ? '<span class="type-badge">Relations</span>' : ''}
                </div>
            </div>
        </div>
    `).join('');
    
    // Search functionality
    const searchInput = document.getElementById('models-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.model-card').forEach(card => {
                const name = card.querySelector('.model-name')?.textContent.toLowerCase() || '';
                const table = card.querySelector('.model-table')?.textContent.toLowerCase() || '';
                card.style.display = (name.includes(query) || table.includes(query)) ? '' : 'none';
            });
        });
    }
}

// =============================================================================
// Routes Section
// =============================================================================

function renderRoutes() {
    const tbody = document.getElementById('routes-tbody');
    if (!tbody) return;
    
    const routes = state.routes || [];
    
    if (routes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No routes found</td></tr>';
        return;
    }
    
    renderRoutesTable(routes);
    
    // Search functionality
    const searchInput = document.getElementById('routes-search');
    if (searchInput) {
        searchInput.addEventListener('input', filterRoutes);
    }
    
    // Filter checkboxes
    ['filter-studio', 'filter-admin', 'filter-ai', 'filter-api'].forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.addEventListener('change', filterRoutes);
        }
    });
}

function renderRoutesTable(routes) {
    const tbody = document.getElementById('routes-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = routes.map(route => {
        const methods = (route.methods || []).map(m => 
            `<span class="method-badge ${m.toLowerCase()}">${m}</span>`
        ).join(' ');
        
        let typeBadges = '';
        if (route.is_studio) typeBadges += '<span class="type-badge studio">Studio</span>';
        if (route.is_admin) typeBadges += '<span class="type-badge admin">Admin</span>';
        if (route.is_ai) typeBadges += '<span class="type-badge ai">AI</span>';
        if (!route.is_studio && !route.is_admin && !route.is_ai) {
            typeBadges += '<span class="type-badge api">API</span>';
        }
        
        return `
            <tr data-studio="${route.is_studio}" data-admin="${route.is_admin}" data-ai="${route.is_ai}">
                <td>${methods}</td>
                <td><code>${escapeHtml(route.path)}</code></td>
                <td>${escapeHtml(route.name || '-')}</td>
                <td>${typeBadges}</td>
            </tr>
        `;
    }).join('');
}

function filterRoutes() {
    const searchInput = document.getElementById('routes-search');
    const query = searchInput?.value.toLowerCase() || '';
    
    const showStudio = document.getElementById('filter-studio')?.checked ?? true;
    const showAdmin = document.getElementById('filter-admin')?.checked ?? true;
    const showAI = document.getElementById('filter-ai')?.checked ?? true;
    const showAPI = document.getElementById('filter-api')?.checked ?? true;
    
    document.querySelectorAll('#routes-tbody tr').forEach(row => {
        const path = row.querySelector('code')?.textContent.toLowerCase() || '';
        const name = row.cells[2]?.textContent.toLowerCase() || '';
        
        const matchesSearch = path.includes(query) || name.includes(query);
        
        const isStudio = row.dataset.studio === 'true';
        const isAdmin = row.dataset.admin === 'true';
        const isAI = row.dataset.ai === 'true';
        const isAPI = !isStudio && !isAdmin && !isAI;
        
        const matchesFilter = 
            (isStudio && showStudio) ||
            (isAdmin && showAdmin) ||
            (isAI && showAI) ||
            (isAPI && showAPI);
        
        row.style.display = (matchesSearch && matchesFilter) ? '' : 'none';
    });
}

// =============================================================================
// Migrations Section
// =============================================================================

function renderMigrations() {
    if (!state.migrations) {
        fetchMigrations().then(() => renderMigrationsData());
    } else {
        renderMigrationsData();
    }
}

async function fetchMigrations() {
    try {
        state.migrations = await jsonGet('/studio/migrations/summary');
    } catch (err) {
        console.error('Failed to fetch migrations:', err);
    }
}

function renderMigrationsData() {
    const mig = state.migrations;
    if (!mig) return;
    
    setText('mig-total', mig.total_migrations ?? '-');
    setText('mig-applied', mig.applied_migrations ?? '-');
    
    const pendingEl = document.getElementById('mig-pending');
    if (pendingEl) {
        const pending = mig.pending_migrations ?? 0;
        pendingEl.textContent = pending;
        pendingEl.className = pending > 0 ? 'status warning' : 'status ok';
    }
    
    const conflictsEl = document.getElementById('mig-conflicts');
    if (conflictsEl) {
        const hasConflicts = mig.conflicts && mig.conflicts.length > 0;
        conflictsEl.textContent = hasConflicts ? 'Yes' : 'None';
        conflictsEl.className = hasConflicts ? 'status error' : 'status ok';
    }
    
    setText('mig-last-applied', mig.last_applied || 'None');
    
    // Apps list
    const appsList = document.getElementById('mig-apps-list');
    if (appsList && mig.apps && mig.apps.length > 0) {
        appsList.innerHTML = mig.apps.map(app => `
            <div class="app-item">
                <span class="app-name">${escapeHtml(app.app_label)}</span>
                <div class="app-stats">
                    <span>Applied: ${app.applied}</span>
                    <span>Pending: ${app.pending}</span>
                </div>
            </div>
        `).join('');
    }
    
    // Conflicts
    const conflictsCard = document.getElementById('conflicts-card');
    const conflictsList = document.getElementById('mig-conflicts-list');
    if (conflictsCard && conflictsList && mig.conflicts && mig.conflicts.length > 0) {
        conflictsCard.style.display = '';
        conflictsList.innerHTML = mig.conflicts.map(c => `
            <div class="conflict-item">
                <div class="conflict-app">${escapeHtml(c.app_label)}</div>
                <div class="conflict-heads">${escapeHtml(c.heads.join(', '))}</div>
            </div>
        `).join('');
    }
}

// =============================================================================
// Diagnostics Section
// =============================================================================

function renderDiagnostics() {
    updateDiagnosticsData();
    
    // Set up auto-refresh
    if (state.diagnosticsInterval) {
        clearInterval(state.diagnosticsInterval);
    }
    state.diagnosticsInterval = setInterval(fetchAndUpdateDiagnostics, 5000);
    
    // Manual refresh button
    const refreshBtn = document.getElementById('refresh-diagnostics');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchAndUpdateDiagnostics);
    }
}

async function fetchAndUpdateDiagnostics() {
    try {
        state.runtimeInfo = await jsonGet('/studio/runtime/info');
        updateDiagnosticsData();
    } catch (err) {
        console.error('Failed to fetch diagnostics:', err);
    }
}

function updateDiagnosticsData() {
    const info = state.runtimeInfo;
    if (!info) return;
    
    setText('diag-pid', info.pid ?? '-');
    setText('diag-start-time', formatDateTime(info.start_time));
    setText('diag-uptime', formatUptime(info.uptime_seconds));
    
    const dbStatus = document.getElementById('diag-db-status');
    if (dbStatus) {
        const status = info.database_status || 'disconnected';
        dbStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        dbStatus.className = `status ${status === 'ok' ? 'ok' : status === 'degraded' ? 'warning' : 'error'}`;
    }
    
    setText('diag-pending-mig', info.pending_migrations ?? '-');
    
    const studioEnabled = document.getElementById('diag-studio-enabled');
    if (studioEnabled) {
        studioEnabled.textContent = info.studio_enabled ? 'Yes' : 'No';
        studioEnabled.className = info.studio_enabled ? 'status ok' : 'status warning';
    }
    
    setText('diag-studio-path', info.studio_base_path || '/studio');
    
    // Installed apps
    const appsList = document.getElementById('diag-apps-list');
    if (appsList && info.installed_apps && info.installed_apps.length > 0) {
        appsList.innerHTML = info.installed_apps.map(app => 
            `<span class="app-badge">${escapeHtml(app)}</span>`
        ).join('');
    }
}

// =============================================================================
// v0.5.4: AI Helpers Section
// =============================================================================

function renderAiHelpers() {
    // Fetch all AI data
    fetchAiContext();
    fetchAiSchemas();
    fetchAiPrompts();
    
    // Set up event listeners
    setupAiHelpersListeners();
}

async function fetchAiContext() {
    const pre = document.getElementById('ai-context-json');
    if (!pre) return;
    
    try {
        state.aiContext = await jsonGet('/studio/ai/context');
        pre.innerHTML = `<code>${escapeHtml(JSON.stringify(state.aiContext, null, 2))}</code>`;
    } catch (err) {
        pre.innerHTML = `<code class="error">Error loading context: ${escapeHtml(err.message)}</code>`;
    }
}

async function fetchAiSchemas() {
    const pre = document.getElementById('ai-schema-json');
    if (!pre) return;
    
    try {
        state.aiSchemas = await jsonGet('/studio/ai/schemas');
        updateSchemaDisplay();
    } catch (err) {
        pre.innerHTML = `<code class="error">Error loading schemas: ${escapeHtml(err.message)}</code>`;
    }
}

function updateSchemaDisplay() {
    const pre = document.getElementById('ai-schema-json');
    const label = document.getElementById('schema-label');
    if (!pre || !state.aiSchemas) return;
    
    const schemaMap = {
        'plan': { data: state.aiSchemas.plan_schema, name: 'Plan Schema' },
        'patch': { data: state.aiSchemas.patch_schema, name: 'Patch Schema' },
        'query': { data: state.aiSchemas.query_schema, name: 'Query Schema' },
        'codegen': { data: state.aiSchemas.codegen_schema, name: 'Codegen Schema' },
    };
    
    const current = schemaMap[state.currentSchemaTab] || schemaMap['plan'];
    pre.innerHTML = `<code>${escapeHtml(JSON.stringify(current.data, null, 2))}</code>`;
    if (label) label.textContent = current.name;
}

async function fetchAiPrompts() {
    const list = document.getElementById('prompt-templates-list');
    if (!list) return;
    
    try {
        state.aiPrompts = await jsonGet('/studio/ai/prompts');
        renderPromptTemplates();
    } catch (err) {
        list.innerHTML = `<div class="error-state">Error loading prompts: ${escapeHtml(err.message)}</div>`;
    }
}

function renderPromptTemplates() {
    const list = document.getElementById('prompt-templates-list');
    if (!list || !state.aiPrompts) return;
    
    const prompts = state.aiPrompts.prompts || [];
    
    if (prompts.length === 0) {
        list.innerHTML = '<div class="empty-state">No prompt templates available</div>';
        return;
    }
    
    list.innerHTML = prompts.map((prompt, index) => `
        <div class="prompt-card" data-prompt-id="${escapeHtml(prompt.id)}">
            <div class="prompt-header">
                <div>
                    <span class="prompt-title">${escapeHtml(prompt.title)}</span>
                    <span class="prompt-category">${escapeHtml(prompt.category)}</span>
                </div>
                <button class="btn btn-sm btn-copy copy-prompt-btn" data-index="${index}">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2"></rect>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
                    </svg>
                    Copy
                </button>
            </div>
            <p class="prompt-description">${escapeHtml(prompt.description)}</p>
            <details class="prompt-details">
                <summary>View Template</summary>
                <pre class="prompt-template"><code>${escapeHtml(prompt.template)}</code></pre>
            </details>
            <div class="prompt-placeholders">
                <span class="placeholder-label">Placeholders:</span>
                ${prompt.placeholders.map(p => `<code class="placeholder">{${escapeHtml(p)}}</code>`).join(' ')}
            </div>
        </div>
    `).join('');
}

function setupAiHelpersListeners() {
    // Refresh buttons
    document.getElementById('refresh-ai-context')?.addEventListener('click', fetchAiContext);
    document.getElementById('refresh-ai-schemas')?.addEventListener('click', fetchAiSchemas);
    document.getElementById('refresh-ai-prompts')?.addEventListener('click', fetchAiPrompts);
    
    // Copy context button
    document.getElementById('copy-ai-context')?.addEventListener('click', () => {
        if (state.aiContext) {
            copyToClipboard(JSON.stringify(state.aiContext, null, 2), 'AI context copied!');
        }
    });
    
    // Copy schema button
    document.getElementById('copy-ai-schema')?.addEventListener('click', () => {
        if (state.aiSchemas) {
            const schemaMap = {
                'plan': state.aiSchemas.plan_schema,
                'patch': state.aiSchemas.patch_schema,
                'query': state.aiSchemas.query_schema,
                'codegen': state.aiSchemas.codegen_schema,
            };
            const schema = schemaMap[state.currentSchemaTab] || schemaMap['plan'];
            copyToClipboard(JSON.stringify(schema, null, 2), 'Schema copied!');
        }
    });
    
    // Schema tabs
    document.querySelectorAll('.schema-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.schema-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.currentSchemaTab = tab.dataset.schema;
            updateSchemaDisplay();
        });
    });
    
    // Prompt copy buttons (delegated)
    document.getElementById('prompt-templates-list')?.addEventListener('click', (e) => {
        const copyBtn = e.target.closest('.copy-prompt-btn');
        if (copyBtn && state.aiPrompts) {
            const index = parseInt(copyBtn.dataset.index, 10);
            const prompt = state.aiPrompts.prompts[index];
            if (prompt) {
                copyToClipboard(prompt.template, 'Prompt template copied!');
            }
        }
    });
}

/**
 * Copy text to clipboard with feedback.
 * @param {string} text - Text to copy
 * @param {string} message - Success message to show
 */
function copyToClipboard(text, message = 'Copied!') {
    navigator.clipboard.writeText(text).then(() => {
        showToast(message);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy', 'error');
    });
}

/**
 * Show a toast notification.
 * @param {string} message - Message to show
 * @param {string} type - 'success' or 'error'
 */
function showToast(message, type = 'success') {
    // Remove existing toast
    document.querySelector('.toast')?.remove();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// =============================================================================
// Utility Functions
// =============================================================================

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatUptime(seconds) {
    if (!seconds && seconds !== 0) return '-';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
    if (minutes > 0) return `${minutes}m ${secs}s`;
    return `${secs}s`;
}

function formatDateTime(isoString) {
    if (!isoString) return '-';
    try {
        const date = new Date(isoString);
        return date.toLocaleString();
    } catch {
        return isoString;
    }
}

// =============================================================================
// v0.5.10: DB & Queries Section
// =============================================================================

async function renderDbQueries() {
    // Initial render with empty state
    const refreshBtn = document.getElementById('refresh-db-queries');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadDbQueries());
    }
    
    // Load data
    await loadDbQueries();
}

async function loadDbQueries() {
    try {
        state.dbQueries = await jsonGet('/studio/db/queries');
        renderDbQueriesData();
    } catch (err) {
        console.error('Failed to load DB queries:', err);
        showToast('Failed to load query data', 'error');
    }
}

function renderDbQueriesData() {
    const data = state.dbQueries;
    if (!data) return;
    
    // Show/hide disabled banner
    const disabledBanner = document.getElementById('tracing-disabled-banner');
    if (disabledBanner) {
        disabledBanner.classList.toggle('hidden', data.enabled);
    }
    
    // Update stats
    setText('db-total-queries', data.stats?.total_queries ?? '-');
    setText('db-avg-queries', data.stats?.avg_queries_per_request?.toFixed(2) ?? '-');
    setText('db-slow-queries', data.stats?.total_slow_queries ?? '0');
    setText('db-n1-count', data.stats?.requests_with_n_plus_one ?? '0');
    
    // Update threshold badge
    const thresholdBadge = document.getElementById('slow-threshold-badge');
    if (thresholdBadge) {
        thresholdBadge.textContent = `Threshold: ${data.slow_threshold_ms}ms`;
    }
    
    // Render slow queries
    const slowList = document.getElementById('slow-queries-list');
    if (slowList) {
        const slowQueries = data.top_slow_queries || [];
        if (slowQueries.length === 0) {
            slowList.innerHTML = '<div class="empty-state"><p>No slow queries recorded</p></div>';
        } else {
            slowList.innerHTML = slowQueries.slice(0, 10).map(q => `
                <div class="query-item slow">
                    <div class="query-header">
                        <span class="query-operation ${q.operation.toLowerCase()}">${escapeHtml(q.operation)}</span>
                        <span class="query-table">${escapeHtml(q.table || 'unknown')}</span>
                        <span class="query-duration">${q.duration_ms.toFixed(2)}ms</span>
                    </div>
                    <pre class="query-sql">${escapeHtml(truncateSql(q.sql))}</pre>
                    ${q.stack_summary ? `<div class="query-stack">${escapeHtml(q.stack_summary)}</div>` : ''}
                </div>
            `).join('');
        }
    }
    
    // Render recent requests
    const requestsList = document.getElementById('recent-requests-list');
    if (requestsList) {
        const batches = data.recent_batches || [];
        if (batches.length === 0) {
            requestsList.innerHTML = '<div class="empty-state"><p>No requests recorded yet</p></div>';
        } else {
            requestsList.innerHTML = batches.map(batch => {
                const statusClass = batch.status_code >= 400 ? 'error' : batch.status_code >= 300 ? 'warning' : 'ok';
                const hasWarnings = batch.slow_queries > 0 || batch.n_plus_one_suspicions?.length > 0;
                
                return `
                <div class="request-item ${hasWarnings ? 'has-warnings' : ''}">
                    <div class="request-header">
                        <span class="request-method ${(batch.method || '').toLowerCase()}">${escapeHtml(batch.method || '-')}</span>
                        <span class="request-path">${escapeHtml(batch.path || '/')}</span>
                        <span class="request-status status-${statusClass}">${batch.status_code || '-'}</span>
                    </div>
                    <div class="request-stats">
                        <span class="request-queries">${batch.total_queries} queries</span>
                        <span class="request-duration">${batch.total_duration_ms.toFixed(2)}ms</span>
                        ${batch.slow_queries > 0 ? `<span class="request-slow">⚠️ ${batch.slow_queries} slow</span>` : ''}
                        ${batch.n_plus_one_suspicions?.length > 0 ? `<span class="request-n1">🔄 N+1</span>` : ''}
                    </div>
                    ${batch.n_plus_one_suspicions?.length > 0 ? `
                        <div class="request-warnings">
                            ${batch.n_plus_one_suspicions.map(w => `<div class="warning-item">${escapeHtml(w)}</div>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
            }).join('');
        }
    }
}

function truncateSql(sql) {
    if (!sql) return '';
    const maxLen = 200;
    if (sql.length <= maxLen) return sql;
    return sql.substring(0, maxLen) + '...';
}

// =============================================================================
// v0.5.11: AI Profiles Section
// =============================================================================

async function renderAiProfiles() {
    // Set up event listeners
    const refreshBtn = document.getElementById('refresh-ai-profiles');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadAiProfiles());
    }
    
    const copyBtn = document.getElementById('copy-ai-profiles');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const json = document.getElementById('ai-profiles-json');
            if (json) {
                copyToClipboard(json.textContent);
                showToast('Profile set JSON copied to clipboard');
            }
        });
    }
    
    // Load both profiles and secrets
    await Promise.all([loadAiProfiles(), loadAiSecrets(), loadAiHealth()]);
}

async function loadAiProfiles() {
    try {
        state.aiProfiles = await jsonGet('/studio/ai/profiles');
        renderAiProfilesData();
    } catch (err) {
        console.error('Failed to load AI profiles:', err);
        showToast('Failed to load AI profiles', 'error');
    }
}

async function loadAiSecrets() {
    try {
        state.aiSecrets = await jsonGet('/studio/ai/secrets');
        renderAiSecretsData();
    } catch (err) {
        console.error('Failed to load AI secrets:', err);
        showToast('Failed to load AI secrets', 'error');
    }
}

// v0.5.12: Load AI profile health
async function loadAiHealth() {
    try {
        state.aiHealth = await jsonGet('/studio/ai/health');
        renderAiHealthData();
    } catch (err) {
        console.error('Failed to load AI health:', err);
        // Show error in health banner
        const banner = document.getElementById('ai-health-banner');
        if (banner) {
            banner.classList.remove('hidden');
            banner.innerHTML = '<div class="ai-health-error-text">Could not load AI profile health</div>';
        }
    }
}

// v0.5.12: Render AI profile health data
function renderAiHealthData() {
    const health = state.aiHealth;
    if (!health) return;
    
    const banner = document.getElementById('ai-health-banner');
    const badge = document.getElementById('ai-health-badge');
    const summary = document.getElementById('ai-health-summary');
    const issuesList = document.getElementById('ai-health-issues');
    
    if (!banner || !badge || !summary || !issuesList) return;
    
    // Show banner
    banner.classList.remove('hidden');
    
    // Determine health status class
    let statusClass = 'health-ok';
    let badgeText = 'OK';
    
    if (health.error_count > 0) {
        statusClass = 'health-error';
        badgeText = 'ERRORS';
    } else if (health.warning_count > 0) {
        statusClass = 'health-warning';
        badgeText = 'WARNINGS';
    }
    
    // Update banner class
    banner.className = `ai-health-banner ${statusClass}`;
    
    // Update badge
    badge.className = `ai-health-badge ${statusClass}`;
    badge.textContent = badgeText;
    
    // Update summary
    const parts = [];
    if (health.error_count > 0) parts.push(`${health.error_count} error(s)`);
    if (health.warning_count > 0) parts.push(`${health.warning_count} warning(s)`);
    if (health.info_count > 0) parts.push(`${health.info_count} info`);
    
    if (parts.length > 0) {
        summary.textContent = parts.join(', ');
    } else {
        summary.textContent = 'Configuration is valid';
    }
    
    // Render issues
    if (health.issues && health.issues.length > 0) {
        issuesList.innerHTML = health.issues.map(issue => `
            <div class="ai-health-issue">
                <span class="ai-health-issue-severity ${issue.severity}">${escapeHtml(issue.severity.toUpperCase())}</span>
                <span class="ai-health-issue-message">${escapeHtml(issue.message)}</span>
            </div>
        `).join('');
    } else {
        issuesList.innerHTML = '';
    }
}

function renderAiProfilesData() {
    const data = state.aiProfiles;
    if (!data) return;
    
    // Show/hide disabled banner
    const disabledBanner = document.getElementById('ai-profiles-disabled-banner');
    if (disabledBanner) {
        disabledBanner.classList.toggle('hidden', data.enabled);
    }
    
    // Update stats
    setText('ai-provider-count', data.providers?.length ?? '-');
    setText('ai-model-count', data.total_models ?? '-');
    setText('ai-default-provider', data.default_provider || 'None');
    setText('ai-environment', data.environment || '-');
    
    // Render providers list
    const providersList = document.getElementById('ai-providers-list');
    if (providersList) {
        const providers = data.providers || [];
        if (providers.length === 0) {
            providersList.innerHTML = '<div class="empty-state"><p>No AI providers configured</p></div>';
        } else {
            providersList.innerHTML = providers.map(provider => {
                const isDefault = provider.name === data.default_provider;
                const models = provider.models || [];
                
                return `
                <div class="provider-card ${isDefault ? 'is-default' : ''} ${provider.is_example ? 'is-example' : ''}">
                    <div class="provider-header">
                        <span class="provider-name">${escapeHtml(provider.display_name)}</span>
                        <span class="provider-kind badge badge-${provider.kind}">${escapeHtml(provider.kind)}</span>
                        ${isDefault ? '<span class="badge badge-primary">Default</span>' : ''}
                        ${provider.is_example ? '<span class="badge badge-warning">Example</span>' : ''}
                    </div>
                    <div class="provider-meta">
                        <span class="provider-id">${escapeHtml(provider.name)}</span>
                        <span class="provider-models">${provider.model_count} models</span>
                        ${provider.has_custom_base_url ? '<span class="badge badge-secondary">Custom URL</span>' : ''}
                    </div>
                    <div class="models-list">
                        ${models.map(model => `
                            <div class="model-item">
                                <div class="model-header">
                                    <span class="model-name">${escapeHtml(model.name)}</span>
                                    <span class="model-kind badge badge-${model.kind}">${escapeHtml(model.kind)}</span>
                                </div>
                                <div class="model-caps">
                                    ${model.supports_tools ? '<span class="cap cap-tools" title="Supports tool calling">🔧</span>' : ''}
                                    ${model.supports_streaming ? '<span class="cap cap-streaming" title="Supports streaming">⚡</span>' : ''}
                                    ${model.supports_vision ? '<span class="cap cap-vision" title="Supports vision">👁️</span>' : ''}
                                </div>
                                <div class="model-tokens">
                                    ${model.max_input_tokens ? `<span class="token-limit">↓${formatTokenCount(model.max_input_tokens)}</span>` : ''}
                                    ${model.max_output_tokens ? `<span class="token-limit">↑${formatTokenCount(model.max_output_tokens)}</span>` : ''}
                                </div>
                                ${model.tags?.length > 0 ? `
                                    <div class="model-tags">
                                        ${model.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            }).join('');
        }
    }
    
    // Update JSON export
    const jsonPre = document.getElementById('ai-profiles-json');
    if (jsonPre) {
        jsonPre.innerHTML = `<code>${escapeHtml(JSON.stringify(data, null, 2))}</code>`;
    }
}

function renderAiSecretsData() {
    const data = state.aiSecrets;
    if (!data) return;
    
    // Update badge
    const badge = document.getElementById('secrets-count-badge');
    if (badge) {
        badge.textContent = `${data.configured_count}/${data.total_count} configured`;
        badge.className = `badge ${data.configured_count === data.total_count ? 'badge-success' : 'badge-warning'}`;
    }
    
    // Render secrets list
    const secretsList = document.getElementById('ai-secrets-list');
    if (secretsList) {
        const secrets = data.secrets || [];
        if (secrets.length === 0) {
            secretsList.innerHTML = '<div class="empty-state"><p>No secrets required</p></div>';
        } else {
            secretsList.innerHTML = secrets.map(secret => `
                <div class="secret-item ${secret.is_configured ? 'configured' : 'missing'}">
                    <div class="secret-header">
                        <span class="secret-var">${escapeHtml(secret.env_var)}</span>
                        <span class="secret-status ${secret.is_configured ? 'ok' : 'warning'}">
                            ${secret.is_configured ? '✓ Configured' : '✗ Not set'}
                        </span>
                    </div>
                    <div class="secret-meta">
                        <span class="secret-provider">Provider: ${escapeHtml(secret.provider_name)}</span>
                        ${secret.required ? '<span class="badge badge-error">Required</span>' : '<span class="badge badge-secondary">Optional</span>'}
                    </div>
                    ${secret.description ? `<div class="secret-desc">${escapeHtml(secret.description)}</div>` : ''}
                </div>
            `).join('');
        }
    }
}

function formatTokenCount(count) {
    if (count >= 1000000) {
        return (count / 1000000).toFixed(0) + 'M';
    }
    if (count >= 1000) {
        return (count / 1000).toFixed(0) + 'K';
    }
    return count.toString();
}

// =============================================================================
// Initialization
// =============================================================================

async function init() {
    console.log('Aksara Studio initializing...');
    
    // Initialize theme
    initTheme();
    
    // Set up event listeners
    const themeToggle = elements.themeToggle();
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    const retryButton = elements.retryButton();
    if (retryButton) {
        retryButton.addEventListener('click', () => {
            elements.errorState()?.classList.add('hidden');
            elements.loadingState()?.classList.remove('hidden');
            init();
        });
    }
    
    // Initialize navigation
    initNavigation();
    
    try {
        // Fetch initial data
        updateConnectionStatus('', 'Connecting...');
        
        const [handshake, contextSummary, runtimeInfo, routes] = await Promise.all([
            jsonGet('/studio/handshake'),
            jsonGet('/studio/context/summary'),
            jsonGet('/studio/runtime/info'),
            jsonGet('/studio/runtime/routes'),
        ]);
        
        state.handshake = handshake;
        state.contextSummary = contextSummary;
        state.runtimeInfo = runtimeInfo;
        state.routes = routes;
        state.isConnected = true;
        
        // Update UI
        updateConnectionStatus('connected', 'Connected');
        
        // Update version badge
        const versionBadge = elements.versionBadge();
        if (versionBadge && handshake.project) {
            versionBadge.textContent = `v${handshake.project.aksara_version}`;
        }
        
        // Show content
        elements.loadingState()?.classList.add('hidden');
        elements.contentArea()?.classList.remove('hidden');
        
        // Navigate to initial section (from hash or default)
        const hash = window.location.hash;
        const section = hash.replace('#/', '') || 'overview';
        navigateTo(section, false);
        
        console.log('Aksara Studio initialized successfully');
        
    } catch (err) {
        console.error('Failed to initialize Aksara Studio:', err);
        
        state.isConnected = false;
        updateConnectionStatus('error', 'Error');
        
        // Show error state
        elements.loadingState()?.classList.add('hidden');
        elements.contentArea()?.classList.add('hidden');
        elements.errorState()?.classList.remove('hidden');
        
        const errorMessage = elements.errorMessage();
        if (errorMessage) {
            if (err.status === 403) {
                errorMessage.textContent = 'Access denied. Check CORS configuration or studio_allowed_origins setting.';
            } else if (err.status === 404) {
                errorMessage.textContent = 'Studio endpoints not found. Make sure Studio is enabled.';
            } else {
                errorMessage.textContent = `Unable to connect to Aksara backend: ${err.message}`;
            }
        }
    }
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (state.diagnosticsInterval) {
        clearInterval(state.diagnosticsInterval);
    }
});

// Start the app
document.addEventListener('DOMContentLoaded', init);
