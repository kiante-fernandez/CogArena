// Leaderboard, with a scorer-version selector.
//
// Reloadable rather than one-shot: changing the version refetches, so every
// render must first clear the table and reset the loading/empty/wrapper state.
// Appending without clearing would stack a second table under the first.
let versionsRendered = false;

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function fmtVersionLabel(v) {
    const when = (v.last_scored_at || '').slice(0, 10);
    const who = `${v.sessions} agent${v.sessions === 1 ? '' : 's'}`;
    if (v.is_legacy) return `legacy (pre-versioning) — ${who}`;
    return `${v.version} — ${who}${when ? ` · ${when}` : ''}`;
}

async function loadLeaderboard(version) {
    const loading = document.getElementById('leaderboard-loading');
    const empty = document.getElementById('leaderboard-empty');
    const wrapper = document.getElementById('leaderboard-table-wrapper');
    const tbody = document.getElementById('leaderboard-body');
    const bar = document.getElementById('version-bar');
    const select = document.getElementById('scorer-version');
    const warning = document.getElementById('version-warning');

    tbody.innerHTML = '';
    empty.classList.add('hidden');
    wrapper.classList.add('hidden');
    warning.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const url = version
            ? `/api/leaderboard?scorer_version=${encodeURIComponent(version)}`
            : '/api/leaderboard';
        let resp = await fetch(url);
        if (resp.status === 400) {
            // Stale bookmark or pruned version: fall back to the default rather
            // than rendering an empty board that looks like data loss.
            resp = await fetch('/api/leaderboard');
        }
        const data = await resp.json();
        loading.classList.add('hidden');

        const versions = data.scorer_versions || [];
        if (!versionsRendered && versions.length > 0) {
            select.innerHTML = '';
            versions.forEach((v) => {
                const opt = document.createElement('option');
                opt.value = v.version;
                opt.textContent = fmtVersionLabel(v);
                select.appendChild(opt);
            });
            // Only worth showing when there is a choice to make.
            if (versions.length > 1) bar.classList.remove('hidden');
            versionsRendered = true;
        }
        if (data.scorer_version) select.value = data.scorer_version;

        const selected = versions.find((v) => v.version === data.scorer_version);
        if (selected && selected.is_legacy) {
            warning.textContent = 'These scores predate scorer versioning. Their '
                + 'provenance was not recorded, so they are not comparable with '
                + 'later versions.';
            warning.classList.remove('hidden');
        } else if (data.scorer_version && data.running_scorer_version
                   && data.scorer_version !== data.running_scorer_version) {
            warning.textContent = `Scorer ${data.running_scorer_version} is deployed, `
                + `but these scores were produced by ${data.scorer_version}.`;
            warning.classList.remove('hidden');
        }

        if (!data.entries || data.entries.length === 0) {
            empty.classList.remove('hidden');
            return;
        }

        wrapper.classList.remove('hidden');
        const totalTasks = data.total_tasks || '?';

        data.entries.forEach((entry, i) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-4 py-3 font-medium text-gray-400">${i + 1}</td>
                <td class="px-4 py-3 font-semibold">${esc(entry.model_name || '—')}</td>
                <td class="px-4 py-3 text-gray-500">${esc(entry.scaffold || '—')}</td>
                <td class="px-4 py-3 text-right font-bold">${entry.composite_score.toFixed(1)}</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l1_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l2_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l3_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${entry.tasks_completed}/${totalTasks}</td>
                <td class="px-4 py-3 text-right text-gray-500">${entry.sessions_scored ?? '—'}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        loading.classList.add('hidden');
        empty.classList.remove('hidden');
        console.error('Leaderboard error:', err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('scorer-version');
    select.addEventListener('change', () => loadLeaderboard(select.value));
    loadLeaderboard(new URLSearchParams(location.search).get('scorer_version'));
});
