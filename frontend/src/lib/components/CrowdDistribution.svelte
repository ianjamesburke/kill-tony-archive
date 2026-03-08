<script lang="ts">
	import type { CrowdReaction } from '$lib/types';

	let { reactions }: { reactions: CrowdReaction[] } = $props();

	const total = $derived(reactions.reduce((sum, r) => sum + r.count, 0));
	const maxCount = $derived(Math.max(...reactions.map((r) => r.count), 1));

	const reactionColors: Record<string, string> = {
		roaring_laughter: '#22c55e',
		big_laughs: '#84cc16',
		moderate_laughs: '#f59e0b',
		light_laughs: '#f97316',
		silence: '#ef4444',
		mixed: '#8b5cf6',
		groans: '#ec4899'
	};

	function getColor(reaction: string): string {
		return reactionColors[reaction] ?? '#71717a';
	}

	function formatLabel(reaction: string): string {
		return reaction.replace(/_/g, ' ');
	}
</script>

<div class="crowd-bars">
	{#each reactions as r}
		<div class="crowd-row">
			<div class="crowd-label">{formatLabel(r.crowd_reaction)}</div>
			<div class="crowd-bar-track">
				<div
					class="crowd-bar-fill"
					style="width: {(r.count / maxCount * 100).toFixed(0)}%; background: {getColor(r.crowd_reaction)}"
				></div>
			</div>
			<div class="crowd-count">{r.count}</div>
			<div class="crowd-pct">
				{total > 0 ? ((r.count / total) * 100).toFixed(0) : 0}%
			</div>
		</div>
	{/each}
</div>

<style>
	.crowd-bars {
		display: flex;
		flex-direction: column;
		gap: 8px;
		max-width: 600px;
	}

	.crowd-row {
		display: grid;
		grid-template-columns: 140px 1fr 40px 40px;
		align-items: center;
		gap: 12px;
	}

	.crowd-label {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--t2);
		text-transform: capitalize;
		text-align: right;
	}

	.crowd-bar-track {
		height: 10px;
		background: var(--dim2);
		border-radius: 4px;
		overflow: hidden;
	}

	.crowd-bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.4s ease;
	}

	.crowd-count {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		text-align: right;
	}

	.crowd-pct {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--dim);
		text-align: right;
	}

	@media (max-width: 768px) {
		.crowd-row {
			grid-template-columns: 100px 1fr 32px 32px;
			gap: 8px;
		}

		.crowd-label {
			font-size: 10px;
		}
	}
</style>
