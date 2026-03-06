<script lang="ts">
	import type { PageData } from './$types';
	import SetCard from '$lib/components/SetCard.svelte';
	import LaughterTimeline from '$lib/components/LaughterTimeline.svelte';
	import { onMount, tick } from 'svelte';

	let { data }: { data: PageData } = $props();

	const ep = $derived(data.episode);
	const sets = $derived(data.sets);
	const laughterTimeline = $derived(data.laughterTimeline);

	let videoStart = $state(0);

	onMount(async () => {
		const match = window.location.hash.match(/t=(\d+)/);
		if (match) {
			videoStart = parseInt(match[1], 10);
			await tick();
			document.getElementById('video-section')?.scrollIntoView({ behavior: 'smooth' });
		}
	});

	const embedUrl = $derived(
		ep.video_id
			? `https://www.youtube.com/embed/${ep.video_id}?start=${videoStart}&autoplay=${videoStart > 0 ? 1 : 0}&enablejsapi=1`
			: null
	);

	function jumpTo(seconds: number) {
		videoStart = seconds;
		document.getElementById('video-section')?.scrollIntoView({ behavior: 'smooth' });
	}

	function formatTime(seconds: number | null): string {
		if (seconds == null) return '—';
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const s = Math.floor(seconds % 60);
		if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}
</script>

<svelte:head>
	<title>Kill Tony DB</title>
</svelte:head>

<div class="ep-hero">
	<div class="ep-hero-left">
		<a href="/episodes" class="back-btn">
			<svg class="back-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M10 12L6 8L10 4" />
			</svg>
			All Episodes
		</a>
		<h1 class="ep-number">#{ep.episode_number}</h1>
		{#if ep.guests.length > 0}
			<div class="ep-guests">
				{#each ep.guests as guest}
					<a href="/guests/{encodeURIComponent(guest)}" class="guest-chip-hero">{guest}</a>
				{/each}
			</div>
		{/if}
		{#if ep.date || ep.venue}
			<div class="ep-meta-row">
				{#if ep.date}<span class="ep-date">{ep.date}</span>{/if}
				{#if ep.venue}<span class="ep-venue">{ep.venue}</span>{/if}
			</div>
		{/if}
		<div class="ep-pills">
			<span class="ep-pill">
				<svg class="pill-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1C6.9 1 6 1.9 6 3v5c0 1.1.9 2 2 2s2-.9 2-2V3c0-1.1-.9-2-2-2zM12 8c0 2.2-1.8 4-4 4s-4-1.8-4-4H3c0 2.5 1.8 4.6 4.2 5v2h1.6v-2C11.2 12.6 13 10.5 13 8h-1z"/></svg>
				{ep.set_count} sets
			</span>
			{#if ep.laughter_pct != null && ep.laughter_pct > 0}
				<span class="ep-pill laugh">
					{ep.laughter_pct.toFixed(1)}% laughs
				</span>
			{/if}
		</div>
		{#if ep.episode_summary}
			<p class="ep-summary">{ep.episode_summary}</p>
		{:else}
			<p class="ep-summary placeholder">Episode summary will be generated after analysis.</p>
		{/if}
	</div>
	<div class="ep-hero-stats">
		{#if ep.episode_rank != null && ep.total_episodes != null}
			<div class="stat-row rank-row">
				<div class="stat-label">Episode Rank</div>
				<div class="stat-rank">
					<span class="rank-num">#{ep.episode_rank}</span>
					<span class="rank-total">of {ep.total_episodes}</span>
				</div>
			</div>
		{/if}
		<div class="stat-row">
			<div class="stat-label">Kill Score</div>
			<div class="stat-val">{ep.episode_kill_score ?? '—'}<span class="score-max">/100</span></div>
		</div>
		<div class="stat-row">
			<div class="stat-label">Avg Set Score</div>
			<div class="stat-val">{ep.avg_kill_score ?? '—'}</div>
		</div>
	</div>
</div>

<!-- YOUTUBE EMBED -->
{#if embedUrl}
	<div class="section" id="video-section">
		<div class="s-header">
			<div>
				<div class="s-title">Full Episode</div>
				<div class="s-sub">Click any set below to jump to that moment in the video</div>
			</div>
		</div>
		<div class="video-wrap">
			{#key videoStart}
				<iframe
					src={embedUrl}
					title="Kill Tony Episode #{ep.episode_number}"
					frameborder="0"
					allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
					allowfullscreen
				></iframe>
			{/key}
		</div>
	</div>
{/if}

<!-- LAUGHTER TIMELINE -->
{#if laughterTimeline}
	<div class="section">
		<LaughterTimeline data={laughterTimeline} onJumpTo={jumpTo} />
	</div>
{/if}

<!-- SETS -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Sets</div>
			<div class="s-sub">All {sets.length} performances from this episode, in order</div>
		</div>
	</div>

	<div class="sets-grid">
		{#each sets as s, i}
			<SetCard
				set={s}
				rank={i + 1}
				showTimecode={true}
				onJumpTo={s.set_start_seconds != null ? () => jumpTo(s.set_start_seconds!) : undefined}
			/>
		{/each}
	</div>
</div>

<style>
	.ep-hero {
		padding: 40px;
		border-bottom: 1px solid var(--border);
		display: grid;
		grid-template-columns: 1fr 320px;
		gap: 48px;
		align-items: center;
	}

	.back-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		color: var(--muted);
		text-decoration: none;
		letter-spacing: 0.5px;
		padding: 6px 14px 6px 10px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--card);
		margin-bottom: 24px;
		transition: border-color 0.15s, color 0.15s, background 0.15s;
	}

	.back-btn:hover {
		border-color: var(--bh);
		color: var(--red);
		background: var(--raised);
	}

	.back-arrow {
		width: 14px;
		height: 14px;
		flex-shrink: 0;
	}

	.ep-number {
		font-size: clamp(48px, 6vw, 72px);
		font-weight: 700;
		letter-spacing: -2px;
		line-height: 1;
		margin-bottom: 12px;
	}

	.ep-guests {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 12px;
	}

	.guest-chip-hero {
		font-family: var(--mono);
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
		background: var(--raised);
		border: 1px solid var(--border);
		padding: 6px 14px;
		border-radius: 6px;
		text-decoration: none;
		transition: border-color 0.15s, color 0.15s;
	}

	.guest-chip-hero:hover {
		border-color: var(--bh);
		color: var(--red);
	}

	.ep-meta-row {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 4px;
	}

	.ep-date {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
	}

	.ep-venue {
		font-size: 13px;
		color: var(--t2);
	}

	.ep-pills {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-top: 8px;
	}

	.ep-pill {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		color: var(--t2);
		background: var(--card);
		border: 1px solid var(--border);
		padding: 5px 12px;
		border-radius: 20px;
		letter-spacing: 0.3px;
	}

	.ep-pill.laugh {
		color: var(--amber);
		border-color: rgba(245, 158, 11, 0.25);
		background: rgba(245, 158, 11, 0.06);
	}

	.pill-icon {
		width: 13px;
		height: 13px;
		flex-shrink: 0;
		opacity: 0.6;
	}

	.ep-summary {
		font-size: 13px;
		color: var(--t2);
		line-height: 1.6;
		margin-top: 16px;
		max-width: 520px;
	}

	.ep-summary.placeholder {
		color: var(--dim);
		font-style: italic;
	}

	.ep-hero-stats {
		border-left: 1px solid var(--border);
		padding-left: 36px;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.stat-row {
		padding: 14px 0;
		border-bottom: 1px solid var(--border);
	}

	.stat-row:last-child {
		border-bottom: none;
	}

	.stat-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		margin-bottom: 5px;
	}

	.stat-val {
		font-family: var(--mono);
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -1px;
		line-height: 1;
	}

	.score-max {
		font-size: 14px;
		font-weight: 400;
		color: var(--muted);
		letter-spacing: 0;
	}

	.stat-rank {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}

	.rank-num {
		font-family: var(--mono);
		font-size: 32px;
		font-weight: 700;
		color: var(--red);
		letter-spacing: -1px;
		line-height: 1;
	}

	.rank-total {
		font-family: var(--mono);
		font-size: 13px;
		color: var(--muted);
	}

	.video-wrap {
		position: relative;
		width: 100%;
		padding-bottom: 56.25%;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--border);
	}

	.video-wrap iframe {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
	}

	.sets-grid {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
</style>
