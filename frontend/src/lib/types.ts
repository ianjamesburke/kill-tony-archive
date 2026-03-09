export interface Stats {
	episode_count: number;
	set_count: number;
	comedian_count: number;
	avg_kill_score: number;
	golden_tickets: number;
	latest_episode: number;
}

export interface Episode {
	episode_number: number;
	date: string | null;
	venue: string | null;
	youtube_url: string | null;
	video_id: string | null;
	guests: string[];
	laugh_count: number | null;
	view_count: number | null;
	like_count: number | null;
	comment_count: number | null;
	upload_date: string | null;
	processed_at: string | null;
	set_count: number;
	avg_kill_score: number | null;
	episode_kill_score: number | null;
	episode_rank: number | null;
	total_episodes: number | null;
	laughter_pct: number | null;
	episode_summary: string | null;
}

export interface ComedySet {
	set_id: string;
	episode_number: number;
	set_number: number;
	comedian_name: string;
	status: string;
	set_transcript: string | null;
	set_start_seconds: number | null;
	set_end_seconds: number | null;
	topic_tags: string[];
	crowd_reaction: string | null;
	tony_praise_level: number | null;
	kill_score: number | null;
	golden_ticket: boolean;
	sign_up_again: boolean;
	promoted_to_regular: boolean;
	invited_secret_show: boolean;
	joke_book_size: string | null;
	interview_summary: string | null;
	disclosed_age: number | null;
	disclosed_occupation: string | null;
	disclosed_location: string | null;
	disclosed_relationship_status: string | null;
	disclosed_years_doing_comedy: number | null;
	guests: string[];
	venue: string | null;
	date: string | null;
	set_rank: number | null;
	total_sets: number | null;
}

export interface SetsResponse {
	sets: ComedySet[];
	total: number;
	limit: number;
	offset: number;
}

export interface TopComedian {
	comedian_name: string;
	appearances: number;
	avg_kill_score: number;
	best_kill_score: number;
	golden_tickets: number;
	status: string;
}

export interface TopicStat {
	topic: string;
	count: number;
}

export interface GuestStat {
	guest_name: string;
	episodes: number[];
	episode_count: number;
	avg_kill_score: number | null;
	avg_bucket_score: number | null;
	score_lift: number | null;
	total_laugh_count: number;
}

export interface GuestsResponse {
	guests: GuestStat[];
	baseline_avg: number;
}

export interface GuestEpisode {
	episode_number: number;
	date: string | null;
	venue: string | null;
	guests: string[];
	laugh_count: number | null;
	avg_kill_score: number | null;
	avg_bucket_score: number | null;
	set_count: number;
	hot_sets: number;
}

export interface GuestDetail {
	guest_name: string;
	episodes: GuestEpisode[];
	episode_count: number;
	avg_kill_score: number | null;
	avg_bucket_score: number | null;
	avg_laugh_count: number | null;
	total_laugh_count: number;
	baseline_avg: number;
}

export interface TopicTimelineEntry {
	episode_number: number;
	date: string | null;
	topics: Record<string, number>;
}

export interface CrowdReaction {
	crowd_reaction: string;
	count: number;
}

export interface SetsStats {
	scores: number[];
	crowd_reactions: CrowdReaction[];
	bucket_count: number;
	regular_count: number;
	bucket_avg: number | null;
	regular_avg: number | null;
	total: number;
	latest_episode: number | null;
}

export interface LaughterTimelinePoint {
	t: number;
	v: number;
}

export interface LaughterSetMarker {
	set_id: string;
	set_number: number;
	comedian_name: string;
	start: number;
	end: number;
	status: string;
}

export interface LaughterTimeline {
	episode_number: number;
	bucket_seconds: number;
	total_laughter_seconds: number | null;
	timeline: LaughterTimelinePoint[];
	sets: LaughterSetMarker[];
}
