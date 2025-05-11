from .Apple import AppleAPI
from .Carbon import CarbonAPI
from .Resso import RessoAPI
from .Soundcloud import SoundAPI
from .Spotify import SpotifyAPI
from .Telegram import TeleAPI
from .JioSavan import Saavn
from .Youtube import YouTubeAPI


class PlaTForms:
    def __init__(self):
        self.saavn = Saavn()
