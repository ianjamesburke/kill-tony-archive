<script lang="ts">
	let {
		scores,
		activeBin = null,
		onBinClick,
		maxValue = 30,
		binSize = 2
	}: {
		scores: number[];
		activeBin?: string | null;
		onBinClick?: (label: string | null) => void;
		maxValue?: number;
		binSize?: number;
	} = $props();

	const bins = $derived(() => {
		const buckets: { label: string; min: number; max: number; count: number }[] = [];
		for (let i = 0; i < maxValue; i += binSize) {
			buckets.push({ label: `${i}-${i + binSize}`, min: i, max: i + binSize, count: 0 });
		}
		for (const score of scores) {
			const idx = Math.min(Math.floor(score / binSize), buckets.length - 1);
			buckets[idx].count++;
		}
		return buckets;
	});

	const maxCount = $derived(Math.max(...bins().map((b) => b.count), 1));

	const avgScore = $derived(() => {
		return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
	});
</script>

<div class="histogram">
	<div class="hist-chart">
		{#each bins() as bin}
			<button
				class="hist-col"
				class:active={activeBin === bin.label}
				class:clickable={!!onBinClick && bin.count > 0}
				title="{bin.label}: {bin.count}"
				onclick={() => {
					if (onBinClick && bin.count > 0) {
						onBinClick(activeBin === bin.label ? null : bin.label);
					}
				}}
			>
				<div class="hist-count">{bin.count || ''}</div>
				<div
					class="hist-bar"
					style="height: {bin.count > 0 ? Math.max(4, (bin.count / maxCount) * 140) : 0}px"
					class:empty={bin.count === 0}
				></div>
				<div class="hist-label">{bin.label}</div>
			</button>
		{/each}
	</div>
	<div class="hist-meta">
		<div class="hist-avg-line">
			Mean: <strong>{avgScore().toFixed(1)}</strong>
		</div>
		<div class="hist-note">Score range: 0–{maxValue}</div>
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
		background: none;
		border: none;
		padding: 0;
		cursor: default;
		border-radius: 4px;
		transition: background 0.15s;
	}

	.hist-col.clickable {
		cursor: pointer;
	}

	.hist-col.clickable:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.hist-col.active {
		background: rgba(220, 38, 38, 0.1);
	}

	.hist-col.active .hist-bar {
		background: var(--red);
		box-shadow: 0 0 8px rgba(220, 38, 38, 0.4);
	}

	.hist-count {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--t2);
		margin-bottom: 4px;
		min-height: 14px;
	}

	.hist-bar {
		width: 100%;
		background: linear-gradient(to top, var(--red), var(--red-s));
		border-radius: 3px 3px 0 0;
		transition: height 0.3s ease, box-shadow 0.15s;
		min-width: 8px;
	}

	.hist-bar.empty {
		background: var(--dim2);
		height: 2px !important;
	}

	.hist-label {
		font-family: var(--mono);
		font-size: 9px;
		color: var(--text);
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
