import sys
from geopy.distance import vincenty
from polyline.codec import PolylineCodec
import urllib.parse
import http.client
import json
import time
from configparser import ConfigParser

import logging

from collections import namedtuple

import pdb


Forcast = namedtuple('Forcast', ['location', 'time', 'summary', 'precipitation', 'wind_speed', 'wind_gust', 'temperature'])


class DarkSkyForcast:

    HOST_NAME = 'api.forecast.io'
    _HTTPS_PORT = 443

    def __init__(self, api_key):
        self.conn = http.client.HTTPSConnection(DarkSkyForcast.HOST_NAME,
                                                DarkSkyForcast._HTTPS_PORT)
        #self.conn.set_debuglevel(2)
        self.api_key = api_key

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        if value is None:
            self.conn.close()

    def get_forecast(self, lat, lng, _time):

        try:
            headers = {
                #'Accept' : '*/*',
                #'Accept-Encoding' : '*'
            }
            self.conn.request('GET',
                              '/forecast/{0}/{1},{2},{3}'.format(self.api_key,
                                                                 lat, lng, _time),
                              headers=headers)

            response = self.conn.getresponse()

            if response.status == 200 and response.reason == 'OK':

                resp_json = json.loads(response.read().decode('UTF-8'))
                return resp_json

        except http.client.NotConnected as err:
            logging.exception(err)
            return None


class GoogleMaps:

    HOST_NAME = 'maps.googleapis.com'
    _HTTPS_PORT = 443

    _MAX_DIST = 1600 #1600 METERS, 1 MILE
    _MAX_TIME = 120 #2 mins

    _HEADERS = {
        'Accept' : '*/*',
        'Accept-Encoding' : '*'
    }

    def __init__(self, api_key):
        self.conn = http.client.HTTPSConnection(GoogleMaps.HOST_NAME,
                                                GoogleMaps._HTTPS_PORT)
        #self.conn.set_debuglevel(2)
        self.api_key = api_key

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        if value is None:
            self.conn.close()

    def get_directions(self, origin, destination, departure_time='now'):
        '''Input: origin: (lat, lon)
        destination: (lat, lon)
        departure_time: default is now'''

        try:
            request = {
                'origin': ','.join(str(f) for f in origin),
                'destination': ','.join(str(f) for f in destination),
                'departure_time': departure_time,
                'key': self.api_key,
            }
            self.conn.request('GET',
                              '/maps/api/directions/json?{0}'.format(urllib.parse.urlencode(request)),
                              headers=GoogleMaps._HEADERS)

            response = self.conn.getresponse()

            if response.status == 200 and response.reason == 'OK':
                resp_json = json.loads(response.read().decode('UTF-8'))
                return resp_json

        except http.client.NotConnected as err:
            logging.exception(err)
            return None

    def geocode(self, address):
        '''Input: address in text
        Output: (lat, lon)'''

        try:
            request = {
                'address' : address,
                'key' : self.api_key,
            }
            self.conn.request('GET',
                              '/maps/api/geocode/json?{0}'.format(urllib.parse.urlencode(request)),
                              headers=GoogleMaps._HEADERS)

            response = self.conn.getresponse()

            if response.status == 200 and response.reason == 'OK':
                resp_json = json.loads(response.read().decode('UTF-8'))

                return (resp_json['results'][0]['geometry']['location']['lat'],
                        resp_json['results'][0]['geometry']['location']['lng'])

        except http.client.NotConnected as err:
            logging.exception(err)
            return None

    def reverse(self, lat, lng):
        '''Input: address in text
        Output: (lat, lon)'''

        try:
            request = {
                'latlng' : '{0},{1}'.format(lat, lng),
                'key' : self.api_key,
            }
            self.conn.request('GET',
                              '/maps/api/geocode/json?{0}'.format(urllib.parse.urlencode(request)),
                              headers=GoogleMaps._HEADERS)

            response = self.conn.getresponse()

            if response.status == 200 and response.reason == 'OK':
                resp_json = json.loads(response.read().decode('UTF-8'))

                return resp_json['results'][0]['formatted_address']

        except http.client.NotConnected as err:
            logging.exception(err)
            return None

    @classmethod
    def _get_mini_steps(cls, polyline,
                        start_location, end_location,
                        total_distance,
                        total_time):

        mini_steps = []

        if PolylineCodec().decode(polyline):
            avg_speed = total_distance/total_time
            curr_loc = start_location

            for next_loc in PolylineCodec().decode(polyline):
                distance = vincenty(curr_loc, next_loc).meters
                mini_steps.append((next_loc[0], next_loc[1], distance, distance/avg_speed))
                curr_loc = next_loc

            distance = vincenty(curr_loc, end_location).meters
            mini_steps.append((end_location[0], end_location[1],
                               distance, distance/avg_speed))
        else:
            mini_steps.append((end_location[0], end_location[1],
                               total_distance, total_time))

        return mini_steps

    @classmethod
    def get_steps(cls, directions):
        '''time_step in seconds: default 10mins, 600sec'''

        leg0 = directions['routes'][0]['legs'][0]

        steps = []
        start_location = (leg0['start_location']['lat'], leg0['start_location']['lng'], 0, 0)
        steps.append(start_location)

        for step in leg0['steps']:

            step_dist = step['distance']['value']
            step_time = step['duration']['value']

            if ('polyline' in step) and \
               ((step_dist > GoogleMaps._MAX_DIST) or (step_time > GoogleMaps._MAX_TIME)):
                sloc = (step['start_location']['lat'], step['start_location']['lng'])
                eloc = (step['end_location']['lat'], step['end_location']['lng'])

                mini_steps = GoogleMaps._get_mini_steps(step['polyline']['points'],
                                                        sloc, eloc,
                                                        step_dist, step_time)
                steps.extend(mini_steps)
            else:
                steps.append((step['end_location']['lat'],
                              step['end_location']['lng'],
                              step_dist,
                              step_time))
        return steps

    @classmethod
    def steps_ata_time(cls, all_steps, departure_time, interval=10):
        '''interval is time in seconds'''

        interval = 60 * interval

        nsteps = [(all_steps[0][0], all_steps[0][1], all_steps[0][2], departure_time)]

        curr_time = 0
        next_time = interval
        curr_dist = 0

        for step in all_steps[1:]:
            _dist = step[2]
            _time = step[3]

            if (curr_time + _time) < next_time:
                curr_time += _time
                curr_dist += _dist
            else:
                curr_time += _time
                curr_dist += _dist
                next_time = curr_time + interval
                nsteps.append((step[0], step[1], int(curr_dist),
                               int(curr_time) + departure_time))

        if (nsteps[-1][0] != all_steps[-1][0]) and (nsteps[-1][1] != all_steps[-1][1]):
            nsteps.append((all_steps[-1][0], all_steps[-1][1],
                           int(curr_dist + all_steps[-1][2]),
                           int(curr_time + all_steps[-1][3]) + departure_time))
        return nsteps

    @classmethod
    def steps_ata_distance(cls, all_steps, departure_time, interval):
        '''Interval is distance in meters'''

        interval = 1600 * interval

        nsteps = [(all_steps[0][0], all_steps[0][1], all_steps[0][2], departure_time)]

        curr_time = 0
        curr_dist = 0
        next_dist = interval

        for step in all_steps[1:]:
            _dist = step[2]
            _time = step[3]

            if (curr_dist + _dist) < next_dist:
                curr_time += _time
                curr_dist += _dist
            else:
                curr_time += _time
                curr_dist += _dist
                next_dist = curr_dist + interval
                nsteps.append((step[0], step[1],
                               int(curr_dist), int(curr_time)))

        if (nsteps[-1][0] != all_steps[-1][0]) and (nsteps[-1][1] != all_steps[-1][1]):
            nsteps.append((all_steps[-1][0], all_steps[-1][1],
                           int(curr_dist + all_steps[-1][2]),
                           int(curr_time + all_steps[-1][3]) + departure_time))
        return nsteps

def localtime(seconds, offset):

    #This method is quiet a hack; but I like it
    if time.daylight:
        timezone = {-4 : 'EDT', -5 : 'CDT', -6 : 'MDT', -7 : 'PDT'}
    else:
        timezone = {-5 : 'EST', -6 : 'CST', -7 : 'MST', -8 : 'PST'}

    if offset not in timezone.keys():
        raise NotImplemented

    stime = time.gmtime(seconds + offset * 3600)
    return time.strftime('%a %b %d %H:%M:%S {0} %Y'.format(timezone[offset]), stime)


class LocationNotFoundError(Exception):

    def __init__(self, loc):
        self.loc = loc
        Exception.__init__(self)

    def __str__(self):
        return "Error: location '{0}' could not be verified".format(self.loc)


class TripWeather:

    def __init__(self, dark_sky_apikey, google_maps_apikey):
        self.dark_sky_apikey = dark_sky_apikey
        self.google_maps_apikey = google_maps_apikey

    def get_report(self, start_location, end_location, start_time, use_distance, interval):
        
        gv3 = GoogleMaps(self.google_maps_apikey)

        gm_star_loc = gv3.geocode(start_location)

        if gm_star_loc is None:
            raise LocationNotFoundError(start_location)

        gm_end_loc = gv3.geocode(end_location)

        if gm_end_loc is None:
            raise LocationNotFoundError(end_location)

        if start_time == 'now':
            start_time = int(time.time())
        else:
            try:
                time_format = r'%m/%d/%Y %H:%M %p'
                start_time = int(time.mktime(time.strptime(start_time,
                                                           time_format)))
            except ValueError:
                time_format = '%a %b %d %H:%M:%S %Z %Y'
                start_time = int(time.mktime(time.strptime(start_time,
                                                           time_format)))
 
        time.sleep(1)
        directions = gv3.get_directions(gm_star_loc, gm_end_loc, start_time)
        all_steps = GoogleMaps.get_steps(directions)

        if use_distance:
            steps = GoogleMaps.steps_ata_distance(all_steps, start_time, interval)
        else:
            steps = GoogleMaps.steps_ata_time(all_steps, start_time, interval)

        with DarkSkyForcast(self.dark_sky_apikey) as dsf:
            count = 1
            for step in steps:
                forecast = dsf.get_forecast(step[0], step[1], step[3])
                if forecast:
                    summary = forecast['currently'].get('summary', 'Not Available')

                    if 'precipProbability' in forecast['currently']:
                        precip_probability = '%.0f' % (forecast['currently']['precipProbability'] * 100)
                    else:
                        precip_probability = 'Not Available'
                    temperature = str(forecast['currently'].get('temperature', 'Not Available'))
                    wind_speed =  str(forecast['currently'].get('windSpeed', 'Not Available'))
                    wind_gust =  str(forecast['currently'].get('windGust', 'Not Available'))

                yield Forcast(gv3.reverse(step[0], step[1]),
                              localtime(step[3], forecast['offset']),
                              summary,
                              precip_probability,
                              wind_speed,
                              wind_gust,
                              temperature)
                count += 1

                if count % 2 == 1:
                    time.sleep(1)
