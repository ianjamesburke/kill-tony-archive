<script lang="ts">
	import type { PageData } from './$types';
	import KillScoreHistogram from '$lib/components/KillScoreHistogram.svelte';
	import CrowdDistribution from '$lib/components/CrowdDistribution.svelte';

	let { data }: { data: PageData } = $props();

	let searchTerm = $state(data.filters.comedian ?? '');
	let statusFilter = $state(data.filters.status ?? '');

	const filteredSets = $derived(() => {
		let sets = data.sets;
		if (searchTerm) {
			const term = searchTerm.toLowerCase();
			sets = sets.filter((s) => s.comedian_name.toLowerCase().includes(term));
		}
		if (statusFilter) {
			sets = sets.filter((s) => s.status === statusFilter);
		}
		return sets;
	});

	function crowdClass(reaction: string | null): string {
		if (!reaction) return 'crowd-low';
		const r = reaction.toLowerCase();
		if (r.includes('roaring') || r.includes('big')) return 'crowd-high';
		if (r.includes('moderate') || r.includes('strong')) return 'crowd-mid';
		return 'crowd-low';
	}

	function formatReaction(reaction: string | null): string {
		if (!reaction) return '—';
		return reaction.replace(/_/g, ' ');
	}

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
	<title>Sets — Kill Tony DB</title>
</svelte:head>

<!-- KILL SCORE DISTRIBUTION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Kill Score Distribution</div>
			<div class="s-sub">How scores spread across all {data.total} sets</div>
		</div>
	</div>
	<KillScoreHistogram sets={data.sets} />
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

<!-- ALL SETS TABLE -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Sets</div>
			<div class="s-sub">{filteredSets().length} sets</div>
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

	<div class="sets-wrap">
		<table class="sets-table">
			<thead>
				<tr>
					<th style="width: 40px">#</th>
					<th>Comedian</th>
					<th>Episode</th>
					<th>Topics</th>
					<th>Crowd</th>
					<th>Status</th>
					<th style="text-align: right">Kill Score</th>
				</tr>
			</thead>
			<tbody>
				{#each filteredSets() as s, i}
					<tr>
						<td class="td-rank">{i + 1}</td>
						<td class="td-name">{s.comedian_name}</td>
						<td>
							<a href="/episodes/{s.episode_number}" class="td-ep">#{s.episode_number}</a>
						</td>
						<td>
							<div class="td-topics">
								{#each s.topic_tags.slice(0, 3) as tag}
									<span class="topic-tag">{tag}</span>
								{/each}
							</div>
						</td>
						<td>
							<span class="td-crowd {crowdClass(s.crowd_reaction)}">
								{formatReaction(s.crowd_reaction)}
							</span>
						</td>
						<td class="td-status">{s.status === 'bucket_pull' ? 'Bucket' : 'Regular'}</td>
						<td>
							<div class="score-cell">
								<div class="score-bar-bg">
									<div
										class="score-bar-fill"
										style="width: {((s.kill_score ?? 0) / 30 * 100).toFixed(0)}%"
									></div>
								</div>
								<span class="td-score">{s.kill_score ?? '—'}</span>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
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

	.sets-wrap {
		overflow: hidden;
		border-radius: 8px;
		border: 1px solid var(--border);
	}

	table.sets-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}

	.sets-table thead tr {
		background: var(--card);
		border-bottom: 1px solid var(--bh);
	}

	.sets-table th {
		font-family: var(--mono);
		font-size: 10px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		padding: 12px 16px;
		text-align: left;
		font-weight: 600;
	}

	.sets-table th:last-child {
		text-align: right;
	}

	.sets-table td {
		padding: 12px 16px;
		border-bottom: 1px solid var(--border);
		vertical-align: middle;
	}

	.sets-table tr:last-child td {
		border-bottom: none;
	}

	.sets-table tbody tr:hover {
		background: rgba(255, 255, 255, 0.025);
	}

	.td-rank {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--dim);
	}

	.td-name {
		font-weight: 600;
	}

	.td-ep {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
		text-decoration: none;
		transition: color 0.15s;
	}

	.td-ep:hover {
		color: var(--red);
	}

	.td-topics {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.td-crowd {
		font-family: var(--mono);
		font-size: 10px;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		font-weight: 600;
	}

	.td-status {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.score-cell {
		display: flex;
		align-items: center;
		gap: 10px;
		justify-content: flex-end;
	}

	.score-bar-bg {
		width: 50px;
		height: 4px;
		background: var(--dim2);
		border-radius: 2px;
		overflow: hidden;
	}

	.score-bar-fill {
		height: 100%;
		background: var(--red);
		border-radius: 2px;
	}

	.td-score {
		font-family: var(--mono);
		font-size: 15px;
		font-weight: 700;
		color: var(--red);
		min-width: 30px;
		text-align: right;
	}
</style>
