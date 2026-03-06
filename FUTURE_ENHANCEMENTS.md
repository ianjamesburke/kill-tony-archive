# Future Enhancements

## Comment Scraping & Sentiment
- Scrape top YouTube comments per episode
- Run sentiment analysis on comments
- Compare community sentiment vs AI-generated kill scores
- "Does the audience agree with our scoring?"

## Comedy DNA Clustering
- Use topic_tags as feature vectors per comedian
- Cluster comedians by style using k-means or hierarchical clustering
- Dendrogram visualization: who's most similar to whom?
- "Comedy family trees"

## The Current Events Index
- Map real-world events to first mention in a KT set
- How quickly do current events appear in comedy?
- "Comedy as a cultural barometer"

## Survival Analysis
- Of all bucket pulls, what % return?
- Kaplan-Meier style "comedy survival curve"
- What traits predict returning? (topic choice, kill score, etc.)

## Audio-Level Analysis
- Actual laughter volume measurement from audio signal
- Applause duration in seconds (not just "crowd" transcript entries)
- Comedian delivery metrics: words per minute, pause timing

## YAMNet Laughter as Kill Score Tiebreaker
- YAMNet frame-level laughter data already stored in `laughter_frames` table (0.48s frames)
- Idea: count laughter frames in window [set_start, set_end + 5s] × 0.48 = laughter seconds per set
- Normalize to a small decimal adder (e.g. laughter_seconds / 20.0, capped at ~1.0) to break kill score ties
- **Blocked by:** WhisperX timestamp drift — set boundary windows are off by 1-2min, causing misattribution
  - Greg Bergman (big_laughs, 1.4s detected) and Zach Townsend (roaring, 1.0s) both showed near-zero due to drift
  - Hans Kim's Korean set caused YAMNet false positives (12.5s detected, only moderate crowd)
- Revisit once WhisperX timestamps are reliable

## Joke-Level Segmentation
- Break each 1-min set into individual joke attempts
- Score each joke independently
- "Best individual joke of all time" leaderboard

## Network Graph
- Comedians connected by co-appearing on same episodes
- Visual clusters showing "eras" of the show
- Guest judge connection maps

## Knockout Bracket Voting System
- User-facing voting system to break tied set rankings
- Pin tied 1-minute sets against each other in a bracket-style knockout
- Users vote on which set is better, shuffling the ranking in the database
- Helps differentiate the many ties caused by the ~25-30 point kill score range
- Could be a standalone feature or integrated into the set leaderboard page
