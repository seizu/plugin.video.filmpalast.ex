#!/usr/bin/python
# kodi18+ (python3+)
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import re
import os
import sys
import xlibs.urllib3 as urllib3p
from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
#import web_pdb; web_pdb.set_trace()

# Constants
BASE_URL = 'https://filmpalast.to'
STREAM_URL_TEMPLATE = 'https://filmpalast.to/stream/{id}/1'
MAX_ITEMS = 32
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
DEBUG = True

# Regex patterns
PATTERNS = {
    'genre_section': r'<section id="genre">(.*?)</section>',
    'genre_links': r'<a[^>]*href="([^"]*)">[ ]*([^<]*)</a>',
    'content_entries': r'id="content"[^>]*>(.+?)<[^>]*id="paging"',
    'movie_data': r'</cite>(.*?)<a[^>]*href="//filmpalast.to([^"]*)"[^>]*title="([^"]*)"[^>]*>[^<]*<img[^>]*src=["\']([^"\']*)["\'][^>]*>',
    'next_page': r'<a[^>]*class="[^"]*pageing[^"]*"[^>]*href=["\']([^"\']*)["\'][^>]*>[ ]*vorw',
    'stars': r'star_on.png',
    'votes': r'<sm.*?p;(.*?)&nbsp.*?ll>',
    'video_sources': r'<p class="hostName">(.*?)<.*?<li class="streamPlayBtn clearfix rb">.*?<a.*?class="button.*?(?:url|href)="(.*?)"',
    'imdb_rating': r'>&ndash; Imdb: ([0-9,.]{0,3})/10',
    'fp_rating': r'average">([0-9,.]{0,3})<',
    'year_runtime': r'>Ver&ouml;ffentlicht: ([^\n]*).*?>Spielzeit:.*?>(.*?)<',
    'description': r'itemprop="description">(.*?)<',
    'genres': r'class="rb"[^>]*genre/(.*?)"',
    'actors': r'class="rb".*?"/search/title/(.*?)"',
    'html_entities': r'&#\d+;'
}

# Plugin configuration
def load_settings():
    # Load all plugin settings into a dictionary
    settings = xbmcaddon.Addon(id='plugin.video.filmpalast.ex')
    
    return {
        'filter_unknown_hoster': settings.getSetting("filterUnknownHoster") == 'true',
        'force_view_mode': settings.getSetting("forceViewMode") == 'true',
        'view_mode': str(settings.getSetting("viewMode")),
        'show_rating': settings.getSetting("showRating") == 'true',
        'show_votes': settings.getSetting("showVotes") == 'true',
        'show_movie_info': settings.getSetting("showMovieInfo") == 'true',
        'preload_info': settings.getSetting("preloadInfo") == 'true',
        'pre_rating': settings.getSetting("preRating") == 'true',
        'pre_genres': settings.getSetting("preGenres") == 'true',
        'pre_description': settings.getSetting("preDescription") == 'true',
        'pre_year': settings.getSetting("preYear") == 'true',
        'bypass_dns_lock': settings.getSetting("bypassDNSlock") == 'true',
        'caching': settings.getSetting("caching") == 'true' or settings.getSetting("bypassDNSlock") == 'true'
    }

# Global variables
config = load_settings()
pluginhandle = int(sys.argv[1])
itemcnt = 0
temp_dir = xbmcvfs.translatePath("special://temp") + "filmpalast" + os.sep

if DEBUG:
    print("View Mode: " + config['view_mode'])

def ensure_temp_dir():
    #Create temp directory or clean it if caching is disabled
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)
    elif not config['caching']:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))

def set_view_mode():
    # Apply view mode if forced in settings
    if config['force_view_mode']:
        xbmc.executebuiltin('Container.SetViewMode({})'.format(config['view_mode']))

def normalize_url(url, base_url=BASE_URL):
    # Ensure URL has proper protocol and domain
    if not url.lower().startswith('http'):
        return base_url + url
    return url

def START():
    # Main menu
    menu_items = [
        ('Neu', BASE_URL + '/'),
        ('Neue Filme', BASE_URL + '/movies/new'),
        ('Neue Serien', BASE_URL + '/serien/view'),
        ('Top Filme', BASE_URL + '/movies/top'),
        ('English', BASE_URL + '/search/genre/Englisch'),
        ('Kategorien', BASE_URL),
        ('Alphabetisch', BASE_URL),
        ('Suche...', BASE_URL + '/search/title/')
    ]
    
    modes = [1, 1, 1, 1, 1, 2, 3, 4]
    
    for (name, url), mode in zip(menu_items, modes):
        addDir(name, url, mode, '', True)
    
    set_view_mode()

def CATEGORIES(url):
    # Show genre categories
    data = getUrl(url)
    if not data:
        return
        
    genre_sections = re.findall(PATTERNS['genre_section'], data, re.S | re.I)
    for genre_section in genre_sections:
        genre_links = re.findall(PATTERNS['genre_links'], genre_section, re.S | re.I)
        for href, name in genre_links:
            addDir(clean(name), href, 1, '', True)
    
    set_view_mode()

def ALPHA():
    # Show alphabetical navigation
    addDir('#', BASE_URL + '/search/alpha/0-9', 1, '', True)
    for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        addDir(char, BASE_URL + '/search/alpha/' + char, 1, '', True)
    
    set_view_mode()

def INDEX(caturl):
    # Display movie/series listings with pagination
    if DEBUG:
        xbmc.log(caturl)
    
    global itemcnt
    data = getUrl(caturl)
    if not data:
        return
    
    # Process entries
    content_entries = re.findall(PATTERNS['content_entries'], data, re.S | re.I)
    for entry in content_entries:
        if DEBUG:
            print(entry)
        
        process_movie_entries(entry)
    
    # Handle pagination
    handle_pagination(data)
    set_view_mode()

def process_movie_entries(entry):
    # Process individual movie entries from HTML
    global itemcnt
    
    movie_matches = re.findall(PATTERNS['movie_data'], entry, re.S | re.I)
    for rating, url, title, image in movie_matches:
        url = normalize_url(url)
        image = normalize_url(image)
        
        title = enhance_title_with_ratings(title, rating, url)
        description = get_preload_description(url) if config['preload_info'] else ""
        
        addLink(clean(title), url, 10, image, description)
        itemcnt += 1

def enhance_title_with_ratings(title, rating, url):
    # Add rating information to title based on settings
    if config['show_rating']:
        stars = len(re.findall(PATTERNS['stars'], rating, re.S | re.I))
        title += "  [COLOR=blue]" + str(stars) + "/10[/COLOR]"
    
    if config['show_votes']:
        votes = re.findall(PATTERNS['votes'], rating, re.S | re.I)
        if votes:
            title += "  [COLOR=blue](" + str(votes[0]) + " votes)[/COLOR]"
    
    if config['preload_info']:
        info = getInfos(url)
        title = add_preload_info_to_title(title, info)
    
    return title

def add_preload_info_to_title(title, info):
    # Add preloaded info to title based on settings
    if config['pre_rating'] and info['imdb']:
        title += " [COLOR=red]" + info['imdb'] + "/10[/COLOR]"
    if config['pre_genres'] and info['genres']:
        title += " [COLOR=green]" + info['genres'] + "[/COLOR]"
    if config['pre_year'] and info['year']:
        title += " [COLOR=blue](" + info['year'] + ")[/COLOR]"
    
    return title

def get_preload_description(url):
    # Get description for preloading if enabled
    if config['pre_description']:
        info = getInfos(url)
        return info.get('description', '')
    return ''

def handle_pagination(data):
    # Handle next page navigation
    global itemcnt
    
    next_pages = re.findall(PATTERNS['next_page'], data, re.S | re.I)
    if next_pages:
        if DEBUG:
            print(next_pages)
        
        next_url = next_pages[0]
        if itemcnt >= MAX_ITEMS:
            addDir('Weiter >>', next_url, 1, '', True)
        else:
            INDEX(next_url)

def SEARCH(url):
    # Handle search functionality
    keyboard = xbmc.Keyboard('', 'Suche')
    keyboard.doModal()
    
    if keyboard.isConfirmed() and keyboard.getText():
        search_string = urllib.parse.quote(keyboard.getText())
        INDEX(url + search_string)

def clean(text):
    # Clean HTML entities from text
    matches = re.findall(PATTERNS['html_entities'], text)
    for hit in set(matches):
        try:
            text = text.replace(hit, chr(int(hit[2:-1])))
        except ValueError:
            pass
    return urllib.parse.unquote_plus(text)

def selectVideoDialog(videos, url, data=None):
    # Show dialog to select video source
    titles = [name for name, src in videos]
    infostring = ""
    
    if config['show_movie_info']:
        info = getInfos(url, data)
        infostring = "FP: {}/10 Imdb: {}/10 Jahr: {}\nDauer: {} Genre: {}".format(
            info['fp'], info['imdb'], info['year'], info['runtime'], info['genres']
        )
    
    idx = xbmcgui.Dialog().select(infostring, titles)
    return videos[idx][1] if idx > -1 else False

def getInfos(url, data=None):
    # Extract movie information from page or cache
    info = {
        'fp': '0', 'imdb': '0', 'genres': '', 'actors': '', 
        'year': '', 'runtime': '', 'description': ''
    }
    
    # Check cache
    if config['caching']:
        cached_info = get_cached_info(url)
        if cached_info:
            return cached_info
    
    # Get data if not provided
    if data is None:
        data = getUrl(url)
    
    if not data:
        return info
    
    # Extract information using regex patterns
    extract_ratings(data, info)
    extract_year_runtime(data, info)
    extract_description(data, info)
    extract_genres_actors(data, info)
    
    # Cache the result
    if config['caching']:
        cache_info(url, info)
    
    return info

def get_cached_info(url):
    # Get cached movie info if available
    cache_file = get_cache_filename(url)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return eval(f.read())
        except Exception:
            pass
    return None

def cache_info(url, info):
    # Cache movie info to file
    cache_file = get_cache_filename(url)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(str(info))
    except Exception:
        pass

def get_cache_filename(url):
    # Generate cache filename for URL
    md5hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(temp_dir, md5hash)

def extract_ratings(data, info):
    # Extract IMDB and FP ratings
    imdb_match = re.search(PATTERNS['imdb_rating'], data, re.S | re.I)
    if imdb_match:
        info['imdb'] = imdb_match.group(1)
    
    fp_match = re.search(PATTERNS['fp_rating'], data, re.S | re.I)
    if fp_match:
        info['fp'] = fp_match.group(1)

def extract_year_runtime(data, info):
    # Extract year and runtime information
    match = re.search(PATTERNS['year_runtime'], data, re.S | re.I)
    if match:
        info['year'] = match.group(1).replace('false', '')
        info['runtime'] = match.group(2)

def extract_description(data, info):
    # Extract movie description
    match = re.search(PATTERNS['description'], data, re.S | re.I)
    if match:
        info['description'] = match.group(1)

def extract_genres_actors(data, info):
    # Extract genres and actors
    genres = re.findall(PATTERNS['genres'], data, re.S | re.I | re.DOTALL)
    info['genres'] = " / ".join(genres)
    
    actors = re.findall(PATTERNS['actors'], data, re.S | re.I | re.DOTALL)
    info['actors'] = " / ".join(actors)

def resolveUrl(media_url, validate_only=False):
    # Resolve media URL using available resolver
    try:
        try:
            import resolveurl as resolver
        except ImportError:
            import urlresolver as resolver
        
        if media_url:
            if validate_only:
                return resolver.HostedMediaFile(media_url).valid_url()
            return resolver.resolve(media_url)
    except Exception as e:
        if DEBUG:
            print("Resolve error:", e)
    return False

def PLAYVIDEO(url):
    # Play video from selected URL
    data = getUrl(url)
    if not data:
        return
    
    # Find available video sources
    videos = get_video_sources(data)
    
    if not videos:
        xbmc.executebuiltin("XBMC.Notification(Fehler!, Video nicht gefunden, 4000)")
        return
    
    # Select video source
    selected_url = select_video_source(videos, url, data)
    if selected_url:
        play_resolved_video(selected_url)

def get_video_sources(data):
    # Extract video sources from page data
    videos = []
    video_matches = re.findall(PATTERNS['video_sources'], data, re.S | re.I | re.DOTALL)
    
    for hoster, media_url in video_matches:
        if config['filter_unknown_hoster'] and not resolveUrl(media_url, True):
            continue
        videos.append((hoster, media_url))
    
    return videos

def select_video_source(videos, url, data):
    # Select video source (single or via dialog)
    if len(videos) == 1:
        return videos[0][1]
    return selectVideoDialog(videos, url, data)

def play_resolved_video(url):
    # Resolve and play the video URL
    stream_url = resolveUrl(url)
    if stream_url:
        if DEBUG:
            print('Opening stream:', stream_url)
        listitem = xbmcgui.ListItem(path=stream_url)
        return xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
    raise Exception("Could not resolve stream URL")

def getUrl(url):
    # Fetch URL content with proper headers
    try:
        if config['bypass_dns_lock']:
            return urllib3p.get_request(url, userAgent=USER_AGENT)
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', USER_AGENT)
        req.add_header('Referer', url)
        
        response = urllib.request.urlopen(req, timeout=30)
        data = response.read().decode('utf-8', errors='ignore')
        response.close()
        return data
    except Exception as e:
        if DEBUG:
            print("Error fetching URL:", e)
        return None

def get_params():
    # Parse URL parameters
    if len(sys.argv) < 3:
        return {}
    
    paramstring = sys.argv[2]
    if len(paramstring) < 2:
        return {}
    
    params = {}
    cleanedparams = paramstring.replace('?', '')
    
    if cleanedparams.endswith('/'):
        cleanedparams = cleanedparams[:-1]
    
    for pair in cleanedparams.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    return params

def addLink(name, url, mode, image, description=""):
    # Add playable link to directory
    # Handle image caching
    if image and config['bypass_dns_lock']:
        cache_image(image)
        image = get_image_cache_path(image)
    
    u = "{}?url={}&mode={}".format(
        sys.argv[0], 
        urllib.parse.quote_plus(url), 
        str(mode)
    )
    
    liz = xbmcgui.ListItem(name)
    liz.setArt({'icon': 'DefaultVideo.png', 'thumb': image})
    liz.setInfo(type="Video", infoLabels={"Title": name, "plot": description})
    liz.setProperty('IsPlayable', 'true')
    
    return xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), 
        url=u, 
        listitem=liz
    )

def addDir(name, url, mode, image, is_folder=False):
    # Add directory to listing
    u = "{}?url={}&mode={}".format(
        sys.argv[0], 
        urllib.parse.quote_plus(url), 
        str(mode)
    )
    
    liz = xbmcgui.ListItem(name)
    liz.setArt({'icon': 'DefaultFolder.png', 'thumb': image})
    liz.setInfo(type="Video", infoLabels={"Title": name})
    
    return xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), 
        url=u, 
        listitem=liz, 
        isFolder=is_folder
    )

def cache_image(image_url):
    # Cache image if needed
    cache_path = get_image_cache_path(image_url)
    try:
        if os.path.exists(cache_path) and os.stat(cache_path).st_size > 0 and config['caching']:
            return
        
        if config['bypass_dns_lock']:
            urllib3p.get_request(image_url, path=cache_path, userAgent=USER_AGENT)
    except Exception:
        pass

def get_image_cache_path(image_url):
    # Get cache path for image
    md5hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
    extension = image_url[-4:] if len(image_url) >= 4 else ''
    return os.path.join(temp_dir, md5hash + extension)

# Main execution
def main():
    # Main plugin execution
    ensure_temp_dir()
    
    params = get_params()
    url = urllib.parse.unquote_plus(params.get("url", ""))
    mode = int(params.get("mode", "0")) if params.get("mode") else None
    
    try:
        if mode is None or not url:
            START()
        elif mode == 1:
            INDEX(url)
        elif mode == 2:
            CATEGORIES(url)
        elif mode == 3:
            ALPHA()
        elif mode == 4:
            SEARCH(url)
        elif mode == 10:
            PLAYVIDEO(url)
        
        xbmcplugin.endOfDirectory(pluginhandle)
    
    except Exception as e:
        if DEBUG:
            print("Plugin error:", e)
        xbmcplugin.endOfDirectory(pluginhandle, succeeded=False)

if __name__ == "__main__":
    main()