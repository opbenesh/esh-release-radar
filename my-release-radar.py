import spotipy
import datetime
import threading
import logging
import time
import itertools
from spotipy.oauth2 import SpotifyOAuth
import smtplib
from email.mime.text import MIMEText
from collections import Counter

client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
redirect_uri = "http://localhost:9999/callback"

max_items_per_album = 5

automated_playlists = [
    "74glIVP7azlpKA77RCgyDL", # Best New Songs Right Now
    "7s2xt5dCX0e5S4Om9vyHKg", # To The Teeth | New Metal
    "56jVMfxcgimVpN0MUSpBhp", # Roadburn: Essential Sounds
    "4VDQ0PYPbuFqjA84cTlSMI", # Roadburn Festival 2023
    "37i9dQZEVXbg6Lzzwd9r3r", # Release Radar
    "37i9dQZF1DX5J7FIl4q56G", # All New Metal
    "1gD2CRBznaV63HIkGQiQM0", # Deathwish Staff Picks
    "0ZQcCFqc1ziBiC1fvrrbsT", # BrooklynVegan Weekly Playlist
    "37i9dQZF1DX3YlUroplxjF", # Crash Course
    "7i3ybB0XlLwlFysT4uULLi", # Season of Mist New Tracks 2022
    "5Z9ssgGRlBWvT31GOLgi9R", # New Metal Songs 2022
    "1eNv0cYgq8XMwnaVqvRTHR", # Noisepicker Weekly
    "37i9dQZF1DXdiUbJTV2anj", # New Blood
    "4uObaSNdGaPWsS7fefPYrj", # Machine Music - Winter 2022-23
    "53x58hBq1M9qCzZxyRUmp4", # Weekly Wire
    "0imR1QYwwV13XTldnuHTOD"  # New Metal Friday
    ]

seen_tracks_playlist_id = "5al4jEBoq01LPmFDuGDnq4"          # Automated: Reviewed Items
seen_tracks_backup_playlist_id = "6LszTDYqWtsxBj8iDTA5Ou"   # Automated: Reviewed Backup
temp_review_clone_id = "5PGCp1CjpaV5DmqdyjSnTt"             # Automated: Temp Review Clone
inbox_playlist_id = "1xsuqA0HU4bSosdaPyVlWG"                # 1 Esh Review
shortlist_playlist_id = "3qYnDeorQj7TPRlmqM8S5c"            # 2 Esh Shortlist
approved_playlist_id = "7pBxidVP9h7ufxsFBMwOQq"             # 3 Esh Approved
previously_played_playlist_id = "7EHT9D4ygqDlyGfqcFvkUv"    # 5 Esh Played
tracked_playlist_id = "5PR4b0qnkhfCUdt4oLbn3o"              # X Esh Tracked

def get_all_playlist_tracks(sp,playlist_id):
    results = sp.playlist_tracks(playlist_id)
    playlist_tracks = results['items']
    while results['next']:
        results = sp.next(results)
        playlist_tracks.extend(results['items'])
    return [playlist_track['track'] for playlist_track in playlist_tracks if playlist_track['track']]

def add_all_playlist_tracks(sp,playlist_id,tracks):
    while True:
        if not tracks:
            return
        current_batch = tracks[:100]
        tracks = tracks[100:]
        sp.playlist_add_items(playlist_id,current_batch)
        
def remove_all_track_ids_from_playlist(sp,playlist_id,track_ids):
    while True:
        if not track_ids:
            return
        current_batch = track_ids[:100]
        track_ids = track_ids[100:]
        sp.playlist_remove_all_occurrences_of_items(playlist_id,current_batch)

def truncate_playlist(sp,playlist_id):
    current_tracks = get_all_playlist_tracks(sp,playlist_id)
    remove_all_track_ids_from_playlist(sp,playlist_id,[track["id"] for track in current_tracks])
    
def parse_date(date_string):
    for fmt in ("%Y-%m-%d","%Y","%Y-%m"):
        try:
            return datetime.datetime.strptime(date_string, fmt)
        except:
            pass
    print("Skipping a weird date: " + date_string)
    return None

def is_new_track(track):
    release_date = parse_date(track["album"]["release_date"])
    return release_date is not None and (datetime.datetime.today() - release_date).days <= 60

def strip_casefold_compare(s1,s2):
    return s1.casefold().strip() == s2.casefold().strip()

def extract_and_normalize_names(track):
    track_name = track["name"].strip().casefold()
    track_artist_ids_flat = ','.join([artist.get("id","") for artist in track["artists"]])
    return (track_name,track_artist_ids_flat)

def filter_tracks(tracks,seen_tracks,albums_counter=dict()):
    new_tracks = []
    seen_tracks_set = set([track["id"] for track in seen_tracks])
    seen_tracks_set_name_artist = set(map(extract_and_normalize_names,seen_tracks))
    for track in tracks:
        if not track or not is_new_track(track):
            continue
        if track["id"] in seen_tracks:
            continue
        if extract_and_normalize_names(track) in seen_tracks_set_name_artist:
            continue
        album_id = track["album"]["id"]
        if album_id not in albums_counter:
            albums_counter[album_id] = 0
        albums_counter[track["album"]["id"]]+=1
        if albums_counter[track["album"]["id"]]>max_items_per_album:
            continue
        new_tracks.append(track)
    return new_tracks
    
def extract_ids(items):
    return [item["id"] for item in items]

def add_new_review_tracks():
    print("Starting!")
    scope = "playlist-modify-private"

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri))
    user = sp.current_user()
    print("Connected!")
    
    print("Retrieving previously seen tracks...")
    seen_tracks = []
    seen_old_track_ids = []
    seen_tracks = get_all_playlist_tracks(sp,seen_tracks_playlist_id)
    seen_tracks += get_all_playlist_tracks(sp,previously_played_playlist_id)
    shortlisted_tracks = get_all_playlist_tracks(sp,shortlist_playlist_id)
    seen_tracks += shortlisted_tracks
    seen_tracks += get_all_playlist_tracks(sp,approved_playlist_id)
    seen_albums_counter = Counter([track["album"]["id"] for track in seen_tracks if track and track["album"]])

    print("Reviewing playlists...")
    collected_tracks = []
    for playlist_id in automated_playlists:
        playlist_name=sp.playlist(playlist_id)["name"]
        print("Fetching tracks from " + playlist_name + ": ",end='')
        new_tracks = extract_ids(filter_tracks(get_all_playlist_tracks(sp,playlist_id),seen_tracks,seen_albums_counter))
        collected_tracks += new_tracks
        print(f"({len(new_tracks)})")

    print("Retrieving previously played artists...")
    previously_played_tracks = get_all_playlist_tracks(sp,previously_played_playlist_id)
    previously_played_tracks += get_all_playlist_tracks(sp,approved_playlist_id)
    tracked_artists_sample_tracks = get_all_playlist_tracks(sp,tracked_playlist_id)
    previously_played_artists_raw = list(itertools.chain.from_iterable([track["artists"] for track in previously_played_tracks + tracked_artists_sample_tracks]))
    previously_played_artist_ids = list(set([artist["id"] for artist in previously_played_artists_raw]))
    
    print("Fetching top tracks for previously played artists: ",end='')
    previously_played_new_tracks = []
    for artist_id in previously_played_artist_ids:
          top_tracks = sp.artist_top_tracks(artist_id)["tracks"]
          previously_played_new_tracks += extract_ids(filter_tracks(top_tracks,seen_tracks,seen_albums_counter))
    collected_tracks += previously_played_new_tracks
    print(f"({len(previously_played_new_tracks)})")
          
    print("Removing duplicates...")
    collected_tracks = list(set(collected_tracks))
    
    print("Saving " + str(len(collected_tracks)) + " new items...")
    add_all_playlist_tracks(sp,seen_tracks_playlist_id,collected_tracks)
    add_all_playlist_tracks(sp,seen_tracks_backup_playlist_id,collected_tracks)
    add_all_playlist_tracks(sp,inbox_playlist_id,collected_tracks)
    if len(collected_tracks)==0:
        print("No new tracks were found.")
        return

    artist_score = dict()
    for track in previously_played_tracks:
        for artist in track["artists"]:
            if artist["id"] not in artist_score:
                artist_score[artist["id"]] = 0
            artist_score[artist["id"]]+=1

    # get current review tracks (and filter irrelevant ones along the way)        
    old_review_queue = get_all_playlist_tracks(sp,inbox_playlist_id)
    print(f"Starting review count: {len(old_review_queue)}")
    current_review_tracks = filter_tracks(old_review_queue,previously_played_tracks)
    print(f"New review count: {len(current_review_tracks)}")
    
    print("Calculating skipped artists...")
    skipped_artists = dict()
    for track in seen_tracks:
        if track in current_review_tracks:
            continue
        if track in shortlisted_tracks:
            continue
        for artist in track["artists"]:
            artist_id = artist["id"]
            if artist_id not in artist_score:
                artist_score[artist_id] = 0
            if artist_score[artist_id] > 0:
                continue
            artist_score[artist_id]-=1

    print("Ranking review tracks...")
    scored_review_tracks = dict()
    for track in current_review_tracks:
        if track["id"] in scored_review_tracks:
            continue
        track_score = max([artist_score[artist["id"]] for artist in track["artists"] if artist["id"] in artist_score]
                          ,default=0)
        first_artist_name = track["artists"][0]["name"]
        scored_review_tracks[(track["id"],first_artist_name)] = track_score
    sort_function = lambda i: (-1*i[1],i[0][1])
    ordered_review_tracks = [track_id for ((track_id,artist_name),score) in sorted(scored_review_tracks.items(), key=sort_function) if score >= -1]

    print("Re-creating review queue...")
    truncate_playlist(sp,temp_review_clone_id)
    add_all_playlist_tracks(sp,temp_review_clone_id,[track["id"] for track in current_review_tracks])
    truncate_playlist(sp,inbox_playlist_id)
    add_all_playlist_tracks(sp,inbox_playlist_id,ordered_review_tracks)

def execute():
    while True:
        print("Starting...")
        try:
            add_new_review_tracks()
        except ConnectionError:
            print("Connection error!")
        print("Sleeping for an hour...")
        time.sleep(1*60*60)

if __name__ == '__main__':
    execute()
