<script lang="ts">
	import { enhance, applyAction } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import VideoThumb from '$lib/components/VideoThumb.svelte';
	import type { VoteResult } from '$lib/types';
	import type { PageData, ActionData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	let result = $state<VoteResult | null>(null);
	let error = $state<string | null>(null);
	let submitting = $state(false);
	let votesToday = $state(0);

	$effect(() => {
		votesToday = data.matchup?.voter.votes_today ?? 0;
	});

	// Without JS the load re-runs after the action, so only trust a server-returned
	// result if it belongs to the matchup currently on screen.
	const shown = $derived.by(() => {
		if (result) return result;
		const m = data.matchup;
		if (form?.result && m && form.set_a === m.a.set_id && form.set_b === m.b.set_id) return form.result;
		return null;
	});
	const shownError = $derived(error ?? form?.error ?? null);

	function outcomeFor(setId: string) {
		if (!shown) return null;
		if (shown.winner.set_id === setId) return { ...shown.winner, won: true };
		if (shown.loser.set_id === setId) return { ...shown.loser, won: false };
		return null;
	}

	async function next() {
		result = null;
		error = null;
		await invalidateAll();
	}
</script>

<svelte:head>
	<title>Vote — Best Kill Tony Set of All Time</title>
	<meta name="description" content="Vote head-to-head on the best Kill Tony 1-minute sets of all time. Elo-ranked crowd voting to find the ultimate minute.">
	<link rel="canonical" href="https://killtonyarchive.com/vote">
	<meta property="og:title" content="Vote — Best Kill Tony Set of All Time">
	<meta property="og:description" content="Vote head-to-head on the best Kill Tony 1-minute sets of all time. Elo-ranked crowd voting to find the ultimate minute.">
	<meta property="og:type" content="website">
	<meta property="og:url" content="https://killtonyarchive.com/vote">
	<meta name="twitter:title" content="Vote — Best Kill Tony Set of All Time">
	<meta name="twitter:description" content="Vote head-to-head on the best Kill Tony 1-minute sets of all time. Elo-ranked crowd voting to find the ultimate minute.">
</svelte:head>

<div class="vote-page">
	<div class="head">
		<div>
			<div class="eyebrow">Head-to-Head</div>
			<h1>Which minute was better?</h1>
			<p class="sub">Two sets from the archive. Watch both, pick one. Every vote moves the <a href="/fan-favorites">fan rankings</a>. No account needed.</p>
		</div>
		<div class="tally">
			<div><b>{votesToday}</b> votes by you today</div>
			<div><a href="/fan-favorites">See the fan favorites →</a></div>
		</div>
	</div>

	{#if data.exhausted || !data.matchup}
		<div class="empty">
			<p>You've voted on every matchup we can offer you right now.</p>
			<a class="btn-ghost" href="/fan-favorites">See the fan favorites</a>
		</div>
	{:else}
		{@const m = data.matchup}
		{#key m.a.set_id + m.b.set_id}
			<form
				method="POST"
				action="?/vote"
				class="matchup"
				use:enhance={() => {
					submitting = true;
					error = null;
					return async ({ result: r }) => {
						submitting = false;
						if (r.type === 'success' && r.data?.result) {
							result = r.data.result as VoteResult;
							votesToday += 1;
						} else if (r.type === 'failure') {
							error = (r.data?.error as string) ?? 'Vote failed';
						} else {
							await applyAction(r);
						}
					};
				}}
			>
				<input type="hidden" name="set_a" value={m.a.set_id}>
				<input type="hidden" name="set_b" value={m.b.set_id}>

				{#each [{ side: 'A', s: m.a }, { side: 'B', s: m.b }] as { side, s } (s.set_id)}
					{@const o = outcomeFor(s.set_id)}
					<div class="card" class:won={o?.won} class:lost={o && !o.won}>
						<VideoThumb {s} {side} />
						<div class="body">
							<div class="who">
								<a class="name" href="/episodes/{s.episode_number}">{s.comedian_name}</a>
								<span class="ep">EP {s.episode_number}</span>
							</div>
							{#if s.excerpt}<p class="quote">"{s.excerpt}"</p>{/if}
							<div class="chips">
								{#if s.golden_ticket}<span class="chip gt">Golden ticket</span>{/if}
								<span class="chip">Kill Score {Math.round(s.kill_score)}</span>
								<span class="chip">#{s.kill_score_rank} by algorithm</span>
							</div>
						</div>
						{#if o}
							<div class="result">
								{#if o.won}You picked {s.comedian_name}.{:else}Not this time.{/if}
								<div class="bar"><i style="width:{Math.round(o.win_rate * 100)}%"></i></div>
								Wins <b>{Math.round(o.win_rate * 100)}%</b> of {o.matchups} matchup{o.matchups === 1 ? '' : 's'} · Elo {o.elo_before} → <b>{o.elo_after}</b>
							</div>
						{:else}
							<button class="vote" name="winner" value={s.set_id} disabled={submitting}>Vote {side}</button>
						{/if}
					</div>
					{#if side === 'A'}<div class="vs">VS</div>{/if}
				{/each}
			</form>
		{/key}

		{#if shownError}<p class="error">{shownError}</p>{/if}

		<div class="actions">
			{#if shown}
				<button class="btn-ghost" onclick={next}>Next matchup →</button>
			{:else}
				<button class="skip" onclick={next}>Haven't seen either · skip</button>
			{/if}
		</div>

		<p class="foot">Player opens at the set's timecode and stops when it ends.<br>Matchups pair sets near each other in rating. Rankings use Elo, the same system chess uses. One vote per matchup per person.</p>
	{/if}
</div>

<style>
	.vote-page { max-width: 1100px; margin: 0 auto; padding: 36px 24px 64px; }
	.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
	.eyebrow { font-family: var(--mono); font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--red); margin-bottom: 8px; }
	h1 { font-size: clamp(30px, 5vw, 48px); letter-spacing: -1px; line-height: 1; text-wrap: balance; }
	.sub { color: var(--muted); font-size: 14px; margin-top: 10px; max-width: 520px; line-height: 1.55; }
	.sub a, .tally a { color: var(--t2); text-decoration: underline; text-underline-offset: 3px; }
	.tally { font-family: var(--mono); font-size: 11px; color: var(--muted); text-align: right; line-height: 1.8; }
	.tally b { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }

	.matchup { display: grid; grid-template-columns: 1fr auto 1fr; gap: 20px; align-items: stretch; }
	.card { background: var(--raised); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; transition: border-color .15s, opacity .15s; }
	.card:hover { border-color: var(--bh); }
	.card.won { border-color: var(--red); }
	.card.lost { opacity: .55; }
	.vs { display: grid; place-items: center; font-family: var(--mono); font-size: 22px; font-weight: 700; color: var(--red); letter-spacing: 2px; }

	.body { padding: 18px 18px 16px; display: flex; flex-direction: column; gap: 10px; flex: 1; }
	.who { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
	.name { font-size: 20px; font-weight: 600; letter-spacing: -.3px; color: var(--text); text-decoration: none; }
	.name:hover { text-decoration: underline; text-underline-offset: 3px; }
	.ep { font-family: var(--mono); font-size: 11px; color: var(--muted); white-space: nowrap; }
	.quote { font-size: 14px; line-height: 1.55; color: var(--t2); font-style: italic; display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
	.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: auto; }
	.chip { font-family: var(--mono); font-size: 10px; letter-spacing: .5px; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; background: var(--card); color: var(--muted); border: 1px solid var(--border); }
	.chip.gt { color: var(--amber); background: rgba(245, 158, 11, .12); border-color: rgba(245, 158, 11, .25); }

	.vote { margin: 0 18px 18px; background: var(--red); color: #fff; border: 0; border-radius: 6px; padding: 14px; font: 600 13px var(--mono); letter-spacing: 1.5px; text-transform: uppercase; cursor: pointer; transition: filter .15s; }
	.vote:hover:not(:disabled) { filter: brightness(1.12); }
	.vote:disabled { opacity: .6; cursor: wait; }
	.result { margin: 0 18px 18px; font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: .5px; line-height: 1.6; }
	.result .bar { height: 4px; background: var(--card); border-radius: 2px; overflow: hidden; margin: 8px 0 6px; }
	.result .bar i { display: block; height: 100%; background: var(--red); }
	.result b { color: var(--text); font-variant-numeric: tabular-nums; }

	.actions { text-align: center; margin-top: 20px; }
	.btn-ghost { display: inline-block; background: transparent; color: var(--text); border: 1px solid var(--bh); border-radius: 6px; padding: 12px 26px; font: 600 12px var(--mono); letter-spacing: 1.5px; text-transform: uppercase; cursor: pointer; text-decoration: none; }
	.btn-ghost:hover { background: var(--raised); }
	.skip { background: none; border: 0; color: var(--dim); font: 11px var(--mono); cursor: pointer; letter-spacing: 1px; text-transform: uppercase; }
	.skip:hover { color: var(--muted); }
	.error { text-align: center; margin-top: 16px; font-family: var(--mono); font-size: 12px; color: var(--red-s); }
	.foot { font-family: var(--mono); font-size: 11px; color: var(--dim); text-align: center; margin-top: 36px; line-height: 1.8; }
	.empty { text-align: center; padding: 64px 0; color: var(--muted); display: flex; flex-direction: column; gap: 20px; align-items: center; }

	button:focus-visible, a:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }

	@media (max-width: 760px) {
		.vote-page { padding: 24px 16px 48px; }
		.matchup { grid-template-columns: 1fr; }
		.tally { text-align: left; }
	}
</style>
