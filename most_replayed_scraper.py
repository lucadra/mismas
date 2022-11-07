import json
import re
from datetime import timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup


def format_time(in_time):
    return str(timedelta(seconds=in_time / 1000))


def get_playback_heatmarkers(_id):
    r = requests.get(f'https://www.youtube.com/watch?v={_id}')
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
            for item in overlays:
                start_millis = item['heatMarkerRenderer']['timeRangeStartMillis']
                duration = item['heatMarkerRenderer']['markerDurationMillis']
                score = item['heatMarkerRenderer']['heatMarkerIntensityScoreNormalized']
                start = float(start_millis / 1000)
                end = float((start_millis + duration) / 1000)
                # normalised_start = (start/duration)/100
                # normalised_end = (end/duration)/100

                heatmarkers.append([start, end, score, _id])

            return pd.DataFrame(heatmarkers, columns=['start_sec', 'end_sec', 'score', 'id'])

            if not heatmarkers:
                print(f'The video "{b.title.text}" has no playback heatmarkers')
                break


# from download import download_video
# import time
#
# time0 = time.time()
# df = get_playback_heatmarkers('mAFv55o47ok')
# df = df[df['score'] > df['score'].quantile(0.75)].reset_index(drop=True)
# df = df.sort_values(by=['start'])
# vid_path = download_video('mAFv55o47ok', 'videos')


def reduce_df(_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce the dataframe merging consecutive shots to minimise the number of cuts to perform
    :param _df: Dataframe containing the shot list
    :return: Reduced dataframe with shot list
    """
    reduced = []
    start, end, _id = [None] * 3
    for i, row in _df.iterrows():
        _id = row['id']
        if i == 0:
            start = row['start_sec']
            end = row['end_sec']
        elif row['start_sec'] == end:
            end = row['end_sec']
        else:
            reduced.append([start, end, _id])
            start = row['start_sec']
            end = row['end_sec']

    reduced.append([start, end, _id])
    return pd.DataFrame(reduced, columns=['start_sec', 'end_sec', 'id'])
