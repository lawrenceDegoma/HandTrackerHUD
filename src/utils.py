import spotipy
from dotenv import load_dotenv
load_dotenv()
from spotipy.oauth2 import SpotifyOAuth
import os

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-playback-state,user-modify-playback-state,user-read-currently-playing"
))

def play():
    sp.start_playback()

def pause():
    sp.pause_playback()

def next_track():
    sp.next_track()

def previous_track():
    sp.previous_track()

def get_current_track():
    current = sp.current_playback()
    if current and current['item']:
        return {
            "name": current['item']['name'],
            "artist": current['item']['artists'][0]['name'],
            "album_art": current['item']['album']['images'][0]['url']
        }
    return None