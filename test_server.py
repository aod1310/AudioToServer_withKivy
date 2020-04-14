import socketserver
import threading
import wave
import os
import time
import plrsig as plr
import soundfile
import multiprocessing
import queue

HOST = ''
PORT = 10000
ADDR = (HOST, PORT)


class AndroidRecorderManager:
    def __init__(self):
        self.recorders = {}
        self.n_recorders = len(self.recorders)
        self.cur_folder = None
        self.sync = False
        self.recorder_syncs = []
        self.barrier = threading.Barrier(self.n_recorders, action=self.barrier_aborted, timeout=1)

    def add_recorder(self, recorder):
        self.recorders[recorder] = {'recorder': recorder, 'name': self.n_recorders, 'connection': recorder.conn}
        self.n_recorders = self.n_recorders + 1
        print('connected\n', recorder)

    def remove_recorder(self, recorder):
        del self.recorders[recorder]
        self.n_recorders = self.n_recorders - 1

    def get_recorders(self):
        return [ recorder['recorder'] for recorder in self.recorders.values() ]

    def check_sync(self, recorder):
        if self.n_recorders > 0:
            recorder_syncs = [recorder['recorder'].RECORD_START for recorder in self.recorders.values()]
            if False not in recorder_syncs:
                #self.barrier = threading.Barrier(self.n_recorders, action=self.barrier_aborted, timeout=1)
                #print(self.barrier)
                #print('need parties : ', self.barrier.parties)
                self.sync = True
                self.set_foldername()
                print('sync!')
                del recorder_syncs
                return True    # 마지막 레코더한테 True가 갈듯.
            else:
                self.sync = False
                self.save_waves()
                print('not sync!')
                del recorder_syncs
                print('event cleared')
                return False

    def set_foldername(self):
        if not os.path.exists('./waves'):
            os.mkdir('./waves')
        cur_time = str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        folder = './waves/' + cur_time
        self.cur_folder = folder
        if not os.path.exists(folder):
            os.mkdir(folder)
        for recorder in self.recorders.values():
            recorder['recorder'].get_foldername(folder)


    def save_waves(self):
        for recorder in self.recorders.values():
            if len(recorder['recorder'].frames) != 0:
                recorder['recorder'].save_audio()

            '''
                        if len(os.listdir(self.cur_folder)) == 2:
                try:
                    _t_apply_filter = threading.Thread(target=self.PLR_Sigmoid_22, args=())
                    #_t_apply_filter = multiprocessing.Process(target=self.PLR_Sigmoid_2, args=())
                    _t_apply_filter.start()
                except Exception as e:
                    print(e)
                    print('use threading')
                    _t_apply_filter = threading.Thread(target=self.PLR_Sigmoid_2, args=())
                    _t_apply_filter.start()
                    '''


    def PLR_Sigmoid_2(self):
        print('filter using PLR-sigmoid')
        signals = plr.load_datas(self.cur_folder)
        mic1, mic2 = signals[0], signals[1]
        mic1, mic2 = plr.signal_sync(mic1, mic2, corr=False)
        plrsigF = plr.calc_PLRsigF(mic1, mic2, n_fft=512, cur_weight=0.8, a=8.0, c=1.5)
        filtered = plr.apply_PLR_sigF(plrsigF, plr.signal_abs_stft(mic1, n_fft=512))
        start = time.time()
        result = plr.griffin_filtered_result(filtered)
        print('griffin proceed time : ', time.time() - start)
        # result = plr.signal_normalizer(result)

        filename = 'filter_result.wav'
        filepath = self.cur_folder + '/' + filename
        soundfile.write(filepath, result, samplerate=16000, format='WAV', subtype='PCM_16')

    def PLR_Sigmoid_22(self):
        print('filter using PLR-sigmoid')
        signals = plr.load_datas(self.cur_folder)
        mic1, mic2 = signals[0], signals[1]
        mic1, mic2 = plr.signal_sync(mic1, mic2, corr=False)
        plrsigF = plr.calc_PLRsigF(mic1, mic2, n_fft=512, cur_weight=0.8, a=8.0, c=1.5)
        filtered = plr.apply_PLR_sigF(plrsigF, plr.signal_abs_stft(mic1, n_fft=512))
        start = time.time()
        lws_result = plr.lws_filtered_result(filtered)
        print('lws proceed time : ', time.time() - start)
        # result = plr.signal_normalizer(result)

        filename = 'filter_result.wav'
        filepath = self.cur_folder + '/' + filename
        soundfile.write(filepath, lws_result, samplerate=16000, format='WAV', subtype='PCM_16')

    def b(self, recorder, data):
        try:
            self.barrier.wait()
            print(recorder.name, ' waiting', len(data))
        # 풀리는 순간에 같이 data를 다시받아올까
        except Exception as e:
            pass

    def barrier_aborted(self):
        print('barrier destroyed')
        #self.barrier.abort()

    def timestamp(self, recorder):
        print(recorder.name, time.time())

    def check_flagChanged_in_other_clients(self):
        recorders = self.get_recorders()
        flag_changed = [ recorder.flag_changed for recorder in recorders ]
        if True in flag_changed:
            return True
        else:
            return False




class AndroidRecorder:
    def __init__(self, conn, name):
        self.live = True
        self.RECORD_START = False
        # self.sync = False
        self.frames = []
        self.conn = conn
        self.name = name
        self.receiver = threading.Thread(target=self.recv_data, args=())
        self.foldername = None
        self.manager = None
        self.barrier = None
        self.q = queue.Queue()
        self.flag_changed = False
        self.flag = None

    def indicate_manager(self, manager):
        self.manager = manager
        print('my manager : ', self.manager)
        return self.manager

    def get_foldername(self, path):
        self.foldername = path
        return path

    # 여기가 사실상 recorde start 버튼 이벤트 핸들러 역할..
    def set_recvflag(self, flag):
        # bool types --> length of received datas are different.. True:1, False:0 and mixed another datas.
        #print('recv_flag')
        if flag is True:
            self.RECORD_START = True
        elif flag is False:
            self.RECORD_START = False
        else:
            return

        self.manager.check_sync(self)

    def store_signal(self, data):
        if self.manager.sync:
            self.frames.append(data)

    # Sync가 True될 때의 시간을 체크해서 폴더를 생성해야됨.
    def save_audio(self):
        # folder = './waves/' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        # if not os.path.exists(folder):  ## check for saving wave files
        #    os.mkdir(folder)
        try:
            # filename = str(self.name) + '_recording' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))) + '.wav'
            filename = str(self.name) + '_recording.wav'
            wf = wave.open(self.foldername + '/' + filename, 'wb')
            wf.setnchannels(1)
            wf.setframerate(16000)
            wf.setsampwidth(2)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            print('save complete', self.name, len(self.frames))
            self.frames.clear()
        except Exception as e:
            print(e)
            print('there is no data to save')

    def recv_data(self):
        while True:
            self.flag_changed =False
            data = self.conn.recv(1600)   # sendall은 지정된 바이트만큼의 전송이 보장되어있음. 분명 데이터는 동일한 시점의 데이터가 들어올건데, 저장하는 방식의 차이인것같아.
            print('name : ', self.name, time.time())
            try:  # 이때 다른 conn들도 continue
                if b'True' in data:
                    self.flag_changed = True
                    self.flag = True
                elif b'False' in data:
                    self.flag_changed = True
                    self.flag = False
                elif b'quit' in data:
                    self.conn.close()
                    self.live = False
                    break
                else:
                    pass
            except Exception as e:
                pass

            changed = self.manager.check_flagChanged_in_other_clients()
            if changed:
                if self.flag is True:
                    self.set_recvflag(self.flag)
                    self.flag = None
                    continue
                elif self.flag is False:
                    self.set_recvflag(self.flag)
                    self.flag = None
                    continue
                else:
                    continue
            if self.manager.sync is True:
                self.store_signal(data)
            else:
                pass




class AndroidTCPHandler(socketserver.BaseRequestHandler):
    manager = AndroidRecorderManager()
    isServerRunning = True

    def handle(self):  # it is called when clients connect this server.
        try:
            self.request.send(('%d recorder connect successfully' % self.manager.n_recorders).encode())
            self.recorder = AndroidRecorder(self.request, self.manager.n_recorders)
            self.manager.add_recorder(self.recorder)
            self.recorder.indicate_manager(self.manager)
            print(self.recorder.receiver.name, self.recorder.receiver)
            self.recorder.receiver.start()
            while self.isServerRunning:
                # self.manager.check_sync()
                if self.recorder.live == False:
                    print('recorder is dead')
                    break
            #self.recorder.receiver.terminate()
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
        # sleep(1)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    ServerStart()
