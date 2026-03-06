import { fetchSets, fetchCrowdReactions, fetchTopics } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
	const comedian = url.searchParams.get('comedian') || undefined;
	const status = url.searchParams.get('status') || undefined;
	const sort = url.searchParams.get('sort') || 'kill_score';
	const order = url.searchParams.get('order') || 'desc';

	const [setsData, crowdReactions, topics] = await Promise.all([
		fetchSets({ comedian, status, sort, order, limit: 200 }),
		fetchCrowdReactions(),
		fetchTopics()
	]);

	return {
		sets: setsData.sets,
		total: setsData.total,
		crowdReactions,
		topics,
		filters: { comedian, status, sort, order }
	};
};
