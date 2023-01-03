import spotipy
import datetime
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np

client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
redirect_uri = "http://localhost:9999/callback"
scope = "playlist-modify-private"

def spotify_connect():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri))

def flatten_spotify_iterator(sp,iter):
    results = iter['items']
    while iter['next']:
        iter = sp.next(iter)
        results.extend(iter['items'])
    return results

def get_playlist_tracks(sp,playlist_id):
    playlist_tracks = flatten_spotify_iterator(sp,sp.playlist_tracks(playlist_id))
    tracks = [playlist_track['track'] for playlist_track in playlist_tracks] 
    columns = tracks[0].keys() if tracks else []
    return pd.DataFrame(tracks,columns=columns)

def add_features_to_tracks(sp,tracks):
    if tracks.count == 0:
        raise Exception("Cannot add features to an empty tracks dataframe")
    track_ids = tracks["id"]
    print(f"tracks len:{len(tracks)}")
    track_features = []
    for track_id_subset in np.array_split(track_ids,100):
        track_features.extend(sp.audio_features(track_id_subset))
    print(f"track_features len:{len(track_features)}")
    track_features_df = pd.DataFrame(track_features,columns=track_features[0].keys())
    return pd.merge(tracks,track_features_df,on=["id"],how="left")