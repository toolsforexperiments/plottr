import pyqtgraph as pg

from plottr import config_entry as getcfg


__all__ = []


bg = getcfg('main', 'pyqtgraph', 'background', default='w')
pg.setConfigOption('background', bg)

fg = getcfg('main', 'pyqtgraph', 'foreground', default='k')
pg.setConfigOption('foreground', fg)
