import os


import re





def find_files_with_issues():


    


    for root, dirs, filenames in os.walk(os.path.join(os.path.dirname(__file__), '..')):


        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv', 'venv', 'node_modules']]


        


        for f in filenames:


            if not f.endswith('.py'):


                continue


            


            filepath = os.path.join(root, f)


            rel_path = os.path.relpath(filepath)


            


            try:


                with open(filepath, 'rb') as file:


                    content = file.read().decode('utf-8')


            except:


                continue


            


                lines = content.split('\n')


                for i, line in enumerate(lines, 1):


            


            # 检查 test db


            lower_content = content.lower()


                lines = content.split('\n')


                for i, line in enumerate(lines, 1):


                    lower_line = line.lower()


    


    return issues





    with open(filepath, 'rb') as f:


        content = f.read().decode('utf-8')


    


    lines = content.split('\n')


    new_lines = []


    removed = False


    


    for line in lines:


            removed = True


            continue


        new_lines.append(line)


    


    if removed:


        with open(filepath, 'w', encoding='utf-8') as f:


            f.write('\n'.join(new_lines))


    


    return removed





    """从文件中删除 test db 相关行"""


    with open(filepath, 'rb') as f:


        content = f.read().decode('utf-8')


    


    lines = content.split('\n')


    new_lines = []


    removed = False


    


    for line in lines:


        lower_line = line.lower()


            removed = True


            continue


        new_lines.append(line)


    


    if removed:


        with open(filepath, 'w', encoding='utf-8') as f:


            f.write('\n'.join(new_lines))


    


    return removed





# 主程序


print("=" * 60)


print("=" * 60)





issues = find_files_with_issues()





        print(f"  {filepath}:{line_num}: {line[:80]}")


        full_path = os.path.join(os.path.dirname(__file__), '..', filepath)


            print(f"    -> 已删除")


else:





    print("\n发现 test DB 引用:")


        print(f"  {filepath}:{line_num}: {line[:80]}")


        full_path = os.path.join(os.path.dirname(__file__), '..', filepath)


            print(f"    -> 已删除")


else:


    print("\n未发现 test DB 引用")





print("\n" + "=" * 60)


print("清理完成")


print("=" * 60)


