import requests


class LoginError(Exception):
    pass


class DynSport:
    APIURL = "https://production-cdn.d3.dyn.sport/api/"
    VIDEO_APIURL = "https://feedpublisher-dynmedia.akamaized.net/divauni/DYN/fe/video/videodata/v2/"
    VIDEOAUTH_APIURL = "https://production-webfacing.d3.dyn.sport/api/dips/playback/tokenize"
    PAGE_TYPES = ["link", "competition", "team", "persona"]
    VIDEO_TYPES = ["event", "program"]

    def __init__(self, page_size=24):
        self.session = requests.Session()
        self.page_size = page_size
        self.subscribed = False

    def login(self, username, password):
        self.username = username
        self.password = password
        try:
            url = "https://api.dyn.sport/auth/web/token"
            r = self.session.post(url, json={'username': self.username, 'password': self.password})
            self.access_token = r.json()['access_token']
            self.refresh_token = r.json()['refresh_token']
            url = "https://production.d3.dyn.sport/api/authorization/exchange"
            r = self.session.post(url, json={'access_token': self.access_token, 'refresh_token': self.refresh_token,
                                             'cookieType': 'Session'})
            tokens = {x['type']: x['value'] for x in r.json()}
            self.useraccount_token = tokens['UserAccount']
            self.subscribed = True
        except KeyError:
            raise LoginError()

    def get_list(self, list_id, page=1, parameter=""):
        url = self.APIURL + f"lists/{list_id}"
        data = {
            'lang': 'de-DE',
            'ff': 'idp,ldp,rpt,sv2,dpl,cd,es',
            'page_size': self.page_size,
            'param': parameter,
            'page': page
        }
        if self.subscribed:
            data['sub'] = 'Subscriber'
        r = self.session.get(url, params=data)
        return r.json()

    def get_page(self, pagename=""):
        url = self.APIURL + f"page"
        data = {
            'path': pagename,
            'lang': 'de-DE',
            'ff': 'idp,ldp,rpt,sv2,dpl,cd,es',
            'max_list_prefetch': 10
        }
        if self.subscribed:
            data['sub'] = 'Subscriber'
        r = self.session.get(url, params=data)
        return r.json()

    def get_video(self, videoid, hls=False):
        url = f"{self.VIDEO_APIURL}{videoid}"
        r = self.session.get(url)
        sources = r.json()['sources']
        for source in sources:
            if not hls and source['format'] == "DASH":
                return source
            if hls and source['format'] == "HLS":
                return source
        return ""

    def get_video_auth(self, videoid, videodata):
        url = self.VIDEOAUTH_APIURL
        data = {"Type": 1,
                "VideoId": videoid,
                "VideoSource": videodata['uri'],
                "VideoKind": "replay", "AssetState": "3", "PlayerType": "HTML5", "VideoSourceFormat": "DASH",
                "VideoSourceName": videodata['name'], "DRMType": "widevine", "AuthType": "Token",
                "ContentKeyData": videodata['drm']['widevine']['contentKeyData'],
                "Other": "48d46ad7-ddf7-4c23-bd85-d3f4de6d0b92|web_browser"}
        if self.subscribed:
            data["User"] = self.useraccount_token
        r = self.session.post(url, json=data)
        try:
            authtoken = r.json()['AuthToken']
            if authtoken == "":
                raise LoginError()
            return authtoken
        except:
            raise LoginError()
