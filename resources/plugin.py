# -*- coding: utf-8 -*-

import logging
import sys
from urllib.parse import urlencode

import routing
import xbmc
import xbmcaddon
from inputstreamhelper import Helper
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory, setResolvedUrl
from datetime import datetime
from zoneinfo import ZoneInfo
import json

from .dynsport import DynSport, LoginError

KODI_VERSION_MAJOR = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
ADDON = xbmcaddon.Addon()
logger = logging.getLogger(ADDON.getAddonInfo('id'))
plugin = routing.Plugin()

_url = sys.argv[0]
_handle = int(sys.argv[1])

dynsport = DynSport()

username = ADDON.getSetting("username")
password = ADDON.getSetting("password")

if username != "" and password != "":
    try:
        dynsport.login(username, password)
    except LoginError:
        xbmc.executebuiltin("Notification(Dyn Sport, Login failed!)")

@plugin.route('/')
def index():
    show_page("/")


@plugin.route('/api/page/<path:pagename>')
def show_page(pagename):
    page = dynsport.get_page(pagename)
    for entry in page['entries']:
        if entry['type'] in ["ListEntry"]:
            if "parameter" in entry['list'].keys():
                parameter = entry['list']['parameter']
            else:
                parameter = ""
            link = plugin.url_for(show_list, list_id=int(entry['list']['id']), page=1, parameter=parameter)
            if "title" in entry.keys() and entry['title'] != "":
                title = entry['title']
            elif "list" in entry.keys() and "title" in entry['list'].keys():
                title = entry['list']['title']
            else:
                title = f"List {entry['list']['id']}"
            is_directory = True
            ListItem(title + "test")
            addDirectoryItem(_handle, link, ListItem(title), is_directory)
        elif entry['type'] in ["ItemEntry"]:
            videolink(entry['item'])
    endOfDirectory(_handle)


@plugin.route('/api/list/<list_id>/<page>')
def show_list_simple(list_id, page=1):
    show_list(list_id, page, "")


@plugin.route('/api/list/<int:list_id>/<int:page>/<str:parameter>')
def show_list(list_id, page=1, parameter=""):
    try:
        page = int(page)
        list = dynsport.get_list(list_id, page, parameter)

        if "paging" in list.keys() and "total" in list["paging"].keys():
            pages_total = list["paging"]["total"]
        else:
            pages_total = 1

        for entry in list['items']:
            if entry['type'] in DynSport.PAGE_TYPES:
                link = plugin.url_for(show_page, entry['path'])
                title = entry['title']
                is_directory = True
                listitem = ListItem(title)
                listitem.setArt(get_images(entry['images']))
                addDirectoryItem(_handle, link, listitem, is_directory)
            elif entry['type'] in DynSport.VIDEO_TYPES:
                videolink(entry)

        if page < pages_total:
            addDirectoryItem(_handle, plugin.url_for(show_list, list_id, page + 1, parameter),
                             ListItem(">>> Nächste Seite"), True)

        endOfDirectory(_handle)
    except Exception as e:
        xbmc.executebuiltin(f"Notification(Dyn Sport Fehler, {str(e)})")
        raise e


def videolink(item):
    metadata = {x['name']: x['value'] for x in item['customMetadata']}
    videoid = metadata['VideoId']
    videostatus = metadata['VideoStatus']
    link = plugin.url_for(play, videoid)
    title = item['title']
    if videostatus == "Scheduled":
       titletext = f"{title} [Scheduled]"
        #except:
       #     titletext = f"{title} [Scheduled]"
    elif videostatus == "Live":
        titletext = f"{title} [B][LIVE][/B]"
    else:
        titletext = title
    listitem = ListItem(titletext)
    if 'ContentDate' in metadata.keys():
        listitem.setDateTime(metadata['ContentDate'])
    if 'duration' in item.keys():
        listitem.addStreamInfo('video', {'duration': item['duration']})
    listitem.setProperty('IsPlayable', 'true')
    listitem.setArt(get_images(item['images']))
    addDirectoryItem(_handle, link, listitem, False)


def get_images(images):
    images0 = {}
    if "wallpaper" in images.keys():
        images0['fanart'] = images['wallpaper']
    if "square" in images.keys():
        images0['thumb'] = images['square']
        images0['icon'] = images['square']
    return images0


@plugin.route('/play/<videoid>')
def play(videoid):
    global _handle
    protocol = "mpd"
    license_type = 'com.widevine.alpha'

    is_helper = Helper(protocol, drm=license_type)

    videodata = dynsport.get_video(videoid)
    lic_url = videodata['drm']['widevine']['licenseUrl']

    play_item = ListItem(path=videodata['uri'])

    if KODI_VERSION_MAJOR >= 19:
        play_item.setProperty('inputstream', is_helper.inputstream_addon)
    else:
        play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
    #play_item.setProperty('inputstream', 'inputstream.adaptive')
    play_item.setProperty('inputstream.adaptive.manifest_type', protocol)
    play_item.setProperty('inputstream.adaptive.license_type', license_type)

    try:
        video_auth = dynsport.get_video_auth(videoid, videodata)

        license_headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0',
            'Content-Type': 'application/octet-stream',
            'Origin': 'https://www.dyn.sport',
            'x-dt-auth-token': video_auth,
            'Host': 'lic.drmtoday.com'
        }

        license_config = {
            'license_server_url': lic_url.replace("specConform=true", ""),
            'headers': urlencode(license_headers),
            'post_data': 'R{SSM}',
            'response_data': 'JBlicense'
        }
        play_item.setProperty('inputstream.adaptive.license_key', '|'.join(license_config.values()))

        setResolvedUrl(_handle, True, listitem=play_item)
    except LoginError:
        xbmc.executebuiltin("Notification(Dyn Sport, Not logged in!)")

def run():
    plugin.run()
