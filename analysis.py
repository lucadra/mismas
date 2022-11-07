import json
import os
import re
import uuid
from pathlib import Path
from typing import List

import pandas as pd
from google.cloud import videointelligence
from google.protobuf.json_format import MessageToJson
from tqdm import tqdm

from most_replayed_scraper import get_playback_heatmarkers
from utils import ensure_coords
from utils import seconds_to_string, check_category, parse_id

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'credentials/mismas-363214-7a6cbac454ec.json'


class VideoIntelligenceRequest():

    def __init__(self, client, path: Path):
        self.df = None
        self.transcript = None
        self.path = path
        self.id = re.findall(r'\[(.*?)\]', path.stem)[0]
        self.filename = path.stem
        self.input_content = path.read_bytes()
        self.client = client

    def label_detection(self, mode='SHOT_MODE') -> pd.DataFrame:
        features = [videointelligence.Feature.LABEL_DETECTION]
        config = videointelligence.LabelDetectionConfig(label_detection_mode=mode)
        video_context = videointelligence.VideoContext(label_detection_config=config)
        operation = self.client.annotate_video(
            request={"input_content": self.input_content, "features": features, "video_context": video_context})
        self.df = parse_label_data(json.loads(MessageToJson(operation.result()._pb)))
        self.df.insert(0, 'id', self.id)
        return self.df

    def frame_label_detection(self, mode='FRAME_MODE') -> pd.DataFrame:
        features = [videointelligence.Feature.LABEL_DETECTION]
        config = videointelligence.LabelDetectionConfig(label_detection_mode=mode)
        video_context = videointelligence.VideoContext(label_detection_config=config)
        operation = self.client.annotate_video(
            request={"input_content": self.input_content, "features": features, "video_context": video_context})
        self.df = parse_frame_label_data(json.loads(MessageToJson(operation.result()._pb)))
        self.df.insert(0, 'id', self.id)
        return self.df

    def transcription(self) -> pd.DataFrame:
        features = [videointelligence.Feature.SPEECH_TRANSCRIPTION]
        config = videointelligence.SpeechTranscriptionConfig(
            language_code="en-US", max_alternatives=1, enable_automatic_punctuation=True, enable_word_confidence=True)
        video_context = videointelligence.VideoContext(speech_transcription_config=config)
        operation = self.client.annotate_video(
            request={"input_content": self.input_content, "features": features,
                     "video_context": video_context})
        self.df = parse_word_data(json.loads(MessageToJson(operation.result()._pb)))
        self.df.insert(0, 'id', self.id)
        return self.df

    def object_tracking(self) -> pd.DataFrame:
        features = [videointelligence.Feature.OBJECT_TRACKING]
        operation = self.client.annotate_video(
            request={"input_content": self.input_content, "features": features})
        self.df = parse_object_tracking_data(json.loads(MessageToJson(operation.result()._pb)))
        self.df.insert(0, 'id', self.id)
        return self.df

    def shot_change_detection(self) -> pd.DataFrame:
        features = [videointelligence.Feature.SHOT_CHANGE_DETECTION]
        operation = self.client.annotate_video(
            request={"input_content": self.input_content, "features": features})
        self.df = parse_shot_change_data(json.loads(MessageToJson(operation.result()._pb)))
        self.df.insert(0, 'id', self.id)
        return self.df


def parse_shot_change_data(data: dict) -> pd.DataFrame:
    annotations = []
    data = data['annotationResults'][0]['shotAnnotations']
    for i, annotation in enumerate(data):
        shot_num = i
        start_sec = float(annotation['startTimeOffset'].strip('s'))
        end_sec = float(annotation['endTimeOffset'].strip('s'))
        start = seconds_to_string(start_sec)
        end = seconds_to_string(end_sec)
        annotations.append([shot_num, start, end, start_sec, end_sec])

    return pd.DataFrame(annotations, columns=['shot_num', 'start', 'end', 'start_sec', 'end_sec'])


def parse_label_data(_data: dict) -> pd.DataFrame:
    annotations = []
    data = _data['annotationResults'][0].get('shotLabelAnnotations') or _data['annotationResults'][0].get(
        'frameLabelAnnotations')
    for annotation in data:
        entity = annotation['entity']['description']
        category = check_category(annotation)
        for item in annotation['segments']:
            start_sec = float(item['segment']['startTimeOffset'].strip('s'))
            end_sec = float(item['segment']['endTimeOffset'].strip('s'))
            start = seconds_to_string(start_sec)
            end = seconds_to_string(end_sec)
            confidence = float(item['confidence'])
            annotations.append([entity, category, start, end, start_sec, end_sec, confidence])

    return pd.DataFrame(annotations,
                        columns=['entity', 'category', 'start', 'end', 'start_sec', 'end_sec', 'confidence'])


def parse_frame_label_data(_data: dict) -> pd.DataFrame:
    annotations = []
    data = _data['annotationResults'][0]['frameLabelAnnotations']
    for annotation in data:
        entity_id = str(uuid.uuid4()).split('-')[0]
        while entity_id in [x[0] for x in annotations]:
            entity_id = str(uuid.uuid4()).split('-')[0]
        entity = annotation['entity']['description']
        category = check_category(annotation)
        for item in annotation['frames']:
            time_sec = float(item['timeOffset'].strip('s'))
            time = seconds_to_string(time_sec)
            confidence = float(item['confidence'])
            annotations.append([entity_id, entity, category, time, time_sec, confidence])

    return pd.DataFrame(annotations, columns=['entity_id', 'entity', 'category', 'time', 'time_sec', 'confidence'])


def parse_word_data(_data: dict) -> pd.DataFrame:
    words = []
    data = _data['annotationResults'][0]['speechTranscriptions']
    transcriptions = [transcription for transcription in data if transcription['alternatives'][0].get('words')]
    for transcription in transcriptions:
        for word in transcription['alternatives'][0].get('words'):
            start_sec = float(word['startTime'].strip('s'))
            end_sec = float(word['endTime'].strip('s'))
            start = seconds_to_string(start_sec)
            end = seconds_to_string(end_sec)
            confidence = float(word['confidence'])
            words.append([word['word'], start, end, start_sec, end_sec, confidence])

    return pd.DataFrame(words, columns=['word', 'start', 'end', 'start_sec', 'end_sec', 'confidence'])


def parse_transcript_data(_data: dict) -> str:
    data = _data['annotationResults'][0]['speechTranscriptions']
    transcriptions = [transcription['alternatives'][0] for transcription in data if
                      transcription['alternatives'][0].get('words')]
    transcript = [transcription['transcript'] for transcription in transcriptions]

    return ''.join(transcript)


def parse_object_tracking_data(data: dict) -> pd.DataFrame:
    """
    Parses the object tracking data from the Video Intelligence API
    :param data: data returned from the Video Intelligence API
    :return: dataframe of object tracking data
    """
    json.dump(data, open('object_tracking_data.json', 'w'), indent=4)
    objects = []
    data = data['annotationResults'][0]['objectAnnotations']
    for item in data:
        object_id = str(uuid.uuid4()).split('-')[0]
        while object_id in [x[0] for x in objects]:
            object_id = str(uuid.uuid4()).split('-')[0]
        object_name = item['entity']['description']
        for frame in item['frames']:
            # sometimes one of the coordinates is missing, sometimes they're even negative. Not sure what that means.
            bbox = frame.get('normalizedBoundingBox')
            left, top, right, bottom = bbox.get('left'), bbox.get('top'), bbox.get('right'), bbox.get('bottom')
            left, top, right, bottom = ensure_coords(left, top, right, bottom)
            time_seconds = float(frame['timeOffset'].strip('s'))
            objects.append([object_id, object_name, time_seconds, left, top, right, bottom])

    return pd.DataFrame(objects, columns=['object_id', 'object_name', 'time_seconds', 'left', 'top', 'right', 'bottom'])


def batch_annotate_from_ids(ids: List[str], service: str, project_directory: Path) -> pd.DataFrame:
    """
    Annotates all videos which ids are provided and returns a dataframe with the annotations
    :param project_directory: main directory of the project
    :param ids: list of ids to annotate
    :param service: service to use for annotation
    :return: dataframe with annotations
    """
    original_videos_dir = project_directory / 'download'
    out_dir = project_directory / 'data' / service
    out_dir.mkdir(parents=True, exist_ok=True)
    video_files = [path for path in original_videos_dir.glob('*.mp4') if parse_id(path.as_posix()) in ids]
    video_client = videointelligence.VideoIntelligenceServiceClient()
    for path in tqdm(video_files, desc=f"Getting {service} data for videos in {Path(project_directory).name}"):
        r = VideoIntelligenceRequest(video_client, path)
        data = getattr(r, service)()
        data.to_csv(Path(out_dir, f'{path.stem}.csv').resolve(), index=False)

    merged_df = pd.concat(
        [pd.read_csv(path.resolve().as_posix()) for path in out_dir.glob('*.csv') if parse_id(path.stem) in ids])
    merged_df.to_csv(Path(out_dir, 'merged.csv').resolve(), index=False)
    return merged_df


def most_replayed(video_ids, project_dir) -> None:
    """
    Finds the most replayed parts of the videos and saves them to a csv file
    :param video_ids:
    :param project_dir:
    :return: saves a csv file with the most replayed parts of the videos
    """
    out_dir = project_dir / 'data' / 'playback'
    out_dir.mkdir(parents=True, exist_ok=True)
    for _id in tqdm(video_ids, desc='Getting most playback data'):
        df = get_playback_heatmarkers(_id)
        if df is not None:
            df.to_csv(Path(out_dir, f'{_id}.csv').resolve(), index=False)
    merged_df = pd.concat([pd.read_csv(path.resolve().as_posix()) for path in out_dir.glob('*.csv')])
    merged_df.to_csv(Path(out_dir, 'merged.csv').resolve(), index=False)


def add_cluster_data(cluster_folder: Path, df: pd.DataFrame) -> pd.DataFrame:
    subdirs = [x for x in cluster_folder.iterdir() if x.is_dir()]
    for subdir in subdirs:
        cluster_name = subdir.name
        for path in subdir.glob('*.gif'):
            _id = parse_id(path.stem)
            df.loc[df['object_id'] == _id, 'cluster'] = cluster_name
    return df




