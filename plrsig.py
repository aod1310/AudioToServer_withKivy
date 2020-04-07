#!/usr/bin/env python
# coding: utf-8

# In[1]:


import librosa
import matplotlib.pyplot as plt
import numpy as np
import soundfile
import librosa.display as display
import os
from scipy.signal import welch, correlate


# In[26]:


def load_datas(folder):
    signals = []
    for data in os.listdir(folder):
        if data.endswith('.wav'):
            y, sr = librosa.load(folder+'/'+data, sr=16000, mono=True)
            signals.append(y)
    return signals

def load_data(path, duration=10):
    #y, sr = librosa.load(path, duration=duration, sr=16000, mono=False)
    y, sr = librosa.load(path, sr=16000, mono=False)
    return y


# In[3]:


def signal_spliter(y):
    mic1 = np.array(y[0, :])
    mic2 = np.array(y[1, :])
    return mic1, mic2


# In[4]:


def signal_normalizer(signal):
    norm_factor = 1.0 / max(np.min(signal), np.max(signal))
    return signal * norm_factor

def signal_abs_stft(signal, n_fft):
    return abs(librosa.core.stft(signal, n_fft=n_fft))

def stft_show(stft, sr=16000):
    plt.figure(figsize=(12, 5))
    display.specshow(librosa.amplitude_to_db(stft), sr=sr, y_axis='log', x_axis='time', cmap='coolwarm')
    plt.tight_layout()
    plt.show()


# signal sync : 1) cut the frames differ to another one
#               2) calculate correlate mic1 and mic2, so get sync!
def signal_sync(mic1, mic2, corr=True):
    if len(mic1) > len(mic2):
        if corr is True:
            mic1, mic2 = get_correlate(mic1, mic2)
        else:
            mic1 = mic1[:len(mic2)]
    elif len(mic1) < len(mic2):
        if corr is True:
            mic2, mic1 = get_correlate(mic2, mic1)
        else:
            mic2 = mic2[:len(mic1)]
    else:
        return mic1, mic2
    return mic1, mic2

def get_correlate(mic1, mic2):
    corr = correlate(mic1, mic2)
    a = np.argmax(corr)
    b = len(mic2)
    diff = np.abs(b-a)
    mic1 = mic1[diff:len(mic2)+diff]
    return mic1, mic2


# In[5]:


def calc_PSD(signal, n_fft, cur_weight=0.8):
    stft = signal_abs_stft(signal, n_fft)
    power_stft = stft ** 2  ## PSD = abs(stft)^2
    prev_weight = 1.0 - cur_weight
    tmp = [ cur_weight*power_stft[:, n-1] + prev_weight*(abs(stft[:,n])**2) for n in range(len(power_stft[1])-1, 0, -1) ] + [(abs(stft[:, 0]))**2]
    PSD_stft = tmp[::-1] ## 마지막 bin이 첫번째 인덱스에 들어갔으므로 뒤집어준다.
    return np.array(PSD_stft)


def calc_PSD_welch(signal, n_fft, cur_weight=0.8):
    #print(len(signal))
    stft = signal_abs_stft(signal, n_fft)
    f, _psd = welch(stft[0, :], nfft=n_fft, fs=16000)
    _psd_mic = [_psd]
    prev_weight = 1.0-cur_weight
    for n in range(1, len(stft[1])):
        _psd_mic.append( (cur_weight*_psd_mic[n-1]) + (prev_weight*(abs(stft[:,n])**2)) )
    print('PSD_welch done')
    return np.array(_psd_mic)


# In[6]:


def calc_PLR(mic1, mic2, n_fft, cur_weight=0.8):
    psd_mic1 = calc_PSD_welch(mic1, n_fft, cur_weight)
    psd_mic2 = calc_PSD_welch(mic2, n_fft, cur_weight)
    PLR = psd_mic1 / psd_mic2
    print('PLR done')
    return PLR

def calc_PLRsigF(mic1, mic2, n_fft, cur_weight=0.8, a=8.0, c=1.5):
    PLR = calc_PLR(mic1, mic2, n_fft, cur_weight)
    PLR_sigF = 1.0 / (1.0+np.exp(-1.0*a*(PLR-c)))
    print('PLR sigmoid done')
    return PLR_sigF

def apply_PLR_sigF(PLRsigF, stft_primary):
    return PLRsigF.T * stft_primary

def griffin_filtered_result(filtered_data, n_iter=30, win_length=512):
    return librosa.griffinlim(filtered_data, n_iter=n_iter, win_length=win_length)

def save_speech_wav(data, name, a, c, path, samplerate=16000):
    path = path + '/{0}+a_{1}+c_{2}.wav'.format(name, a, c)
    soundfile.write(path, data, samplerate=samplerate, format='WAV', subtype='PCM_16')
    
def save_spectrogram_png(data, name, a, c, path, samplerate=16000):
    path = path + '/{0}+a_{1}+c_{2}.png'.format(name, a, c)
    plt.figure(figsize=(12, 5))
    display.specshow(librosa.amplitude_to_db(data), sr=samplerate, y_axis='log', x_axis='time', cmap='coolwarm')
    plt.colorbar(format='%+2.0f dB')
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    
def save_sigmoid_png(a, c):
    path = './pr_tuning_results/images/PLR-sigmoid+a_{0}+c_{1}.png'.format(a, c)
    x = np.linspace(0, 4, num=400)
    y = 1.0 / (1.0 + np.exp(-1.0*a*(x-c)))
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    ax1.plot(x,y)
    ax1.set_xlabel('PLR')
    ax1.set_ylabel('gain')
    plt.savefig(path, dpi=300)


# In[13]:


def save_results(griffin, filtered, name, a, c, duration, n_fft, samplerate=16000):
    path_image = './pr_tuning_results/images/'
    path_wav = './pr_tuning_results/waves/'
    folder_name = 'a={0}_c={1}_nfft={2}_duration={3}'.format(a,c,n_fft,duration)
    if not os.path.exists(path_image+folder_name):
        os.mkdir(path_image+folder_name)
    if not os.path.exists(path_wav+folder_name):
        os.mkdir(path_wav+folder_name)
        
    path_image=path_image+folder_name
    path_wav=path_wav+folder_name
    
    save_speech_wav(griffin, name, a, c, path_wav, samplerate=samplerate)
    save_spectrogram_png(filtered, name, a, c, path_image, samplerate=samplerate)
    save_sigmoid_png(a, c)


# In[27]:


def main(name):
    n_fft=512
    cur_weight=0.8
    a=3.0
    c=1.63
    n_iter=30
    duration=''
    #print('n_fft={0}\ncur_weight={1}\na={2}\nc={3}\nn_iter={4}\nduration={5}'.format(n_fft, cur_weight, a, c, n_iter, duration))
    print('n_fft={0}\ncur_weight={1}\na={2}\nc={3}\nn_iter={4}'.format(n_fft, cur_weight, a, c, n_iter))
    path = './datasets/' + name + '.wav'
    
    #signal = load_data(path)
    signal = load_data(path, duration=duration)
    mic1, mic2 = signal_spliter(signal)
    #mic1 = signal_normalizer(mic1);mic2 = signal_normalizer(mic2)
    PLRsigF = calc_PLRsigF(mic1, mic2, n_fft=n_fft, cur_weight=cur_weight, a=a, c=c)
    filter_result = apply_PLR_sigF(PLRsigF, signal_abs_stft(mic1, n_fft))
    result = griffin_filtered_result(filter_result, n_iter=n_iter, win_length=n_fft)
    result = signal_normalizer(result)*2
    
    save_results(result, filter_result, name, a, c, duration, n_fft, samplerate=16000)





