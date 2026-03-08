import type {
	Stats,
	Episode,
	ComedySet,
	SetsResponse,
	TopComedian,
	TopicStat,
	GuestDetail,
	GuestsResponse,
	CrowdReaction,
	LaughterTimeline
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

async function get<T>(path: string): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`);
	if (!res.ok) {
		throw new Error(`API error ${res.status}: ${path}`);
	}
	return res.json();
}

export async function fetchStats(): Promise<Stats> {
	return get<Stats>('/stats');
}

export async function fetchEpisodes(): Promise<Episode[]> {
	return get<Episode[]>('/episodes');
}

export async function fetchEpisode(
	episodeNumber: number
): Promise<{ episode: Episode; sets: ComedySet[] }> {
	return get(`/episodes/${episodeNumber}`);
}

export async function fetchSets(params?: {
	episode?: number;
	comedian?: string;
	status?: string;
	since?: string;
	sort?: string;
	order?: string;
	limit?: number;
	offset?: number;
}): Promise<SetsResponse> {
	const query = new URLSearchParams();
	if (params) {
		for (const [key, val] of Object.entries(params)) {
			if (val !== undefined && val !== null) {
				query.set(key, String(val));
			}
		}
	}
	const qs = query.toString();
	return get<SetsResponse>(`/sets${qs ? `?${qs}` : ''}`);
}

export async function fetchSet(setId: string): Promise<ComedySet> {
	return get<ComedySet>(`/sets/${setId}`);
}

export async function fetchTopComedians(limit = 25): Promise<TopComedian[]> {
	return get<TopComedian[]>(`/comedians/top?limit=${limit}`);
}

export async function fetchTopics(): Promise<TopicStat[]> {
	return get<TopicStat[]>('/topics');
}

export async function fetchGuests(): Promise<GuestsResponse> {
	return get<GuestsResponse>('/guests');
}

export async function fetchGuestDetail(name: string): Promise<GuestDetail> {
	return get<GuestDetail>(`/guests/${encodeURIComponent(name)}`);
}

export async function fetchCrowdReactions(): Promise<CrowdReaction[]> {
	return get<CrowdReaction[]>('/crowd-reactions');
}

export async function fetchLaughterTimeline(episodeNumber: number): Promise<LaughterTimeline | null> {
	try {
		return await get<LaughterTimeline>(`/episodes/${episodeNumber}/laughter-timeline`);
	} catch {
		return null;
	}
}
