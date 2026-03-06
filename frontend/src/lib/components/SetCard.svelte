<script lang="ts">
	import type { ComedySet } from '$lib/types';

	let {
		set,
		rank,
		showTimecode = false,
		showEpisode = false,
		onJumpTo
	}: {
		set: ComedySet;
		rank: number;
		showTimecode?: boolean;
		showEpisode?: boolean;
		onJumpTo?: (() => void) | undefined;
	} = $props();

	let expanded = $state(false);

	function formatTime(seconds: number | null): string {
		if (seconds == null) return '—';
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function crowdClass(reaction: string | null): string {
		if (!reaction) return 'crowd-low';
		const r = reaction.toLowerCase();
		if (r.includes('roaring') || r.includes('big')) return 'crowd-high';
		if (r.includes('moderate') || r.includes('strong')) return 'crowd-mid';
		return 'crowd-low';
	}

	function formatReaction(reaction: string | null): string {
		if (!reaction) return '—';
		return reaction.replace(/_/g, ' ');
	}

	function statusLabel(status: string): string {
		if (status === 'bucket_pull') return 'Bucket Pull';
		if (status === 'regular') return 'Regular';
		return status;
	}
</script>

<div class="set-card" class:expanded>
	<button class="set-header" class:has-timecode={showTimecode} onclick={() => (expanded = !expanded)}>
		<div class="set-rank">{rank}</div>
		{#if showTimecode}
			<button
				class="set-timecode"
				class:clickable={!!onJumpTo}
				onclick={(e: MouseEvent) => { e.stopPropagation(); onJumpTo?.(); }}
				title={onJumpTo ? 'Jump to this set in the video' : ''}
			>
				{#if onJumpTo}
					<span class="play-icon">&#9654;</span>
				{/if}
				{formatTime(set.set_start_seconds)}
			</button>
		{/if}
		<div class="set-info">
			<div class="set-name">
				{set.comedian_name}
				{#if showEpisode}
					<a href="/episodes/{set.episode_number}" class="set-ep-link" onclick={(e) => e.stopPropagation()}>Ep #{set.episode_number}</a>
				{/if}
				{#if set.golden_ticket}
					<span class="golden">GOLDEN TICKET</span>
				{/if}
			</div>
			<div class="set-meta">
				<span class="set-status">{statusLabel(set.status)}</span>
				{#if set.topic_tags.length > 0}
					<span class="set-topics">
						{#each set.topic_tags as tag}
							<span class="topic-tag">{tag}</span>
						{/each}
					</span>
				{/if}
			</div>
		</div>
		<div class="set-crowd {crowdClass(set.crowd_reaction)}">
			{formatReaction(set.crowd_reaction)}
		</div>
		<div class="set-score">
			{set.kill_score ?? '—'}
		</div>
		<div class="set-expand">{expanded ? '−' : '+'}</div>
	</button>

	{#if expanded}
		<div class="set-detail">
			<div class="detail-grid">
				<div class="detail-col">
					<div class="detail-label">Tony Praise</div>
					<div class="detail-val">{set.tony_praise_level ?? '—'}/5</div>
				</div>
				<div class="detail-col">
					<div class="detail-label">Joke Density</div>
					<div class="detail-val">{set.joke_density ?? '—'}</div>
				</div>
				<div class="detail-col">
					<div class="detail-label">Joke Book</div>
					<div class="detail-val">{set.joke_book_size ?? '—'}</div>
				</div>
				<div class="detail-col">
					<div class="detail-label">Status</div>
					<div class="detail-val">{statusLabel(set.status)}</div>
				</div>
			</div>

			{#if set.interview_summary}
				<div class="detail-section">
					<div class="detail-label">Interview Summary</div>
					<p class="detail-text">{set.interview_summary}</p>
				</div>
			{/if}

			{#if set.set_transcript}
				<div class="detail-section">
					<div class="detail-label">Set Transcript</div>
					<pre class="transcript">{set.set_transcript}</pre>
				</div>
			{/if}

			<div class="detail-badges">
				{#if set.golden_ticket}<span class="badge gold">Golden Ticket</span>{/if}
				{#if set.sign_up_again}<span class="badge">Sign Up Again</span>{/if}
				{#if set.promoted_to_regular}<span class="badge">Promoted to Regular</span>{/if}
				{#if set.invited_secret_show}<span class="badge">Secret Show Invite</span>{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.set-card {
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
		transition: border-color 0.15s;
	}

	.set-card:hover {
		border-color: var(--bh);
	}

	.set-card.expanded {
		border-color: var(--dim);
	}

	.set-header {
		display: grid;
		grid-template-columns: 40px 1fr 120px 60px 30px;
		align-items: center;
		gap: 12px;
		padding: 16px 20px;
		width: 100%;
		background: none;
		border: none;
		color: var(--text);
		cursor: pointer;
		text-align: left;
		font-family: inherit;
	}

	.set-header.has-timecode {
		grid-template-columns: 40px 70px 1fr 120px 60px 30px;
	}

	.set-timecode {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
		background: none;
		border: none;
		padding: 0;
		cursor: default;
		display: flex;
		align-items: center;
		gap: 4px;
		font-family: var(--mono);
	}

	.set-timecode.clickable {
		cursor: pointer;
		color: var(--t2);
		transition: color 0.15s;
	}

	.set-timecode.clickable:hover {
		color: var(--red);
	}

	.play-icon {
		font-size: 9px;
		color: var(--red);
	}

	.set-header:hover {
		background: rgba(255, 255, 255, 0.02);
	}

	.set-rank {
		font-family: var(--mono);
		font-size: 14px;
		font-weight: 700;
		color: var(--dim);
		text-align: center;
	}

	.set-info {
		min-width: 0;
	}

	.set-name {
		font-size: 15px;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.set-ep-link {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		text-decoration: none;
		transition: color 0.15s;
	}

	.set-ep-link:hover {
		color: var(--red);
	}

	.golden {
		font-family: var(--mono);
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 1px;
		color: var(--amber);
		background: rgba(245, 158, 11, 0.1);
		border: 1px solid rgba(245, 158, 11, 0.2);
		padding: 2px 8px;
		border-radius: 3px;
	}

	.set-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 4px;
		flex-wrap: wrap;
	}

	.set-status {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.set-topics {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.set-crowd {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		text-align: center;
	}

	.set-score {
		font-family: var(--mono);
		font-size: 18px;
		font-weight: 700;
		color: var(--red);
		text-align: right;
		letter-spacing: -0.5px;
	}

	.set-expand {
		font-family: var(--mono);
		font-size: 16px;
		color: var(--dim);
		text-align: center;
	}

	.set-detail {
		padding: 0 20px 20px 72px;
		border-top: 1px solid var(--border);
	}

	.detail-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 20px;
		padding: 20px 0;
	}

	.detail-col {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.detail-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.detail-val {
		font-family: var(--mono);
		font-size: 14px;
		font-weight: 600;
		color: var(--t2);
	}

	.detail-section {
		margin-top: 16px;
	}

	.detail-text {
		font-size: 13px;
		color: var(--t2);
		line-height: 1.65;
		margin-top: 6px;
	}

	.transcript {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--t2);
		line-height: 1.7;
		margin-top: 6px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 16px;
		white-space: pre-wrap;
		word-break: break-word;
		max-height: 400px;
		overflow-y: auto;
	}

	.detail-badges {
		display: flex;
		gap: 8px;
		margin-top: 16px;
		flex-wrap: wrap;
	}

	.badge {
		font-family: var(--mono);
		font-size: 10px;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		padding: 4px 10px;
		border-radius: 4px;
		color: var(--t2);
		background: var(--raised);
		border: 1px solid var(--border);
	}

	.badge.gold {
		color: var(--amber);
		background: rgba(245, 158, 11, 0.1);
		border-color: rgba(245, 158, 11, 0.2);
	}
</style>
