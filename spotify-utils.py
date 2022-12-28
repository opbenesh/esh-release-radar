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
import csv

client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
redirect_uri = "http://localhost:9999/callback"

def get_all_playlist_tracks(sp,playlist_id):
    results = sp.playlist_tracks(playlist_id)
    playlist_tracks = results['items']
    while results['next']:
        results = sp.next(results)
        playlist_tracks.extend(results['items'])
    return [playlist_track['track'] for playlist_track in playlist_tracks]

def get_all_playlist_tracks_extended(sp,playlist_id):
    def add_features(playlist_tracks):
        tracks = [pt['track'] for pt in playlist_tracks]
        track_features = sp.audio_features([t["id"] for t in tracks])
        return list(zip(tracks,track_features))
    results = sp.playlist_tracks(playlist_id)
    collected_tracks = add_features(results['items'])
    while results['next']:
        results = sp.next(results)
        collected_tracks.extend(add_features(results['items']))
    return collected_tracks

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

def is_seen_track(track,seen_tracks):
    for seen_track in seen_tracks:
        if seen_track["id"] == track["id"]:
            return True       
        if strip_casefold_compare(track["name"],seen_track["name"]) and track["artists"]==seen_track["artists"]:
            return True
    return False

def filter_tracks(tracks,seen_tracks,albums_counter=dict()):
    new_tracks = []
    for track in tracks:
        if not track or is_seen_track(track,seen_tracks) or not is_new_track(track):
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

def get_track_details(track,features):
    details = dict()
    details["id"]=track["id"]
    details["name"]=track["name"]
    details["album_id"]=track["album"]["id"]
    details["album_name"]=track["album"]["name"]
    details["artist_id"]=track["artists"][0]["id"]
    details["artist_name"]=track["artists"][0]["name"]
    details["duration"]=track["duration_ms"]
    details["popularity"]=track["popularity"]
    if not features:
        return None
    for f in ["acousticness","danceability","energy","instrumentalness","liveness","loudness","speechiness","tempo","valence"]:
        details[f] = features[f]
    return details