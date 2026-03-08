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
	<title>Kill Tony Archive</title>
</svelte:head>

<!-- TODO: Bring back the live bar once all episodes have been indexed -->
<!-- <div class="live-bar">
	<div class="live-dot"></div>
	LIVE DATABASE
	<span class="spacer"></span>
	<span class="live-meta">
		{data.layoutStats.set_count} SETS INDEXED &middot; {data.layoutStats.episode_count} EPISODES &middot; LATEST EP #{data.layoutStats.latest_episode}
	</span>
</div> -->

<!-- NAV -->
<nav>
	<div class="nav-left">
		<a href="/" class="brand"><em>KILL</em> TONY ARCHIVE</a>
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
	<div class="footer-top">
		<div class="footer-disclaimer">All data is AI-processed and may contain inaccuracies.</div>
	</div>
	<div class="footer-links">
		<a href="https://github.com/ianjamesburke" target="_blank" rel="noopener noreferrer" class="footer-link">
			<svg viewBox="0 0 16 16" fill="currentColor" class="footer-icon"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
			GitHub
		</a>
		<a href="https://x.com/atfostermusic" target="_blank" rel="noopener noreferrer" class="footer-link">
			<svg viewBox="0 0 16 16" fill="currentColor" class="footer-icon"><path d="M9.52 6.78L15.48 0h-1.41L8.9 5.88 4.76 0H0l6.25 9.1L0 16h1.41l5.46-6.35L11.24 16H16L9.52 6.78zm-1.93 2.25l-.63-.91L1.93 1.04h2.17l4.07 5.82.63.91 5.28 7.55h-2.17L7.59 9.03z"/></svg>
			@atfostermusic
		</a>
	</div>
	<div class="footer-bottom">
		<div class="footer-left">Kill Tony Archive &middot; All data from public sources</div>
	</div>
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
		border-top: 1px solid var(--border);
	}

	.footer-top {
		text-align: center;
		margin-bottom: 14px;
	}

	.footer-disclaimer {
		font-family: var(--mono);
		font-size: 9px;
		color: var(--dim);
	}

	.footer-links {
		display: flex;
		gap: 20px;
		justify-content: center;
		margin-bottom: 14px;
	}

	.footer-bottom {
		text-align: center;
	}

	.footer-left {
		font-family: var(--mono);
		font-size: 9px;
		color: var(--dim);
		letter-spacing: 1px;
		text-transform: uppercase;
	}

	.footer-link {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		color: var(--muted);
		text-decoration: none;
		letter-spacing: 0.5px;
		transition: color 0.15s;
	}

	.footer-link:hover {
		color: var(--red);
	}

	.footer-icon {
		width: 14px;
		height: 14px;
		flex-shrink: 0;
	}

	@media (max-width: 768px) {
		nav {
			padding: 0 16px;
			height: auto;
			flex-direction: column;
			gap: 0;
		}

		.nav-left {
			flex-direction: column;
			gap: 0;
			width: 100%;
		}

		.brand {
			padding: 12px 0;
			text-align: center;
		}

		.nav-tabs {
			height: 40px;
			width: 100%;
			justify-content: center;
			gap: 0;
			border-top: 1px solid var(--border);
		}

		.nt {
			padding: 0 12px;
			font-size: 12px;
		}

		.nav-right {
			display: none;
		}

		footer {
			padding: 20px 16px;
		}
	}
</style>
