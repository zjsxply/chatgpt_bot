import os
import tenacity
import asyncio
from datetime import datetime, timedelta
import logging

import config

import openai
import openai_async
import tiktoken

import EdgeGPT

from revChatGPT import V1

import Bard


os.environ['HTTP_PROXY'] = config.PROXY
os.environ['HTTPS_PROXY'] = config.PROXY
openai.proxy = config.PROXY
openai.api_key = config.OPENAI_API_KEY

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def _count_tokens(messages: list[dict], model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        logger.warning("gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
        return _count_tokens(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        logger.warning("gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return _count_tokens(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens

def _remove_histories(messages, max_tokens=4096, min_max_generate_tokens=2048):
    '''返回裁剪后的对话及其prompt_tokens'''

    # 保留 system 消息
    system_msg = [msg for msg in messages if msg.get("role") == "system"]
    system_tokens = _count_tokens(system_msg)

    chat_tokens = 0
    chat_msg_rev = [messages[-1]]
    # 倒序计算各次对话 token 数
    for ans, ques in zip(messages[-1::-2], messages[-3::-2]):
        # 到达最后的 system 时停止
        if ques.get("role") == "system":
            break
        
        # 计算本次对话两条消息的 token 数
        tokens = _count_tokens([ans, ques])
        if system_tokens + chat_tokens + tokens + min_max_generate_tokens <= max_tokens:
            chat_tokens += tokens
            chat_msg_rev.extend([ans, ques])
        else:
            break

    return system_msg + chat_msg_rev[::-1], system_tokens + chat_tokens

@tenacity.retry(stop=tenacity.stop_after_attempt(3), after=tenacity.after_log(logger, logging.ERROR), reraise=True, wait=tenacity.wait_exponential(1, 3))
async def _request_openai_chat_api(msg):
    '''向 OpenAi 发送请求，出错自动重试'''
    """ async for chunk in openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=msg,
            temperature=OPENAI_TEMPERATURE,
            timeout=OPENAI_TIMEOUT,
            stream=True,
            # max_tokens=max_tokens-prompt_tokens,
        ):
        print(chunk) """
    return await openai_async.chat_complete(
        config.OPENAI_API_KEY,
        timeout=config.OPENAI_TIMEOUT,
        payload={
            "model": "gpt-3.5-turbo",
            "messages": msg,
            "temperature": config.OPENAI_TEMPERATURE,
        },
    )

async def ask_chat_api(messages, max_tokens=4096):
    '''自动清除过长的历史消息，并对话'''
    msg, prompt_tokens = _remove_histories(messages)
    resp = await _request_openai_chat_api(msg)
    if 'error' in resp:
        if resp['error']['type'] == 'insufficient_quota':
            raise RuntimeError('API账户余额不足')
    finish_reason = resp['choices'][0]['finish_reason']

    msg.append({"role": "assistant", "content": resp["choices"][0]["message"]["content"]})
    return msg, finish_reason

@tenacity.retry(stop=tenacity.stop_after_attempt(3), after=tenacity.after_log(logger, logging.ERROR), reraise=True, wait=tenacity.wait_exponential(1, 3))
async def _request_openai_credit_api():
    '''向 OpenAi 发送请求，出错自动重试'''
    """ return await openai_async.credit_grants(
        config.OPENAI_API_KEY,
        timeout=10,
        payload={},
    ) """
    r = await openai_async.subscription(
        config.OPENAI_API_KEY,
        timeout=10,
        payload={},
    )
    expires_at, total_granted = datetime.fromtimestamp(r["access_until"]), r["hard_limit_usd"]
    
    # 获取当前日期和时间（格林尼治时间）
    now = datetime.utcnow()
    
    # 计算90天前的日期
    delta = timedelta(days=90)
    days_ago = now - delta
    
    r = await openai_async.usage(
        config.OPENAI_API_KEY,
        timeout=10,
        payload={'start_date': days_ago.strftime('%Y-%m-%d'), 'end_date': now.strftime('%Y-%m-%d')},
    )
    total_used = float(r["total_usage"]) / 100
    total_available = float(total_granted) - float(total_used)

    return total_used, total_available, total_granted, expires_at

async def check_credits():
    """ resp = await _request_openai_credit_api()
    return resp['total_used'], resp['total_available'], resp['total_granted'], datetime.fromtimestamp(resp['grants']['data'][0]['expires_at']) """
    return await _request_openai_credit_api()

# OpenAI Web

openai_web_lock = asyncio.Lock()
chatbot = V1.AsyncChatbot(config=config.OPENAI_WEB_ACCOUNT)
V1.BASE_URL = config.OPENAI_CHAT_WEB_BASE

# Session 内含 Bing

class Session:
    '''各 AI model 的会话示例'''
    def __init__(self, model: str, session_id: str):
        self.model = model
        self.id = session_id
        self.lock = asyncio.Lock()
        if model in config.OPENAI_CHAT_API_CMDS:
            self.history = []
        elif model in config.BING_CMDS:
            self.bot = EdgeGPT.Chatbot(cookies=config.BING_COOKIES)
        elif model in config.OPENAI_CHAT_WEB_CMDS:
            self.conversation_id = None
            self.parent_id = None
        elif model in config.BARD_CMDS:
            self.bot = Bard.Chatbot(session_id=config.BARD_COOKIE)
        self.voice = False
        self.last_active = datetime.now()
    
    async def ask(self, question: str) -> tuple[str, str]:
        '''询问问题中，获得锁，阻塞下一次提问'''
        self.last_active = datetime.now()
        async with self.lock:
            if self.model in config.OPENAI_CHAT_API_CMDS:
                msg = {"role": "user", "content": question}
                if _count_tokens([msg]) > 4096:
                    raise ValueError(f'您的输入超出 OpenAI gpt-3.5-turbo 模型的最大输入长度！最大支持 4096 tokens，约为 1300 汉字或 3000 英文单词，而您输入了 {_count_tokens([msg])} tokens')
                self.history.append(msg)
                self.history, finish_reason = await ask_chat_api(self.history)
                reply = self.history[-1]['content'].strip()
            
            elif self.model in config.BING_CMDS:
                if len(question) > 2000:
                    raise ValueError(f'您的输入超出 Bing Chat 的最大输入长度！最大支持 2000 字符，而您输入了 {len(question)} 字符')
                reply_obj = await self.bot.ask(prompt=question, conversation_style=eval(f'EdgeGPT.ConversationStyle.{config.BING_STYLE}'))
                # reply = html.unescape.unquote(reply_obj['item']['messages'][-1]['text'])
                reply = reply_obj['item']['messages'][-1]['adaptiveCards'][0]['body'][0]['text']
                """ sources_obj = reply_obj['item']['messages'][-1]['sourceAttributions']
                sources = '\n'.join(f"{i}. {sources_obj[i]['providerDisplayName']}{sources_obj[i]['seeMoreUrl']}" for i in range(len(sources_obj)))
                if not sources:
                    reply += '\n\n来源：\n' + suggested_responses """
                suggested_responses = '\n'.join(r['text'] for r in reply_obj['item']['messages'][-1]['suggestedResponses'])
                if suggested_responses:
                    reply += '\n\n您可能想问：\n' + suggested_responses
                finish_reason = 'stop' # 无法检测 默认stop
            
            elif self.model in config.OPENAI_CHAT_WEB_CMDS:
                async with  openai_web_lock:
                    async for data in chatbot.ask(prompt=question, conversation_id=self.conversation_id, timeout=config.OPENAI_TIMEOUT):
                        pass
                reply = data["message"]
                if not self.conversation_id:
                    # 记录对话 id，标示对话已初始化完毕
                    self.conversation_id = data["conversation_id"]
                    # 会话 id 置为标题
                    try:
                        await chatbot.change_title(self.conversation_id, self.id)
                    except Exception as e:
                        logger.warning("OpenAI Web 页面设置会话标题出错，session_id: {self.id}, Error: {e}")
                self.parent_id = data["parent_id"]
                # chatbot 不记录 conversation_id
                chatbot.conversation_id = None
                finish_reason = 'stop' # 无法检测 默认stop
            
            elif self.model in config.BARD_CMDS:
                results = self.bot.ask(question)
                reply = results["content"]
                finish_reason = 'stop' # 无法检测 默认stop
        
        self.last_active = datetime.now()
        return reply, finish_reason
    
    async def rm_history(self) -> None:
        async with  self.lock:
            if self.model in config.OPENAI_CHAT_API_CMDS:
                self.history = []
            elif self.model in config.BING_CMDS:
                await self.bot.reset()
            elif self.model in config.OPENAI_CHAT_WEB_CMDS:
                await chatbot.delete_conversation(self.conversation_id)
                self.conversation_id = None
            elif self.model in config.BARD_CMDS:
                self.bot.conversation_id = ""
                self.bot.response_id = ""
                self.bot.choice_id = ""
    
    def set_voice(self, switch=None) -> bool:
        if switch is None:
            self.voice = not self.voice
        else:
            self.voice = switch
        return self.voice

class Sessions:
    '''A set storing sessions. '''
    def __init__(self):
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def add(self, model: str, id: str) -> None:
        if id in self.sessions:
            raise ValueError(f'会话已存在：{id}')
        async with self.lock:
            self.sessions[id] = Session(model, id)

    async def remove(self, session_id: str) -> None:
        if session_id in self.sessions:
            async with self.lock:
                del self.sessions[session_id]

    def list(self) -> list:
        return list(self.sessions.keys())
    
    async def ask(self, model: str, session_id: str, question: str) -> tuple[str, str]:
        if session_id not in self.sessions:
            await self.add(model, session_id)
        return await self.sessions[session_id].ask(question)
    
    async def rm_history(self, session_id: str) -> None:
        return await self.sessions[session_id].rm_history()
    
    async def set_voice(self, model: str, session_id: str, switch=None) -> None:
        if session_id not in self.sessions:
            await self.add(model, session_id)
        return self.sessions[session_id].set_voice(switch)
    
    def is_voice(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        return self.sessions[session_id].voice
