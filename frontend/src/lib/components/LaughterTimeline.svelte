<script lang="ts">
	import type { LaughterTimeline } from '$lib/types';

	let {
		data,
		onJumpTo
	}: {
		data: LaughterTimeline;
		onJumpTo: (seconds: number) => void;
	} = $props();

	const WIDTH = 1200;
	const HEIGHT = 120;
	const PAD_TOP = 8;
	const PAD_BOTTOM = 24;
	const CHART_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

	const maxTime = $derived(data.timeline[data.timeline.length - 1]?.t ?? 0);

	// Smooth the data with a rolling window for a nicer curve
	const SMOOTH_WINDOW = 3;
	const smoothed = $derived.by(() => {
		const pts = data.timeline;
		return pts.map((p, i) => {
			let sum = 0;
			let count = 0;
			for (
				let j = Math.max(0, i - SMOOTH_WINDOW);
				j <= Math.min(pts.length - 1, i + SMOOTH_WINDOW);
				j++
			) {
				sum += pts[j].v;
				count++;
			}
			return { t: p.t, v: sum / count };
		});
	});

	const maxVal = $derived(Math.max(...smoothed.map((p) => p.v), 0.01));

	function x(t: number): number {
		return (t / maxTime) * WIDTH;
	}

	function y(v: number): number {
		return PAD_TOP + CHART_H - (v / maxVal) * CHART_H;
	}

	const areaPath = $derived.by(() => {
		if (smoothed.length === 0) return '';
		const pts = smoothed.map((p) => `${x(p.t)},${y(p.v)}`).join(' L');
		const baseline = PAD_TOP + CHART_H;
		return `M${x(smoothed[0].t)},${baseline} L${pts} L${x(smoothed[smoothed.length - 1].t)},${baseline} Z`;
	});

	const linePath = $derived.by(() => {
		if (smoothed.length === 0) return '';
		return 'M' + smoothed.map((p) => `${x(p.t)},${y(p.v)}`).join(' L');
	});

	// Time axis labels
	const timeLabels = $derived.by(() => {
		const interval = maxTime > 5400 ? 600 : maxTime > 2700 ? 300 : 120;
		const labels: { t: number; label: string }[] = [];
		for (let t = 0; t <= maxTime; t += interval) {
			const m = Math.floor(t / 60);
			labels.push({ t, label: `${m}m` });
		}
		return labels;
	});

	let hoverX = $state<number | null>(null);
	let hoverTime = $state<number | null>(null);
	let hoverSet = $state<(typeof data.sets)[0] | null>(null);

	function handleMouseMove(e: MouseEvent) {
		const svg = (e.currentTarget as SVGElement).getBoundingClientRect();
		const ratio = (e.clientX - svg.left) / svg.width;
		const t = ratio * maxTime;
		hoverX = ratio * WIDTH;
		hoverTime = t;
		hoverSet = data.sets.find((s) => t >= s.start && t <= s.end) ?? null;
	}

	function handleMouseLeave() {
		hoverX = null;
		hoverTime = null;
		hoverSet = null;
	}

	function handleClick(e: MouseEvent) {
		const svg = (e.currentTarget as SVGElement).getBoundingClientRect();
		const ratio = (e.clientX - svg.left) / svg.width;
		onJumpTo(Math.round(ratio * maxTime));
	}

	function handleSetClick(seconds: number, e: MouseEvent) {
		e.stopPropagation();
		onJumpTo(seconds);
	}

	function formatTime(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}
</script>

<div class="timeline-wrap">
	<div class="timeline-header">
		<div class="timeline-title">Timeline</div>
		<div class="timeline-legend">
			<span class="legend-swatch"></span>
			<span class="legend-label">Laughter</span>
		</div>
	</div>

	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<svg
		viewBox="0 0 {WIDTH} {HEIGHT}"
		class="timeline-svg"
		onmousemove={handleMouseMove}
		onmouseleave={handleMouseLeave}
		onclick={handleClick}
	>
		<defs>
			<linearGradient id="laugh-grad" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="var(--red)" stop-opacity="0.6" />
				<stop offset="100%" stop-color="var(--red)" stop-opacity="0.03" />
			</linearGradient>
		</defs>

		<!-- Set regions -->
		{#each data.sets as s}
			{@const sx = x(s.start)}
			{@const sw = x(s.end) - x(s.start)}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<g class="set-region" onclick={(e) => handleSetClick(s.start, e)}>
				<rect
					x={sx}
					y={PAD_TOP}
					width={sw}
					height={CHART_H}
					class="set-band"
					class:regular={s.status === 'regular'}
				/>
				</g>
		{/each}

		<!-- Area fill -->
		<path d={areaPath} fill="url(#laugh-grad)" />

		<!-- Line -->
		<path d={linePath} fill="none" stroke="var(--red)" stroke-width="1.5" opacity="0.8" />

		<!-- Time axis -->
		{#each timeLabels as label}
			<line
				x1={x(label.t)}
				y1={PAD_TOP + CHART_H}
				x2={x(label.t)}
				y2={PAD_TOP + CHART_H + 4}
				stroke="var(--dim)"
				stroke-width="1"
			/>
			<text x={x(label.t)} y={HEIGHT - 4} class="axis-label" text-anchor="middle">
				{label.label}
			</text>
		{/each}

		<!-- Baseline -->
		<line
			x1={0}
			y1={PAD_TOP + CHART_H}
			x2={WIDTH}
			y2={PAD_TOP + CHART_H}
			stroke="var(--border)"
			stroke-width="1"
		/>

		<!-- Hover cursor -->
		{#if hoverX !== null}
			<line
				x1={hoverX}
				y1={PAD_TOP}
				x2={hoverX}
				y2={PAD_TOP + CHART_H}
				stroke="var(--muted)"
				stroke-width="1"
				stroke-dasharray="3,3"
				pointer-events="none"
			/>
		{/if}
	</svg>

	<!-- Tooltip -->
	{#if hoverTime !== null}
		<div class="tooltip" style="left: {((hoverX ?? 0) / WIDTH) * 100}%">
			<span class="tooltip-time">{formatTime(hoverTime)}</span>
			{#if hoverSet}
				<span class="tooltip-set">{hoverSet.comedian_name}</span>
			{/if}
		</div>
	{/if}

</div>

<style>
	.timeline-wrap {
		position: relative;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 16px 20px 12px;
	}

	.timeline-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	.timeline-title {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.timeline-legend {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.legend-swatch {
		display: inline-block;
		width: 24px;
		height: 2px;
		background: var(--red);
		border-radius: 1px;
		opacity: 0.8;
	}

	.legend-label {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		letter-spacing: 0.5px;
	}

	.timeline-svg {
		width: 100%;
		height: auto;
		cursor: crosshair;
		display: block;
	}

	.set-band {
		fill: rgba(255, 255, 255, 0.03);
		stroke: var(--dim);
		stroke-width: 0.5;
		cursor: pointer;
		transition: fill 0.15s;
	}

	.set-band:hover {
		fill: rgba(255, 255, 255, 0.08);
	}

	.set-band.regular {
		fill: rgba(220, 38, 38, 0.06);
		stroke: rgba(220, 38, 38, 0.2);
	}

	.set-band.regular:hover {
		fill: rgba(220, 38, 38, 0.12);
	}


	.axis-label {
		font-family: var(--mono);
		font-size: 8px;
		fill: var(--dim);
	}

	.set-region {
		cursor: pointer;
	}

	.tooltip {
		position: absolute;
		top: 36px;
		transform: translateX(-50%);
		background: var(--raised);
		border: 1px solid var(--bh);
		border-radius: 6px;
		padding: 5px 10px;
		display: flex;
		gap: 8px;
		align-items: center;
		pointer-events: none;
		z-index: 10;
		white-space: nowrap;
	}

	.tooltip-time {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		color: var(--text);
	}

	.tooltip-set {
		font-size: 11px;
		color: var(--t2);
	}

</style>
