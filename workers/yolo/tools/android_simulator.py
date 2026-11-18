"""Camera emulator: explicit public test fixture, never opens a device."""
import struct
import json
import time

CAMERA_ID = 1


def camera_packet(jpeg,frame_id,mode="ICN1",camera_id=CAMERA_ID,timestamp=None):
    timestamp = timestamp or int(time.time()*1000)
    if mode=="RAW_JPEG":
        return jpeg
    if mode=="ICN1":
        camera = str(camera_id).encode()
        return struct.pack("!4sHqqH",b"ICN1",1,frame_id,timestamp,len(camera))+camera+struct.pack("!I",len(jpeg))+jpeg
    header=json.dumps(dict(cameraId=camera_id,frameId=frame_id,capturedAt=timestamp,width=640,height=360)).encode()
    return struct.pack("!I",len(header))+header+jpeg
