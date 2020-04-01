# 后端服务器

## 依赖

- Python >= 3.6.*

- Flask
- Flask-SocketIO
- Flask-CORS
- [BaiduAIP](https://github.com/Baidu-AIP/python-sdk)
- [weibo-crawler](https://github.com/dataabc/weibo-crawler)

其余环境可通过pip install -r requirements.txt 一键安装。

## 运行

首先，将`app.py`里的：APP_ID、API_KEY、SECRET_KEY修改为为自己的BaiduAIP授权码，并配置redis数据库地址。

然后，使用

```bash
python app.py
```

来运行后端服务器。如果需要修改监听地址和端口以及其他的配置请查阅`app.py`里的`__main__`。

## 注意

- 如果需要修改程序，请务必将

  ```python
  import eventlet
  eventlet.monkey_patch()
  ```

  放置在你的程序入口的最开始处；

- 如有微博相关API报错，请修改对应的参数和配置;

- 由于已经对所引用的第三方库做了一定的修改，如非必要，请不要修改`./aip`和`./weibo_crawler`里的文件，以免程序出现异常行为。