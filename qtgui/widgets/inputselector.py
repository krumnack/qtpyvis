from os import listdir, stat
from os.path import isfile, isdir, join, basename
from random import randint

import numpy as np
from scipy.misc import imread

from PyQt5.QtWidgets import QWidget, QFileDialog

# FIXME[todo]: add docstrings!


class DataSource:
    '''An abstract base class for different types of data sources.  The
    individual elements of a data source can be accessed using an array like
    notation.

    Attributes
    ----------
    _description    :   str
                        Short description of the dataset

    '''
    _description: str = None

    def __init__(self, description=None):
        '''Create a new DataSource

        Parameters
        ----------
        description :   str
                        Description of the dataset
        '''
        self._description = description

    def __getitem__(self, index: int):
        '''Provide access to the records in this data source.'''
        pass

    def __len__(self):
        '''Get the number of entries in this data source.'''
        pass

    def getDescription(self) -> str:
        '''Get the description for this DataSource'''
        return self._description


class DataArray(DataSource):
    '''A ``DataArray`` the stores all entries in an array (like the MNIST
    character data). That means that all entries will have the same sizes.

    Attributes
    ----------
    _array  :   np.ndarray
                An array of input data. Can be None.
    '''
    _array: np.ndarray = None

    def __init__(self, array: np.ndarray=None, description: str=None):
        '''Create a new DataArray

        Parameters
        ----------
        array   :   np.ndarray
                    Numpy data array
        description :   str
                        Description of the data set

        '''
        super().__init__(description)
        if array is not None:
            self.setArray(array, description)

    def setArray(self, array, description='array'):
        '''Set the array of this DataSource.

        Parameters
        ----------
        array   :   np.ndarray
                    Numpy data array
        description :   str
                        Description of the data set
        '''
        self._array = array
        self._description = description

    def __getitem__(self, index: int):
        if self._array is None or index is None:
            return None, None
        data = self._array[index]
        info = 'Image ' + str(index) + ' from ' + self._description
        return data, info

    def __len__(self):
        if self._array is None:
            return 0
        return len(self._array)


class DataFile(DataArray):
    '''Data source for reading from a file.

    Attributes
    ----------
    _filename   :   str
                    The name of the file from which the data are read.
    '''

    _filename: str = None

    def __init__(self, filename: str=None):
        '''Create a new data file.

        Parameters
        ----------
        filename    :   str
                        Name of the file containing the data
        '''
        super().__init__()
        if filename is not None:
            self.setFile(filename)

    def setFile(self, filename: str):
        '''Set the data file to be used.

        Parameters
        ----------
        filename    :   str
                        Name of the file containing the data
        '''
        self._filename = filename
        data = np.load(filename, mmap_mode='r')
        self.setArray(data, basename(self._filename))

    def getFile(self) -> str:
        '''Get the underlying file name'''
        return self._filename

    def selectFile(self, parent: QWidget=None):
        filters = 'Numpy Array (*.npy);; All Files (*)'
        filename, _ = QFileDialog.getOpenFileName(
            parent,
            'Select input data archive',
            self._filename,
            filters
        )
        if filename is None or not isfile(filename):
            raise FileNotFoundError('The specified file %s could not be found.' %
                                    filename)
        self.setFile(filename)


class DataSet(DataArray):

    def __init__(self, name: str = None):
        super().__init__()
        self.load(name)

    def load(self, name: str):
        if name == 'mnist':
            from keras.datasets import mnist
            data = mnist.load_data()[0][0]
            self.setArray(data, 'MNIST')
        else:
            raise ValueError('Unknown dataset: {}'.format(name))

    def getName(self) -> str:
        return 'MNIST'


class DataDirectory(DataSource):
    '''A data directory contains data entries (e.g., images), in
    individual files. Each files is only read when accessed.

    Attributes
    ----------
    _dirname    :   str
                    A directory containing input data files. Can be None.


    _filenames  :   list
                    A list of filenames in the data directory. Will be None if
                    no directory was selected. An empty list indicates that no
                    suitable files where found in the directory.
    '''
    _dirname: str = None
    _filenames: list = None

    def __init__(self, dirname: str=None):
        '''Create a new DataDirectory

        Parameters
        ----------
        dirname :   str
                    Name of the directory with files
        '''
        super().__init__()
        self.setDirectory(dirname)

    def setDirectory(self, dirname: str):
        '''Set the directory to load from

        Parameters
        ----------
        dirname :   str
                    Name of the directory with files
        '''
        self._dirname = dirname
        if self._dirname is None:
            self._filenames = None
        else:
            self._filenames = [f for f in listdir(self._dirname)
                               if isfile(join(self._dirname, f))]

    def getDirectory(self) -> str:
        return self._dirname

    def __getitem__(self, index):
        if not self._filenames:
            return None, None
        else:
            # TODO: This can be much improved by caching and/or prefetching
            filename = self._filenames[index]
            data = imread(join(self._dirname, filename))
            return data, filename

    def __len__(self):
        if not self._filenames:
            return 0
        return len(self._filenames)

    def selectDirectory(self, parent: QWidget=None):
        dirname = QFileDialog.getExistingDirectory(parent, 'Select Directory')
        if not dirname or not isdir(dirname):
            raise FileNotFoundError('%s is not a directory.' % dirname)
        else:
            self.setDirectory(dirname)


from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QIntValidator, QIcon
from PyQt5.QtWidgets import QWidget, QPushButton, QRadioButton, QLineEdit
from PyQt5.QtWidgets import QLabel, QGroupBox
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QSizePolicy

from observer import Observer


class QInputSelector(QWidget, Observer):
    '''A Widget to select input data (probably images).  There are
    different modes of selection: from an array, from a file, from a
    directory or from some predefined dataset.

    Modes: there are currently different modes ('array' or 'dir').
    For each mode there exist a corresponding data source. The widget
    has a current mode and will provide data only from the
    corresponding data source.

    ATTENTION: this mode concept may be changed in future versions! It
    seems more plausible to just maintain a list of data sources.

    Attributes
    ----------
    _index  :   int
                The index of the current data entry.
    selected    :   pyqtSignal
                    A signal emitted when new input data are selected.  The
                    signal will carry the new data and some text explaining the
                    data origin. (np.ndarray, str)
    '''
    _index: int = None

    _controller = None

    selected = pyqtSignal(object, str)

    def __init__(self, parent=None):
        '''Initialization of the QNetworkView.

        Parameters
        ---------
        parent  :   QWidget
                    The parent argument is sent to the QWidget constructor.
        '''
        super().__init__(parent)

        self.initUI()

    def setController(self, controller):
        self._controller = controller

    def modelChanged(self, model):
        source = model._sources[model._current_source]
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

    def _newNavigationButton(self, label: str, icon: str=None):
        button = QPushButton()
        icon = QIcon.fromTheme(icon, QIcon())
        if icon.isNull():
            button.setText(label)
        else:
            button.setIcon(icon)
        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        button.clicked.connect(self._navigationButtonClicked)
        return button

    def initUI(self):
        '''Initialize the user interface.'''

        self.firstButton = self._newNavigationButton('|<', 'go-first')
        self.prevButton = self._newNavigationButton('<<', 'go-previous')
        self.nextButton = self._newNavigationButton('>>', 'go-next')
        self.lastButton = self._newNavigationButton('>|', 'go-last')
        self.randomButton = self._newNavigationButton('random')

        self._indexField = QLineEdit()
        self._indexField.setMaxLength(8)
        self._indexField.setAlignment(Qt.AlignRight)
        self._indexField.setValidator(QIntValidator())
        self._indexField.textChanged.connect(self._editIndex)
        self._indexField.textEdited.connect(self._editIndex)
        self._indexField.setSizePolicy(
            QSizePolicy.Maximum, QSizePolicy.Maximum)
        self._indexField.setMinimumWidth(
            QFontMetrics(self.font()).width('8') * 8)

        self.infoLabel = QLabel()
        self.infoLabel.setMinimumWidth(
            QFontMetrics(self.font()).width('8') * 8)
        self.infoLabel.setSizePolicy(
            QSizePolicy.Maximum, QSizePolicy.Expanding)

        self._modeButton = {}
        self._modeButton['array'] = QRadioButton('Array')
        self._modeButton['array'].clicked.connect(
            lambda: self._controller.mode_changed('array'))

        self._modeButton['dir'] = QRadioButton('Directory')
        self._modeButton['dir'].clicked.connect(lambda: self._controller.mode_changed('dir'))

        self._openButton = QPushButton('Open...')
        self._openButton.clicked.connect(self._openButtonClicked)
        self._openButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        sourceBox = QGroupBox('Data sources')
        modeLayout = QVBoxLayout()
        modeLayout.addWidget(self._modeButton['array'])
        modeLayout.addWidget(self._modeButton['dir'])
        sourceLayout = QHBoxLayout()
        sourceLayout.addLayout(modeLayout)
        sourceLayout.addWidget(self._openButton)
        sourceBox.setLayout(sourceLayout)

        navigationBox = QGroupBox('Navigation')
        navigationLayout = QHBoxLayout()
        navigationLayout.addWidget(self.firstButton)
        navigationLayout.addWidget(self.prevButton)
        navigationLayout.addWidget(self._indexField)
        navigationLayout.addWidget(self.infoLabel)
        navigationLayout.addWidget(self.nextButton)
        navigationLayout.addWidget(self.lastButton)
        navigationLayout.addWidget(self.randomButton)
        navigationBox.setLayout(navigationLayout)

        layout = QHBoxLayout()
        layout.addWidget(sourceBox)
        layout.addWidget(navigationBox)
        self.setLayout(layout)

    def modelChanged(self, model):
        valid = model._data_valid
        self.firstButton.setEnabled(valid)
        self.prevButton.setEnabled(valid)
        self.nextButton.setEnabled(valid)
        self.lastButton.setEnabled(valid)
        self.randomButton.setEnabled(valid)
        self._indexField.setEnabled(valid)
        elements = model.elements
        self.infoLabel.setText("of " + str(elements - 1) if valid else "*")
        if valid:
            self._indexField.setValidator(QIntValidator(0, elements))

        mode = model.current_mode
        self._modeButton[mode].setChecked(True)

    def _editIndex(self, text):
        '''Event handler for the edit field.'''
        self._controller.editIndex(text)


    def _navigationButtonClicked(self):
        '''Callback for clicking the 'next' and 'prev' sample button.'''
        if self._index is None:
            index = None
        elif self.sender() == self.firstButton:
            self._controller.rewind()
            index = 0
        elif self.sender() == self.prevButton:
            index = self._index - 1
            self._controller.rewind_one()
        elif self.sender() == self.nextButton:
            index = self._index + 1
            self._controller.advance_one()
        elif self.sender() == self.lastButton:
            index = len(self._sources[self._mode])
            self._controller.advance()
        elif self.sender() == self.randomButton:
            index = randint(0, len(self._sources[self._mode]))
            self._controller.random()
        else:
            index = None
        self._controller.editIndex(index)

    def _openButtonClicked(self):
        '''An event handler for the 'Open' button.
        '''
        try:
            source = self._sources.get(self._mode)
            if self._mode == 'array':
                if not isinstance(source, DataFile):
                    source = DataFile()
                source.selectFile(self)
            elif self._mode == 'dir':
                if not isinstance(source, DataDirectory):
                    source = DataDirectory()
                source.selectDirectory(self)
            self._controller.source_selected(source)
        except FileNotFoundError:
            pass

    def _setMode(self, mode: str):
        '''Set the current mode.

        Parameters
        ----------
        mode    :   str
                    the mode (currently either 'array' or 'dir').
        '''
        if self._mode != mode:
            self._mode = mode

            source = self._sources.get(mode)
            elements = 0 if source is None else len(source)
            valid = (elements > 1)

            self.firstButton.setEnabled(valid)
            self.prevButton.setEnabled(valid)
            self.nextButton.setEnabled(valid)
            self.lastButton.setEnabled(valid)
            self.randomButton.setEnabled(valid)
            self._indexField.setEnabled(valid)
            self.infoLabel.setText("of " + str(elements - 1) if valid else "*")
            if valid:
                self._indexField.setValidator(QIntValidator(0, elements))

            if mode is not None:
                self._modeButton[mode].setChecked(True)

            self._index = None
            self.setIndex(0 if valid else None)

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

    def setIndex(self, index=None):
        '''Set the index of the entry in the current data source.

        The method will emit the 'selected' signal, if a new(!) entry
        was selected.
        '''

        source = self._sources.get(self._mode)
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


from PyQt5.QtWidgets import QWidget, QPushButton, QLabel
from PyQt5.QtWidgets import QHBoxLayout, QSizePolicy


class QInputInfoBox(QWidget):

    def __init__(self, parent=None):
        '''Create a new QInputInfoBox.

        parent  :   QWidget
                    Parent widget
        '''
        super().__init__(parent)
        self._initUI()
        self.showInfo()

    def _initUI(self):
        '''Initialise the UI'''
        self._metaLabel = QLabel()
        self._dataLabel = QLabel()
        self._button = QPushButton('Statistics')
        self._button.setCheckable(True)
        self._button.toggled.connect(self.update)
        self._button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QHBoxLayout()
        layout.addWidget(self._metaLabel)
        layout.addWidget(self._dataLabel)
        layout.addWidget(self._button)
        self.setLayout(layout)

    def showInfo(self, data: np.ndarray=None, description: str=None):
        '''Show info for the given (image) data.

        Parameters
        ----------
        data:
            the actual data
        description:
            some string describing the origin of the data
        '''
        self._meta_text = '<b>Input image:</b><br>\n'
        self._meta_text += f'Description: {description}\n'

        self._data_text = ''
        if data is not None:
            self._data_text += f'Input shape: {data.shape}, dtype={data.dtype}<br>\n'
            self._data_text += 'min = {}, max={}, mean={:5.2f}, std={:5.2f}\n'.format(
                data.min(), data.max(), data.mean(), data.std())
        self.update()

    def update(self):
        self._metaLabel.setText(self._meta_text)
        self._dataLabel.setText(
            self._data_text if self._button.isChecked() else '')
