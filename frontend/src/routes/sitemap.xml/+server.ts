import { fetchEpisodes, fetchGuests } from '$lib/api';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	const [episodes, guestsData] = await Promise.all([
		fetchEpisodes(),
		fetchGuests()
	]);

	const baseUrl = 'https://killtonyarchive.com';
	const today = new Date().toISOString().split('T')[0];

	interface SitemapEntry {
		loc: string;
		priority: string;
		changefreq: string;
		lastmod?: string;
	}

	const staticPages: SitemapEntry[] = [
		{ loc: '', priority: '1.0', changefreq: 'daily' },
		{ loc: '/episodes', priority: '0.9', changefreq: 'daily' },
		{ loc: '/sets', priority: '0.9', changefreq: 'daily' },
		{ loc: '/guests', priority: '0.8', changefreq: 'weekly' },
		{ loc: '/vote', priority: '0.5', changefreq: 'monthly' }
	];

	const episodePages: SitemapEntry[] = episodes.map((ep) => ({
		loc: `/episodes/${ep.episode_number}`,
		priority: '0.7',
		changefreq: 'weekly',
		lastmod: ep.date ? formatDate(ep.date) : undefined
	}));

	const guestPages: SitemapEntry[] = guestsData.guests.map((guest) => ({
		loc: `/guests/${encodeURIComponent(guest.guest_name)}`,
		priority: '0.6',
		changefreq: 'weekly'
	}));

	const allPages = [...staticPages, ...episodePages, ...guestPages];

	const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages
	.map(
		(page) => `  <url>
    <loc>${baseUrl}${page.loc}</loc>
    <changefreq>${page.changefreq}</changefreq>
    <priority>${page.priority}</priority>${page.lastmod ? `\n    <lastmod>${page.lastmod}</lastmod>` : ''}
  </url>`
	)
	.join('\n')}
</urlset>`;

	return new Response(xml, {
		headers: {
			'Content-Type': 'application/xml',
			'Cache-Control': 'max-age=3600'
		}
	});
};

function formatDate(dateStr: string): string {
	// Dates come as YYYYMMDD from the API, convert to YYYY-MM-DD
	if (dateStr.length === 8 && !dateStr.includes('-')) {
		return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
	}
	return dateStr;
}
