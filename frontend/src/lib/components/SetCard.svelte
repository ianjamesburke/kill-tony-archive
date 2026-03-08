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
		if (seconds == null) return '00:00:00';
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const s = Math.floor(seconds % 60);
		return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
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
		if (status === 'special_request') return 'Special Request';
		return status;
	}

	function shortStatus(status: string): string {
		if (status === 'bucket_pull') return 'Bucket';
		if (status === 'regular') return 'Regular';
		if (status === 'special_request') return 'Special';
		return status;
	}

	function formatYears(yrs: number | null): string {
		if (yrs == null) return 'N/A';
		if (yrs === 0) return 'First time';
		return `${yrs} yr${yrs !== 1 ? 's' : ''}`;
	}

	const scoreBarWidth = $derived(((set.kill_score ?? 0) / 29) * 100);
</script>

<div class="set-card" class:expanded>
	<button class="set-header" class:has-timecode={showTimecode} onclick={() => (expanded = !expanded)}>
		<div class="set-rank">{rank}</div>
		{#if showTimecode}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<span
				class="set-timecode"
				class:clickable={!!onJumpTo}
				onclick={(e) => { e.stopPropagation(); onJumpTo?.(); }}
				onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); onJumpTo?.(); } }}
				role={onJumpTo ? 'button' : undefined}
				tabindex={onJumpTo ? 0 : undefined}
			>
				{#if onJumpTo}<svg class="play-icon" viewBox="0 0 10 12" fill="currentColor"><polygon points="0,0 10,6 0,12"/></svg>{/if}
				{formatTime(set.set_start_seconds)}
			</span>
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
				<span class="set-status">{shortStatus(set.status)}</span>
				{#if set.topic_tags.length > 0}
					<span class="set-topics">
						{#each set.topic_tags.slice(0, 3) as tag}
							<span class="topic-tag">{tag}</span>
						{/each}
					</span>
				{/if}
			</div>
		</div>
		<div class="set-crowd {crowdClass(set.crowd_reaction)}">
			{formatReaction(set.crowd_reaction)}
		</div>
		<div class="set-score-col">
			<div class="score-row">
				<div class="score-bar-bg">
					<div
						class="score-bar-fill"
						style="width: {scoreBarWidth.toFixed(0)}%"
					></div>
				</div>
				<span class="score-num">{set.kill_score ?? '—'}</span>
			</div>
			{#if set.set_rank != null}
				<span class="set-rank-badge">#{set.set_rank}</span>
			{/if}
		</div>
		<div class="set-expand">{expanded ? '−' : '+'}</div>
	</button>

	{#if expanded}
		<div class="set-detail">
			<!-- Top row: timecode + badges -->
			<div class="detail-top-row">
				<div class="top-left">
					{#if !showTimecode && onJumpTo}
						<button class="jump-btn" onclick={(e) => { e.stopPropagation(); onJumpTo?.(); }}>
							<svg class="play-icon" viewBox="0 0 10 12" fill="currentColor"><polygon points="0,0 10,6 0,12"/></svg>
							{formatTime(set.set_start_seconds)}
						</button>
					{:else if !showTimecode && set.set_start_seconds != null}
						<div class="timecode-label">{formatTime(set.set_start_seconds)}</div>
					{/if}
					{#if set.date}
						<div class="detail-date">{set.date}</div>
					{/if}
				</div>
				<div class="detail-badges">
					{#if set.golden_ticket}<span class="badge gold">Golden Ticket</span>{/if}
					{#if set.sign_up_again}<span class="badge">Sign Up Again</span>{/if}
					{#if set.promoted_to_regular}<span class="badge promo">Promoted to Regular</span>{/if}
					{#if set.invited_secret_show}<span class="badge secret">Secret Show</span>{/if}
				</div>
			</div>

			<!-- Comedian profile: always show 5 core fields -->
			<div class="profile-strip">
				<div class="profile-field">
					<span class="pf-label">Age</span>
					<span class="pf-val" class:na={set.disclosed_age == null}>{set.disclosed_age ?? 'N/A'}</span>
				</div>
				<div class="profile-field">
					<span class="pf-label">Occupation</span>
					<span class="pf-val" class:na={!set.disclosed_occupation}>{set.disclosed_occupation ?? 'N/A'}</span>
				</div>
				<div class="profile-field">
					<span class="pf-label">From</span>
					<span class="pf-val" class:na={!set.disclosed_location}>{set.disclosed_location ?? 'N/A'}</span>
				</div>
				<div class="profile-field">
					<span class="pf-label">Relationship</span>
					<span class="pf-val" class:na={!set.disclosed_relationship_status}>{set.disclosed_relationship_status ?? 'N/A'}</span>
				</div>
				<div class="profile-field">
					<span class="pf-label">Experience</span>
					<span class="pf-val" class:na={set.disclosed_years_doing_comedy == null}>{formatYears(set.disclosed_years_doing_comedy)}</span>
				</div>
			</div>

			<!-- Score breakdown row -->
			<div class="scores-row">
				<div class="score-item">
					<span class="score-label">Tony</span>
					<span class="score-value">{set.tony_praise_level ?? '—'}<span class="score-dim">/5</span></span>
				</div>
				<div class="score-item">
					<span class="score-label">Crowd</span>
					<span class="score-value crowd-val {crowdClass(set.crowd_reaction)}">{formatReaction(set.crowd_reaction)}</span>
				</div>
				<div class="score-item">
					<span class="score-label">Joke Book</span>
					<span class="score-value">{set.joke_book_size ?? '—'}</span>
				</div>
				<div class="score-item">
					<span class="score-label">Status</span>
					<span class="score-value">{statusLabel(set.status)}</span>
				</div>
			</div>

			<!-- Set transcript -->
			{#if set.set_transcript}
				<div class="detail-section">
					<div class="detail-label">Set Transcript</div>
					<pre class="transcript">{set.set_transcript}</pre>
				</div>
			{/if}

			<!-- Interview summary -->
			{#if set.interview_summary}
				<div class="detail-section">
					<div class="detail-label">Interview Summary</div>
					<p class="detail-text">{set.interview_summary}</p>
				</div>
			{/if}

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
		grid-template-columns: 40px 1fr 120px 110px 30px;
		align-items: center;
		gap: 12px;
		padding: 12px 20px;
		width: 100%;
		background: none;
		border: none;
		color: var(--text);
		cursor: pointer;
		text-align: left;
		font-family: inherit;
	}

	.set-header.has-timecode {
		grid-template-columns: 40px auto 1fr 120px 110px 30px;
	}

	.set-timecode {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		background: none;
		border: none;
		padding: 0;
		cursor: default;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		width: fit-content;
	}

	.set-timecode.clickable {
		cursor: pointer;
		color: var(--red);
		background: var(--red-d);
		border: 1px solid rgba(220, 38, 38, 0.25);
		padding: 4px 8px;
		border-radius: 5px;
		font-weight: 600;
		transition: background 0.15s, border-color 0.15s;
	}

	.set-timecode.clickable:hover {
		background: rgba(220, 38, 38, 0.15);
		border-color: rgba(220, 38, 38, 0.4);
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
		font-size: 14px;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
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
		gap: 6px;
		margin-top: 3px;
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

	.set-score-col {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 3px;
	}

	.score-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.score-bar-bg {
		width: 44px;
		height: 4px;
		background: var(--dim2);
		border-radius: 2px;
		overflow: hidden;
	}

	.score-bar-fill {
		height: 100%;
		background: var(--red);
		border-radius: 2px;
	}

	.score-num {
		font-family: var(--mono);
		font-size: 16px;
		font-weight: 700;
		color: var(--red);
		min-width: 24px;
		text-align: right;
		letter-spacing: -0.5px;
	}

	.set-rank-badge {
		font-family: var(--mono);
		font-size: 9px;
		font-weight: 600;
		color: var(--muted);
	}

	.set-expand {
		font-family: var(--mono);
		font-size: 16px;
		color: var(--dim);
		text-align: center;
	}

	/* ── Expanded detail ── */
	.set-detail {
		padding: 0 20px 20px 72px;
		border-top: 1px solid var(--border);
	}

	.detail-top-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 0 0;
	}

	.top-left {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.jump-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--mono);
		font-size: 12px;
		font-weight: 600;
		color: var(--red);
		background: var(--red-d);
		border: 1px solid rgba(220, 38, 38, 0.25);
		padding: 6px 14px;
		border-radius: 5px;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}

	.jump-btn:hover {
		background: rgba(220, 38, 38, 0.15);
		border-color: rgba(220, 38, 38, 0.4);
	}

	.play-icon {
		width: 6px;
		height: 8px;
		flex-shrink: 0;
	}

	.timecode-label {
		font-family: var(--mono);
		font-size: 12px;
		color: var(--muted);
	}

	.detail-date {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--dim);
	}

	.detail-badges {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.badge {
		font-family: var(--mono);
		font-size: 9px;
		font-weight: 600;
		letter-spacing: 0.5px;
		text-transform: uppercase;
		padding: 3px 8px;
		border-radius: 3px;
		color: var(--t2);
		background: var(--raised);
		border: 1px solid var(--border);
	}

	.badge.gold {
		color: var(--amber);
		background: rgba(245, 158, 11, 0.1);
		border-color: rgba(245, 158, 11, 0.2);
	}

	.badge.promo {
		color: #22c55e;
		background: rgba(34, 197, 94, 0.08);
		border-color: rgba(34, 197, 94, 0.2);
	}

	.badge.secret {
		color: #a78bfa;
		background: rgba(167, 139, 250, 0.08);
		border-color: rgba(167, 139, 250, 0.2);
	}

	/* ── Profile strip: 5 core fields ── */
	.profile-strip {
		display: grid;
		grid-template-columns: 60px 1fr 1fr 1fr 100px;
		gap: 0;
		margin-top: 14px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
	}

	.profile-field {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 10px 14px;
		border-right: 1px solid var(--border);
	}

	.profile-field:last-child {
		border-right: none;
	}

	.pf-label {
		font-family: var(--mono);
		font-size: 8px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.pf-val {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
		line-height: 1.3;
	}

	.pf-val.na {
		color: var(--dim);
		font-weight: 400;
		font-style: italic;
	}

	/* ── Score breakdown row ── */
	.scores-row {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0;
		margin-top: 10px;
	}

	.score-item {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 8px 0;
	}

	.score-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.score-value {
		font-family: var(--mono);
		font-size: 13px;
		font-weight: 600;
		color: var(--t2);
	}

	.score-dim {
		font-weight: 400;
		color: var(--muted);
		font-size: 11px;
	}

	.crowd-val {
		text-transform: capitalize;
	}

	/* ── Sections (transcript, interview) ── */
	.detail-section {
		margin-top: 16px;
	}

	.detail-label {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
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

	@media (max-width: 768px) {
		.set-header {
			grid-template-columns: 30px 1fr auto 30px;
			gap: 8px;
			padding: 10px 12px;
		}

		.set-header.has-timecode {
			grid-template-columns: 30px auto 1fr auto 30px;
		}

		.set-crowd {
			display: none;
		}

		.set-detail {
			padding: 0 12px 16px 12px;
		}

		.profile-strip {
			grid-template-columns: repeat(3, 1fr);
		}

		.scores-row {
			grid-template-columns: repeat(2, 1fr);
		}

		.score-bar-bg {
			width: 30px;
		}

		.set-name {
			font-size: 13px;
		}

		.score-num {
			font-size: 14px;
		}
	}
</style>
