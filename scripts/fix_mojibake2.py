import os

def fix_remaining_mojibake(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    content = raw.decode('utf-8')
    
    # 剩余的乱码映射
    fixes = [
        ('鍙充晶面板', '右侧面板'),
        ('宸ュ叿鏍?*/', '工具栏 */'),
        ('鏍?*/', '栏 */'),
        ('椤?*/', '页 */'),
        ('鏉?*/', '条 */'),
        ('鍖?*/', '区 */'),
        ('涓诲唴瀹瑰尯', '主内容区'),
        ('工作区?', '工作区'),
    ]
    
    fixed_content = content
    fix_count = 0
    
    for garbled, correct in fixes:
        if garbled in fixed_content:
            fixed_content = fixed_content.replace(garbled, correct)
            fix_count += 1
            print(f"修复: {garbled} -> {correct}")
    
    if fix_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"\n总共修复 {fix_count} 处乱码")
    else:
        print("未发现新的乱码")
    
    return fix_count > 0

main_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api', 'main.py')
fix_remaining_mojibake(main_file)
