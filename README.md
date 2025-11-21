# NavidroFM
Generate Automatic Spotify-like playlists for your Navidrome instance.

# About
This tool uses exposed LastFM json endpoints to get information about your scrobble history, downloads those songs via [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi), then imports them into Navidrome for you to listen to.

## Playlists
As described above, the tool makes three playlists. Discover Recommended is more about pure recommendations from LastFM about songs you may like, Discover Mix is a mix of tracks to discover and tracks you already enjoy, and Library Mix is made up of songs from your existing library.

Currently, the tool uses the following LastFM json endpoints [(Courtesy of u/stdeem)](https://www.reddit.com/r/lastfm/comments/d2svfs/comment/fft8xef/?context=3):

Discover Recommended: https://www.last.fm/player/station/user/%7Busername%7D/recommended

Discover Mix: https://www.last.fm/player/station/user/%7Busername%7D/mix

Library Mix: https://www.last.fm/player/station/user/%7Busername%7D/library

# How it Works
This tool runs on a cron schedule (or automatically on start, if configured) (defaults to 4:00am on Mondays) using `TZ` that gets songs from the json endpoints based on the username you provide in `docker-compose`. This means that you do not need to authenticate for LastFM, and can even download playlists using others' usernames, if you so please.

After querying the json enough songs (plus backups) to fulfill the playlist criteria (Discover Recommended and Mix default to 25, Library is 50), the tool begins querying the YouTube Music API to find and download the tracks [(Cookies are highly recommended)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies). Already existing tracks in Navidrome are skipped. Once the download is complete, the tool searches Navidrome for the tracks searched, and adds them to the corresponding playlist. The playlist is not deleted as to retain the same ID.

When the cron schedule re-runs, it deletes all of the discover tracks (but not your local tracks) and begins the process again.

# Installation
1. Download `docker-compose.yml` from this repo
2. Configure your environment variables:
  ```
      TZ: America/Denver
      LASTFM_USERNAME: musername
      NAVIDROME_URL: http://navidrome:4533
      NAVIDROME_USERNAME: username
      NAVIDROME_PASSWORD: password
      SYNC_SCHEDULE: "0 4 * * 1"
  ```
3. Configure playlist variables
   Playlists all default to enabled (true) but can be disabled with false.
   The track length for both Recommended playlists defaults to 25, library is 50)
   ```
      RECOMMENDED: "true"
      RECOMMENDED_TRACKS: "25"
      MIX: "true"
      MIX_TRACKS: "25"
      LIBRARY: "true"
      LIBRARY_TRACKS: "50"
   ```
4. Set Volumes in compose
   The path for `/your/music/library` can be set to the same path as Navidrome uses. The tool makes its own folder `navidrofm` in which it places its downloaded songs.
   The path for `cookies.txt` is optional but [(Cookies are highly recommended)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
   ```
       volumes:
      - /your/music/library:/music
      - ./cookies.txt:/app/cookies/cookies.txt
   ```
5. Deploy and test
   Run `docker compose up -d`.
   If you want the sync to run on start, you can set `RUN_ON_STARTUP: "true"`. Otherwise, the sync will run once it gets the first run from cron.
   The tool will run and download tracks as outlined above.

## Contributions
If you want to add something or clean up code, feel free to open a PR on this repo.

## Issues
I have not encountered any issues during my testing, but if you encounter an issue, you can open an issue here. Please provide logs from everything to help me better help you.
