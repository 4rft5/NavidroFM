# NavidroFM
Generate automatic Spotify-like playlists for your Navidrome instance.

# About
This tool uses exposed LastFM json endpoints to get information about your scrobble history, downloads those songs via [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi), then imports them as Navidrome playlists for you to listen to.

## Playlists
As described above, the tool makes three playlists:

Discover Recommended is more about pure recommendations from LastFM about songs you may like.

Recommended Mix is a mix of tracks to discover and tracks you already enjoy.

Library Mix is made up of songs from your existing library.

<details>
<summary>Endpoint Info</summary>
Currently, the tool uses the following LastFM json endpoints (courtesy of u/stdeem):

Discover Recommended: https://www.last.fm/player/station/user/username/recommended

Recommended Mix: https://www.last.fm/player/station/user/username/mix

Library Mix: https://www.last.fm/player/station/user/username/library
</details>

# How it Works
This tool runs on a cron schedule using `TZ` that gets songs from the json endpoints based on the username you provide in `docker-compose`. This means that you do not need to authenticate for LastFM, and can even download playlists using others' usernames, if you so please.

After querying enough songs (plus backups in case a download or search fails) to fulfill the playlist criteria, the tool begins querying the YouTube Music API to find and download the tracks. Already existing tracks in Navidrome are skipped. Once the download is complete, the tool searches Navidrome for the tracks and adds them to the corresponding playlist. The playlist is cleared, not deleted as to retain the same ID.

Note: The Library playlist will never download any tracks, instead it simply queries the songs and searches Navidrome for them to add to the playlist.

When the cron schedule re-runs, it deletes all of the discover tracks (but not your local tracks) and begins the process again.

# Installation
1. Download `docker-compose.yml` from this repo
2. Configure your environment variables:

   Cron defaults to 4:00am on Mondays.
  ```
      TZ: Your/Timezone
      LASTFM_USERNAME: username
      NAVIDROME_URL: http://navidrome:4533
      NAVIDROME_USERNAME: username
      NAVIDROME_PASSWORD: password
      SYNC_SCHEDULE: "0 4 * * 1"
  ```
3. Configure playlist variables
   
   Playlists all default to enabled with `true` but can be disabled with `false`.
   
   The default track count for both Recommended playlists defaults to 25, Library is 50.
   ```
      RECOMMENDED: "true"
      RECOMMENDED_TRACKS: "25"
      MIX: "true"
      MIX_TRACKS: "25"
      LIBRARY: "true"
      LIBRARY_TRACKS: "50"
   ```
5. Set Volumes in compose
   
   The path for `/your/music/library` can be set to the same path as Navidrome uses. The tool makes its own folder `navidrofm` in which it places its downloaded songs.
   
   The volume for `cookies.txt` is optional but [(Cookies are highly recommended)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
   ```
       volumes:
      - /your/music/library:/music
      - ./cookies.txt:/app/cookies/cookies.txt
   ```
7. Deploy and test
   
   Run `docker compose up -d`.
   
   If you want the sync to run on start, you can set `RUN_ON_STARTUP: "true"`. Otherwise, the sync will run once it gets the first run from cron.
   
   The tool will run and download tracks as outlined above.

## Contributions
If you want to add something or clean up code, feel free to open a PR on this repo.

## Issues
I have not encountered any issues during my testing, but if you encounter an issue, you can open an issue here. Please provide logs from everything to help me better help you.
