<script lang="ts">
	import type { TopicStat } from '$lib/types';

	let { topics }: { topics: TopicStat[] } = $props();

	const topTopics = $derived(topics.slice(0, 20));
	const maxCount = $derived(Math.max(...topTopics.map((t) => t.count), 1));

	const colors = [
		'#ef4444', '#f59e0b', '#8b5cf6', '#3b82f6', '#ec4899',
		'#22c55e', '#06b6d4', '#a78bfa', '#84cc16', '#f97316'
	];

	function topicColor(index: number): string {
		return colors[index % colors.length];
	}
</script>

<div class="topic-bars">
	{#each topTopics as topic, i}
		<div class="topic-row">
			<div class="topic-label">{topic.topic}</div>
			<div class="topic-bar-track">
				<div
					class="topic-bar-fill"
					style="width: {(topic.count / maxCount * 100).toFixed(0)}%; background: {topicColor(i)}"
				></div>
			</div>
			<div class="topic-count">{topic.count}</div>
		</div>
	{/each}
</div>

<style>
	.topic-bars {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.topic-row {
		display: grid;
		grid-template-columns: 140px 1fr 40px;
		align-items: center;
		gap: 12px;
	}

	.topic-label {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--t2);
		text-transform: capitalize;
		text-align: right;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.topic-bar-track {
		height: 8px;
		background: var(--dim2);
		border-radius: 4px;
		overflow: hidden;
	}

	.topic-bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.4s ease;
	}

	.topic-count {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		text-align: right;
	}
</style>
