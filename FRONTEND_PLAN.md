# Kill Tony Frontend — V1 Landing Page Plan

## Hero Section
- Big stats: "X sets analyzed across Y episodes"
- Search bar: find any comedian or episode by name/number

## Section 1: All-Time Leaderboard
- Top 25 sets ranked by kill score
- Filter tabs: All / Regulars / Bucket Pulls
- Each row shows: rank, comedian name, episode #, kill score, crowd reaction, topic tags
- Click to expand → full set transcript + interview summary

## Section 2: Episode Quality Timeline
- Scatter plot: X = episode number, Y = average kill score per episode
- Dots color-coded by primary guest judge
- Secondary overlay line: episode laugh count (total `[laughter]`/`[applause]` entries from transcript)
- Hover for episode details, click to drill into episode

## Section 3: Topic Trends Over Time
- Animated bubble chart OR stacked area chart
- Each topic tag is a bubble/area, sized by frequency
- Auto-plays through episodes chronologically with play/pause
- Draggable slider/scrubber to jump to any point in time
- Shows how comedy topics shift (politics spikes during elections, etc.)

## Section 4: Guest Impact on Show Quality
- Bar chart: total laugh count per episode, averaged by guest judge
- Sorted by funniest shows → least funny
- "Which guests bring the most energy?" (e.g., does Adam Ray = more laughs?)
- Secondary metric: average kill score by guest

## Section 5: Regular Rise Charts
- Line graph showing kill score trajectory for top regulars over their appearances
- X = appearance number, Y = kill score
- Toggle between regulars to compare
- "Most Improved" highlight for biggest score increase over time

## Section 6: Fun Stats Sidebar / Cards
- Most golden tickets awarded (all-time)
- Redban's secret show picks (pattern analysis)
- Tony's Mood Ring: average tony_praise_level per episode over time
- "The One-Joke Wonder": best single-joke sets (joke_count = 1, high kill score)
- Comedian style clusters: who's most similar by topic DNA

## Kill Score Formula

```
kill_score = (
    tony_praise_level * 2        # 2-10 points
    + crowd_reaction_score        # 0-4 (silence=0, light=1, moderate=2, big_laughs=3, roaring=4)
    + joke_book_score             # 0-3 (none=0, small=1, medium=2, large=3)
    + golden_ticket * 10          # bonus
    + invited_secret_show * 5     # bonus
    + sign_up_again * 2           # bonus
)
# Range: roughly -1 to 27
# Most sets will fall in the 4-17 range
```
