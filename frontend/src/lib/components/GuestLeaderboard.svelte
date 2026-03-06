<script lang="ts">
	import type { GuestStat } from '$lib/types';

	let { guests }: { guests: GuestStat[] } = $props();

	const topGuests = $derived(guests.slice(0, 10));
	const maxScore = $derived(
		Math.max(...topGuests.map((g) => g.avg_kill_score ?? 0), 1)
	);
</script>

<div class="guest-list">
	{#each topGuests as guest, i}
		<div class="guest-row">
			<div class="g-rank" class:gold={i === 0} class:silver={i === 1}>
				{i + 1}
			</div>
			<div>
				<div class="g-name">{guest.guest_name}</div>
				<div class="g-eps">
					{guest.episode_count} appearance{guest.episode_count !== 1 ? 's' : ''}
				</div>
			</div>
			<div class="g-score-col">
				<div class="g-score">{guest.avg_kill_score ?? '—'}</div>
				<div class="g-score-bar">
					<div
						class="g-score-fill"
						style="width: {((guest.avg_kill_score ?? 0) / maxScore * 100).toFixed(0)}%"
					></div>
				</div>
			</div>
		</div>
	{/each}
</div>

<style>
	.guest-list {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.guest-row {
		display: grid;
		grid-template-columns: 32px 1fr 60px;
		align-items: center;
		gap: 10px;
		padding: 14px 8px;
		border-bottom: 1px solid var(--border);
		cursor: pointer;
		transition: background 0.1s;
		border-radius: 4px;
	}

	.guest-row:last-child {
		border-bottom: none;
	}

	.guest-row:hover {
		background: rgba(255, 255, 255, 0.03);
	}

	.g-rank {
		font-family: var(--mono);
		font-size: 13px;
		font-weight: 700;
		color: var(--dim);
		text-align: center;
	}

	.g-rank.gold {
		color: var(--amber);
	}

	.g-rank.silver {
		color: var(--t2);
	}

	.g-name {
		font-size: 14px;
		font-weight: 600;
	}

	.g-eps {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-top: 2px;
	}

	.g-score-col {
		text-align: right;
	}

	.g-score {
		font-family: var(--mono);
		font-size: 16px;
		font-weight: 700;
		text-align: right;
		color: var(--text);
	}

	.g-score-bar {
		height: 3px;
		background: var(--dim2);
		border-radius: 2px;
		margin-top: 4px;
		overflow: hidden;
	}

	.g-score-fill {
		height: 100%;
		background: var(--red);
		border-radius: 2px;
		transition: width 0.4s ease;
	}
</style>
