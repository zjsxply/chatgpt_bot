from aiocqhttp import CQHttp, Event
from aiocqhttp import Message, MessageSegment
from aiocqhttp.message import unescape
import logging
import re
import pypinyin

import utilities
import render
import adapter
import config


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

bot = CQHttp()

sessions = adapter.Sessions()

def generate_session_id(model: str, event: Event) -> str:
    '''生成会话 id：[group_id]-[anonymous_id]-user_id-model'''
    session_id = ''
    if event.message_type == 'group':
        session_id += f'{event.group_id}-'
        if event.anonymous:
            session_id += f'{event.anonymous["name"]}-'
    session_id += f'{event.user_id}-{model}'
    return session_id

def mask_sensitive_text(text_list: list, regex_file: str) -> list:
    '''
    text_list: 要过滤敏感词的文本列表
    regex_file: 敏感词匹配正则表达式 txt 路径，一行一个
    '''
    with open(regex_file, encoding='UTF-8') as f:
        patterns = [re.compile(line.strip()) for line in f]
    def _to_huati(s: str) -> str:
        result = ''
        for l in s:
            if 'a' <= l <= 'z':
                result += chr(ord('𝘢') + ord(l) - ord('a'))
            elif 'A' <= l <= 'Z':
                result += chr(ord('𝘈') + ord(l) - ord('A'))
            else:
                result += l
        return result
    def _mask_with_asterisk(match):
        '''将文本每隔一个字符置一个*号，并将剩下的转为花体的拼音首字母'''
        s = match.group(0)
        s = ''.join(pypinyin.lazy_pinyin(s, style=pypinyin.FIRST_LETTER))
        s = ''.join(s[i] + '*' for i in range(0, len(s), 2))[:len(s)] # 可能多出一个*号，截掉
        return _to_huati(s)
    # 替换匹配到的文字为星号
    result_list = []
    for text in text_list:
        for pattern in patterns:
            text = pattern.sub(_mask_with_asterisk, text)
        result_list.append(text)
    return result_list

def _cut_message(segments: Message, MAX_LEN: int) -> list[MessageSegment]:
    '''将超过 MAX_LEN 的消息分为多条'''
    cuts = [Message()]
    for segment in segments:
        if segment.type == 'text':
            segment_str = unescape(str(segment))
            if len(cuts[-1].extract_plain_text()) + len(segment_str) <= MAX_LEN:
                cuts[-1].append(segment)
            else:
                if len(segment_str) <= MAX_LEN:
                    cuts.append(Message(segment_str))
                else:
                    for i in range(0, len(segment_str), MAX_LEN):
                        cuts.append(Message(segment_str[i:i+MAX_LEN]))
        else:
            cuts[-1].append(segment)
    if not cuts[0]:
        del cuts[0]
    return cuts

async def reply_msg(event: Event, reply: str, voice: bool) -> None:
    '''按过滤敏感词、语音、过长分条等要求，回复消息'''
    segments = Message(reply)
    
    # 过滤敏感词
    text_indexes = [i for i in range(len(segments)) if segments[i].type == 'text']
    text_list = [unescape(str(segments[i])) for i in text_indexes]
    result_list = mask_sensitive_text(text_list, 'sensitive.txt')
    for j in range(len(text_indexes)):
        segments[text_indexes[j]] = MessageSegment.text(result_list[j])
    reply_pure_text = segments.extract_plain_text()

    # 语音回复
    if voice:
        await bot.send(event, {'type': 'tts', 'data': {'text': reply_pure_text}})
    
    # 若超出 QQ 单条消息长度限制则转发消息，若超出 QQ 单条消息长度限制则分条
    elif utilities.get_display_rows_num(reply_pure_text) > config.MAX_ROWS:
        bot_name = (await bot.call_action('get_login_info'))['nickname']
        
        MAX_LEN = 2500
        cuts = _cut_message(segments, MAX_LEN)
        forward_msgs = [{
            'type': 'node',
            'data': {
                'user_id': event.self_id,
                'nickname': bot_name,
                'content': unescape(str(cut))
            }
        } for cut in cuts] # [MessageSegment.reply(event.message_id) + ' '] + 
        # 第一条消息前加引用
        forward_msgs[0]['data']['content'] = MessageSegment.reply(event.message_id) + forward_msgs[0]['data']['content']

        logger.debug(f'发送合并转发消息：{forward_msgs}')
        if event.message_type == 'group':
            await bot.call_action('send_group_forward_msg', **{'group_id': event.group_id, 'messages': forward_msgs})
        else:
            await bot.call_action('send_private_forward_msg', **{'user_id': event.user_id, 'messages': forward_msgs})
    
    else:
        await bot.send(event, MessageSegment.reply(event.message_id) + unescape(str(segments)))

    logger.info(f'处理完毕，回复：{reply_pure_text[:60]}')
    return 

async def _is_in_group(group_id: int, user_id: int) -> bool:
    '''判断某人是否在某群中'''
    try:
        group_member_info = await bot.call_action('get_group_member_info', group_id=group_id, user_id=user_id)
    except Exception as e:
        if '群员不存在' in str(e):
            return False
    return True

async def check_permission(event: Event) -> tuple[bool, str]:
    '''Checks if user has permission to access the bot. '''
    
    # 匿名用户不在成员列表中，但也允许访问
    if event.group_id == config.GROUP_ID:
        return True, None

    # 若此人不在指定群里，则拒绝请求
    if not await _is_in_group(config.GROUP_ID, event.user_id):
        return False, '您需要是指定群的群成员，才可使用本Bot'
    
    return True, None

def _is_command(msg_content, cmds: list) -> str:
    '''若是以某指令开头，则返回该指令'''
    for cmd in cmds:
        if utilities.starts_with(msg_content, cmd):
            return cmd

def check_command(event: Event, segments: Message, msg_content: str) -> tuple[str, str]:
    '''Checks if msg is a command and what command it is. Private msgs are regarded as a default command. '''
    for cmds in (config.OPENAI_CHAT_API_CMDS, config.BING_CMDS, config.OPENAI_CHAT_WEB_CMDS, config.BARD_CMDS, ):
        prefix = _is_command(msg_content, cmds)
        if prefix:
            question = msg_content[len(prefix):].strip()
            break
    else:
        if event.message_type == 'private':
            prefix = config.DEFAULT_CMD
            question = msg_content.strip()
        else:
            for seg in segments:
                if seg.type == 'at' and seg.data['qq'] == str(event.self_id):
                    prefix = config.DEFAULT_CMD
                    question = msg_content.strip()
                    break
            else:
                return None, None
    return prefix, question

@bot.on_message
async def _(event: Event):
    anonymous = ', ' + event.anonymous["flag"] if event.anonymous else ''
    logger.info(f'收到消息: {event.message_type}, {event.user_id}{anonymous}, {event.message}')
    segments = Message(event.raw_message)
    msg_content = segments.extract_plain_text().strip()
    
    # 判断是什么 Bot 指令
    prefix, question = check_command(event, segments, msg_content)
    if not prefix:
        return
    
    # 校验权限
    permitted, info = await check_permission(event)
    if not permitted and info:
        return {'reply': f'{MessageSegment.reply(event.message_id)}{config.BOT_INFO_PREFIX}{info}'}
    
    logger.info(f'开始处理指令: {event.message_type}, {event.user_id}, {event.message}')
    try:

        # 处理重置会话指令
        session_id = generate_session_id(prefix, event)
        if utilities.fuzzy_equal(question, config.RESET_CMD):
            await sessions.rm_history(session_id)
            await bot.send(event, f'{MessageSegment.reply(event.message_id)}{config.BOT_INFO_PREFIX}已重置您的 {prefix} 会话')
            return

        # 处理账户额度指令
        if utilities.fuzzy_equal(question, config.USAGE_CMD):
            result = await adapter.check_credits()
            reply = '已使用${}，剩余${}/${}，{}到期'.format(*result)
            await bot.send(event, f'{MessageSegment.reply(event.message_id)}{config.BOT_INFO_PREFIX}{reply}')
            return

        # 处理语音指令
        if utilities.fuzzy_equal(question, config.VOICE_CMD):
            result = await sessions.set_voice(prefix, session_id)
            reply = '已开启语音回复' if result else '已关闭语音回复'
            await bot.send(event, f'{MessageSegment.reply(event.message_id)}{config.BOT_INFO_PREFIX}{reply}')
            return
        
        # 戳一戳以示收到（好像没用）
        await bot.send(event, MessageSegment.poke('poke', event.user_id))

        # 取出回复内容
        reply, finish_reason = await sessions.ask(prefix, session_id, question)
        if finish_reason == 'length':
            reply += f'\n{config.BOT_INFO_PREFIX}回复过长已被截断，您可说`继续`来获取接下来的内容'
        
        # 渲染 LaTeX 公式、替换 Markdown 图片
        try:
            reply = render.replace_latex(render.sub_image(reply))
        except Exception as e:
            logger.error(f'渲染 LaTeX 公式出错: {e}, {reply}')
        
        # 若发送了图片，则进行提示
        for segment in segments:
            if segment.type == 'image':
                reply = f'{config.BOT_INFO_PREFIX}不支持图片输入，已将您消息中的图片忽略后提交给AI\n\n' + reply

        # 回复消息
        await reply_msg(event, reply, sessions.is_voice(session_id))

    except Exception as e:
        logger.error(f'处理消息出错: {e}')
        reply = MessageSegment.reply(event.message_id) + config.BOT_INFO_PREFIX
        
        error_messages = {
            'Conversation not found': ('已为您重置对话，请重新发送消息', True), 
            'Something went wrong, please try reloading the conversation': (f'Oops! 出现未知错误，已为您重置对话，请重新发送消息\n{e}', True), 
            'You have sent too many requests to the model. Please try again later': (f'当前本 Bot 请求速率达到上游模型上限，请稍后重试\n{e}', False), 
            'Too Many Requests': (f'当前本 Bot 请求速率达到上游接口上限，请稍后重试\n{e}', False), 
        }
        
        for msg, response in error_messages.items():
            if msg in str(e):
                if response[1]:
                    await sessions.rm_history(session_id)
                return {'reply': reply + response}
        
        return {'reply': reply + f'处理消息出错，请稍后重试\n{e}'}
    
    return 


bot.run(host='127.0.0.1', port=config.PORT)
