import {
	fetchStats,
	fetchEpisodes,
	fetchSets,
	fetchTopComedians,
	fetchTopics,
	fetchGuests
} from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const [stats, episodes, topSets, topComedians, topics, guests] = await Promise.all([
		fetchStats(),
		fetchEpisodes(),
		fetchSets({ sort: 'kill_score', order: 'desc', limit: 10 }),
		fetchTopComedians(10),
		fetchTopics(),
		fetchGuests()
	]);

	return {
		stats,
		episodes,
		topSets: topSets.sets,
		topComedians,
		topics,
		guests: guests.guests
	};
};
