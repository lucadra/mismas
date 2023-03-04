import concurrent.futures
import os
import tempfile
from pathlib import Path

import pandas as pd
import tqdm
from PIL import Image

import analysis
from object_tracking_operations import (extract_frame, extract_object_thumbs,
                                        interpolate_missing_data, mask_frame)
from utils import (copy_visualiser_dir, ensure_coords, find_video_by_id,
                   serve_directory, uniquify)


def compile_most_present_objects(data: pd.DataFrame) -> pd.DataFrame:
    data = (
        data.groupby(["id", "object_name", "object_id"])
            .agg(start_time=("time_seconds", "min"), end_time=("time_seconds", "max"), left=("left", "last"), right=("right", "last"), top=("top", "last"), bottom=("bottom", "last"))
            .reset_index()
    )
    
    data["duration"] = data["end_time"] - data["start_time"]
    ## apsect ratio is needed for rectpacking to work
    data["aspect_ratio"] = ((data["right"].values - data["left"].values) * 1.77777777777778) / (data["bottom"].values - data["top"].values)
    
    data = data.drop(columns=["left", "right", "top", "bottom"])
    
    data = data.loc[data["duration"] > 0]
    data = data.sort_values(by="duration", ascending=False)
    data = data.reset_index(drop=True)

    data["start_time"] = data["start_time"].apply(lambda x: f'{x:.3f}')
    data["end_time"] = data["end_time"].apply(lambda x: f'{x:.3f}')
    data["duration"] = data["duration"].apply(lambda x: f'{x:.3f}')

    return data


def most_present_objects_to_pixplot(data: pd.DataFrame):
    data = data[data['object_name'].str.contains('goods|product', case=False)]
    pixplot_data = data[['id', 'object_name', 'object_id']].copy()
    pixplot_data['filename'] = pixplot_data['object_name'] + '_' + pixplot_data['object_id'] + '_' + '[' + data['end_time'] + '].jpg'
    pixplot_data.rename(columns={'id': 'category', 'filename': 'filename', 'object_name': 'label'}, inplace=True)
    pixplot_data['tags'] = pixplot_data['label']
    pixplot_data = pixplot_data[['filename', 'category', 'label', 'tags']]
    return pixplot_data


def delete_unwanted_images(images_folder, df):
    image_filenames = set(os.listdir(images_folder))
    df_filenames = set(df['filename'].tolist())
    unwanted_filenames = image_filenames - df_filenames
    for filename in unwanted_filenames:
        os.remove(os.path.join(images_folder, filename))
        print("Deleted", filename)


# this may be entirely useless as playback data is not available for all videos and is not a good measure of interest
def compile_most_reviewed_objects(ot_data: pd.DataFrame, pb_data: pd.DataFrame, yt_data: pd.DataFrame, n: int = 100):
    """
    Returns a dataframe with the most viewed objects in the dataset

    ++++ re-viewed = playback score * duration * views ++++

    :param: ot_data: object tracking data
    :param: pb_data: playback data
    :param: yt_data: youtube metadata from 'youtube_report.csv'
    :param: n: number of objects to return
    """
    # Not all videos have playback data, so we need to filter out the ones that don't
    ot_data = ot_data[ot_data["id"].isin(pb_data["id"])]
    yt_data = yt_data[yt_data["id"].isin(pb_data["id"])]
    # We add a column to the playback data that contains the total number of views for each video
    pb_data = pb_data.merge(yt_data[["id", "views"]], on="id")
    # We reduce the object tracking data to only start and end times for each object
    ot_data = ot_data.groupby(["id", "object_name", "object_id"]).agg({"time_seconds": ["min", "max"]})
    # we turn the groups back into a df and flatten the columns
    ot_data = ot_data.reset_index()
    ot_data.columns = ["id", "object_name", "object_id", "start_time", "end_time"]
    # We add a score column to the object tracking data
    ot_data["score"] = 0
    
    # score is calculated as follows:
    # for each object, we find overlapping intervals in the playback data
    # we calculate the the scores of the overlapping intervals as overlap_duration * segment_score * views
    # we add score to the object tracking data as sum(overlapping_intervals_scores)

    for idx, row in tqdm.tqdm(ot_data.iterrows(), total=len(ot_data)):
        # we find the overlapping intervals
        overlapping_intervals = pb_data[(pb_data["id"] == row["id"]) & (pb_data["start_sec"] < row["end_time"]) & (pb_data["end_sec"] > row["start_time"])]
        # we calculate the weighted average score
        weighted_average_score = 0
        for _, interval in overlapping_intervals.iterrows():
            interval_scores = []
            # we calculate the duration of the overlap
            overlap_duration = min(interval["end_sec"], row["end_time"]) - max(interval["start_sec"], row["start_time"])
            # we calculate the score of the segment
            segment_score = interval["views"] * interval["score"] * overlap_duration
            interval_scores.append(segment_score)
        ot_data.at[idx, "score"] = sum(interval_scores)
    ot_data = ot_data.sort_values(by="score", ascending=False)
    return None


def compile_most_viewed_objects(ot_data: pd.DataFrame, yt_data: pd.DataFrame, n: int = 100):
    """
    Returns a dataframe with the most viewed objects in the dataset
    
    ++++ viewed = duration * views ++++ 

    :param: yt_data: youtube metadata from 'youtube_report.csv'
    :param: n: number of objects to return
    """
    # We reduce the object tracking data to only start and end times for each object
    ot_data = ot_data.groupby(["id", "object_name", "object_id"]).agg({"time_seconds": ["min", "max"]})
    ot_data['duration'] = ot_data['time_seconds']['max'] - ot_data['time_seconds']['min']
    # we turn the groups back into a df and flatten the columns
    ot_data = ot_data.reset_index()
    ot_data.columns = ["id", "object_name", "object_id", "start_time", "end_time", "duration"]
    # We calculate the score column as duration * views
    ot_data = ot_data.merge(yt_data[["id", "views"]], on="id")
    ot_data["score"] = ot_data["duration"] * ot_data["views"]
    ot_data = ot_data.sort_values(by="score", ascending=False)
    ot_data = ot_data.head(n)
    print(ot_data)
    return ot_data


def extract_itematlas_thumbs(project_dir: Path,  object_tracking_data: pd.DataFrame):
    # we only want one frame from each object, i can only pick first or last, 
    # trial and error showed that last is better than first
    in_dir = project_dir / "download"
    out_dir = project_dir / "itematlas" / "img"
    out_dir.mkdir(exist_ok=True, parents=True)
    object_tracking_data = object_tracking_data.drop_duplicates(subset="object_id", keep="last")
    out_dir.mkdir(exist_ok=True)
    extract_object_thumbs(in_dir, out_dir, object_tracking_data)


def extract_top_n_catalogue_thumbs(in_dir: Path, out_dir: Path, ot_data: pd.DataFrame, cat_data: pd.DataFrame, n: int = 100):

    grouped_data = cat_data.groupby(["object_name"])
    
    # calculate total duration of each group
    dur_data = grouped_data.agg({"duration": "sum"}).sort_values(by="duration", ascending=False)
    
    grouped_data = grouped_data.apply(lambda x: x.sort_values(["duration"], ascending = False))
    # take first n rows from each group
    grouped_data = grouped_data.groupby(level=0).head(n)
    grouped_data = grouped_data.reset_index(drop=True)
    grouped_data = grouped_data.groupby(["object_name"])

    # create a new df taking groups from grouped_data in the order of dur_data
    cat_data = pd.DataFrame(columns=cat_data.columns)
    for _, row in dur_data.iterrows():
        # append new rows to df until 1000 rows are reached
        if (len(cat_data) + len(grouped_data.get_group(row.name))) > 1000:
            continue
        else:
            cat_data = cat_data.append(grouped_data.get_group(row.name))

    cat_data = cat_data.reset_index(drop=True)
    print(cat_data)
    ot_data = ot_data[ot_data["object_id"].isin(cat_data["object_id"])]
    ot_data = ot_data.drop_duplicates(subset="object_id", keep="last")
    out_dir = Path(out_dir) / "catalogue_images"
    out_dir.mkdir(exist_ok=True)
    ot_data.to_csv(out_dir / "catalogue_ot.csv", index=False)
    cat_data.to_csv(out_dir / "catalogue.csv", index=False)
    extract_object_thumbs(in_dir, out_dir, ot_data)


def make_most_present_catalogue(in_dir: Path, out_dir: Path, data: pd.DataFrame, n: int = 100):
    cat_data = compile_most_present_objects(data)
    extract_itematlas_thumbs(in_dir, out_dir, data, cat_data, n)
    cat_data = cat_data.head(n)
    cat_data.to_csv(out_dir / "catalogue.csv", index=False)


def make_thumb_trace(in_dir: Path, out_dir: Path, data: pd.DataFrame, key: str):
    """
    Draws the trace of an object in the video
    :param in_dir: directory where to find the video
    :param out_dir: directory where to save the output image
    :param data: object tracking data
    :param key: object identifier
    """
    # Select data and add rows to increase extraction granularity
    data = data[data["object_id"] == key]
    data = data.sort_values(by="time_seconds")
    data = interpolate_missing_data(data)
    data = data.reset_index(drop=True)

    # Find video
    video = find_video_by_id(data["id"][0], in_dir)

    object_name = data["object_name"][0]
    object_id = key

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_frames = Path(tmp_dir) / "frames"
        out_thumbs = Path(tmp_dir) / "thumbs"
        out_frames.mkdir(exist_ok=True)
        out_thumbs.mkdir(exist_ok=True)

        with tqdm.tqdm(total=len(data), desc="Extracting frames") as pbar:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for _, row in data.iterrows():
                    futures.append(executor.submit(extract_frame, video, out_frames, row["time_seconds"], object_id, object_name))
                for future in concurrent.futures.as_completed(futures):
                    pbar.update()

        with tqdm.tqdm(total=len(data), desc="Masking frames") as pbar:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for _, row in data.iterrows():
                    name = f"{object_name}_{object_id}_[{row['time_seconds']:1.3f}].jpg"
                    image_path = out_frames / name
                    # out_path = out_dir / "THUMB_TEST"
                    # out_path.mkdir(exist_ok=True)
                    left, top, right, bottom = ensure_coords(row["left"], row["top"], row["right"], row["bottom"])
                    futures.append(executor.submit(mask_frame, image_path, out_thumbs, left, top, right, bottom, (0, 0, 0, 0)))
                for future in concurrent.futures.as_completed(futures):
                    pbar.update()

        # create composite image
        composite_image = Image.new('RGBA', (1280, 720), (0,0,0, 0))
        for _, row in data.iterrows():
            image = out_thumbs / f"{object_name}_{object_id}_[{row['time_seconds']:1.3f}].png"
            #print(image)
            with Image.open(image) as img:
                alphachannel = img.getchannel('A')
                # Make all opaque pixels into semi-opaque
                newA = alphachannel.point(lambda i: 100 if i>0 else 0)
                # Put new alpha channel back into original image and save
                img.putalpha(newA)
                composite_image = Image.alpha_composite(composite_image, img)
        img_out = out_dir / f"{object_name}_{object_id}.png"
        composite_image.save(out_dir / uniquify(img_out))
        #composite_image.show()
        return composite_image


def serve_itematlas(project_dir: Path):
    data_path = project_dir / 'data' / 'object_tracking' / 'merged.csv'
    
    try:
        data = pd.read_csv(data_path)
    except FileNotFoundError:
        import utils
        print("Object Tracking data not found, running analysis on all downloaded videos...")
        video_ids = [utils.parse_id(v.stem) for v in project_dir.glob('download/*.mp4')]
        analysis.batch_annotate_from_ids(video_ids, 'object_tracking', project_dir)
        data = pd.read_csv(data_path)

    momentmap_dest = copy_visualiser_dir(project_dir, 'itematlas')
    object_data = compile_most_present_objects(data)
    object_data.to_csv(momentmap_dest / 'data' / 'object_data.csv', index=False)    
    extract_itematlas_thumbs(project_dir, data)

    serve_directory(momentmap_dest)

