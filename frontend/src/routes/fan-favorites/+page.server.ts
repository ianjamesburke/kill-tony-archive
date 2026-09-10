import { fetchLeaderboard } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return { leaderboard: await fetchLeaderboard(100) };
};
