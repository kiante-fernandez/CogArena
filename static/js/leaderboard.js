document.addEventListener('DOMContentLoaded', async () => {
    const loading = document.getElementById('leaderboard-loading');
    const empty = document.getElementById('leaderboard-empty');
    const wrapper = document.getElementById('leaderboard-table-wrapper');
    const tbody = document.getElementById('leaderboard-body');

    try {
        const resp = await fetch('/api/leaderboard');
        const data = await resp.json();
        loading.classList.add('hidden');

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
                <td class="px-4 py-3 font-semibold">${esc(entry.model_name || '\u2014')}</td>
                <td class="px-4 py-3 text-gray-500">${esc(entry.scaffold || '\u2014')}</td>
                <td class="px-4 py-3 text-right font-bold">${entry.composite_score.toFixed(1)}</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l1_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l2_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${(entry.l3_overall * 100).toFixed(0)}%</td>
                <td class="px-4 py-3 text-right text-gray-500">${entry.tasks_completed}/${totalTasks}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        loading.classList.add('hidden');
        empty.classList.remove('hidden');
        console.error('Leaderboard error:', err);
    }
});

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
