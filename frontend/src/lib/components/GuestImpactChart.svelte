<script lang="ts">
	import type { GuestStat } from '$lib/types';

	let { guests, baseline }: { guests: GuestStat[]; baseline: number } = $props();

	const sorted = $derived(
		[...guests]
			.filter((g) => g.bucket_lift != null)
			.sort((a, b) => (b.bucket_lift ?? 0) - (a.bucket_lift ?? 0))
	);

	const maxLift = $derived(Math.max(...sorted.map((g) => Math.abs(g.bucket_lift ?? 0)), 0.1));

	// Chart dimensions
	const chartWidth = 600;
	const barHeight = 36;
	const nameWidth = 160;
	const valueWidth = 50;
	const barAreaWidth = chartWidth - nameWidth - valueWidth;
	const midPoint = barAreaWidth / 2;
</script>

<div class="impact-chart">
	<svg
		width="100%"
		viewBox="0 0 {chartWidth} {sorted.length * barHeight + 40}"
		preserveAspectRatio="xMidYMid meet"
	>
		<!-- Baseline line -->
		<line
			x1={nameWidth + midPoint}
			y1="0"
			x2={nameWidth + midPoint}
			y2={sorted.length * barHeight + 20}
			stroke="var(--dim)"
			stroke-width="1"
			stroke-dasharray="4,4"
		/>

		<!-- Baseline label -->
		<text
			x={nameWidth + midPoint}
			y={sorted.length * barHeight + 34}
			text-anchor="middle"
			fill="var(--dim)"
			font-family="var(--mono)"
			font-size="9"
		>
			BASELINE ({baseline})
		</text>

		{#each sorted as guest, i}
			{@const lift = guest.bucket_lift ?? 0}
			{@const barW = (Math.abs(lift) / maxLift) * (midPoint - 10)}
			{@const isPositive = lift >= 0}
			{@const y = i * barHeight + 8}

			<!-- Guest name -->
			<text
				x={nameWidth - 10}
				y={y + barHeight / 2 - 2}
				text-anchor="end"
				fill="var(--t2)"
				font-family="var(--sans)"
				font-size="13"
				font-weight="600"
			>
				{guest.guest_name}
			</text>

			<!-- Bar -->
			<rect
				x={isPositive ? nameWidth + midPoint : nameWidth + midPoint - barW}
				y={y + 4}
				width={barW}
				height={barHeight - 12}
				rx="3"
				fill={isPositive ? 'var(--green)' : 'var(--red)'}
				opacity="0.8"
			/>

			<!-- Value label -->
			<text
				x={isPositive
					? nameWidth + midPoint + barW + 8
					: nameWidth + midPoint - barW - 8}
				y={y + barHeight / 2 - 2}
				text-anchor={isPositive ? 'start' : 'end'}
				fill={isPositive ? 'var(--green)' : 'var(--red-s)'}
				font-family="var(--mono)"
				font-size="12"
				font-weight="700"
			>
				{lift > 0 ? '+' : ''}{lift}
			</text>
		{/each}
	</svg>
</div>

<div class="impact-legend">
	<div class="impact-leg-item">
		<div class="impact-swatch" style="background: var(--green)"></div>
		Bucket pulls scored above average with this guest
	</div>
	<div class="impact-leg-item">
		<div class="impact-swatch" style="background: var(--red)"></div>
		Bucket pulls scored below average with this guest
	</div>
</div>

<style>
	.impact-chart {
		max-width: 700px;
		margin: 0 auto;
	}

	.impact-legend {
		display: flex;
		gap: 24px;
		margin-top: 16px;
		justify-content: center;
	}

	.impact-leg-item {
		display: flex;
		align-items: center;
		gap: 8px;
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
	}

	.impact-swatch {
		width: 14px;
		height: 6px;
		border-radius: 3px;
	}
</style>
