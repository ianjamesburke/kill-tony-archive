import type { Cookies } from '@sveltejs/kit';

const COOKIE = 'kta_voter';
const ONE_YEAR = 60 * 60 * 24 * 365;

/** Anonymous voter identity: a first-party httpOnly cookie, created on first visit to /vote. */
export function getVoterId(cookies: Cookies): string {
	const existing = cookies.get(COOKIE);
	if (existing && /^[0-9a-f-]{36}$/.test(existing)) return existing;
	const id = crypto.randomUUID();
	cookies.set(COOKIE, id, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		secure: true,
		maxAge: ONE_YEAR
	});
	return id;
}
