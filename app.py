#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI文献筛选平台 - 本地模型版
使用Ollama运行本地大模型
"""

import os
import sys
import re
import json
import subprocess
import requests
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from datetime import datetime

# 设置标准输出编码为UTF-8，避免Windows控制台GBK编码错误
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Ollama API地址
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')

# 全局存储
processed_data = {}

# 本地模型库（仅保留支持的文本模型，按大小从小到大排列）
MODEL_LIBRARY = [
    # 4B 模型（最小）
    {'name': 'qwen3:4b', 'family': 'qwen', 'description': '通义千问3 (4B)', 'size': '2.5GB', 'date': '2025-01', 'version': '3'},
    
    # 8B 模型
    {'name': 'qwen3:8b', 'family': 'qwen', 'description': '通义千问3 (8B)', 'size': '5GB', 'date': '2025-01', 'version': '3'},
    
]

# 推荐的本地模型列表（全部7个模型）
RECOMMENDED_MODELS = MODEL_LIBRARY


def check_ollama():
    """检查Ollama是否运行"""
    try:
        response = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=5)
        return response.status_code == 200
    except:
        return False


def get_local_models():
    """获取已安装的本地模型列表"""
    try:
        response = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            return [{'name': m['name'], 'size': m.get('size', 0)} for m in models]
    except Exception as e:
        print(f"获取模型列表失败: {e}")
    return []


def pull_model(model_name):
    """下载模型"""
    try:
        response = requests.post(
            f'{OLLAMA_HOST}/api/pull',
            json={'name': model_name},
            stream=True,
            timeout=300
        )
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'completed' in data and 'total' in data:
                        progress = (data['completed'] / data['total']) * 100
                        yield {'status': 'downloading', 'progress': round(progress, 2)}
                    elif 'status' in data:
                        yield {'status': data['status']}
                except:
                    pass
        
        yield {'status': 'success'}
    except Exception as e:
        yield {'status': 'error', 'message': str(e)}


def chat_with_local_model(model_name, messages, temperature=0.3):
    """与本地模型对话 - 使用 /api/generate 端点以获得更好的性能"""
    try:
        # 分离 system 和 user 消息
        system_prompt = ""
        user_prompt = ""
        
        for msg in messages:
            if msg.get('role') == 'system':
                system_prompt = msg.get('content', '')
            elif msg.get('role') == 'user':
                user_prompt = msg.get('content', '')
        
        # 如果没有 system 消息，将第一个 user 作为 prompt
        if not system_prompt and messages:
            user_prompt = messages[0].get('content', '')
        
        # 调试信息
        print(f"    [DEBUG] 调用模型: {model_name}")
        print(f"    [DEBUG] prompt长度: {len(user_prompt)} 字符")
        print(f"    [DEBUG] system长度: {len(system_prompt)} 字符")
        print(f"    [DEBUG] OLLAMA_HOST: {OLLAMA_HOST}")
        print(f"    [DEBUG] temperature: {temperature}")
        print(f"    [DEBUG] Python版本: {os.sys.version}")
        print(f"    [DEBUG] requests版本: {requests.__version__}")
        
        # 构建请求数据
        request_data = {
            'model': model_name,
            'prompt': user_prompt,
            'system': system_prompt,
            'stream': False,
            'options': {
                'temperature': temperature,
                'num_thread': 8,
                'num_ctx': 2048,
                'batch_size': 512
            },
            'keep_alive': 0
        }
        print(f"    [DEBUG] 请求数据: {json.dumps(request_data, ensure_ascii=False)[:500]}...")
        
        url = f'{OLLAMA_HOST}/api/generate'
        print(f"    [DEBUG] 请求URL: {url}")
        
        try:
            response = requests.post(
                url,
                json=request_data,
                timeout=(30, 300)
            )
            print(f"    [DEBUG] 响应状态码: {response.status_code}")
        except Exception as req_e:
            print(f"    [DEBUG] 请求异常类型: {type(req_e).__name__}")
            print(f"    [DEBUG] 请求异常详情: {str(req_e)}")
            import traceback
            print(f"    [DEBUG] 异常堆栈: {traceback.format_exc()}")
            raise
        
        if response.status_code == 200:
            data = response.json()
            print(f"    [DEBUG] 完整响应数据: {data}")
            response_text = data.get('response', '')
            print(f"    [DEBUG] 响应内容: '{response_text}'")
            return response_text
        else:
            print(f"    [DEBUG] 错误响应: {response.text}")
            raise Exception(f"API错误: {response.status_code}")
    except Exception as e:
        print(f"    [DEBUG] 异常类型: {type(e).__name__}")
        print(f"    [DEBUG] 异常信息: {str(e)}")
        import traceback
        print(f"    [DEBUG] 异常堆栈: {traceback.format_exc()}")
        raise Exception(f"模型调用失败: {str(e)}")


def parse_pubmed_txt(file_path):
    """
    解析PubMed导出的txt文件，提取文献信息
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    records = []
    
    if 'PMID-' in content:
        raw_records = re.split(r'\n\n+(?=PMID-)', content)
        
        for raw_record in raw_records:
            if not raw_record.strip():
                continue
                
            record = {}
            
            pmid_match = re.search(r'PMID-\s*(\d+)', raw_record)
            record['PMID'] = pmid_match.group(1) if pmid_match else ''
            
            title_match = re.search(r'TI\s+-\s+(.*?)(?=\n[A-Z]{2}\s+-|\Z)', raw_record, re.DOTALL)
            if title_match:
                title = title_match.group(1).replace('\n', ' ').replace('      ', ' ').strip()
                record['标题'] = title
            else:
                record['标题'] = ''
            
            abstract_match = re.search(r'AB\s+-\s+(.*?)(?=\n[A-Z]{2}\s+-|\Z)', raw_record, re.DOTALL)
            if abstract_match:
                abstract = abstract_match.group(1).replace('\n', ' ').replace('      ', ' ').strip()
                record['摘要'] = abstract
            else:
                record['摘要'] = ''
            
            mesh_terms = re.findall(r'MH\s+-\s+(.+)', raw_record)
            if mesh_terms:
                record['关键词'] = '; '.join(mesh_terms)
            else:
                keyword_match = re.search(r'OT\s+-\s+(.*?)(?=\n[A-Z]{2}\s+-|\Z)', raw_record, re.DOTALL)
                if keyword_match:
                    keywords = keyword_match.group(1).replace('\n', ' ').replace('      ', ' ').strip()
                    record['关键词'] = keywords
                else:
                    record['关键词'] = ''
            
            authors = re.findall(r'AU\s+-\s+(.+)', raw_record)
            if authors:
                record['作者'] = '; '.join(authors[:5])
            else:
                record['作者'] = ''
            
            date_match = re.search(r'DP\s+-\s+(\d{4})', raw_record)
            if date_match:
                record['日期'] = date_match.group(1)
            else:
                date_match = re.search(r'DA\s+-\s+(\d{4})', raw_record)
                record['日期'] = date_match.group(1) if date_match else ''
            
            country_match = re.search(r'PL\s+-\s+(.+)', raw_record)
            if country_match:
                record['国家'] = country_match.group(1).strip()
            else:
                record['国家'] = ''
            
            records.append(record)
    else:
        paragraphs = content.split('\n\n')
        
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue
                
            record = {
                'PMID': str(i + 1),
                '标题': '',
                '摘要': '',
                '关键词': '',
                '作者': '',
                '日期': '',
                '国家': ''
            }
            
            lines = para.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('Title:') or line.startswith('标题:'):
                    record['标题'] = line.split(':', 1)[1].strip()
                elif line.startswith('Abstract:') or line.startswith('摘要:'):
                    record['摘要'] = line.split(':', 1)[1].strip()
                elif line.startswith('Keywords:') or line.startswith('关键词:'):
                    record['关键词'] = line.split(':', 1)[1].strip()
                elif line.startswith('Author:') or line.startswith('作者:'):
                    record['作者'] = line.split(':', 1)[1].strip()
                elif line.startswith('Date:') or line.startswith('日期:'):
                    record['日期'] = line.split(':', 1)[1].strip()
                elif line.startswith('Country:') or line.startswith('国家:'):
                    record['国家'] = line.split(':', 1)[1].strip()
            
            if not record['标题'] and len(lines) > 0:
                record['标题'] = lines[0]
            if not record['摘要'] and len(lines) > 1:
                record['摘要'] = '\n'.join(lines[1:])
            
            records.append(record)
    
    return records


def export_to_excel(records, output_path):
    """将记录导出到Excel文件"""
    df = pd.DataFrame(records)
    columns_order = ['标题', '关键词', '摘要', '作者', '国家', '日期', 'PMID']
    available_columns = [col for col in columns_order if col in df.columns]
    df = df[available_columns]
    df.to_excel(output_path, index=False, engine='openpyxl')
    return output_path


def parse_excel(file_path):
    """
    解析Excel文件，提取文献信息
    支持智能列名映射（使用包含匹配）
    """
    # 读取Excel文件
    df = pd.read_excel(file_path, engine='openpyxl')

    # 列名映射规则（使用包含匹配，更灵活）
    # 格式：标准字段名: [匹配关键词列表]
    column_mapping = {
        '标题': ['标题', 'title', '文献标题', '文章标题', '题录', '题名'],
        '摘要': ['摘要', 'abstract', '文献摘要', '文章摘要', '概要', '概述'],
        '关键词': ['关键词', 'keyword', '关键字', 'key word', '主题词', 'mesh', '主题'],
        '作者': ['作者', 'author', '作者信息', '撰稿人', 'writer', '研究人员'],
        '日期': ['日期', 'date', '年份', 'year', '发表日期', '发表年份', '出版年', '时间'],
        'PMID': ['pmid', 'pubmed', 'pub med', '文献id', '文献标识', '编号', 'id'],
        '国家': ['国家', 'country', '地区', 'region', '地域', 'place', '地点']
    }

    # 找到实际存在的列（使用包含匹配）
    actual_columns = {}
    for standard_name, keywords in column_mapping.items():
        for col in df.columns:
            col_lower = str(col).lower()
            # 检查列名是否包含任何关键词
            for keyword in keywords:
                if keyword.lower() in col_lower:
                    actual_columns[standard_name] = col
                    break
            if standard_name in actual_columns:
                break

    # 检查必需的列（至少有标题或摘要）
    if '标题' not in actual_columns and '摘要' not in actual_columns:
        raise ValueError("Excel文件必须包含'标题'或'摘要'列，当前列名：" + ', '.join(df.columns))

    records = []
    for _, row in df.iterrows():
        record = {}
        for standard_name, actual_name in actual_columns.items():
            value = row[actual_name]
            # 处理NaN值
            if pd.isna(value):
                record[standard_name] = ''
            else:
                record[standard_name] = str(value).strip()

        # 确保所有字段都存在
        for field in ['标题', '摘要', '关键词', '作者', '日期', 'PMID', '国家']:
            if field not in record:
                record[field] = ''

        records.append(record)

    return records


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/ollama_status')
def ollama_status():
    """检查Ollama状态"""
    is_running = check_ollama()
    models = get_local_models() if is_running else []
    
    return jsonify({
        'running': is_running,
        'host': OLLAMA_HOST,
        'models': models,
        'recommended': RECOMMENDED_MODELS
    })


@app.route('/api/pull_model', methods=['POST'])
def download_model():
    """下载模型"""
    data = request.get_json()
    model_name = data.get('model', '')
    
    if not model_name:
        return jsonify({'error': '请选择模型'}), 400
    
    if not check_ollama():
        return jsonify({'error': 'Ollama未运行，请先启动Ollama服务'}), 500
    
    def generate():
        for progress in pull_model(model_name):
            yield f"data: {json.dumps(progress)}\n\n"
    
    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/local_models')
def local_models():
    """获取本地模型列表"""
    if not check_ollama():
        return jsonify({'error': 'Ollama未运行'}), 500
    
    models = get_local_models()
    return jsonify({'models': models})


@app.route('/upload', methods=['POST'])
def upload_file():
    """上传并解析PubMed文件或Excel文件"""
    global processed_data

    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    # 保留原始文件名（支持中文），仅移除路径中的危险字符
    original_filename = file.filename
    # 移除路径分隔符等危险字符，但保留中文字符
    safe_filename = original_filename.replace('/', '_').replace('\\', '_').replace('..', '_')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_name = f"{timestamp}_{safe_filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
    file.save(file_path)

    try:
        # 根据文件类型选择解析方法（不区分大小写）
        filename_lower = safe_filename.lower()
        if filename_lower.endswith('.txt'):
            records = parse_pubmed_txt(file_path)
            file_type = 'PubMed TXT'
        elif filename_lower.endswith(('.xlsx', '.xls')):
            records = parse_excel(file_path)
            file_type = 'Excel'
        else:
            return jsonify({'error': '不支持的文件格式，请上传.txt或.xlsx/.xls文件'}), 400

        if not records:
            return jsonify({'error': '未能从文件中提取到文献信息，请检查文件格式'}), 400

        output_filename = f"parsed_{timestamp}.xlsx"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        export_to_excel(records, output_path)

        processed_data = {
            'records': records,
            'output_path': output_path,
            'filename': output_filename,
            'total': len(records)
        }

        return jsonify({
            'success': True,
            'message': f'成功解析 {len(records)} 篇文献（{file_type}格式）',
            'total': len(records),
            'preview': records,
            'download_url': f'/download/{output_filename}'
        })

    except Exception as e:
        return jsonify({'error': f'解析失败: {str(e)}'}), 500


@app.route('/screen_papers', methods=['POST'])
def screen_papers():
    """批量筛选文献 - 流式响应"""
    global processed_data

    data = request.get_json()
    model = data.get('model', 'qwen2.5:7b')
    prompt = data.get('prompt', '')

    if not processed_data or 'records' not in processed_data:
        return jsonify({'error': '请先上传文献文件'}), 400

    if not prompt:
        return jsonify({'error': '请先生成或输入筛选提示词'}), 400

    if not check_ollama():
        return jsonify({'error': 'Ollama未运行，请先启动Ollama服务'}), 500

    records = processed_data['records']

    def generate():
        total = len(records)
        results = []

        # 发送开始消息
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        for i, record in enumerate(records):
            current_index = i + 1
            title = record.get('标题', '')
            title_display = title[:50] + '...' if len(title) > 50 else title

            # 发送当前分析进度（分析中）
            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total, 'title': title_display, 'status': 'analyzing'})}\n\n"

            text_parts = []
            if record.get('标题'):
                text_parts.append(f"标题: {record['标题']}")
            if record.get('摘要'):
                text_parts.append(f"摘要: {record['摘要']}")
            if record.get('关键词'):
                text_parts.append(f"关键词: {record['关键词']}")

            paper_text = '\n'.join(text_parts)

            full_prompt = f"""你是一位专业的文献筛选专家。请根据以下筛选标准严格判断这篇文献是否符合要求。

═══════════════════════════════════════
【筛选标准】
═══════════════════════════════════════

{prompt}

═══════════════════════════════════════
【文献信息】
═══════════════════════════════════════

{paper_text}

═══════════════════════════════════════
【输出要求 - 严格遵守】
═══════════════════════════════════════

请按以下格式输出你的分析：

【分类依据】
简要说明文献中支持分类判断的关键内容（2-3句话）。

【分类原因】
详细解释为什么这样分类，包括：
- 如果分类为"是"：说明文献符合哪些筛选标准
- 如果分类为"否"：说明文献为什么不满足筛选标准
- 如果分类为"未知"：说明缺少哪些关键信息导致无法判断

【分类结果】
在最后一行输出统一的分类标识，只能是以下三种之一：
[CLASSIFICATION:是]
[CLASSIFICATION:否]
[CLASSIFICATION:未知]

═══════════════════════════════════════
【关键规则 - 必须遵守】
═══════════════════════════════════════

1. **分类一致性原则**：
   - 如果你在【分类原因】中说明文献"不符合"、"不满足"筛选标准，那么【分类结果】必须是 [CLASSIFICATION:否]
   - 如果你在【分类原因】中说明文献"符合"、"满足"筛选标准，那么【分类结果】必须是 [CLASSIFICATION:是]
   - 绝对不能出现分析说"不符合"但分类结果是"是"的矛盾情况

2. **分类标识格式**：
   - 必须严格按照 [CLASSIFICATION:是] 或 [CLASSIFICATION:否] 或 [CLASSIFICATION:未知] 的格式
   - 必须包含方括号和冒号，不能有任何额外字符
   - 必须单独一行，位于回答的最后

3. **这是程序识别分类结果的关键标记，格式错误会导致筛选结果错误！**"""

            # 重试机制：最多尝试3次
            max_retries = 3
            retry_count = 0
            result = '未知'
            answer_clean = ''
            answer = ''
            
            while retry_count < max_retries:
                try:
                    messages = [{"role": "user", "content": full_prompt}]
                    
                    # 发送AI交互 - 发送给AI的内容
                    if retry_count == 0:
                        yield f"data: {json.dumps({'type': 'ai_interaction', 'paper_id': current_index, 'interaction_type': 'send', 'content': full_prompt[:500] + '...', 'label': '发送给AI的提示词'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'ai_interaction', 'paper_id': current_index, 'interaction_type': 'send', 'content': f'第{retry_count+1}次尝试：请严格按照格式要求输出分类结果', 'label': '重新发送提示词'})}\n\n"
                    
                    answer = chat_with_local_model(model, messages, temperature=0.1)
                    answer_clean = answer.strip()
                    
                    # 发送AI交互 - AI返回的内容
                    yield f"data: {json.dumps({'type': 'ai_interaction', 'paper_id': current_index, 'interaction_type': 'receive', 'content': answer_clean, 'label': f'AI生成的分析（第{retry_count+1}次）'})}\n\n"

                    # 打印AI输出到终端以便调试
                    print(f"  [AI输出] 第{current_index}篇 (尝试{retry_count+1}/{max_retries}):")
                    print(f"  {'='*50}")
                    for line in answer_clean.split('\n')[:10]:  # 只显示前10行
                        print(f"  {line}")
                    if len(answer_clean.split('\n')) > 10:
                        print(f"  ... (共{len(answer_clean.split(chr(10)))}行)")
                    print(f"  {'='*50}")

                    # 从分类标识中提取结果 [CLASSIFICATION:是/否/未知]
                    import re
                    classification_match = re.search(r'\[CLASSIFICATION:([^\]]+)\]', answer_clean)

                    if classification_match:
                        classification = classification_match.group(1).strip()

                        if classification == '是':
                            result = '是'
                        elif classification == '否':
                            result = '否'
                        elif classification == '未知':
                            result = '未知'
                        else:
                            result = '未知'
                            print(f"  [警告] 未知的分类标识: {classification}")

                        # 找到分类标识，退出循环
                        break
                    else:
                        # 如果没有找到分类标识，尝试从文本中推断
                        print(f"  [警告] 未找到分类标识，尝试文本匹配")
                        if '否' in answer_clean or '不是' in answer_clean:
                            result = '否'
                        elif '是' in answer_clean:
                            result = '是'
                        else:
                            result = '未知'

                        # 没有找到分类标识，需要重试（使用原始提示词重新分析）
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            print(f"  [重试] 未找到分类标识，进行第{retry_count+1}次尝试...")
                            continue
                        break

                except Exception as e:
                    print(f"  [错误] 第{retry_count+1}次尝试失败: {e}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise
            
            print(f"  [解析结果] {result} (共尝试{retry_count+1}次)")

            result_data = {
                'index': current_index,
                'title': title_display,
                'result': result,
                'raw_response': answer
            }
            results.append(result_data)

            # 发送分析完成消息
            yield f"data: {json.dumps({'type': 'result', 'data': result_data})}\n\n"

        # 保存Excel文件
        df = pd.DataFrame(processed_data['records'])
        df['筛选结果'] = [r['result'] for r in results]

        # 调整列顺序
        columns_order = ['标题', '关键词', '摘要', '作者', '国家', '日期', 'PMID', '筛选结果']
        available_columns = [col for col in columns_order if col in df.columns]
        df = df[available_columns]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_filename = f"screened_{timestamp}.xlsx"
        result_path = os.path.join(app.config['OUTPUT_FOLDER'], result_filename)
        df.to_excel(result_path, index=False, engine='openpyxl')

        # 保存结果到全局变量供下载使用
        processed_data['screened_output'] = result_path
        processed_data['screened_filename'] = result_filename

        # 发送完成消息
        yield f"data: {json.dumps({'type': 'complete', 'summary': {'total': total, 'yes': len([r for r in results if r['result'] == '是']), 'no': len([r for r in results if r['result'] == '否']), 'unknown': len([r for r in results if r['result'] not in ['是', '否']])}, 'download_url': f'/download/{result_filename}'})}\n\n"

    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@app.route('/export_parsed', methods=['POST'])
def export_parsed():
    """导出解析后的文献 - 不分析"""
    global processed_data
    
    if not processed_data or 'records' not in processed_data:
        return jsonify({'error': '请先上传文献文件'}), 400
    
    try:
        df = pd.DataFrame(processed_data['records'])

        # 调整列顺序
        columns_order = ['标题', '关键词', '摘要', '作者', '国家', '日期', 'PMID']
        available_columns = [col for col in columns_order if col in df.columns]
        df = df[available_columns]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_filename = f"parsed_only_{timestamp}.xlsx"
        result_path = os.path.join(app.config['OUTPUT_FOLDER'], result_filename)
        df.to_excel(result_path, index=False, engine='openpyxl')
        
        return jsonify({
            'success': True,
            'download_url': f'/download/{result_filename}'
        })
        
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'}), 500


@app.route('/download/<filename>')
def download_file(filename):
    """下载文件"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': '文件不存在'}), 404


if __name__ == '__main__':
    print("="*60)
    print("AI文献筛选平台 - 本地模型版")
    print("="*60)
    print("\n使用前请确保：")
    print("1. 已安装Ollama: https://ollama.com")
    print("2. Ollama服务已启动")
    print("\n启动命令: ollama serve")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)