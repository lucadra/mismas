import concurrent.futures
import re
import subprocess
from pathlib import Path

import pandas as pd
import spacy
from tqdm import tqdm

import analysis
from utils import copy_visualiser_dir, find_video_by_id, serve_directory

en = spacy.load("en_core_web_trf")
stopwords = en.Defaults.stop_words

## TODO: Fix this, if i do i'll probably be able to rid of the trf model and go back to web_sm
## Big issue here is that we need a complete continuous text to get good results
## from stemming, so i will need to find a way to feed it the whole text and
## then match stemmed words to the original ones


def extract_reelchart_frames(data: pd.DataFrame, project_dir: Path, segments=20):
    in_dir = project_dir / "download"
    out_dir = project_dir / "reelchart" / "img"
    out_dir.mkdir(exist_ok=True, parents=True)

    clip_data_groups = data.groupby("id")
    commands = []

    for id, clip_data in clip_data_groups:
        clip_duration = clip_data.iloc[-1]["end_sec"] - clip_data.iloc[0]["start_sec"]
        segment_duration = clip_duration / segments
        timestamps = [segment_duration * i for i in range(segments)]
        video = find_video_by_id(id, in_dir)

        commands.extend(
            [
                [
                    "ffmpeg",
                    "-ss",
                    str(timestamp),
                    "-i",
                    str(video),
                    "-vf",
                    "scale=-1:100,format=yuv420p",
                    "-vframes",
                    "1",
                    "-y",
                    str(out_dir / f"{id}_{i}.jpg"),
                ]
                for i, timestamp in enumerate(timestamps)
            ]
        )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                subprocess.run,
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            for command in commands
        ]

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            desc="Processing frames",
            total=len(futures),
        ):
            future.result()


def process_word(word: str) -> str:
    if not word:
        return ""
    doc = en(word)
    if doc[0].pos_ != "PROPN":
        word = doc[0].lemma_
    if word in stopwords:
        return ""
    word = re.sub(r"[.,?!;:]", "", word.lower())
    return "" if word == "i" else word


def process_clip(clip_data, id, timestamps, segment_duration, data_out):
    for i, timestamp in enumerate(timestamps):
        segment_data = clip_data[
            (clip_data["start_sec"] >= timestamp)
            & (clip_data["end_sec"] <= timestamp + segment_duration)
        ]
        for _, row in segment_data.iterrows():
            datum = {
                "id": id,
                "segment": i,
                "word": row["word"],
                "start_sec": row["start_sec"],
            }
            data_out.append(datum)


def make_reelchart_table_with_reference(
    data: pd.DataFrame, segments=20
) -> pd.DataFrame:
    tqdm.pandas(desc="Lemmatising words", unit="word", smoothing=0.1)
    data["word"] = data["word"].progress_apply(process_word)
    data = data.dropna()
    clip_data_groups = data.groupby("id")

    pbar = tqdm(
        total=len(data["id"].unique()),
        desc="Building reelchart table",
        unit="clip",
        smoothing=0.1,
    )
    data_out = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for id in data["id"].unique():
            clip_data = clip_data_groups.get_group(id)
            clip_duration = (
                clip_data.iloc[-1]["end_sec"] - clip_data.iloc[0]["start_sec"]
            )
            segment_duration = clip_duration / segments
            timestamps = [segment_duration * i for i in range(segments)]
            futures.append(
                executor.submit(
                    process_clip, clip_data, id, timestamps, segment_duration, data_out
                )
            )

        for future in concurrent.futures.as_completed(futures):
            pbar.update(1)
            future.result()

    data_out = [datum for datum in data_out if datum["word"]]
    return pd.DataFrame(data_out)


def serve_reelchart(project_dir: Path):
    data_path = project_dir / "data" / "transcription" / "merged.csv"

    try:
        data = pd.read_csv(data_path)
    except FileNotFoundError:
        import utils
        print(
            "Speech Transcription data not found, running analysis on all downloaded videos..."
        )
        video_ids = [utils.parse_id(v.stem) for v in project_dir.glob("download/*.mp4")]
        analysis.batch_annotate_from_ids(video_ids, "transcription", project_dir)
        data = pd.read_csv(data_path)

    visualiser_name = "reelchart"
    reelchart_dest = copy_visualiser_dir(project_dir, visualiser_name)

    reelchart_data = make_reelchart_table_with_reference(data)
    reelchart_data.to_csv(reelchart_dest / "data" / "speech_data.csv", index=False)
    extract_reelchart_frames(data, project_dir)

    serve_directory(reelchart_dest)
