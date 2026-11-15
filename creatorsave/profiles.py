"""Persistable output choices, independent from quality caps."""
from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class OutputProfile:
    quality:str='best'
    container:str='mp4'

    def __post_init__(self):
        if self.quality not in ('best','1080','720','audio','audio_mp3','local_mp3','local_video'):
            raise ValueError('Unknown output quality')
        if self.container not in ('mp4','mkv'):
            raise ValueError('Choose MP4 or MKV')

    @property
    def audio_only(self):return self.quality in ('audio','audio_mp3','local_mp3')
    @property
    def height_limit(self):return int(self.quality) if self.quality in ('1080','720') else None
    @property
    def filename_tag(self):
        quality=(self.quality+'p ') if self.height_limit else ''
        return ' ('+quality+self.container.upper()+')'
    def to_dict(self):return asdict(self)
