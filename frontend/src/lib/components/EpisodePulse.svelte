<script lang="ts">
	import type { Episode } from '$lib/types';

	let { episodes }: { episodes: Episode[] } = $props();

	const sorted = $derived(
		[...episodes].sort((a, b) => a.episode_number - b.episode_number)
	);

	const maxScore = $derived(
		Math.max(...sorted.map((e) => e.avg_kill_score ?? 0), 1)
	);

	function barAlpha(score: number): number {
		return 0.15 + (score / maxScore) * 0.85;
	}

	function barHeight(score: number): number {
		return Math.max(4, (score / maxScore) * 76);
	}
</script>

<div class="ep-wrap">
	<div class="ep-bars">
		{#each sorted as ep}
			<a
				href="/episodes/{ep.episode_number}"
				class="ep-bar"
				style="height: {barHeight(ep.avg_kill_score ?? 0)}px; background: rgba(220,38,38,{barAlpha(ep.avg_kill_score ?? 0).toFixed(2)})"
				title="Ep #{ep.episode_number} — Avg Score: {ep.avg_kill_score ?? 'N/A'}"
			></a>
		{/each}
	</div>
	<div class="ep-axis">
		{#if sorted.length > 0}
			<span class="ep-era">Ep #{sorted[0].episode_number}</span>
			<span class="ep-era">Ep #{sorted[sorted.length - 1].episode_number}</span>
		{/if}
	</div>
	<div class="ep-legend">
		<div class="ep-leg-item">
			<div class="ep-leg-swatch" style="background: rgba(220,38,38,0.15)"></div>
			Low energy
		</div>
		<div class="ep-leg-item">
			<div class="ep-leg-swatch" style="background: rgba(220,38,38,0.55)"></div>
			Average
		</div>
		<div class="ep-leg-item">
			<div class="ep-leg-swatch" style="background: rgba(220,38,38,1)"></div>
			Peak energy
		</div>
	</div>
</div>

<style>
	.ep-wrap {
		position: relative;
	}

	.ep-bars {
		display: flex;
		align-items: flex-end;
		height: 80px;
		gap: 0;
		overflow: hidden;
		border-radius: 4px;
	}

	.ep-bar {
		flex: 1;
		min-width: 1px;
		transition: opacity 0.1s;
		cursor: pointer;
		display: block;
		text-decoration: none;
	}

	.ep-bar:hover {
		opacity: 0.65;
	}

	.ep-axis {
		display: flex;
		justify-content: space-between;
		margin-top: 10px;
		padding: 0 2px;
	}

	.ep-era {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		letter-spacing: 0.5px;
	}

	.ep-legend {
		display: flex;
		align-items: center;
		gap: 20px;
		margin-top: 14px;
	}

	.ep-leg-item {
		display: flex;
		align-items: center;
		gap: 7px;
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
	}

	.ep-leg-swatch {
		width: 22px;
		height: 5px;
		border-radius: 2px;
	}
</style>
