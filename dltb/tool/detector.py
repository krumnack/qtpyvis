"""Abstract base class for detectors.
"""
# standard imports
from typing import Union, Tuple, List, Any
import logging

# third party imports
import numpy as np

# toolbox imports
from ..base.data import Data
from ..base.meta import Metadata
from ..base.image import Image, Imagelike
from .tool import Tool
from .image import ImageTool

# logging
LOG = logging.getLogger(__name__)


# A type for possible detections
Detections = Union[Metadata]


class Detector(Tool):
    # pylint: disable=too-many-ancestors
    """A general detector. A detector is intended to detect something
    in some given data.

    The basic detector interface (:py:meth:`detect`) simply maps given
    data to detections.  What detections are and how they are represented
    will differ for specific subclasses (for example an ImageDetector
    typically returns a list of bounding boxes).
    """

    #
    # Detector
    #

    def _process(self, data, **kwargs) -> Any:
        """Processing data with a :py:class:`Detector` means detecting.
        """
        return self._detect(data, **kwargs)

    # FIXME[todo]: working on batches (data.is_batch). Here arises the
    #   question what the result type should be for the functional API
    #   (A): a list/tuple or some iterator, or even another structure
    #   (a batch version of Metadata)
    def detect(self, data: Data, **kwargs) -> Detections:
        """Preprocess the given data and apply the detector.

        This method is intended for synchronous use - it dose neither
        alter the `data` object, nor the detector itself. Depending
        on the detector, it may be possible to run the method multiple
        times in parallel.

        Arguments
        ---------
        data: Data
            The data to be fed to the detector. This may be
            a :py:class:`Data` object or simple data array.

        Result
        ------
        detection: Detections
            The dections.
        """
        if not self.prepared:  # FIXME[todo]: decorator @assert_prepared...
            raise RuntimeError("Running unprepared detector.")

        # FIXME[todo/hack]: the following will data batches
        # currently we simply flatten the batch, taking the first item.
        # The correct approach would be to really do detection on
        # the whole batch
        if data.is_batch:
            raise ValueError("Detector currently does not support "
                             "batch detection.")

        LOG.info("Running detector '%s' on data %r", self.key, data)

        if not data:
            return None

        # obtain the preprocessed input data
        preprocessed_data = self.preprocess(data)
        print("detect:", type(data), type(preprocessed_data))

        # do the actual processing
        detections = self._detect(preprocessed_data, **kwargs)
        LOG.info("Detector '%s' with %s detections",
                 self.key, detections)

        detections = self._adapt_detections(detections, data)

        return detections

    def _detect(self, data: np.ndarray, **kwargs) -> Detections:
        """Do the actual detection.

        The detector will return a Metadata structure containing the
        detections as a list of :py:class:`Location`s (usually of type
        :py:class:`BoundingBox`) in the 'regions' property.
        """
        raise NotImplementedError("Detector class '" +
                                  type(self).__name__ +
                                  "' is not implemented (yet).")

    def _detect_batch(self, data: np.ndarray, **kwargs) -> Detections:
        # FIXME[todo]: batch processing
        raise NotImplementedError("Detector class '" +
                                  type(self).__name__ +
                                  "' is not implemented (yet).")

    def _adapt_detections(self, detections: Detections,
                          data: Data) -> Detections:
        raise NotImplementedError("Detector class '" +
                                  type(self).__name__ +
                                  "' is not implemented (yet).")

    #
    # Processor
    #

    def _preprocess_data(self, data: Data, **kwargs) -> None:
        """This will add a detector specific `'detections'` attribute
        to the  :py:class:`Data` object.  This attribute is intended
        to hold the detections.  It is going to be filled by
        :py:class:`process_data`.
        """
        super()._preprocess_data(data, **kwargs)
        self.add_data_attribute(data, 'detections')

    def _process_data(self, data: Data, **kwargs) -> None:
        """Process the given data. This will run the detector on
        the data and add the detection results as new attribute
        `'detections'` to  `data`.
        """
        LOG.debug("Processing data %r with detector %s", data, self)
        # self.detect() includes preprocessing and postprocessing
        detections = self.detect(data)
        self.set_data_attribute(data, 'detections', detections)
        LOG.debug("Detections found 2: %s, %s", self.detections(data), data)

    def detections(self, data) -> Metadata:
        """Provide the detections from a data object that was processed
        by this :py:class:`Detector`.
        """
        return self.get_data_attribute(data, 'detections')


class ImageDetector(Detector, ImageTool):
    # pylint: disable=too-many-ancestors
    """A detector to be applied to image data.
    """

    def __init__(self, size: Tuple[int, int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._size = size

    #
    # Implementation of the private API
    #

    external_result: Tuple[str] = ('detections', )
    internal_result: Tuple[str] = ('_detections', )

    def _postprocess(self, context: Data, name: str) -> None:
        # FIXME[todo]: batch processing
        if name == 'detections':
            if hasattr(context, '_detections'):
                detections = context._detections
                if self._size is not None and hasattr(context, 'image'):
                    size = context.image.shape
                    resize_ratio = max(self._size[0]/size[0],
                                       self._size[1]/size[1])
                    detections.scale(resize_ratio)
            else:
                detections = None
            context.add_attribute('detections', detections)

        elif name == 'mark':
            if not hasattr(context, 'detections'):
                self._postprocess(context, 'detections')
            context.add_attribute(name, self.mark_image(context.input_image,
                                                        context.detections))

        elif name == 'extract':
            if not hasattr(context, 'detections'):
                self._postprocess(context, 'detections')
            context.add_attribute(name,
                                  self.extract_from_image(context.image,
                                                          context.detections))

        else:
            super()._postprocess(context, name)

    #
    # FIXME[old]:
    #

    def _preprocess_old(self, array: np.ndarray, **kwargs) -> np.ndarray:
        """Preprocess the image. This will resize the image to the
        target size of this tool, if such a size is set.
        """
        if array.ndim != 2 and array.ndim != 3:
            raise ValueError("The image provided has an illegal format: "
                             f"shape={array.shape}, dtype={array.dtype}")

        # if self._size is not None:
            # resize_ratio = array.shape[1]/400.0
            # array = imutils.resize(array, width=400)  # FIXME[hack]

        return super()._preprocess(array, **kwargs)

    def _adapt_detections(self, detections: Detections,
                          data: Data) -> Detections:

        if detections is None:
            return None

        # if we have scaled the input data, then we have to apply reverse
        # scaling to the detections.
        if self._size is not None:
            size = data.array.shape
            resize_ratio = max(self._size[0]/size[0], self._size[1]/size[1])
            detections.scale(resize_ratio)

        return detections

    def _postprocess_data(self, data: Data, mark: bool = False,
                          extract: bool = False, **kwargs) -> None:
        """Apply different forms of postprocessing to the data object,
        extending it by additional tool specific attributes.

        Arguments
        ---------
        mark: bool
            Visually mark the detections in a copy of the image and
            store the result in the data object as the tool
            specific attribute `marked`.
        extract: bool
            Extract a list of image patches corresponding to the
            detections from the image and store the result in the
            data object as the tool specific attribute `extractions`.
        """
        if mark:
            self.mark_data(data)

        if extract:
            self.extract_data(data)

    #
    # Image specific methods
    #

    def detect_image(self, image: Imagelike, **kwargs) -> Detections:
        """Apply the detector to the given image.

        Arguments
        ---------
        image:
            The image to be processed by this :py:class:`ImageDetector`.

        Result
        ------
        detectons:
            The detections obtained from the detector.
        """
        return self.detect(image)

    def process_image(self, image: Imagelike, **kwargs) -> Image:
        """Create an :py:class:`Image` data object and process it with this
        :py:class:`ImageDetector`.

        Arguments
        ---------
        image:
            The image to be processed by this :py:class:`ImageDetector`.

        Result
        ------
        image:
            The processed image object. This object may have additional
            properties depending on the optional arguments passed to
            this function.
        """
        data = Image(image)
        self.apply(data, **kwargs)
        return data

    #
    # Marking detections
    #

    def mark_image(self, image: Imagelike, detections: Detections = None,
                   copy: bool = True) -> np.ndarray:
        """Mark the given detections in an image.

        Arguments
        ---------
        image: Imagelike
            The image into which the detections are to be drawn.
        detections: Detections
            The detections to draw.
        copy: bool
            A flag indicating if detections should be marked in
            a copy of the image (`True`) or into the original
            image object (`False`).

        Result
        ------
        marked_image: np.ndarray
            An image in which the given detections are visually marked.
        """
        array = Image.as_array(image, copy=copy)
        if detections is None:
            detections = self.detect(array)
        if detections:
            for index, region in enumerate(detections.regions):
                region.mark_image(array)
        return array

    def mark_data(self, data: Data, detections: Detections = None) -> None:
        """Extend the given `Data` image object by a tool specific attribute,
        called `marked`, holding a copy of the original image in which
        the detections are marked. This function assumes that the
        detect has already be applied to the given data object and the
        detections are stored in a tool specific attribute called
        `detections`.

        Arguments
        ---------
        data: Data
            The data object do be marked.
        detections: Detections
            The detections to mark in the image. If None are provided
            the detections from the tools specific attribute `detections`
            is used.
        """
        if detections is None:
            detections = self.detections(data)
        marked_image = self.mark_image(data.array, detections, copy=True)
        self.add_data_attribute(data, 'mark', marked_image)

    def marked_image(self, data) -> np.ndarray:
        """Get a version of the image with visually marked detections.
        This method assumes that this image has already be stored as
        an attribute to the data object, e.g., by calling the method
        :py:meth:`mark_data`, or by provding the argument `mark=True`
        when calling :py:meth:`process`.
        """
        return self.get_data_attribute(data, 'mark')

    #
    # Extracting detections
    #

    def extract_from_image(self, image: Imagelike, detections: Detections,
                           copy: bool = True) -> List[np.ndarray]:
        """Extract detections as a list of image patches from a given
        image.

        Arguments
        ---------
        image: Imagelike
            The image into which the detections are to be drawn.
        detections: Detections
            The detections to draw.
        copy: bool
            A flag indicating if extracted images should be realized
            as views using the same memory as the original image (False),
            or if real copies should be created (True). In some situations
            (e.g., if the detection includes invalid regions outside
            the image), only copy is valid and will be done
            no matter the value of this argument.

        Result
        ------
        extractions: List[np.ndarray]
            An list of extracted image regions.
        """
        array = Image.as_array(image)
        extractions = []
        if detections:
            for region in detections.regions:
                extractions.append(region.location.extract(array, copy=copy))
        return extractions

    def extract_data(self, data: Data,
                     detections: Detections = None) -> None:
        """Extend the given `Data` image object by a tool specific attribute,
        called `extractions`, holding a list of extracted image
        patches based on the detections done by this
        :py:class:`ImageDetector`. This function assumes that the
        detector has already be applied to the given data object and the
        detections are stored in a tool specific attribute called
        `detections`.

        Arguments
        ---------
        data: Data
            The data object do be marked.
        detections: Detections
            The detections to be extracted from the image. If None are
            provided the detections from the tools specific
            data attribute `detections` is used.

        """
        if detections is None:
            detections = self.detections(data)
        extractions = self.extract_from_image(data, detections)
        self.add_data_attribute(data, 'extract', extractions)

    def extractions(self, data) -> List[np.ndarray]:
        """Get a list of image patches extracted from the original image
        based on detections of this :py:class:ImageDetector`.
        This method assumes that this list has already been stored as
        an tool specific attribute `extractions` in the data object,
        e.g., by calling the method :py:meth:`extract_data`, or by provding
        the argument `extract=True` when calling :py:meth:`process`.
        """
        return self.get_data_attribute(data, 'extract')
