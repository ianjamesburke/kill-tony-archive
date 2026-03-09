<script lang="ts">
	import type { PageData } from './$types';
	import type { ComedySet, SetsStats } from '$lib/types';
	import KillScoreHistogram from '$lib/components/KillScoreHistogram.svelte';
	import CrowdDistribution from '$lib/components/CrowdDistribution.svelte';
	import SetCard from '$lib/components/SetCard.svelte';
	import { fetchSets, fetchSetsStats } from '$lib/api';
	import { goto } from '$app/navigation';

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
	let statusFilter = $state('');
	let searchTerm = $state('');
	let scoreRangeBin: string | null = $state(null);
	let page = $state(1);
	let loading = $state(false);

	let sets: ComedySet[] = $state(data.sets);
	let stats: SetsStats = $state(data.stats);
	let total = $state(data.total);

	const displaySets = $derived(() => {
		let s = sets;
		if (searchTerm) {
			const term = searchTerm.toLowerCase();
			s = s.filter((x) => x.comedian_name.toLowerCase().includes(term));
		}
		if (scoreRangeBin) {
			const [minStr, maxStr] = scoreRangeBin.split('-');
			const min = parseInt(minStr, 10);
			const max = parseInt(maxStr, 10);
			s = s.filter((x) => {
				const score = x.kill_score ?? 0;
				return score >= min && score < max;
			});
		}
		return s;
	});

	const totalPages = $derived(Math.ceil(total / PAGE_SIZE));

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

	async function loadSets(targetPage: number, updateStats = false) {
		loading = true;
		try {
			const since = getSinceDate(activePeriod);
			const episode = activePeriod === 'last_ep' ? (stats.latest_episode ?? undefined) : undefined;
			const setsParams = {
				since,
				episode,
				status: statusFilter || undefined,
				sort: 'kill_score',
				order: 'desc',
				limit: PAGE_SIZE,
				offset: (targetPage - 1) * PAGE_SIZE
			};
			if (updateStats) {
				const [setsRes, statsRes] = await Promise.all([
					fetchSets(setsParams),
					fetchSetsStats({ since, episode })
				]);
				sets = setsRes.sets;
				total = setsRes.total;
				stats = statsRes;
			} else {
				const setsRes = await fetchSets(setsParams);
				sets = setsRes.sets;
				total = setsRes.total;
			}
			page = targetPage;
			scoreRangeBin = null;
		} catch {
			// keep current state on error
		} finally {
			loading = false;
		}
	}

	async function selectPeriod(period: TimePeriod) {
		if (period === activePeriod) return;
		activePeriod = period;
		await loadSets(1, true);
	}

	async function changeStatus(newStatus: string) {
		statusFilter = newStatus;
		await loadSets(1, false);
	}
</script>

<svelte:head>
	<title>Sets | Kill Tony Archive</title>
</svelte:head>

<!-- KILL SCORE DISTRIBUTION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Kill Score Distribution</div>
			<div class="s-sub">How scores spread across {stats.total} sets</div>
		</div>
	</div>
	<KillScoreHistogram
		scores={stats.scores.filter((s) => s != null)}
		activeBin={scoreRangeBin}
		onBinClick={(label) => {
			scoreRangeBin = label;
		}}
	/>
</div>

<!-- CROWD BREAKDOWN -->
<div class="section">
	<div class="two-col">
		<div>
			<div class="s-header">
				<div>
					<div class="s-title">Crowd Reactions</div>
					<div class="s-sub">Distribution across all sets</div>
				</div>
			</div>
			<CrowdDistribution reactions={stats.crowd_reactions} />
		</div>
		<div>
			<div class="s-header">
				<div>
					<div class="s-title">Status Breakdown</div>
					<div class="s-sub">Bucket pulls vs regulars</div>
				</div>
			</div>
			<div class="status-cards">
				<div class="status-card">
					<div class="sc-label">Bucket Pulls</div>
					<div class="sc-count">{stats.bucket_count}</div>
					<div class="sc-score">Avg Score: {stats.bucket_avg ?? '—'}</div>
				</div>
				<div class="status-card">
					<div class="sc-label">Regulars</div>
					<div class="sc-count">{stats.regular_count}</div>
					<div class="sc-score">Avg Score: {stats.regular_avg ?? '—'}</div>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- ALL SETS -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Sets</div>
			<div class="s-sub">
				{total} sets · page {page} of {totalPages}
				{#if scoreRangeBin}
					<span class="filter-badge">
						Score {scoreRangeBin}
						<button class="clear-filter" onclick={() => { scoreRangeBin = null; }}>&times;</button>
					</span>
				{/if}
			</div>
		</div>
		<div class="s-badge">{periodLabels[activePeriod]}</div>
	</div>
	<div class="list-controls">
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
		<div class="filter-bar">
			<input
				type="text"
				class="filter-input"
				placeholder="Search comedian..."
				bind:value={searchTerm}
			/>
			<select
				class="filter-select"
				value={statusFilter}
				onchange={(e) => changeStatus((e.target as HTMLSelectElement).value)}
			>
				<option value="">All Status</option>
				<option value="bucket_pull">Bucket Pulls</option>
				<option value="regular">Regulars</option>
			</select>
		</div>
	</div>

	<div class="sets-list" class:loading>
		{#if displaySets().length === 0 && !loading}
			<div class="sets-empty">No sets found.</div>
		{:else}
			{#each displaySets() as s, i}
				<SetCard
					set={s}
					rank={(page - 1) * PAGE_SIZE + i + 1}
					showEpisode={true}
					onJumpTo={s.set_start_seconds != null
						? () => goto(`/episodes/${s.episode_number}#t=${s.set_start_seconds}`)
						: undefined}
				/>
			{/each}
		{/if}
	</div>

	{#if totalPages > 1}
		<div class="pagination">
			<button
				class="page-btn"
				disabled={page <= 1 || loading}
				onclick={() => loadSets(page - 1)}
			>
				← Prev
			</button>
			<span class="page-info">{page} / {totalPages}</span>
			<button
				class="page-btn"
				disabled={page >= totalPages || loading}
				onclick={() => loadSets(page + 1)}
			>
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

	.list-controls {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 16px;
	}

	.period-tabs {
		display: flex;
		gap: 4px;
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

	.filter-bar {
		display: flex;
		gap: 10px;
	}

	.filter-input {
		font-family: var(--mono);
		font-size: 12px;
		background: var(--card);
		border: 1px solid var(--border);
		color: var(--text);
		padding: 8px 14px;
		border-radius: 6px;
		outline: none;
		width: 200px;
		transition: border-color 0.15s;
	}

	.filter-input:focus {
		border-color: var(--red);
	}

	.filter-input::placeholder {
		color: var(--dim);
	}

	.filter-select {
		font-family: var(--mono);
		font-size: 12px;
		background: var(--card);
		border: 1px solid var(--border);
		color: var(--text);
		padding: 8px 14px;
		border-radius: 6px;
		outline: none;
		cursor: pointer;
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

	.sets-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		transition: opacity 0.15s;
	}

	.sets-list.loading {
		opacity: 0.5;
	}

	.sets-empty {
		font-family: var(--mono);
		font-size: 13px;
		color: var(--muted);
		text-align: center;
		padding: 40px 0;
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

	.filter-badge {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--mono);
		font-size: 11px;
		color: var(--red);
		background: var(--red-d);
		border: 1px solid rgba(220, 38, 38, 0.2);
		padding: 2px 10px;
		border-radius: 4px;
		margin-left: 8px;
	}

	.clear-filter {
		background: none;
		border: none;
		color: var(--red);
		font-size: 14px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
		opacity: 0.7;
		transition: opacity 0.15s;
	}

	.clear-filter:hover {
		opacity: 1;
	}

	@media (max-width: 768px) {
		.two-col {
			grid-template-columns: 1fr;
			gap: 0;
		}

		.list-controls {
			flex-direction: column;
			align-items: flex-start;
		}

		.filter-bar {
			flex-direction: column;
			width: 100%;
		}

		.filter-input {
			width: 100%;
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
	}
</style>
