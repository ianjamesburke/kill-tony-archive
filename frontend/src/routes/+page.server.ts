import {
	fetchStats,
	fetchEpisodes,
	fetchSets,
	fetchTopics,
	fetchTopicTimeline,
	fetchGuests
} from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const [stats, episodes, topSets, topics, topicTimeline, guests] = await Promise.all([
		fetchStats(),
		fetchEpisodes(),
		fetchSets({ sort: 'kill_score', order: 'desc', limit: 10 }),
		fetchTopics(),
		fetchTopicTimeline(),
		fetchGuests()
	]);

	return {
		stats,
		episodes,
		topSets: topSets.sets,
		topics,
		topicTimeline,
		guests: guests.guests
	};
};
