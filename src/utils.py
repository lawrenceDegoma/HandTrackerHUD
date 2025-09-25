import spotipy
from dotenv import load_dotenv

load_dotenv()
import numpy as np

from spotipy.oauth2 import SpotifyOAuth
import os

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope="user-read-playback-state,user-modify-playback-state,user-read-currently-playing",
    )
)


def toggle_play_pause():
    current = sp.current_playback()
    if current and current["is_playing"]:
        sp.pause_playback()
    else:
        sp.start_playback()


def next_track():
    sp.next_track()


def previous_track():
    try:
        sp.previous_track()
    except spotipy.SpotifyException as e:
        print(f"Error: no previous track available")


def set_volume(vol):
    current = sp.current_playback()
    if current:
        try:
            sp.volume(int(np.clip(vol, 0, 100)))
        except spotipy.SpotifyException as e:
            print("Volume control not supported on this device:", e)


def get_current_track():
    current = sp.current_playback()
    if current and current["item"]:
        return {
            "name": current["item"]["name"],
            "artist": current["item"]["artists"][0]["name"],
            "album_art": current["item"]["album"]["images"][0]["url"],
        }
    return None
