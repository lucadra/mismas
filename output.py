import os
import subprocess
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from tqdm import tqdm

from metavideo import get_metagrid
from object_tracking_supercut import interpolate_missing_data, extract_object_thumbs, extract_masked_object_clips, \
    merge_with_chromakey, extract_obj_gifs
from utils import uniquify, ensure_dir, ensure_coords, find_video_by_id


def select_shots_by_entity(annotation_data: pd.DataFrame,
                           key: List[str], threshold=0.5,
                           search_categories=False,
                           padding_before=0,
                           padding_after=0):
    """
    Select shots by key entity
    :param annotation_data: dataframe with annotation data
    :param key: key entity to filter by
    :param threshold: minimum confidence score to consider
    :param search_categories: search in categories as well
    :param padding_before: amount of seconds to subtract from start time
    :param padding_after: amount of seconds to add to end time
    :return: dataframe with selected shots
    """
    if type(key) == str:
        key = [key]

    if search_categories and 'category' not in annotation_data.columns:
        raise KeyError("The dataframe has no 'category' column")
    if 'entity' not in annotation_data.columns:
        raise KeyError("The dataframe has no 'entity' column")
    elif all(k not in annotation_data['entity'].unique() for k in key):
        raise ValueError(f"Key entity {key} not found in dataframe")

    entity_shots = annotation_data[annotation_data['entity'].str.lower().isin(key)].reset_index(drop=True)

    if search_categories:
        category_shots = annotation_data[annotation_data['category'].str.lower().isin(key)].reset_index(drop=True)
        selected_shots = pd.concat([entity_shots, category_shots]).drop_duplicates(keep='first')
    else:
        selected_shots = entity_shots

    selected_shots = selected_shots[selected_shots['confidence'] >= threshold].reset_index(drop=True)

    if padding_before:
        selected_shots['start_sec'] -= padding_before
        selected_shots['start_sec'] = selected_shots['start_sec'].apply(lambda x: max(x, 0))

    if padding_after:
        end_time = entity_shots['end_sec'].max()
        selected_shots['end_sec'] += padding_after
        selected_shots['end_sec'] = selected_shots['end_sec'].apply(lambda x: max(x, end_time))

    return selected_shots


def select_shots_by_keyword(annotation_data: pd.DataFrame,
                            key: List[str],
                            threshold=0.5,
                            padding_before=5,
                            padding_after=3):
    key = [key.lower()] if type(key) == str else [k.lower() for k in key]
    if 'word' not in annotation_data.columns:
        raise KeyError("The dataframe has no 'word' column")
    elif all(k not in annotation_data['word'].unique() for k in key):
        raise ValueError(f"Keyword {key} not found in dataframe")

    selected_shots = annotation_data[annotation_data['word'].str.lower().str.replace(r'[^\w\s]+', '').isin(key)]

    selected_shots = selected_shots[selected_shots['confidence'] >= threshold]

    selected_shots = add_padding_shots(annotation_data, padding_after, padding_before, selected_shots)

    selected_shots = selected_shots.drop_duplicates(keep='first')
    selected_shots = selected_shots.sort_index()
    selected_shots = selected_shots.reset_index(drop=True)

    starts = selected_shots['start_sec'].tolist()
    ends = selected_shots['end_sec'].tolist()

    selected_shots = merge_consecutive(selected_shots)

    return selected_shots


## Select shots by consecutive words

def select_shots_by_consecutive_words(annotation_data: pd.DataFrame,
                                      key: List[str]):
    key = [k.lower().strip() for k in key] if isinstance(key, list) else [k.lower().strip() for k in key.split(',')]
    # turn all strings in the 'word' column of the database to lowercase and remove punctuation and spaces
    annotation_data['word'] = annotation_data['word'].str.lower().str.replace(r'[^\w\s]+', '').str.strip()
    selected_shots = pd.DataFrame()
    # get the indexs of rows where the value of the word column matches the key
    indexes = annotation_data[annotation_data['word'].isin(key)].index.values

    # for each index in indexes, get the following n indexes, where n is the length of the key
    for i in indexes:
        following_indexes = [i + j for j in range(len(key))]
        # check that the 'word' column of the first row in the following_indexes list matches the first word in the key
        # that the second row in the following_indexes list matches the second word in the key, etc.
        if all(annotation_data.iloc[m]['word'] == key[n] for n, m in enumerate(following_indexes)):
            # if all the words in the key match the words in the following_indexes list, append a new row to the
            # selected_shots dataframe with the start and end times of the first and last rows in the following_indexes
            # list, and the words in the key
            selected_shots = selected_shots.append({
                'id': annotation_data.iloc[following_indexes[0]]['id'],
                'word': ' '.join(key),
                'start_sec': annotation_data.iloc[following_indexes[0]]['start_sec'],
                'end_sec': annotation_data.iloc[following_indexes[-1]]['end_sec'],
                'id0': following_indexes[0],
                'id1': following_indexes[-1]
            }, ignore_index=True)

            # selected_shots = selected_shots.append(annotation_data.iloc[following_indexes])

    # remove duplicates and sort by index
    selected_shots = selected_shots.drop_duplicates(keep='first')
    selected_shots = selected_shots.sort_index()
    return selected_shots


def merge_consecutive(selected_shots):
    prev_len = len(selected_shots)
    while True:
        for i, row in selected_shots.iterrows():
            if i < len(selected_shots) - 1:
                current_end = float(row['end_sec'])
                next_start = float(selected_shots.iloc[i + 1]['start_sec'])
                if 0 <= next_start - current_end <= 2:
                    selected_shots.loc[i, "end_sec"] = selected_shots.iloc[i + 1]["end_sec"]
                    selected_shots.loc[i, "word"] = selected_shots.iloc[i]["word"] + " " + selected_shots.iloc[i + 1][
                        "word"]
                    selected_shots = selected_shots.drop(i + 1)
                    selected_shots = selected_shots.reset_index(drop=True)
        current_len = len(selected_shots)
        print("current_len: ", current_len, end="\r")
        if current_len < prev_len:
            prev_len = current_len
        else:
            break
    return selected_shots


def add_padding_shots(annotation_data, padding_after, padding_before, selected_shots):
    for n, shot in selected_shots.iterrows():
        if n == 0:
            continue
        for i in range(1, padding_before + 1):
            if n - i < 0:
                break
            current_start = int(shot['start_sec'])
            previous_end = int(annotation_data.iloc[n - i]['end_sec'])
            if current_start - previous_end <= 2:
                selected_shots = selected_shots.append(annotation_data.iloc[n - i])
            else:
                break
        for i in range(1, padding_after + 1):
            if n + i > len(annotation_data):
                break
            current_end = int(shot['end_sec'])
            next_start = int(annotation_data.iloc[n + i]['start_sec'])
            diff = next_start - current_end
            if next_start - current_end <= 2:
                selected_shots = selected_shots.append(annotation_data.iloc[n + i])
            else:
                break
    return selected_shots


def add_padding_to_consecutive_keywords(annotation_data, padding_after, padding_before, selected_shots):
    for n, shot in selected_shots.iterrows():
        if n == 0:
            continue
        for i in range(1, padding_before + 1):
            if n - i < 0:
                break
            current_start = int(shot['start_sec'])
            previous_end = int(annotation_data.iloc[shot['id0'] - i]['end_sec'])
            if current_start - previous_end <= 2:
                selected_shots = selected_shots.append(annotation_data.iloc[shot['id0'] - i])
            else:
                break
        for i in range(1, padding_after + 1):
            if n + i > len(annotation_data):
                break
            current_end = int(shot['end_sec'])
            next_start = int(annotation_data.iloc[shot['id1'] + i]['start_sec'])
            diff = next_start - current_end
            if next_start - current_end <= 2:
                selected_shots = selected_shots.append(annotation_data.iloc[shot['id1'] + i])
            else:
                break
        print(selected_shots)
    return selected_shots

def extract_shots(_df: pd.DataFrame, in_dir: Path, out_dir: Path, text: str = False):
    """
    :param text:
    :param out_dir:
    :param in_dir:
    :param _df: DataFrame with data on which shots to extract
    :return: None
    """
    df = _df.sort_values(by=['id', 'start_sec'])
    out_dir.mkdir(parents=True, exist_ok=True)

    for index, row in tqdm(df.iterrows(), total=df.shape[0], desc='Extracting shots'):
        entity = row[text] if text else row[0]
        video_id = row['id']
        filename = Path(in_dir, find_video_by_id(row['id'], in_dir))
        start = "%.2f" % row['start_sec']
        end = "%.2f" % row['end_sec']
        if start == end:
            continue
        in_path = filename.resolve().as_posix()
        out_path = uniquify(os.path.join(out_dir.as_posix(), f"{video_id}.mp4"))
        command = ["ffmpeg"]
        options = ["-i", in_path, "-ss", start, "-to", end, "-y", "-movflags",
                   "faststart", "-avoid_negative_ts", "1", "-acodec", "copy", out_path]

        if text:
            text_filter = ["drawtext=", "fontfile=Inter-Regular.ttf:", f"text='{entity}':",
                           "fontcolor=white:", "fontsize=24:", "box=1:", "boxcolor=black@0.5:", "boxborderw=5:",
                           "x=(w-text_w)/2:", "y=24"]
            filter_args = "".join(text_filter)
            options.insert(6, "-vf")
            options.insert(7, filter_args)

        args = command + options
        operation = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if operation.returncode != 0:
            print(operation.stderr)
            raise RuntimeError("Ué uagliù è succiesso nu guaio mentre tagliavo i video, liv 'a miezz "
                               "'stderr=subprocess.DEVNULL' e vir nu poc ch'è succiess")


# TODO add threading and hardware acceleration because this can get pretty long and boring
def merge_shots(in_dir: Path, out_dir: Path):
    """
    Merge shots into one video
    :param selected_shots_path: path to selected shots
    :return: None
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [file.as_posix() for file in in_dir.glob('*.mp4')]
    # select only files have an audio and a video stream
    files = [file for file in files if len(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of",
         "default=noprint_wrappers=1:nokey=1", file],
        stdout=subprocess.PIPE).stdout.decode('utf-8').splitlines()) > 0 and len(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of",
         "default=noprint_wrappers=1:nokey=1", file],
        stdout=subprocess.PIPE).stdout.decode('utf-8').splitlines()) > 0]
    files.sort()

    out_path = uniquify(Path(out_dir, 'merged.mp4').as_posix())
    command = ["ffmpeg"]
    input_files = [["-i", file] for file in files]
    input_files = [item for sublist in input_files for item in sublist]
    streams = [f"[{i}:v][{i}:a]" for i in range(len(files))]
    concat = [f"concat=n={len(files)}:v=1:a=1[v][a]"]
    mapper = ['-map', '[v]', '-map', '[a]']
    sync = ["-vsync", "2", '-threads', '0']
    options = input_files + ["-filter_complex"] + [f"{''.join(streams + concat)}"] + mapper + sync + [out_path]
    args = command + options
    print(args)
    operation = subprocess.run(args, stdout=subprocess.DEVNULL)


def agnostic_merge(video_dir, output_dir):
    output_directory = ensure_dir(output_dir)
    files = [os.path.join(video_dir, file) for file in os.listdir(video_dir) if file.endswith('.mp4')]
    out_path = uniquify(os.path.join(output_directory, 'merged.mp4'))
    command = ["ffmpeg"]
    input_files = [["-i", file] for file in files]
    input_files = [item for sublist in input_files for item in sublist]
    aspect_ratio_handler = [
        f'[{i}]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}];' for
        i in range(len(files))]
    streams = [f'[v{i}][{i}:a:0]' for i in range(len(files))]
    concat = [f"concat=n={len(files)}:v=1:a=1[v][a]"]
    mapper = ['-map', '[v]', '-map', '[a]']
    sync = ["-vsync", "2"]
    options = input_files + ["-filter_complex"] + [
        f"{''.join(aspect_ratio_handler + streams + concat)}"] + mapper + sync + [out_path]
    args = command + options
    subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render_heatmap(out_dir: Path, data: pd.DataFrame, key: list, **kwargs) -> None:
    """
    :param data: DataFrame with data to plot
    :param out_dir: folder where to save the heatmap
    :keyword resolution: tuple(width, height)
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    res = (1920, 1080) if kwargs.get('resolution') is None else kwargs.get('resolution')
    data.fillna(0, inplace=True)

    img = np.zeros((res[1], res[0], 4), dtype=np.uint)
    for _, row in data.iterrows():
        left, top, right, bottom = ensure_coords(row['left'], row['top'], row['right'], row['bottom'])
        img[int(top * res[1]):int(bottom * res[1]), int(left * res[0]):int(right * res[0]), 0:3] += 1
    img = img / img.max()
    img[0:res[1], 0:res[0], 3] = 1

    video_id, object_name = data['id'].iat[0], data['object_name'].iat[0]
    out_path = out_dir / f"{video_id}_{object_name}.png"
    plt.imsave(uniquify(out_path.as_posix()), img)


def extract_object_thumbnails(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: list) -> None:
    """
    Given a video and a dataframe with object tracking annotations extracts thumbnails of selected the objects
    :rtype: None
    :param key: name of the object to extract
    :param in_dir: directory where the source video is stored
    :param out_dir: directory where to save the thumbnails
    :param data: dataframe with object tracking annotations
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    data = interpolate_missing_data(data)
    extract_object_thumbs(in_dir, out_dir, data)
    return None


def extract_object_gifs(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: list) -> None:
    """
    Given a video and a dataframe with object tracking annotations extracts gifs of selected the objects
    :rtype: None
    :param key: name of the object to extract
    :param in_dir: directory where the source video is stored
    :param out_dir: directory where to save the thumbnails
    :param data: dataframe with object tracking annotations
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    data = interpolate_missing_data(data)
    extract_obj_gifs(in_dir, out_dir, data)
    return None


def extract_masked_clips(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: list) -> None:
    """
    Given a video and a dataframe with object tracking annotations extracts clips of selected the objects
    :param key: name of the object to extract
    :param in_dir: directory where the source video is stored
    :param out_dir: directory where to save the clips
    :param data: dataframe with object tracking annotations
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    data = interpolate_missing_data(data)
    extract_masked_object_clips(in_dir, out_dir, data)


def extract_object_metavideo(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: list) -> None:
    """
    Given a video and a dataframe with object tracking annotations extracts clips of selected the objects
    :param key: name of the object to extract
    :param in_dir: directory where the source video is stored
    :param out_dir: directory where to save the clips
    :param data: dataframe with object tracking annotations
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    data = interpolate_missing_data(data)
    temp_dir = tempfile.TemporaryDirectory()
    extract_masked_object_clips(in_dir, Path(temp_dir.name), data, color=(0, 255, 0, 0))
    merge_with_chromakey(Path(temp_dir.name), out_dir)


def extract_object_metagrid(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: list) -> None:
    """
    Given a video and a dataframe with object tracking annotations extracts clips of selected the objects
    :param key: name of the object to extract
    :param in_dir: directory where the source video is stored
    :param out_dir: directory where to save the clips
    :param data: dataframe with object tracking annotations
    :return: None
    """
    data = data[data['object_name'].isin(key)]
    data = interpolate_missing_data(data)
    temp_dir = tempfile.TemporaryDirectory()
    extract_object_thumbs(in_dir, Path(temp_dir.name), data)
    get_metagrid(Path(temp_dir.name), out_dir)
