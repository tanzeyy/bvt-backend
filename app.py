
import eventlet

eventlet.monkey_patch()

from weibo_crawler.weibo import run_wb
from aip import AipNlp
from flask_socketio import SocketIO, emit
from flask import Flask, jsonify, request
from flask_cors import CORS
import redis
import emoji
import time
import requests
import json
import APP_ID, API_KEY, SECRET_KEY from config


client = AipNlp(APP_ID, API_KEY, SECRET_KEY)

redis_conn = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)

app = Flask(__name__)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


@app.route("/api/auth_status", methods=['GET'])
def auth_status():
    access_token = redis_conn.get('access_token')
    if access_token:
        # Check validation
        response = requests.get(
            "https://api.weibo.com/2/account/get_uid.json", params={"access_token": access_token})
        if response.json().get('uid'):
            return jsonify({'status': 'done', 'message': '缓存中已有有效token，无需额外操作。'})
    else:
        return jsonify({'status': 'failed', 'message': '无有效授权，请点击按钮进行授权。'})


@app.route("/api/weibo_auth", methods=['GET'])
def weibo_auth():
    access_token = redis_conn.get('access_token')
    if access_token:
        # Check validation
        response = requests.get(
            "https://api.weibo.com/2/account/get_uid.json", params={"access_token": access_token})
        if response.json().get('uid'):
            return jsonify({'status': 'done', 'message': '已从缓存中读取token'})
    code = request.args.get('code')
    print(code)
    payload = {
        'client_id': '170128421',
        'client_secret': 'd2904572d71aaf88e9d491e0165d3647',
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://183.129.170.180:8085/auth_callback'
    }
    response = requests.post(
        'https://api.weibo.com/oauth2/access_token', data=payload)
    print(response.text)
    access_token = response.json().get('access_token')
    if access_token:
        redis_conn.set('access_token', access_token)
        return jsonify({'status': 'done', 'message': '缓存中的token失效，已重新获取。'})
    else:
        return jsonify({'status': 'failed', 'message': '因为意外原因失败。'})


@app.route('/api/get_uid', methods=['GET'])
def get_uid():
    screen_name = request.args.get('screen_name')
    if not screen_name:
        return jsonify({'message': '请提供正确的用户昵称', 'status': 'failed'})

    access_token = redis_conn.get('access_token')
    print(access_token)
    if access_token:
        uid = requests.get('https://api.weibo.com/2/users/show.json', params={
                           'access_token': access_token, 'screen_name': screen_name}).json().get('idstr')
        status = 'done'
    else:
        uid, status = None, 'failed'

    return jsonify({'uid': uid, 'status': status})


@socketio.on('get_weibo')
def get_weibo_data(message):
    user_id = message['uid']
    since_date = message['date']

    # Validate uid
    access_token = redis_conn.get('access_token')
    response = requests.get("https://api.weibo.com/2/users/show.json", params={
        'access_token': access_token,
        'uid': user_id
    })
    if (response.status_code == 400):
        emit("errorUid", {"status": "failed", "info": "wrongUID"})
        

    weibo_generator = run_wb(user_id, redis_conn, since_date=since_date)

    date_list = ['开始']  # Store dates that have occurred
    topic_data = {}
    status_data = {}

    for weibo, wb in weibo_generator:  # 'weibo' is current weibo object, 'wb' is an instance of weibo_crawler
        date = weibo.get("created_at")
        if not date:
            break

        if weibo.get('over'):
            break

        cur_date_idx = next(
            (i for i, d in enumerate(date_list) if date == d), -1)
        if cur_date_idx < 0:
            date_list.append(date)
            for topic, data in topic_data.items():
                data += [0]

        # Analyze topics
        retweet_id = weibo.get('retweet_id')
        if retweet_id:
            retweet_text = wb.get_long_weibo(retweet_id).get('text')
        else:
            retweet_text = ""
        full_text = "placeholder" + \
            weibo.get('text').split('//@')[0] + " " + retweet_text
        try:
            topic = client.topic('无题', emoji.demojize(full_text))
            tag_list = topic['item']['lv2_tag_list'] + \
                topic['item']['lv1_tag_list']
        except:
            tag_list = []

        # Format the topic data
        new_topics = set(tag['tag']
                         for tag in tag_list) - set(topic_data.keys())
        if new_topics:
            for topic in new_topics:
                topic_data[topic] = [0] + [0 for _ in date_list]

        for tag in tag_list:
            print(tag)
            topic_data[tag['tag']][cur_date_idx] += tag['score']

        topics = {
            "dates": date_list,
            "data": [{'name': topic, 'data': data, 'weight': sum(data)} for topic, data in topic_data.items()]
        }
        # [{"name": k, "weight": v} for k, v in cor_topics.items()]
        if date in status_data:
            status_data[date]["comments_count"] += weibo["comments_count"]
            status_data[date]["reposts_count"] += weibo["reposts_count"]
            status_data[date]["attitudes_count"] += weibo["attitudes_count"]
        else:
            status_data[date] = {"attitudes_count": weibo["attitudes_count"],
                                 "comments_count": weibo["comments_count"],
                                 "reposts_count": weibo["reposts_count"]}

        statuses = {
            "dates": list(status_data.keys()),
            "comments_count": [data["comments_count"] for data in status_data.values()],
            "attitudes_count": [data["attitudes_count"] for data in status_data.values()],
            "reposts_count": [data["reposts_count"] for data in status_data.values()]
        }

        emit("receiveData", {"data": {"topics": topics,
                                      "statuses": statuses}})
        time.sleep(0.5)

    emit("updateStatus", {"status": "done"})
    print(topics)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
