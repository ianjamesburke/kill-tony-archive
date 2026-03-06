import { fetchGuests } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const data = await fetchGuests();
	return {
		guests: data.guests,
		baselineBucketAvg: data.baseline_bucket_avg
	};
};
