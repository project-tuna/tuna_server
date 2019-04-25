from django.http import HttpResponse, HttpRequest
import json
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

import python_speech_features
from python_speech_features import sigproc
import librosa
from dtw import dtw
import numpy
from numpy import inf
import scipy.spatial
from scipy.fftpack import dct, rfft
import scipy.io

import amfm_decompy.basic_tools as basic
import amfm_decompy.pYAAPT as pYAAPT
import math

from pydub import AudioSegment

from audio_handle.models import Audio, Demo
import uuid
import hashlib
import json


def mfcc(frames,samplerate=16000,winlen=0.025,winstep=0.01,numcep=13,
        nfilt=26,nfft=512,lowfreq=0,highfreq=None,preemph=0.97,ceplifter=22,appendEnergy=True):

    pspec = sigproc.powspec(frames,nfft)
    energy = numpy.sum(pspec,1) # this stores the total energy in each frame
    energy = numpy.where(energy == 0,numpy.finfo(float).eps,energy) # if energy is zero, we get problems with log

    fb = python_speech_features.get_filterbanks(nfilt,nfft,samplerate,lowfreq,highfreq)
    feat = numpy.dot(pspec,fb.T) # compute the filterbank energies
    feat = numpy.where(feat == 0,numpy.finfo(float).eps,feat) # if feat is zero, we get problems with log
    feat = numpy.log(feat)
    feat = dct(feat, type=2, axis=1, norm='ortho')[:,:numcep]
    feat = python_speech_features.lifter(feat,ceplifter)
    if appendEnergy: feat[:,0] = numpy.log(energy) # replace first cepstral coefficient with log of frame energy
    return feat


def audio_dtw(file_name):
    # wav: 时域信号 array fs: 频率 num
    file_path = '{media_root}/source/{file_name}.wav'
    media_root = settings.MEDIA_ROOT
    file_path = file_path.format(media_root=media_root, file_name=file_name)
    print(file_path)
    wav, fs = librosa.load(file_path, sr=None)
    window_size = 1024
    step = round(window_size/3)
    frames = sigproc.framesig(wav, window_size, step, lambda x:numpy.hanning(x))

    wav_2, fs_2 = librosa.load('%s/demo/voice.wav'%(settings.MEDIA_ROOT), sr=None)
    frames_2 = sigproc.framesig(wav_2, window_size, step, lambda x:numpy.hanning(x))
    mel = mfcc(frames, fs, nfft=1024)
    mel_2 = mfcc(frames_2, fs, nfft=1024)

    # dtw
    d, cost_matrix, acc_cost_matrix, path = dtw(mel, mel_2, scipy.spatial.distance.cosine, warp=1, w=abs(len(mel) - len(mel_2)), s=1.0)

    # path 分散处理
    frames_3 = numpy.full(shape=frames_2.shape, fill_value=0, dtype='float32')
    same_slope_tick = 0
    dot_source_tick = 0
    dot_target_tick = 0
    for i in range(path[0].size):
        path[0][i] += dot_source_tick
        path[1][i] += dot_target_tick
        if (i != 0):
            if (path[1][i] == pre_dot_target):
                line_slope = inf
            elif (path[0][i] == pre_dot_source):
                line_slope = 0
            else:
                line_slope = 1
            if (i != 1):
                if ((pre_line_slope == inf and line_slope == inf) or (pre_line_slope == 0 and line_slope == 0)):
                    same_slope_tick += 1
                else:
                    same_slope_tick = 0
                if (same_slope_tick >= 3):
                    if (line_slope == inf):
                        dot_target_tick += 1
                        path[1][i] += 1
                    else:
                        dot_source_tick += 1
                        path[0][i] += 1
                    same_slope_tick = 0
                    # 修改点后重新计算斜率
                    if (path[1][i] == pre_dot_target):
                        line_slope = inf
                    elif (path[0][i] == pre_dot_source):
                        line_slope = 0
                    else:
                        line_slope = 1
            pre_line_slope = line_slope
        pre_dot_source = path[0][i]
        pre_dot_target = path[1][i]
    for i in range(path[0].size):
        frame_source = path[0][i]
        frame_target = path[1][i]
        if (frame_target >= frames_2.shape[0]):
            break
        elif (frame_source >= frames.shape[0]):
            frame = frames[frames.shape[0] - 1]
        else:
            frame = frames[frame_source]
        frames_3[frame_target] = frame

    # 生成完整时域信号
    len_frame = frames_3.shape[0]
    output = numpy.full(shape=(step * (len_frame - 1) + window_size), fill_value=0, dtype='float32')
    for i in range(len_frame):
        output[i*step:i*step+window_size] += frames_3[i]
    output_path = '{media_root}/dtw/{file_name}.wav'
    output_path = output_path.format(media_root=media_root, file_name=file_name)
    librosa.output.write_wav(output_path, output, fs)


def audio_pitch(file_name):
    # load audio
    media_root = settings.MEDIA_ROOT
    source_path = '{media_root}/dtw/{file_name}.wav'
    source_path = source_path.format(media_root=media_root, file_name=file_name)
    signal_source = basic.SignalObj(source_path)
    signal_target = basic.SignalObj('%s/demo/voice.wav'%(settings.MEDIA_ROOT))

    # YAAPT pitches
    pitches_source = pYAAPT.yaapt(signal_source, frame_length=40, tda_frame_length=40, fft_length=2048, f0_min=75,
                                  f0_max=600)
    pitches_target = pYAAPT.yaapt(signal_target, frame_length=40, tda_frame_length=40, fft_length=2048, f0_min=75,
                                  f0_max=600)
    # Main
    wav, fs = librosa.load(source_path, sr=None)
    output = numpy.full(shape=(len(wav)), fill_value=0, dtype='float32')
    length = 4096
    for i in range(0, len(wav), int(length / 6)):
        # time: /10ms
        time = int(i / fs * 100)
        if (time < len(pitches_source.samp_values) and time < len(pitches_target.samp_values)):
            source_pitch = pitches_source.samp_values[time]
            target_pitch = pitches_target.samp_values[time]
            # 底数常量为相邻两个音高频率关系
            # 例如：A3音符与A4的频率分别为220.0Hz,440.0Hz, 根据十二平均律已知两个音音阶差为12，设常量为t，频率关系则为 440 = 220 * t ** 12, t = pow(440 / 220, 1.0/12)
            n_steps = 0
            if (source_pitch != 0 and target_pitch != 0):
                n_steps = math.log(target_pitch / source_pitch, pow(2, 1.0 / 12))
            new_frame = librosa.effects.pitch_shift(y=numpy.hanning(len(wav[i:i + length])) * wav[i:i + length], sr=fs,
                                                    n_steps=n_steps)
            output[i:i + length] += new_frame

    # 混响效果，听起来效果不是很好。
    # fx = (
    #     AudioEffectsChain()
    #     .highshelf()
    #     .reverb()
    #     # .phaser()
    #     .lowshelf()
    # )
    # output = fx(output)

    # 写入文件
    output_path = '{media_root}/pitch/{file_name}.wav'
    output_path = output_path.format(media_root=media_root, file_name=file_name)
    librosa.output.write_wav(output_path, output, fs)


def audio_remix(file_name):
    media_root = settings.MEDIA_ROOT
    source_path = '{media_root}/pitch/{file_name}.wav'
    source_path = source_path.format(media_root=media_root, file_name=file_name)

    sound1 = AudioSegment.from_file(source_path)
    sound2 = AudioSegment.from_file("%s/bgm/bgm.wav"%(settings.MEDIA_ROOT))

    combined = sound1.overlay(sound2)

    output_path = '{media_root}/output/{file_name}.wav'
    output_path = output_path.format(media_root=media_root, file_name=file_name)
    combined.export(output_path, format='mp3')


# Create your views here.
def index(request):
    audio = request.FILES.get('audio')
    file_name = str(uuid.uuid4())
    path = default_storage.save('./source/%s.wav' % (file_name), ContentFile(audio.read()))
    source_key = request.POST.get('source')
    object = Demo.objects.get(pk=source_key)
    hash = hashlib.md5()
    hash.update(audio.read())
    row = Audio(file_name=file_name, md5=hash.hexdigest(), target=object)
    row.save()
    audio_dtw(file_name)
    audio_pitch(file_name)
    audio_remix(file_name)
    body = {}
    body['audio'] = '%s%soutput/%s.wav'%(settings.HOST, settings.MEDIA_URL, file_name)
    return HttpResponse(json.dumps(body), content_type='application/json')
    return HttpResponse('success')


def flush_list(request):
    Demo.objects.all().delete()
    file = open('%s/audio_list.json'%(settings.MEDIA_ROOT), 'r')
    data = json.loads(file.read())
    for item in data['list']:
        row = Demo(name=item['name'], file_name=item['file_name'])
        row.save()
    return HttpResponse('success')
