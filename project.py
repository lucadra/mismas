import os
from pathlib import Path
from typing import List

import enquiries
import pandas as pd

import analysis
import download
import output
from itematlas import serve_itematlas
from momentmap import serve_momentmap
from reelchart import serve_reelchart
from utils import parse_id


def ensure_mismas() -> Path:
    home_dir = Path.home()
    mismas_dir = home_dir / 'mismas'
    mismas_dir.mkdir(exist_ok=True)
    return mismas_dir


def new_project_handler(mismas_dir: Path) -> Path:
    while True:
        project_name = input('Enter project name: ')
        if not project_name or '/' in project_name:
            print("Invalid project name. It can't be empty or contain slashes.")
            continue

        project_dir = mismas_dir / project_name
        try:
            project_dir.mkdir()
            break
        except FileExistsError:
            print('There is already a project with that name')

    print(f'Created project directory: {project_dir}')
    return project_dir


def existing_project_handler(mismas_dir: Path) -> Path:
    subdirs = [sdir.stem for sdir in mismas_dir.glob('*/')]
    selected = enquiries.choose(prompt='Select project', choices=subdirs, multi=False)
    return mismas_dir / selected


def project_dir_handler(mismas_dir: Path) -> Path:
    choice_to_handler = {
        'Create new project': new_project_handler,
        'Load existing project': existing_project_handler,
    }

    choice = enquiries.choose(prompt='What do you want to do?', choices=choice_to_handler.keys(), multi=False)
    return choice_to_handler[choice](mismas_dir)


def find_channel_uploads() -> List[str]:
    channel_name = input('Enter channel name: ')
    channel_id = download.search_channel_id(channel_name)
    upload_playlist_id = download.get_uploads_playlist_id(channel_id)
    return download.get_video_ids_from_playlist(upload_playlist_id)


def get_id_from_input() -> str:
    user_input = input('Enter video id or URL: ')
    return user_input if '=' not in user_input else user_input.split('=')[1]


def yt_video_selector(project_dir: Path) -> List[str]:
    choice = enquiries.choose(prompt='How do you want to select videos?',
                              choices=['Video id or URL',
                                       'Playlist id or URL',
                                       'Search for channel name',
                                       'Load from file'])

    if choice == 'Video id or URL':
        ids = get_id_from_input()
        video_ids = [ids]
    elif choice == 'Playlist id or URL':
        ids = get_id_from_input()
        video_ids = download.get_video_ids_from_playlist(ids)
    elif choice == 'Search for channel name':
        video_ids = find_channel_uploads()
    elif choice == 'Load from file':
        file_path = enquiries.choose(prompt='Select file', choices=[f.name for f in Path(project_dir).glob('*.csv')])
        video_df = pd.read_csv(Path(project_dir, file_path).as_posix())
        video_ids = video_df['id'].tolist()

    return video_ids


def local_video_selector(project_dir: Path) -> list:
    choice = enquiries.choose(prompt='Do you want select manually or load from file? \n'
                                     'File must be *.csv containing a column named "id"',
                              choices=['Select Manually', 'Load from file'])

    if choice == 'Load from file':
        file_path = enquiries.choose(prompt='Select file', choices=[f.name for f in Path(project_dir).glob('*.csv')])
        video_df = pd.read_csv(Path(project_dir, file_path).as_posix())
        video_ids = video_df['id'].tolist()
    elif choice == 'Select Manually':
        video_folder = project_dir / 'download'
        video_ids = enquiries.choose(prompt='Select videos', choices=[f.stem for f in Path(video_folder).glob('*.mp4')],
                                     multi=True)
        video_ids = [parse_id(v) for v in video_ids]
    else:
        raise ValueError('Invalid choice')

    return video_ids


def analysis_handler(project_dir: Path) -> None:
    Path(project_dir, 'data').mkdir(exist_ok=True)
    video_ids = local_video_selector(project_dir)
    choice = enquiries.choose(prompt='What do you want to do?',
                              choices=['Label Detection',
                                       'Frame Label Detection',
                                       'Transcription',
                                       'Object Tracking',
                                       'Shot Change Detection',
                                       'Youtube Playback Data'])

    if choice == 'Label Detection':
        analysis.batch_annotate_from_ids(video_ids, 'label_detection', project_dir)
    elif choice == 'Frame Label Detection':
        analysis.batch_annotate_from_ids(video_ids, 'frame_label_detection', project_dir)
    elif choice == 'Transcription':
        analysis.batch_annotate_from_ids(video_ids, 'transcription', project_dir)
    elif choice == 'Object Tracking':
        analysis.batch_annotate_from_ids(video_ids, 'object_tracking', project_dir)
    elif choice == 'Shot Change Detection':
        analysis.batch_annotate_from_ids(video_ids, 'shot_change_detection', project_dir)
    elif choice == 'Youtube Playback Data':
        analysis.most_replayed(video_ids, project_dir)



def report_handler(project_dir: Path) -> None:
    video_ids = yt_video_selector(project_dir)
    report = download.compile_videos_report(video_ids)
    report.to_csv(Path(project_dir, 'youtube_report.csv').as_posix(), index=False)
    print('Report saved to: ', Path(project_dir, 'youtube_report.csv').as_posix())


def download_handler(project_dir: Path) -> None:
    download_folder = Path(project_dir, 'download')
    download_folder.mkdir(exist_ok=True)
    video_ids = yt_video_selector(project_dir)
    download.download_videos(video_ids, download_folder)
    print('Videos saved to: ', download_folder.as_posix())


## TODO: Ask god forgiveness for this abomination

def edit_handler(project_dir: Path) -> None:
    choice = enquiries.choose(prompt='What do you want to do?',
                              choices=['Extract Shots',
                                       'Merge Shots',
                                       'Render Heatmap',
                                       'Render Traces',
                                       'Extract Object Thumbnails',
                                       'Extract Object Gifs',
                                       'Extract Masked Clips',
                                       'Generate Object Tracking Metavideo',
                                       'Generate Object Tracking Mosaic',
                                       'Explore Object Tracking data',
                                       'Explore Speech Transcription data',
                                       'Explore Playback data',
                                       ])

    if choice == 'Extract Shots':
        data_path_parent = enquiries.choose(prompt='Select dir with shot data',
                                            choices=[path for path in Path(project_dir, 'data').glob("*/") if
                                                     path.is_dir()],
                                            multi=False)

        data_path_file = enquiries.choose(prompt='Load file with shot data',
                                          choices=[path.name for path in Path(data_path_parent).glob('*.csv')],
                                          multi=False)

        data_path = Path(project_dir, 'data', data_path_parent, data_path_file)
        data = pd.read_csv(data_path)
        shot_data = data
        if enquiries.confirm(prompt='Do you want to select shots?'):
            if data_path.parent.name == 'label_detection':
                data['count'] = data.groupby('entity')['entity'].transform(pd.Series.value_counts)
                data.sort_values('count', ascending=False)
                key = enquiries.choose(prompt="Select word to extract",
                                       choices=data['entity'].unique().tolist(),
                                       multi=True) 
                threshold = input('Enter threshold: ')
                search_categories = enquiries.confirm(prompt='Search in categories as well?')
                padding_before = input('Seconds before: ')
                padding_after = input('Seconds after: ')
                shot_data = output.select_shots_by_entity(data, key,
                                                          threshold=float(threshold),
                                                          search_categories=search_categories,
                                                          padding_before=float(padding_before),
                                                          padding_after=float(padding_after))

            elif data_path.parent.name == 'transcription':
                data['count'] = data.groupby('word')['word'].transform(pd.Series.value_counts)
                data.sort_values('count', ascending=False)
                key = input('Enter word to select: ')
                key = [key] if ',' not in key else key.split(',')
                threshold = input('Enter threshold: ')
                padding_before = input('Words before: ')
                padding_after = input('Words after: ')
                shot_data = output.select_shots_by_keyword(data, key,
                                                           threshold=float(threshold),
                                                           padding_before=int(padding_before),
                                                           padding_after=int(padding_after))

            elif data_path.parent.name == 'object_tracking':
                key = enquiries.choose(prompt='Select object to extract',
                                       choices=data['entity'].unique().tolist())
                shot_data = data[data['entity'] == key]
                threshold = input('Enter threshold: ')
                shot_data = shot_data[shot_data['confidence'] > float(threshold)]
            elif data_path.parent.name == 'playback':
                threshold = input('Enter threshold: ')
                shot_data = data[data['score'] > float(threshold)]

        if enquiries.confirm(prompt='Do you want save to a custom directory?'):
            new_dir = input('Enter directory name: ')
            new_dir = Path(project_dir, new_dir)
            new_dir.mkdir(exist_ok=True)
            out_dir = new_dir
        else:
            out_dir = project_dir / 'shots'
            out_dir.mkdir(exist_ok=True)

        in_dir = project_dir / 'download'
        text_option = enquiries.confirm(prompt='Do you want to add text to the video?')
        if text_option:
            text_option = input('Enter column where to fetch name: ')

        print(shot_data)
        shot_data.to_csv('shot_data.csv', index=False)
        output.extract_shots(shot_data, in_dir, out_dir, text_option)

    elif choice == 'Merge Shots':
        shot_dir = enquiries.choose(prompt='Select directory with shots to merge',
                                    choices=os.scandir(project_dir.as_posix()), multi=False)
        in_dir = Path(shot_dir)
        out_dir = project_dir / 'merged'
        out_dir.mkdir(exist_ok=True)
        output.merge_shots(in_dir, out_dir)

    elif choice == 'Render Heatmap':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                     choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                     multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select object to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.tolist())
        out_dir = project_dir / 'traces'
        out_dir.mkdir(exist_ok=True)
        output.render_heatmap(out_dir, data, key)

    elif choice == 'Render Traces':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                        choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                        multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select object to track', multi=True,
                                 choices=data['object_name'].value_counts().sort_values(ascending=False).index.tolist())
        out_dir = project_dir / 'traces'
        out_dir.mkdir(exist_ok=True)
        output.render_traces(out_dir, data, key)

    elif choice == 'Extract Object Thumbnails':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                     choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                     multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select object to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.tolist())
        in_dir = project_dir / 'download'
        out_dir = project_dir / 'object_thumbnails'
        out_dir.mkdir(exist_ok=True)
        output.extract_object_thumbnails(in_dir, out_dir, data, key)

    elif choice == 'Extract Object Gifs':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                     choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                     multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select object to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.tolist())
        in_dir = project_dir / 'download'
        out_dir = project_dir / 'object_gifs'
        out_dir.mkdir(exist_ok=True)
        output.extract_object_gifs(in_dir, out_dir, data, key)

    elif choice == 'Extract Masked Clips':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations', multi=False,
                                     choices=[file.name for file in
                                              Path(project_dir, 'data', 'object_tracking').rglob('*.csv')]
                                     )

        data_path = Path(project_dir, 'data', 'object_tracking', data_path)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select objects to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.to_list())
        in_dir = project_dir / 'download'
        out_dir = project_dir / 'masked_clips'
        out_dir.mkdir(exist_ok=True)
        output.extract_masked_clips(in_dir, out_dir, data, key)

    elif choice == 'Generate Object Tracking Metavideo':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                     choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                     multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select objects to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.to_list())
        in_dir = project_dir / 'download'
        out_dir = project_dir / 'metavideos'
        out_dir.mkdir(exist_ok=True)
        output.extract_object_metavideo(in_dir, out_dir, data, key)

    elif choice == 'Generate Object Tracking Mosaic':
        data_path = enquiries.choose(prompt='Select file with object tracking annotations',
                                     choices=Path(project_dir, 'data', 'object_tracking').rglob('*.csv'),
                                     multi=False)
        data = pd.read_csv(data_path)
        key = enquiries.choose(prompt='Select objects to extract', multi=True,
                               choices=data['object_name'].value_counts().sort_values(ascending=False).index.to_list())
        in_dir = project_dir / 'download'
        out_dir = project_dir / 'mosaic'
        out_dir.mkdir(exist_ok=True)
        output.extract_object_metagrid(in_dir, out_dir, data, key)

    elif choice == 'Explore Object Tracking data':
        serve_itematlas(project_dir)

    elif choice == 'Explore Speech Transcription data':
        serve_reelchart(project_dir)

    elif choice == 'Explore Playback data':
        serve_momentmap(project_dir)
