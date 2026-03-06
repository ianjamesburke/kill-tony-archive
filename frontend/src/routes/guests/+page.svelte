<script lang="ts">
	import type { PageData } from './$types';
	import GuestImpactChart from '$lib/components/GuestImpactChart.svelte';

	let { data }: { data: PageData } = $props();

	const sortedByAppearances = $derived(
		[...data.guests].sort((a, b) => b.episode_count - a.episode_count)
	);
</script>

<svelte:head>
	<title>Guests — Kill Tony DB</title>
</svelte:head>

<!-- GUEST IMPACT VISUALIZATION -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">Guest Impact on Show Quality</div>
			<div class="s-sub">
				Do random bucket-pull comedians perform better with certain guests on the panel?
				The baseline avg bucket-pull score is <strong>{data.baselineBucketAvg}</strong> — bars
				show each guest's deviation from that.
			</div>
		</div>
	</div>
	<GuestImpactChart guests={data.guests} baseline={data.baselineBucketAvg} />
</div>

<!-- GUEST DIRECTORY -->
<div class="section">
	<div class="s-header">
		<div>
			<div class="s-title">All Guests</div>
			<div class="s-sub">{data.guests.length} guests ranked by avg kill score</div>
		</div>
	</div>

	<div class="guest-grid">
		{#each data.guests as guest}
			<a href="/guests/{encodeURIComponent(guest.guest_name)}" class="guest-card">
				<div class="gc-top">
					<div class="gc-name">{guest.guest_name}</div>
					{#if guest.bucket_lift != null}
						<div
							class="gc-lift"
							class:positive={guest.bucket_lift > 0}
							class:negative={guest.bucket_lift < 0}
						>
							{guest.bucket_lift > 0 ? '+' : ''}{guest.bucket_lift}
						</div>
					{/if}
				</div>
				<div class="gc-appearances">
					{guest.episode_count} appearance{guest.episode_count !== 1 ? 's' : ''}
				</div>
				<div class="gc-metrics">
					<div class="gc-metric">
						<div class="gc-metric-val score">{guest.avg_kill_score ?? '—'}</div>
						<div class="gc-metric-label">Avg Score</div>
					</div>
					<div class="gc-metric">
						<div class="gc-metric-val">{guest.avg_bucket_score ?? '—'}</div>
						<div class="gc-metric-label">Bucket Avg</div>
					</div>
					<div class="gc-metric">
						<div class="gc-metric-val">{guest.total_laugh_count}</div>
						<div class="gc-metric-label">Total Laughs</div>
					</div>
				</div>
			</a>
		{/each}
	</div>
</div>

<style>
	.guest-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 8px;
	}

	.guest-card {
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 20px 24px;
		text-decoration: none;
		color: var(--text);
		transition:
			border-color 0.15s,
			background 0.15s;
	}

	.guest-card:hover {
		border-color: var(--bh);
		background: var(--raised);
	}

	.gc-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 8px;
	}

	.gc-name {
		font-size: 16px;
		font-weight: 600;
		line-height: 1.2;
	}

	.gc-lift {
		font-family: var(--mono);
		font-size: 12px;
		font-weight: 700;
		padding: 3px 8px;
		border-radius: 4px;
		white-space: nowrap;
		flex-shrink: 0;
	}

	.gc-lift.positive {
		color: var(--green);
		background: rgba(34, 197, 94, 0.1);
		border: 1px solid rgba(34, 197, 94, 0.2);
	}

	.gc-lift.negative {
		color: var(--red-s);
		background: var(--red-d);
		border: 1px solid rgba(220, 38, 38, 0.2);
	}

	.gc-appearances {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-top: 4px;
		margin-bottom: 14px;
		letter-spacing: 0.3px;
	}

	.gc-metrics {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1px;
		background: var(--border);
		border-radius: 6px;
		overflow: hidden;
		border: 1px solid var(--border);
	}

	.gc-metric {
		background: var(--surface);
		padding: 10px 12px;
		text-align: center;
	}

	.gc-metric-val {
		font-family: var(--mono);
		font-size: 16px;
		font-weight: 700;
		letter-spacing: -0.5px;
		margin-bottom: 2px;
	}

	.gc-metric-val.score {
		color: var(--red);
	}

	.gc-metric-label {
		font-family: var(--mono);
		font-size: 8px;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--muted);
	}
</style>
