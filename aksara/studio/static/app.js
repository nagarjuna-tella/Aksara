/**
 * Aksara Studio - Dashboard Application
 * 
 * Zero-dependency, zero-build JavaScript for Aksara Studio dashboard.
 * Uses vanilla JS with modern ES6+ features.
 * 
 * v0.5.16
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
    // v0.5.17: Diagnostics 2.0 state
    diagnosticsReport: null,
    diagnosticsLive: true,
    diagnosticsFilter: 'all',
    diagnosticsSearchQuery: '',
    // v0.5.4: AI Helpers state
    aiContext: null,
    aiSchemas: null,
    aiPrompts: null,
    currentSchemaTab: 'plan',
    // v0.5.10: DB Queries state
    dbQueries: null,
    dbQueriesInterval: null,   // v0.5.16: auto-refresh timer
    dbQueriesLive: false,      // v0.5.16: live/paused toggle
    // v0.5.11: AI Profiles state
    aiProfiles: null,
    aiSecrets: null,
    // v0.5.12: AI Profile Health state
    aiHealth: null,
    // v0.5.13: AI Hints state
    aiHints: null,
    // v0.5.19: Agent Mode state
    agent: {
        context: null, selectedSections: [], lastPromptResponse: null,
        // v0.5.20: Playbooks state
        playbooks: null, selectedPlaybook: null, playbookFilter: 'all', playbookSearch: '',
        // v0.5.23: Workflows state
        lastWorkflowResponse: null,
    },
    // v0.5.21: Model Inspector state
    modelInspector: null,
    modelInspectorSelected: null,
    // v0.5.22: Spotlight Search state
    spotlight: {
        visible: false,
        query: '',
        results: [],
        selectedIndex: 0,
        kindFilter: 'all',
        debounceTimer: null,
        indexInfo: null,
    },
    // v0.5.25: AI Hub state
    aiHub: {
        providers: null,
        agentOutput: null,
        contextData: null,
        // v0.5.28: AI Hub 2.0 state
        status: null,
        models: null,
        routing: null,
        onboardingState: { selectedProviders: [] },
    },
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

/**
 * Make a JSON POST request to the backend.
 * @param {string} url - API path (e.g., '/studio/db/plan')
 * @param {any} body - JSON-serialisable payload
 * @returns {Promise<any>} JSON response
 */
async function jsonPost(url, body) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        const err = new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        err.status = resp.status;
        throw err;
    }
    return resp.json();
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
    
    // v0.5.16: Keyboard shortcuts 1-7
    const sectionKeys = {
        'Digit1': 'overview',
        'Digit2': 'models',
        'Digit3': 'routes',
        'Digit4': 'migrations',
        'Digit5': 'diagnostics',
        'Digit6': 'gaps',
        'Digit7': 'db-queries',
        'Digit8': 'ai-hub',
    };
    document.addEventListener('keydown', (e) => {
        // v0.5.22: Cmd/Ctrl+K opens Spotlight Search (always, even in inputs)
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            toggleSpotlight();
            return;
        }
        // Ignore when typing in inputs / textareas / selects
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) {
            // v0.5.17: Escape clears and blurs search inputs
            if (e.key === 'Escape') {
                e.target.value = '';
                e.target.dispatchEvent(new Event('input'));
                e.target.blur();
            }
            return;
        }
        const section = sectionKeys[e.code];
        if (section) {
            e.preventDefault();
            navigateTo(section);
            return;
        }
        // v0.5.17: 'd' key navigates to diagnostics
        if (e.key === 'd' || e.key === 'D') {
            e.preventDefault();
            navigateTo('diagnostics');
            return;
        }
        // v0.5.27: 'g' key navigates to gap analysis
        if (e.key === 'g' && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
            e.preventDefault();
            navigateTo('gaps');
            return;
        }
        // v0.5.17: '/' key focuses the diagnostics search input (if visible)
        if (e.key === '/') {
            const searchInput = document.getElementById('diag-search')
                || document.getElementById('mig-search');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
        // v0.5.19: Cmd/Ctrl+G triggers agent prompt generation
        if ((e.metaKey || e.ctrlKey) && e.key === 'g') {
            e.preventDefault();
            const btn = document.getElementById('agent-generate-btn');
            if (btn) btn.click();
        }
        // v0.5.20: Shift+P opens AI Hub Agent tab
        if (e.shiftKey && e.key === 'P') {
            e.preventDefault();
            navigateTo('ai-hub');
        }
        // v0.5.42: 'A' opens AI Console (redirected from AI Home)
        if (e.key === 'a' && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
            e.preventDefault();
            navigateTo('ai-console');
            return;
        }
        // v0.5.42: Alt/Option+A opens AI Console (works from anywhere)
        if (e.altKey && (e.key === 'a' || e.key === 'A') && !e.metaKey && !e.ctrlKey) {
            e.preventDefault();
            navigateTo('ai-console');
            return;
        }
        // v0.5.25: Cmd/Ctrl+Enter runs AI Hub agent prompt
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            const btn = document.getElementById('ai-hub-agent-run');
            if (btn) btn.click();
        }
    });
}

function navigateTo(section, updateHash = true) {
    // Stop timers for previous section
    stopSectionTimers();
    
    // v0.5.25: Redirect consolidated sections to their new homes
    // v0.5.38: Redirect individual AI tools to unified Inspector
    // v0.5.42: Redirect ai-home to ai-console (ai-home removed from nav)
    const redirects = {
        'api': 'routes',
        'model-inspector': 'models',
        'ai-helpers': 'ai-hub',
        'ai-profiles': 'ai-hub',
        'agent': 'ai-hub',
        'ai-debugger': 'ai-inspector',
        'ai-architecture': 'ai-inspector',
        'ai-performance': 'ai-inspector',
        'ai-home': 'ai-console',
    };
    const activateTab = {
        'api': { attr: 'data-routes-tab', value: 'api-ref' },
        'model-inspector': { attr: 'data-models-tab', value: 'inspector' },
        'ai-helpers': { tab: 'helpers' },
        'ai-profiles': { tab: 'profiles' },
        'agent': { tab: 'agent' },
        'ai-debugger': { inspectorTab: 'debug' },
        'ai-architecture': { inspectorTab: 'architecture' },
        'ai-performance': { inspectorTab: 'performance' },
    };
    const tabInfo = activateTab[section];
    const redirected = redirects[section];
    if (redirected) {
        section = redirected;
    }

    state.currentSection = section;
    
    // Update URL hash
    if (updateHash) {
        window.location.hash = `#/${section}`;
    }
    
    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    // v0.5.42: Auto-expand Advanced nav group when navigating to an advanced section
    const advancedSections = ['ai-graph', 'ai-hub'];
    if (advancedSections.includes(section)) {
        const advToggle = document.getElementById('nav-advanced-toggle');
        const advItems = document.getElementById('nav-advanced-items');
        if (advToggle && advItems && advItems.hidden) {
            advToggle.setAttribute('aria-expanded', 'true');
            advItems.hidden = false;
        }
    }

    // Render the section
    renderSection(section);

    // v0.5.25: Activate the right tab after rendering for redirected sections
    // v0.5.38: Also handle inspector tab activation
    if (tabInfo) {
        setTimeout(() => {
            if (tabInfo.inspectorTab) {
                const tabBtn = document.querySelector(`.ai-inspector-tab[data-inspector-tab="${tabInfo.inspectorTab}"]`);
                if (tabBtn) tabBtn.click();
            } else if (tabInfo.tab) {
                // AI Hub tab
                const tabBtn = document.querySelector(`.ai-hub-tab[data-tab="${tabInfo.tab}"]`);
                if (tabBtn) tabBtn.click();
            } else if (tabInfo.attr) {
                // Section sub-tab (models/routes)
                const tabBtn = document.querySelector(`.section-tab[${tabInfo.attr}="${tabInfo.value}"]`);
                if (tabBtn) tabBtn.click();
            }
        }, 50);
    }
}

// v0.5.16: Clean up timers when leaving a section
function stopSectionTimers() {
    // Stop DB queries auto-refresh
    if (state.dbQueriesInterval) {
        clearInterval(state.dbQueriesInterval);
        state.dbQueriesInterval = null;
    }
    state.dbQueriesLive = false;
    // v0.5.17: Stop diagnostics auto-refresh
    if (state.diagnosticsInterval) {
        clearInterval(state.diagnosticsInterval);
        state.diagnosticsInterval = null;
    }
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
            initSectionTabs('models');
            break;
        case 'routes':
            renderRoutes();
            initSectionTabs('routes');
            break;
        case 'migrations':
            renderMigrations();
            break;
        case 'diagnostics':
            renderDiagnostics();
            break;
        case 'gaps':
            renderGaps();
            break;
        case 'db-queries':
            renderDbQueries();
            break;
        case 'ai-home':
            renderAiHome();
            break;
        case 'ai-hub':
            renderAiHub();
            break;
        case 'ai-console':
            renderAiConsole();
            break;
        case 'ai-inspector':
            renderAiInspector();
            break;
        case 'ai-graph':
            renderAiGraph();
            break;
    }

    // v0.5.29: init AI flow dropdowns + row selection hooks after render
    initAiFlowDropdowns();
    _hookAiFlowRowSelection();
    _syncFlowButtonStates();
}

// v0.5.25: Generic section tab switching for merged sections (Models, Routes)
function initSectionTabs(sectionName) {
    const tabAttr = `data-${sectionName}-tab`;
    const panelAttr = `data-${sectionName}-panel`;
    document.querySelectorAll(`.section-tab[${tabAttr}]`).forEach(btn => {
        btn.addEventListener('click', () => {
            const tabKey = btn.getAttribute(tabAttr);
            // Toggle active tab button
            document.querySelectorAll(`.section-tab[${tabAttr}]`).forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Toggle panels
            document.querySelectorAll(`.section-tab-panel[${panelAttr}]`).forEach(p => {
                p.style.display = p.getAttribute(panelAttr) === tabKey ? '' : 'none';
            });
            // Lazy-load inspector data on first click
            if (sectionName === 'models' && tabKey === 'inspector' && !state.modelInspector) {
                renderModelInspector();
            }
        });
    });
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

    const hintsCard = document.getElementById('overview-launch-hints');
    const hintsList = document.getElementById('overview-launch-hints-list');
    if (hintsCard && hintsList) {
        const hints = [];
        const db = state.handshake?.database || {};
        const migStatus = state.contextSummary?.migration_status || {};
        if (!db.connected) {
            hints.push('No database connection detected. Set DATABASE_URL or run aksara dbsetup.');
        }
        if ((migStatus.pending ?? 0) > 0) {
            hints.push('Migrations are pending. Run aksara migrate.');
        }
        if ((state.contextSummary?.model_count ?? 0) === 0) {
            hints.push('No models registered yet. Import your app models before creating the Aksara app.');
        }
        if (!state.contextSummary) {
            hints.push('Project summary is unavailable. Run aksara doctor launch-check for setup details.');
        }
        hintsCard.style.display = hints.length ? '' : 'none';
        hintsList.innerHTML = hints.map(h => '<li>' + escapeHtml(h) + '</li>').join('');
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
        const methodList = route.methods || ['GET'];
        // Each badge carries data-method so the AI flow context can target
        // a specific (path, method) pair on multi-method routes (a single
        // path can serve GET + POST + DELETE, etc.).
        const methods = methodList.map(m =>
            `<span class="method-badge ${m.toLowerCase()}" data-method="${escapeHtml(m)}" title="Use ${escapeHtml(m)} for AI actions" style="cursor:pointer">${m}</span>`
        ).join(' ');

        let typeBadges = '';
        if (route.is_studio) typeBadges += '<span class="type-badge studio">Studio</span>';
        if (route.is_admin) typeBadges += '<span class="type-badge admin">Admin</span>';
        if (route.is_ai) typeBadges += '<span class="type-badge ai">AI</span>';
        if (!route.is_studio && !route.is_admin && !route.is_ai) {
            typeBadges += '<span class="type-badge api">API</span>';
        }

        const primaryMethod = escapeHtml(methodList[0]);
        return `
            <tr data-studio="${route.is_studio}" data-admin="${route.is_admin}" data-ai="${route.is_ai}" data-path="${escapeHtml(route.path)}" data-method="${primaryMethod}" style="cursor:pointer">
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
    
    // v0.5.16: Wire up search / filter
    const searchInput = document.getElementById('mig-search');
    const statusFilter = document.getElementById('mig-status-filter');
    if (searchInput) searchInput.addEventListener('input', () => filterMigrationApps());
    if (statusFilter) statusFilter.addEventListener('change', () => filterMigrationApps());
}

async function fetchMigrations() {
    try {
        state.migrations = await jsonGet('/studio/migrations/summary');
    } catch (err) {
        console.error('Failed to fetch migrations:', err);
        showToast('Failed to load migrations. Check server logs.', 'error');
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
    
    // Apps list with badges (v0.5.16)
    const appsList = document.getElementById('mig-apps-list');
    if (appsList && mig.apps && mig.apps.length > 0) {
        appsList.innerHTML = mig.apps.map(app => {
            let badgeClass, badgeLabel;
            if (app.has_conflicts) {
                badgeClass = 'mig-badge conflict';
                badgeLabel = 'CONFLICT';
            } else if (app.pending > 0) {
                badgeClass = 'mig-badge pending';
                badgeLabel = 'PENDING';
            } else {
                badgeClass = 'mig-badge applied';
                badgeLabel = 'APPLIED';
            }
            return `
            <div class="app-item" data-status="${app.has_conflicts ? 'conflict' : app.pending > 0 ? 'pending' : 'applied'}">
                <div class="app-item-left">
                    <span class="app-name">${escapeHtml(app.app_label)}</span>
                    <span class="${badgeClass}">${badgeLabel}</span>
                </div>
                <div class="app-stats">
                    <span>Applied: ${app.applied}</span>
                    <span>Pending: ${app.pending}</span>
                </div>
            </div>
        `;
        }).join('');
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

// v0.5.16: Client-side filtering of migration apps
function filterMigrationApps() {
    const searchInput = document.getElementById('mig-search');
    const statusFilter = document.getElementById('mig-status-filter');
    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const status = statusFilter ? statusFilter.value : 'all';
    
    document.querySelectorAll('#mig-apps-list .app-item').forEach(item => {
        const name = item.querySelector('.app-name')?.textContent?.toLowerCase() || '';
        const itemStatus = item.dataset.status;
        const matchesSearch = !query || name.includes(query);
        const matchesStatus = status === 'all' || itemStatus === status;
        item.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
    });
}

// =============================================================================
// Diagnostics Section (v0.5.17: Diagnostics 2.0)
// =============================================================================

function renderDiagnostics() {
    fetchAndRenderDiagnostics();

    // Auto-refresh every 10 seconds (Live mode)
    state.diagnosticsLive = true;
    if (state.diagnosticsInterval) clearInterval(state.diagnosticsInterval);
    state.diagnosticsInterval = setInterval(() => {
        if (state.diagnosticsLive) fetchAndRenderDiagnostics();
    }, 10000);

    // Live toggle
    const liveBtn = document.getElementById('diag-live-btn');
    if (liveBtn) {
        liveBtn.classList.add('btn-live-active');
        liveBtn.textContent = 'Live';
        liveBtn.addEventListener('click', () => {
            state.diagnosticsLive = !state.diagnosticsLive;
            liveBtn.classList.toggle('btn-live-active', state.diagnosticsLive);
            liveBtn.textContent = state.diagnosticsLive ? 'Live' : 'Paused';
        });
    }

    // Refresh Now
    const refreshBtn = document.getElementById('diag-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchAndRenderDiagnostics);
    }

    // Severity filter buttons
    document.querySelectorAll('.diag-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.diag-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.diagnosticsFilter = btn.dataset.filter;
            renderDiagnosticsIssues();
        });
    });

    // Search input
    const searchInput = document.getElementById('diag-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            state.diagnosticsSearchQuery = e.target.value.toLowerCase();
            renderDiagnosticsIssues();
        });
    }
}

async function fetchAndRenderDiagnostics() {
    try {
        state.diagnosticsReport = await jsonGet('/studio/diagnostics');
        updateDiagnosticsSummary();
        renderDiagnosticsIssues();
    } catch (err) {
        console.error('Failed to fetch diagnostics:', err);
        const list = document.getElementById('diag-issues-list');
        if (list) list.innerHTML = '<div class="empty-state">Failed to load diagnostics</div>';
    }
}

function updateDiagnosticsSummary() {
    const r = state.diagnosticsReport;
    if (!r) return;

    const status = r.stats.errors > 0 ? 'error' : (r.stats.warnings > 0 ? 'warning' : 'ok');
    const statusLabels = { ok: 'All Clear', warning: 'Warnings Found', error: 'Issues Detected' };

    const icon = document.getElementById('diag-status-icon');
    const label = document.getElementById('diag-status-label');
    const banner = document.getElementById('diag-summary-banner');

    if (icon) icon.className = 'diag-status-icon diag-' + status;
    if (label) label.textContent = statusLabels[status] || status;
    if (banner) banner.className = 'diag-summary-banner diag-banner-' + status;

    setText('diag-count-errors', (r.stats.errors || 0) + ' error' + (r.stats.errors !== 1 ? 's' : ''));
    setText('diag-count-warnings', (r.stats.warnings || 0) + ' warning' + (r.stats.warnings !== 1 ? 's' : ''));
    setText('diag-count-info', (r.stats.info || 0) + ' info');

    setText('diag-duration', r.duration_ms ? r.duration_ms.toFixed(0) + ' ms' : '-');

    if (r.system) {
        const sys = r.system;
        setText('diag-system-info', `Aksara ${sys.aksara_version || '?'} · Python ${sys.python_version || '?'} · ${sys.os || '?'}`);
    }
}

function renderDiagnosticsIssues() {
    const list = document.getElementById('diag-issues-list');
    if (!list) return;

    const r = state.diagnosticsReport;
    if (!r || !r.issues) {
        list.innerHTML = '<div class="empty-state">No diagnostics data</div>';
        return;
    }

    let issues = r.issues;

    // Filter by severity
    if (state.diagnosticsFilter !== 'all') {
        issues = issues.filter(i => i.severity === state.diagnosticsFilter);
    }

    // Search filter
    if (state.diagnosticsSearchQuery) {
        const q = state.diagnosticsSearchQuery;
        issues = issues.filter(i =>
            (i.title && i.title.toLowerCase().includes(q)) ||
            (i.message && i.message.toLowerCase().includes(q)) ||
            (i.kind && i.kind.toLowerCase().includes(q)) ||
            (i.hint && i.hint.toLowerCase().includes(q))
        );
    }

    if (issues.length === 0) {
        const isFiltered = state.diagnosticsFilter !== 'all' || state.diagnosticsSearchQuery;
        list.innerHTML = isFiltered
            ? '<div class="empty-state">No matching issues</div>'
            : '<div class="empty-state diag-all-clear">No issues found &mdash; everything looks good!</div>';
        return;
    }

    list.innerHTML = issues.map(issue => {
        const sevClass = 'diag-sev-' + issue.severity;
        const kindLabel = (issue.kind || 'general').replace(/_/g, ' ');
        const hintHtml = issue.hint
            ? `<div class="diag-issue-hint"><strong>Hint:</strong> ${escapeHtml(issue.hint)}</div>`
            : '';
        const actionsHtml = renderDiagnosticActions(issue.actions || []);
        return `
            <div class="diag-issue-card ${sevClass}">
                <div class="diag-issue-header">
                    <span class="diag-sev-badge ${sevClass}">${escapeHtml(issue.severity)}</span>
                    <span class="diag-kind-badge">${escapeHtml(kindLabel)}</span>
                    <strong class="diag-issue-title">${escapeHtml(issue.title)}</strong>
                </div>
                <div class="diag-issue-message">${escapeHtml(issue.message)}</div>
                ${hintHtml}
                ${actionsHtml}
            </div>`;
    }).join('');

    // Bind copy-to-clipboard buttons for action examples
    list.querySelectorAll('.diag-action-copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.getAttribute('data-copy');
            if (text) {
                navigator.clipboard.writeText(text).then(() => {
                    const orig = btn.textContent;
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = orig; }, 1200);
                });
            }
        });
    });

    // Bind expand/collapse toggles for action sections
    list.querySelectorAll('.diag-actions-toggle').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const section = toggle.closest('.diag-actions-section');
            if (section) section.classList.toggle('diag-actions-expanded');
        });
    });
}

/**
 * v0.5.18: Render autoremediation action cards for a diagnostic issue.
 */
function renderDiagnosticActions(actions) {
    if (!actions || actions.length === 0) return '';

    const kindIcons = {
        set_env: '\u2699\uFE0F',
        run_command: '\u25B6\uFE0F',
        open_doc: '\uD83D\uDCD6',
        edit_file: '\uD83D\uDCDD',
        add_setting: '\u2699\uFE0F',
    };

    const kindLabels = {
        set_env: 'Set Environment Variable',
        run_command: 'Run Command',
        open_doc: 'Open Documentation',
        edit_file: 'Edit File',
        add_setting: 'Add Setting',
    };

    const actionCards = actions.map(a => {
        const icon = kindIcons[a.kind] || '\u2139\uFE0F';
        const kindLabel = kindLabels[a.kind] || a.kind;
        const exampleHtml = a.example
            ? `<div class="diag-action-example">
                 <code>${escapeHtml(a.example)}</code>
                 <button class="diag-action-copy-btn" data-copy="${escapeHtml(a.example)}" title="Copy to clipboard">Copy</button>
               </div>`
            : '';
        const descHtml = a.description
            ? `<div class="diag-action-desc">${escapeHtml(a.description)}</div>`
            : '';
        return `
            <div class="diag-action-card diag-action-kind-${a.kind}">
                <div class="diag-action-header">
                    <span class="diag-action-icon">${icon}</span>
                    <span class="diag-action-kind-label">${escapeHtml(kindLabel)}</span>
                </div>
                <div class="diag-action-title">${escapeHtml(a.title)}</div>
                ${descHtml}
                ${exampleHtml}
            </div>`;
    }).join('');

    return `
        <div class="diag-actions-section">
            <button class="diag-actions-toggle">\uD83D\uDD27 Fix This Issue (${actions.length} action${actions.length !== 1 ? 's' : ''})</button>
            <div class="diag-actions-list">${actionCards}</div>
        </div>`;
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
// v0.5.27: Gap Analysis Panel
// =============================================================================

async function renderGaps() {
    const listEl = document.getElementById('gaps-issues-list');
    const refreshBtn = document.getElementById('gaps-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadGapAnalysis());

    // Wire filter buttons
    document.querySelectorAll('.gaps-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.gaps-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filter = btn.dataset.filter;
            document.querySelectorAll('.diag-issue-card[data-severity]').forEach(card => {
                card.style.display = (filter === 'all' || card.dataset.severity === filter) ? '' : 'none';
            });
        });
    });

    await loadGapAnalysis();
}

async function loadGapAnalysis() {
    const listEl = document.getElementById('gaps-issues-list');
    if (listEl) listEl.innerHTML = '<div class="empty-state">Scanning\u2026</div>';

    try {
        const report = await jsonGet('/studio/gaps');

        // Update summary banner
        const stats = report.stats || {};
        const statusIcon = document.getElementById('gaps-status-icon');
        const statusLabel = document.getElementById('gaps-status-label');

        const total = stats.total || 0;
        const hasCritical = (stats.critical || 0) > 0;
        const hasError = (stats.error || 0) > 0;

        if (statusIcon && statusLabel) {
            if (hasCritical) {
                statusIcon.style.color = 'var(--color-error)';
                statusLabel.textContent = 'Critical issues found';
            } else if (hasError) {
                statusIcon.style.color = 'var(--color-error)';
                statusLabel.textContent = 'Errors found';
            } else if (total > 0) {
                statusIcon.style.color = 'var(--color-warning)';
                statusLabel.textContent = 'Warnings present';
            } else {
                statusIcon.style.color = 'var(--color-success)';
                statusLabel.textContent = 'All clear';
            }
        }

        setText('gaps-count-critical', `${stats.critical || 0} critical`);
        setText('gaps-count-errors', `${stats.error || 0} errors`);
        setText('gaps-count-warnings', `${stats.warning || 0} warnings`);
        setText('gaps-count-info', `${stats.info || 0} info`);
        setText('gaps-duration', report.duration_ms != null ? `${report.duration_ms.toFixed(0)} ms` : '-');
        setText('gaps-categories', (report.categories_checked || []).join(', '));

        if (!listEl) return;

        const issues = report.issues || [];
        if (issues.length === 0) {
            listEl.innerHTML = '<div class="empty-state">\u2705 No gaps found \u2014 your project looks good!</div>';
            return;
        }

        listEl.innerHTML = issues.map(issue => {
            const severityClass = issue.severity === 'critical' ? 'error' : issue.severity;
            const icon = issue.severity === 'critical' || issue.severity === 'error' ? '\u2717' :
                         issue.severity === 'warning' ? '!' : '\u00b7';
            const fixHtml = (issue.fix_commands || []).map(cmd =>
                `<div class="diag-action"><span class="action-label">\u2192 ${escapeHtml(cmd.description)}</span><code>${escapeHtml(cmd.command)}</code></div>`
            ).join('');
            return `<div class="diag-issue-card ${severityClass}" data-severity="${issue.severity}">
                <div class="diag-issue-header">
                    <span class="diag-severity-badge ${severityClass}">${icon} ${issue.severity.toUpperCase()}</span>
                    <span class="diag-issue-title">${escapeHtml(issue.title)}</span>
                    <span class="diag-issue-category">${escapeHtml(issue.category)}</span>
                </div>
                <div class="diag-issue-body">
                    <p>${escapeHtml(issue.message)}</p>
                    ${issue.hint ? `<p class="diag-hint">Hint: ${escapeHtml(issue.hint)}</p>` : ''}
                    ${fixHtml}
                </div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error('Gap analysis load failed:', err);
        if (listEl) listEl.innerHTML = `<div class="empty-state error">Failed to load gap analysis: ${escapeHtml(err.message)}</div>`;
        showToast('Failed to load gap analysis', 'error');
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
    
    // v0.5.16: Live / Paused toggle
    const liveBtn = document.getElementById('toggle-db-live');
    if (liveBtn) {
        liveBtn.addEventListener('click', () => toggleDbLive());
    }
    
    // Load data
    await loadDbQueries();
}

// v0.5.16: Toggle live auto-refresh for DB queries
function toggleDbLive() {
    state.dbQueriesLive = !state.dbQueriesLive;
    const liveBtn = document.getElementById('toggle-db-live');
    if (liveBtn) {
        liveBtn.textContent = state.dbQueriesLive ? '⏸ Paused' : '▶ Live';
        liveBtn.classList.toggle('btn-live-active', state.dbQueriesLive);
    }
    if (state.dbQueriesLive) {
        // Start polling every 5 seconds
        state.dbQueriesInterval = setInterval(() => loadDbQueries(), 5000);
    } else {
        if (state.dbQueriesInterval) {
            clearInterval(state.dbQueriesInterval);
            state.dbQueriesInterval = null;
        }
    }
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
    
    // v0.5.16: Last updated timestamp
    const lastUpdated = document.getElementById('db-last-updated');
    if (lastUpdated) {
        const now = new Date();
        lastUpdated.textContent = `Updated ${now.toLocaleTimeString()}`;
    }
    
    // Render slow queries
    const slowList = document.getElementById('slow-queries-list');
    if (slowList) {
        const slowQueries = data.top_slow_queries || [];
        if (slowQueries.length === 0) {
            slowList.innerHTML = '<div class="empty-state"><p>No slow queries recorded</p></div>';
        } else {
            slowList.innerHTML = slowQueries.slice(0, 10).map(q => `
                <div class="query-item slow query-slow-highlight">
                    <div class="query-header">
                        <span class="query-operation ${q.operation.toLowerCase()}">${escapeHtml(q.operation)}</span>
                        <span class="query-table">${escapeHtml(q.table || 'unknown')}</span>
                        <span class="query-duration">${q.duration_ms.toFixed(2)}ms</span>
                        <span class="badge badge-slow-query">🔥 Slow Query</span>
                    </div>
                    <pre class="query-sql">${escapeHtml(truncateSql(q.sql))}</pre>
                    ${q.stack_summary ? `<div class="query-stack">${escapeHtml(q.stack_summary)}</div>` : ''}
                    <button class="btn btn-sm btn-explain-plan" onclick="explainQueryPlan('${escapeHtml(q.sql.replace(/'/g, "\\'"))}')">Explain Plan</button>
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
// v0.5.21: Model Inspector Section
// =============================================================================

async function renderModelInspector() {
    const refreshBtn = document.getElementById('refresh-model-inspector');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadModelInspector());
    }
    await loadModelInspector();
}

async function loadModelInspector() {
    try {
        state.modelInspector = await jsonGet('/studio/models/inspect/all');
        renderModelInspectorData();
    } catch (err) {
        console.error('Failed to load model inspector:', err);
        showToast('Failed to load model inspector data', 'error');
    }
}

function renderModelInspectorData() {
    const data = state.modelInspector;
    if (!data) return;

    // Update summary stats
    setText('mi-total-models', data.total_count ?? 0);
    setText('mi-total-fields', data.total_fields ?? 0);
    setText('mi-total-rels', data.total_relationships ?? 0);

    // Render model list
    const listEl = document.getElementById('model-inspector-list');
    if (!listEl) return;

    const models = data.models || [];
    if (models.length === 0) {
        listEl.innerHTML = '<div class="empty-state"><p>No models registered</p></div>';
        return;
    }

    listEl.innerHTML = models.map(m => {
        const commentHtml = (m.comments || []).map(c => `<span class="mi-comment">${escapeHtml(c)}</span>`).join(' ');
        const fieldRows = (m.fields || []).map(f => {
            const badges = [];
            if (f.primary_key) badges.push('<span class="badge badge-pk">PK</span>');
            if (f.unique) badges.push('<span class="badge badge-unique">UQ</span>');
            if (f.nullable) badges.push('<span class="badge badge-null">NULL</span>');
            if (f.ai_sensitive) badges.push('<span class="badge badge-sensitive">⚠️</span>');
            return `<tr>
                <td><code>${escapeHtml(f.name)}</code></td>
                <td>${escapeHtml(f.field_type)}</td>
                <td>${escapeHtml(f.python_type)}</td>
                <td>${badges.join(' ')}</td>
                <td>${escapeHtml(f.default_repr || '-')}</td>
            </tr>`;
        }).join('');

        const relRows = (m.relationships || []).map(r => {
            return `<tr>
                <td><code>${escapeHtml(r.field_name)}</code></td>
                <td><span class="badge">${escapeHtml(r.kind.toUpperCase())}</span></td>
                <td>${escapeHtml(r.target_model)}</td>
                <td>${escapeHtml(r.on_delete)}</td>
            </tr>`;
        }).join('');

        return `
        <div class="card mi-model-card" data-model="${escapeHtml(m.name)}">
            <div class="card-header">
                <h3>${escapeHtml(m.name)} <small class="mi-table-name">${escapeHtml(m.table_name)}</small></h3>
                <span class="badge">${m.num_fields} fields</span>
            </div>
            <div class="card-body">
                ${commentHtml ? `<div class="mi-comments">${commentHtml}</div>` : ''}
                <table class="mi-field-table">
                    <thead><tr><th>Field</th><th>Type</th><th>Python</th><th>Flags</th><th>Default</th></tr></thead>
                    <tbody>${fieldRows}</tbody>
                </table>
                ${relRows ? `
                    <h4 class="mi-sub-heading">Relationships</h4>
                    <table class="mi-rel-table">
                        <thead><tr><th>Field</th><th>Kind</th><th>Target</th><th>On Delete</th></tr></thead>
                        <tbody>${relRows}</tbody>
                    </table>
                ` : ''}
                ${m.create_table_sql ? `
                    <details class="mi-sql-details">
                        <summary>CREATE TABLE SQL</summary>
                        <pre class="mi-sql">${escapeHtml(m.create_table_sql)}</pre>
                    </details>
                ` : ''}
            </div>
        </div>`;
    }).join('');
}

// v0.5.21: Explain Plan button handler
async function explainQueryPlan(sql) {
    try {
        const result = await jsonPost('/studio/db/plan', { sql: sql, analyze: false });
        const planText = (result.plan || []).join('\\n');
        const costInfo = result.estimated_cost != null ? `Estimated cost: ${result.estimated_cost}` : '';
        const warningText = (result.warnings || []).join('\\n');
        showToast(`EXPLAIN Plan retrieved — ${planText.split('\\n').length} line(s)`);
        console.log('EXPLAIN Plan:', planText, costInfo, warningText);
    } catch (err) {
        showToast('Failed to get query plan: ' + err.message, 'error');
    }
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
    
    // v0.5.13: Set up hints filter
    const hintsFilter = document.getElementById('ai-hints-filter');
    if (hintsFilter) {
        hintsFilter.addEventListener('input', () => renderAiHintsData());
    }
    
    // v0.5.16: Tab switching
    document.querySelectorAll('.ai-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.aiTab;
            // Toggle active tab
            document.querySelectorAll('.ai-tab').forEach(t => t.classList.toggle('active', t === tab));
            // Toggle visible pane
            document.querySelectorAll('.ai-tab-pane').forEach(pane => {
                pane.classList.toggle('active', pane.id === `ai-pane-${target}`);
            });
        });
    });
    
    // Load profiles, secrets, health, and hints
    await Promise.all([loadAiProfiles(), loadAiSecrets(), loadAiHealth(), loadAiHints()]);
    
    // v0.5.16: Default to Health tab if there are errors
    if (state.aiHealth && state.aiHealth.error_count > 0) {
        const healthTab = document.querySelector('.ai-tab[data-ai-tab="health"]');
        if (healthTab) healthTab.click();
    }
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

// v0.5.13: Load AI hints
async function loadAiHints() {
    try {
        state.aiHints = await jsonGet('/studio/ai/hints');
        renderAiHintsData();
    } catch (err) {
        console.error('Failed to load AI hints:', err);
        // Don't show error toast - hints are optional
    }
}

// v0.5.13: Render AI hints data
function renderAiHintsData() {
    const hints = state.aiHints;
    if (!hints) return;
    
    const hintsList = document.getElementById('ai-hints-list');
    const hintsCount = document.getElementById('ai-hints-count');
    const filterInput = document.getElementById('ai-hints-filter');
    
    if (!hintsList) return;
    
    // Update count badge
    if (hintsCount) {
        hintsCount.textContent = hints.total_count;
    }
    
    // Get filter value
    const filterValue = filterInput ? filterInput.value.toLowerCase() : '';
    
    // Filter hints
    let routes = hints.routes || [];
    if (filterValue) {
        routes = routes.filter(hint => 
            hint.title.toLowerCase().includes(filterValue) ||
            hint.path.toLowerCase().includes(filterValue) ||
            hint.view_name.toLowerCase().includes(filterValue) ||
            hint.route_name.toLowerCase().includes(filterValue)
        );
    }
    
    if (routes.length === 0) {
        hintsList.innerHTML = '<div class="empty-state"><p>No AI hints defined yet</p></div>';
        return;
    }
    
    hintsList.innerHTML = routes.map(hint => {
        const riskClass = `risk-${hint.risk_level}`;
        const usageLabel = hint.usage_kind.replace('_', ' ');
        const methodsStr = hint.methods.join(', ');
        
        const hasExample = hint.example_prompt || hint.example_input || hint.example_output;
        
        return `
            <div class="ai-hint-item" data-expanded="false">
                <div class="ai-hint-header" onclick="toggleHintExpanded(this)">
                    <div class="ai-hint-title-row">
                        <span class="ai-hint-title">${escapeHtml(hint.title)}</span>
                        <span class="ai-hint-risk-badge ${riskClass}">${hint.risk_level}</span>
                        <span class="ai-hint-usage-badge">${usageLabel}</span>
                    </div>
                    <div class="ai-hint-meta">
                        <span class="ai-hint-methods">${methodsStr}</span>
                        <span class="ai-hint-path">${escapeHtml(hint.path)}</span>
                    </div>
                </div>
                <div class="ai-hint-details hidden">
                    <div class="ai-hint-description">${escapeHtml(hint.description || 'No description')}</div>
                    <div class="ai-hint-view">${escapeHtml(hint.view_name)} → ${escapeHtml(hint.route_name)}</div>
                    ${hasExample ? `
                        <div class="ai-hint-examples">
                            ${hint.example_prompt ? `
                                <div class="ai-hint-example">
                                    <strong>Example Prompt:</strong>
                                    <span>${escapeHtml(hint.example_prompt)}</span>
                                </div>
                            ` : ''}
                            ${hint.example_input ? `
                                <div class="ai-hint-example">
                                    <strong>Example Input:</strong>
                                    <pre class="ai-hint-json">${JSON.stringify(hint.example_input, null, 2)}</pre>
                                </div>
                            ` : ''}
                            ${hint.example_output ? `
                                <div class="ai-hint-example">
                                    <strong>Example Output:</strong>
                                    <pre class="ai-hint-json">${JSON.stringify(hint.example_output, null, 2)}</pre>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                    ${hint.recommended_model || hint.recommended_provider ? `
                        <div class="ai-hint-recommendations">
                            ${hint.recommended_model ? `<span>Model: ${escapeHtml(hint.recommended_model)}</span>` : ''}
                            ${hint.recommended_provider ? `<span>Provider: ${escapeHtml(hint.recommended_provider)}</span>` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// v0.5.13: Toggle hint expanded state
function toggleHintExpanded(header) {
    const item = header.parentElement;
    const details = item.querySelector('.ai-hint-details');
    const isExpanded = item.getAttribute('data-expanded') === 'true';
    
    item.setAttribute('data-expanded', !isExpanded);
    details.classList.toggle('hidden', isExpanded);
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
// v0.5.19: Agent Mode
// =============================================================================

async function loadAgentContext() {
    try {
        const ctx = await jsonGet('/studio/agent/context');
        state.agent.context = ctx;
        // Restore selected sections from localStorage or default to all
        const saved = localStorage.getItem('aksara_agent_sections');
        if (saved) {
            try {
                state.agent.selectedSections = JSON.parse(saved);
            } catch (_) {
                state.agent.selectedSections = ctx.sections.map(s => s.key);
            }
        } else {
            state.agent.selectedSections = ctx.sections.map(s => s.key);
        }
        return ctx;
    } catch (err) {
        console.error('Failed to load agent context:', err);
        showToast('Failed to load agent context. Try: aksara agent context', 'error');
        return null;
    }
}

function renderAgentPanel() {
    loadAgentPlaybooks();
    loadAgentContext().then(ctx => {
        if (!ctx) return;
        renderAgentSections(ctx);
        renderAgentContextJson(ctx);
        initAgentEvents(ctx);
        initWorkflowEvents();
    });
}

function renderAgentSections(ctx) {
    const list = document.getElementById('agent-section-list');
    if (!list) return;

    list.innerHTML = ctx.sections.map(s => {
        const checked = state.agent.selectedSections.includes(s.key) ? 'checked' : '';
        return `<label class="agent-section-item">
            <input type="checkbox" value="${escapeHtml(s.key)}" ${checked} class="agent-section-cb">
            <span class="agent-section-title">${escapeHtml(s.title)}</span>
            <span class="agent-section-size">${s.size_kb.toFixed(1)} KB</span>
        </label>`;
    }).join('');

    // Update toggle-all button state
    updateAgentToggleAll();
}

function updateAgentToggleAll() {
    const btn = document.getElementById('agent-toggle-all');
    if (!btn || !state.agent.context) return;
    const allSelected = state.agent.selectedSections.length === state.agent.context.sections.length;
    btn.textContent = allSelected ? 'Deselect All' : 'Select All';
}

function renderAgentContextJson(ctx) {
    const el = document.getElementById('agent-json-output');
    if (el) {
        const filtered = {
            ...ctx,
            sections: ctx.sections.filter(s => state.agent.selectedSections.includes(s.key)),
        };
        el.textContent = JSON.stringify(filtered, null, 2);
    }
}

function initAgentEvents(ctx) {
    // Section checkbox changes
    const list = document.getElementById('agent-section-list');
    if (list) {
        list.addEventListener('change', (e) => {
            if (e.target.classList.contains('agent-section-cb')) {
                const key = e.target.value;
                if (e.target.checked) {
                    if (!state.agent.selectedSections.includes(key)) {
                        state.agent.selectedSections.push(key);
                    }
                } else {
                    state.agent.selectedSections = state.agent.selectedSections.filter(k => k !== key);
                }
                localStorage.setItem('aksara_agent_sections', JSON.stringify(state.agent.selectedSections));
                updateAgentToggleAll();
                renderAgentContextJson(ctx);
            }
        });
    }

    // Toggle all
    const toggleBtn = document.getElementById('agent-toggle-all');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const allSelected = state.agent.selectedSections.length === ctx.sections.length;
            state.agent.selectedSections = allSelected ? [] : ctx.sections.map(s => s.key);
            localStorage.setItem('aksara_agent_sections', JSON.stringify(state.agent.selectedSections));
            renderAgentSections(ctx);
            renderAgentContextJson(ctx);
        });
    }

    // Generate button
    const genBtn = document.getElementById('agent-generate-btn');
    if (genBtn) {
        genBtn.addEventListener('click', () => generateAgentPrompt());
    }

    // Tab switching
    document.querySelectorAll('.agent-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.agent-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.agent-tab-pane').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            const pane = document.getElementById(`agent-pane-${tab.dataset.agentTab}`);
            if (pane) pane.classList.add('active');
        });
    });
}

async function generateAgentPrompt() {
    const goalEl = document.getElementById('agent-goal');
    const outputEl = document.getElementById('agent-prompt-output');
    const metaEl = document.getElementById('agent-prompt-meta');
    if (!goalEl || !outputEl) return;

    const goal = goalEl.value.trim();

    // v0.5.20: If a playbook is selected, use playbook prompt endpoint
    if (state.agent.selectedPlaybook) {
        outputEl.textContent = 'Generating playbook prompt...';
        if (metaEl) metaEl.textContent = '';
        try {
            const body = {
                playbook_key: state.agent.selectedPlaybook.key,
                user_goal: goal || null,
                selected_sections: state.agent.selectedSections.length ? state.agent.selectedSections : null,
            };
            const resp = await jsonPost('/studio/agent/playbooks/prompt', body);
            state.agent.lastPromptResponse = resp;
            outputEl.textContent = resp.system_prompt;
            if (metaEl) {
                metaEl.innerHTML = `<span>Playbook: <strong>${escapeHtml(state.agent.selectedPlaybook.label)}</strong></span>`
                    + `<span>Model: <strong>${escapeHtml(resp.recommended_model)}</strong></span>`
                    + `<span>Temp: <strong>${resp.recommended_temperature}</strong></span>`
                    + `<span>~${resp.tokens_estimate} tokens</span>`;
            }
        } catch (err) {
            outputEl.textContent = `Error: ${err.message}`;
        }
        return;
    }

    if (!goal) {
        outputEl.textContent = 'Please enter a goal or select a playbook first.';
        return;
    }

    outputEl.textContent = 'Generating prompt...';
    if (metaEl) metaEl.textContent = '';

    try {
        const body = {
            goal: goal,
            selected_sections: state.agent.selectedSections,
        };
        const resp = await jsonPost('/studio/agent/prompt', body);
        state.agent.lastPromptResponse = resp;
        outputEl.textContent = resp.system_prompt;
        if (metaEl) {
            metaEl.innerHTML = `<span>Model: <strong>${escapeHtml(resp.recommended_model)}</strong></span>`
                + `<span>Temp: <strong>${resp.recommended_temperature}</strong></span>`
                + `<span>~${resp.tokens_estimate} tokens</span>`;
        }
    } catch (err) {
        outputEl.textContent = `Error: ${err.message}`;
    }
}

// =============================================================================
// v0.5.20: Agent Playbooks UI
// =============================================================================

async function loadAgentPlaybooks() {
    try {
        const data = await jsonGet('/studio/agent/playbooks');
        state.agent.playbooks = data;
        renderAgentPlaybooks();
        return data;
    } catch (err) {
        console.error('Failed to load agent playbooks:', err);
        showToast('Failed to load playbooks. Try: aksara agent playbooks', 'error');
        return null;
    }
}

function renderAgentPlaybooks() {
    const list = document.getElementById('agent-playbook-list');
    const countEl = document.getElementById('agent-playbook-count');
    if (!list || !state.agent.playbooks) return;

    const playbooks = filterPlaybooks();
    if (countEl) countEl.textContent = `${playbooks.length}`;

    if (playbooks.length === 0) {
        list.innerHTML = '<p class="text-muted">No matching playbooks.</p>';
        return;
    }

    list.innerHTML = playbooks.map(pb => {
        const selected = state.agent.selectedPlaybook && state.agent.selectedPlaybook.key === pb.key;
        const cls = selected ? 'agent-playbook-card agent-playbook-card--selected' : 'agent-playbook-card';
        const riskCls = `agent-playbook-badge agent-playbook-badge--${pb.risk_level}`;
        return `<div class="${cls}" data-playbook-key="${escapeHtml(pb.key)}">
            <div class="agent-playbook-card-header">
                <strong>${escapeHtml(pb.label)}</strong>
                <span class="${riskCls}">${escapeHtml(pb.risk_level)}</span>
            </div>
            <p class="agent-playbook-card-desc">${escapeHtml(pb.description)}</p>
            <div class="agent-playbook-card-meta">
                <span>${escapeHtml(pb.category)}</span>
                <span>${pb.steps.length} steps</span>
            </div>
        </div>`;
    }).join('');

    // Bind click events
    list.querySelectorAll('.agent-playbook-card').forEach(card => {
        card.addEventListener('click', () => {
            const key = card.dataset.playbookKey;
            selectPlaybook(key);
        });
    });

    // Bind filter pills
    initPlaybookFilters();

    // Bind search
    initPlaybookSearch();
}

function filterPlaybooks() {
    if (!state.agent.playbooks) return [];
    let pbs = state.agent.playbooks.playbooks;
    // Category filter
    if (state.agent.playbookFilter && state.agent.playbookFilter !== 'all') {
        pbs = pbs.filter(p => p.category === state.agent.playbookFilter);
    }
    // Search
    if (state.agent.playbookSearch) {
        const q = state.agent.playbookSearch.toLowerCase();
        pbs = pbs.filter(p =>
            p.label.toLowerCase().includes(q) ||
            p.description.toLowerCase().includes(q) ||
            (p.tags || []).some(t => t.toLowerCase().includes(q))
        );
    }
    return pbs;
}

function selectPlaybook(key) {
    if (!state.agent.playbooks) return;
    const pb = state.agent.playbooks.playbooks.find(p => p.key === key);
    if (!pb) return;

    // Toggle: click same playbook deselects
    if (state.agent.selectedPlaybook && state.agent.selectedPlaybook.key === key) {
        state.agent.selectedPlaybook = null;
        renderAgentPlaybooks();
        return;
    }

    state.agent.selectedPlaybook = pb;

    // Auto-prefill goal with default template
    const goalEl = document.getElementById('agent-goal');
    if (goalEl && (!goalEl.value.trim())) {
        goalEl.value = pb.default_goal_template;
    }

    // Auto-select recommended sections
    if (pb.default_sections && pb.default_sections.length && state.agent.context) {
        state.agent.selectedSections = [...pb.default_sections];
        localStorage.setItem('aksara_agent_sections', JSON.stringify(state.agent.selectedSections));
        renderAgentSections(state.agent.context);
        renderAgentContextJson(state.agent.context);
    }

    // Render playbook steps in output area
    renderPlaybookSteps(pb);

    // Re-render to show selection highlight
    renderAgentPlaybooks();
}

function renderPlaybookSteps(pb) {
    const outputEl = document.getElementById('agent-prompt-output');
    if (!outputEl) return;
    const lines = [];
    lines.push(`Playbook: ${pb.label}`);
    lines.push(`Kind: ${pb.kind}  |  Risk: ${pb.risk_level}  |  Usage: ${pb.usage_kind}`);
    lines.push('');
    lines.push('Steps:');
    pb.steps.forEach((step, i) => {
        lines.push(`  ${i + 1}. ${step.title}`);
        lines.push(`     ${step.description}`);
        if (step.estimated_impact) lines.push(`     Impact: ${step.estimated_impact}`);
    });
    if (pb.notes) {
        lines.push('');
        lines.push(`Note: ${pb.notes}`);
    }
    lines.push('');
    lines.push('Press "Generate Prompt" to build the full system prompt.');
    outputEl.textContent = lines.join('\n');
}

function initPlaybookFilters() {
    const container = document.getElementById('agent-playbook-filters');
    if (!container) return;
    container.querySelectorAll('.agent-filter-pill').forEach(pill => {
        pill.classList.toggle('active', pill.dataset.filter === state.agent.playbookFilter);
        // Remove old listeners by cloning
        const newPill = pill.cloneNode(true);
        pill.parentNode.replaceChild(newPill, pill);
        newPill.addEventListener('click', () => {
            state.agent.playbookFilter = newPill.dataset.filter;
            renderAgentPlaybooks();
        });
    });
}

function initPlaybookSearch() {
    const input = document.getElementById('agent-playbook-search');
    if (!input) return;
    // Avoid duplicating listeners
    if (input._playbookSearchBound) return;
    input._playbookSearchBound = true;
    input.addEventListener('input', () => {
        state.agent.playbookSearch = input.value;
        renderAgentPlaybooks();
    });
}


// =============================================================================
// v0.5.23: Agentic Workflows — Plans, Not Pushes
// =============================================================================


function initWorkflowEvents() {
    const wfBtn = document.getElementById('agent-workflow-btn');
    if (wfBtn) {
        if (wfBtn._wfBound) return;
        wfBtn._wfBound = true;
        wfBtn.addEventListener('click', () => generateAgentWorkflow());
    }

    // Restore last goal from localStorage
    const savedGoal = localStorage.getItem('aksara_agent_goal');
    if (savedGoal) {
        const goalEl = document.getElementById('agent-goal');
        if (goalEl && !goalEl.value) goalEl.value = savedGoal;
    }

    // Save goal on change
    const goalEl = document.getElementById('agent-goal');
    if (goalEl && !goalEl._goalSaveBound) {
        goalEl._goalSaveBound = true;
        goalEl.addEventListener('input', () => {
            localStorage.setItem('aksara_agent_goal', goalEl.value);
        });
    }
}

async function generateAgentWorkflow() {
    const goalEl = document.getElementById('agent-goal');
    const outputEl = document.getElementById('agent-workflow-output');
    if (!goalEl || !outputEl) return;

    const goal = goalEl.value.trim();
    if (!goal) {
        outputEl.innerHTML = '<p class="text-muted">Please enter a goal first.</p>';
        return;
    }

    outputEl.innerHTML = '<p class="text-muted">Generating workflow...</p>';

    // Switch to Workflow tab
    document.querySelectorAll('.agent-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.agent-tab-pane').forEach(p => p.classList.remove('active'));
    const wfTab = document.querySelector('[data-agent-tab="workflow"]');
    if (wfTab) wfTab.classList.add('active');
    const wfPane = document.getElementById('agent-pane-workflow');
    if (wfPane) wfPane.classList.add('active');

    const diagCb = document.getElementById('agent-wf-diagnostics');
    const searchCb = document.getElementById('agent-wf-search');
    const searchQueryEl = document.getElementById('agent-wf-search-query');

    const body = {
        goal: goal,
        playbook: state.agent.selectedPlaybook ? state.agent.selectedPlaybook.key : null,
        include_diagnostics: diagCb ? diagCb.checked : true,
        include_search: searchCb ? searchCb.checked : true,
        search_query: searchQueryEl && searchQueryEl.value.trim() ? searchQueryEl.value.trim() : null,
        limit_search_results: 10,
        limit_diagnostics: 10,
    };

    try {
        const resp = await jsonPost('/studio/agent/workflow', body);
        renderAgentWorkflow(resp);
    } catch (err) {
        outputEl.innerHTML = `<p style="color: var(--accent-error);">Error: ${escapeHtml(err.message)}</p>`;
    }
}

function renderAgentWorkflow(response) {
    const outputEl = document.getElementById('agent-workflow-output');
    if (!outputEl) return;

    const wf = response.workflow;
    const steps = wf.steps || [];

    let html = '';

    // Summary header
    html += '<div class="wf-summary">';
    html += `<div class="wf-goal">🎯 ${escapeHtml(wf.goal)}</div>`;
    if (wf.playbook) {
        html += `<div class="wf-meta">📋 Playbook: ${escapeHtml(wf.playbook)}</div>`;
    }
    html += `<div class="wf-meta">📊 ${steps.length} steps · Source: ${escapeHtml(wf.source)}</div>`;
    if (response.summary) {
        html += `<div class="wf-meta-summary">${escapeHtml(response.summary)}</div>`;
    }
    html += '</div>';

    // Stats chips
    const stats = response.stats || {};
    if (stats.by_kind) {
        html += '<div class="wf-stats">';
        for (const [kind, count] of Object.entries(stats.by_kind)) {
            html += `<span class="wf-chip wf-chip-kind" data-kind="${escapeHtml(kind)}">${escapeHtml(kind)}: ${count}</span>`;
        }
        if (stats.has_high_risk) {
            html += '<span class="wf-chip wf-chip-risk">⚠ high-risk steps</span>';
        }
        html += '</div>';
    }

    // Steps timeline
    html += '<div class="wf-timeline">';
    for (const step of steps) {
        const riskClass = step.risk === 'high' ? 'wf-risk-high' : step.risk === 'medium' ? 'wf-risk-medium' : 'wf-risk-low';
        html += `<div class="wf-step ${riskClass}">`;
        html += `<div class="wf-step-header">`;
        html += `<span class="wf-step-order">${step.order}</span>`;
        html += `<span class="wf-step-kind">${escapeHtml(step.kind)}</span>`;
        html += `<span class="wf-step-title">${escapeHtml(step.title)}</span>`;
        if (step.risk) {
            html += `<span class="wf-step-badge wf-badge-${step.risk}">${step.risk}</span>`;
        }
        if (step.estimated_effort) {
            html += `<span class="wf-step-badge wf-badge-effort">${step.estimated_effort}</span>`;
        }
        html += '</div>';

        if (step.description) {
            html += `<div class="wf-step-desc">${escapeHtml(step.description)}</div>`;
        }

        if (step.commands && step.commands.length) {
            html += '<div class="wf-step-commands">';
            for (const cmd of step.commands) {
                html += `<div class="wf-cmd"><code>$ ${escapeHtml(cmd)}</code><button class="wf-copy-btn" onclick="navigator.clipboard.writeText('${escapeHtml(cmd).replace(/'/g, "\\'")}')">📋</button></div>`;
            }
            html += '</div>';
        }

        if (step.notes && step.notes.length) {
            html += '<div class="wf-step-notes">';
            for (const note of step.notes) {
                html += `<div class="wf-note">• ${escapeHtml(note)}</div>`;
            }
            html += '</div>';
        }

        html += '</div>';
    }
    html += '</div>';

    outputEl.innerHTML = html;
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
        
        // v0.5.28: Load AI Hub status indicator
        loadAiStatusIndicator();
        
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

// =============================================================================
// v0.5.22: Spotlight Search
// =============================================================================

function toggleSpotlight() {
    if (state.spotlight.visible) {
        closeSpotlight();
    } else {
        openSpotlight();
    }
}

function openSpotlight() {
    state.spotlight.visible = true;
    state.spotlight.query = '';
    state.spotlight.results = [];
    state.spotlight.selectedIndex = 0;

    const overlay = document.getElementById('spotlight-overlay');
    const input = document.getElementById('spotlight-input');
    if (overlay) {
        overlay.style.display = 'flex';
        if (input) {
            input.value = '';
            input.focus();
        }
    }

    // Set up event listeners
    const backdrop = document.getElementById('spotlight-backdrop');
    if (backdrop) backdrop.onclick = closeSpotlight;

    if (input) {
        input.oninput = (e) => {
            state.spotlight.query = e.target.value;
            clearTimeout(state.spotlight.debounceTimer);
            state.spotlight.debounceTimer = setTimeout(() => spotlightSearch(), 200);
        };
        input.onkeydown = handleSpotlightKeydown;
    }

    // Set up filter buttons
    document.querySelectorAll('.spotlight-filter').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.spotlight-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.spotlight.kindFilter = btn.dataset.kind;
            spotlightSearch();
        };
    });

    renderSpotlightResults();
}

function closeSpotlight() {
    state.spotlight.visible = false;
    const overlay = document.getElementById('spotlight-overlay');
    if (overlay) overlay.style.display = 'none';
    const preview = document.getElementById('spotlight-preview');
    if (preview) preview.style.display = 'none';
}

function handleSpotlightKeydown(e) {
    const results = state.spotlight.results;

    if (e.key === 'Escape') {
        e.preventDefault();
        closeSpotlight();
        return;
    }
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        state.spotlight.selectedIndex = Math.min(state.spotlight.selectedIndex + 1, results.length - 1);
        renderSpotlightResults();
        return;
    }
    if (e.key === 'ArrowUp') {
        e.preventDefault();
        state.spotlight.selectedIndex = Math.max(state.spotlight.selectedIndex - 1, 0);
        renderSpotlightResults();
        return;
    }
    if (e.key === 'Enter') {
        e.preventDefault();
        const selected = results[state.spotlight.selectedIndex];
        if (selected) {
            spotlightNavigate(selected);
        }
        return;
    }
    if (e.key === 'Tab') {
        e.preventDefault();
        const selected = results[state.spotlight.selectedIndex];
        if (selected) {
            spotlightShowPreview(selected);
        }
        return;
    }
}

async function spotlightSearch() {
    const query = state.spotlight.query.trim();
    if (!query) {
        state.spotlight.results = [];
        state.spotlight.selectedIndex = 0;
        renderSpotlightResults();
        return;
    }

    try {
        const body = {
            query: query,
            top_k: 20,
            mode: 'hybrid',
        };
        if (state.spotlight.kindFilter !== 'all') {
            body.kind = state.spotlight.kindFilter;
        }

        const resp = await fetch('/studio/search/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (resp.ok) {
            const data = await resp.json();
            state.spotlight.results = data.results || [];
            state.spotlight.selectedIndex = 0;
        } else {
            state.spotlight.results = [];
        }
    } catch (err) {
        console.error('Spotlight search failed:', err);
        showToast('Search failed.', 'error');
        state.spotlight.results = [];
    }

    renderSpotlightResults();
}

function renderSpotlightResults() {
    const container = document.getElementById('spotlight-results');
    if (!container) return;

    const results = state.spotlight.results;

    if (!state.spotlight.query.trim()) {
        container.innerHTML = '<div class="spotlight-empty">Type to search across your project</div>';
        return;
    }

    if (results.length === 0) {
        container.innerHTML = '<div class="spotlight-empty">No results found</div>';
        return;
    }

    container.innerHTML = results.map((r, i) => `
        <div class="spotlight-result-item ${i === state.spotlight.selectedIndex ? 'selected' : ''}"
             data-index="${i}">
            <span class="spotlight-result-kind" data-kind="${r.kind}">${r.kind}</span>
            <div class="spotlight-result-info">
                <div class="spotlight-result-title">${escapeHtml(r.title)}</div>
                <div class="spotlight-result-summary">${escapeHtml(r.summary)}</div>
            </div>
            <span class="spotlight-result-score">${(r.score * 100).toFixed(0)}%</span>
        </div>
    `).join('');

    // Click handlers
    container.querySelectorAll('.spotlight-result-item').forEach(item => {
        item.onclick = () => {
            const idx = parseInt(item.dataset.index);
            state.spotlight.selectedIndex = idx;
            spotlightNavigate(results[idx]);
        };
        item.onmouseenter = () => {
            state.spotlight.selectedIndex = parseInt(item.dataset.index);
            renderSpotlightResults();
        };
    });
}

function spotlightNavigate(result) {
    closeSpotlight();
    // Navigate to the appropriate section based on result kind
    const kindToSection = {
        model: 'model-inspector',
        route: 'routes',
        migration: 'migrations',
        query: 'db-queries',
        setting: 'overview',
        playbook: 'agent',
    };
    const section = kindToSection[result.kind] || 'overview';
    navigateTo(section);
}

function spotlightShowPreview(result) {
    const preview = document.getElementById('spotlight-preview');
    const header = document.getElementById('spotlight-preview-header');
    const body = document.getElementById('spotlight-preview-body');
    if (!preview || !header || !body) return;

    header.textContent = `${result.kind.toUpperCase()}: ${result.title}`;

    const parts = [result.summary];
    if (result.highlights && result.highlights.length > 0) {
        parts.push('');
        parts.push('Matches:');
        result.highlights.forEach(h => parts.push(`  ${h}`));
    }
    if (result.metadata) {
        parts.push('');
        parts.push('Metadata:');
        Object.entries(result.metadata).forEach(([k, v]) => {
            const val = typeof v === 'object' ? JSON.stringify(v) : String(v);
            if (val.length < 80) parts.push(`  ${k}: ${val}`);
        });
    }

    body.textContent = parts.join('\n');
    preview.style.display = 'block';
}



// =============================================================================
// v0.5.38: AI Home Section
// =============================================================================

async function renderAiHome() {
    // Fetch home data
    try {
        const resp = await fetch('/studio/ai/home');
        if (!resp.ok) throw new Error('Failed to load AI Home');
        const data = await resp.json();

        // Status pill
        const pill = document.getElementById('ai-home-status');
        if (pill) {
            const statusMap = { ready: 'Ready', partial: 'Partial', not_configured: 'Not Configured' };
            pill.textContent = statusMap[data.status] || 'Not Configured';
            pill.className = 'ai-home-status-pill ai-home-status-' + (data.status || 'not_configured');
        }

        // Provider metadata
        const meta = document.getElementById('ai-home-provider-meta');
        if (meta && data.provider) {
            const parts = [];
            if (data.provider) parts.push('Provider: ' + _esc(data.provider));
            if (data.model) parts.push('Model: ' + _esc(data.model));
            if (data.embeddings_model) parts.push('Embeddings: ' + _esc(data.embeddings_model));
            meta.innerHTML = parts.map(p => '<span class="ai-home-meta-item">' + p + '</span>').join('');
        } else if (meta) {
            meta.innerHTML = '<span class="ai-home-meta-item">AI provider optional for first launch</span>';
        }

        // System snapshot
        const snap = data.snapshot || {};
        const ids = ['models', 'routes', 'queries', 'migrations', 'diagnostics'];
        ids.forEach(k => {
            const el = document.getElementById('ai-home-snap-' + k);
            if (el) el.textContent = snap[k] != null ? snap[k] : '-';
        });

        // Scores
        const scoresEl = document.getElementById('ai-home-scores');
        if (scoresEl) {
            let html = '';
            if (data.scores && data.scores.architecture) {
                html += '<a href="#/ai-inspector" class="ai-home-score-link">' +
                    'Architecture: <strong>' + _esc(data.scores.architecture.grade) + '</strong> (' + data.scores.architecture.score + ')' +
                    '</a>';
            }
            if (data.scores && data.scores.performance) {
                html += '<a href="#/ai-inspector" class="ai-home-score-link">' +
                    'Performance: <strong>' + _esc(data.scores.performance.grade) + '</strong> (' + data.scores.performance.score + ')' +
                    '</a>';
            }
            scoresEl.innerHTML = html;
        }

        // Recent observations
        const obsEl = document.getElementById('ai-home-observations');
        if (obsEl) {
            const obs = data.observations || [];
            if (obs.length) {
                obsEl.innerHTML = obs.map(o =>
                    '<div class="ai-home-observation-item">' + _esc(o) + '</div>'
                ).join('');
            } else {
                obsEl.innerHTML = '<p class="text-muted">No recent observations</p>';
            }
        }

        // Prompt suggestions
        const sugEl = document.getElementById('ai-home-suggestions');
        if (sugEl) {
            const prompts = data.suggested_prompts || [];
            let sugHtml = '<span class="ai-home-suggestion-label">Suggestions:</span>';
            prompts.forEach(p => {
                sugHtml += '<button class="ai-home-suggestion-chip">' + _esc(p) + '</button>';
            });
            sugEl.innerHTML = sugHtml;
            // Wire chip clicks
            sugEl.querySelectorAll('.ai-home-suggestion-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    _aiHomePrefillPrompt = chip.textContent;
                    navigateTo('ai-console');
                });
            });
        }

        // Show/hide empty state
        const setupCard = document.getElementById('ai-home-setup');
        const heroCard = document.querySelector('.ai-home-hero');
        if (data.status === 'not_configured') {
            if (setupCard) setupCard.style.display = '';
            if (heroCard) heroCard.style.display = 'none';
        } else {
            if (setupCard) setupCard.style.display = 'none';
        }
    } catch (e) {
        // Silently handle — show defaults
    }

    // Wire hero prompt input
    const input = document.getElementById('ai-home-prompt');
    const goBtn = document.getElementById('ai-home-go');
    if (input && goBtn) {
        const submit = () => {
            const val = input.value.trim();
            if (val) {
                _aiHomePrefillPrompt = val;
                navigateTo('ai-console');
            }
        };
        goBtn.addEventListener('click', submit);
        input.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
    }

    // Wire quick action cards
    document.querySelectorAll('.ai-home-action-card').forEach(card => {
        card.addEventListener('click', () => {
            const action = card.dataset.action;
            if (action === 'investigate') {
                _aiHomePrefillPrompt = 'Investigate my project';
                navigateTo('ai-console');
            } else if (action === 'console') {
                navigateTo('ai-console');
            } else if (action === 'inspector') {
                navigateTo('ai-inspector');
            } else if (action === 'graph') {
                navigateTo('ai-graph');
            }
        });
    });

    // Wire setup button
    const hubBtn = document.getElementById('ai-home-open-hub');
    if (hubBtn) hubBtn.addEventListener('click', () => navigateTo('ai-hub'));

    // v0.5.40: Load daily briefing
    _loadDailyBriefing();

    // Wire briefing refresh button
    const refreshBtn = document.getElementById('ai-home-refresh-briefing');
    if (refreshBtn) refreshBtn.addEventListener('click', () => _loadDailyBriefing());
}

// v0.5.38: Prefill prompt for console navigation from AI Home
let _aiHomePrefillPrompt = null;


// v0.5.40: Daily Briefing loader
async function _loadDailyBriefing() {
    const contentEl = document.getElementById('ai-home-briefing-content');
    if (!contentEl) return;
    contentEl.innerHTML = '<p class="text-muted">Loading daily briefing&hellip;</p>';

    try {
        const resp = await fetch('/studio/ai/daily-briefing');
        if (!resp.ok) throw new Error('Failed to load briefing');
        const data = await resp.json();

        contentEl.innerHTML = '<p>' + _esc(data.summary || 'No summary available.') + '</p>';

        // Scores
        const scoresEl = document.getElementById('ai-home-briefing-scores');
        if (scoresEl) {
            scoresEl.style.display = '';
            const perfEl = document.getElementById('ai-home-briefing-perf');
            const archEl = document.getElementById('ai-home-briefing-arch');
            if (perfEl) perfEl.textContent = data.performance_score >= 0 ? Math.round(data.performance_score) : '-';
            if (archEl) archEl.textContent = data.architecture_score >= 0 ? Math.round(data.architecture_score) : '-';
        }

        // Issues
        const issuesEl = document.getElementById('ai-home-briefing-issues');
        const issueList = document.getElementById('ai-home-briefing-issue-list');
        if (issuesEl && issueList && data.issues && data.issues.length) {
            issuesEl.style.display = '';
            issueList.innerHTML = data.issues.slice(0, 5).map(i =>
                '<li>' + _esc(i) + '</li>'
            ).join('');
        }

        // Recommendations
        const recsEl = document.getElementById('ai-home-briefing-recs');
        const recList = document.getElementById('ai-home-briefing-rec-list');
        if (recsEl && recList && data.recommendations && data.recommendations.length) {
            recsEl.style.display = '';
            recList.innerHTML = data.recommendations.map(r =>
                '<li>' + _esc(r) + '</li>'
            ).join('');
        }
    } catch (e) {
        contentEl.innerHTML = '<p class="text-muted">Briefing unavailable. Configure an AI provider in AI Hub, or continue using non-AI Studio tools.</p>';
    }
}


// =============================================================================
// v0.5.38: AI Inspector Section
// =============================================================================

async function renderAiInspector() {
    const panel = document.getElementById('ai-inspector-panel');
    const _inspectorLoaded = { overview: false, debug: false, architecture: false, performance: false };

    // Wire tab switching
    document.querySelectorAll('.ai-inspector-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.ai-inspector-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.getAttribute('data-inspector-tab');
            _renderInspectorTab(panel, target, _inspectorLoaded);
        });
    });

    // Load default tab
    _renderInspectorTab(panel, 'overview', _inspectorLoaded);
}

async function _renderInspectorTab(panel, tab, loaded) {
    if (!panel) return;

    if (tab === 'overview') {
        panel.innerHTML = '<div class="ai-inspector-loading">Loading overview&hellip;</div>';
        try {
            const resp = await fetch('/studio/ai/inspector');
            if (!resp.ok) throw new Error('Failed');
            const data = await resp.json();
            let html = '<div class="ai-inspector-overview">';
            html += '<div class="cards-grid">';
            html += '<div class="card"><div class="card-header"><h3>Architecture Score</h3></div><div class="card-body"><div class="metric"><span class="metric-value">' +
                (data.architecture.grade || '—') + '</span></div><div class="text-muted">' + (data.architecture.score != null ? 'Score: ' + data.architecture.score : '') + '</div></div></div>';
            html += '<div class="card"><div class="card-header"><h3>Performance Score</h3></div><div class="card-body"><div class="metric"><span class="metric-value">' +
                (data.performance.grade || '—') + '</span></div><div class="text-muted">' + (data.performance.score != null ? 'Score: ' + data.performance.score : '') + '</div></div></div>';
            html += '<div class="card"><div class="card-header"><h3>Diagnostics</h3></div><div class="card-body"><div class="metric"><span class="metric-value">' +
                data.diagnostics_count + '</span><span class="text-muted"> issues</span></div></div></div>';
            html += '</div>';

            if (data.top_issues && data.top_issues.length) {
                html += '<div class="card" style="margin-top:var(--spacing-md);"><div class="card-header"><h3>Top Issues</h3></div><div class="card-body">';
                data.top_issues.forEach(i => {
                    const cls = i.severity === 'error' ? 'severity-error' : i.severity === 'warning' ? 'severity-warning' : 'severity-info';
                    html += '<div class="ai-inspector-issue"><span class="' + cls + '">' + _esc(i.severity) + '</span> <strong>' + _esc(i.code) + '</strong> — ' + _esc(i.message) + '</div>';
                });
                html += '</div></div>';
            }

            html += '</div>';
            panel.innerHTML = html;
        } catch (e) {
            panel.innerHTML = '<div class="ai-inspector-empty">Error loading overview: ' + _esc(e.message) + '</div>';
        }
    } else if (tab === 'debug') {
        panel.innerHTML = '<div class="ai-inspector-loading">Running debugger&hellip;</div>';
        try {
            const resp = await fetch('/studio/ai/debug', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            if (!resp.ok) throw new Error('Debugger failed');
            const data = await resp.json();
            let html = '<div class="ai-inspector-debug">';
            if (data.score != null) {
                html += '<div class="ai-inspector-score-row"><span>Score: <strong>' + data.score + '</strong></span>';
                if (data.grade) html += ' <span class="ai-inspector-grade">(' + _esc(data.grade) + ')</span>';
                html += '</div>';
            }
            if (data.root_causes && data.root_causes.length) {
                html += '<h4>Root Causes</h4>';
                data.root_causes.forEach(rc => {
                    html += '<div class="ai-inspector-finding"><strong>' + _esc(rc.title || rc.description || '') + '</strong>';
                    if (rc.confidence) html += ' <span class="text-muted">(' + Math.round(rc.confidence * 100) + '%)</span>';
                    html += '</div>';
                });
            }
            if (data.issues && data.issues.length) {
                html += '<h4>Issues (' + data.issues.length + ')</h4>';
                data.issues.slice(0, 10).forEach(i => {
                    html += '<div class="ai-inspector-finding">' + _esc(i.title || i.message || '') +
                        ' <span class="text-muted">' + _esc(i.severity || '') + '</span></div>';
                });
                if (data.issues.length > 10) html += '<p class="text-muted">...and ' + (data.issues.length - 10) + ' more</p>';
            }
            if (!data.root_causes?.length && !data.issues?.length) {
                html += '<p class="text-muted">No issues detected</p>';
            }
            html += '</div>';
            panel.innerHTML = html;
        } catch (e) {
            panel.innerHTML = '<div class="ai-inspector-empty">Error: ' + _esc(e.message) + '</div>';
        }
    } else if (tab === 'architecture') {
        panel.innerHTML = '<div class="ai-inspector-loading">Running architecture review&hellip;</div>';
        try {
            const resp = await fetch('/studio/ai/architecture-review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            if (!resp.ok) throw new Error('Architecture review failed');
            const data = await resp.json();
            let html = '<div class="ai-inspector-arch">';
            if (data.score != null) {
                html += '<div class="ai-inspector-score-row"><span>Score: <strong>' + data.score + '</strong></span>';
                if (data.grade) html += ' <span class="ai-inspector-grade">(' + _esc(data.grade) + ')</span>';
                html += '</div>';
            }
            if (data.findings && data.findings.length) {
                html += '<h4>Findings (' + data.findings.length + ')</h4>';
                data.findings.slice(0, 10).forEach(f => {
                    html += '<div class="ai-inspector-finding"><span class="severity-' + _esc(f.severity || 'info') + '">' + _esc(f.severity || '') + '</span> ' + _esc(f.title || f.message || '') + '</div>';
                });
                if (data.findings.length > 10) html += '<p class="text-muted">...and ' + (data.findings.length - 10) + ' more</p>';
            }
            if (data.suggestions && data.suggestions.length) {
                html += '<h4>Suggestions</h4>';
                data.suggestions.slice(0, 5).forEach(s => {
                    html += '<div class="ai-inspector-finding">' + _esc(s.title || s.description || '') +
                        ' <span class="text-muted">' + _esc(s.impact || '') + ' impact</span></div>';
                });
            }
            html += '</div>';
            panel.innerHTML = html;
        } catch (e) {
            panel.innerHTML = '<div class="ai-inspector-empty">Error: ' + _esc(e.message) + '</div>';
        }
    } else if (tab === 'performance') {
        panel.innerHTML = '<div class="ai-inspector-loading">Running performance analysis&hellip;</div>';
        try {
            const resp = await fetch('/studio/ai/performance-analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            if (!resp.ok) throw new Error('Performance analysis failed');
            const data = await resp.json();
            let html = '<div class="ai-inspector-perf">';
            if (data.score != null) {
                html += '<div class="ai-inspector-score-row"><span>Score: <strong>' + data.score + '</strong></span>';
                if (data.grade) html += ' <span class="ai-inspector-grade">(' + _esc(data.grade) + ')</span>';
                html += '</div>';
            }
            if (data.issues && data.issues.length) {
                html += '<h4>Issues (' + data.issues.length + ')</h4>';
                data.issues.slice(0, 10).forEach(i => {
                    const sevClass = _esc(i.severity || 'medium');
                    html += '<div class="ai-inspector-finding"><span class="ai-perf-sev-badge">' + _esc(i.severity) + '</span> ' +
                        _esc(i.title) + ' <span class="text-muted">' + _esc(i.category || '') + '</span></div>';
                });
                if (data.issues.length > 10) html += '<p class="text-muted">...and ' + (data.issues.length - 10) + ' more</p>';
            }
            if (data.recommendations && data.recommendations.length) {
                html += '<h4>Recommendations</h4>';
                data.recommendations.slice(0, 5).forEach(r => {
                    html += '<div class="ai-inspector-finding">' + _esc(r.title) +
                        ' <span class="text-muted">' + _esc(r.impact || '') + ' impact</span></div>';
                });
            }
            html += '</div>';
            panel.innerHTML = html;
        } catch (e) {
            panel.innerHTML = '<div class="ai-inspector-empty">Error: ' + _esc(e.message) + '</div>';
        }
    } else if (tab === 'investigations') {
        // v0.5.40: Investigation Timeline tab
        const invPanel = document.getElementById('ai-inspector-investigations');
        panel.style.display = 'none';
        if (invPanel) {
            invPanel.style.display = '';
            const listEl = document.getElementById('ai-inspector-investigation-list');
            if (listEl) {
                listEl.innerHTML = '<p class="text-muted">Loading investigations&hellip;</p>';
                try {
                    const resp = await fetch('/studio/ai/investigate');
                    if (!resp.ok) throw new Error('Failed to load investigations');
                    const data = await resp.json();
                    const sessions = data.sessions || [];
                    if (!sessions.length) {
                        listEl.innerHTML = '<p class="text-muted">No investigations yet. Start one from the Console or AI Home.</p>';
                    } else {
                        let html = '';
                        sessions.forEach(s => {
                            const statusClass = s.status === 'completed' ? 'severity-info' : s.status === 'running' ? 'severity-warning' : 'severity-error';
                            html += '<div class="ai-inspector-investigation-item">';
                            html += '<div class="ai-inspector-inv-header">';
                            html += '<strong>' + _esc(s.goal) + '</strong>';
                            html += ' <span class="' + statusClass + '">' + _esc(s.status) + '</span>';
                            html += '</div>';
                            html += '<div class="text-muted">';
                            html += 'Strategy: ' + _esc(s.strategy || '-') + ' | ';
                            html += 'Steps: ' + (s.steps_done || 0) + '/' + (s.steps_total || 0) + ' | ';
                            html += 'Findings: ' + (s.findings_count || 0);
                            html += '</div>';
                            html += '</div>';
                        });
                        listEl.innerHTML = html;
                    }
                } catch (e) {
                    listEl.innerHTML = '<div class="ai-inspector-empty">Error: ' + _esc(e.message) + '</div>';
                }
            }
        }
        return;  // don't show the main panel for this tab
    }
    // Ensure main panel is visible for non-investigation tabs
    const invPanel = document.getElementById('ai-inspector-investigations');
    if (invPanel) invPanel.style.display = 'none';
    if (panel) panel.style.display = '';
}


// =============================================================================
// v0.5.25: AI Hub Section
// =============================================================================

// Module-level so mutation handlers can invalidate specific tabs without
// needing access to renderAiHub's closure. Delete an entry to force a reload
// on the user's next visit to that tab.
const _hubLoadedTabs = {};

function _invalidateHubTabs(...tabs) {
    tabs.forEach(t => delete _hubLoadedTabs[t]);
}

async function renderAiHub() {
    // Wipe the cache on every render. The section renderer clones a fresh DOM
    // template each time, so any entries from a previous renderAiHub call refer
    // to nodes that no longer exist and must not block reloads.
    Object.keys(_hubLoadedTabs).forEach(k => delete _hubLoadedTabs[k]);
    _hubLoadedTabs['hub-overview'] = true;

    // Wire tab switching
    document.querySelectorAll('.ai-hub-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.ai-hub-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            document.querySelectorAll('.ai-hub-panel').forEach(p => {
                p.style.display = p.dataset.tabPanel === target ? '' : 'none';
            });
            // Lazy-load consolidated sections on first visit (or after invalidation).
            if (!_hubLoadedTabs[target]) {
                _hubLoadedTabs[target] = true;
                if (target === 'providers') loadAiHubProviders();
                if (target === 'helpers') renderAiHelpers();
                if (target === 'profiles') renderAiProfiles();
                if (target === 'agent') renderAgentPanel();
                if (target === 'context') loadAiHubContext();
                // v0.5.28: New tabs
                if (target === 'hub-models') loadAiHubModels();
                if (target === 'routing') loadAiHubRouting();
                if (target === 'onboarding') loadAiHubOnboarding();
            }
        });
    });

    // Wire AI Profiles sub-tabs (inside the profiles panel)
    document.querySelectorAll('.ai-tab[data-ai-tab]').forEach(tab => {
        tab.addEventListener('click', () => {
            const parent = tab.closest('.ai-hub-panel') || document;
            parent.querySelectorAll('.ai-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.aiTab;
            parent.querySelectorAll('.ai-tab-pane').forEach(p => {
                p.classList.toggle('active', p.id === `ai-pane-${target}`);
            });
        });
    });

    // v0.5.28: Load Hub Overview (default tab)
    await loadAiHubOverview();

    // Wire buttons (providers tab - loaded lazily)
    const refreshBtn = document.getElementById('ai-hub-refresh-providers');
    if (refreshBtn) refreshBtn.addEventListener('click', loadAiHubProviders);

    const detectBtn = document.getElementById('ai-hub-detect-providers');
    if (detectBtn) detectBtn.addEventListener('click', loadAiHubProviders);

    const saveBtn = document.getElementById('ai-hub-cfg-save');
    if (saveBtn) saveBtn.addEventListener('click', aiHubSaveProvider);

    const pingBtn = document.getElementById('ai-hub-cfg-ping');
    if (pingBtn) pingBtn.addEventListener('click', aiHubPingProvider);

    // v0.5.45: Switch model input to dropdown when Ollama is selected;
    // pre-fill model/base_url from saved config so the user can see current
    // values and intentionally clear them (empty string → backend clears field).
    const providerSelectEl = document.getElementById('ai-hub-cfg-provider');
    if (providerSelectEl) {
        providerSelectEl.addEventListener('change', () => {
            const resultEl = document.getElementById('ai-hub-cfg-result');
            if (resultEl) resultEl.innerHTML = '';
            const kind = providerSelectEl.value;
            // Read saved config before any DOM mutations so we can pre-fill.
            const saved = (state.aiHub.providers?.providers || []).find(p => p.kind === kind);
            // Show "Clear key" only when the provider has a stored key.
            // Ollama is keyless; all other providers may have one.
            const clearKeyBtn = document.getElementById('ai-hub-cfg-clear-key');
            if (clearKeyBtn) {
                clearKeyBtn.style.display = (saved?.configured && kind !== 'ollama') ? '' : 'none';
            }
            if (kind === 'ollama') {
                // Pre-fill base_url and model BEFORE loadOllamaModels() — that
                // function reads base_url from the form to query the right host,
                // and uses the current model value for initial select pre-selection.
                const modelEl = document.getElementById('ai-hub-cfg-model');
                const baseUrlEl = document.getElementById('ai-hub-cfg-baseurl');
                if (modelEl && modelEl.tagName === 'INPUT') modelEl.value = saved?.model || '';
                if (baseUrlEl) baseUrlEl.value = saved?.base_url || '';
                loadOllamaModels();
            } else {
                restoreModelTextInput();
                // Pre-fill fields from saved provider config so users see what
                // is already stored and can explicitly clear individual fields.
                const modelEl = document.getElementById('ai-hub-cfg-model');
                const baseUrlEl = document.getElementById('ai-hub-cfg-baseurl');
                if (modelEl && modelEl.tagName === 'INPUT') modelEl.value = saved?.model || '';
                if (baseUrlEl) baseUrlEl.value = saved?.base_url || '';
            }
        });
    }

    const clearKeyBtn = document.getElementById('ai-hub-cfg-clear-key');
    if (clearKeyBtn) clearKeyBtn.addEventListener('click', clearProviderKey);

    const runBtn = document.getElementById('ai-hub-agent-run');
    if (runBtn) runBtn.addEventListener('click', aiHubRunAgent);

    const refreshCtxBtn = document.getElementById('ai-hub-refresh-context');
    if (refreshCtxBtn) refreshCtxBtn.addEventListener('click', loadAiHubContext);

    // v0.5.28: Wire overview refresh
    const overviewRefresh = document.getElementById('ai-hub-overview-refresh');
    if (overviewRefresh) overviewRefresh.addEventListener('click', loadAiHubOverview);

    // v0.5.28: Wire models tab buttons
    const modelsRefresh = document.getElementById('ai-hub-models-refresh');
    if (modelsRefresh) modelsRefresh.addEventListener('click', loadAiHubModels);

    const defaultsSave = document.getElementById('ai-hub-defaults-save');
    if (defaultsSave) defaultsSave.addEventListener('click', aiHubSaveDefaults);

    // v0.5.28: Wire routing tab refresh
    const routingRefresh = document.getElementById('ai-hub-routing-refresh');
    if (routingRefresh) routingRefresh.addEventListener('click', loadAiHubRouting);

    // v0.5.28: Wire onboarding buttons
    const testAllBtn = document.getElementById('onboarding-test-all');
    if (testAllBtn) testAllBtn.addEventListener('click', onboardingTestAll);

    // Step 1: wire provider checkboxes to rebuild the Step 2 key form and update
    // the step 1 indicator immediately — no round-trip needed.
    document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
            _buildOnboardingKeyForm();
            const checkedKinds = Array.from(
                document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]:checked')
            ).map(c => c.value);
            // Persist so selections survive tab cache wipes / section switches.
            _saveOnboardingSelections(checkedKinds);
            const anyChecked = checkedKinds.length > 0;
            const el = document.getElementById('onboarding-step-1-status');
            if (el) {
                el.textContent = anyChecked ? '✓' : '○';
                el.className = 'onboarding-step-status ' + (anyChecked ? 'text-success' : 'text-muted');
            }
        });
    });

    const saveKeysBtn = document.getElementById('onboarding-save-keys');
    if (saveKeysBtn) saveKeysBtn.addEventListener('click', onboardingSaveKeys);

    const saveDefaultsBtn = document.getElementById('onboarding-save-defaults');
    if (saveDefaultsBtn) saveDefaultsBtn.addEventListener('click', onboardingSaveDefaults);

    const runSampleBtn = document.getElementById('onboarding-run-sample');
    if (runSampleBtn) runSampleBtn.addEventListener('click', onboardingRunSample);

    // Cmd+Enter in agent textarea
    const textarea = document.getElementById('ai-hub-agent-prompt');
    if (textarea) {
        textarea.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                aiHubRunAgent();
            }
        });
    }

    // v0.5.38: Hub quick action buttons
    const qaTest = document.getElementById('ai-hub-qa-test');
    if (qaTest) qaTest.addEventListener('click', () => {
        const pingBtn2 = document.getElementById('ai-hub-cfg-ping');
        if (pingBtn2) {
            // Switch to providers tab first
            const provTab = document.querySelector('.ai-hub-tab[data-tab="providers"]');
            if (provTab) provTab.click();
            setTimeout(() => pingBtn2.click(), 200);
        }
    });
    const qaConsole = document.getElementById('ai-hub-qa-console');
    if (qaConsole) qaConsole.addEventListener('click', () => navigateTo('ai-console'));
    const qaInvestigate = document.getElementById('ai-hub-qa-investigate');
    if (qaInvestigate) qaInvestigate.addEventListener('click', () => {
        _aiHomePrefillPrompt = 'Investigate my project';
        navigateTo('ai-console');
    });
}

// v0.5.28: Global AI status indicator (sidebar)
// Combine backend readiness (credentials + chat default) with live reachability.
// ready → backend ready AND ≥1 configured provider is reachable
// partial → configured but either no defaults set or none reachable
// disabled → no configured providers
// providers === null means the /providers fetch failed; fall back to backend status
// alone to avoid falsely reporting disabled when the hub is actually configured.
function _effectiveOverall(backendStatus, providers) {
    if (providers === null) return backendStatus?.overall || 'disabled';
    const configured = providers.filter(p => p.configured);
    if (configured.length === 0) return 'disabled';
    const anyReachable = configured.some(p => p.reachable === true);
    if (!anyReachable) return 'partial';
    return backendStatus?.overall === 'ready' ? 'ready' : 'partial';
}

function _updateAiStatusIndicator(overall) {
    const indicator = document.getElementById('ai-status-indicator');
    const dot = document.getElementById('ai-status-dot');
    const label = document.getElementById('ai-status-label');
    if (!indicator) return;
    indicator.style.display = '';
    const ov = overall || 'disabled';
    dot.className = 'ai-status-dot ai-status-' + ov;
    if (ov === 'ready') {
        label.textContent = 'AI Ready';
        indicator.title = 'AI Hub: defaults set and at least one provider reachable';
    } else if (ov === 'partial') {
        label.textContent = 'AI Partial';
        indicator.title = 'AI Hub: configured but not fully ready (missing defaults or unreachable)';
    } else {
        label.textContent = 'AI Off';
        indicator.title = 'AI Hub: no providers configured';
    }
}

async function loadAiStatusIndicator() {
    const indicator = document.getElementById('ai-status-indicator');
    if (!indicator) return;
    try {
        // Need backend status (for defaults check) AND providers (for reachability).
        // providers: null on fetch failure → _effectiveOverall falls back to backend status
        // so a transient /providers error does not falsely report AI Off.
        const [data, provData] = await Promise.all([
            jsonGet('/studio/ai-hub/status').catch(() => null),
            jsonGet('/studio/ai-hub/providers').catch(() => null),
        ]);
        // Both failed → transport error, not a product state; hide rather than misreport.
        if (data === null && provData === null) { indicator.style.display = 'none'; return; }
        _updateAiStatusIndicator(_effectiveOverall(data, provData?.providers ?? null));
    } catch {
        indicator.style.display = 'none';
    }
}

// v0.5.28: Hub Overview tab
async function loadAiHubOverview() {
    const statusEl = document.getElementById('ai-hub-overall-status');
    const activeEl = document.getElementById('ai-hub-active-provider');
    const countEl = document.getElementById('ai-hub-configured-count');
    const onboardEl = document.getElementById('ai-hub-onboarding-status');
    const warningsEl = document.getElementById('ai-hub-overview-warnings');
    const defaultsEl = document.getElementById('ai-hub-defaults-summary');
    const providersEl = document.getElementById('ai-hub-overview-providers');

    try {
        // Fetch status (credentials/defaults) and provider reachability in parallel.
        // providers: null on fetch failure → _effectiveOverall falls back to backend status.
        const [data, provData] = await Promise.all([
            jsonGet('/studio/ai-hub/status'),
            jsonGet('/studio/ai-hub/providers').catch(() => null),
        ]);
        state.aiHub.status = data;

        // Combine backend readiness (defaults check) with live reachability.
        const providers = provData?.providers ?? null;
        const effectiveOverall = _effectiveOverall(data, providers);

        if (statusEl) {
            const cls = effectiveOverall === 'ready' ? 'text-success' : (effectiveOverall === 'partial' ? 'text-warning' : 'text-danger');
            statusEl.innerHTML = `<span class="${cls}">${effectiveOverall}</span>`;
        }
        if (activeEl) activeEl.textContent = data.active_provider || 'none';
        if (countEl) countEl.textContent = String(data.configured_count || 0);
        if (onboardEl) {
            const ob = data.onboarding;
            if (ob && ob.completed) {
                onboardEl.innerHTML = '<span class="text-success">✓ Complete</span>';
            } else {
                // Count only the 3 steps the backend actually tracks.
                // providers_tested and sample_query_run are not yet tracked
                // (always false), so including them would permanently cap
                // progress at 3/5 and make "Complete" unreachable.
                const done = ob ? [ob.providers_selected, ob.keys_entered, ob.defaults_set].filter(Boolean).length : 0;
                onboardEl.innerHTML = `<span class="text-warning">${done}/3 steps</span>`;
            }
        }
        // Warnings — combine backend warnings with any reachability-driven explanation.
        // The backend warns on missing defaults but has no visibility into live reachability,
        // so we must add the unreachable-provider warning on the frontend.
        if (warningsEl) {
            const warnings = [...(data.warnings || [])];
            const configuredList = providers ? providers.filter(p => p.configured) : null;
            if (configuredList && configuredList.length > 0 && !configuredList.some(p => p.reachable === true)) {
                warnings.push('No configured provider is currently reachable — check network connectivity and credentials');
            }
            warningsEl.innerHTML = warnings.map(w =>
                `<div class="info-banner warning"><span class="info-icon">⚠️</span><p>${escapeHtml(w)}</p></div>`
            ).join('');
        }
        // Defaults summary
        if (defaultsEl) {
            const d = data.defaults || {};
            defaultsEl.innerHTML = `
                <div class="defaults-row"><span class="defaults-label">Chat:</span><span class="defaults-value">${escapeHtml(d.chat_model || 'not set')} <span class="text-muted">(${escapeHtml(d.chat_provider || '-')})</span></span></div>
                <div class="defaults-row"><span class="defaults-label">Code:</span><span class="defaults-value">${escapeHtml(d.code_model || 'not set')} <span class="text-muted">(${escapeHtml(d.code_provider || '-')})</span></span></div>
                <div class="defaults-row"><span class="defaults-label">Embeddings:</span><span class="defaults-value">${escapeHtml(d.embeddings_model || 'not set')} <span class="text-muted">(${escapeHtml(d.embeddings_provider || '-')})</span></span></div>`;
        }
        // Providers summary cards (reuse already-fetched provData — no second ping).
        // providers === null means the fetch failed; render an error rather than
        // the empty-state message, which would contradict the configured_count shown above.
        if (providersEl) {
            if (providers === null) {
                providersEl.innerHTML = '<div class="empty-state text-muted"><p>Provider status unavailable.</p></div>';
            } else if (providers.length === 0) {
                providersEl.innerHTML = '<div class="empty-state"><p>No providers configured.</p></div>';
            } else {
                providersEl.innerHTML = providers.map(p => {
                    const icon = p.configured ? (p.reachable ? '✓' : '⚠') : '○';
                    const cls = p.configured ? (p.reachable ? 'status-ok' : 'status-warn') : 'status-off';
                    return `<div class="provider-summary-row">
                        <span class="provider-status ${cls}">${icon}</span>
                        <span class="provider-name">${escapeHtml(p.kind)}</span>
                        ${p.error ? `<span class="text-danger text-sm">${escapeHtml(p.error)}</span>` : ''}
                    </div>`;
                }).join('');
            }
        }
        // Update sidebar indicator using the same reachability-derived value (no extra ping).
        _updateAiStatusIndicator(effectiveOverall);
    } catch (err) {
        if (statusEl) statusEl.innerHTML = `<span class="text-danger">Error</span>`;
    }
}

// v0.5.28: Models tab
async function loadAiHubModels() {
    const tbody = document.getElementById('ai-hub-models-tbody');
    const chatInput = document.getElementById('ai-hub-default-chat');
    const codeInput = document.getElementById('ai-hub-default-code');
    const embeddingsInput = document.getElementById('ai-hub-default-embeddings');

    try {
        const data = await jsonGet('/studio/ai-hub/models');
        state.aiHub.models = data;

        // Collect unique provider names from the models list for the selects.
        // Always include the currently-saved provider even when it has no model in
        // the returned list (e.g. custom providers) — otherwise the select collapses
        // to auto and a save clears the override. However, we must ensure we do not
        // resurrect a disabled/unconfigured provider.
        const savedProviders = [data.defaults?.chat_provider, data.defaults?.code_provider, data.defaults?.embeddings_provider]
            .filter(Boolean)
            .filter(p => {
                const prov = (state.aiHub?.providers || []).find(x => x.kind === p);
                return prov && prov.configured;
            });
            
        const providerNames = [...new Set([...(data.models || []).map(m => m.provider).filter(Boolean), ...savedProviders])].sort();
        _populateProviderSelect(document.getElementById('ai-hub-default-chat-provider'), providerNames, data.defaults?.chat_provider);
        _populateProviderSelect(document.getElementById('ai-hub-default-code-provider'), providerNames, data.defaults?.code_provider);
        _populateProviderSelect(document.getElementById('ai-hub-default-embeddings-provider'), providerNames, data.defaults?.embeddings_provider);

        // Fill defaults fields AND hydrate provider metadata onto each input
        // so a subsequent save round-trips the provider, not just the model id.
        if (data.defaults) {
            _hydrateModelInput(chatInput, data.defaults.chat_model, data.defaults.chat_provider);
            _hydrateModelInput(codeInput, data.defaults.code_model, data.defaults.code_provider);
            _hydrateModelInput(embeddingsInput, data.defaults.embeddings_model, data.defaults.embeddings_provider);
        }

        // Fill models table — v0.5.43: 4 columns with "Use as default" button
        if (tbody) {
            if (!data.models || data.models.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No models available</td></tr>';
            } else {
                tbody.innerHTML = data.models.map(m => {
                    const btn = `<button class="btn btn-xs btn-ghost" onclick="aiHubUseModel('${escapeHtml(m.model_id)}','${escapeHtml(m.mode)}','${escapeHtml(m.provider)}')" title="Set as ${escapeHtml(m.mode)} default">Use</button>`;
                    return `<tr>
                        <td><code>${escapeHtml(m.model_id)}</code></td>
                        <td>${escapeHtml(m.provider)}</td>
                        <td>${escapeHtml(m.mode)}</td>
                        <td>${btn}</td>
                    </tr>`;
                }).join('');
            }
        }
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// Populate a provider <select> with an "auto" option plus one option per
// provider name. Preserves/restores the currently-selected value if present.
function _populateProviderSelect(selectEl, providerNames, currentProvider) {
    if (!selectEl) return;
    const prev = selectEl.value || currentProvider || '';
    selectEl.innerHTML = '<option value="">auto</option>' +
        providerNames.map(n => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join('');
    if (prev && Array.from(selectEl.options).some(o => o.value === prev)) {
        selectEl.value = prev;
    }
}

// Hydrate a model input with both value AND its associated provider, and
// install a one-time listener that clears dataset.provider on manual edit.
// The backend treats a missing provider as "leave unchanged", so clearing on
// manual edit is the safe default — the user is editing the model id alone.
// Also syncs the associated provider <select> (id = inputEl.id + '-provider').
function _hydrateModelInput(input, modelId, provider) {
    if (!input) return;
    input.value = modelId || '';
    input.dataset.provider = provider || '';
    // Sync the sibling provider select if it exists
    const provSel = document.getElementById(input.id + '-provider');
    if (provSel && provider) provSel.value = provider;
    if (!input.dataset.editListenerInstalled) {
        input.addEventListener('input', () => {
            // Manual edit: drop the stale provider association. Backend then
            // sees provider=null and keeps the previously persisted provider
            // intact (instead of pinning to a now-mismatched one).
            input.dataset.provider = '';
        });
        input.dataset.editListenerInstalled = '1';
    }
}

// Read the effective provider for a model input from the associated select.
// Returns the select's literal value:
//   "" when "auto" is selected → backend treats "" as "clear the stored override"
//   "openai" / etc. → backend sets the provider to that value
//   null (selectEl absent) → backend treats null as "don't change"
// Never falls back to dataset.provider: if the persisted provider is not in
// the option list the select correctly shows "auto", and sending "" to the
// backend re-clears to unset rather than silently re-posting a stale value.
function _readModelProvider(inputEl, selectEl) {
    if (!selectEl) return null;
    return selectEl.value;  // "" for auto, provider name otherwise
}

// v0.5.43: Populate a default model field from the Available Models table
function aiHubUseModel(modelId, mode, provider) {
    const modeToId = { chat: 'ai-hub-default-chat', code: 'ai-hub-default-code', embeddings: 'ai-hub-default-embeddings' };
    const inputId = modeToId[mode];
    if (!inputId) return;
    const input = document.getElementById(inputId);
    if (!input) return;
    // Use the shared hydrator so the input edit listener is installed even
    // when this is the user's first interaction with the field.
    _hydrateModelInput(input, modelId, provider);
    input.classList.add('flash-highlight');
    setTimeout(() => input.classList.remove('flash-highlight'), 900);
}

async function aiHubSaveDefaults() {
    const resultEl = document.getElementById('ai-hub-defaults-result');
    const chatEl = document.getElementById('ai-hub-default-chat');
    const codeEl = document.getElementById('ai-hub-default-code');
    const embeddingsEl = document.getElementById('ai-hub-default-embeddings');
    const chatProvSel = document.getElementById('ai-hub-default-chat-provider');
    const codeProvSel = document.getElementById('ai-hub-default-code-provider');
    const embProvSel = document.getElementById('ai-hub-default-embeddings-provider');

    try {
        const resp = await jsonPost('/studio/ai-hub/defaults', {
            // Use ?? so an explicitly-cleared field sends "" (→ backend clear)
            // rather than null (→ backend "don't change").
            chat_model: chatEl?.value ?? null,
            chat_provider: _readModelProvider(chatEl, chatProvSel),
            code_model: codeEl?.value ?? null,
            code_provider: _readModelProvider(codeEl, codeProvSel),
            embeddings_model: embeddingsEl?.value ?? null,
            embeddings_provider: _readModelProvider(embeddingsEl, embProvSel),
        });
        if (resultEl) {
            resultEl.innerHTML = resp.ok
                ? `<span class="text-success">✓ ${escapeHtml(resp.message || 'Defaults saved')}</span>`
                : `<span class="text-danger">✗ ${escapeHtml(resp.message || 'Failed')}</span>`;
        }
        if (resp.ok) {
            // Defaults affect hub readiness (partial → ready) and onboarding step 4.
            loadAiHubOverview();
            loadAiStatusIndicator();
            _invalidateHubTabs('onboarding', 'routing');
        }
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(err.message)}</span>`;
    }
}

// v0.5.28: Routing tab
async function loadAiHubRouting() {
    const tbody = document.getElementById('ai-hub-routing-tbody');
    const warningsEl = document.getElementById('ai-hub-routing-warnings');

    try {
        const data = await jsonGet('/studio/ai-hub/routes');
        state.aiHub.routing = data;

        if (tbody) {
            const routes = data.routes || [];
            if (routes.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No routing data available.</td></tr>';
            } else {
                tbody.innerHTML = routes.map(r => {
                    const statusCls = r.status === 'ok' ? 'text-success'
                        : (['fallback', 'unreachable'].includes(r.status) ? 'text-warning' : 'text-muted');
                    const statusIcon = {'ok': '✓ Active', 'fallback': '⚠ Fallback',
                        'unreachable': '⚠ Unreachable', 'missing': '○ Missing'}[r.status] || '○ Missing';
                    return `<tr>
                        <td><strong>${escapeHtml(r.feature)}</strong></td>
                        <td>${escapeHtml(r.provider || '-')}</td>
                        <td><code>${escapeHtml(r.model || '-')}</code></td>
                        <td><span class="${statusCls}">${statusIcon}</span>${r.warning ? ` <span class="text-muted text-sm">${escapeHtml(r.warning)}</span>` : ''}</td>
                    </tr>`;
                }).join('');
            }
        }

        // Warnings
        if (warningsEl) {
            const warnings = data.warnings || [];
            warningsEl.innerHTML = warnings.map(w =>
                `<div class="info-banner warning"><span class="info-icon">⚠️</span><p>${escapeHtml(w)}</p></div>`
            ).join('');
        }
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// Local persistence for the two onboarding steps the backend doesn't track
// (test connections, sample query). Without this the onboarding tab would
// keep showing them as ○ even seconds after the user successfully ran them,
// while the overview screen reports "Complete" — that contradiction is what
// this fills in. Stored in localStorage so it survives page reloads.
//
// The key incorporates a hub fingerprint so flags auto-invalidate when the
// hub configuration changes (provider added/removed, active provider switch,
// or default models change). A different fingerprint = a different key =
// fresh flags, preventing stale "Complete" state across different configs.
const _ONBOARDING_LS_KEY = 'aksara.aihub.onboarding.session';
// Stable key for Step 1 selections — not fingerprint-scoped so that a save that
// changes the fingerprint (e.g. OpenAI configured, Anthropic still pending) does
// not drop the still-pending selection.
const _ONBOARDING_SELECTIONS_KEY = 'aksara.aihub.onboarding.selections';
// Cache of the last known configured provider kinds — refreshed on every successful
// /providers fetch so that a transient failure can still show configured providers
// in Step 1 / Step 2 even after a fresh DOM render (all checkboxes start unchecked).
const _CONFIGURED_KINDS_CACHE_KEY = 'aksara.aihub.configured.kinds';
let _hubFingerprint = '';

function _computeHubFingerprint(data, configuredProviders = []) {
    // Encodes the actual configured provider roster including each provider's
    // base URL so that: kind swaps, base URL changes, and new/removed providers
    // all produce a different key and invalidate stored tested/sampled flags.
    // API key changes cannot be covered without exposing secrets — that gap is
    // accepted; rotating a valid key on a working provider is an edge case.
    const d = data.defaults || {};
    const rosterStr = [...configuredProviders]
        .sort((a, b) => a.kind.localeCompare(b.kind))
        .map(p => `${p.kind}@${p.base_url || ''}`)
        .join(',');
    return [
        data.active_provider || '',
        rosterStr,
        d.chat_model || '',
        d.chat_provider || '',
        d.code_model || '',
        d.code_provider || '',
        d.embeddings_model || '',
        d.embeddings_provider || '',
    ].join(':');
}

// Rebuild the Step 2 key-entry form from currently-checked provider checkboxes.
// Called on checkbox change and after loadAiHubOnboarding pre-checks boxes.
function _buildOnboardingKeyForm() {
    const form = document.getElementById('onboarding-keys-form');
    if (!form) return;
    // Snapshot unsaved values before rebuilding so checkbox toggles don't erase typed input.
    const saved = {};
    form.querySelectorAll('input[data-provider]').forEach(el => {
        if (el.value) saved[`${el.dataset.provider}:${el.dataset.field || 'api_key'}`] = el.value;
    });
    // [label, input-type, data-field, placeholder]
    const FIELDS = {
        openai:    ['OpenAI API Key',       'password', 'api_key',  '<API_KEY>'],
        anthropic: ['Anthropic API Key',    'password', 'api_key',  '<ANTHROPIC_API_KEY>'],
        azure:     ['Azure OpenAI API Key', 'password', 'api_key',  ''],
        ollama:    ['Ollama Base URL',      'text',     'base_url', 'http://localhost:11434'],
        custom:    ['Custom HTTP API Key',  'password', 'api_key',  ''],
    };
    const checked = Array.from(
        document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]:checked')
    ).map(cb => cb.value);
    if (checked.length === 0) {
        form.innerHTML = '<p class="text-muted" style="grid-column:1/-1">Select at least one provider above.</p>';
        return;
    }
    form.innerHTML = checked.map(kind => {
        const [label, type, field, ph] = FIELDS[kind] || [`${kind} Key`, 'password', 'api_key', ''];
        return `<div class="form-group">
            <label>${escapeHtml(label)}</label>
            <input type="${type}" class="form-input" data-provider="${kind}" data-field="${field}" placeholder="${escapeHtml(ph)}" autocomplete="off">
        </div>`;
    }).join('');
    // Restore any values that survived the rebuild.
    form.querySelectorAll('input[data-provider]').forEach(el => {
        const v = saved[`${el.dataset.provider}:${el.dataset.field || 'api_key'}`];
        if (v) el.value = v;
    });
}

function _readOnboardingSession() {
    try {
        const key = `${_ONBOARDING_LS_KEY}:${_hubFingerprint}`;
        return JSON.parse(localStorage.getItem(key) || '{}') || {};
    } catch { return {}; }
}
function _markOnboardingStep(step) {
    try {
        const key = `${_ONBOARDING_LS_KEY}:${_hubFingerprint}`;
        const s = _readOnboardingSession();
        s[step] = true;
        localStorage.setItem(key, JSON.stringify(s));
    } catch { /* localStorage may be disabled */ }
}

// After any single-provider test (Providers tab card or Configure panel ping),
// fetch the full provider list and mark onboarding Step 3 as done when ALL
// configured providers are reachable — mirrors the all-at-once check in
// onboardingTestAll so the two paths converge on the same completion signal.
async function _checkAndMarkAllTested() {
    try {
        const provData = await jsonGet('/studio/ai-hub/providers');
        const configured = (provData.providers || []).filter(p => p.configured);
        if (configured.length > 0 && configured.every(p => p.reachable === true)) {
            _markOnboardingStep('tested');
            loadAiHubOnboarding();
        }
    } catch { /* ignore — onboarding stays at current state */ }
}
// Persist Step 1 provider selections so checked-but-unconfigured providers
// survive tab reloads and section switches (the DOM is rebuilt from template).
// Uses a stable key independent of the fingerprint so that a save which changes
// the fingerprint (e.g. OpenAI configured, Anthropic still pending) does not
// evict the still-pending selection.
function _saveOnboardingSelections(kinds) {
    try {
        localStorage.setItem(_ONBOARDING_SELECTIONS_KEY, JSON.stringify(kinds));
    } catch { /* localStorage may be disabled */ }
}
function _loadOnboardingSelections() {
    try {
        return JSON.parse(localStorage.getItem(_ONBOARDING_SELECTIONS_KEY) || '[]') || [];
    } catch { return []; }
}
function _saveConfiguredKindsCache(kinds) {
    try { localStorage.setItem(_CONFIGURED_KINDS_CACHE_KEY, JSON.stringify(kinds)); } catch {}
}
function _loadConfiguredKindsCache() {
    try { return JSON.parse(localStorage.getItem(_CONFIGURED_KINDS_CACHE_KEY) || '[]') || []; } catch { return []; }
}

// v0.5.28: Onboarding tab
async function loadAiHubOnboarding() {
    try {
        // Fetch status and providers in parallel so we can build a fingerprint
        // that includes the actual configured provider roster — not just counts.
        // A provider swap (same count, different kinds) then correctly
        // invalidates stored session flags.
        const [data, provData] = await Promise.all([
            jsonGet('/studio/ai-hub/status'),
            jsonGet('/studio/ai-hub/providers').catch(() => null),  // null = transient failure
        ]);

        const persistedSelections = new Set(_loadOnboardingSelections());
        let configuredProviders = [];
        let configuredKindSet = new Set();
        let providersKnown = false;  // true only when we got a valid /providers response

        if (provData !== null) {
            providersKnown = true;
            configuredProviders = (provData.providers || [])
                .filter(p => p.configured)
                .map(p => ({ kind: p.kind, base_url: p.base_url || '' }));
            configuredKindSet = new Set(configuredProviders.map(p => p.kind));
            // Refresh the configured-kinds cache so future failure paths can fall back to it.
            _saveConfiguredKindsCache(configuredProviders.map(p => p.kind));
            // Update the fingerprint only on a known-good response.
            _hubFingerprint = _computeHubFingerprint(data, configuredProviders);

            // Restore checkboxes from server truth + stable manual selections.
            document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]').forEach(cb => {
                cb.checked = configuredKindSet.has(cb.value) || persistedSelections.has(cb.value);
            });
        } else {
            // Providers fetch failed — restore from stable selections AND the last-known
            // configured-kinds cache so that fresh DOM renders (all checkboxes start unchecked)
            // still show providers that were configured but never manually checked.
            const cachedKinds = new Set(_loadConfiguredKindsCache());
            document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]').forEach(cb => {
                if (cachedKinds.has(cb.value) || persistedSelections.has(cb.value)) cb.checked = true;
            });
        }
        _buildOnboardingKeyForm();

        const ob = data.onboarding || {};
        // Always read the fingerprint-scoped session — when providers fetch fails,
        // _hubFingerprint still holds the last successful fingerprint, so the bucket
        // is the same one that was written on the last good load.  Zeroing out
        // session on failure would break the Step 3 / Step 5 fallback paths.
        const session = _readOnboardingSession();
        // Steps 3 (providers_tested) and 5 (sample_query_run) aren't persisted
        // server-side; OR the session flag in so the tab doesn't contradict
        // the overview's "Complete" state after the user runs those actions.
        // Step 1 is done when any provider is configured OR any checkbox is checked.
        const checkedKinds = Array.from(
            document.querySelectorAll('#onboarding-provider-select input[type="checkbox"]:checked')
        ).map(cb => cb.value);
        const anyChecked = checkedKinds.length > 0;
        // Step 2 is done when every checked provider has been configured.
        // Falls back to the backend flag when providers are unknown (fetch failed).
        const allCheckedConfigured = providersKnown && checkedKinds.length > 0
            ? checkedKinds.every(k => configuredKindSet.has(k))
            : !!ob.keys_entered;

        // Step 3: computed from live reachability when providers are known so that
        // the step clears automatically when a provider later becomes unreachable
        // (e.g. Ollama goes down). Falls back to session.tested only on providers
        // fetch failure so the step does not vanish during a transient outage.
        let step3done;
        if (providersKnown) {
            const liveConfigured = (provData.providers || []).filter(p => p.configured);
            step3done = liveConfigured.length > 0 && liveConfigured.every(p => p.reachable === true);
        } else {
            step3done = !!session.tested;
        }

        const steps = [
            { id: 1, done: !!(ob.providers_selected || anyChecked) },
            { id: 2, done: allCheckedConfigured },
            { id: 3, done: step3done },
            { id: 4, done: !!ob.defaults_set },
            { id: 5, done: !!(ob.sample_query_run || session.sampled) },
        ];
        steps.forEach(s => {
            const el = document.getElementById(`onboarding-step-${s.id}-status`);
            if (el) {
                el.textContent = s.done ? '✓' : '○';
                el.className = 'onboarding-step-status ' + (s.done ? 'text-success' : 'text-muted');
            }
        });

        // Pre-fill onboarding default-model inputs from current settings AND
        // hydrate provider metadata, so a save round-trips provider correctly.
        const d = data.defaults || {};
        _hydrateModelInput(document.getElementById('onboarding-default-chat'), d.chat_model, d.chat_provider);
        _hydrateModelInput(document.getElementById('onboarding-default-code'), d.code_model, d.code_provider);
        _hydrateModelInput(document.getElementById('onboarding-default-embeddings'), d.embeddings_model, d.embeddings_provider);

        // Populate provider selects from live data when available; fall back to the
        // configured-kinds cache on outage so pinned provider overrides are not
        // silently cleared by a save that reads the still-auto-only select.
        const providerNames = providersKnown
            ? configuredProviders.map(p => p.kind).sort()
            : _loadConfiguredKindsCache().sort();
        _populateProviderSelect(document.getElementById('onboarding-default-chat-provider'), providerNames, d.chat_provider);
        _populateProviderSelect(document.getElementById('onboarding-default-code-provider'), providerNames, d.code_provider);
        _populateProviderSelect(document.getElementById('onboarding-default-embeddings-provider'), providerNames, d.embeddings_provider);
    } catch {
        // ignore
    }
}

async function onboardingTestAll() {
    const container = document.getElementById('onboarding-test-results');
    if (!container) return;
    container.innerHTML = '<p class="text-muted">Testing providers...</p>';

    try {
        const provData = await jsonGet('/studio/ai-hub/providers');
        const providers = (provData.providers || []).filter(p => p.configured);
        if (providers.length === 0) {
            container.innerHTML = '<p class="text-muted">No configured providers to test.</p>';
            return;
        }
        const results = [];
        for (const p of providers) {
            try {
                const resp = await jsonPost('/studio/ai-hub/test', { provider: p.kind });
                results.push(resp);
            } catch (err) {
                results.push({ provider: p.kind, reachable: false, error: err.message });
            }
        }
        container.innerHTML = results.map(r => {
            const icon = r.reachable ? '✓' : '✗';
            const cls = r.reachable ? 'text-success' : 'text-danger';
            const latency = r.latency_ms ? ` (${r.latency_ms}ms)` : '';
            return `<div class="onboarding-test-row"><span class="${cls}">${icon} ${escapeHtml(r.provider)}${latency}</span>${r.error ? ` <span class="text-danger">${escapeHtml(r.error)}</span>` : ''}</div>`;
        }).join('');
        // Mark step 3 as done only when every tested provider is reachable —
        // "Verify that each provider is reachable" means the full set, not just one.
        if (results.length > 0 && results.every(r => r.reachable)) {
            _markOnboardingStep('tested');
            loadAiHubOnboarding();
        }
    } catch (err) {
        container.innerHTML = `<p class="text-danger">Error: ${escapeHtml(err.message)}</p>`;
    }
}

async function onboardingSaveKeys() {
    const form = document.getElementById('onboarding-keys-form');
    const resultEl = document.getElementById('onboarding-keys-result');
    if (resultEl) resultEl.innerHTML = '';
    if (!form) return;
    const inputs = form.querySelectorAll('input[data-provider]');
    const errors = [];
    let savedCount = 0;
    for (const input of inputs) {
        const provider = input.dataset.provider;
        const field = input.dataset.field || 'api_key';
        const value = input.value?.trim();
        if (!value) continue;
        try {
            if (field === 'base_url') {
                // Ollama and similar keyless providers use configure (non-secret).
                await jsonPost('/studio/ai-hub/configure', { provider, base_url: value });
            } else {
                await jsonPost('/studio/ai-hub/configure/secret', { provider, api_key: value });
            }
            savedCount++;
        } catch (err) {
            errors.push({ provider, message: err?.message || 'Save failed' });
        }
    }
    if (resultEl) {
        const parts = [];
        if (savedCount > 0) {
            parts.push(`<span class="text-success">✓ Saved ${savedCount} provider${savedCount === 1 ? '' : 's'}</span>`);
        }
        errors.forEach(e => {
            parts.push(`<span class="text-danger">✗ ${escapeHtml(e.provider)}: ${escapeHtml(e.message)}</span>`);
        });
        resultEl.innerHTML = parts.join('<br>');
    }
    // Saving keys moves providers from unconfigured → configured.
    loadAiHubOnboarding();
    loadAiHubOverview();
    loadAiStatusIndicator();
    // New provider config affects providers cards, available models, and routing.
    _invalidateHubTabs('hub-models', 'routing', 'providers');
}

async function onboardingSaveDefaults() {
    const chatEl = document.getElementById('onboarding-default-chat');
    const codeEl = document.getElementById('onboarding-default-code');
    const embeddingsEl = document.getElementById('onboarding-default-embeddings');
    const chatProvSel = document.getElementById('onboarding-default-chat-provider');
    const codeProvSel = document.getElementById('onboarding-default-code-provider');
    const embProvSel = document.getElementById('onboarding-default-embeddings-provider');

    try {
        await jsonPost('/studio/ai-hub/defaults', {
            chat_model: chatEl?.value ?? null,
            chat_provider: _readModelProvider(chatEl, chatProvSel),
            code_model: codeEl?.value ?? null,
            code_provider: _readModelProvider(codeEl, codeProvSel),
            embeddings_model: embeddingsEl?.value ?? null,
            embeddings_provider: _readModelProvider(embeddingsEl, embProvSel),
        });
        // Setting defaults can advance hub readiness from partial → ready.
        loadAiHubOnboarding();
        loadAiHubOverview();
        loadAiStatusIndicator();
        _invalidateHubTabs('routing', 'onboarding');
    } catch { /* ignore */ }
}

async function onboardingRunSample() {
    const resultEl = document.getElementById('onboarding-sample-result');
    const prompt = document.getElementById('onboarding-sample-prompt')?.value?.trim();
    if (!prompt) return;
    if (resultEl) resultEl.innerHTML = '<span class="text-muted">Running...</span>';

    try {
        const resp = await jsonPost('/studio/ai-hub/agent/run', {
            prompt, include_context: true,
        });
        if (resultEl) {
            if (resp.error) {
                resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(resp.error)}</span>`;
            } else {
                resultEl.innerHTML = `<span class="text-success">✓ Response received (${resp.provider}/${resp.model})</span><pre class="ai-hub-output-body">${escapeHtml(resp.output?.substring(0, 500) || '')}</pre>`;
                _markOnboardingStep('sampled');
            }
        }
        loadAiHubOnboarding();
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(err.message)}</span>`;
    }
}

async function loadAiHubProviders() {
    const container = document.getElementById('ai-hub-provider-list');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><p>Loading...</p></div>';

    try {
        const data = await jsonGet('/studio/ai-hub/providers');
        state.aiHub.providers = data;
        // Keep the configured-kinds cache current so the onboarding failure fallback
        // reflects edits made via the Providers tab, not just via the Onboarding tab.
        _saveConfiguredKindsCache(
            (data.providers || []).filter(p => p.configured).map(p => p.kind)
        );

        if (!data.providers || data.providers.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No AI providers detected.</p>
                    <p class="text-muted">Set environment variables (e.g., OPENAI_API_KEY) or use Configure below.</p>
                </div>`;
            return;
        }

        const activeKey = data.active_provider;
        const providerIcons = { openai: '🤖', anthropic: '🧠', azure: '☁️', ollama: '🦙', custom: '🔌' };
        container.innerHTML = data.providers.map(p => {
            const isActive = p.kind === activeKey;
            const statusClass = p.reachable ? 'status-ok' : (p.configured ? 'status-warn' : 'status-off');
            const statusIcon = p.reachable ? '✓' : (p.configured ? '⚠' : '○');
            const statusText = p.reachable ? 'Reachable' : (p.configured ? 'Configured' : 'Not configured');
            const icon = providerIcons[p.kind] || '🔌';
            const modesStr = (p.modes || []).join(', ') || '-';
            return `
                <div class="provider-card ${isActive ? 'provider-active' : ''}">
                    <div class="provider-header">
                        <span class="provider-name"><span class="provider-icon">${icon}</span> ${escapeHtml(p.kind)}${isActive ? ' <span class="badge badge-primary">active</span>' : ''}</span>
                        <span class="provider-status ${statusClass}">${statusIcon} ${statusText}</span>
                    </div>
                    <div class="provider-details">
                        ${p.model ? `<span class="detail-item">Model: <code>${escapeHtml(p.model)}</code></span>` : ''}
                        ${p.base_url ? `<span class="detail-item">URL: <code>${escapeHtml(p.base_url)}</code></span>` : ''}
                        <span class="detail-item">Modes: ${escapeHtml(modesStr)}</span>
                        ${p.error ? `<span class="detail-item text-danger">Error: ${escapeHtml(p.error)}</span>` : ''}
                    </div>
                    <div class="provider-card-actions">
                        <button class="btn btn-xs btn-secondary" onclick="aiHubTestProvider('${escapeHtml(p.kind)}')">Test</button>
                        <button class="btn btn-xs btn-secondary" onclick="aiHubSelectProvider('${escapeHtml(p.kind)}')">Configure</button>
                    </div>
                </div>`;
        }).join('');

        // Populate agent provider selector
        const agentSelect = document.getElementById('ai-hub-agent-provider');
        if (agentSelect) {
            agentSelect.innerHTML = '<option value="">Hub Chat Default</option>' +
                data.providers.filter(p => p.configured).map(p =>
                    `<option value="${p.kind}">${p.kind}${p.kind === activeKey ? ' (active)' : ''}</option>`
                ).join('');
        }

        // Hydrate the configure form for the currently selected provider.
        // state.aiHub.providers is now fresh so the change handler can read
        // up-to-date model, base_url, and configured flag for pre-fill/Clear-key.
        const cfgSelect = document.getElementById('ai-hub-cfg-provider');
        if (cfgSelect) cfgSelect.dispatchEvent(new Event('change'));
    } catch (err) {
        // Null out cached state so _refreshFlowButtonGate falls back to backend
        // status rather than recomputing from a stale pre-mutation provider list.
        state.aiHub.providers = null;
        container.innerHTML = `<div class="empty-state"><p class="text-danger">Error: ${escapeHtml(err.message)}</p></div>`;
    }
}

// v0.5.28: Test a specific provider from the provider card
async function aiHubTestProvider(providerKind) {
    try {
        const resp = await jsonPost('/studio/ai-hub/test', { provider: providerKind });
        const msg = resp.reachable
            ? `✓ ${providerKind} reachable (${resp.latency_ms || 0}ms)`
            : `✗ ${providerKind}: ${resp.error || 'Unreachable'}`;
        showToast(msg, resp.reachable ? 'success' : 'error');
        // Propagate new reachability to provider list, overview, routing, and sidebar.
        await loadAiHubProviders();
        _refreshFlowButtonGate();
        loadAiHubOverview();
        loadAiStatusIndicator();
        _invalidateHubTabs('routing');
        // Mark onboarding Step 3 if all configured providers are now reachable.
        _checkAndMarkAllTested();
    } catch (err) {
        showToast(`Error testing ${providerKind}: ${err.message}`, 'error');
    }
}

// v0.5.28: Select a provider in the configure form
function aiHubSelectProvider(providerKind) {
    const select = document.getElementById('ai-hub-cfg-provider');
    if (select) {
        select.value = providerKind;
        // Dispatch change so the handler fires: pre-fills saved model/base_url
        // and switches the model input to a dropdown for Ollama.
        select.dispatchEvent(new Event('change'));
    }
    const panel = document.getElementById('ai-hub-provider-config-panel');
    if (panel) panel.scrollIntoView({ behavior: 'smooth' });
}

// v0.5.43: Ollama live model discovery — replace text input with a <select> when Ollama is chosen
async function loadOllamaModels() {
    const baseUrl = document.getElementById('ai-hub-cfg-baseurl')?.value || '';
    const resultEl = document.getElementById('ai-hub-cfg-result');
    const existingInput = document.getElementById('ai-hub-cfg-model');
    if (existingInput) existingInput.placeholder = 'Loading models…';
    try {
        const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : '';
        const data = await jsonGet(`/studio/ai-hub/ollama/models${params}`);
        if (!data.running) {
            if (resultEl) resultEl.innerHTML = '<span class="text-warning">⚠ Ollama not running — enter model name manually or start Ollama</span>';
            if (existingInput) existingInput.placeholder = 'llama3';
            return;
        }
        if (data.models && data.models.length > 0) {
            const currentVal = existingInput?.value || '';
            const select = document.createElement('select');
            select.id = 'ai-hub-cfg-model';
            select.className = 'form-select';
            data.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === currentVal || (!currentVal && m.includes('llama3'))) opt.selected = true;
                select.appendChild(opt);
            });
            existingInput?.replaceWith(select);
            if (resultEl) resultEl.innerHTML = `<span class="text-success">✓ Ollama running — ${data.models.length} model(s) available</span>`;
        } else {
            if (resultEl) resultEl.innerHTML = '<span class="text-warning">⚠ Ollama running but no models pulled — run: <code>ollama pull llama3</code></span>';
            if (existingInput) existingInput.placeholder = 'llama3';
        }
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error querying Ollama: ${escapeHtml(err.message)}</span>`;
    }
}

function restoreModelTextInput() {
    const existing = document.getElementById('ai-hub-cfg-model');
    if (existing && existing.tagName === 'SELECT') {
        const input = document.createElement('input');
        input.type = 'text';
        input.id = 'ai-hub-cfg-model';
        input.className = 'form-input';
        input.placeholder = 'gpt-4o';
        existing.replaceWith(input);
    }
}

async function clearProviderKey() {
    const resultEl = document.getElementById('ai-hub-cfg-result');
    const provider = document.getElementById('ai-hub-cfg-provider')?.value;
    if (!provider) return;
    try {
        const resp = await jsonPost('/studio/ai-hub/configure/secret', { provider, api_key: '' });
        if (resultEl) {
            resultEl.innerHTML = resp.ok
                ? `<span class="text-success">✓ ${escapeHtml(resp.message || 'Key cleared')}</span>`
                : `<span class="text-danger">✗ ${escapeHtml(resp.message || 'Failed')}</span>`;
        }
        if (resp.ok) {
            // Hide the button — key no longer exists
            const btn = document.getElementById('ai-hub-cfg-clear-key');
            if (btn) btn.style.display = 'none';
            await loadAiHubProviders();
            _refreshFlowButtonGate();
            loadAiHubOverview();
            loadAiStatusIndicator();
            _invalidateHubTabs('hub-models', 'routing', 'onboarding');
        }
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(err.message)}</span>`;
    }
}

async function aiHubSaveProvider() {
    const resultEl = document.getElementById('ai-hub-cfg-result');
    const provider = document.getElementById('ai-hub-cfg-provider')?.value;
    const apiKey = document.getElementById('ai-hub-cfg-apikey')?.value;
    const model = document.getElementById('ai-hub-cfg-model')?.value;
    const baseUrl = document.getElementById('ai-hub-cfg-baseurl')?.value;

    if (!provider) return;

    // New AI Hub contract splits provider config into two endpoints:
    //   /studio/ai-hub/configure         — non-secret fields (base_url, model)
    //   /studio/ai-hub/configure/secret  — api_key only (written to .env)
    // The old /studio/ai/hub/providers/save bundled both, which made it
    // harder to reason about which call leaks secrets.
    try {
        const cfg = await jsonPost('/studio/ai-hub/configure', {
            provider,
            // Use ?? (not ||) so an explicitly-cleared field sends "" rather
            // than null. The backend converts "" → None (clear the field),
            // while null means "don't change" — two distinct operations.
            base_url: baseUrl ?? null,
            model: model ?? null,
            enabled: true,
        });
        let secretResp = { ok: true, message: '' };
        if (apiKey) {
            secretResp = await jsonPost('/studio/ai-hub/configure/secret', {
                provider, api_key: apiKey,
            });
        }
        const ok = cfg.ok && secretResp.ok;
        const message = [cfg.message, secretResp.message].filter(Boolean).join('; ');
        if (resultEl) {
            resultEl.innerHTML = ok
                ? `<span class="text-success">✓ ${escapeHtml(message || 'Saved')}</span>`
                : `<span class="text-danger">✗ ${escapeHtml(message || 'Failed')}</span>`;
        }
        if (ok) {
            await loadAiHubProviders();
            _refreshFlowButtonGate();
            // Also refresh the overview: counts, overall status, and sidebar indicator.
            loadAiHubOverview();
            loadAiStatusIndicator();
            // Invalidate dependent tabs so they reload on next visit: models
            // list may have new providers; routing and onboarding step status change.
            _invalidateHubTabs('hub-models', 'routing', 'onboarding');
        }
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(err.message)}</span>`;
    }
}

async function aiHubPingProvider() {
    const resultEl = document.getElementById('ai-hub-cfg-result');
    const provider = document.getElementById('ai-hub-cfg-provider')?.value;

    // /studio/ai-hub/test is the new-family equivalent of /providers/ping.
    // Response shape is compatible (provider/reachable/latency_ms/error).
    try {
        const resp = await jsonPost('/studio/ai-hub/test', { provider: provider || '' });
        if (resultEl) {
            resultEl.innerHTML = resp.reachable
                ? `<span class="text-success">✓ ${resp.provider} reachable (${resp.latency_ms}ms)</span>`
                : `<span class="text-danger">✗ ${resp.provider}: ${escapeHtml(resp.error || 'Unreachable')}</span>`;
        }
        // Refresh provider list and overview so reachability state propagates.
        // Invalidate routing so the next routing tab load reflects updated reachability.
        await loadAiHubProviders();
        _refreshFlowButtonGate();
        loadAiHubOverview();
        loadAiStatusIndicator();
        _invalidateHubTabs('routing');
        // Mark onboarding Step 3 if all configured providers are now reachable.
        _checkAndMarkAllTested();
    } catch (err) {
        if (resultEl) resultEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(err.message)}</span>`;
    }
}

async function loadAiHubContext() {
    const container = document.getElementById('ai-hub-context-tree');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><p>Loading context...</p></div>';

    try {
        // Use the summary endpoint: computes only cheap sections (project_info,
        // models, routes, schema_checksum, ai_profiles, ai_hints) and reports
        // size_kb=null for expensive/async sections so the tab stays fast.
        const sections = await jsonGet('/studio/agent/context/summary');

        if (!sections || sections.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No context available.</p></div>';
            return;
        }

        container.innerHTML = sections.map(s => {
            const sizeLabel = s.size_kb === null
                ? 'built on demand'
                : s.size_kb > 1 ? `${s.size_kb.toFixed(1)} KB` : `${Math.round(s.size_kb * 1024)} B`;
            return `
                <div class="context-section">
                    <div class="context-section-header">
                        <span class="context-key">${escapeHtml(s.name)}</span>
                        <span class="badge badge-secondary">${sizeLabel}</span>
                    </div>
                    <div class="context-preview text-muted">${escapeHtml(s.description || '')}</div>
                </div>`;
        }).join('');
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p class="text-danger">Error: ${escapeHtml(err.message)}</p></div>`;
    }
}

async function aiHubRunAgent() {
    const promptEl = document.getElementById('ai-hub-agent-prompt');
    const outputContainer = document.getElementById('ai-hub-agent-output');
    const resultEl = document.getElementById('ai-hub-agent-result');
    const metaEl = document.getElementById('ai-hub-agent-meta');
    const runBtn = document.getElementById('ai-hub-agent-run');
    const providerSelect = document.getElementById('ai-hub-agent-provider');
    const includeCtx = document.getElementById('ai-hub-agent-include-ctx');

    const prompt = promptEl?.value?.trim();
    if (!prompt) return;

    if (runBtn) { runBtn.disabled = true; runBtn.textContent = 'Running...'; }
    if (outputContainer) outputContainer.style.display = '';
    if (resultEl) resultEl.textContent = 'Generating...';

    try {
        const resp = await jsonPost('/studio/ai-hub/agent/run', {
            prompt,
            provider: providerSelect?.value || null,
            include_context: includeCtx?.checked ?? true,
        });

        state.aiHub.agentOutput = resp;

        if (resp.error) {
            if (resultEl) resultEl.textContent = `Error: ${resp.error}`;
            if (metaEl) metaEl.textContent = `${resp.provider} / ${resp.model}`;
        } else {
            if (resultEl) resultEl.textContent = resp.output;
            if (metaEl) metaEl.textContent = `${resp.provider} / ${resp.model} · ~${resp.tokens_estimated || '?'} tokens`;
        }
    } catch (err) {
        if (resultEl) resultEl.textContent = `Error: ${err.message}`;
    } finally {
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Run'; }
    }
}


// =============================================================================
// v0.5.29: Studio AI Flows
// =============================================================================

/** Track AI Hub configured state for flow button enable/disable. */
let _aiHubConfigured = false;

/** Selected context for AI flows (set when user clicks a model/route/query row). */
const _aiFlowContext = { model: null, route: null, query: null, migration: null, diagnostic: null };

/** Check AI Hub status and toggle flow buttons accordingly.
 *
 * Enables only when _effectiveOverall === 'ready', which after backend Fix 2
 * requires: chat_model set + chat_provider configured + at least one provider
 * reachable.  This keeps the gate consistent with the sidebar/overview 'ready'
 * indicator and the routing table's agents-route status. */
async function initAiFlowButtons() {
    try {
        const [status, provData] = await Promise.all([
            jsonGet('/studio/ai-hub/status').catch(() => null),
            jsonGet('/studio/ai-hub/providers').catch(() => null),
        ]);
        const effective = _effectiveOverall(status, provData?.providers ?? null);
        _aiHubConfigured = effective === 'ready';
    } catch { _aiHubConfigured = false; }
    _syncFlowButtonStates();
}

function _syncFlowButtonStates() {
    document.querySelectorAll('.btn-ai-flow').forEach(btn => {
        btn.disabled = !_aiHubConfigured;
        if (!_aiHubConfigured) {
            btn.title = 'Configure AI in AI Hub';
        }
    });
}

// Recompute the flow-button gate from already-cached state (no extra fetch).
// Applies the same _effectiveOverall === 'ready' predicate as initAiFlowButtons
// so that mutations (save, clear, test) immediately reflect the new provider
// set without waiting for a full re-init.
function _refreshFlowButtonGate() {
    const providers = state.aiHub?.providers?.providers ?? null;
    const effective = _effectiveOverall(state.aiHub?.status ?? null, providers);
    _aiHubConfigured = effective === 'ready';
    _syncFlowButtonStates();
}

/** Attach dropdown toggles and item handlers to AI flow buttons in the current DOM. */
function initAiFlowDropdowns() {
    const dropdowns = document.querySelectorAll('.ai-flow-dropdown');
    dropdowns.forEach(dd => {
        const btn = dd.querySelector('.btn-ai-flow');
        const menu = dd.querySelector('.ai-flow-dropdown-menu');
        if (!btn || !menu) return;

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (btn.disabled) {
                if (!_aiHubConfigured) {
                    showToast('Configure AI in AI Hub first', 'error');
                    navigateTo('ai-hub');
                }
                return;
            }
            // Toggle menu
            const visible = menu.style.display !== 'none';
            _closeAllAiMenus();
            if (!visible) menu.style.display = 'block';
        });

        menu.querySelectorAll('.ai-flow-dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.getAttribute('data-action');
                menu.style.display = 'none';
                _dispatchAiFlow(dd.id, action);
            });
        });
    });
    // Close menus on outside click
    document.addEventListener('click', _closeAllAiMenus);
}

function _closeAllAiMenus() {
    document.querySelectorAll('.ai-flow-dropdown-menu').forEach(m => m.style.display = 'none');
}

/** Determine flow kind + payload from dropdown id and call openAiFlowPanel. */
function _dispatchAiFlow(dropdownId, actionKey) {
    let kind, payload;
    if (dropdownId.startsWith('models')) {
        kind = 'model';
        payload = { model_name: _aiFlowContext.model || '', action_key: actionKey };
    } else if (dropdownId.startsWith('routes')) {
        kind = 'route';
        const r = _aiFlowContext.route || {};
        payload = { path: r.path || '', method: r.method || 'GET', action_key: actionKey };
    } else if (dropdownId.startsWith('queries')) {
        kind = 'query';
        payload = { sql: _aiFlowContext.query || '', action_key: actionKey, include_explain: true };
    } else if (dropdownId.startsWith('migrations')) {
        kind = 'migration';
        const m = _aiFlowContext.migration || {};
        payload = { app: m.app || '', name: m.name || '', action_key: actionKey };
    } else if (dropdownId.startsWith('diagnostics')) {
        kind = 'diagnostic';
        payload = { issue_payload: _aiFlowContext.diagnostic || null, action_key: actionKey };
    } else {
        showToast('Unknown AI flow kind', 'error');
        return;
    }
    openAiFlowPanel({ kind, actionKey, payload });
}

/**
 * Open the AI Flow side panel, call the backend, and render the result.
 * @param {{kind: string, actionKey: string, payload: object}} opts
 */
async function openAiFlowPanel({ kind, actionKey, payload }) {
    const panel = document.getElementById('ai-flow-panel');
    if (!panel) return;
    panel.style.display = 'flex';

    // Reset UI
    const resultEl = document.getElementById('ai-flow-result');
    const errorEl = document.getElementById('ai-flow-error');
    const titleEl = document.getElementById('ai-flow-panel-title');
    const badgeEl = document.getElementById('ai-flow-badge');
    const provEl = document.getElementById('ai-flow-provider');
    const modEl = document.getElementById('ai-flow-model');
    const whatDoesEl = document.getElementById('ai-flow-what-it-does');
    const whatCannotEl = document.getElementById('ai-flow-what-it-cannot');
    const sysPre = document.getElementById('ai-flow-system-prompt');
    const usrPre = document.getElementById('ai-flow-user-prompt');
    const rawPre = document.getElementById('ai-flow-raw-json');
    const nextEl = document.getElementById('ai-flow-suggested-next');

    if (titleEl) titleEl.textContent = actionKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    if (resultEl) resultEl.textContent = 'Loading…';
    if (errorEl) errorEl.style.display = 'none';
    if (badgeEl) { badgeEl.textContent = '…'; badgeEl.className = 'ai-flow-badge'; }

    // Show first tab
    _setAiFlowTab('result');

    try {
        const resp = await jsonPost(`/studio/ai/flows/${kind}`, payload);
        if (!resp.ok) {
            if (errorEl) {
                errorEl.style.display = 'block';
                errorEl.textContent = resp.error || 'AI Hub not configured';
                if (resp.error_code === 'AI_HUB_NOT_CONFIGURED') {
                    errorEl.innerHTML = resp.error + ' <a href="#" onclick="navigateTo(\'ai-hub\');return false;">Open AI Hub</a>';
                }
            }
            if (resultEl) resultEl.textContent = '';
            return;
        }

        // Populate panel
        if (titleEl) titleEl.textContent = resp.action_key ? resp.action_key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : kind;
        if (badgeEl) {
            badgeEl.textContent = resp.risk;
            badgeEl.className = 'ai-flow-badge' + (resp.risk === 'medium' ? ' ai-flow-badge-medium' : resp.risk === 'high' ? ' ai-flow-badge-high' : '');
        }
        if (provEl) provEl.textContent = resp.provider ? 'Provider: ' + resp.provider : '';
        if (modEl) modEl.textContent = resp.model ? 'Model: ' + resp.model : '';
        if (whatDoesEl) whatDoesEl.textContent = resp.what_it_does ? '✓ ' + resp.what_it_does : '';
        if (whatCannotEl) whatCannotEl.textContent = resp.what_it_cannot_do ? '✗ ' + resp.what_it_cannot_do : '';
        if (resultEl) resultEl.textContent = resp.result_markdown || '(No result)';
        if (sysPre) sysPre.textContent = resp.system_prompt || '';
        if (usrPre) usrPre.textContent = resp.user_prompt || '';
        if (rawPre) rawPre.textContent = JSON.stringify(resp, null, 2);

        // Suggested next actions
        if (nextEl && resp.suggested_next && resp.suggested_next.length) {
            nextEl.innerHTML = '<strong>Suggested next:</strong> ' +
                resp.suggested_next.map(s => '<a href="#" onclick="_runSuggestedFlow(\'' + s + '\');return false;">' + s.replace(/_/g, ' ') + '</a>').join(' · ');
        } else if (nextEl) {
            nextEl.innerHTML = '';
        }

        // Wire copy buttons
        _wireAiFlowCopy('ai-flow-copy-result', resp.result_markdown || '');
        _wireAiFlowCopy('ai-flow-copy-prompts', 'SYSTEM:\n' + (resp.system_prompt || '') + '\n\nUSER:\n' + (resp.user_prompt || ''));
        _wireAiFlowCopy('ai-flow-copy-json', JSON.stringify(resp, null, 2));
        _wireAiFlowCopy('ai-flow-copy-cli', _buildCliCommand(kind, payload));

        // Wire Run AI button (v0.5.30)
        _wireAiFlowRunButton(kind, payload);
    } catch (err) {
        showToast('AI Flow error: ' + err.message, 'error');
        if (resultEl) resultEl.textContent = '';
        if (errorEl) { errorEl.style.display = 'block'; errorEl.textContent = err.message; }
    }
}

function _wireAiFlowCopy(btnId, text) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    const handler = () => {
        navigator.clipboard.writeText(text).then(
            () => showToast('Copied to clipboard', 'success'),
            () => showToast('Copy failed', 'error')
        );
    };
    btn.onclick = handler;
}

/**
 * Wire the "Run AI" button to execute a flow via the connector (v0.5.30).
 */
function _wireAiFlowRunButton(kind, payload) {
    const btn = document.getElementById('ai-flow-run-ai');
    if (!btn) return;
    btn.onclick = () => _runAiFlow(kind, payload);
}

/**
 * Execute an AI flow through a connector and display the result (v0.5.30).
 * Posts to /studio/ai/flows/run and renders the execution response.
 */
async function _runAiFlow(kind, payload) {
    const btn = document.getElementById('ai-flow-run-ai');
    const execResult = document.getElementById('ai-flow-execution-result');
    const execText = document.getElementById('ai-flow-execution-text');
    const execProvider = document.getElementById('ai-flow-exec-provider');
    const execModel = document.getElementById('ai-flow-exec-model');
    const execElapsed = document.getElementById('ai-flow-exec-elapsed');
    const execTokens = document.getElementById('ai-flow-exec-tokens');

    if (btn) { btn.disabled = true; btn.textContent = '\u231B Running\u2026'; }
    if (execResult) execResult.style.display = 'none';

    // Build context from payload
    const context = {};
    if (kind === 'model') context.model_name = payload.model_name || '';
    else if (kind === 'route') { context.path = payload.path || ''; context.method = payload.method || 'GET'; }
    else if (kind === 'query') context.sql = payload.sql || '';
    else if (kind === 'migration') { context.app = payload.app || ''; context.name = payload.name || ''; }
    else if (kind === 'diagnostic') { context.issue_id = payload.issue_id || ''; context.issue_payload = payload.issue_payload || null; }

    try {
        const resp = await jsonPost('/studio/ai/flows/run', {
            flow_type: kind,
            action_key: payload.action_key,
            context: context,
            provider_override: payload.provider_override || null,
            model_override: payload.model_override || null,
        });

        if (btn) { btn.disabled = false; btn.innerHTML = '&#9889; Run AI'; }

        if (!resp.ok) {
            showToast('AI execution failed: ' + (resp.error || 'Unknown error'), 'error');
            if (execText) execText.textContent = resp.error || 'Execution failed';
            if (execResult) execResult.style.display = 'block';
            return;
        }

        const exec = resp.execution || {};
        if (execText) execText.textContent = exec.response || '(No response)';
        if (execProvider) execProvider.textContent = exec.provider ? 'Provider: ' + exec.provider : '';
        if (execModel) execModel.textContent = exec.model ? 'Model: ' + exec.model : '';
        if (execElapsed) execElapsed.textContent = exec.elapsed_ms ? Math.round(exec.elapsed_ms) + 'ms' : '';
        if (execTokens && exec.tokens && exec.tokens.total) execTokens.textContent = exec.tokens.total + ' tokens';
        if (execResult) execResult.style.display = 'block';

        showToast('AI execution complete', 'success');
    } catch (err) {
        if (btn) { btn.disabled = false; btn.innerHTML = '&#9889; Run AI'; }
        showToast('AI execution error: ' + err.message, 'error');
    }
}

function _buildCliCommand(kind, payload) {
    const parts = ['aksara', 'ai', 'flows', kind];
    if (kind === 'model' && payload.model_name) {
        parts.push(payload.model_name);
    } else if (kind === 'route' && payload.path) {
        parts.push((payload.method || 'GET').toUpperCase() + ':' + payload.path);
    } else if (kind === 'query' && payload.sql) {
        parts.push('--sql', '"' + payload.sql.replace(/"/g, '\\"') + '"');
    } else if (kind === 'migration') {
        if (payload.app) parts.push('--app', payload.app);
        if (payload.name) parts.push('--name', payload.name);
    }
    parts.push('--action', payload.action_key);
    return parts.join(' ');
}

function _runSuggestedFlow(actionKey) {
    // Re-dispatch with same context but new action
    const panel = document.getElementById('ai-flow-panel');
    if (!panel) return;
    // Infer kind from action key
    const action = { explain_model: 'model', suggest_constraints: 'model', refactor_suggestions: 'model',
                     review_endpoint: 'route', harden_permissions: 'route', generate_examples: 'route',
                     explain_plan: 'query', suggest_indexes: 'query', rewrite_suggestions: 'query',
                     explain_migration: 'migration', safe_rollout_plan: 'migration',
                     diagnostic_prioritize: 'diagnostic' };
    const kind = action[actionKey];
    if (!kind) return;
    // Build a minimal payload
    let payload = { action_key: actionKey };
    if (kind === 'model') payload.model_name = _aiFlowContext.model || '';
    else if (kind === 'route') { const r = _aiFlowContext.route || {}; payload.path = r.path || ''; payload.method = r.method || 'GET'; }
    else if (kind === 'query') { payload.sql = _aiFlowContext.query || ''; payload.include_explain = true; }
    else if (kind === 'migration') { const m = _aiFlowContext.migration || {}; payload.app = m.app || ''; payload.name = m.name || ''; }
    else if (kind === 'diagnostic') { payload.issue_payload = _aiFlowContext.diagnostic || null; }
    openAiFlowPanel({ kind, actionKey, payload });
}

function _setAiFlowTab(tabKey) {
    document.querySelectorAll('.ai-flow-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-ai-flow-tab') === tabKey));
    document.querySelectorAll('.ai-flow-tab-panel').forEach(p => p.style.display = p.getAttribute('data-ai-flow-panel') === tabKey ? 'block' : 'none');
}

function _initAiFlowPanelControls() {
    // Close button
    const closeBtn = document.getElementById('ai-flow-panel-close');
    if (closeBtn) closeBtn.addEventListener('click', () => {
        const panel = document.getElementById('ai-flow-panel');
        if (panel) panel.style.display = 'none';
    });
    // Tab switching
    document.querySelectorAll('.ai-flow-tab').forEach(tab => {
        tab.addEventListener('click', () => _setAiFlowTab(tab.getAttribute('data-ai-flow-tab')));
    });
}

/** Keyboard shortcuts for AI flows. */
function _initAiFlowKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Shift+A → open AI Hub
        if (e.shiftKey && !e.ctrlKey && !e.metaKey && e.key === 'A') {
            if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) return;
            e.preventDefault();
            navigateTo('ai-hub');
        }
        // Escape → close AI flow panel
        if (e.key === 'Escape') {
            const panel = document.getElementById('ai-flow-panel');
            if (panel && panel.style.display !== 'none') {
                panel.style.display = 'none';
                e.preventDefault();
            }
        }
    });
}

/**
 * Hook into existing row-click handlers to track selection context.
 * Called after each section render.
 */
function _hookAiFlowRowSelection() {
    // Models: track selected model name
    document.querySelectorAll('#models-list .model-row, #models-list .list-item, #models-list tr[data-model]').forEach(row => {
        row.addEventListener('click', () => {
            const name = row.getAttribute('data-model') || row.querySelector('.model-name')?.textContent || row.querySelector('td')?.textContent || '';
            _aiFlowContext.model = name.trim();
            const btn = document.getElementById('models-ai-btn');
            if (btn) btn.title = _aiHubConfigured ? 'AI actions for ' + name.trim() : 'Configure AI in AI Hub';
        });
    });
    // Routes: track selected route. Two click targets:
    //  (a) the row → defaults to the row's primary (first) method
    //  (b) a method badge → targets that exact (path, method)
    // For multi-method routes, badges let users review POST/DELETE/etc.
    // independently from GET.
    const _markBadgeSelected = (badge) => {
        document.querySelectorAll('.routes-table .method-badge.selected').forEach(b => b.classList.remove('selected'));
        if (badge) badge.classList.add('selected');
    };
    document.querySelectorAll('.routes-table tbody tr[data-path]').forEach(row => {
        row.addEventListener('click', () => {
            _aiFlowContext.route = { path: row.getAttribute('data-path') || '', method: row.getAttribute('data-method') || 'GET' };
            const firstBadge = row.querySelector('.method-badge[data-method]');
            _markBadgeSelected(firstBadge);
        });
    });
    document.querySelectorAll('.routes-table tbody tr[data-path] .method-badge[data-method]').forEach(badge => {
        badge.addEventListener('click', (e) => {
            e.stopPropagation();
            const row = badge.closest('tr');
            if (!row) return;
            _aiFlowContext.route = {
                path: row.getAttribute('data-path') || '',
                method: badge.getAttribute('data-method') || 'GET',
            };
            _markBadgeSelected(badge);
        });
    });
}


// =============================================================================
// v0.5.31: Interactive AI Console
// =============================================================================

const _aiConsoleState = {
    history: [],
    historyIdx: -1,
    sending: false,
    suggestTimer: null,
    suggestIdx: -1,
};

function renderAiConsole() {
    // Hook example buttons
    document.querySelectorAll('.ai-console-example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const cmd = btn.getAttribute('data-cmd');
            const input = document.getElementById('ai-console-input');
            if (input && cmd) {
                input.value = cmd;
                _sendConsoleMessage();
            }
        });
    });
    // Hook send
    const sendBtn = document.getElementById('ai-console-send');
    if (sendBtn) sendBtn.addEventListener('click', _sendConsoleMessage);
    const input = document.getElementById('ai-console-input');
    if (input) {
        input.addEventListener('keydown', _handleConsoleInputKey);
        input.addEventListener('input', _handleConsoleInputChange);
        input.focus();

        // v0.5.38: Prefill prompt from AI Home navigation
        if (_aiHomePrefillPrompt) {
            input.value = _aiHomePrefillPrompt;
            _aiHomePrefillPrompt = null;
            setTimeout(() => _sendConsoleMessage(), 100);
        }
    }
}

function _handleConsoleInputKey(e) {
    const suggestEl = document.getElementById('ai-console-suggestions');
    const items = suggestEl ? suggestEl.querySelectorAll('.ai-console-suggestion-item') : [];

    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (items.length > 0 && _aiConsoleState.suggestIdx >= 0) {
            const active = items[_aiConsoleState.suggestIdx];
            if (active) {
                e.target.value = active.textContent;
                _hideConsoleSuggestions();
            }
        } else {
            _sendConsoleMessage();
        }
        return;
    }
    if (e.key === 'ArrowUp') {
        if (items.length > 0) {
            e.preventDefault();
            _aiConsoleState.suggestIdx = Math.max(0, _aiConsoleState.suggestIdx - 1);
            _highlightConsoleSuggestion(items);
        } else if (_aiConsoleState.history.length > 0) {
            e.preventDefault();
            if (_aiConsoleState.historyIdx < 0) _aiConsoleState.historyIdx = _aiConsoleState.history.length;
            _aiConsoleState.historyIdx = Math.max(0, _aiConsoleState.historyIdx - 1);
            e.target.value = _aiConsoleState.history[_aiConsoleState.historyIdx] || '';
        }
        return;
    }
    if (e.key === 'ArrowDown') {
        if (items.length > 0) {
            e.preventDefault();
            _aiConsoleState.suggestIdx = Math.min(items.length - 1, _aiConsoleState.suggestIdx + 1);
            _highlightConsoleSuggestion(items);
        } else if (_aiConsoleState.historyIdx >= 0) {
            e.preventDefault();
            _aiConsoleState.historyIdx = Math.min(_aiConsoleState.history.length - 1, _aiConsoleState.historyIdx + 1);
            e.target.value = _aiConsoleState.history[_aiConsoleState.historyIdx] || '';
        }
        return;
    }
    if (e.key === 'Escape') {
        _hideConsoleSuggestions();
    }
}

function _handleConsoleInputChange(e) {
    const val = e.target.value.trim();
    clearTimeout(_aiConsoleState.suggestTimer);
    if (val.length < 2) {
        _hideConsoleSuggestions();
        return;
    }
    _aiConsoleState.suggestTimer = setTimeout(() => _fetchConsoleSuggestions(val), 200);
}

async function _fetchConsoleSuggestions(prefix) {
    try {
        const resp = await fetch(`/studio/ai/console/suggest?q=${encodeURIComponent(prefix)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        _showConsoleSuggestions(data.suggestions || []);
    } catch (_) {
        // ignore
    }
}

function _showConsoleSuggestions(items) {
    const el = document.getElementById('ai-console-suggestions');
    if (!el || items.length === 0) {
        _hideConsoleSuggestions();
        return;
    }
    _aiConsoleState.suggestIdx = -1;
    el.innerHTML = items.map(s => `<div class="ai-console-suggestion-item">${_esc(s)}</div>`).join('');
    el.style.display = '';
    el.querySelectorAll('.ai-console-suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            const input = document.getElementById('ai-console-input');
            if (input) input.value = item.textContent;
            _hideConsoleSuggestions();
            input && input.focus();
        });
    });
}

function _hideConsoleSuggestions() {
    const el = document.getElementById('ai-console-suggestions');
    if (el) { el.style.display = 'none'; el.innerHTML = ''; }
    _aiConsoleState.suggestIdx = -1;
}

function _highlightConsoleSuggestion(items) {
    items.forEach((it, i) => it.classList.toggle('active', i === _aiConsoleState.suggestIdx));
}

async function _sendConsoleMessage() {
    const input = document.getElementById('ai-console-input');
    if (!input) return;
    const msg = input.value.trim();
    if (!msg || _aiConsoleState.sending) return;

    _aiConsoleState.sending = true;
    _hideConsoleSuggestions();

    // Save to history
    _aiConsoleState.history.push(msg);
    _aiConsoleState.historyIdx = -1;

    // Clear welcome
    const output = document.getElementById('ai-console-output');
    const welcome = output ? output.querySelector('.ai-console-welcome') : null;
    if (welcome) welcome.remove();

    // Append user message
    _appendConsoleMsg('user', msg);
    input.value = '';

    // v0.5.38: Show plan preview for investigation-type prompts
    const investigationPattern = /\b(investigate|analyze|architecture|performance|debug|review|diagnose)\b/i;
    const planPreview = document.getElementById('ai-console-plan-preview');
    if (planPreview && investigationPattern.test(msg)) {
        planPreview.style.display = '';
        const steps = planPreview.querySelectorAll('.ai-console-plan-step');
        let stepIdx = 0;
        const stepTimer = setInterval(() => {
            if (stepIdx < steps.length) {
                steps[stepIdx].classList.add('active');
                stepIdx++;
            } else {
                clearInterval(stepTimer);
            }
        }, 400);
        // Store timer so we can clear on response
        planPreview._stepTimer = stepTimer;
    }

    // Show loading
    const loadingId = _appendConsoleLoading();

    // Send
    try {
        const resp = await fetch('/studio/ai/console', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        });
        const ct = resp.headers.get('content-type') || '';
        if (!ct.includes('application/json')) {
            throw new Error('Server returned non-JSON response (status ' + resp.status + ') \u2014 check server logs');
        }
        const data = await resp.json();
        _removeConsoleLoading(loadingId);
        _renderConsoleResponse(data);
    } catch (err) {
        _removeConsoleLoading(loadingId);
        _renderConsoleResponse({
            ok: false,
            error: 'Network error: ' + err.message,
            error_code: 'NETWORK_ERROR',
        });
    } finally {
        _aiConsoleState.sending = false;
        // v0.5.38: Hide plan preview
        if (planPreview) {
            if (planPreview._stepTimer) clearInterval(planPreview._stepTimer);
            planPreview.style.display = 'none';
            planPreview.querySelectorAll('.ai-console-plan-step.active').forEach(s => s.classList.remove('active'));
        }
    }
}

function _appendConsoleMsg(role, text, meta) {
    const output = document.getElementById('ai-console-output');
    if (!output) return;
    const div = document.createElement('div');
    div.className = `ai-console-msg ${role}`;
    const label = role === 'user' ? 'You' : 'Aksara AI';
    let html = `<div class="ai-console-msg-label">${label}</div>`;
    html += `<div class="ai-console-msg-body">${role === 'assistant' ? _renderMarkdown(text) : _esc(text)}</div>`;
    if (meta) {
        html += `<div class="ai-console-msg-meta">${meta}</div>`;
    }
    div.innerHTML = html;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
}

function _appendConsoleLoading() {
    const output = document.getElementById('ai-console-output');
    if (!output) return '';
    const id = 'ai-console-loading-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'ai-console-loading';
    div.innerHTML = '<div class="ai-console-loading-dots"><span></span><span></span><span></span></div> Thinking...';
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
    return id;
}

function _removeConsoleLoading(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
}

function _renderConsoleResponse(data) {
    const output = document.getElementById('ai-console-output');
    if (!output) return;

    if (!data.ok) {
        const div = document.createElement('div');
        div.className = 'ai-console-msg assistant ai-console-msg-error';
        div.innerHTML = `<div class="ai-console-msg-label">Aksara AI</div>`
            + `<div class="ai-console-msg-body">${_esc(data.error || 'Unknown error')}</div>`;
        output.appendChild(div);
        output.scrollTop = output.scrollHeight;
        return;
    }

    // v0.5.39: Investigation session response
    if (data.investigation && data.execution && data.execution.investigation_session) {
        _renderInvestigationResult(data, output);
        return;
    }

    // Main response text
    const responseText = (data.execution && data.execution.response) || 'Done.';
    const metaParts = [];
    if (data.flow_type) metaParts.push(data.flow_type + '/' + data.action_key);
    if (data.confidence) metaParts.push('confidence: ' + (data.confidence * 100).toFixed(0) + '%');
    if (data.elapsed_ms) metaParts.push(data.elapsed_ms.toFixed(0) + 'ms');
    if (data.execution && data.execution.provider) metaParts.push(data.execution.provider);

    _appendConsoleMsg('assistant', responseText, metaParts.join(' &bull; '));

    // Suggested next actions
    if (data.suggestions && data.suggestions.length > 0) {
        const row = document.createElement('div');
        row.className = 'ai-console-suggestions-row';
        data.suggestions.forEach(key => {
            const chip = document.createElement('button');
            chip.className = 'ai-console-suggestion-chip';
            chip.textContent = key.replace(/_/g, ' ');
            chip.addEventListener('click', () => {
                const input = document.getElementById('ai-console-input');
                if (input) {
                    input.value = key.replace(/_/g, ' ');
                    _sendConsoleMessage();
                }
            });
            row.appendChild(chip);
        });
        output.appendChild(row);
        output.scrollTop = output.scrollHeight;
    }
}

// v0.5.39: Render investigation session result in console
function _renderInvestigationResult(data, output) {
    const session = data.execution.investigation_session;
    const div = document.createElement('div');
    div.className = 'ai-console-msg assistant ai-console-investigation';

    let html = '<div class="ai-console-msg-label">Aksara AI &mdash; Investigation</div>';

    // Session header
    html += '<div class="ai-investigation-header">';
    html += '<span class="ai-investigation-status ai-investigation-status-' + _esc(session.status) + '">'
        + _esc(session.status) + '</span>';
    html += '<span class="ai-investigation-id">Session: ' + _esc(session.id) + '</span>';
    html += '</div>';

    // Plan steps
    if (session.plan && session.plan.steps) {
        html += '<div class="ai-investigation-plan">';
        html += '<div class="ai-investigation-plan-title">Plan (' + _esc(session.plan.strategy) + ')</div>';
        session.plan.steps.forEach(function(step) {
            const icon = step.status === 'done' ? '&#x2713;' : step.status === 'failed' ? '&#x2717;' : step.status === 'skipped' ? '&#x2014;' : '&#x25CB;';
            html += '<div class="ai-investigation-step ai-investigation-step-' + _esc(step.status) + '">';
            html += '<span class="ai-investigation-step-icon">' + icon + '</span>';
            html += '<span class="ai-investigation-step-label">' + _esc(step.label) + '</span>';
            html += '<span class="ai-investigation-step-status">' + _esc(step.status) + '</span>';
            if (step.error) {
                html += '<div class="ai-investigation-step-error">' + _esc(step.error) + '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    }

    // Findings
    if (session.findings && session.findings.length > 0) {
        html += '<div class="ai-investigation-findings">';
        html += '<div class="ai-investigation-findings-title">Key Findings</div>';
        html += '<ul class="ai-investigation-findings-list">';
        session.findings.forEach(function(f) {
            html += '<li>' + _esc(f) + '</li>';
        });
        html += '</ul></div>';
    }

    // Meta
    const metaParts = [];
    if (data.elapsed_ms) metaParts.push(data.elapsed_ms.toFixed(0) + 'ms');
    metaParts.push('investigation');
    if (metaParts.length) {
        html += '<div class="ai-console-msg-meta">' + metaParts.join(' &bull; ') + '</div>';
    }

    div.innerHTML = html;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
}

// v0.5.43: Lightweight markdown → HTML for AI Console assistant messages.
// No CDN. XSS-safe: _esc() guards all text content before markup is applied.
function _renderMarkdown(text) {
    if (!text) return '';
    // 1. Extract fenced code blocks (protected from inline processing)
    const codeBlocks = [];
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, body) => {
        const i = codeBlocks.length;
        const cls = lang ? ` class="language-${lang.replace(/[^a-zA-Z0-9]/g, '').slice(0, 20)}"` : '';
        codeBlocks.push(`<pre class="md-pre"><code${cls}>${_esc(body.trimEnd())}</code></pre>`);
        return `\uFFF0B${i}\uFFF1`;
    });
    // 2. Line-by-line processing
    const out = [];
    const lines = text.split('\n');
    let i = 0;
    while (i < lines.length) {
        const ln = lines[i];
        // Code block placeholder — pass through as-is
        if (/^\uFFF0B\d+\uFFF1$/.test(ln.trim())) { out.push(ln.trim()); i++; continue; }
        // Heading
        const hm = ln.match(/^(#{1,4})\s+(.*)/);
        if (hm) {
            out.push(`<h${hm[1].length} class="md-h">${_inlineMd(hm[2])}</h${hm[1].length}>`);
            i++; continue;
        }
        // Unordered list — collect consecutive items
        if (/^[-*+] /.test(ln)) {
            const li = [];
            while (i < lines.length && /^[-*+] /.test(lines[i]))
                li.push(`<li>${_inlineMd(lines[i++].replace(/^[-*+] /, ''))}</li>`);
            out.push(`<ul class="md-ul">${li.join('')}</ul>`);
            continue;
        }
        // Ordered list — collect consecutive items
        if (/^\d+\. /.test(ln)) {
            const li = [];
            while (i < lines.length && /^\d+\. /.test(lines[i]))
                li.push(`<li>${_inlineMd(lines[i++].replace(/^\d+\. /, ''))}</li>`);
            out.push(`<ol class="md-ol">${li.join('')}</ol>`);
            continue;
        }
        // Table — collect consecutive pipe-delimited lines
        if (ln.startsWith('|')) {
            const tableLines = [];
            while (i < lines.length && lines[i].startsWith('|')) {
                tableLines.push(lines[i]);
                i++;
            }
            // row 0 = header, row 1 = separator (skip), rows 2+ = body
            const headerCells = tableLines[0].split('|').slice(1, -1)
                .map(c => `<th>${_inlineMd(c.trim())}</th>`).join('');
            let bodyRows = '';
            for (let r = 2; r < tableLines.length; r++) {
                const cells = tableLines[r].split('|').slice(1, -1)
                    .map(c => `<td>${_inlineMd(c.trim())}</td>`).join('');
                bodyRows += `<tr>${cells}</tr>`;
            }
            out.push(`<table class="md-table"><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table>`);
            continue;
        }
        // Blank line → paragraph separator
        if (!ln.trim()) { out.push(''); i++; continue; }
        // Horizontal rule
        if (/^[-*_]{3,}$/.test(ln.trim())) { out.push('<hr>'); i++; continue; }
        // Normal text line
        out.push(_inlineMd(ln));
        i++;
    }
    // 3. Join lines and normalise whitespace/breaks
    let html = out.join('\n');
    html = html.replace(/\n\n+/g, '</p><p class="md-p">');
    html = html.replace(/\n/g, '<br>');
    // Suppress <br> immediately before/after block elements
    html = html.replace(/<br>(<(?:h[1-4]|ul|ol|hr|pre))/g, '$1');
    html = html.replace(/(<\/(?:h[1-4]|ul|ol|pre)>)<br>/g, '$1');
    // 4. Restore fenced code blocks
    codeBlocks.forEach((b, i) => { html = html.replace(`\uFFF0B${i}\uFFF1`, b); });
    return html;
}

// v0.5.43: Inline markdown → HTML helper used by _renderMarkdown.
function _inlineMd(text) {
    // Extract inline code before HTML-escaping
    const codes = [];
    text = text.replace(/`([^`\n]+)`/g, (_, c) => {
        const i = codes.length;
        codes.push(`<code class="md-code">${_esc(c)}</code>`);
        return `\uFFF0I${i}\uFFF1`;
    });
    // HTML-escape remaining text (* _ # are not HTML-special — safe to process after)
    text = _esc(text);
    // Bold + italic (order: *** before ** before *)
    text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__(.+?)__/g, '<strong>$1</strong>');
    text = text.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    text = text.replace(/_([^_\n]+)_/g, '<em>$1</em>');
    // Restore inline codes
    codes.forEach((c, i) => { text = text.replace(`\uFFF0I${i}\uFFF1`, c); });
    return text;
}

const _esc = escapeHtml;  // v0.5.45: Alias — use escapeHtml() for new code

// =============================================================================
// v0.5.32: AI Graph Explorer
// =============================================================================

let _aiGraphData = null;

async function renderAiGraph() {
    // Wire toolbar
    const rebuildBtn = document.getElementById('ai-graph-rebuild');
    if (rebuildBtn) rebuildBtn.addEventListener('click', () => _fetchAiGraph(true));
    const toConsoleBtn = document.getElementById('ai-graph-to-console');
    if (toConsoleBtn) toConsoleBtn.addEventListener('click', () => navigateTo('ai-console'));

    // Wire tabs
    document.querySelectorAll('.ai-graph-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.ai-graph-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            _renderAiGraphTab(tab.getAttribute('data-graph-tab'));
        });
    });

    await _fetchAiGraph(false);
}

async function _fetchAiGraph(rebuild) {
    const panel = document.getElementById('ai-graph-panel');
    if (panel) panel.innerHTML = '<div class="ai-graph-loading">Loading graph\u2026</div>';

    try {
        const url = '/studio/ai/project-graph' + (rebuild ? '?rebuild=true' : '');
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Failed to fetch graph');
        _aiGraphData = await resp.json();
        _renderAiGraphCounts();
        _renderAiGraphSummaryCard();
        // Default tab
        const active = document.querySelector('.ai-graph-tab.active');
        _renderAiGraphTab(active ? active.getAttribute('data-graph-tab') : 'models');
    } catch (e) {
        if (panel) panel.innerHTML = '<div class="ai-graph-empty">No project graph available yet. Run an investigation or rebuild the graph after your app imports cleanly. Error: ' + _esc(e.message) + '</div>';
    }
}

function _renderAiGraphCounts() {
    const el = document.getElementById('ai-graph-counts');
    if (!el || !_aiGraphData) return;
    const m = _aiGraphData.metadata || {};
    const items = [
        { label: 'Models', count: m.model_count || 0, icon: '\u25A3' },
        { label: 'Routes', count: m.route_count || 0, icon: '\u21C4' },
        { label: 'Queries', count: m.query_count || 0, icon: '\u2318' },
        { label: 'Migrations', count: m.migration_count || 0, icon: '\u21BB' },
        { label: 'Diagnostics', count: m.diagnostic_count || 0, icon: '\u26A0' },
        { label: 'Gaps', count: m.gap_count || 0, icon: '\u25CB' },
        { label: 'Events', count: m.event_count || 0, icon: '\u23F1' },
    ];
    el.innerHTML = items.map(i =>
        '<div class="ai-graph-count-card">' +
        '<span class="ai-graph-count-icon">' + i.icon + '</span>' +
        '<span class="ai-graph-count-num">' + i.count + '</span>' +
        '<span class="ai-graph-count-label">' + i.label + '</span>' +
        '</div>'
    ).join('');

    const gen = document.getElementById('ai-graph-generated');
    if (gen && m.generated_at) gen.textContent = 'Generated: ' + new Date(m.generated_at).toLocaleTimeString();
}

// v0.5.38: Populate graph summary card
function _renderAiGraphSummaryCard() {
    const card = document.getElementById('ai-graph-summary-card');
    const grid = document.getElementById('ai-graph-summary-grid');
    if (!card || !grid || !_aiGraphData) return;
    const m = _aiGraphData.metadata || {};
    const items = [
        { label: 'Models', value: m.model_count || 0 },
        { label: 'Routes', value: m.route_count || 0 },
        { label: 'Queries', value: m.query_count || 0 },
        { label: 'Migrations', value: m.migration_count || 0 },
        { label: 'Diagnostics', value: m.diagnostic_count || 0 },
    ];
    grid.innerHTML = items.map(i =>
        '<div class="ai-graph-summary-item"><span class="ai-graph-summary-value">' + i.value + '</span>' +
        '<span class="ai-graph-summary-label">' + i.label + '</span></div>'
    ).join('');
    card.style.display = '';
}

function _renderAiGraphTab(tab) {
    const panel = document.getElementById('ai-graph-panel');
    if (!panel || !_aiGraphData) return;

    switch (tab) {
        case 'models': _renderGraphModels(panel); break;
        case 'routes': _renderGraphRoutes(panel); break;
        case 'queries': _renderGraphQueries(panel); break;
        case 'diagnostics': _renderGraphDiagnostics(panel); break;
        case 'migrations': _renderGraphMigrations(panel); break;
        case 'events': _renderGraphEvents(panel); break;
        case 'relationships': _renderGraphRelationships(panel); break;
        default: panel.innerHTML = '<div class="ai-graph-empty">Select a tab</div>';
    }
}

function _renderGraphModels(panel) {
    const models = _aiGraphData.models || [];
    if (!models.length) { panel.innerHTML = '<div class="ai-graph-empty">No models in graph. Import your models and rebuild the graph.</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Model</th><th>Table</th><th>Fields</th><th>Relations</th><th>Indexes</th></tr></thead><tbody>';
    models.forEach(m => {
        html += '<tr><td><strong>' + _esc(m.name) + '</strong></td><td>' + _esc(m.table) + '</td>'
            + '<td>' + (m.fields || []).length + '</td>'
            + '<td>' + (m.relations || []).map(r => _esc(r)).join(', ') + '</td>'
            + '<td>' + (m.indexes || []).map(i => _esc(i)).join(', ') + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphRoutes(panel) {
    const routes = _aiGraphData.routes || [];
    if (!routes.length) { panel.innerHTML = '<div class="ai-graph-empty">No routes in graph</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Method</th><th>Path</th><th>Name</th><th>Models</th></tr></thead><tbody>';
    routes.forEach(r => {
        html += '<tr><td><span class="method-badge">' + _esc(r.method) + '</span></td>'
            + '<td>' + _esc(r.path) + '</td>'
            + '<td>' + _esc(r.name || '') + '</td>'
            + '<td>' + (r.models || []).map(m => _esc(m)).join(', ') + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphQueries(panel) {
    const queries = _aiGraphData.queries || [];
    if (!queries.length) { panel.innerHTML = '<div class="ai-graph-empty">No queries captured</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Name</th><th>SQL</th><th>Models</th></tr></thead><tbody>';
    queries.forEach(q => {
        html += '<tr><td>' + _esc(q.name) + '</td>'
            + '<td><code>' + _esc((q.sql || '').substring(0, 120)) + '</code></td>'
            + '<td>' + (q.models || []).map(m => _esc(m)).join(', ') + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphDiagnostics(panel) {
    const diags = _aiGraphData.diagnostics || [];
    if (!diags.length) { panel.innerHTML = '<div class="ai-graph-empty">No diagnostic issues</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Severity</th><th>Code</th><th>Message</th></tr></thead><tbody>';
    diags.forEach(d => {
        const cls = d.severity === 'error' ? 'severity-error' : d.severity === 'warning' ? 'severity-warning' : 'severity-info';
        html += '<tr><td><span class="' + cls + '">' + _esc(d.severity) + '</span></td>'
            + '<td>' + _esc(d.code) + '</td>'
            + '<td>' + _esc(d.message) + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphMigrations(panel) {
    const migs = _aiGraphData.migrations || [];
    if (!migs.length) { panel.innerHTML = '<div class="ai-graph-empty">No migrations found</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Name</th><th>App</th><th>Models</th></tr></thead><tbody>';
    migs.forEach(m => {
        html += '<tr><td>' + _esc(m.name) + '</td>'
            + '<td>' + _esc(m.app) + '</td>'
            + '<td>' + (m.models || []).map(x => _esc(x)).join(', ') + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphEvents(panel) {
    const events = _aiGraphData.events || [];
    if (!events.length) { panel.innerHTML = '<div class="ai-graph-empty">No recent events</div>'; return; }
    let html = '<table class="ai-graph-table"><thead><tr><th>Time</th><th>Kind</th><th>Severity</th><th>Source</th><th>Message</th></tr></thead><tbody>';
    events.slice().reverse().forEach(e => {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '';
        const cls = e.severity === 'error' ? 'severity-error' : e.severity === 'warning' ? 'severity-warning' : 'severity-info';
        html += '<tr><td>' + _esc(ts) + '</td>'
            + '<td>' + _esc(e.kind || '') + '</td>'
            + '<td><span class="' + cls + '">' + _esc(e.severity || 'info') + '</span></td>'
            + '<td>' + _esc(e.source_type || '') + '/' + _esc(e.source_id || '') + '</td>'
            + '<td>' + _esc(e.message || '') + '</td></tr>';
    });
    html += '</tbody></table>';
    panel.innerHTML = html;
}

function _renderGraphRelationships(panel) {
    const models = _aiGraphData.models || [];
    const routes = _aiGraphData.routes || [];
    const queries = _aiGraphData.queries || [];
    const migs = _aiGraphData.migrations || [];
    const diags = _aiGraphData.diagnostics || [];

    let html = '<div class="ai-graph-rels">';

    // Route → Model
    const routeModels = routes.filter(r => (r.models || []).length > 0);
    if (routeModels.length) {
        html += '<h4>Route \u2192 Model</h4><ul>';
        routeModels.forEach(r => {
            html += '<li><span class="method-badge">' + _esc(r.method) + '</span> '
                + _esc(r.path) + ' \u2192 ' + (r.models || []).map(m => '<strong>' + _esc(m) + '</strong>').join(', ') + '</li>';
        });
        html += '</ul>';
    }

    // Query → Model
    const queryModels = queries.filter(q => (q.models || []).length > 0);
    if (queryModels.length) {
        html += '<h4>Query \u2192 Model</h4><ul>';
        queryModels.forEach(q => {
            html += '<li>' + _esc(q.name) + ' \u2192 ' + (q.models || []).map(m => '<strong>' + _esc(m) + '</strong>').join(', ') + '</li>';
        });
        html += '</ul>';
    }

    // Migration → Model
    const migModels = migs.filter(m => (m.models || []).length > 0);
    if (migModels.length) {
        html += '<h4>Migration \u2192 Model</h4><ul>';
        migModels.forEach(m => {
            html += '<li>' + _esc(m.name) + ' \u2192 ' + (m.models || []).map(x => '<strong>' + _esc(x) + '</strong>').join(', ') + '</li>';
        });
        html += '</ul>';
    }

    // Model relations
    const modelRels = models.filter(m => (m.relations || []).length > 0);
    if (modelRels.length) {
        html += '<h4>Model Relations</h4><ul>';
        modelRels.forEach(m => {
            html += '<li><strong>' + _esc(m.name) + '</strong>: ' + (m.relations || []).map(r => _esc(r)).join(', ') + '</li>';
        });
        html += '</ul>';
    }

    if (!routeModels.length && !queryModels.length && !migModels.length && !modelRels.length) {
        html += '<div class="ai-graph-empty">No relationships found</div>';
    }

    html += '</div>';
    panel.innerHTML = html;
}

// v0.5.31: Keyboard shortcut — Ctrl+I or Cmd+I opens AI Console
function _initAiConsoleKeyboardShortcut() {
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
            e.preventDefault();
            navigateTo('ai-console');
            setTimeout(() => {
                const input = document.getElementById('ai-console-input');
                if (input) input.focus();
            }, 100);
        }
    });
}


// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (state.diagnosticsInterval) {
        clearInterval(state.diagnosticsInterval);
    }
    if (state.dbQueriesInterval) {
        clearInterval(state.dbQueriesInterval);
    }
});

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    init();
    _initAiFlowPanelControls();
    _initAiFlowKeyboardShortcuts();
    initAiFlowButtons();
    _initAiConsoleKeyboardShortcut();

    // v0.5.42: Collapsible Advanced nav group toggle
    const advancedToggle = document.getElementById('nav-advanced-toggle');
    const advancedItems = document.getElementById('nav-advanced-items');
    if (advancedToggle && advancedItems) {
        advancedToggle.addEventListener('click', () => {
            const expanded = advancedToggle.getAttribute('aria-expanded') === 'true';
            advancedToggle.setAttribute('aria-expanded', String(!expanded));
            advancedItems.hidden = expanded;
        });
    }
});
