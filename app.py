#!/usr/bin/env python3
import os
import sys
import json
import requests
import subprocess
import time
import hashlib
import re
import secrets
import fcntl
from pathlib import Path
from typing import List, Dict, Optional
from ytmusicapi import YTMusic
from datetime import datetime
from zoneinfo import ZoneInfo

LOCK_FILE = '/tmp/navidrofm.lock'

def acquire_lock():
    """Try to acquire lock, return file descriptor or None"""
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        return None

def release_lock(lock_fd):
    """Release the lock"""
    if lock_fd:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except:
            pass

def log(message: str):
    """Print with immediate flush for real-time logging"""
    print(message, flush=True)

class NavidroFM:
    def __init__(self):

        tz_name = os.getenv('TZ', 'UTC')
        try:
            self.timezone = ZoneInfo(tz_name)
        except Exception:
            log(f"Warning: Invalid timezone '{tz_name}', using UTC")
            self.timezone = ZoneInfo('UTC')
        
        self.lastfm_user = os.getenv('LASTFM_USERNAME')
        if not self.lastfm_user:
            raise ValueError("LASTFM_USERNAME environment variable is required")
        
        self.navidrome_url = os.getenv('NAVIDROME_URL', '').rstrip('/')
        self.navidrome_user = os.getenv('NAVIDROME_USERNAME')
        self.navidrome_pass = os.getenv('NAVIDROME_PASSWORD')
        
        if not all([self.navidrome_url, self.navidrome_user, self.navidrome_pass]):
            raise ValueError("NAVIDROME_URL, NAVIDROME_USERNAME, and NAVIDROME_PASSWORD are required")
        
        log(f"Connecting to Navidrome at {self.navidrome_url}...")
        
        salt = secrets.token_hex(8)
        token = hashlib.md5(f"{self.navidrome_pass}{salt}".encode()).hexdigest()
        
        self.subsonic_params = {
            'u': self.navidrome_user,
            't': token,
            's': salt,
            'v': '1.16.1',
            'c': 'lastfm-sync',
            'f': 'json'
        }
        
        try:
            response = self._make_request('ping')
            subsonic_response = response.get('subsonic-response', {})
            status = subsonic_response.get('status')
            
            if status == 'ok':
                log("Successfully connected to Navidrome")
            else:
                error = subsonic_response.get('error', {})
                error_message = error.get('message', 'unknown error')
                raise ConnectionError(f"Navidrome auth failed: {error_message}")
        except requests.exceptions.RequestException as e:
            log(f"Failed to connect to Navidrome: {e}")
            raise
        except Exception as e:
            log(f"Failed to connect to Navidrome: {e}")
            raise
        
        try:
            self.ytmusic = YTMusic()
            log("YouTube Music API initialized")
        except Exception as e:
            log(f"Failed to initialize YouTube Music API: {e}")
            raise
        
        self.music_dir = Path('/music/navidrofm')
        self.cookie_file = Path('/app/cookies/cookies.txt')
        
        self.playlists = {
            'recommended': {
                'enabled': os.getenv('RECOMMENDED', 'false').lower() == 'true',
                'tracks': int(os.getenv('RECOMMENDED_TRACKS', '25')),
                'url': f'https://www.last.fm/player/station/user/{self.lastfm_user}/recommended',
                'name': 'Discover Recommended',
                'dir': self.music_dir / 'recommended',
                'schedule': os.getenv('RECOMMENDED_SCHEDULE', '0 4 * * 1')
            },
            'mix': {
                'enabled': os.getenv('MIX', 'false').lower() == 'true',
                'tracks': int(os.getenv('MIX_TRACKS', '25')),
                'url': f'https://www.last.fm/player/station/user/{self.lastfm_user}/mix',
                'name': 'Recommended Mix',
                'dir': self.music_dir / 'mix',
                'schedule': os.getenv('MIX_SCHEDULE', '0 4 * * 1')
            },
            'library': {
                'enabled': os.getenv('LIBRARY', 'false').lower() == 'true',
                'tracks': int(os.getenv('LIBRARY_TRACKS', '50')),
                'url': f'https://www.last.fm/player/station/user/{self.lastfm_user}/library',
                'name': 'Library Mix',
                'dir': None,
                'schedule': os.getenv('LIBRARY_SCHEDULE', '0 4 * * 1')
            }
        }

        self.listenbrainz_user = os.getenv('LZ_USERNAME')
        
        if self.listenbrainz_user:
            self.listenbrainz_playlists = {
                'exploration': {
                    'enabled': os.getenv('EXPLORATION', 'false').lower() == 'true',
                    'tracks': min(int(os.getenv('EXPLORATION_TRACKS', '25')), 50),
                    'name': 'Weekly Exploration',
                    'dir': self.music_dir / 'exploration',
                    'schedule': os.getenv('EXPLORATION_SCHEDULE', '0 4 * * 1'),
                    'playlist_type': 'weekly-exploration'
                },
                'jams': {
                    'enabled': os.getenv('JAMS', 'false').lower() == 'true',
                    'tracks': min(int(os.getenv('JAMS_TRACKS', '25')), 50),
                    'name': 'Weekly Jams',
                    'dir': self.music_dir / 'jams',
                    'schedule': os.getenv('JAMS_SCHEDULE', '0 4 * * 1'),
                    'playlist_type': 'weekly-jams'
                }
            }
        else:
            self.listenbrainz_playlists = {}
    
    def _make_request(self, endpoint: str, extra_params: Dict = None) -> Dict:
        """Make a request to the Subsonic API"""
        params = self.subsonic_params.copy()
        if extra_params:
            params.update(extra_params)
        
        url = f"{self.navidrome_url}/rest/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_playlist_config(self, playlist_type: str) -> Optional[Dict]:
        """Get configuration for any playlist type (LastFM or ListenBrainz)"""
        if playlist_type in self.playlists:
            return self.playlists[playlist_type]
        elif playlist_type in self.listenbrainz_playlists:
            return self.listenbrainz_playlists[playlist_type]
        return None
    
    def fetch_listenbrainz_playlist_id(self, playlist_type: str) -> Optional[str]:
        """Get the current week's ListenBrainz playlist ID"""
        try:
            if not self.listenbrainz_user:
                log("ListenBrainz username not configured")
                return None
            
            url = f"https://api.listenbrainz.org/1/user/{self.listenbrainz_user}/playlists/createdfor"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            playlists = data.get('playlists', [])
            if not playlists:
                log("No playlists found for user")
                return None
            
            now = datetime.now()
            
            if playlist_type == 'daily-jams':
                current_day = now.timetuple().tm_yday
            else:
                current_week = now.isocalendar()[1]
            
            for playlist_item in playlists:
                playlist = playlist_item.get('playlist', {})
                extension = playlist.get('extension', {}).get('https://musicbrainz.org/doc/jspf#playlist', {})
                algorithm_metadata = extension.get('additional_metadata', {}).get('algorithm_metadata', {})
                source_patch = algorithm_metadata.get('source_patch', '')
                
                if source_patch != playlist_type:
                    continue
                
                date_str = playlist.get('date')
                if date_str:
                    try:
                        playlist_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        
                        if playlist_type == 'daily-jams':
                            playlist_day = playlist_date.timetuple().tm_yday
                            time_match = current_day == playlist_day
                        else:
                            playlist_week = playlist_date.isocalendar()[1]
                            time_match = current_week == playlist_week
                        
                        if time_match:
                            identifier = playlist.get('identifier', '')
                            playlist_id = identifier.split('/')[-1]
                            log(f"Found {playlist_type} playlist: {playlist_id}")
                            return playlist_id
                    except Exception as e:
                        log(f"Error parsing date for playlist: {e}")
                        continue
            
            log(f"No current {playlist_type} playlist found")
            return None
            
        except Exception as e:
            log(f"Error fetching ListenBrainz playlists: {e}")
            return None

    def fetch_listenbrainz_tracks(self, playlist_id: str, num_tracks: int) -> List[Dict]:
        """Fetch tracks from a ListenBrainz playlist"""
        try:
            url = f"https://api.listenbrainz.org/1/playlist/{playlist_id}"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            playlist = data.get('playlist', {})
            tracks = playlist.get('track', [])
            
            if not tracks:
                log("No tracks found in playlist")
                return []
            
            converted_tracks = []
            for track in tracks:
                title = track.get('title', '')
                artist = track.get('creator', '')
                album = track.get('album', '')
                
                if not title or not artist:
                    continue
                
                extension = track.get('extension', {}).get('https://musicbrainz.org/doc/jspf#track', {})
                additional_metadata = extension.get('additional_metadata', {})
                artists_list = additional_metadata.get('artists', [])
                
                if len(artists_list) > 1:
                    artist_names = [a.get('artist_credit_name', '') for a in artists_list if a.get('artist_credit_name')]
                    if artist_names:
                        artist = ', '.join(artist_names)
                
                converted_tracks.append({
                    'name': title,
                    'artists': [{'name': artist}],
                    'album': album
                })
            return converted_tracks
            
        except Exception as e:
            log(f"Error fetching ListenBrainz playlist tracks: {e}")
            return []
        
    def fetch_lastfm_tracks(self, url: str, num_tracks: int) -> List[Dict]:
        """Fetch tracks from LastFM JSON endpoint with backup songs"""
        backup_multiplier = 3
        fetch_count = num_tracks * backup_multiplier
        
        log(f"Fetching {fetch_count} tracks from LastFM (need {num_tracks}, extras as backup)")
        
        all_tracks = []
        seen_ids = set()
        max_attempts = 20
        attempts = 0
        
        while len(all_tracks) < fetch_count and attempts < max_attempts:
            attempts += 1
            log(f"  Query {attempts}: Fetching more tracks...")
            
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                tracks = data.get('playlist', [])
                if not tracks:
                    log("  No more tracks available from API")
                    break
                
                new_tracks = 0
                for track in tracks:
                    track_name = track.get('name', '')
                    artists = track.get('artists', [])
                    artist_name = artists[0].get('name', '') if artists else ''
                    track_id = f"{artist_name}:{track_name}"
                    
                    if track_id not in seen_ids and track_name and artist_name:
                        seen_ids.add(track_id)
                        all_tracks.append(track)
                        new_tracks += 1
                        
                        if len(all_tracks) >= fetch_count:
                            break
                
                log(f"  Added {new_tracks} new tracks (total: {len(all_tracks)}/{fetch_count})")
                
                if new_tracks == 0:
                    log("  API is repeating tracks, stopping")
                    break
                
                if len(all_tracks) < fetch_count:
                    time.sleep(1)
                    
            except Exception as e:
                log(f"  Error fetching LastFM data: {e}")
                break
        
        log(f"Collected {len(all_tracks)} tracks ({num_tracks} + backups)")
        return all_tracks
    
    def fetch_tracks_for_playlist(self, playlist_type: str, config: Dict) -> List[Dict]:
        """Fetch tracks for any playlist type"""
        if playlist_type in self.playlists:
            return self.fetch_lastfm_tracks(config['url'], config['tracks'])
        elif playlist_type in self.listenbrainz_playlists:
            playlist_id = self.fetch_listenbrainz_playlist_id(config['playlist_type'])
            if not playlist_id:
                log("Could not find current week's playlist")
                return []
            return self.fetch_listenbrainz_tracks(playlist_id, config['tracks'])
        return []
    
    def normalize_for_matching(self, text: str) -> str:
        """Normalize text for comparison"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def search_ytmusic_track(self, artist: str, title: str) -> Optional[Dict]:
        """Search YouTube Music for a track with strict matching"""
        try:
            query = f"{artist} {title}"
            results = self.ytmusic.search(query, filter='songs', limit=10)
            
            if not results:
                return None
            
            norm_artist = self.normalize_for_matching(artist)
            norm_title = self.normalize_for_matching(title)
            
            best_match = None
            best_score = 0
            
            for result in results:
                result_artists = result.get('artists', [])
                if isinstance(result_artists, list):
                    result_artist = ', '.join([a.get('name', '') for a in result_artists if isinstance(a, dict)])
                else:
                    result_artist = str(result_artists) if result_artists else ''
                
                result_title = result.get('title', '')
                
                norm_result_artist = self.normalize_for_matching(result_artist)
                norm_result_title = self.normalize_for_matching(result_title)
                
                artist_match = norm_artist in norm_result_artist or norm_result_artist in norm_artist
                title_match = norm_title in norm_result_title or norm_result_title in norm_title
                
                if artist_match and title_match:
                    score = 0
                    if norm_artist == norm_result_artist:
                        score += 2
                    elif artist_match:
                        score += 1
                    
                    if norm_title == norm_result_title:
                        score += 2
                    elif title_match:
                        score += 1
                    
                    if score > best_score:
                        best_score = score
                        best_match = result
            
            if not best_match or best_score < 2:
                return None
            
            video_id = best_match.get('videoId')
            if not video_id:
                return None
            
            album_info = best_match.get('album')
            album_name = title
            album_id = None
            
            if isinstance(album_info, dict):
                album_name = album_info.get('name', album_name)
                album_id = album_info.get('id')
            
            year = ''
            track_number = 1
            
            if album_id:
                try:
                    album_details = self.ytmusic.get_album(album_id)
                    album_name = album_details.get('title', album_name)
                    
                    release_date = album_details.get('releaseDate')
                    if release_date and isinstance(release_date, dict):
                        year = str(release_date.get('year', ''))
                    elif album_details.get('year'):
                        year = str(album_details.get('year'))
                    
                    album_tracks = album_details.get('tracks', [])
                    norm_search_title = self.normalize_for_matching(title)
                    
                    for idx, track in enumerate(album_tracks, start=1):
                        track_video_id = track.get('videoId', '')
                        track_title = track.get('title', '')
                        norm_track_title = self.normalize_for_matching(track_title)
                        
                        if track_video_id == video_id:
                            track_number = idx
                            break
                        elif norm_track_title == norm_search_title:
                            track_number = idx
                            break
                    
                except Exception as e:
                    log(f"  Warning: Could not get album details: {e}")
            
            artists = best_match.get('artists', [])
            if isinstance(artists, list):
                artist_name = ', '.join([a.get('name', '') for a in artists if isinstance(a, dict)])
            else:
                artist_name = artist
            
            thumbnails = best_match.get('thumbnails', [])
            cover_url = None
            if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
                cover_url = thumbnails[-1].get('url', '')
                if cover_url and '=w' in cover_url:
                    cover_url = cover_url.split('=w')[0]
            
            return {
                'video_id': video_id,
                'title': best_match.get('title', title),
                'artist': artist_name or artist,
                'album': album_name,
                'year': year,
                'track_number': track_number,
                'cover_url': cover_url,
                'url': f"https://music.youtube.com/watch?v={video_id}"
            }
            
        except Exception as e:
            log(f"  YouTube Music search error: {e}")
            return None
    
    def download_track_ytmusic(self, video_id: str, output_dir: Path, metadata: Dict, is_first_track: bool = False) -> bool:
        """Download track from YouTube Music"""
        try:
            if is_first_track:
                time.sleep(2)
            
            artist = metadata.get('artist', 'Unknown')
            title = metadata.get('title', 'Unknown')
            safe_filename = self.sanitize_filename(f"{artist} - {title}")
            
            url = f"https://music.youtube.com/watch?v={video_id}"
            
            cmd = [
                'yt-dlp',
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--embed-thumbnail',
                '--no-embed-info-json',
                '--output', str(output_dir / f'{safe_filename}.%(ext)s'),
                '--format', 'bestaudio',
                '--extractor-args', 'youtube:player_client=default,mweb',
            ]
            
            if self.cookie_file.exists():
                cmd.extend(['--cookies', str(self.cookie_file)])
            else:
                log(f"  Warning: Cookie file not found at {self.cookie_file}")
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode == 0:
                audio_file = output_dir / f"{safe_filename}.mp3"
                if audio_file.exists():
                    self.set_metadata(audio_file, metadata)
                    os.chmod(audio_file, 0o666)
                return True
            else:
                error = result.stderr[:200] if result.stderr else 'Unknown error'
                log(f"  Download failed: {error}")
                return False
                
        except subprocess.TimeoutExpired:
            log(f"  Timeout")
            return False
        except Exception as e:
            log(f"  Error: {e}")
            return False

    def set_metadata(self, file_path: Path, metadata: Dict):
        """Set metadata and clean comments"""
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, TPE1, TIT2, TALB, TDRC, TRCK, APIC, COMM
            
            audio = MP3(file_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            
            audio.tags.delall('COMM')
            
            artist_value = metadata.get('artist', '')
            artist_value = artist_value.replace(', ', '; ').replace(' & ', '; ')
            
            audio.tags['TPE1'] = TPE1(encoding=3, text=artist_value)
            audio.tags['TIT2'] = TIT2(encoding=3, text=metadata.get('title', ''))
            audio.tags['TALB'] = TALB(encoding=3, text=metadata.get('album', ''))
            
            if metadata.get('year'):
                audio.tags['TDRC'] = TDRC(encoding=3, text=metadata['year'])
            
            if metadata.get('track_number'):
                audio.tags['TRCK'] = TRCK(encoding=3, text=str(metadata['track_number']))
            
            cover_url = metadata.get('cover_url')
            if cover_url:
                try:
                    response = requests.get(cover_url, timeout=10)
                    if response.status_code == 200:
                        audio.tags['APIC'] = APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=response.content
                        )
                except Exception as e:
                    log(f"  Warning: Could not embed cover art: {e}")
            
            audio.save()
            
            audio = MP3(file_path, ID3=ID3)
            if audio.tags and audio.tags.getall('COMM'):
                log(f"  Warning: Comments still present after deletion")
            
        except Exception as e:
            log(f"  Warning: Could not set metadata: {e}")

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        filename = ' '.join(filename.split())
        return filename.strip()
    
    def cleanup_missing_files(self):
        """Remove orphaned playlist entries after deleting files"""
        try:
            
            response = self._make_request('getPlaylists')
            playlists = response.get('subsonic-response', {}).get('playlists', {}).get('playlist', [])
            
            if isinstance(playlists, dict):
                playlists = [playlists]
            
            managed_names = [config['name'] for config in self.playlists.values()]
            if self.listenbrainz_playlists:
                managed_names.extend([config['name'] for config in self.listenbrainz_playlists.values()])
            
            for playlist in playlists:
                if playlist['name'] in managed_names:
                    playlist_id = playlist['id']
                    try:
                        self._make_request('createPlaylist', {
                            'playlistId': playlist_id
                        })
                    except Exception as e:
                        log(f"    Warning: Could not clear playlist: {e}")
            
        except Exception as e:
            log(f"Warning: Could not cleanup playlists: {e}")
    
    def get_navidrome_playlist_id(self, playlist_name: str) -> Optional[str]:
        """Get or create playlist"""
        try:
            log(f"Fetching playlists from Navidrome...")
            response = self._make_request('getPlaylists')
            
            playlists = response.get('subsonic-response', {}).get('playlists', {}).get('playlist', [])
            
            if isinstance(playlists, dict):
                playlists = [playlists]
            
            for pl in playlists:
                if pl['name'] == playlist_name:
                    log(f"Found existing playlist: {playlist_name} (ID: {pl['id']})")
                    return pl['id']
            
            log(f"Creating new playlist: {playlist_name}")
            response = self._make_request('createPlaylist', {'name': playlist_name})
            playlist = response.get('subsonic-response', {}).get('playlist', {})
            playlist_id = playlist.get('id')
            
            if playlist_id:
                log(f"Created playlist: {playlist_name} (ID: {playlist_id})")
            
            return playlist_id
        except Exception as e:
            import traceback
            log(f"Error managing playlist: {e}")
            traceback.print_exc()
            return None
    
    def search_navidrome_track(self, artist: str, title: str) -> Optional[str]:
        """Search for a track in Navidrome"""
        try:
            query = f"{artist} {title}"
            response = self._make_request('search3', {
                'query': query,
                'artistCount': 0,
                'albumCount': 0,
                'songCount': 5
            })
            
            songs = response.get('subsonic-response', {}).get('searchResult3', {}).get('song', [])
            if songs:
                if isinstance(songs, dict):
                    songs = [songs]
                return songs[0]['id']
            return None
        except Exception as e:
            log(f"Error searching for track: {e}")
            return None
    
    def get_songs_by_path_pattern(self, path_pattern: str) -> List[str]:
        """Get all song IDs matching a path pattern"""
        try:
            response = self._make_request('search3', {
                'query': path_pattern,
                'artistCount': 0,
                'albumCount': 0,
                'songCount': 500
            })
            
            songs = response.get('subsonic-response', {}).get('searchResult3', {}).get('song', [])
            
            if isinstance(songs, dict):
                songs = [songs]
            
            song_ids = []
            for song in songs:
                song_path = song.get('path', '')
                if path_pattern in song_path:
                    song_ids.append(song.get('id'))
            
            return song_ids
        except Exception as e:
            log(f"Error getting songs by path: {e}")
            return []
    
    def scan_and_get_songs_from_directory(self, directory: Path, downloaded_tracks: List[Dict]) -> List[str]:
        """Scan library and find songs by searching for each downloaded track"""
        song_ids = []
        
        try:
            if not downloaded_tracks:
                log("No new tracks downloaded, skipping scan")
                return song_ids
            
            try:
                relative_path = directory.relative_to('/music')
                library_id = os.getenv('NAVIDROME_LIBRARY_ID', '1')
                target_path = f"{library_id}:{relative_path}"
                
                log(f"Triggering selective Navidrome scan for {len(downloaded_tracks)} new tracks...")
                
                self._make_request('startScan', {
                    'fullScan': 'false',
                    'target': target_path
                })
            except ValueError:
                log(f"Warning: Could not determine relative path for {directory}, falling back to full scan")
                log(f"Triggering Navidrome library scan for {len(downloaded_tracks)} new tracks...")
                self._make_request('startScan', {'fullScan': 'false'})
            
            log("Waiting for scan to complete...")
            scan_time = 0
            
            while True:
                time.sleep(2)
                scan_time += 2
                
                try:
                    status = self._make_request('getScanStatus')
                    scan_status = status.get('subsonic-response', {}).get('scanStatus', {})
                    scanning = scan_status.get('scanning', False)
                    count = scan_status.get('count', 0)
                    
                    if not scanning:
                        log(f"Scan completed after {scan_time}s ({count} items processed)")
                        break
                        
                    if scan_time % 20 == 0:
                        log(f"  Still scanning... ({scan_time}s, {count} items so far)")
                        
                except Exception as e:
                    if scan_time % 30 == 0:
                        log(f"  Warning: Could not check scan status: {e}")
                    pass
            
            wait_time = min(max(len(downloaded_tracks), 5), 30)
            log(f"Waiting {wait_time}s for indexing to complete...")
            time.sleep(wait_time)
            
            log(f"\nSearching for {len(downloaded_tracks)} downloaded tracks in Navidrome...")
            
            not_found_tracks = []
            
            for i, track_info in enumerate(downloaded_tracks, 1):
                artist = track_info.get('artist', '')
                title = track_info.get('title', '')
                
                if not artist or not title:
                    continue
                
                try:
                    query = f"{artist} {title}"
                    response = self._make_request('search3', {
                        'query': query,
                        'artistCount': 0,
                        'albumCount': 0,
                        'songCount': 10
                    })
                    
                    songs = response.get('subsonic-response', {}).get('searchResult3', {}).get('song', [])
                    if isinstance(songs, dict):
                        songs = [songs]
                    
                    if songs:
                        song_id = songs[0].get('id')
                        if song_id:
                            song_ids.append(song_id)
                        else:
                            log(f"  [{i}/{len(downloaded_tracks)}] No valid song ID for: {artist} - {title}")
                            not_found_tracks.append(track_info)
                    else:
                        log(f"  [{i}/{len(downloaded_tracks)}] Not found: {artist} - {title}")
                        not_found_tracks.append(track_info)
                        
                except Exception as e:
                    log(f"  [{i}/{len(downloaded_tracks)}] Search error for {artist} - {title}: {e}")
                    not_found_tracks.append(track_info)
            
            if not_found_tracks:
                retry_wait = min(len(not_found_tracks) * 2, 30)
                log(f"\n{len(not_found_tracks)} tracks not found, waiting {retry_wait}s and retrying...")
                time.sleep(retry_wait)
                
                for track_info in not_found_tracks:
                    artist = track_info.get('artist', '')
                    title = track_info.get('title', '')
                    
                    if not artist or not title:
                        continue
                    
                    try:
                        query = f"{artist} {title}"
                        response = self._make_request('search3', {
                            'query': query,
                            'artistCount': 0,
                            'albumCount': 0,
                            'songCount': 10
                        })
                        
                        songs = response.get('subsonic-response', {}).get('searchResult3', {}).get('song', [])
                        if isinstance(songs, dict):
                            songs = [songs]
                        
                        if songs:
                            song_id = songs[0].get('id')
                            if song_id:
                                song_ids.append(song_id)
                                log(f"  Found on retry: {artist} - {title}")
                            
                    except Exception as e:
                        log(f"  Retry search error for {artist} - {title}: {e}")
            
            log(f"\nFound {len(song_ids)}/{len(downloaded_tracks)} tracks in Navidrome")
            return song_ids
            
        except Exception as e:
            import traceback
            log(f"Error scanning and searching tracks: {e}")
            traceback.print_exc()
            return []
    
    def update_playlist(self, playlist_id: str, song_ids: List[str]):
        """Update playlist with songs"""
        try:
            log(f"Updating playlist with {len(song_ids)} tracks...")
            
            if song_ids:
                self._make_request('createPlaylist', {
                    'playlistId': playlist_id,
                    'songId': song_ids
                })
                log(f"Updated playlist with {len(song_ids)} tracks")
            else:
                self._make_request('createPlaylist', {
                    'playlistId': playlist_id
                })
                log("Cleared playlist (no songs to add)")
        except Exception as e:
            import traceback
            log(f"Error updating playlist: {e}")
            traceback.print_exc()
    
    def sync_playlist(self, playlist_type: str):
        """Unified sync function for both LastFM and ListenBrainz playlists"""
        config = self.get_playlist_config(playlist_type)
        
        if not config:
            log(f"Unknown playlist type: {playlist_type}")
            return
            
        if not config['enabled']:
            log(f"Playlist {playlist_type} is disabled, skipping")
            return

        log(f"\n{'='*60}")
        log(f"Syncing {config['name']}")
        log(f"{'='*60}")
        
        tracks = self.fetch_tracks_for_playlist(playlist_type, config)
        
        if not tracks:
            log("No tracks found, aborting")
            return
        
        playlist_id = self.get_navidrome_playlist_id(config['name'])
        if not playlist_id:
            log("Failed to get/create playlist")
            return
        
        song_ids = []
        
        if playlist_type == 'library':
            log("\nBuilding library playlist from existing songs...")
            success_count = 0
            target_count = config['tracks']
            track_index = 0

            while success_count < target_count and track_index < len(tracks):
                track = tracks[track_index]
                track_index += 1
                
                artists = track.get('artists', [])
                artist = artists[0].get('name', '') if artists else ''
                title = track.get('name', '')
                
                if not artist or not title:
                    continue
                
                log(f"[{success_count+1}/{target_count}] Searching: {artist} - {title}")
                song_id = self.search_navidrome_track(artist, title)
                if song_id:
                    song_ids.append(song_id)
                    success_count += 1
                    log(f"  Found in library")
                else:
                    log(f"  Not found in library, trying next backup track")
        
        else:
            playlist_dir = config['dir']
            
            if playlist_dir.exists():
                log(f"\nClearing old songs in {playlist_dir}")
                file_count = 0
                for file in playlist_dir.glob('*'):
                    if file.is_file():
                        try:
                            file.unlink()
                            file_count += 1
                        except Exception as e:
                            log(f"  Warning: Could not delete {file}: {e}")
                log(f"Removed {file_count} old songs")
                
                if file_count > 0:
                    self.cleanup_missing_files()
                    
                    wait_time = min(max(file_count // 2, 5), 20)
                    time.sleep(wait_time)
            else:
                playlist_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(playlist_dir, 0o777)
                log(f"Created directory: {playlist_dir}")
            
            log(f"\nProcessing {config['tracks']} tracks (total available with backups: {len(tracks)})")
            success_count = 0
            target_count = config['tracks']
            track_index = 0
            downloaded_tracks = []
            skipped_count = 0
            time.sleep(2)

            while success_count < target_count and track_index < len(tracks):
                track = tracks[track_index]
                track_index += 1
                
                artists = track.get('artists', [])
                artist = artists[0].get('name', 'Unknown') if artists else 'Unknown'
                title = track.get('name', 'Unknown')
                
                log(f"\n[{success_count+1}/{target_count}] Attempting: {artist} - {title}")
                
                existing_song_id = self.search_navidrome_track(artist, title)
                
                if existing_song_id:
                    log(f"  Already in Navidrome library, skipping download")
                    song_ids.append(existing_song_id)
                    success_count += 1
                    skipped_count += 1
                    continue
                
                ytmusic_info = self.search_ytmusic_track(artist, title)
                
                if ytmusic_info:                 
                    downloaded = self.download_track_ytmusic(
                        ytmusic_info['video_id'],
                        playlist_dir,
                        ytmusic_info
                    )
                    
                    if downloaded:
                        log(f"  Downloaded successfully")
                        success_count += 1
                        downloaded_tracks.append(ytmusic_info)
                    else:
                        log(f"  Download failed, trying next backup track")
                else:
                    log(f"  Not found on YouTube Music, trying next backup track")
                
                time.sleep(1)
            
            log(f"\nSuccessfully added {success_count}/{target_count} tracks")
            log(f"  Downloaded: {len(downloaded_tracks)}")
            
            if downloaded_tracks:
                new_song_ids = self.scan_and_get_songs_from_directory(playlist_dir, downloaded_tracks)
                song_ids.extend(new_song_ids)
        
        log("")
        self.update_playlist(playlist_id, song_ids)
        log(f"\n{'='*60}")
        log(f"Completed syncing {config['name']}")
        if playlist_type != 'library':
            log(f"  Downloaded: {len(downloaded_tracks) if 'downloaded_tracks' in locals() else 'N/A'}")
        log(f"  In Navidrome: {len(song_ids)}")
        log(f"{'='*60}\n")

    def get_next_cron_schedule(self) -> Optional[str]:
        """Get the schedule for the next enabled playlist"""

        sync_schedule = os.getenv('SYNC_SCHEDULE')
        if sync_schedule:
            return sync_schedule
        
        # Fallback in case of weird failure
        for playlist_type in ['recommended', 'mix', 'library']:
            config = self.playlists[playlist_type]
            if config['enabled']:
                return config['schedule']
        return None
    
    def get_current_time(self) -> str:
        """Get current time in the configured timezone"""
        return datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

def main():
    if len(sys.argv) < 2:
        log("Usage: app.py <recommended|mix|library|exploration|jams|all>")
        sys.exit(1)
    
    playlist_type = sys.argv[1]
    
    lock_fd = acquire_lock()
    if not lock_fd:
        sys.exit(0)
    
    try:
        syncer = NavidroFM()
        
        if playlist_type == 'all':
            for ptype in ['recommended', 'mix', 'library']:
                syncer.sync_playlist(ptype)
            for ptype in ['exploration', 'jams']:
                syncer.sync_playlist(ptype)
        else:
            syncer.sync_playlist(playlist_type)
        
        schedule = syncer.get_next_cron_schedule()
        if schedule:
            log(f"\n{'='*60}")
            log(f"Sync completed at {syncer.get_current_time()}")
            log(f"Next sync scheduled: {schedule}")
            log(f"{'='*60}\n")
            
    except Exception as e:
        import traceback
        log(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        release_lock(lock_fd)

if __name__ == '__main__':
    main()