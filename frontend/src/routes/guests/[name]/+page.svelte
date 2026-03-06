<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const g = $derived(data.guest);
	const lift = $derived(
		g.avg_bucket_score != null ? +(g.avg_bucket_score - g.baseline_bucket_avg).toFixed(1) : null
	);

	// SVG line chart dimensions
	const chartW = 500;
	const chartH = 200;
	const padX = 40;
	const padY = 30;
	const plotW = chartW - padX * 2;
	const plotH = chartH - padY * 2;

	const scores = $derived(g.episodes.map((e) => e.avg_kill_score ?? 0));
	const maxScore = $derived(Math.max(...scores, g.baseline_bucket_avg + 2));
	const minScore = $derived(Math.min(...scores, g.baseline_bucket_avg - 2));

	function x(i: number): number {
		if (g.episodes.length <= 1) return padX + plotW / 2;
		return padX + (i / (g.episodes.length - 1)) * plotW;
	}

	function y(score: number): number {
		const range = maxScore - minScore || 1;
		return padY + plotH - ((score - minScore) / range) * plotH;
	}

	const linePath = $derived(
		g.episodes
			.map((e, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(e.avg_kill_score ?? 0).toFixed(1)}`)
			.join(' ')
	);
</script>

<svelte:head>
	<title>{g.guest_name} — Kill Tony DB</title>
</svelte:head>

<div class="guest-hero">
	<div class="guest-hero-left">
		<a href="/guests" class="back-link">&larr; All guests</a>
		<div class="guest-tag">Guest</div>
		<h1 class="guest-name">{g.guest_name}</h1>
	</div>
	<div class="guest-hero-stats">
		<div class="stat-row">
			<div class="stat-label">Appearances</div>
			<div class="stat-val">{g.episode_count}</div>
		</div>
		<div class="stat-row">
			<div class="stat-label">Avg Kill Score</div>
			<div class="stat-val">{g.avg_kill_score ?? '—'}</div>
		</div>
		<div class="stat-row">
			<div class="stat-label">Avg Bucket Score</div>
			<div class="stat-val">{g.avg_bucket_score ?? '—'}</div>
		</div>
		<div class="stat-row">
			<div class="stat-label">Total Laughs</div>
			<div class="stat-val">{g.total_laugh_count.toLocaleString()}</div>
		</div>
		{#if lift != null}
			<div class="stat-row">
				<div class="stat-label">Bucket Lift</div>
				<div class="stat-val lift" class:positive={lift > 0} class:negative={lift < 0}>
					{lift > 0 ? '+' : ''}{lift}
				</div>
			</div>
		{/if}
	</div>
</div>

<!-- EPISODE PERFORMANCE CHART -->
{#if g.episodes.length > 0}
	<div class="section">
		<div class="s-header">
			<div>
				<div class="s-title">Episode Performance</div>
				<div class="s-sub">
					Average kill score per episode when {g.guest_name} was on the panel.
					Dashed line = overall bucket-pull baseline ({g.baseline_bucket_avg}).
				</div>
			</div>
		</div>

		<div class="chart-wrap">
			<svg width="100%" viewBox="0 0 {chartW} {chartH}" preserveAspectRatio="xMidYMid meet">
				<!-- Baseline -->
				<line
					x1={padX}
					y1={y(g.baseline_bucket_avg)}
					x2={chartW - padX}
					y2={y(g.baseline_bucket_avg)}
					stroke="var(--dim)"
					stroke-width="1"
					stroke-dasharray="6,4"
				/>
				<text
					x={chartW - padX + 4}
					y={y(g.baseline_bucket_avg) + 4}
					fill="var(--dim)"
					font-family="var(--mono)"
					font-size="9"
				>
					{g.baseline_bucket_avg}
				</text>

				<!-- Line -->
				{#if g.episodes.length > 1}
					<path d={linePath} fill="none" stroke="var(--red)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
				{/if}

				<!-- Dots -->
				{#each g.episodes as ep, i}
					<circle
						cx={x(i)}
						cy={y(ep.avg_kill_score ?? 0)}
						r="6"
						fill="var(--red)"
						stroke="var(--bg)"
						stroke-width="2"
					/>
					<!-- Episode label -->
					<text
						x={x(i)}
						y={chartH - 6}
						text-anchor="middle"
						fill="var(--muted)"
						font-family="var(--mono)"
						font-size="10"
					>
						#{ep.episode_number}
					</text>
					<!-- Score label -->
					<text
						x={x(i)}
						y={y(ep.avg_kill_score ?? 0) - 12}
						text-anchor="middle"
						fill="var(--text)"
						font-family="var(--mono)"
						font-size="11"
						font-weight="700"
					>
						{ep.avg_kill_score}
					</text>
				{/each}
			</svg>
		</div>
	</div>
{/if}

<!-- EPISODE LIST -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Appearances</div>
			<div class="s-sub">{g.episode_count} appearance{g.episode_count !== 1 ? 's' : ''}</div>
		</div>
	</div>

	<div class="ep-list">
		{#each g.episodes as ep}
			<a href="/episodes/{ep.episode_number}" class="ep-row">
				<div class="ep-num">#{ep.episode_number}</div>
				<div class="ep-info">
					{#if ep.date}
						<span class="ep-date">{ep.date}</span>
					{/if}
					{#if ep.venue}
						<span class="ep-venue">{ep.venue}</span>
					{/if}
					<div class="ep-co-guests">
						{#each ep.guests.filter((n) => n !== g.guest_name) as coGuest}
							<span class="co-guest-chip">{coGuest}</span>
						{/each}
					</div>
				</div>
				<div class="ep-metrics">
					<div class="em">
						<span class="em-label">Score</span>
						<span class="em-val score">{ep.avg_kill_score ?? '—'}</span>
					</div>
					<div class="em">
						<span class="em-label">Bucket</span>
						<span class="em-val">{ep.avg_bucket_score ?? '—'}</span>
					</div>
					<div class="em">
						<span class="em-label">Laughs</span>
						<span class="em-val">{ep.laugh_count ?? '—'}</span>
					</div>
					<div class="em">
						<span class="em-label">Hot Sets</span>
						<span class="em-val">{ep.hot_sets}</span>
					</div>
				</div>
			</a>
		{/each}
	</div>
</div>

<style>
	.guest-hero {
		padding: 40px;
		border-bottom: 1px solid var(--border);
		display: grid;
		grid-template-columns: 1fr 300px;
		gap: 48px;
		align-items: start;
	}

	.back-link {
		display: inline-block;
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		text-decoration: none;
		margin-bottom: 20px;
		letter-spacing: 0.5px;
		transition: color 0.15s;
	}

	.back-link:hover {
		color: var(--red);
	}

	.guest-tag {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--red);
		background: var(--red-d);
		padding: 5px 14px;
		border-radius: 4px;
		display: inline-block;
		margin-bottom: 12px;
		border: 1px solid rgba(220, 38, 38, 0.2);
	}

	.guest-name {
		font-size: clamp(32px, 4vw, 48px);
		font-weight: 700;
		letter-spacing: -1.5px;
		line-height: 1.1;
	}

	.guest-hero-stats {
		border-left: 1px solid var(--border);
		padding-left: 36px;
	}

	.stat-row {
		padding: 12px 0;
		border-bottom: 1px solid var(--border);
	}

	.stat-row:last-child {
		border-bottom: none;
	}

	.stat-row:first-child {
		padding-top: 0;
	}

	.stat-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		margin-bottom: 4px;
	}

	.stat-val {
		font-family: var(--mono);
		font-size: 24px;
		font-weight: 700;
		letter-spacing: -1px;
		line-height: 1;
	}

	.stat-val.lift.positive {
		color: var(--green);
	}

	.stat-val.lift.negative {
		color: var(--red-s);
	}

	.chart-wrap {
		max-width: 600px;
	}

	.ep-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.ep-row {
		display: grid;
		grid-template-columns: 70px 1fr auto;
		align-items: center;
		gap: 20px;
		padding: 16px 20px;
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
		font-size: 18px;
		font-weight: 700;
	}

	.ep-info {
		min-width: 0;
	}

	.ep-date {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-right: 10px;
	}

	.ep-venue {
		font-size: 13px;
		color: var(--t2);
	}

	.ep-co-guests {
		display: flex;
		gap: 6px;
		margin-top: 4px;
		flex-wrap: wrap;
	}

	.co-guest-chip {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--t2);
		background: var(--raised);
		border: 1px solid var(--border);
		padding: 2px 8px;
		border-radius: 4px;
	}

	.ep-metrics {
		display: flex;
		gap: 20px;
	}

	.em {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.em-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.em-val {
		font-family: var(--mono);
		font-size: 16px;
		font-weight: 700;
	}

	.em-val.score {
		color: var(--red);
	}
</style>
