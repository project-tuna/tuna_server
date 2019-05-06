from django.http import HttpResponse, HttpRequest, Http404
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


from audio_handle.models import Audio, Demo
import uuid
import hashlib
import json

from audio_handle.tasks import audio_handler
from tuna_server.celerytask import app

# Create your views here.
def index(request):
    # 储存音频原文件
    audio = request.FILES.get('audio')
    file_name = str(uuid.uuid4())
    default_storage.save('./source/%s.wav' % (file_name), ContentFile(audio.read()))

    # 查询所属歌曲
    source_key = request.POST.get('source')
    object = Demo.objects.get(pk=source_key)

    # 设置通用变量
    demo_path = './audios/demo/' + object.file_name
    bgm_path = './audios/bgm/' + object.file_name
    media_root = settings.MEDIA_ROOT

    # 音频处理队列
    task = audio_handler.delay(file_name=file_name, demo_path=demo_path, bgm_path=bgm_path, media_root=media_root)

    # 文件数据写入数据库
    hash = hashlib.md5()
    hash.update(audio.read())
    row = Audio(file_name=file_name, md5=hash.hexdigest(), target=object, task_id=task.id)
    row.save()

    # 返回数据
    body = {}
    body['task_id'] = task.id
    return HttpResponse(json.dumps(body), content_type='application/json')


def get_task(request):
    task_id = request.GET.get('task_id')
    try:
        audio = Audio.objects.get(task_id=task_id)
    except Audio.DoesNotExist:
        raise Http404('Task not found')

    status = audio.status

    if status == 'PENDING':
        status = app.AsyncResult(task_id).state
        if status != 'PENDING':
            audio.status = status
            audio.save()

    body = {}
    body['status'] = status

    if status == 'SUCCESS':
        file_name = Audio.objects.get(task_id=task_id).file_name
        body['audio'] = settings.HOST + '/audios/output/' + file_name + '.wav'

    return HttpResponse(json.dumps(body), content_type='application/json')


def flush_list(request):
    file = open('%s/audio_list.json'%(settings.MEDIA_ROOT), 'r')
    data = json.loads(file.read())
    for item in data['list']:
        try:
            Demo.objects.get(name=item['name'])
        except Demo.DoesNotExist:
            row = Demo(name=item['name'], file_name=item['file_name'])
            row.save()
    return HttpResponse('success')

def list(request):
    # 获取歌单列表
    object = Demo.objects.all()

    # 构造返回数据
    body = []
    
    for item in object:
        itemObj = {
            'id': item.pk,
            'name': item.name,
            'artist': item.artist,
            'lyric': item.lyric,
            'accompaniment_url': item.accompaniment_url,
            'offset': item.offset,
        }
        body.append(itemObj)
    return HttpResponse(json.dumps(body), content_type='application/json')

def get_demo(request, demo_id):
    try:
        item = Demo.objects.get(pk=demo_id)
    except Demo.DoesNotExist:
        raise Http404('Demo not found')
    body = {
        'id': item.pk,
        'name': item.name,
        'artist': item.artist,
        'lyric': item.lyric,
        'accompaniment_url': item.accompaniment_url, 
        'offset': item.offset,
    }
    return HttpResponse(json.dumps(body), content_type='application/json')
