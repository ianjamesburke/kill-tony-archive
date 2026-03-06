# Kill Tony Data Project

## Project Goal

Build a transcribed database of every Kill Tony 1-minute set, analyzed by Gemini Flash, with the end goal of algorithmically generating the **best Kill Tony minute of all time**.

This DB will also act as a portfolio project and github repo, with an acopanying frontend where people can see interesting visualization like, joke books awards by joke topic, or joke topics spread changeing over time. 
I also want some interesting animations showing the data.
this project is a data science college thisis project.


## What is Kill Tony?

Kill Tony is a weekly comedy podcast/show hosted by Tony Hinchcliffe where random comedians pull a golden ticket to perform a 1-minute stand-up set. After each set, they are interviewed by Tony and the house band/guests. The show has run for 600+ episodes.

## Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite
- **Analysis:** Gemini Flash lite 3.1 (structured data extraction from transcripts)
- **Frontend:** To be determined

## Pipeline Overview (Two-Pass Chunked)

1. Download episode audio from YouTube (yt-dlp), convert to MP3 (ffmpeg)
2. Split into 20min overlapping chunks (3min overlap to avoid splitting sets)
3. **Pass 1:** Upload each chunk to Gemini → get speaker-labeled transcript
4. Merge chunks, deduplicate overlap regions, normalize speaker labels
5. **Pass 2:** Send full transcript text to Gemini → extract structured set data
6. Store in SQLite, expose via FastAPI

## Data Schema

See [SCHEMA.md](SCHEMA.md) for the full data model (episode, set, transcript entry, outcomes, computed fields).

## Website Testing & Screenshots

When asked to pull up a website for UI testing or analysis:
- **Default approach:** Use headless Playwright instances to take and analyze screenshots
- **Never:** Hijack/control the user's Chrome browser instance
- **Workflow:** Launch headless browser → navigate → take screenshot → read/analyze the image
- **Installed skills:** playwright-generate-test, playwright-explore-website, playwright-automation-fill-in-form, playwright-cli, playwright-best-practices, playwright-skill


