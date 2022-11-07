import os
from pathlib import Path

import pandas as pd
from google.cloud import videointelligence

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'credentials/mismas-363214-7a6cbac454ec.json'

file = Path('videos', 'original_videos',
            '[c2B1ghS1fOE]_Haiti riots: Calls for calm after anti-government violence - BBC News.mp4')

if not Path('shot_changes.csv').is_file():
    video_client = videointelligence.VideoIntelligenceServiceClient()
    features = [videointelligence.Feature.SHOT_CHANGE_DETECTION]
    operation = video_client.annotate_video(
        request={"features": features, "input_content": file.read_bytes()}
    )
    print("\nProcessing video for shot change annotations:")

    result = operation.result(timeout=90)
    print("\nFinished processing.")

    shot_changes = []
    # first result is retrieved because a single video was processed
    for i, shot in enumerate(result.annotation_results[0].shot_annotations):
        start_time = (
                shot.start_time_offset.seconds + shot.start_time_offset.microseconds / 1e6
        )
        end_time = (
                shot.end_time_offset.seconds + shot.end_time_offset.microseconds / 1e6
        )
        shot_changes.append({"shot": i, "start_time": start_time, "end_time": end_time})

    shot_changes = pd.DataFrame(shot_changes)
    shot_changes.to_csv('shot_changes.csv', index=False)
else:
    shot_changes = pd.read_csv('shot_changes.csv')

import spacy

# loading the english language small model of spac
en = spacy.load('en_core_web_sm')
stopwords = en.Defaults.stop_words

shot_change_data = pd.read_csv('/home/luca/mismas/BBC News/data/shot_change_detection/merged.csv')
object_tracking_data = pd.read_csv("/home/luca/mismas/BBC News/data/object_tracking/merged.csv")
transcript_data = pd.read_csv('/home/luca/mismas/BBC News/data/transcription/merged.csv')
label_detection_data = pd.read_csv('/home/luca/mismas/BBC News/data/label_detection/merged.csv')
# remove all punctuation from the word column
print("Removing punctuation from the word column")
transcript_data['word'] = transcript_data['word'].str.replace('[^\w\s]', '')
transcript_data['word'] = transcript_data['word'].str.lower()
transcript_data = transcript_data.query('word != ""')
# lemmatize the words
print("Lemmatizing words...")
from tqdm import tqdm

tqdm.pandas()
transcript_data['word'] = transcript_data['word'].progress_apply(lambda x: en(x)[0].lemma_)
# remove all stopwords
print("Removing stopwords...")
transcript_data = transcript_data.query('word not in @stopwords')
# remove empty words


table = []
pbar = tqdm(total=len(shot_change_data), desc="Processing shots", smoothing=0.7)
word_batches = transcript_data.groupby('id')
# object_batches = object_tracking_data.groupby('id')
label_batches = label_detection_data.groupby('id')

for _, row in shot_change_data.iterrows():
    shot = row['shot_num']
    start_time = row['start_sec']
    end_time = row['end_sec']
    current_id = row['id']
    try:
        vid_words = word_batches.get_group(current_id)
    except KeyError:
        pass
    try:
        # vid_objects = label_batches.get_group(current_id)
        vid_labels = label_batches.get_group(current_id)
    except KeyError:
        pass
    words = vid_words[(vid_words['start_sec'] >= start_time) & (vid_words['end_sec'] <= end_time)]
    labels = vid_labels[(vid_labels['start_sec'] >= start_time) & (vid_labels['end_sec'] <= end_time)]

    #    objects = vid_objects[(start_time <= vid_objects['time_seconds']) & (vid_objects['time_seconds'] <= end_time)]
    for _, word in words.iterrows():
        for _, object in labels.iterrows():
            table.append({'source': word['word'], 'target': object['entity']})
    pbar.update(1)

table = pd.DataFrame(table)
# count how many times couples of values appear together in df
# table = table.groupby(['source', 'target']).size().reset_index(name='count')
table = table.drop_duplicates(subset=['source', 'target'])
table.to_csv('multimodal_map.csv', index=False)
# create a dataframe with columns "id" and "group". id = name of the node, group = header of the node
nodesA = pd.DataFrame(table['source'].unique(), columns=['id'])
nodesA['group'] = 'words'
nodesB = pd.DataFrame(table['target'].unique(), columns=['id'])
nodesB['group'] = 'objects'
nodes = pd.concat([nodesA, nodesB])
nodes = nodes.drop_duplicates(subset=['id'], keep='first')
nodes.to_csv('multimodal_nodes.csv', index=False)
