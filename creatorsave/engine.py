"""Download engine; no Qt dependency."""
import base64
import importlib.util
import json
import os
import re
import uuid
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from .core import video_id, redact
from .profiles import OutputProfile

FORMATS = {'best': 'bv*+ba/b', '1080': 'bv*[height<=1080]+ba/b[height<=1080]', '720': 'bv*[height<=720]+ba/b[height<=720]', 'audio': 'bestaudio/best', 'audio_mp3': 'bestaudio/best'}

class Cancelled(Exception):
    pass

class SafeLogger:
    def __init__(self, emit): self.emit = emit
    def debug(self, message): pass
    def warning(self, message): self.emit({'state': 'notice', 'detail': redact(message)})
    def error(self, message): self.emit({'state': 'error', 'detail': redact(message)})

def dependencies():
    return {**{name: shutil.which(name) for name in ('ffmpeg', 'ffprobe', 'deno')},
            **{name: bool(importlib.util.find_spec(name)) for name in ('yt_dlp', 'yt_dlp_ejs')}}

def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, encoding='utf-8', check=True, timeout=90, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return json.loads(result.stdout)

def verify(path, audio_only=False):
    info = probe(path)
    streams = info.get('streams', [])
    if not any(s.get('codec_type') == 'audio' for s in streams):
        raise RuntimeError('No audio track')
    real_video=any(s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic') for s in streams)
    if audio_only and real_video:raise RuntimeError('Audio output contains a video track')
    if not audio_only and not real_video:
        raise RuntimeError('No video track')
    if float(info.get('format', {}).get('duration', 0)) <= 0:
        raise RuntimeError('Invalid duration')
    return info

def options(cookie, emit):
    result = dict(noplaylist=True, quiet=True, logger=SafeLogger(emit), socket_timeout=25,
                  retries=3, fragment_retries=3, extractor_retries=2)
    if cookie:
        if not Path(cookie).is_file(): raise ValueError('Cookie file does not exist')
        result['cookiefile'] = cookie
    return result

def extract(url, cookie='', emit=lambda event: None):
    from yt_dlp import YoutubeDL
    identity = video_id(url)
    with YoutubeDL(options(cookie, emit)) as ydl:
        info = ydl.extract_info('https://www.youtube.com/watch?v=' + identity, download=False)
    # Only retain fields used by the app; signed format URLs are not stored.
    heights = sorted({f['height'] for f in info.get('formats', []) if f.get('height') and f.get('vcodec') not in (None,'none','images')})
    return {key: info.get(key) for key in ('id', 'title', 'channel', 'channel_id', 'channel_url', 'upload_date', 'duration', 'thumbnail')} | {'heights': heights}

def run_ffmpeg(args, cancelled=lambda: False):
    command=['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)]
    process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        while True:
            if cancelled():
                process.terminate()
                try:process.communicate(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.communicate()
                raise Cancelled('Cancelled; source files retained')
            try:
                _,error=process.communicate(timeout=0.25);break
            except subprocess.TimeoutExpired:continue
        if process.returncode:raise RuntimeError('Media processing failed: '+redact(error.decode('utf-8',errors='replace')[-1800:]))
    finally:
        if process.poll() is None:process.kill();process.communicate()


def prepare_audio(source, mp3=False, metadata=None, cancelled=lambda: False, destination=None):
    source=Path(source)
    info=probe(source)
    tracks=[s for s in info['streams'] if s.get('codec_type')=='audio']
    if not tracks:raise RuntimeError('No audio track')
    codec=tracks[0]['codec_name']
    extension='mp3' if mp3 else {'opus':'opus','vorbis':'ogg','aac':'m4a','alac':'m4a','mp3':'mp3','flac':'flac'}.get(codec,'mka')
    target=Path(destination) if destination is not None else source.with_suffix('.'+extension)
    real_video=any(s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic') for s in info['streams'])
    if source==target and not real_video:return source
    temporary=target.with_name(target.stem+'.converting'+target.suffix)
    args=['-i',source,'-map','0:a:0','-vn']
    if mp3 and codec!='mp3':args+=['-c:a','libmp3lame','-b:a','320k']
    else:args+=['-c:a','copy']
    if extension=='mp3':args+=['-id3v2_version','3']
    if extension=='m4a':args+=['-movflags','+faststart']
    for name,key in (('title','title'),('artist','channel')):
        if metadata and metadata.get(key):args+=['-metadata',name+'='+metadata[key]]
    try:
        run_ffmpeg([*args,temporary],cancelled)
        result=verify(temporary,True)
        audio=next(s for s in result['streams'] if s.get('codec_type')=='audio')
        if mp3 and audio.get('codec_name')!='mp3':raise RuntimeError('MP3 codec validation failed')
        if not mp3 and audio.get('codec_name')!=codec:raise RuntimeError('Original audio codec changed')
        os.replace(temporary,target)
    except BaseException:
        temporary.unlink(missing_ok=True);raise
    return target


IMAGE_CODECS={'mjpeg','png','webp','bmp','jpeg2000'}

def cover_streams(media):
    return [s for s in probe(media).get('streams',[]) if s.get('disposition',{}).get('attached_pic') and s.get('codec_name') in IMAGE_CODECS and s.get('width',0)>0 and s.get('height',0)>0]

def embedded_cover_bytes(media):
    media=Path(media);suffix=media.suffix.lower()
    if suffix in ('.opus','.ogg','.flac'):
        from mutagen import File
        from mutagen.flac import Picture
        audio=File(media)
        if audio is not None:
            if getattr(audio,'pictures',None):return [p.data for p in audio.pictures if p.type==3 and p.data]
            if audio.tags:
                return [p.data for p in (Picture(base64.b64decode(raw)) for raw in audio.tags.get('metadata_block_picture',[])) if p.type==3 and p.data]
        return []
    if suffix=='.mp3':
        from mutagen.id3 import ID3,ID3NoHeaderError
        try:return [p.data for p in ID3(media).getall('APIC') if p.type==3 and p.data]
        except ID3NoHeaderError:return []
    result=[]
    for stream in cover_streams(media):
        command=['ffmpeg','-hide_banner','-loglevel','error','-i',str(media),'-map','0:'+str(stream['index']),'-c:v','copy','-frames:v','1','-f','image2pipe','pipe:1']
        frame=subprocess.run(command,capture_output=True,timeout=90,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if frame.stdout:result.append(frame.stdout)
    return result

def has_embedded_cover(media):return bool(embedded_cover_bytes(media))

def cover_matches(media,cover):return Path(cover).read_bytes() in embedded_cover_bytes(media)

def container_matches(info,container):
    formats=set(info.get('format',{}).get('format_name','').split(','))
    return ('mp4' in formats or 'mov' in formats) if container=='mp4' else 'matroska' in formats

def prepare_video(source, container='mp4', cancelled=lambda:False, destination=None):
    if container not in ('mp4','mkv'):raise ValueError('Choose MP4 or MKV')
    source=Path(source);before=verify(source)
    main=next(s for s in before['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
    target=Path(destination) if destination is not None else source.with_suffix('.'+container)
    if source==target and container_matches(before,container):return source
    temporary=target.with_name(target.stem+'.packaging'+target.suffix)
    args=['-i',source,'-map','0:'+str(main['index']),'-map','0:a','-map_metadata','0','-c','copy']
    if container=='mp4':args+=['-movflags','+faststart']
    try:
        try:run_ffmpeg([*args,temporary],cancelled)
        except Cancelled:raise
        except Exception as exc:raise RuntimeError('Selected '+container.upper()+' cannot preserve these streams without re-encoding. Choose another container. '+str(exc)) from exc
        after=verify(temporary)
        video=next(s for s in after['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
        if any(video.get(k)!=main.get(k) for k in ('codec_name','width','height')):raise RuntimeError('Video changed during packaging')
        previous_audio=[s.get('codec_name') for s in before['streams'] if s.get('codec_type')=='audio']
        if previous_audio!=[s.get('codec_name') for s in after['streams'] if s.get('codec_type')=='audio']:raise RuntimeError('Audio changed during packaging')
        os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    return target

def embed_cover(media, cover, audio_only=False, cancelled=lambda:False):
    media=Path(media);cover=Path(cover)
    if cover_matches(media,cover):return True
    target=media.with_name(media.stem+'.cover'+media.suffix);suffix=media.suffix.lower()
    try:
        if suffix in ('.opus','.ogg','.flac'):
            from mutagen import File
            from mutagen.flac import Picture
            shutil.copy2(media,target);audio=File(target)
            if audio is None:raise RuntimeError('Unsupported audio tags')
            picture=Picture();picture.type=3;picture.mime='image/jpeg';picture.desc='Cover';picture.data=cover.read_bytes()
            if suffix=='.flac':audio.clear_pictures();audio.add_picture(picture)
            else:
                if audio.tags is None:audio.add_tags()
                audio['metadata_block_picture']=[base64.b64encode(picture.write()).decode('ascii')]
            audio.save()
        else:
            info=probe(media);args=['-i',media]
            if audio_only and suffix in ('.mp3','.m4a','.mp4'):
                args+=['-i',cover,'-map','0:a:0','-map','1:v:0','-c','copy','-disposition:v:0','attached_pic']
                if suffix=='.mp3':args+=['-id3v2_version','3','-metadata:s:v','title=Album cover','-metadata:s:v','comment=Cover (front)']
            elif suffix=='.mp4':
                main=next(s for s in info['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
                args+=['-i',cover,'-map','0:'+str(main['index']),'-map','0:a','-map','1:v:0','-c','copy','-disposition:v:1','attached_pic','-movflags','+faststart']
            elif suffix in ('.mkv','.mka'):
                for stream in info['streams']:
                    if stream.get('codec_type')=='audio' or (stream.get('codec_type')=='video' and not stream.get('disposition',{}).get('attached_pic')):args+=['-map','0:'+str(stream['index'])]
                args+=['-c','copy','-attach',cover,'-metadata:s:t:0','mimetype=image/jpeg','-metadata:s:t:0','filename=cover.jpg']
            else:return False
            run_ffmpeg([*args,target],cancelled)
        verify(target,audio_only)
        if not cover_matches(target,cover):raise RuntimeError('Embedded cover does not match the source JPG')
        if cancelled():raise Cancelled('Cancelled; original file retained')
        os.replace(target,media);return True
    finally:target.unlink(missing_ok=True)

def verified_media_info(info):
    return {
        'verified_container':info.get('format',{}).get('format_name'),
        'verified_duration':info.get('format',{}).get('duration'),
        'verified_video':[{key:s.get(key) for key in ('codec_name','width','height','bit_rate')} for s in info['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')],
        'verified_audio':[{key:s.get(key) for key in ('codec_name','channels','sample_rate','bit_rate')} for s in info['streams'] if s.get('codec_type')=='audio'],
    }

def finalize_media(media,cover,profile,emit,cancelled):
    """Single output contract for every downloaded video and audio preset."""
    media=Path(media);cover=Path(cover)
    if not cover.is_file():raise RuntimeError('Original cover is missing; work files retained')
    if cancelled():raise Cancelled('Cancelled; source retained')
    if shutil.disk_usage(media.parent).free<media.stat().st_size*2+64*1024**2:raise RuntimeError('Insufficient space for verified output; source retained')
    if not profile.audio_only:
        emit({'state':'packaging'})
        media=prepare_video(media,profile.container,cancelled)
    emit({'state':'cover'})
    if not embed_cover(media,cover,profile.audio_only,cancelled):raise RuntimeError('Cover embedding unsupported; work files retained')
    emit({'state':'verifying'})
    result=verify(media,profile.audio_only)
    if not profile.audio_only:
        if media.suffix.lower()!='.'+profile.container or not container_matches(result,profile.container):raise RuntimeError('Output container differs from your selection')
        real_video=next(s for s in result['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
        if profile.height_limit and real_video.get('height',0)>profile.height_limit:raise RuntimeError('Output resolution exceeds the selected quality limit')
    if not cover_matches(media,cover):raise RuntimeError('Cover verification failed; work files retained')
    if cancelled():raise Cancelled('Cancelled; source retained')
    return media,result


def deliver(sources, root):
    """Never overwrite existing user files; rollback files created by this call."""
    targets = [root / source.name for source in sources]
    if any(p.exists() for p in targets): raise FileExistsError('Output already exists; choose a different staging folder')
    created, partials = [], []
    try:
        for source, target in zip(sources, targets):
            partial = root / (target.name + '.creatorsave-part')
            # Exclusive create avoids overwriting a previous interrupted delivery.
            with source.open('rb') as src, partial.open('xb') as dst:
                partials.append(partial)
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush(); os.fsync(dst.fileno())
            if partial.stat().st_size != source.stat().st_size: raise OSError('Incomplete copy')
            if os.name == 'nt': os.rename(partial, target)
            else:
                os.link(partial, target); partial.unlink()
            created.append(target)
    except BaseException:
        for path in created + partials:
            path.unlink(missing_ok=True)
        raise
    return targets

def download(url, folder, preset, cookie, emit, cancelled, video_format='mp4', *, filename_date=True):
    identity = video_id(url)
    source_url = 'https://www.youtube.com/watch?v=' + identity
    return download_media(source_url, identity, folder, preset, cookie, emit, cancelled, video_format, filename_date=filename_date)


def download_media(source_url, identity, folder, preset, cookie, emit, cancelled, video_format, media_info=None, *, filename_date=True):
    from yt_dlp import YoutubeDL

    profile = OutputProfile(preset, video_format)
    root = Path(folder).resolve()
    root.mkdir(parents=True, exist_ok=True)
    work = root / '.creatorsave' / (identity + '-' + preset + (('-'+video_format) if not profile.audio_only else ''))
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 1024 ** 3: raise RuntimeError('Less than 1 GB free space')
    def check():
        if cancelled(): raise Cancelled('Cancelled; temporary files retained')
    def progress(data):
        check()
        info = data.get('info_dict', {})
        state = 'audio' if info.get('vcodec') == 'none' else 'video'
        emit({'state': state, 'done': data.get('downloaded_bytes', 0), 'total': data.get('total_bytes') or data.get('total_bytes_estimate'), 'estimated': not bool(data.get('total_bytes')), 'speed': data.get('speed')})
    def processing(data):
        check()
        name = data.get('postprocessor', '')
        emit({'state': 'cover' if 'Thumbnail' in name else 'merging'})
    audio_only=preset in ('audio','audio_mp3')
    tag=' (MP3)' if preset=='audio_mp3' else ' (Audio)' if audio_only else profile.filename_tag
    date_prefix = '%(upload_date>%Y-%m-%d|unknown-date)s ' if filename_date else ''
    opts = options(cookie, emit)
    opts.update(format=FORMATS[preset], paths={'home': str(work)},
        outtmpl=date_prefix+'%(title).100B'+tag+' [%(id)s].%(ext)s',
        windowsfilenames=True, writethumbnail=True, keepvideo=True,
        merge_output_format='mkv', continuedl=True, progress_hooks=[progress],
        postprocessor_hooks=[processing], postprocessors=[{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}])
    emit({'state': 'extracting'})
    with YoutubeDL(opts) as ydl:
        if media_info is None:
            info = ydl.extract_info(source_url, download=True)
        else:
            info = ydl.process_ie_result(media_info, download=True)
        prepared=Path(ydl.prepare_filename(info))
        base=prepared.with_suffix('')
    check()
    emit({'state': 'verifying'})
    # Expected final basename comes from yt-dlp, never an arbitrary file in the folder.
    candidates = [Path(str(base) + '.' + ext) for ext in ('mp4', 'mkv', 'webm', 'm4a', 'opus', 'mp3') if Path(str(base) + '.' + ext).is_file()]
    if prepared.is_file():media=prepared
    elif len(candidates)==1:media=candidates[0]
    else:raise RuntimeError('Cannot identify unique final media; work files retained')
    if audio_only:
        emit({'state':'converting' if preset=='audio_mp3' else 'audio_packaging'})
        media=prepare_audio(media,preset=='audio_mp3',info,cancelled)
    cover=Path(str(base)+'.jpg')
    media,result=finalize_media(media,cover,profile,emit,cancelled)
    warnings=[]
    metadata = {key: info.get(key) for key in ('id', 'title', 'channel', 'channel_id', 'channel_url', 'upload_date', 'duration', 'format_id', 'format', 'height', 'width', 'ext')}
    metadata.update(output_profile=profile.to_dict(),source_ext=info.get('ext'),ext=media.suffix.lstrip('.'),audio_mode=('mp3' if preset=='audio_mp3' else 'original') if audio_only else None,cover_embedded=has_embedded_cover(media),verified_audio=[{k:stream.get(k) for k in ('codec_name','bit_rate','sample_rate','channels')} for stream in result['streams'] if stream.get('codec_type')=='audio'])
    metadata.update(source_url=source_url, downloaded_at=datetime.now(timezone.utc).isoformat(), warnings=warnings)
    metadata.update(verified_media_info(result))
    sidecar = Path(str(base) + '.info.json')
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    emit({'state': 'delivering'})
    targets = deliver([media, cover, sidecar], root)
    return {'id': identity, 'path': str(targets[0]), 'warnings': warnings, 'probe': result,'cover_verified':True}



def export_audio_file(source, folder, emit=lambda event: None, cancelled=lambda: False):
    """Convert an explicit existing audio file; never modify or re-download it."""
    source=Path(source).resolve();root=Path(folder).resolve()
    verify(source,True)
    root.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(root).free < 1024**3:raise RuntimeError('Less than 1 GB free space')
    work=root/'.creatorsave'/('local-'+uuid.uuid4().hex);work.mkdir(parents=True)
    stem=source.stem
    if ' (MP3)' not in stem:
        stem=re.sub(r' (?:\(Audio\) )?(\[[A-Za-z0-9_-]{11}\])$',r' (MP3) \1',stem) if re.search(r'\[[A-Za-z0-9_-]{11}\]$',stem) else stem+' (MP3)'
    original_info=source.with_suffix('.info.json')
    metadata={}
    if original_info.is_file():
        try:
            raw=json.loads(original_info.read_text(encoding='utf-8'))
            metadata={key:raw.get(key) for key in ('id','title','channel','channel_id','channel_url','upload_date','source_url')}
        except (OSError,ValueError):pass
    if cancelled():raise Cancelled('Cancelled; source retained')
    emit({'state':'converting'})
    media=prepare_audio(source,True,metadata,cancelled,work/(stem+'.mp3'))
    cover=work/(stem+'.jpg');source_cover=source.with_suffix('.jpg')
    if source_cover.is_file():shutil.copy2(source_cover,cover)
    elif has_embedded_cover(source):
        try:run_ffmpeg(['-i',source,'-map','0:v:0','-frames:v','1','-c:v','mjpeg',cover],cancelled)
        except Cancelled:raise
        except Exception:pass
    media,result=finalize_media(media,cover,OutputProfile('local_mp3'),emit,cancelled)
    warnings=[]
    match=re.search(r'\[([A-Za-z0-9_-]{11})\]$',source.stem)
    identity=metadata.get('id') or (match[1] if match else None)
    metadata.update(id=identity,ext='mp3',audio_mode='mp3',converted_at=datetime.now(timezone.utc).isoformat(),cover_embedded=has_embedded_cover(media),warnings=warnings)
    metadata.update(verified_media_info(result))
    sidecar=work/(stem+'.info.json');sidecar.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    if cancelled():raise Cancelled('Cancelled; source retained')
    emit({'state':'delivering'})
    outputs=[media,sidecar]+([cover] if cover.is_file() else [])
    targets=deliver(outputs,root)
    return {'id':identity,'path':str(targets[0]),'warnings':warnings,'probe':result,'cover_verified':True}


def export_video_file(source,folder,video_format='mp4',emit=lambda event:None,cancelled=lambda:False):
    source=Path(source).resolve();root=Path(folder).resolve();verify(source)
    profile=OutputProfile('local_video',video_format)
    root.mkdir(parents=True,exist_ok=True)
    required=source.stat().st_size*3+128*1024**2
    if shutil.disk_usage(root).free<required:raise RuntimeError('Insufficient space for safe video packaging and cover verification')
    work=root/'.creatorsave'/('local-video-'+uuid.uuid4().hex);work.mkdir(parents=True)
    stem=re.sub(r' (?:\((?:\d+p )?(?:MP4|MKV)\) )?(\[[A-Za-z0-9_-]{11}\])$',profile.filename_tag+r' \1',source.stem) if re.search(r'\[[A-Za-z0-9_-]{11}\]$',source.stem) else source.stem+profile.filename_tag
    cover=work/(stem+'.jpg');original_cover=source.with_suffix('.jpg')
    if original_cover.is_file():shutil.copy2(original_cover,cover)
    else:
        pictures=embedded_cover_bytes(source)
        if not pictures:raise RuntimeError('Original cover missing; source retained')
        cover.write_bytes(pictures[0])
    emit({'state':'packaging'})
    media=prepare_video(source,video_format,cancelled,work/(stem+'.'+video_format))
    media,result=finalize_media(media,cover,profile,emit,cancelled)
    original_info=source.with_suffix('.info.json');metadata={}
    if original_info.is_file():
        try:
            raw=json.loads(original_info.read_text(encoding='utf-8'))
            metadata={key:raw.get(key) for key in ('id','title','channel','channel_id','channel_url','upload_date','source_url')}
        except (OSError,ValueError):pass
    match=re.search(r'\[([A-Za-z0-9_-]{11})\]$',source.stem);identity=metadata.get('id') or (match[1] if match else None)
    metadata.update(id=identity,ext=video_format,output_profile=profile.to_dict(),cover_embedded=True,converted_at=datetime.now(timezone.utc).isoformat())
    metadata.update(verified_media_info(result))
    sidecar=work/(stem+'.info.json');sidecar.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    emit({'state':'delivering'});targets=deliver([media,cover,sidecar],root)
    return {'id':identity,'path':str(targets[0]),'warnings':[],'probe':result,'cover_verified':True}
