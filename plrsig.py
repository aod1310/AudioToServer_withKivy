#!/usr/bin/env python
# coding: utf-8

# In[1]:


import librosa
import numpy as np
import os
from scipy.signal import welch, correlate
import lws

# In[26]:


def load_datas(folder):
    signals = []
    for data in os.listdir(folder):
        if data.endswith('.wav'):
            y, sr = librosa.load(folder + '/' + data, sr=16000, mono=True)
            signals.append(y)
    return signals


def load_data(path, duration=10):
    # y, sr = librosa.load(path, duration=duration, sr=16000, mono=False)
    y, sr = librosa.load(path, sr=16000, mono=False)
    return y


# In[3]:


def signal_spliter(y):
    mic1 = np.array(y[0, :])
    mic2 = np.array(y[1, :])
    return mic1, mic2

def signal_normalizer(signal):
    norm_factor = 1.0 / max(np.min(signal), np.max(signal))
    return signal * norm_factor


def signal_abs_stft(signal, n_fft):
    return abs(librosa.core.stft(signal, n_fft=n_fft))

# signal sync : 1) cut the frames differ to another one
#               2) calculate correlate mic1 and mic2, so get sync!
def signal_sync(mic1, mic2, corr=True):
    if len(mic1) > len(mic2):
        if corr is True:
            mic1, mic2 = get_correlate(mic1, mic2)
        else:
            diff = len(mic1) - len(mic2)
            mic1 = mic1[diff:]
    elif len(mic1) < len(mic2):
        if corr is True:
            mic2, mic1 = get_correlate(mic2, mic1)
        else:
            diff = len(mic2) - len(mic1)
            mic2 = mic2[diff:]
    else:
        return mic1, mic2
    return mic1, mic2


def get_correlate(mic1, mic2):
    corr = correlate(mic1, mic2)
    a = np.argmax(corr)
    b = len(mic2)
    diff = np.abs(b - a)
    mic1 = mic1[diff:len(mic2) + diff]
    return mic1, mic2


# In[5]:


def calc_PSD(signal, n_fft, cur_weight=0.8):
    stft = signal_abs_stft(signal, n_fft)
    power_stft = stft ** 2  ## PSD = abs(stft)^2
    prev_weight = 1.0 - cur_weight
    tmp = [cur_weight * power_stft[:, n - 1] + prev_weight * (abs(stft[:, n]) ** 2) for n in
           range(len(power_stft[1]) - 1, 0, -1)] + [(abs(stft[:, 0])) ** 2]
    PSD_stft = tmp[::-1]  ## 마지막 bin이 첫번째 인덱스에 들어갔으므로 뒤집어준다.
    return np.array(PSD_stft)


def calc_PSD_welch(signal, n_fft, cur_weight=0.8):
    # print(len(signal))
    stft = signal_abs_stft(signal, n_fft)
    f, _psd = welch(stft[0, :], nfft=n_fft, fs=16000)
    _psd_mic = [_psd]
    prev_weight = 1.0 - cur_weight
    for n in range(1, len(stft[1])):
        _psd_mic.append((cur_weight * _psd_mic[n - 1]) + (prev_weight * (abs(stft[:, n]) ** 2)))
    print('PSD_welch done')
    return np.array(_psd_mic)


# In[6]:
def find_mainspeaker(psd1, psd2):
    if sum(sum(psd1)) > sum(sum(psd2)):
        return psd1, psd2
    else:
        return psd2, psd1
    pass

def calc_PLR(mic1, mic2, n_fft, cur_weight=0.8):
    psd_mic1 = calc_PSD_welch(mic1, n_fft, cur_weight)
    psd_mic2 = calc_PSD_welch(mic2, n_fft, cur_weight)
    main_mic, sub_mic = find_mainspeaker(psd_mic1, psd_mic2)   # find mainspeaker
    PLR = main_mic / sub_mic
    print('PLR done')
    return PLR


def calc_PLRsigF(mic1, mic2, n_fft, cur_weight=0.8, a=8.0, c=1.5):
    PLR = calc_PLR(mic1, mic2, n_fft, cur_weight)
    PLR_sigF = 1.0 / (1.0 + np.exp(-1.0 * a * (PLR - c)))
    print('PLR sigmoid done')
    return PLR_sigF


def apply_PLR_sigF(PLRsigF, stft_primary):
    return PLRsigF.T * stft_primary


def griffin_filtered_result(filtered_data, n_iter=30, win_length=512):
    return librosa.griffinlim(filtered_data, n_iter=n_iter, win_length=win_length)

def lws(filtered):
    lws_processor = lws.lws(512, 128, mode='music')
    lws_run = lws_processor.run_lws(filtered.T)
    lws_result = librosa.core.istft(lws_run.T)
    return lws_result






