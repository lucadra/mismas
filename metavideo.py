import json
import subprocess
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
from PIL import Image
from rectpack import newPacker

from utils import find_longest_video, ensure_even


def get_min_thumbs_size_data(in_dir: Path) -> List[dict]:
    """
    Get the minimum size of the thumbnails for each object
    :param in_dir: directory where to find the thumbnails
    :return: dictioanry with object_id as key and (width, height) as value
    """
    object_data = []
    for file in in_dir.glob("*.jpg"):
        object_id = file.stem.split("_")[1]
        width, height = Image.open(file).size
        object_data.append(
            {"object_id": object_id, "width": width, "height": height}
        )
    object_data = pd.DataFrame(object_data)
    object_data = object_data.groupby("object_id").agg({"width": "min", "height": "min"})
    object_data.insert(0, 'object_id', object_data.index)
    return object_data.to_dict(orient="records")


def crop_thumbs_to_normalised_size(in_dir: Path, out_dir: Path, size_data: List[dict]) -> None:
    out_dir.mkdir(exist_ok=True)
    for object_id in size_data:
        min_w = object_id["width"]
        min_h = object_id["height"]
        min_w, min_h = ensure_even(min_w), ensure_even(min_h)
        for file in in_dir.glob(f"*_{object_id['object_id']}_*.jpg"):
            img = Image.open(file)
            w, h = img.size
            if w > min_w or h > min_h:
                left = (w - min_w) // 2
                right = left + min_w
                top = (h - min_h) // 2
                bottom = top + min_h
                img = img.crop((left, top, right, bottom))
                img.save(Path(out_dir, file.name).as_posix())


def merge_normalised_thumbs_to_vid(in_dir: Path, out_dir: Path, size_data: List[dict]) -> None:
    out_dir.mkdir(exist_ok=True)
    for item in size_data:
        pattern = Path(in_dir, f"*_{item['object_id']}_*").with_suffix(".jpg").as_posix()
        out_path = Path(out_dir, f"{item['object_id']}").with_suffix(".mp4").as_posix()
        cmd = ['ffmpeg', '-framerate', '20', '-pattern_type', 'glob', '-i', pattern,
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-b', '4M', '-y', out_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_position_data(size_data: list, **kwargs) -> List[dict]:
    """Get position data for each video in the input directory
    :param kwargs: resolution=HORIZONTALxVERTICAL size of the output video
    :return: list of dicts with position data for each video
    """
    bins = [(1280, 720)] if 'resolution' not in kwargs else [tuple(int(x) for x in kwargs["resolution"].split("x"))]
    rects = [(file['width'], file['height']) for file in size_data]
    packer = newPacker(rotation=False)

    for r in rects:
        packer.add_rect(*r)
    for b in bins:
        packer.add_bin(*b)
        packer.pack()

    position_data = []
    for rect in packer[0]:
        for item in size_data:
            if item['width'] == rect.width and item['height'] == rect.height:
                position_data.append(
                    {"filepath": item['object_id'], "x": rect.x, "y": rect.y + rect.height}
                )

    return position_data


# What happens when longest video is not in position_data?
# ideally, we should output a video for each bin
# that could be a loop in position data that makes a new bin until len(videos in folder) == len(position_data)
def merge_to_grid(in_dir: Path, out_dir: Path, position_data: List[dict], **kwargs) -> None:
    """
    Merge all the videos in the input directory to a single video
    :param in_dir: directory where to find the videos
    :param out_dir: directory where to save the output video
    :param kwargs: resolution=HORIZONTALxVERTICAL size of the output video
    :return: None
    """
    resolution = (1280, 720) if 'resolution' not in kwargs else tuple(int(x) for x in kwargs["resolution"].split("x"))
    out_dir.mkdir(exist_ok=True)
    base_command = ['ffmpeg', '-f', 'lavfi', '-i', f'color=c=0x7F7F7F:s={resolution[0]}x{resolution[1]}:r=20']

    longest_video = find_longest_video(in_dir)
    print(f"Longest video: {longest_video}")
    longest_video_data = next((item for item in position_data if item["filepath"] == longest_video.stem), None)
    print(f"Longest video data: {longest_video_data}")
    position_data = [item for item in position_data if item["filepath"] != longest_video.stem]

    longest_video_input = ['-i', longest_video.as_posix()]
    inputs = [['-i', Path(in_dir, f"{item['filepath']}").with_suffix(".mp4").as_posix()] for item in position_data]
    inputs = longest_video_input + [item for sublist in inputs for item in sublist]

    overlay_options = [
        f'[0:v][1:v]overlay=shortest=1:x={longest_video_data["x"]}:y=main_h-{longest_video_data["y"]}[v0];']
    overlay_options.extend(
        f'[v{i}][{i + 2}:v]overlay=x={position_data[i]["x"]}:y=main_h-{position_data[i]["y"]}[v{i + 1}];' for
        i in range(len(position_data) - 1))
    overlay_options = ''.join(overlay_options).strip(';')

    export_options = ['-map', f'[v{len(position_data) - 1}]', '-y', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-b:v',
                      '4M',
                      Path(out_dir, f"{longest_video.stem}_grid").with_suffix(".mp4").as_posix()]

    cmd = [*base_command, *inputs, '-filter_complex', overlay_options, *export_options]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_metagrid(in_dir: Path, out_dir: Path):
    with tempfile.TemporaryDirectory() as temp_dir:
        size_data = get_min_thumbs_size_data(in_dir)
        crop_thumbs_to_normalised_size(in_dir, Path(temp_dir, 'thumbs'), size_data)
        merge_normalised_thumbs_to_vid(Path(temp_dir, 'thumbs'), Path(temp_dir, 'vids'), size_data)
        position_data = get_position_data(size_data)
        json.dump(position_data, open(Path('position_data.json'), 'w'))
        merge_to_grid(Path(temp_dir, 'vids'), out_dir, position_data)
        print("Done!")
