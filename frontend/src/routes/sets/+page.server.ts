import { fetchSets, fetchSetsStats } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const [setsData, statsData] = await Promise.all([
		fetchSets({ sort: 'kill_score', order: 'desc', limit: 50 }),
		fetchSetsStats()
	]);

	return {
		sets: setsData.sets,
		total: setsData.total,
		stats: statsData
	};
};
