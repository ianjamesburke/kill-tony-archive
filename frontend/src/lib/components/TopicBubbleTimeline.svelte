<script lang="ts">
	import type { TopicTimelineEntry, TopicStat } from '$lib/types';
	import { onMount, onDestroy } from 'svelte';

	let {
		timeline,
		totals
	}: {
		timeline: TopicTimelineEntry[];
		totals: TopicStat[];
	} = $props();

	const TOPIC_COLORS: Record<string, string> = {
		sex: '#ef4444',
		relationships: '#f97316',
		dating: '#fb923c',
		family: '#f59e0b',
		self_deprecation: '#eab308',
		observational: '#84cc16',
		storytelling: '#22c55e',
		crowd_work: '#14b8a6',
		absurdist: '#06b6d4',
		meta: '#3b82f6',
		politics: '#6366f1',
		race: '#8b5cf6',
		religion: '#a78bfa',
		drugs: '#c084fc',
		shock_humor: '#ec4899',
		physical: '#f43f5e',
		regional: '#78716c',
		aging: '#a8a29e',
		lgbtq: '#e879f9',
		crime: '#64748b',
		work: '#0ea5e9',
		food: '#facc15',
		disability: '#94a3b8',
		other: '#6b7280'
	};

	const WINDOW = 5;
	const TOP_N = 12;
	const CX = 250;
	const CY = 140;
	const MIN_R = 14;
	const MAX_R = 52;
	const ANIM_INTERVAL_MS = 400;

	const topTopics = $derived(totals.slice(0, TOP_N).map((t) => t.topic));

	const frames = $derived.by(() => {
		if (timeline.length === 0) return [];
		return timeline.map((entry, idx) => {
			const windowStart = Math.max(0, idx - WINDOW + 1);
			const windowSlice = timeline.slice(windowStart, idx + 1);
			const windowSize = windowSlice.length;
			const avgTopics: Record<string, number> = {};
			for (const topic of topTopics) {
				const sum = windowSlice.reduce((s, e) => s + (e.topics[topic] ?? 0), 0);
				avgTopics[topic] = sum / windowSize;
			}
			return { episode_number: entry.episode_number, date: entry.date, topics: avgTopics };
		});
	});

	let sliderIdx = $state(0);
	let playing = $state(false);
	let animTimer: ReturnType<typeof setInterval> | null = null;

	// Stable positions: keyed by topic, persisted across frames
	let positions: Record<string, { x: number; y: number }> = {};

	// Initialize positions for all topics in a circle layout
	function initPositions() {
		topTopics.forEach((topic, i) => {
			if (!positions[topic]) {
				const angle = (i / topTopics.length) * Math.PI * 2 - Math.PI / 2;
				const dist = 60;
				positions[topic] = {
					x: CX + Math.cos(angle) * dist,
					y: CY + Math.sin(angle) * dist
				};
			}
		});
	}

	const currentFrame = $derived(frames[sliderIdx] ?? frames[frames.length - 1]);

	// Compute target radii for current frame — always returns a value for every topic
	const targetRadii = $derived.by(() => {
		if (!currentFrame) return {};
		const vals = topTopics.map((t) => currentFrame.topics[t] ?? 0);
		const maxVal = Math.max(...vals, 0.1);
		const radii: Record<string, number> = {};
		for (const topic of topTopics) {
			const v = currentFrame.topics[topic] ?? 0;
			radii[topic] = v > 0.05 ? MIN_R + (v / maxVal) * (MAX_R - MIN_R) : 0;
		}
		return radii;
	});

	// Run physics packing — only moves active bubbles, inactive stay put
	function packBubbles(radii: Record<string, number>) {
		initPositions();
		const active = topTopics.filter((t) => (radii[t] ?? 0) > 0);

		for (let iter = 0; iter < 80; iter++) {
			for (const t of active) {
				const p = positions[t];
				p.x += (CX - p.x) * 0.03;
				p.y += (CY - p.y) * 0.03;
			}
			for (let i = 0; i < active.length; i++) {
				for (let j = i + 1; j < active.length; j++) {
					const a = positions[active[i]];
					const b = positions[active[j]];
					const ra = radii[active[i]] ?? 0;
					const rb = radii[active[j]] ?? 0;
					const dx = b.x - a.x;
					const dy = b.y - a.y;
					const dist = Math.sqrt(dx * dx + dy * dy) || 1;
					const minDist = ra + rb + 3;
					if (dist < minDist) {
						const push = (minDist - dist) / 2;
						const nx = dx / dist;
						const ny = dy / dist;
						a.x -= nx * push;
						a.y -= ny * push;
						b.x += nx * push;
						b.y += ny * push;
					}
				}
			}
		}
	}

	// Estimate font size that fits label inside a circle of radius r
	function labelFontSize(label: string, r: number): number {
		// Approximate: usable width inside circle ≈ r * 1.4 (chord at center)
		// Each character ≈ 0.6em wide in monospace
		const maxWidth = r * 1.4;
		const charCount = label.length;
		const sizeFromWidth = maxWidth / (charCount * 0.6);
		// Also cap to ~40% of radius so it doesn't get too tall
		const sizeFromHeight = r * 0.4;
		return Math.min(sizeFromWidth, sizeFromHeight, 12);
	}

	// Rendered bubble data — ALL topics always present
	interface Bubble {
		topic: string;
		x: number;
		y: number;
		r: number;
		color: string;
		label: string;
		fontSize: number;
		active: boolean;
	}
	let renderedBubbles: Bubble[] = $state([]);

	// Recompute whenever frame changes
	$effect(() => {
		const radii = targetRadii;
		if (!currentFrame || Object.keys(radii).length === 0) return;
		packBubbles(radii);
		renderedBubbles = topTopics.map((topic) => {
			const r = radii[topic] ?? 0;
			const label = topic.replace(/_/g, ' ');
			return {
				topic,
				x: positions[topic]?.x ?? CX,
				y: positions[topic]?.y ?? CY,
				r,
				color: TOPIC_COLORS[topic] ?? '#6b7280',
				label,
				fontSize: labelFontSize(label, r),
				active: r > 0
			};
		});
	});

	function startAutoPlay() {
		playing = true;
		sliderIdx = 0;
		animTimer = setInterval(() => {
			if (sliderIdx >= frames.length - 1) {
				stopAutoPlay();
				return;
			}
			sliderIdx++;
		}, ANIM_INTERVAL_MS);
	}

	function stopAutoPlay() {
		playing = false;
		if (animTimer) {
			clearInterval(animTimer);
			animTimer = null;
		}
	}

	function togglePlay() {
		if (playing) {
			stopAutoPlay();
		} else {
			if (sliderIdx >= frames.length - 1) sliderIdx = 0;
			startAutoPlay();
		}
	}

	function handleSliderInput() {
		if (playing) stopAutoPlay();
	}

	onMount(() => {
		initPositions();
		if (frames.length > 1) {
			setTimeout(() => startAutoPlay(), 600);
		}
	});

	onDestroy(() => {
		if (animTimer) clearInterval(animTimer);
	});

	function formatTopic(topic: string): string {
		return topic.replace(/_/g, ' ');
	}

	function formatDate(dateStr: string | null | undefined): string {
		if (!dateStr) return '';
		// dateStr is YYYYMMDD format
		if (dateStr.length === 8) {
			const y = dateStr.slice(0, 4);
			const m = dateStr.slice(4, 6);
			const d = dateStr.slice(6, 8);
			return `${m}/${d}/${y}`;
		}
		return dateStr;
	}
</script>

<div class="topic-timeline">
	<div class="bubble-area">
		<svg width="100%" viewBox="0 0 500 280" preserveAspectRatio="xMidYMid meet">
			{#each renderedBubbles as bubble (bubble.topic)}
				<g
					class="bubble-group"
					style="transform: translate({bubble.x}px, {bubble.y}px)"
				>
					<circle
						r={bubble.r}
						fill={bubble.color}
						opacity={bubble.active ? 0.15 : 0}
						stroke={bubble.color}
						stroke-width="1.5"
						stroke-opacity={bubble.active ? 1 : 0}
					/>
					<text
						text-anchor="middle"
						dominant-baseline="middle"
						fill={bubble.color}
						font-family="var(--mono)"
						font-size={bubble.fontSize}
						font-weight="600"
						opacity={bubble.fontSize >= 4 ? 0.9 : 0}
					>
						{bubble.label}
					</text>
				</g>
			{/each}
		</svg>
	</div>

	<div class="slider-area">
		<div class="slider-label">
			<div class="slider-left">
				<button class="play-btn" onclick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
					{#if playing}
						<svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
							<rect x="3" y="2" width="4" height="12" rx="1" />
							<rect x="9" y="2" width="4" height="12" rx="1" />
						</svg>
					{:else}
						<svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
							<path d="M4 2l10 6-10 6V2z" />
						</svg>
					{/if}
				</button>
				<span class="slider-ep">#{currentFrame?.episode_number ?? '—'}</span>
				{#if currentFrame?.date}
					<span class="slider-date">{formatDate(currentFrame.date)}</span>
				{/if}
			</div>
			<span class="slider-window">{WINDOW}-ep rolling avg</span>
		</div>
		<input
			type="range"
			class="timeline-slider"
			min="0"
			max={Math.max(frames.length - 1, 0)}
			bind:value={sliderIdx}
			oninput={handleSliderInput}
		/>
		<div class="slider-range">
			<span>#{frames[0]?.episode_number ?? '—'}</span>
			<span>#{frames[frames.length - 1]?.episode_number ?? '—'}</span>
		</div>
	</div>

	<div class="topic-legend">
		{#each topTopics as topic}
			<div class="legend-item" class:dim={!renderedBubbles.some((b) => b.topic === topic && b.active)}>
				<div class="legend-dot" style="background: {TOPIC_COLORS[topic] ?? '#6b7280'}"></div>
				<span class="legend-label">{formatTopic(topic)}</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.topic-timeline {
		display: flex;
		flex-direction: column;
		gap: 0;
		height: 100%;
	}

	.bubble-area {
		flex: 1;
		min-height: 0;
	}

	.bubble-area svg {
		width: 100%;
		height: 100%;
	}

	.bubble-group {
		transition: transform 0.7s cubic-bezier(0.25, 0.1, 0.25, 1);
	}

	.bubble-group circle {
		transition:
			r 0.7s cubic-bezier(0.25, 0.1, 0.25, 1),
			opacity 0.7s cubic-bezier(0.25, 0.1, 0.25, 1),
			stroke-opacity 0.7s cubic-bezier(0.25, 0.1, 0.25, 1);
	}

	.bubble-group text {
		transition:
			opacity 0.7s cubic-bezier(0.25, 0.1, 0.25, 1),
			font-size 0.7s cubic-bezier(0.25, 0.1, 0.25, 1);
		pointer-events: none;
	}

	.slider-area {
		padding: 0 4px;
	}

	.slider-label {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 6px;
	}

	.slider-left {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.play-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 1px solid var(--border);
		background: var(--card);
		color: var(--muted);
		cursor: pointer;
		transition: border-color 0.15s, color 0.15s, background 0.15s;
	}

	.play-btn:hover {
		border-color: var(--bh);
		color: var(--red);
		background: var(--raised);
	}

	.slider-ep {
		font-family: var(--mono);
		font-size: 13px;
		font-weight: 700;
		letter-spacing: -0.5px;
	}

	.slider-date {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--dim);
		letter-spacing: -0.3px;
	}

	.slider-window {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--dim);
	}

	.timeline-slider {
		width: 100%;
		height: 4px;
		-webkit-appearance: none;
		appearance: none;
		background: var(--border);
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}

	.timeline-slider::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--red);
		border: 2px solid var(--bg);
		cursor: grab;
	}

	.timeline-slider::-moz-range-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--red);
		border: 2px solid var(--bg);
		cursor: grab;
	}

	.slider-range {
		display: flex;
		justify-content: space-between;
		font-family: var(--mono);
		font-size: 9px;
		color: var(--dim);
		margin-top: 4px;
	}

	.topic-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 12px;
		margin-top: 16px;
		justify-content: center;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 5px;
		transition: opacity 0.3s;
	}

	.legend-item.dim {
		opacity: 0.3;
	}

	.legend-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.legend-label {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		text-transform: capitalize;
	}

	@media (max-width: 768px) {
		.bubble-area {
			min-height: 280px;
		}
	}
</style>
