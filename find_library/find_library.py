import subprocess
import tempfile
from pathlib import Path
import requests
from config import GITLAB_URL, GROUP_PATH, TOKEN, LIBRARY, FILE_EXCLUDE

# ====== CONFIGURATION ======
# GITLAB_URL = "xxxxx"
# GROUP_PATH = "xxxx"         # the group to search
# TOKEN = "xxxxx"             # GitLab personal access token
# LIBRARY = "xxxxx"           # library to search
# FILE_EXCLUDE = "path/to/file"
# ===========================

def get_group_repos():
    """Get all SSH repo URLs in the GitLab group."""
    repos = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/groups/{GROUP_PATH}/projects"
        params = {"per_page": 100, "page": page, "include_subgroups": "true"}
        headers = {"PRIVATE-TOKEN": TOKEN}
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend([proj["ssh_url_to_repo"] for proj in data])
        page += 1
    return repos

def check_requirements(repo_url, library, exclude_file=FILE_EXCLUDE):
    proj_name = Path(repo_url).stem
    found_lines = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(["git", "init"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL)

            subprocess.run(
                ["git", "fetch", "--depth", "1", "origin", "HEAD:refs/remotes/origin/HEAD"],
                cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # list all files to find requirements.txt in any folder
            ls_result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", "origin/HEAD"],
                cwd=tmp_dir, check=True, stdout=subprocess.PIPE, text=True
            )

            files = [f for f in ls_result.stdout.splitlines() if f.endswith("requirements.txt")]

            for file in files:
                subprocess.run(
                    ["git", "checkout", "origin/HEAD", "--", file],
                    cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

                req_path = Path(tmp_dir) / file
                if req_path.exists():
                    try:
                        with open(req_path, "r", encoding="utf-8-sig") as f:
                            lines = f.readlines()
                    except UnicodeDecodeError:
                        with open(req_path, "r", encoding="latin-1") as f:
                            lines = f.readlines()

                    for line in lines:
                        if line.strip().startswith(library):
                            found_lines.append(f"{file}: {line.strip()}")
        except subprocess.CalledProcessError:
            pass

    if found_lines:
        print(f"{proj_name}:")
        for line in found_lines:
            print(f"  {line}")
    else:
        print(f"{proj_name}: not found → adding to {FILE_EXCLUDE}")
        with open(exclude_file, "a") as f:
            f.write(proj_name + "\n")

def load_excluded_projects(filename=FILE_EXCLUDE):
    try:
        with open(filename, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()

def main():
    repos = get_group_repos()
    excluded = load_excluded_projects()

    print("Checking projects (skipping excluded ones):")
    for repo in repos:
        proj_name = Path(repo).stem
        if proj_name in excluded:
            print(f" - {proj_name} (skipped)")
            continue
        print(f" - {proj_name}")
    print("\nResults:")

    for repo in repos:
        proj_name = Path(repo).stem
        if proj_name in excluded:
            continue
        check_requirements(repo, LIBRARY)

if __name__ == "__main__":
    main()