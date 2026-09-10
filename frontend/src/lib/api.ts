import type {
	Stats,
	Episode,
	ComedySet,
	SetsResponse,
	SetsStats,
	TopComedian,
	TopicStat,
	TopicTimelineEntry,
	GuestDetail,
	GuestsResponse,
	CrowdReaction,
	LaughterTimeline,
	Matchup,
	VoteResult,
	Leaderboard
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string,
		path: string
	) {
		super(`API error ${status} on ${path}: ${detail}`);
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, init);
	if (!res.ok) {
		let detail = res.statusText;
		try {
			detail = (await res.json()).detail ?? detail;
		} catch {
			/* non-JSON error body */
		}
		throw new ApiError(res.status, detail, path);
	}
	return res.json();
}

async function get<T>(path: string): Promise<T> {
	return request<T>(path);
}

async function post<T>(path: string, body: unknown): Promise<T> {
	return request<T>(path, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
}

export async function fetchStats(): Promise<Stats> {
	return get<Stats>('/stats');
}

export async function fetchEpisodes(withDataOnly = true): Promise<Episode[]> {
	return get<Episode[]>(`/episodes?with_data=${withDataOnly}`);
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

export async function fetchSetsStats(params?: {
	since?: string;
	episode?: number;
}): Promise<SetsStats> {
	const query = new URLSearchParams();
	if (params) {
		for (const [key, val] of Object.entries(params)) {
			if (val !== undefined && val !== null) {
				query.set(key, String(val));
			}
		}
	}
	const qs = query.toString();
	return get<SetsStats>(`/sets/stats${qs ? `?${qs}` : ''}`);
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

export async function fetchTopicTimeline(): Promise<TopicTimelineEntry[]> {
	return get<TopicTimelineEntry[]>('/topics/timeline');
}

export async function fetchGuests(): Promise<GuestsResponse> {
	return get<GuestsResponse>('/guests');
}

export async function fetchGuestDetail(name: string): Promise<GuestDetail> {
	return get<GuestDetail>(`/guests/${encodeURIComponent(name)}`);
}

export function guestCardImageUrl(name: string): string {
	return `${API_BASE}/guests/${encodeURIComponent(name)}/card.png`;
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

export async function fetchMatchup(voterId: string): Promise<Matchup> {
	return get<Matchup>(`/vote/matchup?voter_id=${encodeURIComponent(voterId)}`);
}

export async function submitVote(vote: {
	set_a: string;
	set_b: string;
	winner: string;
	voter_id: string;
}): Promise<VoteResult> {
	return post<VoteResult>('/vote', vote);
}

export async function fetchLeaderboard(limit = 50): Promise<Leaderboard> {
	return get<Leaderboard>(`/vote/leaderboard?limit=${limit}`);
}
