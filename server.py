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

lock = threading.Lock()
### https://stackoverflow.com/questions/35717109/python-class-object-sharing-between-processes-created-using-multiprocessing-modu ##
# 프로세스간의 클래스객체공유.
class AndroidRecorderManager:
    def __init__(self):
        self.recorders = {}
        self.n_recorders = len(self.recorders)
        self.cur_folder = None
        self.sync = False
        self.recorder_syncs = []
        self.t_check_sync = threading.Thread(target=self.check_sync, args=())
        self.t_check_sync.start()
        self.exist_saved = False

    def restart_recorders(self):
        recorders = self.get_recorders()
        barrier = threading.Barrier(len(recorders), action=self.notice_restarted, timeout=5)
        for recorder in recorders:
            print(recorder, recorder.receiver.name, ' receiver --> shutdown !')
            recorder.receiver_flag = False
            recorder.receiver.join()
            del recorder.receiver
            #recorder.generate_new_thread()
        print('receivers reboot....')
        for recorder in recorders:
            recorder.receiver_flag = True
            thread_restart_recorder = threading.Thread(target=self._restart_recorder, args=(recorder, barrier))
            thread_restart_recorder.start()
        del barrier

    def _restart_recorder(self, recorder, barrier):   ## poll 하는 시간을 x.000초로 맞추면 어느정도 동일한 지점에서부터 가져오니까 괜찮지않을까?
        try:
            recorder.generate_new_thread()
            barrier.wait()
            recorder.receiver.start()
            print(recorder.name, recorder.receiver.name, 'starts\n', time.time())
        except Exception as e:
            print(e)

    def notice_restarted(self):
        print('receivers restart')

    def add_recorder(self, recorder):
        self.recorders[recorder] = {'recorder': recorder, 'name': self.n_recorders, 'connection': recorder.conn}
        self.n_recorders = self.n_recorders + 1
        print('connected\n', recorder, recorder.conn)
        if self.n_recorders > 1:
            print('restart recorders for sync')
            self.restart_recorders()

    def remove_recorder(self, recorder):
        del self.recorders[recorder]
        self.n_recorders = self.n_recorders - 1

    def get_recorders(self):
        return [ recorder['recorder'] for recorder in self.recorders.values() ]

    def check_sync(self):
        while True:
            #print(self.n_recorders)
            if self.n_recorders > 0:
                try:
                    recorder_syncs = [recorder['recorder'].RECORD_START for recorder in self.recorders.values()]
                    recorder_frames = [len(recorder['recorder'].frames) for recorder in self.recorders.values()]
                except Exception as e:
                    continue
                if False not in recorder_syncs:
                    self.sync = True
                else:
                    self.sync = False
                    if 0 not in recorder_frames:
                        self.save_waves()
                del recorder_syncs
                del recorder_frames
        print('check sync dead')

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
        self.set_foldername()
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

    def check_flagChanged_in_other_clients(self):
        recorders = self.get_recorders()
        flag_changed = [ recorder.flag_changed for recorder in recorders ]
        if True in flag_changed:
            return True
        else:
            return False


    def decision_main_mic(self):
        pass




class AndroidRecorder:
    def __init__(self, conn, name):
        self.live = True
        self.RECORD_START = False
        self.sync = False
        self.frames = []
        self.conn = conn
        self.name = name
        self.receiver = None
        self.foldername = None
        self.manager = None
        self.barrier = None
        self.q = queue.Queue()
        self.flag_changed = False
        self.flag = None
        self.receiver_flag = True
        self.generate_new_thread()

    def generate_new_thread(self):
        self.receiver = threading.Thread(target=self.recv_data, args=())
        return self.receiver

    def indicate_manager(self, manager):
        self.manager = manager
        print('my manager : ', self.manager)
        return self.manager

    def get_foldername(self, path):
        self.foldername = path
        return path

    def set_sync(self, flag):
        self.sync = flag

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

        self.manager.check_sync()

    def store_signal(self, data):
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
            print(self.name, len(b''.join(self.frames)), self.frames[0])
            self.frames.clear()
        except Exception as e:
            print(e)
            print('there is no data to save')

    def recv_data(self):
        #print(self.receiver.name, 'starts')
        while self.receiver_flag is True:
            self.flag_changed = False
            data = self.conn.recv(1600)  # sendall은 지정된 바이트만큼의 전송이 보장되어있음. 분명 데이터는 동일한 시점의 데이터가 들어올건데, 저장하는 방식의 차이인것같아.
            try:  # 이때 다른 conn들도 continue
                if b'True' in data:
                    self.flag_changed = True
                    # self.flag = True
                    self.RECORD_START = True
                    print(self.name, 'True received')
                elif b'False' in data:
                    self.flag_changed = True
                    # self.flag = False
                    self.RECORD_START = False
                    print(self.name, 'False received')
                elif b'quit' in data:
                    print(self.receiver.name, 'called quit')
                    self.conn.close()
                    self.live = False
                    break
                else:
                    pass
            except Exception as e:
                pass
            changed = self.manager.check_flagChanged_in_other_clients()
            if changed:
                #self.manager.check_sync()
                continue

            if self.manager.sync:
                print('name : ', self.name, time.time())
                self.store_signal(data)




class AndroidTCPHandler(socketserver.BaseRequestHandler):
    manager = AndroidRecorderManager()
    isServerRunning = True

    def handle(self):  # it is called when clients connect this server.
        try:
            self.request.send(('%d recorder connect successfully' % self.manager.n_recorders).encode())
            self.recorder = AndroidRecorder(self.request, self.manager.n_recorders)
            self.recorder.indicate_manager(self.manager)
            self.recorder.receiver.start()
            self.manager.add_recorder(self.recorder)
            #(self.recorder.receiver.name, self.recorder.receiver)
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
    print('if you want close this server, press CTRL-C')

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
