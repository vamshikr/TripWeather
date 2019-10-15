# TripWeather

I lived in Colorado, Washington State and Wisconsin for over 10 years. I freakout driving in snowy conditions and have some bad experiences.

This command line program takes a _source location_, _destination location_ and _time_ and lists out weather conditions through out the trip.
The program uses *google maps* api and *dark sky* api to get directions and location information, and for weather forcast.

### Usage:
```
python3 -m trip_weather "Denver,CO" "Salt Lake City,UT" "$(date)"
```


### Install dependencies
```
pip install -r requirements.txt
```

### API Keys

* Create an API Key for `api.forecast.io` from https://darksky.net/dev

* Create an API Key for using Goecoding and Direction APIs from https://console.developers.google.com/

Export the API Keys as environment variables as shown below

```
export DARK_SKY_APIKEY=<your dark sky api key>
export GOOGLE_MAPS_APIKEY=<your google maps api key>
```

