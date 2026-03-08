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

	let hoveredEp: Episode | null = $state(null);
	let tooltipX = $state(0);
	let barsEl: HTMLDivElement | undefined = $state();

	function handleHover(ep: Episode, e: MouseEvent) {
		hoveredEp = ep;
		const bar = e.currentTarget as HTMLElement;
		if (barsEl) {
			const barsRect = barsEl.getBoundingClientRect();
			const barRect = bar.getBoundingClientRect();
			tooltipX = barRect.left + barRect.width / 2 - barsRect.left;
		}
	}
</script>

<div class="ep-wrap">
	<div class="ep-bars" bind:this={barsEl}>
		{#each sorted as ep}
			<a
				href="/episodes/{ep.episode_number}"
				class="ep-bar"
				style="height: {barHeight(ep.avg_kill_score ?? 0)}px; background: rgba(220,38,38,{barAlpha(ep.avg_kill_score ?? 0).toFixed(2)})"
				onmouseenter={(e) => handleHover(ep, e)}
				onmouseleave={() => (hoveredEp = null)}
				role="link"
			></a>
		{/each}
		{#if hoveredEp}
			<div class="tooltip" style="left: {tooltipX}px">
				<div class="tt-ep">Ep #{hoveredEp.episode_number}</div>
				<div class="tt-rows">
					{#if hoveredEp.avg_kill_score != null}
						<div class="tt-row">
							<span class="tt-label">Avg Set Score</span>
							<span class="tt-val">{hoveredEp.avg_kill_score}</span>
						</div>
					{/if}
					{#if hoveredEp.episode_kill_score != null}
						<div class="tt-row">
							<span class="tt-label">Kill Score</span>
							<span class="tt-val">{hoveredEp.episode_kill_score}</span>
						</div>
					{/if}
					<div class="tt-row">
						<span class="tt-label">Sets</span>
						<span class="tt-val">{hoveredEp.set_count}</span>
					</div>
					{#if hoveredEp.laughter_pct != null && hoveredEp.laughter_pct > 0}
						<div class="tt-row">
							<span class="tt-label">Laugh %</span>
							<span class="tt-val">{hoveredEp.laughter_pct.toFixed(1)}%</span>
						</div>
					{/if}
				</div>
			</div>
		{/if}
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
		position: relative;
		display: flex;
		align-items: flex-end;
		height: 80px;
		gap: 0;
		overflow: visible;
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

	.tooltip {
		position: absolute;
		bottom: calc(100% + 10px);
		transform: translateX(-50%);
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 10px 14px;
		pointer-events: none;
		z-index: 10;
		white-space: nowrap;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
	}

	.tooltip::after {
		content: '';
		position: absolute;
		top: 100%;
		left: 50%;
		transform: translateX(-50%);
		border: 5px solid transparent;
		border-top-color: var(--border);
	}

	.tt-ep {
		font-family: var(--mono);
		font-size: 12px;
		font-weight: 700;
		color: var(--red);
		margin-bottom: 6px;
		letter-spacing: -0.3px;
	}

	.tt-rows {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}

	.tt-row {
		display: flex;
		justify-content: space-between;
		gap: 16px;
	}

	.tt-label {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		letter-spacing: 0.3px;
	}

	.tt-val {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 700;
		color: var(--text);
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
