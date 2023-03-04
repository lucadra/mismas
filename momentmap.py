import concurrent.futures
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import tqdm

import analysis
from utils import copy_visualiser_dir, find_video_by_id, serve_directory


def extract_playback_frames(project_dir: Path, data: pd.DataFrame):
    out_dir = project_dir / "momentmap" / "img"
    out_dir.mkdir(exist_ok=True, parents=True)
    commands = []

    for _, row in data.iterrows():
        in_path = find_video_by_id(row["id"], project_dir / "download")
        timestamp = (row["start_sec"] + row["end_sec"]) / 2
        out_path = out_dir / f"{row['id']}_{row['segment']}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            in_path.as_posix(),
            "-vframes",
            "1",
            "-q:v",
            "2",
            out_path,
        ]
        commands.append(cmd)

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(
                subprocess.run,
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            for cmd in commands
        ]

        for _ in tqdm.tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Extracting playback frames",
            unit="frames",
        ):
            pass


def serve_momentmap(project_dir: Path):
    print("momentmap")
    data_path = project_dir / "data" / "playback" / "merged.csv"

    try:
        data = pd.read_csv(data_path)
    except FileNotFoundError:
        import utils

        print("Playback data not found, running analysis on all downloaded videos...")
        video_ids = [utils.parse_id(v.stem) for v in project_dir.glob("download/*.mp4")]
        analysis.most_replayed(video_ids, project_dir)
        data = pd.read_csv(data_path)

    momentmap_dest = copy_visualiser_dir(project_dir, "momentmap")
    shutil.copy(
        project_dir / "data" / "playback" / "merged.csv",
        momentmap_dest / "data" / "playback_data.csv",
    )

    extract_playback_frames(project_dir, data)

    serve_directory(momentmap_dest)
