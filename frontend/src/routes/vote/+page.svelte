<div class="coming-soon">
	<div class="cs-badge">Coming Soon</div>
	<h1 class="cs-title">Head-to-Head</h1>
	<p class="cs-desc">
		We're working on a feature that lets you vote between two sets to help rank the best Kill Tony minute of all time. Interested? Reach out and let me know.
	</p>
	<div class="cs-preview">
		<div class="cs-card">
			<div class="cs-card-label">Set A</div>
			<div class="cs-card-placeholder"></div>
		</div>
		<div class="cs-vs">VS</div>
		<div class="cs-card">
			<div class="cs-card-label">Set B</div>
			<div class="cs-card-placeholder"></div>
		</div>
	</div>
	<p class="cs-footnote">Elo-ranked crowd voting — no account needed</p>
</div>

<style>
	.coming-soon {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: 80px 24px;
		min-height: 60vh;
	}

	.cs-badge {
		font-family: var(--mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--red);
		background: var(--red-d);
		border: 1px solid rgba(220, 38, 38, 0.2);
		padding: 5px 14px;
		border-radius: 4px;
		margin-bottom: 24px;
	}

	.cs-title {
		font-size: clamp(36px, 6vw, 64px);
		font-weight: 700;
		letter-spacing: -1px;
		margin-bottom: 12px;
	}

	.cs-desc {
		font-size: 15px;
		color: var(--muted);
		line-height: 1.6;
		max-width: 420px;
		margin-bottom: 48px;
	}

	.cs-preview {
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 40px;
	}

	.cs-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
	}

	.cs-card-label {
		font-family: var(--mono);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: var(--muted);
	}

	.cs-card-placeholder {
		width: 260px;
		height: 160px;
		border-radius: 8px;
		border: 1px dashed var(--border);
		background: var(--raised);
	}

	.cs-vs {
		font-family: var(--mono);
		font-size: 20px;
		font-weight: 700;
		color: var(--red);
		letter-spacing: 2px;
	}

	.cs-footnote {
		font-family: var(--mono);
		font-size: 11px;
		color: var(--dim);
	}

	@media (max-width: 768px) {
		.coming-soon {
			padding: 48px 16px;
		}

		.cs-preview {
			flex-direction: column;
			gap: 16px;
		}

		.cs-card-placeholder {
			width: 220px;
			height: 130px;
		}
	}
</style>
