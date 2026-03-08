import { fetchGuests } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const data = await fetchGuests();
	return {
		guests: data.guests,
		baselineAvg: data.baseline_avg
	};
};
