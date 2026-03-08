import {
	fetchStats,
	fetchEpisodes,
	fetchSets,
	fetchTopics,
	fetchGuests
} from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const [stats, episodes, topSets, topics, guests] = await Promise.all([
		fetchStats(),
		fetchEpisodes(),
		fetchSets({ sort: 'kill_score', order: 'desc', limit: 10 }),
		fetchTopics(),
		fetchGuests()
	]);

	return {
		stats,
		episodes,
		topSets: topSets.sets,
		topics,
		guests: guests.guests
	};
};
