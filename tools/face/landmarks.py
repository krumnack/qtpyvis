import numpy as np

from datasources import Metadata
from util.image import Landmarks, BoundingBox
from base import run
from tools.detector import (ImageDetector as BaseDetector,
                            ImageController as BaseController)
from .detector import Detector as FaceDetector

class FacialLandmarks(Landmarks):

    def eyes(self):
        not NotImplementedError()

    def mouth(self):
        not NotImplementedError()

class FacialLandmarks68(FacialLandmarks):

    pass



class Detector(BaseDetector):
    """A facial landmark detector.

    """
    _face_detector: FaceDetector = None


    @staticmethod
    def create(name: str, prepare: bool=True):
        if name == 'dlib':
            from .dlib import FacialLandmarkDetector
            detector = FacialLandmarkDetector()
        else:
            raise ValueError(f"Unknown detector name '{name}'.")

        if prepare:
            detector.prepare()
        return detector

    def __init__(self, face_detector: FaceDetector=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.face_detector = face_detector

    @property
    def face_detector(self):
        return self._face_detector

    @face_detector.setter
    def face_detector(self, face_detector):
        self._face_detector = face_detector


    def _detect_regions(self, image: np.ndarray, regions):
        metadata = Metadata(description=
                            'Facial landmarks detectec by the dlib detctor')
        for region in regions:
            # FIXME[hack]: suppose region.location is a BoundingBox
            detection = self._predictor(image, region.location)
            metadata.add_region(self._detection_landmarks(detection))

        return metadata
        
    def _detect_all(self, image: np.ndarray,
                    face_detector: FaceDetector=None) -> Metadata:
        if face_detector is None:
            face_detector = self._face_detector
        if face_detector is None:
            raise ValueError("No face detector was provided for "
                             "face landmark detection.")
        faces = face_detector.detect(image)
        return self._detect_all(image, faces.regions)


class Controller(BaseController):

    def process_all(self, data):
        """Process the given data.

        """
        self._next_data = data
        if not self._detector.busy:
            self._process()

    @run
    def _process_all(self):
        self._detector.busy = True
        while self._next_data is not None:

            self._data = self._next_data
            self._next_data = None
            self._detector.change(data_changed=True)
            
            self._detections = self._detector.detect_all(self._data)
            self._detector.change(detection_finished=True)

        self._detector.busy = False