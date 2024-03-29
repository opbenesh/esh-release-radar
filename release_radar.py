import datetime
from collections import Counter
import pandas as pd
import spotipy_pandas
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from sqlalchemy import create_engine

max_items_per_album = 5

automated_playlists = [
    "74glIVP7azlpKA77RCgyDL",  # Best New Songs Right Now
    "7s2xt5dCX0e5S4Om9vyHKg",  # To The Teeth | New Metal
    "56jVMfxcgimVpN0MUSpBhp",  # Roadburn: Essential Sounds
    "4VDQ0PYPbuFqjA84cTlSMI",  # Roadburn Festival 2023
    "37i9dQZEVXbg6Lzzwd9r3r",  # Release Radar
    "37i9dQZF1DX5J7FIl4q56G",  # All New Metal
    "1gD2CRBznaV63HIkGQiQM0",  # Deathwish Staff Picks
    "0ZQcCFqc1ziBiC1fvrrbsT",  # BrooklynVegan Weekly Playlist
    "37i9dQZF1DX3YlUroplxjF",  # Crash Course
    "7i3ybB0XlLwlFysT4uULLi",  # Season of Mist New Tracks 2022
    "5Z9ssgGRlBWvT31GOLgi9R",  # New Metal Songs 2022
    "37i9dQZF1DXdiUbJTV2anj",  # New Blood
    "4uObaSNdGaPWsS7fefPYrj",  # Machine Music - Winter 2022-23
    "0imR1QYwwV13XTldnuHTOD",  # New Metal Friday
    "37i9dQZF1DWXDJDWnzE39E",  # Heavy Queens
    "3N9kTuURGVUgG7rEc8kXch",  # Slow Metal & Heavier Post Rock /2023
    "1dRIvXur9F2L7ocdVpKRvm",  # Metal Up Your Ass /2023
]

# 1 Esh Review
# inbox_playlist_id = "1xsuqA0HU4bSosdaPyVlWG"
# 2 Esh Shortlist
shortlist_playlist_id = "3qYnDeorQj7TPRlmqM8S5c"
# 3 Esh Approved
approved_playlist_id = "7pBxidVP9h7ufxsFBMwOQq"
# 5 Esh Played
# previously_played_playlist_id = "7EHT9D4ygqDlyGfqcFvkUv"

client_id = os.environ["RELEASE_RADAR_SPOTIFY_APP_ID"]
client_secret = os.environ["RELEASE_RADAR_SPOTIFY_APP_SECRET"]
redirect_uri = "http://localhost:9999/callback"
scope = "playlist-modify-private user-library-read"

db_conn_str = os.environ["RELEASE_RADAR_DB_CONN_STR"]

super_user_id = 1

dry_run = False


def parse_date(date_string):
    for fmt in ("%Y-%m-%d", "%Y", "%Y-%m"):
        try:
            return datetime.datetime.strptime(date_string, fmt)
        except ValueError:
            pass
    return None


def is_new_track(track):
    release_date = parse_date(track["release_date"])
    if not release_date:
        return None
    return (datetime.datetime.today() - release_date).days <= 60


def strip_casefold_compare(s1, s2):
    return s1.casefold().strip() == s2.casefold().strip()


def extract_and_normalize_names(track):
    def normalize(s):
        return s.strip().casefold()

    return (normalize(track["track_name"]), normalize(track["artist_name"]))


def filter_tracks(
    tracks, seen_track_ids, seen_tracks_set_name_artist, albums_counter=dict()
):
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
        albums_counter[album_id] += 1
        if albums_counter[album_id] > max_items_per_album:
            return False
        return True

    return tracks[tracks.apply(filter_track, axis=1)]


def operate_radar():
    print("Starting!")

    print("Connecting to Spotify...")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    )
    print("Connecting to database...")
    db_engine = create_engine(db_conn_str)

    print("Retrieving previously seen tracks...")
    previously_reviewed_tracks = pd.read_sql("reviewed_items", db_engine)
    print(f"Seen tracks count: {len(previously_reviewed_tracks)}")
    print("Backing up seen tracks...")
    formatted_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    previously_reviewed_tracks.to_csv(
        f"backup/seen_tracks_{formatted_time}.csv.gz", index=False, compression="gzip"
    )

    for user in pd.read_sql("users", db_engine).to_dict("records"):
        print(f'Finding new tracks for {user["name"]}...')
        user_id = user["id"]
        super_mode = user_id == super_user_id
        if super_mode and sp.current_user_saved_tracks(limit=1)["items"]:
            print("Found saved tracks! Aborting")
            continue
        tracked_playlist_id = user["tracked_artists_playlist_id"]
        inbox_playlist_id = user["inbox_playlist_id"]
        user_reviewed_tracks = previously_reviewed_tracks[
            previously_reviewed_tracks["user_id"] == user_id
        ]
        find_new_tracks(
            super_mode,
            user_id,
            tracked_playlist_id,
            inbox_playlist_id,
            sp,
            db_engine,
            user_reviewed_tracks,
        )


def find_new_tracks(
    super_mode,
    user_id,
    tracked_playlist_id,
    inbox_playlist_id,
    sp,
    db_engine,
    previously_reviewed_tracks,
):
    empty_tracks_playlist = previously_reviewed_tracks[
        previously_reviewed_tracks["user_id"] < 0
    ].copy()

    tracked_playlist_tracks = spotipy_pandas.get_playlist_tracks(
        sp, tracked_playlist_id
    )

    if super_mode:
        shortlisted_tracks = spotipy_pandas.get_playlist_tracks(
            sp, shortlist_playlist_id
        )
        approved_tracks = spotipy_pandas.get_playlist_tracks(sp, approved_playlist_id)
    else:
        shortlisted_tracks = empty_tracks_playlist.copy()
        approved_tracks = empty_tracks_playlist.copy()

    seen_tracks = pd.concat(
        [
            previously_reviewed_tracks,
            shortlisted_tracks,
            approved_tracks,
        ]
    )
    seen_albums_counter = Counter(seen_tracks.groupby(["album_id"]).count())
    seen_tracks_ids_set = set(seen_tracks["id"].unique())

    if super_mode:
        print("Reviewing playlists...")
        collected_track_dfs = []
        for playlist_id in automated_playlists:
            try:
                playlist_name = sp.playlist(playlist_id)["name"]
            except spotipy.client.SpotifyException:
                print(f"Playlist {playlist_id} not found, skipping.")
                continue
            print("Fetching tracks from " + playlist_name + ": ", end="")
            playlist_tracks = spotipy_pandas.get_playlist_tracks(sp, playlist_id)
            new_tracks = filter_tracks(
                playlist_tracks, seen_tracks_ids_set, seen_albums_counter
            )
            collected_track_dfs.append(new_tracks)
            print(f"({len(new_tracks)})")
        collected_tracks = pd.concat(collected_track_dfs)
    else:
        collected_tracks = empty_tracks_playlist.copy()

    print("Retrieving tracked artists...")
    tracked_artist_ids = pd.concat([tracked_playlist_tracks, approved_tracks])[
        "artist_id"
    ].unique()

    print("Fetching top tracks for tracked artists: ", end="")
    tracked_artists_top_tracks = spotipy_pandas.get_artists_top_tracks(
        sp, tracked_artist_ids
    )
    tracked_artists_top_tracks = filter_tracks(
        tracked_artists_top_tracks, seen_tracks_ids_set, seen_albums_counter
    )
    print(f"({len(tracked_artists_top_tracks)})")
    collected_tracks = pd.concat([collected_tracks, tracked_artists_top_tracks])

    old_review_tracks = spotipy_pandas.get_playlist_tracks(sp, inbox_playlist_id)
    if old_review_tracks is None:
        old_review_tracks = empty_tracks_playlist.copy()
    print(f"Previous review count: {len(old_review_tracks)}")

    current_review_tracks = pd.concat([old_review_tracks, collected_tracks])
    current_review_tracks.drop_duplicates(subset=["id"], inplace=True)
    current_review_tracks.drop_duplicates(
        subset=["track_name", "artist_name"], inplace=True
    )
    print(f"New items found: {len(current_review_tracks) - len(old_review_tracks)}")

    previously_played_tracks_ids_set = set(tracked_playlist_tracks["id"].unique())
    previously_played_tracks_name_artist_set = set(
        tracked_playlist_tracks.apply(extract_and_normalize_names, axis=1).unique()
    )
    current_review_tracks = filter_tracks(
        current_review_tracks,
        previously_played_tracks_ids_set,
        previously_played_tracks_name_artist_set,
    )
    print(f"Updated review count after cleanup: {len(current_review_tracks)}")

    print("Ranking review tracks...")
    played_artist_score = tracked_playlist_tracks["artist_id"].value_counts().to_dict()
    ignored_track_ids_for_scoring = set(
        pd.concat([shortlisted_tracks, current_review_tracks])["id"].to_list()
    )
    seen_artist_score = (
        seen_tracks[~seen_tracks["id"].isin(ignored_track_ids_for_scoring)]["artist_id"]
        .value_counts()
        .multiply(-1)
        .add(1)
        .to_dict()
    )
    artist_score = seen_artist_score | played_artist_score
    current_review_tracks["score"] = current_review_tracks.apply(
        lambda track: artist_score.get(track["artist_id"], 0), axis=1
    )
    ordered_review_tracks = current_review_tracks.sort_values(
        ["score", "artist_name"], ascending=[False, True]
    )

    if not dry_run:
        print("Re-creating review queue...")
        spotipy_pandas.overwrite_playlist(sp, inbox_playlist_id, ordered_review_tracks)
        print("Updating reviewed items log...")
        collected_tracks["user_id"] = user_id
        collected_tracks.to_sql(
            "reviewed_items", db_engine, if_exists="append", index=False
        )


if __name__ == "__main__":
    operate_radar()
