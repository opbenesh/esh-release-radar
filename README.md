# esh-release-radar
A better way to discover new music.

## Project Description
`esh-release-radar` is an alternative to Spotify's own Release Radar feature. It works by:
1. Crawling through a list of predefined playlists and searching for new tracks
2. Checking the top tracks for previously liked artists to see if they've recently released anything
3. Ranking the results based on whether or not you've marked an artist as "Played" before (ML-based smarter ranking is in the making!)
4. Creating a unified review queue

I've built `esh-release-radar` in order to find cool new metal tracks for my very own metal radio show at KZRadio! Check it out at https://www.kzradio.net/shows/esh :)

## Issues and Roadmap
The source code still contains some very me-specific things (e.g. hardcoded IDs of my playlists), but I do plan to make it ready for public usage in the close future. In addition, I'm working on an ML-based recommender system using Spotify's audio features data.
