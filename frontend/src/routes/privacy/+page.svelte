<svelte:head>
	<title>Privacy Policy — Kill Tony Archive</title>
	<meta name="description" content="Privacy policy for Kill Tony Archive, including information about advertising, cookies, and how to opt out.">
	<link rel="canonical" href="https://killtonyarchive.com/privacy">
	<meta property="og:title" content="Privacy Policy — Kill Tony Archive">
	<meta property="og:description" content="Privacy policy for Kill Tony Archive.">
	<meta property="og:url" content="https://killtonyarchive.com/privacy">
</svelte:head>

<div class="privacy-page">
	<div class="privacy-inner">
		<h1 class="privacy-title">Privacy Policy</h1>
		<p class="privacy-date">Last updated: May 2026</p>

		<section class="privacy-section">
			<h2>Overview</h2>
			<p>Kill Tony Archive ("we", "us", "our") is a fan-built database of Kill Tony episodes and sets. This policy explains how we collect and use data when you visit <strong>killtonyarchive.com</strong>.</p>
		</section>

		<section class="privacy-section">
			<h2>Advertising</h2>
			<p>We use Google AdSense to display advertisements on this site. Google AdSense uses cookies and similar tracking technologies to serve ads based on your prior visits to this and other websites.</p>
			<p>Google's use of advertising cookies enables it and its partners to serve ads based on your visit to this site and/or other sites on the internet. You may opt out of personalised advertising by visiting <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener noreferrer">Google Ads Settings</a>.</p>
		</section>

		<section class="privacy-section">
			<h2>Cookies</h2>
			<p>We do not set first-party cookies. Third-party services used on this site (Google AdSense, YouTube embeds) may set their own cookies to function. These are governed by each provider's own privacy policies:</p>
			<ul>
				<li><a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google Privacy Policy</a></li>
				<li><a href="https://www.youtube.com/t/privacy" target="_blank" rel="noopener noreferrer">YouTube Privacy Policy</a></li>
			</ul>
		</section>

		<section class="privacy-section">
			<h2>Data We Collect</h2>
			<p>Kill Tony Archive does not collect or store any personally identifiable information from visitors. We do not require account creation, logins, or form submissions.</p>
			<p>Standard server logs (IP address, browser user agent, pages visited) may be retained for up to 30 days by our hosting provider (Railway) for operational purposes.</p>
		</section>

		<section class="privacy-section">
			<h2>Opting Out of Personalised Ads</h2>
			<p>You can opt out of personalised advertising from Google and other participating ad networks through:</p>
			<ul>
				<li><a href="https://www.google.com/settings/ads" target="_blank" rel="noopener noreferrer">Google Ads Settings</a></li>
				<li><a href="https://optout.aboutads.info/" target="_blank" rel="noopener noreferrer">Digital Advertising Alliance opt-out</a></li>
				<li><a href="https://optout.networkadvertising.org/" target="_blank" rel="noopener noreferrer">Network Advertising Initiative opt-out</a></li>
			</ul>
			<p>You can also use your browser's privacy settings or an ad blocker to block ads entirely.</p>
		</section>

		<section class="privacy-section">
			<h2>Third-Party Content</h2>
			<p>Episode pages embed YouTube videos. YouTube may collect data when these embeds load. See <a href="https://www.youtube.com/t/privacy" target="_blank" rel="noopener noreferrer">YouTube's Privacy Policy</a> for details.</p>
		</section>

		<section class="privacy-section">
			<h2>Contact</h2>
			<p>Questions about this policy? Reach out via <a href="https://x.com/atfostermusic" target="_blank" rel="noopener noreferrer">@atfostermusic on X</a>.</p>
		</section>
	</div>
</div>

<style>
	.privacy-page {
		padding: 60px 40px;
		max-width: 800px;
		margin: 0 auto;
	}

	.privacy-title {
		font-size: 36px;
		font-weight: 700;
		letter-spacing: -1px;
		margin-bottom: 6px;
	}

	.privacy-date {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--muted);
		margin-bottom: 48px;
		letter-spacing: 0.5px;
	}

	.privacy-section {
		margin-bottom: 36px;
	}

	.privacy-section h2 {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--red);
		margin-bottom: 12px;
	}

	.privacy-section p {
		font-size: 14px;
		color: var(--t2);
		line-height: 1.7;
		margin-bottom: 10px;
	}

	.privacy-section ul {
		list-style: none;
		padding: 0;
		margin: 10px 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.privacy-section li {
		font-size: 14px;
		color: var(--t2);
		padding-left: 16px;
		position: relative;
	}

	.privacy-section li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: var(--dim);
	}

	.privacy-section a {
		color: var(--red-s);
		text-decoration: none;
		transition: color 0.15s;
	}

	.privacy-section a:hover {
		color: var(--red);
	}

	@media (max-width: 768px) {
		.privacy-page {
			padding: 32px 16px;
		}

		.privacy-title {
			font-size: 26px;
		}
	}
</style>
