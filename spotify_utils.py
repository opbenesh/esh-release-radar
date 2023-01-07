import spotipy
import datetime
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np
from operator import itemgetter
import math

client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
redirect_uri = "http://localhost:9999/callback"
scope = "playlist-modify-private"
audio_features_to_use = ["acousticness","danceability","energy","instrumentalness","liveness","loudness","speechiness","tempo","valence"]


def spotify_connect():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri))

def flatten_spotify_iterator(sp,iter):
    results = iter['items']
    while iter['next']:
        iter = sp.next(iter)
        results.extend(iter['items'])
    return results

def rebuild_track_dict(track):
    return {
        "id": track["id"],
        "artist_ids": ','.join(map(itemgetter("id"),track["artists"])),
        "artist_names": ','.join(map(itemgetter("name"),track["artists"])),
        "album_id": track["album"].get("id"),
        "album_name": track["album"].get("name"),
        "release_date": track["album"].get("release_date"),
        "duration": track["duration_ms"] / 1000
    }

def get_playlist_tracks(sp,playlist_id,audio_features=False):
    playlist_tracks = flatten_spotify_iterator(sp,sp.playlist_tracks(playlist_id))
    tracks = [rebuild_track_dict(playlist_track["track"]) for playlist_track in playlist_tracks]
    columns = tracks[0].keys()
    tracks_df = pd.DataFrame(tracks,columns=columns)
    tracks_df["playlist_offset"]=tracks_df.index
    if audio_features:
        track_ids = tracks_df["id"]
        track_features = []
        for track_id_subset in np.array_split(track_ids,100):
            track_features.extend(filter(None,sp.audio_features(track_id_subset)))
        track_features_df = pd.DataFrame(track_features,columns=track_features[0].keys())
        track_features_df = track_features_df[["id"] + audio_features_to_use]        
        tracks_df = pd.merge(tracks_df,track_features_df,on=["id"],how="left")
    return tracks_df