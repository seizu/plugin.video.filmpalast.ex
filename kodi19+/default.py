#!/usr/bin/python
# kodi18+ (python3+)

import urllib.request
import urllib.parse
import urllib.error
import re
from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcplugin

dbg = False
pluginhandle = int(sys.argv[1])
itemcnt = 0
baseurl = 'http://filmpalast.to'
streamurl = 'http://filmpalast.to/stream/{id}/1'
settings = xbmcaddon.Addon(id='plugin.video.filmpalast.ex')
maxitems = (int(settings.getSetting("items_per_page"))+1)*32
filterUnknownHoster = settings.getSetting("filterUnknownHoster") == 'true'
forceViewMode = settings.getSetting("forceViewMode") == 'true'
viewMode = str(settings.getSetting("viewMode"))
showRating = settings.getSetting("showRating") == 'true'
showVotes = settings.getSetting("showVotes") == 'true'
showMovieInfo = settings.getSetting("showMovieInfo") == 'true'
preloadInfo = settings.getSetting("preloadInfo") == 'true'
preRating = settings.getSetting("preRating") == 'true'
preGenres = settings.getSetting("preGenres") == 'true'
userAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0'

def START():
    #addDir('Neu', baseurl, 1, '', True)
    addDir('Neue Filme', baseurl + '/movies/new', 1, '', True)
    addDir('Neue Serien', baseurl + '/serien/view', 1, '', True)
    addDir('Top Filme', baseurl + '/movies/top', 1, '', True)
    addDir('Kategorien', baseurl, 2, '', True)
    addDir('Alphabetisch', baseurl, 3, '', True)
    addDir('Suche...', baseurl+'/search/title/', 4, '', True)
    if forceViewMode:
        xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def CATEGORIES(url):
    data = getUrl(url)
    for genre in re.findall('<section id="genre">(.*?)</section>', data, re.S | re.I):
        for (href, name) in re.findall('<a[^>]*href="([^"]*)">[ ]*([^<]*)</a>', genre, re.S | re.I):
            addDir(clean(name), href, 1, '', True)
    if forceViewMode:
        xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def ALPHA():
    addDir('#', baseurl + '/search/alpha/0-9', 1, '', True)
    for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        addDir(char, baseurl + '/search/alpha/' + char, 1, '', True)
    if forceViewMode:
        xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def INDEX(caturl):
    if (dbg):
        print(caturl)
    global itemcnt
    data = getUrl(caturl)
    for entry in re.findall('id="content"[^>]*>(.+?)<[^>]*id="paging"', data, re.S | re.I):
        if (dbg):
            print(entry)
        for rating, url, title, image in re.findall(
                '</cite>(.*?)<a[^>]*href="//filmpalast.to([^"]*)"[^>]*title="([^"]*)"[^>]*>[^<]*<img[^>]*src=["\']([^"\']*)["\'][^>]*>', entry, re.S | re.I):
            if 'http:' not in url:
                url = baseurl + url
            if 'http:' not in image:
                image = baseurl + image
            if showRating:
                stars = len(re.findall('star_on.png', rating, re.S | re.I))
                title = title + "  [COLOR=blue]"+str(stars)+"/10[/COLOR]"
            if showVotes:
                votes = re.findall(
                    '<sm.*?p;(.*?)&nbsp.*?ll>', rating, re.S | re.I)
                title = title + \
                    "  [COLOR=blue](" + str(votes[0]) + " votes)[/COLOR]"
            if preloadInfo:
                info = getInfos(getUrl(url))
                if preRating and info['imdb']:
                    title = title + " [COLOR=red]"+info['imdb'] + "/10[/COLOR]"
                if preGenres and info['genres']:
                    title = title + " [COLOR=green]"+info['genres']+"[/COLOR]"
            addLink(clean(title), url, 10, image)
            itemcnt = itemcnt + 1
    nextPage = re.findall('<a[^>]*class="[^"]*pageing[^"]*"[^>]*href=["\']([^"\']*)["\'][^>]*>[ ]*vorw', data, re.S | re.I)
    if nextPage:
        if (dbg):
            print(nextPage)
        if itemcnt >= maxitems:
            addDir('Weiter >>', nextPage[0], 1, '',  True)
        else:
            INDEX(nextPage[0])
    if forceViewMode:
        xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def SEARCH(url):
    keyboard = xbmc.Keyboard('', 'Suche')
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        search_string = urllib.parse.quote(keyboard.getText())
        INDEX(url + search_string)

def clean(s):
    matches = re.findall("&#\d+;", s)
    for hit in set(matches):
        try:
            s = s.replace(hit, chr(int(hit[2:-1])))
        except ValueError:
            pass
    return urllib.parse.unquote_plus(s)

def selectVideoDialog(videos, data):
    titles = []
    infostring = ""
    for name, src in videos:
        titles.append(name)
    if showMovieInfo:
        info = getInfos(data)
        infostring = "FP: {0}/10 Imdb: {1}/10 Jahr: {2}\nDauer: {3} Genre: {4}".format(info['fp'], info['imdb'], info['year'], info['runtime'], info['genres'])
    idx = xbmcgui.Dialog().select(infostring, titles)
    if idx > -1:
        return videos[idx][1]

def getInfos(data):
    info = {'fp': '0', 'imdb': '0', 'genres': '', 'actors': '', 'year': '', 'runtime': '', 'description': ''}
    match = re.search('>&ndash; Imdb: ([0-9,.]{0,3})/10', data, re.S | re.I)
    if match:
        info['imdb'] = match.group(1)
    match = re.search('average">([0-9,.]{0,3})<', data, re.S | re.I)
    if match:
        info['fp'] = match.group(1)
    match = re.search('>Ver&ouml;ffentlicht: ([^\n]*).*?>Spielzeit:.*?>(.*?)<', data, re.S | re.I)
    if match:
        info['year'] = match.group(1).replace('false', '')
        info['runtime'] = match.group(2)
    match = re.search('itemprop="description">(.*?)<', data, re.S | re.I)
    if match:
        info['description'] = match.group(1)
    for genre in re.findall('class="rb"[^>]*genre/(.*?)"', data, re.S | re.I | re.DOTALL):
        info['genres'] = info['genres'] + genre + " / "
    for actor in re.findall('class="rb".*?"/search/title/(.*?)"', data, re.S | re.I | re.DOTALL):
        info['actors'] = info['actors'] + actor + " / "
    info['actors'] = info['actors'].rstrip(' /')
    info['genres'] = info['genres'].rstrip(' /')
    return info

def resolveUrl(mediaUrl, validateOnly=False):
    try:
        try:
            import resolveurl as resolver
        except:
            import urlresolver as resolver
        if mediaUrl:
            if validateOnly:
                return resolver.HostedMediaFile(mediaUrl).valid_url()
            return resolver.resolve(mediaUrl)
    except resolver.resolver.ResolverError as e:
        print("Resolve error")
    return False

def PLAYVIDEO(url):
    global filterUnknownHoster
    print(url)
    data = getUrl(url)
    if not data:
        return
    videos = []
    for hoster, mediaUrl in re.findall(
            '<p class="hostName">(.*?)<.*?<li class="streamPlayBtn clearfix rb">.*?<a.*?class="button.*?(?:url|href)="(.*?)"', data, re.S | re.I | re.DOTALL):
        if filterUnknownHoster and resolveUrl(mediaUrl, True) == False:
            continue
        videos += [(hoster, mediaUrl)]
    lv = len(videos)
    if lv == 0:
        xbmc.executebuiltin(
            "XBMC.Notification(Fehler!, Video nicht gefunden, 4000)")
        return
    url = selectVideoDialog(videos, data) if lv > 1 else videos[0][1]
    if url:
        stream_url = resolveUrl(url)
        if stream_url:
            print(('open stream: ' + stream_url))
            listitem = xbmcgui.ListItem(path=stream_url)
            return xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
    raise Exception('Resolve URL aborted')

def getUrl(url):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', userAgent)
    req.add_header('Referer', url)
    response = urllib.request.urlopen(req, timeout=30)
    data = response.read().decode('utf-8')
    response.close()
    return data  # .decode('utf-8')

def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
        params = sys.argv[2]
        cleanedparams = params.replace('?', '')
        if (params[len(params)-1] == '/'):
            params = params[0:len(params)-2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param

def addLink(name, url, mode, image):
    u = sys.argv[0] + "?url=" + urllib.parse.quote_plus(url) + "&mode=" + str(mode)
    #liz = xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=image)
    liz = xbmcgui.ListItem(name)
    liz.setArt({'icon': 'DefaultVideo.png', 'thumb': image})
    liz.setInfo(type="Video", infoLabels={"Title": name})
    liz.setProperty('IsPlayable', 'true')
    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz)

def addDir(name, url, mode, image, is_folder=False):
    u = sys.argv[0] + "?url=" + urllib.parse.quote_plus(url) + "&mode=" + str(mode)
    liz = xbmcgui.ListItem(name)
    liz.setArt({'icon': 'DefaultFolder.png', 'thumb': image})
    # liz.setArtpath()
    #liz = xbmcgui.ListItem(name, icon="DefaultFolder.png", thumbnailImage=image)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=is_folder)

params = get_params()
url = None
mode = None

try:
    url = urllib.parse.unquote_plus(params["url"])
except:
    pass
try:
    mode = int(params["mode"])
except:
    pass

try:
    if mode == None or url == None or len(url) < 1:
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
    print(e)
    pass