import { fetchEpisodes } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const episodes = await fetchEpisodes();
	return { episodes };
};
