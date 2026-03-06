import { fetchGuestDetail } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const name = decodeURIComponent(params.name);
	try {
		const guest = await fetchGuestDetail(name);
		return { guest };
	} catch {
		error(404, `Guest "${name}" not found`);
	}
};
