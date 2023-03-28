from contextlib import redirect_stdout
import matplotlib.pyplot as plt
import io
import base64
import re
import sympy
import requests
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM


""" def render_latex(formula):
    '''
    渲染 LaTeX 公式
    formula -> PNG Base64 String
    '''
    fig, ax = plt.subplots()
    ax.text(0.05, 0.5, formula, fontsize=14)
    ax.axis('off')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', transparent=True, dpi=200, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8') """

""" def render_latex(formula):
    '''
    渲染 LaTeX 公式
    '$formula$' -> PNG Base64 String
    '''
    buf = io.BytesIO()
    # Render the formula as a PNG image
    sympy.preview(formula, viewer='BytesIO', output='png', outputbuffer=buf)
    # Get the image data from the BytesIO object
    buf.seek(0)
    # Encode the image data as base64
    return base64.b64encode(buf.read()).decode('utf-8') """

def render_latex(formula):
    resp = requests.get('https://www.zhihu.com/equation', params={'tex': formula})
    read_buf = io.BytesIO(resp.content)
    drawing = svg2rlg(read_buf)
    write_buf = io.BytesIO()
    with redirect_stdout(read_buf):
        renderPM.drawToFile(drawing, write_buf, fmt="PNG", dpi=300)
    write_buf.seek(0)
    return base64.b64encode(write_buf.read()).decode('utf-8')

def replace_latex(markdown):
    '''将消息中的 LaTeX 公式替换为 CQ码: Base64 图片'''
    latex_regex = r'\$\$(.*?)\$\$|\$(.*?)\$'
    
    # 替换函数
    def _replace_latex(match):
        # 提取LaTeX公式
        formula = match.group(0).replace('$', '')
        # 渲染LaTeX公式
        img_data = render_latex(formula)
        # 返回img标签
        return f'[CQ:image,file=base64://{img_data}]'
    
    # 替换Markdown中的LaTeX公式
    new_markdown = re.sub(latex_regex, _replace_latex, markdown)
    
    return new_markdown

def sub_image(markdown_text):
    '''将消息中的 Markdown 图片替换为 CQ 码'''
    img_regex = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^\)]*)\)')

    def check_image(url):
        r = requests.head(url)
        return r.status_code == 200

    def replace_img(match):
        alt = match.group('alt')
        src = match.group('src')
        return f'[CQ:image,url={src}]' if check_image(src) else match.string

    # 替换Markdown中的图片URL
    return img_regex.sub(replace_img, markdown_text)
