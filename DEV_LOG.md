# Kill Tony Data Project - Dev Log

## Test Episode
- **URL:** https://www.youtube.com/watch?v=hpncO7ak9m8
- **Purpose:** Primary test case for transcript extraction and analysis pipeline refinement

## Progress

### Phase 1: Transcription ✓ COMPLETE
- [x] Get episode number from metadata (extracted #589)
- [x] Transcribe audio with Gemini 3.1 Flash Lite (14 entries)
- [x] Save as `KT#XXX.txt` format (KT#589.txt)
- [x] Verify transcript quality
- **Status:** Successfully transcribed KT#589 (Ron White episode)
- **File:** `data/transcripts/KT#589.txt`
- **Entries:** 14 segments extracted

### Phase 2: Analysis Prompt
- [ ] Design prompt for Gemini to structure transcript
- [ ] Extract: chapters, themes, comedians, metadata
- [ ] Test output quality

## Technical Fixes Applied
- Fixed JSON parsing to handle MM:SS.MS timestamp format
- Added sanitization for Gemini's extra JSON fields (box_2d, label, etc.)
- Loads GEMINI_API_KEY from root .env file
- Extracts episode number from video title automatically

## Notes
- Keeping transcription and analysis as separate steps
- Using .env GEMINI_API_KEY at root
- Focus on MVP - get working solution, not perfect
- Large episodes (~70MB) are being handled efficiently
