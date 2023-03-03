import json
import re
from datetime import timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup


def format_time(in_time):
    return str(timedelta(seconds=in_time / 1000))


def get_playback_heatmarkers(video_index):
    r = requests.get(f'https://www.youtube.com/watch?v={video_index}')
    b = BeautifulSoup(r.text, 'html.parser')

    for script in b.find_all('script'):
        if script.text.startswith('var ytInitialData'):
            response_json = re.sub(r'^.*?{', '{', script.text).replace(';', '')
            response_dict = json.loads(response_json)

            try:
                overlays = response_dict['playerOverlays']['playerOverlayRenderer']['decoratedPlayerBarRenderer'][
                    'decoratedPlayerBarRenderer']['playerBar']['multiMarkersPlayerBarRenderer']['markersMap'][0][
                    'value']['heatmap']['heatmapRenderer']['heatMarkers']
            except KeyError:
                print(f'The video "{b.title.text}" has no playback heatmarkers')
                break

            heatmarkers = []
            for i,item in enumerate(overlays):
                start_millis = item['heatMarkerRenderer']['timeRangeStartMillis']
                duration = item['heatMarkerRenderer']['markerDurationMillis']
                score = item['heatMarkerRenderer']['heatMarkerIntensityScoreNormalized']
                start = float(start_millis / 1000)
                end = float((start_millis + duration) / 1000)

                heatmarkers.append([video_index, i, start, end, score])

            return pd.DataFrame(heatmarkers, columns=['id', 'segment', 'start_sec', 'end_sec', 'score'])
