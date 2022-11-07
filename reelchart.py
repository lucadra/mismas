import subprocess
from pathlib import Path

import pandas as pd
import spacy
from tqdm import tqdm

from utils import find_video_by_id

project_dir = Path("/home/luca/mismas/BBC News")
data = pd.read_csv('/home/luca/mismas/BBC News/data/transcription/merged.csv')

en = spacy.load('en_core_web_sm')
stopwords = en.Defaults.stop_words


def extract_reelchart_frames(data: pd.DataFrame, project_dir: Path, segments=20):
    clip_data_groups = data.groupby('id')
    in_dir = project_dir / 'download'
    out_dir = project_dir / 'reelchart_images'
    out_dir.mkdir(exist_ok=True)
    for id in data['id'].unique():
        clip_data = clip_data_groups.get_group(id)
        clip_duration = clip_data.iloc[-1]['end_sec'] - clip_data.iloc[0]['start_sec']
        segment_duration = clip_duration / segments
        timestamps = [segment_duration * i for i in range(segments)]
        video = find_video_by_id(id, in_dir)
        for i, timestamp in enumerate(timestamps):
            # out_path = out_dir / f"{id}_{i}.jpg"
            # command = ["ffmpeg", "-ss", str(timestamp),"-i", video, "-vframes", "1", "-y", out_path]
            # subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # extract gif from video from timestamp to timestamp + segment_duration
            out_path = out_dir / f"{id}_{i}.gif"
            command = ["ffmpeg", "-ss", str(timestamp), "-t", str(segment_duration), "-i", video, "-vf",
                       "fps=12,scale=320:-1:flags=lanczos", "-y", out_path]
            subprocess.run(command)


def make_reelchart_table(data: pd.DataFrame, project_dir: Path, segments=20):
    # check if 'joe' and 'biden' are in the word column, if they are, print a message
    if 'joe' in data['word'].unique() and 'biden' in data['word'].unique():
        print("Joe Biden is in the data in line 34")

    clip_data_groups = data.groupby('id')
    in_dir = project_dir / 'download'
    out_dir = project_dir / 'data'
    data = data.assign(word=data['word'].str.lower())
    if 'joe' in data['word'].unique() and 'biden' in data['word'].unique():
        print("Joe Biden is in the data in line 41")

    tqdm.pandas()
    # lemmatize the words, keep proper nouns
    data['word'] = data['word'].progress_apply(lambda x: en(x)[0].lemma_ if en(x)[0].pos_ != 'PROPN' else x)
    if 'joe' in data['word'].unique() and 'biden' in data['word'].unique():
        print("Joe Biden is in the data in line 47")
    data = data.query('word not in @stopwords')
    if 'joe' in data['word'].unique() and 'biden' in data['word'].unique():
        print("Joe Biden is in the data in line 50")
    data = data.assign(word=data['word'].str.lower())
    if 'joe' in data['word'].unique() and 'biden' in data['word'].unique():
        print("Joe Biden is in the data in line 53")
    pbar = tqdm(total=len(data['id'].unique()), desc="Building reelchart table", unit="clip")
    data_out = []
    for id in data['id'].unique():

        clip_data = clip_data_groups.get_group(id)
        clip_duration = clip_data.iloc[-1]['end_sec'] - clip_data.iloc[0]['start_sec']
        segment_duration = clip_duration / segments
        timestamps = [segment_duration * i for i in range(segments)]

        for i, timestamp in enumerate(timestamps):
            segment_data = clip_data[
                (clip_data['start_sec'] >= timestamp) & (clip_data['end_sec'] <= timestamp + segment_duration)]
            words_all = data['word'].unique()
            for word in words_all:
                count = segment_data[segment_data['word'] == word].shape[0]
                datum = {'id': id, 'segment': i, 'word': word, 'count': count}
                data_out.append(datum)
        pbar.update(1)

    return pd.DataFrame(data_out)


def make_reelchart_table_with_reference(data: pd.DataFrame, project_dir: Path, segments=20):
    # check if 'joe' and 'biden' are in the word column, if they are, print a message

    clip_data_groups = data.groupby('id')
    in_dir = project_dir / 'download'
    out_dir = project_dir / 'data'
    tqdm.pandas()
    # lemmatize the words, keep proper nouns
    data['word'] = data['word'].progress_apply(lambda x: en(x)[0].lemma_ if en(x)[0].pos_ != 'PROPN' else x)

    data = data.query('word not in @stopwords')
    data = data.assign(word=data['word'].str.lower())
    pbar = tqdm(total=len(data['id'].unique()), desc="Building reelchart table", unit="clip")
    data_out = []
    for id in data['id'].unique():

        clip_data = clip_data_groups.get_group(id)
        clip_duration = clip_data.iloc[-1]['end_sec'] - clip_data.iloc[0]['start_sec']
        segment_duration = clip_duration / segments
        timestamps = [segment_duration * i for i in range(segments)]

        for i, timestamp in enumerate(timestamps):
            segment_data = clip_data[
                (clip_data['start_sec'] >= timestamp) & (clip_data['end_sec'] <= timestamp + segment_duration)]
            words_all = data['word'].unique()
            for word in words_all:
                count = segment_data[segment_data['word'] == word].shape[0]
                datum = {'id': id, 'segment': i, 'word': word, 'count': count}
                data_out.append(datum)
        pbar.update(1)

    return pd.DataFrame(data_out)


# pomergigio = make_reelchart_table(data, project_dir)
# pomergigio.to_csv('/home/luca/mismas/BBC News/data/reelchart_table.csv', index=False)
# pomergiorgio = pomergigio[pomergigio['count'] > 0]
# pomergiorgio.to_csv('/home/luca/mismas/BBC News/data/reelchart_table_nonzero.csv', index=False)
extract_reelchart_frames(data, project_dir)
