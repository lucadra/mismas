import concurrent.futures
import contextlib
import os
from pathlib import Path
from typing import List

import enquiries
import isodate
import pandas as pd
from googleapiclient.discovery import build
from pytube import YouTube, exceptions
from tqdm import tqdm

from utils import seconds_to_string


def find_txt_files(_dir, prompt):
    txt_files = [file for file in os.listdir(_dir) if file.endswith(".txt")]
    if not txt_files:
        raise Exception("No txt files found")
    if len(txt_files) == 1:
        file = txt_files[0]
    elif len(txt_files) > 1:
        file = enquiries.choose(prompt, txt_files)
    return os.path.join(_dir, file)


def parse_txt(_filepath):
    with open(_filepath, encoding="utf8") as f:
        lines = f.readlines()
        lines = [x.strip() for x in lines]
        f.close()
        if not lines:
            raise Exception("No URLs found in txt file")
    return lines


def get_api_key():
    with open(find_txt_files(os.path.join(os.getcwd(), 'credentials'), "Select API Key"), encoding="utf8") as f:
        _api_key = f.readline()
        f.close()
    return _api_key


def get_id_from_url(_url):
    return _url.split("=")[1]


def parse_duration(_duration):
    duration = isodate.parse_duration(_duration)
    return duration.total_seconds()


api_key = get_api_key()
youtube = build('youtube', 'v3', developerKey=api_key)


def compile_videos_report(_ids: List[str]) -> pd.DataFrame:
    report = []
    video_request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=_ids)

    video_response = video_request.execute()
    channels_ids = {video["snippet"]["channelId"] for video in video_response["items"]}

    channel_request = youtube.channels().list(
        part="snippet,contentDetails,statistics,contentOwnerDetails,topicDetails,brandingSettings",
        id=list(channels_ids))
    channel_response = channel_request.execute()
    for video in video_response["items"]:
        channel = next(
            (channel for channel in channel_response["items"] if channel["id"] == video["snippet"]["channelId"]), None)
        duration = parse_duration(video["contentDetails"]["duration"])
        report.append({
            "id": video.get("id", ""),
            "title": video.get("snippet", {}).get("title", ""),
            "duration": seconds_to_string(duration),
            "duration_seconds": "%3f" % duration,
            "channel": channel.get("snippet", {}).get("title", ""),
            "views": video.get("statistics", {}).get("viewCount", ""),
            "likes": video.get("statistics", {}).get("likeCount", ""),
            "favorites": video.get("statistics", {}).get("favoriteCount", ""),
            "comments": video.get("statistics", {}).get("commentCount", ""),
            "date": video.get("snippet", {}).get("publishedAt", ""),
            "licensed_content": video.get("contentDetails", {}).get("licensedContent", ""),
            "tags": video.get("snippet", {}).get("tags", ""),
            "description": video.get("snippet", {}).get("description", ""),
            "url": "https://www.youtube.com/watch?v=" + video.get("id", ""),
            "channel_creation_date": channel.get("snippet", {}).get("publishedAt", ""),
            "channel_views": channel.get("statistics", {}).get("viewCount", ""),
            "channel_subscribers": channel.get("statistics", {}).get("subscriberCount", ""),
            "channel_videos": channel.get("statistics", {}).get("videoCount", ""),
            "channel_country": channel.get("snippet", {}).get("country", ""),
            "channel_topic_categories": channel.get("topicDetails", {}).get("topicCategories", ""),
            "channel_keywords": channel.get("brandingSettings", {}).get("channel", {}).get("keywords", ""),
            "channel_description": channel.get("snippet", {}).get("description", ""),
            "channel_url": "https://www.youtube.com/channel/" + channel.get("id", ""),
        })

    return pd.DataFrame(report)


def get_video_ids_from_playlist(_id: str) -> List[str]:
    """
    Loads a playlist from a given URL. Playlist must be public
    :param _id: id of the playlist
    :return: list of video IDs
    """

    pbar = None
    result = youtube.playlistItems().list(part="snippet,contentDetails", playlistId=_id, maxResults=50).execute()
    ids = [item['snippet']['resourceId']['videoId'] for item in result['items']]
    if 'nextPageToken' in result:
        pbar = tqdm(total=int(result['pageInfo']['totalResults']), desc="Loading playlist")

    while len(ids) < result["pageInfo"]["totalResults"]:
        result = youtube.playlistItems().list(part="snippet,contentDetails", playlistId=_id,
                                              maxResults=50, pageToken=result['nextPageToken']).execute()
        new_ids = [item['snippet']['resourceId']['videoId'] for item in result['items']]
        ids.extend(new_ids)
        pbar.update(len(new_ids))

    return ids


def get_uploads_playlist_id(_id: str) -> str:
    """
    Loads a channel from a given URL. Channel must be public.
    :return: id of the uploads playlist for the given channel id
    """
    result = youtube.channels().list(part="snippet, contentDetails", id=_id).execute()
    return result['items'][0]['contentDetails']['relatedPlaylists']['uploads']


def find_channel_id(_query: str) -> str:
    """
    Returns the channel ID of the first search result for a given channel name
    The function may fail, but it's the best we can do since the API doesn't provide a way to retrieve channels
    by their public url. Best we can do is retrieve a channel by its Username, but the username is not always the same
    as the custom url. TODO: Add option to select channel with enqueries
    :param _query: Channel name
    :return: Channel ID
    """
    return youtube.search().list(part="snippet", q=_query, type="channel").execute()['items'][0]['id']['channelId']


def search_channel_id(_query: str) -> str:
    """
    Queries the API and prompts user to select a channel from the results
    :param _query: Channel name
    :return: Channel ID
    """
    channels = youtube.search().list(part="snippet", q=_query,
                                     type="channel").execute()  # ['items'][0]['id']['channelId']
    selected_channel = enquiries.choose("Select channel:",
                                        choices=[[channel['snippet']['title'], channel['id']['channelId']]
                                                 for channel in channels['items']], multi=False)
    return selected_channel[1]


def download_video(_id: str, _output_dir: str) -> str:
    """
    Downloads a video from a given ID
    :param _id: id of the video to download
    :param _output_dir: Directory where to save the video
    :return: Path of the downloaded video
    """
    yt = YouTube(f'https://www.youtube.com/watch?v={_id}')
    with contextlib.suppress(exceptions.LiveStreamError):
        yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first().download(
            _output_dir, filename=f'{yt.title}.mp4', filename_prefix=f"[{_id}]_", skip_existing=True)
    return os.path.join(_output_dir, f"[{_id}]_{yt.title}.mp4")


def download_videos(_ids: List[str], output_dir: Path) -> None:
    """
    Downloads videos of videos from a given list of URLs
    :param output_dir: directory where to save the videos
    :param _ids: List of YouTube ids of the videos to download
    :return:
    """
    output_dir.mkdir(exist_ok=True)
    pbar = tqdm(total=len(_ids), desc="Downloading videos")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_video, _id, output_dir.as_posix()) for _id in _ids]
        for _ in concurrent.futures.as_completed(futures):
            pbar.update(1)
