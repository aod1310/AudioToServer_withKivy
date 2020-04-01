import socketserver
import threading
import wave
import time
import os
from time import sleep

HOST = ''
PORT = 10000
ADDR = (HOST, PORT)
lock = threading.Lock()


class AndroidRecorderManager:
    def __init__(self):
        self.recorders = {}
        self.n_recorders = len(self.recorders)

    def add_recorder(self, recorder):
        lock.acquire()
        self.recorders[recorder] = {'recorder': recorder, 'name': self.n_recorders, 'connection': recorder.conn}
        lock.release()
        self.n_recorders = self.n_recorders + 1
        print('connected\n', recorder)

    def remove_recorder(self, recorder):
        lock.acquire()
        del self.recorders[recorder]
        self.n_recorders = self.n_recorders - 1
        lock.release()
        # print(recorder, 'connection out')

    def check_sync(self):  # all connected devices pushes Record start Button?
        if self.n_recorders > 0:
            self.syncs = [recorder['recorder'].RECORD_START for recorder in self.recorders.values()]
            if False not in self.syncs:
                self.update_syncs(True)
                #print('sync!')
            else:
                self.update_syncs(False)
                #print('not sync!')

    def update_syncs(self, flag):
        for recorder in self.recorders.values():
            recorder['recorder'].update_sync(flag)


class AndroidRecorder:
    def __init__(self, conn, name):
        self.live = True
        self.RECORD_START = False
        self.sync = False
        self.frames = []
        self.conn = conn
        self.name = name
        print(self.conn)
        self.receiver = threading.Thread(target=self.recv_data, args=())

    def set_recvflag(self, flag):
        # bool types --> length of received datas are different.. True:1, False:0 and mixed another datas.
        if flag =='True':
            self.RECORD_START = True
        else :
            self.RECORD_START = False

        if len(self.frames) != 0:
            self.save_audio()
            self.frames.clear()

    def store_signal(self, data):
        if self.sync == True:
            self.frames.append(data)
        # print(data)

    def save_audio(self):
        folder = './waves/' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        if not os.path.exists(folder):  ## check for saving wave files
            os.mkdir(folder)
        try:
            filename = str(self.name) + '_recording' + folder + '.wav'
            wf = wave.open(folder+ '/' + filename, 'wb')
            wf.setnchannels(1)
            wf.setframerate(16000)
            wf.setsampwidth(2)
            wf.writeframes(b''.join(self.frames))
            wf.close()
        except Exception as e:
            print(e)
            print('there is no data to save')

    def recv_data(self):
        while True:
            data = self.conn.recv(1600)

            try:
                temp = data.decode().strip()
                print(temp)
                if temp == 'quit':
                    self.conn.close()
                    self.live = False
                    break
                if temp == 'True' or temp == 'False':
                    lock.acquire()
                    self.set_recvflag(temp)
                    lock.release()
                    continue
            except Exception as e:
                print(e)
            if self.RECORD_START:
                self.store_signal(data)
            else:
                pass


    def update_sync(self, flag):
        self.sync = flag

    def get_RECORD_START(self):
        return self.RECORD_START


class AndroidTCPHandler(socketserver.BaseRequestHandler):
    manager = AndroidRecorderManager()
    isServerRunning = True

    def handle(self):  # it is called when clients connect this server.
        try:
            self.request.send('connect successfully'.encode())
            self.recorder = AndroidRecorder(self.request, self.manager.n_recorders)
            self.manager.add_recorder(self.recorder)
            self.recorder.receiver.start()
            while self.isServerRunning:
                self.manager.check_sync()
                if self.recorder.live == False:
                    print('recorder is dead')
                    break
        except Exception as e:
            print(e)
        print('connection out', self.client_address)
        self.manager.remove_recorder(self.recorder)


class AndroidServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def ServerStart():
    print('starting server---------')
    print('if you wnat close this server, press CTRL-C')

    try:
        server = AndroidServer(ADDR, AndroidTCPHandler)
        server.allow_reuse_address = True
        server.serve_forever()

    except:
        print('close server')
        AndroidTCPHandler.isServerRunning = False
        sleep(1)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    ServerStart()