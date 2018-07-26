import time
import zmq
import json
import subprocess
import os
from warnings import warn

import plottr
from plottr.config import config


def listener_is_running():

    addr = config['network']['addr']
    port = config['network']['port']
    srvr = f"tcp://{addr}:{port}"

    timeout = config['client']['send_timeout']

    context = zmq.Context()
    context.setsockopt(zmq.LINGER, timeout)
    socket = context.socket(zmq.PUSH)
    socket.connect(srvr)

    enc_data = json.dumps({}).encode()
    socket.send(enc_data)

    t0 = time.time()
    socket.close()
    context.term()

    if (time.time() - t0) > (timeout / 1000.):
        return False

    return True


def start_listener():

    if listener_is_running():
        return

    path_parts = plottr.__file__.split(os.sep)
    plottr_path = os.sep.join(path_parts[:-2] + ["plottr.py"])

    subprocess.Popen(
        f"python {plottr_path}", shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    time.sleep(1.0)

    for _ in range(5):
        if listener_is_running():
            return
        time.sleep(1.0)

    warn("Failed to start listener!")
