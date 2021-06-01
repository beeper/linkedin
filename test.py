import sys

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

convos = linkedin.get_conversations()

for element in convos["elements"]:
    print("=" * 100)
    print(element)
