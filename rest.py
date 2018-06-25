import sys
import os
import json
import httplib
import pycurl
import cStringIO
import traceback


class McM:
    def __init__(self, id='sso', debug=False, cookie=None, dev=True, int=False):
        self.dev = dev
        if self.dev:
            self.server = 'cms-pdmv-dev.cern.ch/mcm/'
        elif int:
            self.server = 'cms-pdmv-int.cern.ch/mcm/'
        else:
            self.server = 'cms-pdmv.cern.ch/mcm/'

        self.headers = {}
        self.id = id
        self.debug = debug
        self.__connect(cookie)

    def __connect(self, cookie=None):
        if self.id == 'cert':
            self.http_client = httplib.HTTPSConnection(self.server,
                                                       cert_file=os.getenv('X509_USER_PROXY'),
                                                       key_file=os.getenv('X509_USER_PROXY'))

        elif self.id == 'sso':
            if cookie:
                self.cookie_filename = cookie
            else:
                if self.dev:
                    self.cookie_filename = '%s/private/dev-cookie.txt' % (os.getenv('HOME'))
                else:
                    self.cookie_filename = '%s/private/prod-cookie.txt' % (os.getenv('HOME'))

            if not os.path.isfile(self.cookie_filename):
                print('The required sso cookie file is absent. Trying to make one for you')
                os.system('cern-get-sso-cookie -u https://%s -o %s --krb' % (self.server,
                                                                             self.cookie_filename))

                if not os.path.isfile(self.cookie_filename):
                    print('Unfortunately sso cookie file cannot be made automatically. Quitting...')
                    sys.exit(1)
            else:
                print('Found a cookie file at %s. Make sure it\'s not expired!' % (self.cookie_filename))

            self.curl = pycurl.Curl()
            print('Using sso-cookie file %s' % (self.cookie_filename))
            self.curl.setopt(pycurl.COOKIEFILE, self.cookie_filename)
            self.output = cStringIO.StringIO()
            self.curl.setopt(pycurl.SSL_VERIFYPEER, 1)
            self.curl.setopt(pycurl.SSL_VERIFYHOST, 2)
            self.curl.setopt(pycurl.CAPATH, '/etc/pki/tls/certs')
            self.curl.setopt(pycurl.WRITEFUNCTION, self.output.write)
        else:
            self.http_client = httplib.HTTPConnection(self.server)

    # Generic methods for GET, PUT, DELETE HTTP methods
    def __get(self, url):
        fullurl = 'https://' + self.server + url
        if self.debug:
            print('GET |%s|' % (fullurl))

        if self.id == 'sso':
            self.curl.setopt(pycurl.URL, str(fullurl))
            self.curl.setopt(pycurl.HTTPGET, 1)
            self.curl.setopt(pycurl.CUSTOMREQUEST, 'GET')
            self.curl.perform()
        else:
            self.http_client.request("GET", url, headers=self.headers)

        try:
            res = json.loads(self.__response())
            return res
        except Exception as ex:
            print('Error while making a GET request to %s. Exception: %s' % (fullurl, ex))
            print(traceback.format_exc())
            return None

    def __put(self, url, data):
        fullurl = 'https://' + self.server + url
        post_data = json.dumps(data)
        if self.debug:
            print('POST |%s| DATA |%s|' % (fullurl, post_data))

        if self.id == 'sso':
            self.curl.setopt(pycurl.URL, str(fullurl))
            self.curl.setopt(pycurl.CUSTOMREQUEST, "PUT")
            self.curl.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
            self.curl.setopt(pycurl.POSTFIELDS, post_data)
            self.curl.perform()
        else:
            self.http_client.request("PUT", url, json.dumps(data), headers=self.headers)

        try:
            res = json.loads(self.__response())
            return res
        except Exception as ex:
            print('Error while making a PUT request to %s. Exception: %s' % (fullurl, ex))
            print(traceback.format_exc())
            return None

    def __delete(self, url):
        fullurl = 'https://' + self.server + url
        if self.debug:
            print('DELETE |%s|' % (fullurl))

        if self.id == 'sso':
            self.curl.setopt(pycurl.URL, str(fullurl))
            self.curl.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
            self.curl.perform()
        else:
            self.http_client.request("DELETE", url, headers=self.headers)

        try:
            res = json.loads(self.__response())
            return res
        except Exception as ex:
            print('Error while making a DELETE request to %s. Exception: %s' % (fullurl, ex))
            print(traceback.format_exc())
            return None

    # Generic methods for I/O
    def __clear(self):
        if self.id == 'sso':
            self.output = cStringIO.StringIO()
            self.curl.setopt(pycurl.WRITEFUNCTION, self.output.write)

    def __response(self):
        if self.id == 'sso':
            response = self.output.getvalue()
            self.__clear()
            return response
        else:
            return self.http_client.getresponse().read()

    # McM methods
    def get(self, object_type, object_id=None, query='', method='get', page=-1):
        """
        Get data from McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_id - usually prep id of desired object
        query - query to be run in order to receive an object, e.g. tags=M17p1A
        method - action to be performed, such as get, migrate or inspect
        page - which page to be fetched. -1 means no paginantion, return all results
        """
        if object_id:
            url = 'restapi/%s/%s/%s' % (object_type, method, object_id.strip())
        else:
            url = 'search/?db_name=%s&page=%d&%s' % (object_type, page, query)

        res = self.__get(url)
        if res:
            return res["results"]
        else:
            return None

    def update(self, object_type, object_data):
        """
        Update data in McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_data - new JSON of an object to be updated
        """
        return self.put(object_type, object_data, method='update')

    def put(self, object_type, object_data, method='save'):
        """
        Put data into McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_data - new JSON of an object to be updated
        method - action to be performed, default is 'save'
        """
        url = 'restapi/%s/%s' % (object_type, method)
        res = self.__put(url, object_data)
        return res

    def approve(self, object_type, object_id, level):
        url = 'restapi/%s/approve/%s/%d' % (object_type, object_id, level)
        return self.__get(url)

    def clone_request(self, object_data):
        return self.put('requests', object_data, method='clone')

    def get_range_of_requests(self, query):
        res = self.__put('restapi/requests/listwithfile', data={'contents': query})
        if res:
            return res["results"]
        else:
            return None

    def delete(self, object_type, object_id):
        url = 'restapi/%s/delete/%s' % (object_type, object_id)
        self.__delete(url)
