# Public test image

`astronaut.png`: NASA photograph of Eileen Collins, distributed by scikit-image.
scikit-image documents the image as public domain, with no known copyright restrictions:
https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut

Pinned download: https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/astronaut.png

Used solely as a public test fixture, not live camera footage. In memory, the image is
resized without aspect distortion and padded to 640×360 before JPEG encoding.
No facial identity analysis is performed. This single image does not validate crowd
counting accuracy or gesture recognition. The worker counts detector outputs, not ground truth.
