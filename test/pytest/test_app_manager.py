"""
Script made to test the app manager
"""
import numpy as np
import psutil
import zmq

from plottr.data.datadict import DataDictBase, DataDict
from plottr.data.datadict_storage import datadict_to_hdf5
from plottr import QtWidgets, QtCore, plottrPath
from plottr.apps.appmanager import AppManager
from plottr import qtapp, qtsleep

# Module where the launching function lives.
MODULE = 'plottr.apps.autoplot'

# The function that opens the app.
FUNC = 'autoplotDDH5App'


def _make_testdata() -> DataDictBase:
    x, y, z = (np.linspace(-5,5,51) for i in range(3))
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = np.exp(-yy**2-zz**2) + np.random.normal(loc=0, size=xx.shape)
    return DataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )


def test_closing_appManager(qtbot):
    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)
    ret = appManager.close()
    assert ret

def test_open_new_process(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')

    assert 0 in appManager.processes

    newProcess = appManager.processes[0]['process']
    pid = newProcess.processId()
    assert psutil.pid_exists(pid)

    assert not appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')

    ret = appManager.close()
    assert ret


def test_closing_process(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')

    assert 0 in appManager.processes

    newProcess = appManager.processes[0]['process']
    pid = newProcess.processId()
    assert psutil.pid_exists(pid)
    psutilProcess = psutil.Process(pid)
    psutilProcess.terminate()
    qtsleep(1)
    assert 0 not in appManager.processes
    assert not psutil.pid_exists(pid)

    ret = appManager.close()
    assert ret


def test_closing_multiple_open_apps(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')
    assert appManager.launchApp(1, MODULE, FUNC, str(tmp_path), 'data')
    assert appManager.launchApp(2, MODULE, FUNC, str(tmp_path), 'data')
    assert appManager.launchApp(3, MODULE, FUNC, str(tmp_path), 'data')

    assert 0 in appManager.processes
    assert 1 in appManager.processes
    assert 2 in appManager.processes
    assert 3 in appManager.processes

    process_0 = appManager.processes[0]['process']
    pid_0 = process_0.processId()
    assert psutil.pid_exists(pid_0)

    process_1 = appManager.processes[1]['process']
    pid_1 = process_1.processId()
    assert psutil.pid_exists(pid_1)

    process_2 = appManager.processes[2]['process']
    pid_2 = process_2.processId()
    assert psutil.pid_exists(pid_2)

    process_3 = appManager.processes[3]['process']
    pid_3 = process_3.processId()
    assert psutil.pid_exists(pid_3)

    ret = appManager.close()
    assert ret

    assert not psutil.pid_exists(pid_0)
    assert not psutil.pid_exists(pid_1)
    assert not psutil.pid_exists(pid_2)
    assert not psutil.pid_exists(pid_3)


def test_correct_port_assignment(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')
    appManager.launchApp(1, MODULE, FUNC, str(tmp_path), 'data')
    appManager.launchApp(2, MODULE, FUNC, str(tmp_path), 'data')
    appManager.launchApp(3, MODULE, FUNC, str(tmp_path), 'data')

    initialPort = appManager.initialPort
    correctPorts = list(initialPort + np.arange(0, 4))
    ports = [process['port'] for process in appManager.processes.values()]
    assert sorted(correctPorts) == sorted(ports)

    process_2 = appManager.processes[2]['process']
    pid = process_2.processId()
    psutilProcess = psutil.Process(pid)
    psutilProcess.terminate()
    # If you don't give time for the process to properly close and the signals to propagate the test will fail.
    qtsleep(0.5)

    correctPortsReduced = correctPorts.copy()
    correctPortsReduced.pop(2)

    ports = [process['port'] for process in appManager.processes.values()]
    assert sorted(correctPortsReduced) == sorted(ports)

    appManager.launchApp(5, MODULE, FUNC, str(tmp_path), 'data')
    ports = [process['port'] for process in appManager.processes.values()]
    assert sorted(correctPorts) == sorted(ports)

    ret = appManager.close()
    assert ret


def test_ping_process(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')
    qtsleep(0.5)
    assert appManager.pingApp(0)

    ret = appManager.close()
    assert ret


def test_pinging_app_from_outside_manager(qtbot, tmp_path):

    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f'tcp://127.0.0.1:12345')

    socket.send_pyobj("ping")
    reply = socket.recv_pyobj()
    assert reply == 'pong'

    ret = appManager.close()
    assert ret


def test_getting_values(qtbot, tmp_path):
    datadict = _make_testdata()
    datadict_to_hdf5(datadict, str(tmp_path), 'data')

    appManager = AppManager()
    appManager.show()
    qtbot.waitExposed(appManager)
    qtbot.addWidget(appManager)

    assert appManager.launchApp(0, MODULE, FUNC, str(tmp_path), 'data')

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f'tcp://127.0.0.1:12345')

    socket.send_pyobj(tuple(["fc", 'getOutput', None]))
    reply = socket.recv_pyobj()


    ret = appManager.close()
    assert ret

    assert reply is not None





