<script lang="ts">
	import type { PageData } from './$types';
	import GuestImpactChart from '$lib/components/GuestImpactChart.svelte';

	let { data }: { data: PageData } = $props();

</script>

<svelte:head>
	<title>Guests | Kill Tony Archive</title>
</svelte:head>

<!-- GUEST IMPACT VISUALIZATION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Guest Impact</div>
			<div class="s-sub">
				How guests shift the episode's avg kill score vs. the overall average ({data.baselineAvg})
			</div>
		</div>
	</div>
	<GuestImpactChart guests={data.guests} baseline={data.baselineAvg} />
</div>

<!-- GUEST DIRECTORY -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Guests</div>
			<div class="s-sub">{data.guests.length} guests ranked by avg kill score</div>
		</div>
	</div>

	<div class="guest-list">
		{#each data.guests as guest}
			<a href="/guests/{encodeURIComponent(guest.guest_name)}" class="guest-row">
				<div class="guest-left">
					<div class="guest-name">{guest.guest_name}</div>
					<div class="guest-meta">
						{guest.episode_count} appearance{guest.episode_count !== 1 ? 's' : ''}
					</div>
				</div>
				<div class="guest-stats">
					<div class="guest-stat">
						<span class="guest-stat-label">Avg Score</span>
						<span class="guest-stat-val score">{guest.avg_kill_score ?? '—'}</span>
					</div>
					{#if guest.score_lift != null}
						<div class="guest-stat">
							<span class="guest-stat-label">Impact</span>
							<span class="guest-stat-val" class:pos={guest.score_lift > 0} class:neg={guest.score_lift < 0}>
								{guest.score_lift > 0 ? '+' : ''}{guest.score_lift}
							</span>
						</div>
					{/if}
					<div class="guest-stat">
						<span class="guest-stat-label">Laughs</span>
						<span class="guest-stat-val">{guest.total_laugh_count.toLocaleString()}</span>
					</div>
				</div>
			</a>
		{/each}
	</div>
</div>

<style>
	.guest-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.guest-row {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: center;
		gap: 20px;
		padding: 18px 20px;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 6px;
		text-decoration: none;
		color: var(--text);
		transition:
			border-color 0.15s,
			background 0.15s;
	}

	.guest-row:hover {
		border-color: var(--bh);
		background: var(--raised);
	}

	.guest-left {
		min-width: 0;
	}

	.guest-name {
		font-size: 16px;
		font-weight: 700;
		letter-spacing: -0.5px;
	}

	.guest-meta {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-top: 4px;
	}

	.guest-stats {
		display: flex;
		gap: 20px;
		justify-content: flex-end;
	}

	.guest-stat {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.guest-stat-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.guest-stat-val {
		font-family: var(--mono);
		font-size: 18px;
		font-weight: 700;
		letter-spacing: -0.5px;
	}

	.guest-stat-val.score {
		color: var(--red);
	}

	.guest-stat-val.pos {
		color: var(--green);
	}

	.guest-stat-val.neg {
		color: var(--red-s);
	}

	@media (max-width: 768px) {
		.guest-row {
			grid-template-columns: 1fr;
			gap: 8px;
			padding: 14px 16px;
		}

		.guest-stats {
			gap: 12px;
			flex-wrap: wrap;
		}

		.guest-stat-val {
			font-size: 14px;
		}
	}
</style>
