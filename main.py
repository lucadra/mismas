import enquiries
import os
from project import (analysis_handler, download_handler, edit_handler,
                     ensure_mismas, project_dir_handler, report_handler)

ACTIONS = {
    '[>] Generate Report': report_handler,
    '[>] Download': download_handler,
    '[>] Analyse': analysis_handler,
    '[>] Edit': edit_handler,
}


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Welcome to MISMAS')
    mismas_dir = ensure_mismas()
    project_dir = project_dir_handler(mismas_dir)
    menu = ['[>] Generate Report', '[>] Download', '[>] Analyse', '[>] Edit', '[x] Exit']
    while True:
        choice = enquiries.choose(prompt='What do you want to do?',
                                  choices=menu,
                                  multi=False)
        if choice == '[x] Exit':
            break
        else:
            ACTIONS[choice](project_dir)


if __name__ == '__main__':
    main()
