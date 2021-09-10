from typing import List

import pyqtgraph as pg

from plottr import config_entry as getcfg


__all__: List[str] = []


bg = getcfg('main', 'pyqtgraph', 'background', default='w')
pg.setConfigOption('background', bg)

fg = getcfg('main', 'pyqtgraph', 'foreground', default='k')
pg.setConfigOption('foreground', fg)
