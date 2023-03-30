## Bot 设置

# ws 监听端口
PORT = 6655
# 代理
PROXY = 'http://localhost:1080'
# Bot 的提示信息（非 AI 回复的内容）的前缀
BOT_INFO_PREFIX = '[info] '
# 管理 QQ（好像目前没用到
ADMIN_QQ = 123456
# 限定只有这个群的群成员可以使用 Bot（不限于在该群中使用，也可其它群或私聊，但非该群成员私聊或在其他地方都不能使用
GROUP_ID = 123456
# 当回复消息在手机上显示的行数（估计值）超过该值时，转为合并转发消息发送
MAX_ROWS = 15
# revchatgpt 的后端接口
OPENAI_CHAT_WEB_BASE = "https://chatgpt-proxy.lss233.com/api/" # 'https://bypass.duti.tech/api/'
# 校园网登录链接
NETWORK_LOGIN_URL = ''


## 账号部分

OPENAI_API_KEY = ''
BING_COOKIE = ''
OPENAI_WEB_ACCOUNT = {
  # "email": "",
  # "password": "",
  "access_token": "",
  "proxy": PROXY,
  "paid": True,
  "model": "gpt-4",
}
# 
BARD_COOKIE = ''


## 模型参数设置

# OpenAI API 温度设定，越大，创新性越强，但准确度下降；范围0~2
OPENAI_TEMPERATURE = 1
# OpenAI API/Web 请求超时时间
OPENAI_TIMEOUT = 4*60
# 单条消息最多使用的 tokens 数（未实现）
# OPENAI_MAX_TOKENS = 4096
# Bing 的风格，"creative", "balanced", "precise"
BING_STYLE = 'creative'


## 命令

OPENAI_CHAT_API_CMDS = ['ai']
OPENAI_CHAT_WEB_CMDS = ['aai']
BING_CMDS = ['bing', 'nb']
BARD_CMDS = ['bard', 'gg']
# 当私聊或在群中被 @，且没有指定指令时，默认使用的指令
DEFAULT_CMD = OPENAI_CHAT_API_CMDS[0]

RESET_CMD = '!reset'
RELOAD_CMD = '!reload' # 未实现
USAGE_CMD = '!usage'
VOICE_CMD = '!voice'


# 初始化 Bing cookies
import http.cookies
BING_COOKIES = [{'name': key, 'value': morsel.value} for key, morsel in http.cookies.SimpleCookie(BING_COOKIE).items()]
