from enum import Enum

import spotipy
import validators
from spotipy.oauth2 import SpotifyClientCredentials


class URLType(Enum):
    YOUTUBE = "YouTube"
    SPOTIFY = "Spotify"
    UNKNOWN = "Unknown"


def is_url(url) -> bool:
    """Check if a given string is a URL."""
    if not isinstance(url, str):
        return False

    try:
        return validators.url(url) is True
    except validators.ValidationError:
        return False


def identify_url_type(url):
    """
    Identifies whether the given string is a YouTube or Spotify URL.

    Args:
        url (str): The URL to evaluate.

    Returns:
        URLType: Enum indicating the type of URL.
    """
    if is_url(url) is False:
        return URLType.UNKNOWN
    if "spotify.com" in url:
        return URLType.SPOTIFY
    if "youtube.com" in url or "youtu.be" in url:
        return URLType.YOUTUBE


def parse_spotify_url(url: str) -> str:
    """
    Parse a Spotify URL to extract the track ID.

    Args:
        url (str): The Spotify URL to parse.

    Returns:
        str: The track ID extracted from the URL.
    """
    track_id: str = url.split("/track/")[1].split("?")[0]

    spotify = spotipy.Spotify(
        client_credentials_manager=SpotifyClientCredentials(
            client_id="9e38891317d2436a8b5377b498b9c57d",
            client_secret="f71108ab31a44cf39ce44fa1fa78f188",
        )
    )

    results = spotify.track(track_id)
    return f"{results["name"]} - {results["artists"][0]["name"]}"
