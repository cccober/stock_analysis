import os



import re



import glob







def find_all_py_files():



    """查找所有 Python 文件"""



    files = []



    for root, dirs, filenames in os.walk(os.path.join(os.path.dirname(__file__), '..')):



        # 排除 .git 和 __pycache__



        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv', 'venv']]



        for f in filenames:



            if f.endswith('.py'):



                files.append(os.path.join(root, f))



    return files







    with open(filepath, 'rb') as f:



        content = f.read()



    



    try:



        text = content.decode('utf-8')



    except:



        return False



    



    original = text



    



    lines = text.split('\n')



    new_lines = []



    removed = False



    for line in lines:



            removed = True



            continue



        new_lines.append(line)



    



    if removed:



        with open(filepath, 'w', encoding='utf-8') as f:



            f.write('\n'.join(new_lines))



        return True



    return False







    """删除 test 数据库相关代码"""



    with open(filepath, 'rb') as f:



        content = f.read()



    



    try:



        text = content.decode('utf-8')



    except:



        return False



    



    original = text



    removed = False



    



    # 删除包含 test 数据库的行



    lines = text.split('\n')



    new_lines = []



    for line in lines:



        lower_line = line.lower()



            if 'duckdb' in lower_line or 'db' in lower_line or 'database' in lower_line:



                print(f"  删除 test DB 行: {line.strip()[:80]}")



                removed = True



                continue



        new_lines.append(line)



    



    if removed:



        with open(filepath, 'w', encoding='utf-8') as f:



            f.write('\n'.join(new_lines))



        return True



    return False







def fix_mojibake_in_file(filepath):



    """修复文件中的乱码"""



    with open(filepath, 'rb') as f:



        raw = f.read()



    



    try:



        text = raw.decode('utf-8')



    except:



        return False



    



    # 检查是否包含 GBK 乱码特征字符



    # GBK 乱码通常包含这些字符范围



    garbled_chars = set()



    for char in text:



        code = ord(char)



        # GBK 乱码常见范围



        if 0x4e00 <= code <= 0x9fff:



            # 正常中文字符，跳过



            continue



        elif code > 0x9fff:



            # 可能是乱码字符



            garbled_chars.add(char)



    



    if not garbled_chars:



        return False



    



    # 定义乱码映射



    fixes = {



        '底部': '底部',



        '状态栏': '状态栏',



        '工作区': '工作区',



        '数据': '数据',



        '查询': '查询',



        '分析': '分析',



        '因子': '因子',



        '收藏': '收藏',



        '股票': '股票',



        '搜索': '搜索',



        '查看': '查看',



        '日历': '日历',



        '月线': '月线',



        '周线': '周线',



        '日线': '日线',



        '同步': '同步',



        '设置': '设置',



        '超级': '超级',



        '图表': '图表',



        '左侧': '左侧',



        '面板': '面板',



        '顶部': '顶部',



        '栏目': '栏目',



        '消息': '消息',



        '资讯': '资讯',



        '讯中': '讯中',



        '心中': '心中',



        '新闻': '新闻',



        '时间': '时间',



        '价格': '价格',



        '涨跌': '涨跌',



        '成交': '成交',



        '量价': '量价',



        '指标': '指标',



        '技术': '技术',



        '显示': '显示',



        '记录': '记录',



        '区域': '区域',



        '基本': '基本',



        '信息': '信息',



        '成功': '成功',



        '失败': '失败',



        '获取': '获取',



        '名称': '名称',



        '日期': '日期',



        '开始': '开始',



        '结束': '结束',



        '最新': '最新',



        '最近': '最近',



        '数量': '数量',



        '记录': '记录',



        '无法': '无法',



        '确定': '确定',



        '编码': '编码',



        '解码': '解码',



        '转换': '转换',



        '正确': '正确',



        '错误': '错误',



        '问题': '问题',



        '解决': '解决',



        '修复': '修复',



        '文件': '文件',



        '内容': '内容',



        '字符': '字符',



        '注释': '注释',



        '样式': '样式',



        '颜色': '颜色',



        '背景': '背景',



        '边框': '边框',



        '间隔': '间隔',



        '字号': '字号',



        '宽度': '宽度',



        '高度': '高度',



        '位置': '位置',



        '居中': '居中',



        '对齐': '对齐',



        '隐藏': '隐藏',



        '滑动': '滑动',



        '滚动': '滚动',



        '点击': '点击',



        '鼠标': '鼠标',



        '按钮': '按钮',



        '输入': '输入',



        '文本': '文本',



        '选项': '选项',



        '下拉': '下拉',



        '菜单': '菜单',



        '标签': '标签',



        '页面': '页面',



        '视图': '视图',



        '功能': '功能',



        '操作': '操作',



        '提示': '提示',



        '警告': '警告',



        '等待': '等待',



        '加载': '加载',



        '刷新': '刷新',



        '重试': '重试',



        '取消': '取消',



        '确认': '确认',



        '提交': '提交',



        '保存': '保存',



        '删除': '删除',



        '更改': '更改',



        '添加': '添加',



        '移除': '移除',



        '清除': '清除',



        '重置': '重置',



        '恢复': '恢复',



        '打开': '打开',



        '关闭': '关闭',



        '退出': '退出',



        '返回': '返回',



        '前进': '前进',



        '上一': '上一',



        '下一': '下一',



        '第一': '第一',



        '最后': '最后',



        '当前': '当前',



        '总数': '总数',



        '条数': '条数',



        '页数': '页数',



        '前一': '前一',



        '后一': '后一',



        '跳到': '跳到',



        '转到': '转到',



        '筛选': '筛选',



        '排序': '排序',



        '过滤': '过滤',



        '分类': '分类',



        '关键': '关键',



        '词汇': '词汇',



        '描述': '描述',



        '备注': '备注',



        '说明': '说明',



        '解释': '解释',



        '定义': '定义',



        '标题': '标题',



        '副标': '副标',



        '数字': '数字',



        '时区': '时区',



        '格式': '格式',



        '模板': '模板',



        '布局': '布局',



        '排列': '排列',



        '间距': '间距',



        '字体': '字体',



        '大小': '大小',



        '粗细': '粗细',



        '效果': '效果',



        '动画': '动画',



        '过渡': '过渡',



        '变化': '变化',



        '缩放': '缩放',



        '旋转': '旋转',



        '倒置': '倒置',



        '翻到': '翻到',



        '拖拽': '拖拽',



        '平移': '平移',



        '变形': '变形',



        '剪裁': '剪裁',



        '遮罩': '遮罩',



        '工具': '工具',



        '具栏': '具栏',



        '主内': '主内',



        '容区': '容区',



        '标签': '标签',



        '页 */': '页 */',



        '条 */': '条 */',



        '区 */': '区 */',



        '栏 */': '栏 */',



        '右侧': '右侧',



        '工具栏 */': '工具栏 */',



        '左侧栏目': '左侧栏目',



        '左侧面板': '左侧面板',



        '左侧瀹稿櫒': '左侧容器',



        '左侧内容': '左侧内容',



        '左侧区域': '左侧区域',



        '左侧栏目': '左侧栏目',



        '左侧选项': '左侧选项',



        '左侧菜单': '左侧菜单',



        '左侧标签': '左侧标签',



        '左侧按钮': '左侧按钮',



        '左侧鍥炬爣': '左侧图标',



        '左侧鍒楄〃': '左侧列表',



        '左侧面板': '左侧面板',



        '左侧工具': '左侧工具',



        '左侧瀵艰埅': '左侧导航',



        '左侧閫夋嫨': '左侧选择',



        '左侧显示': '左侧显示',



        '左侧隐藏': '左侧隐藏',



        '左侧灞曞紑': '左侧展开',



        '左侧鏀跺浘': '左侧收拢',



        '左侧鍥哄畾': '左侧固定',



        '左侧娴姩': '左侧浮动',



        '左侧缁濆': '左侧绝对',



        '左侧鐩稿': '左侧相对',



        '左侧居中': '左侧居中',



        '左侧对齐': '左侧对齐',



        '左侧间距': '左侧间距',



        '左侧边框': '左侧边框',



        '左侧背景': '左侧背景',



        '左侧颜色': '左侧颜色',



        '左侧字体': '左侧字体',



        '左侧字号': '左侧字号',



        '左侧宽度': '左侧宽度',



        '左侧高度': '左侧高度',



        '左侧位置': '左侧位置',



        '左侧大小': '左侧大小',



        '左侧粗细': '左侧粗细',



        '左侧样式': '左侧样式',



        '左侧效果': '左侧效果',



        '左侧动画': '左侧动画',



        '左侧过渡': '左侧过渡',



        '左侧变化': '左侧变化',



        '左侧转换': '左侧转换',



        '左侧缩放': '左侧缩放',



        '左侧旋转': '左侧旋转',



        '左侧翻到': '左侧翻到',



        '左侧拖拽': '左侧拖拽',



        '左侧平移': '左侧平移',



        '左侧变形': '左侧变形',



        '左侧剪裁': '左侧剪裁',



        '左侧遮罩': '左侧遮罩',



    }



    



    fixed_text = text



    fix_count = 0



    



    for garbled, correct in fixes.items():



        if garbled in fixed_text:



            fixed_text = fixed_text.replace(garbled, correct)



            fix_count += 1



    



    if fix_count > 0:



        with open(filepath, 'w', encoding='utf-8') as f:



            f.write(fixed_text)



        print(f"  修复了 {fix_count} 处乱码")



        return True



    return False







# 主程序



print("=" * 60)



print("开始清理和修复")



print("=" * 60)







files = find_all_py_files()



print(f"\n找到 {len(files)} 个 Python 文件\n")







total_mojibake = 0







for filepath in files:



    rel_path = os.path.relpath(filepath)



    modified = False



    



        modified = True



    



    if result_test:



        modified = True



    



    result_moji = fix_mojibake_in_file(filepath)



    if result_moji:



        total_mojibake += 1



        modified = True



    



    if modified:



        print(f"  [已修改] {rel_path}\n")







print("=" * 60)



print("清理和修复完成")



print("=" * 60)



print(f"修复乱码的文件数: {total_mojibake}")



