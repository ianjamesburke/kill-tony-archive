<script lang="ts">
	import type { MatchupSet } from '$lib/types';

	let { s, side }: { s: MatchupSet; side: string } = $props();
	let playing = $state(false);

	const thumb = $derived(`https://img.youtube.com/vi/${s.video_id}/hqdefault.jpg`);
	const embed = $derived(
		`https://www.youtube.com/embed/${s.video_id}?start=${s.set_start_seconds}&end=${s.set_end_seconds}&autoplay=1&rel=0`
	);

	function formatTime(seconds: number): string {
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const sec = Math.floor(seconds % 60);
		return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
	}
</script>

<div class="thumb">
	<span class="corner">{side}</span>
	{#if playing}
		<iframe
			src={embed}
			title="{s.comedian_name}, episode {s.episode_number}"
			allow="autoplay; encrypted-media; picture-in-picture"
			allowfullscreen
		></iframe>
	{:else}
		<img src={thumb} alt="{s.comedian_name}, episode {s.episode_number}" loading="lazy">
		<button type="button" class="play" aria-label="Play set {side}" onclick={() => (playing = true)}>
			<span><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg></span>
		</button>
		<span class="ts">{formatTime(s.set_start_seconds)}</span>
	{/if}
</div>

<style>
	.thumb { position: relative; aspect-ratio: 16 / 9; background: #000; max-width: 100%; }
	.thumb iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
	.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; opacity: .85; }
	.corner { position: absolute; left: 10px; top: 10px; z-index: 1; font-family: var(--mono); font-size: 10px; letter-spacing: 2px; font-weight: 700; background: var(--red); color: #fff; padding: 3px 8px; border-radius: 3px; pointer-events: none; }
	.play { position: absolute; inset: 0; display: grid; place-items: center; cursor: pointer; background: none; border: 0; padding: 0; }
	.play span { width: 52px; height: 52px; border-radius: 50%; background: rgba(9, 9, 11, .75); border: 1px solid rgba(255, 255, 255, .18); display: grid; place-items: center; backdrop-filter: blur(4px); }
	.play svg { width: 20px; height: 20px; fill: #fff; margin-left: 3px; }
	.play:focus-visible { outline: 2px solid #fff; outline-offset: -4px; }
	.ts { position: absolute; right: 10px; bottom: 10px; font-family: var(--mono); font-size: 10px; background: rgba(9, 9, 11, .8); padding: 3px 7px; border-radius: 3px; color: var(--text); font-variant-numeric: tabular-nums; pointer-events: none; }
</style>
