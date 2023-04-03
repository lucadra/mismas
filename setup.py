import os
import subprocess
import venv


def get_installed_packages():
    pip_executable = os.path.join('venv', 'Scripts', 'pip3.exe') if os.name == 'nt' else os.path.join('venv', 'bin', 'pip3')
    installed_packages = subprocess.check_output([pip_executable, 'list']).decode('utf-8')
    installed_packages = installed_packages.strip().split('\n')
    installed_packages = installed_packages[2:]
    return installed_packages


def create_venv():
    print('Creating virtual environment...')
    venv.create(os.path.join('venv'), with_pip=True)
    installed_packages = get_installed_packages()
    print('Installing required packages...')
    with open('requirements.txt', 'r') as f:
        required_packages = f.read()
    for package in required_packages.splitlines():
        package_name = package.split('==')[0]
        if not any((package_name == line.split('==')[0]) or (package_name in line) for line in installed_packages):
            print(f"Installing \033[1m{package_name}\033[0m...")
            pip_executable = os.path.join('venv', 'Scripts', 'pip3.exe') if os.name == 'nt' else os.path.join('venv', 'bin', 'pip3')
            subprocess.run([pip_executable, 'install', package])
        else:
            print(f"\033[32m{package_name} already installed \u2713\033[0m")
    # Make mismas.sh executable, bat file should already be executable
    os.chmod('mismas.sh', 0o755)


def run_main():
    python_executable = os.path.join('venv', 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join('venv', 'bin', 'python3')
    print('Initialising MISMAS...')
    subprocess.run([python_executable, 'main.py'], shell=True)


if __name__ == '__main__':
    create_venv()
    run_main()
