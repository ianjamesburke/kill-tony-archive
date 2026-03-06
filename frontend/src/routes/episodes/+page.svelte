<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Episodes — Kill Tony DB</title>
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
				<div class="ep-num">#{ep.episode_number}</div>
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
						<span class="ep-stat-label">Sets</span>
						<span class="ep-stat-val">{ep.set_count}</span>
					</div>
					<div class="ep-stat">
						<span class="ep-stat-label">Avg Score</span>
						<span class="ep-stat-val score">{ep.avg_kill_score ?? '—'}</span>
					</div>
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
		grid-template-columns: 80px 1fr 180px;
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
