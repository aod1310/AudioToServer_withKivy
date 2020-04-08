import socketserver
import threading
import wave
import time
import os
from time import sleep
import time
import plrsig as plr
import soundfile
import multiprocessing

HOST = ''
PORT = 10000
ADDR = (HOST, PORT)
#lock = threading.Lock()


class AndroidRecorderManager:
    def __init__(self):
        self.recorders = {}
        self.n_recorders = len(self.recorders)
        self.cur_folder = None
        self.sync = False
        self.recorder_syncs = []

    def add_recorder(self, recorder):
        #lock.acquire()
        self.recorders[recorder] = {'recorder': recorder, 'name': self.n_recorders, 'connection': recorder.conn}
        #lock.release()
        self.n_recorders = self.n_recorders + 1
        #self.recorder_syncs.append(recorder.RECORD_START)
        print('connected\n', recorder)

    def remove_recorder(self, recorder):
        #lock.acquire()
        del self.recorders[recorder]
        self.n_recorders = self.n_recorders - 1
        #lock.release()
        # print(recorder, 'connection out')

    def check_sync(self):
        if self.n_recorders > 0:
            recorder_syncs = [recorder['recorder'].RECORD_START for recorder in self.recorders.values()]
            if False not in recorder_syncs:
                self.sync = True
                self.set_foldername()
                print('sync!')
            else:
                self.sync = False
                self.save_waves()
                print('not sync!')
            del recorder_syncs
    '''
    def check_sync(self):  # all connected devices pushes Record start Button?
        start = time.time()
        if self.n_recorders > 0:
            _recorders = [recorder['recorder'] for recorder in self.recorders.values()]
            #self.syncs = [recorder['recorder'].RECORD_START for recorder in self.recorders.values()]
            self.syncs = [recorder.RECORD_START for recorder in _recorders]
            if False not in self.syncs:
                #self.update_syncs(True)
                with multiprocessing.Pool() as pool:
                    pool.map(self.synctest, _recorders)
                    print('pool')
                self.set_foldername()
                print('sync!')
            else:
                self.update_syncs(False)
                print('not sync!')
                self.save_waves()
        print('process time : ', time.time() - start)
        time.sleep(0.2)
    

    def synctest(self, recorder):
        print('recorder = ', recorder, 'changed')
        recorder.sync=True

    def update_syncs(self, flag):
        #start = time.time()
        updaters = []
        for recorder in self.recorders.values():  ################# 여기때문에 딜레이문제 발생하는듯함. ####################
            recorder['recorder'].update_sync(flag)
        #print('process time : ', time.time() - start)
    '''

    def set_foldername(self):
        if not os.path.exists('./waves'):
            os.mkdir('./waves')
        cur_time = str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        folder = './waves/' + cur_time
        if not os.path.exists(folder):
            os.mkdir(folder)
        for recorder in self.recorders.values():
            recorder['recorder'].get_foldername(folder)
        self.cur_folder = folder

    def save_waves(self):
        for recorder in self.recorders.values():
            if len(recorder['recorder'].frames) != 0:
                recorder['recorder'].save_audio()
        if len(os.listdir(self.cur_folder)) == 2:
            self.PLR_Sigmoid_2()

    def PLR_Sigmoid_2(self):
        print('filter using PLR-sigmoid')
        signals = plr.load_datas(self.cur_folder)
        mic1, mic2 = signals[0], signals[1]
        mic1, mic2 = plr.signal_sync(mic1, mic2, corr=False)
        plrsigF = plr.calc_PLRsigF(mic1, mic2, n_fft=512, cur_weight=0.8, a=3.0, c=1.63)
        filtered = plr.apply_PLR_sigF(plrsigF, plr.signal_abs_stft(mic1, n_fft=512))
        result = plr.griffin_filtered_result(filtered)
        #result = plr.signal_normalizer(result)

        filename = 'filter_result.wav'
        filepath = self.cur_folder + '/' + filename
        soundfile.write(filepath, result, samplerate=16000, format='WAV', subtype='PCM_16')


class AndroidRecorder:
    def __init__(self, conn, name):
        self.live = True
        self.RECORD_START = False
        #self.sync = False
        self.frames = []
        self.conn = conn
        self.name = name
        print(self.conn)
        self.receiver = threading.Thread(target=self.recv_data, args=())
        self.foldername = None
        self.manager = None

    def indicate_manager(self, manager):
        self.manager = manager
        print('my manager : ', self.manager)
        return self.manager

    def get_foldername(self, path):
        self.foldername = path
        return path

    # sync가 끊어지는 순간 둘다 저장하게 해야함.
    def set_recvflag(self, flag):
        # bool types --> length of received datas are different.. True:1, False:0 and mixed another datas.
        print('recv_flag')
        if flag =='True':
            self.RECORD_START = True
        else :
            self.RECORD_START = False

        self.manager.check_sync()

    def store_signal(self, data):
        if self.manager.sync:
            self.frames.append(data)
        #print(self.name, data)

    # Sync가 True될 때의 시간을 체크해서 폴더를 생성해야됨.
    def save_audio(self):
        #folder = './waves/' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        #if not os.path.exists(folder):  ## check for saving wave files
        #    os.mkdir(folder)
        try:
            #filename = str(self.name) + '_recording' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))) + '.wav'
            filename = str(self.name) + '_recording.wav'
            wf = wave.open(self.foldername + '/' + filename, 'wb')
            wf.setnchannels(1)
            wf.setframerate(16000)
            wf.setsampwidth(2)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            self.frames.clear()
            print('save complete')
        except Exception as e:
            print(e)
            print('there is no data to save')

    def recv_data(self):
        while True:
            data = self.conn.recv(1600)
            #print(len(data))
            try:
                if b'False' in data:
                    self.set_recvflag('False')
                    continue
                temp = data.decode().strip()
                #print(temp)
                if 'quit' in temp:
                    self.conn.close()
                    self.live = False
                    break
                if 'True' in temp or 'False' in temp:
                    self.set_recvflag(temp)
                    #continue
            except Exception as e:
                #print(self.name, e)
                pass
            #if self.RECORD_START:
            if self.manager.sync is False:
                del data
                continue
            elif self.manager.sync is True:
                self.store_signal(data)
            else:
                pass

    #def update_sync(self, flag):
    #    self.sync = flag
    #    print(time.time())

    def get_RECORD_START(self):
        return self.RECORD_START


class AndroidTCPHandler(socketserver.BaseRequestHandler):
    manager = AndroidRecorderManager()
    isServerRunning = True

    def handle(self):  # it is called when clients connect this server.
        try:
            self.request.send(('%d recorder connect successfully' % self.manager.n_recorders).encode())
            self.recorder = AndroidRecorder(self.request, self.manager.n_recorders)
            self.manager.add_recorder(self.recorder)
            self.recorder.indicate_manager(self.manager)
            self.recorder.receiver.start()
            while self.isServerRunning:
                #self.manager.check_sync()
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
        #sleep(1)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    ServerStart()
