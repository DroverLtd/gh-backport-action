import argparse
import json
import os
import typing
import traceback
from datetime import datetime

from helpers import (
    _get_base_branch,
    _get_target_branch,
    _get_pr_number,
    git,
    github_get_commits_in_pr,
    github_open_pull_request,
    github_add_label_to_pr,
    git_setup,
    github_open_issue,
)


def release(initial_name: str, to_branch: str, pr_number: str):
    """
    Backport a list of commit on a *new* branch starting from to_branch.
    """
    new_branch = f"release-{initial_name[:15]}-{pr_number}-{to_branch}"
    git("switch", "-c", new_branch, "origin/" + initial_name)
    print(f"Switched to future branch: {new_branch}.")
#     try:
#         for commit_hash in commits:
#             git("cherry-pick", commit_hash)
#     except:
#         print("An error occurred while cherry-picking.")
#         raise RuntimeError("Could not cherry pick at least one commit automatically.")

    git("push", "-u", "origin", new_branch)
    return new_branch


def entrypoint(event_dict, pr_branch, gh_token, last_git_commit_message):
    base_branch = _get_base_branch(event_dict)
    pr_number = _get_pr_number(event_dict)

#     commits_to_backport = github_get_commits_in_pr(pr_number=pr_number, gh_token=gh_token)

#     print(f"found {len(commits_to_backport)} commits to release.")

    new_branch = release(base_branch, pr_branch, pr_number)

    # Truncate for PR title
    last_git_commit_message = last_git_commit_message.strip()
    pr_title = (last_git_commit_message[:75] + '..') if len(last_git_commit_message) > 75 else last_git_commit_message

    new_pr_number = github_open_pull_request(
        title=pr_title,
        head=new_branch,
        base=pr_branch,
        body=f"An automated release for #{pr_number}.",
        gh_token=gh_token,
    )
    github_add_label_to_pr(new_pr_number, pr_branch, gh_token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="automated release GH action.")
    parser.add_argument("pr_branch", type=str)
    parser.add_argument("github_token", type=str)
    parser.add_argument("last_git_commit_message", type=str)
    github_event_path = os.getenv("GITHUB_EVENT_PATH")

    with open(github_event_path, "r") as f:
        github_event = json.load(f)

    args = parser.parse_args()
    git_setup(args.github_token)
    try:
        entrypoint(
            event_dict=github_event,
            pr_branch=args.pr_branch,
            gh_token=args.github_token,
            last_git_commit_message=args.last_git_commit_message
        )
    except Exception as main_exception:
        main_traceback = traceback.format_exc()
        traceback_formatted_for_body = f"\n```python\n{main_traceback}```"
        try:
            pr_num = _get_pr_number(event_dict=github_event)
            title = f"Could not automatically release #{pr_num}"
            body = f"Exception occurred when trying to cherry-pick PR #{pr_num}.\nPlease cherry-pick it manually."
            body += traceback_formatted_for_body
            github_open_issue(title, body, gh_token=args.github_token)
            exit(1)
        except Exception:  # could not get pr number ; fallback on next try/except
            pass
        try:
            tar_branch = _get_target_branch(event_dict=github_event)
            title = f"Could not automatically release branch {tar_branch}"
            body = f"Exception occurred when trying to cherry-pick PR commits of `{tar_branch}`.\nPlease cherry-pick it manually."
            body += traceback_formatted_for_body

            github_open_issue(title, body, gh_token=args.github_token)
            exit(1)
        except Exception:  # could not get target branch; fallback on next try/except
            pass
        try:
            title = f"Automatic Backport failed"
            body = f"Exception occurred when trying to release a branch.\nCheck `actions` tab to see more."
            body += traceback_formatted_for_body
            github_open_issue(title, body, gh_token=args.github_token)
            exit(1)
        except Exception:  # could not create a github issue;
            print("Several Exceptions occurred:")
            print(traceback)
            print("--" * 8)
            print(traceback.format_exc())
            exit(1)
