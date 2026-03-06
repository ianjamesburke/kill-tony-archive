<script lang="ts">
	import type { PageData } from './$types';
	import SetCard from '$lib/components/SetCard.svelte';
	import { onMount, tick } from 'svelte';

	let { data }: { data: PageData } = $props();

	const ep = $derived(data.episode);
	const sets = $derived(data.sets);

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
		// Scroll video into view
		document.getElementById('video-section')?.scrollIntoView({ behavior: 'smooth' });
	}

	function formatTime(seconds: number | null): string {
		if (seconds == null) return '—';
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}
</script>

<svelte:head>
	<title>Episode #{ep.episode_number} — Kill Tony DB</title>
</svelte:head>

<div class="ep-hero">
	<div class="ep-hero-left">
		<a href="/episodes" class="back-link">&larr; All episodes</a>
		<div class="ep-tag">Episode</div>
		<h1 class="ep-number">#{ep.episode_number}</h1>
		{#if ep.date}
			<div class="ep-date">{ep.date}</div>
		{/if}
		{#if ep.venue}
			<div class="ep-venue">{ep.venue}</div>
		{/if}
	</div>
	<div class="ep-hero-stats">
		<div class="stat-row">
			<div class="stat-label">Sets</div>
			<div class="stat-val">{ep.set_count}</div>
		</div>
		<div class="stat-row">
			<div class="stat-label">Avg Kill Score</div>
			<div class="stat-val">{ep.avg_kill_score ?? '—'}</div>
		</div>
		{#if ep.guests.length > 0}
			<div class="stat-row">
				<div class="stat-label">Guests</div>
				<div class="stat-guests">
					{#each ep.guests as guest}
						<span class="guest-chip">{guest}</span>
					{/each}
				</div>
			</div>
		{/if}
		{#if ep.view_count}
			<div class="stat-row">
				<div class="stat-label">Views</div>
				<div class="stat-val">{ep.view_count.toLocaleString()}</div>
			</div>
		{/if}
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
		align-items: start;
	}

	.back-link {
		display: inline-block;
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		text-decoration: none;
		margin-bottom: 20px;
		letter-spacing: 0.5px;
		transition: color 0.15s;
	}

	.back-link:hover {
		color: var(--red);
	}

	.ep-tag {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--red);
		background: var(--red-d);
		padding: 5px 14px;
		border-radius: 4px;
		display: inline-block;
		margin-bottom: 12px;
		border: 1px solid rgba(220, 38, 38, 0.2);
	}

	.ep-number {
		font-size: clamp(48px, 6vw, 72px);
		font-weight: 700;
		letter-spacing: -2px;
		line-height: 1;
		margin-bottom: 8px;
	}

	.ep-date {
		font-family: var(--mono);
		font-size: 13px;
		color: var(--muted);
		margin-bottom: 4px;
	}

	.ep-venue {
		font-size: 14px;
		color: var(--t2);
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

	.stat-row:first-child {
		padding-top: 0;
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

	.stat-guests {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 4px;
	}

	.guest-chip {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--t2);
		background: var(--raised);
		border: 1px solid var(--border);
		padding: 4px 10px;
		border-radius: 4px;
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
