<script lang="ts">
	import type { GuestStat } from '$lib/types';

	let { guests, baseline }: { guests: GuestStat[]; baseline: number } = $props();

	const N = 5;

	const sorted = $derived(
		[...guests]
			.filter((g) => g.score_lift != null)
			.sort((a, b) => (b.score_lift ?? 0) - (a.score_lift ?? 0))
	);

	const top = $derived(sorted.filter((g) => (g.score_lift ?? 0) > 0).slice(0, N));
	const bottom = $derived(sorted.filter((g) => (g.score_lift ?? 0) < 0).slice(-N));
	const visible = $derived([...top, ...bottom]);

	const maxAbs = $derived(
		Math.max(...visible.map((g) => Math.abs(g.score_lift ?? 0)), 0.1)
	);
</script>

<div class="impact-list">
	{#each visible as guest, i}
		{@const lift = guest.score_lift ?? 0}
		{@const pct = (Math.abs(lift) / maxAbs) * 50}
		{@const positive = lift >= 0}
		{#if i === top.length && top.length > 0 && bottom.length > 0}
			<div class="impact-divider"></div>
		{/if}
		<a href="/guests/{encodeURIComponent(guest.guest_name)}" class="impact-row">
			<span class="impact-name">{guest.guest_name}</span>
			<div class="impact-bar-wrap">
				{#if positive}
					<div class="impact-bar-half left"></div>
					<div class="impact-bar-half right">
						<div class="impact-bar-fill pos" style="width: {pct}%"></div>
					</div>
				{:else}
					<div class="impact-bar-half left">
						<div class="impact-bar-fill neg" style="width: {pct}%"></div>
					</div>
					<div class="impact-bar-half right"></div>
				{/if}
				<div class="impact-center-line"></div>
			</div>
			<span class="impact-val" class:pos={positive} class:neg={!positive}>
				{positive ? '+' : ''}{lift}
			</span>
		</a>
	{/each}
</div>

<style>
	.impact-list {
		display: flex;
		flex-direction: column;
		gap: 1px;
		background: var(--border);
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
	}

	.impact-divider {
		height: 3px;
		background: var(--border);
	}

	.impact-row {
		display: grid;
		grid-template-columns: 140px 1fr 48px;
		align-items: center;
		gap: 8px;
		padding: 6px 12px;
		background: var(--bg);
		text-decoration: none;
		color: var(--text);
		transition: background 0.1s;
	}

	.impact-row:hover {
		background: var(--raised);
	}

	.impact-name {
		font-size: 12px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.impact-bar-wrap {
		display: grid;
		grid-template-columns: 1fr 1fr;
		height: 10px;
		position: relative;
	}

	.impact-bar-half {
		display: flex;
		overflow: hidden;
	}

	.impact-bar-half.left {
		justify-content: flex-end;
	}

	.impact-bar-half.right {
		justify-content: flex-start;
	}

	.impact-bar-fill {
		height: 100%;
		border-radius: 2px;
	}

	.impact-bar-fill.pos {
		background: var(--green);
		opacity: 0.7;
	}

	.impact-bar-fill.neg {
		background: var(--red);
		opacity: 0.7;
	}

	.impact-center-line {
		position: absolute;
		left: 50%;
		top: -2px;
		bottom: -2px;
		width: 1px;
		background: var(--border);
	}

	.impact-val {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 700;
		text-align: right;
	}

	.impact-val.pos {
		color: var(--green);
	}

	.impact-val.neg {
		color: var(--red-s);
	}

	@media (max-width: 768px) {
		.impact-row {
			grid-template-columns: 110px 1fr 42px;
			padding: 5px 10px;
		}

		.impact-name {
			font-size: 11px;
		}
	}
</style>
