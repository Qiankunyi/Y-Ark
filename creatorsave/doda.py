"""Resolve doda's interview course page to its public EQ streams."""
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .engine import Cancelled, download_media

PAGE = 'https://doda.jp/dcfront/prepare/videoList/'
CDN = 'https://ssl-cache.stream.ne.jp/www50/eqb503auub/jmc_pub/'
HEADERS = {'Referer': 'https://doda.jp/'}

# The page's modal links share one URL. Their clickMovie handlers provide these IDs.
COURSE = {
    157: '講座の目的と転職市場',
    68: '面接官と応募者のギャップ　～片思いにならないために～',
    69: '面接官の見ているポイント　～今日の面接、相手は誰？～',
    70: '面接官のポイント・失敗事例　①. 人事面接　～最初はやっぱり「基本」から～',
    71: '面接官のポイント・失敗事例　②. 現場面接　～キーワードは「具体性」～',
    72: '面接官のポイント・失敗事例　③. 役員面接　～最後はやっぱり「覚悟感」～',
    73: '自己紹介（経歴説明）　～自己紹介の落とし穴～',
    74: '自己PR　～求められる「私」を売り込め！～',
    75: '転職理由　～私が「前」に進む理由～',
    76: '志望理由　～御社と私が「重なるところ」～',
    77: '将来ビジョン　～入社の先が見えていますか？～',
    78: 'ストーリーの一貫性　～「変わる」と「目指す」がつながる私～',
    79: '企業への質問　～問いかけてアピールする～',
    80: '文章化・ロールプレイの重要性　～「わかった」と「できる」は違う！～',
    81: '講座のまとめとチェックリスト',
}


def page_url(url):
    parsed = urlsplit(url.strip())
    if (parsed.scheme not in ('http', 'https') or parsed.netloc.lower() != 'doda.jp'
            or parsed.path.rstrip('/') != '/dcfront/prepare/videoList'):
        raise ValueError('Expected the doda interview course page')
    return PAGE


def lessons(url):
    source_url = page_url(url)
    return [
        {'url': source_url, 'source': 'doda', 'episode': episode,
         'id': f'doda-{episode}', 'title': title, 'channel': 'doda', 'selected': False}
        for episode, title in COURSE.items()
    ]


def media_info(episode):
    title = COURSE[episode]
    callback = 'metaDataResult'
    request = Request(f'{CDN}eq_meta/v1/{episode}.jsonp?callback={callback}', headers=HEADERS)
    with urlopen(request, timeout=15) as response:
        payload = response.read(128 * 1024 + 1).decode('utf-8-sig').strip()
    if not payload.startswith(callback + '(') or not payload.endswith(');'):
        raise ValueError('Invalid doda playback metadata')
    movie = json.loads(payload[len(callback) + 1:-2])['movie']
    if (movie.get('meta_id') != str(episode) or movie.get('enable') != '1'
            or movie.get('auth') != '0' or movie.get('viewlimit_flg') != '0'):
        raise ValueError('doda lesson is unavailable for public playback')
    heights = {'hd': 720, 'hq': 480, 'sq': 360, 'lq': 240}
    formats = [
        {'url': CDN + entry['url'], 'format_id': entry['text'],
         'height': heights[entry['text']], 'protocol': 'm3u8_native', 'ext': 'mp4',
         'vcodec': 'h264', 'acodec': 'aac'}
        for entry in movie['movie_list_hls']
        if entry['text'] in heights
        and re.fullmatch(r'jmc_pd/[\w/]+\.m3u8', entry['url'], re.ASCII)
    ]
    thumbnail = urlsplit(movie['thumbnail_url'])
    prefix = '/www50/eqb503auub/jmc_pub/'
    if not formats or not re.fullmatch(prefix + r'thumbnail/[\w/.]+\.jpg', thumbnail.path, re.ASCII):
        raise ValueError('doda lesson is missing a supported stream or cover')
    return {
        'id': f'doda-{episode}', 'title': title, 'channel': 'doda',
        'duration': int(movie['duration']), 'formats': formats,
        'thumbnail': CDN + thumbnail.path.removeprefix(prefix), 'http_headers': HEADERS,
    }


def download(url, episode, folder, preset, emit, cancelled, video_format):
    source_url = page_url(url)
    if cancelled():
        raise Cancelled('Cancelled')
    info = media_info(episode)
    if cancelled():
        raise Cancelled('Cancelled')
    return download_media(source_url, info['id'], folder, preset, '', emit, cancelled, video_format, info)
