import { fetchStats } from '$lib/api';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async () => {
	const stats = await fetchStats();
	return { layoutStats: stats };
};
