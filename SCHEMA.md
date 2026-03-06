# Kill Tony Data Schema

## Episode

| Field | Type | Required | Source |
|-------|------|----------|--------|
| episode_number | integer | yes | YouTube title (regex `#(\d+)`) |
| date | date | yes | YouTube metadata |
| venue | string | no | Gemini extraction |
| youtube_url | string | yes | input |
| video_id | string | yes | input |
| guests | list[string] | yes | YouTube title + Gemini confirmation |
| full_transcript | list[TranscriptEntry] | yes | Gemini transcription (pass 1) |
| laugh_count | integer | no | Computed: count of `crowd` entries with [laughter]/[applause] |

### YouTube Stats (from yt-dlp extract_info)

| Field | Type | Description |
|-------|------|-------------|
| view_count | integer | Total views at time of processing |
| like_count | integer | Total likes |
| comment_count | integer | Total comments |
| upload_date | string | YouTube upload date (YYYYMMDD) |

### TranscriptEntry

| Field | Type | Description |
|-------|------|-------------|
| start_seconds | float | Timestamp |
| end_seconds | float | Timestamp |
| speaker | string | Label: `tony`, `redban`, `guest:ron_white`, `comedian:hans_kim`, `crowd`, `band`, `announcer` |
| text | string | What was said |

## Set (one per comedian per episode)

### Core Info

| Field | Type | Required | Source |
|-------|------|----------|--------|
| set_id | string | yes | Computed: `{episode_number}_{set_number}` |
| episode_number | integer | yes | parent episode |
| set_number | integer | yes | order in episode |
| comedian_name | string | yes | Gemini extraction |
| status | enum | yes | `bucket_pull` or `regular` |
| set_transcript | string | yes | Gemini extraction (pass 2) |
| set_start_seconds | float | yes | Gemini extraction |
| set_end_seconds | float | yes | Gemini extraction |

### Inferred Demographics (optional, only from explicit mentions)

| Field | Type | Description |
|-------|------|-------------|
| inferred_gender | string or null | Only if Tony or comedian explicitly states (e.g. "this young lady", "as a woman") |
| inferred_ethnicity | string or null | Only if comedian self-identifies (e.g. "I'm 1/8th black", "as a Latina") |

### Topic & Content

| Field | Type | Required | Source |
|-------|------|----------|--------|
| topic_tags | list[string] | no | Gemini analysis (3-5 per set) |
| joke_count | integer | no | Gemini analysis |

### Crowd & Judge Reaction

| Field | Type | Required | Source |
|-------|------|----------|--------|
| crowd_reaction | enum | no | `silence`, `light`, `moderate`, `big_laughs`, `roaring` |
| tony_praise_level | integer (1-5) | no | Gemini analysis |
| guest_feedback_sentiment | enum | no | `positive`, `negative`, `neutral`, `none` |

### Set Outcomes (all optional, default false)

| Field | Type | Description |
|-------|------|-------------|
| golden_ticket | boolean | Received Tony's golden ticket |
| sign_up_again | boolean | Tony tells them to keep signing up |
| promoted_to_regular | boolean | "You're a regular now" moment |
| invited_secret_show | boolean | Invited to Redban's secret show |
| joke_book_size | enum | `none`, `small`, `medium`, `large` |
| interview_summary | string | Brief summary of post-set interview |

### Computed (populated after extraction)

| Field | Type | Description |
|-------|------|-------------|
| appearance_num | integer | Count of this comedian across all episodes in DB |
| kill_score | float | See formula below |
| joke_density | float | joke_count / set_duration_seconds |

## Set Kill Score Formula

```
set_kill_score = (
    tony_praise_level * 2        # 2-10 points
    + crowd_reaction_score        # 0-4 (silence=0, light=1, moderate=2, big_laughs=3, roaring=4)
    + joke_book_score             # 0-3 (none=0, small=1, medium=2, large=3)
    + golden_ticket * 10          # bonus
    + invited_secret_show * 5     # bonus
    + sign_up_again * 2           # bonus
)
```

Theoretical max: 29. Set ranking uses tiebreakers: crowd_reaction ordinal DESC, then joke_density DESC.

## Episode Kill Score Formula

```
episode_kill_score = (avg_set_kill_score / 29) * 70 + (laughter_pct / 100) * 30
```

Scale: 0-100. Components:
- **70%** from average set kill score (normalized against theoretical max of 29)
- **30%** from laughter percentage (% of episode runtime with crowd laughter/applause)

Episode rank is computed from episode_kill_score DESC across all indexed episodes.
