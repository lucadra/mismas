import json
from pathlib import Path
from typing import List

import pandas as pd

from analysis import parse_frame_label_data

path = Path(
    '/home/luca/mismas/J6_BBC/download/[UXR_bqyAy4E]_Chaos in Washington as Trump supporters storm Capitol and force lockdown of Congress - BBC News.mp4')
# video_client = videointelligence.VideoIntelligenceServiceClient()
# video = VideoIntelligenceRequest(video_client, path)
# data = video.label_detection(mode='FRAME_MODE')
# pprint(data)
# json.dump(data, open('frame_mode.json', 'w'))
data = json.load(open('frame_mode.json'))
df = parse_frame_label_data(data)
df.to_csv('frame_mode.csv', index=False)


def get_highest_confidence_frame(df: pd.DataFrame, key: List['str']) -> pd.DataFrame:
    key = [k.lower().strip() for k in key]
    df['entity'] = df['entity'].apply(lambda x: x.lower().strip())
    df = df[df['entity'].isin(key)]
    entities = df.groupby('entity_id')
    df = entities.apply(lambda x: x[x['confidence'] == x['confidence'].max()])
    return df


data = get_highest_confidence_frame(df, ['Riot', 'Police'])
