import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import Config
from models import init_db, load_questions_from_json, User, Question, Session, Message, get_db_connection
import ai_service
import os

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.get_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            return jsonify({'success': True, 'role': user.role})
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/user/info')
@login_required
def get_user_info():
    return jsonify({
        'username': current_user.username,
        'points': current_user.points,
        'role': current_user.role
    })

@app.route('/api/questions')
@login_required
def get_questions():
    questions = Question.get_all()
    return jsonify([{
        'id': q['id'],
        'title': q['title'],
        'difficulty': q.get('difficulty', '中等')
    } for q in questions])

@app.route('/api/question/<int:question_id>')
@login_required
def get_question(question_id):
    question = Question.get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404
    
    return jsonify({
        'id': question['id'],
        'title': question['title'],
        'surface': question['surface'],
        'difficulty': question.get('difficulty', '中等')
    })

@app.route('/api/session', methods=['POST'])
@login_required
def create_or_get_session():
    data = request.get_json()
    question_id = data.get('question_id')
    
    session = Session.get_by_user_and_question(current_user.id, question_id)
    if session:
        messages = Message.get_by_session(session['id'])
        return jsonify({
            'session_id': session['id'],
            'messages': messages,
            'exists': True
        })
    
    return jsonify({
        'session_id': None,
        'messages': [],
        'exists': False
    })

@app.route('/api/session/<int:session_id>')
@login_required
def get_session(session_id):
    session = Session.get(session_id)
    if not session or session['user_id'] != current_user.id:
        return jsonify({'error': '会话不存在'}), 404
    
    messages = Message.get_by_session(session_id)
    return jsonify({
        'session_id': session_id,
        'question_id': session['question_id'],
        'updated_at': session['updated_at'],
        'messages': messages
    })

@app.route('/api/sessions')
@login_required
def get_all_sessions():
    sessions = Session.get_all_by_user(current_user.id)
    
    grouped = {
        '今天': [],
        '昨天': [],
        '7天内': [],
        '30天内': [],
        '更早': []
    }
    
    # 使用北京时间进行分组判断
    now = datetime.now()
    from datetime import timezone
    # 设置北京时间时区
    beijing_timezone = timezone(timedelta(hours=8))
    # 获取当前北京时间
    beijing_now = now.astimezone(beijing_timezone)
    
    for s in sessions:
        # 解析会话的更新时间 - 数据库存储的是UTC时间
        updated_str = s['updated_at']
        # 检查时间格式
        if 'T' in updated_str:
            # ISO格式
            updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
        else:
            # 普通格式 - 假设是UTC时间
            updated = datetime.strptime(updated_str, '%Y-%m-%d %H:%M:%S')
            # 明确设置为UTC时间
            updated = updated.replace(tzinfo=timezone.utc)
        
        # 转换为北京时间（UTC+8）
        beijing_updated = updated.astimezone(beijing_timezone)
        # 计算与北京时间的天数差
        diff = (beijing_now - beijing_updated).days
        
        if diff == 0:
            grouped['今天'].append(s)
        elif diff == 1:
            grouped['昨天'].append(s)
        elif diff < 7:
            grouped['7天内'].append(s)
        elif diff < 30:
            grouped['30天内'].append(s)
        else:
            grouped['更早'].append(s)
    
    return jsonify(grouped)

@app.route('/api/session/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    session = Session.get(session_id)
    if not session or session['user_id'] != current_user.id:
        return jsonify({'error': '会话不存在'}), 404
    
    Session.delete(session_id)
    return jsonify({'success': True})

@app.route('/api/send', methods=['POST'])
@login_required
def send_message():
    if current_user.points < 1:
        return jsonify({'error': '积分不足'}), 403
    
    data = request.get_json()
    session_id = data.get('session_id')
    question_id = data.get('question_id')
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'error': '消息内容不能为空'}), 400
    
    if not session_id and question_id:
        # 不查找已存在的会话，每次都创建新会话
        question = Question.get(question_id)
        # 使用北京时间生成会话名称
        now = datetime.now()
        from datetime import timezone
        # 设置北京时间时区
        beijing_timezone = timezone(timedelta(hours=8))
        # 获取当前北京时间
        beijing_now = now.astimezone(beijing_timezone)
        name = f"{question['title']} - {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}"
        session_id = Session.create(current_user.id, question_id, name)
    
    if not session_id:
        return jsonify({'error': '会话不存在'}), 404
    
    session = Session.get(session_id)
    if not session or session['user_id'] != current_user.id:
        return jsonify({'error': '会话不存在'}), 404
    
    question = Question.get(session['question_id'])
    points_data = json.loads(question['points_json'])
    examples_data = json.loads(question.get('examples_json', '[]'))
    
    messages = Message.get_by_session(session_id)
    known_facts = '\n'.join([m['summary'] for m in messages if m['summary']])
    
    # 获取最近的3条消息
    recent_messages = messages[-3:]
    recent_messages_list = []
    for msg in recent_messages:
        recent_messages_list.append({
            'role': msg['role'],
            'content': msg['content']
        })
    
    Message.create(session_id, 'user', content)
    
    # 关键词列表
    reasoning_keywords = ['推理：', '推理', '推断', '猜测', '推测']
    hint_keywords = ['提示', '提示：', '线索', '帮助', '提示一下']
    
    # 1. 首先检查直接关键词
    is_reasoning = any(keyword in content for keyword in reasoning_keywords)
    is_hint = any(keyword in content for keyword in hint_keywords)
    
    if is_reasoning:
        # 调用推理接口
        reasoning = content
        result = ai_service.judge_reasoning(reasoning, question['surface'], question['bottom'], points_data)
        score = ai_service.calculate_score(result['results'], len(points_data))
        
        ai_response = f"推理判定：{score}"
        summary = None
        response_type = 'reasoning'
        
        if score == "正确":
            ai_response += f"\n\n完整汤底：\n{question['bottom']}"
    
    elif is_hint:
        # 调用提示接口，传递用户的具体问题
        result = ai_service.give_hint(question['surface'], question['bottom'], known_facts, recent_messages_list, content)
        ai_response = result['hint']
        summary = result['summary']
        response_type = 'hint'
    
    else:
        # 2. 如果没有直接关键词，使用deepseek进行分类
        classification = ai_service.classify_message(content)
        
        if classification == 'reasoning':
            # 调用推理接口
            reasoning = content
            result = ai_service.judge_reasoning(reasoning, question['surface'], question['bottom'], points_data)
            score = ai_service.calculate_score(result['results'], len(points_data))
            
            ai_response = f"推理判定：{score}"
            summary = None
            response_type = 'reasoning'
            
            if score == "正确":
                ai_response += f"\n\n完整汤底：\n{question['bottom']}"
        
        elif classification == 'hint':
            # 调用提示接口，传递用户的具体问题
            result = ai_service.give_hint(question['surface'], question['bottom'], known_facts, recent_messages_list, content)
            ai_response = result['hint']
            summary = result['summary']
            response_type = 'hint'
        
        else:
            # 3. 否则视为普通问题，调用回答接口
            result = ai_service.answer_question(content, question['surface'], question['bottom'], known_facts, examples_data)
            ai_response = result['answer_type']
            summary = result['summary']
            response_type = 'answer'
    
    Message.create(session_id, 'assistant', ai_response, summary)
    Session.update_timestamp(session_id)
    current_user.update_points(-1)
    
    return jsonify({
        'response': ai_response,
        'summary': summary,
        'type': response_type,
        'points': current_user.points,
        'session_id': session_id
    })

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')

@app.route('/api/admin/questions')
@admin_required
def admin_get_questions():
    questions = Question.get_all()
    return jsonify([{
        'id': q['id'],
        'title': q['title'],
        'surface': q['surface'][:100] + '...' if len(q['surface']) > 100 else q['surface'],
        'bottom': q['bottom'][:100] + '...' if len(q['bottom']) > 100 else q['bottom'],
        'points_count': len(json.loads(q['points_json'])),
        'points': json.loads(q['points_json']),
        'examples': json.loads(q.get('examples_json', '[]')),
        'difficulty': q.get('difficulty', '中等')
    } for q in questions])

@app.route('/api/admin/question/<int:question_id>')
@admin_required
def admin_get_question(question_id):
    question = Question.get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404
    
    return jsonify({
        'id': question['id'],
        'title': question['title'],
        'surface': question['surface'],
        'bottom': question['bottom'],
        'points': json.loads(question['points_json']),
        'examples': json.loads(question.get('examples_json', '[]')),
        'difficulty': question.get('difficulty', '中等')
    })

@app.route('/api/admin/question', methods=['POST'])
@admin_required
def admin_create_question():
    data = request.get_json()
    
    # 检查是否提供了ID，如果提供则使用，否则自动生成
    if 'id' in data and data['id']:
        # 使用导入的ID
        new_id = data['id']
    else:
        # 自动生成题目ID
        import sqlite3
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM questions")
        max_id = cursor.fetchone()[0]
        conn.close()
        
        new_id = max_id + 1 if max_id else 1
    
    result = Question.create(new_id, data['title'], data['surface'], data['bottom'], data['points'], data.get('difficulty', '中等'), data.get('examples', []))
    if result:
        return jsonify({'success': True})
    else:
        return jsonify({'error': '题目ID已存在'}), 400

@app.route('/api/admin/question/<int:question_id>', methods=['PUT'])
@admin_required
def admin_update_question(question_id):
    data = request.get_json()
    
    # 忽略传入的id，直接使用路径中的question_id
    Question.update(question_id, data['title'], data['surface'], data['bottom'], data['points'], data.get('difficulty', '中等'), data.get('examples', []))
    
    return jsonify({'success': True})

@app.route('/api/admin/question/<int:question_id>', methods=['DELETE'])
@admin_required
def admin_delete_question(question_id):
    Question.delete(question_id)
    return jsonify({'success': True})

@app.route('/api/admin/users')
@admin_required
def admin_get_users():
    users = User.get_all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'points': u.points,
        'role': u.role
    } for u in users])

@app.route('/api/admin/user', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.get_json()
    
    if User.get_by_username(data['username']):
        return jsonify({'error': '用户名已存在'}), 400
    
    User.create(data['username'], data['password'], data.get('points', 100), data.get('role', 'user'))
    return jsonify({'success': True})

@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    data = request.get_json()
    user = User.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if 'points' in data:
        user.update_points_direct(data['points'])
    if 'role' in data:
        user.update_role(data['role'])
    
    return jsonify({'success': True})

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    if user_id == current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
    
    User.delete(user_id)
    return jsonify({'success': True})

@app.route('/api/admin/user/<int:user_id>/password', methods=['PUT'])
@admin_required
def admin_change_password(user_id):
    data = request.get_json()
    user = User.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    user.update_password(data['password'])
    return jsonify({'success': True})

@app.route('/api/admin/user/<int:user_id>/logout')
@admin_required
def admin_logout_user(user_id):
    # 这里可以实现登出逻辑，比如清除session等
    return jsonify({'success': True})

@app.route('/api/admin/records')
@admin_required
def admin_get_records():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, q.title as question_title, 
               m1.content as question_content, m2.content as answer_content, 
               m1.created_at
        FROM messages m1
        JOIN messages m2 ON m1.session_id = m2.session_id AND m1.id + 1 = m2.id
        JOIN sessions s ON m1.session_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN questions q ON s.question_id = q.id
        WHERE m1.role = 'user' AND m2.role = 'assistant'
        ORDER BY m1.created_at DESC
        LIMIT 100
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    records = []
    for row in rows:
        records.append({
            'username': row['username'],
            'question_title': row['question_title'],
            'question_content': row['question_content'],
            'answer_content': row['answer_content'],
            'created_at': row['created_at']
        })
    
    return jsonify(records)

@app.route('/api/admin/database/export')
@admin_required
def export_database():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turtlesoup.db')
    if not os.path.exists(db_path):
        return jsonify({'error': '数据库文件不存在'}), 404
    
    return send_file(db_path, as_attachment=True, download_name='turtlesoup.db')

@app.route('/api/admin/database/import', methods=['POST'])
@admin_required
def import_database():
    if 'db_file' not in request.files:
        return jsonify({'error': '请选择文件'}), 400
    
    file = request.files['db_file']
    if file.filename == '':
        return jsonify({'error': '请选择文件'}), 400
    
    if not file.filename.endswith('.db'):
        return jsonify({'error': '请选择.db文件'}), 400
    
    # 保存上传的文件到数据库路径
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turtlesoup.db')
    
    # 先备份原数据库
    backup_path = db_path + '.bak'
    if os.path.exists(db_path):
        os.replace(db_path, backup_path)
    
    try:
        file.save(db_path)
        return jsonify({'success': True})
    except Exception as e:
        # 如果出错，恢复备份
        if os.path.exists(backup_path):
            os.replace(backup_path, db_path)
        return jsonify({'error': f'导入失败: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    
    questions_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'questions.json')
    if os.path.exists(questions_json_path):
        load_questions_from_json(questions_json_path)
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
