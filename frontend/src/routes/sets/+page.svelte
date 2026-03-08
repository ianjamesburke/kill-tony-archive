<script lang="ts">
	import type { PageData } from './$types';
	import KillScoreHistogram from '$lib/components/KillScoreHistogram.svelte';
	import CrowdDistribution from '$lib/components/CrowdDistribution.svelte';
	import SetCard from '$lib/components/SetCard.svelte';
	import { goto } from '$app/navigation';

	let { data }: { data: PageData } = $props();

	let searchTerm = $state(data.filters.comedian ?? '');
	let statusFilter = $state(data.filters.status ?? '');
	let scoreRangeBin: string | null = $state(null);

	const filteredSets = $derived(() => {
		let sets = data.sets;
		if (searchTerm) {
			const term = searchTerm.toLowerCase();
			sets = sets.filter((s) => s.comedian_name.toLowerCase().includes(term));
		}
		if (statusFilter) {
			sets = sets.filter((s) => s.status === statusFilter);
		}
		if (scoreRangeBin) {
			const [minStr, maxStr] = scoreRangeBin.split('-');
			const min = parseInt(minStr, 10);
			const max = parseInt(maxStr, 10);
			sets = sets.filter((s) => {
				const score = s.kill_score ?? 0;
				return score >= min && score < max;
			});
		}
		return sets;
	});

	const bucketSets = $derived(data.sets.filter((s) => s.status === 'bucket_pull'));
	const regularSets = $derived(data.sets.filter((s) => s.status === 'regular'));
	const bucketAvg = $derived(
		bucketSets.length > 0
			? (bucketSets.reduce((sum, x) => sum + (x.kill_score ?? 0), 0) / bucketSets.length).toFixed(1)
			: '—'
	);
	const regularAvg = $derived(
		regularSets.length > 0
			? (regularSets.reduce((sum, x) => sum + (x.kill_score ?? 0), 0) / regularSets.length).toFixed(1)
			: '—'
	);
</script>

<svelte:head>
	<title>Sets | Kill Tony Archive</title>
</svelte:head>

<!-- KILL SCORE DISTRIBUTION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Kill Score Distribution</div>
			<div class="s-sub">How scores spread across all {data.total} sets</div>
		</div>
	</div>
	<KillScoreHistogram
		scores={data.sets.filter((s) => s.kill_score != null).map((s) => s.kill_score!)}
		activeBin={scoreRangeBin}
		onBinClick={(label) => { scoreRangeBin = label; }}
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
			<CrowdDistribution reactions={data.crowdReactions} />
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
					<div class="sc-count">{bucketSets.length}</div>
					<div class="sc-score">Avg Score: {bucketAvg}</div>
				</div>
				<div class="status-card">
					<div class="sc-label">Regulars</div>
					<div class="sc-count">{regularSets.length}</div>
					<div class="sc-score">Avg Score: {regularAvg}</div>
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
				{filteredSets().length} sets{#if scoreRangeBin}
					<span class="filter-badge">
						Score {scoreRangeBin}
						<button class="clear-filter" onclick={() => { scoreRangeBin = null; }}>&times;</button>
					</span>
				{/if}
			</div>
		</div>
		<div class="filter-bar">
			<input
				type="text"
				class="filter-input"
				placeholder="Search comedian..."
				bind:value={searchTerm}
			/>
			<select class="filter-select" bind:value={statusFilter}>
				<option value="">All Status</option>
				<option value="bucket_pull">Bucket Pulls</option>
				<option value="regular">Regulars</option>
			</select>
		</div>
	</div>

	<div class="sets-list">
		{#each filteredSets() as s, i}
			<SetCard
				set={s}
				rank={i + 1}
				showEpisode={true}
				onJumpTo={s.set_start_seconds != null
					? () => goto(`/episodes/${s.episode_number}#t=${s.set_start_seconds}`)
					: undefined}
			/>
		{/each}
	</div>
</div>

<style>
	.two-col {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 40px;
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
	}
</style>
