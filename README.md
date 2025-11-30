# NavidroFM
Generate automatic Spotify-like playlists for your Navidrome instance.

# About
This tool uses public scrobble history to get information about your music taste and recommendations, downloads those songs via [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi), then imports them as Navidrome playlists for you to listen to.

## Playlists

| Provider     | Playlist             | Function                                       |
| ------------ | -------------------- | ---------------------------------------------- |
| LastFM       | Discover Recommended | Recommendations of songs you may like.         |
| LastFM       | Recommended Mix      | Mix of tracks to discover and tracks you know. |
| LastFM       | Library Mix          | Mix of songs from your existing library.       |
| ListenBrainz | Weekly Exploration   | Discover new tracks based on your history.     |
| ListenBrainz | Weekly Jams          | Mix of songs, both new and from your library.  |

Note: The LastFM Library playlist will never download any tracks, instead it simply queries the songs and searches Navidrome for them to add to the playlist.

<details>
<summary>LastFM Endpoint Info</summary>
Currently, the tool uses the following LastFM json endpoints (courtesy of u/stdeem):

Discover Recommended: https://www.last.fm/player/station/user/username/recommended

Recommended Mix: https://www.last.fm/player/station/user/username/mix

Library Mix: https://www.last.fm/player/station/user/username/library
</details>

## How it Works
This tool runs on a cron schedule using `TZ` that gets songs from the endpoints based on the usernames you provide in `docker-compose`.

After querying enough songs (plus backups in case a download or search fails) to fulfill the playlist criteria, the tool begins querying the YouTube Music API to find and download the tracks and apply correct metadata. Already existing tracks in Navidrome are skipped. Once the download is complete, the tool searches Navidrome for the tracks and adds them to the corresponding playlist.

When the cron schedule re-runs, it deletes all of the downloaded tracks (and never your local tracks) and begins the process again.

# Installation
1. Download `docker-compose.yml` from this repo
2. Configure your environment variables:

   Cron defaults to 4:00am on Mondays.
  ```
      TZ: Your/Timezone
      NAVIDROME_URL: http://navidrome:4533
      NAVIDROME_USERNAME: username
      NAVIDROME_PASSWORD: password
      SYNC_SCHEDULE: "0 4 * * 1"
  ```
3. Configure playlist variables
   
   Playlists all default to false but can be enabled with `"true"` (See below).
   
      3.1 LastFM
   
      The default track count for both Recommended playlists defaults to 25, Library is 50.
      ```
         LASTFM_USERNAME: username
         RECOMMENDED: "true"
         RECOMMENDED_TRACKS: "25"
         MIX: "true"
         MIX_TRACKS: "25"
         LIBRARY: "true"
         LIBRARY_TRACKS: "50"
      ```
   
      3.2 ListenBrainz

      The default track count for both playlists defaults to 25 with a max of 50.
      ```
         LZ_USERNAME: username
         EXPLORATION: "true"
         EXPLORATION_TRACKS: "25"
         JAMS: "true"
         JAMS_TRACKS: "25"
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

Right now I am looking for assistance in:

   * Switching to Alpine (Kept encountering weird yt-dlp errors)

   * A better way to scan the library after a download is done.

## Issues
If you encounter an issue, you can open an issue here. Please provide logs from everything to help me better help you.
