# Tuna_Server 自动调音后端服务

## 前言

这是一个自动调音项目的后端服务，根据目标音频的干音来进行 DTW(动态时间规整) 以及 Pitch Shift 达到调音的效果。

## 启动

1. 安装依赖
    ``` bash
    pip3 install -r requirements.txt
    ```

2. 添加目标干音到 /audios/demo 下

3. 修改 /audios/audio_list.json 数据，name 为需要在前端展示的歌曲名，file_name 为在本地文件的文件名

4. 添加伴奏到 /audios/bgm 下，文件名需与干音相同

5. 启动服务

    ``` bash
    python3 manage.py makemigrations && python3 manage.py migrate && python3 manage.py runserver
    ```
    
6. 刷新数据库歌单列表

    访问 http://127.0.0.1:8000/audio/flush_list 以刷新数据库里歌单列表，照理来说应该是跑个 bash 脚本干这活，但是我没找到数据库操作的命令行工具。
    
## 附言

第一个 Python 项目，各种结构不是很好，配置也不够全，为了毕业（