<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import type { LayoutData } from './$types';

	let { children, data }: { children: any; data: LayoutData } = $props();

	function isActive(path: string): boolean {
		if (path === '/') return page.url.pathname === '/';
		return page.url.pathname.startsWith(path);
	}
</script>

<svelte:head>
	<title>Kill Tony DB</title>
</svelte:head>

<!-- LIVE BAR -->
<div class="live-bar">
	<div class="live-dot"></div>
	LIVE DATABASE
	<span class="spacer"></span>
	<span class="live-meta">
		{data.layoutStats.set_count} SETS INDEXED &middot; {data.layoutStats.episode_count} EPISODES &middot; LATEST EP #{data.layoutStats.latest_episode}
	</span>
</div>

<!-- NAV -->
<nav>
	<div class="nav-left">
		<a href="/" class="brand"><em>KILL</em> TONY DB</a>
		<div class="nav-tabs">
			<a href="/" class="nt" class:active={isActive('/')}>Overview</a>
			<a href="/episodes" class="nt" class:active={isActive('/episodes')}>Episodes</a>
			<a href="/sets" class="nt" class:active={isActive('/sets')}>Sets</a>
			<a href="/guests" class="nt" class:active={isActive('/guests')}>Guests</a>
		</div>
	</div>
	<div class="nav-right">
		<div class="nav-tag">Kill Score v2.1</div>
	</div>
</nav>

<!-- PAGE CONTENT -->
{@render children()}

<!-- FOOTER -->
<footer>
	<div class="footer-left">Kill Tony DB &middot; Data Science Thesis &middot; All data from public sources</div>
	<div class="footer-right">Built with SvelteKit + FastAPI</div>
</footer>

<style>
	.live-bar {
		background: var(--red);
		padding: 5px 24px;
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: white;
	}

	.live-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: white;
		animation: blink 1.4s ease-in-out infinite;
	}

	@keyframes blink {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.3;
		}
	}

	.spacer {
		flex: 1;
	}

	.live-meta {
		opacity: 0.65;
		font-weight: 400;
		letter-spacing: 0.5px;
	}

	nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 40px;
		height: 54px;
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}

	.nav-left {
		display: flex;
		align-items: center;
		gap: 36px;
	}

	.brand {
		font-family: var(--mono);
		font-size: 13px;
		font-weight: 700;
		letter-spacing: 3px;
		text-transform: uppercase;
		text-decoration: none;
		color: var(--text);
	}

	.brand em {
		color: var(--red);
		font-style: normal;
	}

	.nav-tabs {
		display: flex;
		height: 54px;
	}

	.nt {
		display: flex;
		align-items: center;
		padding: 0 18px;
		font-size: 13px;
		font-weight: 500;
		color: var(--muted);
		cursor: pointer;
		border-bottom: 2px solid transparent;
		transition:
			color 0.15s,
			border-color 0.15s;
		letter-spacing: 0.3px;
		text-decoration: none;
	}

	.nt:hover {
		color: var(--t2);
	}

	.nt.active {
		color: var(--text);
		border-bottom-color: var(--red);
	}

	.nav-right {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.nav-tag {
		font-family: var(--mono);
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--muted);
		background: var(--raised);
		border: 1px solid var(--border);
		padding: 5px 12px;
		border-radius: 4px;
	}

	footer {
		padding: 24px 40px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-top: 1px solid var(--border);
	}

	footer .footer-left,
	footer .footer-right {
		font-family: var(--mono);
		font-size: 10px;
		color: var(--muted);
		letter-spacing: 1px;
		text-transform: uppercase;
	}
</style>
