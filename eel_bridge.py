"""Functions for creating and manipulating the project directory structure"""
import os
from pathlib import Path

import eel
import pandas as pd

from project import ensure_mismas

global project_dir
project_dir = None

eel.init('www')


@eel.expose
def get_projects():
    """Get list of projects from mismas directory, with info about how many files have been downloaded
    and how many have been saved in the youtube_report.csv"""
    mismas_dir = ensure_mismas()
    projects = []
    for project in os.listdir(mismas_dir):
        project_dir = os.path.join(mismas_dir, project)
        if os.path.isdir(project_dir):
            project_name = project
            if os.path.isfile(os.path.join(project_dir, 'youtube_report.csv')):
                youtube_report = pd.read_csv(os.path.join(project_dir, 'youtube_report.csv'))
                saved = len(youtube_report['id'].unique())
            else:
                saved = 0

            if os.path.isdir(os.path.join(project_dir, 'download')):
                downloaded = len(os.listdir(os.path.join(project_dir, 'download')))
            else:
                downloaded = 0

            projects.append({'project_name': project_name, 'downloaded': downloaded, 'saved': saved})

    return projects


@eel.expose
def new_project_handler(mismas_dir: Path) -> Path:
    """
    Create a new project folder
    :param mismas_dir: The root directory for Mismas
    :return project_dir: The selected project directory
    """
    while True:
        project_name = input('Enter project name: ')
        project_dir = Path(mismas_dir, project_name)

        try:
            project_dir.mkdir()
            print(f'Created project directory: {project_dir}')
            break
        except FileExistsError:
            print('There is already a project with that name')
    return project_dir


@eel.expose
def set_project_dir(input_string: str):
    mismas_dir = ensure_mismas()
    project_path = Path(mismas_dir, input_string)
    if not project_path.exists():
        raise FileNotFoundError(f'Project directory {project_path} does not exist')
    global project_dir
    project_dir = project_path
    report = pd.read_csv(os.path.join(project_dir, 'youtube_report.csv')).to_dict('records') if os.path.isfile(
        os.path.join(project_dir, 'youtube_report.csv')) else []
    return report


eel.start('main.html')
