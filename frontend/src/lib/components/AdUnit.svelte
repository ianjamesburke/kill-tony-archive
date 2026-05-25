<script lang="ts">
	import { onMount } from 'svelte';

	let { adSlot = 'XXXXXXXXXX' }: { adSlot?: string } = $props();

	onMount(() => {
		try {
			((window as any).adsbygoogle = (window as any).adsbygoogle || []).push({});
		} catch {}
	});
</script>

<div class="ad-unit">
	<ins
		class="adsbygoogle"
		style="display:block"
		data-ad-client="ca-pub-6987368776964335"
		data-ad-slot={adSlot}
		data-ad-format="auto"
		data-full-width-responsive="true"
	></ins>
</div>

<style>
	.ad-unit {
		width: 100%;
		min-height: 90px;
		overflow: hidden;
	}
</style>
