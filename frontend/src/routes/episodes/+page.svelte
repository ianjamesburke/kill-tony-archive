<script lang="ts">
	import type { PageData } from './$types';
	import type { Episode } from '$lib/types';
	import KillScoreHistogram from '$lib/components/KillScoreHistogram.svelte';

	let { data }: { data: PageData } = $props();

	type TimePeriod = 'all' | 'year' | '30d' | 'last_ep';
	const periodLabels: Record<TimePeriod, string> = {
		all: 'All Time',
		year: 'Last Year',
		'30d': 'Last 30 Days',
		last_ep: 'Last Episode'
	};

	const PAGE_SIZE = 50;

	let activePeriod: TimePeriod = $state('all');
	let page = $state(1);

	function getSinceDate(period: TimePeriod): string | undefined {
		if (period === 'all') return undefined;
		const now = new Date();
		let d: Date;
		if (period === 'year') {
			d = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
		} else if (period === '30d') {
			d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
		} else {
			return undefined;
		}
		const yyyy = d.getFullYear();
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		return `${yyyy}${mm}${dd}`;
	}

	const latestEpisode = $derived(
		data.episodes.reduce((max, e) => Math.max(max, e.episode_number), 0)
	);

	const periodEpisodes = $derived((): Episode[] => {
		if (activePeriod === 'all') return data.episodes;
		if (activePeriod === 'last_ep') {
			return data.episodes.filter((e) => e.episode_number === latestEpisode);
		}
		const since = getSinceDate(activePeriod)!;
		return data.episodes.filter((e) => e.date != null && e.date >= since);
	});

	const totalPages = $derived(Math.ceil(periodEpisodes().length / PAGE_SIZE));

	const pagedEpisodes = $derived((): Episode[] => {
		const eps = periodEpisodes();
		return eps.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
	});

	function selectPeriod(period: TimePeriod) {
		if (period === activePeriod) return;
		activePeriod = period;
		page = 1;
	}

	const maxKillScore = $derived(
		Math.max(...periodEpisodes().map((e) => e.episode_kill_score ?? 0), 1)
	);

	const epScores = $derived(
		periodEpisodes()
			.filter((e) => e.episode_kill_score != null)
			.map((e) => e.episode_kill_score!)
	);

	const totalSets = $derived(periodEpisodes().reduce((s, e) => s + (e.set_count ?? 0), 0));

	const avgEpScore = $derived(
		epScores.length > 0
			? (epScores.reduce((a, b) => a + b, 0) / epScores.length).toFixed(1)
			: '—'
	);

	const bestEp = $derived(
		periodEpisodes().reduce(
			(best: Episode | undefined, e) =>
				(e.episode_kill_score ?? 0) > (best?.episode_kill_score ?? 0) ? e : best,
			undefined
		)
	);

	const epsWithLaugh = $derived(
		periodEpisodes().filter((e) => e.laughter_pct != null && e.laughter_pct > 0)
	);

	const avgLaughPct = $derived(
		epsWithLaugh.length > 0
			? (epsWithLaugh.reduce((s, e) => s + e.laughter_pct!, 0) / epsWithLaugh.length).toFixed(
					1
				) + '%'
			: '—'
	);
</script>

<svelte:head>
	<title>Episodes | Kill Tony Archive</title>
</svelte:head>

<!-- KILL SCORE DISTRIBUTION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Kill Score Distribution</div>
			<div class="s-sub">How scores spread across {epScores.length} episodes</div>
		</div>
	</div>
	<KillScoreHistogram scores={epScores} maxValue={100} binSize={5} />
</div>

<!-- EPISODE BREAKDOWN -->
<div class="section">
	<div class="two-col">
		<div>
			<div class="s-header">
				<div>
					<div class="s-title">Episode Stats</div>
					<div class="s-sub">Overview across all indexed episodes</div>
				</div>
			</div>
			<div class="status-cards">
				<div class="status-card">
					<div class="sc-label">Total Episodes</div>
					<div class="sc-count">{periodEpisodes().length}</div>
					<div class="sc-score">{totalSets} sets indexed</div>
				</div>
				<div class="status-card">
					<div class="sc-label">Avg Episode Score</div>
					<div class="sc-count">{avgEpScore}</div>
					<div class="sc-score">across scored episodes</div>
				</div>
			</div>
		</div>
		<div>
			<div class="s-header">
				<div>
					<div class="s-title">Audience Data</div>
					<div class="s-sub">Laughter analysis from processed audio</div>
				</div>
			</div>
			<div class="status-cards">
				<div class="status-card">
					<div class="sc-label">Avg Laugh %</div>
					<div class="sc-count">{avgLaughPct}</div>
					<div class="sc-score">{epsWithLaugh.length} episodes with audio</div>
				</div>
				{#if bestEp && bestEp.episode_kill_score != null}
					<div class="status-card">
						<div class="sc-label">Best Episode</div>
						<div class="sc-count">#{bestEp.episode_number}</div>
						<div class="sc-score">Score: {bestEp.episode_kill_score}</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<!-- ALL EPISODES -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Episodes</div>
			<div class="s-sub">
				{periodEpisodes().length} episodes · page {page} of {Math.max(1, totalPages)}
			</div>
		</div>
		<div class="s-badge">{periodLabels[activePeriod]}</div>
	</div>
	<div class="period-tabs">
		{#each Object.entries(periodLabels) as [key, label]}
			<button
				class="period-tab"
				class:active={activePeriod === key}
				onclick={() => selectPeriod(key as TimePeriod)}
			>
				{label}
			</button>
		{/each}
	</div>

	<div class="ep-list">
		{#each pagedEpisodes() as ep}
			<a href="/episodes/{ep.episode_number}" class="ep-row">
				<div class="ep-left">
					{#if ep.episode_rank != null}
						<div class="ep-rank">#{ep.episode_rank}</div>
					{/if}
					<div class="ep-title-block">
						<div class="ep-title">
							<span class="ep-num">#{ep.episode_number}</span>
							{#if ep.guests.length > 0}
								<span class="ep-dash">—</span>
								<span class="ep-guest-names">{ep.guests.join(', ')}</span>
							{/if}
						</div>
						<div class="ep-meta">
							{#if ep.date}
								<span class="ep-date">{ep.date}</span>
							{/if}
							{#if ep.venue}
								<span class="ep-venue">{ep.venue}</span>
							{/if}
						</div>
					</div>
				</div>
				<div class="ep-stats">
					<div class="ep-stat ep-stat-score">
						<span class="ep-stat-label">Kill Score</span>
						<div class="ep-score-row">
							<div class="ep-score-bar-bg">
								<div
									class="ep-score-bar-fill"
									style="width: {(((ep.episode_kill_score ?? 0) / maxKillScore) * 100).toFixed(0)}%"
								></div>
							</div>
							<span class="ep-stat-val score">{ep.episode_kill_score ?? '—'}</span>
						</div>
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
				</div>
			</a>
		{/each}
	</div>

	{#if totalPages > 1}
		<div class="pagination">
			<button class="page-btn" disabled={page <= 1} onclick={() => page--}> ← Prev </button>
			<span class="page-info">{page} / {totalPages}</span>
			<button class="page-btn" disabled={page >= totalPages} onclick={() => page++}>
				Next →
			</button>
		</div>
	{/if}
</div>

<style>
	.two-col {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 40px;
	}

	.status-cards {
		display: flex;
		gap: 16px;
	}

	.status-card {
		flex: 1;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 24px;
	}

	.sc-label {
		font-family: var(--mono);
		font-size: 10px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		margin-bottom: 8px;
	}

	.sc-count {
		font-family: var(--mono);
		font-size: 36px;
		font-weight: 700;
		letter-spacing: -1.5px;
		line-height: 1;
		margin-bottom: 8px;
	}

	.sc-score {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--red);
	}

	.period-tabs {
		display: flex;
		gap: 4px;
		margin-bottom: 16px;
	}

	.period-tab {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.5px;
		padding: 7px 16px;
		border-radius: 5px;
		border: 1px solid var(--border);
		background: var(--card);
		color: var(--muted);
		cursor: pointer;
		transition:
			background 0.15s,
			color 0.15s,
			border-color 0.15s;
	}

	.period-tab:hover {
		border-color: var(--bh);
		color: var(--t2);
	}

	.period-tab.active {
		background: var(--red-d);
		border-color: rgba(220, 38, 38, 0.3);
		color: var(--red);
	}

	.ep-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.ep-row {
		display: grid;
		grid-template-columns: 1fr auto;
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
		flex-direction: row;
		align-items: baseline;
		gap: 10px;
		min-width: 0;
	}

	.ep-rank {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		color: var(--red);
		letter-spacing: 0.5px;
		flex-shrink: 0;
	}

	.ep-title-block {
		min-width: 0;
	}

	.ep-title {
		display: flex;
		align-items: baseline;
		gap: 0;
		flex-wrap: wrap;
	}

	.ep-num {
		font-family: var(--mono);
		font-size: 16px;
		font-weight: 700;
		letter-spacing: -0.5px;
		flex-shrink: 0;
	}

	.ep-dash {
		margin: 0 8px;
		color: var(--muted);
		font-weight: 400;
	}

	.ep-guest-names {
		font-size: 15px;
		font-weight: 500;
		color: var(--t2);
	}

	.ep-meta {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-top: 4px;
	}

	.ep-date {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
	}

	.ep-venue {
		font-size: 12px;
		color: var(--dim);
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

	.ep-stat-score {
		min-width: 120px;
	}

	.ep-score-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.ep-score-bar-bg {
		flex: 1;
		height: 4px;
		background: var(--border);
		border-radius: 2px;
		overflow: hidden;
		min-width: 60px;
	}

	.ep-score-bar-fill {
		height: 100%;
		background: var(--red);
		border-radius: 2px;
		opacity: 0.7;
		transition: width 0.3s ease;
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 16px;
		margin-top: 24px;
	}

	.page-btn {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		padding: 8px 20px;
		border-radius: 5px;
		border: 1px solid var(--border);
		background: var(--card);
		color: var(--muted);
		cursor: pointer;
		transition:
			background 0.15s,
			color 0.15s,
			border-color 0.15s;
	}

	.page-btn:hover:not(:disabled) {
		border-color: var(--bh);
		color: var(--t2);
	}

	.page-btn:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.page-info {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
		min-width: 60px;
		text-align: center;
	}

	@media (max-width: 768px) {
		.two-col {
			grid-template-columns: 1fr;
			gap: 24px;
		}

		.status-cards {
			flex-direction: column;
		}

		.period-tabs {
			flex-wrap: wrap;
		}

		.period-tab {
			font-size: 10px;
			padding: 6px 10px;
		}

		.ep-row {
			grid-template-columns: 1fr;
			gap: 8px;
			padding: 14px 16px;
		}

		.ep-title {
			flex-direction: column;
			gap: 2px;
		}

		.ep-dash {
			display: none;
		}

		.ep-guest-names {
			font-size: 13px;
		}

		.ep-stats {
			gap: 12px;
			flex-wrap: wrap;
		}

		.ep-stat-score {
			min-width: auto;
		}

		.ep-stat-val {
			font-size: 14px;
		}

		.ep-score-bar-bg {
			min-width: 40px;
		}
	}
</style>
