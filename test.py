import json
import sys
import textwrap
from pathlib import Path
from datetime import datetime

from linkedin_api import Linkedin
from requests.cookies import cookiejar_from_dict

cookies = cookiejar_from_dict(
    {
        "liap": "true",
        "li_at": sys.argv[1],
        "JSESSIONID": sys.argv[2],
    }
)
linkedin = Linkedin("", "", cookies=cookies)

convo_cache_path = Path("convocache.json")
if convo_cache_path.exists():
    print("Using convocache.json")
    with open(convo_cache_path) as f:
        convos = json.load(f)
else:
    convos = linkedin.get_conversations()

    with open(convo_cache_path, "w+") as convocache:
        json.dump(convos, convocache, sort_keys=True, indent=2)

thread_cache_path = Path("threadcache.json")
threads = {}
if thread_cache_path.exists():
    print("Using threadcache.json")
    with open(thread_cache_path) as f:
        threads = json.load(f)


def get_path(obj, *path):
    v = obj
    for k in path:
        v = v.get(k, {})
    return v


for convo in convos["elements"]:
    print("=" * 100)
    participants = convo.get("participants", [])
    print("Participants:")
    for p in participants:
        profile = get_path(
            p, "com.linkedin.voyager.messaging.MessagingMember", "miniProfile"
        )
        if profile is not None:
            print("  {} {}".format(profile.get("firstName"), profile.get("lastName")))

            picture = get_path(profile, "picture", "com.linkedin.common.VectorImage")
            pictureArtifacts = picture.get("artifacts", [])
            if len(pictureArtifacts) > 0:
                print(
                    "    {}{}".format(
                        picture.get("rootUrl"),
                        pictureArtifacts[0].get("fileIdentifyingUrlPathSegment"),
                    )
                )

    print("Thread")
    urn = convo["entityUrn"].split(":")[-1]

    if urn in threads:
        thread = threads[urn]
    else:
        thread = linkedin.get_conversation(urn)
        threads[urn] = thread

    for element in thread.get("elements", []):
        time = datetime.utcfromtimestamp(element.get("createdAt") // 1000)

        sender_profile = get_path(
            element,
            "from",
            "com.linkedin.voyager.messaging.MessagingMember",
            "miniProfile",
        )
        sender = "{} {}".format(
            sender_profile.get("firstName"), sender_profile.get("lastName")
        )
        print(f"  {sender} @ {time}")
        print(f"    Reactions: {element['reactionSummaries']}")
        paragraphs = get_path(
            element,
            "eventContent",
            "com.linkedin.voyager.messaging.event.MessageEvent",
            "attributedBody",
            "text",
        ).split("\n")
        for text in paragraphs:
            wrapped = textwrap.wrap(text, 80)
            for line in wrapped:
                print(f"    {line}")
            print()

with open(thread_cache_path, "w+") as f:
    json.dump(threads, f, sort_keys=True, indent=2)
