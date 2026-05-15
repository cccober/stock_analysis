import os

def find_garbled_comments(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # 查找所有 /* */ 注释
    idx = content.find(b'/*')
    count = 0
    found = []
    
    while idx != -1 and count < 100:
        end = content.find(b'*/', idx)
        if end == -1:
            break
        
        comment = content[idx:end+2]
        try:
            text = comment.decode('utf-8')
            # 检查是否包含 GBK 乱码特征字符
            garbled_chars = ['搴', '鐘', '宸', '鏁', '鏌', '鍒', '鍥', '鏀', '鑲', '鎼', 
                           '鏃', '鏈', '鍛', '鍚', '璁', '瓒', '闈', '椤', '鏍', '娑',
                           '璧', '蹇', '鏂', '浠', '鎴', '閲', '鎸', '鎶', '鏄', '鍖',
                           '鍩', '淇', '澶', '鑾', '寮', '缁', '鏉', '纭', '缂', '瑙',
                           '杞', '姝', '閿', '闂', '鍐', '瀛', '涓', '棰', '鑳', '杈',
                           '闂', '瀹', '楂', '浣', '灞', '瀵', '闅', '婊', '鐐', '榧',
                           '鎸', '杈', '閫', '鑿', '椤', '瑙', '鍔', '鎿', '鎻', '璀',
                           '绛', '鍔', '鍒', '鍙', '纭', '鏇', '娣', '绉', '娓', '鎭',
                           '鎵', '鍏', '閫', '杩', '鍓', '涓', '绗', '鏈', '褰', '鎬',
                           '鏉', '椤', '鍓', '鍚', '璺', '杞', '绛', '鎺', '杩', '鍒',
                           '鍏', '璇', '鎻', '澶', '璇', '瀹', '鏍', '鍓', '鏁', '鏃',
                           '妯', '甯', '闂', '澶', '绮', '鍊', '缈', '鎷', '骞', '鍓',
                           '閬', '瀹', '鍖']
            
            has_garbled = any(g in text for g in garbled_chars)
            
            if has_garbled:
                line_num = content[:idx].count(b'\n') + 1
                found.append((line_num, text))
        except:
            pass
        
        idx = content.find(b'/*', end + 2)
        count += 1
    
    return found

# 检查 main.py
main_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api', 'main.py')
results = find_garbled_comments(main_file)

if results:
    print(f"在 {main_file} 中找到 {len(results)} 处乱码注释:")
    for line_num, text in results:
        print(f"  行 {line_num}: {text}")
else:
    print("未找到乱码注释")
