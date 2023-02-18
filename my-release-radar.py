import glob
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
import pandas as pd
import spotify_utils

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

seen_tracks_playlist_id = "6G1K7HGkhBuhkllH8DNXKK"          # Automated: Reviewed Items
seen_tracks_backup_playlist_id = "1Qd9qOo15OMYiXSzypBZX0"   # Automated: Reviewed Backup
temp_review_clone_id = "5PGCp1CjpaV5DmqdyjSnTt"             # Automated: Temp Review Clone
inbox_playlist_id = "1xsuqA0HU4bSosdaPyVlWG"                # 1 Esh Review
shortlist_playlist_id = "3qYnDeorQj7TPRlmqM8S5c"            # 2 Esh Shortlist
approved_playlist_id = "7pBxidVP9h7ufxsFBMwOQq"             # 3 Esh Approved
previously_played_playlist_id = "7EHT9D4ygqDlyGfqcFvkUv"    # 5 Esh Played
tracked_playlist_id = "5PR4b0qnkhfCUdt4oLbn3o"              # X Esh Tracked
    
def parse_date(date_string):
    for fmt in ("%Y-%m-%d","%Y","%Y-%m"):
        try:
            return datetime.datetime.strptime(date_string, fmt)
        except:
            pass
    print("Skipping a weird date: " + date_string)
    return None

def is_new_track(track):
    release_date = parse_date(track["release_date"])
    return release_date is not None and (datetime.datetime.today() - release_date).days <= 60

def strip_casefold_compare(s1,s2):
    return s1.casefold().strip() == s2.casefold().strip()

def extract_and_normalize_names(track):
    def normalize(s):
        return s.strip().casefold()
    return (normalize(track["track_name"]),normalize(track["artist_name"]))

def filter_tracks(tracks,seen_track_ids,seen_tracks_set_name_artist,albums_counter=dict()):
    def filter_track(track):
        if not is_new_track(track):
            return False
        if track["id"] in seen_track_ids:
            return False
        if extract_and_normalize_names(track) in seen_tracks_set_name_artist:
            return False
        album_id = track["album_id"]
        if album_id not in albums_counter:
            albums_counter[album_id] = 0
        albums_counter[album_id]+=1
        if albums_counter[album_id]>max_items_per_album:
            return False
        return True
    return tracks[tracks.apply(filter_track,axis=1)]
    
def extract_ids(items):
    return [item["id"] for item in items]

def add_new_review_tracks():
    print("Starting!")
    sp = spotify_utils.spotify_connect()
    user = sp.current_user()
    print("Connected!")
    
    print("Retrieving previously seen tracks...")
    seen_tracks = []
    seen_old_track_ids = []
    
    reviewed_tracks_archive = pd.concat(map(pd.read_csv, glob.glob("data/reviewed_tracks_archive_*.csv")))
    reviewed_tracks_spotify = spotify_utils.get_playlist_tracks(sp,seen_tracks_playlist_id)
    previously_played_tracks = spotify_utils.get_playlist_tracks(sp,previously_played_playlist_id)
    shortlisted_tracks = spotify_utils.get_playlist_tracks(sp,shortlist_playlist_id)
    approved_tracks = spotify_utils.get_playlist_tracks(sp,approved_playlist_id)
    seen_tracks = pd.concat([reviewed_tracks_archive,reviewed_tracks_spotify,previously_played_tracks,shortlisted_tracks,approved_tracks])
    seen_albums_counter = Counter(seen_tracks.groupby(['album_id']).count())
    seen_tracks_ids_set = set(seen_tracks["id"].unique())
    seen_tracks_name_artist_set = set(seen_tracks.apply(extract_and_normalize_names,axis=1).unique())
    tracked_artists_sample_tracks = spotify_utils.get_playlist_tracks(sp,tracked_playlist_id)

    print("Reviewing playlists...")
    collected_track_dfs = []
    for playlist_id in automated_playlists:
        playlist_name=sp.playlist(playlist_id)["name"]
        print("Fetching tracks from " + playlist_name + ": ",end='')
        playlist_tracks = spotify_utils.get_playlist_tracks(sp,playlist_id)
        new_tracks = filter_tracks(playlist_tracks,seen_tracks_ids_set,seen_albums_counter)
        collected_track_dfs.append(new_tracks)
        print(f"({len(new_tracks)})")
    collected_tracks = pd.concat(collected_track_dfs)

    print("Retrieving previously played artists...")
    tracked_artist_ids = pd.concat([previously_played_tracks,approved_tracks,tracked_artists_sample_tracks])["artist_id"].unique()
    
    print("Fetching top tracks for previously played artists: ",end='')
    tracked_artists_top_tracks = spotify_utils.get_artists_top_tracks(sp,tracked_artist_ids) 
    tracked_artists_top_tracks = filter_tracks(tracked_artists_top_tracks,seen_tracks_ids_set,seen_albums_counter)
    print(f"({len(tracked_artists_top_tracks)})")
    collected_tracks = pd.concat([collected_tracks,tracked_artists_top_tracks])
          
    print("Removing duplicates...")
    collected_tracks.drop_duplicates(subset=["id"],inplace=True)
    
    print("Saving " + str(len(collected_tracks)) + " new items...")
    spotify_utils.add_tracks_to_playlist(sp,seen_tracks_playlist_id,collected_tracks)
    spotify_utils.add_tracks_to_playlist(sp,seen_tracks_backup_playlist_id,collected_tracks)
    spotify_utils.add_tracks_to_playlist(sp,inbox_playlist_id,collected_tracks)
    if len(collected_tracks)==0:
        print("No new tracks were found.")
        #return


    # get current review tracks (and filter irrelevant ones along the way)        
    old_review_queue = spotify_utils.get_playlist_tracks(sp,inbox_playlist_id)
    print(f"Starting review count: {len(old_review_queue)}")
    previously_played_tracks_ids_set = set(previously_played_tracks["id"].unique())
    previously_played_tracks_name_artist_set = set(previously_played_tracks.apply(extract_and_normalize_names,axis=1).unique())
    current_review_tracks = filter_tracks(old_review_queue,previously_played_tracks_ids_set,previously_played_tracks_name_artist_set)
    print(f"New review count: {len(current_review_tracks)}")
    
    print("Ranking review tracks...")
    played_artist_score = previously_played_tracks["artist_id"].value_counts().to_dict()
    ignored_track_ids_for_scoring = set(shortlisted_tracks["id"].to_list() + current_review_tracks["id"].to_list())
    seen_artist_score = seen_tracks[~seen_tracks["id"].isin(ignored_track_ids_for_scoring)]["artist_id"].value_counts().multiply(-1).add(1).to_dict()
    artist_score = seen_artist_score | played_artist_score
    current_review_tracks["score"] = current_review_tracks.apply(lambda track: artist_score.get(track["artist_id"],0),axis=1)
    ordered_review_tracks = current_review_tracks.sort_values(["score","artist_name"],ascending=[False,True])

    print("Re-creating review queue...")
    spotify_utils.overwrite_playlist(sp,temp_review_clone_id,current_review_tracks)
    spotify_utils.overwrite_playlist(sp,inbox_playlist_id,ordered_review_tracks)

def execute():
    while True:
        print("Starting...")
        try:
            add_new_review_tracks()
        except ConnectionError:
            print("Connection error!")
        return
        print("Sleeping for an hour...")
        time.sleep(1*60*60)

if __name__ == '__main__':
    execute()
