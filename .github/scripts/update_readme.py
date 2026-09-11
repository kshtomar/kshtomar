#!/usr/bin/env python3
"""
Automated script to update dynamic sections in README.md:
- Recent GitHub public activity
- (Optional) Blog posts from an RSS feed
- Last updated timestamp
"""

import os
import re
import datetime
import urllib.request
import json
import xml.etree.ElementTree as ET

GITHUB_USERNAME = "kshtomar"
README_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "README.md")
BLOG_RSS_URL = os.environ.get("BLOG_RSS_URL", "")  # Can be set as repo secret / env var in the future


def fetch_github_activity(username, max_events=5):
    url = f"https://api.github.com/users/{username}/events/public"
    headers = {
        "User-Agent": f"profile-readme-updater-{username}",
        "Accept": "application/vnd.github.v3+json"
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching GitHub events: {e}")
        return None

    items = []
    seen = set()

    for event in data:
        event_type = event.get("type")
        repo = event.get("repo", {})
        repo_name = repo.get("name", "")
        repo_url = f"https://github.com/{repo_name}"
        created_at = event.get("created_at", "")[:10]

        line = None
        key = (event_type, repo_name)

        if event_type == "PushEvent":
            commits = event.get("payload", {}).get("commits", [])
            commit_count = len(commits)
            if commit_count > 0:
                first_msg = commits[0].get("message", "").split("\n")[0]
                if len(first_msg) > 60:
                    first_msg = first_msg[:57] + "..."
                first_msg = first_msg.replace("`", "")
                line = f"🔨 Pushed {commit_count} commit{'s' if commit_count > 1 else ''} to [`{repo_name}`]({repo_url}) ({created_at})"
        elif event_type == "PullRequestEvent":
            payload = event.get("payload", {})
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            pr_title = pr.get("title", "")
            pr_url = pr.get("html_url", repo_url)
            line = f"🔀 {action.capitalize()} PR [#{pr.get('number')} {pr_title}]({pr_url}) in [`{repo_name}`]({repo_url}) ({created_at})"
        elif event_type == "IssuesEvent":
            payload = event.get("payload", {})
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            issue_title = issue.get("title", "")
            issue_url = issue.get("html_url", repo_url)
            line = f"⚠️ {action.capitalize()} issue [#{issue.get('number')} {issue_title}]({issue_url}) in [`{repo_name}`]({repo_url}) ({created_at})"
        elif event_type == "WatchEvent":
            line = f"⭐ Starred [`{repo_name}`]({repo_url}) ({created_at})"
        elif event_type == "CreateEvent":
            ref_type = event.get("payload", {}).get("ref_type", "repo")
            ref_name = event.get("payload", {}).get("ref", "")
            if ref_type == "repository":
                line = f"🎉 Created repository [`{repo_name}`]({repo_url}) ({created_at})"
            elif ref_type == "branch":
                line = f"🌿 Created branch `{ref_name}` in [`{repo_name}`]({repo_url}) ({created_at})"
        elif event_type == "ForkEvent":
            forkee = event.get("payload", {}).get("forkee", {})
            fork_url = forkee.get("html_url", repo_url)
            line = f"🍴 Forked [`{repo_name}`]({repo_url}) ({created_at})"

        if line and key not in seen:
            seen.add(key)
            items.append(line)
            if len(items) >= max_events:
                break

    return items


def fetch_blog_posts(feed_url, max_posts=4):
    if not feed_url:
        return None
    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "profile-blog-updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        posts = []
        # Support both RSS and Atom
        channel = root.find("channel")
        if channel is not None:
            # RSS 2.0
            for item in channel.findall("item")[:max_posts]:
                title = item.findtext("title", "Untitled").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "")[:16]
                posts.append(f"- 📝 [{title}]({link}) *({pub_date})*")
        else:
            # Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:max_posts]:
                title = entry.findtext("atom:title", namespaces=ns, default="Untitled").strip()
                link_elem = entry.find("atom:link", ns)
                link = link_elem.attrib.get("href", "") if link_elem is not None else ""
                published = entry.findtext("atom:published", namespaces=ns, default="")[:10]
                posts.append(f"- 📝 [{title}]({link}) *({published})*")
        return posts
    except Exception as e:
        print(f"Error fetching blog feed: {e}")
        return None


def replace_section(content, start_tag, end_tag, replacement):
    pattern = re.compile(
        f"({re.escape(start_tag)})(.*?)({re.escape(end_tag)})",
        re.DOTALL
    )
    if not pattern.search(content):
        print(f"Warning: Marker {start_tag} ... {end_tag} not found.")
        return content
    return pattern.sub(f"\\1\n{replacement.strip()}\n\\3", content)


def main():
    if not os.path.exists(README_PATH):
        print(f"README file not found at {README_PATH}")
        return

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    # 1. Update Recent Activity
    activities = fetch_github_activity(GITHUB_USERNAME)
    if activities:
        activity_md = "\n".join(f"- {act}" for act in activities)
    else:
        activity_md = "- 🚀 Actively coding & building projects on GitHub! Check out my pinned repositories above."

    readme = replace_section(
        readme,
        "<!-- START_SECTION:activity -->",
        "<!-- END_SECTION:activity -->",
        activity_md
    )

    # 2. Update Blog section (if available)
    if BLOG_RSS_URL:
        posts = fetch_blog_posts(BLOG_RSS_URL)
        if posts:
            blog_md = "\n".join(posts)
        else:
            blog_md = "*Articles coming soon! Stay tuned.*"
        readme = replace_section(
            readme,
            "<!-- START_SECTION:blog -->",
            "<!-- END_SECTION:blog -->",
            blog_md
        )

    # 3. Update Timestamp
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    timestamp_md = f"⚡ *Automated profile layers running via GitHub Actions • Last synced: {now_utc}*"
    readme = replace_section(
        readme,
        "<!-- START_SECTION:updated_at -->",
        "<!-- END_SECTION:updated_at -->",
        timestamp_md
    )

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print("Successfully updated README.md")


if __name__ == "__main__":
    main()
