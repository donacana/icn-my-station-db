"""Public-domain sample or explicitly supplied local file; never open cameras."""
from pathlib import Path
import cv2
import numpy as np
from app import ROOT

class FrameSource:
    def __init__(self, image=None, video=None, generated=False):
        if sum([image is not None, video is not None, generated]) > 1:
            raise ValueError("Choose one frame source")
        self.capture = None
        if video is not None:
            path = Path(video)
            if not path.is_file():
                raise FileNotFoundError("Local video missing")
            self.capture = cv2.VideoCapture(str(path))
            if not self.capture.isOpened():
                raise ValueError("Cannot open local test video")
            self.image = None
        elif generated:
            self.image = np.full((360,640,3), 114, np.uint8)
        else:
            path = Path(image) if image else ROOT / "tests/assets/astronaut.png"
            self.image = cv2.imread(str(path))
            if self.image is None:
                raise FileNotFoundError("Test image missing; run tools.prepare_sample")

    def next_image(self):
        image = self.image
        if self.capture:
            ok, image = self.capture.read()
            if not ok:
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, image = self.capture.read()
            if not ok:
                raise ValueError("Empty test video")
        # Preserve aspect ratio inside a 640x360 frame.
        h,w = image.shape[:2]
        scale = min(640/w, 360/h)
        nw,nh = round(w*scale),round(h*scale)
        result = np.full((360,640,3),114,np.uint8)
        left,top = (640-nw)//2,(360-nh)//2
        result[top:top+nh,left:left+nw] = cv2.resize(image,(nw,nh))
        return result

    def next_jpeg(self):
        ok,jpeg = cv2.imencode(".jpg",self.next_image())
        if not ok:
            raise RuntimeError("Test JPEG encoding failed")
        return jpeg.tobytes()

    def close(self):
        if self.capture:
            self.capture.release()

def demo_jpeg():
    source = FrameSource()
    try:
        return source.next_jpeg()
    finally:
        source.close()
