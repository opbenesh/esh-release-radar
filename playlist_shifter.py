import datetime
from collections import Counter
import pandas as pd
import spotipy_pandas
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os


playlists_to_shift = [
    # ("Esh Review", "1xsuqA0HU4bSosdaPyVlWG", True),
    # ("Esh Shortlist", "3qYnDeorQj7TPRlmqM8S5c", True),
    ("Esh Approved", "7pBxidVP9h7ufxsFBMwOQq", False),
    ("Esh Played", "7EHT9D4ygqDlyGfqcFvkUv", False),
]

shifter_backup_playlist = "3Egt20VFz2t7hfnVWZwFqu"

client_secret = os.environ["RELEASE_RADAR_SPOTIFY_APP_SECRET"]
client_id = os.environ["RELEASE_RADAR_SPOTIFY_APP_ID"]
redirect_uri = "http://localhost:9999/callback"
scope = "playlist-modify-private user-library-modify user-library-read"


def shift_playlists():
    print("Starting!")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    )
    print("Connected!")

    playlist_pairs = zip(playlists_to_shift[:-1], playlists_to_shift[1:])
    for i, (source, target) in enumerate(playlist_pairs, start=1):
        source_name, source_id, offset_based_cleanup = source
        target_name, target_id, _ = target
        print(f"Iteration {i}: shifting from {source_name} to {target_name}...")
        saved_tracks = spotipy_pandas.get_saved_tracks(sp)
        if saved_tracks is None:
            print("The saved items list is empty. Exiting.")
            return
        source_tracks = spotipy_pandas.get_playlist_tracks(sp, source_id)
        if source_tracks is None:
            print("The source playlist is empty. Skipping.")
            continue
        saved_source_tracks = source_tracks[
            source_tracks["id"].isin(saved_tracks["id"])
        ]
        if saved_source_tracks.empty:
            print("No saved tracks in this playlist. Skipping.")
            continue
        print(
            f"Found {len(saved_source_tracks)} saved tracks in this playlist. Shifting..."
        )
        spotipy_pandas.add_tracks_to_playlist(sp, target_id, saved_source_tracks)
        if offset_based_cleanup:
            playlist_from_max_saved_offset = saved_source_tracks[
                "playlist_offset"
            ].max()
            tracks_to_remove = source_tracks[
                source_tracks["playlist_offset"] <= playlist_from_max_saved_offset
            ]
        else:
            tracks_to_remove = saved_source_tracks
        spotipy_pandas.add_tracks_to_playlist(
            sp, shifter_backup_playlist, tracks_to_remove
        )
        spotipy_pandas.remove_tracks_from_library(sp, saved_source_tracks)
        spotipy_pandas.remove_tracks_from_playlist(sp, source_id, tracks_to_remove)

        print("Done!")


if __name__ == "__main__":
    shift_playlists()
