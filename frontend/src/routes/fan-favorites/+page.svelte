<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const lb = $derived(data.leaderboard);

	function formatTime(seconds: number): string {
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const s = Math.floor(seconds % 60);
		return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
	}

	function delta(rank: number, ksRank: number): { cls: string; text: string } {
		const d = ksRank - rank;
		if (d > 0) return { cls: 'up', text: `▲${d}` };
		if (d < 0) return { cls: 'dn', text: `▼${-d}` };
		return { cls: 'eq', text: '=' };
	}
</script>

<svelte:head>
	<title>Fan Favorites — Best Kill Tony Sets Ranked by Fans</title>
	<meta name="description" content="The best Kill Tony 1-minute sets as ranked by fans in head-to-head votes, compared against the algorithm's Kill Score.">
	<link rel="canonical" href="https://killtonyarchive.com/fan-favorites">
	<meta property="og:title" content="Fan Favorites — Best Kill Tony Sets Ranked by Fans">
	<meta property="og:description" content="The best Kill Tony 1-minute sets as ranked by fans in head-to-head votes, compared against the algorithm's Kill Score.">
	<meta property="og:type" content="website">
	<meta property="og:url" content="https://killtonyarchive.com/fan-favorites">
	<meta name="twitter:title" content="Fan Favorites — Best Kill Tony Sets Ranked by Fans">
	<meta name="twitter:description" content="The best Kill Tony 1-minute sets as ranked by fans in head-to-head votes, compared against the algorithm's Kill Score.">
</svelte:head>

<div class="fav-page">
	<div class="head">
		<div>
			<div class="eyebrow">Fan Favorites</div>
			<h1>The people's best minute</h1>
			<p class="sub">Ranked purely by head-to-head votes. Compared against the Kill Score, the algorithm's pick, so you can see where the crowd and the math disagree.</p>
		</div>
		<div class="tally">
			<div><b>{lb.total_votes.toLocaleString()}</b> votes cast</div>
			<div><b>{lb.ranked_count}</b> sets ranked · min {lb.min_matchups} matchups</div>
			<div><a href="/vote">Cast your vote →</a></div>
		</div>
	</div>

	{#if lb.sets.length === 0}
		<div class="empty">
			<p>No set has reached {lb.min_matchups} matchups yet. The leaderboard fills in as votes come in.</p>
			<a class="btn-ghost" href="/vote">Start voting</a>
		</div>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>#</th><th>Set</th><th class="num">Elo</th><th>Win rate</th><th class="num">Matchups</th><th class="num">Kill Score rank</th>
					</tr>
				</thead>
				<tbody>
					{#each lb.sets as s (s.set_id)}
						{@const d = delta(s.rank, s.kill_score_rank)}
						<tr>
							<td class="rank" class:gold={s.rank === 1}>{s.rank}</td>
							<td>
								<a class="lb-name" href="/episodes/{s.episode_number}">{s.comedian_name}</a>
								<div class="lb-ep">
									<a href="https://www.youtube.com/watch?v={s.video_id}&t={s.set_start_seconds}s" target="_blank" rel="noopener noreferrer">EP {s.episode_number} · set {s.set_number} · {formatTime(s.set_start_seconds)}</a>
									{#if s.golden_ticket}<span class="gt">Golden ticket</span>{/if}
								</div>
							</td>
							<td class="num elo">{s.elo}</td>
							<td><div class="winbar"><div class="b"><i style="width:{Math.round(s.win_rate * 100)}%"></i></div><span>{Math.round(s.win_rate * 100)}%</span></div></td>
							<td class="num">{s.matchups}</td>
							<td class="num">#{s.kill_score_rank} <span class="delta {d.cls}">{d.text}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="note"><b>Kill Score rank</b> is where the algorithm puts this set. Green means fans rank it higher than the math does. A set needs {lb.min_matchups} matchups before it appears here so a few early votes can't put it on top.</p>
	{/if}
</div>

<style>
	.fav-page { max-width: 1100px; margin: 0 auto; padding: 36px 24px 64px; }
	.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
	.eyebrow { font-family: var(--mono); font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--red); margin-bottom: 8px; }
	h1 { font-size: clamp(30px, 5vw, 48px); letter-spacing: -1px; line-height: 1; text-wrap: balance; }
	.sub { color: var(--muted); font-size: 14px; margin-top: 10px; max-width: 520px; line-height: 1.55; }
	.tally { font-family: var(--mono); font-size: 11px; color: var(--muted); text-align: right; line-height: 1.8; }
	.tally b { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
	.tally a { color: var(--t2); text-decoration: underline; text-underline-offset: 3px; }

	.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
	table { width: 100%; border-collapse: collapse; font-size: 14px; min-width: 640px; }
	th { font-family: var(--mono); font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--border); font-weight: 600; background: var(--raised); }
	td { padding: 13px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
	tr:last-child td { border-bottom: 0; }
	tbody tr:hover td { background: rgba(255, 255, 255, .015); }
	.rank { font-family: var(--mono); font-weight: 700; color: var(--muted); width: 44px; font-variant-numeric: tabular-nums; }
	.rank.gold { color: var(--amber); }
	.lb-name { font-weight: 600; color: var(--text); text-decoration: none; }
	.lb-name:hover { text-decoration: underline; text-underline-offset: 3px; }
	.lb-ep { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-top: 2px; display: flex; gap: 10px; flex-wrap: wrap; }
	.lb-ep a { color: inherit; text-decoration: none; }
	.lb-ep a:hover { color: var(--t2); }
	.gt { color: var(--amber); text-transform: uppercase; font-size: 10px; letter-spacing: .5px; }
	.num { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; }
	.elo { font-weight: 700; }
	.delta { font-size: 11px; }
	.delta.up { color: var(--green); }
	.delta.dn { color: var(--red); }
	.delta.eq { color: var(--dim); }
	.winbar { display: flex; align-items: center; gap: 8px; min-width: 130px; }
	.winbar .b { flex: 1; height: 4px; background: var(--card); border-radius: 2px; overflow: hidden; }
	.winbar .b i { display: block; height: 100%; background: var(--red); }
	.winbar span { font-family: var(--mono); font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; width: 34px; text-align: right; }
	.note { font-family: var(--mono); font-size: 11px; color: var(--dim); margin-top: 14px; line-height: 1.7; }
	.note b { color: var(--muted); font-weight: 600; }
	.empty { text-align: center; padding: 64px 0; color: var(--muted); display: flex; flex-direction: column; gap: 20px; align-items: center; }
	.btn-ghost { display: inline-block; background: transparent; color: var(--text); border: 1px solid var(--bh); border-radius: 6px; padding: 12px 26px; font: 600 12px var(--mono); letter-spacing: 1.5px; text-transform: uppercase; text-decoration: none; }
	.btn-ghost:hover { background: var(--raised); }

	@media (max-width: 760px) {
		.fav-page { padding: 24px 16px 48px; }
		.tally { text-align: left; }
	}
</style>
