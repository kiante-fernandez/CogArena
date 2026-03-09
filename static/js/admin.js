document.addEventListener('DOMContentLoaded', () => {
    const keyInput = document.getElementById('admin-key');
    const authBtn = document.getElementById('auth-btn');
    const filterSection = document.getElementById('filter-section');
    const statusFilter = document.getElementById('status-filter');
    const loading = document.getElementById('admin-loading');
    const empty = document.getElementById('admin-empty');
    const errorDiv = document.getElementById('admin-error');
    const wrapper = document.getElementById('admin-table-wrapper');
    const tbody = document.getElementById('admin-body');

    // Restore saved key
    const savedKey = localStorage.getItem('cogarena_admin_key');
    if (savedKey) keyInput.value = savedKey;

    function getKey() {
        return keyInput.value.trim();
    }

    function saveKey() {
        localStorage.setItem('cogarena_admin_key', getKey());
    }

    function showError(msg) {
        loading.classList.add('hidden');
        empty.classList.add('hidden');
        wrapper.classList.add('hidden');
        errorDiv.textContent = msg;
        errorDiv.classList.remove('hidden');
    }

    function statusBadge(approved) {
        if (approved === true) return '<span class="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-800">Approved</span>';
        if (approved === false) return '<span class="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-800">Rejected</span>';
        return '<span class="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800">Pending</span>';
    }

    async function loadSubmissions() {
        const key = getKey();
        if (!key) { showError('Please enter an admin key.'); return; }
        saveKey();

        loading.classList.remove('hidden');
        empty.classList.add('hidden');
        errorDiv.classList.add('hidden');
        wrapper.classList.add('hidden');
        filterSection.classList.remove('hidden');

        const status = statusFilter.value;
        const url = status ? `/api/admin/submissions?status=${status}` : '/api/admin/submissions';

        try {
            const resp = await fetch(url, { headers: { 'X-Admin-Key': key } });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                showError(err.detail || `Error ${resp.status}`);
                return;
            }
            const data = await resp.json();
            loading.classList.add('hidden');

            if (!data.submissions || data.submissions.length === 0) {
                empty.classList.remove('hidden');
                return;
            }

            wrapper.classList.remove('hidden');
            tbody.innerHTML = '';

            data.submissions.forEach(sub => {
                const row = document.createElement('tr');
                const date = sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '\u2014';
                row.innerHTML = `
                    <td class="px-4 py-3 font-medium">${esc(sub.agent_name || '\u2014')}</td>
                    <td class="px-4 py-3">${esc(sub.model_name || '\u2014')}</td>
                    <td class="px-4 py-3 text-gray-500">${esc(sub.scaffold || '\u2014')}</td>
                    <td class="px-4 py-3 text-right font-bold">${sub.composite_score.toFixed(1)}</td>
                    <td class="px-4 py-3 text-right text-gray-500">${(sub.l1_overall * 100).toFixed(0)}%</td>
                    <td class="px-4 py-3 text-right text-gray-500">${(sub.l2_overall * 100).toFixed(0)}%</td>
                    <td class="px-4 py-3 text-right text-gray-500">${(sub.l3_overall * 100).toFixed(0)}%</td>
                    <td class="px-4 py-3 text-right text-gray-500">${sub.tasks_completed}</td>
                    <td class="px-4 py-3">${statusBadge(sub.approved)}</td>
                    <td class="px-4 py-3 text-gray-500 text-xs">${date}</td>
                    <td class="px-4 py-3 text-center">
                        <div class="flex gap-1 justify-center">
                            ${sub.approved !== true ? `<button class="approve-btn text-xs font-medium px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700" data-id="${esc(sub.session_id)}">Approve</button>` : ''}
                            ${sub.approved !== false ? `<button class="reject-btn text-xs font-medium px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700" data-id="${esc(sub.session_id)}">Reject</button>` : ''}
                        </div>
                    </td>
                `;
                tbody.appendChild(row);
            });

            // Attach button handlers
            tbody.querySelectorAll('.approve-btn').forEach(btn => {
                btn.addEventListener('click', () => reviewAction(btn.dataset.id, 'approve'));
            });
            tbody.querySelectorAll('.reject-btn').forEach(btn => {
                btn.addEventListener('click', () => reviewAction(btn.dataset.id, 'reject'));
            });
        } catch (err) {
            showError('Network error: ' + err.message);
        }
    }

    async function reviewAction(sessionId, action) {
        const key = getKey();
        try {
            const resp = await fetch(`/api/admin/submissions/${sessionId}/${action}`, {
                method: 'POST',
                headers: { 'X-Admin-Key': key, 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                alert(err.detail || `Error ${resp.status}`);
                return;
            }
            loadSubmissions();
        } catch (err) {
            alert('Network error: ' + err.message);
        }
    }

    authBtn.addEventListener('click', loadSubmissions);
    keyInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadSubmissions(); });
    statusFilter.addEventListener('change', loadSubmissions);
});

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
