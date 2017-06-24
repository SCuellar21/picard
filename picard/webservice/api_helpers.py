import re
from PyQt5.QtCore import QUrl
from picard import config
from picard.const import (ACOUSTID_KEY,
                          ACOUSTID_HOST,
                          ACOUSTID_PORT)
from picard.webservice import PICARD_VERSION_STR


def escape_lucene_query(text):
    return re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\/])', r'\\\1', text)


def _wrap_xml_metadata(data):
    return ('<?xml version="1.0" encoding="UTF-8"?>' +
            '<metadata xmlns="http://musicbrainz.org/ns/mmd-2.0#">%s</metadata>' % data)


class APIHelper():

    def __init__(self, host, port, api_path, webservice):
        self.host = host
        self.port = port
        self.api_path = api_path
        self._webservice = webservice

    def get(self, path_list, handler, parse_format=True,
                priority=False, important=False, mblogin=False,
                cacheloadcontrol=None, refresh=False, queryargs=None):
        path = self.api_path + "/".join(path_list)
        return self._webservice.get(self.host, self.port, path, handler,
                 priority=priority, important=important, mblogin=mblogin,
                 refresh=refresh, queryargs=queryargs)

    def post(self, path_list, data, handler, priority=False, important=False,
                 mblogin=False, queryargs=None):
        path = self.api_path + "/".join(path_list)
        return self._webservice.post(self.host, self.port, path, data, handler,
                  priority=priority, important=important, mblogin=mblogin,
                  queryargs=queryargs)

    def put(self, path_list, data, handler, priority=True, important=False,
                mblogin=True, queryargs=None):
        path = self.api_path + "/".join(path_list)
        return self._webservice.put(self.host, self.port, path, data, handler,
                 priority=priority, important=important, mblogin=mblogin,
                 queryargs=queryargs)

    def delete(self, path_list, handler, priority=True, important=False,
                   mblogin=True, queryargs=None):
        path = self.api_path + "/".join(path_list)
        return self._webservice.put(self.host, self.port, path, handler,
                 priority=priority, important=important, mblogin=mblogin,
                 queryargs=queryargs)


class MBAPIHelper():

    def __init__(self, webservice):
        self.api_helper = APIHelper(config.setting['server_host'],config.setting['server_port'],
                                  "/ws/2/", webservice)

    def _get_by_id(self, entitytype, entityid, handler, inc=None, queryargs=None,
                   priority=False, important=False, mblogin=False, refresh=False):
        path_list = [entitytype, entityid]
        if queryargs is None:
            queryargs = {}
        if inc:
            queryargs["inc"] = "+".join(inc)
        return self.api_helper.get(path_list, handler,
                        priority=priority, important=important, mblogin=mblogin,
                        refresh=refresh, queryargs=queryargs)

    def get_release_by_id(self, releaseid, handler, inc=None,
                          priority=False, important=False, mblogin=False, refresh=False):
        if inc is None:
            inc = []
        return self._get_by_id('release', releaseid, handler, inc,
                               priority=priority, important=important, mblogin=mblogin, refresh=refresh)

    def get_track_by_id(self, trackid, handler, inc=None,
                        priority=False, important=False, mblogin=False, refresh=False):
        if inc is None:
            inc = []
        return self._get_by_id('recording', trackid, handler, inc,
                               priority=priority, important=important, mblogin=mblogin, refresh=refresh)

    def lookup_discid(self, discid, handler, priority=True, important=True, refresh=False):
        inc = ['artist-credits', 'labels']
        return self._get_by_id('discid', discid, handler, inc, queryargs={"cdstubs": "no"},
                               priority=priority, important=important, refresh=refresh)

    @staticmethod
    def _find(self, entitytype, handler, **kwargs):
        filters = []

        limit = kwargs.pop("limit")
        if limit:
            filters.append(("limit", limit))

        is_search = kwargs.pop("search", False)
        if is_search:
            if config.setting["use_adv_search_syntax"]:
                query = kwargs["query"]
            else:
                query = escape_lucene_query(kwargs["query"]).strip().lower()
                filters.append(("dismax", 'true'))
        else:
            query = []
            for name, value in kwargs.items():
                value = escape_lucene_query(value).strip().lower()
                if value:
                    query.append('%s:(%s)' % (name, value))
            query = ' '.join(query)

        if query:
            filters.append(("query", query))
        queryargs = {}
        for name, value in filters:
            value = QUrl.toPercentEncoding(string_(value))
            queryargs[string_(name)] = value
        path_list = [entitytype]
        return self.api_helper.get(path_list, handler, queryargs=queryargs,
                            priority=True, important=True, mblogin=False,
                            refresh=False)

    def find_releases(self, handler, **kwargs):
        return self._find('release', handler, **kwargs)

    def find_tracks(self, handler, **kwargs):
        return self._find('recording', handler, **kwargs)

    def find_artists(self, handler, **kwargs):
        return self._find('artist', handler, **kwargs)

    def _browse(self, entitytype, handler, inc=None, **kwargs):
        path_list = [entitytype]
        queryargs = kwargs
        if inc:
            queryargs["inc"] = "+".join(inc)
        return self.api_helper.get(path_list, handler, queryargs=queryargs,
                            priority=True, important=True, mblogin=False,
                            refresh=False)

    def browse_releases(self, handler, **kwargs):
        inc = ["media", "labels"]
        return self._browse("release", handler, inc, **kwargs)

    def submit_ratings(self, ratings, handler):
        path_list = ['rating']
        params = {"client": CLIENT_STRING}
        recordings = (''.join(['<recording id="%s"><user-rating>%s</user-rating></recording>' %
            (i[1], j*20) for i, j in ratings.items() if i[0] == 'recording']))

        data = _wrap_xml_metadata('<recording-list>%s</recording-list>' % recordings)
        return self.api_helper.post(path_list, data, handler, priority=True, queryargs=params)

    def get_collection(self, collection_id, handler, limit=100, offset=0):
        path_list = ["collection"]
        queryargs = None
        if collection_id is not None:
            inc = ["releases", "artist-credits", "media"]
            path_list.extend[collection_id, "releases"]
            queryargs = {}
            queryargs["inc"] = "+".join(inc)
            queryargs["limit"] = limit
            queryargs["offset"] = offset
        return self.api_helper.get(path_list, handler, priority=True, important=True,
                            mblogin=True, queryargs=queryargs)

    def get_collection_list(self, handler):
        return self.get_collection(None, handler)

    def _collection_request(self, collection_id, releases):
        while releases:
            ids = ";".join(releases if len(releases) <= 400 else releases[:400])
            releases = releases[400:]
            yield ["collection", collection_id, "releases", ids]

    def _get_client_queryarg(self):
        return {"client": CLIENT_STRING}

    def put_to_collection(self, collection_id, releases, handler):
        for path_list in self._collection_request(collection_id, releases):
            self.api_helper.put(path_list, "", handler,
                     queryargs=self._get_client_queryarg())

    def delete_from_collection(self, collection_id, releases, handler):
        for path_list in self._collection_request(collection_id, releases):
            self.delete(path_list, handler,
                        queryargs=self._get_client_queryarg())


class AcoustIdAPIHelper():

    def __init__(self, webservice):
        self.api_helper = APIHelper(ACOUSTID_HOST, ACOUSTID_PORT,
                                    '/v2/', webservice)

    def _encode_acoustid_args(self, args, format='xml'):
        filters = []
        args['client'] = ACOUSTID_KEY
        args['clientversion'] = PICARD_VERSION_STR
        args['format'] = format
        for name, value in args.items():
            value = string_(QUrl.toPercentEncoding(value))
            filters.append('%s=%s' % (string_(name), value))
        return '&'.join(filters)

    def query_acoustid(self, handler, **args):
        path_list = ['lookup']
        body = self._encode_acoustid_args(args)
        return self.api_helper.post(path_list, body, handler, priority=False, important=False, mblogin=False)

    def submit_acoustid_fingerprints(self, submissions, handler):
        path_list = ['submit']
        args = {'user': config.setting["acoustid_apikey"]}
        for i, submission in enumerate(submissions):
            args['fingerprint.%d' % i] = string_(submission.fingerprint)
            args['duration.%d' % i] = string_(submission.duration)
            args['mbid.%d' % i] = string_(submission.recordingid)
            if submission.puid:
                args['puid.%d' % i] = string_(submission.puid)
        body = self._encode_acoustid_args(args, format='json')
        return self.api_helper.post(path_list, body, handler, priority=True, important=False, mblogin=False)
