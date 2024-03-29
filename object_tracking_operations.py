import concurrent.futures
import re
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from tqdm import tqdm

from metavideo import crop_thumbs_to_normalised_size, get_min_thumbs_size_data
from utils import (clean_user_input, ensure_coords, find_longest_video,
                   find_video_by_id, uniquify)

warnings.simplefilter(action="ignore", category=FutureWarning)


# TODO: Code in this file can be made much more efficent using ffmpeg to crop 


def add_rows(data: pd.DataFrame) -> pd.DataFrame:
    data = data.reindex(index=data.index.repeat(2))
    data = data.iloc[1:]
    data.loc[1:data.shape[0]:2] = np.nan
    data.loc[:, :3] = data.iloc[:, :3].ffill()
    return data.reset_index(drop=True)


def interpolate_subsection(data: pd.DataFrame) -> pd.DataFrame:
    data.iloc[:, 3:] = data.iloc[:, 3:].astype(float)
    data.iloc[:, 3:] = (
        data.iloc[:, 3:].interpolate(method="linear", axis=0).ffill().bfill()
    )
    return data


def interpolate_missing_data(data: pd.DataFrame) -> pd.DataFrame:
    """
    Interpolate missing data in the dataframe, this brings the sampling rate to 20 fps
    :param data: data returned from the object tracking call to the API
    :return: dataframe with interpolated data
    """
    unique_objects = data["object_id"].unique()
    interpolated_data = pd.DataFrame()
    pd.options.mode.chained_assignment = None
    for object_data in tqdm(
            unique_objects, desc="Interpolating data to generate new frames"
    ):
        object_rows = data.groupby("object_id").get_group(object_data).reset_index(drop=True)
        object_rows = add_rows(object_rows)
        object_rows = interpolate_subsection(object_rows)
        interpolated_data = interpolated_data.append(object_rows)
    interpolated_data = interpolated_data.reset_index(drop=True)
    return interpolated_data


def extract_frame(in_path: Path, out_dir: Path, timestamp: float, object_id: str, object_name: str) -> int:
    out_path = out_dir / f"{object_name}_{object_id}_[{timestamp:1.3f}].jpg"
    cmd = ["ffmpeg", "-y", "-ss", str(timestamp), "-i", in_path.as_posix(), "-vframes", "1",
           "-q:v", "2", out_path.as_posix()]
    operation = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    return operation.returncode


def masked_frames_to_video(in_dir: Path, out_path: Path, fps: int):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path = uniquify(out_path.as_posix())
    fps = str(fps)
    args = ["ffmpeg", "-threads", "0", "-framerate", fps, "-pattern_type", "glob", "-i", "*.jpg", "-c:v",
            "libx264", "-y", out_path]
    subprocess.run(args, cwd=in_dir.as_posix(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    
def draw_mask(image: Image, left: float, top: float, right: float, bottom: float, color):
    """
    :param: color: tuple of (r, g, b, a) values
    """
    image.putalpha(255)
    draw = ImageDraw.Draw(image)
    w, h = image.size
    draw.rectangle((0, 0, left * w, h), fill=color)
    draw.rectangle((0, 0, w, top * h), fill=color)
    draw.rectangle((right * w, 0, w, h), fill=color)
    draw.rectangle((0, bottom * h, w, h), fill=color)


def mask_frame(in_path: Path, out_path: Path, left: float, top: float, right: float, bottom: float,
               color: Tuple[int]) -> None:
    image = Image.open(in_path.as_posix())
    draw_mask(image, left, top, right, bottom, color)
    out_path = out_path / in_path.name
    # set outpath suffix to png
    out_path = Path(out_path.as_posix().replace(".jpg", ".png"))
    image.save(out_path.as_posix())


def mask_frames(in_dir: Path, out_dir: Path, data: pd.DataFrame, **kwargs):
    color = "black" if "color" not in kwargs else kwargs["color"]
    out_dir.mkdir(parents=True, exist_ok=True)
    for _, row in data.iterrows():
        in_path = Path(
            in_dir,
            f"{row['object_name']}_{row['object_id']}_[{row['time_seconds']:1.3f}].png",
        )
        left, top, right, bottom = ensure_coords(
            row["left"], row["top"], row["right"], row["bottom"]
        )
        mask_frame(in_path, out_dir, left, top, right, bottom, color)


def extract_masked_object_clips(in_dir: Path, out_dir: Path, data: pd.DataFrame, **kwargs):
    """
    Generates a video for each object in the data frame, isolating the object in the video
    :param in_dir: directory where the video is stored
    :param out_dir: directory where to save generated videos
    :param data: object tracking annotations
    :param kwargs: color=tuple(r, g, b, a) to specify the color of the masked area
    :return:
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    executor = concurrent.futures.ThreadPoolExecutor()
    pbar = tqdm(
        total=len(data["object_id"].unique()), desc="Extracting masked object clips"
    )

    for object_id in data["object_id"].unique():
        temp_dir = tempfile.TemporaryDirectory()
        object_data = data.groupby("object_id").get_group(object_id)
        object_name = object_data["object_name"].iat[0]
        timestamps = object_data["time_seconds"].unique()

        video_path = find_video_by_id(object_data["id"].iat[0], in_dir)
        frames_out_dir = Path(temp_dir.name, "frames")
        frames_out_dir.mkdir(parents=True, exist_ok=True)

        futures = [
            executor.submit(extract_frame, video_path, frames_out_dir, timestamp, object_id, object_name)
            for timestamp in timestamps
        ]
        concurrent.futures.wait(futures)

        masked_frames_out_dir = Path(temp_dir.name, "masked_frames")
        masked_frames_out_dir.mkdir(parents=True, exist_ok=True)

        mask_frames(frames_out_dir, masked_frames_out_dir, object_data, **kwargs)

        vid_out_path = Path(out_dir, f"{object_name}_{object_id}_masked.mp4")
        masked_frames_to_video(masked_frames_out_dir, vid_out_path, 20)

        temp_dir.cleanup()
        pbar.update(1)


def select_data_for_object_clip_extraction(
        data: pd.DataFrame, keyword: str, threshold: float
) -> pd.DataFrame:
    data = data[data["object_name"] == keyword]
    data_selection = pd.DataFrame()
    duration_threshold = threshold
    for object_id in data["object_id"].unique():
        object_data = data.groupby("object_id").get_group(object_id)
        if (
                object_data["time_seconds"].iat[-1] - object_data["time_seconds"].iat[0]
                > duration_threshold
        ):
            data_selection = data_selection.append(object_data)
    return data_selection


def chroma_constructor(in_dir: Path, out_dir: Path):
    """Generates the command needed to merge masked clips together"""
    longest_vid = find_longest_video(in_dir)
    overlay_vids = [
        vid.as_posix() for vid in in_dir.glob("*.mp4") if vid != longest_vid
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    base = ["ffmpeg", "-f", "lavfi", "-i", "color=c=0x7F7F7F:s=1280x720:r=20", "-i", longest_vid.as_posix()]
    inputs = [["-i", overlay_vid] for overlay_vid in overlay_vids]
    inputs = [item for sublist in inputs for item in sublist]
    chroma_options = [
        f"[{i + 1}:v]colorkey=0x00FF00:0.2:0.2[ckout{i}];"
        for i in range(len(overlay_vids))
    ]
    overlay_options = ["[0:v][ckout0]overlay=shortest=1[out0];"]
    overlay_options.extend(
        f"[out{i - 1}][ckout{i}]overlay[out{i}];"
        for i in range(1, len(overlay_vids))
    )
    filter_options = "".join(chroma_options + overlay_options)
    filter_options = filter_options.strip(";")
    filter_command = ["-filter_complex", filter_options]
    out_path = out_dir / longest_vid.name.split("_")[0]
    out_path = out_path.with_suffix(".mp4")
    export = ["-map", f"[out{len(overlay_vids) - 1}]", "-y", out_path.as_posix()]
    return base + inputs + filter_command + export


def merge_with_chromakey(in_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    command = chroma_constructor(in_dir, out_dir)
    subprocess.run(command) 


def extract_frame(in_path: Path, out_dir: Path, timestamp: float, object_id: str, object_name: str) -> int:
    out_path = out_dir / f"{object_name}_{object_id}_[{timestamp:1.3f}].jpg"
    cmd = ["ffmpeg", "-y", "-ss", str(timestamp), "-i", in_path.as_posix(), "-vframes", "1",
           "-q:v", "2", out_path.as_posix()]
    operation = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    return operation.returncode


def crop_frame(in_path: Path, out_dir: Path, left: float, top: float, right: float, bottom: float) -> None:
    image = Image.open(in_path.as_posix())
    w, h = image.size
    left, top, right, bottom = ensure_coords(left, top, right, bottom)
    left, top, right, bottom = (
        int(left * w),
        int(top * h),
        int(right * w),
        int(bottom * h),
    )
    image = image.crop((left, top, right, bottom))
    out_path = out_dir / in_path.name
    image.save(out_path.as_posix())


def extract_object_thumbs(in_dir: Path, out_dir: Path, data: pd.DataFrame):
    """
    Extracts object thumbnails from the video frames.
    :param in_dir:
    :param out_dir:
    :param data:
    :return:
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    video_groups = data.groupby("id")
    commands = []

    with tqdm(total=data.shape[0], desc="Building commands") as pbar:
        for video_id, v_group in video_groups:
            video_path = find_video_by_id(video_id, in_dir)
            output = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", video_path.as_posix()])
            dimensions = re.search(r"([0-9]+)x([0-9]+)", output.decode("utf-8"))
            w, h = int(dimensions.group(1)), int(dimensions.group(2))

            label_groups = v_group.groupby("object_name")
            for label_name, label_data in label_groups:
                object_groups = label_data.groupby("object_id")
                for object_id, object_data in object_groups:
                    for _, row in object_data.iterrows():
                        left, top, right, bottom = ensure_coords(row['left'], row['top'], row['right'], row['bottom'])
                        left, top, right, bottom = int(left * w), int(top * h), int(right * w), int(bottom * h)
                        out_path = out_dir / f"{label_name}_{object_id}_[{row['time_seconds']:.3f}].jpg"
                        cmd = [ 
                            "ffmpeg", "-y", "-ss", str(row['time_seconds']), "-i", video_path.as_posix(), "-vframes", "1",
                            "-vf", f"crop={right - left}:{bottom - top}:{left}:{top}", "-q:v", "2", out_path.as_posix()
                            ]
                        commands.append(cmd)
                        pbar.update(1)

    with tqdm(total=len(commands), desc="Extracting object thumbnails") as pbar:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for cmd in commands]
            for _ in concurrent.futures.as_completed(futures):
                pbar.update(1)


def extract_obj_gifs(in_dir: Path, out_dir: Path, data: pd.DataFrame):
    """
    Extracts object gifs from the video frames.
    :param in_dir:
    :param out_dir:
    :param data:
    :return:
    """
    tmp_dir = tempfile.TemporaryDirectory()
    executor = concurrent.futures.ProcessPoolExecutor()

    out_dir.mkdir(parents=True, exist_ok=True)
    pbar = tqdm(
        total=len(data["object_id"].unique()), desc="Extracting object thumbnails", smoothing=0
    )

    object_groups = data.groupby("object_id")

    for object_id in data["object_id"].unique():
        object_data = object_groups.get_group(object_id)
        object_name = object_data["object_name"].iat[0]
    
        video_path = find_video_by_id(object_data["id"].iat[0], in_dir)
        timestamps = object_data["time_seconds"].to_numpy()

        frame_path = Path(tmp_dir.name, 'frames')
        thumb_path = Path(tmp_dir.name, 'thumbs')

        frame_path.mkdir(parents=True, exist_ok=True)
        thumb_path.mkdir(parents=True, exist_ok=True)

        futures = [
            executor.submit(extract_frame, video_path, frame_path, timestamp, object_id, object_name)
            for timestamp in timestamps
        ]
        concurrent.futures.wait(futures)

        for _, row in object_data.iterrows():
            in_path = Path(
                frame_path, f'{row["object_name"]}_{row["object_id"]}_[{row["time_seconds"]:1.3f}].jpg',
            )
            crop_frame(
                in_path, thumb_path, row["left"], row["top"], row["right"], row["bottom"]
            )
            # make a list of thumbs with the same object_id and object_name
            thumb_list = list(thumb_path.glob(f'{row["object_name"]}_{row["object_id"]}*.jpg'))
            # sort the list by timestamp
            thumb_list.sort(key=lambda x: float(x.stem.split('[')[-1].split(']')[0]))
            # copy the files to another dir in the tmp dir and rename as object_id_0001.jpg, object_id_0002.jpg, etc.
            Path(tmp_dir.name, 'renamed').mkdir(parents=True, exist_ok=True)
            for i, thumb in enumerate(thumb_list):
                shutil.copy(thumb, Path(tmp_dir.name, 'renamed', f'{row["object_id"]}_{i:04d}.jpg'))
            # merge the renamed thumbs into a gif
            subprocess.run(
                ['ffmpeg', '-framerate', '12', '-i', f'{tmp_dir.name}/renamed/{row["object_id"]}_%04d.jpg', '-y',
                 f'{out_dir}/{row["object_id"]}.gif'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pbar.update(1)


def extract_obj_gifs_parallel(in_dir: Path, out_dir: Path, data: pd.DataFrame):
    """
    Extracts object gifs from the video frames.
    :param in_dir:
    :param out_dir:
    :param data:
    :return:
    """
    tmp_dir = tempfile.TemporaryDirectory()
    out_dir.mkdir(parents=True, exist_ok=True)
    executor = concurrent.futures.ProcessPoolExecutor()
    pbar = tqdm(
        total=len(data["object_id"].unique()), desc="Extracting object gifs", smoothing=0
    )

    object_groups = data.groupby("object_id")

    for object_id in data["object_id"].unique():
        object_data = object_groups.get_group(object_id)
        object_name = object_data["object_name"].iat[0]
        object_id = object_data["object_id"].iat[0]
        video_path = find_video_by_id(object_data["id"].iat[0], in_dir)
        timestamps = object_data["time_seconds"].to_numpy()

        frame_path = Path(tmp_dir.name, 'frames')
        thumb_path = Path(tmp_dir.name, 'thumbs')

        frame_path.mkdir(parents=True, exist_ok=True)
        thumb_path.mkdir(parents=True, exist_ok=True)

        futures = [
            executor.submit(extract_frame, video_path, frame_path, timestamp, object_id, object_name)
            for timestamp in timestamps
        ]
        concurrent.futures.wait(futures)

        futures = [
            executor.submit(
                crop_frame,
                Path(frame_path, f'{row["object_name"]}_{row["object_id"]}_[{row["time_seconds"]:1.3f}].jpg'),
                thumb_path,
                row["left"],
                row["top"],
                row["right"],
                row["bottom"],
            )
            for _, row in object_data.iterrows()
        ]
        concurrent.futures.wait(futures)

        size_data = get_min_thumbs_size_data(thumb_path)
        crop_thumbs_to_normalised_size(thumb_path, thumb_path, size_data)

        futures = [
            executor.submit(
                merge_to_gif, out_dir, row, thumb_path, tmp_dir
            ) for _, row in object_data.iterrows()
        ]
        concurrent.futures.wait(futures)

        subprocess.run(
            ['ffmpeg', '-framerate', '12', '-i', f'{tmp_dir.name}/renamed/{object_id}_%04d.jpg', '-y',
             f'{out_dir}/{object_id}.gif'],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pbar.update(1)


def merge_to_gif(out_dir, row, thumb_path, tmp_dir):
    thumb_list = list(thumb_path.glob(f'{row["object_name"]}_{row["object_id"]}*.jpg'))
    # sort the list by timestamp
    thumb_list.sort(key=lambda x: float(x.stem.split('[')[-1].split(']')[0]))
    # copy the files to another dir in the tmp dir and rename as object_id_0001.jpg, object_id_0002.jpg, etc.
    Path(tmp_dir.name, 'renamed').mkdir(parents=True, exist_ok=True)
    for i, thumb in enumerate(thumb_list):
        shutil.copy(thumb, Path(tmp_dir.name, 'renamed', f'{row["object_id"]}_{i:04d}.jpg'))


def reject_outliers(data, m=2.0) -> List[int]:
    data = np.array(data)
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d / mdev if mdev else 0.0
    output = data[s < m]
    return output if len(output) > 1 else data


def get_meta_overlay(data: pd.DataFrame, entities: List[str]):
    entities = clean_user_input(entities)
    data = data[data["object_name"].isin(entities)]
    data = interpolate_missing_data(data)
    return data
