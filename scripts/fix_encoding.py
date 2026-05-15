import codecs
import os

def fix_file_encoding(filepath):
    """修复文件编码问题"""
    # 读取文件内容（假设当前是UTF-8但被错误显示）
    with open(filepath, 'rb') as f:
        raw_bytes = f.read()
    
    # 尝试用 UTF-8 解码
    try:
        content = raw_bytes.decode('utf-8')
        print(f"文件 {filepath} 已经是正确的 UTF-8 编码")
        return True
    except UnicodeDecodeError:
        pass
    
    # 尝试用 GBK 解码（可能是被错误保存为 GBK 了）
    try:
        content = raw_bytes.decode('gbk')
        # 重新用 UTF-8 保存
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"文件 {filepath} 已从 GBK 转换为 UTF-8")
        return True
    except UnicodeDecodeError:
        pass
    
    print(f"无法确定文件 {filepath} 的编码")
    return False

# 修复 main.py
main_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api', 'main.py')
fix_file_encoding(main_file)
