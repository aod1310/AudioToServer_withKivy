from jnius import autoclass

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.utils import platform
import socket
from audiostream import get_input
import threading

lock = threading.Lock()


class AndroidClient:
    msg = ''

    def __init__(self):
        self.clientsocket = None
        self.RECORD = False
        self.recording = get_input(callback=self._record_callback,
                                   source='mic',
                                   rate=16000,
                                   channels=1,
                                   encoding=16,
                                   buffersize=1600)


    def connectServer(self, ip):
        try :
            self.HOST = ip
            self.PORT = 10000
            self.ADDR = (self.HOST, self.PORT)
            self.clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.clientsocket.connect(self.ADDR)
            self.msg = self.clientsocket.recv(1024).decode().strip()
        except Exception as e:
            print(e)
            return False

    def start_record(self, instance):
        try:
            if self.RECORD:
                self.clientsocket.send('False'.encode())
                instance.text = 'stop record'
                lock.acquire()
                self.RECORD = False
                lock.release()
                self.recording.stop()
                del self.t_poll
            else:
                self.clientsocket.send('True'.encode())
                instance.text = 'start record'
                lock.acquire()
                self.RECORD = True
                lock.release()
                self.recording.start()
                self.t_poll = threading.Thread(target=self._thread_poll, args=())
                self.t_poll.start()
        except Exception as e:
            print(e)
            print('recording fail because of no connection.')

    def _record_callback(self, buf):
        self.clientsocket.send(bytes(buf))
        #print(buf)
        #self.msg = buf[:10]

    # threads can only be started once!! if i wanna use this method, generate another thread
    def _thread_poll(self):
        while self.RECORD:
            self.recording.poll()




class Root(BoxLayout):
    def __init__(self, **kwargs):
        super(Root, self).__init__(**kwargs)
        if platform == 'android':
            DisplayMetrics = autoclass('android.util.DisplayMetrics')
            metrics = DisplayMetrics()

            txt =  'DPI : {}'.format(metrics.getDeviceDensity())
            self.lblMetrics = Label(text=txt)
            self.add_widget(self.lblMetrics)

        self.lblConn = Label(text=AndroidClient.msg) # test
        self.add_widget(self.lblConn)


class ButtonsLayout(BoxLayout):
    def __init__(self, **kwargs):
        global client
        super(ButtonsLayout, self).__init__(**kwargs)
        self.size_hint = (1, None)
        self.height = 200

        record_start = Button(text='start_record')
        record_start.bind(on_press=client.start_record)
        self.add_widget(record_start)


class lblofIPLayout(BoxLayout):
    lbl = Label(text='wait connecting')

    def __init__(self, **kwargs):
        super(lblofIPLayout, self).__init__(**kwargs)
        self.size_hint = (1, None)
        self.height = 300
        self.add_widget(self.lbl)
        ipinputlayout = IPInputLayout()
        self.add_widget(ipinputlayout)


class IPInputLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(IPInputLayout, self).__init__(**kwargs)
        self.connect = False
        self.size_hint = (1, None)
        self.height = 200

        self.ip_input = TextInput(size_hint=(.35, 1))

        self.btn_connect = Button(text='Connect Server', size_hint=(.35, 1))
        self.btn_connect.bind(on_press=self.connectServer)
        self.btn_connect.disabled = self.connect

        self.btn_disconnect = Button(text='Disconnect', size_hint=(.30, 1))
        self.btn_disconnect.bind(on_press=self.disconnectServer)
        self.btn_disconnect.disabled = not self.connect

        self.add_widget(self.ip_input)
        self.add_widget(self.btn_connect)
        self.add_widget(self.btn_disconnect)

    def connectServer(self, instance):
        global client
        ip = self.ip_input.text
        try:
            if len(ip) == 0:
                print('no ip')
                return None
            re = client.connectServer(ip)
            if re is False: return
            lblofIPLayout.lbl.text = 'Connect Success'
            self.connect = True
            self.updateButtons()
        except Exception as e:
            print(e)
            print('wrong address or server down')

    def disconnectServer(self, instance):
        global client
        try:
            print('disconnect server called')
            client.clientsocket.send('quit'.encode())
            lblofIPLayout.lbl.text = 'Disconnected'
            self.connect = False
            self.updateButtons()

        except Exception as e:
            print(e)
            print('no client socket')

    def updateButtons(self):
        self.btn_disconnect.disabled = not self.connect
        self.btn_connect.disabled = self.connect


class AppLoader(App):
    def build(self):
        root = Root(orientation='vertical')
        lblofinputL = lblofIPLayout(orientation='vertical')
        btnsL = ButtonsLayout()
        root.add_widget(lblofinputL)
        root.add_widget(btnsL)

        return root


if __name__ == '__main__':
    ### Global Android Client to access Kivy object ###
    client = AndroidClient()
    AppLoader().run()
