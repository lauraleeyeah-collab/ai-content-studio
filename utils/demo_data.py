"""
演示模式（Demo Mode）数据与分发逻辑。

用途：面试演示/离线体验时不需要真实 DashScope API Key，
所有 Agent 的 LLM 调用返回内置的高质量示例结果，让完整流程
可以在 30 秒内跑通，同时展示"LLM 负责判断、Python 负责计算"
的确定性后处理逻辑（打分排序、比例核验等依然真实执行）。

开启方式：
1. 环境变量 XHS_DEMO_MODE=1（启动前设置）
2. 或任意页面侧栏的"演示模式"开关（运行时切换）
"""
import json
import os

# ─────────────────────────────────────────────
# 示例原始文本（页面"一键填入示例笔记"用）
# ─────────────────────────────────────────────
DEMO_RAW_TEXT = """月薪8k到25k，我只做对了一件事：把AI用在工作里
我去年还只会用Excel做表，今年已经用AI自动化了80%的重复工作。今天分享我的AI工具组合，全部免费或低成本。
#AI工具 #效率提升 #职场 #副业
点赞1.2万 评论486 收藏5200 分享300
博主：小鹿AI笔记（3.5万粉丝）
6月28日发布

别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）
很多人下载了DeepSeek就用了一次，我整理了10个真正能提效的用法：做周报、写周计划、翻译英文邮件、整理会议纪要、生成PPT大纲...
#DeepSeek #AI提示词 #效率工具 #打工人
点赞8600 评论320 收藏4100 分享210
博主：AI玩转手册（2.1万粉丝）
7月2日发布

普通人3天学会用AI做小红书副业，我的真实收益记录
从0开始学AI做内容，第1周0收入，第3周开始有商家找我合作。附完整学习路径和踩坑清单，别走我走过的弯路。
#小红书运营 #副业 #AI写作 #搞钱
点赞2.3万 评论1020 收藏9800 分享1500
博主：搞钱日记本（8.9万粉丝）
7月5日发布"""

# ─────────────────────────────────────────────
# Agent0 采集/结构化结果
# ─────────────────────────────────────────────
DEMO_STRUCTURED = [
    {
        "raw_id": "1",
        "title": "月薪8k到25k，我只做对了一件事：把AI用在工作里",
        "body_text": "我去年还只会用Excel做表，今年已经用AI自动化了80%的重复工作。今天分享我的AI工具组合，全部免费或低成本。",
        "hashtags": ["AI工具", "效率提升", "职场", "副业"],
        "likes": 12000, "comments": 486, "collects": 5200, "shares": 300,
        "blogger_fans": 35000, "post_date": "2026-06-28", "note_type": "图文笔记",
        "extraction_confidence": "高",
    },
    {
        "raw_id": "2",
        "title": "别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）",
        "body_text": "很多人下载了DeepSeek就用了一次，我整理了10个真正能提效的用法：做周报、写周计划、翻译英文邮件、整理会议纪要、生成PPT大纲。",
        "hashtags": ["DeepSeek", "AI提示词", "效率工具", "打工人"],
        "likes": 8600, "comments": 320, "collects": 4100, "shares": 210,
        "blogger_fans": 21000, "post_date": "2026-07-02", "note_type": "图文笔记",
        "extraction_confidence": "高",
    },
    {
        "raw_id": "3",
        "title": "普通人3天学会用AI做小红书副业，我的真实收益记录",
        "body_text": "从0开始学AI做内容，第1周0收入，第3周开始有商家找我合作。附完整学习路径和踩坑清单，别走我走过的弯路。",
        "hashtags": ["小红书运营", "副业", "AI写作", "搞钱"],
        "likes": 23000, "comments": 1020, "collects": 9800, "shares": 1500,
        "blogger_fans": 89000, "post_date": "2026-07-05", "note_type": "图文笔记",
        "extraction_confidence": "高",
    },
]

# ─────────────────────────────────────────────
# Agent1 热点筛选（5维度打分，代码负责算总分和排序）
# ─────────────────────────────────────────────
DEMO_FILTERED = [
    {
        "topic_id": "3",
        "title": "普通人3天学会用AI做小红书副业，我的真实收益记录",
        "scores": {"relevance": 10, "freshness": 9, "engagement": 9, "replicability": 9, "extensibility": 10},
        "scoring_confidence": "高",
        "reason": "与AI工具+搞钱副业赛道高度相关，互动数据健康，副业变现路径可复制性强，且能延展出多个角度。",
    },
    {
        "topic_id": "1",
        "title": "月薪8k到25k，我只做对了一件事：把AI用在工作里",
        "scores": {"relevance": 10, "freshness": 7, "engagement": 8, "replicability": 9, "extensibility": 9},
        "scoring_confidence": "高",
        "reason": "职场+AI提效是赛道核心话题，薪资反差制造高点击，工具组合清单类内容收藏率高。",
    },
    {
        "topic_id": "2",
        "title": "别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）",
        "scores": {"relevance": 9, "freshness": 8, "engagement": 7, "replicability": 8, "extensibility": 9},
        "scoring_confidence": "高",
        "reason": "具体工具的高频用法清单，搜索流量稳定，但竞争较激烈，需要差异化角度。",
    },
]

# ─────────────────────────────────────────────
# Agent2 爆款拆解
# ─────────────────────────────────────────────
DEMO_ANALYZED = [
    {
        "topic_id": "3",
        "title": "普通人3天学会用AI做小红书副业，我的真实收益记录",
        "note_type": "图文笔记",
        "data_sufficiency": "充足",
        "title_formula": {"type": "数字时间型+结果承诺型", "template": "普通人{时间}学会{技能}，我的{收益}记录"},
        "opening_hook": {"pattern": "叙事式+数据对比", "description": "用'第1周0收入→第3周接商单'的真实时间线制造代入感"},
        "content_structure": "身份引入→时间线复盘→学习路径清单→踩坑提醒→互动引导",
        "emotion_trigger": {"pattern": "希望感+损失厌恶", "description": "给普通人希望，同时用'别走弯路'暗示不跟会吃亏"},
        "interaction_script": "评论区扣'副业'领取完整学习路径表格",
        "replicability": {"score": 9, "reason": "学习路径和踩坑清单是通用干货，任何赛道都能套用"},
    },
    {
        "topic_id": "1",
        "title": "月薪8k到25k，我只做对了一件事：把AI用在工作里",
        "note_type": "图文笔记",
        "data_sufficiency": "充足",
        "title_formula": {"type": "身份反差型+数字对比型", "template": "月薪{X}到{Y}，我只做对了一件事：{核心方法}"},
        "opening_hook": {"pattern": "反差引入", "description": "薪资数字反差直接抓住目标人群注意力"},
        "content_structure": "前后对比→方法揭示→工具清单→成本说明→行动号召",
        "emotion_trigger": {"pattern": "焦虑缓解+希望", "description": "缓解'不会用AI会被淘汰'的焦虑，给出低成本解决方案"},
        "interaction_script": "收藏这份工具清单，评论区告诉我你最想提效的工作场景",
        "replicability": {"score": 8, "reason": "工具清单类可批量复制，但需要真实使用体验支撑"},
    },
    {
        "topic_id": "2",
        "title": "别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）",
        "note_type": "图文笔记",
        "data_sufficiency": "充足",
        "title_formula": {"type": "反常识型+数字清单型", "template": "别再{行为}了！{工具}的{N}个隐藏用法（亲测有效）"},
        "opening_hook": {"pattern": "反常识点破", "description": "'收藏吃灰'精准命中绝大多数人的真实使用场景"},
        "content_structure": "痛点共鸣→用法清单→每个用法配场景→总结引导",
        "emotion_trigger": {"pattern": "占便宜心理+行动焦虑", "description": "'隐藏用法'暗示信息差，'亲测有效'降低信任门槛"},
        "interaction_script": "先收藏，评论区打卡你用到了第几个",
        "replicability": {"score": 8, "reason": "换工具就能批量生产同类清单，但需要真实测试避免同质化"},
    },
]

# ─────────────────────────────────────────────
# Agent3 选题生成（10条，8视频+2图文，比例符合默认配置）
# ─────────────────────────────────────────────
DEMO_TOPICS = [
    {
        "topic_title": "用AI把简历改到HR主动约面，我的3步实操",
        "core_angle": "AI改简历的3步实操流程，突出'HR主动约面'的结果导向",
        "borrowed_from": {"source_topic_id": "1", "structure_type": "教程型+数字清单型"},
        "persona_fit": "命中职场发展+AI工具方向，贴合目标人群求职痛点",
        "estimated_potential": "高",
        "potential_reason": "简历话题常年高搜索量，套路验证次数多，人设匹配度高",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "DeepSeek帮我做周报，省下2小时，领导以为我开挂了",
        "core_angle": "用具体工具解决打工人周报痛点，突出时间节省和结果反差",
        "borrowed_from": {"source_topic_id": "2", "structure_type": "痛点共鸣型+结果反差"},
        "persona_fit": "命中职场发展+效率工具方向，周报是打工人高频刚需",
        "estimated_potential": "高",
        "potential_reason": "周报场景覆盖面广，示范过程可看性强，适合视频形式",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "AI副业第一周收入0，我靠什么撑到第3周接单",
        "core_angle": "真实时间线复盘，破除'AI副业一夜暴富'幻觉，建立信任",
        "borrowed_from": {"source_topic_id": "3", "structure_type": "时间线复盘型"},
        "persona_fit": "命中搞钱副业方向，真实记录符合账号'不装'的调性",
        "estimated_potential": "高",
        "potential_reason": "真实感强，收藏率预期高，反套路标题点击率高",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "月薪8k和25k的差距，差的不是努力，是这套AI工作流",
        "core_angle": "从薪资反差切入AI工作流方法论，比单点工具更有深度",
        "borrowed_from": {"source_topic_id": "1", "structure_type": "身份反差型"},
        "persona_fit": "命中职场发展+AI工具方向，切入'方法论'提升内容壁垒",
        "estimated_potential": "高",
        "potential_reason": "薪资话题点击率高，工作流体系比工具清单更难被抄袭",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "收藏了100篇AI教程还在吃灰？我帮你筛出这5篇就够了",
        "core_angle": "做信息筛选服务，帮用户从海量教程中解脱，反向利用'收藏吃灰'心理",
        "borrowed_from": {"source_topic_id": "2", "structure_type": "反常识型+筛选清单型"},
        "persona_fit": "命中AI工具+效率提升方向，'帮用户省时间'符合账号价值主张",
        "estimated_potential": "中",
        "potential_reason": "切入角度新颖但依赖素材整理质量，竞争中等",
        "content_format": "图文笔记",
    },
    {
        "topic_title": "英语六级都没过的人，靠AI把英文邮件写到了外企客户心坎里",
        "core_angle": "结合英语学习+职场场景，AI辅助语言表达的真实案例",
        "borrowed_from": {"source_topic_id": "1", "structure_type": "身份反差型+结果承诺"},
        "persona_fit": "命中英语学习+职场发展方向，贴合有语言短板的目标人群",
        "estimated_potential": "高",
        "potential_reason": "英语+职场双痛点叠加，身份反差强化传播性",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "记账3年我悟了：AI帮我自动分类，每月多存2000",
        "core_angle": "把AI自动化应用到理财记账场景，契合搞钱人设的完整叙事",
        "borrowed_from": {"source_topic_id": "3", "structure_type": "时间线复盘型"},
        "persona_fit": "命中理财+AI工具方向，账号内容版图从'赚钱'延伸到'存钱'",
        "estimated_potential": "中",
        "potential_reason": "记账话题稳定，但需和已有理财内容差异化",
        "content_format": "图文笔记",
    },
    {
        "topic_title": "3个免费AI工具，让我每天省出2小时做副业",
        "core_angle": "免费工具组合+时间管理，把'提效'和'搞钱'两个主线串起来",
        "borrowed_from": {"source_topic_id": "1", "structure_type": "数字清单型+结果承诺"},
        "persona_fit": "命中AI工具+搞钱副业方向，串联账号两大内容主线",
        "estimated_potential": "高",
        "potential_reason": "免费工具点击率高，'省时间做副业'双重价值主张",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "我用AI写小红书文案3个月，总结出5条不踩坑的提示词",
        "core_angle": "分享AI写作的真实经验和可复用提示词，反哺账号主题",
        "borrowed_from": {"source_topic_id": "3", "structure_type": "复盘型+清单型"},
        "persona_fit": "命中AI写作+小红书运营方向，内容即账号本身的方法论沉淀",
        "estimated_potential": "高",
        "potential_reason": "AI+小红书双热门，实操经验比理论教程更有说服力",
        "content_format": "视频笔记",
    },
    {
        "topic_title": "自律不是靠意志力，我给自己搭了一套AI习惯提醒系统",
        "core_angle": "从'自律习惯'人设方向切入，AI工具做行为设计",
        "borrowed_from": {"source_topic_id": "2", "structure_type": "教程型"},
        "persona_fit": "命中自律习惯方向，补齐账号内容版图中'习惯养成'板块",
        "estimated_potential": "中",
        "potential_reason": "习惯养成话题稳定，AI结合角度有一定新鲜感",
        "content_format": "视频笔记",
    },
]

# ─────────────────────────────────────────────
# Agent4 文案生成（图文笔记示例）
# ─────────────────────────────────────────────
DEMO_COPY = """用AI把简历改到HR主动约面，我的3步实操（附提示词模板）

上个月用这套方法帮朋友改简历，投出去第4天就有3家HR主动约面，其中还有一家是她之前投了没回音的。

先说结论：AI改简历的核心不是"让AI写"，而是"让AI帮你做匹配和量化"。

第1步：先让AI拆解目标JD
把目标岗位的JD粘给AI，让它列出：这个岗位最看重哪5个能力、每个能力在JD里的出现频率、你的简历里对应证据够不够。这一步帮你搞清楚"HR到底在找什么"。

第2步：用"成果量化"模板重写经历
不要写"负责XX工作"，要写"通过XX方法，把XX指标从A提升到B"。给你一个可以直接用的提示词：
"你是资深HR，请把我这段工作经历改写成成果导向的描述，必须包含量化数字和具体方法，控制在2行以内，语气专业但不生硬。"

第3步：AI模拟面试官交叉检查
把改好的简历和JD一起丢给AI，让它扮演这个岗位的面试官，针对简历提出5个可能被追问的问题。答不上来的地方，就是简历里"吹过头"的地方，赶紧改掉。

三句话总结：
- JD拆解决定方向，这一步省不得
- 量化数字是简历的命，AI只帮你找措辞
- 面试官视角检查，专治"简历看着挺好"

评论区扣"简历"，我把上面3个提示词模板整理成一份文档发你。

#AI工具 #简历 #求职 #职场干货 #面试技巧"""

# ─────────────────────────────────────────────
# 笔记爆款分析（Agent: note_scorer）
# ─────────────────────────────────────────────
DEMO_NOTE_SCORE = {
    "scores": {
        "title_attractiveness": {
            "score": 9,
            "reason": "数字对比（8k到25k）+身份反差制造强点击冲动，人群指向明确",
            "suggestion": "可保留核心结构，把'25k'换成更具体的数字（如'1年涨3倍'）",
        },
        "cover_appeal": {
            "score": 7,
            "reason": "文字型封面信息密度高，但缺少视觉记忆点",
            "suggestion": "增加人物实拍或对比图表元素，提升辨识度",
        },
        "copy_quality": {
            "score": 8,
            "reason": "正文逻辑清晰，前后对比→方法→清单结构完整",
            "suggestion": "工具清单可增加每个工具的一句话使用场景",
        },
        "hashtag_strategy": {
            "score": 6,
            "reason": "标签都是大词，竞争激烈，缺少垂直细分标签",
            "suggestion": "补充'AI提效''办公自动化'等中长尾标签",
        },
        "structure_flow": {
            "score": 8,
            "reason": "开篇代入感强，但中间工具介绍稍显平铺",
            "suggestion": "每个工具增加'我用它省了多少时间'的具体案例",
        },
        "emotion_hook": {
            "score": 8,
            "reason": "焦虑缓解+希望感双触发，收藏动机明确",
            "suggestion": "结尾可增加'你已经比90%的人先行动了'的认同感设计",
        },
        "interaction_design": {
            "score": 7,
            "reason": "有评论引导，但缺少具体钩子",
            "suggestion": "用'评论区扣1领清单'替代开放式提问，互动率更高",
        },
    },
    "overall_comment": "整体是一篇完成度很高的干货型笔记，标题和结构是最大亮点；主要提升空间在标签策略和互动引导，属于低成本高回报的优化项。",
}

# ─────────────────────────────────────────────
# 竞品账号分析（Agent: account_analyzer 的 llm_analysis）
# ─────────────────────────────────────────────
DEMO_ACCOUNT_ANALYSIS = {
    "content_strategy": "以'AI工具+搞钱'双主线驱动，干货教程占80%、真实记录占20%，用结果反差制造点击。",
    "positioning_analysis": "定位'深圳搞钱女孩'，人设清晰且具有地域符号，与目标人群（大学生+职场人）距离近，信任感强。",
    "strengths": [
        "内容主线聚焦，AI工具、职场、搞钱三个主题形成相互导流的内容矩阵",
        "标题公式熟练，数字对比、身份反差使用频率高且有效",
        "真实时间线复盘类内容占比合理，建立差异化信任",
    ],
    "weaknesses": [
        "视频笔记比例偏低，与平台当前流量倾斜方向不完全匹配",
        "标签策略偏重大词，垂直流量池覆盖不足",
        "发布时间集中在工作日白天，可能错过通勤/晚间流量高峰",
    ],
    "content_gaps": "AI工具的'翻车/避坑'视角内容较少，该角度冲突性强、传播性好；'AI+理财记账'等生活化场景覆盖不足。",
    "growth_assessment": "账号处于稳定增长期，互动率健康，内容模型已被验证；瓶颈在内容形式单一（图文为主）和垂直标签覆盖。",
    "actionable_recommendations": [
        {"priority": "高", "action": "把视频笔记比例提升到60%以上，优先改造'操作演示型'选题", "rationale": "平台流量倾斜视频，且演示型内容完播率更高"},
        {"priority": "高", "action": "标签策略改为'2大词+4中词+2小词'组合", "rationale": "提升垂直流量池覆盖，中长尾标签竞争小、转化准"},
        {"priority": "中", "action": "新增'AI工具避坑'系列，每周1条", "rationale": "冲突性内容易引发评论互动，且形成内容护城河"},
    ],
    "borrowable_patterns": [
        "薪资/收益数字对比标题公式（月薪8k→25k、第1周0收入→第3周接单）",
        "'拆解教程+免费提示词模板'的收藏驱动结构",
        "评论区'扣关键词领资料'的私域引流话术",
    ],
}

# ─────────────────────────────────────────────
# 热门内容趋势（Agent: trend_summarizer 的 llm_summary）
# ─────────────────────────────────────────────
DEMO_TREND_SUMMARY = {
    "dominant_themes": ["AI工具实操教程", "AI+副业变现", "职场提效工具组合", "AI写作/提示词技巧"],
    "emerging_patterns": "从'工具介绍'转向'真实使用记录'，带时间线和收入/效果数据的复盘型内容增长明显；'AI+具体场景'（简历、周报、记账）细分内容正在起量。",
    "declining_patterns": "纯工具罗列清单（只列工具名不演示）互动下滑，泛泛的'AI改变世界'鸡汤类内容失去流量。",
    "viral_formulas": [
        {
            "formula": "身份反差+数字对比标题（月薪8k到25k / 第1周0收入到第3周接单）",
            "evidence_count": 3,
            "example_titles": ["月薪8k到25k，我只做对了一件事：把AI用在工作里", "普通人3天学会用AI做小红书副业，我的真实收益记录"],
        },
        {
            "formula": "反常识点破+清单落地（别再收藏吃灰了+10个用法）",
            "evidence_count": 2,
            "example_titles": ["别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）"],
        },
    ],
    "content_gaps": "AI工具的'翻车/避坑/真实成本'视角几乎空白；'AI+个人理财记账'生活化场景覆盖不足；针对特定职业（老师、会计、护士）的AI工作流定制内容稀缺。",
    "format_recommendations": "视频笔记优先（操作演示+口播复盘），图文用于清单类和深度长文；合集/系列形式适合'工具工作流'主题沉淀。",
    "strategic_summary": "该赛道正从'工具科普期'进入'效果验证期'，真实数据、具体场景、可复用模板是三大流量杠杆。建议账号内容向'真实使用记录+场景化工作流'升级，用避坑视角建立差异化，同时提高视频内容占比以承接平台流量倾斜。",
}

# ─────────────────────────────────────────────
# 标题优化（生成 + 评分）
# ─────────────────────────────────────────────
DEMO_TITLES = [
    {"title": "月薪8k到25k，我只做对了一件事：把AI用在工作里", "formula_type": "身份反差型+数字对比型", "rationale": "保留原爆款结构，数字反差直接命中职场人群"},
    {"title": "AI写周报被领导点名表扬，我的3个提示词技巧（建议收藏）", "formula_type": "结果承诺型+数字清单型", "rationale": "具体结果+收藏指令，命中搜索词'AI写周报'且前20字含关键词"},
    {"title": "普通人和高薪的差距，就差这套AI工作流", "formula_type": "痛点共鸣型", "rationale": "'普通人vs高薪'制造身份代入，弱化说教感"},
    {"title": "我用AI改简历，第4天收到3个面试邀请", "formula_type": "结果承诺型", "rationale": "具体时间+具体结果，比'提升通过率'更有画面感"},
    {"title": "DeepSeek帮我做周报，领导以为我开挂了", "formula_type": "悬念型+身份反差型", "rationale": "结果悬念+领导视角反差，引发好奇"},
    {"title": "职场AI提效必看：AI写周报的3个技巧，领导追着要模板", "formula_type": "身份标签型+数字清单型", "rationale": "'职场AI'命中赛道搜索词，前20字双关键词覆盖"},
]

DEMO_TITLE_SCORES = [
    {"title": "月薪8k到25k，我只做对了一件事：把AI用在工作里", "scores": {"click_curiosity": 9, "keyword_relevance": 8, "emotional_resonance": 8, "information_clarity": 8, "uniqueness": 8}},
    {"title": "普通人和高薪的差距，就差这套AI工作流", "scores": {"click_curiosity": 8, "keyword_relevance": 8, "emotional_resonance": 9, "information_clarity": 7, "uniqueness": 7}},
    {"title": "别再收藏吃灰了！DeepSeek的10个隐藏用法（亲测有效）", "scores": {"click_curiosity": 8, "keyword_relevance": 9, "emotional_resonance": 7, "information_clarity": 8, "uniqueness": 7}},
    {"title": "我用AI改简历，第4天收到3个面试邀请", "scores": {"click_curiosity": 7, "keyword_relevance": 8, "emotional_resonance": 8, "information_clarity": 9, "uniqueness": 7}},
    {"title": "DeepSeek帮我做周报，领导以为我开挂了", "scores": {"click_curiosity": 7, "keyword_relevance": 8, "emotional_resonance": 7, "information_clarity": 7, "uniqueness": 8}},
    {"title": "AI副业第1周0收入，我靠什么撑到第3周接单", "scores": {"click_curiosity": 8, "keyword_relevance": 7, "emotional_resonance": 8, "information_clarity": 8, "uniqueness": 9}},
]

# ─────────────────────────────────────────────
# 标签推荐（8个标签，2大+4中+2小，不触发分布警告）
# ─────────────────────────────────────────────
DEMO_HASHTAGS = {
    "recommended_hashtags": [
        {"tag": "AI工具", "category": "大词", "estimated_heat": "高", "rationale": "赛道核心大词，保证初始流量池", "relevance_score": 9},
        {"tag": "效率提升", "category": "大词", "estimated_heat": "高", "rationale": "职场人群高频搜索词", "relevance_score": 8},
        {"tag": "职场干货", "category": "中词", "estimated_heat": "中", "rationale": "垂直定位职场人群，竞争适中", "relevance_score": 9},
        {"tag": "AI提示词", "category": "中词", "estimated_heat": "中", "rationale": "搜索量大且与内容强相关", "relevance_score": 9},
        {"tag": "办公自动化", "category": "中词", "estimated_heat": "中", "rationale": "精准命中'AI做表/做文档'场景", "relevance_score": 8},
        {"tag": "简历优化", "category": "中词", "estimated_heat": "中", "rationale": "场景化标签，转化精准", "relevance_score": 8},
        {"tag": "副业搞钱", "category": "小词", "estimated_heat": "低", "rationale": "细分流量池，竞争小但精准", "relevance_score": 7},
        {"tag": "DeepSeek用法", "category": "小词", "estimated_heat": "低", "rationale": "工具长尾词，搜索意图明确", "relevance_score": 7},
    ],
    "strategy_note": "采用'2大词引流 + 4中词定位 + 2小词精准'的漏斗结构：大词保证初始曝光，中词承接垂直人群，小词锁定高转化搜索。",
    "avoid_tags": ["#副业赚钱（泛泛无人群指向）", "#搞钱（被过度使用，内容易淹没）"],
}

# ─────────────────────────────────────────────
# 截图/图片内容提取（视觉模型）
# ─────────────────────────────────────────────
DEMO_IMAGE_EXTRACT = [
    {
        "title": "用AI写周报的正确姿势，我踩过这些坑",
        "body_text": "很多人让AI写周报写得像流水账，分享3个提示词技巧和我的真实改稿过程。",
        "hashtags": ["AI工具", "周报", "效率提升"],
        "likes": 5600, "comments": 210, "collects": 2900, "shares": 150,
        "blogger_fans": 18000, "post_date": "2026-07-01", "note_type": "图文笔记",
        "extraction_confidence": "高",
    },
    {
        "title": "DeepSeek+Excel，1分钟搞定月度数据汇总",
        "body_text": "演示用DeepSeek写公式+辅助数据分析的完整流程，全程不需要编程基础。",
        "hashtags": ["DeepSeek", "Excel", "办公自动化"],
        "likes": 9200, "comments": 480, "collects": 6100, "shares": 380,
        "blogger_fans": 42000, "post_date": "2026-07-03", "note_type": "视频笔记",
        "extraction_confidence": "高",
    },
]

# ─────────────────────────────────────────────
# M1 图文工厂：示例选题 / 搜索词 / 封面提示词 / 平台化正文 / 互动话术
# ─────────────────────────────────────────────
DEMO_TOPIC = {
    "title": "用AI写周报被领导点名表扬，我的3个提示词技巧",
    "angle": "真实使用记录视角：从'写周报像流水账'到'被评为重点周报'，分享3个可复用的提示词技巧",
    "content": "很多人让AI写周报写得像流水账，核心是没给AI角色设定、素材和追问。我用了半年AI写周报，从被领导说'像流水账'到被评为'重点周报'，分享3个提示词技巧：给AI角色设定、喂结构化素材、追加追问让进度量化。数据和结论一定要自己核对。",
}

DEMO_SEARCH_KEYWORDS = [
    {"keyword": "AI写周报", "search_intent": "找教程", "priority": 9, "is_long_tail": True},
    {"keyword": "AI提效工具", "search_intent": "找工具清单", "priority": 8, "is_long_tail": False},
    {"keyword": "职场AI", "search_intent": "找干货", "priority": 7, "is_long_tail": False},
    {"keyword": "AI提示词模板", "search_intent": "找模板", "priority": 7, "is_long_tail": True},
    {"keyword": "周报怎么写", "search_intent": "找答案", "priority": 6, "is_long_tail": True},
    {"keyword": "办公自动化", "search_intent": "找方法", "priority": 5, "is_long_tail": False},
    {"keyword": "打工人提效", "search_intent": "找共鸣", "priority": 4, "is_long_tail": False},
]

DEMO_COVER_PROMPT = {
    "subject": "年轻职场女性坐在电脑前，屏幕上是AI生成周报的界面，桌上放着一杯咖啡，整体明亮通透的办公场景",
    "style": "真实摄影感 + 轻ins风，浅色背景，人物自然不做作",
    "composition": "人物居中偏右，左侧留出1/3空间给文字位，画面下方留白",
    "text_slot": "主标题：AI写周报\\n副标题：3个提示词技巧",
    "color_scheme": "主色浅米白，对比色深蓝，文字用高对比深色大字",
    "negative_hint": ["避免花哨滤镜", "避免遮挡人物面部", "避免画面过暗"],
}

DEMO_PLATFORM_COPY = {
    "content": "如果你还在为每周写周报发愁，这篇直接收藏。我用AI写周报已经半年，从被领导说'像流水账'到被评为'重点周报'，核心就3个提示词技巧。\n\n第一，给AI角色设定。不要直接说'帮我写周报'，先告诉它'你是一个项目经理，要突出本周进度和风险'，输出立刻有重点。\n\n第二，喂结构化素材。把本周做的5件事按'完成/进行中/风险'分类贴进去，AI输出的周报自带逻辑，不用你二次整理。\n\n第三，追加追问。第一次输出后，加一句'把进度量化成百分比，风险给应对方案'，周报的专业度直接拉满。\n\n最后提醒一句：AI写周报是提效不是代劳，数据和结论一定要自己核对。建议收藏，下周写周报前直接翻出来用。",
    "structure_note": "清单体：开头给价值承诺 + 3步实操 + 结尾提醒，符合小红书收藏导向",
    "rewrite_reasons": [
        "开头改成直接给'收藏理由'，符合小红书搜索与收藏权重",
        "正文拆成3个短段，每段一个要点，降低阅读门槛",
        "结尾加了显性「建议收藏」指令，提升收藏率",
    ],
}
DEMO_INTERACTION_COPY = {
    "collect_reasons": [
        "建议收藏，下周写周报前直接翻出这篇照着做",
        "3个提示词模板可以直接复制改自己场景用",
    ],
    "comment_guides": [
        "你写周报最头疼的是哪一步？评论区报个数字：1素材整理 2措辞表达 3领导看不懂",
        "有没有用过AI写周报翻车的？分享下你的坑，我帮你改提示词",
    ],
    "cta_suggestions": [
        "建议收藏，下次需要时直接翻出来用",
        "转发给同样被周报折磨的同事",
    ],
    "strategy_note": "收藏理由显性+评论区二选一提问，双管齐下提升收藏率与评论率",
}

# ─────────────────────────────────────────────
# M2 视频工厂：分镜脚本 / 播放优化 / 互动策略
# ─────────────────────────────────────────────
DEMO_VIDEO_STORYBOARD = {
 "video_title_hook": "用AI写周报被领导点名表扬，这条视频拆解3个提示词技巧",
 "duration_seconds": 60,
 "storyboard": [
  {
   "time_start": 0,
   "time_end": 5,
   "scene": "钩子",
   "visual": "人物近景直面镜头",
   "voiceover": "（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。",
   "subtitle": "（钩子段字幕）周报被领导点名表扬",
   "transition": "硬切"
  },
  {
   "time_start": 5,
   "time_end": 15,
   "scene": "痛点",
   "visual": "场景：痛点，人物中景，屏幕演示AI周报界面",
   "voiceover": "（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。",
   "subtitle": "（痛点段字幕）写周报像流水账？",
   "transition": "硬切"
  },
  {
   "time_start": 15,
   "time_end": 30,
   "scene": "方法一",
   "visual": "场景：方法一，人物中景，屏幕演示AI周报界面",
   "voiceover": "（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。",
   "subtitle": "（方法一段字幕）第1招：给AI角色设定",
   "transition": "硬切"
  },
  {
   "time_start": 30,
   "time_end": 45,
   "scene": "方法二",
   "visual": "场景：方法二，人物中景，屏幕演示AI周报界面",
   "voiceover": "（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。",
   "subtitle": "（方法二段字幕）第2招：喂结构化素材",
   "transition": "硬切"
  },
  {
   "time_start": 45,
   "time_end": 55,
   "scene": "避坑",
   "visual": "场景：避坑，人物中景，屏幕演示AI周报界面",
   "voiceover": "（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。",
   "subtitle": "（避坑段字幕）第3招：追加追问+自己核对",
   "transition": "硬切"
  },
  {
   "time_start": 55,
   "time_end": 60,
   "scene": "结尾",
   "visual": "人物近景直面镜头",
   "voiceover": "（结尾段口播）建议收藏，下次写周报直接翻出来用。",
   "subtitle": "（结尾段字幕）建议收藏",
   "transition": "叠化"
  }
 ],
 "closing_cta": "建议收藏，下次写周报直接翻出来用。"
}

DEMO_VIDEO_PLAY = {
 "five_sec_hook": "被领导点名表扬的周报，我只改了3个地方。",
 "hook_assessment": "现有开头已给出结果承诺，可再增加具体数字增强可信度。",
 "collect_cta": "建议收藏，下次写周报前直接翻出这条视频照着做。",
 "completion_tips": [
  "方法段落各控制在12秒内，避免拖沓",
  "结尾前3秒给'建议收藏'动作，别等口播结束"
 ],
 "subtitle_tips": [
  "字幕字号加大，适配地铁通勤静音观看",
  "关键数字（3个技巧）用大字高亮"
 ],
 "risks": [
  "避免出现'绝对有效'等极限词",
  "AI生成画面需标注AI创作，符合平台强制标注要求"
 ]
}

DEMO_VIDEO_INTERACTION = {
 "comment_pin": "这条视频建议收藏，3个提示词技巧可以直接复制改自己场景用。你写周报最头疼哪一步？评论区报个数字。",
 "engagement_questions": [
  "你写周报最头疼的是哪一步？1素材整理 2措辞表达 3领导看不懂",
  "有没有用AI写周报翻车过？分享下你的坑，我帮你改提示词"
 ],
 "share_reasons": [
  "转发给同样被周报折磨的同事",
  "分享到工作群，下周写周报前一起用"
 ],
 "reply_strategy": "发布后前30分钟回复所有评论，置顶评论引导收藏。",
 "risk_notes": [
  "不承诺'绝对有效'，用'我亲测'表述",
  "AI生成画面需标注"
 ]
}

# ─────────────────────────────────────────────
# M3 渠道中心：渠道改写（按平台版本）/ 合规检查
# ─────────────────────────────────────────────
DEMO_CHANNEL_REWRITES = {'公众号': {'ai_label': {'required': True, 'template': '本文由 AI 辅助创作'},
         'channel': '公众号',
         'code_checks': {'has_collect_cta': False,
                         'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
         'content': '被领导点名表扬的周报，我只改了3个提示词技巧。\n'
                    '\n'
                    '## 为什么你的周报像流水账\n'
                    "很多人让AI写周报，第一步就错了：直接说'帮我写周报'，AI只能给你模板腔。\n"
                    '\n'
                    '## 第1招：给AI角色设定\n'
                    "告诉它'你是一个项目经理，要突出本周进度和风险'……\n"
                    '\n'
                    '## 第2招：喂结构化素材\n'
                    '按完成/进行中/风险分类……\n'
                    '\n'
                    '## 第3招：追加追问\n'
                    "'进度量化成百分比，风险给应对方案'……\n"
                    '\n'
                    '## 写在最后\n'
                    'AI写周报是提效不是代劳，数据和结论一定要自己核对。你写周报最头疼哪一步？评论区聊聊。',
         'publish_tips': ['标题前20字放关键词', '声明AI辅助创作'],
         'rewrite_reasons': ['开头3秒钩子+分段小标题，符合公众号完读率权重', '信息密度高、节奏快，适配64个流量点位', '结尾互动问题引导评论']},
 '小红书': {'ai_label': {'required': True, 'template': '本文由 AI 辅助创作'},
         'channel': '小红书',
         'code_checks': {'has_collect_cta': True,
                         'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
         'content': '被领导点名表扬的周报，我只改了3个提示词技巧，这篇建议收藏。\n'
                    '\n'
                    "第一，给AI角色设定。告诉它'你是一个项目经理，要突出进度和风险'，输出立刻有重点。\n"
                    '\n'
                    '第二，喂结构化素材。按完成/进行中/风险分类贴进去，周报自带逻辑。\n'
                    '\n'
                    "第三，追加追问。加一句'进度量化成百分比，风险给应对方案'。\n"
                    '\n'
                    '最后提醒：AI写周报是提效不是代劳，数据和结论自己核对。建议收藏，下周直接翻出来用。',
         'publish_tips': ["标题前20字放'AI写周报'关键词", '发布时勾选AI创作标注'],
         'rewrite_reasons': ['开头直接给结果承诺+收藏指令，符合小红书CES收藏高权重',
                             '清单体三步骤结构，降低阅读门槛，利好停留时长',
                             '结尾显性收藏指令，提升收藏率']},
 '抖音': {'ai_label': {'required': True, 'template': '本视频含 AI 辅助创作内容'},
        'channel': '抖音',
        'code_checks': {'has_collect_cta': True,
                        'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
        'content': '被领导点名表扬的周报，我只改了3个地方。\n'
                   '\n'
                   '第一，给AI角色设定，让它当项目经理。\n'
                   '第二，喂结构化素材，按完成/进行中/风险分类。\n'
                   '第三，追加追问，让进度量化成百分比。\n'
                   '\n'
                   '数据和结论一定要自己核对。建议收藏，下次写周报直接翻出来用。',
        'publish_tips': ['发布时勾选AI创作标注', '评论区置顶引导收藏'],
        'rewrite_reasons': ['口播短文案，3秒钩子开头，符合抖音5秒完播权重', "显性'建议收藏'指令，符合收藏率第一权重", '删掉长段解释，适配快节奏']},
 '知乎': {'ai_label': {'required': True, 'template': '本文由 AI 辅助创作'},
        'channel': '知乎',
        'code_checks': {'has_collect_cta': False,
                        'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
        'content': '结论先行：用AI写周报被领导认可，核心不是工具，是提示词方法。\n'
                   '\n'
                   "我用了半年AI写周报，从'像流水账'到'重点周报'，方法就3条：\n"
                   '\n'
                   '1. 给AI角色设定（项目经理视角）\n'
                   '2. 喂结构化素材（完成/进行中/风险）\n'
                   '3. 追加追问（进度量化+风险应对）\n'
                   '\n'
                   '注意事项：AI输出的是草稿，数据与结论必须人工核对，这是提效工具不是代劳工具。\n'
                   '\n'
                   "延伸阅读：想系统提升职场表达，可以先从'结构化汇报'入手。",
        'publish_tips': ['发布时声明AI辅助创作', '补充具体案例数据增强可信度'],
        'rewrite_reasons': ['结论先行，第一段直接给答案，符合知乎专业内容偏好', '分点论证+注意事项，建立专业人设', '结尾给延伸建议，引导深度互动']},
 '视频号': {'ai_label': {'required': True, 'template': '本文由 AI 辅助创作'},
         'channel': '视频号',
         'code_checks': {'has_collect_cta': True,
                         'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
         'content': '你写周报是不是也像流水账？\n'
                    '\n'
                    "我用了半年AI写周报，从被领导说'像流水账'到被评为'重点周报'，就3个改变。\n"
                    '\n'
                    '给AI角色设定、喂结构化素材、追加追问让进度量化。\n'
                    '\n'
                    '你写周报最头疼哪一步？评论区报个数字，我帮你改提示词。\n'
                    '\n'
                    '建议收藏，下次写周报直接翻出来用。',
         'publish_tips': ['发布后前30分钟回复所有评论', '配合私域群发分享'],
         'rewrite_reasons': ['评论引导问题设计，符合视频号社交推荐靠评论数', '真实人设叙事（我用了半年），贴近私域承接调性', '结尾引导收藏+评论双行动']},
 '问一问': {'ai_label': {'required': True, 'template': '本文由 AI 辅助创作'},
         'channel': '问一问',
         'code_checks': {'has_collect_cta': True,
                         'red_lines': {'hits': [], 'passed': True, 'suggestion': ''}},
         'content': '用AI写周报，3个提示词技巧（亲测有效）：\n'
                    '\n'
                    "1. 给AI角色设定：告诉它'你是项目经理，突出进度和风险'。\n"
                    '2. 喂结构化素材：按完成/进行中/风险分类。\n'
                    "3. 追加追问：'进度量化成百分比，风险给应对方案'。\n"
                    '\n'
                    '【图】建议配一张周报前后对比截图。\n'
                    '\n'
                    '提醒：数据和结论要自己核对，AI是提效不是代劳。建议收藏。',
         'publish_tips': ['配图用周报前后对比截图', '回答保持简洁，别展开长文'],
         'rewrite_reasons': ['开头直接给答案，符合问一问高信息密度偏好', '配图位标注，图片好看是奖励项', '可直接收藏的实用结构']}}

DEMO_COMPLIANCE = {'ai_label_suggestion': 'AI 生成内容，建议声明「本文由 AI 辅助创作」。',
 'llm_findings': [],
 'overall_verdict': 'pass',
 'summary': '未发现高合规风险，AI 标注建议已给出。'}


# ─────────────────────────────────────────────
# 系统Prompt关键词 → 示例数据 路由
# 用 SYSTEM_PROMPT 里的稳定身份词做匹配，避免误命中
# ─────────────────────────────────────────────


def _video_gen_demo(system_prompt: str, user_prompt: str) -> str:
    """M2 延伸演示：从 user_prompt 提取目标模型，返回对应提示词版本。"""
    import re
    m = re.search(r"目标模型：([^\s\n]+)", user_prompt)
    model = m.group(1) if m else "可灵 Kling"
    data = DEMO_VIDEO_GEN_PROMPTS.get(model)
    if data is None:
        data = dict(DEMO_VIDEO_GEN_PROMPTS["可灵 Kling"])
        data["model"] = model
    return json.dumps(data, ensure_ascii=False)


def _channel_rewrite_demo(system_prompt: str, user_prompt: str) -> str:
    """M3 渠道改写演示：从 user_prompt 提取目标平台，返回该平台版本。"""
    import re
    m = re.search(r"目标平台：([^\s\n]+)", user_prompt)
    channel = m.group(1) if m else "小红书"
    data = DEMO_CHANNEL_REWRITES.get(channel)
    if data is None:
        data = dict(DEMO_CHANNEL_REWRITES["小红书"])
        data["channel"] = channel
    return json.dumps(data, ensure_ascii=False)


# ─────────────────────────────────────────────
# M4 数据中心：渠道指标 / 爆款归因解读
# ─────────────────────────────────────────────
DEMO_METRICS = [{'channel': '小红书',
  'collects': 980,
  'comments': 210,
  'completion_rate': 0.0,
  'content_title': '用AI写周报被领导点名表扬',
  'likes': 620,
  'play_rate': 0.0,
  'shares': 160,
  'views': 8500},
 {'channel': '抖音',
  'collects': 2600,
  'comments': 340,
  'completion_rate': 0.31,
  'content_title': '用AI写周报被领导点名表扬',
  'likes': 1500,
  'play_rate': 0.42,
  'shares': 90,
  'views': 32000},
 {'channel': '视频号',
  'collects': 220,
  'comments': 150,
  'completion_rate': 0.28,
  'content_title': '用AI写周报被领导点名表扬',
  'likes': 380,
  'play_rate': 0.35,
  'shares': 110,
  'views': 6800},
 {'channel': '公众号',
  'collects': 60,
  'comments': 12,
  'completion_rate': 0.0,
  'content_title': '用AI写周报被领导点名表扬',
  'likes': 85,
  'play_rate': 0.0,
  'shares': 8,
  'views': 2100},
 {'channel': '问一问',
  'collects': 290,
  'comments': 45,
  'completion_rate': 0.0,
  'content_title': '用AI写周报被领导点名表扬',
  'likes': 140,
  'play_rate': 0.0,
  'shares': 60,
  'views': 3600}]

DEMO_ATTRIBUTION = {'channel_gap': '小红书收藏率高但曝光低于抖音，说明搜索词覆盖到位但缺爆款标题承接；公众号表现弱，长文改写得不够深。',
 'confidence': 'medium',
 'recommendations': ['下一轮视频脚本中段每10秒一个信息点，压缩方法段时长',
                     "小红书标题前20字替换为更高频搜索词（如'AI提效'）",
                     '公众号版本补充真实案例数据，提升完读率',
                     '问一问版本增加配图位，图片好看是红利奖励项'],
 'summary': '抖音收藏率高验证了显性收藏指令策略，下一步优化完播率与小红书搜索词。',
 'top_channel': '抖音（总曝光 3.2 万，收藏率最高），原因是收藏指令显性 + 3秒钩子开头，符合抖音收藏率第一权重。',
 'weak_dimension': '完播率（31%，低于均值），前5秒钩子强度足够但中段节奏偏慢，信息点密度不够。'}

# ─────────────────────────────────────────────
# M2 延伸：视频生成提示词（按模型返回）
# ─────────────────────────────────────────────
DEMO_VIDEO_GEN_PROMPTS = {'Seedance': {'checks': {'structure': {'expected_shot_count': 6,
                                       'issues': [],
                                       'passed': True,
                                       'shot_count': 6}},
              'global_style_prompt': '年轻职场女性，浅色办公场景，真实摄影感，人物与场景全程保持一致，音画一体。',
              'model': 'Seedance',
              'model_tips': ['提示词可直接粘贴到对应模型生成', '多镜头建议逐段生成后拼接'],
              'shots': [{'audio_instruction': '口播：（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。字幕：（钩子段字幕）周报被领导点名表扬。',
                         'shot_index': 1,
                         'time_range': '0s-5s'},
                        {'audio_instruction': '口播：（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：痛点，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。字幕：（痛点段字幕）写周报像流水账？。',
                         'shot_index': 2,
                         'time_range': '5s-15s'},
                        {'audio_instruction': '口播：（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：方法一，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。字幕：（方法一段字幕）第1招：给AI角色设定。',
                         'shot_index': 3,
                         'time_range': '15s-30s'},
                        {'audio_instruction': '口播：（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：方法二，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。字幕：（方法二段字幕）第2招：喂结构化素材。',
                         'shot_index': 4,
                         'time_range': '30s-45s'},
                        {'audio_instruction': '口播：（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：避坑，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。字幕：（避坑段字幕）第3招：追加追问+自己核对。',
                         'shot_index': 5,
                         'time_range': '45s-55s'},
                        {'audio_instruction': '口播：（结尾段口播）建议收藏，下次写周报直接翻出来用。。自动生成对口型音效与轻快背景音乐。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（结尾段口播）建议收藏，下次写周报直接翻出来用。。字幕：（结尾段字幕）建议收藏。',
                         'shot_index': 6,
                         'time_range': '55s-60s'}],
              'video_title': '用AI写周报被领导点名表扬，我的3个提示词技巧'},
 'Vidu': {'checks': {'structure': {'expected_shot_count': 6,
                                   'issues': [],
                                   'passed': True,
                                   'shot_count': 6}},
          'global_style_prompt': '以封面图为首帧，保持人物与场景一致，真实摄影感。',
          'model': 'Vidu',
          'model_tips': ['提示词可直接粘贴到对应模型生成', '多镜头建议逐段生成后拼接'],
          'shots': [{'audio_instruction': '口播：（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。字幕：（钩子段字幕）周报被领导点名表扬。',
                     'shot_index': 1,
                     'time_range': '0s-5s'},
                    {'audio_instruction': '口播：（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '场景：痛点，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。字幕：（痛点段字幕）写周报像流水账？。',
                     'shot_index': 2,
                     'time_range': '5s-15s'},
                    {'audio_instruction': '口播：（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '场景：方法一，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。字幕：（方法一段字幕）第1招：给AI角色设定。',
                     'shot_index': 3,
                     'time_range': '15s-30s'},
                    {'audio_instruction': '口播：（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '场景：方法二，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。字幕：（方法二段字幕）第2招：喂结构化素材。',
                     'shot_index': 4,
                     'time_range': '30s-45s'},
                    {'audio_instruction': '口播：（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '场景：避坑，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。字幕：（避坑段字幕）第3招：追加追问+自己核对。',
                     'shot_index': 5,
                     'time_range': '45s-55s'},
                    {'audio_instruction': '口播：（结尾段口播）建议收藏，下次写周报直接翻出来用。。旁白口播，背景音乐轻快。',
                     'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                     'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（结尾段口播）建议收藏，下次写周报直接翻出来用。。字幕：（结尾段字幕）建议收藏。',
                     'shot_index': 6,
                     'time_range': '55s-60s'}],
          'video_title': '用AI写周报被领导点名表扬，我的3个提示词技巧'},
 '可灵 Kling': {'checks': {'structure': {'expected_shot_count': 6,
                                       'issues': [],
                                       'passed': True,
                                       'shot_count': 6}},
              'global_style_prompt': '年轻职场女性，浅色办公场景，真实摄影感，人物与场景全程保持一致。',
              'model': '可灵 Kling',
              'model_tips': ['提示词可直接粘贴到对应模型生成', '多镜头建议逐段生成后拼接'],
              'shots': [{'audio_instruction': '口播：（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（钩子段口播）被领导点名表扬的周报，我只改了3个地方，这条视频建议收藏。。字幕：（钩子段字幕）周报被领导点名表扬。',
                         'shot_index': 1,
                         'time_range': '0s-5s'},
                        {'audio_instruction': '口播：（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：痛点，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（痛点段口播）很多人写周报像流水账，领导根本不看，问题出在没给AI设定角色。。字幕：（痛点段字幕）写周报像流水账？。',
                         'shot_index': 2,
                         'time_range': '5s-15s'},
                        {'audio_instruction': '口播：（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：方法一，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法一段口播）第一，给AI角色设定，让它当项目经理，输出立刻有重点。。字幕：（方法一段字幕）第1招：给AI角色设定。',
                         'shot_index': 3,
                         'time_range': '15s-30s'},
                        {'audio_instruction': '口播：（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：方法二，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（方法二段口播）第二，喂结构化素材，按完成/进行中/风险分类。。字幕：（方法二段字幕）第2招：喂结构化素材。',
                         'shot_index': 4,
                         'time_range': '30s-45s'},
                        {'audio_instruction': '口播：（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '场景：避坑，人物中景，屏幕演示AI周报界面。镜头运动：固定机位中景。（避坑段口播）第三，追加追问让进度量化，但数据和结论一定要自己核对。。字幕：（避坑段字幕）第3招：追加追问+自己核对。',
                         'shot_index': 5,
                         'time_range': '45s-55s'},
                        {'audio_instruction': '口播：（结尾段口播）建议收藏，下次写周报直接翻出来用。。背景音乐：轻快工作氛围。',
                         'negative_prompt': '画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁',
                         'prompt': '人物近景直面镜头。镜头运动：固定机位中景。（结尾段口播）建议收藏，下次写周报直接翻出来用。。字幕：（结尾段字幕）建议收藏。',
                         'shot_index': 6,
                         'time_range': '55s-60s'}],
              'video_title': '用AI写周报被领导点名表扬，我的3个提示词技巧'}}


_ROUTES = [
    ("数据整理专员", DEMO_STRUCTURED),          # Agent0 采集结构化
    ("资深运营专家", DEMO_FILTERED),            # Agent1 热点筛选
    ("爆款内容拆解专家", DEMO_ANALYZED),        # Agent2 爆款拆解
    ("内容策划专家", DEMO_TOPICS),              # Agent3 选题生成
    ("专属文案写手", DEMO_COPY),                # Agent4 文案生成（纯文本）
    ("爆款内容评审专家", DEMO_NOTE_SCORE),      # 笔记爆款分析
    ("竞品分析专家", DEMO_ACCOUNT_ANALYSIS),    # 竞品账号分析
    ("内容趋势分析师", DEMO_TREND_SUMMARY),     # 热门内容趋势
    ("标题优化专家", DEMO_TITLES),              # 标题生成
    ("标题评审专家", DEMO_TITLE_SCORES),        # 标题评分
    ("流量分发策略专家", DEMO_HASHTAGS),        # 标签推荐
    ("内容识别专家", DEMO_IMAGE_EXTRACT),       # 截图内容提取
    ("搜索引擎优化", DEMO_SEARCH_KEYWORDS),     # M1 搜索词分析
    ("内容封面设计师", DEMO_COVER_PROMPT),      # M1 封面提示词
    ("自媒体内容专家", DEMO_PLATFORM_COPY),     # M1 平台化正文改写
    ("短视频导演", DEMO_VIDEO_STORYBOARD),      # M2 分镜脚本
    ("播放优化", DEMO_VIDEO_PLAY),              # M2 播放优化
    ("视频互动运营", DEMO_VIDEO_INTERACTION),   # M2 视频互动策略（需在"互动运营专家"之前，避免子串误匹配）
    ("互动运营专家", DEMO_INTERACTION_COPY),    # M1 互动话术
    ("内容合规审核", DEMO_COMPLIANCE),          # M3 合规检查
    ("跨平台自媒体", _channel_rewrite_demo),    # M3 渠道改写（按目标平台返回不同版本）
    ("数据驱动内容策略", DEMO_ATTRIBUTION),     # M4 爆款归因解读
    ("视频生成提示词", _video_gen_demo),        # M2 延伸 视频生成提示词
]


def is_demo_mode() -> bool:
    """是否处于演示模式：环境变量 XHS_DEMO_MODE=1，或 Streamlit 会话里打开了演示开关。"""
    if os.environ.get("XHS_DEMO_MODE") == "1":
        return True
    try:
        import streamlit as st
        return bool(st.session_state.get("demo_mode", False))
    except Exception:
        return False




def get_demo_response(system_prompt: str, user_prompt: str) -> str:
    """
    根据 system_prompt 匹配内置示例数据，返回字符串。
    copywriter 返回纯文本，其余返回 JSON 字符串（call_llm_json 会再解析）。
    匹配不到时抛异常，避免静默返回错误数据掩盖问题。
    """
    for keyword, payload in _ROUTES:
        if keyword in system_prompt:
            if callable(payload):
                return payload(system_prompt, user_prompt)
            if isinstance(payload, str):
                return payload
            return json.dumps(payload, ensure_ascii=False)
    raise RuntimeError(
        f"演示模式下未找到匹配的示例数据。system_prompt 前80字: {system_prompt[:80]}"
    )


def render_demo_toggle() -> bool:
    """
    Streamlit 侧栏组件：演示模式开关。
    返回当前是否处于演示模式，并同步写入 st.session_state["demo_mode"]。
    """
    import streamlit as st

    default_on = os.environ.get("XHS_DEMO_MODE") == "1"
    demo = st.toggle(
        "演示模式（无需 API Key）",
        value=default_on,
        help="开启后所有 AI 调用返回内置示例结果，用于流程演示和离线体验。",
    )
    st.session_state["demo_mode"] = demo
    if demo:
        st.info("演示模式已开启：AI 调用返回内置示例数据，可完整跑通流程。")
    return demo
