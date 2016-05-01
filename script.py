import os
import re
import praw
import requests
import time

# This bot will:
#  * Locally save all posts on some subreddit A
#  * If any post from subreddit A is crossposted on some subreddit B,
#    the original content of the post will be commented on the crosspost
#    in case the original was/is deleted.

SECONDS_IN_DAY = 86400

# Account settings (private)
USERNAME = ''
PASSWORD = ''

# OAuth settings (private)
CLIENT_ID = ''
CLIENT_SECRET = ''
REDIRECT_URI = 'http://127.0.0.1:65010/authorize_callback'

# Configuration Settings
USER_AGENT = "Bestof archiver | maintained by "+MAINTAINER
AUTH_TOKENS = ["identity","read","submit"]
EXPIRY_BUFFER = 60

# Bot-specific Settings
MAINTAINER = "/u/MAINTAINER_HERE" # The person to contact about bot issues
SUBREDDIT_A = "legaladvice"           # The subreddit from which to archive
SUBREDDIT_B = "bestoflegaladvice"     # The subreddit to which to mirror
DIR_POSTS = "archive"       # Directory in which to store archives

REPLY_TEMPLATE = "**Initial post:** \n\n{body}\n\n*****\n\
I am a bot. [Report issues](https://www.reddit.com/message/compose/?to="+MAINTAINER+")"

def get_session_data():
    response = requests.post("https://www.reddit.com/api/v1/access_token",
      auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
      data = {"grant_type": "password", "username": USERNAME, "password": PASSWORD},
      headers = {"User-Agent": USER_AGENT})
    response_dict = dict(response.json())
    response_dict['retrieved_at'] = time.time()
    return response_dict

def get_praw():
    r = praw.Reddit(USER_AGENT)
    r.set_oauth_app_info(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    session_data = get_session_data()
    r.set_access_credentials(set(AUTH_TOKENS), session_data['access_token'])
    return (r, session_data)

def main(r, session_data):
    EXPIRES_AT = session_data['retrieved_at'] + session_data['expires_in']
    while True:
        if time.time() >= EXPIRES_AT - EXPIRY_BUFFER:
            raise praw.errors.OAuthInvalidToken
        sub_a = r.get_subreddit(SUBREDDIT_A)
        posts_a = sub_a.get_new(limit=50)
        for post in posts_a:
            post_store(post)
        
        sub_b = r.get_subreddit(SUBREDDIT_B)
        posts_b = sub_b.get_new(limit=50)
        for post in posts_b:
            if post.is_self:
                continue
            ref_post = post_get(post.url)
            if ref_post is not None and not already_replied(post):
                post.add_comment(REPLY_TEMPLATE.format(body=ref_post))
        
        time.sleep(20)

def already_replied(post):
    for comment in post.comments:
        if comment.author is None:
            continue
        if comment.author.name.lower() == USERNAME.lower():
            return comment
    return None
    
def post_get(url):
    m = re.search("/comments/([^/]+)/", url)
    if m is None or len(m.groups()) == 0:
        return None
    pid = m.groups()[0]
    
    postfile = os.path.join(DIR_POSTS, pid)
    if not os.path.isfile(postfile):
        return None
    with open(postfile) as f:
        data = f.read()

    if len(data) == 0:
        return None
    return data
    
def post_store(post):
    postfile = os.path.join(DIR_POSTS, post.id)
    if not post.is_self:
        return
        
    post_text = post.selftext.encode("utf-8")
    if not os.path.exists(postfile):
        with open(postfile, "w") as f:
            f.write(post_text)

if __name__ == "__main__":
    while True:
        try:
            print("Retrieving new OAuth token...")
            main(*get_praw())
        except praw.errors.OAuthInvalidToken:
            print("OAuth token expired.")
        except praw.errors.HTTPException:
            print("HTTP error. Retrying in 10...")
            time.sleep(10)
