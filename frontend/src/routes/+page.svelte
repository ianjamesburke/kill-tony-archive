<script lang="ts">
	import type { PageData } from './$types';
	import type { ComedySet } from '$lib/types';
	import EpisodePulse from '$lib/components/EpisodePulse.svelte';
	import GuestLeaderboard from '$lib/components/GuestLeaderboard.svelte';
	import SetCard from '$lib/components/SetCard.svelte';
	import TopicBubbleTimeline from '$lib/components/TopicBubbleTimeline.svelte';
	import { fetchSets } from '$lib/api';
	import { goto } from '$app/navigation';

	let { data }: { data: PageData } = $props();

	type TimePeriod = 'all' | 'year' | '30d' | 'last_ep';
	const periodLabels: Record<TimePeriod, string> = {
		all: 'All Time',
		year: 'Last Year',
		'30d': 'Last 30 Days',
		last_ep: 'Last Episode'
	};

	let activePeriod: TimePeriod = $state('all');
	let filteredSets: ComedySet[] = $state(data.topSets);
	let loading = $state(false);

	function getSinceDate(period: TimePeriod): string | undefined {
		if (period === 'all') return undefined;
		const now = new Date();
		let d: Date;
		if (period === 'year') {
			d = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
		} else if (period === '30d') {
			d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
		} else {
			// last_ep: use the latest episode number to filter
			return undefined;
		}
		const yyyy = d.getFullYear();
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		return `${yyyy}${mm}${dd}`;
	}

	async function selectPeriod(period: TimePeriod) {
		if (period === activePeriod) return;
		activePeriod = period;

		if (period === 'all') {
			filteredSets = data.topSets;
			return;
		}

		loading = true;
		try {
			if (period === 'last_ep') {
				const latestEp = data.stats.latest_episode;
				const res = await fetchSets({
					episode: latestEp,
					sort: 'kill_score',
					order: 'desc',
					limit: 10
				});
				filteredSets = res.sets;
			} else {
				const since = getSinceDate(period);
				const res = await fetchSets({
					since,
					sort: 'kill_score',
					order: 'desc',
					limit: 10
				});
				filteredSets = res.sets;
			}
		} catch {
			filteredSets = [];
		} finally {
			loading = false;
		}
	}

	function formatNumber(n: number): string {
		return n.toLocaleString();
	}
</script>

<!-- HERO -->
<div class="hero">
	<div>
		<h1 class="hero-title">Kill Tony<br /><span class="thin">Archive</span></h1>
		<p class="hero-desc">
			Every 1-minute set from {data.stats.episode_count} episodes, scored, transcribed, and analyzed.
			The complete record of what makes a crowd erupt — and what falls flat.
		</p>
	</div>
	<div class="hero-metrics">
		<div class="hm-row">
			<div class="hm-label">Episodes</div>
			<div class="hm-val">{formatNumber(data.stats.episode_count)}</div>
		</div>
		<div class="hm-row">
			<div class="hm-label">Total Sets</div>
			<div class="hm-val">{formatNumber(data.stats.set_count)}</div>
		</div>
		<div class="hm-row">
			<div class="hm-label">Comedians</div>
			<div class="hm-val">{formatNumber(data.stats.comedian_count)}</div>
		</div>
		<div class="hm-row">
			<div class="hm-label">Avg Kill Score</div>
			<div class="hm-val">{data.stats.avg_kill_score}</div>
		</div>
		<div class="hm-row">
			<div class="hm-label">Golden Tickets</div>
			<div class="hm-val">{formatNumber(data.stats.golden_tickets)}</div>
		</div>
	</div>
</div>

<!-- EPISODE PULSE -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Episode Pulse</div>
			<div class="s-sub">
				Average kill score per episode — height reflects overall show performance
			</div>
		</div>
		<div class="s-badge">{data.stats.episode_count} episodes</div>
	</div>
	<EpisodePulse episodes={data.episodes} />
</div>

<!-- MAIN GRID: Topics + Guests -->
<div class="section">
	<div class="main-grid">
		<div class="mg-panel">
			<div class="s-header">
				<div>
					<div class="s-title">Topic Trends</div>
					<div class="s-sub">How joke topics shift across episodes</div>
				</div>
			</div>
			<TopicBubbleTimeline timeline={data.topicTimeline} totals={data.topics} />
		</div>

		<div class="mg-panel">
			<div class="s-header">
				<div>
					<div class="s-title">Top Guests</div>
					<div class="s-sub">Ranked by avg Kill Score during their appearances</div>
				</div>
			</div>
			<GuestLeaderboard guests={data.guests} />
		</div>
	</div>
</div>

<!-- TOP SETS -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Top Sets</div>
			<div class="s-sub">
				The highest-performing 1-minute sets in the database, ranked by Kill Score
			</div>
		</div>
		<div class="s-badge">Top 10</div>
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
	<div class="top-sets-list" class:loading>
		{#if filteredSets.length === 0 && !loading}
			<div class="sets-empty">No sets found for this period.</div>
		{:else}
			{#each filteredSets as s, i}
				<SetCard
					set={s}
					rank={i + 1}
					showEpisode={true}
					onJumpTo={s.set_start_seconds != null
						? () => goto(`/episodes/${s.episode_number}#t=${s.set_start_seconds}`)
						: undefined}
				/>
			{/each}
		{/if}
	</div>
</div>

<style>
	.hero {
		padding: 48px 40px 44px;
		border-bottom: 1px solid var(--border);
		display: grid;
		grid-template-columns: 1fr 260px;
		gap: 48px;
		align-items: center;
	}

	.hero-tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--red);
		background: var(--red-d);
		padding: 5px 14px;
		border-radius: 4px;
		margin-bottom: 16px;
		border: 1px solid rgba(220, 38, 38, 0.2);
	}

	.hero-dot {
		width: 5px;
		height: 5px;
		background: var(--red);
		border-radius: 50%;
		display: inline-block;
	}

	.hero-title {
		font-size: clamp(56px, 8vw, 96px);
		font-weight: 700;
		line-height: 1.05;
		letter-spacing: -1.5px;
		margin-bottom: 10px;
	}

	.hero-title .thin {
		font-weight: 400;
		color: var(--muted);
	}

	.hero-desc {
		font-size: 14px;
		color: var(--muted);
		line-height: 1.65;
		max-width: 520px;
	}

	.hero-metrics {
		display: flex;
		flex-direction: column;
		gap: 0;
		border-left: 1px solid var(--border);
		padding-left: 36px;
	}

	.hm-row {
		display: flex;
		flex-direction: column;
		padding: 14px 0;
		border-bottom: 1px solid var(--border);
	}

	.hm-row:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.hm-row:first-child {
		padding-top: 0;
	}

	.hm-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		margin-bottom: 5px;
	}

	.hm-val {
		font-family: var(--mono);
		font-size: 32px;
		font-weight: 700;
		letter-spacing: -1.5px;
		line-height: 1;
	}

	.main-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1px;
		background: var(--border);
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--border);
	}

	.mg-panel {
		background: var(--bg);
		padding: 36px 40px;
		display: flex;
		flex-direction: column;
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

	.top-sets-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		transition: opacity 0.15s;
	}

	.top-sets-list.loading {
		opacity: 0.5;
	}

	.sets-loading,
	.sets-empty {
		font-family: var(--mono);
		font-size: 13px;
		color: var(--muted);
		text-align: center;
		padding: 40px 0;
	}

	@media (max-width: 768px) {
		.hero {
			grid-template-columns: 1fr;
			padding: 32px 16px;
			gap: 24px;
		}

		.hero-title {
			font-size: clamp(36px, 12vw, 56px);
		}

		.hero-metrics {
			border-left: none;
			border-top: 1px solid var(--border);
			padding-left: 0;
			padding-top: 20px;
			flex-direction: row;
			flex-wrap: wrap;
			gap: 0;
		}

		.hm-row {
			flex: 1;
			min-width: 50%;
			padding: 10px 0;
			border-bottom: none;
			border-right: 1px solid var(--border);
		}

		.hm-row:nth-child(even) {
			border-right: none;
			padding-left: 16px;
		}

		.hm-row:last-child {
			border-right: none;
		}

		.hm-val {
			font-size: 22px;
		}

		.main-grid {
			grid-template-columns: 1fr;
		}

		.period-tabs {
			flex-wrap: wrap;
		}

		.period-tab {
			font-size: 10px;
			padding: 6px 10px;
		}
	}
</style>
