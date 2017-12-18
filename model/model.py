import numpy as np
from scipy.misc import imresize

from network import Network
from network.layers import Layer
from util import ArgumentError
from qtgui.widgets.networkselector import (DataSource,
                                           DataArray,
                                           DataDirectory,
                                           DataFile,
                                           DataSet)


class Model(object):
    '''Model class encompassing network, current activations, and the like.

    Attributes
    ----------
    _observers  :   set
                    Objects observing this class for changes
    _data   :   np.ndarray
                Current input data
    _layer  :   Layer
                Currently selected layer
    _unit   :   int
                Currently selected unit in the layer
    _network    :   Network
                Currently active network
    _current_mode   :   str
                The current mode: can be 'array' or 'dir'
    _sources    :   dict
                    The available data sources. A dictionary with mode names as
                    keys and DataSource objects as values.

    '''

    _observers:   set = set()
    _data:        np.ndarray = None
    _network:     Network = None
    _layer:       Layer = None
    _unit:        Layer = None
    _sources:     dict = {}
    _data_valid:  bool = False
    _current_mode: str = None

    def __init__(self, network: Network):
        '''Create a new Model instance.

        Parameters
        ----------
        network :   Network
                    Network instance backing the model
        '''
        self._network = Network

    def setDataSource(self, source: DataSource):
        if isinstance(source, DataArray):
            self._current_mode = 'array'
        elif isinstance(source, DataDirectory):
            self._current_mode = 'dir'
        else:
            return
        self._sources[self._current_mode] = source

    def setDataArray(self, data: np.ndarray = None):
        '''Set the data array to be used.

        Parameters
        ----------
        data:
            An array of data. The first axis is used to select the
            data record, the other axes belong to the actual data.
        '''
        self.setDataSource(DataArray(data))

    def setDataFile(self, filename: str):
        '''Set the data file to be used.
        '''
        self.setDataSource(DataFile(filename))

    def setDataDirectory(self, dirname: str = None):
        '''Set the directory to be used for loading data.
        '''
        self.setDataSource(DataDirectory(dirname))

    def setDataSet(self, name: str):
        '''Set a data set to be used.

        Parameters
        ----------
        name:
            The name of the dataset. The only dataset supported up to now
            is 'mnist'.
        '''
        self.setDataSource(DataSet(name))

    def activations_for_layers(self, layers, data):
        '''Get activations for a set of layers. TODO: Cache results.

        Parameters
        ----------
        layers  :   Layer or list
                    Layers to query
        data    :   np.ndarray
                    Data to pump through the net.
        '''
        activations = self._network.get_activations(
            list(layers), data)[0]

        if activations.ndim in {2, 4}:
            if activations.shape[0] != 1:
                raise RuntimeError('Attempting to visualise batch.')
            activations = np.squeeze(activations, axis=0)

        self._activations = activations

        return activations

    def add_observer(self, observer):
        '''Add an object to observe this model.

        Parameters
        ----------
        observer    :   object
                        Object which wants to be notified of changes

        '''
        self._observers.add(observer)

    def setNetwork(self, network=None):
        if isinstance(network, str):
            raise ArgumentError(f'Need to look uo network name for {network}.')
        if self._network != network:
            self._network_info.setNetwork(network)
            self.setLayer(None)
            self.notifyObservers()

    def id_for_layer(self, layer_str):
        layer_id = -1
        for index, label in enumerate(self._network.layer_dict.keys()):
            if layer_str == label:
                layer_id = index

        if layer_id <= -1:
            raise RuntimeError(f'Layer for string {layer_str} not found.')
        else:
            return layer_id

    def setLayer(self, layer=None):
        '''Set the current layer to choose units from.

        Parameters
        ----------
        layer       :   network.layers.Layer
                        Layer instance to display

        '''

        if self._layer != layer:
            self._layer = layer
            self.notifyObservers()

    def notifyObservers(self):
        '''Notify all observers that the state of this model has changed.'''

        for o in self._observers:
            o.modelChanged(self)

    # def setInputDataFile(self, filename):

    # def setInputDataSet(self, data_set):
    # def setInputDataDirectory(self, directory):

    def setInputData(self, data: np.ndarray=None, description: str=None):
        '''Provide one data vector as input for the network.
        The input data must have 2, 3, or 4 dimensions.

        - 2 dimensions means a single gray value image
        - 3 dimensions means a single three-channel image. The channels will
          be repeated thrice to form a three-dimensional input
        - 4 dimensions are only supported insofar as the shape must be
          (1, A, B, C), meaning the fist dimension is singular and can be
          dropped. Actual batches are not supported

        The input image shape will be adapted for the chosen network by resizing
        the images

        Parameters
        ----------
        data    :   np.ndarray
                    The data array
        description :   str
                        Data description
        '''

        if data is None or not data.ndim:
            raise ArgumentError('Data cannot be None.')

        if data is not None:
            network_shape = self._network.get_input_shape(include_batch=False)

            if data.ndim > 4 or data.ndim < 2:
                raise ArgumentError('Data must have between 2 '
                                    'and 4 dimensions.')

            if data.ndim == 4:
                if data.shape[0] == 1:
                    # first dimension has size of 1 -> remove
                    data = data.squeeze(0)
                else:
                    raise ArgumentError('Cannot visualize batch of images')

            if data.ndim == 2:
                # Blow up to three dimensions by repeating the channel
                data = data[..., np.newaxis].repeat(3, axis=2)

            if data.shape[0:2] != network_shape[0:2]:
                # Image does not fit into network -> resize
                data = imresize(data, network_shape[0:2])

            if data.shape[2] != network_shape[2]:
                # different number of channels
                # FIXME[hack]: find better way to do RGB <-> grayscale
                # conversion

                if network_shape[2] == 1:
                    data = np.mean(data, axis=2)
                elif network_shape[2] == 3 and data.shape[2] == 1:
                    data = data.repeat(3, axis=2)
                else:
                    raise ArgumentError('Incompatible network input shape.')

        self._data = data

    def setUnit(self, unit: int=None):
        '''Change the currently visualised unit. This should be called when the
        user clicks on a unit in the ActivationView. The activation mask will be
        nearest-neighbour-interpolated to the shape of the input data.

        Parameters
        ----------
        unit    :   int
                    Index of the unit in the layer (0-based)
        '''
        self._unit = unit
        activation_mask = self.activations_for_layers(self._layer, self._data)
        if activation_mask is not None:
            if activation_mask.shape == self._data.shape:
                activation_mask = imresize(activation_mask, self._data.shape,
                                           interp='nearest')
        return activation_mask

    def setMode(self, mode: str):
        '''Set the current mode.

        Parameters
        ----------
        mode    :   str
                    the mode (currently either 'array' or 'dir').
        '''
        self.current_current_mode = mode
        if self._current_mode != mode:
            self._current_mode = mode

            source = self._sources.get(mode)
            elements = len(source or [])
            self._data_valid = (elements > 1)
            self.elements = elements


            self._index = None
            self.setIndex(0 if self._data_valid else None)

    def editIndex(self, index)
        try:
            index = int(text)
            if index < 0:
                raise ValueError('Index out of range')
        except ValueError:
            index = self._index

        if index != self._index:
            self.setIndex(index)

    def setIndex(self, index=None):
        '''Set the index of the entry in the current data source.

        The method will emit the 'selected' signal, if a new(!) entry
        was selected.
        '''

        source = self._sources.get(self._current_mode)
        if index is None or source is None or len(source) < 1:
            index = None
        elif index < 0:
            index = 0
        elif index >= len(source):
            index = len(source) - 1

        if self._index != index:

            self._index = index
            if source is None or index is None:
                data, info = None, None
            else:
                data, info = source[index]

            # FIXME[bug]: there is an error in PyQt forbidding to emit None
            # signals.
            if data is None:
                data = np.ndarray(())
            if info is None:
                info = ''
            self.selected.emit(data, info)

        self._indexField.setText('' if index is None else str(index))

    def _setSource(self, source: DataSource):
        if source is None:
            return
        if isinstance(source, DataArray):
            mode = 'array'
            info = (source.getFile()
                    if isinstance(source, DataFile)
                    else source.getDescription())
            if info is None:
                info = ''
            if len(info) > 40:
                info = info[0:info.find('/', 10) + 1] + \
                    '...' + info[info.rfind('/', 0, -20):]
            self._modeButton['array'].setText('Array: ' + info)
        elif isinstance(source, DataDirectory):
            mode = 'dir'
            self._modeButton['dir'].setText('Directory: ' +
                                            source.getDirectory())
        else:
            return

        self._sources[mode] = source
        self._mode = None
        self._setMode(mode)

    def setDataArray(self, data: np.ndarray = None):
        '''Set the data array to be used.

        Parameters
        ----------
        data:
            An array of data. The first axis is used to select the
            data record, the other axes belong to the actual data.
        '''
        self._setSource(DataArray(data))

    def setDataFile(self, filename: str):
        '''Set the data file to be used.
        '''
        self._setSource(DataFile(filename))

    def setDataDirectory(self, dirname: str = None):
        '''Set the directory to be used for loading data.
        '''
        self._setSource(DataDirectory(dirname))

    def setDataSet(self, name: str):
        '''Set a data set to be used.

        Parameters
        ----------
        name:
            The name of the dataset. The only dataset supported up to now
            is 'mnist'.
        '''
        self._setSource(DataSet(name))
