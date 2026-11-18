"""Read-only public health/status check. Never accepts or prints credentials."""
import argparse
import json
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-url",required=True,help="Explicit public http/https origin; never inferred")
    args=parser.parse_args()
    parsed=urlsplit(args.base_url)
    if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
        parser.error("base-url must be a public http/https origin without credentials")
    url=urljoin(args.base_url.rstrip("/")+"/","api/v1/yolo/cameras")
    with urlopen(url,timeout=8) as response:
        cameras=json.load(response)
    safe=[{key:item.get(key) for key in ("cameraId","zoneId","name","isActive","camera","worker")}
          for item in cameras]
    print(json.dumps({"httpStatus":response.status,"cameras":safe},ensure_ascii=False))


if __name__=="__main__":
    main()
