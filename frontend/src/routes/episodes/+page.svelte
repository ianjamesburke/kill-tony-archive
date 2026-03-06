<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	function formatViews(n: number | null): string {
		if (n == null) return '—';
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
		if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
		return n.toLocaleString();
	}
</script>

<svelte:head>
	<title>Kill Tony DB</title>
</svelte:head>

<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Episodes</div>
			<div class="s-sub">{data.episodes.length} episodes in the database</div>
		</div>
	</div>

	<div class="ep-list">
		{#each data.episodes as ep}
			<a href="/episodes/{ep.episode_number}" class="ep-row">
				<div class="ep-left">
					{#if ep.episode_rank != null}
						<div class="ep-rank">#{ep.episode_rank}</div>
					{/if}
					<div class="ep-num">#{ep.episode_number}</div>
				</div>
				<div class="ep-info">
					<div class="ep-info-top">
						{#if ep.date}
							<span class="ep-date">{ep.date}</span>
						{/if}
						{#if ep.venue}
							<span class="ep-venue">{ep.venue}</span>
						{/if}
					</div>
					{#if ep.guests.length > 0}
						<div class="ep-guests">
							{#each ep.guests as guest}
								<span class="guest-chip">{guest}</span>
							{/each}
						</div>
					{/if}
				</div>
				<div class="ep-stats">
					<div class="ep-stat">
						<span class="ep-stat-label">Kill Score</span>
						<span class="ep-stat-val score">{ep.episode_kill_score ?? '—'}</span>
					</div>
					<div class="ep-stat">
						<span class="ep-stat-label">Sets</span>
						<span class="ep-stat-val">{ep.set_count}</span>
					</div>
					<div class="ep-stat">
						<span class="ep-stat-label">Avg Set</span>
						<span class="ep-stat-val">{ep.avg_kill_score ?? '—'}</span>
					</div>
					{#if ep.laughter_pct != null && ep.laughter_pct > 0}
						<div class="ep-stat">
							<span class="ep-stat-label">Laugh %</span>
							<span class="ep-stat-val">{ep.laughter_pct.toFixed(1)}%</span>
						</div>
					{/if}
					{#if ep.view_count}
						<div class="ep-stat">
							<span class="ep-stat-label">Views</span>
							<span class="ep-stat-val">{formatViews(ep.view_count)}</span>
						</div>
					{/if}
				</div>
			</a>
		{/each}
	</div>
</div>

<style>
	.ep-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.ep-row {
		display: grid;
		grid-template-columns: 100px 1fr auto;
		align-items: center;
		gap: 20px;
		padding: 18px 20px;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 6px;
		text-decoration: none;
		color: var(--text);
		transition:
			border-color 0.15s,
			background 0.15s;
	}

	.ep-row:hover {
		border-color: var(--bh);
		background: var(--raised);
	}

	.ep-left {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}

	.ep-rank {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		color: var(--red);
		letter-spacing: 0.5px;
	}

	.ep-num {
		font-family: var(--mono);
		font-size: 20px;
		font-weight: 700;
		letter-spacing: -0.5px;
	}

	.ep-info {
		min-width: 0;
	}

	.ep-info-top {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.ep-date {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
	}

	.ep-venue {
		font-size: 13px;
		color: var(--t2);
	}

	.ep-guests {
		display: flex;
		gap: 6px;
		margin-top: 6px;
		flex-wrap: wrap;
	}

	.guest-chip {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--t2);
		background: var(--raised);
		border: 1px solid var(--border);
		padding: 3px 8px;
		border-radius: 4px;
	}

	.ep-stats {
		display: flex;
		gap: 20px;
		justify-content: flex-end;
	}

	.ep-stat {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.ep-stat-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.ep-stat-val {
		font-family: var(--mono);
		font-size: 18px;
		font-weight: 700;
		letter-spacing: -0.5px;
	}

	.ep-stat-val.score {
		color: var(--red);
	}
</style>
