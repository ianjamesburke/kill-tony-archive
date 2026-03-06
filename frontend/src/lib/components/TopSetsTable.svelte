<script lang="ts">
	import type { ComedySet } from '$lib/types';

	let { sets }: { sets: ComedySet[] } = $props();

	const maxScore = $derived(Math.max(...sets.map((s) => s.kill_score ?? 0), 1));

	function crowdClass(reaction: string | null): string {
		if (!reaction) return 'crowd-low';
		const r = reaction.toLowerCase();
		if (r.includes('roaring') || r.includes('eruption') || r.includes('big'))
			return 'crowd-high';
		if (r.includes('moderate') || r.includes('strong')) return 'crowd-mid';
		return 'crowd-low';
	}
</script>

<div class="sets-wrap">
	<table class="sets-table">
		<thead>
			<tr>
				<th style="width: 40px">#</th>
				<th>Comedian</th>
				<th>Topics</th>
				<th>Crowd</th>
				<th style="text-align: right">Kill Score</th>
			</tr>
		</thead>
		<tbody>
			{#each sets as s, i}
				<tr>
					<td class="td-rank" class:top-three={i < 3}>{i + 1}</td>
					<td>
						<div class="td-name">{s.comedian_name}</div>
						<a href="/episodes/{s.episode_number}" class="td-ep">Ep #{s.episode_number}</a>
					</td>
					<td>
						<div class="td-topics">
							{#each s.topic_tags as tag}
								<span class="topic-tag">{tag}</span>
							{/each}
						</div>
					</td>
					<td>
						<span class="td-crowd {crowdClass(s.crowd_reaction)}">
							{s.crowd_reaction ?? '—'}
						</span>
					</td>
					<td>
						<div class="score-bar-wrap">
							<div class="score-bar-bg">
								<div
									class="score-bar-fill"
									style="width: {((s.kill_score ?? 0) / maxScore * 100).toFixed(0)}%"
								></div>
							</div>
							<div class="td-score">{s.kill_score ?? '—'}</div>
						</div>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
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
		padding: 12px 18px;
		text-align: left;
		font-weight: 600;
	}

	.sets-table th:last-child,
	.sets-table td:last-child {
		text-align: right;
	}

	.sets-table td {
		padding: 14px 18px;
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
		font-size: 13px;
		font-weight: 700;
		color: var(--muted);
		width: 40px;
	}

	.td-rank.top-three {
		color: var(--amber);
	}

	.td-name {
		font-weight: 600;
		font-size: 14px;
	}

	.td-ep {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-top: 2px;
		text-decoration: none;
		display: block;
		transition: color 0.15s;
	}

	.td-ep:hover {
		color: var(--red);
	}

	.td-topics {
		display: flex;
		gap: 5px;
		flex-wrap: wrap;
	}

	.td-crowd {
		font-family: var(--mono);
		font-size: 10px;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		font-weight: 600;
	}

	.td-score {
		font-family: var(--mono);
		font-size: 17px;
		font-weight: 700;
		letter-spacing: -0.5px;
		color: var(--red);
	}

	.score-bar-wrap {
		display: flex;
		align-items: center;
		gap: 10px;
		justify-content: flex-end;
	}

	.score-bar-bg {
		flex: 1;
		height: 4px;
		background: var(--dim2);
		border-radius: 2px;
		overflow: hidden;
		max-width: 60px;
	}

	.score-bar-fill {
		height: 100%;
		background: var(--red);
		border-radius: 2px;
	}
</style>
