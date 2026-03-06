<script lang="ts">
	import type { ComedySet } from '$lib/types';

	let { sets }: { sets: ComedySet[] } = $props();

	const bins = $derived(() => {
		const buckets: { label: string; min: number; max: number; count: number; sets: ComedySet[] }[] =
			[];
		for (let i = 0; i <= 28; i += 2) {
			buckets.push({
				label: `${i}-${i + 2}`,
				min: i,
				max: i + 2,
				count: 0,
				sets: []
			});
		}
		for (const s of sets) {
			const score = s.kill_score ?? 0;
			const idx = Math.min(Math.floor(score / 2), buckets.length - 1);
			buckets[idx].count++;
			buckets[idx].sets.push(s);
		}
		return buckets;
	});

	const maxCount = $derived(Math.max(...bins().map((b) => b.count), 1));

	const avgScore = $derived(() => {
		const scores = sets.filter((s) => s.kill_score != null).map((s) => s.kill_score!);
		return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
	});
</script>

<div class="histogram">
	<div class="hist-chart">
		{#each bins() as bin}
			<div class="hist-col" title="{bin.label}: {bin.count} sets">
				<div class="hist-count">{bin.count || ''}</div>
				<div
					class="hist-bar"
					style="height: {bin.count > 0 ? Math.max(4, (bin.count / maxCount) * 140) : 0}px"
					class:empty={bin.count === 0}
				></div>
				<div class="hist-label">{bin.label}</div>
			</div>
		{/each}
	</div>
	<div class="hist-meta">
		<div class="hist-avg-line">
			Mean: <strong>{avgScore().toFixed(1)}</strong>
		</div>
		<div class="hist-note">Kill Score range: 0–29</div>
	</div>
</div>

<style>
	.histogram {
		width: 100%;
	}

	.hist-chart {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		height: 180px;
		padding-bottom: 24px;
		position: relative;
	}

	.hist-col {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-end;
		height: 100%;
		position: relative;
	}

	.hist-count {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		margin-bottom: 4px;
		min-height: 14px;
	}

	.hist-bar {
		width: 100%;
		background: linear-gradient(to top, var(--red), var(--red-s));
		border-radius: 3px 3px 0 0;
		transition: height 0.3s ease;
		min-width: 8px;
	}

	.hist-bar.empty {
		background: var(--dim2);
		height: 2px !important;
	}

	.hist-label {
		font-family: var(--mono);
		font-size: 9px;
		color: var(--dim);
		margin-top: 6px;
		position: absolute;
		bottom: 0;
	}

	.hist-meta {
		display: flex;
		justify-content: space-between;
		margin-top: 12px;
		padding-top: 12px;
		border-top: 1px solid var(--border);
	}

	.hist-avg-line {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--t2);
	}

	.hist-avg-line strong {
		color: var(--red);
	}

	.hist-note {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--dim);
	}
</style>
