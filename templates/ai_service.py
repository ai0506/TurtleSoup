import json
from openai import OpenAI
from config import Config

client = OpenAI(
    api_key=Config.DEEPSEEK_API_KEY,
    base_url=Config.DEEPSEEK_BASE_URL
)

def call_deepseek(system_prompt, user_message):
    response = client.chat.completions.create(
        model=Config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=Config.DEEPSEEK_TEMPERATURE,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def answer_question(question, surface, bottom, known_facts):
    system_prompt = f"""你是一个海龟汤游戏的主持人。你需要根据汤底回答玩家的问题。

汤面（公开的故事片段）：
{surface}

汤底（完整的故事真相）：
{bottom}

已知事实（玩家已经得知的信息）：
{known_facts if known_facts else "暂无"}

回答规则：
1. 只能回答"是"、"否"、"与此无关"或"模糊问题"四种类型之一
2. 如果问题中的事实在汤底中有明确依据，回答"是"
3. 如果问题中的事实与汤底明确矛盾，回答"否"
4. 如果问题内容在汤底中完全未提及，回答"与此无关"
5. 如果问题无法用是/否回答，或需要进一步细化（如指代不明），回答"模糊问题"

重要原则：
- 保持回答的一致性。如果汤底中某个人物有某种特征（如侏儒），那么关于这个特征的相关问题应该保持一致
- 对于近义词或相关概念（如"病"、"病症"、"疾病"），如果汤底中明确提到某种身体状况，应视为相关
- 不要过度推断。只根据汤底明确描述的内容回答，不要添加额外假设
- summary中不要输出额外的内容，只需要输出玩家问题的事实总结陈述句(或相反的陈述句如果是否回答，或者null)
- 如果问题涉及汤底中明确提到的特征，即使表述方式不同，也应给出一致的回答
- 对于时间相关的问题（如"之前"、"曾经"、"过去"等），如果汤底中提到了相关的时间点或事件，应根据具体内容判断
- 特别注意：如果两个问题本质上是同一个问题的不同表述方式，应给出一致的回答
- 谨慎判断"与此无关"。只有当问题内容与汤底完全无关，且无法从汤底中找到任何相关信息时，才使用"与此无关"

你需要返回JSON格式：
{{
    "answer_type": "是|否|与此无关|模糊问题",
    "summary": "事实总结陈述句。如果是'是'，转换为肯定陈述；如果是'否'，转换为否定陈述（与问题相反的事实）；如果是'与此无关'或'模糊问题'，设为null"
}}

示例：
问题："有第三者吗？"（汤底中有汤面中未提及但汤底中存在的人物，即第三者）
返回：{{"answer_type": "是", "summary": "存在第三者。"}}

问题："男孩有病吗？"（汤底中男孩没有病）
返回：{{"answer_type": "否", "summary": "男孩没有病。"}}

问题："足球是用什么做的？"
返回：{{"answer_type": "模糊问题", "summary": null}}

问题："男孩是侏儒吗？"（汤底明确提到男孩是侏儒）
返回：{{"answer_type": "是", "summary": "男孩是侏儒。"}}

问题："侏儒是一种病症吗？"（客观事实，与汤底中的侏儒特征相关）
返回：{{"answer_type": "是", "summary": "侏儒是一种病症。"}}

问题："男孩喝海龟汤吗？"（太宽泛的问题）
返回：{{"answer_type": "模糊问题", "summary": null}}

问题："男孩之前喝过海龟汤吗？"（汤底中提到之前喝过海龟汤）
返回：{{"answer_type": "是", "summary": "男孩之前喝过海龟汤。"}}"""

    return call_deepseek(system_prompt, question)

def give_hint(surface, bottom, known_facts):
    system_prompt = f"""你是一个海龟汤游戏的主持人。玩家请求一个提示。

汤面（公开的故事片段）：
{surface}

汤底（完整的故事真相）：
{bottom}

已知事实（玩家已经得知的信息）：
{known_facts if known_facts else "暂无"}

请给出一个与故事相关的提示，但不要直接泄露关键事实。

你需要返回JSON格式：
{{
    "hint": "提示内容",
    "summary": "提示的事实总结"
}}"""

    return call_deepseek(system_prompt, "请给我一个提示")

def judge_reasoning(reasoning, surface, bottom, points):
    points_desc = "\n".join([f"- ID {p['id']}: {p['text']}" + (f"（可接受表述：{', '.join(p.get('accept', []))}）" if p.get('accept') else "") for p in points])
    
    system_prompt = f"""你是一个海龟汤游戏的主持人。玩家提交了推理，你需要判断推理是否覆盖了关键事实。

汤面（公开的故事片段）：
{surface}

汤底（完整的故事真相）：
{bottom}

评分点（关键事实列表）：
{points_desc}

判断规则：
1. 对于每个评分点，判断玩家的推理是否覆盖了该关键事实
2. 如果推理中提到了该事实的核心内容，或使用了"可接受表述"中的词汇，则视为覆盖（true）
3. 如果推理未提及该关键事实，或明确相反，则视为未覆盖（false）
4. 忽略细节差异，只关注核心事实是否被提及

你需要返回JSON格式：
{{
    "results": [
        {{"id": 1, "covered": true}},
        {{"id": 2, "covered": false}},
        ...
    ]
}}"""

    return call_deepseek(system_prompt, f"玩家推理：{reasoning}")

def calculate_score(results, total_points):
    covered = sum(1 for r in results if r['covered'])
    ratio = covered / total_points
    
    if ratio >= 0.7:
        return "正确"
    elif ratio >= 0.2:
        return "部分正确"
    else:
        return "错误"

def classify_message(content):
    """分类用户消息类型
    
    Args:
        content: 用户输入的消息内容
        
    Returns:
        str: 分类结果，可能的值为 'reasoning'（推理）、'hint'（提示）或 'question'（普通问题）
    """
    system_prompt = """你是一个海龟汤游戏的消息分类器。请分析用户输入的消息，判断它属于以下哪种类型：
    
    1. 推理（reasoning）：用户尝试推测完整的故事真相，通常包含对多个线索的整合和逻辑分析
    2. 提示（hint）：用户请求游戏提示或线索，通常表达困惑或需要帮助
    3. 问题（question）：用户询问具体的事实问题，通常是是/否类型的问题
    
    请根据消息内容判断类型，并返回JSON格式：
    {
        "type": "reasoning|hint|question"
    }
    
    如果消息内容为不相关的，统一回复问题。
    
    示例：
    输入："我觉得那个男的其实是他自己杀了自己，因为他有双重人格"
    输出：{"type": "reasoning"}
    
    输入："能给我一个提示吗？我卡住了"
    输出：{"type": "hint"}
    
    输入："那个女的是他的妻子吗？"
    输出：{"type": "question"}
    """
    
    result = call_deepseek(system_prompt, content)
    return result.get('type', 'question')
