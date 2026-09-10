import { fail } from '@sveltejs/kit';
import { ApiError, fetchMatchup, submitVote } from '$lib/api';
import { getVoterId } from '$lib/server/voter';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ cookies }) => {
	const voterId = getVoterId(cookies);
	try {
		return { matchup: await fetchMatchup(voterId), exhausted: false };
	} catch (err) {
		if (err instanceof ApiError && err.status === 409) {
			return { matchup: null, exhausted: true };
		}
		throw err;
	}
};

export const actions: Actions = {
	vote: async ({ request, cookies }) => {
		const voterId = getVoterId(cookies);
		const form = await request.formData();
		const set_a = String(form.get('set_a') ?? '');
		const set_b = String(form.get('set_b') ?? '');
		const winner = String(form.get('winner') ?? '');
		if (!set_a || !set_b || !winner) {
			return fail(400, { error: 'Missing matchup fields' });
		}
		try {
			const result = await submitVote({ set_a, set_b, winner, voter_id: voterId });
			return { result, set_a, set_b, winner };
		} catch (err) {
			if (err instanceof ApiError) {
				return fail(err.status, { error: err.detail });
			}
			throw err;
		}
	}
};
