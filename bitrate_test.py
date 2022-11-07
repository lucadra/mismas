import os
import subprocess
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from analysis import most_replayed
from utils import find_video_by_id, uniquify, map_to_range

video_id = '5F1LC4QmkRA'

most_replayed([video_id], Path(os.getcwd()))

df_path = Path('/home/luca/PycharmProjects/mismas/data/playback/5F1LC4QmkRA.csv')
df = pd.read_csv(df_path)
in_dir = Path('/home/luca/mismas/J6_BBC/download')
out_dir = Path(os.getcwd()) / 'variable_bitrate'


def extract_shots_with_variable_bitrate(_df: pd.DataFrame, in_dir: Path, out_dir: Path, text: str = False):
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
        bitrate = map_to_range(row['score'], [0, 1], [500000, 4000000000])
        crf = 52 - 30 ** row['score']
        # crf = map_to_range(row['score'], [df.score.min(), df.score.max()], [51, 30])
        crf = str(int(crf))
        buffer = bitrate * 2
        # v_bitrate = (3000000 * row['score']) if (3000000 * row['score']) > 450000 else 0.0001*8000000
        # a_bitrate = (320000 * row['score']) if (320000 * row['score']) > 45000 else 0.001*320000
        # v_bitrate, a_bitrate = str(int(v_bitrate)), str(int(a_bitrate))
        min_rate = bitrate if -2.14748e+09 < bitrate < 2.14748e+09 else 2.14748e+09
        max_rate = bitrate if 0 < bitrate < 2.14748e+09 else 2.14748e+09
        buffer = buffer if -2.14748e+09 < buffer < 2.14748e+09 else 2.14748e+09
        min_rate = str(int(min_rate))
        max_rate = str(int(max_rate))
        bitrate = str(int(bitrate))
        buffer = str(int(buffer))

        if start == end:
            continue
        in_path = filename.resolve().as_posix()
        out_path = uniquify(os.path.join(out_dir.as_posix(), f"{video_id}.mp4"))
        command = ["ffmpeg"]
        options = ["-i", in_path, "-ss", start, "-to", end, "-y", "-movflags",
                   "faststart", "-avoid_negative_ts", "1", "-c:v", "libx264", "-preset", "medium", "-crf", crf,
                   out_path]

        if text:
            text_filter = ["drawtext=", "fontfile=Inter-Regular.ttf:", f"text='{entity}':",
                           "fontcolor=white:", "fontsize=24:", "box=1:", "boxcolor=black@0.5:", "boxborderw=5:",
                           "x=(w-text_w)/2:", "y=24"]
            filter_args = "".join(text_filter)
            options.insert(6, "-vf")
            options.insert(7, filter_args)

        args = command + options
        operation = subprocess.run(args, stdout=subprocess.DEVNULL)
        print(args)
        if operation.returncode != 0:
            print(operation.stderr)
            raise RuntimeError("Ué uagliù è succiess un guaio mentre tagliavo i video, liv 'a miezz "
                               "'stderr=subprocess.DEVNULL' e vir nu poc ch'è succiess")


extract_shots_with_variable_bitrate(df, in_dir, out_dir, text='score')

from output import merge_shots

merge_shots(out_dir, Path(os.getcwd()) / 'merged')
