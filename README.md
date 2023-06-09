# chatgpt_bot
 接入 ChatGPT、GPT-4、新必应、Google Bard 的 QQ 机器人

## 特性

- 一个 Bot，同时支持 ChatGPT、GPT-4、新必应、Google Bard
- 群内会话隔离，不同人对 Bot 说话不相互干扰，匿名用户也不混淆
- 过长消息自动使用合并转发消息发送，保持清爽防止刷屏
- 有特色的敏感词过滤方式，以 * 号覆盖一半字，另一半字转为拼音首字母
- 支持访问权设置，只有特定群的群成员可用 Bot
- 由用户自由设置是否用语音进行回复
- 渲染 LaTeX 数学公式，回复消息显示 Markdown 图片
- 将收到的图片 OCR 识别再提交给 AI
- 检测到掉线后，自动登录校园网

## 配置

请先将`config.template.py`复制一份命名为`config.py`，而后按照里面的说明配置各项内容

## 安装依赖

```powershell
pip install -r requirement.txt -U -i https://pypi.python.org/simple
```

## 运行

```powershell
python main.py
```

另外需要运行 go-cqhttp