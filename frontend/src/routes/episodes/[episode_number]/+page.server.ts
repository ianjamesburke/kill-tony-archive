import { fetchEpisode } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const epNum = parseInt(params.episode_number, 10);
	if (isNaN(epNum)) {
		error(400, 'Invalid episode number');
	}

	try {
		const data = await fetchEpisode(epNum);
		return {
			episode: data.episode,
			sets: data.sets
		};
	} catch {
		error(404, `Episode #${epNum} not found`);
	}
};
