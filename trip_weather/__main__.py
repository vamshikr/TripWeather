import argparse
import os

from .trip_weather import TripWeather

def parse_cli_args():
    parser = argparse.ArgumentParser(description='Weather Contions On Your Next Trip.')
    parser.add_argument('origin', type=str, help='Starting Location')
    parser.add_argument('destination', type=str, help='Destination')
    parser.add_argument('departure_time', type=str, help='Departure Time')
    parser.add_argument('--use-distance', action='store_true', default=False)
    parser.add_argument('--interval', type=int, required=False, default=10)
    parser.add_argument('--config', type=str, required=False, default='api_keys.conf')
    
    return parser.parse_args()


if __name__ == '__main__':
    cli_args = parse_cli_args()

    tw = TripWeather(os.environ['DARK_SKY_APIKEY'], os.environ['GOOGLE_MAPS_APIKEY'])

    count = 1
    for step in tw.get_report(cli_args.origin,
                              cli_args.destination,
                              cli_args.departure_time,
                              cli_args.use_distance,
                              cli_args.interval):
        print('%d) Location:%s, Time:%s, Summary:%s, Precipitation:%s%%, windSpeed:%s, windGust:%s, Temperature:%sF' % (
        count, step.location, step.time, step.summary, step.precipitation, step.wind_speed, step.wind_gust,
        step.temperature))
        count += 1

