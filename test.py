import json
import sys
from pathlib import Path

from linkedin_api import Linkedin
from requests.cookies import cookiejar_from_dict

convo_cache_path = Path("convocache.json")
if convo_cache_path.exists():
    print("Using convocache.json")
    with open(convo_cache_path) as f:
        convos = json.load(f)
else:
    cookies = cookiejar_from_dict(
        {
            "liap": "true",
            "li_at": sys.argv[1],
            "JSESSIONID": sys.argv[2],
        }
    )
    linkedin = Linkedin("", "", cookies=cookies)

    convos = linkedin.get_conversations()

    with open("convocache.json", "w+") as convocache:
        json.dump(convos, convocache, sort_keys=True, indent=2)


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
