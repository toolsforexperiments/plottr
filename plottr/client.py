"""
plottr. A simple server application that can plot data streamed through
network sockets from other processes.

Author: Wolfgang Pfaff <wolfgangpfff@gmail.com>

This is the module containing client tools.
"""
import zmq
import json
import time
import numpy as np
from .config import config


class DataSender(object):

    def __init__(self, dataId):
        self.data = {
            'id' : dataId,
            'update' : False,
            'datasets' : {},
        }

    def addDataSetSimple(self, **kwargs):
        """
        convert specified numpy arrays into a dataset dictionary.
        first array is assumed to be data, all others axes (in given order).
        """
        names = [ k for k in kwargs.keys() ]
        dataset = {}
        for i, n in enumerate(names):
            dataset[n] = {}
            if isinstance(kwargs[n], np.ndarray):
                dataset[n]['values'] = kwargs[n].reshape(-1).tolist()
            else:
                dataset[n]['values'] = kwargs[n]
            if not i:
                dataset[n]['axes'] = names[1:]

        self.data['datasets'].update(dataset)

    def sendData(self, update=True, timeout=None):
        if update:
            self.data['update'] = True
        else:
            self.data['update'] = False
        encData = json.dumps(self.data).encode()

        addr = config['network']['addr']
        port = config['network']['port']
        srvr = f"tcp://{addr}:{port}"

        if timeout is None:
            timeout = config['client']['send_timeout']

        context = zmq.Context()
        context.setsockopt(zmq.LINGER, timeout)
        socket = context.socket(zmq.PUSH)
        socket.connect(srvr)

        t0 = time.time()
        socket.send(encData)
        socket.close()
        context.term()

        if (time.time() - t0) > (timeout / 1000.):
            print('Timeout during sending!')
