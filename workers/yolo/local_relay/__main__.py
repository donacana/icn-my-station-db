"""Default loopback listener. LAN binding requires explicit --host."""
import argparse
import os
import uvicorn
from app.demo_protocol import MAX_DEMO_PACKET as MAX_PACKET
from local_relay.server import RelaySettings,create_app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8000)
    parser.add_argument("--camera-id",type=int,default=1)
    args=parser.parse_args()
    settings=RelaySettings(camera_id=args.camera_id,worker_token=os.getenv("YOLO_WORKER_TOKEN","local-worker-demo"),
                           camera_token=os.getenv("YOLO_CAMERA_TOKEN","local-camera-demo"))
    uvicorn.run(create_app(settings),host=args.host,port=args.port,workers=1,
                ws="websockets",ws_max_size=MAX_PACKET,ws_max_queue=1,
                ws_ping_interval=20,ws_ping_timeout=20,ws_per_message_deflate=False,
                proxy_headers=False,access_log=False,log_level="warning")


if __name__=="__main__":
    main()
