import os
import re
import subprocess
from functools import reduce
from pathlib import Path
import string
import numpy as np
import socket
import webbrowser
import http.server
import shutil

def get_filename(_path):
    return os.path.basename(_path).split('.')[0]


def parse_id(_path: str) -> str:
    try:
        idx = re.findall(r'\[(.*?)\]', _path)[0]
    except IndexError:
        idx = ''
    return idx


def ensure_dir(_dir: str) -> str:
    """Check directory exists, if not create it"""
    dir_path = os.path.join(os.getcwd(), _dir)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def seconds_to_string(t: float) -> str:
    return "%02d:%02d:%02d.%03d" % reduce(lambda ll, b: divmod(ll[0], b) + ll[1:], [(round(t * 1000),), 1000, 60, 60])


def uniquify(_path):
    filename, extension = os.path.splitext(_path)
    counter = 1
    if not os.path.exists(f"{filename}_{str(counter).zfill(3)}{extension}"):
        unique_path = f"{filename}_{str(counter).zfill(3)}{extension}"
    else:
        while os.path.exists(f"{filename}_{str(counter).zfill(3)}{extension}"):
            counter += 1
            _path = f"{filename}_{str(counter).zfill(3)}{extension}"
        unique_path = _path

    return unique_path


def check_category(_annotation):
    try:
        category = [item['description'] for item in _annotation['categoryEntities']]
    except KeyError:
        category = ['n/a']

    return ','.join(category) if len(category) > 1 else category[0]


def ensure_coords(left, top, right, bottom):
    left = 0 if left is None else left
    top = 0 if top is None else top
    right = 0 if right is None else right
    bottom = 0 if bottom is None else bottom
    return max(left, 0), max(top, 0), min(right, 1), min(bottom, 1)


def clean_user_input(user_input):
    """Ensure the arg passed to the function is an array of strings"""
    user_input = user_input if type(user_input) == list else user_input.split(',') if ',' in user_input else [
        user_input]
    return [item.lower().strip() for item in user_input]


def find_video_by_id(video_id: str, in_dir: Path) -> Path:
    """
    Find video by id
    :param video_id: video id
    :param in_dir: directory to search in
    :return: video filename
    """
    return next(file_path for file_path in in_dir.glob('*.mp4') if video_id in file_path.name)


def find_longest_video(in_dir: Path) -> Path:
    durations = np.array([float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                                                'default=noprint_wrappers=1:nokey=1', video.as_posix()],
                                               stdout=subprocess.PIPE).stdout) for video in in_dir.glob('*.mp4')])
    return list(in_dir.glob('*.mp4'))[durations.argmax()]


def ensure_even(n: int):
    return n if n % 2 == 0 else n - 1


def map_to_range(n, domain, range):
    return range[0] + (n - domain[0]) * (range[1] - range[0]) / (domain[1] - domain[0])


def sanitize_video_title(title: str, max_len: int = 26) -> str:
    path = Path(title.strip())
    path = path.with_name(re.sub(r'\s+', '-', path.name))
    path = path.with_name(path.name.replace('.', ''))
    valid_chars = f"-_.{string.ascii_letters}{string.digits}"
    new_name = ''.join(c for c in path.stem if c in valid_chars)
    new_name = re.sub(r'-+', '-', new_name)
    new_name = new_name.lstrip('-')
    path = path.with_stem(new_name)
    if len(path.name) > max_len:
        extension = path.suffix
        path = path.with_name(path.name[:max_len-len(extension)-1] + extension)
    return path.name


def copy_visualiser_dir(project_dir, visualiser_name):
    visualiser_source = Path(f'visualisers/{visualiser_name}')
    visualiser_dest = project_dir / visualiser_name
    shutil.copytree(visualiser_source, visualiser_dest, dirs_exist_ok=True)
    shutil.copy(project_dir / 'youtube_report.csv', visualiser_dest / 'data')
    return visualiser_dest


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


def serve_directory(dir_path) -> None:
    port = 8000
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                s.listen(1)
                break
        except OSError:
            port += 1

    

    print(f"Serving at http://localhost:{port}, press Ctrl+C to stop")

    os.chdir(dir_path)
    ## No-Cache headers are needed to avoid loading cached files from another run
    httpd = http.server.HTTPServer(('localhost', port), NoCacheHTTPRequestHandler)
    webbrowser.open(f'http://localhost:{port}')
    httpd.serve_forever()


#####################################GRAVEYARD############################################

def set_background(vid_path):
    resolution = subprocess.run(
        ["ffprobe", "-v",
         "error",
         "-select_streams",
         "v:0",
         "-show_entries",
         "stream=width,height",
         "-of",
         "csv=s=x:p=0",
         vid_path,
         ],
        stdout=subprocess.PIPE,
    )
    resolution = resolution.stdout.decode("utf-8").strip().split("x")
    resolution = [int(res) for res in resolution]
    command = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x7F7F7F:s={resolution[0]}x{resolution[1]}:r=20",
        "-i",
        vid_path,
        "-shortest",
        "-filter_complex",
        "[1:v]chromakey=0x00FF00:0.2:0.1[ckout];[0v][ckout]overlay=shortest=1[out]",
        "-map",
        "[out]",
        "-y",
        uniquify(vid_path),
    ]
    subprocess.run(command)
